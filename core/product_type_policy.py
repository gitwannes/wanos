# --- file: core/product_type_policy.py ---
"""Resolved product type (light | switch) for Phase D1."""
from __future__ import annotations

from typing import Mapping, Optional

from core.well_known_entities import is_hard_deny_entity_id

PRODUCT_TYPES: frozenset[str] = frozenset({"light", "switch"})

VENT_MOTOR_WALL_SWITCH = "switch.vent.toilet_ventilatie"
PROJECTOR_EIDS: frozenset[str] = frozenset({"switch.cinema_projector", "switch.epson"})

# Provisioning types that appear on Timers & types with intrinsic read-only product type.
_INTRINSIC_PROVISIONING_TYPES: frozenset[str] = frozenset({
    "blinds",
    "speaker",
    "media_player",
    "motion",
    "power",
    "energy",
    "fluid",
    "door",
    "temp_hum",
    "temp",
    "hum",
    "sensor",
    "scene",
    "unknown",
    "voltage",
    "shutter",
})


def is_vent_motor_eid(eid: str) -> bool:
    """Vent motor actuators (read-only switch); wall switch is excluded."""
    e = str(eid or "").strip().lower()
    if e.startswith("zwave.vent."):
        return True
    if not e.startswith("switch.vent."):
        return False
    return e != VENT_MOTOR_WALL_SWITCH


def is_ssr_or_safety_eid(eid: str) -> bool:
    e = str(eid or "").strip().lower()
    return e.startswith("switch.ssr.") or e.startswith("switch.safety.")


def is_hue_physical_relay(eid: str) -> bool:
    return "hue_physical" in str(eid or "").lower()


def is_binary_actuator(
    *,
    eid: str,
    origin: Optional[str],
    device_type: Optional[str],
) -> bool:
    """Z-Wave / RFX binary actuators eligible for light|switch override."""
    o = str(origin or "").lower()
    t = str(device_type or "").lower()
    if o not in ("zwave", "rfxcom"):
        return False
    if t not in ("switch", "light"):
        return False
    if is_ssr_or_safety_eid(eid) or is_vent_motor_eid(eid):
        return False
    return True


def is_product_type_editable(
    eid: str,
    *,
    origin: Optional[str] = None,
    device_type: Optional[str] = None,
) -> bool:
    """True when Timers & types may write device_product_types for this eid."""
    e = str(eid or "").strip()
    if not e or is_hard_deny_entity_id(e):
        return False
    if (origin or "").lower() == "hue":
        return False
    if is_ssr_or_safety_eid(e) or is_vent_motor_eid(e) or e in PROJECTOR_EIDS:
        return False
    if is_hue_physical_relay(e):
        return True
    if e == VENT_MOTOR_WALL_SWITCH:
        return True
    if is_binary_actuator(eid=e, origin=origin, device_type=device_type):
        return True
    # Binary actuators by entity_id prefix (Z-Wave / RFX / legacy switch.*).
    t = str(device_type or "").lower()
    if t in ("switch", "light", ""):
        if e.startswith("zwave.vent."):
            return False
        if e.startswith("zwave.") or e.startswith("rfx."):
            return True
        if e.startswith("switch.") and not is_ssr_or_safety_eid(e) and not is_vent_motor_eid(e):
            # Exclude class prefixes already handled; allow plain switch.* and wall switch.
            if e.startswith("switch.ssr.") or e.startswith("switch.safety."):
                return False
            return True
    return False


def is_timers_types_inventory_row(
    eid: str,
    *,
    origin: Optional[str] = None,
    device_type: Optional[str] = None,
) -> bool:
    """Devices listed on Timers & types (inventory), including read-only rows."""
    e = str(eid or "").strip()
    if not e or is_hard_deny_entity_id(e):
        return False
    if str(device_type or "").lower() == "scene":
        return False
    if (origin or "").lower() == "automation":
        return False
    return True


def resolve_product_type(
    eid: str,
    *,
    origin: Optional[str] = None,
    overrides: Optional[Mapping[str, str]] = None,
) -> str:
    """
    Resolved product type for Explorer / auto-off tier / labels.

    Hue origin → light (no override). Else override ?? switch.
    """
    if (origin or "").lower() == "hue":
        return "light"
    e = str(eid or "").strip()
    raw = (overrides or {}).get(e)
    if raw is not None:
        v = str(raw).strip().lower()
        if v in PRODUCT_TYPES:
            return v
    return "switch"


def product_type_row_display(
    eid: str,
    *,
    origin: Optional[str],
    device_type: Optional[str],
    overrides: Optional[Mapping[str, str]],
) -> tuple[str, bool]:
    """
    Return (display_value, editable) for Timers & types product type column.
    display_value is light|switch|speaker|shutter|door|… for read-only rows.
    """
    resolved = resolve_product_type(eid, origin=origin, overrides=overrides)
    if is_product_type_editable(eid, origin=origin, device_type=device_type):
        return resolved, True
    o = str(origin or "").lower()
    t = str(device_type or "").lower()
    if o == "hue":
        return "light", False
    if t in ("speaker", "media_player"):
        return "speaker", False
    if t in ("blinds", "shutter"):
        return "shutter", False
    if t in _INTRINSIC_PROVISIONING_TYPES:
        return t if t != "shutter" else "shutter", False
    return resolved, False


def sanitize_product_type_overrides(raw: object) -> dict[str, str]:
    """Keep only light overrides (switch is birth default; omit from YAML)."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        eid = str(k).strip()
        if not eid:
            continue
        val = str(v).strip().lower()
        if val == "light":
            out[eid] = "light"
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def auto_off_type_tier(
    eid: str,
    device_type: Optional[str],
    *,
    origin: Optional[str] = None,
    overrides: Optional[Mapping[str, str]] = None,
) -> str:
    """Type key for auto-off per-type defaults: light | switch | speaker | …"""
    from core.auto_off_policy import metadata_type_for_eid

    prov = metadata_type_for_eid(eid, device_type)
    if prov == "speaker":
        return "speaker"
    if prov in ("blinds", "door", "fluid", "power", "energy", "temp_hum", "motion", "sensor", "scene", "unknown"):
        return prov
    return resolve_product_type(eid, origin=origin, overrides=overrides)
