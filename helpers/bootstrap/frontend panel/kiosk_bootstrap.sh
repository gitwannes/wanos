#!/usr/bin/env bash
# ==============================================================================
# Kiosk Bootstrap: Full System Setup (Raspberry Pi OS Buster / Debian 10)
# (Note: Buster is needed for FKMS support, this was removed from later versions.)
# Goal: kiosk-mode touch-screen frontend
# Target: Raspberry Pi 3 Model B Rev 1.2
#         + Waveshare 4.3" DSI IPS (800x480)
#         + ADS7846 resistive touchscreen on SPI0.1 (GPIO 25 interrupt)
#
# Display stack : vc4-fkms-v3d (legacy FKMS, required for this DSI screen on Buster)
# Compositor    : Weston (drm backend via weston-launch)
# Browser       : Chromium 92+ (native Wayland, --ozone-platform=wayland)
# Touch input   : ADS7846 via libinput inside Weston (no X11 input drivers needed)
# Idle blanking : python3-evdev monitors ADS7846 evdev, blanks after 10 min idle
#
# Run as root or with sudo: sudo ./kiosk_bootstrap.sh
#
# Requires a .env file in the same directory as this script, containing:
#   KIOSK_USER=wanospanel
#   BACKEND_IP=10.32.251.30
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Pre-flight checks and environment
# ------------------------------------------------------------------------------

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with root privileges (sudo)." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE" >&2
    echo "Create it with the following keys:" >&2
    echo "  KIOSK_USER=<username>" >&2
    echo "  BACKEND_IP=0.0.0.0" >&2
    exit 1
fi

# Load the .env file into the current shell environment
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

# Validate required keys
MISSING=()
[ -z "${BACKEND_IP:-}" ] && MISSING+=("BACKEND_IP")
[ -z "${KIOSK_USER:-}" ] && MISSING+=("KIOSK_USER")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Error: The following required keys are missing from .env:" >&2
    for key in "${MISSING[@]}"; do
        echo "  - $key" >&2
    done
    exit 1
fi

# Derive home path from KIOSK_USER
KIOSK_HOME="/home/${KIOSK_USER}"
KIOSK_DIR="${KIOSK_HOME}/kiosk"
DASHBOARD_URL="http://${BACKEND_IP}:8000/kiosk.html"

echo "=========================================="
echo " Starting Kiosk Bootstrap Setup (Buster)..."
echo "=========================================="
echo " Kiosk user : ${KIOSK_USER}"
echo " Kiosk home : ${KIOSK_HOME}"
echo " Backend IP : ${BACKEND_IP}"
echo " Dashboard  : ${DASHBOARD_URL}"
echo "=========================================="

# ------------------------------------------------------------------------------
# 0. Ensure apt sources point to legacy raspbian archive for Buster
# ------------------------------------------------------------------------------

echo "[0/9] Ensuring apt sources include legacy raspbian for Buster..."

# Replace the default raspbian archive line with the legacy HTTPS mirror for Buster.
# This ensures packages (weston, chromium, etc.) remain available for Buster.
if ! grep -q "^deb https://legacy.raspbian.org/raspbian/ buster main contrib non-free rpi" /etc/apt/sources.list 2>/dev/null; then
    # Comment out the old line(s) referencing raspbian.raspberrypi.org to avoid duplicates.
    sed -i.bak -E 's|^deb http://raspbian.raspberrypi.org/raspbian/ buster main contrib non-free rpi|# &|g' /etc/apt/sources.list || true
    # Append the legacy line if not present
    echo "deb https://legacy.raspbian.org/raspbian/ buster main contrib non-free rpi" >> /etc/apt/sources.list
fi

# ------------------------------------------------------------------------------
# 1. Update system and install core kiosk tools
# ------------------------------------------------------------------------------

echo "[1/9] Installing kiosk dependencies (Weston + Chromium + evdev)..."
apt-get update && apt-get upgrade -y

