# --- file: core/entity_id_list.py ---
"""
Generate a fixed-width entity_id authoring report.

Used by GET /api/admin/entity-id-list (Admin → System Commands download).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

ROOT = Path(__file__).resolve().parent.parent

REGISTRY_FILENAME = "entity_registry.auto.yaml"

# Scene history keys (logic/history_ids.py): 900000 + (crc32(event) & 0xFFFF).
# These are not authoring IDs — automations use event: "SCENE_…" strings.
SCENE_IDX_BASE = 900000

# Column order for the fixed-width report.
COLUMNS = (
    "idx",
    "entity_id",
    "domain",
    "type",
    "prefix",
    "origin",
    "status",
    "name",
    "name_at_birth",
    "hidden",
)

# Z-Wave idx band → device type (mirrors config_zwave.auto.yaml comments / bridge).
_ZWAVE_TYPE_BY_BAND = (
    (71000, 71999, "switch"),
    (72000, 72999, "switch"),
    (73000, 73999, "blinds"),
    (74000, 74999, "power"),
    (75000, 75999, "sensor"),
    (76000, 76999, "temp_hum"),
)


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Resolve WanOS root (directory that holds entity_registry.auto.yaml / config.yaml)."""
    here = (start or Path(__file__).resolve()).resolve()
    if here.is_file():
        here = here.parent
    candidates = [here, here.parent, Path.cwd(), Path.cwd().parent]
    for base in candidates:
        if (base / REGISTRY_FILENAME).is_file() or (base / "config.yaml").is_file():
            return base
    return ROOT


