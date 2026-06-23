# --------------------------------------------------------------------------------
# CODE TO REPLACE IT WITH
# --------------------------------------------------------------------------------
#!/usr/bin/env bash
# wanoslog.sh
# Universal log-tailing multiplexer for the WanOS Systemd service.
#
# Usage: 
#   ./wanoslog.sh consolelog      -> Tails live Systemd Journal (stdout/stderr)
#   ./wanoslog.sh applog          -> Tails high-level business logic
#   ./wanoslog.sh applogdebug     -> Tails low-level debug chatter
#   ./wanoslog.sh automationlog   -> Tails declarative automation actions
#   ./wanoslog.sh log             -> Interactive menu
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
APP_LOG_FILE="/var/log/wanos/wanos.log"
APP_DEBUG_LOG_FILE="/var/log/wanos/wanos_debug.log"
AUTOM_LOG_FILE="/var/log/wanos/wanos_automations.log"
TAIL_LINES=20     # default number of lines to show initially for tails

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

usage() {
  cat <<EOF
Usage: $0 <command> [args]

Commands:
  consolelog      (Tails live Systemd Journal)
  applog          (Tails /var/log/wanos/wanos.log)
  applogdebug     (Tails /var/log/wanos/wanos_debug.log)
  automationlog   (Tails /var/log/wanos/wanos_automations.log)
  log [choice] [lines]

log choices:
  1 = console     (Systemd Journalctl)
  2 = app         (/var/log/wanos/wanos.log)
  3 = app-debug   (/var/log/wanos/wanos_debug.log)
  4 = automation  (/var/log/wanos/wanos_automations.log)

Examples:
  $0 consolelog
  $0 log        # interactive prompt
  $0 log 2      # tail app log
  $0 log 1 100  # tail console log with 100 lines
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

# -------------------------
# Console log tailing (Systemd Journald)
# -------------------------
if [ "$CMD" = "consolelog" ]; then
  log "Tailing systemd journal for wanos.service. Showing last $TAIL_LINES lines then following."
  # sudo is used natively to ensure journal access permissions aren't an issue
  exec sudo journalctl -u wanos.service -n "$TAIL_LINES" -f
fi

# -------------------------
# App log tailing
# -------------------------
if [ "$CMD" = "applog" ]; then
  ensure_readable_file_or_exit "$APP_LOG_FILE"
  log "Tailing app log ($APP_LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$APP_LOG_FILE"
fi

# -------------------------
# App debug log tailing
# -------------------------
if [ "$CMD" = "applogdebug" ]; then
  ensure_readable_file_or_exit "$APP_DEBUG_LOG_FILE"
  log "Tailing app debug log ($APP_DEBUG_LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$APP_DEBUG_LOG_FILE"
fi

# -------------------------
# Automation log tailing
# -------------------------
if [ "$CMD" = "automationlog" ]; then
  ensure_readable_file_or_exit "$AUTOM_LOG_FILE"
  log "Tailing automation log ($AUTOM_LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$AUTOM_LOG_FILE"
fi

# -------------------------
# Log chooser (interactive or non-interactive)
# -------------------------
if [ "$CMD" = "log" ]; then
  choice=""
  lines="$TAIL_LINES"
  if [ ${#REMAINING_ARGS[@]} -ge 1 ] && [[ "${REMAINING_ARGS[0]}" =~ ^[1-4]$ ]]; then
    choice="${REMAINING_ARGS[0]}"
    if [ ${#REMAINING_ARGS[@]} -ge 2 ] && [[ "${REMAINING_ARGS[1]}" =~ ^[0-9]+$ ]]; then
      lines="${REMAINING_ARGS[1]}"
    fi
  else
    cat <<EOF
Which log do you want to tail?
  1) console    (Systemd Journal)
  2) app        (/var/log/wanos/wanos.log)
  3) app-debug  (/var/log/wanos/wanos_debug.log)
  4) automation (/var/log/wanos/wanos_automations.log)
Enter choice [1-4]:
EOF
    read -r choice
    echo "Number of lines to show initially (press Enter for default $TAIL_LINES):"
    read -r input_lines
    if [ -n "$input_lines" ]; then
      if [[ "$input_lines" =~ ^[0-9]+$ ]]; then
        lines="$input_lines"
      else
        log "Invalid lines value: $input_lines"
        usage
      fi
    fi
  fi

  case "$choice" in
    1)
      log "Tailing systemd journal for wanos.service. Showing last $lines lines then following."
      exec sudo journalctl -u wanos.service -n "$lines" -f
      ;;
    2)
      ensure_readable_file_or_exit "$APP_LOG_FILE"
      log "Tailing app log ($APP_LOG_FILE). Showing last $lines lines then following."
      exec tail -n "$lines" -F "$APP_LOG_FILE"
      ;;
    3)
      ensure_readable_file_or_exit "$APP_DEBUG_LOG_FILE"
      log "Tailing app debug log ($APP_DEBUG_LOG_FILE). Showing last $lines lines then following."
      exec tail -n "$lines" -F "$APP_DEBUG_LOG_FILE"
      ;;
    4)
      ensure_readable_file_or_exit "$AUTOM_LOG_FILE"
      log "Tailing automation log ($AUTOM_LOG_FILE). Showing last $lines lines then following."
      exec tail -n "$lines" -F "$AUTOM_LOG_FILE"
      ;;
    *)
      log "Invalid choice: $choice"
      usage
      ;;
  esac
fi

# -------------------------
# Unknown command handling
# -------------------------
log "ERROR: Unknown command: ${CMD:-<none>}"
usage