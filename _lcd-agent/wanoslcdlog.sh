#!/usr/bin/env bash
# --- file: _lcd-agent/wanoslcdlog.sh ---
# Log tailer for the LCD Pi agent (subset of main-Pi wanoslog.sh).
#
# LCD agent only writes:
#   1 = console  (systemd journal for wanos-lcd-agent)
#   2 = app      (/var/log/wanos/wanos.log)
# No app-debug / automation / power / iwhw on this Pi.
#
# Usage:
#   ./wanoslcdlog.sh consolelog
#   ./wanoslcdlog.sh applog
#   ./wanoslcdlog.sh log
#   ./wanoslcdlog.sh log 1
#   ./wanoslcdlog.sh log 2 100
set -euo pipefail

APP_LOG_FILE="/var/log/wanos/wanos.log"
SERVICE_UNIT="wanos-lcd-agent.service"
TAIL_LINES=20

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

usage() {
  cat <<EOF
Usage: $0 <command> [args]

Commands:
  consolelog      (Tails live Systemd Journal for ${SERVICE_UNIT})
  applog          (Tails ${APP_LOG_FILE})
  log [choice] [lines]

log choices (LCD Pi — only these exist):
  1 = console     (Systemd Journalctl)
  2 = app         (${APP_LOG_FILE})

Examples:
  $0 consolelog
  $0 log              # interactive prompt
  $0 log 2            # tail app log
  $0 log 1 100        # console, last 100 lines then follow
EOF
  exit 2
}

ensure_readable_file_or_exit() {
  local file="$1"
  if [ ! -f "$file" ]; then
    log "Log file not found: $file"
    exit 1
  fi
  if [ ! -r "$file" ]; then
    log "Log file not readable by current user: $file"
    exit 1
  fi
}

if [ $# -lt 1 ]; then
  usage
fi

CMD="$1"
shift || true
REMAINING_ARGS=("$@")

for arg in "${REMAINING_ARGS[@]}"; do
  case "$arg" in
    -h|--help) usage ;;
  esac
done

if [ "$CMD" = "consolelog" ]; then
  log "Tailing systemd journal for ${SERVICE_UNIT}. Showing last ${TAIL_LINES} lines then following."
  exec sudo journalctl -u "${SERVICE_UNIT}" -n "${TAIL_LINES}" -f
fi

if [ "$CMD" = "applog" ]; then
  ensure_readable_file_or_exit "${APP_LOG_FILE}"
  log "Tailing app log (${APP_LOG_FILE}). Showing last ${TAIL_LINES} lines then following."
  exec tail -n "${TAIL_LINES}" -F "${APP_LOG_FILE}"
fi

if [ "$CMD" = "log" ]; then
  choice=""
  lines="${TAIL_LINES}"

  if [ ${#REMAINING_ARGS[@]} -ge 1 ] && [[ "${REMAINING_ARGS[0]}" =~ ^[12]$ ]]; then
    choice="${REMAINING_ARGS[0]}"
    if [ ${#REMAINING_ARGS[@]} -ge 2 ] && [[ "${REMAINING_ARGS[1]}" =~ ^[0-9]+$ ]]; then
      lines="${REMAINING_ARGS[1]}"
    fi
  else
    cat <<EOF
Which log do you want to tail? (LCD Pi — only 1 and 2)
  1) console    (Systemd Journal — ${SERVICE_UNIT})
  2) app        (${APP_LOG_FILE})
Enter choice [1-2]:
EOF
    read -r choice
    echo "Number of lines to show initially (press Enter for default ${TAIL_LINES}):"
    read -r input_lines
    if [ -n "${input_lines}" ]; then
      if [[ "${input_lines}" =~ ^[0-9]+$ ]]; then
        lines="${input_lines}"
      else
        log "Invalid lines value: ${input_lines}"
        usage
      fi
    fi
  fi

  case "${choice}" in
    1)
      log "Tailing systemd journal for ${SERVICE_UNIT}. Showing last ${lines} lines then following."
      exec sudo journalctl -u "${SERVICE_UNIT}" -n "${lines}" -f
      ;;
    2)
      ensure_readable_file_or_exit "${APP_LOG_FILE}"
      log "Tailing app log (${APP_LOG_FILE}). Showing last ${lines} lines then following."
      exec tail -n "${lines}" -F "${APP_LOG_FILE}"
      ;;
    *)
      log "Invalid choice: ${choice} (LCD Pi supports 1 or 2 only)"
      usage
      ;;
  esac
fi

log "ERROR: Unknown command: ${CMD:-<none>}"
usage
