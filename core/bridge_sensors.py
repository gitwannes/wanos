# --- file: core/bridge_sensors.py ---
"""Allowlisted WanOS sensors exposed to the Power dashboard bridge (W2)."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.well_known_entities import (
    ENTITY_COLD_WATER,
    ENTITY_OUTSIDE,
    ENTITY_WATER_HOT,
    ENTITY_WATERLINK_DIGITAL_METER,
)

# Fixed allowlist for Power Add-sensor picker (entity_id is the stable FK).
BRIDGE_SENSOR_ALLOWLIST: List[Dict[str, str]] = [
    {
        "entity_id": ENTITY_WATERLINK_DIGITAL_METER,
        "kind": "water_official",
        "unit": "m3",
        "default_name": "Water-Link",
    },
    {
        "entity_id": ENTITY_COLD_WATER,
        "kind": "water_cold",
        "unit": "L",
        "default_name": "Koud water",
    },
    {
        "entity_id": ENTITY_WATER_HOT,
        "kind": "water_hot",
        "unit": "L",
        "default_name": "Warm water",
    },
    {
        "entity_id": ENTITY_OUTSIDE,
        "kind": "ambient",
        "unit": "C",
        "default_name": "Ambient temperature",
    },
]

_ALLOW_BY_ID = {row["entity_id"]: row for row in BRIDGE_SENSOR_ALLOWLIST}

ResolveFn = Callable[[str], Optional[int]]
LastSeenFn = Callable[[int], Optional[int]]


def _display_name(meta: Optional[Dict[str, Any]], fallback: str) -> str:
    if not meta:
        return fallback
    name = meta.get("name")
    if name is not None and str(name).strip() != "":
        return str(name).strip()
    return fallback


def _coerce_float(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        if "temp" in raw:
            return _coerce_float(raw.get("temp"))
        if "value" in raw:
            return _coerce_float(raw.get("value"))
        return None
    text = str(raw).strip().replace(",", ".")
    for sep in (" ", "°"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    try:
        return float(text)
    except ValueError:
        return None


def resolve_sensor_value(
    *,
    entity_id: str,
    devices: Dict[Any, Any],
    outside_temp: Optional[float],
    resolve_idx: ResolveFn,
) -> Optional[float]:
    """Read a live numeric value for an allowlisted entity."""
    spec = _ALLOW_BY_ID.get(entity_id)
    if not spec:
        return None
    if spec["kind"] == "ambient":
        return _coerce_float(outside_temp)
    idx = resolve_idx(entity_id)
    if idx is None:
        return None
    return _coerce_float(devices.get(idx))


def list_bridge_sensors(
    *,
    device_metadata: Dict[Any, Any],
    devices: Dict[Any, Any],
    outside_temp: Optional[float],
    owm_last_poll_unix: Optional[int],
    resolve_idx: ResolveFn,
    last_seen_unix: Optional[LastSeenFn] = None,
) -> List[Dict[str, Any]]:
    """Allowlist rows with live name/value/updated_unix when resolvable."""
    by_entity: Dict[str, Dict[str, Any]] = {}
    for raw_idx, meta in (device_metadata or {}).items():
        if not isinstance(meta, dict):
            continue
        eid = str(meta.get("entity_id") or "").strip()
        if not eid:
            continue
        by_entity[eid] = {"idx": raw_idx, "meta": meta}

    out: List[Dict[str, Any]] = []
    for spec in BRIDGE_SENSOR_ALLOWLIST:
        eid = spec["entity_id"]
        hit = by_entity.get(eid)
        idx = resolve_idx(eid)
        present = hit is not None or idx is not None or spec["kind"] == "ambient"
        if not present:
            continue
        name = _display_name(hit["meta"] if hit else None, spec["default_name"])
        value = resolve_sensor_value(
            entity_id=eid,
            devices=devices,
            outside_temp=outside_temp,
            resolve_idx=resolve_idx,
        )
        updated: Optional[int] = None
        if spec["kind"] == "ambient":
            if owm_last_poll_unix is not None:
                try:
                    updated = int(owm_last_poll_unix)
                except (TypeError, ValueError):
                    updated = None
        elif idx is not None and last_seen_unix is not None:
            updated = last_seen_unix(int(idx))
        out.append(
            {
                "entity_id": eid,
                "kind": spec["kind"],
                "unit": spec["unit"],
                "name": name,
                "value": value,
                "available": value is not None,
                "updated_unix": updated,
            }
        )
    return out
