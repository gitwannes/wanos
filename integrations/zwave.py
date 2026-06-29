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

    @property
    def mqtt_prefix(self) -> str:
        """Dynamically pulls the MQTT prefix from config (defaults to 'zwave')"""
        zwave_conf = getattr(self.state_manager._config, "zwave", None)
        return getattr(zwave_conf, "mqtt_prefix", "zwave") if zwave_conf else "zwave"

    async def start(self) -> None:
        # SILENT STANDBY: Only listen for the Z-Wave JS UI authoritative driver status
        await self.mqtt_client.subscribe(f"{self.mqtt_prefix}/driver/status", self._parse_hardware_status)

        # Listen to internal state changes to detect when the USB stick is plugged in
        self.state_manager.register_listener(self._on_state_changed)

        await self.logger.info(
            f"[Z-Wave] Bridge in Silent Standby. Prefix '{self.mqtt_prefix}'. Waiting for hardware detection.")

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

            # 3. Intent vs State: Only process true hardware physical states
            if not (mapped_path.endswith("/currentValue") or mapped_path.endswith("/value")):
                return

            # Strip the suffix to match our YAML base dictionary (e.g., nodeID_31/37/1)
            base_path = mapped_path.rsplit('/', 1)[0]

            target_idx = self.name_to_idx.get(base_path)
            if not target_idx:
                return

            # Safely extract routing info for logging and logic
            node_name = base_path.split('/')[0]  # e.g. "31"
            command_class = base_path.split('/')[1]  # "37", "38", or "50"

            # Fetch the custom name we pre-seeded, or fallback
            custom_name = self.state_manager._state.dashboard_map.get(target_idx, f"Z-Wave Node {node_name}")

            raw_val = data.get("value")
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
                except ValueError:
                    state_val = 0

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

            # CC 50: Power Meters
            elif command_class == "50":
                try:
                    wattage = float(raw_val)
                    self.state_manager.dispatch(Event(
                        type=EventType.POWER_UPDATED,
                        payload={
                            "idx": target_idx,
                            "value": wattage,
                            "device_type": "power",
                            "origin": "zwave",
                            "name": custom_name
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

        # --- LAZY BOOT & HARDWARE MAPPING ---
        # Only wake up and map nodes if Tier 1 (USB) and Tier 2 (MQTT LWT) are both verified
        if state.system.zwave_hardware_connected and self.is_mqtt_engine_alive and not self._is_mapped:
            zwave_conf = getattr(self.state_manager._config, "zwave", None)
            if zwave_conf and zwave_conf.device_map:
                for idx, mapping_str in zwave_conf.device_map.items():
                    # Parse the Pipe delimiter
                    if "|" in mapping_str:
                        clean_path, custom_name = [s.strip() for s in mapping_str.split("|", 1)]
                    else:
                        clean_path = mapping_str.strip()
                        custom_name = f"Z-Wave Node {clean_path.split('/')[0]}"

                    self.idx_to_name[idx] = clean_path
                    self.name_to_idx[clean_path] = idx

                    # Pre-seed the dashboard map so the UI knows the name before the first click!
                    self.state_manager._state.dashboard_map[idx] = custom_name

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

            prop_path = self.idx_to_name.get(idx)
            if not prop_path:
                continue

            # Update cache to prevent bounce-back
            self._last_known_states[idx] = new_state

            # Format the target topic for Z-Wave JS UI
            # Z-Wave JS UI uses /targetValue/set to receive intent payloads
            target_topic = f"{self.mqtt_prefix}/{prop_path}/targetValue/set"

            # Route payload translation based on data type (blinds vs switches)
            if isinstance(new_state, int):
                zwave_payload = {"value": new_state}
            else:
                zwave_payload = {"value": True if new_state == "ON" else False}

            await self.mqtt_client.publish(target_topic, zwave_payload)

            if is_force:
                await self.logger.warning(f"⚡ [FORCED] Z-Wave Command Sent: {prop_path} -> {new_state}")
            else:
                await self.logger.info(f"[Z-Wave] Command Sent: {prop_path} -> {new_state}")