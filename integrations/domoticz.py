# --- file: integrations/domoticz.py ---
import asyncio
import json
from typing import Any
from core.models import Event, EventType, SystemState
from core.state_manager import StateManager
from core.logger import WanosComponent


class DomoticzHomeHubBridge(WanosComponent):
    def __init__(self, state_manager: StateManager, domoticz_mqtt_client: Any,
                 domoticz_in_topic: str = "domoticz/out",
                 domoticz_out_topic: str = "domoticz/in") -> None:
        super().__init__(state_manager)  # Initialize component (sets self.state_manager and self.logger)
        self.state_manager.domoticz_client = domoticz_mqtt_client
        self.mqtt_client = domoticz_mqtt_client
        self._in_topic = domoticz_in_topic
        self._out_topic = domoticz_out_topic

        # Circuit breaker dictionary tracking the entire system's state history
        # Keys are now raw integer IDXs
        self._last_known_states: dict[int, Any] = {}

        # Early-gate cache to silently drop exact duplicate Domoticz broadcasts
        self._raw_cache: dict[int, Any] = {}

        # ⚡ Debounce properties to filter out rapid signal bouncing
        self._debounce_tasks: dict[int, asyncio.Task] = {}
        self._debounce_delay: float = 0.3  # 300ms waiting room

        # Core track loop tracking variable to evaluate config reload deltas
        self._tracked_whitelist: set[int] = set()

    @property
    def watched_idxs(self) -> set[int]:
        """Dynamically builds a whitelist by scanning both the dashboard and automations."""
        idxs = set()

        # 1. Grab UI Dashboard IDXs
        if hasattr(self.state_manager._config, "dashboard"):
            for idx in self.state_manager._config.dashboard.keys():
                if isinstance(idx, int) and idx < 10000:
                    idxs.add(idx)

        # 2. Grab Hardware RFX Switch Translation Component Triggers
        if hasattr(self.state_manager._config, "rfx_switches"):
            for switch in self.state_manager._config.rfx_switches:
                idxs.add(switch.on_trigger_idx)
                idxs.add(switch.off_trigger_idx)
                idxs.add(switch.virtual_idx)

        # 3. Grab Automation IDXs
        if hasattr(self.state_manager._config, "automations"):
            for rule in self.state_manager._config.automations:
                triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]
                for t in triggers:
                    # Filter out any internal/virtual IDXs
                    if t.idx is not None and t.idx < 10000:
                        idxs.add(t.idx)
                if rule.actions:
                    for action in rule.actions:
                        if action.idx is not None and action.idx < 10000:
                            idxs.add(action.idx)
        return idxs

    async def start(self) -> None:
        # 1. Start listening for incoming broadcasts first
        await self.mqtt_client.subscribe(self._in_topic, self._parse_domoticz_inbound)
        self.state_manager.register_listener(self._on_state_changed)

        # 2. Track internal toggle state to catch transitions
        self._integration_enabled = self.state_manager._state.system.domoticz_integration_enabled

        # Initialize structural tracking whitelist matrix cache
        self._tracked_whitelist = self.watched_idxs

        # 3. Only run cold-boot sync if the switch is ON at startup
        if self._integration_enabled:
            await self._fetch_initial_states_mqtt()

        await self.logger.success("[Domoticz] HomeHub Bridge initialized (Pure MQTT IDX Mode).")

    async def stop(self) -> None:
        await self.logger.warning("[Domoticz] HomeHub Bridge stopped.")

    async def _fetch_initial_states_mqtt(self) -> None:
        """Fires MQTT commands to force Domoticz to broadcast current hardware states."""
        # ⚡ HUB GUARD: Do not publish if network is down
        if not getattr(self.mqtt_client, 'is_connected', False):
            await self.logger.warning("[Domoticz] Network down. Aborting initial state sync.")
            return

        all_idxs_to_fetch = self.watched_idxs

        # ⚡ EXCLUDE STATELESS RFX BUTTONS FROM BOOT SYNC ⚡
        # We never want to ask Domoticz for the status of a stateless remote control button.
        if hasattr(self.state_manager._config, "rfx_switches"):
            for switch in self.state_manager._config.rfx_switches:
                all_idxs_to_fetch.discard(switch.on_trigger_idx)
                all_idxs_to_fetch.discard(switch.off_trigger_idx)

        count = len(all_idxs_to_fetch)
        await self.logger.info(
            f"Firing {count} MQTT state requests to Domoticz for cold-boot sync and awaiting asynchronous echo...")

        for idx in all_idxs_to_fetch:
            # We only query actual Domoticz hardware (virtual IDXs >= 10000 exist only locally)
            if idx < 10000:
                command_payload = {
                    "command": "getdeviceinfo",
                    "idx": idx
                }
                await self.mqtt_client.publish(self._out_topic, command_payload)
                await asyncio.sleep(0.05)

    async def _parse_domoticz_inbound(self, topic: str, payload: str) -> None:
        # ⚡ Master Lockout: Silently drop all incoming Domoticz messages if integration is disabled in the UI
        if not self.state_manager._state.system.domoticz_integration_enabled:
            return

        try:
            data: dict[str, Any] = json.loads(payload)
            idx = data.get("idx")

            if idx is None:
                return

            idx = int(idx)

            # Cancel any pending debounce task for this specific IDX
            if idx in self._debounce_tasks:
                self._debounce_tasks[idx].cancel()

            # Spawn a new delayed execution task (The "Waiting Room")
            self._debounce_tasks[idx] = asyncio.create_task(self._process_debounced_payload(idx, data))

        except ValueError as val_err:
            await self.logger.error(f"Domoticz parser dropped invalid JSON: {val_err}")
        except Exception as e:
            await self.logger.error(f"Error handling Domoticz translation: {e}")

    async def _process_debounced_payload(self, idx: int, data: dict[str, Any]) -> None:
        """Waits for the debounce window to clear, then processes the final resting state."""
        try:
            await asyncio.sleep(self._debounce_delay)
        except asyncio.CancelledError:
            # A newer message arrived for this IDX before the timer finished. Silently die.
            return

        # Clean up the task reference
        if idx in self._debounce_tasks:
            del self._debounce_tasks[idx]

        try:
            # Only process if it's explicitly in our compiled whitelist
            if idx not in self.watched_idxs:
                return

            # ⚡ Hardware Interception: Translate Stateless 433MHz Signals to Stateful Virtual Nodes Early
            if hasattr(self.state_manager._config, "rfx_switches"):
                for switch in self.state_manager._config.rfx_switches:
                    if idx == switch.on_trigger_idx or idx == switch.off_trigger_idx:
                        target_state: str = "ON" if idx == switch.on_trigger_idx else "OFF"
                        virtual_idx: int = switch.virtual_idx

                        # ⚡ Deterministic Echo Drop: If the virtual node is already in this state in the circuit-breaker, it's an echo.
                        if self._last_known_states.get(virtual_idx) == target_state:
                            return

                        # Look up the actual virtual name from the map, preventing the physical remote's name from bleeding into the UI
                        virtual_name = self.state_manager._config.dashboard.get(virtual_idx, f"idx_{virtual_idx}")

                        self.state_manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": virtual_idx,
                                "state": target_state,
                                "name": virtual_name,
                                "is_push_button": False,
                                "rfx_origin": idx  # ⚡ Tag the origin!
                            }
                        ))
                        await self.logger.debug(
                            f"[Domoticz] RFX Remote intercepted: Translated Trigger IDX {idx} -> Virtual Node IDX {virtual_idx} set to {target_state}")
                        return
            # ⚡ Prioritize the live Domoticz name, fallback to config map, then generic idx_ string
            device_name = data.get("name") or self.state_manager._config.dashboard.get(idx, f"idx_{idx}")

            # ⚡ EARLY GATE DUPLICATE FILTER ⚡
            nvalue = data.get("nvalue")
            svalue1 = data.get("svalue1")
            svalue2 = data.get("svalue2")
            svalue = data.get("svalue")

            cache_state = {"nvalue": nvalue, "svalue1": svalue1, "svalue2": svalue2, "svalue": svalue}

            # ⚡ PUSH BUTTON BYPASS: Momentary buttons send the exact same payload every time.
            # We MUST bypass the cache filter for these, otherwise only the first press works!
            switch_type = data.get("switchType", "")
            is_push_button = switch_type.split(" ")[0] == "Push"

            if not is_push_button and self._raw_cache.get(idx) == cache_state:
                return  # Exact duplicate value. Silently drop to prevent engine noise.

            self._raw_cache[idx] = cache_state

            # Forward raw data to internal bus
            filtered_raw_data = {
                "idx": idx,
                "name": data.get("name", device_name),
                "dtype": data.get("dtype"),
                "nvalue": nvalue,
                "svalue": svalue,
                "svalue1": svalue1,
                "svalue2": svalue2
            }

            await self.state_manager.mqtt_client.publish("wanos/domsensors/raw", filtered_raw_data)

            dtype = data.get("dtype", "")

            # 1. Temp & Humidity Sensors
            if "Temp" in dtype or "Hum" in dtype:
                svalue_str: str = str(data.get("svalue1", data.get("svalue", "")))
                raw_temp: str | None = None
                raw_hum: str | None = None

                if ";" in svalue_str:
                    parts: list[str] = svalue_str.split(";")
                    raw_temp = parts[0]
                    if len(parts) > 1:
                        raw_hum = parts[1]
                else:
                    raw_temp = data.get("svalue1")
                    raw_hum = data.get("svalue2")

                log_parts = []
                if raw_temp is not None and raw_temp != "":
                    log_parts.append(f"{raw_temp}°C")
                    self.state_manager.dispatch(Event(
                        type=EventType.TEMP_UPDATED,
                        payload={"idx": idx, "value": float(raw_temp)}
                    ))
                if raw_hum is not None and raw_hum != "":
                    log_parts.append(f"{raw_hum}%")
                    self.state_manager.dispatch(Event(
                        type=EventType.HUMIDITY_UPDATED,
                        payload={"idx": idx, "value": int(float(raw_hum))}
                    ))

                log_display = " / ".join(log_parts) if log_parts else "No Data"
                await self.logger.debug(
                    f"[Domoticz] Node '{device_name}' (IDX {idx}) sensor ({dtype}) update received -> {log_display}")

            # 2. Power Sensors
            elif "Usage" in dtype or "Watt" in dtype or "Power" in dtype:
                try:
                    raw_svalue = data.get("svalue1", "0.0")
                    wattage = float(raw_svalue)
                    log_display = f"{wattage} W"
                    self.state_manager.dispatch(Event(
                        type=EventType.POWER_UPDATED,
                        payload={"idx": idx, "value": wattage}
                    ))
                except (ValueError, TypeError) as e:
                    await self.logger.error(f"Failed to parse power reading for IDX {idx}: {e}")

            # 3. Switches and Relays
            else:
                nvalue = data.get("nvalue", 0)
                status_string = "ON" if nvalue > 0 else "OFF"
                log_display = status_string

                # Detect if this inbound switch update belongs to a decoupled virtual RFX target
                is_rfx_virtual: bool = False
                if hasattr(self.state_manager._config, "rfx_switches"):
                    is_rfx_virtual = any(s.virtual_idx == idx for s in self.state_manager._config.rfx_switches)

                if not is_push_button and self._last_known_states.get(idx) == status_string:
                    return

                    # Only commit to circuit-breaker cache if it's NOT a virtual RFX switch.
                    # For virtual RFX nodes, we let _on_state_changed handle cache mutation and command transmissions.
                if not is_rfx_virtual:
                    self._last_known_states[idx] = status_string

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": idx,
                        "state": status_string,
                        "name": data.get("name"),  # for hybrid dashboard map learning
                        "is_push_button": is_push_button,
                        "rfx_origin": None  # ⚡ Tag as UI/Internal origin
                    }
                ))
                await self.logger.debug(
                    f"[Domoticz] Node '{device_name}' (IDX {idx}) sensor ({dtype}) update received -> {log_display}")

        except Exception as e:
            await self.logger.error(f"Error in debounced Domoticz translation: {e}")

    async def _on_state_changed(self, state: SystemState, events: list[Event] = None) -> None:
        try:
            # --- EVALUATE MASTER TOGGLE TRANSITIONS ---
            current_enabled = state.system.domoticz_integration_enabled
            if current_enabled and not getattr(self, '_integration_enabled', False):
                self._integration_enabled = True
                await self.logger.success("[Domoticz] Integration ENABLED via UI.")
                # ⚡ CACHE PURGE: Wipe the internal bridge memory so the incoming sync echoes aren't silently dropped!
                # This forces the bridge to pass the data to the Engine, triggering a clean is_initialization boot sequence.
                self._raw_cache.clear()
                self._last_known_states.clear()
                await self.logger.info("[Domoticz] Initiating network sync...")
                asyncio.create_task(self._fetch_initial_states_mqtt())
            elif not current_enabled and getattr(self, '_integration_enabled', False):
                self._integration_enabled = False
                await self.logger.info("[Domoticz] Integration DISABLED via UI.")

            if not current_enabled:
                return

            forced_devices = set()
            initialized_devices = set()
            rfx_origins: dict[int, Any] = {}
            if events:
                for event in events:
                    if event.type == EventType.HUB_STATE_CHANGED:
                        payload = event.payload
                        if payload.get("force"):
                            forced_devices.add(payload.get("idx"))
                        if payload.get("is_initialization"):
                            initialized_devices.add(payload.get("idx"))
                        if "rfx_origin" in payload and payload.get("rfx_origin") is not None:
                            rfx_origins[payload.get("idx")] = payload.get("rfx_origin")
                    elif event.type == EventType.CONFIG_RELOAD_REQUESTED:
                        # Delta verification evaluation loop for dynamic inclusions/exclusions
                        new_whitelist = self.watched_idxs
                        added_idxs = new_whitelist - self._tracked_whitelist
                        removed_idxs = self._tracked_whitelist - new_whitelist
                        self._tracked_whitelist = new_whitelist

                        if removed_idxs:
                            await self.logger.info(
                                f"[Domoticz] Config reload pruned {len(removed_idxs)} devices from active listening channels.")

                        # ⚡ Exclude stateless RFX triggers from the active delta query
                        if hasattr(self.state_manager._config, "rfx_switches"):
                            for switch in self.state_manager._config.rfx_switches:
                                added_idxs.discard(switch.on_trigger_idx)
                                added_idxs.discard(switch.off_trigger_idx)

                        if added_idxs:
                            await self.logger.info(
                                f"[Domoticz] Config reload detected {len(added_idxs)} new devices. Querying delta status...")
                            for new_idx in added_idxs:
                                if new_idx < 10000:
                                    command_payload = {
                                        "command": "getdeviceinfo",
                                        "idx": new_idx
                                    }
                                    await self.mqtt_client.publish(self._out_topic, command_payload)
                                    await asyncio.sleep(0.05)

            # Iterate purely over integer IDXs directly mapped in state.devices
            for idx, current_state in state.devices.items():
                # Only publish to real Domoticz IDXs (ignore local 10000+ virtuals)
                if isinstance(idx, int) and idx < 10000:
                    is_force = idx in forced_devices
                    is_init = idx in initialized_devices

                    # ⚡ Fire if state changed OR if a force flag was passed!
                    if current_state is not None and (
                            current_state != self._last_known_states.get(idx) or is_force):

                        # ⚡ 100% DETERMINISTIC INITIALIZATION GUARD ⚡
                        # If the core engine tagged this as its very first contact with this device (value went from None to string),
                        # we silently align our circuit-breaker cache and abort the outbound transmission.
                        # This natively absorbs boot storms and reconnect echoes without any arbitrary timers.
                        if is_init:
                            self._last_known_states[idx] = current_state
                            continue

                        # ⚡ HUB GUARD: Do not publish if network is down
                        if not getattr(self.mqtt_client, 'is_connected', False):
                            continue

                        # Check if this state update targets a decoupled virtual RFX switch item
                        rfx_match = None
                        if hasattr(self.state_manager._config, "rfx_switches"):
                            rfx_match = next(
                                (s for s in self.state_manager._config.rfx_switches if s.virtual_idx == idx), None)

                        if rfx_match:
                            rfx_origin = rfx_origins.get(idx)

                            if rfx_origin is not None:
                                # Origin: Physical Remote. Sync the UI visual state only.
                                domoticz_command_ui = {
                                    "command": "switchlight",
                                    "idx": idx,
                                    "switchcmd": "On" if current_state == "ON" else "Off"
                                }
                                await self.mqtt_client.publish(self._out_topic, domoticz_command_ui)
                                await self.logger.info(
                                    f"[Domoticz] UI Sync Sent: Virtual IDX {idx} -> {domoticz_command_ui['switchcmd']} (Physical origin: {rfx_origin})")
                            else:
                                # Origin: UI or Internal Automation. DUAL BLAST.
                                target_trigger_idx: int = rfx_match.on_trigger_idx if current_state == "ON" else rfx_match.off_trigger_idx

                                # 1. Physical blast
                                domoticz_command_physical = {
                                    "command": "switchlight",
                                    "idx": target_trigger_idx,
                                    "switchcmd": "On"
                                    # 433MHz trigger entities require an ON pulse execution command
                                }
                                await self.mqtt_client.publish(self._out_topic, domoticz_command_physical)

                                # 2. UI blast
                                domoticz_command_ui = {
                                    "command": "switchlight",
                                    "idx": idx,
                                    "switchcmd": "On" if current_state == "ON" else "Off"
                                }
                                await self.mqtt_client.publish(self._out_topic, domoticz_command_ui)

                                await self.logger.info(
                                    f"[Domoticz] Dual Blast Sent: Physical IDX {target_trigger_idx} -> On & Virtual IDX {idx} -> {domoticz_command_ui['switchcmd']}")
                        else:
                            domoticz_command = {
                                "command": "switchlight",
                                "idx": idx,
                                "switchcmd": "On" if current_state == "ON" else "Off"
                            }
                            await self.mqtt_client.publish(self._out_topic, domoticz_command)

                            if is_force:
                                await self.logger.warning(
                                    f"⚡ [FORCED OVERRIDE] Command Sent: Target IDX {idx} -> {domoticz_command['switchcmd']}")
                            else:
                                await self.logger.info(
                                    f"[Domoticz] Command Sent: Target IDX {idx} -> {domoticz_command['switchcmd']}")

                        self._last_known_states[idx] = current_state
        except Exception as e:
            await self.logger.error(f"Error processing outbound Domoticz commands: {e}")