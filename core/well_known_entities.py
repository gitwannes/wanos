# --- file: core/well_known_entities.py ---
"""
Stable entity_id lookup keys for system fixtures.

entity_registry.auto.yaml remains the source of truth for entity_id ↔ idx.
Call sites resolve these strings via StateManager.resolve_entity_id /
EntityRegistry.resolve / AutomationEngine.resolve_entity_id — never bake
the numeric idx into business logic.
"""
from __future__ import annotations

from typing import Optional

# Sauna / IR / safety
ENTITY_SAUNA_DOOR = "sensor.door.sauna_deur"
ENTITY_SAUNA_HIGH = "sensor.temp_hum.sauna_high"
ENTITY_SAUNA_LOW = "sensor.temp_hum.sauna_low"
ENTITY_SAUNA_STATUS = "sensor.generic.sauna_status"
ENTITY_IR_STATUS = "sensor.generic.ir_status"
ENTITY_SAFETY_SSR = "switch.ssr.safety_ssr_12v"
# Pi power (5V) — sole hard-deny: never visible/selectable/commandable in operator UIs
ENTITY_SAFETY_WISC = "switch.safety.safety_wisc_5v"

# Hard-deny entity_ids (code fence; not stored in deviceexplorer_hide)
HARD_DENY_ENTITY_IDS = frozenset({ENTITY_SAFETY_WISC})


def is_hard_deny_entity_id(eid: Optional[str]) -> bool:
    if not eid:
        return False
    return str(eid).strip() in HARD_DENY_ENTITY_IDS


# Bathroom / water / outside
ENTITY_BATHROOM_VENT = "zwave.vent.badk_1e"
ENTITY_BATHROOM_HUM = "sensor.temp_hum.badk_1e"
ENTITY_WATER_HOT = "sensor.fluid.warm_water"
ENTITY_COLD_WATER = "sensor.fluid.koud_water"
ENTITY_OUTSIDE = "sensor.temp_hum.outside_temp_hum"

# Epson projector (D2 rename from switch.cinema_projector)
ENTITY_EPSON = "switch.epson"

# Host gauges / mains
ENTITY_HOST_CPU_TEMP = "sensor.temp_hum.host_cpu_temperature"
ENTITY_HOST_CPU_USAGE = "sensor.generic.host_cpu_usage"
ENTITY_HOST_MEMORY_FREE = "sensor.generic.host_memory_free"
ENTITY_HOST_DISK_FREE = "sensor.generic.host_disk_free_root"
ENTITY_HOST_LOG2RAM_FREE = "sensor.generic.host_log2ram_free"
ENTITY_HOST_LOAD_1M = "sensor.generic.host_load_average_1m"
ENTITY_HOST_LOAD_5M = "sensor.generic.host_load_average_5m"
ENTITY_HOST_LOAD_15M = "sensor.generic.host_load_average_15m"
ENTITY_MAINS_VOLTAGE = "sensor.generic.mains_voltage"
ENTITY_WANOS_DB_SIZE = "sensor.generic.wanos_db_size"

# B9A: status sensors — Blockly condition (if) only; never When / never action.
STATUS_CONDITION_ONLY_EIDS = frozenset({ENTITY_SAUNA_STATUS, ENTITY_IR_STATUS})

# B9A: published host gauges hidden from Blockly pickers only (still in state / Explorer).
BLOCKY_HOST_GAUGE_HIDDEN_EIDS = frozenset({ENTITY_HOST_LOAD_1M, ENTITY_HOST_LOAD_5M})

# B9A: Blockly display-name overrides for host gauges.
BLOCKY_HOST_GAUGE_LABELS = {
    ENTITY_HOST_CPU_TEMP: "Host CPU Temperature",
    ENTITY_HOST_CPU_USAGE: "Host CPU Usage",
    ENTITY_HOST_MEMORY_FREE: "Host Memory Free",
    ENTITY_HOST_DISK_FREE: "Host Disk Free (Root)",
    ENTITY_HOST_LOG2RAM_FREE: "Host Log2Ram Free",
    ENTITY_HOST_LOAD_15M: "Host average load %",
    ENTITY_WANOS_DB_SIZE: "WanOS DB size",
    ENTITY_MAINS_VOLTAGE: "Mains voltage",
}
