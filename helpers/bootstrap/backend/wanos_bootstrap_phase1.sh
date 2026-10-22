#!/usr/bin/env bash
# --- file: helpers/bootstrap/backend/wanos_bootstrap_phase1.sh ---
# ==============================================================================
# WanOS Phase 1: System Bootstrapping (Debian 13 Trixie Lite 64-bit)
# Ops7: no Samba; installs nginx + PHP-FPM; gates patched PHP micro-release
# Run as root or with sudo: sudo ./wanos_bootstrap_phase1.sh
# ==============================================================================

# Enforce strict error handling and guard against undefined variables
set -euo pipefail

# Directory this script lives in (phase1 + logcap siblings when copied together)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WANNES_HOME="/home/wannes"

# Ensure script is run with root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with root privileges (sudo)." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "=========================================="
echo " Starting WanOS Phase 1 Setup..."
echo "=========================================="

# --- helpers ---
# First field only; strip blank/full-line comments and inline "# ..." tails
wanos_apt_install_from_list() {
    local src="$1"
    awk '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        {
            sub(/#.*/, "")
            gsub(/^[[:space:]]+|[[:space:]]+$/, "")
            if (length($0) > 0) print $1
        }
    ' "${src}" | xargs -r apt-get install -y --no-install-recommends
}

# PHP2Shell gate: Trixie 8.4.x >= 8.4.27; Bookworm fallback 8.2.x >= 8.2.35
wanos_php_version_gate() {
    if ! command -v php >/dev/null 2>&1; then
        echo "ERROR: php CLI not found after apt install." >&2
        exit 1
    fi
    local cur major_minor need lowest
    cur="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION.".".PHP_RELEASE_VERSION;')"
    major_minor="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
    case "${major_minor}" in
        8.4) need="8.4.27" ;;
        8.2) need="8.2.35" ;;
        *)
            echo "ERROR: unexpected PHP ${cur} (expected 8.4.x on Trixie, or 8.2.x Bookworm fallback)." >&2
            echo "       PHP2Shell requires a patched micro-release before public :443." >&2
            exit 1
            ;;
    esac
    lowest="$(printf '%s\n' "${need}" "${cur}" | sort -V | head -n1)"
    if [ "${lowest}" != "${need}" ]; then
        echo "ERROR: PHP ${cur} is below patched minimum ${need} (PHP2Shell)." >&2
        echo "       apt upgrade php-fpm php-cli (or install patched builds) before exposing :443." >&2
        exit 1
    fi
    echo "OK: PHP ${cur} meets patched gate (>= ${need})"
    php -v | head -n1
}

# 1. Update system and install core tools from external apt-packages.txt
echo "[1/7] Updating system packages & installing dependencies from apt-packages.txt..."
apt-get update && apt-get upgrade -y

# Locate external apt-packages.txt helper file
APT_PKG_SRC=""
if [ -f "${SELF_DIR}/apt-packages.txt" ]; then
    APT_PKG_SRC="${SELF_DIR}/apt-packages.txt"
elif [ -f "$WANNES_HOME/apt-packages.txt" ]; then
    APT_PKG_SRC="$WANNES_HOME/apt-packages.txt"
elif [ -f "./apt-packages.txt" ]; then
    APT_PKG_SRC="./apt-packages.txt"
fi

if [ -n "$APT_PKG_SRC" ]; then
    echo "Installing OS dependencies from $APT_PKG_SRC..."
    wanos_apt_install_from_list "$APT_PKG_SRC"
else
    echo "ERROR: External apt-packages.txt not found next to this script, in $WANNES_HOME/, or cwd!" >&2
    echo "Please copy apt-packages.txt to the Raspberry Pi before running Phase 1." >&2
    exit 1
fi

# NOTE: The package is named 'bat', but Debian renames its binary to 'batcat' to avoid conflicts
command -v batcat &>/dev/null || echo "WARNING: batcat binary not found after package installation."

# Ensure PHP-FPM is enabled; gate patched micro-release (Ops7 / PHP2Shell)
echo "[1b] Enabling PHP-FPM + version gate..."
FPM_UNIT=""
while IFS= read -r unit; do
    case "${unit}" in
        php*-fpm.service)
            FPM_UNIT="${unit%.service}"
            break
            ;;
    esac
done < <(systemctl list-unit-files --type=service --no-legend --no-pager | awk '{print $1}')

if [ -z "${FPM_UNIT}" ]; then
    echo "ERROR: No php*-fpm.service unit found after package install." >&2
    exit 1
fi
systemctl enable --now "${FPM_UNIT}"
wanos_php_version_gate

# nginx present for later app.wanos.be + WLW vhost (site files still manual / overlay)
if command -v nginx >/dev/null 2>&1; then
    systemctl enable nginx
    echo "OK: nginx package present (enable only; site config is a later step)."
else
    echo "ERROR: nginx not found after apt install." >&2
    exit 1
fi

# Ops7: never install Samba — purge if a prior image left it
if dpkg -l samba 2>/dev/null | grep -q '^ii'; then
    echo "Purging leftover Samba (Ops7: unused)..."
    systemctl disable --now smbd nmbd 2>/dev/null || true
    apt-get purge -y samba samba-common samba-common-bin 2>/dev/null || true
    apt-get autoremove -y || true
fi

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
systemctl disable hciuart 2>/dev/null || true
systemctl mask hciuart

# 3. Environment & Aliases (.bashrc, .profile, .vimrc)
echo "[3/7] Configuring user bash profiles..."

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

# 5. WanOS Logging Directory + app tree stub
echo "[5/7] Creating Log Directories and app tree stub..."
mkdir -p /var/log/wanos
chown wannes:wannes /var/log/wanos
mkdir -p "$WANNES_HOME/wanos"
chown -R wannes:wannes "$WANNES_HOME/wanos"

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

# 7. Summary (no Samba — Ops7)
echo "[7/7] Phase 1 host baseline complete (no Samba)."

echo "================================================================"
echo " [PHASE 1 COMPLETE]"
echo "================================================================"
echo "NEXT STEPS:"
echo "1. Reboot:                 sudo reboot"
echo "2. Sync WanOS tree:        helpers\\wanos-sync.bat run  (from PC)"
echo "3. Run Phase 2 as wannes:  ./wanos_bootstrap_phase2.sh"
echo "4. Finish Nginx app.wanos.be + Mosquitto/Z-Wave (install guide)."
echo "5. Then WLW overlay:       sudo bash ~/be90webserver/helpers/bootstrap/wlw_bootstrap.sh"
echo "PHP gate OK above - do not expose public :443 until LE + WLW smoke."
echo "================================================================"
