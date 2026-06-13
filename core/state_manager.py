# --- file: core/state_manager.py ---
import asyncio
import time
from typing import Optional, Any, Set
from loguru import logger

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

        # Optional reference to the MqttPublisher, injected after construction.
        # If set, pulse events are forwarded to it for accumulation and batched emit.
        self.mqtt_publisher: Optional[Any] = None

        self._start_time = time.time()  # Track initialization timestamp for Engine Uptime calculation

        # Load centralized configuration profiles
        self._config = load_config()

    def register_listener(self, callback: Any) -> None:
        """Registers an async callback to be triggered on post-drain state snapshots."""
        self._state_listeners.append(callback)
        self._state.sauna.target_temp = float(self._config.sauna.default_setpoint)
        self._state.sauna.max_temp = float(self._config.sauna.max_temp)
        self._state.lab_seed = self._config.lab_seed
        self._state.devices["door_sauna"] = "CLOSED"
        self._state.devices["door_bathroom"] = "CLOSED"
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
                logger.error(f"Hardware Init Error: Safety Pin unavailable - {e}")

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
                logger.error(f"Safety Relay Error: Write failed - {e}")

    def _recalculate_sauna_metrics(self) -> bool:
        sns = self._state.sensors
        changed = False
        if sns.sauna_high_temp is not None and sns.sauna_low_temp is not None:
            raw_temp = (sns.sauna_high_temp + sns.sauna_low_temp) / 2
            calc_temp = round(raw_temp * 2) / 2
            if calc_temp != sns.sauna_calc_temp:
                sns.sauna_calc_temp = calc_temp
                changed = True
        if sns.sauna_high_hum is not None and sns.sauna_low_hum is not None:
            raw_hum = (sns.sauna_high_hum + (sns.sauna_low_hum * 4)) / 5
            calc_hum = round(raw_hum)
            if calc_hum != sns.sauna_calc_hum:
                sns.sauna_calc_hum = calc_hum
                changed = True
        return changed

    async def _process_events(self) -> None:
        """
        Sequential event execution loop with outbound network batch debouncing.
        Drains the queue fully before broadcasting, collecting the set of changed
        domains across the batch so each publisher/listener knows exactly what changed.
        """
        pending_broadcast = False
        # Accumulates which top-level state domains changed during the current drain batch
        changed_domains: Set[str] = set()

        while True:
            event: Event = await self._queue.get()
            try:
                changed, domains = await self._handle_event(event)
                if changed:
                    pending_broadcast = True
                    changed_domains.update(domains)
            except Exception as e:
                await self.logger.error(f"Error handling event {event.type.value}: {e}")
            finally:
                self._queue.task_done()

            if pending_broadcast and self._queue.empty():
                snapshot_obj: SystemState = self.get_state_snapshot()

                # Notify the domain-scoped MQTT publisher with the changed domain set.
                # The publisher routes each domain to its dedicated topic and cadence.
                if self.mqtt_publisher:
                    try:
                        await self.mqtt_publisher.on_state_changed(snapshot_obj, changed_domains)
                    except Exception as e:
                        await self.logger.error(f"Error in MQTT publisher: {e}")

                # Notify all other registered state listeners (e.g., Domoticz bridge)
                for listener in self._state_listeners:
                    try:
                        await listener(snapshot_obj)
                    except Exception as e:
                        await self.logger.error(f"Error in state listener execution: {e}")

                pending_broadcast = False
                changed_domains = set()

    async def _handle_event(self, event: Event) -> tuple[bool, Set[str]]:
        """
        Processes a single event and mutates internal state.
        Returns (state_changed: bool, changed_domains: Set[str]).
        changed_domains contains the top-level SystemState keys that were modified,
        allowing the publisher to route only the affected topic(s).
        """
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        payload = event.payload or {}
        state_changed: bool = False
        changed_domains: Set[str] = set()

        # --- LIVE TERMINAL LOGGING INJECTION GATEWAY ---
        is_manual_lab_action = payload.get("lab_override", False)
        is_user_command = event_name in [
            "SAUNA_ON", "SAUNA_OFF", "SETPOINT_CHANGED", "MODULATION_UPDATED",
            "SAUNA_HOLD", "HOLD_TOGGLED", "TIMER_ADJUSTED", "IR_ON", "IR_OFF"
        ]

        if event_name == "SYSTEM_READY":
            logger.info("Internal Engine State validated and locked.")
            logger.info(f"Internal Event Processed: {event_name}")
        elif is_user_command or is_manual_lab_action:
            logger.info(f"Lab Action Received: {event_name} | Payload: {payload}")
            await self.logger.info(f"User Action Processed: {event_name}")
        elif event_name == "HUB_STATE_CHANGED":
            # Direct formatting as requested for clean hardware state updates
            logger.debug(f"Event Received: {payload}")

        # If it's a background simulator event, translate it to a string for the UI panel!
        if not self._state.hardware.live_mode and not is_manual_lab_action:
            log_msg = ""
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Generates HH:MM:SS.ms

            if event_name == "TEMP_UPDATED":
                sid = payload.get("sensor_id")
                new_val = payload.get("value")
                old_val = getattr(self._state.sensors, f"{sid}_temp", None)
                if old_val is not None:
                    delta = round(float(new_val) - float(old_val), 1)
                    if delta != 0.0:  # Only log if it actually shifted!
                        sign = "+" if delta > 0 else ""
                        log_msg = f"{ts}|🌡️ {sid} temp: {sign}{delta}°C -> {new_val:.1f}°C"
                else:
                    log_msg = f"{ts}|🌡️ {sid} temp: -> {new_val:.1f}°C"

            elif event_name == "POWER_UPDATED":
                sensor_id: str = payload.get("sensor_id", "")
                val: float = payload.get("value", 0.0)
                sns: Any = self._state.sensors

                # --- START DEBUG CODE ---
                #logger.warning(f"[DEBUG POWER] Raw Payload: {payload}")
                #logger.warning(f"[DEBUG POWER] Extracted sensor_id: '{sensor_id}' | value: {val}")
                #logger.warning(f"[DEBUG POWER] Does SensorsState have '{sensor_id}'? -> {hasattr(sns, sensor_id)}")
                #if not hasattr(sns, sensor_id):
                #    logger.warning(
                #        f"[DEBUG POWER] Missing from models.py! Routing to state.devices['{sensor_id}'] instead.")
                # --- END DEBUG CODE ---

                # Matches the exact YAML key to the internal sensor dictionary (e.g., 'pc_power')
                if hasattr(sns, sensor_id):
                    setattr(sns, sensor_id, val)
                    state_changed = True
                    changed_domains.add("sensors")
                else:
                    self._state.devices[sensor_id] = val
                    state_changed = True
                    changed_domains.add("devices")

            elif event_name == "HUMIDITY_UPDATED":
                sid = payload.get("sensor_id")
                new_val = payload.get("value")
                old_val = getattr(self._state.sensors, f"{sid}_hum", None)
                if old_val is not None:
                    delta = int(new_val) - int(old_val)
                    if delta != 0:  # Only log if it actually shifted!
                        sign = "+" if delta > 0 else ""
                        log_msg = f"{ts}|💧 {sid} humidity: {sign}{delta}% -> {new_val}%"
                else:
                    log_msg = f"{ts}|💧 {sid} humidity: -> {new_val}%"

            elif event_name == "EXTERNAL_WEATHER_UPDATED":
                self._state.sensors.sunrise_unix = payload.get("sunrise")
                self._state.sensors.sunset_unix = payload.get("sunset")
                state_changed = True
                changed_domains.add("sensors")

            elif event_name == "HUB_STATE_CHANGED":
                dev = payload.get("device_id")
                st = payload.get("state")
                log_msg = f"{ts}|🔌 {dev}: -> {st}"

            if log_msg:
                self._state.hardware.lab_simulation_logs.insert(0, log_msg)
                self._state.hardware.lab_simulation_logs = self._state.hardware.lab_simulation_logs[:50]
                state_changed = True
                changed_domains.add("hardware")

        if event_name == "SYSTEM_READY":
            self._state.hardware.live_mode = False
            self._set_hardware_safety_gate(False)
            state_changed = True
            changed_domains.add("hardware")

        elif event_name == "SYSTEM_METRICS_UPDATED":
            wanos_conn = payload.get("wanos_connected", False)
            dom_conn = payload.get("domoticz_connected", False)
            ip_addr = payload.get("ip_address", "0.0.0.0")

            # GATEWAY FAILSAFE: Only trigger updates if real mutations occurred or boot variables are blank!
            if (self._state.system.wanos_mqtt_connected != wanos_conn or
                    self._state.system.domoticz_mqtt_connected != dom_conn or
                    self._state.system.ip_address != ip_addr or
                    self._state.system.app_boot_unix is None):

                self._state.system.wanos_mqtt_connected = wanos_conn
                self._state.system.domoticz_mqtt_connected = dom_conn
                self._state.system.ip_address = ip_addr

                # Capture static Unix boot times once during host identification
                if self._state.system.app_boot_unix is None and ip_addr != "0.0.0.0":
                    import psutil
                    self._state.system.app_boot_unix = int(self._start_time)
                    self._state.system.os_boot_unix = int(psutil.boot_time())

                state_changed = True
                changed_domains.add("system")

        elif event_name == "HARDWARE_LIVE_MODE_CHANGED":
            self._state.hardware.live_mode = payload.get("live", False)
            self._set_hardware_safety_gate(self._state.hardware.live_mode)
            state_changed = True
            changed_domains.add("hardware")

        elif event_name == "LAB_SIMULATION_LOG":
            msg = payload.get("message", "")
            if msg:
                # Insert at the top (index 0) so the newest logs are first, keep max 50
                self._state.hardware.lab_simulation_logs.insert(0, msg)
                self._state.hardware.lab_simulation_logs = self._state.hardware.lab_simulation_logs[:50]
                state_changed = True
                changed_domains.add("hardware")

        # --------------------------------------------------------
        # PHYSICAL PULSE MAPPING
        # --------------------------------------------------------
        elif event_name == "WATER_PULSE":
            wtype = payload.get("fluid", "cold")
            count = payload.get("count", 1)

            for _ in range(count):
                if wtype == "cold":
                    self._state.sensors.water_cold_liters += (1.0 / 396.0)
                else:
                    self._state.sensors.water_hot_liters += (1.0 / 396.0)

                if self._state.metrics.douche_active:
                    self._state.metrics.douche_water_liters += 1

            # Forward raw pulse count to the publisher for batched, rounded MQTT emit.
            # The publisher accumulates independently and flushes on its own interval.
            if self.mqtt_publisher:
                self.mqtt_publisher.accumulate_water(wtype, count)

            state_changed = True
            changed_domains.add("sensors")
            changed_domains.add("metrics")

        elif event_name == "KWH_PULSE":
            self._state.metrics.kwh_wh_ticks += 1

            # Forward to publisher for batched Wh accumulation and periodic MQTT emit
            if self.mqtt_publisher:
                self.mqtt_publisher.accumulate_kwh(1)

            state_changed = True
            changed_domains.add("metrics")

        # --------------------------------------------------------
        # MULTI-ZONE TEMPERATURE & HUMIDITY ROUTING (SORTING OFFICE)
        # --------------------------------------------------------
        elif event_name == "TEMP_UPDATED":
            sensor_id: str = payload.get("sensor_id", "")
            val: float = payload.get("value", 0.0)
            sns: Any = self._state.sensors

            # 1. Core Engine Target: explicitly requested by internal math loop?
            if hasattr(sns, f"{sensor_id}_temp"):
                setattr(sns, f"{sensor_id}_temp", val)

                # Raw sensor value updated, ensure frontend syncs via SSE
                state_changed = True
                changed_domains.add("sensors")

                if sensor_id in ["sauna_high", "sauna_low"]:
                    if self._recalculate_sauna_metrics() or is_manual_lab_action:
                        changed_domains.add("sensors")
            # 2. Generic Peripheral Target: Store it safely for the UI
            else:
                self._state.devices[f"{sensor_id}_temp"] = val
                state_changed = True
                changed_domains.add("devices")

        elif event_name == "HUMIDITY_UPDATED":
            sensor_id: str = payload.get("sensor_id", "")
            val: int = payload.get("value", 0)
            sns: Any = self._state.sensors

            # 1. Core Engine Target
            if hasattr(sns, f"{sensor_id}_hum"):
                setattr(sns, f"{sensor_id}_hum", val)

                # Raw sensor value updated, ensure frontend syncs via SSE
                state_changed = True
                changed_domains.add("sensors")

                # ⚡ AUTOMATED BATHROOM VENTILATOR HYSTERESIS LOOP ⚡
                if sensor_id == "bathroom" and sns.bathroom_hum is not None:
                    on_threshold: int = self._config.bathroom.vent_on_humidity
                    off_threshold: int = self._config.bathroom.vent_off_humidity

                    # Engine relies entirely on the generic devices dictionary mapping
                    current_vent_state: str = self._state.devices.get("bathroom_ventilator", "OFF")

                    if sns.bathroom_hum >= on_threshold and current_vent_state != "ON":
                        self._state.devices["bathroom_ventilator"] = "ON"
                        changed_domains.add("devices")
                        msg: str = f"Bathroom humidity ({sns.bathroom_hum}%) >= ON threshold ({on_threshold}%). Auto-engaging ventilator."
                        logger.info(msg)
                        if not self._state.hardware.live_mode:
                            from datetime import datetime
                            ts: str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self._state.hardware.lab_simulation_logs.insert(0, f"{ts}|{msg}")
                    elif sns.bathroom_hum <= off_threshold and current_vent_state == "ON":
                        self._state.devices["bathroom_ventilator"] = "OFF"
                        changed_domains.add("devices")
                        msg: str = f"Bathroom humidity ({sns.bathroom_hum}%) <= OFF threshold ({off_threshold}%). Auto-disengaging ventilator."
                        logger.info(msg)
                        if not self._state.hardware.live_mode:
                            from datetime import datetime
                            ts: str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self._state.hardware.lab_simulation_logs.insert(0, f"{ts}|{msg}")

                if sensor_id in ["sauna_high", "sauna_low"]:
                    if self._recalculate_sauna_metrics() or is_manual_lab_action:
                        changed_domains.add("sensors")
            # 2. Generic Peripheral Target
            else:
                self._state.devices[f"{sensor_id}_hum"] = val
                state_changed = True
                changed_domains.add("devices")

        elif event_name == "SENSOR_ERROR":
            sid = payload.get("sensor", "unknown")
            if sid not in self._state.hardware.sensor_errors:
                self._state.hardware.sensor_errors.append(sid)
                state_changed = True
                changed_domains.add("hardware")
            if sid in ["sauna_high", "sauna_low"] and self._state.sauna.active:
                await self.logger.critical(f"Critical sensor failure on {sid}. Emergency stopping heater elements.")
                self.dispatch(Event(type=EventType.SAUNA_OFF))

        # --------------------------------------------------------
        # CORE CONTROLLER MODULE ROUTERS
        # --------------------------------------------------------
        elif event_name == "SAUNA_ON":
            door_open = self._state.devices.get("door_sauna") == "OPEN"
            if door_open:
                await self.logger.warning("🌡️ Bouncer rejected SAUNA_ON: Door is open.")
                return False, set()
            if self._state.sensors.sauna_calc_temp is None:
                await self.logger.warning(
                    "🌡️ Bouncer rejected SAUNA_ON: Temperature data is currently missing (NULL).")
                return False, set()
            self._state.sauna.active = True
            self._state.sauna.hold_mode = "autohold"
            now = int(time.time())
            self._state.sauna.session_start_time = now
            self._sauna_timer_triggered = False
            self._sauna_timer_duration_secs = self._config.sauna.default_timer * 60
            self._state.sauna.session_end_time = self._sauna_timer_duration_secs
            state_changed = True
            changed_domains.add("sauna")

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
            changed_domains.add("sauna")

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
                changed_domains.add("sauna")

        elif event_name == "HOLD_TOGGLED":
            current_mode = self._state.sauna.hold_mode
            if current_mode == "autohold":
                self._state.sauna.hold_mode = "nohold"
            elif current_mode == "hold":
                self._state.sauna.hold_mode = "nohold"
            else:
                self._state.sauna.hold_mode = "hold"
            state_changed = True
            changed_domains.add("sauna")

        elif event_name == "SAUNA_TIMER_EXPIRED":
            logger.warning("Sauna session limit countdown reached 0.")
            self.dispatch(Event(type=EventType.SAUNA_OFF))

        elif event_name == "IR_ON":
            if self._state.sensors.sauna_calc_temp is None:
                await self.logger.warning(
                    "🌡️ Bouncer rejected IR_ON: Temperature data is currently missing (NULL).")
                return False, set()
            self._state.ir.active = True
            now = int(time.time())
            self._state.ir.session_start_time = now
            self._state.ir.session_end_time = now + (self._config.ir.max_time_mins * 60)
            self._state.ir.modulation_pwm = 100
            self._state.ir.frequency = self._config.ir.pwm_freq
            self._timer_manager.schedule("ir_main", self._state.ir.session_end_time, "IR_TIMER_EXPIRED")
            state_changed = True
            changed_domains.add("ir")

        elif event_name == "IR_OFF":
            self._state.ir.active = False
            self._state.ir.modulation_pwm = 0
            self._timer_manager.cancel("ir_main")
            state_changed = True
            changed_domains.add("ir")

        elif event_name == "IR_TIMER_EXPIRED":
            self.dispatch(Event(type=EventType.IR_OFF))

        elif event_name == "DOOR_CHANGED":
            sensor_id = payload.get("sensor_id", "sauna")
            is_open = payload.get("is_open", False)
            device_key = f"door_{sensor_id}"
            new_state = "OPEN" if is_open else "CLOSED"

            # Doors are switches, so they go directly to devices!
            if self._state.devices.get(device_key) != new_state:
                self._state.devices[device_key] = new_state
                state_changed = True
                changed_domains.add("devices")

                # Sauna safety interlock logic evaluation
                if sensor_id == "sauna" and is_open and self._state.sauna.active:
                    self._state.sauna.active = False
                    self._state.sauna.modulation_pwm = 0
                    self._state.sauna.phases_pwm = [0, 0, 0]
                    self._state.sauna.ventilation_state = "OFF"
                    changed_domains.add("sauna")
                    asyncio.create_task(
                        self.logger.warning("🚪 Sauna door opened while active! Emergency cutoff triggered."))

        elif event_name == "HUB_STATE_CHANGED":
            device = payload.get("device_id")
            state_val = payload.get("state")  # "ON" or "OFF"
            old_val = self._state.devices.get(device)

            # 100% Generic Assignment. Any inbound switch event goes straight to the dict.
            if old_val != state_val:
                self._state.devices[device] = state_val
                state_changed = True
                changed_domains.add("devices")

                # 🛡️ THE GENERIC INITIALIZATION TAG 🛡️
                # If old_val is None, this is the very first time we hear about this device.
                if old_val is None:
                    payload["is_initialization"] = True
                else:
                    payload["transitioned"] = True

        elif event_name == "LIGHTING_STATE_CHANGED":
            zone = payload.get("zone")
            state_val = payload.get("state")  # "ON" or "OFF"
            target_device = f"{zone}_hue"
            if self._state.devices.get(target_device) != state_val:
                self._state.devices[target_device] = state_val
                state_changed = True
                changed_domains.add("devices")

        elif event_name == "VENT_WAIT_EXPIRED":
            self._state.sauna.ventilation_state = "RUNNING"
            self._state.devices["sauna_extrvent"] = "ON"
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_run_mins * 60)
            self._timer_manager.schedule("vent_run", self._state.sauna.ventilation_deadline, "VENT_RUN_EXPIRED")
            state_changed = True
            changed_domains.add("sauna")
            changed_domains.add("devices")

        elif event_name == "VENT_RUN_EXPIRED":
            self._state.sauna.ventilation_state = "OFF"
            self._state.devices["sauna_extrvent"] = "OFF"
            self._state.sauna.ventilation_deadline = None
            state_changed = True
            changed_domains.add("sauna")
            changed_domains.add("devices")

        elif event_name == "SETPOINT_CHANGED":
            new_target = payload.get("target")
            if new_target is not None:
                self._state.sauna.target_temp = min(float(new_target), self._state.sauna.max_temp)
                state_changed = True
                changed_domains.add("sauna")

        elif event_name == "MODULATION_UPDATED":
            self._state.sauna.modulation_pwm = payload.get("pwm", 0)
            self._state.sauna.phases_pwm = payload.get("phases", [0, 0, 0])
            state_changed = True
            changed_domains.add("sauna")

        if event_name in ["TEMP_UPDATED", "SAUNA_ON", "SAUNA_OFF", "SETPOINT_CHANGED", "DOOR_CHANGED"]:
            current_temp = self._state.sensors.sauna_calc_temp
            if current_temp is not None and self._state.sauna.active:

                # ⏱️ CONFIGURABLE TIMER COUNTDOWN EVALUATION GATEWAY
                offset = getattr(self._config.sauna, "timer_offset_temp", 7.0)
                threshold_temp = self._state.sauna.target_temp - offset

                if not self._sauna_timer_triggered:
                    if current_temp >= threshold_temp:
                        self._sauna_timer_triggered = True
                        self._state.sauna.session_end_time = int(time.time()) + self._sauna_timer_duration_secs
                        self._timer_manager.schedule("sauna_main", self._state.sauna.session_end_time,
                                                     "SAUNA_TIMER_EXPIRED")
                        logger.info(
                            f"Heat threshold met ({current_temp}°C >= {threshold_temp}°C). Activating timer countdown!")
                        state_changed = True
                        changed_domains.add("sauna")
                    else:
                        if self._state.sauna.session_end_time != self._sauna_timer_duration_secs:
                            self._state.sauna.session_end_time = self._sauna_timer_duration_secs
                            state_changed = True
                            changed_domains.add("sauna")

                # AUTOMATIC HOLD STEPPING INTERRUPT:
                if current_temp >= self._state.sauna.target_temp:
                    if self._state.sauna.hold_mode == "autohold":
                        self._state.sauna.hold_mode = "hold"
                        logger.info("Setpoint met! System automatically dropped load: autohold -> hold")
                        state_changed = True
                        changed_domains.add("sauna")

                calc_result = self.sauna_logic.evaluate(self._state)
                if calc_result:
                    self._state.sauna.modulation_pwm = calc_result.get("pwm", 0)
                    self._state.sauna.phases_pwm = calc_result.get("phases", [0, 0, 0])
                    state_changed = True
                    changed_domains.add("sauna")

        # --- DEFENSIVE RE-RENDER CHECKPOINT ---
        from logic.auxiliary_controller import AuxiliaryController
        from logic.automation_rules import AutomationEngine

        old_lcd_text: str = self._state.sauna.lcd_text
        old_light_color: str = self._state.sauna.light_color
        old_fireorder: str = self._state.sauna.fireorder

        # Delegate display and lighting logic cleanly to the pure business logic controller
        self._state.sauna = AuxiliaryController.evaluate(self._state)

        if not self._state.sauna.active:
            self._state.sauna.fireorder = "--"
        else:
            raw_order = self.sauna_logic.get_current_order_string()
            self._state.sauna.fireorder = raw_order.replace(" -> ", "")

        if (self._state.sauna.lcd_text != old_lcd_text or
                self._state.sauna.light_color != old_light_color or
                self._state.sauna.fireorder != old_fireorder):
            state_changed = True
            changed_domains.add("sauna")

        # ⚡ AUTOMATION ENGINE HOOK ⚡
        # Evaluates the current event and dispatches any automated downstream cascades or scenes.
        for auto_event in AutomationEngine.evaluate(event, self._state):
            self.dispatch(auto_event)

        return state_changed, changed_domains

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

        def _is_connected(client_mgr) -> bool:
            if not client_mgr:
                return False
            if hasattr(client_mgr, "client") and client_mgr.client is not None:
                if hasattr(client_mgr.client, "is_connected"):
                    return client_mgr.client.is_connected()
                return True
            return False

        while True:
            try:
                await asyncio.sleep(2.0)
                metrics_payload = {
                    "wanos_connected": _is_connected(self.mqtt_client),
                    "domoticz_connected": _is_connected(self.domoticz_client),
                    "ip_address": _get_ip()
                }
                self.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED, payload=metrics_payload))
            except asyncio.CancelledError:
                break
            except Exception:
                pass