# Package notes (Buster-specific):
#   weston            : Wayland compositor; uses drm backend via weston-launch
#   weston-launch     : setuid-root launcher; grants DRM/input seat access to
#                       non-root user without a TTY login session
#   chromium-browser  : version 92 from RPi archive; supports --ozone-platform=wayland
#   python3-evdev     : used by the idle blanking monitor to read ADS7846 touch events
#   libinput-tools    : provides `libinput debug-events` for touch diagnostics
#   iw                : used to disable Wi-Fi power save
#   logrotate         : log rotation for kiosk and system logs
apt-get install -y \
    weston \
    chromium-browser \
    python3-evdev \
    libinput-tools \
    vim \
    curl \
    git \
    udev \
    iw \
    logrotate

# Ensure the kiosk user exists; create if missing.
if ! id -u "$KIOSK_USER" &>/dev/null; then
    echo "Creating user $KIOSK_USER ..."
    useradd -m -s /bin/bash "$KIOSK_USER"
fi

# Add kiosk user to the groups required for Weston DRM + input seat access:
#   video  : DRM device access (/dev/dri/*)
#   input  : evdev device access (/dev/input/event*)
#   tty    : required for weston-launch to open a VT
#   render : GPU render node access (/dev/dri/renderD*)
usermod -aG video,input,tty,render "$KIOSK_USER"

# ------------------------------------------------------------------------------
# 2. Hardware interfaces (/boot/config.txt + cmdline.txt)
# ------------------------------------------------------------------------------

echo "[2/9] Configuring DSI hardware overlays for Waveshare 4.3\" (FKMS + ADS7846)..."

BOOT_CONFIG="/boot/config.txt"
CMDLINE="/boot/cmdline.txt"

# Remove any conflicting or legacy overlay/param lines before appending clean config.
# This makes the script safe to re-run without duplicating entries.
sed -i '/^hdmi_force_hotplug/d'          "$BOOT_CONFIG" || true
sed -i '/^hdmi_group/d'                  "$BOOT_CONFIG" || true
sed -i '/^hdmi_mode/d'                   "$BOOT_CONFIG" || true
sed -i '/^hdmi_cvt/d'                    "$BOOT_CONFIG" || true
sed -i '/^hdmi_drive/d'                  "$BOOT_CONFIG" || true
sed -i '/^enable_uart/d'                 "$BOOT_CONFIG" || true
sed -i '/^dtparam=audio/d'               "$BOOT_CONFIG" || true
sed -i '/^dtparam=i2c_arm/d'             "$BOOT_CONFIG" || true
sed -i '/^dtparam=spi/d'                 "$BOOT_CONFIG" || true
sed -i '/^display_rotate/d'              "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=vc4-kms-v3d/d'       "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=vc4-kms-dsi-7inch/d' "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=vc4-fkms-v3d/d'      "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=WS_4_3inch_DSI/d'    "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=ft5406/d'            "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=disable-bt/d'        "$BOOT_CONFIG" || true
sed -i '/^dtoverlay=ads7846/d'           "$BOOT_CONFIG" || true

# Append the correct overlay configuration for this hardware:
#
#   dtparam=audio=off       : no audio hardware in this kiosk setup
#   dtparam=i2c_arm=on      : required for DSI display control/init over I2C
#   dtparam=spi=on          : enables SPI bus; required before ads7846 can claim spi0.1
#   enable_uart=1           : disables BT (reclaims HW UART on Pi 3) + enables serial
#                             console on GPIO 14/15 for SSH-less boot debugging
#   dtoverlay=disable-bt    : disables Bluetooth at firmware level (Pi 3 specific;
#                             frees the hardware UART used by enable_uart=1)
#   dtoverlay=vc4-fkms-v3d  : FKMS display driver; required for this DSI screen on
#                             Buster. Bookworm removed FKMS support. Do NOT replace
#                             with vc4-kms-v3d (full KMS) — incompatible with this
#                             Waveshare DSI screen on Buster.
#   dtoverlay=ads7846,...   : resistive touch controller on SPI0.1
#     cs=1                  : chip select 1 (spi0.1)
#     penirq=25             : BCM GPIO 25 is the pen-down interrupt (NOT irq number 166;
#                             irq 166 is the kernel virtual IRQ assigned to GPIO 25)
#     penirq_pull=2         : pull-up on the interrupt pin
#     speed=50000           : SPI clock speed in Hz
#     keep_vref_on=0        : differential mode (correct for resistive matrix)
#     swapxy=0              : no axis swap (calibrated via libinput matrix instead)
#     pmax=255              : max pressure value
#     xohms=150             : X-plate resistance in ohms (panel-specific)
#     xmin/xmax/ymin/ymax   : raw ADC range limits for this panel
cat << 'EOF' >> "$BOOT_CONFIG"

