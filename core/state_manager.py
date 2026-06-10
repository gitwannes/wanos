# --- file: core/state_manager.py ---
import asyncio
import time
from typing import Optional, Any

from .models import SystemState, Event, EventType
from .mqtt_transport import MqttClientManager
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
        self._telemetry_task: Optional[asyncio.Task] = None
        self._state_listeners: list[Any] = []  # Observer callback registry list
        self.mqtt_client: MqttClientManager = mqtt_client
        self.domoticz_client: Optional[Any] = None  # Populated dynamically by home_hub bridge
        self.logger: WanosLogger = logger

        self._start_time = time.time()  # Track initialization timestamp for Engine Uptime calculation

        # Load centralized configuration profiles
        self._config = load_config()

    def register_listener(self, callback: Any) -> None:
        """Registers an async callback to be triggered instantly on state changes."""
        self._state_listeners.append(callback)
        self._state.sauna.target_temp = float(self._config.sauna.default_setpoint)
        self._state.sauna.max_temp = float(self._config.sauna.max_temp)
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
        self._telemetry_task = asyncio.create_task(self._system_telemetry_loop())
        await self.logger.success("State Manager worker started.")

    async def stop(self) -> None:
        self._set_hardware_safety_gate(False)
        if self._telemetry_task:
            self._telemetry_task.cancel()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await asyncio.gather(self._worker_task, self._telemetry_task, return_exceptions=True)
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
                snapshot_obj: SystemState = self.get_state_snapshot()

                # 1. External Network Broadcast
                await self.mqtt_client.publish("wisc/system/state", snapshot_obj.model_dump())

                # 2. Internal Observer Push
                for listener in self._state_listeners:
                    try:
                        await listener(snapshot_obj)
                    except Exception as e:
                        await self.logger.error(f"Error in state listener execution: {e}")

                pending_broadcast = False

    async def _handle_event(self, event: Event) -> bool:
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        payload = event.payload or {}
        state_changed: bool = False

        # --- LIVE TERMINAL LOGGING INJECTION GATEWAY ---
        is_routine_sensory = event_name in ["TEMP_UPDATED", "HUMIDITY_UPDATED", "KWH_PULSE", "WATER_PULSE",
                                            "SYSTEM_METRICS_UPDATED"]
        is_manual_ui_action = payload.get("ui_override", False)

        if not is_routine_sensory or is_manual_ui_action:
            print(f"📥 [StateManager] Event Received: {event_name.ljust(22)} | Payload: {payload}")
            await self.logger.info(f"User Action Processed: {event_name}")

        # If it's a background simulator event, translate it to a string for the UI panel!
        if not self._state.hardware.live_mode and not is_manual_ui_action:
            log_msg = ""
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Generates HH:MM:SS.ms

            if event_name == "TEMP_UPDATED":
                sid = payload.get("sensor_id")
                new_val = payload.get("value")
                old_val = getattr(self._state.environment, f"{sid}_temp", None)
                if old_val is not None:
                    delta = round(float(new_val) - float(old_val), 1)
                    if delta != 0.0:  # Only log if it actually shifted!
                        sign = "+" if delta > 0 else ""
                        log_msg = f"{ts}|🌡️ {sid} temp: {sign}{delta}°C -> {new_val:.1f}°C"
                else:
                    log_msg = f"{ts}|🌡️ {sid} temp: -> {new_val:.1f}°C"

            elif event_name == "HUMIDITY_UPDATED":
                sid = payload.get("sensor_id")
                new_val = payload.get("value")
                old_val = getattr(self._state.environment, f"{sid}_hum", None)
                if old_val is not None:
                    delta = int(new_val) - int(old_val)
                    if delta != 0:  # Only log if it actually shifted!
                        sign = "+" if delta > 0 else ""
                        log_msg = f"{ts}|💧 {sid} humidity: {sign}{delta}% -> {new_val}%"
                else:
                    log_msg = f"{ts}|💧 {sid} humidity: -> {new_val}%"

            elif event_name == "HUB_STATE_CHANGED":
                dev = payload.get("device_id")
                st = payload.get("state")
                log_msg = f"{ts}|🔌 {dev}: -> {st}"

            if log_msg:
                self._state.hardware.lab_simulation_logs.insert(0, log_msg)
                self._state.hardware.lab_simulation_logs = self._state.hardware.lab_simulation_logs[:50]
                state_changed = True

        if event_name == "INITIAL_STATE_LOADED":
            self._state.hardware.live_mode = False
            self._set_hardware_safety_gate(False)
            state_changed = True

        elif event_name == "SYSTEM_METRICS_UPDATED":
            self._state.system.wanos_mqtt_connected = payload.get("wanos_connected", False)
            self._state.system.domoticz_mqtt_connected = payload.get("domoticz_connected", False)
            self._state.system.ip_address = payload.get("ip_address", "0.0.0.0")
            self._state.system.os_uptime_formatted = payload.get("os_uptime", "00:00:00")
            self._state.system.app_uptime_formatted = payload.get("app_uptime", "00:00:00")
            state_changed = True

        elif event_name == "HARDWARE_LIVE_MODE_CHANGED":
            self._state.hardware.live_mode = payload.get("live", False)
            self._set_hardware_safety_gate(self._state.hardware.live_mode)
            state_changed = True

        elif event_name == "LAB_SIMULATION_LOG":
            msg = payload.get("message", "")
            if msg:
                # Insert at the top (index 0) so the newest logs are first, keep max 50
                self._state.hardware.lab_simulation_logs.insert(0, msg)
                self._state.hardware.lab_simulation_logs = self._state.hardware.lab_simulation_logs[:50]
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
        # MULTI-ZONE TEMPERATURE & HUMIDITY ROUTING (SORTING OFFICE)
        # --------------------------------------------------------
        elif event_name == "TEMP_UPDATED":
            sensor_id = payload.get("sensor_id")
            val = payload.get("value")
            env = self._state.environment

            # 1. Core Engine Target: explicitly requested by internal math loop?
            if hasattr(env, f"{sensor_id}_temp"):
                setattr(env, f"{sensor_id}_temp", val)
                if sensor_id in ["sauna_high", "sauna_low"]:
                    if self._recalculate_sauna_metrics() or is_manual_ui_action:
                        state_changed = True
                else:
                    state_changed = True
            # 2. Generic Peripheral Target: Store it safely for the UI
            else:
                self._state.devices[f"{sensor_id}_temp"] = val
                state_changed = True

        elif event_name == "HUMIDITY_UPDATED":
            sensor_id = payload.get("sensor_id")
            val = payload.get("value")
            env = self._state.environment

            # 1. Core Engine Target
            if hasattr(env, f"{sensor_id}_hum"):
                setattr(env, f"{sensor_id}_hum", val)

                # ⚡ AUTOMATED BATHROOM VENTILATOR HYSTERESIS LOOP ⚡
                if sensor_id == "bathroom" and env.bathroom_hum is not None:
                    on_threshold = self._config.bathroom.vent_on_humidity
                    off_threshold = self._config.bathroom.vent_off_humidity

                    # Engine relies entirely on the generic devices dictionary mapping
                    current_vent_state = self._state.devices.get("bathroom_ventilator", "OFF")

                    if env.bathroom_hum >= on_threshold and current_vent_state != "ON":
                        self._state.devices["bathroom_ventilator"] = "ON"
                        state_changed = True
                        msg = f"💨 Bathroom humidity ({env.bathroom_hum}%) >= ON threshold ({on_threshold}%). Auto-engaging ventilator."
                        print(f"[StateManager] {msg}")
                        if not self._state.hardware.live_mode:
                            from datetime import datetime
                            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self._state.hardware.lab_simulation_logs.insert(0, f"{ts}|{msg}")
                    elif env.bathroom_hum <= off_threshold and current_vent_state == "ON":
                        self._state.devices["bathroom_ventilator"] = "OFF"
                        state_changed = True
                        msg = f"💨 Bathroom humidity ({env.bathroom_hum}%) <= OFF threshold ({off_threshold}%). Auto-disengaging ventilator."
                        print(f"[StateManager] {msg}")
                        if not self._state.hardware.live_mode:
                            from datetime import datetime
                            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self._state.hardware.lab_simulation_logs.insert(0, f"{ts}|{msg}")

                if sensor_id in ["sauna_high", "sauna_low"]:
                    if self._recalculate_sauna_metrics() or is_manual_ui_action:
                        state_changed = True
                else:
                    state_changed = True
            # 2. Generic Peripheral Target
            else:
                self._state.devices[f"{sensor_id}_hum"] = val
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
                await self.logger.warning("🌡️ Bouncer rejected SAUNA_ON: Door is open.")
                return False
            if self._state.sauna.current_temp is None:
                await self.logger.warning("🌡️ Bouncer rejected SAUNA_ON: Temperature data is currently missing (NULL).")
                return False
            self._state.sauna.active = True
            self._state.sauna.hold_mode = "autohold"
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
            if self._state.sauna.current_temp is None:
                await self.logger.warning("🌡️ Bouncer rejected IR_ON: Temperature data is currently missing (NULL).")
                return False
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
            state_val = payload.get("state")  # "ON" or "OFF"

            # 100% Generic Assignment. Any inbound switch event goes straight to the dict.
            if self._state.devices.get(device) != state_val:
                self._state.devices[device] = state_val
                state_changed = True

        elif event_name == "LIGHTING_STATE_CHANGED":
            zone = payload.get("zone")
            state_val = payload.get("state")  # "ON" or "OFF"
            target_device = f"{zone}_hue"
            if self._state.devices.get(target_device) != state_val:
                self._state.devices[target_device] = state_val
                state_changed = True

        elif event_name == "VENT_WAIT_EXPIRED":
            self._state.sauna.ventilation_state = "RUNNING"
            self._state.devices["sauna_extrvent"] = "ON"
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_run_mins * 60)
            self._timer_manager.schedule("vent_run", self._state.sauna.ventilation_deadline, "VENT_RUN_EXPIRED")
            state_changed = True

        elif event_name == "VENT_RUN_EXPIRED":
            self._state.sauna.ventilation_state = "OFF"
            self._state.devices["sauna_extrvent"] = "OFF"
            self._state.sauna.ventilation_deadline = None
            state_changed = True

        elif event_name == "SETPOINT_CHANGED":
            new_target = payload.get("target")
            if new_target is not None:
                self._state.sauna.target_temp = min(float(new_target), self._state.sauna.max_temp)
                state_changed = True

        elif event_name == "MODULATION_UPDATED":
            self._state.sauna.modulation_pwm = payload.get("pwm", 0)
            self._state.sauna.phases_pwm = payload.get("phases", [0, 0, 0])
            state_changed = True

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
        from logic.auxiliary_controller import AuxiliaryController

        old_lcd_text: str = self._state.sauna.lcd_text
        old_light_color: str = self._state.sauna.light_color
        old_fireorder: str = self._state.sauna.fireorder

        # Delegate display and lighting logic cleanly to the pure business logic controller
        self._state.sauna = AuxiliaryController.evaluate(self._state.sauna)

        if not self._state.sauna.active:
            self._state.sauna.fireorder = "--"
        else:
            raw_order = self.sauna_logic.get_current_order_string()
            self._state.sauna.fireorder = raw_order.replace(" -> ", "")

        if (self._state.sauna.lcd_text != old_lcd_text or
                self._state.sauna.light_color != old_light_color or
                self._state.sauna.fireorder != old_fireorder):
            state_changed = True

        return state_changed

    async def _system_telemetry_loop(self) -> None:
        """Background execution loop polling hardware diagnostics and connection channels."""
        import socket

        def _get_ip():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "127.0.0.1"

        def _format_seconds(seconds: float) -> str:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            if days > 0:
                return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"

        def _get_os_uptime():
            try:
                with open('/proc/uptime', 'r') as f:
                    return _format_seconds(float(f.readline().split()[0]))
            except Exception:
                return "Emulation Host"

        def _is_connected(client_mgr) -> bool:
            if not client_mgr:
                return False
            # Check if the manager wrapper class has a valid, initialized aiomqtt Client object
            if hasattr(client_mgr, "client") and client_mgr.client is not None:
                # If your aiomqtt client version exposes an internal connection check:
                if hasattr(client_mgr.client, "is_connected"):
                    return client_mgr.client.is_connected()
                # Safe fallback: if the client object is active and alive, count it as connected
                return True
            return False

        while True:
            try:
                await asyncio.sleep(2.0)
                metrics_payload = {
                    "wanos_connected": _is_connected(self.mqtt_client),
                    "domoticz_connected": _is_connected(self.domoticz_client),
                    "ip_address": _get_ip(),
                    "os_uptime": _get_os_uptime(),
                    "app_uptime": _format_seconds(time.time() - self._start_time)
                }
                self.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED, payload=metrics_payload))
            except asyncio.CancelledError:
                break
            except Exception:
                pass