# --- file: core/entity_registry_check.py ---
"""
Shared entity_id / automation consistency checks.

Used by:
  - GET /api/debug/entity-registry-check   (Admin Debug button — keep)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Device-ish numeric literals still lurking in Python after migration.
# Require a device-access/comparison context so ports (e.g. 60128) are ignored.
MAGIC_IDX_RE = re.compile(
    r"(?:devices\.get\(|devices\[|\[\s*|==\s*|!=\s*|idx\s*==\s*|"
    r"[\"']idx[\"']\s*:\s*)"
    r"(7[1-6]\d{3}|4\d{4}|5[01]\d{3}|6\d{4}|80001|1[01]\d{3}|20\d{3}|21\d{3}|22\d{3}|30001)\b"
)

# Virtual / non-device idxs that may remain as bare ints in code.
ALLOWLIST_IDXS = {
    90001,  # bathroom vent lock flag
}

SCAN_DIRS = ("logic", "core/event_handlers", "hardware")
SCAN_SKIP_FILES = {
    "entity_registry_check.py",
    "entity_registry.py",
}

AUTOMATION_IDX_RE = re.compile(r"^(\s*(?:-\s*)?)idx:\s*(\d+)\s*(#.*)?$", re.MULTILINE)
AUTOMATION_EID_RE = re.compile(r"^(\s*(?:-\s*)?)entity_id:\s*([^\s#]+)(.*)$", re.MULTILINE)
TOP_LEVEL_RE = re.compile(r"^[A-Za-z0-9_]")


def _load_registry(path: Path) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, int]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("entities", raw) if isinstance(raw, dict) else {}
    by_idx: Dict[int, Dict[str, Any]] = {}
    eid_to_idx: Dict[str, int] = {}
    for key, val in (entries or {}).items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(val, str):
            row = {"entity_id": val, "status": "active"}
        elif isinstance(val, dict) and val.get("entity_id"):
            row = {
                "entity_id": str(val["entity_id"]),
                "status": str(val.get("status") or "active"),
            }
        else:
            continue
        by_idx[idx] = row
        if row["status"] != "removed":
            eid = row["entity_id"]
            if eid in eid_to_idx and eid_to_idx[eid] != idx:
                # collision noted later
                pass
            eid_to_idx[eid] = idx
    return by_idx, eid_to_idx


def _automations_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    in_auto = False
    for line in lines:
        stripped = line.lstrip("\r\n")
        if re.match(r"^automations:\s*(#.*)?$", stripped):
            in_auto = True
            out.append(line)
            continue
        if in_auto and TOP_LEVEL_RE.match(stripped) and not stripped.startswith("automations:"):
            break
        if in_auto:
            out.append(line)
    return "".join(out)


def _scan_python_magic_idxs(root: Path) -> List[str]:
    hits: List[str] = []
    for rel in SCAN_DIRS:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.name in SCAN_SKIP_FILES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    continue
                for m in MAGIC_IDX_RE.finditer(line):
                    idx = int(m.group(1))
                    if idx in ALLOWLIST_IDXS:
                        continue
                    # Skip entity_id string literals that contain digits coincidentally — already filtered by word boundary
                    hits.append(f"{path.relative_to(root)}:{i}: {line.strip()[:120]}".encode("ascii", "replace").decode("ascii"))
    return hits


def run_entity_cutover_checks(
    *,
    root: Optional[Path] = None,
    registry_path: Optional[Path] = None,
    config_path: Optional[Path] = None,
    device_metadata: Optional[Dict[Any, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns a report dict:
      ok: bool
      errors: list[str]
      warnings: list[str]
      stats: dict
    """
    root = root or ROOT
    registry_path = registry_path or (root / "entity_registry.auto.yaml")
    config_path = config_path or (root / "config.yaml")
    automations_path = root / "automations.auto.yaml"

    errors: List[str] = []
    warnings: List[str] = []
    stats: Dict[str, Any] = {}

    if not registry_path.exists():
        errors.append(f"Missing registry file: {registry_path}")
        return {"ok": False, "errors": errors, "warnings": warnings, "stats": stats}

    if not config_path.exists():
        errors.append(f"Missing config file: {config_path}")
        return {"ok": False, "errors": errors, "warnings": warnings, "stats": stats}

    by_idx, eid_to_idx = _load_registry(registry_path)
    active = {i: r for i, r in by_idx.items() if r.get("status") != "removed"}
    removed = {i: r for i, r in by_idx.items() if r.get("status") == "removed"}
    stats["registry_active"] = len(active)
    stats["registry_removed"] = len(removed)

    # Empty entity_ids
    for idx, row in active.items():
        if not row.get("entity_id"):
            errors.append(f"Registry idx {idx} has empty entity_id")

    # Collisions (same entity_id → multiple idxs among active)
    seen: Dict[str, int] = {}
    for idx, row in active.items():
        eid = row["entity_id"]
        if eid in seen:
            errors.append(f"Collision: '{eid}' used by idx {seen[eid]} and {idx}")
        else:
            seen[eid] = idx

    # Automations block (prefer automations.auto.yaml; fall back to config.yaml)
    config_text = config_path.read_text(encoding="utf-8")
    if automations_path.exists():
        auto_file_text = automations_path.read_text(encoding="utf-8")
        auto_text = _automations_block(auto_file_text) or auto_file_text
        auto_source = "automations.auto.yaml"
    else:
        auto_file_text = config_text
        auto_text = _automations_block(config_text)
        auto_source = "config.yaml"
        warnings.append("automations.auto.yaml missing — checking automations in config.yaml")

    leftover_idxs = AUTOMATION_IDX_RE.findall(auto_text)
    stats["automation_leftover_idxs"] = len(leftover_idxs)
    for _indent, idx_s, _rest in leftover_idxs:
        errors.append(f"Automations still has numeric idx: {idx_s}")

    eids_in_rules = [m[1] for m in AUTOMATION_EID_RE.findall(auto_text)]
    stats["automation_entity_ids"] = len(eids_in_rules)
    for eid in eids_in_rules:
        if eid not in eid_to_idx:
            # might be removed
            removed_hit = next((i for i, r in removed.items() if r.get("entity_id") == eid), None)
            if removed_hit is not None:
                errors.append(f"Automation refs removed entity_id '{eid}' (was idx {removed_hit})")
            else:
                errors.append(f"Automation refs unknown entity_id '{eid}'")

    # Structured config blocks (entity_id-only after Script A)
    try:
        raw_cfg = yaml.safe_load(config_text) or {}
    except yaml.YAMLError as exc:
        errors.append(f"config.yaml parse error: {exc}")
        raw_cfg = {}

    try:
        if automations_path.exists():
            raw_auto = yaml.safe_load(auto_file_text) or {}
        else:
            raw_auto = {}
    except yaml.YAMLError as exc:
        errors.append(f"automations.auto.yaml parse error: {exc}")
        raw_auto = {}

    # Merge auto domains (auto file wins; legacy config.yaml fallback)
    merged_auto = {
        "deviceexplorer_hide": raw_auto.get("deviceexplorer_hide"),
        "lighting": raw_auto.get("lighting", raw_cfg.get("lighting")),
        "automations": raw_auto.get("automations", raw_cfg.get("automations")),
    }
    stats["automations_source"] = auto_source

    def _require_eids(label: str, refs: List[Any]) -> None:
        for ref in refs:
            eid = str(ref).strip()
            if not eid:
                continue
            if re.fullmatch(r"\d+", eid):
                errors.append(f"{label} still has numeric idx: {eid}")
                continue
            if eid not in eid_to_idx:
                removed_hit = next((i for i, r in removed.items() if r.get("entity_id") == eid), None)
                if removed_hit is not None:
                    errors.append(f"{label} refs removed entity_id '{eid}' (was idx {removed_hit})")
                else:
                    errors.append(f"{label} refs unknown entity_id '{eid}'")

    hide = merged_auto.get("deviceexplorer_hide")
    if hide is None:
        errors.append("deviceexplorer_hide missing from automations.auto.yaml")
    elif not isinstance(hide, list):
        errors.append("deviceexplorer_hide must be a list")
    else:
        _require_eids("deviceexplorer_hide", hide)
        stats["deviceexplorer_hide"] = len(hide)
        for ref in hide:
            eid = str(ref).strip()
            if eid == "switch.safety.safety_wisc_5v":
                errors.append("deviceexplorer_hide must not contain hard-deny eid switch.safety.safety_wisc_5v")

    hw = (raw_cfg.get("hardware_links") or {}).get("power_meters") or {}
    if not isinstance(hw, dict):
        errors.append("hardware_links.power_meters must be a map")
    else:
        _require_eids("hardware_links.power_meters keys", list(hw.keys()))
        _require_eids("hardware_links.power_meters values", list(hw.values()))
        stats["power_meter_links"] = len(hw)

    travel = ((raw_cfg.get("blinds") or {}).get("travel_times")) or {}
    if isinstance(travel, dict):
        _require_eids("blinds.travel_times", list(travel.keys()))
        stats["blinds_travel_times"] = len(travel)

    lighting = merged_auto.get("lighting") or {}
    managed = lighting.get("managed_lights") or []
    delays = lighting.get("auto_off_delays") or {}
    if isinstance(managed, list):
        _require_eids("lighting.managed_lights", managed)
        stats["managed_lights"] = len(managed)
    if isinstance(delays, dict):
        _require_eids("lighting.auto_off_delays", list(delays.keys()))

    history = raw_cfg.get("history") or {}
    if "tracked_idxs" in history:
        errors.append("history.tracked_idxs must be renamed to tracked_entities")
    tracked = history.get("tracked_entities") or []
    if isinstance(tracked, list):
        _require_eids("history.tracked_entities", tracked)
        stats["tracked_entities"] = len(tracked)

    zwave_path = root / "config_zwave.auto.yaml"
    if zwave_path.exists():
        try:
            yaml.safe_load(zwave_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"config_zwave.auto.yaml parse error: {exc}")

    # Live metadata (optional — when WanOS is running)
    if device_metadata is not None:
        live_missing = []
        live_ok = 0
        for key, meta in device_metadata.items():
            if not isinstance(meta, dict):
                continue
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            eid = meta.get("entity_id")
            if not eid:
                live_missing.append(idx)
            else:
                live_ok += 1
                reg = by_idx.get(idx)
                if reg and reg.get("entity_id") != eid:
                    warnings.append(
                        f"Live metadata idx {idx} entity_id '{eid}' != registry '{reg.get('entity_id')}'"
                    )
        stats["live_metadata_with_entity_id"] = live_ok
        stats["live_metadata_missing_entity_id"] = len(live_missing)
        if live_missing:
            sample = ", ".join(str(i) for i in live_missing[:12])
            more = f" (+{len(live_missing) - 12})" if len(live_missing) > 12 else ""
            errors.append(f"Live device_metadata missing entity_id for idxs: {sample}{more}")

    # Python magic idxs — leftover bare device numbers in scanned Python.
    # Cleared via entity_id resolve; 90001 (vent lock) remains allowlisted.
    magic = _scan_python_magic_idxs(root)
    stats["python_magic_idx_hits"] = len(magic)
    for hit in magic[:40]:
        warnings.append(f"Python magic idx: {hit}")
    if len(magic) > 40:
        warnings.append(f"Python magic idx: … +{len(magic) - 40} more")

    ok = len(errors) == 0
    report = {"ok": ok, "errors": errors, "warnings": warnings, "stats": stats}
    report["report_text"] = format_entity_cutover_report(report)
    return report


