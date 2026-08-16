#!/usr/bin/env bash
# --- file: wanoslog.sh ---
# Universal log-tailing multiplexer for the WanOS Systemd service.
#
# Usage:
#   ./wanoslog.sh consolelog      -> Tails live Systemd Journal (stdout/stderr)
#   ./wanoslog.sh applog          -> Tails high-level business logic
#   ./wanoslog.sh applogdebug     -> Tails low-level debug chatter
#   ./wanoslog.sh automationlog   -> Tails automation log (DEBUG omitted)
#   ./wanoslog.sh automationlog debug -> Tails automation log (all levels)
#   ./wanoslog.sh powerlog        -> Tails power analytics data
#   ./wanoslog.sh iwhwlog         -> Tails IWHW subsystem log
#   ./wanoslog.sh log             -> Interactive menu
#   ./wanoslog.sh log 4           -> Automation log, DEBUG omitted
#   ./wanoslog.sh log 4 debug     -> Automation log, all levels
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
APP_LOG_FILE="/var/log/wanos/wanos.log"
APP_DEBUG_LOG_FILE="/var/log/wanos/wanos_debug.log"
AUTOM_LOG_FILE="/var/log/wanos/wanos_automations.log"
POWER_LOG_FILE="/var/log/wanos/wanos_power.log"
IWHW_LOG_FILE="/var/log/wanos/wanos_iwhw.log"
TAIL_LINES=20

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

usage() {
  cat <<EOF
Usage: $0 <command> [args]

Commands:
  consolelog      (Tails live Systemd Journal)
  applog          (Tails /var/log/wanos/wanos.log)
  applogdebug     (Tails /var/log/wanos/wanos_debug.log)
  automationlog [debug]
                  (Tails /var/log/wanos/wanos_automations.log;
                   omit DEBUG unless "debug" is passed)
  powerlog        (Tails /var/log/wanos/wanos_power.log)
  iwhwlog         (Tails /var/log/wanos/wanos_iwhw.log)
  log [choice] [lines|debug]...

log choices:
  1 = console     (Systemd Journalctl)
  2 = app         (/var/log/wanos/wanos.log)
  3 = app-debug   (/var/log/wanos/wanos_debug.log)
  4 = automation  (/var/log/wanos/wanos_automations.log; DEBUG omitted
                   unless "debug" is also passed)
  5 = power       (/var/log/wanos/wanos_power.log)
  6 = iwhw        (/var/log/wanos/wanos_iwhw.log)

Examples:
  $0 consolelog
  $0 log              # interactive prompt
  $0 log 2            # tail app log
  $0 log 1 100        # tail console log with 100 lines
  $0 log 4            # automation, no DEBUG
  $0 log 4 debug      # automation, all levels (incl. DEBUG / X-RAY)
  $0 log 4 100 debug  # same, last 100 lines then follow
  $0 automationlog debug
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

# Tail automation log. $1 = line count; $2 = 1 to include DEBUG, else omit.
tail_automation() {
  local lines="$1"
  local with_debug="${2:-0}"
  ensure_readable_file_or_exit "$AUTOM_LOG_FILE"
  if [ "$with_debug" = "1" ]; then
    log "Tailing automation log ($AUTOM_LOG_FILE). Showing last $lines lines then following (all levels)."
    exec tail -n "$lines" -F "$AUTOM_LOG_FILE"
  fi
  log "Tailing automation log ($AUTOM_LOG_FILE). Showing last $lines lines then following (DEBUG omitted)."
  tail -n "$lines" -F "$AUTOM_LOG_FILE" | grep --line-buffered -v DEBUG
  exit $?
}

# True if arg is the optional "debug" token (any case).
is_debug_token() {
  local a
  a="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  [ "$a" = "debug" ]
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
  with_debug=0
  if [ ${#REMAINING_ARGS[@]} -ge 1 ] && is_debug_token "${REMAINING_ARGS[0]}"; then
    with_debug=1
  fi
  tail_automation "$TAIL_LINES" "$with_debug"
fi

# -------------------------
# Power log tailing
# -------------------------
if [ "$CMD" = "powerlog" ]; then
  ensure_readable_file_or_exit "$POWER_LOG_FILE"
  log "Tailing power log ($POWER_LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$POWER_LOG_FILE"
fi

# -------------------------
# IWHW log tailing
# -------------------------
if [ "$CMD" = "iwhwlog" ]; then
  ensure_readable_file_or_exit "$IWHW_LOG_FILE"
  log "Tailing IWHW log ($IWHW_LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$IWHW_LOG_FILE"
fi

# -------------------------
# Log chooser (interactive or non-interactive)
# -------------------------
if [ "$CMD" = "log" ]; then
  choice=""
  lines="$TAIL_LINES"
  with_debug=0

  # Non-interactive: log <1-6> [lines] [debug] (order of lines/debug flexible)
  if [ ${#REMAINING_ARGS[@]} -ge 1 ] && [[ "${REMAINING_ARGS[0]}" =~ ^[1-6]$ ]]; then
    choice="${REMAINING_ARGS[0]}"
    idx=1
    while [ "$idx" -lt ${#REMAINING_ARGS[@]} ]; do
      arg="${REMAINING_ARGS[$idx]}"
      if [[ "$arg" =~ ^[0-9]+$ ]]; then
        lines="$arg"
      elif is_debug_token "$arg"; then
        with_debug=1
      else
        log "Unknown log option: $arg"
        usage
      fi
      idx=$((idx + 1))
    done
  else
    cat <<EOF
Which log do you want to tail?
  1) console    (Systemd Journal)
  2) app        (/var/log/wanos/wanos.log)
  3) app-debug  (/var/log/wanos/wanos_debug.log)
  4) automation (/var/log/wanos/wanos_automations.log; DEBUG omitted by default)
  5) power      (/var/log/wanos/wanos_power.log)
  6) iwhw       (/var/log/wanos/wanos_iwhw.log)
Enter choice [1-6]:
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
    if [ "$choice" = "4" ]; then
      echo "Include DEBUG / X-RAY lines? [y/N]:"
      read -r dbg_ans
      dbg_lc="$(printf '%s' "$dbg_ans" | tr '[:upper:]' '[:lower:]')"
      if [ "$dbg_lc" = "y" ] || [ "$dbg_lc" = "yes" ] || [ "$dbg_lc" = "debug" ]; then
        with_debug=1
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
      tail_automation "$lines" "$with_debug"
      ;;
    5)
      ensure_readable_file_or_exit "$POWER_LOG_FILE"
      log "Tailing power log ($POWER_LOG_FILE). Showing last $lines lines then following."
      exec tail -n "$lines" -F "$POWER_LOG_FILE"
      ;;
    6)
      ensure_readable_file_or_exit "$IWHW_LOG_FILE"
      log "Tailing IWHW log ($IWHW_LOG_FILE). Showing last $lines lines then following."
      exec tail -n "$lines" -F "$IWHW_LOG_FILE"
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
