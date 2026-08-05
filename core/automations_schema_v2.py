# --- file: core/automations_schema_v2.py ---
"""
Automation schema v2 (Phase 6A): trigger + ordered cases.

Legacy Y1 (on:/off:) and flat (conditions/actions) are migrator/API input only.
Engine evaluate still consumes flat rules via expand_automations_for_engine().
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

_NUMERIC_IDX_RE = re.compile(r"^\d+$")

from core.schedule_events import (  # noqa: E402
    SCHEDULE_WINDOW_EDGES,
    canonicalize_schedule_event,
)

# Deprecated name — prefer SCHEDULE_WINDOW_EDGES
EVENT_FAMILY_TO_ON_OFF = SCHEDULE_WINDOW_EDGES

try:
    from loguru import logger as _logger
except ImportError:  # pragma: no cover
    import logging
    _logger = logging.getLogger("automations_schema_v2")


def _warn(msg: str) -> None:
    try:
        _logger.warning(msg)
    except Exception:
        print(msg)

# Canonical dump order: name first … id last (Phase 6A).
_V2_KEY_ORDER = (
    "name",
    "scene",
    "require_confirmation",
    "trigger",
    "cases",
    "id",
)

_OFF_EVENT_TO_FAMILY = {off: fam for fam, (_on, off) in SCHEDULE_WINDOW_EDGES.items()}
_ON_EVENT_TO_FAMILY = {on: fam for fam, (on, _off) in SCHEDULE_WINDOW_EDGES.items()}
# Legacy concrete events still reverse-map to families during cutover
_ON_EVENT_TO_FAMILY["TWILIGHT_MORNING_ON_TRIGGER"] = "twilight_morning"
_ON_EVENT_TO_FAMILY["TWILIGHT_EVENING_ON_TRIGGER"] = "twilight_evening"
_OFF_EVENT_TO_FAMILY["TWILIGHT_MORNING_OFF_TRIGGER"] = "twilight_morning"
_OFF_EVENT_TO_FAMILY["TWILIGHT_EVENING_OFF_TRIGGER"] = "twilight_evening"


def is_v2_rule(rule: Any) -> bool:
    return isinstance(rule, dict) and isinstance(rule.get("cases"), list)


def is_y1_branched_rule(rule: Any) -> bool:
    if not isinstance(rule, dict) or is_v2_rule(rule):
        return False
    return ("on" in rule) or ("off" in rule) or (True in rule) or (False in rule)


def ordered_v2_dict(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Emit canonical key order for YAML/API dumps."""
    out: Dict[str, Any] = {}
    for key in _V2_KEY_ORDER:
        if key in rule and rule[key] is not None:
            out[key] = rule[key]
    for key, val in rule.items():
        if key not in out and val is not None:
            out[key] = val
    return out


def _copy_action(action: Any) -> Dict[str, Any]:
    if not isinstance(action, dict):
        return {}
    out = copy.deepcopy(action)
    # Drop empty optional rich fields for cleaner YAML (keep explicit 0).
    for k in ("preset", "station", "target", "scene", "event"):
        if out.get(k) in ("", None):
            out.pop(k, None)
    for k in ("bri", "volume"):
        if out.get(k) in ("", None):
            out.pop(k, None)
    if out.get("xy") in ("", None, []):
        out.pop("xy", None)
    return out


def _copy_condition(cond: Any) -> Dict[str, Any]:
    if not isinstance(cond, dict):
        return {}
    out = copy.deepcopy(cond)
    # Normalize alias leftovers
    if "condition_is" in out and "is" not in out:
        out["is"] = out.pop("condition_is")
    else:
        out.pop("condition_is", None)
    return out


