#!/usr/bin/env bash
# --- file: helpers/bootstrap/backend/wanos_bootstrap_phase1.sh ---
# ==============================================================================
# WanOS Phase 1: System Bootstrapping (Debian 13 Trixie Lite 64-bit)
# Run as root or with sudo: sudo ./wanos_bootstrap_phase1.sh
# ==============================================================================

# Enforce strict error handling and guard against undefined variables
set -euo pipefail

# Directory this script lives in (phase1 + logcap siblings when copied together)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure script is run with root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with root privileges (sudo)." >&2
    exit 1
fi

echo "=========================================="
echo " Starting WanOS Phase 1 Setup..."
echo "=========================================="

# 1. Update system and install core tools from external apt-packages.txt
echo "[1/7] Updating system packages & installing dependencies from apt-packages.txt..."
apt-get update && apt-get upgrade -y

# Locate external apt-packages.txt helper file
APT_PKG_SRC=""
if [ -f "$WANNES_HOME/apt-packages.txt" ]; then
    APT_PKG_SRC="$WANNES_HOME/apt-packages.txt"
elif [ -f "./apt-packages.txt" ]; then
    APT_PKG_SRC="./apt-packages.txt"
fi

if [ -n "$APT_PKG_SRC" ]; then
    echo "Installing OS dependencies from $APT_PKG_SRC..."
    # Filter out comments (#) and blank lines, then pass package names to apt-get
    grep -vE '^\s*#|^\s*$' "$APT_PKG_SRC" | xargs apt-get install -y --no-install-recommends
else
    echo "ERROR: External apt-packages.txt not found in $WANNES_HOME/ or current directory!" >&2
    echo "Please copy apt-packages.txt to the Raspberry Pi before running Phase 1." >&2
    exit 1
fi

# NOTE: The package is named 'bat', but Debian renames its binary to 'batcat' to avoid conflicts
# Verify the 'batcat' binary was properly installed by the 'bat' package
command -v batcat &>/dev/null || echo "WARNING: batcat binary not found after package installation."

# 2. Hardware Interfaces (/boot/firmware for modern Pi OS)
echo "[2/7] Configuring Boot Firmware & Hardware Overlays..."
BOOT_CONFIG="/boot/firmware/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"

if ! grep -q "dtoverlay=disable-bt" "$BOOT_CONFIG"; then
    cat << 'EOF' >> "$BOOT_CONFIG"

# --- WanOS Hardware Config ---
# Pi 4: disable-bt remaps PL011 (ttyAMA0) to GPIO 14/15; enable_uart=1 is redundant but harmless
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

# Disable Bluetooth service — hardware already disabled via dtoverlay=disable-bt above
# Mask prevents hciuart from logging errors at every boot
sudo systemctl disable hciuart 2>/dev/null || true
sudo systemctl mask hciuart

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
# Admin UI / API: POST /api/admin/restart → passwordless service restart (not host reboot)
wannes ALL=(root) NOPASSWD: /usr/bin/systemctl restart wanos.service
EOF
chmod 0440 /etc/sudoers.d/wannes_sudo_policy

visudo -c -f /etc/sudoers.d/wannes_sudo_policy || {
    echo "ERROR: sudoers syntax invalid — removing file to prevent lockout."
    rm /etc/sudoers.d/wannes_sudo_policy
    exit 1
}

# Non-interactive check (must exit 0 once wanos.service exists; safe to skip early in Phase 1)
if systemctl cat wanos.service &>/dev/null; then
    if su - wannes -c 'sudo -n /usr/bin/systemctl restart wanos.service'; then
        echo "OK: passwordless systemctl restart wanos.service works for user wannes"
    else
        echo "WARN: sudo -n systemctl restart wanos.service failed for wannes — check sudoers"
    fi
else
    echo "NOTE: wanos.service not installed yet — after Phase 5, verify as user wannes:"
    echo "      sudo -n systemctl restart wanos.service"
fi

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

# 6b. rsyslog logcap — stop daemon.log; truncate syslog at 20 MiB (no archive).
# Scripts live in helpers/ (mirrored). Prefer the synced tree; fall back to
# copies next to this phase1 script on a fresh host before first sync.
LOGCAP_SCRIPT=""
for cand in \
    "${WANNES_HOME}/wanos/helpers/wanos_rsyslog_logcap.sh" \
    "${SELF_DIR}/wanos_rsyslog_logcap.sh" \
    "./wanos_rsyslog_logcap.sh"; do
    if [ -f "${cand}" ]; then
        LOGCAP_SCRIPT="${cand}"
        break
    fi
done
if [ -n "${LOGCAP_SCRIPT}" ]; then
    echo "[6b] Applying WanOS rsyslog logcap (${LOGCAP_SCRIPT})..."
    bash "${LOGCAP_SCRIPT}"
else
    echo "WARN: wanos_rsyslog_logcap.sh not found — skip rsyslog cap."
    echo "      After code sync: sudo bash ${WANNES_HOME}/wanos/helpers/wanos_rsyslog_logcap.sh"
fi

# 7. Configure Samba using external smb.conf
echo "[7/7] Configuring Samba from external smb.conf..."
mkdir -p "$WANNES_HOME/wanos"
chown -R wannes:wannes "$WANNES_HOME/wanos"

# Locate external smb.conf helper file
SMB_SRC=""
if [ -f "$WANNES_HOME/smb.conf" ]; then
    SMB_SRC="$WANNES_HOME/smb.conf"
elif [ -f "./smb.conf" ]; then
    SMB_SRC="./smb.conf"
fi

if [ -n "$SMB_SRC" ]; then
    echo "Copying $SMB_SRC to /etc/samba/smb.conf..."
    cp "$SMB_SRC" /etc/samba/smb.conf
else
    echo "ERROR: External smb.conf not found in $WANNES_HOME/ or current directory!" >&2
    echo "Please copy smb.conf to the Raspberry Pi before running Phase 1." >&2
    exit 1
fi

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