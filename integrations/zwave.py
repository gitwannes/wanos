# --- file: integrations/zwave.py ---
import json
import asyncio
from typing import Any, List
from core.models import Event, EventType, SystemState
from core.state_manager import StateManager
from core.logger import WanosComponent


class ZWaveJSUIBridge(WanosComponent):
    def __init__(self, state_manager: StateManager, mqtt_client: Any) -> None:
        super().__init__(state_manager)
        self.mqtt_client = mqtt_client
        self.name_to_idx: dict[str, int] = {}
        self.idx_to_name: dict[int, str] = {}
        self._last_known_states: dict[int, str] = {}
        self._integration_enabled: bool = False

        # Re-scoped tracking booleans for lazy-boot architecture
        self.is_mqtt_engine_alive: bool = False
        self._is_mapped: bool = False
        self._was_hardware_connected: bool = False
        self._last_config_id: int = 0

        # Debounce Tracker for MQTT Heartbeats
        self._last_heartbeat_processed: float = 0.0

    @property
    def mqtt_prefix(self) -> str:
        """Dynamically pulls the MQTT prefix from config (defaults to 'zwave')"""
        zwave_conf = getattr(self.state_manager._config, "zwave", None)
        return getattr(zwave_conf, "mqtt_prefix", "zwave") if zwave_conf else "zwave"

    async def start(self) -> None:
        # SILENT STANDBY: Only listen for the Z-Wave JS UI authoritative driver status
        await self.mqtt_client.subscribe(f"{self.mqtt_prefix}/driver/status", self._parse_hardware_status)

        # ⚡ OUT-OF-BAND DATA PLANE WATCHDOG
        # Subscribes to the heartbeat immediately so it bypasses the integration ON/OFF deadlock
        await self.mqtt_client.subscribe(f"{self.mqtt_prefix}/_EVENTS/+/controller/statistics_updated",
                                         self._parse_heartbeat)

        # Listen to internal state changes to detect when the USB stick is plugged in
        self.state_manager.register_listener(self._on_state_changed)

        await self.logger.info(
            f"[Z-Wave] Bridge in Silent Standby. Prefix '{self.mqtt_prefix}'. Waiting for hardware detection.")

    async def _parse_heartbeat(self, topic: str, payload: str) -> None:
        """Dedicated out-of-band interceptor for the MQTT Data Plane heartbeat."""
        import time
        now = time.time()

        # Throttle Guard: Ignore duplicate heartbeats arriving within 2 seconds of each other
        if now - self._last_heartbeat_processed > 2.0:
            self._last_heartbeat_processed = now
            self.state_manager.dispatch(Event(type=EventType.ZWAVE_HEARTBEAT, payload={}))

    async def _parse_hardware_status(self, topic: str, payload: str) -> None:
        """
        Parses the driver payload from Z-Wave JS UI to update self.is_mqtt_engine_alive.
        The driver payload is a raw string/boolean: "true" or "false".
        """
        try:
            is_alive = payload.strip().lower() == "true"

            if is_alive and not self.is_mqtt_engine_alive:
                self.is_mqtt_engine_alive = True
                await self.logger.success("[Z-Wave] JS Engine is online.")
            elif not is_alive and self.is_mqtt_engine_alive:
                self.is_mqtt_engine_alive = False
                await self.logger.error("🔴 [Z-Wave] Z-Wave JS Engine reported OFFLINE.")
        except Exception as e:
            await self.logger.error(f"[Z-Wave] Failed to parse hardware driver status: {e}")

    async def stop(self) -> None:
        await self.logger.warning("[Z-Wave] Z-Wave Bridge stopped.")

    async def _parse_inbound(self, topic: str, payload: str) -> None:
        """Parses physical sensor updates coming from the Z-Wave JS UI MQTT Broker"""
        if not self._integration_enabled:
            return

        try:
            data: dict[str, Any] = json.loads(payload)

            # ⚡ DATA TYPE GUARD
            # Z-Wave JS UI sometimes broadcasts raw scalar values (like true/false) on root topics.
            # If it's not a JSON dictionary object, we drop it to prevent attribute errors.
            if not isinstance(data, dict):
                return

            prefix = self.mqtt_prefix

            # 1. Strip the prefix to match internal routing logic
            if topic.startswith(f"{prefix}/"):
                mapped_path = topic[len(prefix) + 1:]
            else:
                return

            # 2. Dead Node Interceptor (Topics ending in /status)
            parts = mapped_path.split('/')
            if len(parts) == 2 and parts[1] == "status":
                node_name = parts[0]
                status_val = data.get("status", "").lower()

                if status_val == "dead":
                    for cfg_path, idx in self.name_to_idx.items():
                        if cfg_path.startswith(f"{node_name}/"):
                            if self._last_known_states.get(idx) == "DEAD":
                                continue
                            self._last_known_states[idx] = "DEAD"

                            # Fetch the custom name we pre-seeded during boot
                            custom_name = self.state_manager._state.dashboard_map.get(idx,
                                                                                      f"Z-Wave Node {node_name}")

                            # Push explicit DEAD intent to the frontend
                            self.state_manager.dispatch(Event(
                                type=EventType.HUB_STATE_CHANGED,
                                payload={
                                    "idx": idx,
                                    "state": "DEAD",
                                    "name": custom_name,
                                    "device_type": "switch",
                                    "origin": "zwave",
                                    "is_initialization": False
                                }
                            ))
                return

            # 3. Intent vs State: Ensure the payload contains a valid state object
            raw_val = data.get("value")
            if raw_val is None:
                return

            # Normalize path tracking strings to securely strip leaf node identifiers
            if mapped_path.endswith("/currentValue"):
                base_path = mapped_path[:-13]
            elif mapped_path.endswith("/value"):
                base_path = mapped_path[:-6]
            else:
                base_path = mapped_path

            # Isolate network routing arrays
            parts = base_path.split('/')
            if len(parts) < 2:
                return
            node_name = parts[0]
            command_class = parts[1]

            # Suppress high-volume kWh history counters and accumulator resets from CC 50
            if command_class == "50" and ("65537" in base_path or "66049" in base_path or "reset" in base_path):
                return

            target_idx = self.name_to_idx.get(base_path)

            if not target_idx:
                # ⚡ INBOX INTERCEPTOR ⚡
                # Filter out Node 1 (Controller) and metadata/object configuration noise completely
                if node_name == "1" or "duration" in mapped_path or "targetValue" in mapped_path:
                    return

                # Forward unmapped actionable classes (Switches, Shutters, Motion, Multilevel Sensors, Meters)
                if command_class in ["25", "37", "38", "48", "49", "50"]:
                    # Clean up the display value if it arrives encapsulated inside a dictionary object
                    display_val = raw_val.get("value") if isinstance(raw_val, dict) else raw_val

                    self.state_manager.dispatch(Event(
                        type=EventType.ZWAVE_DISCOVERY,
                        payload={
                            "path": base_path,
                            "node": node_name,
                            "command_class": command_class,
                            "value": display_val
                        }
                    ))
                return

            # Safely extract routing info for logging and logic
            # Fetch the custom name we pre-seeded, or fallback
            custom_name = self.state_manager._state.dashboard_map.get(target_idx, f"Z-Wave Node {node_name}")

            if raw_val is None:
                return

            # 4. Route Command Classes
            # CC 37: Binary Switches
            if command_class == "37":
                state_str = "ON" if raw_val in [True, 1, "ON", "true"] else "OFF"

                if self._last_known_states.get(target_idx) == state_str:
                    return
                self._last_known_states[target_idx] = state_str

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": target_idx,
                        "state": state_str,
                        "name": custom_name,
                        "device_type": "switch",
                        "origin": "zwave",
                        "is_initialization": False
                    }
                ))

            # CC 38: Multilevel Switches (Blinds / Dimmers)
            elif command_class == "38":
                try:
                    state_val = int(raw_val)
                    # ⚡ INBOUND CLAMP: Map hardware limit (99) back to clean UI metric (100)
                    if state_val == 99:
                        state_val = 100
                except ValueError:
                    state_val = 0

                if self._last_known_states.get(target_idx) == state_val:
                    return

                if self._last_known_states.get(target_idx) == state_val:
                    return
                self._last_known_states[target_idx] = state_val

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": target_idx,
                        "state": state_val,
                        "name": custom_name,
                        "device_type": "blinds",
                        "origin": "zwave",
                        "is_initialization": False
                    }
                ))

            # CC 50: Power Meters, Electric Meters, and Line Voltage Monitors
            elif command_class == "50":
                try:
                    val_float = float(raw_val)

                    # ⚡ LINE VOLTAGE INTERCEPTOR: Node 50 Endpoint 0 Value 66561 reports AC Mains Voltage
                    if "66561" in base_path:
                        voltage_rounded: int = int(round(val_float))
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": target_idx,
                                "state": f"{voltage_rounded} V",
                                "name": custom_name,
                                "device_type": "sensor",
                                "origin": "zwave",
                                "is_initialization": False
                            }
                        ))
                    else:
                        self.state_manager.dispatch(Event(
                            type=EventType.POWER_UPDATED,
                            payload={
                                "idx": target_idx,
                                "value": val_float,
                                "device_type": "power",
                                "origin": "zwave",
                                "name": custom_name
                            }
                        ))
                        # ⚡ DUAL-DISPATCH: Push formatted string directly to the Device Explorer UI
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": target_idx,
                                "state": f"{val_float} W",
                                "name": custom_name,
                                "device_type": "power",
                                "origin": "zwave",
                                "is_initialization": False
                            }
                        ))
                except (ValueError, TypeError):
                    pass

            # CC 48: Binary Sensors (Physical Motion Transceivers / Tamper Flags)
            elif command_class == "48":
                state_str = "ON" if raw_val in [True, 1, "ON", "true", "Motion"] else "OFF"
                if self._last_known_states.get(target_idx) == state_str:
                    return
                self._last_known_states[target_idx] = state_str

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": target_idx,
                        "state": state_str,
                        "name": custom_name,
                        "device_type": "sensor",
                        "origin": "zwave",
                        "is_initialization": False
                    }
                ))

            # CC 49: Multilevel Sensors (Live Wattage Power, Air Temperature, Illuminance Lux)
            elif command_class == "49":
                try:
                    val_float = float(raw_val)
                    lower_path = base_path.lower()

                    if "power" in lower_path:
                        self.state_manager.dispatch(Event(
                            type=EventType.POWER_UPDATED,
                            payload={
                                "idx": target_idx,
                                "value": val_float,
                                "device_type": "power",
                                "origin": "zwave",
                                "name": custom_name
                            }
                        ))
                        # ⚡ DUAL-DISPATCH: Push formatted string directly to the Device Explorer UI
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": target_idx,
                                "state": f"{val_float} W",
                                "name": custom_name,
                                "device_type": "power",
                                "origin": "zwave",
                                "is_initialization": False
                            }
                        ))
                    elif "temp" in lower_path or "air" in lower_path:
                        self.state_manager.dispatch(Event(
                            type=EventType.TEMP_UPDATED,
                            payload={
                                "idx": target_idx,
                                "value": val_float,
                                "name": custom_name
                            }
                        ))
                        # ⚡ DUAL-DISPATCH: Push formatted string directly to the Device Explorer UI
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": target_idx,
                                "state": f"{val_float} °C",
                                "name": custom_name,
                                "device_type": "sensor",
                                "origin": "zwave",
                                "is_initialization": False
                            }
                        ))
                    elif "humid" in lower_path:
                        self.state_manager.dispatch(Event(
                            type=EventType.HUMIDITY_UPDATED,
                            payload={
                                "idx": target_idx,
                                "value": int(val_float),
                                "name": custom_name
                            }
                        ))
                        # ⚡ DUAL-DISPATCH: Push formatted string directly to the Device Explorer UI
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": target_idx,
                                "state": f"{int(val_float)} %",
                                "name": custom_name,
                                "device_type": "sensor",
                                "origin": "zwave",
                                "is_initialization": False
                            }
                        ))
                    elif "illuminance" in lower_path:
                        # ⚡ DUAL-DISPATCH: Push formatted string directly to the Device Explorer UI
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": target_idx,
                                "state": f"{int(val_float)} Lux",
                                "name": custom_name,
                                "device_type": "sensor",
                                "origin": "zwave",
                                "is_initialization": False
                            }
                        ))
                except (ValueError, TypeError):
                    pass

        except Exception as e:
            await self.logger.error(f"[Z-Wave] Parser error on topic {topic}: {e}")

    async def _on_state_changed(self, state: SystemState, events: List[Event] = None) -> None:
        """Acts as the Lazy-Boot Gateway and handles OUTBOUND commands to the ZBT-2"""

        # --- HARDWARE DETECTION LOGGING ---
        if state.system.zwave_hardware_connected and not self._was_hardware_connected:
            self._was_hardware_connected = True
            await self.logger.success("[Z-Wave] Physical USB stick detected.")
        elif not state.system.zwave_hardware_connected and self._was_hardware_connected:
            self._was_hardware_connected = False
            await self.logger.error("🔴 [Z-Wave] Physical USB stick unplugged.")

        # --- HOT-RELOAD DETECTOR ---
        # Natively inspects the event batch for an explicit reload request to eliminate fragile memory address hacks
        is_config_reload = False
        if events:
            for event in events:
                if event.type == EventType.CONFIG_RELOAD_REQUESTED:
                    is_config_reload = True
                    break

        if is_config_reload and self._is_mapped:
            self._is_mapped = False
            self._integration_enabled = False  # Reset to force a clean, synchronous MQTT re-subscription cycle
            await self.logger.info("🔄 [Z-Wave] Core config reload detected. Rebuilding endpoint translations...")

        # --- LAZY BOOT & HARDWARE MAPPING ---
        # Only wake up and map nodes if Tier 1 (USB) and Tier 2 (MQTT LWT) are both verified
        if state.system.zwave_hardware_connected and self.is_mqtt_engine_alive and not self._is_mapped:
            zwave_conf = getattr(self.state_manager._config, "zwave", None)

            if zwave_conf and zwave_conf.device_map:
                # Expose raw configuration mapping to the frontend's PERMANENT memory
                self.state_manager._state.system.zwave_mapped = zwave_conf.device_map
                self.state_manager._state.system.zwave_usb_path = getattr(zwave_conf, "usb_path", "")

                # ⚡ PURGE ORPHANED NODES
                # Identify IDXs that were mapped previously but are absent from the new config.
                new_idxs = [int(k) for k in zwave_conf.device_map.keys()]
                for old_idx in list(self.idx_to_name.keys()):
                    if old_idx not in new_idxs:
                        # Explicitly nullify the state in RAM
                        if old_idx in self.state_manager._state.device_metadata:
                            self.state_manager._state.device_metadata[old_idx] = None
                        if old_idx in self.state_manager._state.dashboard_map:
                            self.state_manager._state.dashboard_map[old_idx] = None
                        if old_idx in self.state_manager._state.devices:
                            self.state_manager._state.devices[old_idx] = None

                        # Dispatch a dummy event to guarantee the SSE stream pushes the 'null' payloads to the UI
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={"idx": old_idx, "state": None, "device_type": "unknown", "origin": "zwave",
                                     "is_initialization": False}
                        ))
                        await self.logger.warning(f"[Z-Wave] Orphaned node (IDX {old_idx}) purged from RAM.")

                # Extract currently loaded baseline exclusions to seamlessly merge tracking lists
                hidden_list: list[int] = list(self.state_manager._state.system.hidden_explorer_idxs)

                # ⚡ Merge dedicated Z-Wave hidden nodes into the global UI exclusion list
                zwave_hidden_nodes = getattr(zwave_conf, "hidden_nodes", [])
                for h_idx in zwave_hidden_nodes:
                    if h_idx not in hidden_list:
                        hidden_list.append(h_idx)

                self.idx_to_name.clear()
                self.name_to_idx.clear()

                for idx, mapping_str in zwave_conf.device_map.items():
                    # Automatically append motion sensor block keys to the hidden collection
                    if 75000 <= idx < 76000 and idx not in hidden_list:
                        hidden_list.append(idx)

                    # Parse the Pipe delimiter
                    if "|" in mapping_str:
                        parts = [s.strip() for s in mapping_str.split("|")]
                        clean_path = parts[0]
                        custom_name = parts[1] if len(parts) > 1 else f"Z-Wave Node {clean_path.split('/')[0]}"
                    else:
                        clean_path = mapping_str.strip()
                        custom_name = f"Z-Wave Node {clean_path.split('/')[0]}"

                    self.idx_to_name[idx] = clean_path
                    self.name_to_idx[clean_path] = idx

                    # Pre-seed the dashboard map so the UI knows the name before the first click!
                    self.state_manager._state.dashboard_map[idx] = custom_name

                    # METADATA SEEDING: Explicitly declare hardware semantics so the UI renders toggles correctly!
                    if idx not in self.state_manager._state.device_metadata:
                        hw_type = "sensor"
                        # Explicit path check prevents voltage monitors under index 71xxx from being misclassified as switches
                        if "66561" in clean_path:
                            hw_type = "sensor"
                        elif 71000 <= idx < 73000:
                            hw_type = "switch"
                        elif 73000 <= idx < 74000:
                            hw_type = "blinds"
                        elif 74000 <= idx < 75000:
                            hw_type = "power"

                        self.state_manager._state.device_metadata[idx] = {
                            "name": custom_name,
                            "type": hw_type,
                            "origin": "zwave"
                        }

                    # STATE SEEDING: Force the frontend to draw newly mapped devices instantly
                    if idx not in self.state_manager._state.devices:
                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": idx,
                                "state": "Sync...",
                                "name": custom_name,
                                "device_type": hw_type,
                                "origin": "zwave",
                                "is_initialization": True
                            }
                        ))

                # This assignment perfectly bypasses the system_handlers.py list wipeout race condition
                self.state_manager._state.system.hidden_explorer_idxs = hidden_list

            self._is_mapped = True
            await self.logger.info(
                f"[Z-Wave] Engine Online. Mapped {len(self.idx_to_name)} dedicated Z-Wave nodes. Waiting for UI arming...")

        # --- OUTBOUND COMMAND ROUTING & LAZY SUBSCRIPTION ---
        current_enabled = state.system.zwave_integration_enabled
        if current_enabled and not self._integration_enabled:
            self._integration_enabled = True
            await self.logger.success("[Z-Wave] Integration ENABLED via UI.")

            # Subscribe to telemetry ONLY at the exact moment the integration is armed.
            # This prevents Mosquitto from flushing its retained messages into the void before WanOS is ready.
            if self._is_mapped:
                await self.mqtt_client.subscribe(f"{self.mqtt_prefix}/#", self._parse_inbound)
                await self.logger.info(f"[Z-Wave] Telemetry stream opened for {len(self.idx_to_name)} nodes.")

        elif not current_enabled and self._integration_enabled:
            self._integration_enabled = False
            await self.logger.info("[Z-Wave] Integration DISABLED via UI.")

        if not self._integration_enabled or not events or not getattr(self.mqtt_client, 'is_connected', False):
            return

        for event in events:
            if event.type != EventType.HUB_STATE_CHANGED:
                continue

            payload = event.payload or {}
            idx = payload.get("idx")
            new_state = payload.get("state")
            origin = payload.get("origin")
            is_force = payload.get("force", False)

            # Prevent infinite loops: Don't echo commands back to Z-Wave if Z-Wave sent them
            if origin == "zwave" and not is_force:
                continue

            # ⚡ READ-ONLY MASTER SAFETY INTERLOCK:
            # Hard-block outbound state changes to our foundational 5V power supply modules.
            # Even if a user bypasses the UI and forces an API event, the bridge will silently
            # drop the command to preserve the physical hardware AND-gate interlock.
            if idx in [71036, 71040]:
                # 71036 = safety 12V = SSR
                # 71040 = safety 5V = Pi itself - without this this code cannot run :-)
                await self.logger.warning(
                    f"🛡️ Z-Wave Bridge intercepted and dropped an unauthorized outbound command to Master Safety Relay (IDX {idx}).")
                continue

            prop_path = self.idx_to_name.get(idx)
            if not prop_path:
                continue

            # Update cache to prevent bounce-back
            self._last_known_states[idx] = new_state

            # Format the target topic for Z-Wave JS UI
            # Z-Wave JS UI uses /targetValue/set to receive intent payloads
            target_topic = f"{self.mqtt_prefix}/{prop_path}/targetValue/set"

            # ⚡ MULTILEVEL INTENT PARSING (100% Clamping)
            # Safely route payload translation based on data type (blinds vs switches).
            # We explicitly clamp '100' down to '99' to respect the Z-Wave CC 38 byte limit.
            if isinstance(new_state, int):
                zwave_payload = {"value": 99 if new_state == 100 else new_state}
            elif isinstance(new_state, str) and new_state.isdigit():
                num_val = int(new_state)
                zwave_payload = {"value": 99 if num_val == 100 else num_val}
            else:
                zwave_payload = {"value": True if new_state == "ON" else False}

            await self.mqtt_client.publish(target_topic, zwave_payload)

            if is_force:
                await self.logger.warning(f"⚡ [FORCED] Z-Wave Command Sent: {prop_path} -> {new_state}")
            else:
                await self.logger.info(f"[Z-Wave] Command Sent: {prop_path} -> {new_state}")