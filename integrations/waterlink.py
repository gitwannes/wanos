# --- file: integrations/waterlink.py ---
"""
Water-Link digital meter WanOS bridge (G24).

Telemetry-only: poll portal cumulative m3 every poll_interval_hours (default 6).
Reuses G23 OIDC PKCE + SAP form client (integrations/waterlink_client.py).

Health (kickoff 2026-11-05): 2 consecutive poll failures -> offline / auto-kill path.
No portal ping on every health-monitor tick.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional, Tuple

from aiohttp import ClientSession, ClientTimeout, CookieJar
from loguru import logger

from core.models import Event, EventType
from integrations.waterlink_client import WaterLinkPortalClient

LOG_TAG = "[WaterLink]"
# Kickoff lock: 2 consecutive poll failures mark the bridge offline.
FAIL_HYSTERESIS = 2
# Headless login + meter GET can take a while (Incapsula / SAP).
POLL_TIMEOUT_SECS = 90.0
# Chunked wait so Admin enable mid-interval can force an early poll.
SLEEP_CHUNK_SECS = 30.0


class WaterLinkBridge:
    """Poll Water-Link portal and ingest cumulative m3 into WanOS."""

    def __init__(self, state_manager: Any, config: Any) -> None:
        self.state_manager = state_manager
        self._poll_task: Optional[asyncio.Task] = None
        self._integration_enabled = False
        self.is_connected = False
        self._fail_streak: int = 0
        self._force_poll = False
        self._session: Optional[ClientSession] = None
        self._apply_config(config)

    def _apply_config(self, config: Any) -> None:
        """Refresh meter / poll / idx / name from AppConfig.waterlink."""
        self.config = config
        wl = getattr(config, "waterlink", None) if config is not None else None
        hours = float(getattr(wl, "poll_interval_hours", 6.0) or 6.0)
        self.poll_interval_secs: float = max(60.0, hours * 3600.0)
        self.meter_id: str = str(getattr(wl, "meter_id", "") or "").strip()
        try:
            self.idx: int = int(getattr(wl, "idx", 82001) or 82001)
        except (TypeError, ValueError):
            self.idx = 82001
        self.name: str = str(
            getattr(wl, "name", None) or "Water-Link m\u00b3"
        ).strip() or "Water-Link m\u00b3"

    def _credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Read portal secrets from process env (restart needed after .env change)."""
        user = os.getenv("WATERLINK_USER") or os.getenv("WATERLINK_USERNAME")
        password = os.getenv("WATERLINK_PASSWORD")
        return (
            user.strip() if isinstance(user, str) else None,
            password if isinstance(password, str) else None,
        )

    async def _ensure_session(self) -> ClientSession:
        """Lazy-create aiohttp session with cookie jar (SAP login needs cookies)."""
        if self._session is not None and not self._session.closed:
            return self._session
        self._session = ClientSession(
            cookie_jar=CookieJar(unsafe=True),
            timeout=ClientTimeout(total=POLL_TIMEOUT_SECS),
        )
        return self._session

    async def _close_session(self) -> None:
        """Tear down the aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _note_success(self) -> None:
        """Clear fail streak and mark connected after a good poll."""
        self._fail_streak = 0
        self.is_connected = True

    def _note_failure(self, detail: str) -> None:
        """Count a failed poll; trip offline after FAIL_HYSTERESIS consecutive fails."""
        self._fail_streak = int(self._fail_streak) + 1
        if self._fail_streak < FAIL_HYSTERESIS:
            logger.warning(
                f"{LOG_TAG} poll miss {self._fail_streak}/{FAIL_HYSTERESIS}: {detail}"
            )
            return
        self.is_connected = False
        logger.error(
            f"{LOG_TAG} poll failed ({self._fail_streak} consecutive): {detail}"
        )

    async def start(self) -> None:
        """Mark bridge process up and start poll loop."""
        logger.info(
            f"{LOG_TAG} Bridge started (poll_interval_secs={self.poll_interval_secs:.0f}, "
            f"fail_hysteresis={FAIL_HYSTERESIS}, meter_id={self.meter_id or '-'}, "
            f"idx={self.idx})"
        )
        await self._ensure_session()
        # Boot grace: Admin shows LIVE until first poll(s) decide otherwise.
        self._fail_streak = 0
        self.is_connected = True
        self._force_poll = True
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop poll loop and close the session."""
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
        was = self._integration_enabled
        self._integration_enabled = bool(enabled)
        if self._integration_enabled and not was:
            self._force_poll = True

    def apply_reload(self, config: Any) -> None:
        """Hot-reload waterlink: block (full CONFIG_RELOAD)."""
        self._apply_config(config)
        self._force_poll = True
        logger.info(
            f"{LOG_TAG} Config reloaded (meter_id={self.meter_id or '-'}, "
            f"idx={self.idx}, poll_secs={self.poll_interval_secs:.0f})"
        )

    async def ping(self) -> bool:
        """
        Health for HealthMonitor: no live portal call.
        True while consecutive poll failures stay below FAIL_HYSTERESIS.
        """
        ok = self._fail_streak < FAIL_HYSTERESIS
        logger.debug(
            f"{LOG_TAG} ping ok={ok} fail_streak={self._fail_streak} "
            f"connected={self.is_connected}"
        )
        return ok

    async def _poll_loop(self) -> None:
        """Forever poll while started; chunked sleep so enable can wake early."""
        while True:
            try:
                if self._integration_enabled:
                    await self._poll_once()
                waited = 0.0
                target = self.poll_interval_secs
                while waited < target:
                    if self._force_poll:
                        self._force_poll = False
                        break
                    chunk = min(SLEEP_CHUNK_SECS, target - waited)
                    await asyncio.sleep(chunk)
                    waited += chunk
                    # While disabled, keep chunking without rushing a poll.
                    if not self._integration_enabled:
                        continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"{LOG_TAG} Poll loop error: {exc}")
                await asyncio.sleep(SLEEP_CHUNK_SECS)

    async def _poll_once(self) -> None:
        """Full headless login + meter GET; dispatch absolute fluid m3."""
        user, password = self._credentials()
        if not user or not password:
            self._note_failure("missing WATERLINK_USER / WATERLINK_PASSWORD")
            return
        if not self.meter_id:
            self._note_failure("missing waterlink.meter_id in config")
            return

        session = await self._ensure_session()
        client = WaterLinkPortalClient(
            username=user,
            password=password,
            meter_id=self.meter_id,
            session=session,
        )
        try:
            await client.login_authorization_code_pkce()
            telemetry = await client.get_meter_reading()
        except Exception as exc:
            detail = str(exc).strip() or type(exc).__name__
            self._note_failure(detail)
            # Fresh cookies next attempt (login state may be poisoned).
            await self._close_session()
            return

        total_m3 = telemetry.get("total_m3")
        if total_m3 is None:
            self._note_failure("meterReading missing or unparsable")
            return

        self._note_success()
        logger.info(
            f"{LOG_TAG} poll ok idx={self.idx} m3={float(total_m3)} "
            f"reading_date={telemetry.get('reading_date')}"
        )
        self.state_manager.dispatch(
            Event(
                type=EventType.WATERLINK_METRIC,
                payload={
                    "idx": self.idx,
                    "value": float(total_m3),
                    "device_type": "fluid",
                    "origin": "waterlink",
                    "name": self.name,
                },
            )
        )
