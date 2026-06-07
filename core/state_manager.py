# --- file: core/state_manager.py ---
import asyncio
from typing import Optional, Any
from .models import SystemState, Event, EventType
from .mqtt_client import MqttClientManager


class StateManager:
    def __init__(self, mqtt_client: MqttClientManager) -> None:
        self._state: SystemState = SystemState()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.mqtt_client: MqttClientManager = mqtt_client

    async def start(self) -> None:
        """Starts the background event consumer loop."""
        self._worker_task = asyncio.create_task(self._process_events())
        print("✅ State Manager worker started.")

    async def stop(self) -> None:
        """Cancels the consumer loop gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        print("🛑 State Manager worker stopped.")

    def dispatch(self, event: Event) -> None:
        """
        The ONLY way to influence state.
        Thread-safe: Safely bridges calls from hardware threads to the main async loop.
        """
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            # Fallback if called outside an active event loop
            self._queue.put_nowait(event)

    def get_state_snapshot(self) -> SystemState:
        """Returns a safe, read-only deep copy of the current state."""
        return self._state.model_copy(deep=True)

    async def _process_events(self) -> None:
        """The sequential event loop. Completely eliminates race conditions."""
        while True:
            event: Event = await self._queue.get()
            try:
                await self._handle_event(event)
            except Exception as e:
                print(f"⚠️ Error handling event {event.type.value}: {e}")
            finally:
                self._queue.task_done()

    async def _handle_event(self, event: Event) -> None:
        """Business logic router. Mutates the private state and triggers broadcasts."""
        print(f"📥 Processing Event: {event.type.value} | {event.payload}")
        state_changed: bool = False

        if event.type == EventType.INITIAL_STATE_LOADED:
            self._state.hardware.live_mode = False
            state_changed = True

        elif event.type == EventType.TEMP_UPDATED:
            new_temp: Optional[float] = event.payload.get("value")
            # Nested dot notation applied here
            if new_temp is not None and new_temp != self._state.sauna.current_temp:
                self._state.sauna.current_temp = new_temp
                state_changed = True

        # --- SAUNA LOGIC COMMANDS ---
        elif event.type == EventType.SAUNA_ON:
            if not self._state.sauna.active:
                self._state.sauna.active = True
                state_changed = True
                print("🔥 Sauna activated!")

        elif event.type == EventType.SAUNA_OFF:
            if self._state.sauna.active:
                self._state.sauna.active = False
                self._state.sauna.modulation_pwm = 0  # Safety: kill the heater when turned off
                state_changed = True
                print("❄️ Sauna deactivated!")

        elif event.type == EventType.SETPOINT_CHANGED:
            new_target: Optional[float] = event.payload.get("target")
            if new_target is not None and new_target != self._state.sauna.target_temp:
                self._state.sauna.target_temp = new_target
                state_changed = True
                print(f"🎯 Setpoint changed to {new_target}°C")

        else:
            print(f"⚠️ Unhandled event type: {event.type.value}")

        if state_changed:
            snapshot: dict[str, Any] = self.get_state_snapshot().model_dump()
            print(f"📤 Broadcasting State: {snapshot}")
            await self.mqtt_client.publish("wisc/system/state", snapshot)