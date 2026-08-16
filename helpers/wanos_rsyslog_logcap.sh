#!/usr/bin/env bash
# --- file: helpers/wanos_rsyslog_logcap.sh ---
# WanOS Ops logcap (locked 2026-08-16): stop daemon.log; rsyslog truncates
# /var/log/syslog at 20 MiB (no archive). Idempotent. Run as root.
#
# Lives in helpers/ so wanos-sync mirrors it (helpers/bootstrap is excluded).
#   sudo bash /home/wannes/wanos/helpers/wanos_rsyslog_logcap.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run as root (sudo)." >&2
    exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRUNCATE_SRC="${HERE}/wanos-syslog-truncate.sh"
LOGROTATE_SRC="${HERE}/logrotate.rsyslog"
TRUNCATE_DST="/usr/local/sbin/wanos-syslog-truncate"
RSYSLOG_CONF="/etc/rsyslog.conf"
LOGROTATE_DST="/etc/logrotate.d/rsyslog"
BACKUP_CONF="${RSYSLOG_CONF}.bak.wanos-logcap"
BACKUP_ROTATE="${LOGROTATE_DST}.bak.wanos-logcap"
TMP_CONF="$(mktemp /tmp/rsyslog.conf.wanos-logcap.XXXXXX)"
# 20 MiB — rsyslog $outchannel size is bytes (not logrotate "20M").
SYSLOG_CAP_BYTES="20971520"

cleanup() {
    rm -f "${TMP_CONF}"
}
trap cleanup EXIT

if [ ! -f "${TRUNCATE_SRC}" ]; then
    echo "ERROR: missing ${TRUNCATE_SRC}" >&2
    exit 1
fi
if [ ! -f "${LOGROTATE_SRC}" ]; then
    echo "ERROR: missing ${LOGROTATE_SRC}" >&2
    exit 1
fi
if [ ! -f "${RSYSLOG_CONF}" ]; then
    echo "ERROR: missing ${RSYSLOG_CONF}" >&2
    exit 1
fi
if ! command -v rsyslogd >/dev/null 2>&1; then
    echo "ERROR: rsyslogd not found." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required to patch rsyslog.conf." >&2
    exit 1
fi

echo "[WanOS logcap] Installing ${TRUNCATE_DST}"
install -m 0755 "${TRUNCATE_SRC}" "${TRUNCATE_DST}"

if [ ! -f "${BACKUP_CONF}" ]; then
    cp -a "${RSYSLOG_CONF}" "${BACKUP_CONF}"
    echo "[WanOS logcap] Backed up ${RSYSLOG_CONF} -> ${BACKUP_CONF}"
fi

echo "[WanOS logcap] Patching ${RSYSLOG_CONF} (stdout -> temp, then validate)"
python3 - "${RSYSLOG_CONF}" "${TMP_CONF}" "${SYSLOG_CAP_BYTES}" "${TRUNCATE_DST}" <<'PY'
# --- file: helpers/wanos_rsyslog_logcap.sh (embedded) ---
"""Idempotent rsyslog.conf patch: outchannel cap + disable daemon.log."""
from __future__ import annotations

import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
cap_bytes = sys.argv[3]
truncate_dst = sys.argv[4]
text = src.read_text(encoding="utf-8")

outchannel_line = (
    f"$outchannel wanos_syslog_cap,/var/log/syslog,{cap_bytes},{truncate_dst}"
)
outchannel_block = (
    "# --- WanOS logcap: rsyslog truncates /var/log/syslog at 20 MiB (no archive) ---\n"
    f"{outchannel_line}\n"
)

if outchannel_line not in text:
    marker = "#### RULES ####"
    if marker in text:
        text = text.replace(marker, outchannel_block + "\n" + marker, 1)
    else:
        match = re.search(r"^auth,authpriv\.\*", text, flags=re.M)
        if match is None:
            print("ERROR: cannot find insert point (RULES or auth,authpriv.*) in rsyslog.conf", file=sys.stderr)
            sys.exit(1)
        text = text[: match.start()] + outchannel_block + "\n" + text[match.start() :]

syslog_pat = re.compile(
    r"^(\*\.\*;auth,authpriv\.none\s+)-?/var/log/syslog\s*$",
    flags=re.M,
)
text, syslog_n = syslog_pat.subn(r"\1:omfile:$wanos_syslog_cap", text, count=1)
if syslog_n == 0 and ":omfile:$wanos_syslog_cap" not in text:
    print("ERROR: syslog action line (*.*;auth,authpriv.none … /var/log/syslog) not found", file=sys.stderr)
    sys.exit(1)

daemon_pat = re.compile(
    r"^(daemon\.\*\s+-?/var/log/daemon\.log)\s*$",
    flags=re.M,
)
text, daemon_n = daemon_pat.subn(
    r"# WanOS logcap: daemon.log disabled (duplicate of syslog)\n# \1",
    text,
    count=1,
)
if daemon_n == 0:
    commented = re.search(
        r"^#\s*daemon\.\*\s+-?/var/log/daemon\.log\s*$",
        text,
        flags=re.M,
    )
    if commented is None:
        print("ERROR: daemon.log rule not found (active or already commented)", file=sys.stderr)
        sys.exit(1)

dst.write_text(text, encoding="utf-8")
PY

if ! rsyslogd -N1 -f "${TMP_CONF}"; then
    echo "ERROR: rsyslogd -N1 rejected patched config. ${RSYSLOG_CONF} unchanged." >&2
    exit 1
fi
cp -a "${TMP_CONF}" "${RSYSLOG_CONF}"
echo "[WanOS logcap] Installed patched ${RSYSLOG_CONF}"

if [ -f "${LOGROTATE_DST}" ] && [ ! -f "${BACKUP_ROTATE}" ]; then
    cp -a "${LOGROTATE_DST}" "${BACKUP_ROTATE}"
    echo "[WanOS logcap] Backed up ${LOGROTATE_DST} -> ${BACKUP_ROTATE}"
fi
install -m 0644 "${LOGROTATE_SRC}" "${LOGROTATE_DST}"
echo "[WanOS logcap] Installed ${LOGROTATE_DST} (no syslog / daemon.log archives)"

if systemctl cat rsyslog.service >/dev/null 2>&1; then
    systemctl restart rsyslog.service
    echo "[WanOS logcap] Restarted rsyslog.service"
else
    echo "WARN: rsyslog.service not found — patched files are in place; start rsyslog yourself." >&2
fi

echo "[WanOS logcap] Done."
echo "  Check: grep -E 'wanos_syslog_cap|daemon.log' ${RSYSLOG_CONF}"
echo "  Check: grep -E '^/var/log/(syslog|daemon\\.log)' ${LOGROTATE_DST} || true"
echo "  Smoke: df -h /var/log ; ls -l /var/log/syslog /var/log/wanos/wanos.log"
echo "  Leftover /var/log/daemon.log is not deleted (recovery was a one-shot)."
