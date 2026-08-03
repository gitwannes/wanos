# --- file: logic/history_ids.py ---
"""
Shared virtual IDX constants for history, Device Explorer, and scene tallies.

Why this module exists
----------------------
`20101` (sauna calc) and scene history keys are used from multiple packages
(state_manager, sensor_history_manager, automation_rules). A tiny shared module
avoids circular imports and keeps the IDX map in one place (also commented in
config.yaml).

Scene synthetic range (900000…)
-------------------------------
`device_events.idx` is an INTEGER. Scenes are named events (strings), not
hardware IDXs. We map event_name → int as:

    900000 + (crc32(event_name) & 0xFFFF)   →   900000 … 965535

900000 sits above real WanOS bands (1xxxx–8xxxx) so it never collides with
GPIO / SHT11 / Z-Wave / Hue / Sonos IDXs. The low 16 bits of CRC32 give a
stable id per event name (collision risk is negligible for a handful of scenes).
"""
from __future__ import annotations

import re
import zlib
from typing import Any, Optional

# 20101 : sauna temp — virtual composite (0.7×20001 + 0.3×20002); hum from 20001
SAUNA_CALC_IDX = 20101

# Scene history keys: 900000 + (crc32(event) & 0xFFFF) → 900000…965535
SCENE_IDX_BASE = 900000

HOST_CPU_USAGE_IDX = 22002
HOST_MEMORY_FREE_IDX = 22003
HOST_DISK_FREE_IDX = 22004
HOST_LOG2RAM_FREE_IDX = 22005
HOST_LOAD_1M_IDX = 22006
WANOS_DB_SIZE_IDX = 22009  # sum of SQLite .db + .db-wal footprints (MiB)
MAINS_VOLTAGE_IDX = 71046  # Z-Wave AC mains (Node 50 / Value 66561)

# Runtime SQLite bases (cwd); each may also have -wal / -shm sidecars
WANOS_SQLITE_BASES = (
    "sensor_history.db",
    "device_history.db",
    "sauna_sessions.db",
)

HOST_HISTORY_IDXS = (
    HOST_CPU_USAGE_IDX,
    HOST_MEMORY_FREE_IDX,
    HOST_DISK_FREE_IDX,
    HOST_LOG2RAM_FREE_IDX,
    HOST_LOAD_1M_IDX,
    WANOS_DB_SIZE_IDX,
    MAINS_VOLTAGE_IDX,
)


def scene_history_idx(event: str) -> int:
    return SCENE_IDX_BASE + (zlib.crc32(event.encode("utf-8")) & 0xFFFF)


def wanos_db_size_mib() -> float:
    """Total on-disk size of WanOS SQLite files (.db + .db-wal + .db-shm), in MiB."""
    import os
    total = 0
    for base in WANOS_SQLITE_BASES:
        for path in (base, f"{base}-wal", f"{base}-shm"):
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
    return round(total / (1024.0 * 1024.0), 2)


def parse_numeric_state(state: Any) -> Optional[float]:
    """Extract leading number from states like '23 %', '231 V', '12.4 MB', or raw floats."""
    if isinstance(state, (int, float)):
        return float(state)
    if not isinstance(state, str):
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", state.replace(",", "."))
    return float(m.group(0)) if m else None
