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

    async def start(self) -> None:
        # SILENT STANDBY: Only listen for the Z-Wave JS UI authoritative driver status
        # We do NOT map nodes or subscribe to telemetry until the physical USB stick is detected.
        await self.mqtt_client.subscribe("zwave/driver/status", self._parse_hardware_status)

        # Listen to internal state changes to detect when the USB stick is plugged in
        self.state_manager.register_listener(self._on_state_changed)

        await self.logger.info("[Z-Wave] Bridge in Silent Standby. Waiting for hardware detection.")

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
        """Parses physical sensor updates coming from the ZBT-2"""
        if not self._integration_enabled:
            return

        try:
            data: dict[str, Any] = json.loads(payload)
            parts = topic.split('/')

            node_name = parts[1]
            command_class = parts[2]

            target_idx = self.name_to_idx.get(node_name)
            if not target_idx:
                return

            raw_val = data.get("value")

            # Route Binary Switches / Plugs
            if command_class in ["switch_binary", "targetValue"]:
                state_str = "ON" if raw_val in [True, 1, "ON", "true"] else "OFF"

                # Deduplication cache
                if self._last_known_states.get(target_idx) == state_str:
                    return
                self._last_known_states[target_idx] = state_str

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": target_idx,
                        "state": state_str,
                        "name": node_name,
                        "device_type": "switch",
                        "origin": "zwave",
                        "is_initialization": False
                    }
                ))

            # Route Power Meters (Electric_W)
            elif command_class == "meter" and "Electric_W" in topic:
                self.state_manager.dispatch(Event(
                    type=EventType.POWER_UPDATED,
                    payload={"idx": target_idx, "value": float(raw_val), "device_type": "power", "origin": "zwave",
                             "name": node_name}
                ))

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
                for idx, prop_path in zwave_conf.device_map.items():
                    # Safely map explicitly declared Z-Wave sensors (e.g. 70001: "nodeID_5/37/0/targetValue")
                    self.idx_to_name[idx] = prop_path
                    self.name_to_idx[prop_path] = idx

            # Now that we are awake and mapped, subscribe to actual Z-Wave mesh telemetry
            await self.mqtt_client.subscribe("zwave/+/+/+/+", self._parse_inbound)
            self._is_mapped = True
            await self.logger.info(
                f"[Z-Wave] Engine Online. Mapped {len(self.idx_to_name)} dedicated Z-Wave nodes.")

        # --- OUTBOUND COMMAND ROUTING ---
        current_enabled = state.system.zwave_integration_enabled
        if current_enabled and not self._integration_enabled:
            self._integration_enabled = True
            await self.logger.success("[Z-Wave] Integration ENABLED via UI.")
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
            # Z-Wave JS UI listens on ".../set" for properties mapped like "nodeID_5/37/0/targetValue"
            target_topic = f"zwave/{prop_path}/set"

            # Z-Wave JS UI expects a boolean payload for binary switches
            zwave_payload = {"value": True if new_state == "ON" else False}

            await self.mqtt_client.publish(target_topic, zwave_payload)

            if is_force:
                await self.logger.warning(f"⚡ [FORCED] Z-Wave Command Sent: {prop_path} -> {new_state}")
            else:
                await self.logger.info(f"[Z-Wave] Command Sent: {prop_path} -> {new_state}")