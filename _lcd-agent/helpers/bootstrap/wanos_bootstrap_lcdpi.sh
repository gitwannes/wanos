#!/usr/bin/env bash
# --- file: _lcd-agent/helpers/bootstrap/wanos_bootstrap_lcdpi.sh ---
# ==============================================================================
# WanOS LCD Pi Bootstrap: MQTT + dual I2C LCD agent
# Run as root: sudo ./wanos_bootstrap_lcdpi.sh
# Target tree: /home/wannes/wanos  (same path as WanOS; LCD files only)
# ==============================================================================

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with root privileges (sudo)." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Agent lives two levels up from helpers/bootstrap when tree is already synced.
AGENT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APP_USER="wannes"
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_HOME}/wanos"
VENV_DIR="${APP_DIR}/wanos_venv"
ENV_FILE="${APP_DIR}/.env"
SERVICE_UNIT="/etc/systemd/system/wanos-lcd-agent.service"
SERVICE_SRC="${SCRIPT_DIR}/wanos-lcd-agent.service"
# Bookworm+: /boot/firmware/config.txt — older Pi OS: /boot/config.txt
BOOT_CONFIG=""
for cand in "/boot/firmware/config.txt" "/boot/config.txt"; do
    if [ -f "${cand}" ]; then
        BOOT_CONFIG="${cand}"
        break
    fi
done
LCD_PI_HOST_HINT="10.32.251.51"

echo "=========================================="
echo " Starting WanOS LCD Pi Bootstrap..."
echo "=========================================="

echo "[1/8] Installing OS dependencies..."
apt-get update
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    i2c-tools \
    rsync \
    git \
    vim \
    curl

echo "[2/8] Enabling I2C interface..."
if [ -z "${BOOT_CONFIG}" ]; then
    echo "ERROR: config.txt not found under /boot/firmware or /boot. Unsupported Pi OS layout?" >&2
    exit 1
fi
echo "Using boot config: ${BOOT_CONFIG}"
if ! grep -qE '^dtparam=i2c_arm=on' "${BOOT_CONFIG}"; then
    cat << 'EOF' >> "${BOOT_CONFIG}"

# --- WanOS LCD Pi hardware config ---
dtparam=i2c_arm=on
EOF
fi

echo "[3/8] Ensuring user and groups..."
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    echo "ERROR: User '${APP_USER}' does not exist. Create it first." >&2
    exit 1
fi
usermod -a -G i2c "${APP_USER}"

echo "[4/8] Creating ${APP_DIR} and /var/log/wanos..."
mkdir -p "${APP_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
mkdir -p /var/log/wanos
chown "${APP_USER}:${APP_USER}" /var/log/wanos

echo "[5/8] Installing Python venv (wanos_venv)..."
if [ ! -d "${VENV_DIR}" ]; then
    sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
fi
sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
if [ -f "${AGENT_ROOT}/requirements.txt" ]; then
    sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${AGENT_ROOT}/requirements.txt"
else
    sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install aiomqtt typing_extensions smbus2 python-dotenv
fi

echo "[6/8] Placing lcd_pi_agent.py..."
# Prefer a sidecar next to this script (first-boot ~/lcd-bootstrap), then the
# synced agent tree. After `wanos-sync run lcd`, AGENT_ROOT == APP_DIR and the
# file is already at DEST — do not cp onto itself (GNU cp errors; set -e quits).
DEST="${APP_DIR}/lcd_pi_agent.py"
AGENT_SRC=""
for cand in \
    "${SCRIPT_DIR}/lcd_pi_agent.py" \
    "${AGENT_ROOT}/lcd_pi_agent.py" \
    "${DEST}"; do
    if [ -f "${cand}" ]; then
        AGENT_SRC="${cand}"
        break
    fi
done
if [ -z "${AGENT_SRC}" ]; then
    echo "ERROR: lcd_pi_agent.py not found under ${AGENT_ROOT}." >&2
    echo "Sync with: helpers\\wanos-sync.bat run lcd" >&2
    exit 1
