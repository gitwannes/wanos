#!/usr/bin/env bash
# ==============================================================================
# WanOS Phase 1: System Bootstrapping (Debian 13 Trixie Lite 64-bit)
# Run as root or with sudo: sudo ./wanos_bootstrap_phase1.sh
# ==============================================================================

# Enforce strict error handling and guard against undefined variables
set -euo pipefail

# Ensure script is run with root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with root privileges (sudo)." >&2
    exit 1
fi

echo "=========================================="
echo " Starting WanOS Phase 1 Setup..."
echo "=========================================="

# 1. Update system and install core tools
echo "[1/7] Updating system packages & installing dependencies..."
apt-get update && apt-get upgrade -y
# NOTE: The package is named 'bat', but Debian renames its binary to 'batcat' to avoid conflicts
apt-get install -y vim bat samba i2c-tools python3-venv python3-pip python3-libgpiod udev curl git

# Verify the 'batcat' binary was properly installed by the 'bat' package
command -v batcat &>/dev/null || echo "WARNING: batcat binary not found after package installation."

# 2. Hardware Interfaces (/boot/firmware for modern Pi OS)
echo "[2/7] Configuring Boot Firmware & Hardware Overlays..."
BOOT_CONFIG="/boot/firmware/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"

if ! grep -q "dtoverlay=disable-bt" "$BOOT_CONFIG"; then
    cat << 'EOF' >> "$BOOT_CONFIG"

# --- WanOS Hardware Config ---
dtparam=audio=off
dtoverlay=disable-bt
enable_uart=1
EOF
fi

if [ -f "$CMDLINE" ]; then
    if ! grep -q "consoleblank=0" "$CMDLINE"; then
        sed -i 's/$/ consoleblank=0/' "$CMDLINE"
    fi
fi

# 3. Environment & Aliases (.bashrc, .profile, .vimrc)
echo "[3/7] Configuring user bash profiles..."
WANNES_HOME="/home/wannes"

if ! grep -q "WanOS Custom Aliases" "$WANNES_HOME/.bashrc"; then
    cat << 'EOF' >> "$WANNES_HOME/.bashrc"

# --- WanOS Custom Aliases ---
alias ls='ls -lh --color=auto'
alias cat='batcat'
alias lw='ls /var/log/wanos/* -t'
EOF
fi

if ! grep -q "WanOS Path & Console Monitors" "$WANNES_HOME/.profile"; then
    cat << 'EOF' >> "$WANNES_HOME/.profile"

# --- WanOS Path & Console Monitors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}** active console sessions${YELLOW}"
w
echo -e "${GREEN}** background jobs${YELLOW}"
# Note: 'jobs' will output nothing at login startup, but serves as a reminder placeholder
jobs
echo -e "${GREEN}** active python jobs${YELLOW}"
pgrep -af python || echo "None"
echo -e "${NC}"

# Clean up variables
unset RED GREEN YELLOW NC

if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi
EOF
fi

# Seed files: Create only if they do not exist
if [ ! -f "$WANNES_HOME/.vimrc" ]; then
    cat << 'EOF' > "$WANNES_HOME/.vimrc"
syntax on
colorscheme torte
set mouse=a
EOF
fi

mkdir -p "$WANNES_HOME/.config/bat"
if [ ! -f "$WANNES_HOME/.config/bat/config" ]; then
    cat << 'EOF' > "$WANNES_HOME/.config/bat/config"
--paging=never
--style=plain
EOF
fi
chown -R wannes:wannes "$WANNES_HOME/.config" "$WANNES_HOME/.vimrc"

# 4. Sudo Policies & Groups
echo "[4/7] Setting Sudo Policies and Groups..."
usermod -a -G dialout,i2c,gpio wannes

cat << 'EOF' > /etc/sudoers.d/wannes_sudo_policy
Defaults timestamp_timeout=30
wannes ALL=(ALL) ALL
wannes ALL=(root) NOPASSWD: /usr/local/bin/log2ram write
EOF
chmod 0440 /etc/sudoers.d/wannes_sudo_policy

visudo -c -f /etc/sudoers.d/wannes_sudo_policy || {
    echo "ERROR: sudoers syntax invalid — removing file to prevent lockout."
    rm /etc/sudoers.d/wannes_sudo_policy
    exit 1
}

# 5. WanOS Logging Directory
echo "[5/7] Creating Log Directories..."
mkdir -p /var/log/wanos
chown wannes:wannes /var/log/wanos

# 6. Install & Configure Log2Ram
echo "[6/7] Installing Log2Ram..."
if ! command -v log2ram &>/dev/null; then
    (
        cd /tmp
        git clone --branch v1.1.3 --depth 1 https://github.com/azlux/log2ram.git
        cd log2ram
        chmod +x install.sh
        ./install.sh
    )
    sed -i 's/^SIZE=.*/SIZE=256M/' /etc/log2ram.conf
    
    mkdir -p /etc/systemd/system/log2ram-daily.timer.d
    cat << 'EOF' > /etc/systemd/system/log2ram-daily.timer.d/override.conf
[Timer]
OnCalendar=
OnCalendar=hourly
EOF
    systemctl daemon-reload
else
    echo "Log2Ram is already installed. Skipping."
fi

# 7. Configure Samba
echo "[7/7] Configuring Samba..."
mkdir -p "$WANNES_HOME/wanos"
chown -R wannes:wannes "$WANNES_HOME/wanos"

cat << 'EOF' > /etc/samba/smb.conf
[global]
    workgroup = WORKGROUP
    server string = WanOS Storage
    server role = standalone server
    security = user

    # Logging
    log file = /var/log/samba/log.%m
    max log size = 1000
    logging = file
    panic action = /usr/share/samba/panic-action %d

    # Disable printer subsystem (improves performance and limits noise)
    load printers = no
    printing = standard
    printcap name = /dev/null
    disable spoolss = yes

    # Guest handling
    map to guest = bad user

[wanos_share]
    comment = WanOS Application Share
    path = /home/wannes/wanos
    valid users = wannes
    browseable = yes
    read only = no
    guest ok = no

    # Permissions: Ensures files and folders are immediately executable (rwxrwxr-x)
    create mask = 0775
    force create mode = 0775
    directory mask = 0775
    force directory mode = 0775
EOF

systemctl enable --now smbd

echo "================================================================"
echo " [PHASE 1 COMPLETE]"
echo "================================================================"
echo "NEXT STEPS:"
echo "1. Set Samba password:   sudo smbpasswd -a wannes"
echo "2. Reboot the system:    sudo reboot"
echo "3. Connect from Windows to \\\\<PI_IP>\\wanos_share"
echo "4. Copy your .env, requirements.txt, and application code."
echo "5. Run Phase 2 script:   ./wanos_bootstrap_phase2.sh"
echo "================================================================"