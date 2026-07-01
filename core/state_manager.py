# --- file: core/state_manager.py ---
import asyncio
import time
import json
from datetime import datetime
from typing import Optional, Any, Set
from loguru import logger

from .models import SystemState, Event, EventType
from .mqtt_transport import MqttClientManager
from .logger import WanosLogger
from .config import load_config
from core.event_handlers.registry import EVENT_ROUTERS

from logic.health_monitor import HealthMonitor
from logic.sauna_controller import SaunaController

try:
    import lgpio
    LGPIO_AVAILABLE = True
except ImportError:
    LGPIO_AVAILABLE = False


class StateManager:
    @staticmethod
    def _remove_timer_robustly(active_timers: list[Any], target_timer_id: str) -> list[Any]:
        """Safely parses and filters out a timer by its timer_id regardless of JSON string spacing."""
        retained_timers = []
        for t in active_timers:
            if isinstance(t, dict) and t.get("timer_id") == target_timer_id:
                continue
            if isinstance(t, str):
                try:
                    parsed = json.loads(t)
                    if isinstance(parsed, dict) and parsed.get("timer_id") == target_timer_id:
                        continue
                except json.JSONDecodeError:
                    if t == target_timer_id:
                        continue
            retained_timers.append(t)
        return retained_timers

    def __init__(self, mqtt_client: MqttClientManager, logger: WanosLogger) -> None:
        self._state: SystemState = SystemState()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._state_listeners: list[Any] = []  
        self.mqtt_client: MqttClientManager = mqtt_client
        self.domoticz_client: Optional[Any] = None  
        self.rfxcom_bridge: Optional[Any] = None  
        self.hue_bridge: Optional[Any] = None  
        self.epson_bridge: Optional[Any] = None
        self.zwave_bridge: Optional[Any] = None  
        self.logger: WanosLogger = logger

        # Optional reference to the MqttPublisher, injected after construction.
        self.mqtt_publisher: Optional[Any] = None

        self._start_time = time.time()

        # Generate immutable build timestamp string once at process boot
        self._build_timestamp: str = datetime.now().strftime("%Y%m%d%H%M")

        # Track rolling data windows for moving averages
        self._sensor_history: dict[int, list[float]] = {}

        # Load centralized configuration profiles
        self._config = load_config()

        # Extract health monitor to pure background task manager
        self._health_monitor = HealthMonitor(self)

        # Assemble initial structural application lifecycle tags inside live RAM state
        self._state.system.version_major = f"v{self._config.version}"
        self._state.system.version_full = f"v{self._config.version}-build_{self._build_timestamp}"

        # Transfer the parsed dictionary from the static config into the live SystemState 
        self._state.dashboard_map = self._config.dashboard
        self._state.system.hidden_explorer_idxs = self._config.deviceexplorer_exclude

        # STALE CACHE PURGE & COMPREHENSIVE ALLOCATION
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
            if idx < 10000:
                self._state.devices[idx] = None

        # ⚡ Programmatic initialization for virtual physical/environment sensors
        # Iterates through your config.yaml dashboard mappings to guarantee metadata creation!
        for idx, name in self._config.dashboard.items():
            if 10000 <= idx < 20000:  # Local GPIO Doors & Contacts
                self._state.device_metadata[idx] = {"name": name, "type": "sensor", "origin": "gpio_input"}
                self._state.devices[idx] = None
            elif 20000 <= idx < 30000:  # SHT11 Temperature & Humidity Probes
                self._state.device_metadata[idx] = {"name": name, "type": "temp_hum", "origin": "sht11"}
                self._state.devices[idx] = None
            elif 30000 <= idx < 40000:  # OpenWeatherMap Virtual Probes
                self._state.device_metadata[idx] = {"name": name, "type": "temp_hum", "origin": "owm"}
                self._state.devices[idx] = None

        if hasattr(self._config, "native_rfx"):
            for rfx_dev in self._config.native_rfx:
                self._state.system.native_rfx_devices.append({
                    "name": rfx_dev.name,
                    "virtual_idx": rfx_dev.virtual_idx
                })
                self._state.dashboard_map[rfx_dev.virtual_idx] = rfx_dev.name
                self._state.device_metadata[rfx_dev.virtual_idx] = {"name": rfx_dev.name, "type": "switch", "origin": "rfxcom"}
                self._state.devices[rfx_dev.virtual_idx] = "OFF"

        if hasattr(self._config, "hue") and getattr(self._config, "hue", None):
            for idx_int in self._config.hue.device_map.keys():
                semantic_name = self._state.dashboard_map.get(idx_int, f"Hue Light {idx_int}")
                self._state.dashboard_map[idx_int] = semantic_name
                self._state.device_metadata[idx_int] = {"name": semantic_name, "type": "light", "origin": "hue"}
                self._state.devices[idx_int] = None

            group_map = getattr(self._config, "hue").group_map if hasattr(getattr(self._config, "hue"), "group_map") else {}
            for idx_int in group_map.keys():
                semantic_name = self._state.dashboard_map.get(idx_int, f"Hue Group {idx_int}")
                self._state.dashboard_map[idx_int] = semantic_name
                self._state.device_metadata[idx_int] = {"name": semantic_name, "type": "light", "origin": "hue"}
                self._state.devices[idx_int] = None

        if getattr(self._config, "epson", None):
            self._state.dashboard_map[80001] = "Epson Projector"
            self._state.device_metadata[80001] = {"name": "Epson Projector", "type": "switch", "origin": "epson"}
            self._state.devices[80001] = "OFF"

        # ⚡ Programmatic initialization for virtual read-only status sensors
        self._state.dashboard_map[21001] = "Sauna status"
        self._state.device_metadata[21001] = {"name": "Sauna status", "type": "sensor", "origin": "system"}
        self._state.devices[21001] = "OFF"

        self._state.dashboard_map[21002] = "IR status"
        self._state.device_metadata[21002] = {"name": "IR status", "type": "sensor", "origin": "system"}
        self._state.devices[21002] = "OFF"

        if hasattr(self._config, "hue") and getattr(self._config.hue, "presets", None):
            self._state.system.hue_presets = {k: v.model_dump() for k, v in self._config.hue.presets.items()}

        self._extract_scenes_from_config()

    def _extract_scenes_from_config(self) -> None:
        self._state.system.available_scenes.clear()
        if hasattr(self._config, "automations"):
            for rule in self._config.automations:
                if getattr(rule, "scene", False) is not True:
                    continue
                triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]
                for t in triggers:
                    if t.event:
                        if not any(s["event"] == t.event for s in self._state.system.available_scenes):
                            self._state.system.available_scenes.append({
                                "name": rule.name,
                                "event": t.event
                            })

    def register_listener(self, callback: Any) -> None:
        self._state_listeners.append(callback)
        self._state.sauna.target_temp = float(self._config.sauna.default_sauna_setpoint)
        self._state.sauna.max_temp = float(self._config.sauna.max_temp)
        self._state.boot_seed = self._config.boot_seed

        self._state.ir.modulation_pwm = self._config.ir.default_ir_modulation
        freq_map = {0: 0, 25: 25, 33: 33, 50: 50, 67: 33, 75: 25, 100: 5}
        self._state.ir.frequency = freq_map.get(self._state.ir.modulation_pwm, 0)

        self._sauna_timer_triggered = False
        self._sauna_timer_duration_secs = 0

        self._gpio_chip = None
        if LGPIO_AVAILABLE:
            try:
                self._gpio_chip = lgpio.gpiochip_open(0)
                lgpio.gpio_claim_output(self._gpio_chip, self._config.pins.safety_gpio)
            except Exception as e:
                logger.error(f"Hardware Init Error: Safety Pin unavailable - {e}")

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
        self._health_monitor.start()
        await self.logger.success("State Manager worker started.")

    async def stop(self) -> None:
        self._set_hardware_safety_gate(False)
        await self._health_monitor.stop()
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
        except ValueError:
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

    async def _process_events(self) -> None:
        pending_broadcast = False
        changed_domains: Set[str] = set()
        batch_events: list[Event] = [] 

        while True:
            event: Event = await self._queue.get()
            try:
                changed, domains = await self._handle_event(event)
                if changed:
                    pending_broadcast = True
                    changed_domains.update(domains)
                    batch_events.append(event) 
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

                for listener in self._state_listeners:
                    try:
                        await listener(snapshot_obj, batch_events)
                    except Exception as e:
                        await self.logger.error(f"Error in state listener: {e}")

                pending_broadcast = False
                changed_domains.clear()
                batch_events.clear()

    async def _handle_event(self, event: Event) -> tuple[bool, Set[str]]:
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        payload = event.payload or {}
        state_changed: bool = False
        changed_domains: Set[str] = set()

        # --- ⚡ UNIVERSAL NULL GUARD (BOOT STORM PROTECTOR) ⚡ ---
        # Intercepts every single event before it hits the handlers.
        # If the device is currently NULL or "Sync..." in memory, this is its first heartbeat.
        meta_idx = payload.get("idx")
        if meta_idx is not None:
            current_cached_val: Any = self._state.devices.get(meta_idx)
            if current_cached_val is None or current_cached_val == "Sync...":
                payload["is_initialization"] = True
            else:
                payload["transitioned"] = True

        # DYNAMIC METADATA REGISTRY HOOK
        meta_type = payload.get("device_type")
        meta_name = payload.get("name")
        meta_origin = payload.get("origin")

        if meta_idx is not None and meta_type is not None:
            existing = self._state.device_metadata.get(meta_idx)
            if not existing or existing.get("type") != meta_type or existing.get("name") != meta_name or existing.get("origin") != meta_origin:
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
            if is_simulation_action or is_boot_baseline_seed:
                origin_tag = " [SIMULATION]" if is_simulation_action else " [BOOT_SEED]"
                logger.debug(f"Event Received [{event_name}]{origin_tag}: {payload}")
            elif event_name == "HUB_STATE_CHANGED" and payload.get("is_initialization") and payload.get(
                    "origin") == "domoticz":
                logger.info(
                    f"--> Domoticz sensor idx {payload.get('idx')} ({payload.get('name', 'Unknown')}): initial state received: {payload.get('state')}")
            else:
                # TELEMETRY ROUTING GATEWAY: Move Power, lux, hum en temperature from INFO to DEBUG
                is_telemetry = (
                        event_name in ["POWER_UPDATED", "TEMP_UPDATED", "HUMIDITY_UPDATED"] or
                        (event_name == "HUB_STATE_CHANGED" and payload.get("device_type") in ["power", "sensor"])
                )

                if is_telemetry:
                    logger.debug(f"Event Received [{event_name}]: {payload}")
                else:
                    logger.info(f"Event Received [{event_name}]: {payload}")

        # ⚡ ROUTE TO STRATEGY PATTERN HANDLER
        handler = EVENT_ROUTERS.get(event_name)
        if handler:
            ch, dom = await handler(event, self)
            state_changed |= ch
            changed_domains.update(dom)

        # --------------------------------------------------------
        # CROSS-CUTTING CONCERNS (Timers & PID Logic)
        # --------------------------------------------------------
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
                        self._timer_manager.schedule("sauna_main", self._state.sauna.session_end_time, "SAUNA_TIMER_EXPIRED")
                        logger.info(f"Heat threshold met ({current_temp}°C >= {threshold_temp}°C). Activating timer countdown!")
                        state_changed = True
                        changed_domains.add("sauna")
                    else:
                        if self._state.sauna.session_end_time != self._sauna_timer_duration_secs:
                            self._state.sauna.session_end_time = self._sauna_timer_duration_secs
                            state_changed = True
                            changed_domains.add("sauna")

                # AUTOMATIC HOLD STEPPING INTERRUPT
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

        # AUTOMATION ENGINE HOOK
        if self._state.system.automations_enabled:
            for auto_event in AutomationEngine.evaluate(event, self._state):
                self.dispatch(auto_event)

        return state_changed, changed_domains