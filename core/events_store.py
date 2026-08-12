# --- file: core/events_store.py ---
"""Surgical read/write of events: catalog in automations.auto.yaml (B10B)."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from core.automations_store import _dump_root, _to_commented, load_automations_roundtrip, read_automations
from core.event_catalog import (
    SYSTEM_KEY_TO_UUID,
    SYSTEM_UUID_TO_KEY,
    SYSTEM_UUID_TO_NAME,
    is_blocky_pickable_event_id,
    normalize_event_name_key,
    system_seeds_for_yaml,
)

EVENTS_KEY = "events"


def _as_event_list(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict) and row.get("id"):
            out.append(dict(row))
    return out


def read_events() -> List[Dict[str, Any]]:
    """Return events: rows from disk (may be empty before migrate/merge)."""
    root, _ = load_automations_roundtrip()
    return _as_event_list(root.get(EVENTS_KEY)) if isinstance(root, dict) else []


def events_by_id_from_root(root: Any) -> Dict[str, Dict[str, Any]]:
    """Build id→event row map from an already-loaded automations.auto.yaml root."""
    if not isinstance(root, dict):
        return {}
    return {str(e["id"]): e for e in _as_event_list(root.get(EVENTS_KEY)) if e.get("id")}


def events_by_id() -> Dict[str, Dict[str, Any]]:
    root, _ = load_automations_roundtrip()
    return events_by_id_from_root(root)


def find_event(event_id: str) -> Optional[Dict[str, Any]]:
    return events_by_id().get(str(event_id))


def rule_display_name(rule: Dict[str, Any]) -> str:
    """
    Display name for a rule in usages / delete-blocked messages.

    System rules (SR): always the companion SE catalog name (never drifted YAML
    free-text). User rules: YAML ``name`` (or id fallback).
    """
    trig = rule.get("trigger")
    eid = ""
    if isinstance(trig, dict) and trig.get("event"):
        eid = str(trig["event"])
    elif isinstance(trig, list):
        for t in trig:
            if isinstance(t, dict) and t.get("event") and not t.get("entity_id"):
                eid = str(t["event"])
                break
    if eid and eid in SYSTEM_UUID_TO_KEY:
        cat = find_event(eid)
        if isinstance(cat, dict) and cat.get("name"):
            return str(cat["name"]).strip()
        seed = str(SYSTEM_UUID_TO_NAME.get(eid) or "").strip()
        if seed:
            return seed
    return str(rule.get("name") or rule.get("id") or "?")


def _ordered_event_row(row: Dict[str, Any]) -> CommentedMap:
    """Stable key order for YAML readability."""
    ordered = CommentedMap()
    for key in (
        "id",
        "name",
        "origin",
        "show_on_dashboard",
        "require_confirmation",
        "enabled",
    ):
        if key in row:
            ordered[key] = row[key]
    for k, v in row.items():
        if k not in ordered and not str(k).startswith("_"):
            ordered[k] = v
    return ordered


def _write_events_list(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")

    seq = CommentedSeq()
    for row in rows:
        seq.append(_ordered_event_row(dict(row)))

    if EVENTS_KEY in root:
        root[EVENTS_KEY] = seq
    else:
        # Insert events: before automations when possible
        new_root = CommentedMap()
        inserted = False
        for k, v in root.items():
            if not inserted and k == "automations":
                new_root[EVENTS_KEY] = seq
                inserted = True
            new_root[k] = v
        if not inserted:
            new_root[EVENTS_KEY] = seq
        root = new_root

    _dump_root(root, path)
    return [dict(r) for r in rows]


def name_clash(name: str, exclude_id: Optional[str] = None) -> Optional[str]:
    """Return conflicting event id if name collides (trim+casefold), else None."""
    needle = normalize_event_name_key(name)
    if not needle:
        return "empty"
    for row in read_events():
        rid = str(row.get("id") or "")
        if exclude_id and rid == exclude_id:
            continue
        if normalize_event_name_key(str(row.get("name") or "")) == needle:
            return rid
    return None


def merge_system_seeds_into_yaml() -> List[Dict[str, Any]]:
    """
    Y1 boot/migrate merge:
    - insert missing system ids
    - on existing system rows: force name/origin/confirm/enabled;
      B10E: force show_on_dashboard false (system never on Explorer)
    - leave user rows untouched (except confirm coerced when dashboard off — see update_event)
    """
    current = read_events()
    by_id = {str(r["id"]): dict(r) for r in current if r.get("id")}
    seeds = system_seeds_for_yaml()

    for seed in seeds:
        eid = str(seed["id"])
        if eid in by_id:
            by_id[eid] = {
                "id": eid,
                "name": seed["name"],
                "origin": "system",
                # B10E: system events never appear on Explorer
                "show_on_dashboard": False,
                "require_confirmation": False,
                "enabled": True,
            }
        else:
            by_id[eid] = dict(seed)

    # Preserve user rows; system seeds first (stable seed order) then users
    seed_ids = [str(s["id"]) for s in seeds]
    ordered: List[Dict[str, Any]] = [by_id[i] for i in seed_ids if i in by_id]
    for eid, row in by_id.items():
        if eid in seed_ids:
            continue
        # Coerce stranded confirm without dashboard (B10E invariant)
        if str(row.get("origin") or "user") == "user":
            if not bool(row.get("show_on_dashboard")) and bool(row.get("require_confirmation")):
                row = dict(row)
                row["require_confirmation"] = False
                by_id[eid] = row
        ordered.append(by_id[eid])

    written = _write_events_list(ordered)
    # After SE catalog names are authoritative, rewrite any drifted SR titles.
    sync_system_rule_names_to_catalog()
    return written


def sync_system_rule_names_to_catalog() -> int:
    """
    B10F: SR ``name`` must equal companion SE catalog name.

    Walks ``automations:`` in place (preserves sibling comments) and overwrites
    drifted free-text titles. Returns how many rules were renamed.
    """
    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        return 0
    seq = root.get("automations")
    if not isinstance(seq, list):
        return 0

    renamed = 0
    for rule in seq:
        if not isinstance(rule, dict):
            continue
        trig = rule.get("trigger")
        eid = ""
        if isinstance(trig, dict) and trig.get("event") and not trig.get("entity_id"):
            eid = str(trig["event"])
        elif isinstance(trig, list):
            for t in trig:
                if isinstance(t, dict) and t.get("event") and not t.get("entity_id"):
                    eid = str(t["event"])
                    break
        if not eid or eid not in SYSTEM_UUID_TO_KEY:
            continue
        cat = find_event(eid)
        cat_name = ""
        if isinstance(cat, dict) and cat.get("name"):
            cat_name = str(cat["name"]).strip()
        if not cat_name:
            cat_name = str(SYSTEM_UUID_TO_NAME.get(eid) or "").strip()
        if not cat_name:
            continue
        if str(rule.get("name") or "").strip() != cat_name:
            rule["name"] = cat_name
            renamed += 1

    if renamed:
        _dump_root(root, path)
    return renamed


def create_user_event(
    name: str,
    *,
    show_on_dashboard: bool = False,
    require_confirmation: bool = False,
    enabled: bool = True,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("Event name is required.")
    clash = name_clash(cleaned)
    if clash == "empty":
        raise ValueError("Event name is required.")
    if clash:
        raise ValueError(f"Event name already in use (id={clash}).")

    row = {
        "id": event_id or str(uuid.uuid4()),
        "name": cleaned,
        "origin": "user",
        "show_on_dashboard": bool(show_on_dashboard),
        # B10E: confirm only valid with explorer/dashboard
        "require_confirmation": bool(require_confirmation) if show_on_dashboard else False,
        "enabled": bool(enabled),
    }
    rows = read_events()
    if any(str(r.get("id")) == row["id"] for r in rows):
        raise ValueError(f"Duplicate event id '{row['id']}'.")
    rows.append(row)
    _write_events_list(rows)
    return row


def update_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    PUT replace by id.
    System (B10E): no field edits from API — identity forced from constants;
      show_on_dashboard always false (reject attempts to set true).
    User: name/show/confirm/enabled; confirm coerced off when dashboard off.
    """
    eid = str(row.get("id") or "").strip()
    if not eid:
        raise ValueError("PUT requires event id.")

    rows = read_events()
    idx = next((i for i, r in enumerate(rows) if str(r.get("id")) == eid), None)
    if idx is None:
        raise KeyError(f"Event id '{eid}' not found.")

    existing = dict(rows[idx])
    origin = str(existing.get("origin") or "user")

    if origin == "system" or eid in SYSTEM_UUID_TO_KEY:
        if row.get("show_on_dashboard") is True:
            raise ValueError("System events cannot appear on the Explorer dashboard.")
        updated = dict(existing)
        key = SYSTEM_UUID_TO_KEY.get(eid)
        if key:
            from core.event_catalog import SYSTEM_KEY_TO_NAME

            updated["name"] = SYSTEM_KEY_TO_NAME[key]
        updated["origin"] = "system"
        updated["show_on_dashboard"] = False
        updated["require_confirmation"] = False
        updated["enabled"] = True
        rows[idx] = updated
        _write_events_list(rows)
        return updated

    # User event
    cleaned = str(row.get("name", existing.get("name")) or "").strip()
    if not cleaned:
        raise ValueError("Event name is required.")
    clash = name_clash(cleaned, exclude_id=eid)
    if clash and clash != "empty":
        raise ValueError(f"Event name already in use (id={clash}).")

    show = bool(row.get("show_on_dashboard", existing.get("show_on_dashboard", False)))
    confirm = bool(row.get("require_confirmation", existing.get("require_confirmation", False)))
    if not show:
        confirm = False
    if confirm and not show:
        raise ValueError("Require confirmation needs Appear on explorer.")

    # Disable guard (both directions): cannot disable a user event while any
    # automation still *listens* (When user event trigger) OR *fires* it
    # (Fire user event action). Listeners alone used to slip through — e.g.
    # disable "cinema ON" (E) while a U rule still triggers on it — leaving a
    # dead catalog target. Fire-refs must also block so Fire-user-event actions
    # cannot target a disabled E (same as "all off overall").
    enabled = bool(row.get("enabled", existing.get("enabled", True)))
    if not enabled and bool(existing.get("enabled", True)):
        refs = rule_refs_to_event(eid)
        if refs:
            raise ValueError(
                "Cannot disable: referenced by automation rule(s): "
                + ", ".join(refs)
            )

    updated = {
        "id": eid,
        "name": cleaned,
        "origin": "user",
        "show_on_dashboard": show,
        "require_confirmation": confirm,
        "enabled": enabled,
    }
    rows[idx] = updated
    _write_events_list(rows)
    return updated


