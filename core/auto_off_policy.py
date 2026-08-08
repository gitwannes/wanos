# --- file: core/auto_off_policy.py ---
"""Auto-off eligibility + delay precedence helpers."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Set

from core.well_known_entities import (
    ENTITY_IR_STATUS,
    ENTITY_SAFETY_SSR,
    ENTITY_SAFETY_WISC,
    ENTITY_SAUNA_DOOR,
    ENTITY_SAUNA_HIGH,
    ENTITY_SAUNA_LOW,
    ENTITY_SAUNA_STATUS,
    is_hard_deny_entity_id,
)

# Minutes bounds
AUTO_OFF_MINUTES_MIN = 1
AUTO_OFF_MINUTES_MAX = 720  # 12h

# device_metadata.type allow-list for type defaults + inventory
AUTO_OFF_ALLOWED_TYPES: frozenset[str] = frozenset({"switch", "light", "speaker"})

# Explicit device extras (type may be switch but still out)
AUTO_OFF_DEVICE_DENY_EIDS: frozenset[str] = frozenset({
    ENTITY_SAFETY_WISC,
    ENTITY_SAFETY_SSR,  # 71036 SSR
    "switch.cinema_projector",
})

# Hard-coded WanOS/WISC specials (also type-denylisted; listed for migrator clarity)
AUTO_OFF_SPECIAL_DENY_EIDS: frozenset[str] = frozenset({
    ENTITY_SAUNA_DOOR,
    ENTITY_SAUNA_HIGH,
    ENTITY_SAUNA_LOW,
    ENTITY_SAUNA_STATUS,
    ENTITY_IR_STATUS,
})


def normalize_minutes(value: Any) -> int:
    mins = int(value)
    if mins < AUTO_OFF_MINUTES_MIN or mins > AUTO_OFF_MINUTES_MAX:
        raise ValueError(
            f"auto-off minutes must be {AUTO_OFF_MINUTES_MIN}–{AUTO_OFF_MINUTES_MAX}, got {mins}"
        )
    return mins


def metadata_type_for_eid(eid: str, device_type: Optional[str] = None) -> str:
    """Prefer live metadata type; fall back to entity_id domain heuristics."""
    if device_type:
        t = str(device_type).strip().lower()
        if t == "media_player":
            return "speaker"
        if t in ("temp&hum",):
            return "temp_hum"
        if t == "shutter":
            return "blinds"
        return t
    e = str(eid or "").strip().lower()
    if not e:
        return "unknown"
    if e.startswith("hue."):
        return "light"
    if e.startswith("media_player."):
        return "speaker"
    if e.startswith("blinds."):
        return "blinds"
    if e.startswith("switch."):
        return "switch"
    if e.startswith("sensor.temp_hum.") or e.startswith("sensor.temp.") or e.startswith("sensor.hum."):
        return "temp_hum"
    if e.startswith("sensor.power."):
        return "power"
    if e.startswith("sensor.energy."):
        return "energy"
    if e.startswith("sensor.fluid."):
        return "fluid"
    if e.startswith("sensor.door."):
        return "door"
    if e.startswith("scene."):
        return "scene"
    if "voltage" in e:
        return "voltage"
    if e.startswith("sensor."):
        return "sensor"
    return "unknown"


def is_auto_off_device_denied(eid: str) -> bool:
    e = str(eid or "").strip()
    if not e:
        return True
    if is_hard_deny_entity_id(e):
        return True
    if e in AUTO_OFF_DEVICE_DENY_EIDS or e in AUTO_OFF_SPECIAL_DENY_EIDS:
        return True
    return False


def is_auto_off_eligible(eid: str, device_type: Optional[str] = None) -> bool:
    """True if eid may appear in managed_auto_off / inventory."""
    e = str(eid or "").strip()
    if not e or is_auto_off_device_denied(e):
        return False
    t = metadata_type_for_eid(e, device_type)
    return t in AUTO_OFF_ALLOWED_TYPES


def resolve_auto_off_minutes(
    *,
    eid: str,
    device_type: Optional[str],
    auto_off_delays: Mapping[str, int],
    default_pertype: Mapping[str, int],
    default_minutes: int,
) -> int:
    """Precedence: per-device → type → general."""
    e = str(eid).strip()
    if e in auto_off_delays:
        return int(auto_off_delays[e])
    t = metadata_type_for_eid(e, device_type)
    if t in default_pertype:
        return int(default_pertype[t])
    return int(default_minutes)


def sanitize_managed_list(entity_ids: Any) -> list[str]:
    out: list[str] = []
    seen: Set[str] = set()
    if not isinstance(entity_ids, list):
        return out
    for ref in entity_ids:
        eid = str(ref).strip()
        if not eid or eid in seen:
            continue
        seen.add(eid)
        out.append(eid)
    out.sort()
    return out


def sanitize_delay_map(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in raw.items():
        eid = str(k).strip()
        if not eid:
            continue
        out[eid] = normalize_minutes(v)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def sanitize_pertype_map(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in raw.items():
        t = str(k).strip().lower()
        if not t:
            continue
        out[t] = normalize_minutes(v)
    return dict(sorted(out.items(), key=lambda kv: kv[0]))
