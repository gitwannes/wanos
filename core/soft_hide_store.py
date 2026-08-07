# --- file: core/soft_hide_store.py ---
"""Surgical read/write of deviceexplorer_hide in automations.auto.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from core.automations_store import _dump_root, load_automations_roundtrip
from core.well_known_entities import is_hard_deny_entity_id

HIDE_KEY = "deviceexplorer_hide"
LEGACY_EXCLUDE_KEY = "deviceexplorer_exclude"


def _as_eid_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    seen = set()
    for ref in raw:
        eid = str(ref).strip()
        if not eid or eid in seen:
            continue
        seen.add(eid)
        out.append(eid)
    return out


def read_soft_hide_entity_ids() -> List[str]:
    """Return current soft-hide list from disk."""
    root, _ = load_automations_roundtrip()
    if not isinstance(root, dict):
        return []
    return _as_eid_list(root.get(HIDE_KEY))


def write_soft_hide_entity_ids(entity_ids: List[str]) -> List[str]:
    """
    Replace deviceexplorer_hide surgically; strip legacy deviceexplorer_exclude if present.
    Returns the sorted unique list written.
    """
    cleaned: List[str] = []
    seen = set()
    for ref in entity_ids:
        eid = str(ref).strip()
        if not eid or eid in seen:
            continue
        if is_hard_deny_entity_id(eid):
            raise ValueError(f"Hard-deny entity_id not allowed in soft-hide: {eid}")
        seen.add(eid)
        cleaned.append(eid)
    cleaned.sort()

    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")

    seq = CommentedSeq(cleaned)
    if HIDE_KEY in root:
        root[HIDE_KEY] = seq
    else:
        new_root = CommentedMap()
        inserted = False
        for k, v in root.items():
            if not inserted and k in ("lighting", "automations"):
                new_root[HIDE_KEY] = seq
                inserted = True
            if k == LEGACY_EXCLUDE_KEY:
                continue
            new_root[k] = v
        if not inserted:
            new_root[HIDE_KEY] = seq
        root = new_root

    if LEGACY_EXCLUDE_KEY in root:
        del root[LEGACY_EXCLUDE_KEY]

    _dump_root(root, path)
    return cleaned


def soft_hide_path() -> Path:
    return Path(__file__).resolve().parent.parent / "automations.auto.yaml"
