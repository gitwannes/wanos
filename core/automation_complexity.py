# --- file: core/automation_complexity.py ---
"""
B25 / B14b — derived Automations Library complexity score + tier.

Computed on read (API list). Never persisted to YAML.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from core.condition_tree import (
    _cond_as_dict,
    count_leaf_compares,
    is_group_node,
)


def _max_logic_nest_depth(conds: Any, *, depth: int = 0) -> int:
    """Max Logic group nest depth in a conditions list (top-level AND is depth 0)."""
    if not isinstance(conds, list):
        return depth
    max_d = depth
    for raw in conds:
        d = _cond_as_dict(raw)
        if not d:
            continue
        if is_group_node(d):
            # Entering a group increases depth by 1.
            child_depth = depth + 1
            max_d = max(max_d, child_depth)
            max_d = max(
                max_d,
                _max_logic_nest_depth(d.get("children") or [], depth=child_depth),
            )
    return max_d


def _walk_then_metrics(then_block: Any, *, depth: int) -> Tuple[int, int, int, int]:
    """
    Walk a ``then:`` subtree.

    Returns (leaf_compares, logic_nest_max, then_nest_max, action_count).
    ``depth`` is the then-nesting level of this block (1 = first then under top branch).
    """
    if not isinstance(then_block, dict):
        return 0, 0, 0, 0
    leaves = 0
    logic_max = 0
    then_max = depth
    actions = 0
    for a in then_block.get("leading_actions") or []:
        if isinstance(a, dict):
            actions += 1
    for br in then_block.get("branches") or []:
        if not isinstance(br, dict):
            continue
        conds = br.get("conditions") or []
        leaves += count_leaf_compares(conds)
        logic_max = max(logic_max, _max_logic_nest_depth(conds))
        nested = br.get("then")
        if nested is not None:
            nl, nlog, nth, na = _walk_then_metrics(nested, depth=depth + 1)
            leaves += nl
            logic_max = max(logic_max, nlog)
            then_max = max(then_max, nth)
            actions += na
        else:
            for a in br.get("actions") or []:
                if isinstance(a, dict):
                    actions += 1
    for a in then_block.get("trailing_actions") or []:
        if isinstance(a, dict):
            actions += 1
    return leaves, logic_max, then_max, actions


def score_inputs(rule: Dict[str, Any]) -> Dict[str, int]:
    """
    Structural inputs for the B25 formula.

    score =
      leaf_compares
      + 2 * top_level_branches
      + logic_nest_depth_max
      + then_nest_depth_max
      + action_count
    """
    branches = rule.get("branches") if isinstance(rule, dict) else None
    if not isinstance(branches, list):
        # Legacy / non-branch: treat as opaque minimal score.
        return {
            "leaf_compares": 0,
            "top_level_branches": 0,
            "logic_nest_depth_max": 0,
            "then_nest_depth_max": 0,
            "action_count": 0,
        }

    leaf_compares = 0
    logic_nest_depth_max = 0
    then_nest_depth_max = 0
    action_count = 0
    top_level_branches = len(branches)

    for br in branches:
        if not isinstance(br, dict):
            continue
        conds = br.get("conditions") or []
        leaf_compares += count_leaf_compares(conds)
        logic_nest_depth_max = max(logic_nest_depth_max, _max_logic_nest_depth(conds))
        then_block = br.get("then")
        if then_block is not None:
            nl, nlog, nth, na = _walk_then_metrics(then_block, depth=1)
            leaf_compares += nl
            logic_nest_depth_max = max(logic_nest_depth_max, nlog)
            then_nest_depth_max = max(then_nest_depth_max, nth)
            action_count += na
        else:
            for a in br.get("actions") or []:
                if isinstance(a, dict):
                    action_count += 1

    return {
        "leaf_compares": int(leaf_compares),
        "top_level_branches": int(top_level_branches),
        "logic_nest_depth_max": int(logic_nest_depth_max),
        "then_nest_depth_max": int(then_nest_depth_max),
        "action_count": int(action_count),
    }


def compute_complexity_score(rule: Dict[str, Any]) -> int:
    """Derived structural score (non-negative int)."""
    inp = score_inputs(rule)
    return (
        inp["leaf_compares"]
        + 2 * inp["top_level_branches"]
        + inp["logic_nest_depth_max"]
        + inp["then_nest_depth_max"]
        + inp["action_count"]
    )


def tier_for_score(score: int) -> str:
    """Map score → S / M / C (locked B25)."""
    if score <= 6:
        return "S"
    if score <= 14:
        return "M"
    return "C"


def complexity_for_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Payload fragment for GET /api/automations (not written to disk)."""
    score = compute_complexity_score(rule)
    return {
        "complexity_score": score,
        "complexity_tier": tier_for_score(score),
    }


def attach_complexity(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy of ``row`` with complexity fields added (idempotent)."""
    out = dict(row)
    # Strip any stale persisted keys — SoT is always derived.
    out.pop("complexity", None)
    frag = complexity_for_rule(out)
    out["complexity_score"] = frag["complexity_score"]
    out["complexity_tier"] = frag["complexity_tier"]
    return out
