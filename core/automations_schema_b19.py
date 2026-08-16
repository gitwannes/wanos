# --- file: core/automations_schema_b19.py ---
"""
B19 / B13 — Domoticz-shaped branch authoring (If / Else-if / Else).

On-disk: ``branches`` (no authoring ``trigger``). Wake is derived at runtime from
device/event Compares in any branch. Legacy ``trigger``+``cases`` is migrator input
and cutover-window engine expand only — API writes reject it.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from core.automations_schema_v2 import (
    _copy_action,
    _copy_condition,
    is_v2_rule,
    legacy_to_v2,
    ordered_v2_dict,
)

# Canonical dump order: name first … id last.
_B19_KEY_ORDER = (
    "name",
    "enabled",
    "branches",
    "id",
)

_WHEN_IF = "if"
_WHEN_ELIF = "else_if"
_WHEN_ELSE = "else"
_VALID_WHEN = frozenset({_WHEN_IF, _WHEN_ELIF, _WHEN_ELSE})


def is_branch_rule(rule: Any) -> bool:
    """True when rule uses B19 ``branches`` authoring shape."""
    return isinstance(rule, dict) and isinstance(rule.get("branches"), list)


def is_legacy_cases_rule(rule: Any) -> bool:
    """True when rule still has v2 ``trigger``+``cases`` (pre-B19)."""
    return isinstance(rule, dict) and isinstance(rule.get("cases"), list) and not is_branch_rule(rule)


def ordered_branch_dict(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Emit canonical key order for YAML/API dumps."""
    out: Dict[str, Any] = {}
    for key in _B19_KEY_ORDER:
        if key in rule and rule[key] is not None:
            out[key] = rule[key]
    for key, val in rule.items():
        if key not in out and val is not None:
            out[key] = val
    return out


def _normalize_branch(branch: Any, *, index: int) -> Dict[str, Any]:
    if not isinstance(branch, dict):
        raise ValueError(f"Branch {index}: must be a mapping.")
    when = str(branch.get("when") or "").strip()
    if when not in _VALID_WHEN:
        raise ValueError(f"Branch {index}: when must be if|else_if|else (got {when!r}).")
    conds_in = branch.get("conditions") or []
    if not isinstance(conds_in, list):
        conds_in = []
    acts_in = branch.get("actions") or []
    if not isinstance(acts_in, list):
        acts_in = []
    out: Dict[str, Any] = {
        "when": when,
        "conditions": [_copy_condition(c) for c in conds_in],
        "actions": [_copy_action(a) for a in acts_in],
    }
    label = branch.get("label")
    if label not in (None, ""):
        out["label"] = str(label)
    return out


