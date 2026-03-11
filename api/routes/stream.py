import json
import asyncio
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models.task import get_task
from services.stream_manager import stream_manager

router = APIRouter(prefix="/tasks", tags=["Stream"])


@router.get("/{task_id}/stream")
async def stream_task(task_id: str):
    """
    Stream live execution progress using Server-Sent Events.
    Each agent step is emitted as it happens — not buffered.

    Connect with:
        curl -N http://localhost:8000/tasks/{task_id}/stream
    """
    row = await get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # If task already completed, return its steps as a replay
    if row["status"] in ("completed", "failed", "cancelled"):
        async def completed_stream():
            yield {
                "data": json.dumps({
                    "type": row["status"],
                    "message": f"Task already {row['status']}"
                })
            }
        return EventSourceResponse(completed_stream())

    queue = stream_manager.get_queue(task_id)
    if not queue:
        raise HTTPException(
            status_code=404,
            detail="Stream not available for this task"
        )

    async def event_generator():
        """
        Reads from the task's queue and yields SSE events.
        Stops when it receives None (sentinel) from the agent loop.
        """
        try:
            while True:
                try:
                    # Wait for next event with timeout
                    # Timeout prevents hanging connections if agent crashes
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=120.0
                    )

                    # None is the sentinel — agent loop is done
                    if event is None:
                        yield {"data": json.dumps({"type": "done"})}
                        break

                    yield {"data": json.dumps(event)}

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield {"data": json.dumps({"type": "heartbeat"})}

        except asyncio.CancelledError:
            # Client disconnected — clean up
            pass
        finally:
            stream_manager.remove_queue(task_id)

    return EventSourceResponse(event_generator())