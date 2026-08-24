#!/usr/bin/env bash
# --- file: _lcd-agent/startwanoslcd.sh ---
# Service control for WanOS LCD Pi agent (mirrors startwanos.sh on main Pi).

# Automatically elevate to root if not already running as root
if [ "$EUID" -ne 0 ]; then
    echo "Elevating privileges... (Please enter your password if prompted)"
    exec sudo "$0" "$@"
fi

case "$1" in
    start)
        echo "Starting WanOS LCD agent..."
        systemctl start wanos-lcd-agent.service
        ;;
    stop)
        echo "Stopping WanOS LCD agent..."
        systemctl stop wanos-lcd-agent.service
        ;;
    restart)
        echo "Restarting WanOS LCD agent..."
        systemctl restart wanos-lcd-agent.service
        ;;
    log)
        echo "Tailing WanOS LCD console log (Press CTRL+C to exit)..."
        journalctl -u wanos-lcd-agent.service -n 50 -f
        ;;
    status)
        systemctl status wanos-lcd-agent.service --no-pager
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|log|status}"
        exit 1
        ;;
esac