# --- Kiosk Display Hardware Config (Buster + FKMS + Waveshare 4.3" DSI + ADS7846) ---
dtparam=audio=off
dtparam=i2c_arm=on
dtparam=spi=on
enable_uart=1
dtoverlay=disable-bt
dtoverlay=vc4-fkms-v3d
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=50000,keep_vref_on=0,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900
EOF

# Prevent the TTY from blanking beneath Weston (kernel-level console blanking)
if [ -f "$CMDLINE" ] && ! grep -q "consoleblank=0" "$CMDLINE"; then
    sed -i 's/$/ consoleblank=0/' "$CMDLINE"
fi

# Disable Bluetooth UART service — BT is disabled via dtoverlay=disable-bt above.
# Masking prevents it from being accidentally started by another dependency.
systemctl disable hciuart 2>/dev/null || true
systemctl mask hciuart 2>/dev/null || true

# Disable getty on tty1 so Weston (via weston-launch) can exclusively own the VT.
# Weston requires undivided control of the VT it runs on; a getty competing for
# tty1 will cause Weston to fail to acquire the DRM master role.
systemctl disable getty@tty1.service 2>/dev/null || true
systemctl mask getty@tty1.service 2>/dev/null || true

# ------------------------------------------------------------------------------
# 3. Wi-Fi power management override
# ------------------------------------------------------------------------------

echo "[3/9] Disabling Wi-Fi power save..."

# Wi-Fi power save causes the adapter to go into a low-power sleep state between
# packets, introducing latency spikes that break the backend connectivity check
# and SSE streaming. This service disables it on every boot after the interface
# is available.
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

# ------------------------------------------------------------------------------
# 4. Touchscreen udev rules and backlight permissions
# ------------------------------------------------------------------------------

echo "[4/9] Setting touch udev rules and backlight permissions..."

# Allow backlight control from userspace without sudo.
# The rpi_backlight sysfs node is created by the vc4-fkms-v3d + DSI firmware path.
# bl_power: 0 = on, 1 = off (inverted logic — used by the idle blanking monitor)
# Use permissive mode for simplicity; consider a group-based approach for stricter security.
cat << 'EOF' > /etc/udev/rules.d/99-backlight.rules
SUBSYSTEM=="backlight", RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"
EOF

# Map the ADS7846 touch input device to the DSI-1 Wayland output so Weston
# routes touch events to the correct display.
# ATTRS{name} must match exactly what the kernel reports in /proc/bus/input/devices
# and dmesg: "ADS7846 Touchscreen"
cat << 'EOF' > /etc/udev/rules.d/99-waveshare-touch.rules
KERNEL=="event[0-9]*", SUBSYSTEM=="input", ATTRS{name}=="ADS7846 Touchscreen", ENV{WL_OUTPUT}="DSI-1"
EOF

udevadm control --reload-rules && udevadm trigger

# ------------------------------------------------------------------------------
# 5. Environment & aliases
# ------------------------------------------------------------------------------

echo "[5/9] Configuring user bash profiles and kiosk directory..."

# Ensure kiosk home exists and create kiosk directory
mkdir -p "$KIOSK_DIR"
chown -R "$KIOSK_USER:$KIOSK_USER" "$KIOSK_DIR"

# --- Interactive shell customizations for the admin/SSH user ---
# By default, set ADMIN_USER to 'wannes' unless overridden in .env.
# This user receives console aliases and interactive tweaks; the kiosk user
# remains headless and receives no interactive console config.
ADMIN_USER="${ADMIN_USER:-wannes}"
ADMIN_HOME="/home/${ADMIN_USER}"
ADMIN_BASHRC="${ADMIN_HOME}/.bashrc"

# Ensure admin home exists (idempotent) and is owned by the admin user.
if [ ! -d "${ADMIN_HOME}" ]; then
    mkdir -p "${ADMIN_HOME}"
    chown "${ADMIN_USER}:${ADMIN_USER}" "${ADMIN_HOME}" || true
