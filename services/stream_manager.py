import asyncio
from typing import Dict


class StreamManager:
    """
    Manages one asyncio Queue per task.

    Agent loop  →  puts events into queue
    SSE endpoint →  gets events from queue and sends to client

    This decouples the agent execution from the HTTP streaming layer.
    """

    def __init__(self):
        # task_id → asyncio.Queue
        self._queues: Dict[str, asyncio.Queue] = {}

    def create_queue(self, task_id: str) -> asyncio.Queue:
        """Create a new queue for a task. Called when task is created."""
        queue = asyncio.Queue()
        self._queues[task_id] = queue
        return queue

    def get_queue(self, task_id: str) -> asyncio.Queue | None:
        """Get existing queue for a task. Returns None if not found."""
        return self._queues.get(task_id)

    async def publish(self, task_id: str, event: dict):
        """
        Agent loop calls this to emit an event.
        Puts event into the task's queue.
        """
        queue = self._queues.get(task_id)
        if queue:
            await queue.put(event)

    async def publish_done(self, task_id: str):
        """
        Signal that the stream is finished.
   
        """
        queue = self._queues.get(task_id)
        if queue:
            await queue.put(None)

    def remove_queue(self, task_id: str):
        """Clean up queue after streaming is done."""
        self._queues.pop(task_id, None)



stream_manager = StreamManager()