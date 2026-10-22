#!/usr/bin/env bash
# --- file: helpers/bootstrap/backend/wanos_bootstrap_phase2.sh ---
# ==============================================================================
# WanOS Phase 2: Application Setup (venv, RFX udev, wanos.service, nginx refresh)
# Ops7: system python3 is Trixie 3.13 - sync tree via wanos-sync (no Samba)
# Run as user wannes: ./wanos_bootstrap_phase2.sh
# ==============================================================================

set -euo pipefail

if [ "$(id -un)" != "wannes" ]; then
    echo "Error: This script must be run as the user 'wannes'." >&2
    exit 1
fi

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WANNES_HOME="/home/wannes"
APP_DIR="$WANNES_HOME/wanos"
UNIT_DST="/etc/systemd/system/wanos.service"
LE_FULLCHAIN="/etc/letsencrypt/live/app.wanos.be/fullchain.pem"
LE_PRIVKEY="/etc/letsencrypt/live/app.wanos.be/privkey.pem"

wanos_find_bootstrap_file() {
    local name="$1"
    local cand
    for cand in \
        "${SELF_DIR}/${name}" \
        "${APP_DIR}/helpers/bootstrap/backend/${name}" \
        "${WANNES_HOME}/${name}" \
        "./${name}"; do
        if [ -f "${cand}" ]; then
            echo "${cand}"
            return 0
        fi
    done
    return 1
}

# Install systemd unit from bootstrap template (comments with # are OK for systemd)
wanos_install_service() {
    local unit_src
    unit_src="$(wanos_find_bootstrap_file wanos.service)" || {
        echo "ERROR: wanos.service template not found next to this script or under helpers/bootstrap/backend/." >&2
        echo "SCP bootstrap helpers (path segment bootstrap is excluded from wanos-sync mirror)." >&2
        exit 1
    }
    if [ ! -x "${APP_DIR}/wanos_venv/bin/python" ]; then
        echo "ERROR: ${APP_DIR}/wanos_venv/bin/python missing - venv step must succeed first." >&2
        exit 1
    fi
    echo "Installing ${unit_src} -> ${UNIT_DST}"
    sudo cp "${unit_src}" "${UNIT_DST}"
    sudo systemctl daemon-reload
    sudo systemctl enable --now wanos.service
    sudo systemctl --no-pager --lines=15 status wanos.service || true
    echo "OK: wanos.service enabled"
    if sudo -n /usr/bin/systemctl restart wanos.service 2>/dev/null; then
        echo "OK: passwordless systemctl restart wanos.service works"
    else
        echo "NOTE: sudo -n restart failed - phase1 sudoers should allow it after reboot/login"
    fi
}

# Prefer LE certs when present; else keep / regenerate self-signed (same as phase1)
wanos_refresh_nginx_site() {
    local tmpl pub_cert pub_key ssl_dir
    tmpl="$(wanos_find_bootstrap_file wanos.nginx.conf)" || {
        echo "WARN: wanos.nginx.conf not found - skip nginx refresh."
        return 0
    }
    ssl_dir="/etc/ssl/wanos"
    if [ -f "${LE_FULLCHAIN}" ] && [ -f "${LE_PRIVKEY}" ]; then
        pub_cert="${LE_FULLCHAIN}"
        pub_key="${LE_PRIVKEY}"
        echo "Nginx app.wanos.be TLS: Let's Encrypt"
    else
        mkdir -p "${ssl_dir}" 2>/dev/null || sudo mkdir -p "${ssl_dir}"
        pub_cert="${ssl_dir}/app.wanos.be.crt"
        pub_key="${ssl_dir}/app.wanos.be.key"
        if [ ! -f "${pub_cert}" ] || [ ! -f "${pub_key}" ]; then
            echo "Generating self-signed TLS for app.wanos.be..."
            sudo openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
                -keyout "${pub_key}" -out "${pub_cert}" \
                -subj "/CN=app.wanos.be" 2>/dev/null
            sudo chmod 640 "${pub_key}"
            sudo chmod 644 "${pub_cert}"
        fi
        echo "Nginx app.wanos.be TLS: self-signed (run ACME-DNS LE, then re-run phase2)"
    fi

    sed \
        -e "s|__SSL_CERTIFICATE__|${pub_cert}|g" \
        -e "s|__SSL_CERTIFICATE_KEY__|${pub_key}|g" \
        "${tmpl}" | sudo tee /etc/nginx/sites-available/wanos > /dev/null
    sudo chmod 644 /etc/nginx/sites-available/wanos
    sudo ln -sfn /etc/nginx/sites-available/wanos /etc/nginx/sites-enabled/wanos
    sudo rm -f /etc/nginx/sites-enabled/default

    echo "--- nginx -t ---"
    if sudo nginx -t; then
        sudo systemctl reload nginx
        echo "OK: app.wanos.be site refreshed"
    else
        echo "ERROR: nginx -t failed." >&2
        exit 1
    fi
}

echo "=========================================="
echo " Starting WanOS Phase 2 Setup..."
echo "=========================================="

# 1. Setup Virtual Environment & Requirements
echo "[1/4] Setting up Python Virtual Environment..."
cd "$APP_DIR"

if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found in $APP_DIR."
    echo "Sync the WanOS tree first: helpers\\wanos-sync.bat run"
    exit 1
fi

echo "System python3: $(python3 -V 2>&1)"
if [ ! -d "wanos_venv" ]; then
    python3 -m venv wanos_venv
fi

[ -f "wanos_venv/bin/activate" ] || { echo "ERROR: Virtual environment creation failed."; exit 1; }

source wanos_venv/bin/activate

python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt

# 2. RFXCom Udev Rules
echo "[2/4] Setting up RFXCom Udev Rules..."
sudo tee /etc/udev/rules.d/99-rfxcom.rules > /dev/null << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="rfxcom"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty

# 3. systemd unit
echo "[3/4] Installing wanos.service..."
wanos_install_service

# 4. nginx site refresh (pick up LE if issued after phase1)
echo "[4/4] Refreshing nginx app.wanos.be site..."
wanos_refresh_nginx_site

command -v deactivate &>/dev/null && deactivate || true

echo "================================================================"
echo " [PHASE 2 COMPLETE]"
echo "================================================================"
echo "venv:           $APP_DIR/wanos_venv"
echo "service:        wanos.service (enable --now)"
echo "nginx:          sites-enabled/wanos -> app.wanos.be"
echo " "
echo "Still operator: Mosquitto st.pwd if missing; ACME-DNS LE; Z-Wave store restore + Docker."
echo "Checklist:      docs/ops7-operator-checklist.md"
echo "================================================================"
