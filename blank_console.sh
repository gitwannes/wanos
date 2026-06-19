#!/usr/bin/env bash
#
# setup_screen_control.sh
#
# Purpose:
#   Configure Raspberry Pi OS Bullseye so that the screen:
#     - NEVER auto-wakes
#     - NEVER auto-dims
#     - NEVER auto-blanks
#     - NEVER receives DPMS ON events
#   Your blank_console.sh script becomes the ONLY controller of the screen.
#
# Behavior:
#   - All system paths and toggles are defined at the top
#   - You can enable/disable each modification individually
#   - Creates .bak backups before modifying any file
#   - Requires sudo
#   - Exits gracefully if a file or directory is missing
#   - Does NOT reboot automatically
#
# ---------------------------------------------------------------------------

set -euo pipefail

# =============================================================================
# CONFIGURATION TOGGLES (set true/false to enable/disable each modification)
# =============================================================================

MODIFY_CMDLINE=true      # Disable console blanking (consoleblank=0)
MODIFY_UDEV=true         # Block kernel backlight "change" events
MODIFY_X11=true          # Disable X11 DPMS + blanking
MODIFY_LIGHTDM=true      # Disable LightDM DPMS wakeups
MODIFY_LOGIND=true       # Disable systemd-logind wake triggers

# =============================================================================
# FILE PATHS (all full paths defined here)
# =============================================================================

CMDLINE="/boot/cmdline.txt"
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

echo "Applying screen-control configuration for Bullseye..."
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

    if [ ! -f "$CMDLINE" ]; then
        echo "ERROR: $CMDLINE not found. Skipping consoleblank modification."
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
        echo "WARNING: X11 directory not found: $X11_CONF_DIR"
        echo "Skipping X11 DPMS disable (system may be console-only or Wayland)."
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
        echo "Skipping LightDM DPMS disable."
        echo
    else
        backup_file "$LIGHTDM_CONF"

        # Ensure [Seat:*] section exists
        if ! grep -q "^

\[Seat:\*\]

" "$LIGHTDM_CONF"; then
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
        sed -i '/HandleSuspendKey=/d' "$LOGIND_CONF"
        sed -i '/HandleHibernateKey=/d' "$LOGIND_CONF"
        sed -i '/HandlePowerKey=/d' "$LOGIND_CONF"

        cat >> "$LOGIND_CONF" <<'EOF'
HandleLidSwitch=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
HandlePowerKey=ignore
EOF

        echo "logind wake triggers disabled."
        echo
    fi
else
    echo "[LOGIND] Skipped (toggle disabled)."
    echo
fi

# =============================================================================
# Final message
# =============================================================================

echo "-------------------------------------------------------------------"
echo "Screen-control configuration applied."
echo "Backups created for all modified files (.bak)."
echo
echo "IMPORTANT:"
echo "  • Reboot is required for all changes to take effect."
echo "  • After reboot, ONLY your blank_console.sh script will control"
echo "    the screen. No auto-wake, no auto-dim, no auto-blank."
echo "-------------------------------------------------------------------"
echo
echo "Done."
