import asyncio
import json
from typing import Any, Dict
from core.models import Event, EventType, SystemState
from core.state_manager import StateManager


class DomoticzHomeHubBridge:
    def __init__(self, state_manager: StateManager, domoticz_mqtt_client: Any,
                 domoticz_in_topic: str = "domoticz/out",
                 domoticz_out_topic: str = "domoticz/in") -> None:
        self.state_manager = state_manager
        self.state_manager.domoticz_client = domoticz_mqtt_client
        self.mqtt_client = domoticz_mqtt_client
        self.logger = state_manager.logger
        self._in_topic = domoticz_in_topic
        self._out_topic = domoticz_out_topic

        # Dynamic reverse-lookup tables generated straight from hardware.yaml
        idx_mapping = state_manager._config.domoticz.idx
        self._idx_to_name = {mapping.id: name for name, mapping in idx_mapping.items()}
        self._name_to_idx = {name: mapping.id for name, mapping in idx_mapping.items()}

        # Circuit breaker dictionary tracking the entire system's state history
        self._last_known_states: Dict[str, Any] = {}

    async def start(self) -> None:
        await self.mqtt_client.subscribe(self._in_topic, self._parse_domoticz_inbound)
        self.state_manager.register_listener(self._on_state_changed)
        await self.logger.success("🏠 Domoticz HomeHub Bridge initialized (Dynamic Registry Mode).")

    async def stop(self) -> None:
        await self.logger.warning("🏠 Domoticz HomeHub Bridge stopped.")

    async def _parse_domoticz_inbound(self, topic: str, payload: str) -> None:
        try:
            data: Dict[str, Any] = json.loads(payload)
            idx = data.get("idx")

            if idx is None:
                return

            device_name = self._idx_to_name.get(idx)
            if not device_name:
                return  # Unregistered device, safely ignore

            # Log only verified hardware snapshots into the Tier 2 console system history
            await self.logger.debug(f"⚙️ [DOMOTICZ] Node '{device_name}' (IDX {idx}) pushed frame: {payload}")

            device_type = self.state_manager._config.domoticz.idx[device_name].type

            # The generic translator handles ALL devices automatically without explicit IDs
            if device_type == "temphum":
                raw_temp = data.get("svalue1")
                raw_hum = data.get("svalue2")
                if raw_temp is not None:
                    self.state_manager.dispatch(Event(
                        type=EventType.TEMP_UPDATED,
                        payload={"sensor_id": device_name, "value": float(raw_temp)}
                    ))
                if raw_hum is not None:
                    self.state_manager.dispatch(Event(
                        type=EventType.HUMIDITY_UPDATED,
                        payload={"sensor_id": device_name, "value": int(float(raw_hum))}
                    ))

            elif device_type == "switch":
                nvalue = data.get("nvalue", 0)
                status_string = "ON" if nvalue > 0 else "OFF"

                # Lock into local memory to prevent echo loops
                self._last_known_states[device_name] = status_string

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"device_id": device_name, "state": status_string}
                ))

        except ValueError as val_err:
            await self.logger.error(f"Domoticz parser dropped invalid JSON: {val_err}")
        except Exception as e:
            await self.logger.error(f"Error handling Domoticz translation: {e}")

    async def _on_state_changed(self, state: SystemState) -> None:
        try:
            # Dynamically sweep the entire UI registry for modifications
            for device_name, idx in self._name_to_idx.items():
                device_type = self.state_manager._config.domoticz.idx[device_name].type
                if device_type != "switch":
                    continue

                # 1. Look for the state in explicitly mapped core properties (The Engine)
                current_state = None
                if device_name == "bathroom_ventilator":
                    current_state = "ON" if state.environment.bathroom_vent_on else "OFF"
                elif device_name == "sauna_extrvent":
                    current_state = "ON" if state.environment.sauna_extraction_vent_on else "OFF"
                elif device_name == "cinema_hue":
                    current_state = "ON" if state.environment.cinema_hue_on else "OFF"
                elif device_name == "sauna_hue":
                    current_state = "ON" if state.environment.sauna_hue_on else "OFF"
                else:
                    # 2. Look for the state in the generic peripheral dictionary (The Dashboard)
                    current_state = state.devices.get(device_name)

                # If it changed, broadcast it back out to Domoticz!
                if current_state is not None and current_state != self._last_known_states.get(device_name):
                    domoticz_command = {
                        "command": "switchlight",
                        "idx": idx,
                        "switchcmd": "On" if current_state == "ON" else "Off"
                    }
                    await self.mqtt_client.publish(self._out_topic, domoticz_command)
                    await self.logger.info(f"🏠 Domoticz Sync: {device_name} -> {current_state}")
                    self._last_known_states[device_name] = current_state

        except Exception as e:
            await self.logger.error(f"Error in Domoticz outbound sync: {e}")