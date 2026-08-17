# --- file: core/condition_tree.py ---
"""
B4 / H4 — nested AND/OR/NOT condition trees for branch Compares.

Wire shape:
  - Leaf: ``{ type: device_state|time_of_day|event, ... }``
  - Group: ``{ op: and|or|not, children: [...] }``

Top-level ``conditions: [ ... ]`` on a branch = implicit AND of each entry (flat shorthand).
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Iterator, List, Optional

_VALID_OPS = frozenset({"and", "or", "not"})
_LEAF_TYPES = frozenset({"device_state", "time_of_day", "event"})


def _cond_as_dict(cond: Any) -> Dict[str, Any]:
    if hasattr(cond, "model_dump"):
        return cond.model_dump(by_alias=True)
    return cond if isinstance(cond, dict) else {}


def is_group_node(cond: Any) -> bool:
    d = _cond_as_dict(cond)
    if d.get("type") in _LEAF_TYPES:
        return False
    op = str(d.get("op") or "").strip().lower()
    return op in _VALID_OPS and isinstance(d.get("children"), list)


def is_leaf_node(cond: Any) -> bool:
    d = _cond_as_dict(cond)
    return d.get("type") in _LEAF_TYPES


def copy_condition_node(cond: Any) -> Dict[str, Any]:
    """Deep-copy one condition leaf or group node."""
    if hasattr(cond, "model_dump"):
        raw = cond.model_dump(by_alias=True)
    elif isinstance(cond, dict):
        raw = copy.deepcopy(cond)
    else:
        return {}
    if "condition_is" in raw and "is" not in raw:
        raw["is"] = raw.pop("condition_is")
    else:
        raw.pop("condition_is", None)
    if is_group_node(raw):
        ch = raw.get("children") or []
        raw["children"] = [copy_condition_node(c) for c in ch]
    return raw


def normalize_condition_list(conds: Any) -> List[Dict[str, Any]]:
    if not isinstance(conds, list):
        return []
    return [copy_condition_node(c) for c in conds if isinstance(c, dict)]


def iter_condition_leaves(conds: Any) -> Iterator[Dict[str, Any]]:
    """Yield every leaf Compare in a branch conditions list (recursive)."""
    if not isinstance(conds, list):
        return
    for c in conds:
        d = _cond_as_dict(c)
        if not d:
            continue
        if is_group_node(d):
            yield from iter_condition_leaves(d.get("children") or [])
        elif is_leaf_node(d):
            yield d


def count_leaf_compares(conds: Any) -> int:
    return sum(1 for _ in iter_condition_leaves(conds))


def _leaf_is_value(cond: Dict[str, Any]) -> Any:
    """Resolve ``is`` / ``condition_is`` alias for validation."""
    if cond.get("is") is not None:
        return cond.get("is")
    return cond.get("condition_is")


def validate_leaf_node(cond: Dict[str, Any], *, path: str) -> Optional[str]:
    ctype = str(cond.get("type") or "")
    if ctype == "device_state":
        if not cond.get("entity_id"):
            return f"{path}: device Compare needs entity_id."
        if _leaf_is_value(cond) is None and cond.get("op") is None:
            return f"{path}: device Compare needs is/op."
        return None
    if ctype == "event":
        if not cond.get("event"):
            return f"{path}: event Compare needs event id."
        return None
    if ctype == "time_of_day":
        tod = _leaf_is_value(cond)
        if tod not in ("dark", "light"):
            return f"{path}: time Compare must be dark|light."
        return None
    return f"{path}: unknown Compare type {ctype!r}."


def validate_group_node(cond: Dict[str, Any], *, path: str) -> Optional[str]:
    op = str(cond.get("op") or "").strip().lower()
    if op not in _VALID_OPS:
        return f"{path}: op must be and|or|not (got {op!r})."
    children = cond.get("children") or []
    if not isinstance(children, list):
        return f"{path}: children must be a list."
    if op == "not":
        if len(children) != 1:
            return f"{path}: not must have exactly one child."
    elif len(children) < 1:
        return f"{path}: {op} must have at least one child."
    for i, child in enumerate(children):
        err = validate_condition_node(child, path=f"{path}.children[{i}]")
        if err:
            return err
    return None


def validate_condition_node(cond: Any, *, path: str = "condition") -> Optional[str]:
    d = _cond_as_dict(cond)
    if not d:
        return f"{path}: must be a mapping."
    if is_group_node(d):
        return validate_group_node(d, path=path)
    if is_leaf_node(d):
        return validate_leaf_node(d, path=path)
    if d.get("type"):
        return f"{path}: unknown Compare type {d.get('type')!r}."
    return f"{path}: expected leaf (type) or group (op)."


def validate_condition_list(conds: Any) -> Optional[str]:
    if conds is None:
        return None
    if not isinstance(conds, list):
        return "conditions must be a list."
    for i, c in enumerate(conds):
        err = validate_condition_node(c, path=f"conditions[{i}]")
        if err:
            return err
    return None


def evaluate_condition_list(
    conds: Any,
    hold_fn: Callable[[Any], bool],
) -> bool:
    """
    Evaluate branch ``conditions`` (top-level AND). ``hold_fn`` evaluates one leaf/group node.
    """
    if not conds:
        return True
    if not isinstance(conds, list):
        return False
    for c in conds:
        if not hold_fn(c):
            return False
    return True


def evaluate_condition_node(
    cond: Any,
    hold_fn: Callable[[Any], bool],
) -> bool:
    """Evaluate one leaf or nested group."""
    d = _cond_as_dict(cond)
    if not d:
        return False
    if is_group_node(d):
        op = str(d.get("op") or "").lower()
        children = d.get("children") or []
        if op == "not":
            if len(children) != 1:
                return False
            return not evaluate_condition_node(children[0], hold_fn)
        if op == "and":
            return all(evaluate_condition_node(c, hold_fn) for c in children)
        if op == "or":
            return any(evaluate_condition_node(c, hold_fn) for c in children)
        return False
    return hold_fn(cond)


def condition_node_may_wake_device(
    cond: Any,
    *,
    event_idx: Any,
    event_name: str,
    is_transition: bool,
    resolve_idx: Callable[[Any], Any],
) -> bool:
    """True when this node mentions the waking device for B19 derived wake."""
    if not isinstance(cond, dict):
        return False
    if is_group_node(cond):
        return any(
            condition_node_may_wake_device(
                c,
                event_idx=event_idx,
                event_name=event_name,
                is_transition=is_transition,
                resolve_idx=resolve_idx,
            )
            for c in (cond.get("children") or [])
        )
    if cond.get("type") != "device_state":
        return False
    cond_idx = resolve_idx(cond)
    if cond_idx is None or event_idx is None or cond_idx != event_idx:
        return False
    if event_name == "DOOR_CHANGED":
        return True
    if event_name in (
        "HUB_STATE_CHANGED",
        "TEMP_UPDATED",
        "HUMIDITY_UPDATED",
        "POWER_UPDATED",
    ):
        if event_name == "HUB_STATE_CHANGED" and not is_transition:
            return False
        return True
    return False


def condition_node_may_wake_event(
    cond: Any,
    *,
    bus_token: str,
    to_bus_token: Callable[[str], str],
) -> Optional[str]:
    """Return matched event UUID when this node wakes on the bus event, else None."""
    if not isinstance(cond, dict):
        return None
    if is_group_node(cond):
        for c in cond.get("children") or []:
            matched = condition_node_may_wake_event(
                c, bus_token=bus_token, to_bus_token=to_bus_token
            )
            if matched:
                return matched
        return None
    if cond.get("type") != "event":
        return None
    want = cond.get("event")
    if want and to_bus_token(str(want)) == to_bus_token(bus_token):
        return to_bus_token(str(want))
    return None