fi

# Append WanOS aliases to the admin user's .bashrc if not already present.
if [ ! -f "${ADMIN_BASHRC}" ]; then
    touch "${ADMIN_BASHRC}"
    chown "${ADMIN_USER}:${ADMIN_USER}" "${ADMIN_BASHRC}" || true
fi

if ! grep -q "WanOS Custom Aliases" "${ADMIN_BASHRC}" 2>/dev/null; then
    cat << 'EOF' >> "${ADMIN_BASHRC}"
# --- WanOS Custom Aliases ---
alias ls='ls -lh --color=auto'
EOF
    chown "${ADMIN_USER}:${ADMIN_USER}" "${ADMIN_BASHRC}" || true
fi

# ------------------------------------------------------------------------------
# 6. Install Log2Ram
# ------------------------------------------------------------------------------

echo "[6/9] Installing Log2Ram..."

# Log2Ram moves /var/log to a tmpfs RAM mount and syncs to SD card periodically.
# This dramatically reduces SD card write wear from continuous log I/O.
if ! command -v log2ram &>/dev/null; then
    # Read the OS codename from /etc/os-release.
    # VERSION_CODENAME may not be set on all minimal Buster images, so we
    # extract it explicitly and fall back to "buster" as a safety net.
    . /etc/os-release
    CODENAME="${VERSION_CODENAME:-}"
    if [ -z "$CODENAME" ]; then
        CODENAME=$(grep "^VERSION_CODENAME" /etc/os-release | cut -d= -f2 | tr -d '"')
    fi
    [ -z "$CODENAME" ] && CODENAME="buster"

    # Verify the azlux repo is reachable before attempting to add it.
    # Buster is EOL; the repo may drop support. Fail clearly rather than
    # leaving a broken apt source entry.
    if ! curl -sf --head "http://packages.azlux.fr/debian/dists/${CODENAME}/" > /dev/null; then
        echo "Warning: azlux repo not reachable for '${CODENAME}'. Skipping Log2Ram install." >&2
    else
        wget -O /usr/share/keyrings/azlux-archive-keyring.gpg https://azlux.fr/repo.gpg
        echo "deb [signed-by=/usr/share/keyrings/azlux-archive-keyring.gpg] http://packages.azlux.fr/debian/ ${CODENAME} main" \
            > /etc/apt/sources.list.d/azlux.list
        apt-get update
        apt-get install -y log2ram
        # 128M is sufficient for Buster kiosk log volume; default (40M) can fill
        # up quickly if Chromium or Weston log verbosely.
        sed -i 's/^SIZE=.*/SIZE=128M/' /etc/log2ram.conf
    fi
else
    echo "Log2Ram is already installed. Skipping."
fi

# ------------------------------------------------------------------------------
# 7. Wayland kiosk application (Weston + Chromium native Wayland)
# ------------------------------------------------------------------------------

echo "[7/9] Configuring Weston-based kiosk and Chromium launcher..."

# Create weston config for the kiosk user
mkdir -p "${KIOSK_HOME}/.config"
cat << 'EOF' > "${KIOSK_HOME}/.config/weston.ini"
[core]
# drm-backend.so: renders directly to DRM/KMS framebuffer (FKMS vc4 device).
# This is the correct backend for a headless Pi kiosk with no display manager.
backend=drm-backend.so

# idle-time=0 disables Weston's own built-in idle/DPMS handling.
# Screen blanking is managed separately by the python3-evdev idle monitor,
# which reads ADS7846 touch events and controls rpi_backlight/bl_power directly.
idle-time=0

[output]
# DSI-1 is the DRM connector name assigned by vc4-fkms-v3d for the DSI port.
name=DSI-1
mode=800x480

# NOTE: We intentionally do NOT autolaunch Chromium from Weston here.
# Chromium will be launched by a supervised systemd --user unit (chromium-kiosk.service)
# to provide robust restart behavior and crash recovery.
EOF

chown -R "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.config"

