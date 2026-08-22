# --- file: core/auto_off_store.py ---
"""Surgical read/write of auto_off_devices in automations.auto.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from core.auto_off_policy import (
    AUTO_OFF_ALLOWED_TYPES,
    sanitize_delay_map,
    sanitize_managed_list,
    sanitize_pertype_map,
    normalize_minutes,
)
from core.automations_store import _dump_root, load_automations_roundtrip

from core.product_type_policy import sanitize_product_type_overrides

AUTO_OFF_KEY = "auto_off_devices"
PRODUCT_TYPES_KEY = "device_product_types"
LEGACY_LIGHTING_KEY = "lighting"


def read_auto_off_config() -> Dict[str, Any]:
    """Return auto_off_devices + device_product_types from disk."""
    root, _ = load_automations_roundtrip()
    block = _read_auto_off_block(root)
    block["device_product_types"] = _read_product_types(root)
    return block


def auto_off_timer_payload_from_config(config: object) -> Dict[str, Any]:
    """In-memory auto-off payload for GET /api/state (same shape as read_auto_off_config)."""
    ao = getattr(config, "auto_off_devices", None)
    pt = getattr(config, "device_product_types", None) or {}
    if ao is None:
        block = _empty_block()
    else:
        dump = ao.model_dump() if hasattr(ao, "model_dump") else ao.dict()
        block = {
            "managed_auto_off": sanitize_managed_list(dump.get("managed_auto_off")),
            "default_auto_off_minutes": int(
                dump.get("default_auto_off_minutes")
                if dump.get("default_auto_off_minutes") is not None
                else 300
            ),
            "default_pertype_auto_off_minutes": sanitize_pertype_map(
                dump.get("default_pertype_auto_off_minutes")
            ),
            "auto_off_delays": sanitize_delay_map(dump.get("auto_off_delays")),
        }
    block["device_product_types"] = sanitize_product_type_overrides(
        pt if isinstance(pt, dict) else {}
    )
    return block


def _read_auto_off_block(root: object) -> Dict[str, Any]:
    """Return auto_off_devices block only (empty defaults if missing)."""
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


def _read_product_types(root: object) -> Dict[str, str]:
    if not isinstance(root, dict):
        return {}
    raw = root.get(PRODUCT_TYPES_KEY)
    return sanitize_product_type_overrides(raw if isinstance(raw, dict) else {})


def _empty_block() -> Dict[str, Any]:
    return {
        "managed_auto_off": [],
        "default_auto_off_minutes": 300,
        "default_pertype_auto_off_minutes": {},
        "auto_off_delays": {},
        "device_product_types": {},
    }


def write_auto_off_config(
    *,
    managed_auto_off: List[str],
    default_auto_off_minutes: int,
    default_pertype_auto_off_minutes: Dict[str, int],
    auto_off_delays: Dict[str, int],
    device_product_types: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Replace auto_off_devices surgically; optionally replace device_product_types.
    Strips legacy lighting: if present.
    Caller must validate eligibility / orphans / unresolved eids before calling.
    """
    managed = sanitize_managed_list(managed_auto_off)
    general = normalize_minutes(default_auto_off_minutes)
    pertype = sanitize_pertype_map(default_pertype_auto_off_minutes)
    delays = sanitize_delay_map(auto_off_delays)
    product_types = (
        sanitize_product_type_overrides(device_product_types)
        if device_product_types is not None
        else None
    )

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

    new_root = _merge_auto_off_into_root(root, block)
    if product_types is not None:
        new_root = _merge_product_types_into_root(new_root, product_types)

    if LEGACY_LIGHTING_KEY in new_root:
        del new_root[LEGACY_LIGHTING_KEY]

    _dump_root(new_root, path)
    result = {
        "managed_auto_off": managed,
        "default_auto_off_minutes": general,
        "default_pertype_auto_off_minutes": pertype,
        "auto_off_delays": delays,
    }
    if product_types is not None:
        result["device_product_types"] = product_types
    return result


def _merge_auto_off_into_root(root: dict, block: CommentedMap) -> CommentedMap:
    if AUTO_OFF_KEY in root:
        root[AUTO_OFF_KEY] = block
        return root
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
    return new_root


def _merge_product_types_into_root(root: dict, product_types: Dict[str, str]) -> CommentedMap:
    pt_map = CommentedMap()
    for k, v in product_types.items():
        pt_map[k] = v
    if PRODUCT_TYPES_KEY in root:
        if product_types:
            root[PRODUCT_TYPES_KEY] = pt_map
        elif PRODUCT_TYPES_KEY in root:
            del root[PRODUCT_TYPES_KEY]
        return root
    if not product_types:
        return root
    new_root = CommentedMap()
    inserted = False
    for k, v in root.items():
        if not inserted and k in (AUTO_OFF_KEY, "automations"):
            new_root[PRODUCT_TYPES_KEY] = pt_map
            inserted = True
        new_root[k] = v
    if not inserted:
        new_root[PRODUCT_TYPES_KEY] = pt_map
    return new_root


def auto_off_path() -> Path:
    return Path(__file__).resolve().parent.parent / "automations.auto.yaml"