def delete_event(event_id: str) -> None:
    """
    Delete user event only, with guards:
    - system → reject
    - show_on_dashboard → reject
    - referenced as rule trigger or fire-action → reject
    """
    eid = str(event_id).strip()
    rows = read_events()
    target = next((r for r in rows if str(r.get("id")) == eid), None)
    if target is None:
        raise KeyError(f"Event id '{eid}' not found.")
    if str(target.get("origin")) == "system" or eid in SYSTEM_UUID_TO_KEY:
        raise ValueError("System events cannot be deleted.")
    if bool(target.get("show_on_dashboard")):
        raise ValueError("Cannot delete an event shown on the dashboard.")

    refs = rule_refs_to_event(eid)
    if refs:
        raise ValueError(
            f"Event is used by automation rule(s): {', '.join(refs)}. Remove those refs first."
        )

    new_rows = [r for r in rows if str(r.get("id")) != eid]
    _write_events_list(new_rows)


def rule_refs_to_event(event_id: str) -> List[str]:
    """Return rule names that trigger on or fire this event id."""
    eid = str(event_id)
    hits: List[str] = []
    for rule in read_automations():
        if not isinstance(rule, dict):
            continue
        if _rule_references_event(rule, eid):
            hits.append(rule_display_name(rule))
    return hits