# --- idle_monitor.py (resolves device by name) ---
cat << 'EOF' > "${KIOSK_DIR}/idle_monitor.py"
#!/usr/bin/env python3
"""
ADS7846 idle blanking monitor for WanOS kiosk (Buster).

Finds the input device named "ADS7846 Touchscreen" dynamically and watches it
for EV_ABS touch activity. Blanks the rpi_backlight after IDLE_SECONDS of inactivity.
Unblanks immediately on the next touch event.

bl_power logic (inverted): write 0 to turn ON, write 1 to turn OFF.
"""

import evdev
import time
import os
import sys

TOUCH_DEVICE_NAME = "ADS7846 Touchscreen"
BACKLIGHT_PATH = "/sys/class/backlight/rpi_backlight/bl_power"
IDLE_SECONDS = 600   # 10 minutes

def find_touch_device(name=TOUCH_DEVICE_NAME):
    """Return the device path for the input device with the given name."""
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
            if d.name == name:
                return path
        except Exception:
            continue
    raise FileNotFoundError(f"Input device named '{name}' not found")

def set_backlight(on: bool):
    """Write to bl_power. Silently ignore if path is not available."""
    try:
        with open(BACKLIGHT_PATH, "w") as f:
            # bl_power is inverted: 0 = ON, 1 = OFF
            f.write("0" if on else "1")
    except OSError:
        pass

def main():
    try:
        device_path = find_touch_device()
    except FileNotFoundError as e:
        print(f"idle_monitor: {e}", flush=True)
        return

    try:
        device = evdev.InputDevice(device_path)
    except (FileNotFoundError, PermissionError) as e:
        print(f"idle_monitor: cannot open {device_path}: {e}", flush=True)
        return

    print(f"idle_monitor: watching {device.name} at {device.path} — blanking after {IDLE_SECONDS}s idle", flush=True)

    last_activity = time.monotonic()
    blanked = False
    set_backlight(True)  # Ensure backlight is ON at startup

    for event in device.read_loop():
        now = time.monotonic()

        # Any EV_ABS event (touch contact) counts as activity
        if event.type == evdev.ecodes.EV_ABS:
            last_activity = now
            if blanked:
                # Unblank on first touch after idle
                set_backlight(True)
                blanked = False

        # Check idle timeout on every event (including EV_SYN sync events)
        if not blanked and (now - last_activity) >= IDLE_SECONDS:
            set_backlight(False)
            blanked = True

if __name__ == "__main__":
    main()
EOF

chmod +x "${KIOSK_DIR}/idle_monitor.py"
chown "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_DIR}/idle_monitor.py"

# --- systemd user service for idle monitor ---
USER_SYSTEMD_DIR="${KIOSK_HOME}/.config/systemd/user"
mkdir -p "${USER_SYSTEMD_DIR}"
cat << EOF > "${USER_SYSTEMD_DIR}/idle-monitor.service"
[Unit]
Description=WanOS ADS7846 Idle Backlight Monitor
After=network.target

[Service]
Type=simple
WorkingDirectory=${KIOSK_DIR}
ExecStart=/usr/bin/python3 ${KIOSK_DIR}/idle_monitor.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

chown -R "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.config/systemd"

# Enable lingering so the kiosk user's systemd --user instance runs at boot.
# This allows user services to be started even when the user is not logged in.
loginctl enable-linger "${KIOSK_USER}"

# ------------------------------------------------------------------------------
# Ensure per-user runtime directory exists and is owned correctly
# (prevents pam_systemd failures when starting user@<UID>.service)
# ------------------------------------------------------------------------------

# Create /run/user/<UID> and set ownership/permissions before invoking any
# systemctl --user commands from the root provisioning script. This is
# idempotent and safe to run multiple times.
KIOSK_UID="$(id -u "${KIOSK_USER}")"
KIOSK_GID="$(id -g "${KIOSK_USER}")"
RUNTIME_DIR="/run/user/${KIOSK_UID}"
if [ ! -d "${RUNTIME_DIR}" ]; then
    mkdir -p "${RUNTIME_DIR}"
fi
# Ensure correct ownership and permissions so pam_systemd will set XDG_RUNTIME_DIR
chown "${KIOSK_UID}:${KIOSK_GID}" "${RUNTIME_DIR}"
chmod 700 "${RUNTIME_DIR}"

