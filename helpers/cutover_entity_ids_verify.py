# --- file: helpers/cutover_entity_ids_verify.py ---
"""
ONE-OFF Cutover gate — verify entity_id migration before enabling entity_id-only engine.

Delete this file after a successful cutover (with Script A). See docs/todo/260803_migration.md.

Usage (from WanOS root):
  py -3 helpers/cutover_entity_ids_verify.py
  exit 0 = green, non-zero = do not cut over
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.entity_registry_check import (  # noqa: E402
    format_entity_cutover_report,
    run_entity_cutover_checks,
)


def main() -> int:
    report = run_entity_cutover_checks(root=ROOT)
    # Prefer shared text (also returned as report["report_text"] for Admin modal).
    print(report.get("report_text") or format_entity_cutover_report(report), end="")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
