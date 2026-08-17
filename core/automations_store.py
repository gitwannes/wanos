# --- file: core/automations_store.py ---
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString


# YAML 1.1 bool-ish tokens — must be quoted when dumped as device/event states.
_YAML_BOOLISH = {
    "y", "Y", "yes", "Yes", "YES", "n", "N", "no", "No", "NO",
    "true", "True", "TRUE", "false", "False", "FALSE",
    "on", "On", "ON", "off", "Off", "OFF",
}


def _quote_boolish_scalars(node: Any) -> None:
    """In-place: quote state/is/to_state strings that YAML would otherwise load as bools."""
    if isinstance(node, dict):
        for key, val in list(node.items()):
            if key in ("state", "is", "to_state"):
                if isinstance(val, bool):
                    node[key] = DoubleQuotedScalarString("ON" if val else "OFF")
                elif isinstance(val, str) and val in _YAML_BOOLISH:
                    node[key] = DoubleQuotedScalarString(val)
                else:
                    _quote_boolish_scalars(val)
            else:
                _quote_boolish_scalars(val)
    elif isinstance(node, list):
        for item in node:
            _quote_boolish_scalars(item)


def _root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _automations_path() -> Path:
    return _root_dir() / "automations.auto.yaml"


def _rt_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_automations_roundtrip() -> Tuple[Any, Path]:
    """
    Loads automations.auto.yaml using ruamel round-trip mode.

    Returns:
      (yaml_root_node, file_path)
    """
    path = _automations_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    yaml = _rt_yaml()
    with path.open("r", encoding="utf-8") as f:
        root = yaml.load(f)

    return root, path


def _ensure_automations_seq(root: Any) -> CommentedSeq:
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")
    autos = root.get("automations")
    if autos is None:
        seq: CommentedSeq = CommentedSeq()
        root["automations"] = seq
        return seq
    if isinstance(autos, CommentedSeq):
        return autos
    if isinstance(autos, list):
        seq = CommentedSeq(autos)
        root["automations"] = seq
        return seq
    raise ValueError("automations: must be a list")


def _dump_root(root: Any, path: Path) -> None:
    yaml = _rt_yaml()
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(root, f)


def _to_commented(node: Any) -> Any:
    """Plain dict/list → CommentedMap/CommentedSeq for ruamel-friendly inserts."""
    if isinstance(node, dict):
        out = CommentedMap()
        for k, v in node.items():
            out[k] = _to_commented(v)
        return out
    if isinstance(node, list):
        out = CommentedSeq()
        for item in node:
            out.append(_to_commented(item))
        return out
    return node


def automations_from_root(root: Any) -> List[Dict[str, Any]]:
    """Extract automations: rows from an already-loaded YAML root (no disk I/O)."""
    automations = root.get("automations", []) if isinstance(root, dict) else []
    if automations is None:
        return []
    if isinstance(automations, list):
        return automations
    try:
        return list(automations)
    except TypeError:
        return []


def read_automations() -> List[Dict[str, Any]]:
    root, _ = load_automations_roundtrip()
    return automations_from_root(root)


def write_automations(rules: List[Dict[str, Any]]) -> None:
    """
    Full replace of the `automations:` list (legacy). Prefer append/update/delete
    helpers so sibling rule comments stay intact.
    """
    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")

    seq = CommentedSeq()
    for rule in rules:
        seq.append(_to_commented(rule))
    root["automations"] = seq
    _quote_boolish_scalars(root["automations"])
    _dump_root(root, path)


def _canonical_rule_for_disk(rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shape to write into automations.auto.yaml.

    B19 branch rules must stay as ``branches`` — never run through ``legacy_to_v2``
    (that would rewrite them to trigger+cases and break Admin Debug / reload).
    Cutover leftovers without branches still use the v2 path.
    """
    from core.automations_schema_b19 import (
        is_branch_rule,
        normalize_branch_rule,
        ordered_branch_dict,
        validate_branch_entity_ids,
    )
    from core.automations_schema_v2 import legacy_to_v2, ordered_v2_dict, validate_v2_entity_ids

    if is_branch_rule(rule):
        br = ordered_branch_dict(normalize_branch_rule(dict(rule)))
        validate_branch_entity_ids(br)
        return br
    v2 = ordered_v2_dict(legacy_to_v2(rule))
    validate_v2_entity_ids(v2)
    return v2


def append_automation(rule: Dict[str, Any]) -> None:
    """Append one rule (B19 branches or legacy v2); preserve comments on existing entries."""
    row = _canonical_rule_for_disk(rule)
    root, path = load_automations_roundtrip()
    seq = _ensure_automations_seq(root)
    item = _to_commented(row)
    _quote_boolish_scalars(item)
    seq.append(item)
    _dump_root(root, path)


def update_automation(rule_id: str, rule: Dict[str, Any]) -> bool:
    """Replace one rule by id (B19 branches or legacy v2)."""
    row = _canonical_rule_for_disk(rule)
    if row.get("id") is None:
        row["id"] = rule_id
    root, path = load_automations_roundtrip()
    seq = _ensure_automations_seq(root)
    for i, existing in enumerate(seq):
        if isinstance(existing, dict) and existing.get("id") == rule_id:
            item = _to_commented(row)
            _quote_boolish_scalars(item)
            seq[i] = item
            _dump_root(root, path)
            return True
    return False


def replace_all_automations(rules: List[Dict[str, Any]]) -> None:
    """Full replace of automations list (migrator). Preserves other top-level keys/comments."""
    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")
    seq = CommentedSeq()
    for rule in rules:
        item = _to_commented(rule)
        _quote_boolish_scalars(item)
        seq.append(item)
    root["automations"] = seq
    _dump_root(root, path)


def delete_automation(rule_id: str) -> bool:
    """Remove one rule by id; preserve comments on remaining entries."""
    root, path = load_automations_roundtrip()
    seq = _ensure_automations_seq(root)
    for i, existing in enumerate(list(seq)):
        if isinstance(existing, dict) and existing.get("id") == rule_id:
            del seq[i]
            _dump_root(root, path)
            return True
    return False
