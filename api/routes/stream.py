import json
import asyncio
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models.task import get_task
from models.step import get_steps
from services.stream_manager import stream_manager

router = APIRouter(prefix="/tasks", tags=["Stream"])


@router.get("/{task_id}/stream")
async def stream_task(task_id: str):
    row = await get_task(task_id)  
    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Task already finished — replay steps as stream events
    if row["status"] in ("completed", "failed", "cancelled"):
        steps = await get_steps(task_id)

        async def replay_stream():
            for s in steps:
                yield {  #yield sends one SSE event to the client.
                    "data": json.dumps({
                        "step": s["step_number"],
                        "tool": s["tool_name"],
                        "input": s["input"],
                        "output": s["output"],
                        "status": s["status"],
                        "duration_ms": s["duration_ms"],
                        "attempt": s["attempt"]
                    })
                }
            yield {
                "data": json.dumps({
                    "type": row["status"],
                    "message": f"Task {row['status']}"
                })
            }
            yield {"data": json.dumps({"type": "done"})}

        return EventSourceResponse(replay_stream())

    # Task still running — stream live from queue
    queue = stream_manager.subscribe(task_id)
    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0) #here queue gets a new event from the agent loop, which is put there by stream_manager.publish() in task_runner.py. If no new event 
                    if event is None:
                        yield {"data": json.dumps({"type": "done"})}
                        break
                    yield {"data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"data": json.dumps({"type": "heartbeat"})}
        except asyncio.CancelledError:
            pass
        finally:
            stream_manager.unsubscribe(task_id, queue)

    return EventSourceResponse(event_generator())
