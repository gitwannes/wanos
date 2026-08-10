# --- file: integrations/hue.py ---
import asyncio
import json
import os
import ssl
from typing import Any, Dict, List, Optional
import aiohttp
from loguru import logger

from core.models import Event, EventType, SystemState, device_name, format_device_ref
from core.event_catalog import legacy_key_for_bus_token
from core.state_manager import StateManager
from core.config import AppConfig


class HueLocalBridge:
    """
    Philips Hue Local API v2 Integration.
    Establishes a continuous, bi-directional local connection to the Hue Bridge.
    - Outbound: Asynchronous HTTP PUT requests for zero-latency control.
    - Inbound: Persistent Server-Sent Events (SSE) stream for instant hardware telemetry.
    """

    def __init__(self, state_manager: StateManager, config: AppConfig) -> None:
        self.state_manager: StateManager = state_manager
        self._config: AppConfig = config

        # Security: The Hue API token should ideally live in .env, but can fallback to config.yaml
        self.bridge_ip: Optional[str] = getattr(config.hue, "bridge_ip", None)
        self.api_key: Optional[str] = getattr(config.hue, "application_key", None) or os.getenv("HUE_API_KEY")

        self.is_connected: bool = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._sse_task: Optional[asyncio.Task[None]] = None
        self._stop_event: asyncio.Event = asyncio.Event()

        # Dictionaries for O(1) bi-directional translations
        self.idx_to_uuid: Dict[int, str] = {}
        self.uuid_to_idx: Dict[str, int] = {}
        self.idx_to_group_uuid: Dict[int, str] = {}
        self.group_uuid_to_idx: Dict[str, int] = {}
        # ⚡ Nested Scene Map: { WanOS_Room_IDX: { "clean_scene_name": "Scene_UUID" } }
        self.room_scenes: Dict[int, Dict[str, str]] = {}

        self._initialize_mappings()

    def _initialize_mappings(self) -> None:
        """Parses the configuration to build fast in-memory translation maps."""
        hue_conf = getattr(self._config, "hue", None)
        if not hue_conf:
            return

        # Clear existing maps to prevent translation state contamination on configuration reloads
        self.idx_to_uuid.clear()
        self.uuid_to_idx.clear()
        self.idx_to_group_uuid.clear()
        self.group_uuid_to_idx.clear()
        self.room_scenes.clear()

        device_map: Dict[Any, Any] = getattr(hue_conf, "device_map", {}) or {}
        for idx_str, raw_val in device_map.items():
            try:
                idx = int(idx_str)
                # Safely peel Pydantic SecretStr proxy wrappers to reveal the true UUID
                val_str = raw_val.get_secret_value() if hasattr(raw_val, "get_secret_value") else str(raw_val)
                clean_uuid = val_str.split("|")[0].strip() if "|" in val_str else val_str.strip()
                self.idx_to_uuid[idx] = clean_uuid
                self.uuid_to_idx[clean_uuid] = idx
            except Exception:
                logger.error(f"[HUE] Invalid configuration in device_map for IDX: {idx_str}")

        group_map: Dict[Any, Any] = getattr(hue_conf, "group_map", {}) or {}
        for idx_str, raw_val in group_map.items():
            try:
                idx = int(idx_str)
                # Safely peel Pydantic SecretStr proxy wrappers to reveal the true UUID
                val_str = raw_val.get_secret_value() if hasattr(raw_val, "get_secret_value") else str(raw_val)
                clean_uuid = val_str.split("|")[0].strip() if "|" in val_str else val_str.strip()
                self.idx_to_group_uuid[idx] = clean_uuid
                self.group_uuid_to_idx[clean_uuid] = idx
            except Exception:
                logger.error(f"[HUE] Invalid configuration in group_map for IDX: {idx_str}")

        # The room_scenes dict is left intentionally blank here. It will be dynamically populated
        # from the physical Hue Bridge during the _sync_initial_state() boot routine.
        logger.info(
            f"[HUE] Mapped {len(self.idx_to_uuid)} lights and {len(self.idx_to_group_uuid)} groups from configuration."
        )

    async def start(self) -> None:
        """Initializes the network session and background listener tasks."""
        if not self.bridge_ip or not self.api_key:
            logger.error("🔴 [HUE] Missing bridge_ip or application_key in config/env. Integration disabled.")
            return

        if "X" in str(self.bridge_ip):
            logger.error(
                "🔴 [HUE] Configuration Safeguard: bridge_ip still contains placeholder 'X' character. Fix config.yaml IP target.")
            return

        # Hue API local bridges use self-signed certificates. We must explicitly bypass SSL validation.
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(connector=connector)

        # Reset the stop event flag to allow background listener tasks to run during a reload cycle
        self._stop_event.clear()

        # Wire into the central WanOS event bus to listen for outbound commands if not already subscribed
        if self._on_state_changed not in self.state_manager._state_listeners:
            self.state_manager.register_listener(self._on_state_changed)

        # INITIATE FULL BOOT SYNC: Grab all names, colors, and states before starting the live stream
        await self._sync_initial_state()

        # Start the continuous background listener for inbound physical switch events
        self._sse_task = asyncio.create_task(self._sse_listener_loop())
        logger.info(f"[HUE] Integration bridging established targeting {self.bridge_ip}")

    async def stop(self) -> None:
        """Safely tears down open sockets and network streams."""
        self._stop_event.set()
        if self._sse_task:
            self._sse_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
        self.is_connected = False
        logger.warning("🟠 [HUE] Network bridge torn down.")

    async def _sync_initial_state(self) -> None:
        """
        Performs one-time REST GET requests on boot to dynamically learn the ecosystem.
        - Fetches Rooms & Zones to map scene context and bridge grouped_light name references.
        - Fetches Scenes to build the automation string keys dynamically.
        - Fetches Lights and Grouped Lights to instantly populate the UI with native names and current states.
        """
        if not self._session:
            return

        headers = {"hue-application-key": self.api_key}

        try:
            # =========================================================================
            # 1. 🌍 DYNAMIC SCENE & ROOM CROSS-REFERENCE EXTRACTION
            # =========================================================================
            # Fetch Rooms and Zones to map scene contexts and build group name lookup tables
            group_names: Dict[str, str] = {}
            grouped_light_to_name: Dict[str, str] = {}
            room_uuid_to_idx: Dict[str, int] = {}  # ⚡ Temporary mapping to link Room UUIDs to WanOS IDXs

            for endpoint in ["room", "zone"]:
                url = f"https://{self.bridge_ip}/clip/v2/resource/{endpoint}"
                async with self._session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("data", []):
                            room_uuid = item["id"]
                            g_name = item.get("metadata", {}).get("name", "unknown")
                            group_names[room_uuid] = g_name

                            # ⚡ Check if this specific Room UUID was mapped in config_hue.yaml
                            mapped_idx = self.group_uuid_to_idx.get(room_uuid)

                            # Crawl internal services to map the anonymous grouped_light reference
                            for service in item.get("services", []):
                                if service.get("rtype") == "grouped_light":
                                    gl_id = service.get("rid")
                                    grouped_light_to_name[gl_id] = f"{g_name.removesuffix('-rm')}"

                                    if mapped_idx:
                                        room_uuid_to_idx[room_uuid] = mapped_idx
                                        # ⚡ DYNAMIC UUID BRIDGING:
                                        # The Hue App gives users the Room UUID, but live telemetry uses the Grouped Light UUID.
                                        # We instantly inject the hidden gl_id into our translation maps so telemetry routes flawlessly!
                                        self.group_uuid_to_idx[gl_id] = mapped_idx
                                        self.idx_to_group_uuid[mapped_idx] = gl_id

            # Fetch all native Scenes
            url = f"https://{self.bridge_ip}/clip/v2/resource/scene"
            async with self._session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.room_scenes.clear()
                    scene_count = 0

                    for scene in data.get("data", []):
                        scene_uuid = scene.get("id")
                        scene_name = scene.get("metadata", {}).get("name", "unknown")
                        group_id = scene.get("group", {}).get("rid")

                        # ⚡ Look up the WanOS IDX assigned to this specific room/zone
                        idx = room_uuid_to_idx.get(group_id)
                        if not idx:
                            continue  # If the room isn't mapped in config_hue.yaml, we don't load its scenes

                        # Generate a clean, predictable string key for safe dictionary lookup
                        clean_name = "".join(c for c in scene_name.lower().replace(" ", "_").replace("-", "_") if
                                             c.isalnum() or c == "_")

                        if idx not in self.room_scenes:
                            self.room_scenes[idx] = {}

                        self.room_scenes[idx][clean_name] = scene_uuid
                        scene_count += 1

                    logger.success(
                        f"[HUE] Dynamically extracted and mapped {scene_count} native scenes to configured IDXs.")

            # =========================================================================
            # 2. 💡 DYNAMIC LIGHT & ROOM/ZONE GROUP EXTRACTION
            # =========================================================================
            for endpoint in ["light", "grouped_light"]:
                url = f"https://{self.bridge_ip}/clip/v2/resource/{endpoint}"
                async with self._session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        response_json = await resp.json()

                        for resource in response_json.get("data", []):
                            uuid = resource.get("id")
                            idx = self.uuid_to_idx.get(uuid) if endpoint == "light" else self.group_uuid_to_idx.get(
                                uuid)
                            if not idx:
                                continue

                            # Resolve Name: Lights provide it directly, Groups pull from cross-reference map
                            if endpoint == "light":
                                native_name = resource.get("metadata", {}).get("name")
                                default_name = native_name if native_name else f"Hue Light {idx}"
                            else:
                                default_name = grouped_light_to_name.get(uuid, f"Hue Group {idx}")

                            # ⚡ Resolve the UI name by checking the global state manager map,
                            # ensuring we don't try to access the old deprecated config.dashboard block.
                            name = device_name(self.state_manager._state, idx, default_name)

                            # Push resolved names into device_metadata to maintain UI parity
                            if idx in self.state_manager._state.device_metadata:
                                self.state_manager._state.device_metadata[idx]["name"] = name
                            else:
                                self.state_manager._state.device_metadata[idx] = {
                                    "name": name, "type": "light", "origin": "hue",
                                }

                            # Construct the rich payload for the StateManager
                            # Both individual bulbs and rooms get "light" device_type so the UI gives them the rich glowing orb (Option B)
                            payload: Dict[str, Any] = {
                                "idx": idx,
                                "origin": "hue",
                                "device_type": "light",
                                "name": name,
                                "is_initialization": True
                            }

                            if "on" in resource and "on" in resource["on"]:
                                payload["state"] = "ON" if resource["on"]["on"] else "OFF"

                            if "dimming" in resource and "brightness" in resource["dimming"]:
                                payload["bri"] = resource["dimming"]["brightness"]

                            if "color" in resource and "xy" in resource["color"]:
                                payload["xy"] = [
                                    resource["color"]["xy"].get("x"),
                                    resource["color"]["xy"].get("y")
                                ]

                            # Dispatch directly to WanOS to update states
                            self.state_manager.dispatch(Event(
                                type=EventType.HUB_STATE_CHANGED,
                                payload=payload
                            ))
                        logger.success(
                            f"[HUE] Initial sync complete for endpoint '{endpoint}'. Native names and statuses downloaded.")
                    else:
                        logger.error(
                            f"🔴 [HUE] Failed to fetch initial names for endpoint '{endpoint}'. HTTP {resp.status}")
        except Exception as e:
            logger.error(f"🔴 [HUE] Network error during initial sync: {e}")

    def _is_integration_enabled(self) -> bool:
        """Checks the central SystemState to respect UI Admin Panel master toggles."""
        snapshot = self.state_manager.get_state_snapshot()
        return snapshot.system.hue_integration_enabled

    async def _on_state_changed(self, snapshot: SystemState, batch_events: List[Event]) -> None:
        """
        Subscribed callback triggered by the StateManager after queue drain.
        Filters for HUB_STATE_CHANGED targeting our mapped IDXs or Scenes.
        """
        # Respect the UI Master Kill Switch
        if not self._is_integration_enabled():
            return

        for event in batch_events:
            # B10B: catalog events arrive as UUID bus tokens; compare via legacy key.
            if legacy_key_for_bus_token(event.type) != "HUB_STATE_CHANGED":
                continue

            payload = event.payload
            origin = payload.get("origin")

            # 🛡️ Infinite Loop Guard: Ignore state changes that WE injected from the SSE stream!
            if origin == "hue":
                continue

            # Scenario A: Native Hue Scene Trigger
            # Fired by config.yaml actions using `target: "hue_scene"`
            target = payload.get("target")
            if target == "hue_scene":
                scene_name = payload.get("scene")
                idx = payload.get("idx")
                if scene_name and idx is not None:
                    await self._send_scene_command(idx, scene_name)
                continue

            # Scenario B: Direct Light Command (State, Brightness, Color)
            idx = payload.get("idx")
            if idx in self.idx_to_uuid:
                await self._send_light_command(idx, payload)

            # Scenario C: Group Command (Rooms and Zones)
            elif idx in self.idx_to_group_uuid:
                await self._send_group_command(idx, payload)

    async def _send_light_command(self, idx: int, payload: Dict[str, Any]) -> None:
        """Translates WanOS abstract rich payloads into Hue API v2 JSON format for individual bulbs."""
        uuid = self.idx_to_uuid.get(idx)
        if not uuid or not self._session:
            return

        state_val = payload.get("state")
        bri = payload.get("bri")
        xy = payload.get("xy")

        hue_payload: Dict[str, Any] = {}

        if state_val == "ON":
            hue_payload["on"] = {"on": True}
        elif state_val == "OFF":
            hue_payload["on"] = {"on": False}

        if bri is not None:
            # Hue V2 expects a float brightness percentage (0.0 to 100.0)
            # Clamp safeguard natively catches legacy v1 'bri: 254' from YAML to prevent 400 Bad Requests
            clamped_bri = min(100.0, max(0.0, float(bri)))
            hue_payload["dimming"] = {"brightness": clamped_bri}

        if xy is not None and isinstance(xy, list) and len(xy) == 2:
            # Hue V2 expects explicit x and y nested attributes
            hue_payload["color"] = {"xy": {"x": float(xy[0]), "y": float(xy[1])}}

        if not hue_payload:
            return  # No actionable light data in payload

        url = f"https://{self.bridge_ip}/clip/v2/resource/light/{uuid}"
        headers = {"hue-application-key": self.api_key}

        try:
            async with self._session.put(url, headers=headers, json=hue_payload) as resp:
                if resp.status not in (200, 207):
                    err_text = await resp.text()
                    logger.error(
                        f"🔴 [HUE] API Error {resp.status} for light "
                        f"{format_device_ref(self.state_manager._state, idx)}: {err_text}")
        except Exception as e:
            logger.error(f"🔴 [HUE] Communication failure on light command: {e}")
            self.is_connected = False

    async def _send_group_command(self, idx: int, payload: Dict[str, Any]) -> None:
        """Translates WanOS abstract rich payloads into Hue API v2 JSON format for Rooms/Zones."""
        uuid = self.idx_to_group_uuid.get(idx)
        if not uuid or not self._session:
            return

        state_val = payload.get("state")
        bri = payload.get("bri")
        xy = payload.get("xy")

        hue_payload: Dict[str, Any] = {}

        if state_val == "ON":
            hue_payload["on"] = {"on": True}
        elif state_val == "OFF":
            hue_payload["on"] = {"on": False}

        if bri is not None:
            # Clamp safeguard natively catches legacy v1 'bri: 254' from YAML
            clamped_bri = min(100.0, max(0.0, float(bri)))
            hue_payload["dimming"] = {"brightness": clamped_bri}

        if xy is not None and isinstance(xy, list) and len(xy) == 2:
            hue_payload["color"] = {"xy": {"x": float(xy[0]), "y": float(xy[1])}}

        if not hue_payload:
            return  # No actionable data

        url = f"https://{self.bridge_ip}/clip/v2/resource/grouped_light/{uuid}"
        headers = {"hue-application-key": self.api_key}

        try:
            async with self._session.put(url, headers=headers, json=hue_payload) as resp:
                if resp.status not in (200, 207):
                    err_text = await resp.text()
                    logger.error(
                        f"🔴 [HUE] API Error {resp.status} for group "
                        f"{format_device_ref(self.state_manager._state, idx)}: {err_text}")
        except Exception as e:
            logger.error(f"🔴 [HUE] Communication failure on group command: {e}")
            self.is_connected = False

    async def _send_scene_command(self, idx: int, scene_name: str) -> None:
        """Triggers a perfectly synchronized native Zigbee multicast scene."""
        clean_name = "".join(
            c for c in scene_name.lower().replace(" ", "_").replace("-", "_") if c.isalnum() or c == "_")
        uuid = self.room_scenes.get(idx, {}).get(clean_name)

        if not uuid or not self._session:
            logger.warning(
                f"🟠 [HUE] Scene '{scene_name}' "
                f"({format_device_ref(self.state_manager._state, idx)}) triggered but not found in mapped room scenes!"
            )
            return

        # V2 API requires sending the 'active' recall action to the scene resource UUID
        hue_payload = {"recall": {"action": "active"}}
        url = f"https://{self.bridge_ip}/clip/v2/resource/scene/{uuid}"
        headers = {"hue-application-key": self.api_key}

        try:
            async with self._session.put(url, headers=headers, json=hue_payload) as resp:
                if resp.status not in (200, 207):
                    logger.error(f"🔴 [HUE] API Error {resp.status} for scene '{scene_name}'")
                else:
                    logger.info(
                        f"🎬 [HUE] Multicast Scene triggered natively: {scene_name} "
                        f"({format_device_ref(self.state_manager._state, idx)})"
                    )
        except Exception as e:
            logger.error(f"🔴 [HUE] Communication failure on scene command: {e}")
            self.is_connected = False

    async def _sse_listener_loop(self) -> None:
        """
        Maintains a persistent HTTP/2 Server-Sent Events stream.
        This provides instant, zero-latency feedback if someone uses the Hue app
        or presses a physical Zigbee wall switch.
        """
        url = f"https://{self.bridge_ip}/eventstream/clip/v2"
        headers = {
            "hue-application-key": self.api_key,
            "Accept": "text/event-stream"
        }

        # Backoff timer prevents aggressive slamming if the bridge reboots
        retry_backoff = 2

        while not self._stop_event.is_set():
            if not self._session:
                await asyncio.sleep(1)
                continue

            try:
                # timeout=None ensures the socket stays open forever
                async with self._session.get(url, headers=headers, timeout=None) as resp:
                    if resp.status == 200:
                        self.is_connected = True
                        retry_backoff = 2  # Reset backoff on success

                        # Asynchronously read the infinite stream line by line
                        async for line in resp.content:
                            if self._stop_event.is_set():
                                break

                            decoded_line = line.decode('utf-8').strip()

                            # SSE payloads are prefixed with "data: "
                            if decoded_line.startswith("data: "):
                                json_str = decoded_line[6:]
                                try:
                                    event_data = json.loads(json_str)
                                    self._process_inbound_telemetry(event_data)
                                except json.JSONDecodeError:
                                    continue
                    else:
                        logger.error(f"🔴 [HUE] SSE Stream failed with status {resp.status}")
                        self.is_connected = False
                        await asyncio.sleep(retry_backoff)
                        retry_backoff = min(60, retry_backoff * 2)

            except asyncio.TimeoutError:
                continue  # Harmless, just reconnect
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"🔴 [HUE] SSE Stream collapsed: {e}")
                    self.is_connected = False
                    await asyncio.sleep(retry_backoff)
                    retry_backoff = min(60, retry_backoff * 2)

    def _process_inbound_telemetry(self, data: list) -> None:
        """Translates native Hue V2 telemetry into WanOS event bus payloads."""

        # Respect the UI Admin toggle. If disabled, ignore inbound data.
        if not self._is_integration_enabled():
            return

        # Hue SSE packets contain a list of event objects
        for event in data:
            if "data" not in event:
                continue

            for resource in event["data"]:
                r_type = resource.get("type")

                # Process both individual lights and grouped zones
                if r_type not in ["light", "grouped_light"]:
                    continue

                uuid = resource.get("id")
                idx = self.uuid_to_idx.get(uuid) if r_type == "light" else self.group_uuid_to_idx.get(uuid)

                # If the entity isn't mapped in our config, we don't track it
                if not idx:
                    continue

                # Construct the rich payload for the StateManager
                payload: Dict[str, Any] = {
                    "idx": idx,
                    "origin": "hue",
                    "device_type": "light",  # Forces Option B UI rendering with glowing orb
                    # Pull the name dynamically from device_metadata seeded during boot
                    "name": device_name(
                        self.state_manager._state,
                        idx,
                        f"Hue {'Group' if r_type == 'grouped_light' else 'Light'} {idx}",
                    ),
                }

                if "on" in resource and "on" in resource["on"]:
                    payload["state"] = "ON" if resource["on"]["on"] else "OFF"

                if "dimming" in resource and "brightness" in resource["dimming"]:
                    payload["bri"] = resource["dimming"]["brightness"]

                if "color" in resource and "xy" in resource["color"]:
                    payload["xy"] = [
                        resource["color"]["xy"].get("x"),
                        resource["color"]["xy"].get("y")
                    ]

                # Only dispatch if the packet contained actionable attributes
                if "state" in payload or "bri" in payload or "xy" in payload:
                    self.state_manager.dispatch(Event(
                        type=EventType.HUB_STATE_CHANGED,
                        payload=payload
                    ))