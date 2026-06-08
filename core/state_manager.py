# --- file: core/state_manager.py ---
import asyncio
import time
from typing import Optional, Any

from .models import SystemState, Event, EventType
from .mqtt_client import MqttClientManager
from .logger import WanosLogger
from .config import load_config

try:
    import lgpio

    LGPIO_AVAILABLE = True
except ImportError:
    LGPIO_AVAILABLE = False


class StateManager:
    def __init__(self, mqtt_client: MqttClientManager, logger: WanosLogger) -> None:
        self._state: SystemState = SystemState()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self.mqtt_client: MqttClientManager = mqtt_client
        self.logger: WanosLogger = logger

        # Load centralized configuration profiles
        self._config = load_config()
        self._state.sauna.target_temp = float(self._config.sauna.default_setpoint)
        self._state.lab_seed = self._config.lab_seed

        # ⏱️ DELAYED TIMELINE TRACKING VARIABLES
        self._sauna_timer_triggered = False
        self._sauna_timer_duration_secs = 0

        # Open hardware safety channel chip context if available
        self._gpio_chip = None
        if LGPIO_AVAILABLE:
            try:
                self._gpio_chip = lgpio.gpiochip_open(0)
                lgpio.gpio_claim_output(self._gpio_chip, self._config.pins.safety_gpio)
            except Exception as e:
                print(f"[Hardware Init Error] Safety Pin unavailable: {e}")

        # Boot business controllers
        from logic.sauna_controller import SaunaController
        self.sauna_logic = SaunaController(
            initial_target_temp=self._state.sauna.target_temp,
            kp=self._config.sauna.kp,
            ki=self._config.sauna.ki,
            kd=self._config.sauna.kd
        )
        from logic.timers import TimerManager
        self._timer_manager = TimerManager(dispatch_callback=self._dispatch_from_timer)

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(self._process_events())
        await self.logger.success("State Manager worker started.")

    async def stop(self) -> None:
        self._set_hardware_safety_gate(False)
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._gpio_chip and LGPIO_AVAILABLE:
            lgpio.gpiochip_close(self._gpio_chip)
        await self.logger.warning("State Manager worker stopped.")

    def dispatch(self, event: Event) -> None:
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            self._queue.put_nowait(event)

    async def _dispatch_from_timer(self, event_type_str: str, payload: dict) -> None:
        try:
            e_type = EventType(event_type_str)
            self.dispatch(Event(type=e_type, payload=payload))
        except ValueError:
            await self.logger.error(f"Timer dispatch error: {event_type_str}")

    def get_state_snapshot(self) -> SystemState:
        return self._state.model_copy(deep=True)

    def _set_hardware_safety_gate(self, state: bool):
        self._state.hardware.safety_pin_active = state
        if self._gpio_chip and LGPIO_AVAILABLE:
            try:
                val = 1 if state else 0
                lgpio.gpio_write(self._gpio_chip, self._config.pins.safety_gpio, val)
            except Exception as e:
                print(f"[Safety Relay Error] Write failed: {e}")

    def _recalculate_sauna_metrics(self) -> bool:
        env = self._state.environment
        changed = False
        if env.sauna_high_temp is not None and env.sauna_low_temp is not None:
            raw_temp = (env.sauna_high_temp + env.sauna_low_temp) / 2
            calc_temp = round(raw_temp * 2) / 2
            if calc_temp != env.sauna_calc_temp:
                env.sauna_calc_temp = calc_temp
                self._state.sauna.current_temp = calc_temp
                changed = True
        if env.sauna_high_hum is not None and env.sauna_low_hum is not None:
            raw_hum = (env.sauna_high_hum + (env.sauna_low_hum * 4)) / 5
            calc_hum = round(raw_hum)
            if calc_hum != env.sauna_calc_hum:
                env.sauna_calc_hum = calc_hum
                self._state.sauna.current_humidity = calc_hum
                changed = True
        return changed

    def _update_lcd_text(self) -> None:
        """Authentic LCD Virtual Terminal Matrix Renderer with True Degree Symbols."""
        sauna = self._state.sauna

        if sauna.active:
            temp_display = f"{int(sauna.current_temp)}°C" if sauna.current_temp is not None else "--°C"
            if sauna.door_open:
                sauna.lcd_text = f"CLOSE DOOR | {temp_display}"
            elif sauna.hold_mode == "hold":
                sauna.lcd_text = f"SAUNA HOLD | {temp_display}"
            else:
                sauna.lcd_text = f"SAUNA ON | {temp_display} ({sauna.modulation_pwm}%)"
            return

        if sauna.ventilation_state == "RUNNING":
            sauna.lcd_text = "VENT RUNNING"
        elif sauna.ventilation_state == "WAITING":
            sauna.lcd_text = "VENT WAITING"
        else:
            sauna.lcd_text = ""

    async def _process_events(self) -> None:
        """Sequential event execution stream loop with outbound network batch debouncing."""
        pending_broadcast = False
        while True:
            event: Event = await self._queue.get()
            try:
                changed = await self._handle_event(event)
                if changed:
                    pending_broadcast = True
            except Exception as e:
                await self.logger.error(f"Error handling event {event.type.value}: {e}")
            finally:
                self._queue.task_done()

            if pending_broadcast and self._queue.empty():
                snapshot = self.get_state_snapshot().model_dump()
                await self.mqtt_client.publish("wisc/system/state", snapshot)
                pending_broadcast = False

    async def _handle_event(self, event: Event) -> bool:
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        payload = event.payload or {}
        state_changed: bool = False

        # --- LIVE TERMINAL LOGGING INJECTION GATEWAY ---
        is_routine_sensory = event_name in ["TEMP_UPDATED", "HUMIDITY_UPDATED", "KWH_PULSE", "WATER_PULSE"]
        is_manual_ui_action = payload.get("ui_override", False)

        if not is_routine_sensory or is_manual_ui_action:
            print(f"📥 [StateManager] Event Received: {event_name.ljust(22)} | Payload: {payload}")
            await self.logger.info(f"User Action Processed: {event_name}")

        if event_name == "INITIAL_STATE_LOADED":
            self._state.hardware.live_mode = False
            self._set_hardware_safety_gate(False)
            state_changed = True

        elif event_name == "HARDWARE_LIVE_MODE_CHANGED":
            self._state.hardware.live_mode = payload.get("live", False)
            self._set_hardware_safety_gate(self._state.hardware.live_mode)
            state_changed = True

        # --------------------------------------------------------
        # PHYSICAL PULSE MAPPING
        # --------------------------------------------------------
        elif event_name == "WATER_PULSE":
            wtype = payload.get("fluid", "cold")
            count = payload.get("count", 1)

            for _ in range(count):
                if wtype == "cold":
                    self._state.metrics.water_cold_liters += (1.0 / 396.0)
                else:
                    self._state.metrics.water_hot_liters += (1.0 / 396.0)

                if self._state.metrics.douche_active:
                    self._state.metrics.douche_water_liters += 1
            state_changed = True

        elif event_name == "KWH_PULSE":
            self._state.metrics.kwh_wh_ticks += 1
            state_changed = True

        # --------------------------------------------------------
        # MULTI-ZONE TEMPERATURE & HUMIDITY ROUTING
        # --------------------------------------------------------
        elif event_name == "TEMP_UPDATED":
            sensor_id = payload.get("sensor_id", "sauna_high")
            val = payload.get("value")
            env = self._state.environment
            if sensor_id == "sauna_high":
                env.sauna_high_temp = val
            elif sensor_id == "sauna_low":
                env.sauna_low_temp = val
            elif sensor_id == "bathroom":
                env.bathroom_temp = val
            elif sensor_id == "cinema":
                env.cinema_temp = val
            elif sensor_id == "outside":
                env.outside_temp = val

            if sensor_id in ["sauna_high", "sauna_low"]:
                if self._recalculate_sauna_metrics() or is_manual_ui_action:
                    state_changed = True
            else:
                state_changed = True

        elif event_name == "HUMIDITY_UPDATED":
            sensor_id = payload.get("sensor_id", "sauna_high")
            val = payload.get("value")
            env = self._state.environment
            if sensor_id == "sauna_high":
                env.sauna_high_hum = val
            elif sensor_id == "sauna_low":
                env.sauna_low_hum = val
            elif sensor_id == "bathroom":
                env.bathroom_hum = val

                # ⚡ AUTOMATED BATHROOM VENTILATOR HYSTERESIS LOOP ⚡
                if env.bathroom_hum is not None:
                    # Direct, configuration-pure Pydantic object lookup! No fallbacks.
                    on_threshold = self._config.bathroom.vent_on_humidity
                    off_threshold = self._config.bathroom.vent_off_humidity

                    if env.bathroom_hum >= on_threshold and not env.bathroom_vent_on:
                        env.bathroom_vent_on = True
                        state_changed = True
                        print(
                            f"💨 [StateManager] Bathroom humidity ({env.bathroom_hum}%) >= ON threshold ({on_threshold}%). Auto-engaging ventilator.")
                    elif env.bathroom_hum <= off_threshold and env.bathroom_vent_on:
                        env.bathroom_vent_on = False
                        state_changed = True
                        print(
                            f"💨 [StateManager] Bathroom humidity ({env.bathroom_hum}%) <= OFF threshold ({off_threshold}%). Auto-disengaging ventilator.")

            elif sensor_id == "cinema":
                env.cinema_hum = val
            elif sensor_id == "outside":
                env.outside_hum = val

            if sensor_id in ["sauna_high", "sauna_low"]:
                if self._recalculate_sauna_metrics() or is_manual_ui_action:
                    state_changed = True
            else:
                state_changed = True

        elif event_name == "SENSOR_ERROR":
            sid = payload.get("sensor", "unknown")
            if sid not in self._state.hardware.sensor_errors:
                self._state.hardware.sensor_errors.append(sid)
                state_changed = True
            if sid in ["sauna_high", "sauna_low"] and self._state.sauna.active:
                await self.logger.critical(f"Critical sensor failure on {sid}. Emergency stopping heater elements.")
                self.dispatch(Event(type=EventType.SAUNA_OFF))

        # --------------------------------------------------------
        # CORE CONTROLLER MODULE ROUTERS
        # --------------------------------------------------------
        elif event_name == "SAUNA_ON":
            if self._state.sauna.door_open:
                await self.logger.warning("Bouncer rejected SAUNA_ON: Door is open.")
                return
            self._state.sauna.active = True
            self._state.sauna.hold_mode = "autohold"

            # Reset timeline flags and seed active session timing windows
            now = int(time.time())
            self._state.sauna.session_start_time = now
            self._sauna_timer_triggered = False
            self._sauna_timer_duration_secs = self._config.sauna.default_timer * 60
            self._state.sauna.session_end_time = self._sauna_timer_duration_secs
            state_changed = True

        elif event_name == "SAUNA_OFF":
            self._state.sauna.active = False
            self._state.sauna.modulation_pwm = 0
            self._state.sauna.phases_pwm = [0, 0, 0]
            self._timer_manager.cancel("sauna_main")
            self._sauna_timer_triggered = False

            self._state.sauna.ventilation_state = "WAITING"
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_delay_mins * 60)
            self._timer_manager.schedule("vent_wait", self._state.sauna.ventilation_deadline, "VENT_WAIT_EXPIRED")
            state_changed = True

        elif event_name == "TIMER_ADJUSTED":
            minutes_to_add = payload.get("minutes", 0)
            if self._state.sauna.active:
                self._sauna_timer_duration_secs += (minutes_to_add * 60)

                if self._sauna_timer_triggered:
                    self._state.sauna.session_end_time += (minutes_to_add * 60)
                    self._timer_manager.cancel("sauna_main")
                    self._timer_manager.schedule("sauna_main", self._state.sauna.session_end_time,
                                                 "SAUNA_TIMER_EXPIRED")
                else:
                    self._state.sauna.session_end_time = self._sauna_timer_duration_secs
                state_changed = True

        elif event_name == "HOLD_TOGGLED":
            current_mode = self._state.sauna.hold_mode
            if current_mode == "autohold":
                self._state.sauna.hold_mode = "nohold"
            elif current_mode == "hold":
                self._state.sauna.hold_mode = "nohold"
            else:
                self._state.sauna.hold_mode = "hold"
            state_changed = True

        elif event_name == "SAUNA_TIMER_EXPIRED":
            print("🚨 [StateManager] Sauna session limit countdown reached 0.")
            self.dispatch(Event(type=EventType.SAUNA_OFF))

        elif event_name == "IR_ON":
            self._state.ir.active = True
            now = int(time.time())
            self._state.ir.session_start_time = now
            self._state.ir.session_end_time = now + (self._config.ir.max_time_mins * 60)
            self._state.ir.modulation_pwm = 100
            self._state.ir.frequency = self._config.ir.pwm_freq
            self._timer_manager.schedule("ir_main", self._state.ir.session_end_time, "IR_TIMER_EXPIRED")
            state_changed = True

        elif event_name == "IR_OFF":
            self._state.ir.active = False
            self._state.ir.modulation_pwm = 0
            self._timer_manager.cancel("ir_main")
            state_changed = True

        elif event_name == "IR_TIMER_EXPIRED":
            self.dispatch(Event(type=EventType.IR_OFF))

        elif event_name == "DOOR_CHANGED":
            sensor_id = payload.get("sensor_id", "sauna")
            is_open = payload.get("is_open", False)
            if sensor_id == "sauna":
                self._state.sauna.door_open = is_open

                # Sauna safety interlock logic
                if is_open and self._state.sauna.active:
                    self._state.sauna.active = False
                    self._state.sauna.modulation_pwm = 0
                    self._state.sauna.phases_pwm = [0, 0, 0]
                    self._state.sauna.ventilation_state = "OFF"
                    asyncio.create_task(
                        self.logger.warning("🚪 Sauna door opened while active! Emergency cutoff triggered."))

            elif sensor_id == "bathroom":
                self._state.environment.door_bathroom_open = is_open
            state_changed = True

        elif event_name == "HUB_STATE_CHANGED":
            device = payload.get("device_id")
            is_on = payload.get("state") == "ON"
            if device == "bathroom_ventilator":
                self._state.environment.bathroom_vent_on = is_on
                state_changed = True

        elif event_name == "VENT_WAIT_EXPIRED":
            self._state.sauna.ventilation_state = "RUNNING"
            self._state.environment.sauna_extraction_vent_on = True
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_run_mins * 60)
            self._timer_manager.schedule("vent_run", self._state.sauna.ventilation_deadline, "VENT_RUN_EXPIRED")
            state_changed = True

        elif event_name == "VENT_RUN_EXPIRED":
            self._state.sauna.ventilation_state = "OFF"
            self._state.environment.sauna_extraction_vent_on = False
            self._state.sauna.ventilation_deadline = None
            state_changed = True

        elif event_name == "SETPOINT_CHANGED":
            new_target = payload.get("target")
            if new_target is not None:
                self._state.sauna.target_temp = new_target
                state_changed = True

        elif event_name == "MODULATION_UPDATED":
            self._state.sauna.modulation_pwm = payload.get("pwm", 0)
            self._state.sauna.phases_pwm = payload.get("phases", [0, 0, 0])
            state_changed = True

        # Process PID calculations dynamically un-nested at root event level
        if event_name in ["TEMP_UPDATED", "SAUNA_ON", "SAUNA_OFF", "SETPOINT_CHANGED", "DOOR_CHANGED"]:
            if self._state.sauna.current_temp is not None and self._state.sauna.active:

                # ⏱️ CONFIGURABLE TIMER COUNTDOWN EVALUATION GATEWAY
                offset = getattr(self._config.sauna, "timer_offset_temp", 7.0)
                threshold_temp = self._state.sauna.target_temp - offset

                if not self._sauna_timer_triggered:
                    if self._state.sauna.current_temp >= threshold_temp:
                        self._sauna_timer_triggered = True
                        self._state.sauna.session_end_time = int(time.time()) + self._sauna_timer_duration_secs
                        self._timer_manager.schedule("sauna_main", self._state.sauna.session_end_time,
                                                     "SAUNA_TIMER_EXPIRED")
                        print(
                            f"⏱️ [StateManager] Heat threshold met ({self._state.sauna.current_temp}°C >= {threshold_temp}°C). Activating timer countdown!")
                        state_changed = True
                    else:
                        if self._state.sauna.session_end_time != self._sauna_timer_duration_secs:
                            self._state.sauna.session_end_time = self._sauna_timer_duration_secs
                            state_changed = True

                # AUTOMATIC HOLD STEPPING INTERRUPT:
                if self._state.sauna.current_temp >= self._state.sauna.target_temp:
                    if self._state.sauna.hold_mode == "autohold":
                        self._state.sauna.hold_mode = "hold"
                        print("🎯 [StateManager] Setpoint met! System automatically dropped load: autohold -> hold")
                        state_changed = True

                calc_result = self.sauna_logic.evaluate(self._state.sauna)
                if calc_result:
                    self._state.sauna.modulation_pwm = calc_result.get("pwm", 0)
                    self._state.sauna.phases_pwm = calc_result.get("phases", [0, 0, 0])
                    state_changed = True

        # --- DEFENSIVE RE-RENDER CHECKPOINT ---
        old_lcd_text = self._state.sauna.lcd_text
        self._update_lcd_text()
        if self._state.sauna.lcd_text != old_lcd_text:
            state_changed = True

        return state_changed