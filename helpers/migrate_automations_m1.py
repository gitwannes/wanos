# WanOS Blocky M1 migration helper (human-run)
#
# Purpose:
# - Backfill stable `id:` on automation rules missing ids.
# - Merge exactly one ON + one OFF sibling per trigger key into a single Y1 branched rule:
#     trigger: {entity_id: ...}
#     on:  {conditions: ..., actions: ...}
#     off: {conditions: ..., actions: ...}
#
# - Also merges event-family ON/OFF pairs based on the explicit family map:
#     trigger: {event: <family>}
#
# - Leaves SYNC rules and multi-trigger rules (trigger as a list) untouched.
#
# Usage:
#   python3 helpers/migrate_automations_m1.py --dry-run
#   python3 helpers/migrate_automations_m1.py --write

from __future__ import annotations

import argparse
import uuid
import sys
from pathlib import Path
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

# Allow running this helper directly from the `helpers/` folder.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.automations_store import read_automations, write_automations


EVENT_FAMILY_TO_ON_OFF: Dict[str, Tuple[str, str]] = {
    "blinds": ("BLINDS_OPEN_TRIGGER", "BLINDS_CLOSE_TRIGGER"),
    "twilight_evening": ("TWILIGHT_EVENING_ON_TRIGGER", "TWILIGHT_EVENING_OFF_TRIGGER"),
    "twilight_morning": ("TWILIGHT_MORNING_ON_TRIGGER", "TWILIGHT_MORNING_OFF_TRIGGER"),
    "sauna": ("SAUNA_ON", "SAUNA_OFF"),
    "ir": ("IR_ON", "IR_OFF"),
    "cinema": ("SCENE_CINEMA_ON", "SCENE_CINEMA_OFF"),
}


def _as_trigger(rule: Dict[str, Any]) -> Optional[dict]:
    t = rule.get("trigger")
    if isinstance(t, dict):
        return t
    # Allow `trigger:` to be stored as a 1-element list (common YAML style)
    # without treating it as OR logic.
    if isinstance(t, list) and len(t) == 1 and isinstance(t[0], dict):
        return t[0]
    return None


def _has_on_off(rule: Dict[str, Any]) -> bool:
    return ("on" in rule) or ("off" in rule)


def _ensure_rule_id(rule: Dict[str, Any]) -> str:
    rid = rule.get("id")
    if rid:
        return str(rid)
    new_id = str(uuid.uuid4())
    rule["id"] = new_id
    return new_id


def _branch_from_flat(conditions: Any, actions: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"actions": actions or []}
    if conditions is not None:
        out["conditions"] = conditions
    return out