# ------------------------------------------------------------------------------
# Ensure the persistent per-user systemd manager is running for the kiosk user
# This avoids dbus activation races where org.freedesktop.systemd1 fails to spawn
# when systemctl --user is invoked from a transient session.
# ------------------------------------------------------------------------------

if ! systemctl is-active --quiet "user@${KIOSK_UID}.service"; then
    # Start the user manager from the system instance. This is idempotent.
    systemctl start "user@${KIOSK_UID}.service" || true

    # Wait briefly for the user manager to become active (timeout ~10s)
    for _ in $(seq 1 20); do
        if systemctl is-active --quiet "user@${KIOSK_UID}.service"; then
            break
        fi
        sleep 0.5
    done
fi

# Optional: show status for provisioning logs (harmless if it fails)
systemctl status "user@${KIOSK_UID}.service" --no-pager || true

# ------------------------------------------------------------------------------
# Reload and enable the idle-monitor user service as the kiosk user.
# Use dbus-run-session so systemctl --user works during provisioning even if
# the persistent user manager is not yet active. Because we started the
# persistent user manager above, dbus activation races are avoided.
# ------------------------------------------------------------------------------

runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=/run/user/${KIOSK_UID} systemctl --user daemon-reload || true"
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=/run/user/${KIOSK_UID} systemctl --user enable --now idle-monitor.service || true"

# ------------------------------------------------------------------------------
# 8. chromium-kiosk.sh (user launcher) and user unit for Chromium
# ------------------------------------------------------------------------------

echo "[8/9] Installing chromium-kiosk launcher and user unit (systemd --user)..."

# Write the launcher script that detects the Wayland socket and exports WAYLAND_DISPLAY.
cat > "${KIOSK_DIR}/chromium-kiosk.sh" <<'CHROMIUM_SH'
#!/bin/bash
set -euo pipefail

# Launcher for Chromium under systemd --user.
# Waits for a wayland-* socket in XDG_RUNTIME_DIR, exports WAYLAND_DISPLAY,
# optionally waits for the backend, then execs chromium-browser so the env is inherited.

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
echo "chromium-kiosk: runtime dir=${RUNTIME_DIR}"

# Wait for Wayland socket (up to ~100s by default)
RETRIES=0
WAYLAND_SOCKET=""
until [ -n "$WAYLAND_SOCKET" ] && [ -S "$WAYLAND_SOCKET" ]; do
    sleep 0.5
    RETRIES=$((RETRIES + 1))
    WAYLAND_SOCKET=$(ls "${RUNTIME_DIR}"/wayland-* 2>/dev/null | head -n1 || true)
    if [ "$RETRIES" -ge 200 ]; then
        echo "chromium-kiosk: Wayland socket not found after $((RETRIES*0.5))s" >&2
        exit 1
    fi
done

export WAYLAND_DISPLAY="$(basename "$WAYLAND_SOCKET")"
echo "chromium-kiosk: using WAYLAND_DISPLAY=${WAYLAND_DISPLAY}"

# Small settle delay to let compositor finish initialisation
sleep 0.5

# Optional backend reachability check: wait for the backend URL before loading remote page.
# If you prefer Chromium to show a local splash or its offline page, comment out this block.
RETRIES=0
until curl -sf -o /dev/null "http://BACKEND_IP_PLACEHOLDER:8000/kiosk.html"; do
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ "$RETRIES" -ge 150 ]; then
        echo "chromium-kiosk: backend unreachable after 5 min — starting Chromium anyway." >&2
        break
    fi
done

# Exec Chromium so it inherits XDG_RUNTIME_DIR and WAYLAND_DISPLAY
exec /usr/bin/chromium-browser \
    --ozone-platform=wayland \
    --enable-features=UseOzonePlatform \
    --kiosk \
    --no-first-run \
    --disable-infobars \
    --check-for-update-interval=31536000 \
    --touch-events=enabled \
    --no-sandbox \
    "http://BACKEND_IP_PLACEHOLDER:8000/kiosk.html"
CHROMIUM_SH

