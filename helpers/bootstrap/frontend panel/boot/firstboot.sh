#!/bin/bash
# /boot/firstboot.sh
set -e

echo "[FIRSTBOOT] Starting initial configuration..."

### --- LOCALE, TIMEZONE, KEYBOARD, WIFI COUNTRY --- ###
raspi-config nonint do_change_locale en_US.UTF-8
raspi-config nonint do_change_timezone Europe/Brussels
raspi-config nonint do_configure_keyboard be
raspi-config nonint do_wifi_country BE

### --- ENABLE SSH --- ###
raspi-config nonint do_ssh 0

### --- CREATE USER 'wannes' --- ###
if ! id wannes >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" wannes
    echo "wannes:changeme" | chpasswd
    usermod -aG sudo wannes
fi

### --- DISABLE PI USER --- ###
if id pi >/dev/null 2>&1; then
    passwd -l pi
fi

### --- CHANGE HOSTNAME --- ###
NEW_HOSTNAME="wanospanel"
CURRENT_HOSTNAME=$(cat /etc/hostname)

if [ "$CURRENT_HOSTNAME" != "$NEW_HOSTNAME" ]; then
    echo "$NEW_HOSTNAME" > /etc/hostname
    sed -i "s/$CURRENT_HOSTNAME/$NEW_HOSTNAME/g" /etc/hosts
fi

### --- CLEANUP --- ###
echo "[FIRSTBOOT] Cleaning up..."
rm -f /etc/systemd/system/firstboot.service
rm -f /boot/firstboot.service
rm -f /boot/firstboot.sh
systemctl daemon-reload

echo "[FIRSTBOOT] Done. Reboot recommended."
