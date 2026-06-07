# --- file: core/state_manager.py ---
import asyncio
from typing import Optional, Any
from .models import SystemState, Event, EventType
from .mqtt_client import MqttClientManager
from .logger import WanosLogger
from .config import load_config
from logic.sauna_controller import SaunaController


class StateManager:
    def __init__(self, mqtt_client: MqttClientManager, logger: WanosLogger) -> None:
        self._state: SystemState = SystemState()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.mqtt_client: MqttClientManager = mqtt_client
        self.logger: WanosLogger = logger

        # 1. Read config.yaml and inject the default setpoint into the Vault
        app_config = load_config()
        self._state.sauna.target_temp = float(app_config.sauna.default_setpoint)

        # Boot the Brain with the freshly loaded configuration values
        self.sauna_logic = SaunaController(
            initial_target_temp=self._state.sauna.target_temp,
            kp=app_config.sauna.kp,
            ki=app_config.sauna.ki,
            kd=app_config.sauna.kd
        )

    async def start(self) -> None:
        """Starts the background event consumer loop."""
        self._worker_task = asyncio.create_task(self._process_events())
        await self.logger.success("State Manager worker started.")

    async def stop(self) -> None:
        """Cancels the consumer loop gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.logger.warning("State Manager worker stopped.")

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
                await self.logger.error(f"Error handling event {event.type.value}: {e}")
            finally:
                self._queue.task_done()

    async def _handle_event(self, event: Event) -> None:
        """Business logic router. Mutates the private state and triggers broadcasts."""
        await self.logger.debug(f"Processing Event: {event.type.value} | {event.payload}")
        state_changed: bool = False

        if event.type == EventType.INITIAL_STATE_LOADED:
            self._state.hardware.live_mode = False
            state_changed = True

        elif event.type == EventType.TEMP_UPDATED:
            new_temp: Optional[float] = event.payload.get("value")
            if new_temp is not None and new_temp != self._state.sauna.current_temp:
                self._state.sauna.current_temp = new_temp
                state_changed = True

        # --- SAUNA LOGIC COMMANDS ---
        elif event.type == EventType.SAUNA_ON:
            if not self._state.sauna.active:
                self._state.sauna.active = True
                state_changed = True
                await self.logger.success("🔥 Sauna activated!")
                fire_order_txt = self.sauna_logic.get_current_order_string()
                await self.logger.info(f"📅 Daily Element Priority: [{fire_order_txt}]")

        elif event.type == EventType.SAUNA_OFF:
            if self._state.sauna.active:
                self._state.sauna.active = False
                self._state.sauna.modulation_pwm = 0
                self._state.sauna.phases_pwm = [0, 0, 0]
                state_changed = True
                await self.logger.info("❄️ Sauna deactivated!")

        elif event.type == EventType.SETPOINT_CHANGED:
            new_target: Optional[float] = event.payload.get("target")
            if new_target is not None and new_target != self._state.sauna.target_temp:
                self._state.sauna.target_temp = new_target
                state_changed = True
                await self.logger.info(f"🎯 Setpoint changed to {new_target}°C")

        elif event.type == EventType.MODULATION_UPDATED:
            raw_pwm = event.payload.get("pwm")
            raw_phases = event.payload.get("phases", [0, 0, 0])
            if raw_pwm is not None:
                new_pwm: int = int(round(float(raw_pwm)))
                if new_pwm != self._state.sauna.modulation_pwm or raw_phases != self._state.sauna.phases_pwm:
                    self._state.sauna.modulation_pwm = new_pwm
                    self._state.sauna.phases_pwm = raw_phases
                    state_changed = True
                    await self.logger.info(
                        f"⚡ Heater power: {new_pwm}% | Phases: U:{raw_phases[0]}%, V:{raw_phases[1]}%, W:{raw_phases[2]}%")

        else:
            await self.logger.warning(f"Unhandled event type: {event.type.value}")

        # --- THE BRAIN TRIGGER ---
        # 3. If any core variables change, ask the brain to evaluate the PID
        if event.type in [EventType.TEMP_UPDATED, EventType.SAUNA_ON, EventType.SAUNA_OFF, EventType.SETPOINT_CHANGED]:
            if self._state.sauna.current_temp is not None:
                calc_result = self.sauna_logic.evaluate(
                    active=self._state.sauna.active,
                    current_temp=self._state.sauna.current_temp,
                    target_temp=self._state.sauna.target_temp
                )

                # If the Brain calculated new math, drop a MODULATION_UPDATED event into the queue
                if calc_result is not None:
                    await self._queue.put(Event(
                        type=EventType.MODULATION_UPDATED,
                        payload=calc_result
                    ))

        # --- MQTT BROADCAST ---
        if state_changed:
            snapshot: dict[str, Any] = self.get_state_snapshot().model_dump()
            await self.logger.debug("Broadcasting State Update.")
            await self.mqtt_client.publish("wisc/system/state", snapshot)