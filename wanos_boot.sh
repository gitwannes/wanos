#!/usr/bin/env bash
# wanos_boot.sh
# before use: convert line endings to LF: sed -i 's/\r$//' wanos_boot.sh
# Manage a development uvicorn process for "uvicorn main:app --host 0.0.0.0 --port 8000"
# Commands:
#   start           Start uvicorn in background (writes PID to $PID_FILE, logs to $LOG_FILE)
#   status          Show whether uvicorn is running and which PID (if any)
#   stop [force]    Attempt graceful shutdown (SIGINT) of the PID in $PID_FILE; use 'force' to kill -9
#   log             Tail the console log: show last 20 lines then follow
#
# Use "sed -i 's/\r$//' wanos_boot.sh" to convert to Unix endings.
# Paths use $HOME so the script works for the current user.
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
VENV_DIR="$HOME/wisc_backend/wisc_backend_venv"
APP_CMD="uvicorn main:app --host 0.0.0.0 --port 8000"
LOG_FILE="$HOME/wisc_backend/wanos.console.log"
PID_FILE="$HOME/wisc_backend/wanos_uvicorn.pid"
GRACE_PERIOD=10   # seconds to wait for graceful shutdown
TAIL_LINES=20     # number of lines to show initially for 'log' command

# -------------------------
# Helpers
# -------------------------
log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

usage() {
  cat <<EOF
Usage: $0 <command> [args]

Commands:
  start           Start uvicorn in background (writes PID to $PID_FILE, logs to $LOG_FILE)
  status          Show whether uvicorn is running and which PID (if any)
  stop [force]    Attempt graceful shutdown (SIGINT) of the PID in $PID_FILE; 'force' forces kill -9
  log             Show last $TAIL_LINES lines of the console log and follow (tail -n $TAIL_LINES -f)

Examples:
  $0 start
  $0 status
  $0 stop
  $0 stop force
  $0 log
EOF
  exit 2
}

# Return PID from pidfile if present and process exists, otherwise empty
read_pidfile() {
  if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      printf '%s' "$pid"
      return 0
    fi
  fi
  printf ''
  return 1
}

# Activate virtualenv in the current shell
activate_venv() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
  else
    log "ERROR: virtualenv activate script not found at $VENV_DIR/bin/activate"
    exit 1
  fi
}

# -------------------------
# Parse command line
# -------------------------
if [ $# -lt 1 ]; then
  usage
fi

CMD="$1"
shift || true

DO_FORCE=false
# Accept 'force' only as an argument to stop (plain token, no dashes)
for arg in "$@"; do
  case "$arg" in
    force) DO_FORCE=true ;;
    -h|--help) usage ;;
    *) log "Unknown argument: $arg"; usage ;;
  esac
done

# -------------------------
# Status
# -------------------------
if [ "$CMD" = "status" ]; then
  pid=$(read_pidfile || true)
  if [ -n "$pid" ]; then
    log "uvicorn appears to be running (PID: $pid). Log: $LOG_FILE"
    ps -o pid,cmd -p "$pid" || true
    exit 0
  else
    pids=$(pgrep -f "uvicorn main:app" || true)
    if [ -n "$pids" ]; then
      log "uvicorn processes found (not matching pidfile): $pids"
      ps -o pid,cmd -p $pids || true
      exit 0
    fi
    log "No uvicorn process found."
    exit 1
  fi
fi

# -------------------------
# Stop (graceful) flow
# -------------------------
if [ "$CMD" = "stop" ]; then
  pid=$(read_pidfile || true)
  if [ -z "$pid" ]; then
    pids=$(pgrep -f "uvicorn main:app" || true)
    if [ -z "$pids" ]; then
      log "No uvicorn process found (no pidfile and no matching processes)."
      exit 0
    else
      log "No valid pidfile, but found uvicorn processes: $pids"
      pid="$pids"
    fi
  fi

  log "Attempting graceful shutdown of PID(s): $pid"
  # send SIGINT (same as Ctrl+C) for graceful shutdown
  kill -INT $pid 2>/dev/null || true

  # wait up to GRACE_PERIOD seconds for processes to exit
  for i in $(seq 1 $GRACE_PERIOD); do
    sleep 1
    still=$(for p in $pid; do kill -0 "$p" 2>/dev/null && printf '%s ' "$p"; done || true)
    if [ -z "$still" ]; then
      log "Shutdown successful: no uvicorn processes remain."
      [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
      exit 0
    fi
    log "Waiting for processes to exit... ($i/$GRACE_PERIOD)"
  done

  # graceful timed out
  still=$(for p in $pid; do kill -0 "$p" 2>/dev/null && printf '%s ' "$p"; done || true)
  if [ -z "$still" ]; then
    log "Shutdown completed in the final check."
    [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
    exit 0
  fi

  if [ "$DO_FORCE" = true ]; then
    log "Graceful shutdown timed out. Forcing kill -9 on: $still"
    kill -9 $still 2>/dev/null || true
    sleep 1
    remaining=$(for p in $still; do kill -0 "$p" 2>/dev/null && printf '%s ' "$p"; done || true)
    if [ -n "$remaining" ]; then
      log "Force kill failed: some processes still present: $remaining"
      exit 1
    else
      log "Force kill successful."
      [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
      exit 0
    fi
  else
    log "Graceful shutdown timed out. Re-run with: $0 stop force"
    exit 1
  fi
fi

# -------------------------
# Start flow
# -------------------------
if [ "$CMD" = "start" ]; then
  existing_pid=$(read_pidfile || true)
  if [ -n "$existing_pid" ]; then
    log "App already running (PID: $existing_pid). Doing nothing."
    exit 0
  fi

  pids=$(pgrep -f "uvicorn main:app" || true)
  if [ -n "$pids" ]; then
    log "Found uvicorn process(es) (no pidfile): $pids. Doing nothing."
    exit 0
  fi

  log "Starting uvicorn in background. Log -> $LOG_FILE"
  activate_venv

  mkdir -p "$(dirname "$LOG_FILE")"
  touch "$LOG_FILE"
  chmod 644 "$LOG_FILE"

  nohup $APP_CMD >> "$LOG_FILE" 2>&1 &
  uvicorn_pid=$!

  sleep 0.5

  if kill -0 "$uvicorn_pid" 2>/dev/null; then
    echo "$uvicorn_pid" > "$PID_FILE"
    log "Started uvicorn (PID: $uvicorn_pid). PID written to $PID_FILE"
    log "Tail the log with: $0 log (logfile in $LOG_FILE)"
    exit 0
  else
    found=$(pgrep -f "uvicorn main:app" || true)
    if [ -n "$found" ]; then
      echo "$found" > "$PID_FILE"
      log "Started uvicorn (detected PID(s): $found). PID written to $PID_FILE"
      exit 0
    fi
    log "Failed to start uvicorn. Check $LOG_FILE for errors."
    exit 1
  fi
fi

# -------------------------
# Log tailing
# -------------------------
if [ "$CMD" = "log" ]; then
  if [ ! -f "$LOG_FILE" ]; then
    log "Log file not found: $LOG_FILE"
    exit 1
  fi
  # Show last TAIL_LINES lines then follow
  log "Tailing log ($LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -f "$LOG_FILE"
fi

# -------------------------
# Unknown command handling
# -------------------------
log "ERROR: Unknown command: ${CMD:-<none>}"
usage
