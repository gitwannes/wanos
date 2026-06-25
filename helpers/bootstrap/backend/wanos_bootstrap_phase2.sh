#!/usr/bin/env bash
# ==============================================================================
# WanOS Phase 2: Application Setup (Python VENV & App Scripts)
# Run as user wannes: ./wanos_bootstrap_phase2.sh
# ==============================================================================

# Strict enforcement of variables and failures
set -euo pipefail

# Ensure this script is NOT run as root, but as the active application user
if [ "$(id -un)" != "wannes" ]; then
    echo "Error: This script must be run as the user 'wannes'." >&2
    exit 1
fi

WANNES_HOME="/home/wannes"
APP_DIR="$WANNES_HOME/wanos"

echo "=========================================="
echo " Starting WanOS Phase 2 Setup..."
echo "=========================================="

# 1. Setup Virtual Environment & Requirements
echo "[1/3] Setting up Python Virtual Environment..."
cd "$APP_DIR"

if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found in $APP_DIR."
    echo "Please copy it via Samba first."
    exit 1
fi

if [ ! -d "wanos_venv" ]; then
    python3 -m venv wanos_venv
fi

[ -f "wanos_venv/bin/activate" ] || { echo "ERROR: Virtual environment creation failed."; exit 1; }

source wanos_venv/bin/activate

# Left unguarded intentionally: acts as a fast-sync if requirements change
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt

# 2. RFXCom Udev Rules
echo "[2/3] Setting up RFXCom Udev Rules..."
sudo tee /etc/udev/rules.d/99-rfxcom.rules > /dev/null << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="rfxcom"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty

# 3. Cleanup
echo "[3/3] Finalizing setup..."
command -v deactivate &>/dev/null && deactivate || true

echo "================================================================"
echo " [PHASE 2 COMPLETE]"
echo "================================================================"
echo "The WanOS application environment is fully primed."
echo "Virtual environment path: $APP_DIR/wanos_venv"
echo " "
echo "NOTE: The /dev/rfxcom symlink will only become visible after"
echo "you physically plug the USB device back into the Pi."
echo " "
echo "You may now start the application ecosystem."
echo "================================================================"