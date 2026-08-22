# --- file: core/automations_schema_b22.py ---
"""
B22 — Nested If/Do via branch ``then:`` (If/Then + inner If/Do/Else-if/Do).

Top-level branch: ``actions`` xor ``then``. Wake Compares stay on outer ``conditions`` only.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from core.automation_limits import MAX_NEST_DEPTH
from core.condition_tree import (
    iter_condition_leaves,
    validate_condition_list,
)

_WHEN_IF = "if"
_WHEN_ELIF = "else_if"
_VALID_WHEN = frozenset({_WHEN_IF, _WHEN_ELIF})


def _leaf_is_any(cond: Dict[str, Any]) -> bool:
    is_val = cond.get("is")
    if is_val is None:
        is_val = cond.get("condition_is")
    return str(is_val or "").upper() == "ANY"


def wake_device_entity_ids(conditions: Any) -> Set[str]:
    """Device entity_ids referenced in a branch's top-level wake ``conditions``."""
    out: Set[str] = set()
    for leaf in iter_condition_leaves(conditions or []):
        if leaf.get("type") != "device_state":
            continue
        eid = str(leaf.get("entity_id") or "").strip()
        if eid:
            out.add(eid)
    return out


def _validate_then_branch_conditions(
    conds: Any,
    *,
    path: str,
    wake_devices: Set[str],
) -> Optional[str]:
    err = validate_condition_list(conds)
    if err:
        return f"{path}: {err}"
    for leaf in iter_condition_leaves(conds or []):
        lp = f"{path} leaf"
        ctype = str(leaf.get("type") or "")
        if ctype == "event":
            return f"{lp}: event Compare not allowed inside then (wake-only)."
        if ctype == "device_state":
            eid = str(leaf.get("entity_id") or "").strip()
            if eid and eid in wake_devices:
                return f"{lp}: device {eid!r} is wake device — not allowed inside then."
            if _leaf_is_any(leaf):
                return f"{lp}: is: ANY not allowed inside then."
    return None


def validate_then_block(
    then_block: Any,
    *,
    path: str,
    wake_devices: Set[str],
    depth: int,
) -> Optional[str]:
    """Validate ``then: { branches: [...] }`` subtree."""
    if depth > MAX_NEST_DEPTH:
        return f"{path}: then nesting exceeds MAX_NEST_DEPTH ({MAX_NEST_DEPTH})."
    if not isinstance(then_block, dict):
        return f"{path}: then must be a mapping."
    branches = then_block.get("branches")
    if not isinstance(branches, list) or not branches:
        return f"{path}: then.branches must be a non-empty list."
    if branches[0].get("when") != _WHEN_IF:
        return f"{path}: first inner branch must be when: if."
    for i, br in enumerate(branches):
        if not isinstance(br, dict):
            return f"{path}.branches[{i}]: must be a mapping."
        when = str(br.get("when") or "").strip()
        if when not in _VALID_WHEN:
            return f"{path}.branches[{i}]: when must be if|else_if."
        if when == _WHEN_IF and i != 0:
            return f"{path}.branches[{i}]: only first inner branch may be when: if."
        bp = f"{path}.branches[{i}]"
        conds = br.get("conditions") or []
        err = _validate_then_branch_conditions(
            conds, path=f"{bp}.conditions", wake_devices=wake_devices
        )
        if err:
            return err
        has_actions = isinstance(br.get("actions"), list) and len(br.get("actions") or []) > 0
        has_then = br.get("then") is not None
        if has_actions and has_then:
            return f"{bp}: cannot have both actions and then."
        if has_then:
            err = validate_then_block(
                br.get("then"),
                path=f"{bp}.then",
                wake_devices=wake_devices,
                depth=depth + 1,
            )
            if err:
                return err
    return None


def validate_top_branch_b22(branch: Dict[str, Any], *, index: int) -> Optional[str]:
    """Validate actions/then XOR and then subtree for one top-level branch."""
    has_actions = isinstance(branch.get("actions"), list) and len(branch.get("actions") or []) > 0
    has_then = branch.get("then") is not None
    if has_actions and has_then:
        return f"Branch {index}: cannot have both actions and then."
    if has_then:
        wake_devices = wake_device_entity_ids(branch.get("conditions"))
        return validate_then_block(
            branch.get("then"),
            path=f"Branch {index}.then",
            wake_devices=wake_devices,
            depth=1,
        )
    return None


def iter_then_actions(then_block: Any):
    """Yield action dicts from a then subtree (leading, inner leaves, trailing; all depths)."""
    if not isinstance(then_block, dict):
        return
    for a in then_block.get("leading_actions") or []:
        if isinstance(a, dict):
            yield a
    for br in then_block.get("branches") or []:
        if not isinstance(br, dict):
            continue
        then_nested = br.get("then")
        if then_nested is not None:
            yield from iter_then_actions(then_nested)
        else:
            for a in br.get("actions") or []:
                if isinstance(a, dict):
                    yield a
    for a in then_block.get("trailing_actions") or []:
        if isinstance(a, dict):
            yield a