fi
if [ "${AGENT_SRC}" = "${DEST}" ] || { [ -e "${DEST}" ] && [ "${AGENT_SRC}" -ef "${DEST}" ]; }; then
    echo "Already in place: ${DEST}"
else
    cp "${AGENT_SRC}" "${DEST}"
fi
chown "${APP_USER}:${APP_USER}" "${DEST}"
chmod 0644 "${DEST}"

echo "[7/8] Writing ${ENV_FILE} (if missing)..."
if [ ! -f "${ENV_FILE}" ]; then
    cat << 'EOF' > "${ENV_FILE}"
# WanOS LCD agent — secrets in /home/wannes/wanos/.env (same path as WanOS main; never git)
# Broker = WanOS main Pi MQTT (usually 10.32.251.30).
WANOS_LCD_MQTT_BROKER_HOST=
WANOS_LCD_MQTT_BROKER_PORT=1883
WANOS_LCD_MQTT_USERNAME=st
WANOS_LCD_MQTT_PASSWORD=
WANOS_LCD_I2C_BUS=1
WANOS_LCD_ADDR_SCREEN1=39
WANOS_LCD_ADDR_SCREEN2=38
WANOS_LCD_TOPIC_SCREEN1=wanos/lcd/screen1
WANOS_LCD_TOPIC_SCREEN2=wanos/lcd/screen2
WANOS_LCD_SCREENSAVER_TIMEOUT_SECS=600
EOF
    chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
    chmod 0600 "${ENV_FILE}"
fi
if grep -q '^WANOS_LCD_MQTT_BROKER_HOST=$' "${ENV_FILE}"; then
    echo "WARNING: WANOS_LCD_MQTT_BROKER_HOST is still empty in ${ENV_FILE}."
fi
if grep -q '^WANOS_LCD_MQTT_PASSWORD=$' "${ENV_FILE}"; then
    echo "WARNING: WANOS_LCD_MQTT_PASSWORD is still empty in ${ENV_FILE}."
fi

echo "[8/8] Installing systemd unit..."
if [ -f "${SERVICE_SRC}" ]; then
    cp "${SERVICE_SRC}" "${SERVICE_UNIT}"
else
    cat << EOF > "${SERVICE_UNIT}"
[Unit]
Description=WanOS LCD Pi Agent
After=network-online.target
Wants=network-online.target

[Service]
User=${APP_USER}
Group=${APP_USER}
EnvironmentFile=${ENV_FILE}
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/lcd_pi_agent.py
Restart=always
RestartSec=5
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF
fi
chmod 0644 "${SERVICE_UNIT}"
systemctl daemon-reload
systemctl enable wanos-lcd-agent.service

echo "=========================================="
echo " [LCD PI BOOTSTRAP COMPLETE]"
echo "=========================================="
echo "SSH (reuse same PC key as WanOS Pi) — from Windows (once):"
echo "  Get-Content \$env:USERPROFILE\\.ssh\\id_ed25519.pub |"
echo "    ssh ${APP_USER}@${LCD_PI_HOST_HINT} \"mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys\""
echo "  ssh -o BatchMode=yes ${APP_USER}@${LCD_PI_HOST_HINT} \"echo ok\""
echo ""
echo "NEXT STEPS:"
echo "1) Edit ${ENV_FILE} (MQTT broker host + password)."
echo "2) Reboot (I2C overlay): sudo reboot"
echo "3) i2cdetect: sudo i2cdetect -y 1  (expect 26 and 27)"
echo "4) From PC: helpers\\wanos-sync.bat run lcd"
echo "5) sudo systemctl restart wanos-lcd-agent.service"
echo "6) Logs: journalctl -u wanos-lcd-agent -f   OR   tail -f /var/log/wanos/wanos.log"
echo "   Full guide: helpers/bootstrap/wanos-install-lcd-agent.md"
echo "=========================================="