# Substitute BACKEND_IP into the launcher script
sed -i "s|BACKEND_IP_PLACEHOLDER|${BACKEND_IP}|g" "${KIOSK_DIR}/chromium-kiosk.sh"
chmod +x "${KIOSK_DIR}/chromium-kiosk.sh"
chown "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_DIR}/chromium-kiosk.sh"

# Create the systemd --user unit for Chromium (runs under kiosk user)
USER_CHROME_UNIT="${KIOSK_HOME}/.config/systemd/user/chromium-kiosk.service"
cat > "${USER_CHROME_UNIT}" <<'UNIT_EOF'
[Unit]
Description=Chromium Kiosk (Wayland) - user unit
StartLimitIntervalSec=600
StartLimitBurst=10

[Service]
Type=simple
# Run the launcher script; systemd user instance sets XDG_RUNTIME_DIR (%t).
ExecStart=/usr/bin/env XDG_RUNTIME_DIR=%t /home/KIOSK_USER_PLACEHOLDER/kiosk/chromium-kiosk.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
UNIT_EOF

# Substitute kiosk user into the unit file
sed -i "s|KIOSK_USER_PLACEHOLDER|${KIOSK_USER}|g" "${USER_CHROME_UNIT}"
chown "${KIOSK_USER}:${KIOSK_USER}" "${USER_CHROME_UNIT}"

# Ensure the user systemd directory ownership is correct
chown -R "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}/.config/systemd"

# Enable lingering so the kiosk user's systemd --user instance runs at boot (already done above)
loginctl enable-linger "${KIOSK_USER}"

# Before invoking systemctl --user, ensure the persistent user manager is active.
# If it is not active, start it from the system instance and wait (idempotent).
if ! systemctl is-active --quiet "user@${KIOSK_UID}.service"; then
    systemctl start "user@${KIOSK_UID}.service" || true
    for _ in $(seq 1 20); do
        if systemctl is-active --quiet "user@${KIOSK_UID}.service"; then
            break
        fi
        sleep 0.5
    done
fi

# Reload user daemon and enable/start the chromium user unit as the kiosk user.
# Use dbus-run-session so systemctl --user works during provisioning even if
# the persistent user manager is not yet active. Because we ensured the user
# manager is running above, dbus activation races are avoided.
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=/run/user/${KIOSK_UID} systemctl --user daemon-reload || true"
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=/run/user/${KIOSK_UID} systemctl --user enable --now chromium-kiosk.service || true"

echo "[+] chromium-kiosk user unit installed and started (user: ${KIOSK_USER})"

# ------------------------------------------------------------------------------
# 9. start_kiosk.sh (system-level wrapper) and weston.service
# ------------------------------------------------------------------------------

echo "[9/9] Creating start_kiosk.sh (wrapper for weston-launch) and weston.service..."

# start_kiosk.sh: entry point used by the weston.service unit.
# Sequence:
#   1. Ensure XDG_RUNTIME_DIR is set for the kiosk user
#   2. Exec weston-launch -u ${KIOSK_USER} so weston-launch drops to kiosk user
tee "${KIOSK_DIR}/start_kiosk.sh" > /dev/null << 'START_EOF'
#!/bin/bash
set -euo pipefail

# Ensure XDG_RUNTIME_DIR is set for the kiosk user (systemd user normally sets this,
# but for system-level weston-launch we set it explicitly to the user's runtime dir).
# Create and chown the runtime dir so PAM/systemd can set XDG_RUNTIME_DIR correctly
# when weston-launch drops privileges to the kiosk user.

# Resolve kiosk user's UID and ensure a valid XDG_RUNTIME_DIR variable name
KIOSK_UID="$(id -u wanospanel 2>/dev/null || echo 1000)"
export XDG_RUNTIME_DIR="/run/user/${KIOSK_UID}"
# Create and secure the runtime dir so PAM/systemd and weston-launch can use it
mkdir -p "${XDG_RUNTIME_DIR}"
chown "${KIOSK_UID}:${KIOSK_UID}" "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}"

# Start weston-launch and drop to kiosk user (-u). weston-launch is setuid-root.
exec /usr/bin/weston-launch -u KIOSK_USER_PLACEHOLDER -- --backend=drm-backend.so --tty=1
START_EOF

