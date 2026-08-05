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
    """In-place: quote state/is strings that YAML would otherwise load as bools."""
    if isinstance(node, dict):
        for key, val in list(node.items()):
            if key in ("state", "is"):
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


def read_automations() -> List[Dict[str, Any]]:
    root, _ = load_automations_roundtrip()
    automations = root.get("automations", []) if isinstance(root, dict) else []
    if automations is None:
        return []
    if isinstance(automations, list):
        return automations
    try:
        return list(automations)
    except TypeError:
        return []


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


def append_automation(rule: Dict[str, Any]) -> None:
    """Append one rule (expected v2 canonical); preserve comments on existing entries."""
    from core.automations_schema_v2 import legacy_to_v2, ordered_v2_dict, validate_v2_entity_ids

    v2 = ordered_v2_dict(legacy_to_v2(rule))
    validate_v2_entity_ids(v2)
    root, path = load_automations_roundtrip()
    seq = _ensure_automations_seq(root)
    item = _to_commented(v2)
    _quote_boolish_scalars(item)
    seq.append(item)
    _dump_root(root, path)


def update_automation(rule_id: str, rule: Dict[str, Any]) -> bool:
    """Replace one rule by id with v2 canonical shape."""
    from core.automations_schema_v2 import legacy_to_v2, ordered_v2_dict, validate_v2_entity_ids

    v2 = ordered_v2_dict(legacy_to_v2(rule))
    validate_v2_entity_ids(v2)
    if v2.get("id") is None:
        v2["id"] = rule_id
    root, path = load_automations_roundtrip()
    seq = _ensure_automations_seq(root)
    for i, existing in enumerate(seq):
        if isinstance(existing, dict) and existing.get("id") == rule_id:
            item = _to_commented(ordered_v2_dict(v2))
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
