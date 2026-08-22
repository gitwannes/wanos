# --- file: core/rules_activation_pending.py ---
"""B23: track automation/event YAML writes pending scoped engine reload."""

from __future__ import annotations

from typing import Any, Dict, List

from core.models import SystemAdminState


def _empty_pending() -> Dict[str, Any]:
    return {
        "count": 0,
        "rule_ids": [],
        "event_ids": [],
        "needs_automations": False,
        "needs_events": False,
    }


def pending_snapshot(system: SystemAdminState) -> Dict[str, Any]:
    """Return ``rules_activation_pending`` dict for API / state snapshots."""
    raw = getattr(system, "rules_activation_pending", None)
    if not isinstance(raw, dict):
        return _empty_pending()
    rule_ids = [str(x) for x in (raw.get("rule_ids") or []) if str(x).strip()]
    event_ids = [str(x) for x in (raw.get("event_ids") or []) if str(x).strip()]
    count = len(rule_ids) + len(event_ids)
    needs_automations = bool(raw.get("needs_automations")) or bool(rule_ids)
    needs_events = bool(raw.get("needs_events")) or bool(event_ids)
    return {
        "count": count,
        "rule_ids": rule_ids,
        "event_ids": event_ids,
        "needs_automations": needs_automations,
        "needs_events": needs_events,
    }


def sync_pending_count(system: SystemAdminState) -> None:
    """Recompute count + needs_* flags from id lists."""
    snap = pending_snapshot(system)
    system.rules_activation_pending = snap


def ensure_pending(system: SystemAdminState) -> Dict[str, Any]:
    if not isinstance(getattr(system, "rules_activation_pending", None), dict):
        system.rules_activation_pending = _empty_pending()
    return system.rules_activation_pending


def mark_rule_pending(system: SystemAdminState, rule_id: str) -> None:
    rid = str(rule_id or "").strip()
    if not rid:
        return
    pending = ensure_pending(system)
    ids: List[str] = list(pending.get("rule_ids") or [])
    if rid not in ids:
        ids.append(rid)
    pending["rule_ids"] = ids
    pending["needs_automations"] = True
    sync_pending_count(system)


def unmark_rule_pending(system: SystemAdminState, rule_id: str) -> None:
    """Drop rule id from pending queue (e.g. delete disabled draft — no reload needed)."""
    rid = str(rule_id or "").strip()
    if not rid:
        return
    pending = ensure_pending(system)
    ids = [str(x) for x in (pending.get("rule_ids") or []) if str(x) != rid]
    pending["rule_ids"] = ids
    if not ids:
        pending["needs_automations"] = False
    sync_pending_count(system)


def mark_event_pending(system: SystemAdminState, event_id: str) -> None:
    eid = str(event_id or "").strip()
    if not eid:
        return
    pending = ensure_pending(system)
    ids: List[str] = list(pending.get("event_ids") or [])
    if eid not in ids:
        ids.append(eid)
    pending["event_ids"] = ids
    pending["needs_events"] = True
    sync_pending_count(system)


def mark_rule_pending_on_manager(manager: Any, rule_id: str) -> None:
    mark_rule_pending(manager._state.system, rule_id)
    with manager._api_state_cache_lock:
        manager._api_state_cache = None


def unmark_rule_pending_on_manager(manager: Any, rule_id: str) -> None:
    unmark_rule_pending(manager._state.system, rule_id)
    with manager._api_state_cache_lock:
        manager._api_state_cache = None


def mark_event_pending_on_manager(manager: Any, event_id: str) -> None:
    mark_event_pending(manager._state.system, event_id)
    with manager._api_state_cache_lock:
        manager._api_state_cache = None


def clear_pending(system: SystemAdminState) -> None:
    system.rules_activation_pending = _empty_pending()


def clear_pending_on_manager(manager: Any) -> None:
    clear_pending(manager._state.system)
    with manager._api_state_cache_lock:
        manager._api_state_cache = None


def activation_scopes(system: SystemAdminState) -> List[str]:
    """Scopes required for ``POST /api/automations/activate``."""
    snap = pending_snapshot(system)
    scopes: List[str] = []
    if snap.get("needs_automations"):
        scopes.append("automations")
    if snap.get("needs_events"):
        scopes.append("events")
    return scopes
