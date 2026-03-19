import asyncio
from typing import Dict, List


class StreamManager:
    """
    Manages one list of queues per task.
    Each connected client gets their own personal queue.
    Agent loop publishes to ALL queues simultaneously.
    Past events stored in history for reconnecting clients.
    """

    def __init__(self):
        # task_id → list of queues (one per connected client)
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        # task_id → list of past events (for reconnect replay)
        self._history: Dict[str, list] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """
        Called when a client connects.
        Creates personal queue for this client.
        Replays all past events so reconnecting clients catch up.
        """
        queue = asyncio.Queue()

        if task_id not in self._subscribers:
            self._subscribers[task_id] = []

        # replay past events into new queue immediately
        for past_event in self._history.get(task_id, []):
            queue.put_nowait(past_event)

        self._subscribers[task_id].append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        """
        Called when a client disconnects.
        Removes only THIS client's queue.
        Other connected clients are unaffected.
        """
        subscribers = self._subscribers.get(task_id, [])
        if queue in subscribers:
            subscribers.remove(queue)

    async def publish(self, task_id: str, event: dict):
        """
        Agent loop calls this to emit an event.
        Stores in history AND sends to all connected clients.
        """
        # store in history for future reconnects
        if task_id not in self._history:
            self._history[task_id] = []
        self._history[task_id].append(event)

        # send to every connected client
        for queue in self._subscribers.get(task_id, []):
            await queue.put(event)

    async def publish_done(self, task_id: str):
        """
        Signal stream finished to ALL connected clients.
        """
        for queue in self._subscribers.get(task_id, []):
            await queue.put(None)

    def cleanup(self, task_id: str):
        """
        Called after task fully completes.
        Removes all queues and history for this task.
        """
        self._subscribers.pop(task_id, None)
        self._history.pop(task_id, None)


stream_manager = StreamManager()