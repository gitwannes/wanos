# --- file: core/state_manager.py ---
import asyncio
import time
import json
import threading
from datetime import datetime
from typing import Optional, Any, Set, Dict
from loguru import logger

from .models import SystemState, Event, EventType, device_name
from .mqtt_transport import MqttClientManager
from .logger import WanosLogger, iwhw_logger
from .config import load_config
from .entity_registry import EntityRegistry
from core.event_handlers.registry import EVENT_ROUTERS
from core.nvm_manager import NVRAMManager
from core.event_catalog import to_bus_token, legacy_key_for_bus_token
from core.command_commit import CommandCommit
from core.auto_off_store import auto_off_timer_payload_from_config

from logic.health_monitor import HealthMonitor
from logic.sauna_controller import SaunaController
from logic.power_analytics import PowerAnalytics
from logic.history_manager import DeviceHistoryManager
from logic.sensor_history_manager import SensorHistoryManager
from logic.history_ids import SAUNA_CALC_IDX, SCENE_IDX_BASE, scene_history_idx


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
        self._drain_sink: Optional[list] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._state_listeners: list[Any] = []  
        self.mqtt_client: MqttClientManager = mqtt_client
        self.rfxcom_bridge: Optional[Any] = None  
        self.hue_bridge: Optional[Any] = None  
        self.epson_bridge: Optional[Any] = None
        self.sonos_bridge: Optional[Any] = None
        self.zwave_bridge: Optional[Any] = None  
        self.logger: WanosLogger = logger

        # Initialize Non-Volatile Memory Disk I/O Controller
        self.nvm = NVRAMManager()

        # Stable entity_id ↔ idx registry (system-owned YAML)
        self.entity_registry = EntityRegistry()
        self.entity_registry.load()

        # Optional reference to the MqttPublisher, injected after construction.
        self.mqtt_publisher: Optional[Any] = None

        # B10H: event-driven SSE broadcast (set from main.py).
        self._sse_hub: Optional[Any] = None

        # C18: Q4/Q5 request-level success/fail (siblings hold old_val until apply).
        self.command_commit = CommandCommit(self)

        # B10H: REST /api/state cache — refreshed on queue drain (avoid per-request deep copy).
        self._api_state_cache: Optional[Dict[str, Any]] = None
        self._api_state_cache_lock = threading.Lock()

        self._start_time = time.time()

        # Generate immutable build timestamp string once at process boot
        self._build_timestamp: str = datetime.now().strftime("%Y%m%d%H%M")

        # Track rolling data windows for moving averages
        self._sensor_history: dict[int, list[float]] = {}

        # Transient counter to prevent high-frequency hardware pulses from flooding the terminal
        self._pulse_log_counters: dict[int, int] = {}

        # FIRST-SYNC TRACKING SET (Boot Storm Protector)
        # An immutable ledger tracking which IDXs have reported their physical state at least once since the Python process started.
        self._initialized_idxs: set[int] = set()
        self._shutting_down: bool = False

        # Load centralized configuration profiles
        self._config = load_config()

        # Extract health monitor to pure background task manager
        self._health_monitor = HealthMonitor(self)

        # Instantiate isolated mathematical telemetry and logging engine
        self._power_analytics = PowerAnalytics(self)
        self.history_manager = DeviceHistoryManager(self)
        self.sensor_history = SensorHistoryManager(self)

        # ATOMIC RECONCILIATION: Delegate metadata assembly to the atomic rebuilder
        self.rebuild_core_metadata()

        # Timer Manager placeholder.
        # Instantiation has been moved to start() to safely bind to the asyncio loop!
        self._timer_manager = None

    def rebuild_core_metadata(self) -> None:
        """
        Ruthlessly rebuilds the semantic Source of Truth (names, types) directly from YAML.
        Called on initial boot and hot-reloads to guarantee 100% parity and prevent ghost nodes.
        """
        # Assemble initial structural application lifecycle tags inside live RAM state
        self._state.system.version_major = f"v{self._config.version}"
        self._state.system.version_full = f"v{self._config.version}-build_{self._build_timestamp}"

        # ATOMIC RECONCILIATION: Wipe old metadata for core integrations (Keep Z-Wave as it lazy-loads)
        # Skip null placeholders (Z-Wave orphan tombstones) and anything tagged origin=zwave.
        keys_to_purge = [
            k for k, v in self._state.device_metadata.items()
            if isinstance(v, dict) and v.get("origin") != "zwave"
        ]
        for k in keys_to_purge:
            self._state.device_metadata.pop(k, None)

        self._state.system.hidden_explorer_idxs = []
        yaml_idxs: set[int] = set()

        # 1. Parse GPIO Inputs
        if hasattr(self._config, "gpio_inputs") and self._config.gpio_inputs:
            for key, node in self._config.gpio_inputs.items():
                if node.idx is not None:
                    # Preserve semantic GPIO kinds for entity_id classification (door/fluid/energy).
                    node_type = node.type if node.type in ("door", "fluid", "energy") else "sensor"
                    self._state.device_metadata[node.idx] = {"name": node.name, "type": node_type,
                                                             "origin": "gpio_input"}
                    yaml_idxs.add(node.idx)

                    # DYNAMIC PESSIMISTIC INITIALIZATION
                    if node.idx not in self._state.devices:
                        if node.type == "door":
                            self._state.devices[node.idx] = "CLOSED"
                        elif node.type in ["fluid", "energy"]:
                            self._state.devices[node.idx] = 0.0
                        else:
                            self._state.devices[node.idx] = None

        # 2. Parse SHT11 Sensors
        if hasattr(self._config, "sht11_sensors"):
            for key, node in self._config.sht11_sensors.items():
                self._state.device_metadata[node.idx] = {"name": node.name, "type": "temp_hum", "origin": "sht11"}
                yaml_idxs.add(node.idx)
                if node.idx not in self._state.devices:
                    self._state.devices[node.idx] = None

        # 20101 : sauna temp — virtual composite (0.7×20001 + 0.3×20002); hum from 20001
        self._state.device_metadata[SAUNA_CALC_IDX] = {
            "name": "sauna temp",
            "type": "temp_hum",
            "origin": "system",
        }
        yaml_idxs.add(SAUNA_CALC_IDX)
        if SAUNA_CALC_IDX not in self._state.devices:
            self._state.devices[SAUNA_CALC_IDX] = None

        # 3. Parse OpenWeatherMap
        if hasattr(self._config, "weather") and getattr(self._config.weather, "idx", None):
            w_idx = self._config.weather.idx
            w_name = self._config.weather.name
            self._state.device_metadata[w_idx] = {"name": w_name, "type": "temp_hum", "origin": "owm"}
            yaml_idxs.add(w_idx)
            if w_idx not in self._state.devices:
                self._state.devices[w_idx] = None

        if hasattr(self._config, "native_rfx"):
            self._state.system.native_rfx_devices.clear()
            for rfx_dev in self._config.native_rfx:
                self._state.system.native_rfx_devices.append({
                    "name": rfx_dev.name,
                    "virtual_idx": rfx_dev.virtual_idx
                })
                self._state.device_metadata[rfx_dev.virtual_idx] = {"name": rfx_dev.name, "type": "switch",
                                                                    "origin": "rfxcom"}
                yaml_idxs.add(rfx_dev.virtual_idx)
                if rfx_dev.virtual_idx not in self._state.devices:
                    self._state.devices[rfx_dev.virtual_idx] = "OFF"

        hue_conf = getattr(self._config, "hue", None)
        if hue_conf:
            device_map = getattr(hue_conf, "device_map", {}) or {}
            for idx_key, raw_val in device_map.items():
                try:
                    idx_int = int(idx_key)
                    yaml_idxs.add(idx_int)
                    if idx_int not in self._state.devices:
                        self._state.devices[idx_int] = None
                    val_str = raw_val.get_secret_value() if hasattr(raw_val, "get_secret_value") else str(raw_val)
                    if "|" in val_str:
                        friendly_name = val_str.split("|", 1)[1].strip()
                        self._state.device_metadata[idx_int] = {
                            "name": friendly_name, "type": "light", "origin": "hue", "hue_kind": "light",
                        }
                    else:
                        self._state.device_metadata[idx_int] = {
                            "name": f"Hue Light {idx_int}", "type": "light", "origin": "hue", "hue_kind": "light",
                        }
                except Exception:
                    pass

            group_map = getattr(hue_conf, "group_map", {}) or {}
            for idx_key, raw_val in group_map.items():
                try:
                    idx_int = int(idx_key)
                    yaml_idxs.add(idx_int)
                    if idx_int not in self._state.devices:
                        self._state.devices[idx_int] = None
                    val_str = raw_val.get_secret_value() if hasattr(raw_val, "get_secret_value") else str(raw_val)
                    if "|" in val_str:
                        friendly_name = val_str.split("|", 1)[1].strip()
                        self._state.device_metadata[idx_int] = {
                            "name": friendly_name, "type": "light", "origin": "hue", "hue_kind": "group",
                        }
                    else:
                        self._state.device_metadata[idx_int] = {
                            "name": f"Hue Group {idx_int}", "type": "light", "origin": "hue", "hue_kind": "group",
                        }
                except Exception:
                    pass

        if getattr(self._config, "epson", None):
            epson_name = "cinema projector"
            self._state.device_metadata[80001] = {"name": epson_name, "type": "switch", "origin": "epson"}
            yaml_idxs.add(80001)
            if 80001 not in self._state.devices:
                self._state.devices[80001] = "OFF"

        if getattr(self._config, "sonos", None):
            max_vol = getattr(self._config.sonos, "max_volume", 70)
            for idx, node in self._config.sonos.device_map.items():
                self._state.device_metadata[idx] = {
                    "name": node.name, "type": "speaker", "origin": "sonos",
                    "max_volume": max_vol,
                }
                yaml_idxs.add(idx)
                if idx not in self._state.devices:
                    self._state.devices[idx] = None

        if getattr(self._config, "onkyo", None):
            max_vol = getattr(self._config.onkyo, "max_volume", 60)
            for idx, node in self._config.onkyo.device_map.items():
                self._state.device_metadata[idx] = {"name": node.name, "type": "speaker", "origin": "onkyo",
                                                    "max_volume": max_vol}
                yaml_idxs.add(idx)
                if idx not in self._state.devices:
                    self._state.devices[idx] = None

        sauna_name = "sauna status"
        self._state.device_metadata[21001] = {"name": sauna_name, "type": "sensor", "origin": "system"}
        yaml_idxs.add(21001)
        if 21001 not in self._state.devices:
            self._state.devices[21001] = "OFF"

        ir_name = "IR status"
        self._state.device_metadata[21002] = {"name": ir_name, "type": "sensor", "origin": "system"}
        yaml_idxs.add(21002)
        if 21002 not in self._state.devices:
            self._state.devices[21002] = "OFF"

        sys_metrics_map = {
            22001: "Host CPU Temperature",
            22002: "Host CPU Usage",
            22003: "Host Memory Free",
            22004: "Host Disk Free (Root)",
            22005: "Host Log2Ram Free",
            22006: "Host Load Average (1m)",
            22007: "Host Load Average (5m)",
            22008: "Host Load Average (15m)",
            22009: "WanOS DB size",
        }
        for s_idx, s_name in sys_metrics_map.items():
            self._state.device_metadata[s_idx] = {"name": s_name, "type": "sensor", "origin": "system"}
            yaml_idxs.add(s_idx)
            if s_idx not in self._state.devices:
                self._state.devices[s_idx] = None

        hue_cfg = getattr(self._config, "hue", None)
        if hue_cfg is not None:
            preset_map = getattr(hue_cfg, "presets", None) or {}
            self._state.system.hue_presets = {
                k: v.model_dump() for k, v in preset_map.items()
            }
        else:
            self._state.system.hue_presets = {}

        if getattr(self._config, "sonos", None) and getattr(self._config.sonos, "stations", None):
            self._state.system.sonos_stations = dict(self._config.sonos.stations)
        else:
            self._state.system.sonos_stations = {}

        self._state.system.auto_off_timer = auto_off_timer_payload_from_config(self._config)

        nvram_data = self.nvm.load()
        for nv_idx, nv_val in nvram_data.items():
            self._state.devices[nv_idx] = nv_val
            yaml_idxs.add(nv_idx)
            meta = self._state.device_metadata.get(nv_idx)
            if not isinstance(meta, dict):
                self._state.device_metadata[nv_idx] = {
                    "name": f"Counter {nv_idx}", "type": "sensor", "origin": "nvram",
                }

        self._extract_scenes_from_config()

        # B10B: purge legacy scene.* / 900000+ registry rows (history idxs ≠ devices).
        self.entity_registry.purge_synthetic_scene_history_rows()

        # Synthetic history IDXs (900000+) stay in RAM for chart name resolve, but
        # must NOT birth entity_ids (Explorer uses dashboard_events only).
        for idx, meta in list(self._state.device_metadata.items()):
            if not isinstance(meta, dict):
                continue
            try:
                i = int(idx)
            except (TypeError, ValueError):
                continue
            if i >= SCENE_IDX_BASE or (
                    meta.get("origin") == "automation" and meta.get("type") == "scene"):
                yaml_idxs.add(i)
                # Strip any stamped entity_id; do not ensure/birth.
                meta.pop("entity_id", None)

        # Soft-hide placeholders (entity_id in YAML → resolve to idx)
        exclusions: list[int] = []
        for ref in (getattr(self._config, "deviceexplorer_hide", None) or []):
            eid = str(ref).strip()
            if not eid:
                continue
            idx = self.entity_registry.resolve(eid)
            if idx is None:
                logger.warning(f"deviceexplorer_hide: unresolved entity_id '{eid}'")
                continue
            exclusions.append(idx)
            yaml_idxs.add(idx)
            if idx not in self._state.device_metadata or self._state.device_metadata.get(idx) is None:
                self._state.device_metadata[idx] = {
                    "name": f"Hidden {eid}", "type": "unknown", "origin": "system"
                }
                self.entity_registry.ensure(idx, self._state.device_metadata[idx])
        self._state.system.hidden_explorer_idxs = exclusions

        # UNIVERSAL ORPHAN EVICTION (non-Z-Wave)
        # Nullify RAM for devices removed from YAML so SSE Object.assign clears the UI.
        # Z-Wave orphans are handled exclusively by integrations/zwave.py.
        candidate_idxs = (
            set(self._state.devices.keys())
            | set(self._state.device_metadata.keys())
        )
        for idx in list(candidate_idxs):
            if not isinstance(idx, int):
                continue
            # Synthetic scene history keys — never purge as YAML orphans
            if idx >= SCENE_IDX_BASE:
                continue
            meta = self._state.device_metadata.get(idx)
            if isinstance(meta, dict) and meta.get("origin") == "zwave":
                continue
            if idx in yaml_idxs:
                continue

            self._state.devices[idx] = None
            self._state.device_metadata[idx] = None
            self.entity_registry.mark_removed(idx)
            self.dispatch(Event(
                type=EventType.HUB_STATE_CHANGED,
                payload={
                    "idx": idx,
                    "state": None,
                    "device_type": "unknown",
                    "origin": "system",
                    "is_initialization": True,
                }
            ))

        # Apply hidden flags from deviceexplorer_hide
        self.sync_hidden_metadata()

        # Birth / freeze entity_ids for every live metadata row; persist entity_registry.auto.yaml
        self.entity_registry.reconcile(self._state.device_metadata)
        self._stamp_resolved_product_types()

    def _stamp_resolved_product_types(self) -> None:
        """Attach resolved_product_type to binary actuators / Hue (D1 Explorer / auto-off tier)."""
        from core.product_type_policy import resolve_product_type

        overrides = getattr(self._config, "device_product_types", None) or {}
        for _idx, meta in self._state.device_metadata.items():
            if not isinstance(meta, dict):
                continue
            eid = meta.get("entity_id")
            if not eid:
                meta.pop("resolved_product_type", None)
                continue
            origin = str(meta.get("origin") or "")
            dtype = str(meta.get("type") or "").lower()
            # Product light|switch only applies to Hue mesh and binary actuators.
            if origin == "hue" or dtype in ("switch", "light"):
                meta["resolved_product_type"] = resolve_product_type(
                    str(eid),
                    origin=origin,
                    overrides=overrides,
                )
            else:
                meta.pop("resolved_product_type", None)

    def ensure_entity_id(self, idx: int) -> Optional[str]:
        """Stamp a frozen entity_id onto device_metadata[idx] (does not flush disk)."""
        if int(idx) >= SCENE_IDX_BASE:
            meta = self._state.device_metadata.get(idx)
            if isinstance(meta, dict):
                meta.pop("entity_id", None)
            return None
        meta = self._state.device_metadata.get(idx)
        if not isinstance(meta, dict):
            return None
        eid = self.entity_registry.ensure(int(idx), meta)
        return eid or None

    def flush_entity_registry(self) -> None:
        """Persist dirty entity_registry.auto.yaml once (call after batch ensures)."""
        self.entity_registry.save()

    def resolve_entity_id(self, entity_id: str) -> Optional[int]:
        """Always-resolve helper: entity_id → idx (None if missing/removed)."""
        return self.entity_registry.resolve(entity_id)

    def sync_hidden_metadata(self) -> None:
        """
        Single rule for Explorer / History visibility:
        meta.hidden = idx in system.hidden_explorer_idxs
        (populated from automations.auto.yaml deviceexplorer_hide entity_ids → idxs).
        """
        hidden = set()
        for x in (self._state.system.hidden_explorer_idxs or []):
            try:
                hidden.add(int(x))
            except (TypeError, ValueError):
                continue
        for idx, meta in list(self._state.device_metadata.items()):
            if not isinstance(meta, dict):
                continue
            try:
                i = int(idx)
            except (TypeError, ValueError):
                continue
            meta["hidden"] = i in hidden

    def _extract_scenes_from_config(self) -> None:
        """
        B10B: rebuild Explorer dashboard_events from events: catalog (+ listener rules).

        System-seed YAML merge runs in load_config() (not here) so RAM rebuilds on
        CONFIG_RELOAD do not rewrite automations.auto.yaml on every extract.
        """
        from core.events_store import build_dashboard_events, read_events

        self._state.system.dashboard_events = build_dashboard_events()

        # Seed history metadata for catalog events (UUID → 900000+ idx) so charts
        # resolve the current label. Not Explorer devices — no entity_id birth.
        for row in read_events():
            eid = str(row.get("id") or "")
            if not eid:
                continue
            s_idx = scene_history_idx(eid)
            self._state.device_metadata[s_idx] = {
                "name": str(row.get("name") or eid),
                "type": "scene",
                "origin": "automation",
                "event": eid,
            }

    def register_listener(self, callback: Any) -> None:
        self._state_listeners.append(callback)

        # 🛡️ ONE-TIME INITIALIZATION GUARD
        # Ensures internal runtime states and control loops are configured exactly once on the first registration hook.
        # This prevents follow-up integration bridge setups from wiping running metrics or resetting active loops.
        if not hasattr(self, "sauna_logic"):
            self._state.sauna.target_temp = float(self._config.sauna.default_sauna_setpoint)
            self._state.sauna.min_temp = float(self._config.sauna.min_temp)
            self._state.sauna.max_temp = float(self._config.sauna.max_temp)
            self._state.boot_seed = self._config.boot_seed

            self._state.ir.modulation_pwm = self._config.ir.default_ir_modulation
            freq_map = {0: 0, 25: 25, 33: 33, 50: 50, 67: 33, 75: 25, 100: 5}
            self._state.ir.frequency = freq_map.get(self._state.ir.modulation_pwm, 0)

            self._sauna_timer_triggered = False
            self._sauna_timer_duration_secs = 0

            self.sauna_logic = SaunaController(
                initial_target_temp=self._state.sauna.target_temp,
                kp=self._config.sauna.kp,
                ki=self._config.sauna.ki,
                kd=self._config.sauna.kd
            )

    async def start(self) -> None:
        self._worker_task = asyncio.create_task(self._process_events())
        self._health_monitor.start()
        self._power_analytics.start()
        self.history_manager.start()
        self.sensor_history.start()
        from logic.automation_rules import AutomationEngine
        AutomationEngine._history_manager = self.history_manager

        # SINGLETON TIMER INSTANTIATION (Event Loop Safe)
        # Must be initialized inside an async context so its internal background tasks bind to the running loop!
        if self._timer_manager is None:
            from logic.timers import TimerManager
            self._timer_manager = TimerManager(dispatch_callback=self._dispatch_from_timer)
            # KICK-OFF NVRAM FLUSH LOOP
            # Schedules the very first disk save. Once this fires (5 minutes after boot), the handler in
            # telemetry_handlers.py will continuously reschedule itself to create the infinite loop.
            self._timer_manager.schedule("nvram_flush", int(time.time()) + 300, EventType.NVRAM_FLUSH_TRIGGER.value)

        # Start integration bridges if they were persistently enabled
        if getattr(self._state.system, "sonos_integration_enabled", False):
            from integrations.sonos import SonosBridge
            self.sonos_bridge = SonosBridge(self)
            await self.sonos_bridge.start()

        if getattr(self._state.system, "onkyo_integration_enabled", False):
            from integrations.onkyo import OnkyoBridge
            self.onkyo_bridge = OnkyoBridge(self)
            await self.onkyo_bridge.start()

        await self.logger.success("State Manager worker started.")
        await asyncio.to_thread(self.warm_api_state_cache)

    async def stop(self) -> None:
        self._set_hardware_safety_gate(False)
        await self._health_monitor.stop()
        await self._power_analytics.stop()
        await self.history_manager.stop()
        await self.sensor_history.stop()
        if self.sonos_bridge:
            await self.sonos_bridge.stop()
        if getattr(self, "onkyo_bridge", None):
            await self.onkyo_bridge.stop()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

            # FINAL NVRAM SHUTDOWN FLUSH
            # Guaranteed save cycle when the WanOS process shuts down gracefully
            nvm_payload = {k: v for k, v in self._state.devices.items() if
                           isinstance(k, int) and 11000 <= k < 12000}
            self.nvm.flush(nvm_payload)

        await self.logger.warning("State Manager worker stopped.")

    def dispatch(self, event: Event) -> None:
        """
        Enqueue an event. Catalog keys (SAUNA_ON, …) are normalized to their fixed
        UUID bus token via to_bus_token so the queue always carries UUID-on-bus for
        pickable/system catalog events; internals stay readable EventType strings.
        """
        bus = to_bus_token(event.type)
        raw = event.type.value if hasattr(event.type, "value") else str(event.type)
        if bus != raw:
            event = Event(type=bus, payload=event.payload or {})
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            self._queue.put_nowait(event)

    async def _dispatch_from_timer(self, event_type_str: str, payload: dict) -> None:
        # G15: skip stale env schedule timers (cross-day / missed recalc).
        timer_id = (payload or {}).get("timer_id")
        deadline = (payload or {}).get("deadline")
        if timer_id and deadline is not None:
            from logic.environment_scheduler import EnvironmentScheduler

            stale_reason = EnvironmentScheduler.env_timer_fire_stale(
                str(timer_id), int(deadline), self._state
            )
            if stale_reason:
                logger.warning(
                    f"[Timer] Skipping stale env timer {timer_id!r} "
                    f"(deadline={deadline}, event={event_type_str}): {stale_reason}"
                )
                return

        # Timers may store legacy keys or UUIDs; always normalize to bus token.
        bus = to_bus_token(event_type_str)
        try:
            e_type: Any = EventType(bus)
        except ValueError:
            e_type = bus
        self.dispatch(Event(type=e_type, payload=payload))

    def get_state_snapshot(self) -> SystemState:
        return self._state.model_copy(deep=True)

    def warm_api_state_cache(self) -> None:
        """Populate REST cache from live state (sync — call via to_thread at boot)."""
        self._update_api_state_cache_from_snapshot(self.get_state_snapshot())

    def _update_api_state_cache_from_snapshot(self, snapshot: SystemState) -> None:
        payload: Dict[str, Any] = snapshot.model_dump()
        with self._api_state_cache_lock:
            self._api_state_cache = payload

    def _snapshot_and_cache_for_broadcast(self) -> SystemState:
        """Deep snapshot for MQTT/SSE listeners + refresh REST cache (sync — worker thread)."""
        snapshot: SystemState = self.get_state_snapshot()
        self.command_commit.hold_pending_on_snapshot(snapshot)
        self._update_api_state_cache_from_snapshot(snapshot)
        return snapshot

    def get_api_state_payload(self) -> Dict[str, Any]:
        """Cached model_dump for GET /api/state."""
        with self._api_state_cache_lock:
            cached = self._api_state_cache
        if cached is not None:
            return dict(cached)
        return self.get_state_snapshot().model_dump()

    def _set_hardware_safety_gate(self, state: bool) -> None:
        self._state.hardware.safety_pin_active = state

    async def _process_events(self) -> None:
        pending_broadcast = False
        changed_domains: Set[str] = set()
        batch_events: list[Event] = []

        while True:
            event: Event = await self._queue.get()
            try:
                # Follow-ups append into this list during _handle_event (same drain).
                self._drain_sink = batch_events
                changed, domains = await self._handle_event(event)
                if changed:
                    pending_broadcast = True
                    changed_domains.update(domains)
                    if event not in batch_events:
                        batch_events.append(event)
            except Exception as e:
                type_label = event.type.value if hasattr(event.type, "value") else str(event.type)
                await self.logger.error(f"Error handling event {type_label}: {e}")
            finally:
                self._drain_sink = None
                self._queue.task_done()

            if self._queue.empty():
                # Always flush dirty registry when the queue drains (batched, never per-event).
                self.flush_entity_registry()

                if pending_broadcast:
                    # Snapshot holds C18 in-flight idxs at old_val (Q4/Q5). Listeners
                    # only send hardware — I/O is create_task, not awaited here.
                    snapshot_obj: SystemState = await asyncio.to_thread(
                        self._snapshot_and_cache_for_broadcast
                    )

                    if self._sse_hub is not None:
                        try:
                            await self._sse_hub.broadcast(snapshot_obj, changed_domains)
                        except Exception as e:
                            await self.logger.error(f"Error in SSE hub broadcast: {e}")

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

                    self.command_commit.fail_unclaimed()
                    self.command_commit.arm_watch()

                    pending_broadcast = False
                    changed_domains.clear()
                    batch_events.clear()

    async def _handle_event(self, event: Event) -> tuple[bool, Set[str]]:
        # B10B dual-mode bus: catalog events travel as UUIDs; internals stay enum strings.
        # legacy_name maps system UUIDs back to EventType keys for existing == "SAUNA_ON" checks.
        bus_token = to_bus_token(event.type)
        legacy_name = legacy_key_for_bus_token(bus_token)
        raw_type = event.type.value if hasattr(event.type, "value") else str(event.type)
        if raw_type != bus_token:
            event = Event(type=bus_token, payload=event.payload or {})

        # All string comparisons below use legacy_name (readable key or pass-through token).
        event_name = legacy_name
        payload = event.payload or {}
        state_changed: bool = False
        changed_domains: Set[str] = set()

        # Ignore door chatter queued during GPIO teardown
        if self._shutting_down and event_name == "DOOR_CHANGED":
            return False, set()

        # --- UNIVERSAL NULL GUARD (BOOT STORM PROTECTOR) ---
        # Intercepts every single event before it hits the handlers.
        # If the device is currently NULL or "Sync..." in memory, this is its first heartbeat.
        meta_idx = payload.get("idx")
        if meta_idx is not None:
            try:
                meta_idx = int(meta_idx)
                payload["idx"] = meta_idx
            except (TypeError, ValueError):
                pass
        if meta_idx is not None:
            if meta_idx not in self._initialized_idxs:
                payload["is_initialization"] = True
                self._initialized_idxs.add(meta_idx)
            current_cached_val: Any = self._state.devices.get(meta_idx)
            if current_cached_val is None:
                current_cached_val = self._state.devices.get(str(meta_idx))
            if current_cached_val is None or current_cached_val == "Sync...":
                payload["is_initialization"] = True
            elif not payload.get("is_initialization"):
                # Only flag as transitioned if it's explicitly not an initialization phase
                payload["transitioned"] = True

        # DYNAMIC METADATA REGISTRY HOOK
        meta_type = payload.get("device_type")
        meta_name = payload.get("name")
        meta_origin = payload.get("origin")

        if meta_idx is not None and meta_type is not None:
            existing = self._state.device_metadata.get(meta_idx)
            if not isinstance(existing, dict):
                existing = {}
            # Keep origin/name when the event omits them (e.g. Sonos poll without device_type wipe).
            resolved_origin = meta_origin if meta_origin is not None else existing.get("origin")
            resolved_name = meta_name if meta_name is not None else existing.get("name")
            if (not existing or existing.get("type") != meta_type or existing.get(
                    "name") != resolved_name or existing.get("origin") != resolved_origin):
                new_meta = {
                    "name": resolved_name or f"idx_{meta_idx}",
                    "type": meta_type,
                    "origin": resolved_origin,
                    "hidden": int(meta_idx) in set(int(x) for x in (self._state.system.hidden_explorer_idxs or [])),
                }
                if existing.get("hue_kind"):
                    new_meta["hue_kind"] = existing["hue_kind"]
                if existing.get("entity_id"):
                    new_meta["entity_id"] = existing["entity_id"]
                if existing.get("max_volume") is not None and "max_volume" not in new_meta:
                    new_meta["max_volume"] = existing["max_volume"]
                self._state.device_metadata[meta_idx] = new_meta
                self.entity_registry.ensure(int(meta_idx), new_meta)
                # Do not save per-event — flush once after the queue drain (see worker).
                state_changed = True
                changed_domains.add("device_metadata")

        # --- LIVE TERMINAL LOGGING INJECTION GATEWAY ---
        is_manual_lab_action = payload.get("lab_override", False)
        is_boot_baseline_seed = payload.get("boot_seed", False)
        is_simulation_action = payload.get("from_simulator", False)
        is_user_command = event_name in [
            "SAUNA_ON", "SAUNA_OFF", "SAUNA_SETPOINT_CHANGED", "SAUNA_MODULATION_UPDATED",
            "SAUNA_HOLD", "SAUNA_HOLD_TOGGLED", "SAUNA_TIMER_ADJUSTED", "IR_ON", "IR_OFF",
            "IR_MODULATION_UPDATED"
        ]

        # DATA PLANE WATCHDOG HOOK
        # Updates the rolling timestamp but does NOT flag state_changed to avoid
        # spamming the SSE stream with unnecessary broadcasts every heartbeat.
        if event_name == "ZWAVE_HEARTBEAT":
            self._state.system.last_zwave_heartbeat_unix = int(time.time())

        if event_name == "SYSTEM_READY":
            logger.info("Internal Engine State validated and locked.")
            logger.info(f"Internal Event Processed: {event_name}")
        elif (
                is_user_command or is_manual_lab_action) and not is_simulation_action and not is_boot_baseline_seed:
            logger.info(f"Lab Action Received: {event_name} | Payload: {payload}")
            await self.logger.info(f"User Action Processed: {event_name}")
        elif event_name != "SYSTEM_METRICS_UPDATED":
            if is_simulation_action or is_boot_baseline_seed:
                origin_tag = " [SIMULATION]" if is_simulation_action else " [BOOT_SEED]"
                logger.debug(f"Event Received [{event_name}]{origin_tag}: {payload}")
            elif event_name == "HUB_STATE_CHANGED" and payload.get("origin") == "system":
                # COMPLETE SILENCE: Do not log high-frequency host stats (CPU, RAM, Load) at all
                pass
            else:
                # High-chatter bus events → DEBUG (IWHW / dedicated lines keep the audit trail)
                is_debug_event = event_name in [
                    "POWER_UPDATED",
                    "TEMP_UPDATED",
                    "HUMIDITY_UPDATED",
                    "ZWAVE_HEARTBEAT",
                    "NVRAM_FLUSH_TRIGGER",
                    "HUB_STATE_CHANGED",
                    "ZWAVE_DISCOVERY",
                    "TIMER_SCHEDULED",
                    "TIMER_CANCELLED",
                ]

                # HARDWARE PULSE GUARD: Only log 1 in 10 pulses to prevent terminal I/O saturation
                if event_name == "WATER_PULSE":
                    target_idx = payload.get("idx")
                    self._pulse_log_counters[target_idx] = self._pulse_log_counters.get(target_idx, 0) + 1
                    if self._pulse_log_counters[target_idx] % 10 == 0:
                        logger.debug(f"Event Received [{event_name}] (Every 10th pulse): {payload}")
                elif is_debug_event:
                    logger.debug(f"Event Received [{event_name}]: {payload}")
                else:
                    logger.info(f"Event Received [{event_name}]: {payload}")

            # ZERO-TRUST BACKEND FIREWALL (Granular HITL Isolation)
            # Prevents lab simulators from injecting ghost data into active physical control loops.
        if is_manual_lab_action or is_simulation_action:
            target_idx = payload.get("idx")

            # Conflict 1: Fake weather vs Active OpenWeatherMap polling
            if target_idx == 30001 and self._state.system.owm_integration_enabled:
                return False, set()

            # Conflict 2: Fake doors & water vs Active GPIO Input hardware
            if event_name in ["DOOR_CHANGED", "WATER_PULSE"] and self._state.hardware.gpio_input_enabled:
                return False, set()

            # Conflict 3: Fake temps vs Active SHT11 Probes AND Active 9kW Heaters
            if event_name in ["TEMP_UPDATED", "HUMIDITY_UPDATED"]:
                if target_idx in [20001, 20002, 20003, 20004] and self._state.hardware.sht11_enabled:
                    return False, set()
                # CRITICAL: We strictly drop fake sauna temps if the actual GPIO outputs are armed
                # to prevent the real PID loop from snapping physical relays based on slider movements!
                if target_idx in [20001, 20002] and self._state.hardware.gpio_output_enabled:
                    return False, set()

        # EMERGENCY START GATE INTERCEPTOR (Prevention)
        # Validates physical requirements BEFORE routing the command to the logic handlers
        if event_name in ["SAUNA_ON", "IR_ON"]:
            reasons = []
            is_sim = self._state.hardware.simulations_enabled

            # Rule 1: 5V Master Safety Relay (Bypassed during physics simulation)
            if not is_sim and self._state.devices.get(71036) != "ON" and False:
                # Disabled: shutting down the 5V will not impact WanOS - this enables a 'dry run' mode.
                reasons.append("5V Safety Relay OFF")
            # Rule 2: Output Bus Armed Status (Bypassed during physics simulation)
            if not is_sim and not self._state.hardware.gpio_output_enabled:
                reasons.append("Outputs disarmed")
            # Rule 3: Telemetry Health (Always required, even if it's simulated telemetry)
            if self._state.sensors.sauna_calc_temp is None:
                reasons.append("Telemetry offline")
            # Rule 4: Physical Door (Sauna Only)
            if event_name == "SAUNA_ON" and self._state.devices.get(10001) == "OPEN":
                reasons.append("Door open")

            if reasons:
                sys_name = "Sauna" if event_name == "SAUNA_ON" else "IR"
                await self.logger.warning(
                    f"🔴 {sys_name} explicitly blocked by Start Gate: {', '.join(reasons)}")
                self.dispatch(Event(type=EventType.ALERT_INJECTED,
                                    payload={"msg_text": f"⚠️ {sys_name} start blocked: {', '.join(reasons)}"}))
                return state_changed, changed_domains

        # DASHBOARD EVENT INTERCEPTOR (IWHW Ledger + history) — match by event UUID id
        for dash_ev in self._state.system.dashboard_events:
            if dash_ev.get("id") == bus_token:
                name: str = dash_ev.get("name", "Unknown")
                origin_tag: str = str(payload.get("origin", "MANUAL")).upper()[:10]

                # Format is explicitly handled in Python to guarantee vertical column alignment
                # 10 chars type | 10 chars origin | 10 chars setting | 5 chars IDX | name
                iwhw_logger.info(f"{'SCENE':<10} | {origin_tag:<10} | {'EXECUTED':<10} | {'-----':<5} | {name}")
                break

        # IWHW LEDGER: Capture baseline state before mathematical mutation
        old_state_raw = None
        if meta_idx is not None:
            old_state_raw = self._state.devices.get(meta_idx)
            # If the state is a rich dict (e.g., Hue/Sonos), clone it to prevent memory reference mutation
            if isinstance(old_state_raw, dict):
                old_state_raw = old_state_raw.copy()

        # ROUTE TO STRATEGY PATTERN HANDLER (UUID alias or legacy key)
        handler = EVENT_ROUTERS.get(bus_token) or EVENT_ROUTERS.get(legacy_name)
        if handler:
            ch, dom = await handler(event, self)
            state_changed |= ch
            changed_domains.update(dom)

        # IWHW LEDGER: Evaluate binary state mutations behind the duplicate filter
        if meta_idx is not None and state_changed:
            meta = self._state.device_metadata.get(meta_idx, {})
            dev_type = meta.get("type", "")

            # Only log physical actuators and switches, ignore passive sensors and metrics
            # Note: 'blinds' and 'shutter' are explicitly excluded here; they are handled by the async proportional debounce engine in hub_handlers.py
            if dev_type in ["switch", "light", "speaker"]:
                new_state_raw = self._state.devices.get(meta_idx)

                # Extract strict binary core state, ignoring colors/brightness/volume
                old_bin = old_state_raw.get("state") if isinstance(old_state_raw, dict) else old_state_raw
                new_bin = new_state_raw.get("state") if isinstance(new_state_raw, dict) else new_state_raw

                if dev_type == "blinds":
                    def format_blind(val):
                        if val == 100: return "CLOSED"
                        if val == 0: return "OPEN"
                        return f"{val}%"

                    old_bin = format_blind(old_bin) if isinstance(old_bin, (int, float)) else old_bin
                    new_bin = format_blind(new_bin) if isinstance(new_bin, (int, float)) else new_bin

                # ⚡ SILENCE BOOT STORMS: Ignore events explicitly flagged as initialization,
                # or transitions involving None / 'Sync...' as either the origin or destination.
                is_init = payload.get("is_initialization", False)
                suppress_log = payload.get("suppress_device_log", False)
                is_valid_transition = (
                    old_bin != new_bin
                    and new_bin is not None
                    and new_bin not in ["Sync...", "DEAD"]
                    and old_bin is not None
                    and old_bin not in ["Sync...", "DEAD"]
                    and not is_init
                    and not suppress_log
                )
                # If the core binary state transitioned safely, write to the dedicated log
                if is_valid_transition:
                    origin: str = meta.get("origin", "")
                    prefix: str = origin.upper() if origin in ["hue", "sonos", "onkyo"] else dev_type.upper()

                    # Normalize semantic aliases
                    if prefix == "BLINDS": prefix = "SHUTTER"
                    if prefix == "LIGHT": prefix = "SWITCH"
                    prefix = prefix[:10]

                    name: str = meta.get("name", f"idx_{meta_idx}")

                    # Resolve Origin Payload
                    raw_origin = payload.get("origin")
                    if not raw_origin:
                        raw_origin = "SYSTEM" if is_init else "MANUAL"
                    origin_tag: str = str(raw_origin).upper()[:10]

                    new_bin_str: str = str(new_bin)[:10]
                    idx_str: str = str(meta_idx)[:5]

                    # Format is explicitly handled in Python to guarantee vertical column alignment
                    # 10 chars type | 10 chars origin | 10 chars setting | 5 chars IDX | name
                    iwhw_logger.info(f"{prefix:<10} | {origin_tag:<10} | {new_bin_str:<10} | {idx_str:<5} | {name}")

        # --------------------------------------------------------
        # CROSS-CUTTING CONCERNS (Universal Hooks, Timers & PID Logic)
        # --------------------------------------------------------

        p_idx = payload.get("idx")

        # EPHEMERAL MOTION LEDGER (Admin Diagnostics) + rising-edge history
        # Tracks how many times a motion sensor (75xxx) trips per boot session.
        if event_name == "HUB_STATE_CHANGED" and p_idx is not None:
            if str(p_idx).startswith("75") and payload.get("state") == "ON":
                current_tally = self._state.metrics.motion_triggers.get(p_idx, 0)
                self._state.metrics.motion_triggers[p_idx] = current_tally + 1
                state_changed = True
                changed_domains.add("metrics")
                if not payload.get("is_initialization", False) and hasattr(self, "history_manager"):
                    self.history_manager.log_event(int(p_idx), "ON", level=100.0)

        # MASTER Z-WAVE SAFETY CASCADE (Phase B)
        # If the 5V Master Safety Relay drops, we must instantly cut the software outputs.
        if event_name == "HUB_STATE_CHANGED" and p_idx == 71036 and payload.get("state") != "ON" and False:
            # Disabled: shutting down the 5V will not impact WanOS - this enables a 'dry run' mode.
            if self._state.hardware.gpio_output_enabled:
                await self.logger.critical(
                    "🚨 Master 5V Safety Relay (71036) dropped! Cascading emergency output disarm.")
                self.dispatch(Event(type=EventType.GPIO_OUTPUT_TOGGLED, payload={"enabled": False}))

        # UNIVERSAL 0.0W INTERCEPTOR
        # Config-driven: when a mapped switch turns OFF, flush its linked power meter to 0.0W.
        if event_name == "HUB_STATE_CHANGED" and payload.get("state") == "OFF":
            switch_idx = payload.get("idx")
            hardware_links = getattr(self._config, "hardware_links", None)
            power_map = hardware_links.power_meters if hardware_links else {}
            switch_meta = self._state.device_metadata.get(switch_idx) if switch_idx is not None else None
            switch_eid = switch_meta.get("entity_id") if isinstance(switch_meta, dict) else None
            if switch_eid and switch_eid in power_map:
                power_idx = self.resolve_entity_id(power_map[switch_eid])
                if power_idx is not None:
                    self.dispatch(Event(type=EventType.POWER_UPDATED, payload={
                        "idx": power_idx, "value": 0.0, "device_type": "power", "origin": "system",
                        "name": device_name(self._state, power_idx, f"Power {power_idx}"),
                    }))

        # ISOLATED HIGH-FREQUENCY HARDWARE EVENT ROUTING
        # Intercepts physical pulse meter ticks directly from GPIO and routes them straight to the math engine
        if event_name == "KWH_PULSE" and p_idx == 11001:
            await self._power_analytics.process_pulse_tick()

        # UNIVERSAL SPARKLINE HISTORY AGGREGATOR
        is_power_event: bool = False

        if event_name == "POWER_UPDATED":
            is_power_event = True
        elif event_name == "HUB_STATE_CHANGED" and p_idx is not None:
            # Cross-reference our metadata registry to catch Z-Wave power payloads lacking explicit types
            meta_type = payload.get("device_type") or self._state.device_metadata.get(p_idx, {}).get("type")
            if meta_type in ["power", "energy"]:
                is_power_event = True

        if is_power_event:
            p_val = payload.get("value") if payload.get("value") is not None else payload.get("state")
            if p_idx is not None and p_val is not None:
                try:
                    numeric_val = float(str(p_val).replace(" W", "").replace("W", "").strip())
                    if p_idx not in self._state.sensors.sensor_history:
                        self._state.sensors.sensor_history[p_idx] = []
                    hist = self._state.sensors.sensor_history[p_idx]
                    hist.append(numeric_val)
                    if len(hist) > 20:
                        hist.pop(0)
                    state_changed = True
                    changed_domains.add("sensors")
                except (ValueError, TypeError):
                    pass

        # SAUNA COMPOSITE RECOVERY & STRICT FAILURE REQUIREMENT
        # Manually calculates the 70/30 High/Low atmosphere split here based purely on IDXs.
        if event_name in ["TEMP_UPDATED", "HUMIDITY_UPDATED"] or (
                event_name == "HUB_STATE_CHANGED" and p_idx in [20001, 20002]):

            # OUT-OF-BAND SAFETY HEARTBEAT TRACKER
            # Refreshes the active communication timestamp anytime local SHT11 sauna probes (20001/20002) publish data,
            # completely independent of whether the underlying temperature digits shifted or remained flat.
            if p_idx in [20001, 20002]:
                self._state.sauna.last_heartbeat_unix = int(time.time())

            d_high = self._state.devices.get(20001)
            d_low = self._state.devices.get(20002)

            # STRICT REQUIREMENT: BOTH probes must exist and report valid floats
            if isinstance(d_high, dict) and d_high.get("temp") is not None and isinstance(d_low,
                                                                                          dict) and d_low.get(
                "temp") is not None:
                try:
                    t_high = float(d_high["temp"])
                    t_low = float(d_low["temp"])
                    calc_t = round((t_high * 0.7) + (t_low * 0.3), 1)
                    self._state.sensors.sauna_calc_temp = calc_t

                    calc_h = None
                    if d_high.get("hum") is not None:
                        calc_h = int(float(d_high["hum"]))
                        self._state.sensors.sauna_calc_hum = calc_h

                    # Mirror onto virtual IDX 20101 for Device Explorer + climate history
                    # 20101 : sauna temp — virtual composite (0.7×20001 + 0.3×20002); hum from 20001
                    prev_20101 = self._state.devices.get(SAUNA_CALC_IDX)
                    new_20101 = {"temp": calc_t}
                    if calc_h is not None:
                        new_20101["hum"] = calc_h
                    elif isinstance(prev_20101, dict) and prev_20101.get("hum") is not None:
                        new_20101["hum"] = prev_20101["hum"]
                    self._state.devices[SAUNA_CALC_IDX] = new_20101
                    if hasattr(self, "sensor_history"):
                        self.sensor_history.note_climate_temp(SAUNA_CALC_IDX, calc_t)
                        if calc_h is not None:
                            self.sensor_history.note_climate_hum(SAUNA_CALC_IDX, float(calc_h))

                    state_changed = True
                    changed_domains.add("sensors")
                    changed_domains.add("devices")
                except (ValueError, TypeError):
                    pass
            else:
                # FAILSAFE: If EITHER probe drops, composite is instantly voided
                if self._state.sensors.sauna_calc_temp is not None:
                    self._state.sensors.sauna_calc_temp = None
                    self._state.sensors.sauna_calc_hum = None
                    self._state.devices[SAUNA_CALC_IDX] = None
                    state_changed = True
                    changed_domains.add("sensors")
                    changed_domains.add("devices")

        if event_name in ["TEMP_UPDATED", "SAUNA_ON", "SAUNA_OFF", "SAUNA_SETPOINT_CHANGED", "DOOR_CHANGED"]:
            current_temp = self._state.sensors.sauna_calc_temp

            # EMERGENCY THERMAL KILL SWITCH
            # Checks every relevant tick. If the engine is currently firing the heaters but we lose telemetry, drop the axe.
            if self._state.sauna.active and current_temp is None:
                await self.logger.critical(
                    "EMERGENCY SHUTDOWN: Temperature telemetry lost during active heating session!")
                self.dispatch(Event(type=EventType.ALERT_INJECTED,
                                    payload={"msg_text": "🚨 EMERGENCY SHUTDOWN: Sauna telemetry lost!",
                                             "level": "critical"}))
                self.dispatch(Event(type=EventType.SAUNA_OFF, payload={}))
                # Bypass PID logic for this tick
            elif current_temp is not None and self._state.sauna.active:

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

        # AUTOMATION ENGINE HOOK — apply YAML follow-ups in this drain (do not
        # dispatch onto the queue: empty()+snapshot would SSE old sibling RAM).
        if self._state.system.automations_enabled:
            sink = getattr(self, "_drain_sink", None)
            if state_changed and sink is not None and event not in sink:
                sink.append(event)
            for auto_event in AutomationEngine.evaluate(event, self._state):
                ch, dom = await self._handle_event(auto_event)
                state_changed = state_changed or ch
                changed_domains |= dom

        # ---------------------------------------------------------------------
        # CRITICAL INTERLOCK & SCADA VISUAL ANNUNCIATOR CONCERNS
        # ---------------------------------------------------------------------
        safety_conf = getattr(self._config, "sauna_safety", None)
        grace_period: int = getattr(safety_conf, "door_grace_period_secs", 30) if safety_conf else 30
        indicator_lights: list[int] = getattr(safety_conf, "indicator_lights",
                                              [51002, 51004, 51005]) if safety_conf else [51002, 51004, 51005]

        # 1. Door Interlock State Machine
        if event_name in ["DOOR_CHANGED", "HUB_STATE_CHANGED"] and p_idx == 10001:
            door_state = self._state.devices.get(10001)
            if door_state == "OPEN":
                if self._state.sauna.active and not self._state.sauna.is_paused:
                    if not self._timer_manager.is_scheduled("sauna_door_grace"):
                        deadline = int(time.time()) + grace_period
                        self._timer_manager.schedule("sauna_door_grace", deadline, "SAUNA_DOOR_GRACE_EXPIRED")
                        await self.logger.warning(
                            f"⏳ Sauna door opened! Starting silent {grace_period}s safety countdown.")
            elif door_state == "CLOSED":
                if self._timer_manager.is_scheduled("sauna_door_grace"):
                    self._timer_manager.cancel("sauna_door_grace")
                    await self.logger.success("🟢 Sauna door closed within grace window. Heaters unaffected.")
                if self._state.sauna.is_paused:
                    self._state.sauna.is_paused = False
                    self._state.sauna.last_light_temp = None  # Evict throttle cache to enforce instant visual re-evaluation
                    await self.logger.success("🟢 Sauna door closed. Resuming active heating session automatically.")
                    state_changed = True
                    changed_domains.add("sauna")

        # 2. Door Grace Period Expiry Trip
        if event_name == "SAUNA_DOOR_GRACE_EXPIRED":
            if self._state.sauna.active and self._state.devices.get(10001) == "OPEN":
                self._state.sauna.is_paused = True
                await self.logger.critical(
                    "🚨 Sauna door grace period expired! Forcefully cutting heaters and entering PAUSE state.")

                # Force vibrant SCADA Green to notify occupants of an unsealed thermal environment
                for l_idx in indicator_lights:
                    self.dispatch(Event(type=EventType.HUB_STATE_CHANGED, payload={
                        "idx": l_idx, "state": "ON", "xy": [0.1700, 0.7000], "force": True, "origin": "system"
                    }))
                state_changed = True
                changed_domains.add("sauna")

        # 3. Clean Session Interlock Teardown & Analytic SQL Flushes
        if event_name == "SAUNA_OFF":
            if self._timer_manager.is_scheduled("sauna_door_grace"):
                self._timer_manager.cancel("sauna_door_grace")
            self._state.sauna.is_paused = False
            self._state.sauna.last_light_temp = None
            await self._power_analytics.terminate_session("sauna")

        if event_name == "IR_OFF":
            await self._power_analytics.terminate_session("ir")

        # EN 60335-2-53 ABSOLUTE LIMIT TRACKER
        # Instantiates an un-bypassable 6-hour absolute running boundary the exact moment an active
        # heating session successfully transitions through the Start Gate verification interlocks.
        if event_name == "SAUNA_ON" and self._state.sauna.active:
            self._state.sauna.absolute_cutoff_unix = int(time.time()) + 6 * 3600

        # 4. Proportional Thermal Lighting Gradient (Blue ➔ Red)
        if self._state.sauna.active and not self._state.sauna.is_paused and self._state.sensors.sauna_calc_temp is not None:
            last_t = self._state.sauna.last_light_temp
            curr_t = self._state.sensors.sauna_calc_temp

            # Enforce 1°C quantization steps to shield Zigbee mesh from telemetry stream congestion
            if last_t is None or abs(curr_t - last_t) >= 1.0:
                self._state.sauna.last_light_temp = curr_t
                target_t = self._state.sauna.target_temp or 80.0
                min_t = 20.0

                # Math: Calculate linear scalar interpolation parameter clamped between 0.0 and 1.0
                clamped_t = max(min_t, min(target_t, curr_t))
                factor = (clamped_t - min_t) / max(1.0, (target_t - min_t))

                # Linear cross-fade RGB weights
                r_factor = factor
                g_factor = 0.0
                b_factor = 1.0 - factor

                # CIE 1931 color space transformation matrix mapping
                X = r_factor * 0.664511 + g_factor * 0.154324 + b_factor * 0.162028
                Y = r_factor * 0.283881 + g_factor * 0.668433 + b_factor * 0.047685
                Z = r_factor * 0.000088 + g_factor * 0.072310 + b_factor * 0.986039
                xyz_sum = X + Y + Z
                xy = [round(X / xyz_sum, 4), round(Y / xyz_sum, 4)] if xyz_sum > 0 else [0.3127, 0.3290]

                for l_idx in indicator_lights:
                    self.dispatch(Event(type=EventType.HUB_STATE_CHANGED, payload={
                        "idx": l_idx, "state": "ON", "xy": xy, "force": True, "origin": "system"
                    }))

        return state_changed, changed_domains