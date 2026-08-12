# --- file: core/reload_alerts.py ---
"""Scope-specific CONFIG_RELOAD alert copy (B10G / G6 follow-up)."""

from __future__ import annotations

from typing import Any, Dict

# Stored message text matches AlertManager output after emoji / ERROR: strip.
RELOAD_ALERT_COPY: Dict[str, Dict[str, str]] = {
    "full": {
        "in_progress": "🔄 Reloading all config…",
        "complete": "🟢 All config reloaded.",
        "failed_prefix": "ERROR: All config reload failed: ",
    },
    "hue_presets": {
        "in_progress": "🔄 Reloading hue presets…",
        "complete": "🟢 Hue presets reloaded.",
        "failed_prefix": "ERROR: Hue presets reload failed: ",
    },
    "timers_types": {
        "in_progress": "🔄 Reloading timers & types…",
        "complete": "🟢 Timers & types reloaded.",
        "failed_prefix": "ERROR: Timers & types reload failed: ",
    },
}


def resolve_reload_alert_scope(payload: Dict[str, Any] | None) -> str:
    """Map CONFIG_RELOAD payload to alert row (B10G Option A — unscoped API → full)."""
    payload = payload or {}
    scope = str(payload.get("scope") or "").strip().lower()
    if scope == "hue_presets":
        return "hue_presets"
    if scope in ("timers_types", "auto_off_metadata", "product_types"):
        return "timers_types"
    return "full"


def reload_alert_in_progress(scope_key: str) -> str:
    row = RELOAD_ALERT_COPY.get(scope_key) or RELOAD_ALERT_COPY["full"]
    return row["in_progress"]


def reload_alert_complete(scope_key: str) -> str:
    row = RELOAD_ALERT_COPY.get(scope_key) or RELOAD_ALERT_COPY["full"]
    return row["complete"]


def reload_alert_failed(scope_key: str, err: str) -> str:
    row = RELOAD_ALERT_COPY.get(scope_key) or RELOAD_ALERT_COPY["full"]
    return f"{row['failed_prefix']}{err}"
