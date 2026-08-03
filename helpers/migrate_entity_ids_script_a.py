# --- file: helpers/migrate_entity_ids_script_a.py ---
"""
ONE-OFF Script A — rewrite config device refs idx → entity_id using entity_registry.yaml.

Migrates:
  - automations:  idx: N  →  entity_id: …
  - deviceexplorer_exclude list items
  - hardware_links.power_meters (both sides)
  - blinds.travel_times keys
  - lighting.managed_lights + auto_off_delays
  - history.tracked_idxs → tracked_entities (list items)
  - config_zwave.yaml hidden_nodes

Does NOT touch hardware maps (device_map, gpio idxs, boot_seed, weather.idx, …).

Delete this file after a successful cutover (see docs/todo/260803_migration.md).

Usage (from WanOS root):
  py -3 helpers/migrate_entity_ids_script_a.py           # dry-run
  py -3 helpers/migrate_entity_ids_script_a.py --apply   # write (+ backups)
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = ROOT / "entity_registry.yaml"
DEFAULT_CONFIG = ROOT / "config.yaml"
DEFAULT_ZWAVE = ROOT / "config_zwave.yaml"

IDX_LINE_RE = re.compile(r"^(\s*(?:-\s*)?)idx:\s*(\d+)(.*)$")
TOP_LEVEL_RE = re.compile(r"^[A-Za-z0-9_]")
KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_]+):\s*(.*)$")
LIST_ITEM_NUM_RE = re.compile(r"^(\s*-\s+)(\d+)(.*)$")
DICT_NUM_KEY_RE = re.compile(r"^(\s+)(\d+):\s*(.*)$")
FLOW_LIST_RE = re.compile(r"^(\[)(.*)(\])\s*(#.*)?$")

# Parent keys whose numeric list items become entity_ids
MIGRATE_LIST_KEYS = {
    "deviceexplorer_exclude",
    "tracked_idxs",
    "tracked_entities",
    "hidden_nodes",
    "managed_lights",
}
# Parent keys: numeric dict key → entity_id; value stays as-is (seconds / minutes)
MIGRATE_DICT_KEY_ONLY = {"travel_times", "auto_off_delays"}
# Parent keys: both numeric key and numeric value → entity_ids
MIGRATE_DICT_BOTH = {"power_meters"}


def load_idx_to_entity(registry_path: Path) -> Dict[int, str]:
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("entities", raw) if isinstance(raw, dict) else {}
    out: Dict[int, str] = {}
    for key, val in (entries or {}).items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(val, str):
            out[idx] = val
        elif isinstance(val, dict) and val.get("entity_id"):
            if str(val.get("status") or "active") == "removed":
                continue
            out[idx] = str(val["entity_id"])
    return out


def _eol(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _replace_flow_ints(inner: str, idx_to_eid: Dict[int, str], changes: List[str], missing: List[str],
                       ctx: str) -> str:
    """Replace bare integers inside a flow list `[a, b, c]`."""
    parts: List[str] = []
    for token in inner.split(","):
        raw = token.strip()
        if not raw:
            continue
        if re.fullmatch(r"\d+", raw):
            idx = int(raw)
            if idx not in idx_to_eid:
                missing.append(f"{ctx}: idx {idx} has no entity_id in registry")
                parts.append(raw)
            else:
                eid = idx_to_eid[idx]
                changes.append(f"{ctx}: {idx} -> {eid}")
                parts.append(eid)
        else:
            parts.append(raw)
    return ", ".join(parts)


def migrate_structured_text(
    text: str,
    idx_to_eid: Dict[int, str],
    *,
    migrate_automations: bool = True,
) -> Tuple[str, List[str], List[str]]:
    """
    Section-aware rewrite of list/dict device refs + optional automations idx lines.
    """
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    changes: List[str] = []
    missing: List[str] = []

    stack: List[Tuple[int, str]] = []
    in_automations = False

    def parent_key() -> Optional[str]:
        return stack[-1][1] if stack else None

    for line in lines:
        stripped = line.lstrip("\r\n")
        body = stripped.rstrip("\r\n")
        eol = _eol(line)

        # --- automations block (idx: N → entity_id) ---
        if migrate_automations and re.match(r"^automations:\s*(#.*)?$", body):
            in_automations = True
            stack = [(0, "automations")]
            out.append(line)
            continue

        if in_automations and TOP_LEVEL_RE.match(body) and not body.startswith("automations:"):
            in_automations = False

        if in_automations and migrate_automations:
            m = IDX_LINE_RE.match(body)
            if m:
                indent, idx_s, rest = m.group(1), m.group(2), m.group(3)
                idx = int(idx_s)
                if idx not in idx_to_eid:
                    missing.append(f"automations: idx {idx} has no entity_id in registry")
                    out.append(line)
                    continue
                eid = idx_to_eid[idx]
                changes.append(f"automations: {idx} -> {eid}")
                out.append(f"{indent}entity_id: {eid}{rest}{eol}")
                continue
            out.append(line)
            continue

        # Numeric dict entries under migrate parents (must run before KEY_RE —
        # otherwise `72001: 74001` is mistaken for a named key).
        dict_m = DICT_NUM_KEY_RE.match(body)
        pk = parent_key()
        if dict_m and pk in (MIGRATE_DICT_KEY_ONLY | MIGRATE_DICT_BOTH):
            prefix, idx_s, rest = dict_m.group(1), dict_m.group(2), dict_m.group(3)
            idx = int(idx_s)
            if idx not in idx_to_eid:
                missing.append(f"{pk}: key idx {idx} has no entity_id in registry")
                out.append(line)
                continue
            eid = idx_to_eid[idx]
            new_rest = rest.strip()
            if pk in MIGRATE_DICT_BOTH:
                vm = re.match(r"^(\d+)(.*)$", new_rest)
                if vm:
                    v_idx = int(vm.group(1))
                    v_tail = vm.group(2)  # includes comment spacing
                    if v_idx not in idx_to_eid:
                        missing.append(f"{pk}: value idx {v_idx} has no entity_id in registry")
                        out.append(line)
                        continue
                    v_eid = idx_to_eid[v_idx]
                    changes.append(f"{pk}: {idx}:{v_idx} -> {eid}:{v_eid}")
                    new_rest = f"{v_eid}{v_tail}"
                else:
                    changes.append(f"{pk}: key {idx} -> {eid}")
            else:
                changes.append(f"{pk}: {idx} -> {eid}")
            out.append(f"{prefix}{eid}: {new_rest}{eol}")
            continue

        # --- key stack for structured sections ---
        key_m = KEY_RE.match(body)
        if key_m and not body.lstrip().startswith("-") and not re.match(r"^\s*\d+:", body):
            indent_s, key, rest = key_m.group(1), key_m.group(2), key_m.group(3)
            indent = len(indent_s)
            while stack and stack[-1][0] >= indent:
                stack.pop()

            write_key = key
            if key == "tracked_idxs":
                write_key = "tracked_entities"
                changes.append("history: tracked_idxs -> tracked_entities")

            stack.append((indent, write_key))

            # Flow list on same line: managed_lights: [...], hidden_nodes: [...]
            if write_key in MIGRATE_LIST_KEYS:
                flow = FLOW_LIST_RE.match(rest.strip())
                if flow:
                    inner = flow.group(2)
                    comment = flow.group(4) or ""
                    new_inner = _replace_flow_ints(inner, idx_to_eid, changes, missing, write_key)
                    cmt = f" {comment}" if comment else ""
                    out.append(f"{indent_s}{write_key}: [{new_inner}]{cmt}{eol}")
                    continue

            if write_key != key:
                if rest:
                    out.append(f"{indent_s}{write_key}: {rest}{eol}")
                else:
                    out.append(f"{indent_s}{write_key}:{eol}")
                continue

            out.append(line)
            continue

        # List items under migrate list parents
        list_m = LIST_ITEM_NUM_RE.match(body)
        if list_m and parent_key() in MIGRATE_LIST_KEYS:
            prefix, idx_s, rest = list_m.group(1), list_m.group(2), list_m.group(3)
            idx = int(idx_s)
            ctx = parent_key() or "?"
            if idx not in idx_to_eid:
                missing.append(f"{ctx}: idx {idx} has no entity_id in registry")
                out.append(line)
                continue
            eid = idx_to_eid[idx]
            changes.append(f"{ctx}: {idx} -> {eid}")
            out.append(f"{prefix}{eid}{rest}{eol}")
            continue

        out.append(line)

    return "".join(out), changes, missing


def migrate_automations_text(text: str, idx_to_eid: Dict[int, str]) -> Tuple[str, List[str], List[str]]:
    """Back-compat wrapper — full structured migrate including automations."""
    return migrate_structured_text(text, idx_to_eid, migrate_automations=True)


def _process_file(
    path: Path,
    idx_to_eid: Dict[int, str],
    *,
    apply: bool,
    migrate_automations: bool,
) -> int:
    original = path.read_text(encoding="utf-8")
    updated, changes, missing = migrate_structured_text(
        original, idx_to_eid, migrate_automations=migrate_automations
    )

    print(f"\n=== {path.name} ===")
    print(f"Planned replacements: {len(changes)}")
    for c in changes[:50]:
        print(f"  {c}")
    if len(changes) > 50:
        print(f"  … +{len(changes) - 50} more")

    if missing:
        print(f"MISSING ({len(missing)}):", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 2

    if updated == original:
        print("No changes needed.")
        return 0

    if not apply:
        print("Dry-run only. Re-run with --apply to write.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".pre_entity_migrate_{stamp}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"Backup: {backup}")
    print(f"Wrote:  {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Script A: migrate config idxs to entity_id")
    parser.add_argument("--apply", action="store_true", help="Write files (creates .bak first)")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--zwave", type=Path, default=DEFAULT_ZWAVE)
    parser.add_argument("--skip-zwave", action="store_true")
    args = parser.parse_args()

    if not args.registry.exists():
        print(f"ERROR: registry not found: {args.registry}", file=sys.stderr)
        return 1
    if not args.config.exists():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 1

    idx_to_eid = load_idx_to_entity(args.registry)
    print(f"Registry: {args.registry} ({len(idx_to_eid)} active entity_ids)")

    rc = _process_file(args.config, idx_to_eid, apply=args.apply, migrate_automations=True)
    if rc != 0:
        return rc

    if not args.skip_zwave and args.zwave.exists():
        rc = _process_file(args.zwave, idx_to_eid, apply=args.apply, migrate_automations=False)
        if rc != 0:
            return rc
    elif not args.skip_zwave:
        print(f"NOTE: zwave config not found ({args.zwave}) — skipped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
