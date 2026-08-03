# --- file: integrations/sonos.py ---
import asyncio
import re
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

    @staticmethod
    def _tunein_station_id(uri: str) -> Optional[str]:
        match = re.search(r'tunein[%:]?(\d+)', uri, re.IGNORECASE)
        return match.group(1) if match else None

    @classmethod
    def _station_uri_matches(cls, configured_url: str, current_uri: str) -> bool:
        if not configured_url or not current_uri:
            return False
        if configured_url == current_uri:
            return True
        cfg_id = cls._tunein_station_id(configured_url)
        cur_id = cls._tunein_station_id(current_uri)
        if cfg_id and cur_id:
            return cfg_id == cur_id
        return configured_url in current_uri or current_uri in configured_url

    def _already_playing_station(self, speaker: soco.SoCo, url: str, volume: Optional[int]) -> bool:
        """Return True when the speaker is already playing the requested stream at the target volume."""
        try:
            transport = speaker.get_current_transport_info()
            if transport.get('current_transport_state') != 'PLAYING':
                return False

            if volume is not None and speaker.volume != volume:
                return False

            media = speaker.get_current_media_info()
            track = speaker.get_current_track_info()
            current_uri = media.get('uri') or track.get('uri') or ''
            return self._station_uri_matches(url, current_uri)
        except Exception:
            return False

    def _start_playback(self, speaker: soco.SoCo, volume: Optional[int], station_key: Optional[str],
                        station_url: Optional[str]) -> bool:
        """
        Apply volume, tune station if needed, and start playback.
        Returns False when playback was skipped because the station was already active.
        """
        if volume is not None:
            speaker.volume = volume

        wants_station = bool(station_key and station_url)
        if wants_station:
            if self._already_playing_station(speaker, station_url, volume):
                return False
            speaker.play_uri(station_url, title=station_key)
            speaker.play()
            return True

        speaker.play()
        return True

    def _pause_speaker(self, speaker: soco.SoCo) -> None:
        speaker.pause()

    async def execute_command(self, payload: dict[str, Any]) -> None:
        """Unified command processor handling playback toggles, volume curves, and URI streaming."""
        idx = payload.get("idx")
        speaker = self.speakers.get(idx)
        if not speaker:
            return

        try:
            target_state = payload.get("state") or payload.get("action")

            # OFF/pause is authoritative — must run before any station/volume handling
            if target_state == "OFF" or target_state == "pause":
                await asyncio.to_thread(self._pause_speaker, speaker)
                self.manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"idx": idx, "state": "OFF", "origin": "sonos"}))
                return

            volume = payload.get("volume")
            if volume is not None:
                volume = max(0, min(100, int(volume)))

            station_key = payload.get("station")
            station_url = self.stations.get(station_key) if station_key else None

            should_play = (
                target_state in ("ON", "play")
                or station_url is not None
            )

            if not should_play:
                if volume is not None:
                    await asyncio.to_thread(setattr, speaker, 'volume', volume)
                return

            playback_started = await asyncio.to_thread(
                self._start_playback, speaker, volume, station_key, station_url)

            if playback_started:
                self.manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"idx": idx, "state": "ON", "origin": "sonos"}))
        except Exception as e:
            logger.error(f"Sonos command failed on {idx}: {e}")
