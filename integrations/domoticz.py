# --- file: integrations/domoticz.py ---
import asyncio
import json
import aiohttp
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

        # Debounce properties to filter out rapid signal bouncing
        self._debounce_tasks: dict[int, asyncio.Task] = {}
        self._debounce_delay: float = 0.3  # 300ms waiting room

        # Core track loop tracking variable to evaluate config reload deltas
        self._tracked_whitelist: set[int] = set()

        # Dynamic Favorites Memory: Stores IDXs discovered during the HTTP boot-sync
        self._dynamic_favorites_idxs: set[int] = set()

        # Read-Only Sensor Guard: Tracks IDXs that should never receive outbound MQTT commands
        self._read_only_idxs: set[int] = set()

    @property
    def watched_idxs(self) -> set[int]:
        """Dynamically builds a comprehensive whitelist by scanning the dashboard, managed lights, and automations."""
        idxs = set()

        # 1. Grab UI Dashboard IDXs
        if hasattr(self.state_manager._config, "dashboard"):
            for idx in self.state_manager._config.dashboard.keys():
                if isinstance(idx, int) and idx < 10000:
                    idxs.add(idx)

        # 2. Grab Managed Lights IDXs
        if hasattr(self.state_manager._config, "lighting") and self.state_manager._config.lighting.managed_lights:
            for idx in self.state_manager._config.lighting.managed_lights:
                if isinstance(idx, int) and idx < 10000:
                    idxs.add(idx)

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

        # Seamlessly merge dynamically discovered HTTP favorites into the live MQTT whitelist
        idxs.update(self._dynamic_favorites_idxs)
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
            asyncio.create_task(self._fetch_initial_states_http())

        await self.logger.success("[Domoticz] HomeHub Bridge initialized (Pure MQTT IDX Mode + HTTP Sync).")

    async def stop(self) -> None:
        await self.logger.warning("[Domoticz] HomeHub Bridge stopped.")

    async def _fetch_initial_states_http(self) -> None:
        """Fetches all favorite devices in a single atomic JSON burst using the legacy API."""
        try:
            dom_http = self.state_manager._config.domoticz.http
        except AttributeError:
            await self.logger.error("[Domoticz] HTTP configuration missing in config.yaml! Aborting boot-sync.")
            return

        host = dom_http.host
        port = dom_http.port
        user = dom_http.username
        pwd = dom_http.password

        # PRE-2023 LEGACY ENDPOINT
        # Using type=devices ensures compatibility with older Domoticz C++ engines. (pre-2023) :: Smartastic
        url = f"http://{host}:{port}/json.htm?type=devices&filter=all&used=true"
        auth = aiohttp.BasicAuth(user, pwd) if user and pwd else None

        await self.logger.info("[Domoticz] Initiating atomic HTTP boot-sync via legacy API...")

        try:
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.get(url, timeout=15.0) as response:
                    if response.status != 200:
                        await self.logger.error(f"[Domoticz] HTTP sync failed with status {response.status}")
                        return

                    data = await response.json()

                    if data.get("status") == "ERR":
                        await self.logger.error("[Domoticz] HTTP API returned ERR. Ensure credentials are correct.")
                        return

                    results = data.get("result", [])
                    await self.logger.success(
                        f"[Domoticz] HTTP sync complete. Discovered {len(results)} favorite devices.")

                    for device in results:
                        self._normalize_http_device(device)

        except asyncio.TimeoutError:
            # asyncio.TimeoutError renders as an empty string by default. This explicit catch
            # translates it into a human-readable diagnosis of the network blockage.
            await self.logger.error(
                "[Domoticz] HTTP sync exception: Connection timed out (15s). Is Domoticz offline or unreachable?")
        except aiohttp.ClientError as e:
            await self.logger.error(f"[Domoticz] HTTP sync exception: Network/Client error occurred: {repr(e)}")
        except Exception as e:
            # Fallback using repr(e) to guarantee the exact Python Class name is always printed,
            # preventing invisible ghost-errors.
            await self.logger.error(f"[Domoticz] HTTP sync exception: {repr(e)}")

    def _normalize_http_device(self, device: dict[str, Any]) -> None:
        """Translates Domoticz HTTP JSON formats into unified WanOS events."""
        try:
            idx_str = device.get("idx")
            if not idx_str:
                return
            idx = int(idx_str)

            # RESOLVE DASHBOARD SCOPE: Re-extract config_name at the top of the block
            # to safely clear the NameError thrown by the normalization pipeline.
            config_name = self.state_manager._config.dashboard.get(idx)
            is_favorite = device.get("Favorite", 0) == 1

            # COMPREHENSIVE SYNC GATE: Only process devices starred in Domoticz OR explicitly monitored anywhere in config.yaml
            if not is_favorite and idx not in self.watched_idxs:
                return

            # Dynamically register this so the MQTT listener watches it permanently
            self._dynamic_favorites_idxs.add(idx)

            # Prioritize config.yaml mapped names. Explicitly reject Domoticz "Unknown" default labels.
            dom_name = device.get("Name")
            if dom_name and dom_name.lower() == "unknown":
                dom_name = None
            name = config_name or dom_name or f"idx_{idx}"

            device_type = device.get("Type", "")
            switch_type = device.get("SwitchType", "")

            # 1. Blinds / Roller Shutters (Percentage)
            if switch_type == "Blinds Percentage":
                # HTTP JSON uses 'LevelInt' for the blind percentage integer
                level = device.get("LevelInt", 0)
                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"idx": idx, "state": level, "name": name, "device_type": "blinds", "origin": "domoticz",
                             "is_push_button": False,
                             "rfx_origin": None,
                             "is_initialization": True}
                ))

            # 2. Standard Switches / Relays
            elif device_type in ["Light/Switch", "Lighting 2", "Lighting 1"]:
                status = device.get("Status", "Off")
                is_push_button = switch_type.startswith("Push")
                state_str = "ON" if status.lower() == "on" else "OFF"

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"idx": idx, "state": state_str, "name": name, "device_type": "switch",
                             "origin": "domoticz",
                             "is_push_button": is_push_button,
                             "rfx_origin": None, "is_initialization": True}
                ))

            # 3. Temp / HumidityZ
            elif "Temp" in device_type or "Hum" in device_type:
                self._read_only_idxs.add(idx)  # Lock sensor to prevent outbound commands
                temp = device.get("Temp")
                hum = device.get("Humidity")

                # Detect if this is a single sensor or a compound Temp+Hum sensor
                dtype_tag = "temp_hum" if (temp is not None and hum is not None) else (
                    "temp" if temp is not None else "hum")

                if temp is not None:
                    self.state_manager.dispatch(Event(
                        type=EventType.TEMP_UPDATED,
                        payload={"idx": idx, "value": float(temp), "name": name, "device_type": dtype_tag,
                                 "origin": "domoticz",
                                 "is_initialization": True}
                    ))
                if hum is not None:
                    self.state_manager.dispatch(Event(
                        type=EventType.HUMIDITY_UPDATED,
                        payload={"idx": idx, "value": int(hum), "name": name, "device_type": dtype_tag,
                                 "origin": "domoticz",
                                 "is_initialization": True}
                    ))

            # 4. Power / Wattage Sensors
            elif "Usage" in device_type or "Watt" in device_type or "Power" in device_type or "Kwh" in switch_type:
                self._read_only_idxs.add(idx)  # Lock sensor to prevent outbound commands
                try:
                    # Domoticz HTTP API typically returns power in the 'Usage' or 'Data' fields as a string like "0.0 Watt"
                    raw_power = str(device.get("Usage", device.get("Data", "0.0")))

                    # Clean out alphabetical characters (like ' Watt' or ' W') to parse the pure float
                    clean_power = ''.join(c for c in raw_power if c.isdigit() or c == '.' or c == '-')
                    if not clean_power or clean_power == "." or clean_power == "-":
                        clean_power = "0.0"

                    self.state_manager.dispatch(Event(
                        type=EventType.POWER_UPDATED,
                        payload={"idx": idx, "value": float(clean_power), "name": name, "device_type": "power",
                                 "origin": "domoticz", "is_initialization": True}
                    ))
                except Exception as e:
                    asyncio.create_task(
                        self.logger.error(f"[Domoticz] Power normalization failed for IDX {idx}: {e}"))

        except Exception as e:
            asyncio.create_task(self.logger.error(f"[Domoticz] Normalization failed for device: {e}"))

    async def _parse_domoticz_inbound(self, topic: str, payload: str) -> None:
        # Master Lockout: Silently drop all incoming Domoticz messages if integration is disabled in the UI
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

            # Prioritize config.yaml mapped names. Explicitly reject Domoticz "Unknown" default labels.
            config_name = self.state_manager._config.dashboard.get(idx)
            dom_name = data.get("name")
            if dom_name and dom_name.lower() == "unknown":
                dom_name = None
            device_name = config_name or dom_name or f"idx_{idx}"

            # EARLY GATE DUPLICATE FILTER
            nvalue = data.get("nvalue")
            svalue1 = data.get("svalue1")
            svalue2 = data.get("svalue2")
            svalue = data.get("svalue")

            cache_state = {"nvalue": nvalue, "svalue1": svalue1, "svalue2": svalue2, "svalue": svalue}

            # PUSH BUTTON BYPASS: Momentary buttons send the exact same payload every time.
            # We MUST bypass the cache filter for these, otherwise only the first press works!
            switch_type = data.get("switchType", "")
            is_push_button = switch_type.split(" ")[0] == "Push"

            if not is_push_button and self._raw_cache.get(idx) == cache_state:
                return  # Exact duplicate value. Silently drop to prevent engine noise.

            self._raw_cache[idx] = cache_state

            # Forward raw data to internal bus
            filtered_raw_data = {
                "idx": idx,
                "name": device_name,
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
                self._read_only_idxs.add(idx)  # Lock sensor to prevent outbound commands
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

                has_temp = raw_temp is not None and raw_temp != ""
                has_hum = raw_hum is not None and raw_hum != ""
                dtype_tag = "temp_hum" if (has_temp and has_hum) else ("temp" if has_temp else "hum")

                log_parts = []
                if has_temp:
                    log_parts.append(f"{raw_temp}°C")
                    self.state_manager.dispatch(Event(
                        type=EventType.TEMP_UPDATED,
                        payload={"idx": idx, "value": float(raw_temp), "device_type": dtype_tag, "origin": "domoticz",
                                 "name": device_name}
                    ))
                if has_hum:
                    log_parts.append(f"{raw_hum}%")
                    self.state_manager.dispatch(Event(
                        type=EventType.HUMIDITY_UPDATED,
                        payload={"idx": idx, "value": int(float(raw_hum)), "device_type": dtype_tag,
                                 "origin": "domoticz",
                                 "name": device_name}
                    ))
                log_display = " / ".join(log_parts) if log_parts else "No Data"

                # 2. Power Sensors
            elif "Usage" in dtype or "Watt" in dtype or "Power" in dtype:
                self._read_only_idxs.add(idx)  # Lock sensor to prevent outbound commands
                try:
                    raw_svalue = data.get("svalue1", "0.0")
                    wattage = float(raw_svalue)
                    # log_display = f"{wattage} W"
                    log_display = ""  # don't log power (too much noise)
                    self.state_manager.dispatch(Event(
                        type=EventType.POWER_UPDATED,
                        payload={"idx": idx, "value": wattage, "device_type": "power", "origin": "domoticz",
                                 "name": device_name}
                    ))
                except (ValueError, TypeError) as e:
                    await self.logger.error(f"Failed to parse power reading for IDX {idx}: {e}")

                # 3. Switches, Relays, and Blinds
            else:
                if switch_type == "Blinds Percentage":
                    try:
                        # MQTT payload for blinds uses svalue1 for the percentage
                        target_state = int(data.get("svalue1", 0))
                    except ValueError:
                        target_state = 0
                    log_display = f"{target_state}%"
                    dtype_tag = "blinds"
                else:
                    nvalue = data.get("nvalue", 0)
                    target_state = "ON" if nvalue > 0 else "OFF"
                    log_display = target_state
                    dtype_tag = "switch"

                if not is_push_button and self._last_known_states.get(idx) == target_state:
                    return

                self._last_known_states[idx] = target_state

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={
                        "idx": idx,
                        "state": target_state,
                        "name": data.get("name"),  # for hybrid dashboard map learning
                        "device_type": dtype_tag,
                        "origin": "domoticz",
                        "is_push_button": is_push_button,
                        "rfx_origin": None  # Tag as UI/Internal origin
                    }
                ))
            if log_display:
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
                # CACHE PURGE: Wipe the internal bridge memory so the incoming sync echoes aren't silently dropped!
                # This forces the bridge to pass the data to the Engine, triggering a clean is_initialization boot sequence.
                self._raw_cache.clear()
                self._last_known_states.clear()
                await self.logger.info("[Domoticz] Initiating network sync...")
                asyncio.create_task(self._fetch_initial_states_http())
            elif not current_enabled and getattr(self, '_integration_enabled', False):
                self._integration_enabled = False
                await self.logger.info("[Domoticz] Integration DISABLED via UI.")

            if not current_enabled:
                return

            forced_devices = set()
            initialized_devices = set()
            rfx_origins: dict[int, Any] = {}
            idxs_to_check: set[int] = set()
            is_full_sweep: bool = False

            if events:
                for event in events:
                    # Safely grab payload, defaulting to empty dict for events that don't have one
                    payload = event.payload or {}

                    # UNIVERSAL FLAG EXTRACTION
                    # Extract initialization tags across ALL event types (Temp, Hum, Power, Hub State)
                    if payload.get("is_initialization") and payload.get("idx") is not None:
                        initialized_devices.add(payload.get("idx"))

                    if event.type in [EventType.HUB_STATE_CHANGED, EventType.LIGHTING_STATE_CHANGED]:
                        if payload.get("force") and payload.get("idx") is not None:
                            forced_devices.add(payload.get("idx"))
                        if "rfx_origin" in payload and payload.get("rfx_origin") is not None:
                            rfx_origins[payload.get("idx")] = payload.get("rfx_origin")
                        if payload.get("idx") is not None:
                            idxs_to_check.add(payload.get("idx"))
                    elif event.type in [EventType.SYSTEM_SWEEP_REQUESTED, EventType.CONFIG_RELOAD_REQUESTED]:
                        is_full_sweep = True

                    if event.type == EventType.CONFIG_RELOAD_REQUESTED:
                        # Delta verification evaluation loop for dynamic inclusions/exclusions
                        new_whitelist = self.watched_idxs
                        added_idxs = new_whitelist - self._tracked_whitelist
                        removed_idxs = self._tracked_whitelist - new_whitelist
                        self._tracked_whitelist = new_whitelist

                        if removed_idxs:
                            await self.logger.info(
                                f"[Domoticz] Config reload pruned {len(removed_idxs)} devices from active listening channels.")

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

            # STRICT EVENT-DRIVEN ROUTING GUARD
            # If a full sweep macro runs, parse all physical hardware targets. Otherwise, exclusively
            # evaluate the explicit device indices mutated in this event transaction. This isolates
            # background metrics/telemetry ticks (SYSTEM_METRICS_UPDATED) and drops un-synced queue floods entirely.
            if is_full_sweep:
                idxs_to_check = {idx for idx in state.devices.keys() if isinstance(idx, int) and idx < 10000}

            if not idxs_to_check:
                return

            # Iterate purely over integer IDXs targeted by active events
            for idx in idxs_to_check:
                current_state = state.devices.get(idx)

                # READ-ONLY SENSOR GUARD
                # Do not attempt to evaluate or transmit state changes for thermometers, humidity sensors or power meters!
                if idx in self._read_only_idxs:
                    continue

                # Only publish to real Domoticz IDXs (ignore local 10000+ virtuals)
                if isinstance(idx, int) and idx < 10000:
                    is_force = idx in forced_devices
                    is_init = idx in initialized_devices

                    # Fire if state changed OR if a force flag was passed!
                    if current_state is not None and (
                            current_state != self._last_known_states.get(idx) or is_force):

                        # 100% DETERMINISTIC INITIALIZATION GUARD
                        # If the core engine tagged this as its very first contact with this device (value went from None to string),
                        # we silently align our circuit-breaker cache and abort the outbound transmission.
                        # This natively absorbs boot storms and reconnect echoes without any arbitrary timers.
                        if is_init:
                            self._last_known_states[idx] = current_state
                            continue

                        # HUB GUARD: Do not publish if network is down
                        if not getattr(self.mqtt_client, 'is_connected', False):
                            continue

                        # OUTBOUND SAFETY GUARD
                        # If the UI sends an integer, it is controlling a blind. We dynamically swap to "Set Level".
                        if isinstance(current_state, int):
                            domoticz_command = {
                                "command": "switchlight",
                                "idx": idx,
                                "switchcmd": "Set Level",
                                "level": current_state
                            }
                        else:
                            domoticz_command = {
                                "command": "switchlight",
                                "idx": idx,
                                "switchcmd": "On" if current_state == "ON" else "Off"
                            }
                        await self.mqtt_client.publish(self._out_topic, domoticz_command)

                        if is_force:
                            await self.logger.warning(
                                f"[FORCED OVERRIDE] Command Sent: Target IDX {idx} -> {domoticz_command['switchcmd']}")
                        else:
                            await self.logger.info(
                                f"[Domoticz] Command Sent: Target IDX {idx} -> {domoticz_command['switchcmd']}")

                        self._last_known_states[idx] = current_state
        except Exception as e:
            await self.logger.error(f"Error processing outbound Domoticz commands: {e}")