def normalize_branch_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one B19 rule; does not enforce enable-validity (API does)."""
    branches_in = rule.get("branches") or []
    if not isinstance(branches_in, list) or not branches_in:
        raise ValueError("Automation must contain at least one branch.")
    branches = [_normalize_branch(b, index=i) for i, b in enumerate(branches_in)]
    # Structural: first must be if; else only last; else_if only after if.
    if branches[0]["when"] != _WHEN_IF:
        raise ValueError("First branch must be when: if.")
    for i, b in enumerate(branches):
        if b["when"] == _WHEN_ELSE and i != len(branches) - 1:
            raise ValueError("when: else is only allowed as the last branch.")
        if b["when"] == _WHEN_IF and i != 0:
            raise ValueError("Only the first branch may be when: if (use else_if).")
    out = {
        "name": rule.get("name") or "",
        "enabled": bool(rule.get("enabled", True)),
        "branches": branches,
        "id": rule.get("id"),
    }
    # Drop legacy keys if present on write normalize.
    return ordered_branch_dict(out)


def iter_branch_conditions(rule: Dict[str, Any]):
    """Yield condition dicts from all branches."""
    for br in rule.get("branches") or []:
        if not isinstance(br, dict):
            continue
        for c in br.get("conditions") or []:
            if isinstance(c, dict):
                yield c


def iter_branch_actions(rule: Dict[str, Any]):
    """Yield action dicts from all branches."""
    for br in rule.get("branches") or []:
        if not isinstance(br, dict):
            continue
        for a in br.get("actions") or []:
            if isinstance(a, dict):
                yield a


def derive_wake_entity_ids(rule: Dict[str, Any]) -> List[str]:
    """Device entity_ids mentioned in device_state Compares (any branch)."""
    out: List[str] = []
    seen = set()
    for c in iter_branch_conditions(rule):
        if c.get("type") != "device_state":
            continue
        eid = str(c.get("entity_id") or "").strip()
        if eid and eid not in seen:
            seen.add(eid)
            out.append(eid)
    return out


def derive_wake_event_ids(rule: Dict[str, Any]) -> List[str]:
    """Catalog event UUIDs mentioned in event Compares (any branch)."""
    out: List[str] = []
    seen = set()
    for c in iter_branch_conditions(rule):
        if c.get("type") != "event":
            continue
        eid = str(c.get("event") or "").strip()
        if eid and eid not in seen:
            seen.add(eid)
            out.append(eid)
    return out


def primary_event_id_from_rule(rule: Dict[str, Any]) -> Optional[str]:
    """First event UUID for SR/UR helpers — branches or legacy trigger."""
    if is_branch_rule(rule):
        evs = derive_wake_event_ids(rule)
        return evs[0] if evs else None
    trig = rule.get("trigger")
    if isinstance(trig, dict) and trig.get("event"):
        return str(trig["event"])
    if isinstance(trig, list):
        for t in trig:
            if isinstance(t, dict) and t.get("event"):
                return str(t["event"])
    return None


def wake_summary_labels(rule: Dict[str, Any]) -> List[str]:
    """Read-only Library wake chips: entity_ids + event UUIDs (caller may resolve names)."""
    return derive_wake_entity_ids(rule) + derive_wake_event_ids(rule)


def validate_branch_rule_for_enable(rule: Dict[str, Any]) -> Optional[str]:
    """
    Return error message if rule cannot be enabled; None if valid.

    Locked: one if root; every if/else_if has ≥1 Compare; else optional; Do may be empty.
    """
    try:
        norm = normalize_branch_rule(rule)
    except ValueError as exc:
        return str(exc)
    for i, br in enumerate(norm["branches"]):
        when = br["when"]
        conds = br.get("conditions") or []
        if when in (_WHEN_IF, _WHEN_ELIF) and not conds:
            return f"Branch {i} ({when}): at least one Compare is required."
        for j, c in enumerate(conds):
            ctype = str(c.get("type") or "")
            if ctype == "device_state":
                if not c.get("entity_id"):
                    return f"Branch {i} condition {j}: device Compare needs entity_id."
                if c.get("is") is None and c.get("op") is None:
                    return f"Branch {i} condition {j}: device Compare needs is/op."
            elif ctype == "event":
                if not c.get("event"):
                    return f"Branch {i} condition {j}: event Compare needs event id."
            elif ctype == "time_of_day":
                if c.get("is") not in ("dark", "light"):
                    return f"Branch {i} condition {j}: time Compare must be dark|light."
            else:
                return f"Branch {i} condition {j}: unknown Compare type {ctype!r}."
    return None


def validate_branch_entity_ids(rule: Dict[str, Any]) -> None:
    """Reuse v2 entity_id validation over branch conditions/actions."""
    from core.automations_schema_v2 import validate_v2_entity_ids

    # Build a synthetic v2 shell so existing deny/idx checks apply.
    cases = []
    for br in rule.get("branches") or []:
        if not isinstance(br, dict):
            continue
        cases.append({
            "conditions": br.get("conditions") or [],
            "actions": br.get("actions") or [],
        })
    validate_v2_entity_ids({
        "name": rule.get("name"),
        "trigger": {},
        "cases": cases,
        "id": rule.get("id"),
    })


def _case_has_discrete_to_state(case: Dict[str, Any]) -> bool:
    """True when case has a discrete edge matcher (ON/OFF/OPEN/CLOSED)."""
    ts = case.get("to_state")
    if ts is None or ts == "":
        return False
    return str(ts).upper() in ("ON", "OFF", "OPEN", "CLOSED")


def _cases_need_split_for_first_match(cases: List[Dict[str, Any]], *, numeric_on_trigger: bool) -> bool:
    """
    True when first-match Else-if cannot preserve legacy “all matching cases run”.

    - Every case has discrete to_state (even duplicates like OFF/OFF) → Else-if chain OK.
    - Otherwise (always-run case + conditionals, event multi-case without edges) → split.
    """
    if len(cases) < 2 or numeric_on_trigger:
        return False
    if all(_case_has_discrete_to_state(c) for c in cases):
        return False
    return True


def _canonicalize_trigger(trigger: Any) -> Any:
    """Unwrap singleton trigger lists (YAML often uses a 1-item list, not true OR)."""
    if isinstance(trigger, list) and len(trigger) == 1:
        return trigger[0]
    return trigger


def _trigger_wake_conditions(trigger: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Build Compare list fragments from a legacy trigger.

    Returns (common_conds, error_or_none).
    Multi-edge OR-list → error (skip until H4). Singleton lists are unwrapped first.
    """
    trigger = _canonicalize_trigger(trigger)
    if isinstance(trigger, list):
        return [], "OR-list trigger (when any of) — skip until H4 / manual"
    if not isinstance(trigger, dict):
        return [], "missing trigger"
    if trigger.get("event"):
        return [{"type": "event", "event": str(trigger["event"])}], None
    eid = trigger.get("entity_id")
    if not eid:
        return [], "trigger has neither entity_id nor event"
    # Numeric / level threshold on When → device_state Compare with op.
    if trigger.get("op"):
        cond: Dict[str, Any] = {
            "type": "device_state",
            "entity_id": str(eid),
            "op": str(trigger["op"]),
            "is": trigger.get("state"),
        }
        if trigger.get("attribute"):
            cond["attribute"] = trigger["attribute"]
        return [cond], None
    # Discrete state on trigger (common in unwrapped OR-edge YAML) → Compare ON/OFF/…
    raw_st = trigger.get("state")
    if raw_st is not None and raw_st != "":
        st = str(raw_st).upper()
        if st in ("ON", "OFF", "OPEN", "CLOSED"):
            return [{"type": "device_state", "entity_id": str(eid), "is": st}], None
    # Plain device wake — per-case to_state becomes the Compare; ANY → is: ANY.
    return [], None


