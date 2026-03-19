import asyncio
import uuid
from datetime import datetime, timezone

from models.task import create_task, update_task_status
from agent.planner import plan_task
from agent.loop import execute_agent_loop
from services.stream_manager import stream_manager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def start_task(goal: str) -> str:
    """
    Creates a task in DB and fires off background execution.

    Returns task_id immediately — client doesn't wait for execution.
    This is the async job pattern: submit → stream → result.
    """
    task_id = str(uuid.uuid4())
    created_at = _now()

    # Save task to DB immediately with status 'queued'
    await create_task(task_id, goal, created_at)

 

   
    asyncio.create_task(
        _run_task_background(task_id, goal)
    )

    return task_id


async def _run_task_background(task_id: str, goal: str):
    """
    Full execution pipeline run in background:
    1. Plan — ask LLM to break goal into steps
    2. Execute — run each step with tools
    3. Stream — emit events to SSE queue as steps run
    """

    
    cancel_event = asyncio.Event()

    _cancel_events[task_id] = cancel_event

    
    task_cache = {}

    try:
       
        await update_task_status(task_id, "planning")
        await stream_manager.publish(task_id, {
            "type": "planning",
            "message": "Breaking down your goal into steps..."
        })

        steps, prompt_used = await asyncio.get_event_loop().run_in_executor(
        None, plan_task, goal
        ) 

        await stream_manager.publish(task_id, {
            "type": "planned",
            "message": f"Plan ready — {len(steps)} steps to execute",
            "total_steps": len(steps)
        })

        
        async def emit(event: dict): # Helper to emit events from agent loop. though we used publish above for planning updates, we want to give the loop a simple emit function to send updates as it excetujes steps , it reduces coupling means the loop doesn't need to know about stream_manager, it just calls emit and the caller handles how to send it to lient, so we dont have to pu       
            await stream_manager.publish(task_id, event)

        await execute_agent_loop(
            task_id=task_id,
            goal=goal,
            steps=steps,
            prompt_used=prompt_used,
            emit=emit,
            cancel_event=cancel_event,
            cache=task_cache
        )

    except Exception as e:
        # Planning failed or unexpected error
        await update_task_status(
            task_id,
            status="failed",
            completed_at=_now(),
            error=str(e)
        )
        await stream_manager.publish(task_id, {
            "type": "failed",
            "error": str(e)
        })

    finally:
        await stream_manager.publish_done(task_id)
        stream_manager.cleanup(task_id)      # ← ADD THIS
        _cancel_events.pop(task_id, None)


def get_cancel_event(task_id: str) -> asyncio.Event | None:
    """
    Called by DELETE /tasks/{id} to cancel a running task.
    Returns None if task is not currently running.
    """
    return _cancel_events.get(task_id)



_cancel_events: dict[str, asyncio.Event] = {}  