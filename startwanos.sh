#!/usr/bin/env bash

# Automatically elevate to root if not already running as root
if [ "$EUID" -ne 0 ]; then
    echo "Elevating privileges... (Please enter your password if prompted)"
    exec sudo "$0" "$@"
fi

# Handle the command switches
case "$1" in
    start)
        echo "🚀 Starting WanOS..."
        systemctl start wanos.service
        ;;
    stop)
        echo "🛑 Stopping WanOS..."
        systemctl stop wanos.service
        ;;
    restart)
        echo "🔄 Restarting WanOS..."
        systemctl restart wanos.service
        ;;
    log)
        echo "📋 Tailing WanOS console log (Press CTRL+C to exit)..."
        journalctl -u wanos.service -n 50 -f
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|log}"
        exit 1
        ;;
esac