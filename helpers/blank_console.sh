#!/usr/bin/env bash
#
# bank_console.sh
#
# Purpose:
#   Configure Raspberry Pi OS so that the screen:
#     - NEVER auto-wakes
#     - NEVER auto-dims
#     - NEVER auto-blanks
#     - NEVER receives DPMS ON events
#   Your custom scripts become the ONLY controller of the screen.
#
# Behavior:
#   - Dynamically detects legacy (/boot) vs modern (/boot/firmware) OS paths.
#   - Safely skips X11/LightDM modifications if running on a "Lite" OS image.
#   - Creates .bak backups before modifying any file.
# ---------------------------------------------------------------------------

set -euo pipefail

# =============================================================================
# CONFIGURATION TOGGLES
# =============================================================================

MODIFY_CMDLINE=true      # Disable console blanking (consoleblank=0)
MODIFY_UDEV=true         # Block kernel backlight "change" events
MODIFY_X11=true          # Disable X11 DPMS + blanking (skipped safely if missing)
MODIFY_LIGHTDM=true      # Disable LightDM DPMS wakeups (skipped safely if missing)
MODIFY_LOGIND=true       # Disable systemd-logind wake triggers

# =============================================================================
# DYNAMIC FILE PATHS
# =============================================================================

# Detect correct cmdline path (Trixie/Bookworm uses /firmware, older uses /boot)
if [ -f "/boot/firmware/cmdline.txt" ]; then
    CMDLINE="/boot/firmware/cmdline.txt"
elif [ -f "/boot/cmdline.txt" ]; then
    CMDLINE="/boot/cmdline.txt"
else
    CMDLINE=""
fi

UDEV_RULE="/etc/udev/rules.d/99-backlight.rules"
X11_CONF_DIR="/etc/X11/xorg.conf.d"
X11_MONITOR_CONF="$X11_CONF_DIR/10-monitor.conf"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
LOGIND_CONF="/etc/systemd/logind.conf"

# =============================================================================
# Helper: require sudo
# =============================================================================

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run with sudo."
    exit 1
fi

echo "Applying universal screen-control configuration..."
echo "Detected CMDLINE path: ${CMDLINE:-Not Found}"
echo

# =============================================================================
# Helper: backup a file if it exists
# =============================================================================

backup_file() {
    local file="$1"
    if [ -f "$file" ]; then
        cp "$file" "$file.bak"
        echo "Backup created: $file.bak"
    fi
}

# =============================================================================
# 1. Disable console blanking (kernel-level)
# =============================================================================

if [ "$MODIFY_CMDLINE" = true ]; then
    echo "[CMDLINE] Disabling console blanking..."

    if [ -z "$CMDLINE" ]; then
        echo "ERROR: cmdline.txt not found in /boot or /boot/firmware. Skipping."
        echo
    else
        backup_file "$CMDLINE"

        if ! grep -q "consoleblank=0" "$CMDLINE"; then
            echo "Adding consoleblank=0 to cmdline.txt..."
            sed -i 's/$/ consoleblank=0/' "$CMDLINE"
        else
            echo "consoleblank=0 already present."
        fi
        echo
    fi
else
    echo "[CMDLINE] Skipped (toggle disabled)."
    echo
fi

# =============================================================================
# 2. Block kernel backlight “change” events (udev rule)
# =============================================================================

if [ "$MODIFY_UDEV" = true ]; then
    echo "[UDEV] Installing backlight override rule..."

    if [ ! -d "/etc/udev/rules.d" ]; then
        echo "ERROR: /etc/udev/rules.d does not exist. Skipping udev rule."
        echo
    else
        backup_file "$UDEV_RULE"

        cat > "$UDEV_RULE" <<'EOF'
# Prevent kernel from re-enabling or adjusting backlight automatically
ACTION=="change", SUBSYSTEM=="backlight", RUN+="/bin/true"
EOF

        echo "Udev rule installed."
        echo
    fi
else
    echo "[UDEV] Skipped (toggle disabled)."
    echo
fi

# =============================================================================
# 3. Disable X11 DPMS and screen blanking
# =============================================================================

if [ "$MODIFY_X11" = true ]; then
    echo "[X11] Disabling X11 DPMS and blanking..."

    if [ ! -d "$X11_CONF_DIR" ]; then
        echo "INFO: X11 directory not found: $X11_CONF_DIR"
        echo "Skipping X11 DPMS disable (Expected on Lite OS images)."
        echo
    else
        backup_file "$X11_MONITOR_CONF"

        cat > "$X11_MONITOR_CONF" <<'EOF'
# Disable all DPMS and blanking for X11
Section "Monitor"
    Identifier "HDMI-1"
    Option "DPMS" "false"
EndSection

Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection
EOF

        echo "X11 DPMS disabled."
        echo
    fi
else
    echo "[X11] Skipped (toggle disabled)."
    echo
fi

# =============================================================================
# 4. Disable LightDM DPMS wakeups
# =============================================================================

if [ "$MODIFY_LIGHTDM" = true ]; then
    echo "[LIGHTDM] Disabling LightDM DPMS..."

    if [ ! -f "$LIGHTDM_CONF" ]; then
        echo "INFO: LightDM not found at $LIGHTDM_CONF"
        echo "Skipping LightDM DPMS disable (Expected on Lite OS images)."
        echo
    else
        backup_file "$LIGHTDM_CONF"

        # Ensure [Seat:*] section exists
        if ! grep -q "^\[Seat:\*\]" "$LIGHTDM_CONF"; then
            echo "[Seat:*]" >> "$LIGHTDM_CONF"
        fi

        # Remove old xserver-command lines
        sed -i '/xserver-command=/d' "$LIGHTDM_CONF"

        # Add DPMS disable
        echo "xserver-command=X -s 0 -dpms" >> "$LIGHTDM_CONF"

        echo "LightDM DPMS disabled."
        echo
    fi
else
    echo "[LIGHTDM] Skipped (toggle disabled)."
    echo
fi

# =============================================================================
# 5. Disable systemd-logind wake triggers
# =============================================================================

if [ "$MODIFY_LOGIND" = true ]; then
    echo "[LOGIND] Disabling logind wake triggers..."

    if [ ! -f "$LOGIND_CONF" ]; then
        echo "ERROR: $LOGIND_CONF not found. Skipping logind modification."
        echo
    else
        backup_file "$LOGIND_CONF"

        sed -i '/HandleLidSwitch=/d' "$LOGIND_CONF"
        sed -i '/HandleSuspendKey=/