#!/usr/bin/env bash
# --- file: .cursor/start.sh ---
# Cloud Agent start phase for WanOS (per-boot, idempotent).
#
# Brings up the local Mosquitto broker the backend connects to. The broker
# credentials are (re)derived from .env every boot so the password file always
# matches WANOS_MQTT_PASSWORD, then the daemon is started if not already up.
# This script reconciles state and returns; the app itself runs as a terminal.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RT="$REPO_ROOT/.cursor/runtime"
CONF="$RT/mosquitto.conf"
PASSWD="$RT/mosquitto.passwd"
MQTT_USER="st"   # matches wanos.mqtt.username in config.yaml
MQTT_PORT=1883

mkdir -p "$RT"

# Ensure the log directory exists (cheap; snapshot may not preserve it).
sudo mkdir -p /var/log/wanos
sudo chown "$(id -u):$(id -g)" /var/log/wanos 2>/dev/null || true

if [ ! -f "$REPO_ROOT/.env" ]; then
    echo "[start] ERROR: .env missing; run .cursor/install.sh first." >&2
    exit 1
fi

# Load WANOS_MQTT_PASSWORD from .env.
set -a
# shellcheck disable=SC1091
. "$REPO_ROOT/.env"
set +a
if [ -z "${WANOS_MQTT_PASSWORD:-}" ]; then
    echo "[start] ERROR: WANOS_MQTT_PASSWORD not set in .env." >&2
    exit 1
fi

# (Re)generate the broker password file and config from the current .env.
mosquitto_passwd -b -c "$PASSWD" "$MQTT_USER" "$WANOS_MQTT_PASSWORD"
cat > "$CONF" <<EOF
# --- file: .cursor/runtime/mosquitto.conf (dev broker, generated) ---
listener ${MQTT_PORT} 127.0.0.1
allow_anonymous false
password_file ${PASSWD}
persistence false
log_dest stdout
EOF

# Start the broker only if nothing is already listening on the port.
if mosquitto_pub -h 127.0.0.1 -p "$MQTT_PORT" -u "$MQTT_USER" -P "$WANOS_MQTT_PASSWORD" \
        -t 'wanos/_healthcheck' -m up >/dev/null 2>&1; then
    echo "[start] Mosquitto already running and authenticating on ${MQTT_PORT}."
else
    echo "[start] launching Mosquitto broker..."
    mosquitto -c "$CONF" -d
    # Wait for readiness (auth round-trip), up to ~10s.
    for _ in $(seq 1 20); do
        if mosquitto_pub -h 127.0.0.1 -p "$MQTT_PORT" -u "$MQTT_USER" \
                -P "$WANOS_MQTT_PASSWORD" -t 'wanos/_healthcheck' -m up >/dev/null 2>&1; then
            echo "[start] Mosquitto is up on 127.0.0.1:${MQTT_PORT}."
            break
        fi
        sleep 0.5
    done
fi

echo "[start] done."
