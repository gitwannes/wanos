# --- file: integrations/home_hub.py ---
import asyncio
import json
from typing import Any, Dict
from core.models import Event, EventType, SystemState
from core.state_manager import StateManager
from loguru import logger


class DomoticzHomeHubBridge:
    def __init__(self, state_manager: StateManager, domoticz_mqtt_client: Any,
                 domoticz_in_topic: str = "domoticz/out",
                 domoticz_out_topic: str = "domoticz/in") -> None:
        self.state_manager = state_manager
        self.state_manager.domoticz_client = domoticz_mqtt_client
        self.mqtt_client = domoticz_mqtt_client
        self._in_topic = domoticz_in_topic
        self._out_topic = domoticz_out_topic

        # Dynamic reverse-lookup tables generated straight from hardware.yaml
        idx_mapping = state_manager._config.domoticz.idx
        self._idx_to_name = {mapping.id: name for name, mapping in idx_mapping.items()}
        self._name_to_idx = {name: mapping.id for name, mapping in idx_mapping.items()}

        # Circuit breaker dictionary tracking the entire system's state history
        self._last_known_states: Dict[str, Any] = {}

        # Early-gate cache to silently drop exact duplicate Domoticz broadcasts
        self._raw_cache: Dict[int, Any] = {}

        # ⚡ Debounce properties to filter out rapid signal bouncing
        self._debounce_tasks: Dict[int, asyncio.Task] = {}
        self._debounce_delay: float = 0.3  # 300ms waiting room

    @property
    def watched_idxs(self) -> set[int]:
        """Dynamically scans the YAML config for any raw IDXs used in automations."""
        idxs = set()
        if hasattr(self.state_manager._config, "automations"):
            for rule in self.state_manager._config.automations:
                # 1. Grab Trigger IDXs
                if rule.trigger.idx:
                    idxs.add(rule.trigger.idx)
                # 2. Grab Action IDXs
                if rule.actions:
                    for action in rule.actions:
                        if action.idx:
                            idxs.add(action.idx)
        return idxs

    async def start(self) -> None:
        # 1. Start listening for incoming broadcasts first
        await self.mqtt_client.subscribe(self._in_topic, self._parse_domoticz_inbound)
        self.state_manager.register_listener(self._on_state_changed)

        # 2. Track internal toggle state to catch transitions
        self._integration_enabled = self.state_manager._state.system.domoticz_integration_enabled

        # 3. Only run cold-boot sync if the switch is ON at startup
        if self._integration_enabled:
            await self._fetch_initial_states_mqtt()

        logger.success("[Domoticz] HomeHub Bridge initialized (Pure MQTT Mode).")

    async def stop(self) -> None:
        logger.warning("[Domoticz] HomeHub Bridge stopped.")

    async def _fetch_initial_states_mqtt(self) -> None:
        """Fires MQTT commands to force Domoticz to broadcast current hardware states."""

        # Combine mapped IDXs and raw YAML IDXs into a single unique set
        all_idxs_to_fetch = set()
        for idx in self._name_to_idx.values():
            if idx > 0:
                all_idxs_to_fetch.add(idx)
        for idx in self.watched_idxs:
            if idx > 0:
                all_idxs_to_fetch.add(idx)

        # Calculate the total count
        count = len(all_idxs_to_fetch)
        logger.info(
            f"Firing {count} MQTT state requests to Domoticz for cold-boot sync and awaiting asynchronous echo...")

        for idx in all_idxs_to_fetch:
            command_payload = {
                "command": "getdeviceinfo",
                "idx": idx
            }
            # Ask Domoticz to broadcast the status of this specific IDX
            await self.mqtt_client.publish(self._out_topic, command_payload)

            # Tiny 50ms network buffer to prevent Mosquitto/Domoticz queue stuttering
            await asyncio.sleep(0.05)

    async def _parse_domoticz_inbound(self, topic: str, payload: str) -> None:
        # ⚡ Master Lockout: Silently drop all incoming Domoticz messages if integration is disabled in the UI
        if not self.state_manager._state.system.domoticz_integration_enabled:
            return

        try:
            data: Dict[str, Any] = json.loads(payload)
            idx = data.get("idx")

            if idx is None:
                return

            # --- DEBUG CODE ---
            #if idx == 9:
            #    logger.info(f"[DIAGNOSTIC] Raw frame hit bridge entrance for IDX 9: {payload}")

            device_name = self._idx_to_name.get(idx)
            # Only drop it if it's NOT in hardware.yaml AND NOT in our automation rules
            if not device_name and idx not in self.watched_idxs:
                return  # Unregistered device, safely ignore

            # ⚡ EARLY GATE DUPLICATE FILTER ⚡
            # Extract only the value fields Domoticz uses to broadcast states
            nvalue = data.get("nvalue")
            svalue1 = data.get("svalue1")
            svalue2 = data.get("svalue2")
            svalue = data.get("svalue")

            cache_state = {"nvalue": nvalue, "svalue1": svalue1, "svalue2": svalue2, "svalue": svalue}

            if self._raw_cache.get(idx) == cache_state:
                return  # Exact duplicate value. Silently drop to prevent engine noise.

            self._raw_cache[idx] = cache_state

            # Forward only the requested fields in the exact order to the WanOS internal raw bus
            filtered_raw_data = {
                "idx": data.get("idx"),
                "name": data.get("name", device_name),
                "dtype": data.get("dtype"),
                "nvalue": data.get("nvalue"),
                "svalue": data.get("svalue"),
                "svalue1": data.get("svalue1"),
                "svalue2": data.get("svalue2")
            }

            await self.state_manager.mqtt_client.publish("wanos/domsensors/raw", filtered_raw_data)

            # Safely extract device type, defaulting to unknown if it's an unmapped raw IDX
            device_type = "unknown"
            if device_name:
                device_type = self.state_manager._config.domoticz.idx[device_name].type

            # The generic translator handles ALL devices automatically without explicit IDs
            # This perfectly processes both natural live updates AND our boot-sync responses!
            if device_type == "temphum":
                # Domoticz encapsulates combined Temp/Hum sensors via 'svalue1' or 'svalue'
                # frequently formatted as a semicolon-separated string: "21.5;45;0" (Temp;Hum;Status)
                svalue_str: str = str(data.get("svalue1", data.get("svalue", "")))

                raw_temp: str | None = None
                raw_hum: str | None = None

                if ";" in svalue_str:
                    parts: list[str] = svalue_str.split(";")
                    raw_temp = parts[0]
                    if len(parts) > 1:
                        raw_hum = parts[1]
                else:
                    # Fallback for cleanly split values if Domoticz sends them natively
                    raw_temp = data.get("svalue1")
                    raw_hum = data.get("svalue2")

                # Format a clean log string regardless of how Domoticz packed the payload
                log_parts = []
                if raw_temp is not None and raw_temp != "":
                    log_parts.append(f"{raw_temp}°C")
                if raw_hum is not None and raw_hum != "":
                    log_parts.append(f"{raw_hum}%")

                log_display = " / ".join(log_parts) if log_parts else "No Data"
                logger.debug(f"[Domoticz] Node '{device_name}' (IDX {idx}) sensor update received -> {log_display}")

                if raw_temp is not None and raw_temp != "":
                    self.state_manager.dispatch(Event(
                        type=EventType.TEMP_UPDATED,
                        payload={"sensor_id": device_name, "value": float(raw_temp)}
                    ))
                if raw_hum is not None and raw_hum != "":
                    self.state_manager.dispatch(Event(
                        type=EventType.HUMIDITY_UPDATED,
                        payload={"sensor_id": device_name, "value": int(float(raw_hum))}
                    ))

            elif device_type == "switch" or idx in self.watched_idxs:
                # or idx: If it's not a mapped device, we still process it if the automation engine needs it!
                nvalue = data.get("nvalue", 0)
                status_string = "ON" if nvalue > 0 else "OFF"

                # Wrap unmapped IDXs in our virtual string format
                target_id = device_name if device_name else f"idx_{idx}"

                if self._last_known_states.get(target_id) == status_string:
                    return

                # Lock into local memory to prevent echo loops
                self._last_known_states[target_id] = status_string

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "device_id": target_id,  # passes "sauna_hue" OR "idx_1524"
                        "idx": idx,  # Always pass the raw integer
                        "state": status_string
                    }
                ))

            elif device_type == "power":
                try:
                    # Domoticz sends Wattage as a string in the 'svalue1' field
                    raw_svalue = data.get("svalue1", "0.0")
                    wattage = float(raw_svalue)

                    # --- DEBUG CODE ---
                    # logger.info(f"[DIAGNOSTIC] Bridge successfully translated '{device_name}' -> {wattage} W")

                    # Dispatch the new event to the WanOS State Manager
                    event = Event(
                        type=EventType.POWER_UPDATED,
                        payload={
                            "sensor_id": device_name,  # This will automatically be "pc_(aux_)power" from the YAML
                            "value": wattage
                        }
                    )
                    self.state_manager.dispatch(event)

                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to parse power reading for {device_name}: {e}")

        except ValueError as val_err:
            logger.error(f"Domoticz parser dropped invalid JSON: {val_err}")
        except Exception as e:
            logger.error(f"Error handling Domoticz translation: {e}")

    async def _on_state_changed(self, state: SystemState) -> None:
        try:
            # --- EVALUATE MASTER TOGGLE TRANSITIONS ---
            current_enabled = state.system.domoticz_integration_enabled
            if current_enabled and not getattr(self, '_integration_enabled', False):
                self._integration_enabled = True
                logger.info("[Domoticz] Integration ENABLED via UI. Initiating network sync...")
                asyncio.create_task(self._fetch_initial_states_mqtt())
            elif not current_enabled and getattr(self, '_integration_enabled', False):
                self._integration_enabled = False
                logger.info("[Domoticz] Integration DISABLED via UI.")

            # If the integration is locked out, do not push outbound commands
            if not current_enabled:
                return

            # 1. Mapped Semantic Devices (From hardware.yaml)
            for device_name, idx in self._name_to_idx.items():
                device_type = self.state_manager._config.domoticz.idx[device_name].type
                if device_type != "switch":
                    continue

                # Grab the state directly from the generic devices dictionary
                current_state = state.devices.get(device_name)

                # If it changed, assemble the JSON and broadcast it back out to Domoticz
                if current_state is not None and current_state != self._last_known_states.get(device_name):
                    domoticz_command = {
                        "command": "switchlight",
                        "idx": idx,
                        "switchcmd": "On" if current_state == "ON" else "Off"
                    }
                    await self.mqtt_client.publish(self._out_topic, domoticz_command)
                    logger.info(f"[Domoticz] Command Sent: {device_name} -> {current_state}")
                    self._last_known_states[device_name] = current_state

            # 2. Raw IDXs from Automations (e.g., "idx_1524")
            for key, current_state in state.devices.items():
                if key.startswith("idx_"):
                    raw_idx = int(key.split("_")[1])
                    if current_state is not None and current_state != self._last_known_states.get(key):
                        domoticz_command = {"command": "switchlight", "idx": raw_idx,
                                            "switchcmd": "On" if current_state == "ON" else "Off"}
                        await self.mqtt_client.publish(self._out_topic, domoticz_command)
                        logger.info(f"[Domoticz] Raw Command Sent: IDX {raw_idx} -> {current_state}")
                        self._last_known_states[key] = current_state

        except Exception as e:
            logger.error(f"Error in Domoticz outbound sync: {e}")