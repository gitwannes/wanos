# --- file: core/automations_fire_status.py ---
"""
B10F: build today's fire-status payload for Automations Library (SR editor).

Schedule math lives server-side — FE only renders Will fire / Has fired / Doesn't fire today.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.event_catalog import SYSTEM_KEY_TO_UUID
from core.models import SystemState

# Env-schedule SE keys → SensorsState unix field name.
_ENV_SCHEDULE_FIELDS: tuple[tuple[str, str], ...] = (
    ("BLINDS_OPEN_TRIGGER", "env_schedule_blinds_open_unix"),
    ("BLINDS_CLOSE_TRIGGER", "env_schedule_blinds_close_unix"),
    ("MORNING_ON_TRIGGER", "env_schedule_twilight_morning_on_unix"),
    ("SUNRISE_TRIGGER", "env_schedule_twilight_morning_off_unix"),
    ("SUNSET_TRIGGER", "env_schedule_twilight_evening_on_unix"),
    ("EVENING_OFF_TRIGGER", "env_schedule_twilight_evening_off_unix"),
)

# Morning/evening window edges — None unix means Doesn't fire today (skip).
_SKIP_WHEN_NONE_KEYS = frozenset({
    "MORNING_ON_TRIGGER",
    "SUNRISE_TRIGGER",
    "SUNSET_TRIGGER",
    "EVENING_OFF_TRIGGER",
})

# Unix epoch after which session_end_time is a wall deadline (not a duration).
_UNIX_FLOOR = 1_000_000_000


def _hhmm_local(at_unix: int) -> str:
    """Local Pi clock HH:MM for status copy."""
    return datetime.fromtimestamp(int(at_unix)).strftime("%H:%M")


def _entry(
    event_uuid: str,
    state: str,
    at_unix: Optional[int] = None,
) -> Dict[str, Any]:
    """One fire-status row for the API."""
    row: Dict[str, Any] = {
        "event_uuid": event_uuid,
        "state": state,
        "at_hhmm": None,
        "at_unix": None,
    }
    if at_unix is not None and state in ("will_fire", "has_fired"):
        row["at_unix"] = int(at_unix)
        row["at_hhmm"] = _hhmm_local(int(at_unix))
    return row


def _will_or_has(now_unix: int, at_unix: int) -> str:
    """Wall-clock: past scheduled time → has_fired; else will_fire."""
    if now_unix > int(at_unix):
        return "has_fired"
    return "will_fire"


def _session_armed_unix(session_end_time: Optional[int], timer_armed: bool) -> Optional[int]:
    """
    Return unix deadline when the session timer is armed.

    Sauna stores a duration in session_end_time until heat threshold; only treat
    as armed when the timer is scheduled and the value looks like a unix end.
    """
    if not timer_armed or session_end_time is None:
        return None
    end = int(session_end_time)
    if end < _UNIX_FLOOR:
        return None
    return end


def build_automations_fire_status(
    state: SystemState,
    *,
    sauna_timer_armed: bool = False,
    ir_timer_armed: bool = False,
) -> Dict[str, Any]:
    """
    Build GET /api/automations/fire-status body.

    Always includes the six env-schedule SEs + Sauna OFF + IR OFF.
    """
    now_unix = int(time.time())
    entries: List[Dict[str, Any]] = []
    sns = state.sensors
    sun_ready = bool(sns.sunrise_unix and sns.sunset_unix)

    for key, field in _ENV_SCHEDULE_FIELDS:
        eid = SYSTEM_KEY_TO_UUID[key]
        if not sun_ready:
            # Rare: before first OWM sun fetch / OWM down — no editor status line.
            entries.append(_entry(eid, "not_armed"))
            continue
        at_unix = getattr(sns, field, None)
        if at_unix is None:
            if key in _SKIP_WHEN_NONE_KEYS:
                entries.append(_entry(eid, "doesnt_fire_today"))
            else:
                entries.append(_entry(eid, "not_armed"))
            continue
        st = _will_or_has(now_unix, int(at_unix))
        entries.append(_entry(eid, st, int(at_unix)))

    # Sauna OFF / IR OFF — session_end_time when timer armed (B10F; no absolute clamp).
    sauna_uuid = SYSTEM_KEY_TO_UUID["SAUNA_OFF"]
    sauna_end = _session_armed_unix(
        state.sauna.session_end_time if state.sauna else None,
        sauna_timer_armed,
    )
    if sauna_end is not None:
        entries.append(_entry(sauna_uuid, _will_or_has(now_unix, sauna_end), sauna_end))
    else:
        entries.append(_entry(sauna_uuid, "not_armed"))

    ir_uuid = SYSTEM_KEY_TO_UUID["IR_OFF"]
    ir_end = _session_armed_unix(
        state.ir.session_end_time if state.ir else None,
        ir_timer_armed,
    )
    if ir_end is not None:
        entries.append(_entry(ir_uuid, _will_or_has(now_unix, ir_end), ir_end))
    else:
        entries.append(_entry(ir_uuid, "not_armed"))

    return {"server_now_unix": now_unix, "entries": entries}