# Human-readable labels for stats keys (shown in CLI + Admin modal).
_STAT_HELP: Dict[str, str] = {
    "registry_active": "active rows in entity_registry.auto.yaml (idx <-> entity_id)",
    "registry_removed": "orphan rows kept with status=removed (not purged)",
    "automation_leftover_idxs": "numeric idx: still under automations: (must be 0)",
    "automation_entity_ids": "entity_id refs found in automations: rules",
    "deviceexplorer_hide": "entity_ids soft-hidden from Device Explorer",
    "power_meter_links": "switch->meter links in hardware_links.power_meters",
    "blinds_travel_times": "per-blind travel overrides in blinds.travel_times",
    "managed_lights": "lights/groups in lighting.managed_lights (auto-off)",
    "tracked_entities": "sensors in history.tracked_entities",
    "automations_source": "file providing automations/lighting/hide (auto preferred)",
    "python_magic_idx_hits": "bare device idxs still in Python (warnings only)",
    "live_metadata_with_entity_id": "live RAM devices that already have entity_id",
    "live_metadata_missing_entity_id": "live RAM devices missing entity_id (error if >0)",
}


def format_entity_cutover_report(report: Dict[str, Any]) -> str:
    """
    CLI / Admin modal text for a cutover check report.
    Keep this the single source of interpretive copy.
    """
    lines: List[str] = []
    ok = bool(report.get("ok"))
    stats = report.get("stats") or {}
    warnings = list(report.get("warnings") or [])
    errors = list(report.get("errors") or [])
    live = "live_metadata_with_entity_id" in stats or "live_metadata_missing_entity_id" in stats

    lines.append("ENTITY REGISTRY / CUTOVER CHECK")
    lines.append("=" * 40)
    lines.append("")
    lines.append("How to read this report")
    lines.append("- GREEN (ok=true, no ERRORS): registry + config entity_id refs are consistent.")
    lines.append("  Automations are entity_id-only (no numeric idx in rules). Smoke-test after deploy.")
    lines.append("- RED (any ERRORS): fix before relying on automations / further cutover cleanup.")
    lines.append("- WARNINGS: non-blocking. Unexpected leftovers (e.g. new bare idxs).")
    lines.append("  Allowlisted virtual idxs (90001 vent lock) are ignored by design.")
    if live:
        lines.append("- This run included live device_metadata (Admin API / running WanOS).")
        lines.append("  CLI without WanOS running skips the live-metadata section.")
    else:
        lines.append("- No live device_metadata in this run (typical for CLI offline).")
        lines.append("  Admin Debug check also validates RAM coverage while WanOS is up.")
    lines.append("")

    lines.append("STATS")
    lines.append("-" * 40)
    if not stats:
        lines.append("  (none)")
    else:
        for key in sorted(stats.keys()):
            help_txt = _STAT_HELP.get(key, "")
            suffix = f"  # {help_txt}" if help_txt else ""
            lines.append(f"  {key}: {stats[key]}{suffix}")
    lines.append("")

    if warnings:
        lines.append(f"WARNINGS ({len(warnings)}) - non-blocking")
        lines.append("-" * 40)
        lines.append("  'Python magic idx' = hardcoded device number in .py source.")
        lines.append("  Prefer entity_id + resolve; only allowlisted virtual idxs should remain.")
        lines.append("")
        for w in warnings:
            lines.append(f"  - {w}")
        lines.append("")

    if errors:
        lines.append(f"ERRORS ({len(errors)}) - BLOCKING")
        lines.append("-" * 40)
        lines.append("  Unknown/removed entity_ids, leftover numeric idxs in YAML,")
        lines.append("  registry collisions, or live metadata gaps. Fix before trusting automations.")
        lines.append("")
        for e in errors:
            lines.append(f"  - {e}")
        lines.append("")
        lines.append("RESULT: RED - do not cut over until fixed.")
    else:
        lines.append("RESULT: GREEN - entity_id cutover checks passed.")
        if warnings:
            lines.append(
                f"({len(warnings)} warning(s) are non-blocking; review before ship.)"
            )
        else:
            lines.append("(No warnings.)")

    return "\n".join(lines) + "\n"