def load_yaml(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # Callers that care (CLI) can print; API path just skips broken enrichment.
        return None


def split_entity_id(entity_id: str) -> Tuple[str, str, str]:
    """
    Return (domain, type_hint, prefix).

    Examples:
      sensor.door.sauna_deur     → sensor, door, sensor.door
      switch.vent.foo            → switch, vent, switch.vent
      media_player.living        → media_player, media_player, media_player
      hue.group.living_hue       → hue, group, hue.group
      blinds.cinema              → blinds, blinds, blinds
    """
    parts = [p for p in str(entity_id).split(".") if p]
    if not parts:
        return "", "", ""
    domain = parts[0]
    if len(parts) == 1:
        return domain, domain, domain
    if len(parts) == 2:
        # domain.slug → type is the domain itself (e.g. media_player, blinds, switch)
        return domain, domain, domain
    # domain.subtype.slug... → type = subtype, prefix = domain.subtype
    subtype = parts[1]
    prefix = f"{domain}.{subtype}"
    return domain, subtype, prefix


def is_synthetic_scene_history(idx: int, entity_id: str = "", dtype: str = "", origin: str = "") -> bool:
    """
    True for scene fire history keys — exclude from the authoring entity_id list.

    Matches idx >= 900000, unknown.idx_9* births, or type/origin scene+automation.
    """
    if idx >= SCENE_IDX_BASE:
        return True
    eid = str(entity_id or "")
    if eid.startswith("unknown.idx_9"):
        return True
    if dtype == "scene" and origin == "automation":
        return True
    if eid.startswith("scene."):
        return True
    return False


def origin_from_idx(idx: int) -> str:
    """Best-effort origin from WanOS idx bands (see config.yaml IDX mapping)."""
    if idx >= SCENE_IDX_BASE:
        return "automation"
    if 10000 <= idx <= 19999:
        return "gpio_input"
    if 20000 <= idx <= 20099:
        return "sht11"
    if idx == 20101:
        return "system"
    if 21000 <= idx <= 21999:
        return "system"
    if 22000 <= idx <= 22999:
        return "system"
    if idx == 30001:
        return "owm"
    if 40000 <= idx <= 49999:
        return "rfxcom"
    if 50000 <= idx <= 59999:
        return "hue"
    if 60000 <= idx <= 60999:
        return "sonos"
    if 61000 <= idx <= 61999:
        return "onkyo"
    if 70000 <= idx <= 79999:
        return "zwave"
    if idx == 80001:
        return "epson"
    return ""


def device_type_from_idx(idx: int, domain: str, type_hint: str) -> str:
    """Prefer typed subtype from entity_id; fall back to Z-Wave band / domain."""
    # Multi-segment entity ids already carry a useful type (door, vent, power, …).
    if type_hint and type_hint != domain:
        return type_hint
    for lo, hi, dtype in _ZWAVE_TYPE_BY_BAND:
        if lo <= idx <= hi:
            return dtype
    # Map common domains to device_metadata-style types.
    mapping = {
        "blinds": "blinds",
        "media_player": "speaker",
        "scene": "scene",
        "hue": "light",
        "switch": "switch",
        "sensor": "sensor",
        "unknown": "unknown",
    }
    return mapping.get(domain, type_hint or domain or "unknown")


def _pipe_name(raw: Any) -> Optional[str]:
    """Parse 'uuid | friendly name' or 'path | name | id' style config values."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in ("null", "none", "~"):
        return None
    if "|" in text:
        return text.split("|", 1)[1].split("|", 1)[0].strip() or None
    return None


def enrich_from_configs(root: Path) -> Tuple[Dict[int, Dict[str, Any]], Set[str]]:
    """
    Build idx → {name, type, origin} and a set of hidden entity_ids from configs.
    Best-effort only; missing/broken files are skipped.
    """
    by_idx: Dict[int, Dict[str, Any]] = {}
    hidden: Set[str] = set()

    def put(idx: Any, *, name: Optional[str] = None, dtype: Optional[str] = None, origin: Optional[str] = None) -> None:
        try:
            i = int(idx)
        except (TypeError, ValueError):
            return
        row = by_idx.setdefault(i, {})
        if name and not row.get("name"):
            row["name"] = name
        if dtype and not row.get("type"):
            row["type"] = dtype
        if origin and not row.get("origin"):
            row["origin"] = origin

    # --- config_hardware.yaml ---
    hw = load_yaml(root / "config_hardware.yaml") or {}
    gpio = hw.get("gpio_input") or hw.get("gpio_inputs") or {}
    if isinstance(gpio, dict):
        for node in gpio.values():
            if not isinstance(node, dict):
                continue
            put(node.get("idx"), name=node.get("name"), dtype=node.get("type"), origin="gpio_input")
    sht = hw.get("sht11_sensors") or {}
    if isinstance(sht, dict):
        for node in sht.values():
            if not isinstance(node, dict):
                continue
            put(node.get("idx"), name=node.get("name"), dtype="temp_hum", origin="sht11")

    # --- config.yaml (master) + automations.auto.yaml (exclude / lighting / rules) ---
    cfg = load_yaml(root / "config.yaml") or {}
    auto_cfg = load_yaml(root / "automations.auto.yaml") or {}
    weather = cfg.get("weather") or {}
    if isinstance(weather, dict) and weather.get("idx") is not None:
        put(weather.get("idx"), name=weather.get("name") or "Outside temp & hum", dtype="temp_hum", origin="owm")
    for rfx in cfg.get("native_rfx") or []:
        if isinstance(rfx, dict):
            put(rfx.get("virtual_idx"), name=rfx.get("name"), dtype="switch", origin="rfxcom")
    sonos = (cfg.get("sonos") or {}).get("device_map") or {}
    if isinstance(sonos, dict):
        for idx, node in sonos.items():
            name = node.get("name") if isinstance(node, dict) else None
            put(idx, name=name, dtype="speaker", origin="sonos")
    onkyo = (cfg.get("onkyo") or {}).get("device_map") or {}
    if isinstance(onkyo, dict):
        for idx, node in onkyo.items():
            name = node.get("name") if isinstance(node, dict) else None
            put(idx, name=name, dtype="speaker", origin="onkyo")
    if cfg.get("epson"):
        put(80001, name="cinema projector", dtype="switch", origin="epson")
    for eid in auto_cfg.get("deviceexplorer_exclude") or cfg.get("deviceexplorer_exclude") or []:
        if eid:
            hidden.add(str(eid).strip())

    # Built-ins seeded by StateManager.rebuild_core_metadata
    put(20101, name="sauna temp", dtype="temp_hum", origin="system")
    put(21001, name="sauna status", dtype="sensor", origin="system")
    put(21002, name="IR status", dtype="sensor", origin="system")
    for s_idx, s_name in {
        22001: "Host CPU Temperature",
        22002: "Host CPU Usage",
        22003: "Host Memory Free",
        22004: "Host Disk Free (Root)",
        22005: "Host Log2Ram Free",
        22006: "Host Load Average (1m)",
        22007: "Host Load Average (5m)",
        22008: "Host Load Average (15m)",
        22009: "WanOS DB size",
    }.items():
        put(s_idx, name=s_name, dtype="sensor", origin="system")

    # --- config_hue.yaml (or hue block in config.yaml) ---
    hue_doc = load_yaml(root / "config_hue.yaml") or {}
    hue = hue_doc.get("hue") if isinstance(hue_doc, dict) else None
    if not isinstance(hue, dict):
        hue = cfg.get("hue") if isinstance(cfg.get("hue"), dict) else {}
    for idx, raw in (hue.get("device_map") or {}).items():
        put(idx, name=_pipe_name(raw) or f"Hue Light {idx}", dtype="light", origin="hue")
    for idx, raw in (hue.get("group_map") or {}).items():
        put(idx, name=_pipe_name(raw) or f"Hue Group {idx}", dtype="light", origin="hue")

    # --- config_zwave.auto.yaml ---
    zw = load_yaml(root / "config_zwave.auto.yaml") or {}
    zwave = zw.get("zwave") if isinstance(zw, dict) else None
    if isinstance(zwave, dict):
        for eid in zwave.get("hidden_nodes") or []:
            if eid:
                hidden.add(str(eid).strip())
        for idx, raw in (zwave.get("device_map") or {}).items():
            try:
                i = int(idx)
            except (TypeError, ValueError):
                continue
            name = _pipe_name(raw)
            # Strip trailing "= comment" annotations from names
            if name and " = " in name:
                name = name.split(" = ", 1)[0].strip()
            dtype = device_type_from_idx(i, "switch", "switch")
            for lo, hi, band_type in _ZWAVE_TYPE_BY_BAND:
                if lo <= i <= hi:
                    dtype = band_type
                    break
            put(i, name=name, dtype=dtype, origin="zwave")

    return by_idx, hidden


def load_registry(path: Path) -> Dict[int, Dict[str, Any]]:
    raw = load_yaml(path)
    if not isinstance(raw, dict):
        return {}
    entries = raw.get("entities", raw)
    if not isinstance(entries, dict):
        return {}
    by_idx: Dict[int, Dict[str, Any]] = {}
    for key, val in entries.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(val, str):
            by_idx[idx] = {"entity_id": val, "status": "active"}
        elif isinstance(val, dict) and val.get("entity_id"):
            row = {
                "entity_id": str(val["entity_id"]),
                "status": str(val.get("status") or "active"),
            }
            if "name_at_birth" in val:
                row["name_at_birth"] = val.get("name_at_birth")
            by_idx[idx] = row
    return by_idx


def build_rows(root: Path) -> List[Dict[str, str]]:
    registry_path = root / REGISTRY_FILENAME
    if not registry_path.is_file():
        raise FileNotFoundError(f"Missing {registry_path}")

    by_idx = load_registry(registry_path)
    enrich, hidden_eids = enrich_from_configs(root)

    rows: List[Dict[str, str]] = []
    for idx in sorted(by_idx.keys()):
        reg = by_idx[idx]
        eid = str(reg.get("entity_id") or "")
        domain, type_hint, prefix = split_entity_id(eid)
        meta = enrich.get(idx) or {}

        origin = str(meta.get("origin") or origin_from_idx(idx) or "")
        dtype = str(meta.get("type") or device_type_from_idx(idx, domain, type_hint) or "")
        if is_synthetic_scene_history(idx, eid, dtype, origin):
            continue
        name = str(meta.get("name") or reg.get("name_at_birth") or "")
        name_at_birth = str(reg.get("name_at_birth") or "")
        status = str(reg.get("status") or "active")
        is_hidden = "yes" if eid in hidden_eids else ""

        rows.append({
            "idx": str(idx),
            "entity_id": eid,
            "domain": domain,
            "type": dtype,
            "prefix": prefix,
            "origin": origin,
            "status": status,
            "name": name,
            "name_at_birth": name_at_birth,
            "hidden": is_hidden,
        })
    return rows


def format_fixed_width(rows: List[Dict[str, str]], columns: Tuple[str, ...] = COLUMNS) -> str:
    widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            widths[c] = max(widths[c], len(str(row.get(c, ""))))

    def fmt(row: Dict[str, str]) -> str:
        return "  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns)

    header = {c: c for c in columns}
    sep = {c: "-" * widths[c] for c in columns}
    lines = [fmt(header), fmt(sep)]
    lines.extend(fmt(r) for r in rows)
    lines.append("")
    lines.append(f"# rows: {len(rows)}")
    lines.append(f"# columns: {', '.join(columns)}")
    lines.append("# source: entity_registry.auto.yaml (+ config_*.yaml / automations.auto.yaml enrichment)")
    lines.append(
        f"# excluded: synthetic scene history (idx>={SCENE_IDX_BASE} / "
        "unknown.idx_9* / scene.* / type=scene+origin=automation)"
    )
    lines.append("")
    return "\n".join(lines)


def generate_entity_id_list_text(root: Optional[Path] = None) -> str:
    """Build the full fixed-width report from live registry + config enrichment."""
    base = (root or ROOT).resolve()
    rows = build_rows(base)
    return format_fixed_width(rows)
