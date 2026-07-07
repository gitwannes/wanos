# --- logic/timers.py ---
import asyncio
import time
import logging
from typing import Callable, Dict, Awaitable

logger = logging.getLogger(__name__)

class TimerManager:
    """
    Manages asynchronous sleep tasks based on absolute Unix timestamps.
    When a deadline is reached, it fires an event back into the central queue.
    """
    def __init__(self, dispatch_callback: Callable[[str, dict], Awaitable[None]]):
        # This callback is usually `state_manager._handle_event` or a queue `put` method
        self._dispatch = dispatch_callback
        self._tasks: Dict[str, asyncio.Task] = {}

    def schedule(self, timer_id: str, deadline: int, event_type: str, payload: dict = None):
        """Schedules a new sleep task, cancelling any existing task with the same ID."""
        self.cancel(timer_id)
        
        # Spawn the background sleeper task
        task = asyncio.create_task(
            self._sleep_and_fire(timer_id, deadline, event_type, payload or {})
        )
        self._tasks[timer_id] = task
        logger.debug(f"Timer '{timer_id}' scheduled for deadline {deadline}.")

    def cancel(self, timer_id: str):
        """Safely cancels an active sleep task."""
        if timer_id in self._tasks:
            self._tasks[timer_id].cancel()
            del self._tasks[timer_id]
            logger.debug(f"Timer '{timer_id}' cancelled.")

    def is_scheduled(self, timer_id: str) -> bool:
        """Checks if a timer is actively scheduled and has not yet completed."""
        task = self._tasks.get(timer_id)
        # Verify the key exists and that the async task hasn't finished execution
        return task is not None and not task.done()

    async def _sleep_and_fire(self, timer_id: str, deadline: int, event_type: str, payload: dict):
        """The internal worker that sleeps until the deadline and dispatches the event."""
        # Capture the specific async task object running this execution
        my_task = asyncio.current_task()
        try:
            now = int(time.time())
            sleep_duration = max(0, deadline - now)

            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)

            # The sleep finished without being cancelled. The deadline is reached!
            logger.debug(f"Timer '{timer_id}' expired. Firing {event_type}.")
            await self._dispatch(event_type, payload)

        except asyncio.CancelledError:
            # The task was cancelled intentionally (e.g., the user adjusted the time or turned the sauna off)
            pass
        finally:
            # Clean up the task reference, but ONLY if this exact task is still the active owner
            # This prevents orphaned/cancelled tasks from deleting newly scheduled replacements!
            if self._tasks.get(timer_id) == my_task:
                del self._tasks[timer_id]