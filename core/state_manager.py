# --- file: core/state_manager.py ---
import asyncio
import time
import re
import json
from datetime import datetime
from typing import Optional, Any, Set
from loguru import logger

from .models import SystemState, Event, EventType
from .mqtt_transport import MqttClientManager
from .logger import WanosLogger, automation_logger
from .config import load_config
from integrations.epson import EpsonProjector

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
        self.domoticz_client: Optional[Any] = None  # Populated dynamically by Domoticz bridge
        self.rfxcom_bridge: Optional[Any] = None  # ⚡ Populated dynamically by Native RFXCOM bridge
        self.hue_bridge: Optional[Any] = None  # ⚡ Populated dynamically by local Hue API v2 bridge
        self.epson_bridge: Optional[Any] = None
        self.logger: WanosLogger = logger

        # Optional reference to the MqttPublisher, injected after construction.
        # If set, pulse events are forwarded to it for accumulation and batched emit.
        self.mqtt_publisher: Optional[Any] = None

        self._start_time = time.time()  # Track initialization timestamp for Engine Uptime calculation

        # Track rolling data windows for moving averages
        # Modified to expect integer IDXs as dictionary keys
        self._sensor_history: dict[int, list[float]] = {}

        # Load centralized configuration profiles
        self._config = load_config()

        # Transfer the parsed dictionary from the static config
        # into the live SystemState so it gets sent to app.js during the initial /api/state fetch!
        self._state.dashboard_map = self._config.dashboard

        # ⚡ Map the excluded UI devices to the live state payload
        self._state.system.hidden_explorer_idxs = self._config.deviceexplorer_exclude

        # ⚡ STALE CACHE PURGE & COMPREHENSIVE ALLOCATION: Pre-fill the state dictionary with explicit None values
        # for every unique raw integer IDX mentioned anywhere in config.yaml (Dashboard, Managed Lights,
        # and Automation Triggers/Actions). This forces the frontend to overwrite its stale UI cache
        # with 'null', triggering the "SYNCING..." visual state upon reconnect, and ensures no device stays untracked.
        all_config_idxs = set()
        if hasattr(self._config, "dashboard"):
            all_config_idxs.update(k for k in self._config.dashboard.keys() if isinstance(k, int))
        if hasattr(self._config, "lighting") and self._config.lighting.managed_lights:
            all_config_idxs.update(idx for idx in self._config.lighting.managed_lights if isinstance(idx, int))
        if hasattr(self._config, "automations"):
            for rule in self._config.automations:
                triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]
                for t in triggers:
                    if t.idx is not None:
                        all_config_idxs.add(t.idx)
                if rule.actions:
                    for action in rule.actions:
                        if action.idx is not None:
                            all_config_idxs.add(action.idx)

        for idx in all_config_idxs:
            if idx < 10000:  # Only track real external hardware components
                self._state.devices[idx] = None

        # ⚡ NATIVE RFX AUTO-INITIALIZATION
        # Maps the RFX devices and forcefully sets them to "OFF" since 433MHz is stateless and can't be queried.
        if hasattr(self._config, "native_rfx"):
            for rfx_dev in self._config.native_rfx:
                self._state.system.native_rfx_devices.append({
                    "name": rfx_dev.name,
                    "virtual_idx": rfx_dev.virtual_idx
                })
                self._state.dashboard_map[rfx_dev.virtual_idx] = rfx_dev.name
                self._state.device_metadata[rfx_dev.virtual_idx] = {"name": rfx_dev.name, "type": "switch",
                                                                    "origin": "rfxcom"}
                self._state.devices[rfx_dev.virtual_idx] = "OFF"

        # ⚡ LOCAL HUE AUTO-INITIALIZATION
        # Pre-seeds the device registry so advanced lights and room groups appear in the UI immediately on boot.
        if hasattr(self._config, "hue") and getattr(self._config, "hue", None):
            # Seed individual bulb channels (5000x block)
            for idx_int in self._config.hue.device_map.keys():
                semantic_name = self._state.dashboard_map.get(idx_int, f"Hue Light {idx_int}")
                self._state.dashboard_map[idx_int] = semantic_name
                self._state.device_metadata[idx_int] = {
                    "name": semantic_name,
                    "type": "light",
                    "origin": "hue"
                }
                self._state.devices[idx_int] = None

            # Seed collective room/zone groups (5100x block)
            group_map = getattr(self._config.hue, "group_map", {})
            for idx_int in group_map.keys():
                semantic_name = self._state.dashboard_map.get(idx_int, f"Hue Group {idx_int}")
                self._state.dashboard_map[idx_int] = semantic_name
                self._state.device_metadata[idx_int] = {
                    "name": semantic_name,
                    "type": "light",
                    "origin": "hue"
                }
                self._state.devices[idx_int] = None

        # ⚡ EPSON PROJECTOR AUTO-INITIALIZATION
        # Pre-seeds the projector to OFF since it cannot report its physical state on boot
        if getattr(self._config, "epson", None):
            self._state.dashboard_map[80001] = "Epson Projector"
            self._state.device_metadata[80001] = {
                "name": "Epson Projector",
                "type": "switch",
                "origin": "epson"
            }
            self._state.devices[80001] = "OFF"

        # Dynamically scan configuration file for stateless triggers
        self._extract_scenes_from_config()

    def _extract_scenes_from_config(self) -> None:
        """Scans the automations configuration for stateless events to expose as scenes in the dynamic UI."""
        self._state.system.available_scenes.clear()
        if hasattr(self._config, "automations"):
            for rule in self._config.automations:
                # ⚡ Explicitly filter out background macros; only expose rules flagged as scenes
                if getattr(rule, "scene", False) is not True:
                    continue
                triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]
                for t in triggers:
                    if t.event:
                        # Avoid duplicates if multiple backend rules trigger on the exact same event string
                        if not any(s["event"] == t.event for s in self._state.system.available_scenes):
                            self._state.system.available_scenes.append({
                                "name": rule.name,
                                "event": t.event
                            })

    def register_listener(self, callback: Any) -> None:
        """Registers an async callback to be triggered on post-drain state snapshots."""
        self._state_listeners.append(callback)
        self._state.sauna.target_temp = float(self._config.sauna.default_sauna_setpoint)
        self._state.sauna.max_temp = float(self._config.sauna.max_temp)
        self._state.boot_seed = self._config.boot_seed

        # ⚡ Initialize IR Setpoint from config so it shows default on boot while OFF
        self._state.ir.modulation_pwm = self._config.ir.default_ir_modulation
        freq_map = {0: 0, 25: 25, 33: 33, 50: 50, 67: 33, 75: 25, 100: 5}
        # If an invalid default (e.g. 42%) is placed in config.yaml, fallback safely to 0Hz
        self._state.ir.frequency = freq_map.get(self._state.ir.modulation_pwm, 0)

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
        except ValueError:
            # ⚡ Fall back to raw string for dynamic custom scenes
            e_type = event_type_str

        self.dispatch(Event(type=e_type, payload=payload))

    def get_state_snapshot(self) -> SystemState:
        return self._state.model_copy(deep=True)

    def _set_hardware_safety_gate(self, state: bool) -> None:
        self._state.hardware.safety_pin_active = state
        if self._gpio_chip and LGPIO_AVAILABLE:
            try:
                val = 1 if state else 0
                lgpio.gpio_write(self._gpio_chip, self._config.pins.safety_gpio, val)
            except Exception as e:
                logger.error(f"Safety Relay Error: Write failed - {e}")

    def _recalculate_sauna_metrics(self) -> bool:
        """
        Mathematical calculation combining the two physical SHT11 temperature probes
        (Ceiling probe via virtual IDX 20001 and Bench probe via virtual IDX 20002)
        into a single smoothed virtual metric (sauna_calc_temp).
        Note for Programmers: This calculated metric is what actually drives the PID heating logic!
        """
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

    def _recalculate_environmental_schedule(self) -> None:
        """
        🌍 The Daily Time-Series Engine (Schedule Calculator)
        This function dynamically calculates exact UNIX timestamps for today's environmental phases.
        It runs whenever OWM fetches weather, applying Min/Max logic (Clamps) to prevent edge cases
        like blinds opening at 4:30 AM in mid-summer.
        """
        sns = self._state.sensors
        cfg = self._config.environmental_schedule
        if not sns.sunrise_unix or not sns.sunset_unix or not cfg:
            return

        def _get_unix_for_today(time_str: str) -> int:
            try:
                h, m = map(int, time_str.split(':'))
                now = datetime.now()
                target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                return int(target.timestamp())
            except (ValueError, AttributeError):
                return 0

        # --- Phase 1: BLINDS CLAMPING MATH ---
        mo_early = _get_unix_for_today(cfg.blinds.morning_open_earliest)
        mo_late = _get_unix_for_today(cfg.blinds.morning_open_latest)
        ec_early = _get_unix_for_today(cfg.blinds.evening_close_earliest)
        ec_late = _get_unix_for_today(cfg.blinds.evening_close_latest)

        # Open = Max(Sunrise, 07:30). If 09:00 limit exists, clamp Open = Min(Open, 09:00).
        blinds_open = max(sns.sunrise_unix, mo_early)
        if mo_late > 0: blinds_open = min(blinds_open, mo_late)

        # Close = Max(Sunset, 16:30). If 22:00 limit exists, clamp Close = Min(Close, 22:00).
        blinds_close = max(sns.sunset_unix, ec_early)
        if ec_late > 0: blinds_close = min(blinds_close, ec_late)

        # --- Phase 2: TWILIGHT LOGIC ---
        twi_eve_on = sns.sunset_unix
        twi_eve_off = _get_unix_for_today(cfg.twilight.evening_off_time)
        twi_morn_on = _get_unix_for_today(cfg.twilight.morning_on_time)
        twi_morn_off = sns.sunrise_unix

        # Store to unified State Memory
        sns.env_schedule_blinds_open_unix = blinds_open
        sns.env_schedule_blinds_close_unix = blinds_close
        sns.env_schedule_twilight_evening_on_unix = twi_eve_on
        sns.env_schedule_twilight_evening_off_unix = twi_eve_off

        # ⚡ Edge Case Protection: Skip morning twilight entirely if sunrise occurs BEFORE the configured on-time
        if twi_morn_off > twi_morn_on:
            sns.env_schedule_twilight_morning_on_unix = twi_morn_on
            sns.env_schedule_twilight_morning_off_unix = twi_morn_off
        else:
            sns.env_schedule_twilight_morning_on_unix = None
            sns.env_schedule_twilight_morning_off_unix = None

        # --- Phase 3: SCHEDULER DEPLOYMENT ---
        now_unix = int(time.time())
        # ⚡ Dispatched dynamically to the bus so the Glass-Box Timeline UI registers them instantly.
        # Metadata mapping is handled automatically downstream via Subscriber Fan-Out logic.
        if blinds_open > now_unix:
            self.dispatch(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_blinds_open", "deadline": blinds_open, "event_type": "BLINDS_OPEN_TRIGGER",
                "event_payload": {}
            }))
        if blinds_close > now_unix:
            self.dispatch(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_blinds_close", "deadline": blinds_close, "event_type": "BLINDS_CLOSE_TRIGGER",
                "event_payload": {}
            }))
        if twi_eve_on > now_unix:
            self.dispatch(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_eve_on", "deadline": twi_eve_on, "event_type": "TWILIGHT_EVENING_ON_TRIGGER",
                "event_payload": {}
            }))
        if twi_eve_off > now_unix:
            self.dispatch(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_eve_off", "deadline": twi_eve_off,
                "event_type": "TWILIGHT_EVENING_OFF_TRIGGER",
                "event_payload": {}
            }))
        if sns.env_schedule_twilight_morning_on_unix and sns.env_schedule_twilight_morning_on_unix > now_unix:
            self.dispatch(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_morn_on", "deadline": sns.env_schedule_twilight_morning_on_unix,
                "event_type": "TWILIGHT_MORNING_ON_TRIGGER",
                "event_payload": {}
            }))
        if sns.env_schedule_twilight_morning_off_unix and sns.env_schedule_twilight_morning_off_unix > now_unix:
            self.dispatch(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_morn_off", "deadline": sns.env_schedule_twilight_morning_off_unix,
                "event_type": "TWILIGHT_MORNING_OFF_TRIGGER",
                "event_payload": {}
            }))

        logger.debug("🌍 Environmental Time-Series mathematically calculated and deployed.")

    async def _process_events(self) -> None:
        """
        Sequential event execution loop with outbound network batch debouncing.
        Drains the queue fully before broadcasting.
        """
        pending_broadcast = False
        changed_domains: Set[str] = set()
        batch_events: list[Event] = []  # ⚡ Collect events that triggered changes

        while True:
            event: Event = await self._queue.get()
            try:
                changed, domains = await self._handle_event(event)
                if changed:
                    pending_broadcast = True
                    changed_domains.update(domains)
                    batch_events.append(event)  # ⚡ Add causal event to batch
            except Exception as e:
                await self.logger.error(f"Error handling event {event.type.value}: {e}")
            finally:
                self._queue.task_done()

            if pending_broadcast and self._queue.empty():
                snapshot_obj: SystemState = self.get_state_snapshot()

                if self.mqtt_publisher:
                    try:
                        await self.mqtt_publisher.on_state_changed(snapshot_obj, changed_domains)
                    except Exception as e:
                        await self.logger.error(f"Error in MQTT publisher: {e}")

                # Notify all other registered state listeners (e.g., Domoticz bridge)
                for listener in self._state_listeners:
                    try:
                        # ⚡ Pass the batch_events so listeners know WHY the state changed!
                        await listener(snapshot_obj, batch_events)
                    except Exception as e:
                        await self.logger.error(f"Error in state listener: {e}")

                pending_broadcast = False
                changed_domains.clear()
                batch_events.clear()  # ⚡ Clear the batch for the next round

    def _push_alert(self, *msgs: Optional[str], domain: str = "system") -> tuple[bool, Set[str]]:
        """
        Safely timestamps, deduplicates, and structures UI alerts into routing dictionaries.
        Auto-classifies severity based on emojis to maintain backwards compatibility
        with all existing log strings across the architecture!
        """
        changed = False
        domains: Set[str] = set()
        import uuid

        for raw_msg in msgs:
            if not raw_msg:
                continue

            # ⚡ Auto-classify severity and strip legacy emojis for clean JSON delivery
            level = "info"
            clean_msg = raw_msg

            if "🔴 CRITICAL" in raw_msg:
                level = "critical"
                clean_msg = raw_msg.replace("🔴 CRITICAL:", "").replace("🔴 CRITICAL", "").strip()
            elif "🔴" in raw_msg:
                level = "warning"
                clean_msg = raw_msg.replace("🔴", "").strip()
            elif "🟢 SUCCESS" in raw_msg:
                level = "success"
                clean_msg = raw_msg.replace("🟢 SUCCESS:", "").replace("🟢 SUCCESS", "").strip()
            elif "🟢" in raw_msg:
                level = "success"
                clean_msg = raw_msg.replace("🟢", "").strip()
            elif "🧹" in raw_msg:
                level = "info"
                clean_msg = raw_msg.replace("🧹", "").strip()
            elif "🔄" in raw_msg:
                level = "info"
                clean_msg = raw_msg.replace("🔄", "").strip()

            timestamp: str = datetime.now().strftime("%-d/%b %H:%M:%S")
            msg_handled = False

            # Prevent spam & increment counter: Check if base message is already active
            for existing in self._state.system.system_alert_msgs:
                if existing.get("message") == clean_msg:
                    existing["count"] = existing.get("count", 1) + 1
                    existing["timestamp"] = timestamp  # Refresh UI time on re-occurrence
                    changed = True
                    domains.add(domain)
                    msg_handled = True
                    break

            # Brand new message: Append as structured dictionary!
            if not msg_handled:
                self._state.system.system_alert_msgs.append({
                    "id": str(uuid.uuid4())[:8],
                    "level": level,
                    "message": clean_msg,
                    "timestamp": timestamp,
                    "count": 1
                })
                changed = True
                domains.add(domain)

        return changed, domains

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

        # ⚡ DYNAMIC METADATA REGISTRY HOOK
        # Intercept any payload that carries a device_type and name, logging it into the global UI registry.
        meta_idx = payload.get("idx")
        meta_type = payload.get("device_type")
        meta_name = payload.get("name")
        meta_origin = payload.get("origin")

        if meta_idx is not None and meta_type is not None:
            existing = self._state.device_metadata.get(meta_idx)
            if not existing or existing.get("type") != meta_type or existing.get("name") != meta_name or existing.get(
                    "origin") != meta_origin:
                self._state.device_metadata[meta_idx] = {
                    "name": meta_name or f"idx_{meta_idx}",
                    "type": meta_type,
                    "origin": meta_origin
                }
                state_changed = True
                changed_domains.add("device_metadata")

        # --- LIVE TERMINAL LOGGING INJECTION GATEWAY ---
        is_manual_lab_action = payload.get("lab_override", False)
        is_boot_baseline_seed = payload.get("boot_seed", False)
        is_simulation_action = payload.get("from_simulator", False)
        is_user_command = event_name in [
            "SAUNA_ON", "SAUNA_OFF", "SAUNA_SETPOINT_CHANGED", "SAUNA_MODULATION_UPDATED",
            "SAUNA_HOLD", "SAUNA_HOLD_TOGGLED", "SAUNA_TIMER_ADJUSTED", "IR_ON", "IR_OFF", "IR_MODULATION_UPDATED"
        ]

        if event_name == "SYSTEM_READY":
            logger.info("Internal Engine State validated and locked.")
            logger.info(f"Internal Event Processed: {event_name}")
        elif (is_user_command or is_manual_lab_action) and not is_simulation_action and not is_boot_baseline_seed:
            logger.info(f"Lab Action Received: {event_name} | Payload: {payload}")
            await self.logger.info(f"User Action Processed: {event_name}")
        elif event_name != "SYSTEM_METRICS_UPDATED":
            # Captures background automation, external bridges, and simulated physics ticks
            if is_simulation_action or is_boot_baseline_seed:
                origin_tag = ""
                if is_simulation_action:
                    origin_tag = " [SIMULATION]"
                elif is_boot_baseline_seed:
                    origin_tag = " [BOOT_SEED]"
                logger.debug(f"Event Received [{event_name}]{origin_tag}: {payload}")

            # ⚡ Domoticz HTTP Boot-Sync formatting interceptor
            elif event_name == "HUB_STATE_CHANGED" and payload.get("is_initialization") and payload.get(
                    "origin") == "domoticz":
                d_idx = payload.get("idx")
                d_name = payload.get("name", "Unknown")
                d_state = payload.get("state")
                logger.info(f"--> Domoticz sensor idx {d_idx} ({d_name}): initial state received: {d_state}")

            elif event_name != "POWER_UPDATED":
                logger.info(f"Event Received [{event_name}]: {payload}")

        # --- HARDWARE TELEMETRY ROUTERS ---
        if event_name == "POWER_UPDATED":
            idx: int = payload.get("idx")
            raw_val: float = payload.get("value", 0.0)
            sns: Any = self._state.sensors
            moving_avg = 10

            # Initialize tracking histories in RAM if absent
            # Using the raw integer IDXs for the moving average buffer keys
            if idx not in self._sensor_history:
                self._sensor_history[idx] = []

            history = self._sensor_history[idx]

            if raw_val == 0.0:
                # Flush the math buffer so the moving average drops to zero instantly
                history.clear()
                history.append(0.0)
            else:
                history.append(raw_val)
                if len(history) > moving_avg:
                    history.pop(0)

            # Compute smoothed moving average aggregate
            avg_val = round(sum(history) / len(history), 1)

            # ⚡ GENERIC CATCH-ALL: Universally store ALL power sensors in the generic registry
            if self._state.devices.get(idx) != avg_val:
                self._state.devices[idx] = avg_val
                state_changed = True
                changed_domains.add("devices")

            # Route explicitly mapped core IDXs to their semantic SensorsState variables
            # 9 = pc_power, 9622 = pc_aux_power
            if idx == 9:
                if avg_val == 0.0:
                    sns.pc_power_history = [0.0] * moving_avg
                elif len(sns.pc_power_history) == 0:
                    sns.pc_power_history = [avg_val] * moving_avg
                else:
                    sns.pc_power_history.append(avg_val)
                    if len(sns.pc_power_history) > moving_avg:
                        sns.pc_power_history.pop(0)

                if sns.pc_power != avg_val:
                    sns.pc_power = avg_val
                    state_changed = True
                    changed_domains.add("sensors")

            elif idx == 9622:
                if avg_val == 0.0:
                    sns.pc_aux_power_history = [0.0] * moving_avg
                elif len(sns.pc_aux_power_history) == 0:
                    sns.pc_aux_power_history = [avg_val] * moving_avg
                else:
                    sns.pc_aux_power_history.append(avg_val)
                    if len(sns.pc_aux_power_history) > moving_avg:
                        sns.pc_aux_power_history.pop(0)

                if sns.pc_aux_power != avg_val:
                    sns.pc_aux_power = avg_val
                    state_changed = True
                    changed_domains.add("sensors")

        elif event_name == "EXTERNAL_WEATHER_UPDATED":
            # Map absolute sun cycles cleanly into state tracking arrays
            self._state.sensors.sunrise_unix = payload.get("sunrise")
            self._state.sensors.sunset_unix = payload.get("sunset")
            state_changed = True
            changed_domains.add("sensors")
            # ⚡ Trigger recalculation instantly when weather cycles shift
            self._recalculate_environmental_schedule()

        # --- SYSTEM STATE ROUTERS ---
        elif event_name == "SYSTEM_READY":
            self._state.hardware.live_mode = False
            self._set_hardware_safety_gate(False)
            state_changed = True
            changed_domains.add("hardware")

        elif event_name == "SYSTEM_METRICS_UPDATED":
            wanos_conn = payload.get("wanos_connected", False)
            dom_conn = payload.get("domoticz_connected", False)
            rfx_conn = payload.get("rfxcom_connected", False)
            hue_conn = payload.get("hue_connected", False)
            epson_conn = payload.get("epson_connected", False)
            ip_addr = payload.get("ip_address", "0.0.0.0")

            prev_wanos = self._state.system.wanos_mqtt_connected
            prev_dom = self._state.system.domoticz_mqtt_connected
            prev_rfx = self._state.system.rfxcom_connected
            prev_hue = self._state.system.hue_connected
            prev_epson = self._state.system.epson_connected

            # --- UI CONNECTION TRANSITION ALERTS & RECOVERY ---
            # 1. Local WanOS Broker
            if prev_wanos and not wanos_conn:
                ch, dom = self._push_alert("🔴 CRITICAL: Local MQTT Broker offline")
                state_changed |= ch  # state_changed |= ch is shorthand for state_changed = state_changed or ch
                changed_domains |= dom
            elif not prev_wanos and wanos_conn and self._state.system.app_boot_unix is not None:
                ch, dom = self._push_alert("🟢 SUCCESS: Local MQTT Broker back online")
                state_changed |= ch
                changed_domains |= dom

            # 2. Domoticz Broker
            if prev_dom and not dom_conn:
                ch, dom = self._push_alert("🔴 CRITICAL: Domoticz MQTT Broker Connection down")
                state_changed |= ch
                changed_domains |= dom
            elif not prev_dom and dom_conn and self._state.system.app_boot_unix is not None:
                ch, dom = self._push_alert("🟢 SUCCESS: Domoticz MQTT Broker Connection back online")
                state_changed |= ch
                changed_domains |= dom
                if not self._state.system.domoticz_integration_enabled:
                    self.dispatch(
                        Event(type=EventType.DOMOTICZ_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

            # 3. Native RFXCOM USB Serial
            if prev_rfx and not rfx_conn:
                ch, dom = self._push_alert("🔴 CRITICAL: Native RFXCOM USB Transceiver offline or disconnected")
                state_changed |= ch
                changed_domains |= dom
            elif not prev_rfx and rfx_conn and self._state.system.app_boot_unix is not None:
                ch, dom = self._push_alert("🟢 SUCCESS: Native RFXCOM USB Transceiver mounted")
                state_changed |= ch
                changed_domains |= dom
                if not self._state.system.rfxcom_integration_enabled:
                    self.dispatch(
                        Event(type=EventType.RFXCOM_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

            # 4. Local Hue Bridge
            if prev_hue and not hue_conn:
                ch, dom = self._push_alert("🔴 CRITICAL: Local Hue Bridge connection lost")
                state_changed |= ch
                changed_domains |= dom
            elif not prev_hue and hue_conn and self._state.system.app_boot_unix is not None:
                ch, dom = self._push_alert("🟢 SUCCESS: Local Hue Bridge connected via API v2")
                state_changed |= ch
                changed_domains |= dom
                if not self._state.system.hue_integration_enabled:
                    self.dispatch(
                        Event(type=EventType.HUE_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

            # 5. Epson Projector TCP
            if prev_epson and not epson_conn:
                ch, dom = self._push_alert("🔴 CRITICAL: Epson Projector TCP connection lost (Unplugged?)")
                state_changed |= ch
                changed_domains |= dom
            elif not prev_epson and epson_conn and self._state.system.app_boot_unix is not None:
                ch, dom = self._push_alert("🟢 SUCCESS: Epson Projector TCP socket responding")
                state_changed |= ch
                changed_domains |= dom
                if not self._state.system.epson_integration_enabled:
                    self.dispatch(
                        Event(type=EventType.EPSON_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

            # GATEWAY FAILSAFE: Only trigger updates if real mutations occurred or boot variables are blank!
            if (prev_wanos != wanos_conn or
                    prev_dom != dom_conn or
                    prev_rfx != rfx_conn or
                    prev_hue != hue_conn or
                    prev_epson != epson_conn or
                    self._state.system.ip_address != ip_addr or
                    self._state.system.app_boot_unix is None):
                self._state.system.wanos_mqtt_connected = wanos_conn
                self._state.system.domoticz_mqtt_connected = dom_conn
                self._state.system.rfxcom_connected = rfx_conn
                self._state.system.hue_connected = hue_conn
                self._state.system.epson_connected = epson_conn
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

        elif event_name == "AUTOMATIONS_TOGGLED":
            is_enabled = payload.get("enabled", True)
            state_str = "ON" if is_enabled else "OFF"
            self._state.system.automations_enabled = is_enabled
            state_changed = True
            changed_domains.add("system")

            color = "🟢" if is_enabled else "🔴"
            ch, dom = self._push_alert(f"{color} Automations engine turned {state_str}")
            state_changed |= ch
            changed_domains |= dom

            automation_logger.info(f"Master Toggle -> Automations Engine set to {state_str}")

        elif event_name == "DOMOTICZ_TOGGLED":
            is_enabled = payload.get("enabled", False)
            state_str = "ON" if is_enabled else "OFF"
            self._state.system.domoticz_integration_enabled = is_enabled
            state_changed = True
            changed_domains.add("system")

            color = "🟢" if is_enabled else "🔴"
            raw_error = payload.get("error_msg")
            error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
            ch, dom = self._push_alert(error_alert, f"{color} Domoticz polling turned {state_str}")
            state_changed |= ch
            changed_domains |= dom

            # --- THE UX WIPE (NULLIFICATION) ---
            if not is_enabled:
                for idx in list(self._state.devices.keys()):
                    if isinstance(idx, int) and idx < 10000:
                        if self._state.devices[idx] is not None:
                            self._state.devices[idx] = None
                            state_changed = True
                            changed_domains.add("devices")
            else:
                # ⚡ DEBOUNCED AUTO-SWEEP SCHEDULER
                # Only trigger sweeps if this was an automatic network recovery! Manual UI clicks stay silent.
                if payload.get("is_auto_recovery", False):
                    deadline = int(time.time()) + 10
                    self._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED",
                                                 {"reason": "network_recovery"})
                    logger.info("Domoticz Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

        elif event_name == "RFXCOM_TOGGLED":
            is_enabled = payload.get("enabled", False)
            state_str = "ON" if is_enabled else "OFF"
            self._state.system.rfxcom_integration_enabled = is_enabled
            state_changed = True
            changed_domains.add("system")

            color = "🟢" if is_enabled else "🔴"
            raw_error = payload.get("error_msg")
            error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
            ch, dom = self._push_alert(error_alert, f"{color} Native RFXCOM Engine turned {state_str}")
            state_changed |= ch
            changed_domains |= dom

            if is_enabled and payload.get("is_auto_recovery", False):
                deadline = int(time.time()) + 10
                self._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED",
                                             {"reason": "network_recovery"})
                logger.info("RFXCOM Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

        elif event_name == "OWM_TOGGLED":
            is_enabled = payload.get("enabled", False)
            state_str = "ON" if is_enabled else "OFF"
            self._state.system.owm_integration_enabled = is_enabled
            state_changed = True
            changed_domains.add("system")

            color = "🟢" if is_enabled else "🔴"
            raw_error = payload.get("error_msg")
            error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
            ch, dom = self._push_alert(error_alert, f"{color} OWM Integration turned {state_str}")
            state_changed |= ch
            changed_domains |= dom

            if is_enabled and payload.get("is_auto_recovery", False):
                deadline = int(time.time()) + 10
                self._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED",
                                             {"reason": "network_recovery"})
                logger.info("OWM Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

        elif event_name == "HUE_TOGGLED":
            is_enabled = payload.get("enabled", False)
            state_str = "ON" if is_enabled else "OFF"
            self._state.system.hue_integration_enabled = is_enabled
            state_changed = True
            changed_domains.add("system")

            color = "🟢" if is_enabled else "🔴"
            raw_error = payload.get("error_msg")
            error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
            ch, dom = self._push_alert(error_alert, f"{color} Hue Integration turned {state_str}")
            state_changed |= ch
            changed_domains |= dom

            if is_enabled and payload.get("is_auto_recovery", False):
                deadline = int(time.time()) + 10
                self._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED",
                                             {"reason": "network_recovery"})
                logger.info("Hue Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

        elif event_name == "EPSON_TOGGLED":
            is_enabled = payload.get("enabled", False)
            state_str = "ON" if is_enabled else "OFF"
            self._state.system.epson_integration_enabled = is_enabled
            state_changed = True
            changed_domains.add("system")

            color = "🟢" if is_enabled else "🔴"
            raw_error = payload.get("error_msg")
            error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
            ch, dom = self._push_alert(error_alert, f"{color} Epson Integration turned {state_str}")
            state_changed |= ch
            changed_domains |= dom

            if is_enabled and payload.get("is_auto_recovery", False):
                deadline = int(time.time()) + 10
                self._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED",
                                             {"reason": "network_recovery"})
                logger.info("Epson Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

        elif event_name == "SIMULATIONS_TOGGLED":
            self._state.hardware.simulations_enabled = payload.get("enabled", False)
            state_changed = True
            changed_domains.add("hardware")

        elif event_name == "ALERT_DISMISSED":
            msg_to_remove = payload.get("id")
            original_len = len(self._state.system.system_alert_msgs)
            self._state.system.system_alert_msgs = [
                msg for msg in self._state.system.system_alert_msgs
                if msg.get("id") != msg_to_remove
            ]
            if len(self._state.system.system_alert_msgs) != original_len:
                state_changed = True
                changed_domains.add("system")

        elif event_name == "ALERT_CLEAR_NON_CRITICAL":
            original_len = len(self._state.system.system_alert_msgs)
            self._state.system.system_alert_msgs = [
                msg for msg in self._state.system.system_alert_msgs
                if msg.get("level") == "critical"
            ]
            if len(self._state.system.system_alert_msgs) != original_len:
                state_changed = True
                changed_domains.add("system")

        elif event_name == "ALERT_INJECTED":
            errmsg_to_send = payload.get("msg_text", "")
            ch, dom = self._push_alert(errmsg_to_send)
            state_changed |= ch
            changed_domains |= dom

        elif event_name == "CONFIG_RELOAD_REQUESTED":
            await self.logger.info("🔄 Configuration hot-reload requested via UI button.")
            try:
                from logic.automation_rules import AutomationEngine
                new_config = load_config()
                self._config = new_config
                AutomationEngine._config = None  # Reset rules engine cached reference copy

                # Hybrid Learning Option B: Cumulative map update preserving dynamic allocations
                for idx, name in new_config.dashboard.items():
                    self._state.dashboard_map[idx] = name

                # ⚡ Sync the Explorer Exclusion List
                # Overwrites the live RAM state with the fresh list from the hard drive so the UI hides the dropped devices
                self._state.system.hidden_explorer_idxs = new_config.deviceexplorer_exclude

                # ⚡ Re-extract scenes dynamically in case the user added new ones to config.yaml
                self._extract_scenes_from_config()

                # ⚡ RECYCLE HUE INTEGRATION MAPPINGS & CONNECTIONS
                # Triggers full lifecycle stop/start teardown sequence to bind to configuration mutations seamlessly
                if self.hue_bridge:
                    await self.hue_bridge.stop()
                    self.hue_bridge._config = new_config
                    self.hue_bridge._initialize_mappings()
                    await self.hue_bridge.start()

                state_changed = True
                changed_domains.add("system")

                # num_rules: int = len(new_config.automations)
                msg: str = f"🟢 Config reloaded."  #: {num_rules} automations activated."
                ch, dom = self._push_alert(msg)
                state_changed |= ch
                changed_domains |= dom

                # Automatically trigger a system sweep 2 seconds after a config reload
                # We pass a specific reason payload so the Sweeper knows to bypass physical hardware movements
                self._timer_manager.schedule("post_reload_sweep", int(time.time()) + 2, "SYSTEM_SWEEP_REQUESTED",
                                             {"reason": "config_reload"})
            except Exception as e:
                ch, dom = self._push_alert(f"🔴 Config reload failed: {e}")
                state_changed |= ch
                changed_domains |= dom

        elif event_name == "SYSTEM_SWEEP_REQUESTED":
            """
            🌍 The Catch-Up Sweeper
            When this runs, it doesn't just evaluate manual sensor states. It explicitly looks
            at the 6-point Daily Time-Series to figure out exactly what Phase of the day we are in.
            It instantly force-dispatches the correct ambient light, absorbing any power outages
            or logic downtime gracefully!
            """
            # Ensure boundaries are up to date
            self._recalculate_environmental_schedule()

            sns = self._state.sensors
            now = int(time.time())

            # 1. Blinds Enforcement
            # ⚡ ENHANCED RECOVERY GUARD
            # Skip forcing physical roller shutter movements and environmental triggers if this
            # sweep was automatically scheduled by a reconnection, a config reload, or a manual UI trigger.
            # Adding `None` ensures that manual UI sweeps (which have no reason payload) ALSO skip the blinds!
            is_passive_sweep = payload.get("reason") in ["domoticz_reconnection", "network_recovery", "config_reload",
                                                         None]

            if is_passive_sweep:
                logger.info("[Sweeper] Skipping time-series hardware alignment to respect passive sync baseline.")
            else:
                # 1. Blinds Enforcement
                if sns.env_schedule_blinds_open_unix and sns.env_schedule_blinds_close_unix:
                    if sns.env_schedule_blinds_open_unix <= now < sns.env_schedule_blinds_close_unix:
                        self.dispatch(Event(type=EventType.BLINDS_OPEN_TRIGGER))
                    else:
                        self.dispatch(Event(type=EventType.BLINDS_CLOSE_TRIGGER))

                # 2. Morning Twilight Enforcement
                if sns.env_schedule_twilight_morning_on_unix and sns.env_schedule_twilight_morning_off_unix:
                    if sns.env_schedule_twilight_morning_on_unix <= now < sns.env_schedule_twilight_morning_off_unix:
                        self.dispatch(Event(type=EventType.TWILIGHT_MORNING_ON_TRIGGER))
                    else:
                        self.dispatch(Event(type=EventType.TWILIGHT_MORNING_OFF_TRIGGER))

                # 3. Evening Twilight Enforcement
                if sns.env_schedule_twilight_evening_on_unix and sns.env_schedule_twilight_evening_off_unix:
                    if sns.env_schedule_twilight_evening_on_unix <= now < sns.env_schedule_twilight_evening_off_unix:
                        self.dispatch(Event(type=EventType.TWILIGHT_EVENING_ON_TRIGGER))
                    else:
                        self.dispatch(Event(type=EventType.TWILIGHT_EVENING_OFF_TRIGGER))

            ch, dom = self._push_alert("🟢 System Sweeper complete. Environmental phases synchronized.")
            state_changed |= ch
            changed_domains |= dom

        # --------------------------------------------------------
        # GENERIC TIMER ROUTING & GLASS-BOX TRACKING
        # --------------------------------------------------------
        elif event_name == "TIMER_SCHEDULED":
            timer_id: Optional[str] = payload.get("timer_id")
            deadline: Optional[int] = payload.get("deadline")
            tgt_event_type: Optional[str] = payload.get("event_type")
            tgt_payload: dict[str, Any] = payload.get("event_payload", {})

            if timer_id and deadline and tgt_event_type:
                self._timer_manager.schedule(timer_id, deadline, tgt_event_type, tgt_payload)

                active = self._state.system.active_timers

                # Clear old instances of this timer_id safely before injecting new ones
                self._state.system.active_timers = [
                    t for t in active
                    if not (isinstance(t, str) and (t == timer_id or f'"timer_id": "{timer_id}"' in t))
                       and not (isinstance(t, dict) and t.get("timer_id") == timer_id)
                ]

                # ⚡ SUBSCRIBER FAN-OUT LOGIC ⚡
                # If the timer targets a generic broadcast trigger, scan the automation rules
                # and fan out a unique timeline object for every specific rule that listens to it.
                matched_rules = False
                if hasattr(self._config, "automations"):
                    for rule in self._config.automations:
                        rule_triggered = False
                        triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]

                        for t in triggers:
                            if getattr(t, "event", None):
                                rule_evt = t.event.value if hasattr(t.event, 'value') else str(t.event)
                                if rule_evt == tgt_event_type:
                                    rule_triggered = True
                                    break

                        if rule_triggered:
                            matched_rules = True
                            name_suffix = " (conditional)" if getattr(rule, "conditions", None) else ""
                            timeline_obj = {
                                "timer_id": timer_id,
                                "deadline": deadline,
                                "event_type": tgt_event_type,
                                "idx": None,
                                "name": f"{rule.name}{name_suffix}",
                                "type": "scene",
                                "target_state": "Execute"
                            }
                            # Bypass Pydantic string coercion by injecting a serialized JSON object natively
                            self._state.system.active_timers.append(json.dumps(timeline_obj))

                # ⚡ FALLBACK LOGIC
                # If no automation rules matched (e.g., standard lighting auto-off timers),
                # append the directly targeted hardware object.
                if not matched_rules:
                    target_idx = tgt_payload.get("idx")
                    timeline_obj = {
                        "timer_id": timer_id,
                        "deadline": deadline,
                        "event_type": tgt_event_type,
                        "idx": target_idx,
                        "name": tgt_payload.get("name", self._state.dashboard_map.get(target_idx, "System Macro")),
                        "type": tgt_payload.get("type", "scene" if target_idx is None else "switch"),
                        "target_state": tgt_payload.get("target_state", "Execute")
                    }
                    self._state.system.active_timers.append(json.dumps(timeline_obj))

                state_changed = True
                changed_domains.add("system")

        elif event_name == "TIMER_CANCELLED":
            timer_id: Optional[str] = payload.get("timer_id")
            if timer_id:
                self._timer_manager.cancel(timer_id)
                active = self._state.system.active_timers
                original_len = len(active)

                self._state.system.active_timers = [
                    t for t in active
                    if not (isinstance(t, str) and (t == timer_id or f'"timer_id": "{timer_id}"' in t))
                       and not (isinstance(t, dict) and t.get("timer_id") == timer_id)
                ]

                if len(self._state.system.active_timers) < original_len:
                    state_changed = True
                    changed_domains.add("system")

        elif event_name == "LIGHT_TIMER_EXPIRED":
            idx: Optional[int] = payload.get("idx")
            if idx is not None:
                timer_id = f"light_auto_off_{idx}"
                active = self._state.system.active_timers
                original_len = len(active)

                self._state.system.active_timers = [
                    t for t in active
                    if not (isinstance(t, str) and (t == timer_id or f'"timer_id": "{timer_id}"' in t))
                       and not (isinstance(t, dict) and t.get("timer_id") == timer_id)
                ]

                if len(self._state.system.active_timers) < original_len:
                    state_changed = True
                    changed_domains.add("system")

                automation_logger.info(f"Auto-off timer expired for light IDX {idx}, turning off light.")
                # Force the specific IDX OFF by simulating a regular hub command
                self.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"idx": idx, "state": "OFF", "force": True}  # Force to prevent State Desynchronization
                ))

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
            idx: int = payload.get("idx")
            val: float = payload.get("value", 0.0)
            sns: Any = self._state.sensors

            # ⚡ GENERIC CATCH-ALL: Universally store ALL sensors in the generic dictionary
            current = self._state.devices.get(idx)
            if not isinstance(current, dict):
                current = {}
            if current.get("temp") != val:
                current["temp"] = val
                self._state.devices[idx] = current
                state_changed = True
                changed_domains.add("devices")

            # --- CORE ENGINE TARGET ROUTING ---
            # We explicitly map virtual hardware IDXs to their semantic internal variables.
            # Note for programmers: IDX 20001 (Sauna Ceiling Probe) and IDX 20002 (Sauna Bench Probe)
            # are 2 independent physical SHT11 temperature probes that get mathematically
            # calculated into ONE combined metric (`sauna_calc_temp`) in _recalculate_sauna_metrics().
            if idx == 20001:
                if sns.sauna_high_temp != val:
                    sns.sauna_high_temp = val
                    state_changed = True
                    changed_domains.add("sensors")
                    if self._recalculate_sauna_metrics() or is_manual_lab_action:
                        changed_domains.add("sensors")
            elif idx == 20002:
                if sns.sauna_low_temp != val:
                    sns.sauna_low_temp = val
                    state_changed = True
                    changed_domains.add("sensors")
                    if self._recalculate_sauna_metrics() or is_manual_lab_action:
                        changed_domains.add("sensors")
            elif idx == 20003:  # Cinema Probe
                if sns.cinema_temp != val:
                    sns.cinema_temp = val
                    state_changed = True
                    changed_domains.add("sensors")
            elif idx == 20004:  # Bathroom1 Probe
                if sns.bathroom1_temp != val:
                    sns.bathroom1_temp = val
                    state_changed = True
                    changed_domains.add("sensors")
            elif idx == 30001:  # OWM Outside Temp
                if sns.outside_temp != val:
                    sns.outside_temp = val
                    state_changed = True
                    changed_domains.add("sensors")

                if current.get("temp") != val:
                    current["temp"] = val
                    self._state.devices[idx] = current
                    state_changed = True
                    changed_domains.add("devices")

        elif event_name == "HUMIDITY_UPDATED":
            idx: int = payload.get("idx")
            val: int = payload.get("value", 0)
            sns: Any = self._state.sensors

            # ⚡ GENERIC CATCH-ALL: Universally store ALL sensors in the generic dictionary
            current = self._state.devices.get(idx)
            if not isinstance(current, dict):
                current = {}
            if current.get("hum") != val:
                current["hum"] = val
                self._state.devices[idx] = current
                state_changed = True
                changed_domains.add("devices")

            # --- CORE ENGINE TARGET ROUTING ---
            # Note for programmers: IDX 20001 and IDX 20002 are mathematically
            # calculated into the single `sauna_calc_hum` metric.
            if idx == 20001:
                if sns.sauna_high_hum != val:
                    sns.sauna_high_hum = val
                    state_changed = True
                    changed_domains.add("sensors")
                    if self._recalculate_sauna_metrics() or is_manual_lab_action:
                        changed_domains.add("sensors")
            elif idx == 20002:
                if sns.sauna_low_hum != val:
                    sns.sauna_low_hum = val
                    state_changed = True
                    changed_domains.add("sensors")
                    if self._recalculate_sauna_metrics() or is_manual_lab_action:
                        changed_domains.add("sensors")
            elif idx == 20003:  # Cinema Probe
                if sns.cinema_hum != val:
                    sns.cinema_hum = val
                    state_changed = True
                    changed_domains.add("sensors")
            elif idx == 20004:  # Bathroom1 Probe
                if sns.bathroom1_hum != val:
                    sns.bathroom1_hum = val
                    state_changed = True
                    changed_domains.add("sensors")
            elif idx == 30001:  # OWM Outside Hum
                if sns.outside_hum != val:
                    sns.outside_hum = val
                    state_changed = True
                    changed_domains.add("sensors")

                if current.get("hum") != val:
                    current["hum"] = val
                    self._state.devices[idx] = current
                    state_changed = True
                    changed_domains.add("devices")

        elif event_name == "SENSOR_ERROR":
            idx = payload.get("idx")
            if idx not in self._state.hardware.sensor_errors:
                self._state.hardware.sensor_errors.append(idx)
                state_changed = True
                changed_domains.add("hardware")
            # 20001 & 20002 = Sauna SHT Probes
            if idx in [20001, 20002] and self._state.sauna.active:
                await self.logger.critical(f"Critical sensor failure on IDX {idx}. Emergency stopping heater elements.")
                self.dispatch(Event(type=EventType.SAUNA_OFF))

        # --------------------------------------------------------
        # CORE CONTROLLER MODULE ROUTERS
        # --------------------------------------------------------
        elif event_name == "SAUNA_ON":
            door_sauna_open = self._state.devices.get(10001) == "OPEN"  # 10001 = door_sauna
            if door_sauna_open:
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

        elif event_name == "SAUNA_TIMER_ADJUSTED":
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

        elif event_name == "SAUNA_HOLD_TOGGLED":
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

            # Note: We NO LONGER overwrite the modulation_pwm here!
            # It will automatically use the default or whatever the user dragged it to last.
            self._timer_manager.schedule("ir_main", self._state.ir.session_end_time, "IR_TIMER_EXPIRED")
            state_changed = True
            changed_domains.add("ir")

        elif event_name == "IR_OFF":
            self._state.ir.active = False
            # Note: We NO LONGER drop modulation_pwm to 0 here!
            # The slider will stay locked visually at its last value
            self._timer_manager.cancel("ir_main")
            state_changed = True
            changed_domains.add("ir")

        elif event_name == "IR_TIMER_EXPIRED":
            self.dispatch(Event(type=EventType.IR_OFF))

        elif event_name == "IR_MODULATION_UPDATED":
            self._state.ir.modulation_pwm = payload.get("pwm", 0)
            self._state.ir.frequency = payload.get("freq", 0)
            state_changed = True
            changed_domains.add("ir")

        elif event_name == "DOOR_CHANGED":
            idx = payload.get("idx")
            is_open = payload.get("is_open", False)
            new_state = "OPEN" if is_open else "CLOSED"

            # Doors are switches, so they go directly to devices using their integer IDX!
            if self._state.devices.get(idx) != new_state:
                self._state.devices[idx] = new_state
                state_changed = True
                changed_domains.add("devices")

                # Sauna safety interlock logic evaluation
                # IDX 10001 is the Sauna Door
                if idx == 10001 and is_open and self._state.sauna.active:
                    self._state.sauna.active = False
                    self._state.sauna.modulation_pwm = 0
                    self._state.sauna.phases_pwm = [0, 0, 0]
                    self._state.sauna.ventilation_state = "OFF"
                    changed_domains.add("sauna")
                    asyncio.create_task(
                        self.logger.warning("🚪 Sauna door opened while active! Emergency cutoff triggered."))

        elif event_name == "HUB_STATE_CHANGED":
            idx = payload.get("idx")
            state_val = payload.get("state")  # "ON" or "OFF"
            old_val = self._state.devices.get(idx)
            is_init = payload.get("is_initialization", False)

            # ⚡ RICH PAYLOAD MERGE FOR HUE/ADVANCED LIGHTING
            # This safely merges attributes like brightness and color into a dictionary without destroying them.
            is_rich_payload = "bri" in payload or "xy" in payload
            new_val = state_val

            if isinstance(old_val, dict):
                new_val = old_val.copy()
                if state_val is not None:
                    new_val["state"] = state_val
                if "bri" in payload:
                    new_val["bri"] = payload["bri"]
                if "xy" in payload:
                    new_val["xy"] = payload["xy"]
            elif is_rich_payload:
                new_val = {"state": state_val}
                if "bri" in payload:
                    new_val["bri"] = payload["bri"]
                if "xy" in payload:
                    new_val["xy"] = payload["xy"]

            # ⚡ Hybrid Learning: Cache semantic names from Domoticz if not already mapped in config.yaml
            device_name = payload.get("name")
            if device_name and idx not in self._state.dashboard_map and str(idx) not in self._state.dashboard_map:
                self._state.dashboard_map[idx] = device_name
                # Suppress the redundant log spam if this is the initial HTTP boot sync
                if not is_init:
                    logger.info(f"Name for {idx} added to the dashboard map: {device_name}.")

            # Grab the bypass flags!
            is_push_button = payload.get("is_push_button", False)
            is_force = payload.get("force", False)

            # ⚡ ALWAYS process the event if it's a push button, a forced command, or if the state actually changed.
            if old_val != new_val or is_push_button or is_force:
                self._state.devices[idx] = new_val
                state_changed = True
                changed_domains.add("devices")

                # 🛡️ THE GENERIC INITIALIZATION TAG 🛡️
                # If old_val is None, this is the very first time we hear about this device.
                if old_val is None:
                    payload["is_initialization"] = True
                else:
                    payload["transitioned"] = True

                # ⚡ Artificially inject 0.0W to instantly flush power graphs when switches turn off
                # Includes full metadata payload so the Device Explorer properly updates!
                if state_val == "OFF":
                    if idx == 8:  # pc
                        self.dispatch(Event(type=EventType.POWER_UPDATED, payload={
                            "idx": 9, "value": 0.0, "device_type": "power", "origin": "domoticz",
                            "name": self._state.dashboard_map.get(9, "pc_power")
                        }))
                    elif idx == 9618:  # pc_aux
                        self.dispatch(Event(type=EventType.POWER_UPDATED, payload={
                            "idx": 9622, "value": 0.0, "device_type": "power", "origin": "domoticz",
                            "name": self._state.dashboard_map.get(9622, "pc_aux_power")
                        }))

                # ⚡ Bathroom 1e ventilator timer lock
                # 7558 is the Domoticz extraction fan raw IDX
                if idx == 7558 and state_val == "ON" and old_val != "ON":
                    # 90001 is the internal virtual lock IDX
                    self._state.devices[90001] = True
                    deadline = int(time.time()) + (self._config.bathroom1.vent_min_runtime_mins * 60)
                    self._timer_manager.schedule("bath1_vent_lock", deadline, "BATH1_VENT_LOCK_EXPIRED")

                # ⚡ EPSON INTERCEPTOR
                if idx == 80001 and (old_val != state_val or is_force):
                    if self._state.system.epson_integration_enabled:
                        if getattr(self, "epson_bridge", None):
                            # We use asyncio.create_task so the TCP network call doesn't block WanOS's event queue!
                            asyncio.create_task(self.epson_bridge.power(state_val))
                        else:
                            automation_logger.error(
                                "Tried to trigger Epson projector, but bridge is offline or misconfigured.")
                    else:
                        # 🛡️ Bouncer logic: Provide clear UI feedback that the integration is disabled
                        automation_logger.warning("Epson command dropped: Integration is disabled in UI.")
                        ch, dom = self._push_alert("🔴 Epson command dropped: Integration is disabled.")
                        state_changed |= ch
                        changed_domains |= dom

        elif event_name == "BATH1_VENT_LOCK_EXPIRED":
            # The 5-minute minimum runtime has passed. Release the internal lock.
            self._state.devices[90001] = False
            state_changed = True
            changed_domains.add("devices")

            # Immediately force an artificial humidity update to evaluate if it should turn off NOW
            if self._state.sensors.bathroom1_hum is not None:
                self.dispatch(Event(
                    type=EventType.HUMIDITY_UPDATED,
                    payload={"idx": 20004, "value": self._state.sensors.bathroom1_hum}  # 20004 = bathroom1_hum
                ))

        elif event_name == "LIGHTING_STATE_CHANGED":
            idx = payload.get("idx")
            state_val = payload.get("state")  # "ON" or "OFF"
            if self._state.devices.get(idx) != state_val:
                self._state.devices[idx] = state_val
                state_changed = True
                changed_domains.add("devices")

        elif event_name == "VENT_WAIT_EXPIRED":
            self._state.sauna.ventilation_state = "RUNNING"
            self._state.devices[8577] = "ON"  # 8577 = sauna_extrvent
            self._state.sauna.ventilation_deadline = int(time.time()) + (self._config.sauna.vent_run_mins * 60)
            self._timer_manager.schedule("vent_run", self._state.sauna.ventilation_deadline, "VENT_RUN_EXPIRED")
            state_changed = True
            changed_domains.add("sauna")
            changed_domains.add("devices")

        elif event_name == "VENT_RUN_EXPIRED":
            self._state.sauna.ventilation_state = "OFF"
            self._state.devices[8577] = "OFF"  # 8577 = sauna_extrvent
            self._state.sauna.ventilation_deadline = None
            state_changed = True
            changed_domains.add("sauna")
            changed_domains.add("devices")

        elif event_name == "SAUNA_SETPOINT_CHANGED":
            new_target = payload.get("target")
            if new_target is not None:
                self._state.sauna.target_temp = min(float(new_target), self._state.sauna.max_temp)
                state_changed = True
                changed_domains.add("sauna")

        elif event_name == "SAUNA_MODULATION_UPDATED":
            self._state.sauna.modulation_pwm = payload.get("pwm", 0)
            self._state.sauna.phases_pwm = payload.get("phases", [0, 0, 0])
            state_changed = True
            changed_domains.add("sauna")

        if event_name in ["TEMP_UPDATED", "SAUNA_ON", "SAUNA_OFF", "SAUNA_SETPOINT_CHANGED", "DOOR_CHANGED"]:
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
        # Master Safety Gate: Run automations if the toggle is ON, or forcefully run them
        # if Live Hardware is active (to ensure the real house never ignores rules).
        if self._state.system.automations_enabled:
            for auto_event in AutomationEngine.evaluate(event, self._state):
                self.dispatch(auto_event)

        return state_changed, changed_domains

    async def _system_telemetry_loop(self) -> None:
        """Background execution loop polling hardware diagnostics and connection channels."""
        import socket

        def _get_ip() -> str:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "127.0.0.1"

        def _is_connected(client_mgr: Any) -> bool:
            if client_mgr is not None and hasattr(client_mgr, "is_connected"):
                return client_mgr.is_connected
            return False

        async def _ping_epson() -> bool:
            if not getattr(self._config, "epson", None) or not self._config.epson.ip_address:
                return False
            try:
                # ⚡ Non-blocking TCP ping to check if the projector's network stack is alive
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._config.epson.ip_address, 3629),
                    timeout=1.0
                )
                writer.close()
                await writer.wait_closed()
                return True
            except Exception:
                return False

        # ⚡ Dedicated Strike Counters for Auto-Kill thresholds
        # Network integrations get 3 strikes (6 seconds) to survive minor TCP blips.
        # USB hardware gets 1 strike (2 seconds) because a missing /dev/tty is immediately fatal.
        strikes = {"domoticz": 0, "hue": 0, "epson": 0, "rfxcom": 0}

        while True:
            try:
                await asyncio.sleep(2.0)

                wanos_conn = _is_connected(self.mqtt_client)
                dom_conn = _is_connected(self.domoticz_client)
                rfx_conn = _is_connected(self.rfxcom_bridge)
                hue_conn = _is_connected(getattr(self, "hue_bridge", None))
                epson_conn = await _ping_epson()

                # Update strike tracking based on physical socket availability
                strikes["domoticz"] = 0 if dom_conn else strikes["domoticz"] + 1
                strikes["hue"] = 0 if hue_conn else strikes["hue"] + 1
                strikes["epson"] = 0 if epson_conn else strikes["epson"] + 1
                strikes["rfxcom"] = 0 if rfx_conn else strikes["rfxcom"] + 1

                # ⚡ Evaluate Auto-Kill thresholds
                if strikes["domoticz"] >= 3 and self._state.system.domoticz_integration_enabled:
                    self.dispatch(Event(type=EventType.DOMOTICZ_TOGGLED, payload={"enabled": False,
                                                                                  "error_msg": "🔌 Domoticz connection lost after 3 retries. Integration disabled."}))

                if strikes["hue"] >= 3 and self._state.system.hue_integration_enabled:
                    self.dispatch(Event(type=EventType.HUE_TOGGLED, payload={"enabled": False,
                                                                             "error_msg": "🔌 Hue Bridge connection lost after 3 retries. Integration disabled."}))

                if strikes["epson"] >= 3 and self._state.system.epson_integration_enabled:
                    self.dispatch(Event(type=EventType.EPSON_TOGGLED, payload={"enabled": False,
                                                                               "error_msg": "🔌 Epson Projector connection lost after 3 retries. Integration disabled."}))

                if strikes["rfxcom"] >= 1 and self._state.system.rfxcom_integration_enabled:
                    self.dispatch(Event(type=EventType.RFXCOM_TOGGLED, payload={"enabled": False,
                                                                                "error_msg": "🔌 USB RFXCOM disconnected. Integration disabled."}))

                metrics_payload = {
                    "wanos_connected": wanos_conn,
                    "domoticz_connected": dom_conn,
                    "rfxcom_connected": rfx_conn,
                    "hue_connected": hue_conn,
                    "epson_connected": epson_conn,
                    "ip_address": _get_ip()
                }
                self.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED, payload=metrics_payload))
            except asyncio.CancelledError:
                break
            except Exception:
                pass