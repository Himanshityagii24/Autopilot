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
    tool_input: str,
    task_id: str,
    step_number: int,
) -> tuple[str, int]:
    """
    Runs a tool with exponential backoff retry.
    Bonus: max 3 attempts, delay doubles each time (1s → 2s → 4s)

    Returns:
        output      : tool result string
        attempt_used: which attempt succeeded (1, 2, or 3)
    """
    last_error = None

    for attempt in range(1, settings.max_retry_attempts + 1):
        try:
            # Tools are sync functions — run in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, tool_fn, tool_input)
            return output, attempt

        except Exception as e:
            last_error = e
            if attempt < settings.max_retry_attempts:
                delay = settings.retry_base_delay * (2 ** (attempt - 1))
                print(f"  ⚠️  Step {step_number} attempt {attempt} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"Tool failed after {settings.max_retry_attempts} attempts. "
        f"Last error: {last_error}"
    )


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
    3. Check cache 
    4. Emit 'running' event to SSE stream
    5. Write step to DB as 'running'
    6. Execute tool with retry 
    7. Update DB with result
    8. Emit 'done' or 'failed' event
    9. Store artifact if write_file tool was used

    Args:
        task_id     : UUID of the task
        goal        : Original natural language goal
        steps       : List of planned steps from planner
        prompt_used : Exact planning prompt — stored per step for reproducibility
        emit        : Async callable to push SSE events to client
        cancel_event: asyncio.Event — checked before each step
        cache       : Dict for tool result caching — key is "tool:input"
    """

    if cache is None:
        cache = {}

    # Track outputs so steps can reference previous step results
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
                await update_step(
                    task_id, step_number,
                    status="failed", output=error_msg
                )
                await emit({
                    "step": step_number,
                    "tool": tool_name,
                    "status": "failed",
                    "error": error_msg
                })
                continue   
            
            cache_key = f"{tool_name}:{tool_input}"
            if settings.cache_enabled and cache_key in cache:
                cached_output = cache[cache_key]
                print(f"Cache hit for step {step_number} — {tool_name}")

                await create_step(
                    task_id, step_number, tool_name,
                    tool_input, prompt_used
                )
                await update_step(
                    task_id, step_number,
                    status="done",
                    output=f"[CACHED] {cached_output}",
                    duration_ms=0,
                    attempt=1
                )
                await emit({
                    "step": step_number,
                    "tool": tool_name,
                    "input": tool_input,
                    "output": cached_output,
                    "status": "done",
                    "duration_ms": 0,
                    "cached": True
                })
                step_outputs[step_number] = cached_output
                continue

            
            await emit({
                "step": step_number,
                "tool": tool_name,
                "input": tool_input,
                "status": "running"
            })

            
            await create_step(
                task_id, step_number, tool_name,
                tool_input, prompt_used
            )

            
            start_ms = time.time()
            try:
                output, attempt_used = await run_tool_with_retry(
                    tool_fn, tool_input, task_id, step_number
                )
                duration_ms = int((time.time() - start_ms) * 1000)

                
                if settings.cache_enabled:
                    cache[cache_key] = output

                
                await update_step(
                    task_id, step_number,
                    status="done",
                    output=output,
                    duration_ms=duration_ms,
                    attempt=attempt_used
                )

                
                if tool_name == "write_file":
                    filename = tool_input.split(",")[0].strip() if "," in tool_input else tool_input
                    filename = filename.strip("'\"").strip()
                    await create_artifact(
                        task_id=task_id,
                        filename=filename,
                        file_path=output,
                        created_at=_now()
                    )

                
                await emit({
                    "step": step_number,
                    "tool": tool_name,
                    "input": tool_input,
                    "output": output,
                    "status": "done",
                    "duration_ms": duration_ms,
                    "attempt": attempt_used
                })

                step_outputs[step_number] = output

            except Exception as e:
                duration_ms = int((time.time() - start_ms) * 1000)
                error_msg = str(e)

                await update_step(
                    task_id, step_number,
                    status="failed",
                    output=error_msg,
                    duration_ms=duration_ms,
                    attempt=settings.max_retry_attempts
                )

                await emit({
                    "step": step_number,
                    "tool": tool_name,
                    "status": "failed",
                    "error": error_msg,
                    "duration_ms": duration_ms
                })
                

       
        await update_task_status(
            task_id,
            status="completed",
            completed_at=_now()
        )
        await emit({
            "type": "completed",
            "message": "All steps completed successfully"
        })

    except Exception as e:
        
        await update_task_status(
            task_id,
            status="failed",
            completed_at=_now(),
            error=str(e)
        )
        await emit({
            "type": "failed",
            "error": str(e)
        })


def _now() -> str:
    """Returns current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()