def rule_fire_refs_to_event(event_id: str) -> List[str]:
    """Return rule names that fire this event as an action (not merely trigger)."""
    eid = str(event_id)
    hits: List[str] = []
    for rule in read_automations():
        if not isinstance(rule, dict):
            continue
        if _rule_fires_event(rule, eid):
            hits.append(rule_display_name(rule))
    return hits


def rule_trigger_refs_to_event(event_id: str) -> List[str]:
    """Return rule names whose trigger listens to this event id."""
    eid = str(event_id)
    hits: List[str] = []
    for rule in read_automations():
        if not isinstance(rule, dict):
            continue
        if _trigger_has_event(rule.get("trigger"), eid):
            hits.append(rule_display_name(rule))
    return hits


def _rule_fires_event(rule: Dict[str, Any], event_id: str) -> bool:
    for case in rule.get("cases") or []:
        if not isinstance(case, dict):
            continue
        for action in case.get("actions") or []:
            if isinstance(action, dict) and str(action.get("event") or "") == event_id:
                return True
    for branch_key in ("on", "off"):
        branch = rule.get(branch_key)
        if not isinstance(branch, dict):
            continue
        for action in branch.get("actions") or []:
            if isinstance(action, dict) and str(action.get("event") or "") == event_id:
                return True
    return False