def migrate_m1(rules_in: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns:
      (rules_out, report)
    """
    rules = deepcopy(rules_in)

    # 1) Backfill ids for any rule missing id (including SYNC and multi-trigger rules).
    missing_id_count = 0
    for r in rules:
        if isinstance(r, dict) and not r.get("id"):
            missing_id_count += 1
            _ensure_rule_id(r)

    # Index candidates for device ON/OFF merges:
    on_by_eid: Dict[str, List[int]] = {}
    off_by_eid: Dict[str, List[int]] = {}

    # Index candidates for event-family merges:
    on_by_family: Dict[str, List[int]] = {}
    off_by_family: Dict[str, List[int]] = {}

    # Track which rule indexes should be merged/replaced:
    idx_to_merge_into: Dict[int, str] = {}

    # Precompute reverse mapping for event keys -> (family, edge)
    event_key_to_family_edge: Dict[str, Tuple[str, str]] = {}
    for fam, (on_key, off_key) in EVENT_FAMILY_TO_ON_OFF.items():
        event_key_to_family_edge[on_key] = (fam, "on")
        event_key_to_family_edge[off_key] = (fam, "off")

    for idx, r in enumerate(rules):
        if not isinstance(r, dict):
            continue
        if _has_on_off(r):
            continue  # already Y1 branched; do not auto-remerge

        trig = _as_trigger(r)
        if trig is None:
            continue  # multi-trigger rules (trigger as list) are left untouched

        # Device trigger merge candidates:
        eid = trig.get("entity_id")
        state = trig.get("state")
        if eid and isinstance(state, str) and state in ("ON", "OFF"):
            if state == "ON":
                on_by_eid.setdefault(eid, []).append(idx)
            else:
                off_by_eid.setdefault(eid, []).append(idx)
            continue

        # Event trigger merge candidates:
        ev = trig.get("event")
        if ev and isinstance(ev, str) and ev in event_key_to_family_edge:
            fam, edge = event_key_to_family_edge[ev]
            if edge == "on":
                on_by_family.setdefault(fam, []).append(idx)
            else:
                off_by_family.setdefault(fam, []).append(idx)
            continue

    merges: List[Dict[str, Any]] = []
    used_rule_indexes: set[int] = set()

    # 2) Merge eligible device pairs:
    for eid, on_idxs in on_by_eid.items():
        off_idxs = off_by_eid.get(eid, [])
        if len(on_idxs) != 1 or len(off_idxs) != 1:
            continue

        on_idx = on_idxs[0]
        off_idx = off_idxs[0]
        if on_idx in used_rule_indexes or off_idx in used_rule_indexes:
            continue

        on_rule = rules[on_idx]
        off_rule = rules[off_idx]

        # Do not merge if either is SYNC style (defensive; should not happen due state filter).
        on_state = _as_trigger(on_rule).get("state") if _as_trigger(on_rule) else None
        off_state = _as_trigger(off_rule).get("state") if _as_trigger(off_rule) else None
        if on_state == "SYNC" or off_state == "SYNC":
            continue

        # Create branched parent rule:
        parent_id = on_rule.get("id") or off_rule.get("id") or str(uuid.uuid4())
        parent_name = on_rule.get("name") or off_rule.get("name") or f"automation_{eid}"
        parent_scene = bool(on_rule.get("scene", False)) or bool(off_rule.get("scene", False))
        parent_require_confirmation = bool(on_rule.get("require_confirmation", False)) or bool(
            off_rule.get("require_confirmation", False)
        )

        branched_rule: Dict[str, Any] = {
            "id": parent_id,
            "name": parent_name,
            "scene": parent_scene,
            "require_confirmation": parent_require_confirmation,
            "trigger": {"entity_id": eid},
            "on": _branch_from_flat(on_rule.get("conditions"), on_rule.get("actions")),
            "off": _branch_from_flat(off_rule.get("conditions"), off_rule.get("actions")),
        }

        used_rule_indexes.add(on_idx)
        used_rule_indexes.add(off_idx)
        merges.append({"type": "device", "eid": eid, "on_idx": on_idx, "off_idx": off_idx})
        rules[on_idx] = branched_rule
        rules[off_idx] = None  # placeholder removed later

    # 3) Merge eligible event-family pairs:
    for fam, on_idxs in on_by_family.items():
        off_idxs = off_by_family.get(fam, [])
        if len(on_idxs) != 1 or len(off_idxs) != 1:
            continue

        on_idx = on_idxs[0]
        off_idx = off_idxs[0]
        if on_idx in used_rule_indexes or off_idx in used_rule_indexes:
            continue

        on_rule = rules[on_idx]
        off_rule = rules[off_idx]

        parent_id = on_rule.get("id") or off_rule.get("id") or str(uuid.uuid4())
        parent_name = on_rule.get("name") or off_rule.get("name") or f"automation_{fam}"
        parent_scene = bool(on_rule.get("scene", False)) or bool(off_rule.get("scene", False))
        parent_require_confirmation = bool(on_rule.get("require_confirmation", False)) or bool(
            off_rule.get("require_confirmation", False)
        )

        branched_rule = {
            "id": parent_id,
            "name": parent_name,
            "scene": parent_scene,
            "require_confirmation": parent_require_confirmation,
            "trigger": {"event": fam},
            "on": _branch_from_flat(on_rule.get("conditions"), on_rule.get("actions")),
            "off": _branch_from_flat(off_rule.get("conditions"), off_rule.get("actions")),
        }

        used_rule_indexes.add(on_idx)
        used_rule_indexes.add(off_idx)
        merges.append({"type": "event_family", "family": fam, "on_idx": on_idx, "off_idx": off_idx})
        rules[on_idx] = branched_rule
        rules[off_idx] = None

    # 4) Finalize list: remove None placeholders, keep original order as much as possible.
    rules_out: List[Dict[str, Any]] = [r for r in rules if isinstance(r, dict)]

    report = {
        "missing_id_count": missing_id_count,
        "merge_count": len(merges),
        "merges": merges,
        "rule_count_in": len(rules_in),
        "rule_count_out": len(rules_out),
    }
    return rules_out, report


def main() -> None:
    parser = argparse.ArgumentParser(description="WanOS Blocky M1 migration helper")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write")
    parser.add_argument("--write", action="store_true", help="Write changes to automations.auto.yaml")
    args = parser.parse_args()

    if not args.dry_run and not args.write:
        raise SystemExit("Pass --dry-run or --write")

    rules = read_automations()
    rules_out, report = migrate_m1(rules)

    if args.dry_run:
        print("=== M1 migration DRY-RUN ===")
        print(f"Missing ids backfilled: {report['missing_id_count']}")
        print(f"Merges eligible & applied: {report['merge_count']}")
        for m in report["merges"]:
            print(f"- {m}")
        print(f"Rules in/out: {report['rule_count_in']} -> {report['rule_count_out']}")
        print("No file written (dry-run).")
        return

    # Write
    write_automations(rules_out)
    print("=== M1 migration WRITE ===")
    print(f"Wrote automations.auto.yaml. Merges applied: {report['merge_count']}")


if __name__ == "__main__":
    main()

