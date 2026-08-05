# --- file: core/schedule_events.py ---
"""
Environmental schedule window edges and event renames.

SCHEDULE_WINDOW_EDGES maps a Blocky/Y1 "family" to (enter_edge, exit_edge) trigger
event names. Edges are not always named ON/OFF (blinds use OPEN/CLOSE; twilight
morning exit is sunrise, evening enter is sunset).

Canonical twilight edge names (cutover):
  MORNING_ON_TRIGGER  — configured morning-on clock
  SUNRISE_TRIGGER     — astronomical sunrise (end of morning twilight window)
  SUNSET_TRIGGER      — astronomical sunset (start of evening twilight window)
  EVENING_OFF_TRIGGER — configured evening-off clock

Important: SUNRISE_TRIGGER / SUNSET_TRIGGER are **not** BLINDS_OPEN / BLINDS_CLOSE.
Blinds open/close use clamped times: max(sunrise|sunset, earliest) and optional latest.
"""
from __future__ import annotations

from typing import Dict, Optional

# Family key → (enter edge event, exit edge event)
SCHEDULE_WINDOW_EDGES: Dict[str, tuple[str, str]] = {
    "blinds": ("BLINDS_OPEN_TRIGGER", "BLINDS_CLOSE_TRIGGER"),
    "twilight_evening": ("SUNSET_TRIGGER", "EVENING_OFF_TRIGGER"),
    "twilight_morning": ("MORNING_ON_TRIGGER", "SUNRISE_TRIGGER"),
    "sauna": ("SAUNA_ON", "SAUNA_OFF"),
    "ir": ("IR_ON", "IR_OFF"),
    "cinema": ("SCENE_CINEMA_ON", "SCENE_CINEMA_OFF"),
}

# Legacy event strings → canonical (deliberate cutover aliases; accept forever for YAML/timers).
SCHEDULE_EVENT_ALIASES: Dict[str, str] = {
    "TWILIGHT_MORNING_ON_TRIGGER": "MORNING_ON_TRIGGER",
    "TWILIGHT_MORNING_OFF_TRIGGER": "SUNRISE_TRIGGER",
    "TWILIGHT_EVENING_ON_TRIGGER": "SUNSET_TRIGGER",
    "TWILIGHT_EVENING_OFF_TRIGGER": "EVENING_OFF_TRIGGER",
}

# Deprecated alias — prefer SCHEDULE_WINDOW_EDGES
EVENT_FAMILY_TO_ON_OFF = SCHEDULE_WINDOW_EDGES


def canonicalize_schedule_event(name: Optional[str]) -> Optional[str]:
    """Map legacy twilight event names to canonical ones; pass through otherwise."""
    if name is None:
        return None
    if hasattr(name, "value"):
        s = str(name.value)
    else:
        s = str(name)
    return SCHEDULE_EVENT_ALIASES.get(s, s)
