# --- file: core/event_catalog.py ---
"""
B10B system event catalog — fixed UUID + display name (identity authority).

Bus token for pickable/catalog events = UUID only.
Internal (non-catalog) EventType strings stay as readable enum values.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# (legacy EventType key, fixed UUID, approved UI name)
_SYSTEM_SEED_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("BLINDS_OPEN_TRIGGER", "a130c1d4-1bc9-4491-b126-81f716c045c9", "Blinds open"),
    ("BLINDS_CLOSE_TRIGGER", "70716703-5fc0-438b-8af5-db6a1cb1bd07", "Blinds close"),
    # B10E display names (UUIDs unchanged) — Morning/Evening lights windows
    ("MORNING_ON_TRIGGER", "9a6f9e9a-a571-472e-89ef-4b866b5c2525", "Morning lights on"),
    ("SUNRISE_TRIGGER", "7dd2bc22-f1fa-491f-a97d-085fd9b9d0c8", "Morning lights off"),
    ("SUNSET_TRIGGER", "bd0413be-926a-45ef-bdb8-1adfe3b7e8ab", "Evening lights on"),
    ("EVENING_OFF_TRIGGER", "443765ef-992a-4c90-9bda-5fce40cb70d2", "Evening lights off"),
    ("SAUNA_ON", "39120e7f-93e2-46ba-af70-9b6d7bf08df3", "Sauna ON"),
    ("SAUNA_OFF", "08b79199-86aa-4a1e-a29c-20ef2eb74e98", "Sauna OFF"),
    ("IR_ON", "056c3ade-659a-49e0-87f2-2c60e84ca792", "IR ON"),
    ("IR_OFF", "a97bba4d-78d3-4ce2-b134-fff36c2cd88c", "IR OFF"),
    ("SAUNA_SETPOINT_CHANGED", "9fa21346-3952-4267-b2fd-c3362e520431", "Sauna setpoint changed"),
    ("SAUNA_MODULATION_UPDATED", "b94ab2e2-a5d6-4651-9ff8-c832221c9169", "Sauna modulation updated"),
    ("SAUNA_SETPOINT_REACHED", "60821356-d372-4e53-a00b-fdd0377fe0e6", "Sauna setpoint reached"),
    ("SAUNA_HOLD", "718d81a1-c9bb-4f02-8b92-78de27c9aae9", "Sauna hold"),
    ("SAUNA_TIMER_EXPIRED", "25df4527-8989-433d-8ee7-c52fe8273289", "Sauna timer expired"),
    ("SAUNA_HOLD_TOGGLED", "97f7eb14-c136-4230-9a11-c393fb8eec19", "Sauna hold toggled"),
    ("SAUNA_TIMER_ADJUSTED", "8af93aec-f43a-422f-b022-1a1f9558c7f7", "Sauna timer adjusted"),
    ("SAUNA_DOOR_GRACE_EXPIRED", "b751d97c-38e0-413e-bcb1-fe03d14ec36b", "Sauna paused (door open)"),
    ("VENT_WAIT_EXPIRED", "94bbfd22-d226-4408-bc6d-3b4897b1ec81", "Sauna ventilator run start"),
    ("VENT_RUN_EXPIRED", "26a640cd-2ba3-4541-bf1d-17e45d5d60d0", "Sauna ventilator run expired"),
    ("IR_MODULATION_UPDATED", "8bcbaacf-b072-422d-a270-b7810228684b", "IR modulation updated"),
    ("TEMP_UPDATED", "0b334052-620b-4379-89fb-8a548948873e", "Temperature updated"),
    ("HUMIDITY_UPDATED", "317b453b-18bb-4083-8b62-e14ba2bc4d26", "Humidity updated"),
    ("POWER_UPDATED", "d6bebc9e-394e-4806-a007-4f863a7ccf5e", "Power updated"),
    ("WATER_PULSE", "cef390eb-f9e0-4757-ae34-0e7918d49a9e", "Water pulse"),
    ("KWH_PULSE", "a1f2fe49-82db-4011-a9bb-c8afdbd46358", "kWh pulse"),
    ("DOOR_CHANGED", "02d6b1d7-de0b-41f1-b89b-f371e2d35cea", "Door state changed"),
    ("HUB_STATE_CHANGED", "c3457c08-c26e-4ab7-8c32-76e0a746d6c3", "Hub state changed"),
    # B10E: bus key renamed from EXTERNAL_WEATHER_UPDATED (same UUID)
    ("SUNRISE_SUNSET_UPDATE", "0117e989-cf45-4359-98d3-9656284eb577", "Sunrise/sunset update"),
    ("SENSOR_ERROR", "fff4c790-1b10-4084-a11f-4d7bf519ce40", "Sensor error"),
)

# Key → UUID / UUID → key / key → display name
SYSTEM_KEY_TO_UUID: Dict[str, str] = {k: u for k, u, _ in _SYSTEM_SEED_ROWS}
SYSTEM_UUID_TO_KEY: Dict[str, str] = {u: k for k, u, _ in _SYSTEM_SEED_ROWS}
SYSTEM_KEY_TO_NAME: Dict[str, str] = {k: n for k, _, n in _SYSTEM_SEED_ROWS}
SYSTEM_UUID_TO_NAME: Dict[str, str] = {u: n for k, u, n in _SYSTEM_SEED_ROWS}

# Seeded in YAML / GET /api/events, but excluded from Blockly trigger/fire pickers.
# HUB_STATE_CHANGED is high-chatter hub telemetry — use device edges or specific events.
NON_PICKABLE_SYSTEM_UUIDS: frozenset[str] = frozenset(
    {
        SYSTEM_KEY_TO_UUID["HUB_STATE_CHANGED"],
    }
)

# B10E: always fireable as actions even when no listening rule (hardcoded handlers).
FIRE_ALWAYS_SYSTEM_KEYS: frozenset[str] = frozenset(
    {"SAUNA_ON", "SAUNA_OFF", "IR_ON", "IR_OFF"}
)
FIRE_ALWAYS_SYSTEM_UUIDS: frozenset[str] = frozenset(
    SYSTEM_KEY_TO_UUID[k] for k in FIRE_ALWAYS_SYSTEM_KEYS
)


def is_fire_always_system_event_id(event_id: str) -> bool:
    """True if this system UUID may be fired even with no Blockly listener."""
    return str(event_id) in FIRE_ALWAYS_SYSTEM_UUIDS


def system_seed_rows() -> List[Dict[str, Any]]:
    """YAML-shaped system rows (origin forced; confirm/enabled fixed)."""
    out: List[Dict[str, Any]] = []
    for key, eid, name in _SYSTEM_SEED_ROWS:
        out.append(
            {
                "id": eid,
                "name": name,
                "origin": "system",
                "show_on_dashboard": False,
                "require_confirmation": False,
                "enabled": True,
                # Internal marker for migrator/docs — not persisted to YAML
                "_legacy_key": key,
            }
        )
    return out


def system_seeds_for_yaml() -> List[Dict[str, Any]]:
    """Persistable system event rows (no _legacy_key)."""
    return [
        {
            "id": eid,
            "name": name,
            "origin": "system",
            "show_on_dashboard": False,
            "require_confirmation": False,
            "enabled": True,
        }
        for _key, eid, name in _SYSTEM_SEED_ROWS
    ]


def event_type_str(event_type: Any) -> str:
    """Normalize EventType | str → plain string token."""
    if event_type is None:
        return ""
    if hasattr(event_type, "value"):
        return str(event_type.value)
    return str(event_type)


def to_bus_token(event_type: Any) -> str:
    """
    Catalog keys (and their UUIDs) → UUID bus token.
    Everything else (internals) → unchanged string.
    """
    s = event_type_str(event_type)
    if not s:
        return s
    if s in SYSTEM_KEY_TO_UUID:
        return SYSTEM_KEY_TO_UUID[s]
    # B10E legacy bus key → same UUID as SUNRISE_SUNSET_UPDATE
    if s == "EXTERNAL_WEATHER_UPDATED":
        return SYSTEM_KEY_TO_UUID["SUNRISE_SUNSET_UPDATE"]
    return s


def legacy_key_for_bus_token(token: Any) -> str:
    """
    Resolve bus token → legacy EventType key when system catalog;
    otherwise return the token string unchanged (user UUID or internal).
    """
    s = event_type_str(token)
    if s in SYSTEM_UUID_TO_KEY:
        return SYSTEM_UUID_TO_KEY[s]
    return s


def is_system_bus_uuid(token: Any) -> bool:
    return event_type_str(token) in SYSTEM_UUID_TO_KEY


def is_blocky_pickable_event_id(token: Any) -> bool:
    """False for catalog rows that must not appear in Blockly event menus."""
    return event_type_str(token) not in NON_PICKABLE_SYSTEM_UUIDS


def display_name_for_event_id(
    event_id: str,
    events_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """UI label: catalog row name, else system constant, else raw id."""
    if events_by_id and event_id in events_by_id:
        name = events_by_id[event_id].get("name")
        if name:
            return str(name)
    if event_id in SYSTEM_UUID_TO_NAME:
        return SYSTEM_UUID_TO_NAME[event_id]
    return event_id


def normalize_event_name_key(name: str) -> str:
    """Trim + casefold for uniqueness compares."""
    return str(name or "").strip().casefold()
