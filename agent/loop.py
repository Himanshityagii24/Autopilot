import re
import asyncio
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from core.config import settings
from agent.tools.registry import get_tool
from models.step import create_step, update_step, create_artifact
from models.task import update_task_status


async def run_tool_with_retry(
    tool_fn: Callable,
    tool_input,
    task_id: str,
    step_number: int,
) -> tuple[str, int]:
    """
    Runs a tool with exponential backoff retry.
    Bonus: max 3 attempts, delay doubles each time (1s → 2s → 4s)
    """
    last_error = None

    for attempt in range(1, settings.max_retry_attempts + 1):
        try:
            loop = asyncio.get_event_loop()

            if isinstance(tool_input, tuple):
                output = await loop.run_in_executor(None, lambda: tool_fn(*tool_input))
            else:
                output = await loop.run_in_executor(None, tool_fn, tool_input)

            return output, attempt

        except Exception as e:
            last_error = e
            if attempt < settings.max_retry_attempts:
                delay = settings.retry_base_delay * (2 ** (attempt - 1))
                print(f"  Warning: Step {step_number} attempt {attempt} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"Tool failed after {settings.max_retry_attempts} attempts. "
        f"Last error: {last_error}"
    )


def parse_tool_input(tool_name: str, raw_input: str):
    """
    Parse and clean tool input based on tool name.
    Handles all cases where LLM gives malformed inputs.
    """
    
    raw_input = raw_input.strip().replace("\r", "")

    if tool_name == "write_file":
        if "," in raw_input:
            parts = raw_input.split(",", 1)
            filename = parts[0].strip().strip("'\"").strip()
            content  = parts[1].strip()

            
            if len(filename) > 50 or " " in filename or "\n" in filename:
                return ("output.md", raw_input)

            
            filename = re.sub(r'[<>:"/\\|?*\n\r]', '', filename).strip()
            if not filename:
                filename = "output.md"

            
            if "." not in filename:
                filename = filename + ".md"

            return (filename, content)
        else:
            
            return ("output.md", raw_input)

    if tool_name == "http_get":
        url = raw_input.strip().strip("'\"").strip()
        
        url = url.split("\n")[0].strip()

        
        if len(url) > 300 or (" " in url[:30] and "://" not in url[:30]):
            raise ValueError(f"http_get received text instead of a URL — skipping this step")

        
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        return url

    if tool_name == "read_file":
        filename = raw_input.strip().strip("'\"").strip()
        filename = filename.split("\n")[0].strip()
        # Remove artifacts\ prefix if LLM adds it
        filename = filename.replace("artifacts\\", "").replace("artifacts/", "")
        return filename

    if tool_name == "web_search":
        # Remove newlines, keep query clean
        query = raw_input.replace("\n", " ").strip()
        # Truncate overly long queries
        return query[:200]

    if tool_name == "summarize":
        return raw_input.strip()

    return raw_input


async def execute_agent_loop(
    task_id: str,
    goal: str,
    steps: list[dict],
    prompt_used: str,
    emit: Callable,
    cancel_event: asyncio.Event,
    cache: Optional[dict] = None
):
    """
    Core agent execution loop.

    For each planned step:
    1. Check if cancelled
    2. Resolve tool from registry
    3. Check cache (bonus)
    4. Emit 'running' event to SSE stream
    5. Write step to DB as 'running'
    6. Execute tool with retry (bonus)
    7. Update DB with result
    8. Emit 'done' or 'failed' event
    9. Store artifact if write_file tool was used
    """

    if cache is None:
        cache = {}

    step_outputs: dict[int, str] = {}

    try:
        await update_task_status(task_id, "running")

        for step in steps:

            if cancel_event.is_set():
                await update_task_status(
                    task_id,
                    status="cancelled",
                    completed_at=_now()
                )
                await emit({
                    "type": "cancelled",
                    "message": "Task was cancelled"
                })
                return

            step_number = step["step_number"]
            tool_name   = step["tool"]
            tool_input  = step["input"]

            for ref_step, ref_output in step_outputs.items():
                tool_input = tool_input.replace(
                    f"output_of_step_{ref_step}",
                    ref_output[:500]
                )

            tool_fn = get_tool(tool_name)
            if not tool_fn:
                error_msg = f"Unknown tool: {tool_name}"
                await update_step(task_id, step_number, status="failed", output=error_msg)
                await emit({
                    "step": step_number, "tool": tool_name,
                    "status": "failed", "error": error_msg
                })
                continue

            try:
                parsed_input = parse_tool_input(tool_name, tool_input)
            except ValueError as e:
                error_msg = str(e)
                await create_step(task_id, step_number, tool_name,
                                  str(tool_input)[:2000], prompt_used)
                await update_step(task_id, step_number,
                                  status="failed", output=error_msg,
                                  duration_ms=0, attempt=1)
                await emit({
                    "step": step_number, "tool": tool_name,
                    "input": tool_input, "status": "failed",
                    "error": error_msg
                })
                continue

            cache_key = f"{tool_name}:{tool_input}"
            if settings.cache_enabled and cache_key in cache:
                cached_output = cache[cache_key]
                print(f"Cache hit for step {step_number} - {tool_name}")

                await create_step(task_id, step_number, tool_name,
                                  str(tool_input)[:2000], prompt_used)
                await update_step(
                    task_id, step_number,
                    status="done", output=f"[CACHED] {cached_output}",
                    duration_ms=0, attempt=1
                )
                await emit({
                    "step": step_number, "tool": tool_name,
                    "input": tool_input, "output": cached_output,
                    "status": "done", "duration_ms": 0, "cached": True
                })
                step_outputs[step_number] = cached_output
                continue

            await emit({
                "step": step_number, "tool": tool_name,
                "input": tool_input, "status": "running"
            })

            await create_step(task_id, step_number, tool_name,
                              str(tool_input)[:2000], prompt_used)

            start_ms = time.time()
            try:
                output, attempt_used = await run_tool_with_retry(
                    tool_fn, parsed_input, task_id, step_number
                )
                duration_ms = int((time.time() - start_ms) * 1000)

                if settings.cache_enabled:
                    cache[cache_key] = output

                await update_step(
                    task_id, step_number,
                    status="done", output=output,
                    duration_ms=duration_ms, attempt=attempt_used
                )

                if tool_name == "write_file":
                    if isinstance(parsed_input, tuple):
                        filename = parsed_input[0]
                    else:
                        filename = tool_input.split(",")[0].strip().strip("'\"").strip()

                    await create_artifact(
                        task_id=task_id,
                        filename=filename,
                        file_path=output,
                        created_at=_now()
                    )

                await emit({
                    "step": step_number, "tool": tool_name,
                    "input": tool_input, "output": output,
                    "status": "done", "duration_ms": duration_ms,
                    "attempt": attempt_used
                })

                step_outputs[step_number] = output

            except Exception as e:
                duration_ms = int((time.time() - start_ms) * 1000)
                error_msg = str(e)

                await update_step(
                    task_id, step_number,
                    status="failed", output=error_msg,
                    duration_ms=duration_ms,
                    attempt=settings.max_retry_attempts
                )
                await emit({
                    "step": step_number, "tool": tool_name,
                    "status": "failed", "error": error_msg,
                    "duration_ms": duration_ms
                })
         
        await update_task_status(task_id, status="completed", completed_at=_now())
        await emit({"type": "completed", "message": "All steps completed successfully"})

    except Exception as e:
        await update_task_status(
            task_id, status="failed",
            completed_at=_now(), error=str(e)
        )
        await emit({"type": "failed", "error": str(e)})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()