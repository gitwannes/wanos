#!/usr/bin/env python3
# --- file: helpers/ops8-php2shell/ops8_status.py ---
"""Ops8 PHP2Shell bridge status (inventory + markers). ASCII console output."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

MARKER_PATH = "/var/lib/wanos-ops8/bridge"
FPM_INI = "/etc/php/7.4/fpm/conf.d/99-ops8-php2shell.ini"
CVE_A = "CVE-2026-109618"
CVE_B = "CVE-2026-109619"
WANTED_SUFFIX = "wanosops8"


def _run(cmd: List[str]) -> Tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return 127, ""
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def php_cli_version() -> str:
    code, out = _run(["php", "-v"])
    if code != 0:
        return "unavailable"
    return _first_line(out)


def php_fpm_version() -> str:
    code, out = _run(["php-fpm7.4", "-v"])
    if code != 0:
        return "unavailable"
    return _first_line(out)


def dpkg_php74() -> List[Dict[str, str]]:
    code, out = _run(
        ["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Architecture}\\n", "php7.4*"]
    )
    rows: List[Dict[str, str]] = []
    if code != 0 or not out:
        return rows
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append(
                {
                    "package": parts[0],
                    "version": parts[1],
                    "arch": parts[2] if len(parts) > 2 else "",
                }
            )
    return rows


def fpm_active() -> str:
    code, out = _run(["systemctl", "is-active", "php7.4-fpm"])
    if code == 0:
        return out or "active"
    return out or "inactive"


def read_marker() -> Dict[str, str]:
    if not os.path.isfile(MARKER_PATH):
        return {}
    data: Dict[str, str] = {}
    with open(MARKER_PATH, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            data[key.strip()] = val.strip()
    return data


def mitigation_on() -> bool:
    if not os.path.isfile(FPM_INI):
        return False
    with open(FPM_INI, "r", encoding="utf-8", errors="replace") as fh:
        body = fh.read()
    # Accept Off / 0 / off
    return bool(
        re.search(
            r"(?im)^\s*session\.upload_progress\.enabled\s*=\s*(Off|0)\s*$",
            body,
        )
    )


def apt_holds() -> List[str]:
    code, out = _run(["apt-mark", "showhold"])
    if code != 0 or not out:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith("php7.4")]


def changelog_mentions_cves() -> Optional[bool]:
    """Best-effort: apt changelog for php7.4-fpm mentions both CVEs."""
    code, out = _run(["apt-get", "changelog", "php7.4-fpm"])
    if code != 0 or not out:
        return None
    return (CVE_A in out) and (CVE_B in out)


def build_report() -> Dict[str, Any]:
    pkgs = dpkg_php74()
    fpm_ver = ""
    for row in pkgs:
        if row["package"] == "php7.4-fpm":
            fpm_ver = row["version"]
            break
    bridged_pkg = WANTED_SUFFIX in fpm_ver
    marker = read_marker()
    report: Dict[str, Any] = {
        "php_cli": php_cli_version(),
        "php_fpm": php_fpm_version(),
        "php7.4-fpm_version": fpm_ver or "unknown",
        "bridged_package": bridged_pkg,
        "fpm_service": fpm_active(),
        "mitigation_file": FPM_INI,
        "mitigation_on": mitigation_on(),
        "marker_path": MARKER_PATH,
        "marker": marker,
        "holds": apt_holds(),
        "packages": pkgs,
        "cves": [CVE_A, CVE_B],
        "changelog_mentions_both_cves": changelog_mentions_cves(),
        "verdict": "",
    }
    if bridged_pkg and report["mitigation_on"]:
        report["verdict"] = "OK_bridged_and_mitigated"
    elif bridged_pkg:
        report["verdict"] = "BRIDGED_mitigation_missing"
    elif report["mitigation_on"]:
        report["verdict"] = "MITIGATED_only_rebuild_pending"
    else:
        report["verdict"] = "VULNERABLE_unpatched_deb11u12_or_unknown"
    return report


def main() -> int:
    as_json = "--json" in sys.argv
    report = build_report()
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    print("=== Ops8 status (python) ===")
    print("CLI:           {}".format(report["php_cli"]))
    print("FPM binary:    {}".format(report["php_fpm"]))
    print("php7.4-fpm:    {}".format(report["php7.4-fpm_version"]))
    print("FPM service:   {}".format(report["fpm_service"]))
    print("bridged pkg:   {}".format(report["bridged_package"]))
    print("mitigation:    {}".format("on" if report["mitigation_on"] else "off"))
    print("marker:        {}".format(report["marker"] or "(absent)"))
    holds = report["holds"]
    print("apt holds:     {}".format(", ".join(holds) if holds else "(none)"))
    cve_chg = report["changelog_mentions_both_cves"]
    if cve_chg is None:
        print("changelog CVE: (unavailable)")
    else:
        print("changelog CVE: {}".format("both mentioned" if cve_chg else "not both"))
    print("verdict:       {}".format(report["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