def _branch_payload(branch: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not isinstance(branch, dict):
        return [], []
    conds = branch.get("conditions") or []
    acts = branch.get("actions") or []
    if not isinstance(conds, list):
        conds = []
    if not isinstance(acts, list):
        acts = []
    return [_copy_condition(c) for c in conds], [_copy_action(a) for a in acts]


def legacy_to_v2(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one Y1 branched or flat rule to v2. Pass through if already v2."""
    if is_v2_rule(rule):
        return ordered_v2_dict(_normalize_v2(rule))

    name = rule.get("name") or ""
    scene = bool(rule.get("scene", False))
    require_confirmation = bool(rule.get("require_confirmation", False))
    rule_id = rule.get("id")
    trigger = rule.get("trigger")

    if is_y1_branched_rule(rule):
        on_branch = rule["on"] if "on" in rule else (rule[True] if True in rule else None)
        off_branch = rule["off"] if "off" in rule else (rule[False] if False in rule else None)
        cases: List[Dict[str, Any]] = []

        trig = trigger if isinstance(trigger, dict) else {}
        # Device or event-family trigger without edge state on trigger.
        out_trigger: Dict[str, Any] = {}
        if trig.get("entity_id"):
            out_trigger = {"entity_id": trig["entity_id"]}
        elif trig.get("event"):
            out_trigger = {"event": trig["event"]}
        else:
            _warn(f"[v2] Branched rule '{name}' missing trigger entity_id/event — keeping raw trigger")
            out_trigger = copy.deepcopy(trig) if isinstance(trig, dict) else {}

        if on_branch is not None:
            conds, actions = _branch_payload(on_branch)
            case: Dict[str, Any] = {"to_state": "ON", "actions": actions}
            if conds:
                case["conditions"] = conds
            cases.append(case)
        if off_branch is not None:
            conds, actions = _branch_payload(off_branch)
            case = {"to_state": "OFF", "actions": actions}
            if conds:
                case["conditions"] = conds
            cases.append(case)

        return ordered_v2_dict({
            "name": name,
            "scene": scene,
            "require_confirmation": require_confirmation,
            "trigger": out_trigger,
            "cases": cases,
            "id": rule_id,
        })

    # Flat rule
    cases_flat: List[Dict[str, Any]] = []
    out_trigger_f: Any = copy.deepcopy(trigger)
    case_match: Dict[str, Any] = {}

    if isinstance(trigger, dict) and trigger.get("entity_id") and trigger.get("state"):
        st = str(trigger.get("state"))
        if st.upper() in ("ON", "OFF"):
            out_trigger_f = {"entity_id": trigger["entity_id"]}
            case_match["to_state"] = st.upper()
        elif st.upper() in ("SYNC", "SYNCOPPOSITE"):
            # Expand via normalize after building a provisional v2 shell
            out_trigger_f = {"entity_id": trigger["entity_id"], "state": st.upper()}
            case_match = {}

    conds = rule.get("conditions") or []
    if not isinstance(conds, list):
        conds = []
    actions = rule.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    case_f: Dict[str, Any] = {"actions": [_copy_action(a) for a in actions]}
    if case_match.get("to_state"):
        case_f["to_state"] = case_match["to_state"]
    if conds:
        case_f["conditions"] = [_copy_condition(c) for c in conds]
    cases_flat.append(case_f)

    provisional = ordered_v2_dict({
        "name": name,
        "scene": scene,
        "require_confirmation": require_confirmation,
        "trigger": out_trigger_f,
        "cases": cases_flat,
        "id": rule_id,
    })
    # SYNC|SYNCOPPOSITE → ON/OFF cases
    return ordered_v2_dict(_normalize_v2(provisional))


def _rewrite_mirror_action(action: Dict[str, Any], edge: str) -> Dict[str, Any]:
    """Map SYNC / SYNCOPPOSITE action states onto an explicit ON/OFF edge."""
    out = _copy_action(action)
    st = str(out.get("state") or "").upper()
    if st == "SYNC":
        out["state"] = edge
    elif st == "SYNCOPPOSITE":
        out["state"] = "OFF" if edge == "ON" else "ON"
    return out


def _migrate_sync_to_cases(rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retire trigger/action SYNC|SYNCOPPOSITE → explicit ON/OFF cases (one rule).
    Pure mirrors become two cases; leftover SYNC action states inside an edged case
    are rewritten to that case's to_state (or flipped for SYNCOPPOSITE).
    """
    out = copy.deepcopy(rule)
    trigger = out.get("trigger")
    cases = out.get("cases") or []
    if not isinstance(cases, list):
        cases = []

    trig_sync = (
        isinstance(trigger, dict)
        and trigger.get("entity_id")
        and str(trigger.get("state") or "").upper() in ("SYNC", "SYNCOPPOSITE")
    )

    if trig_sync:
        eid = trigger["entity_id"]
        out["trigger"] = {"entity_id": eid}
        # Single undedged case (classic SYNC rule) → expand to ON + OFF
        if len(cases) == 1 and not cases[0].get("to_state"):
            base_acts = cases[0].get("actions") or []
            base_conds = cases[0].get("conditions") or []
            new_cases: List[Dict[str, Any]] = []
            for edge in ("ON", "OFF"):
                case: Dict[str, Any] = {
                    "to_state": edge,
                    "actions": [_rewrite_mirror_action(a, edge) for a in base_acts if isinstance(a, dict)],
                }
                if base_conds:
                    case["conditions"] = [_copy_condition(c) for c in base_conds]
                new_cases.append(case)
            out["cases"] = new_cases
            cases = new_cases
        else:
            cases = out.get("cases") or cases

    # Rewrite any remaining SYNC/SYNCOPPOSITE on actions using case to_state
    fixed_cases: List[Dict[str, Any]] = []
    for c in cases:
        if not isinstance(c, dict):
            continue
        edge = str(c.get("to_state") or "").upper()
        acts_in = c.get("actions") or []
        if edge in ("ON", "OFF"):
            acts_out = [_rewrite_mirror_action(a, edge) for a in acts_in if isinstance(a, dict)]
        else:
            # No edge — cannot resolve SYNC; leave non-SYNC actions, drop SYNC states to ON as last resort? 
            # Better: expand missing edge into ON/OFF if any action is SYNC
            has_mirror = any(
                isinstance(a, dict) and str(a.get("state") or "").upper() in ("SYNC", "SYNCOPPOSITE")
                for a in acts_in
            )
            if has_mirror:
                for e in ("ON", "OFF"):
                    nc = {
                        "to_state": e,
                        "actions": [_rewrite_mirror_action(a, e) for a in acts_in if isinstance(a, dict)],
                    }
                    if c.get("conditions"):
                        nc["conditions"] = [_copy_condition(x) for x in c["conditions"]]
                    fixed_cases.append(nc)
                continue
            acts_out = [_copy_action(a) for a in acts_in if isinstance(a, dict)]
        nc2 = dict(c)
        nc2["actions"] = acts_out
        fixed_cases.append(nc2)
    out["cases"] = fixed_cases
    return out


def _canonicalize_trigger(trigger: Any) -> Any:
    """Rewrite legacy twilight event strings on triggers (dict or OR-list)."""
    if isinstance(trigger, list):
        return [_canonicalize_trigger(t) for t in trigger]
    if isinstance(trigger, dict):
        out = copy.deepcopy(trigger)
        if out.get("event"):
            out["event"] = canonicalize_schedule_event(out["event"])
        # Strip retired SYNC from trigger (cases carry edges after _migrate_sync_to_cases)
        if str(out.get("state") or "").upper() in ("SYNC", "SYNCOPPOSITE"):
            out.pop("state", None)
        return out
    return trigger


def _normalize_v2(rule: Dict[str, Any]) -> Dict[str, Any]:
    cases_in = rule.get("cases") or []
    cases_out: List[Dict[str, Any]] = []
    for c in cases_in:
        if not isinstance(c, dict):
            continue
        case: Dict[str, Any] = {}
        if c.get("to_state") is not None:
            case["to_state"] = str(c["to_state"]).upper() if str(c["to_state"]).upper() in ("ON", "OFF") else c["to_state"]
        conds = c.get("conditions") or []
        if isinstance(conds, list) and conds:
            case["conditions"] = [_copy_condition(x) for x in conds]
        acts = c.get("actions") or []
        case["actions"] = [_copy_action(a) for a in acts] if isinstance(acts, list) else []
        for a in case["actions"]:
            if isinstance(a, dict) and a.get("event"):
                a["event"] = canonicalize_schedule_event(a["event"])
        cases_out.append(case)
    out = {
        "name": rule.get("name") or "",
        "scene": bool(rule.get("scene", False)),
        "require_confirmation": bool(rule.get("require_confirmation", False)),
        "trigger": copy.deepcopy(rule.get("trigger")),
        "cases": cases_out,
        "id": rule.get("id"),
    }
    out = _migrate_sync_to_cases(out)
    out["trigger"] = _canonicalize_trigger(out.get("trigger"))
    return out


def v2_to_editor_projection(rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Project v2 → Y1/flat when lossless (legacy helper; Blocky uses raw v2 since Phase 6B).
    Multi-case non-ON/OFF (e.g. Cinema merge) stays v2.
    """
    if not is_v2_rule(rule):
        return rule

    v2 = _normalize_v2(rule)
    cases = v2.get("cases") or []
    trigger = v2.get("trigger")
    base = {
        "name": v2.get("name"),
        "scene": bool(v2.get("scene", False)),
        "require_confirmation": bool(v2.get("require_confirmation", False)),
        "id": v2.get("id"),
    }

    # Two cases ON+OFF, no extra conditions → Y1 branched
    if (
        len(cases) == 2
        and isinstance(trigger, dict)
        and {str(cases[0].get("to_state")).upper(), str(cases[1].get("to_state")).upper()} == {"ON", "OFF"}
        and not cases[0].get("conditions")
        and not cases[1].get("conditions")
    ):
        on_c = next(c for c in cases if str(c.get("to_state")).upper() == "ON")
        off_c = next(c for c in cases if str(c.get("to_state")).upper() == "OFF")
        out_trig = {}
        if trigger.get("entity_id"):
            out_trig = {"entity_id": trigger["entity_id"]}
        elif trigger.get("event"):
            # Keep family name if already family; else leave concrete event as family-like
            ev = trigger["event"]
            fam = _ON_EVENT_TO_FAMILY.get(ev) or _OFF_EVENT_TO_FAMILY.get(ev) or ev
            if fam in SCHEDULE_WINDOW_EDGES:
                out_trig = {"event": fam}
            else:
                out_trig = {"event": ev}
        return {
            **base,
            "trigger": out_trig,
            "on": {"conditions": [], "actions": copy.deepcopy(on_c.get("actions") or [])},
            "off": {"conditions": [], "actions": copy.deepcopy(off_c.get("actions") or [])},
        }

    # Single case with to_state ON/OFF → flat edge
    if len(cases) == 1 and isinstance(trigger, dict) and cases[0].get("to_state") in ("ON", "OFF", "on", "off"):
        st = str(cases[0]["to_state"]).upper()
        if trigger.get("entity_id"):
            flat = {
                **base,
                "trigger": {"entity_id": trigger["entity_id"], "state": st},
                "actions": copy.deepcopy(cases[0].get("actions") or []),
            }
            if cases[0].get("conditions"):
                flat["conditions"] = copy.deepcopy(cases[0]["conditions"])
            return flat

    # Single case, trigger already carries state (SYNC etc.) or event
    if len(cases) == 1:
        flat = {
            **base,
            "trigger": copy.deepcopy(trigger),
            "actions": copy.deepcopy(cases[0].get("actions") or []),
        }
        if cases[0].get("conditions"):
            flat["conditions"] = copy.deepcopy(cases[0]["conditions"])
        # Don't project if case also has to_state conflicting — already handled above
        if not cases[0].get("to_state"):
            return flat

    # Non-projectable (Cinema multi-condition, etc.)
    return ordered_v2_dict(v2)


def _expand_v2_case_to_flat(
    base: Dict[str, Any],
    trigger: Any,
    case: Dict[str, Any],
    case_index: int,
) -> Optional[Dict[str, Any]]:
    """One v2 case → one engine flat rule."""
    actions = case.get("actions") or []
    if not isinstance(actions, list) or not actions:
        return None
    conditions = case.get("conditions")
    if conditions == []:
        conditions = None

    rule_id = base.get("id")
    name = base.get("name")
    to_state = case.get("to_state")
    to_state_u = str(to_state).upper() if to_state is not None else None

    flat_trigger: Any
    suffix = ""
    label = ""

    if isinstance(trigger, list):
        # OR multi-trigger: keep as list (engine supports it)
        flat_trigger = copy.deepcopy(trigger)
        suffix = f"#c{case_index}"
        label = f" [case {case_index}]"
    elif isinstance(trigger, dict) and trigger.get("entity_id"):
        eid = trigger["entity_id"]
        if to_state_u in ("ON", "OFF"):
            flat_trigger = {"entity_id": eid, "state": to_state_u}
            suffix = f"#{to_state_u.lower()}"
            label = f" [{to_state_u}]"
        elif trigger.get("state"):
            flat_trigger = {"entity_id": eid, "state": trigger["state"]}
            suffix = f"#c{case_index}" if case_index else ""
        else:
            # No edge — should not match device transitions usefully; still emit
            flat_trigger = {"entity_id": eid}
            suffix = f"#c{case_index}"
            label = f" [case {case_index}]"
    elif isinstance(trigger, dict) and trigger.get("event"):
        ev = str(trigger["event"])
        if ev in SCHEDULE_WINDOW_EDGES and to_state_u in ("ON", "OFF"):
            on_ev, off_ev = SCHEDULE_WINDOW_EDGES[ev]
            flat_trigger = {"event": on_ev if to_state_u == "ON" else off_ev}
            suffix = f"#{to_state_u.lower()}"
            label = f" [{to_state_u}]"
        else:
            # Concrete event (e.g. SCENE_CINEMA_OFF) with condition-discriminated cases
            flat_trigger = {"event": canonicalize_schedule_event(ev)}
            suffix = f"#c{case_index}"
            label = f" [case {case_index}]"
    else:
        flat_trigger = copy.deepcopy(trigger)
        suffix = f"#c{case_index}"
        label = f" [case {case_index}]"

    out = {
        "id": f"{rule_id}{suffix}" if rule_id else None,
        "name": f"{name}{label}" if name else name,
        "scene": bool(base.get("scene", False)),
        "require_confirmation": bool(base.get("require_confirmation", False)),
        "trigger": flat_trigger,
        "actions": copy.deepcopy(actions),
    }
    if conditions:
        out["conditions"] = copy.deepcopy(conditions)
    return out


def expand_automations_for_engine(raw_automations: Any) -> List[dict]:
    """
    Dual-read expand: v2 cases, Y1 on/off, and flat → flat list for AutomationEngine.
    """
    if raw_automations is None:
        return []
    if not isinstance(raw_automations, list):
        _warn(f"automations: expected list, got {type(raw_automations)}")
        return []

    expanded: List[dict] = []
    for rule in raw_automations:
        if not isinstance(rule, dict):
            continue

        if is_v2_rule(rule):
            v2 = _normalize_v2(rule)
            cases = v2.get("cases") or []
            base = {
                "id": v2.get("id"),
                "name": v2.get("name"),
                "scene": v2.get("scene"),
                "require_confirmation": v2.get("require_confirmation"),
            }
            for i, case in enumerate(cases):
                flat = _expand_v2_case_to_flat(base, v2.get("trigger"), case, i)
                if flat:
                    expanded.append(flat)
            continue

        if is_y1_branched_rule(rule):
            # Reuse conversion then expand as v2 (keeps one code path)
            v2 = legacy_to_v2(rule)
            cases = v2.get("cases") or []
            base = {
                "id": v2.get("id"),
                "name": v2.get("name"),
                "scene": v2.get("scene"),
                "require_confirmation": v2.get("require_confirmation"),
            }
            for i, case in enumerate(cases):
                flat = _expand_v2_case_to_flat(base, v2.get("trigger"), case, i)
                if flat:
                    expanded.append(flat)
            continue

        # Flat pass-through — canonicalize schedule event aliases
        flat = copy.deepcopy(rule)
        if "trigger" in flat:
            flat["trigger"] = _canonicalize_trigger(flat["trigger"])
        expanded.append(flat)

    return expanded


def cinema_off_merge_key(rule: Dict[str, Any]) -> Optional[str]:
    """Return merge key for SCENE_CINEMA_OFF + single time_of_day condition pairs."""
    if is_y1_branched_rule(rule) or is_v2_rule(rule):
        return None
    trig = rule.get("trigger")
    if not isinstance(trig, dict) or trig.get("event") != "SCENE_CINEMA_OFF":
        return None
    conds = rule.get("conditions") or []
    if not isinstance(conds, list) or len(conds) != 1:
        return None
    c0 = conds[0]
    if not isinstance(c0, dict) or c0.get("type") != "time_of_day":
        return None
    is_val = c0.get("is") or c0.get("condition_is")
    if is_val not in ("dark", "light"):
        return None
    return "SCENE_CINEMA_OFF::time_pair"


def merge_cinema_off_pair(rules: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Merge complementary Cinema OFF dark/light flat rules into one v2 rule.
    Returns (new_list, log_lines).
    """
    logs: List[str] = []
    # Collect candidates by event
    dark = None
    light = None
    dark_i = light_i = -1
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            continue
        key = cinema_off_merge_key(r)
        if not key:
            continue
        conds = r.get("conditions") or []
        is_val = (conds[0].get("is") or conds[0].get("condition_is")) if conds else None
        if is_val == "dark":
            dark, dark_i = r, i
        elif is_val == "light":
            light, light_i = r, i

    if dark is None or light is None:
        return rules, logs

    # Prefer dashboard/scene metadata from the scene:true rule
    primary = dark if dark.get("scene") else (light if light.get("scene") else dark)
    secondary = light if primary is dark else dark

    v2 = {
        "name": primary.get("name") or "--- CINEMA OFF",
        "scene": bool(primary.get("scene") or secondary.get("scene")),
        "require_confirmation": bool(
            primary.get("require_confirmation") or secondary.get("require_confirmation")
        ),
        "trigger": {"event": "SCENE_CINEMA_OFF"},
        "cases": [
            {
                "conditions": [{"type": "time_of_day", "is": "dark"}],
                "actions": [_copy_action(a) for a in (dark.get("actions") or [])],
            },
            {
                "conditions": [{"type": "time_of_day", "is": "light"}],
                "actions": [_copy_action(a) for a in (light.get("actions") or [])],
            },
        ],
        "id": primary.get("id") or secondary.get("id"),
    }
    v2 = ordered_v2_dict(v2)

    drop = {dark_i, light_i}
    out: List[Dict[str, Any]] = []
    inserted = False
    for i, r in enumerate(rules):
        if i in drop:
            if not inserted:
                out.append(v2)
                inserted = True
            continue
        out.append(r)
    if not inserted:
        out.append(v2)

    logs.append(
        f"Merged Cinema OFF pair -> id={v2.get('id')} name={v2.get('name')!r} "
        f"(dropped ids {dark.get('id')}, {light.get('id')})"
    )
    return out, logs


def migrate_rules_to_v2(
    rules: List[Dict[str, Any]],
    *,
    merge_cinema: bool = True,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Full list migrate: optional Cinema merge, then every rule → v2 ordered dict."""
    logs: List[str] = []
    working = list(rules)
    if merge_cinema:
        working, merge_logs = merge_cinema_off_pair(working)
        logs.extend(merge_logs)

    out: List[Dict[str, Any]] = []
    for r in working:
        if not isinstance(r, dict):
            continue
        if is_v2_rule(r) and not is_y1_branched_rule(r):
            # Still re-order / normalize
            v2 = ordered_v2_dict(_normalize_v2(r))
            out.append(v2)
            logs.append(f"normalize v2: {v2.get('name')!r} id={v2.get('id')}")
        else:
            v2 = legacy_to_v2(r)
            out.append(v2)
            kind = "Y1" if is_y1_branched_rule(r) else "flat"
            logs.append(f"{kind}->v2: {v2.get('name')!r} id={v2.get('id')} cases={len(v2.get('cases') or [])}")
    return out, logs


def validate_v2_entity_ids(rule: Dict[str, Any]) -> None:
    """Raise ValueError if any entity_id looks numeric."""
    def visit(node: Any, path: str) -> None:
        if isinstance(node, list):
            for i, it in enumerate(node):
                visit(it, f"{path}[{i}]")
            return
        if not isinstance(node, dict):
            return
        eid = node.get("entity_id")
        if isinstance(eid, str) and _NUMERIC_IDX_RE.match(eid):
            raise ValueError(f"{path}.entity_id must not be a numeric idx")
        for k, v in node.items():
            visit(v, f"{path}.{k}" if path else k)

    visit(rule, "rule")