def convert_v2_rule_to_branches(rule: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
    """
    Convert one legacy v2 (or Y1 via legacy_to_v2) rule to B19.

    Returns (branch_rule | None, skip_reason | None, split_extra_rules).
    When non-exclusive multi-case cannot be first-match, splits into N rules
    (first returned as main, rest in split_extra_rules) with a report reason.
    """
    if is_branch_rule(rule):
        return ordered_branch_dict(normalize_branch_rule(rule)), None, []

    v2 = ordered_v2_dict(legacy_to_v2(dict(rule))) if not is_v2_rule(rule) else ordered_v2_dict(rule)
    if is_branch_rule(v2):
        return ordered_branch_dict(normalize_branch_rule(v2)), None, []

    # Unwrap singleton trigger lists before wake / skip decisions.
    v2 = dict(v2)
    v2["trigger"] = _canonicalize_trigger(v2.get("trigger"))

    cases = [c for c in (v2.get("cases") or []) if isinstance(c, dict)]
    if not cases:
        return None, "no cases", []

    wake_common, err = _trigger_wake_conditions(v2.get("trigger"))
    if err:
        return None, err, []

    trig = v2.get("trigger") if isinstance(v2.get("trigger"), dict) else {}
    device_eid = str(trig.get("entity_id") or "") if trig else ""
    numeric_on_trigger = bool(trig.get("op")) if trig else False
    # Edge already expressed in wake_common (unwrapped OR-edge with state on trigger).
    wake_has_device = any(
        isinstance(c, dict)
        and c.get("type") == "device_state"
        and str(c.get("entity_id") or "") == device_eid
        for c in wake_common
    )

    # Non-exclusive multi-case (e.g. always + conditional) → split rules.
    # Discrete to_state chains (incl. duplicate OFF/OFF like sauna) → Else-if, no split.
    if _cases_need_split_for_first_match(cases, numeric_on_trigger=numeric_on_trigger):
        split_rules: List[Dict[str, Any]] = []
        base_name = str(v2.get("name") or "rule")
        for i, case in enumerate(cases):
            one = copy.deepcopy(v2)
            one["cases"] = [case]
            if i > 0:
                one["name"] = f"{base_name} ({i + 1})"
                one["id"] = None  # caller assigns new ids
            br, skip, _extra = convert_v2_rule_to_branches(one)
            if skip or br is None:
                return None, skip or f"split case {i} failed", []
            split_rules.append(br)
        main = split_rules[0]
        return main, f"split into {len(split_rules)} rules (non-exclusive cases)", split_rules[1:]

    branches: List[Dict[str, Any]] = []
    for i, case in enumerate(cases):
        when = _WHEN_IF if i == 0 else _WHEN_ELIF
        conds: List[Dict[str, Any]] = [_copy_condition(c) for c in wake_common]
        # Per-case device edge from to_state (skip ANY if wake_common already has device Compare).
        to_state = case.get("to_state")
        if device_eid and not numeric_on_trigger:
            if to_state is None or to_state == "":
                if not wake_has_device:
                    conds.append({
                        "type": "device_state",
                        "entity_id": device_eid,
                        "is": "ANY",
                    })
            else:
                conds.append({
                    "type": "device_state",
                    "entity_id": device_eid,
                    "is": str(to_state).upper() if str(to_state).upper() in (
                        "ON", "OFF", "OPEN", "CLOSED"
                    ) else str(to_state),
                })
        for c in case.get("conditions") or []:
            if isinstance(c, dict):
                conds.append(_copy_condition(c))
        # Deduplicate exact wake_common re-copies already in case conditions — keep simple.
        acts = [_copy_action(a) for a in (case.get("actions") or []) if isinstance(a, dict)]
        br: Dict[str, Any] = {"when": when, "conditions": conds, "actions": acts}
        label = case.get("label")
        if label:
            br["label"] = str(label)
        elif to_state not in (None, ""):
            br["label"] = str(to_state).lower()
        branches.append(br)

    out = {
        "name": v2.get("name") or "",
        "enabled": bool(v2.get("enabled", True)),
        "branches": branches,
        "id": v2.get("id"),
    }
    try:
        return ordered_branch_dict(normalize_branch_rule(out)), None, []
    except ValueError as exc:
        return None, str(exc), []


def migrate_rules_to_branches(
    rules: List[Any],
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """
    Migrate a list of automation rules to B19 branches.

    Returns (new_list, report_lines, skipped_names).
    Idempotent: already-branch rules pass through.
    """
    import uuid as _uuid

    out: List[Dict[str, Any]] = []
    report: List[str] = []
    skipped: List[str] = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        name = str(rule.get("name") or rule.get("id") or "?")
        if is_branch_rule(rule):
            try:
                out.append(ordered_branch_dict(normalize_branch_rule(rule)))
                report.append(f"OK skip(already-branch): {name}")
            except ValueError as exc:
                skipped.append(name)
                report.append(f"SKIP invalid-branch {name}: {exc}")
            continue
        br, reason, extras = convert_v2_rule_to_branches(rule)
        if br is None:
            skipped.append(name)
            report.append(f"SKIP {name}: {reason}")
            # Keep legacy row so Pi is not silent-loss until operator fixes.
            out.append(rule)
            continue
        if not br.get("id"):
            br["id"] = str(_uuid.uuid4())
        out.append(br)
        if reason and reason.startswith("split"):
            report.append(f"OK {name}: {reason}")
            for ex in extras:
                if not ex.get("id"):
                    ex["id"] = str(_uuid.uuid4())
                out.append(ex)
                report.append(f"OK split-extra: {ex.get('name')}")
        else:
            report.append(f"OK migrated: {name}")
    return out, report, skipped
