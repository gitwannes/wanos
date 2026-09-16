# --- file: integrations/homewizard.py ---
"""
HomeWizard Energy Local API bridge (G10).

Telemetry-only: poll HTTPS /api/measurement every poll_secs (default 60).
Uses aiohttp (Pi Python 3.9 — HomeWizardEnergyV2 needs 3.12+).
Tokens from ~/.config/wanos/homewizard_tokens.json (same as discovery scout).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aiohttp import ClientSession, ClientTimeout
from loguru import logger

from core.models import Event, EventType

DEFAULT_TOKEN_FILE = Path.home() / ".config" / "wanos" / "homewizard_tokens.json"
LOG_TAG = "[HomeWizard]"


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
        # host -> last status label (online | offline | no_token | http_N | error)
        self._host_status: Dict[str, str] = {}
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

    def _log_host_status(self, host: str, status: str) -> None:
        """INFO only when a host status changes (health pings every ~2s)."""
        prev = self._host_status.get(host)
        self._host_status[host] = status
        if prev != status:
            logger.info(f"{LOG_TAG} host {host}: {status}" + (f" (was {prev})" if prev else ""))

    async def start(self) -> None:
        """Mark bridge process up and start poll loop (device reachability via ping)."""
        hosts = sorted(self._by_host.keys())
        logger.info(
            f"{LOG_TAG} Bridge started (poll_secs={self.poll_secs}, "
            f"hosts={hosts or '-'}, metrics={len(self.device_map)})"
        )
        # Process is up; host reachability is updated by ping()/poll.
        self.is_connected = True
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop poll loop."""
        self.is_connected = False
        self._integration_enabled = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None
        logger.info(f"{LOG_TAG} Bridge stopped")

    def set_enabled(self, enabled: bool) -> None:
        """Mirror Admin integration enable into the poll gate."""
        self._integration_enabled = bool(enabled)

    def apply_reload(self, config: Any) -> None:
        """Hot-reload config map (full CONFIG_RELOAD)."""
        self._apply_config(config)
        logger.info(f"{LOG_TAG} Config reloaded ({len(self.device_map)} metrics)")

    async def ping(self) -> bool:
        """Health: True if at least one configured host answers v2 /api with token."""
        if not self._by_host:
            logger.debug(f"{LOG_TAG} ping: no hosts in device_map")
            return True
        tokens = _load_tokens(self.token_file)
        timeout = ClientTimeout(total=5)
        any_ok = False
        async with ClientSession() as session:
            for host in sorted(self._by_host.keys()):
                token = tokens.get(host)
                if not token:
                    self._log_host_status(host, "no_token")
                    continue
                try:
                    async with session.get(
                        f"https://{host}/api",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-Api-Version": "2",
                        },
                        ssl=False,
                        timeout=timeout,
                    ) as res:
                        if res.status == 200:
                            self._log_host_status(host, "online")
                            any_ok = True
                        else:
                            self._log_host_status(host, f"http_{res.status}")
                except Exception as exc:
                    self._log_host_status(host, f"offline ({type(exc).__name__})")
        logger.debug(
            f"{LOG_TAG} ping any_ok={any_ok} status={dict(self._host_status)}"
        )
        return any_ok

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
        timeout = ClientTimeout(total=10)
        any_ok = False
        async with ClientSession() as session:
            for host, metrics in self._by_host.items():
                token = tokens.get(host)
                if not token:
                    self._log_host_status(host, "no_token")
                    logger.warning(
                        f"{LOG_TAG} No token for {host} - run helpers/homewizard_discovery.py pair"
                    )
                    continue
                try:
                    async with session.get(
                        f"https://{host}/api/measurement",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-Api-Version": "2",
                            "Accept": "application/json",
                        },
                        ssl=False,
                        timeout=timeout,
                    ) as res:
                        body = await res.text()
                        if res.status != 200:
                            self._log_host_status(host, f"http_{res.status}")
                            logger.warning(
                                f"{LOG_TAG} {host} measurement HTTP {res.status}"
                            )
                            continue
                        measurement = json.loads(body)
                except Exception as exc:
                    self._log_host_status(host, f"offline ({type(exc).__name__})")
                    logger.warning(f"{LOG_TAG} {host} poll failed: {exc}")
                    continue
                if not isinstance(measurement, dict):
                    self._log_host_status(host, "bad_json")
                    continue
                self._log_host_status(host, "online")
                any_ok = True
                for idx, field, name, dtype in metrics:
                    value = extract_measurement_field(measurement, field)
                    if value is None:
                        continue
                    self._dispatch_metric(idx, value, name, dtype)
        # Steady-state success summary every poll_secs - DEBUG only (host up/down stays INFO)
        logger.debug(
            f"{LOG_TAG} poll done any_ok={any_ok} "
            f"hosts={dict(self._host_status)}"
        )
        if self._integration_enabled:
            self.is_connected = any_ok

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
