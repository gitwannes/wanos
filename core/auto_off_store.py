# --- file: core/auto_off_store.py ---
"""Surgical read/write of auto_off_devices in automations.auto.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from core.auto_off_policy import (
    AUTO_OFF_ALLOWED_TYPES,
    sanitize_delay_map,
    sanitize_managed_list,
    sanitize_pertype_map,
    normalize_minutes,
)
from core.automations_store import _dump_root, load_automations_roundtrip

AUTO_OFF_KEY = "auto_off_devices"
LEGACY_LIGHTING_KEY = "lighting"


def read_auto_off_config() -> Dict[str, Any]:
    """Return current auto_off_devices block from disk (empty defaults if missing)."""
    root, _ = load_automations_roundtrip()
    if not isinstance(root, dict):
        return _empty_block()
    raw = root.get(AUTO_OFF_KEY)
    if not isinstance(raw, dict):
        return _empty_block()
    return {
        "managed_auto_off": sanitize_managed_list(raw.get("managed_auto_off")),
        "default_auto_off_minutes": int(
            raw.get("default_auto_off_minutes")
            if raw.get("default_auto_off_minutes") is not None
            else 300
        ),
        "default_pertype_auto_off_minutes": sanitize_pertype_map(
            raw.get("default_pertype_auto_off_minutes")
        ),
        "auto_off_delays": sanitize_delay_map(raw.get("auto_off_delays")),
    }


def _empty_block() -> Dict[str, Any]:
    return {
        "managed_auto_off": [],
        "default_auto_off_minutes": 300,
        "default_pertype_auto_off_minutes": {},
        "auto_off_delays": {},
    }


def write_auto_off_config(
    *,
    managed_auto_off: List[str],
    default_auto_off_minutes: int,
    default_pertype_auto_off_minutes: Dict[str, int],
    auto_off_delays: Dict[str, int],
) -> Dict[str, Any]:
    """
    Replace auto_off_devices surgically. Strips legacy lighting: if present.
    Caller must validate eligibility / orphans / unresolved eids before calling.
    """
    managed = sanitize_managed_list(managed_auto_off)
    general = normalize_minutes(default_auto_off_minutes)
    pertype = sanitize_pertype_map(default_pertype_auto_off_minutes)
    delays = sanitize_delay_map(auto_off_delays)

    managed_set = set(managed)
    for eid in delays:
        if eid not in managed_set:
            raise ValueError(
                f"auto_off_delays key '{eid}' is not in managed_auto_off "
                "(remove override when unchecking)"
            )
    for t in pertype:
        if t not in AUTO_OFF_ALLOWED_TYPES:
            raise ValueError(f"Invalid auto-off type key '{t}'")

    block = CommentedMap()
    block["managed_auto_off"] = CommentedSeq(managed)
    block["default_auto_off_minutes"] = general
    pertype_map = CommentedMap()
    for k, v in pertype.items():
        pertype_map[k] = v
    block["default_pertype_auto_off_minutes"] = pertype_map
    delays_map = CommentedMap()
    for k, v in delays.items():
        delays_map[k] = v
    block["auto_off_delays"] = delays_map

    root, path = load_automations_roundtrip()
    if not isinstance(root, dict):
        raise ValueError("automations.auto.yaml root must be a mapping")

    if AUTO_OFF_KEY in root:
        root[AUTO_OFF_KEY] = block
        new_root = root
    else:
        new_root = CommentedMap()
        inserted = False
        for k, v in root.items():
            if k == LEGACY_LIGHTING_KEY:
                if not inserted:
                    new_root[AUTO_OFF_KEY] = block
                    inserted = True
                continue
            if not inserted and k == "automations":
                new_root[AUTO_OFF_KEY] = block
                inserted = True
            new_root[k] = v
        if not inserted:
            new_root[AUTO_OFF_KEY] = block

    if LEGACY_LIGHTING_KEY in new_root:
        del new_root[LEGACY_LIGHTING_KEY]

    _dump_root(new_root, path)
    return {
        "managed_auto_off": managed,
        "default_auto_off_minutes": general,
        "default_pertype_auto_off_minutes": pertype,
        "auto_off_delays": delays,
    }


def auto_off_path() -> Path:
    return Path(__file__).resolve().parent.parent / "automations.auto.yaml"
