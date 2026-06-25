# KIOSK Control Cheat Sheet

A single file you can copy to the device (for example `/home/wannes/kiosk-control.md`).  
Replace **`wanospanel`** with your kiosk username if different.

---

## Prerequisites
- Run commands as **root** or prefix with `sudo`.  
- Ensure your `.env` contains `KIOSK_USER` and `BACKEND_IP`.  
- This sheet assumes the kiosk user is **wanospanel**; change `KIOSK_USER` where needed.

---

## Quick variables
```bash
# Edit these if your kiosk user differs
KIOSK_USER=wanospanel
KIOSK_UID=$(id -u "$KIOSK_USER")
RUNTIME_DIR="/run/user/${KIOSK_UID}"
```

---

## Start services now
Ensure runtime dir and per-user manager exist, then start compositor and user units.
```bash
# Start user manager
systemctl start "user@${KIOSK_UID}.service"

# Start system compositor
systemctl start weston.service

# Reload user units and start them under the running user manager
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user daemon-reload || true"
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user start idle-monitor.service chromium-kiosk.service || true"
```

---

## Stop services
Stop user units, compositor, and optionally the per-user manager.
```bash
# Stop user units
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user stop chromium-kiosk.service idle-monitor.service" || true

# Stop compositor
systemctl stop weston.service || true

# Optionally stop per-user manager (system instance)
systemctl stop "user@${KIOSK_UID}.service" || true
```

---

## Enable or disable at boot
Enable so services start automatically after reboot; disable to prevent auto-start.
```bash
# Enable at boot (recommended production flow)
systemctl enable weston.service
loginctl enable-linger "${KIOSK_USER}"
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user enable idle-monitor.service chromium-kiosk.service" || true

# Disable at boot
systemctl disable weston.service
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user disable idle-monitor.service chromium-kiosk.service" || true
loginctl disable-linger "${KIOSK_USER}" || true
```

---

## Status checks
Check compositor, per-user manager, and user units.
```bash
# System compositor
systemctl status weston.service --no-pager

# Per-user manager
systemctl status "user@${KIOSK_UID}.service" --no-pager

# Kiosk user units
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user status chromium-kiosk.service idle-monitor.service --no-pager"
```

Quick combined check:
```bash
systemctl is-active --quiet weston.service && echo "weston: active" || echo "weston: inactive"
systemctl is-active --quiet "user@${KIOSK_UID}.service" && echo "user@UID: active" || echo "user@UID: inactive"
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user is-active chromium-kiosk.service && echo 'chromium-kiosk: active' || echo 'chromium-kiosk: inactive'"
```

---

## View logs and follow live output
System and user journals for debugging.
```bash
# Weston logs (system)
journalctl -u weston.service -n 200 --no-pager
journalctl -u weston.service -f --no-pager

# Per-user manager logs (system journal)
journalctl -u "user@${KIOSK_UID}.service" -n 200 --no-pager

# Chromium user logs (user journal)
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} journalctl --user -u chromium-kiosk.service -n 200 --no-pager"
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} journalctl --user -u chromium-kiosk.service -f --no-pager"

# Idle monitor logs (user journal)
runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} journalctl --user -u idle-monitor.service -n 200 --no-pager"
```

---

## Useful diagnostics
Quick checks to confirm runtime environment and sockets.
```bash
# Wayland socket presence
ls -l "${RUNTIME_DIR}"/wayland-* || echo "No Wayland socket found"

# User bus socket
ls -l "${RUNTIME_DIR}/bus" || echo "User bus socket missing"

# Check XDG_RUNTIME_DIR ownership and permissions
ls -ld "${RUNTIME_DIR}"

# Check Chromium processes and environment (replace <PID> if needed)
ps aux | grep chromium | grep -v grep
# For a running PID:
# tr '\0' '\n' < /proc/<PID>/environ | grep -E 'XDG_RUNTIME_DIR|WAYLAND_DISPLAY'
```

---

## One-line helper to start everything now
Copy‑paste this single line as root to run the full immediate start sequence:
```bash
KIOSK_USER=wanospanel; KIOSK_UID=$(id -u "$KIOSK_USER"); RUNTIME_DIR="/run/user/${KIOSK_UID}"; mkdir -p "${RUNTIME_DIR}"; chown "${KIOSK_UID}:${KIOSK_UID}" "${RUNTIME_DIR}"; chmod 700 "${RUNTIME_DIR}"; systemctl start "user@${KIOSK_UID}.service"; systemctl start weston.service; runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user daemon-reload || true"; runuser -l "${KIOSK_USER}" -c "XDG_RUNTIME_DIR=${RUNTIME_DIR} systemctl --user start idle-monitor.service chromium-kiosk.service || true"
```

---

## Recommended production flow
1. Run the bootstrap script once as root:
```bash
sudo ./kiosk_bootstrap.sh
```
2. Reboot the device:
```bash
sudo reboot
```
After reboot the compositor and user units should start automatically (lingering + enabled units).

---

## Notes and troubleshooting tips
- Prefer **enable + reboot** for predictable startup; starting units immediately during provisioning can race with DBus activation.  
- If a user unit fails, inspect the user journal (see logs section) and confirm the Wayland socket exists.  
- If `user@<UID>.service` is inactive, ensure `/run/user/<UID>` exists and is owned by the kiosk user and that lingering is enabled.

---

Copy this file to the device and keep it with your provisioning artifacts for quick operational reference.
