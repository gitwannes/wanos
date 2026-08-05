# --- file: core/automations_store.py ---
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from ruamel.yaml import YAML


def _root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _automations_path() -> Path:
    return _root_dir() / "automations.auto.yaml"


def load_automations_roundtrip() -> Tuple[Any, Path]:
    """
    Loads automations.auto.yaml using ruamel round-trip mode.

    Returns:
      (yaml_root_node, file_path)
    """
    path = _automations_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with path.open("r", encoding="utf-8") as f:
        root = yaml.load(f)

    return root, path


def read_automations() -> List[Dict[str, Any]]:
    root, _ = load_automations_roundtrip()
    automations = root.get("automations", []) if isinstance(root, dict) else []
    if automations is None:
        return []
    if isinstance(automations, list):
        return automations
    # ruamel uses CommentedSeq; it behaves like a list but may not type-check as list.
    try:
        return list(automations)
    except TypeError:
        return []


def write_automations(rules: List[Dict[str, Any]]) -> None:
    """
    Surgical write of only the `automations:` key.
    Other top-level keys (deviceexplorer_exclude, lighting) are preserved by ruamel.
    """
    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")

    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    root["automations"] = rules
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(root, f)

