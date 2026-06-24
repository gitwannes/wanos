#!/usr/bin/env bash
# ==============================================================================
# Kiosk Phase 2: Application Setup (Wayland & Chromium)
# Run as user wannes: ./kiosk_bootstrap_phase2.sh
# ==============================================================================

set -euo pipefail

if [ "$(id -un)" != "wannes" ]; then
    echo "Error: This script must be run as the user 'wannes'." >&2
    exit 1
fi

WANNES_HOME="/home/wannes"
KIOSK_DIR="$WANNES_HOME/kiosk"

# --- CONFIGURATION ---
# Change this to the IP address of your Backend WanOS Pi!
BACKEND_IP="10.32.251.28"
DASHBOARD_URL="http://$BACKEND_IP:8000/wisc-panel.html"
# ---------------------

echo "=========================================="
echo " Starting Kiosk Phase 2 Setup..."
echo "=========================================="

mkdir -p "$KIOSK_DIR"

# 1. Create the Kiosk Startup Wrapper
echo "[1/2] Generating Wayland boot script..."
cat << EOF > "$KIOSK_DIR/start_kiosk.sh"
#!/bin/bash

# Boot-Wait Loop: Hold Chromium hostage until the Backend API responds
# This completely prevents the "No Internet" dinosaur error on weak Wi-Fi
until curl -s --head http://$BACKEND_IP:8000 | grep "200" > /dev/null; do
    sleep 2
done

# Resolve the correct Wayland KMS backlight path dynamically at runtime
BL_PATH=""
for candidate in /sys/class/backlight/rpi_backlight /sys/class/backlight/10-0045; do
    if [ -e "\$candidate/bl_power" ]; then
        BL_PATH="\$candidate"
        break
    fi
done

if [ -n "\$BL_PATH" ]; then
    # Start the Wayland idle supervisor (swayidle) in the background.
    # 600 seconds = 10 minutes. 
    swayidle -w \\
        timeout 600 "echo 1 > \$BL_PATH/bl_power" \\
        resume "echo 0 > \$BL_PATH/bl_power" &
else
    echo "Warning: No compatible backlight path found. Screen blanking disabled."
fi

# Launch the Cage compositor locked to Chromium
exec cage -s -- chromium-browser \\
    --kiosk \\
    --ozone-platform=wayland \\
    --enable-features=UseOzonePlatform \\
    --incognito \\
    --disable-infobars \\
    --no-first-run \\
    --window-position=0,0 \\
    --check-for-update-interval=31536000 \\
    --touch-events=enabled \\
    "$DASHBOARD_URL"
EOF

chmod +x "$KIOSK_DIR/start_kiosk.sh"

# 2. Create the Systemd Kiosk Service
echo "[2/2] Generating Systemd service..."
sudo tee /etc/systemd/system/kiosk.service > /dev/null << EOF
[Unit]
Description=WanOS HTML Kiosk Dashboard
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
User=wannes
Group=wannes
WorkingDirectory=/home/wannes/kiosk
# Forces software cursor hiding in wlroots compositors
Environment="WLR_NO_HARDWARE_CURSORS=1" 
ExecStart=/home/wannes/kiosk/start_kiosk.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable kiosk.service

echo "================================================================"
echo " [KIOSK PHASE 2 COMPLETE]"
echo "================================================================"
echo "The Kiosk display engine is now fully installed and armed."
echo "Target URL: $DASHBOARD_URL"
echo " "
echo "To manually start the dashboard immediately, run:"
echo "sudo systemctl start kiosk.service"
echo "================================================================"