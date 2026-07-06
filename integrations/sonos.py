# --- file: integrations/sonos.py ---
import asyncio
import soco
from typing import Dict, Any, Optional
from loguru import logger
from core.models import Event, EventType


class SonosBridge:
    def __init__(self, manager: Any) -> None:
        self.manager = manager
        self.device_map = manager._config.sonos.device_map if manager._config.sonos else {}
        self.stations = manager._config.sonos.stations if manager._config.sonos else {}
        self.speakers: Dict[int, soco.SoCo] = {}
        self._polling_task: Optional[asyncio.Task] = None
        self._running: bool = False

        for idx, node in self.device_map.items():
            self.speakers[idx] = soco.SoCo(node.ip)

    async def start(self) -> None:
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_loop())
        logger.info(f"Sonos Bridge started. Monitoring {len(self.speakers)} speakers via TCP.")

    async def stop(self) -> None:
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        logger.info("Sonos Bridge stopped.")

    async def _poll_loop(self) -> None:
        """
        Lightweight async background loop querying port 1400 every 10s.
        Updates the WanOS state if someone uses the physical speaker buttons or native app.
        """
        while self._running:
            for idx, speaker in self.speakers.items():
                try:
                    # Offload the blocking HTTP requests to the C-thread pool
                    info = await asyncio.to_thread(speaker.get_current_transport_info)
                    state = info.get('current_transport_state', 'UNKNOWN')
                    current_vol = await asyncio.to_thread(getattr, speaker, 'volume')

                    is_on = state == 'PLAYING'
                    expected_state = "ON" if is_on else "OFF"
                    current_device_dict = self.manager._state.devices.get(idx)

                    # Validate if playback state OR volume sliders moved
                    state_changed = False
                    if not isinstance(current_device_dict, dict):
                        state_changed = True
                    else:
                        if current_device_dict.get("state") != expected_state or current_device_dict.get(
                                "volume") != current_vol:
                            state_changed = True

                    if state_changed:
                        self.manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={
                                "idx": idx,
                                "state": expected_state,
                                "volume": current_vol,
                                "origin": "sonos",
                                "is_initialization": True  # Suppresses the UI logger spam
                            }
                        ))
                except Exception:
                    # Explicitly flag the speaker as DEAD if it drops off the Wi-Fi
                    if self.manager._state.devices.get(idx) != "DEAD":
                        self.manager.dispatch(Event(
                            type=EventType.HUB_STATE_CHANGED,
                            payload={"idx": idx, "state": "DEAD", "origin": "sonos"}
                        ))

            await asyncio.sleep(10)

    async def execute_command(self, payload: dict[str, Any]) -> None:
        """Unified command processor handling playback toggles, volume curves, and URI streaming."""
        idx = payload.get("idx")
        speaker = self.speakers.get(idx)
        if not speaker: return

        try:
            # 1. Adjust volume if explicitly defined
            if "volume" in payload:
                vol = max(0, min(100, int(payload["volume"])))
                await asyncio.to_thread(setattr, speaker, 'volume', vol)

            # 2. Extract radio station URIs from config maps if defined
            if "station" in payload:
                station_key = payload["station"]
                url = self.stations.get(station_key)
                if url:
                    await asyncio.to_thread(speaker.play_uri, url, title=station_key)

            # 3. Handle explicit or implicit playback state changes
            # ⚡ Fall-through execution ensures a play command fires directly after loading a radio URI
            target_state = payload.get("state") or payload.get("action")
            if target_state == "ON" or target_state == "play" or "station" in payload:
                await asyncio.to_thread(speaker.play)
                self.manager.dispatch(
                    Event(type=EventType.HUB_STATE_CHANGED, payload={"idx": idx, "state": "ON", "origin": "sonos"}))
            elif target_state == "OFF" or target_state == "pause":
                await asyncio.to_thread(speaker.pause)
                self.manager.dispatch(Event(type=EventType.HUB_STATE_CHANGED,
                                            payload={"idx": idx, "state": "OFF", "origin": "sonos"}))
        except Exception as e:
            logger.error(f"Sonos command failed on {idx}: {e}")