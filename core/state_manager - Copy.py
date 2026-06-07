# --- file: core/state_manager.py ---
import asyncio
import time
from typing import Optional, Any

from .models import SystemState, Event, EventType
from .mqtt_client import MqttClientManager
from .logger import WanosLogger
from .config import load_config
from logic.sauna_controller import SaunaController
from logic.timers import TimerManager
from logic.auxiliary_controller import AuxiliaryController


class StateManager:
    def __init__(self, mqtt_client: MqttClientManager, logger: WanosLogger) -> None:
        self._state: SystemState = SystemState()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.mqtt_client: MqttClientManager = mqtt_client
        self.logger: WanosLogger = logger

        # 1. Load and save configuration so it can be accessed by the timers
        self._config = load_config()
        self._state.sauna.target_temp = float(self._config.sauna.default_setpoint)

        # 2. Boot the Brain and Timers
        self.sauna_logic = SaunaController(
            initial_target_temp=self._state.sauna.target_temp,
            kp=self._config.sauna.kp,
            ki=self._config.sauna.ki,
            kd=self._config.sauna.kd
        )
        # Pass our custom dispatch wrapper so the TimerManager can inject events
        self._timer_manager = TimerManager(dispatch_callback=self._dispatch_from_timer)

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

    async def _dispatch_from_timer(self, event_type_str: str, payload: dict) -> None:
        """Helper to convert string events from TimerManager into Event objects."""
        try:
            e_type = EventType(event_type_str)
            self.dispatch(Event(type=e_type, payload=payload))
        except ValueError:
            await self.logger.error(f"Timer tried to dispatch unknown event type: {event_type_str}")

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
        # Extract values cleanly to avoid missing-attribute errors
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        payload = event.payload or {}

        await self.logger.debug(f"Processing Event: {event_name} | {payload}")
        state_changed: bool = False

        if event_name == "INITIAL_STATE_LOADED":
            self._state.hardware.live_mode = False
            state_changed = True

        elif event_name == "TEMP_UPDATED":
            new_temp: Optional[float] = payload.get("value")
            if new_temp is not None and new_temp != self._state.sauna.current_temp:
                self._state.sauna.current_temp = new_temp
                state_changed = True

        # --------------------------------------------------------
        # CORE SAUNA COMMANDS
        # --------------------------------------------------------
        elif event_name == "SAUNA_ON":
            # Door Interlock Guard
            if self._state.sauna.door_open:
                await self.logger.warning("Bouncer rejected SAUNA_ON: Door is open.")
                return

            self._state.sauna.active = True

            # Absolute Timers
            now = int(time.time())
            self._state.sauna.session_start_time = now
            self._state.sauna.session_end_time = now + (self._config.sauna.default_timer * 60)

            # Schedule the expiration event
            self._timer_manager.schedule(
                timer_id="sauna_main",
                deadline=self._state.sauna.session_end_time,
                event_type="SAUNA_TIMER_EXPIRED"
            )

            # Clear any active ventilation tasks
            self._timer_manager.cancel("vent_wait")
            self._timer_manager.cancel("vent_run")
            self._state.sauna.ventilation_state = "OFF"
            self._state.sauna.ventilation_deadline = None
            state_changed = True

        elif event_name == "SAUNA_OFF":
            self._state.sauna.active = False
            self._state.sauna.modulation_pwm = 0.0
            self._state.sauna.phases_pwm = [0.0, 0.0, 0.0]
            self._state.sauna.session_start_time = None
            self._state.sauna.session_end_time = None

            self._timer_manager.cancel("sauna_main")

            # Trigger Ventilation Stage 1 (Waiting)
            self._state.sauna.ventilation_state = "WAITING"
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_delay_mins * 60)
            self._timer_manager.schedule(
                timer_id="vent_wait",
                deadline=self._state.sauna.ventilation_deadline,
                event_type="VENT_WAIT_EXPIRED"
            )
            state_changed = True

        # --------------------------------------------------------
        # ENVIRONMENT & SECURITY EVENTS
        # --------------------------------------------------------
        elif event_name == "DOOR_CHANGED":
            self._state.sauna.door_open = payload.get("is_open", False)
            if self._state.sauna.door_open and self._state.sauna.active:
                await self.logger.warning("Safety Interlock Tripped: Door opened during active session.")
            state_changed = True

        elif event_name == "HOLD_TOGGLED":
            # Cycle through the 3 states
            current = self._state.sauna.hold_mode
            if current == "autohold":
                self._state.sauna.hold_mode = "hold"
            elif current == "hold":
                self._state.sauna.hold_mode = "nohold"
            else:
                self._state.sauna.hold_mode = "autohold"
            state_changed = True

        elif event_name == "HUMIDITY_UPDATED":
            self._state.sauna.current_humidity = payload.get("value")
            state_changed = True

        # --------------------------------------------------------
        # ABSOLUTE TIMER EVENTS
        # --------------------------------------------------------
        elif event_name == "TIMER_ADJUSTED":
            if self._state.sauna.active and self._state.sauna.session_end_time:
                minutes_to_add = payload.get("minutes", 0)
                self._state.sauna.session_end_time += (minutes_to_add * 60)
                # Reschedule the active timer with the new deadline
                self._timer_manager.schedule(
                    timer_id="sauna_main",
                    deadline=self._state.sauna.session_end_time,
                    event_type="SAUNA_TIMER_EXPIRED"
                )
                state_changed = True

        elif event_name == "SAUNA_TIMER_EXPIRED":
            await self.logger.info("Session timer expired. Shutting down sauna.")
            # Safely route back through the standard shutdown sequence
            self.dispatch(Event(type=EventType.SAUNA_OFF, payload={}))

        elif event_name == "VENT_WAIT_EXPIRED":
            await self.logger.info("Ventilation wait period over. Starting extraction fan.")
            self._state.sauna.ventilation_state = "RUNNING"
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_run_mins * 60)
            self._timer_manager.schedule(
                timer_id="vent_run",
                deadline=self._state.sauna.ventilation_deadline,
                event_type="VENT_RUN_EXPIRED"
            )
            state_changed = True

        elif event_name == "VENT_RUN_EXPIRED":
            await self.logger.info("Ventilation cycle complete. Shutting fan off.")
            self._state.sauna.ventilation_state = "OFF"
            self._state.sauna.ventilation_deadline = None
            state_changed = True

        # --------------------------------------------------------
        # SETPOINT & MODULATION
        # --------------------------------------------------------
        elif event_name == "SETPOINT_CHANGED":
            new_target: Optional[float] = payload.get("target")
            if new_target is not None and new_target != self._state.sauna.target_temp:
                self._state.sauna.target_temp = new_target
                state_changed = True
                await self.logger.info(f"🎯 Setpoint changed to {new_target}°C")

        elif event_name == "MODULATION_UPDATED":
            raw_pwm = payload.get("pwm")
            raw_phases = payload.get("phases", [0, 0, 0])
            if raw_pwm is not None:
                new_pwm: int = int(round(float(raw_pwm)))
                if new_pwm != self._state.sauna.modulation_pwm or raw_phases != self._state.sauna.phases_pwm:
                    self._state.sauna.modulation_pwm = new_pwm
                    self._state.sauna.phases_pwm = raw_phases
                    state_changed = True
                    await self.logger.info(
                        f"⚡ Heater power: {new_pwm}% | Phases: U:{raw_phases[0]}%, V:{raw_phases[1]}%, W:{raw_phases[2]}%")
        else:
            await self.logger.warning(f"Unhandled event type: {event_name}")

        # --------------------------------------------------------
        # THE BRAIN TRIGGER (Heater Logic)
        # --------------------------------------------------------
        # If any variables change that affect heating, ask the Brain to evaluate
        if event_name in ["TEMP_UPDATED", "SAUNA_ON", "SAUNA_OFF", "SETPOINT_CHANGED", "DOOR_CHANGED", "HOLD_TOGGLED"]:
            if self._state.sauna.current_temp is not None:
                # Pass the full state model so the Brain can evaluate door/hold safety interlocks
                calc_result = self.sauna_logic.evaluate(self._state.sauna)

                # If the Brain calculated new math, drop a MODULATION_UPDATED event into the queue
                if calc_result is not None:
                    # Expecting calc_result to be a dict: {"pwm": float, "phases": list[float]}
                    # If evaluate() returns a tuple, you would format it here before dispatching.
                    if isinstance(calc_result, tuple):
                        calc_result = {"pwm": calc_result[0], "phases": calc_result[1]}

                    self.dispatch(Event(
                        type=EventType.MODULATION_UPDATED,
                        payload=calc_result
                    ))

        # --------------------------------------------------------
        # THE AUXILIARY TRIGGER (Lights & LCD)
        # --------------------------------------------------------
        # Evaluate auxiliary environmental variables (Lights, LCD text)
        new_state = AuxiliaryController.evaluate(self._state.sauna)

        # Check if the Auxiliary Controller actually changed anything visual
        if (new_state.light_color != self._state.sauna.light_color or
                new_state.lcd_text != self._state.sauna.lcd_text):
            state_changed = True

        self._state.sauna = new_state

        # --- MQTT / SSE BROADCAST ---
        if state_changed:
            snapshot: dict[str, Any] = self.get_state_snapshot().model_dump()
            await self.logger.debug("Broadcasting State Update.")
            await self.mqtt_client.publish("wisc/system/state", snapshot)