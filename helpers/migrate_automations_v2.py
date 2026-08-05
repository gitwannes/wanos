#!/usr/bin/env python3
"""
Phase 6A: migrate automations.auto.yaml → unified schema v2 (trigger + cases).

Usage (from repo root):
  python3 helpers/migrate_automations_v2.py --dry-run
  python3 helpers/migrate_automations_v2.py --write

Always review dry-run. --write copies backup automations.auto.yaml.bak.<UTC> first.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.automations_schema_v2 import migrate_rules_to_v2  # noqa: E402
from core.automations_store import (  # noqa: E402
    _automations_path,
    load_automations_roundtrip,
    replace_all_automations,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate automations to schema v2")
    parser.add_argument("--dry-run", action="store_true", help="Print plan; do not write")
    parser.add_argument("--write", action="store_true", help="Backup + write migrated file")
    parser.add_argument("--no-cinema-merge", action="store_true", help="Skip Cinema OFF pair merge")
    args = parser.parse_args()

    if args.dry_run == args.write:
        print("Specify exactly one of --dry-run or --write", file=sys.stderr)
        return 2

    path = _automations_path()
    if not path.exists():
        print(f"Missing {path}", file=sys.stderr)
        return 1

    root, _ = load_automations_roundtrip()
    rules = list(root.get("automations") or [])
    print(f"Loaded {len(rules)} rules from {path}")

    migrated, logs = migrate_rules_to_v2(rules, merge_cinema=not args.no_cinema_merge)
    for line in logs:
        print(f"  - {line}")
    print(f"Result: {len(migrated)} rules (was {len(rules)})")

    if args.dry_run:
        print("Dry-run only - no file written.")
        return 0

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_name(f"{path.name}.bak.{utc}")
    bak.write_bytes(path.read_bytes())
    print(f"Backup: {bak}")

    replace_all_automations(migrated)
    print(f"Wrote v2 automations -> {path}")
    print("Next: restart WanOS or trigger CONFIG_RELOAD; Admin Debug -> GREEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
