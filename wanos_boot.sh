#!/usr/bin/env bash
# wanos_boot.sh
# Manage a development uvicorn process for "uvicorn main:app --host 0.0.0.0 --port 8000"
# Commands:
#   start           Start uvicorn in background (logs to $LOG_FILE)
#   status          Show whether uvicorn is running and which PID(s)
#   stop [force]    Attempt graceful shutdown (SIGINT) of matching uvicorn PID(s); 'force' forces kill-9
#   consolelog      Show last $TAIL_LINES lines of wanos.console.log and follow
#   applog          Show last $TAIL_LINES lines of /var/log/wisc/wanos.log and follow
#   reload          Attempt stop (no force); if stop succeeds, start; do not force-kill
set -euo pipefail

# -------------------------
# Configuration
# -------------------------
VENV_DIR="$HOME/wisc_backend/wisc_backend_venv"

# For info: manual launch: uvicorn main:app --host 0.0.0.0 --port 8000
APP_CMD="$VENV_DIR/bin/python -u -m uvicorn"
APP_ARGS="main:app --host 0.0.0.0 --port 8000"

LOG_FILE="$HOME/wisc_backend/wanos.console.log"
APP_LOG_FILE="/var/log/wisc/wanos.log"
GRACE_PERIOD=10   # seconds to wait for graceful shutdown
TAIL_LINES=20     # number of lines to show initially for 'consolelog' and 'applog'

# -------------------------
# Helpers
# -------------------------
log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

usage() {
  cat <<EOF
Usage: $0 <command> [args]

Commands:
  start           Start uvicorn in background (logs to $LOG_FILE)
  status          Show whether uvicorn is running and which PID(s)
  stop [force]    Attempt graceful shutdown (SIGINT) of matching uvicorn PID(s); 'force' forces kill -9
  consolelog      Show last $TAIL_LINES lines of $LOG_FILE and follow
  applog          Show last $TAIL_LINES lines of $APP_LOG_FILE and follow
  reload          Attempt stop (no force); if stop succeeds, start; do not force-kill

Examples:
  $0 start
  $0 status
  $0 stop
  $0 stop force
  $0 consolelog
  $0 applog
  $0 reload
EOF
  exit 2
}

# Return space-separated list of live uvicorn PIDs (or empty)
find_uvicorn_pids() {
  pids=$(pgrep -f "uvicorn main:app" || true)
  if [ -z "$pids" ]; then
    printf ''
  else
    printf '%s' "$(echo "$pids" | tr '\n' ' ' | sed 's/ $//')"
  fi
}

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
  pids=$(find_uvicorn_pids)
  if [ -n "$pids" ]; then
    log "uvicorn appears to be running (PID(s): $pids). Console log: $LOG_FILE"
    ps -o pid,ppid,cmd -p $pids || true
    exit 0
  fi
  log "No uvicorn process found."
  exit 1
fi

# -------------------------
# Stop (graceful) flow (no pidfile)
# -------------------------
if [ "$CMD" = "stop" ]; then
  pids=$(find_uvicorn_pids)
  if [ -z "$pids" ]; then
    log "No uvicorn process found."
    exit 0
  fi

  log "Attempting graceful shutdown of PID(s): $pids"
  kill -INT $pids 2>/dev/null || true

  for i in $(seq 1 $GRACE_PERIOD); do
    sleep 1
    still=$(for p in $pids; do kill -0 "$p" 2>/dev/null && printf '%s ' "$p"; done || true)
    if [ -z "$still" ]; then
      log "Shutdown successful: no uvicorn processes remain."
      exit 0
    fi
    log "Waiting for processes to exit... ($i/$GRACE_PERIOD)"
  done

  still=$(for p in $pids; do kill -0 "$p" 2>/dev/null && printf '%s ' "$p"; done || true)
  if [ -z "$still" ]; then
    log "Shutdown completed in the final check."
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
      exit 0
    fi
  else
    log "Graceful shutdown timed out. Re-run with: $0 stop force"
    exit 1
  fi
fi

# -------------------------
# Start flow (no pidfile)
# -------------------------
if [ "$CMD" = "start" ]; then
  pids_now=$(find_uvicorn_pids)
  if [ -n "$pids_now" ]; then
    log "Found uvicorn process(es): $pids_now. Doing nothing."
    exit 0
  fi

  log "Starting uvicorn in background. Console log -> $LOG_FILE"
  activate_venv

  mkdir -p "$(dirname "$LOG_FILE")"
  touch "$LOG_FILE"
  chmod 644 "$LOG_FILE"

  # Ensure unbuffered Python output and run under bash -lc so reloader and worker inherit redirection.
  export PYTHONUNBUFFERED=1
  # Use venv python directly so installed packages are available
  nohup bash -lc "$APP_CMD $APP_ARGS --reload" >> "$LOG_FILE" 2>&1 &
  starter_pid=$!

  sleep 1

  uv_pids=$(find_uvicorn_pids)
  if [ -n "$uv_pids" ]; then
    log "Started uvicorn (detected PID(s): $uv_pids). Console log -> $LOG_FILE"
    log "Tail the console log with: $0 consolelog"
    exit 0
  fi

  if kill -0 "$starter_pid" 2>/dev/null; then
    log "Started uvicorn (starter PID: $starter_pid). Console log -> $LOG_FILE"
    log "Tail the console log with: $0 consolelog"
    exit 0
  fi

  log "Failed to start uvicorn. Check $LOG_FILE for errors."
  exit 1
fi

# -------------------------
# Reload: stop (no force) then start if stop succeeded
# -------------------------
if [ "$CMD" = "reload" ]; then
  log "Reload requested: attempting graceful stop first (no force)."
  # run stop without force
  if "$0" stop; then
    log "Stop succeeded; starting again."
    "$0" start
    exit $?
  else
    log "Stop failed or timed out; reload aborted (will not force-kill)."
    exit 1
  fi
fi

# -------------------------
# Console log tailing
# -------------------------
if [ "$CMD" = "consolelog" ]; then
  if [ ! -f "$LOG_FILE" ]; then
    log "Console log file not found: $LOG_FILE"
    exit 1
  fi
  log "Tailing console log ($LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$LOG_FILE"
fi

# -------------------------
# App log tailing
# -------------------------
if [ "$CMD" = "applog" ]; then
  if [ ! -f "$APP_LOG_FILE" ]; then
    log "App log file not found: $APP_LOG_FILE"
    exit 1
  fi
  log "Tailing app log ($APP_LOG_FILE). Showing last $TAIL_LINES lines then following."
  exec tail -n "$TAIL_LINES" -F "$APP_LOG_FILE"
fi

# -------------------------
# Unknown command handling
# -------------------------
log "ERROR: Unknown command: ${CMD:-<none>}"
usage