# Substitute kiosk user into the start_kiosk.sh
sed -i "s|KIOSK_USER_PLACEHOLDER|${KIOSK_USER}|g" "${KIOSK_DIR}/start_kiosk.sh"
# Substitute the numeric UID into the value placeholder (not into a variable name)
sed -i "s|KIOSK_UID_VALUE_PLACEHOLDER|$(id -u ${KIOSK_USER})|g" "${KIOSK_DIR}/start_kiosk.sh"

chmod +x "${KIOSK_DIR}/start_kiosk.sh"
chown "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_DIR}/start_kiosk.sh"

# Create weston.service (system-level) that runs the start_kiosk.sh wrapper.
cat > /etc/systemd/system/weston.service <<'WESTON_UNIT'
[Unit]
Description=Weston compositor for kiosk
After=network.target
StartLimitIntervalSec=600
StartLimitBurst=3

[Service]
User=root
Group=root
Type=simple
# ExecStart runs the wrapper which calls weston-launch -u <kiosk user>
ExecStart=KIOSK_DIR_PLACEHOLDER/start_kiosk.sh
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
WESTON_UNIT

# Substitute the kiosk directory path into the weston unit
sed -i "s|KIOSK_DIR_PLACEHOLDER|${KIOSK_DIR}|g" /etc/systemd/system/weston.service

# Enable and start weston.service (system-level)
systemctl daemon-reload
systemctl enable --now weston.service

# ------------------------------------------------------------------------------
# Chromium version check and warning
# ------------------------------------------------------------------------------

echo "[INFO] Checking chromium-browser availability and version..."
if command -v chromium-browser &>/dev/null; then
    CHROME_VER_FULL="$(chromium-browser --version 2>/dev/null || true)"
    # Example output: "Chromium 92.0.4515.159"
    CHROME_MAJOR="$(echo "$CHROME_VER_FULL" | awk '{print $2}' | cut -d. -f1 || true)"
    if [ -n "$CHROME_MAJOR" ] && [ "$CHROME_MAJOR" -lt 92 ]; then
        echo "Warning: chromium-browser version appears older than v92: ${CHROME_VER_FULL}" >&2
        echo "Chromium v92+ is recommended for native Wayland (--ozone-platform=wayland) on Buster."
    else
        echo "Found chromium-browser: ${CHROME_VER_FULL}"
    fi
else
    echo "Warning: chromium-browser not found. The kiosk requires Chromium (v92+ recommended)." >&2
fi

# ------------------------------------------------------------------------------
# First-boot hardware detection logging
# ------------------------------------------------------------------------------

KIOSK_HW_LOG="/var/log/kiosk-hw-detect.log"
FIRSTBOOT_MARKER="/var/lib/kiosk-firstboot-done"

if [ ! -f "${FIRSTBOOT_MARKER}" ]; then
    echo "[INFO] First boot detected: capturing hardware detection info to ${KIOSK_HW_LOG} ..."
    {
        echo "=== dmesg | grep -i ads7846 ==="
        dmesg | grep -i ads7846 || true
        echo ""
        echo "=== /proc/bus/input/devices ==="
        cat /proc/bus/input/devices || true
    } > "${KIOSK_HW_LOG}" 2>&1 || true
    touch "${FIRSTBOOT_MARKER}"
    chmod 644 "${KIOSK_HW_LOG}" || true
    echo "[INFO] Hardware detection log written. Inspect ${KIOSK_HW_LOG} for device names and ADC ranges."
fi

# ------------------------------------------------------------------------------
# Final ownership and completion message
# ------------------------------------------------------------------------------

# Ensure kiosk directory and config files are owned by the kiosk user
chown -R "${KIOSK_USER}:${KIOSK_USER}" "${KIOSK_HOME}"

echo "================================================================"
echo " [KIOSK BOOTSTRAP COMPLETE - BUSTER + WESTON + CHROMIUM WAYLAND]"
echo "================================================================"
echo " Kiosk URL   : ${DASHBOARD_URL}"
echo " Kiosk user  : ${KIOSK_USER}"
echo " Kiosk home  : ${KIOSK_HOME}"
echo " Next step:"
echo "   sudo reboot"
echo "================================================================"
