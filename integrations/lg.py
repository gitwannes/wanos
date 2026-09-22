# --- file: integrations/lg.py ---
"""
LG webOS TV bridge (G16).

Power via Wake-on-LAN (cold ON) + SSAP (OFF / reachable=ON).
App launch via pywebostv ApplicationControl from a fixed config catalog.
Adaptive TCP poll of SSAP ports owns power state for idx in device_map.
G20: after commanded OFF, an off-latch suppresses poll-ON while SSAP stays
open (Instant On / network standby); latch clears on SSAP close or WanOS ON.
"""

from __future__ import annotations

import asyncio
import json
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from core.command_commit import claim_and_finish, claim_payload, is_outbound_hub_command
from core.event_catalog import legacy_key_for_bus_token
from core.models import Event, EventType, SystemState, format_device_ref

WS_PORT = 3000
WSS_PORT = 3001

DEFAULT_KEY_FILE = Path.home() / ".config" / "wanos" / "lg_webos_client_keys.json"


def _tcp_open(host: str, port: int, timeout: float = 0.6) -> bool:
    """Return True if TCP connect succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ssap_ports_open(host: str) -> bool:
    """True when webOS SSAP is listening (TV treated as ON)."""
    return _tcp_open(host, WS_PORT) or _tcp_open(host, WSS_PORT)


class LgWebOsBridge:
    """LG webOS power + app launch bridge."""

    def __init__(self, state_manager: Any, config: Any) -> None:
        self.state_manager = state_manager
        self._apply_config(config)
        self._poll_task: Optional[asyncio.Task] = None
        self._listener_registered = False
        self._integration_enabled = False
        # Bridge health (Admin): True after start(); independent of TV power.
        self.is_connected = False
        self._last_power: Optional[str] = None
        self._fast_poll_until: float = 0.0
        self._command_lock = asyncio.Lock()
        # G20: commanded-OFF latch — poll must not flip hub ON while SSAP stays up.
        self._off_latch: bool = False
        self._off_latch_suppress_logged: bool = False

    def _apply_config(self, config: Any) -> None:
        """Refresh host/MAC/maps from AppConfig.lg (or None)."""
        self.config = config
        lg = getattr(config, "lg", None) if config is not None else None
        self.host: str = str(getattr(lg, "host", "") or "").strip()
        self.mac: str = str(getattr(lg, "mac", "") or "").strip()
        key_path = getattr(lg, "client_key_file", None) if lg else None
        self.key_file = Path(key_path).expanduser() if key_path else DEFAULT_KEY_FILE
        self.wol_wait_secs: float = float(getattr(lg, "wol_wait_secs", 8.0) or 8.0)
        self.poll_secs: float = float(getattr(lg, "poll_secs", 10.0) or 10.0)
        self.poll_fast_secs: float = float(getattr(lg, "poll_fast_secs", 2.5) or 2.5)
        self.poll_fast_window_secs: float = float(
            getattr(lg, "poll_fast_window_secs", 30.0) or 30.0
        )
        self.device_map: Dict[int, Any] = dict(getattr(lg, "device_map", None) or {})
        self.apps: Dict[str, Any] = dict(getattr(lg, "apps", None) or {})
        # Primary TV idx (first map entry) — config may only have 62001
        self.tv_idx: Optional[int] = None
        if self.device_map:
            self.tv_idx = sorted(int(k) for k in self.device_map.keys())[0]

    def bump_fast_poll(self) -> None:
        """Enter fast adaptive poll window after a commanded transition."""
        self._fast_poll_until = time.monotonic() + self.poll_fast_window_secs

    def _poll_interval(self) -> float:
        if time.monotonic() < self._fast_poll_until:
            return self.poll_fast_secs
        return self.poll_secs

    def _arm_off_latch(self) -> None:
        """Arm G20 latch after accepting a WanOS OFF command."""
        if not self._off_latch:
            logger.info(
                "[LG] OFF latch armed - poll ON suppressed until SSAP closes "
                "or WanOS ON"
            )
        self._off_latch = True
        self._off_latch_suppress_logged = False

    def _clear_off_latch(self, reason: str) -> None:
        """Clear G20 latch (ports closed, WanOS ON, or failed OFF)."""
        if self._off_latch:
            logger.info(f"[LG] OFF latch cleared ({reason})")
        self._off_latch = False
        self._off_latch_suppress_logged = False

    def _load_store(self) -> Dict[str, str]:
        """Load pywebostv store for this host from key file."""
        if not self.key_file.is_file():
            return {}
        try:
            data = json.loads(self.key_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"[LG] Could not read key file {self.key_file}: {exc}")
            return {}
        if not isinstance(data, dict):
            return {}
        entry = data.get(self.host)
        if isinstance(entry, dict) and entry.get("client_key"):
            return {"client_key": str(entry["client_key"])}
        if isinstance(entry, str) and entry.strip():
            return {"client_key": entry.strip()}
        return {}

    def _save_store(self, store: Dict[str, str]) -> None:
        """Persist client_key for this host (helper may rewrite the same file)."""
        data: Dict[str, Any] = {}
        if self.key_file.is_file():
            try:
                loaded = json.loads(self.key_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        if store.get("client_key"):
            data[self.host] = {"client_key": store["client_key"]}
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _send_wol(self) -> None:
        """Send Wake-on-LAN magic packet to configured MAC."""
        from wakeonlan import send_magic_packet

        if not self.mac:
            raise RuntimeError("[LG] MAC not configured for WOL")
        logger.info(f"[LG] Sending WOL to {self.mac}")
        send_magic_packet(self.mac)

    async def _connect_client(self) -> Any:
        """Connect + register pywebostv client (caller must close)."""
        from pywebostv.connection import REGISTRATION_PAYLOAD, WebOSClient

        store = self._load_store()
        if store.get("client_key"):
            REGISTRATION_PAYLOAD["client-key"] = store["client_key"]
        else:
            REGISTRATION_PAYLOAD.pop("client-key", None)

        last_err: Optional[BaseException] = None
        for secure in (False, True):
            client = WebOSClient(self.host, secure=secure)
            try:
                # pywebostv is sync — run in thread to avoid blocking the loop
                await asyncio.to_thread(client.connect)
                def _register() -> None:
                    for status in client.register(store):
                        if status == WebOSClient.REGISTERED:
                            break

                await asyncio.to_thread(_register)
                if store.get("client_key"):
                    self._save_store(store)
                return client
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                try:
                    await asyncio.to_thread(client.close)
                except Exception:  # noqa: BLE001
                    pass
        raise RuntimeError(f"[LG] register failed: {last_err}")

    async def start(self) -> None:
        """Register listener, mark healthy, start poll, boot power sync."""
        if not self.host or self.tv_idx is None:
            logger.warning("[LG] Missing host or device_map — bridge idle.")
            return

        self._integration_enabled = bool(
            self.state_manager._state.system.lg_integration_enabled
        )
        if not self._listener_registered:
            self.state_manager.register_listener(self._on_state_changed)
            self._listener_registered = True

        self.is_connected = True
        logger.info(
            f"[LG] Bridge started host={self.host} idx={self.tv_idx} "
            f"enabled={self._integration_enabled}"
        )

        # Boot power probe (kickoff: set 62001 once)
        await self._probe_and_dispatch(is_initialization=True)

        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop poll loop; mark bridge unhealthy."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None
        self.is_connected = False
        logger.info("[LG] Bridge stopped.")

    async def reload_config(self, config: Any) -> None:
        """Apply new config after hot-reload (maps / host / apps)."""
        self._apply_config(config)
        logger.info(f"[LG] Config refreshed host={self.host} idx={self.tv_idx}")

    async def _poll_loop(self) -> None:
        """Adaptive SSAP port poll → HUB_STATE_CHANGED origin=lg."""
        try:
            while True:
                await asyncio.sleep(self._poll_interval())
                if not self._integration_enabled or not self.host:
                    continue
                await self._probe_and_dispatch(is_initialization=False)
        except asyncio.CancelledError:
            return

    async def _probe_and_dispatch(self, is_initialization: bool) -> None:
        """TCP probe SSAP; dispatch power if changed (or always on init)."""
        if self.tv_idx is None or not self.host:
            return
        on = await asyncio.to_thread(ssap_ports_open, self.host)

        # G20: after commanded OFF, Instant On keeps SSAP open — do not bounce ON.
        # Boot probe never inherits a latch (process-local).
        if self._off_latch and not is_initialization:
            if on:
                if not self._off_latch_suppress_logged:
                    logger.info(
                        "[LG] OFF latch: SSAP still open - keeping hub OFF"
                    )
                    self._off_latch_suppress_logged = True
                return
            # Deep OFF: ports closed — release latch so a later reopen can be ON.
            self._clear_off_latch("SSAP closed")
            new_state = "OFF"
        else:
            new_state = "ON" if on else "OFF"

        if not is_initialization and new_state == self._last_power:
            return
        self._last_power = new_state
        self.state_manager.dispatch(
            Event(
                type=EventType.HUB_STATE_CHANGED,
                payload={
                    "idx": self.tv_idx,
                    "state": new_state,
                    "origin": "lg",
                    "is_initialization": is_initialization,
                },
            )
        )
        if is_initialization:
            logger.info(f"[LG] Boot power sync → {new_state}")

    async def _on_state_changed(
        self, state: SystemState, events: Optional[List[Event]] = None
    ) -> None:
        """C18 listener: outbound power / app for our idx."""
        try:
            current_enabled = state.system.lg_integration_enabled
            if current_enabled and not self._integration_enabled:
                self._integration_enabled = True
                logger.success("[LG] Engine ENABLED via UI.")
            elif not current_enabled and self._integration_enabled:
                self._integration_enabled = False
                logger.info("[LG] Engine DISABLED via UI.")

            if not current_enabled or not events or self.tv_idx is None:
                return

            for event in events:
                if legacy_key_for_bus_token(event.type) != "HUB_STATE_CHANGED":
                    continue
                payload = event.payload or {}
                if not is_outbound_hub_command(payload):
                    continue
                idx = payload.get("idx")
                if idx is None or int(idx) != int(self.tv_idx):
                    continue
                claim_payload(self.state_manager, payload)
                asyncio.create_task(self._command_and_report(payload))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[LG] Unexpected error in _on_state_changed: {exc}")

    async def _command_and_report(self, payload: Dict[str, Any]) -> None:
        """Run power/app I/O off the drain; finish C18."""
        async with self._command_lock:
            ok, reason = await self._execute_command(payload)
        claim_and_finish(
            self.state_manager, payload, ok, reason if not ok else ""
        )
        self.bump_fast_poll()

    async def _execute_command(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Apply ON/OFF and optional app catalog key.

        Locked: app-only while OFF → fail; ON+app → WOL then launch.
        """
        if not self._integration_enabled:
            return False, "[LG] integration disabled"
        if not self.host:
            return False, "[LG] host not configured"

        state_val = str(payload.get("state") or "").upper()
        app_key = payload.get("app")
        app_key_s = str(app_key).strip() if app_key else ""

        want_on = state_val == "ON"
        want_off = state_val == "OFF"
        want_app = bool(app_key_s)

        if want_off and want_app:
            return False, "[LG] cannot combine OFF with app"

        ports_up = await asyncio.to_thread(ssap_ports_open, self.host)

        # App-only while OFF → fail (kickoff)
        if want_app and not want_on and not ports_up:
            return False, "[LG] TV is OFF; app launch requires ON (or ON+app)"

        # G20: arm latch before OFF I/O so a concurrent poll cannot bounce ON.
        armed_off_latch = False
        try:
            if want_on and not ports_up:
                try:
                    await asyncio.to_thread(self._send_wol)
                except Exception as exc:  # noqa: BLE001
                    return False, f"[LG] WOL failed: {exc}"
                await asyncio.sleep(self.wol_wait_secs)
                ports_up = await asyncio.to_thread(ssap_ports_open, self.host)
                if not ports_up:
                    return False, "[LG] SSAP still closed after WOL"

            if want_on:
                # Explicit WanOS ON / WOL path — clear any commanded-OFF latch.
                self._clear_off_latch("WanOS ON")
                self._last_power = "ON"

            if want_off:
                self._arm_off_latch()
                armed_off_latch = True
                if not ports_up:
                    # Idempotent OFF
                    self._last_power = "OFF"
                    return True, ""
                client = await self._connect_client()
                try:
                    from pywebostv.controls import SystemControl

                    await asyncio.to_thread(SystemControl(client).power_off)
                    self._last_power = "OFF"
                finally:
                    await asyncio.to_thread(client.close)
                return True, ""

            if want_app:
                if not ports_up and not want_on:
                    return False, "[LG] TV is OFF"
                # After cold ON, brief settle for launcher
                if want_on:
                    await asyncio.sleep(min(3.0, self.wol_wait_secs / 3.0))
                ok_launch, reason = await self._launch_app(app_key_s)
                return ok_launch, reason

            if want_on:
                # Power ON only (ports already up or WOL succeeded)
                return True, ""

            return False, "[LG] empty command"

        except Exception as exc:  # noqa: BLE001
            if armed_off_latch:
                self._clear_off_latch("OFF command failed")
            logger.error(
                f"[LG] Command failed for "
                f"{format_device_ref(self.state_manager._state, self.tv_idx)}: {exc}"
            )
            return False, f"[LG] {exc}"

    async def _launch_app(self, catalog_key: str) -> Tuple[bool, str]:
        """Launch app by config catalog key."""
        node = self.apps.get(catalog_key)
        if node is None:
            return False, f"[LG] unknown app key {catalog_key!r}"
        webos_id = getattr(node, "id", None) if not isinstance(node, dict) else node.get("id")
        if not webos_id:
            return False, f"[LG] app {catalog_key!r} has no webOS id"

        client = await self._connect_client()
        try:
            from pywebostv.controls import Application, ApplicationControl

            app_obj = Application({"id": str(webos_id), "title": catalog_key})
            await asyncio.to_thread(ApplicationControl(client).launch, app_obj)
            label = getattr(node, "label", None) if not isinstance(node, dict) else node.get("label")
            logger.info(f"[LG] Launched app key={catalog_key} id={webos_id} label={label}")
            return True, ""
        finally:
            await asyncio.to_thread(client.close)
