#!/usr/bin/env bash
# discover_network_manager.sh
# Detect which network manager is active on a Raspberry Pi / Debian system.
# Prints raw outputs (grep'd for useful info) and a human-readable summary.

set -euo pipefail
IFS=$'\n\t'

echo
echo "=== Network Manager Discovery Report ==="
echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%SZ (UTC)")"
echo "Host: $(hostname) / User: $(whoami)"
echo "----------------------------------------"
echo

# Helper to print section headers
section() {
  printf "\n--- %s ---\n" "$1"
}

# 1) Interfaces, addresses, routes
section "IP addresses (ip addr show)"
ip addr show

section "Routing table (ip route show)"
ip route show

# 2) Service checks
section "Service status (systemctl)"
echo "NetworkManager: $(systemctl is-active NetworkManager 2>/dev/null || echo inactive)"
echo "systemd-networkd: $(systemctl is-active systemd-networkd 2>/dev/null || echo inactive)"
echo "dhcpcd: $(systemctl is-active dhcpcd 2>/dev/null || echo inactive)"
echo "networking (ifupdown): $(systemctl is-active networking 2>/dev/null || echo inactive)"

# 3) Which processes are running (clean, no grep self-match)
section "Running network-related processes (pgrep -a)"
pgrep -a dhcpcd 2>/dev/null || echo "no dhcpcd process found"
pgrep -a dhclient 2>/dev/null || echo "no dhclient process found"
pgrep -a NetworkManager 2>/dev/null || echo "no NetworkManager process found"
pgrep -a systemd-networkd 2>/dev/null || echo "no systemd-networkd process found"

# 4) dhcpcd config presence and head
section "dhcpcd config (/etc/dhcpcd.conf) (exists? and head)"
if [ -f /etc/dhcpcd.conf ]; then
  echo "/etc/dhcpcd.conf exists. Showing first 80 lines:"
  sed -n '1,80p' /etc/dhcpcd.conf || true
else
  echo "/etc/dhcpcd.conf: NOT FOUND"
fi

# 5) Classic Debian ifupdown file
section "/etc/network/interfaces (exists? and content head)"
if [ -f /etc/network/interfaces ]; then
  echo "/etc/network/interfaces exists. Showing first 80 lines:"
  sed -n '1,80p' /etc/network/interfaces || true
else
  echo "/etc/network/interfaces: NOT FOUND"
fi

# 6) NetworkManager CLI (if available)
section "NetworkManager status (nmcli) - only if nmcli is installed"
if command -v nmcli >/dev/null 2>&1; then
  nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status || true
else
  echo "nmcli: not installed"
fi

# 7) systemd-networkd info (if available)
section "systemd-networkd (networkctl) - only if networkctl is installed"
if command -v networkctl >/dev/null 2>&1; then
  networkctl list || true
else
  echo "networkctl: not installed"
fi

# 8) DHCP lease files for systemd-networkd (if any)
section "systemd-networkd DHCP leases (if any)"
if [ -d /run/systemd/netif/leases ]; then
  ls -l /run/systemd/netif/leases || echo "no lease files"
  sed -n '1,120p' /run/systemd/netif/leases/* 2>/dev/null || true
else
  echo "/run/systemd/netif/leases: not present"
fi

# 9) Check for denyinterfaces in dhcpcd.conf (common when NM manages interfaces)
section "dhcpcd.conf denyinterfaces (if present)"
if [ -f /etc/dhcpcd.conf ]; then
  grep -E '^\s*denyinterfaces' /etc/dhcpcd.conf || echo "no denyinterfaces line found"
fi

# 10) Quick tests: ping broker example (optional)
# You can uncomment and set BROKER_IP to test per-interface reachability.
# BROKER_IP="8.8.8.8"
# section "Ping test via specific interfaces (uncomment and set BROKER_IP to use)"
# ping -I eth0 -c3 $BROKER_IP || true
# ping -I wlan0 -c3 $BROKER_IP || true

# -------------------------
# Human-readable summary
# -------------------------
section "Human-readable summary"

# Determine active flags
nm_active=$(systemctl is-active NetworkManager 2>/dev/null || echo inactive)
sdn_active=$(systemctl is-active systemd-networkd 2>/dev/null || echo inactive)
dhcpcd_active=$(systemctl is-active dhcpcd 2>/dev/null || echo inactive)
ifupdown_exists=0
if [ -f /etc/network/interfaces ]; then
  ifupdown_exists=1
fi

echo "Summary:"
if [ "$dhcpcd_active" = "active" ]; then
  echo "  - dhcpcd is ACTIVE (systemd service state: active)."
else
  echo "  - dhcpcd is NOT active (systemd service state: $dhcpcd_active)."
fi

if [ "$nm_active" = "active" ]; then
  echo "  - NetworkManager is ACTIVE. This may conflict with dhcpcd if both manage the same interfaces."
else
  echo "  - NetworkManager is not active."
fi

if [ "$sdn_active" = "active" ]; then
  echo "  - systemd-networkd is ACTIVE. This may conflict with dhcpcd if both manage the same interfaces."
else
  echo "  - systemd-networkd is not active."
fi

if [ "$ifupdown_exists" -eq 1 ]; then
  echo "  - /etc/network/interfaces exists. If it contains interface definitions, ifupdown may be in use."
else
  echo "  - /etc/network/interfaces not present."
fi

# Final recommendation logic
echo
echo "Recommendation:"
if [ "$dhcpcd_active" = "active" ] && [ "$nm_active" != "active" ] && [ "$sdn_active" != "active" ]; then
  echo "  -> Your system appears to be managed by dhcpcd only. This is the normal Raspberry Pi OS default."
else
  echo "  -> Mixed or multiple managers detected. To avoid conflicts, pick one manager per interface."
  echo "     If you want dhcpcd to manage interfaces and NetworkManager is installed, add 'denyinterfaces <if>'"
  echo "     to /etc/dhcpcd.conf for interfaces you want NM to manage, or disable the other manager."
fi

echo
echo "End of report."
