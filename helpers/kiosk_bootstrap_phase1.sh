#!/usr/bin/env bash
# ==============================================================================
# Kiosk Phase 1: System Bootstrapping (Debian 12 Bookworm Lite 32-bit)
# Run as root or with sudo: sudo ./kiosk_bootstrap_phase1.sh
# ==============================================================================

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with root privileges (sudo)." >&2
    exit 1
fi

echo "=========================================="
echo " Starting Kiosk Phase 1 Setup..."
echo "=========================================="

# 1. Update system and install core Kiosk tools
echo "[1/7] Installing Wayland Kiosk dependencies..."
apt-get update && apt-get upgrade -y
apt-get install -y cage chromium-browser swayidle vim bat samba curl git udev iw

# 2. Hardware Interfaces (/boot/firmware/config.txt)
echo "[2/7] Configuring DSI Hardware Overlays..."
BOOT_CONFIG="/boot/firmware/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"

# Safely strip out old HDMI/UART forces if they exist at the start of a line
sed -i '/^hdmi_force_hotplug/d' "$BOOT_CONFIG" || true
sed -i '/^enable_uart/d' "$BOOT_CONFIG" || true

if ! grep -q "vc4-kms-dsi-7inch" "$BOOT_CONFIG"; then
    cat << 'EOF' >> "$BOOT_CONFIG"

# --- Kiosk Display Hardware Config ---
dtparam=audio=off
dtoverlay=disable-bt
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-dsi-7inch
EOF
fi

# Prevent TTY from blanking beneath the compositor
if [ -f "$CMDLINE" ] && ! grep -q "consoleblank=0" "$CMDLINE"; then
    sed -i 's/$/ consoleblank=0/' "$CMDLINE"
fi

# Silence the Bluetooth UART service to prevent boot errors since hardware BT is disabled
systemctl disable hciuart 2>/dev/null || true
systemctl mask hciuart

# 3. Wi-Fi Power Management Override (Critical for SSE stability)
echo "[3/7] Disabling Wi-Fi Power Save..."
cat << 'EOF' > /etc/systemd/system/wifi-powersave-off.service
[Unit]
Description=Disable WiFi Power Management
Requires=sys-subsystem-net-devices-wlan0.device
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/iw dev wlan0 set power_save off

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable wifi-powersave-off.service

# 4. Touchscreen & Backlight Udev Rules
echo "[4/7] Setting Display and Touch Udev Rules..."

# Allow swayidle to blank the DSI screen without sudo
cat << 'EOF' > /etc/udev/rules.d/99-backlight.rules
SUBSYSTEM=="backlight", RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
EOF

# Map the FT5406 digitizer strictly to the DSI-1 output for Cage
cat << 'EOF' > /etc/udev/rules.d/99-cage-touch.rules
KERNEL=="event[0-9]*", SUBSYSTEM=="input", ATTRS{name}=="FT5406 memory based driver", ENV{WL_OUTPUT}="DSI-1"
EOF

udevadm control --reload-rules && udevadm trigger

# 5. Environment & Aliases
echo "[5/7] Configuring user bash profiles..."
WANNES_HOME="/home/wannes"

if ! grep -q "WanOS Custom Aliases" "$WANNES_HOME/.bashrc"; then
    cat << 'EOF' >> "$WANNES_HOME/.bashrc"
# --- WanOS Custom Aliases ---
alias ls='ls -lh --color=auto'
# Note: The 'bat' package on Debian 32-bit renames its binary to 'batcat' to avoid conflicts
alias cat='batcat'
EOF
fi

mkdir -p "$WANNES_HOME/.config/bat"
if [ ! -f "$WANNES_HOME/.config/bat/config" ]; then
    echo "--paging=never" > "$WANNES_HOME/.config/bat/config"
    echo "--style=plain" >> "$WANNES_HOME/.config/bat/config"
fi
chown -R wannes:wannes "$WANNES_HOME/.config"

# 6. Install Log2Ram (Preserves SD card from browser cache writes)
echo "[6/7] Installing Log2Ram..."
if ! command -v log2ram &>/dev/null; then
    (
        cd /tmp
        git clone --branch v1.1.3 --depth 1 https://github.com/azlux/log2ram.git
        cd log2ram && chmod +x install.sh && ./install.sh
    )
    sed -i 's/^SIZE=.*/SIZE=128M/' /etc/log2ram.conf
else
    echo "Log2Ram is already installed. Skipping."
fi

# 7. Configure Samba (For easy remote configuration access)
echo "[7/7] Configuring Samba..."
mkdir -p "$WANNES_HOME/kiosk"
chown -R wannes:wannes "$WANNES_HOME/kiosk"

cat << 'EOF' > /etc/samba/smb.conf
[global]
    workgroup = WORKGROUP
    server string = Kiosk Storage
    server role = standalone server
    security = user
    log file = /var/log/samba/log.%m
    logging = file
    load printers = no
    printing = standard
    printcap name = /dev/null
    disable spoolss = yes
    map to guest = bad user

[kiosk_share]
    path = /home/wannes/kiosk
    valid users = wannes
    browseable = yes
    read only = no
    create mask = 0775
    directory mask = 0775
EOF
systemctl enable --now smbd

echo "================================================================"
echo " [KIOSK PHASE 1 COMPLETE]"
echo "================================================================"
echo "NEXT STEPS:"
echo "1. Set Samba password:   sudo smbpasswd -a wannes"
echo "2. Reboot the system:    sudo reboot"
echo "3. Run Phase 2 script:   ./kiosk_bootstrap_phase2.sh"
echo "================================================================"