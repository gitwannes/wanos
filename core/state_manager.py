import asyncio
from typing import Optional
from .models import SystemState, Event, EventType
from .mqtt_client import MqttClientManager

class StateManager:
    def __init__(self, mqtt_client: MqttClientManager):
        self._state = SystemState()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.mqtt_client = mqtt_client

    async def start(self):
        """Starts the background event consumer loop."""
        self._worker_task = asyncio.create_task(self._process_events())
        print("✅ State Manager worker started.")

    async def stop(self):
        """Cancels the consumer loop gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        print("🛑 State Manager worker stopped.")

    def dispatch(self, event: Event):
        """
        The ONLY way to influence state.
        Thread-safe: Safely bridges calls from hardware threads to the main async loop.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            # Fallback if called outside an active event loop
            self._queue.put_nowait(event)

    def get_state_snapshot(self) -> SystemState:
        """Returns a safe, read-only deep copy of the current state."""
        return self._state.model_copy(deep=True)

    async def _process_events(self):
        """The sequential event loop. Completely eliminates race conditions."""
        while True:
            event = await self._queue.get()
            try:
                await self._handle_event(event)
            except Exception as e:
                print(f"⚠️ Error handling event {event.type.value}: {e}")
            finally:
                self._queue.task_done()

    async def _handle_event(self, event: Event):
        """Business logic router. Mutates the private state and triggers broadcasts."""
        print(f"📥 Processing Event: {event.type.value} | {event.payload}")
        state_changed = False

        if event.type == EventType.INITIAL_STATE_LOADED:
            self._state.hardware_live_mode = False
            state_changed = True

        elif event.type == EventType.TEMP_UPDATED:
            new_temp = event.payload.get("value")
            if new_temp is not None and new_temp != self._state.sauna_temp:
                self._state.sauna_temp = new_temp
                state_changed = True
        
        else:
            print(f"⚠️ Unhandled event type: {event.type.value}")

        if state_changed:
            snapshot = self.get_state_snapshot().model_dump()
            print(f"📤 Broadcasting State: {snapshot}")
            await self.mqtt_client.publish("wisc/system/state", snapshot)