def count_system_event_listeners(event_id: str, *, exclude_rule_id: Optional[str] = None) -> int:
    """How many rules listen to this system event (B10E: max one)."""
    eid = str(event_id)
    n = 0
    for rule in read_automations():
        if not isinstance(rule, dict):
            continue
        rid = str(rule.get("id") or "")
        if exclude_rule_id and rid == exclude_rule_id:
            continue
        if _trigger_has_event(rule.get("trigger"), eid):
            n += 1
    return n


def _rule_references_event(rule: Dict[str, Any], event_id: str) -> bool:
    trig = rule.get("trigger")
    if _trigger_has_event(trig, event_id):
        return True
    for case in rule.get("cases") or []:
        if not isinstance(case, dict):
            continue
        for action in case.get("actions") or []:
            if isinstance(action, dict) and str(action.get("event") or "") == event_id:
                return True
    # Legacy on/off branches if still present
    for branch_key in ("on", "off"):
        branch = rule.get(branch_key)
        if not isinstance(branch, dict):
            continue
        for action in branch.get("actions") or []:
            if isinstance(action, dict) and str(action.get("event") or "") == event_id:
                return True
    return False


def _trigger_has_event(trig: Any, event_id: str) -> bool:
    if isinstance(trig, dict):
        return str(trig.get("event") or "") == event_id
    if isinstance(trig, list):
        return any(isinstance(t, dict) and str(t.get("event") or "") == event_id for t in trig)
    return False


def enabled_listener_rule_ids(event_id: str) -> List[str]:
    """Rule ids that listen to event_id and are enabled (default true)."""
    eid = str(event_id)
    out: List[str] = []
    for rule in read_automations():
        if not isinstance(rule, dict):
            continue
        if rule.get("enabled", True) is False:
            continue
        if _trigger_has_event(rule.get("trigger"), eid):
            rid = str(rule.get("id") or "")
            if rid:
                out.append(rid)
    return out


def build_dashboard_events() -> List[Dict[str, Any]]:
    """
    Explorer dashboard buttons (B10E: user events only):
    show_on_dashboard ∧ enabled ∧ ≥1 enabled listener rule.
    """
    out: List[Dict[str, Any]] = []
    for row in read_events():
        eid = str(row.get("id") or "")
        if not eid:
            continue
        origin = str(row.get("origin") or "user")
        # System never on Explorer
        if origin == "system" or eid in SYSTEM_UUID_TO_KEY:
            continue
        if not bool(row.get("show_on_dashboard")):
            continue
        if row.get("enabled", True) is False:
            continue
        # Confirm without dashboard is invalid — treat as no confirm
        confirm = bool(row.get("require_confirmation", False)) and bool(row.get("show_on_dashboard"))
        if not enabled_listener_rule_ids(eid):
            continue
        out.append(
            {
                "id": eid,
                "name": str(row.get("name") or eid),
                "require_confirmation": confirm,
            }
        )
    out.sort(key=lambda r: normalize_event_name_key(r["name"]))
    return out


def pickable_events_for_blocky(*, for_fire: bool = False) -> List[Dict[str, Any]]:
    """
    Blockly pickers.
    Trigger (for_fire=False): all pickable system + enabled user.
    Fire (for_fire=True): enabled user + system that either has a listener or is
    in FIRE_ALWAYS_SYSTEM_UUIDS (Sauna/IR ON/OFF).
    """
    from core.event_catalog import FIRE_ALWAYS_SYSTEM_UUIDS

    out: List[Dict[str, Any]] = []
    for row in read_events():
        eid = str(row.get("id") or "")
        if not eid or not is_blocky_pickable_event_id(eid):
            continue
        origin = str(row.get("origin") or "user")
        if origin == "user" and row.get("enabled", True) is False:
            continue
        if for_fire and origin == "system":
            if eid not in FIRE_ALWAYS_SYSTEM_UUIDS and not enabled_listener_rule_ids(eid):
                continue
        out.append(
            {
                "id": str(row.get("id")),
                "name": str(row.get("name") or row.get("id")),
                "origin": origin,
                "show_on_dashboard": bool(row.get("show_on_dashboard", False)),
                "require_confirmation": bool(row.get("require_confirmation", False)),
                "enabled": bool(row.get("enabled", True)),
            }
        )
    out.sort(key=lambda r: normalize_event_name_key(r["name"]))
    return out
