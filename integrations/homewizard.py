# --- file: integrations/homewizard.py ---
"""
HomeWizard Energy Local API bridge (G10).

Telemetry-only: poll HTTPS /api/measurement every poll_secs (default 60).
Uses aiohttp (Pi Python 3.9 — HomeWizardEnergyV2 needs 3.12+).
Tokens from ~/.config/wanos/homewizard_tokens.json (same as discovery scout).

Health (A+B+D, 2026-09-22):
  A — connected = last successful poll within 3 * poll_secs (no 2s HTTPS probe).
  B — one shared ClientSession, connector limit=1, per-host lock.
  D — host online/offline INFO only after 3 consecutive poll failures (or recovery).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aiohttp import ClientSession, ClientTimeout, TCPConnector
from loguru import logger

from core.models import Event, EventType

DEFAULT_TOKEN_FILE = Path.home() / ".config" / "wanos" / "homewizard_tokens.json"
LOG_TAG = "[HomeWizard]"

# Staleness multiplier for health (connected iff last OK within this many poll_secs).
STALE_POLL_MULT = 3.0
# Consecutive poll failures before INFO offline / non-online host status.
FAIL_HYSTERESIS = 3
# Measurement GET budget (P1 TLS often 0.8-1.6s; spikes to ~5s observed).
POLL_TIMEOUT_SECS = 15.0


def _load_tokens(path: Path) -> Dict[str, str]:
    """Read host -> bearer token map."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"{LOG_TAG} Could not read token file {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for host, token in data.items():
        if isinstance(host, str) and isinstance(token, str) and token.strip():
            out[host.strip()] = token.strip()
    return out


def extract_measurement_field(measurement: Dict[str, Any], field: str) -> Optional[float]:
    """
    Resolve a metric from a v2 measurement dict.
    field: plain key (power_w) or external.<type> (external.gas_meter).
    """
    key = (field or "").strip()
    if not key:
        return None
    if key.startswith("external."):
        want_type = key.split(".", 1)[1].strip()
        external = measurement.get("external")
        if external is None:
            external = measurement.get("external_devices")
        if isinstance(external, list):
            for item in external:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type") or "") == want_type:
                    try:
                        return float(item.get("value"))
                    except (TypeError, ValueError):
                        return None
        elif isinstance(external, dict):
            for item in external.values():
                if not isinstance(item, dict):
                    continue
                if str(item.get("type") or "") == want_type:
                    try:
                        return float(item.get("value"))
                    except (TypeError, ValueError):
                        return None
        return None
    raw = measurement.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class HomeWizardBridge:
    """Poll HomeWizard P1 / kWh meters and dispatch telemetry."""

    def __init__(self, state_manager: Any, config: Any) -> None:
        self.state_manager = state_manager
        self._poll_task: Optional[asyncio.Task] = None
        self._integration_enabled = False
        self.is_connected = False
        # host -> last status label (online | offline (...) | no_token | http_N | ...)
        self._host_status: Dict[str, str] = {}
        # host -> monotonic timestamp of last successful measurement
        self._last_ok_mono: Dict[str, float] = {}
        # host -> consecutive failed polls (reset on success)
        self._fail_streak: Dict[str, int] = {}
        # host -> asyncio.Lock (serialize HTTPS to that meter)
        self._host_locks: Dict[str, asyncio.Lock] = {}
        self._session: Optional[ClientSession] = None
        self._apply_config(config)

    def _apply_config(self, config: Any) -> None:
        """Refresh poll interval + device_map from AppConfig.homewizard."""
        self.config = config
        hw = getattr(config, "homewizard", None) if config is not None else None
        self.poll_secs: float = float(getattr(hw, "poll_secs", 60.0) or 60.0)
        token_path = getattr(hw, "token_file", None) if hw else None
        self.token_file = (
            Path(str(token_path)).expanduser()
            if token_path
            else DEFAULT_TOKEN_FILE
        )
        self.device_map: Dict[int, Any] = dict(getattr(hw, "device_map", None) or {})
        # host -> list of (idx, field, name, type)
        self._by_host: Dict[str, List[Tuple[int, str, str, str]]] = {}
        for idx_key, node in self.device_map.items():
            try:
                idx = int(idx_key)
            except (TypeError, ValueError):
                continue
            host = str(getattr(node, "host", "") or "").strip()
            field = str(getattr(node, "field", "") or "").strip()
            name = str(getattr(node, "name", "") or field or f"hw-{idx}")
            dtype = str(getattr(node, "type", "sensor") or "sensor").strip().lower()
            if not host or not field:
                continue
            self._by_host.setdefault(host, []).append((idx, field, name, dtype))

    def _stale_after_secs(self) -> float:
        """Max age of last OK poll before health reports disconnected."""
        return max(5.0, float(self.poll_secs)) * STALE_POLL_MULT

    def _host_lock(self, host: str) -> asyncio.Lock:
        """Return (and create) the per-host request lock."""
        lock = self._host_locks.get(host)
        if lock is None:
            lock = asyncio.Lock()
            self._host_locks[host] = lock
        return lock

    async def _ensure_session(self) -> ClientSession:
        """Lazy-create a shared keep-alive session (limit=1 connector)."""
        if self._session is not None and not self._session.closed:
            return self._session
        connector = TCPConnector(limit=1, ssl=False)
        self._session = ClientSession(
            connector=connector,
            timeout=ClientTimeout(total=POLL_TIMEOUT_SECS),
        )
        return self._session

    async def _close_session(self) -> None:
        """Tear down the shared aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _log_host_status(self, host: str, status: str) -> None:
        """INFO only when a host status label changes."""
        prev = self._host_status.get(host)
        self._host_status[host] = status
        if prev != status:
            logger.info(f"{LOG_TAG} host {host}: {status}" + (f" (was {prev})" if prev else ""))

    def _note_success(self, host: str) -> None:
        """Record a good poll: clear fail streak, refresh OK time, mark online."""
        self._fail_streak[host] = 0
        self._last_ok_mono[host] = time.monotonic()
        self._log_host_status(host, "online")

    def _note_failure(self, host: str, status: str, detail: str) -> None:
        """
        Count a failed poll. INFO status change only after FAIL_HYSTERESIS
        consecutive failures; earlier misses stay DEBUG. When hysteresis
        trips, drop last-OK so health/staleness matches the offline status.
        """
        streak = int(self._fail_streak.get(host, 0)) + 1
        self._fail_streak[host] = streak
        if streak < FAIL_HYSTERESIS:
            logger.debug(
                f"{LOG_TAG} {host} poll miss {streak}/{FAIL_HYSTERESIS}: {detail}"
            )
            return
        self._last_ok_mono.pop(host, None)
        self._log_host_status(host, status)
        logger.warning(f"{LOG_TAG} {host} poll failed: {detail}")

    def _seed_boot_ok(self) -> None:
        """
        Boot grace: treat configured hosts as fresh so health does not
        auto-kill before the first poll_secs window completes.
        """
        now = time.monotonic()
        for host in self._by_host:
            self._last_ok_mono[host] = now
            self._fail_streak[host] = 0

    def _health_ok(self) -> bool:
        """
        True if at least one token-backed host has a successful poll
        within 3 * poll_secs (boot seed counts until first real poll).
        """
        if not self._by_host:
            return True
        tokens = _load_tokens(self.token_file)
        now = time.monotonic()
        stale_after = self._stale_after_secs()
        any_fresh = False
        for host in self._by_host:
            if not tokens.get(host):
                self._log_host_status(host, "no_token")
                continue
            last = self._last_ok_mono.get(host)
            if last is not None and (now - last) <= stale_after:
                any_fresh = True
        return any_fresh

    async def start(self) -> None:
        """Mark bridge process up and start poll loop."""
        hosts = sorted(self._by_host.keys())
        logger.info(
            f"{LOG_TAG} Bridge started (poll_secs={self.poll_secs}, "
            f"stale_after={self._stale_after_secs():.0f}s, "
            f"fail_hysteresis={FAIL_HYSTERESIS}, "
            f"hosts={hosts or '-'}, metrics={len(self.device_map)})"
        )
        await self._ensure_session()
        self._seed_boot_ok()
        self.is_connected = True
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop poll loop and close the shared session."""
        self.is_connected = False
        self._integration_enabled = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None
        await self._close_session()
        logger.info(f"{LOG_TAG} Bridge stopped")

    def set_enabled(self, enabled: bool) -> None:
        """Mirror Admin integration enable into the poll gate."""
        self._integration_enabled = bool(enabled)

    def apply_reload(self, config: Any) -> None:
        """Hot-reload config map (full CONFIG_RELOAD)."""
        self._apply_config(config)
        # New hosts get boot grace so health does not flap mid-reload.
        now = time.monotonic()
        for host in self._by_host:
            if host not in self._last_ok_mono:
                self._last_ok_mono[host] = now
                self._fail_streak[host] = 0
        logger.info(f"{LOG_TAG} Config reloaded ({len(self.device_map)} metrics)")

    async def ping(self) -> bool:
        """
        Health for HealthMonitor: no live HTTPS.
        True if at least one configured host has a fresh last-OK poll
        (age <= 3 * poll_secs).
        """
        ok = self._health_ok()
        logger.debug(
            f"{LOG_TAG} ping ok={ok} status={dict(self._host_status)} "
            f"last_ok_age="
            + ",".join(
                f"{h}:{(time.monotonic() - t):.0f}s"
                for h, t in sorted(self._last_ok_mono.items())
            )
        )
        return ok

    async def _poll_loop(self) -> None:
        """Forever poll while started; skip work when integration disabled."""
        while True:
            try:
                if self._integration_enabled:
                    await self._poll_once()
                await asyncio.sleep(max(5.0, float(self.poll_secs)))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"{LOG_TAG} Poll loop error: {exc}")

    async def _poll_once(self) -> None:
        """Fetch measurement per host and dispatch per mapped field."""
        if not self._by_host:
            return
        tokens = _load_tokens(self.token_file)
        session = await self._ensure_session()
        any_ok = False
        for host, metrics in self._by_host.items():
            token = tokens.get(host)
            if not token:
                self._log_host_status(host, "no_token")
                logger.warning(
                    f"{LOG_TAG} No token for {host} - run helpers/homewizard_discovery.py pair"
                )
                continue
            async with self._host_lock(host):
                try:
                    async with session.get(
                        f"https://{host}/api/measurement",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-Api-Version": "2",
                            "Accept": "application/json",
                        },
                        ssl=False,
                        timeout=ClientTimeout(total=POLL_TIMEOUT_SECS),
                    ) as res:
                        body = await res.text()
                        if res.status != 200:
                            self._note_failure(
                                host,
                                f"http_{res.status}",
                                f"measurement HTTP {res.status}",
                            )
                            continue
                        measurement = json.loads(body)
                except Exception as exc:
                    exc_name = type(exc).__name__
                    detail = str(exc).strip() or exc_name
                    self._note_failure(
                        host,
                        f"offline ({exc_name})",
                        detail,
                    )
                    continue
            if not isinstance(measurement, dict):
                self._note_failure(host, "bad_json", "measurement JSON not an object")
                continue
            self._note_success(host)
            any_ok = True
            for idx, field, name, dtype in metrics:
                value = extract_measurement_field(measurement, field)
                if value is None:
                    continue
                self._dispatch_metric(idx, value, name, dtype)
        # Steady-state success summary every poll_secs - DEBUG only
        logger.debug(
            f"{LOG_TAG} poll done any_ok={any_ok} "
            f"hosts={dict(self._host_status)}"
        )
        if self._integration_enabled:
            self.is_connected = self._health_ok()

    def _dispatch_metric(
        self,
        idx: int,
        value: float,
        name: str,
        dtype: str,
    ) -> None:
        """Push one metric into WanOS bus."""
        sm = self.state_manager
        if dtype == "power":
            sm.dispatch(
                Event(
                    type=EventType.POWER_UPDATED,
                    payload={
                        "idx": idx,
                        "value": float(value),
                        "device_type": "power",
                        "origin": "homewizard",
                        "name": name,
                    },
                )
            )
            return
        # energy / fluid / sensor — store absolute reading
        sm.dispatch(
            Event(
                type=EventType.HOMEWIZARD_METRIC,
                payload={
                    "idx": idx,
                    "value": float(value),
                    "device_type": dtype,
                    "origin": "homewizard",
                    "name": name,
                },
            )
        )
