# --- file: helpers/bootstrap/backend/wanos-install-backend.md ---
# WanOS Backend Fresh Installation & Bootstrap Blueprint

**Ops7 locks + order of operations (canonical):** [`docs/bootstrap-main-pi.md`](../../../docs/bootstrap-main-pi.md) · delivery [`docs/todo/ops7-fresh-install.md`](../../../docs/todo/ops7-fresh-install.md).  
**WLW host flash:** not here — WLW overlay is be90webserver; see that repo `docs/bootstrap-host.md`.

This document is the long-form operational guide for deploying a fresh WanOS backend on a Raspberry Pi 4 (shared with WLW at `.30`). Canonical locks/order: [`docs/bootstrap-main-pi.md`](../../../docs/bootstrap-main-pi.md). Short ticks: [`docs/ops7-operator-checklist.md`](../../../docs/ops7-operator-checklist.md). Scripts: `wanos_bootstrap_phase1.sh` / `wanos_bootstrap_phase2.sh`; helpers: `docker-compose.yml`, `mosquitto-st.conf`, `wanos.service`, `wanos.nginx.conf`. **No Samba** (Ops7).

**Automated (Ops7):** phase1 — nginx + PHP-FPM (gate ≥ **8.4.27**) + **`app.wanos.be` site** (self-signed until LE) + **Mosquitto apt + `mosquitto-st.conf`**. phase2 — venv + **`wanos.service` enable** + nginx refresh (prefer LE). **Still operator:** `st.pwd`, ACME-DNS first LE (Nomeo CNAME), Z-Wave store backup/restore + Docker.

---

## Phase 0: Base OS Flashing & Pre-Flight File Transfers

The bootstrap pipeline requires a freshly flashed Linux host with SSH access and initial deployment files placed in the home directory before running installation scripts.

### 0.1 Flash Operating System Image
1. Launch **Raspberry Pi Imager** on your development machine.
2. Select **Raspberry Pi 4** as the target hardware device.
3. Choose **Debian 13 (Trixie) Lite 64-Bit** (or Raspberry Pi OS Lite 64-Bit) as the operating system.
4. Configure **OS Customization Settings**:
   * **Hostname:** `wanos`
   * **Username / Password:** `wannes` / `<your-secure-password>`
   * **Wireless LAN:** Enter your local Wi-Fi credentials and select Country `BE`.
   * **Locale / Timezone:** `Europe/Brussels`
   * **Keyboard Layout:** Generic 105 -> Belgian (`be`)
   * **Services:** Enable SSH using password authentication

### 0.2 Initial Boot & Verification
1. Insert the flashed SD card into your Raspberry Pi 4, connect the power supply, and attach Ethernet.
2. Determine the Pi's assigned local IP address (e.g., `10.32.251.30`) from your network router.
3. Open a terminal and connect over SSH:
   ```bash
   ssh wannes@10.32.251.30
   ```
4. Run system diagnostic commands to verify the environment:
   ```bash
   # Verify OS release metadata
   cat /etc/os-release
   
   # Output raw Debian version
   cat /etc/debian_version
   
   # Confirm running kernel architecture
   uname -r
   ```

### 0.3 Pre-Flight File Delivery
Before executing Phase 1, transfer the bootstrap scripts and helper files into `/home/wannes/` (or keep them beside the scripts) via SCP — path segment `bootstrap` is excluded from main `wanos-sync` mirror:
* `wanos_bootstrap_phase1.sh` (nginx, PHP-FPM, Mosquitto apt, `app.wanos.be` site, no Samba)
* `wanos_bootstrap_phase2.sh` (venv, `wanos.service`, nginx LE refresh)
* `apt-packages.txt` (OS-level package list)
* `wanos.nginx.conf` (site template)
* `requirements.txt` (after first sync, or copy with phase2)
* `docker-compose.yml` (Z-Wave JS UI)
* `mosquitto-st.conf` (MQTT broker conf)
* `wanos.service` (systemd unit template)

---

## Phase 1: System Bootstrapping & OS Tuning (Scripted + Manual Post-Actions)

Phase 1 optimizes the OS, installs packages from `apt-packages.txt` (incl. **nginx**, **PHP-FPM**, **mosquitto**), gates patched PHP (≥ 8.4.27 on Trixie), installs the **`app.wanos.be`** nginx site + Mosquitto conf, disables onboard Bluetooth for UART, sets up `log2ram`, applies **rsyslog logcap** when available, and **does not install Samba**.

### 1.1 Execute Phase 1 Script
Run `wanos_bootstrap_phase1.sh` with superuser privileges:
```bash
# Ensure execution bit is assigned
chmod +x wanos_bootstrap_phase1.sh

# Run Phase 1 setup (Requires root)
sudo ./wanos_bootstrap_phase1.sh
```

> **What `wanos_bootstrap_phase1.sh` performs automatically:**
> * Updates APT and upgrades system packages.
> * Installs packages from `apt-packages.txt` (tools, **nginx**, **PHP-FPM**, **mosquitto**, python3-venv/pip, …). **No Samba.**
> * Enables PHP-FPM; **fails** if `php -v` is below patched gate (8.4.27 / 8.2.35).
> * Installs **`app.wanos.be`** nginx site from `wanos.nginx.conf` (self-signed under `/etc/ssl/wanos/` until LE).
> * Deploys **`mosquitto-st.conf`**; enables mosquitto when `st.pwd` exists (else prints `mosquitto_passwd` hint).
> * Purges leftover Samba if present.
> * Boot overlays: `dtoverlay=disable-bt`, `enable_uart=1`; masks `hciuart`.
> * Bash aliases, console monitors, `.vimrc`, bat config.
> * Groups `dialout`/`i2c`/`gpio`; sudoers for log2ram + `wanos.service` restart.
> * `/var/log/wanos` + `/home/wannes/wanos` stub.
> * log2ram 256M; rsyslog logcap when script available.

### 1.2 Manual Post-Phase 1 Actions
1. **Reboot** (overlays, groups, log2ram):
   ```bash
   sudo reboot
   ```

2. **Sync codebase to the Pi (`/home/wannes/wanos/`):**
   On the Windows workstation, SSH keys + rsync via `helpers\wanos-sync.bat` (no Samba/`Z:`).

   **Full fresh-PC procedure:**  
   → [`docs/wanos-sync.md`](../../../docs/wanos-sync.md)

   ```text
   helpers\wanos-sync.bat test
   helpers\wanos-sync.bat run
   ```

   That deploys the WanOS tree to `/home/wannes/wanos/` (excludes venvs, docs, sync tooling, Pi-owned YAML/DBs). Ensure these are available on the Pi for later phases (via sync and/or bootstrap copy):
   * WanOS source (`main.py`, `core/`, `logic/`, `hardware/`, `integrations/`, …)
   * Config profiles (`config.yaml`, `config_hardware.yaml`, …)
   * `entity_registry.auto.yaml` — optional on first install; created/updated at runtime. See `docs/todo/phaseB-blocky.md`.
   * `requirements.txt`
   * `.env` (create on the Pi; never sync secrets from git)
   * Bootstrap helpers already used in Phase 0/1 (`docker-compose.yml`, `mosquitto-st.conf`, `wanos.service`, …)
   * Rsyslog logcap (mirrored under `helpers/`): `wanos_rsyslog_logcap.sh`, `wanos-syslog-truncate.sh`, `logrotate.rsyslog`

### 1.3 Existing host — rsyslog logcap (**Ops1** 2026-08-16) ✅ **Done**

These files live in `helpers/` so day-to-day `wanos-sync` **mirrors** them (`helpers/bootstrap` stays excluded). After `helpers\wanos-sync.bat run`:

```bash
sudo bash /home/wannes/wanos/helpers/wanos_rsyslog_logcap.sh
```

The script is idempotent. It backs up `/etc/rsyslog.conf` and `/etc/logrotate.d/rsyslog` once (`.bak.wanos-logcap`), validates with `rsyslogd -N1`, then restarts `rsyslog`. It does **not** delete a leftover `/var/log/daemon.log`.

**Pi smoke ✅ 2026-08-16:** rsyslog 8.2102.0; `log2ram` 16% (163M / 1.0G); `wanos.log` + `journalctl -u wanos.service` live; `$outchannel wanos_syslog_cap` + commented `daemon.log`; logrotate has no `/var/log/syslog` or `/var/log/daemon.log` paths. `/etc/rsyslog.conf` is `0640` — use **sudo** grep.

```bash
# daemon.log rule commented; syslog uses $outchannel wanos_syslog_cap
sudo grep -E 'wanos_syslog_cap|daemon.log' /etc/rsyslog.conf

# logrotate must not list /var/log/syslog or /var/log/daemon.log as paths
sudo grep -E '^/var/log/(syslog|daemon\.log)' /etc/logrotate.d/rsyslog || true

df -h /var/log
ls -l /var/log/syslog /var/log/wanos/wanos.log
journalctl -u wanos.service -n 5 --no-pager
```

WanOS app logs stay `/var/log/wanos/*`. Optional later (not this script): uvicorn `--no-access-log` / JWT, `ForwardToSyslog`, log2ram `SIZE`, auth/kern no-archive.

---

## Phase 2: Venv, RFX udev, `wanos.service`, nginx refresh (Scripted)

Phase 2 builds `wanos_venv`, installs requirements (incl. certbot in the venv for ACME-DNS), RFX udev, **enables `wanos.service`**, and **refreshes** the `app.wanos.be` nginx site (LE certs if present).

### 2.1 Execute Phase 2 Script
SSH back into the Raspberry Pi as user `wannes` (do **NOT** run with `sudo`):
```bash
cd /home/wannes/wanos

# Assign execution permissions
chmod +x wanos_bootstrap_phase2.sh

# Run Phase 2 compilation as user wannes
./wanos_bootstrap_phase2.sh
```

> **What `wanos_bootstrap_phase2.sh` performs automatically:**
> * Verifies `requirements.txt` exists in `/home/wannes/wanos/`.
> * Creates `wanos_venv`; upgrades pip tooling; installs `requirements.txt`.
> * RFX udev rule → `/dev/rfxcom`.
> * Installs and **`enable --now` `wanos.service`** from bootstrap template.
> * Refreshes nginx `app.wanos.be` site (Let's Encrypt paths if present, else self-signed).

---

## Phase 3: MQTT — password file (operator; packages/conf by phase1)

Phase 1 already `apt`-installs **mosquitto** / **mosquitto-clients** and deploys **`mosquitto-st.conf`**. Broker starts only when **`/etc/mosquitto/conf.d/st.pwd`** exists.

### 3.1 Create or restore `st.pwd`
```bash
# New password:
sudo mosquitto_passwd -c /etc/mosquitto/conf.d/st.pwd wannes

# Or restore offline backup of st.pwd into /etc/mosquitto/conf.d/st.pwd
sudo systemctl enable --now mosquitto
sudo systemctl status mosquitto
```

> **`mosquitto-st.conf`:** TCP **1883** (backend) + WebSockets **9001** (browser).

---

## Phase 4: Middleware & Z-Wave Container Setup (Manual Setup)

The bootstrap scripts do not install Docker or Docker Compose. You must install the Docker engine manually using the official convenience script and deploy the Z-Wave JS UI middleware.

### 4.1 Install Docker Engine via Official Convenience Script
Using the official Docker installer ensures you get the latest stable Docker engine and native Go-based Docker Compose V2 plugin:
```bash
# Download the official Docker installation script
curl -fsSL [https://get.docker.com](https://get.docker.com) -o get-docker.sh

# Execute installer with root privileges
sudo sh get-docker.sh

# Clean up temporary installer file
rm get-docker.sh

# Grant user wannes permission to run containers without sudo
sudo usermod -aG docker wannes

# Apply group membership changes immediately
newgrp docker
```

### 4.2 Verify Hardware Serial Controller Node
Check the system serial paths to confirm your Z-Wave USB controller stick is recognized by Linux:
```bash
ls -l /dev/serial/by-id/
```
*Expected Output:*
Shows a symlink pointing to your USB stick (e.g., `/dev/serial/by-id/usb-Nabu_Casa_ZWA-2_1CDBD4AF8A6C-if00`). Ensure this path matches line 11 of your `docker-compose.yml` file.

### 4.3 Restore Z-Wave store (**operator** — Ops7)

Before starting the container on a **fresh** card, restore the backed-up store tree to **`/opt/zwave-js-ui`** (from wanos-sync / interim rsync of the old card). See [`docs/ops7-operator-checklist.md`](../../../docs/ops7-operator-checklist.md) and [`docs/integration_zwave.md`](../../../docs/integration_zwave.md) § 9.2b. Skipping this loses mesh / NVM state.

```bash
# Example after copying from PC backup:
sudo mkdir -p /opt/zwave-js-ui
# … copy store files into /opt/zwave-js-ui …
sudo chown -R root:root /opt/zwave-js-ui   # adjust if your live perms differ
```

### 4.4 Deploy Z-Wave JS UI Container
Launch the containerized middleware using Docker Compose:
```bash
cd /home/wannes/wanos

# Launch Z-Wave JS UI container in detached background mode
docker compose up -d
```

### 4.5 Verify Middleware Container Health
```bash
# Confirm container is active and running
docker ps

# Verify web management port 8091 is open
ss -tulpn | grep 8091
```
Confirm nodes match the pre-cutover mesh (restored store).

---

## Phase 5: Systemd Core Service (`wanos.service`)

**Automated by phase2** after venv exists: copies `helpers/bootstrap/backend/wanos.service` → `/etc/systemd/system/wanos.service`, `daemon-reload`, `enable --now`. Uvicorn binds **`127.0.0.1:8080`** only (no `--reload`).

### 5.1 Verify (after phase2)
```bash
sudo systemctl status wanos.service
/home/wannes/wanos/wanoslog.sh 1
```

**Dev-only (never in unit):** `uvicorn main:app --host 127.0.0.1 --port 8080 --reload`.

### 5.2 Manual re-install (if needed)
```bash
sudo cp /path/to/wanos.service /etc/systemd/system/wanos.service
sudo systemctl daemon-reload
sudo systemctl enable --now wanos.service
```

### 5.4 Passwordless service restart (Admin “Reboot WanOS”)

Phase 1 writes this into `/etc/sudoers.d/wannes_sudo_policy`. Required so the Admin API can restart the **WanOS service only** (not the host) without a password prompt:

```text
wannes ALL=(root) NOPASSWD: /usr/bin/systemctl restart wanos.service
```

**Fresh install:** sudoers already applied by `wanos_bootstrap_phase1.sh`. After phase2 enables the unit, verify as user `wannes`:

```bash
# Must exit 0 with no password prompt
sudo -n systemctl restart wanos.service
echo "exit=$?"
```

**Existing Pi (upgrade / policy missing):** append the line (or re-run Phase 1 sudoers block), then validate:

```bash
# Edit as root (visudo-safe)
sudo visudo -f /etc/sudoers.d/wannes_sudo_policy
# Add:
#   wannes ALL=(root) NOPASSWD: /usr/bin/systemctl restart wanos.service

sudo visudo -c -f /etc/sudoers.d/wannes_sudo_policy

# As user wannes — must exit 0
sudo -n systemctl restart wanos.service
echo "exit=$?"
```

If `sudo: a password is required`, the Admin Reboot button will show a UI error until NOPASSWD is fixed.

---

## Phase 6: NGINX Reverse Proxy & Let's Encrypt SSL via ACME-DNS (Nomeo DNS Integration)

Because Nomeo DNS lacks a native Certbot API plugin, we use **ACME-DNS CNAME delegation**. This requires downloading the official `acme-dns-auth.py` hook and adding a **one-time static CNAME record** in Nomeo's control panel, allowing Let's Encrypt to validate certificates automatically every 60 days without opening inbound ports.

### 6.1 Prerequisites & Nomeo Initial A Record Setup
1. Log into your **Nomeo Control Panel** (`wanos.be`).
2. Navigate to **DNS Management** for `wanos.be` and add a new `A` record:
   * **Host / Subdomain:** `app`
   * **Type:** `A`
   * **Target / IP Address:** `10.32.251.30` (Your Raspberry Pi's local network IP)
   * **TTL:** `300` (or default)
3. Save the DNS changes.

### 6.2 Certbot symlink & ACME-DNS hook (nginx already from phase1)
1. **Nginx** is already installed and the `app.wanos.be` site is live from **phase1** (self-signed until this LE succeeds). Do **not** re-`apt install nginx` unless missing.

2. Symlink the **venv** `certbot` (from phase2 `requirements.txt`) for ACME-DNS — this is the binary the WanOS LE procedure uses (apt also ships `certbot`; prefer the venv path here for renew cron consistency):
   ```bash
   sudo ln -sf /home/wannes/wanos/wanos_venv/bin/certbot /usr/local/bin/certbot
   ```

3. Create the configuration directory, download the official ACME-DNS authentication hook script, and set permissions:
   ```bash
   sudo mkdir -p /etc/letsencrypt
   sudo curl -o /etc/letsencrypt/acme-dns-auth.py https://raw.githubusercontent.com/joohoi/acme-dns-certbot-joohoi/master/acme-dns-auth.py
   sudo chmod 0700 /etc/letsencrypt/acme-dns-auth.py
   ```

> Important: This setup uses the **manual auth hook** (`--manual-auth-hook /etc/letsencrypt/acme-dns-auth.py`) stored in Certbot’s renewal config.
> You do **not** need (and should avoid) installing the `certbot-acme-dns` plugin; if present, it may cause Certbot plugin-load errors.

### 6.3 Run Initial Let's Encrypt ACME-DNS Issue Command
Request the initial certificate using the downloaded authentication hook:

```bash
sudo certbot certonly --manual \
  --manual-auth-hook /etc/letsencrypt/acme-dns-auth.py \
  --preferred-challenges dns \
  --debug-challenges \
  -d app.wanos.be
```

### 6.4 Add One-Time CNAME Delegation Record in Nomeo DNS
During the execution of Step 6.3, Certbot will pause and display instructions containing an `acme-dns.io` server string:

```text
Please add a CNAME record with the following information:
  Name:  _acme-challenge.app.wanos.be
  Value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.auth.acme-dns.io
```

1. Return to your **Nomeo Control Panel** for `wanos.be`.
2. Add a new **CNAME** record:
   * **Host / Subdomain:** `_acme-challenge.app`
   * **Type:** `CNAME`
   * **Target / Value:** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.auth.acme-dns.io` *(Copy exact string provided by terminal)*
3. Save the DNS changes in Nomeo.
4. Wait 30 seconds for DNS propagation, then press **Enter** in your Pi terminal session.
5. Certbot will verify the CNAME, generate keys, and store certificate files in `/etc/letsencrypt/live/app.wanos.be/`.

### 6.5 NGINX `app.wanos.be` site (automated)

Phase1 installs the site from **`wanos.nginx.conf`** (self-signed under `/etc/ssl/wanos/` until LE exists). After §6.3–6.4 succeed, **re-run phase2** (or phase1) so the site picks up `/etc/letsencrypt/live/app.wanos.be/*`.

```bash
# Prefer: re-run phase2 as wannes (refreshes nginx + leaves venv alone if already built)
./wanos_bootstrap_phase2.sh

sudo nginx -t
sudo ss -tulpn | grep -E '8000|8080|443|80'
```

*Expected:* `127.0.0.1:8080` uvicorn · `80`/`443`/`8000` nginx.

### Completion
Navigate to `https://app.wanos.be` (after LE) — UI loads; port **8000** redirects to HTTPS.

### 6.7 Configure Automated Renewal Cron Job
Because we use the virtual environment binary instead of the Debian APT package, configure a daily root cron job to automate background certificate renewals and reload NGINX on success:

1. Open root crontab:
   ```bash
   sudo crontab -e
   ```
2. Append the following schedule line:
   ```cron
   40 3 * * * /home/wannes/wanos/wanos_venv/bin/certbot renew --quiet --post-hook "systemctl reload nginx"
   ```
3. Test dry-run renewal to verify ACME-DNS connectivity:
   ```bash
   sudo /home/wannes/wanos/wanos_venv/bin/certbot renew --dry-run
   ```

---

## Phase 7: Backend Displays & Hardware Bus Verification (Manual Setup)

The WanOS backend directly drives status peripherals (I²C Character LCDs and SPI E-Ink displays) attached to the Raspberry Pi 4 GPIO header.

### 7.1 Verify Bus Overlays in Firmware Configuration
Confirm `/boot/firmware/config.txt` contains active I²C and SPI configuration parameters:
```text
dtparam=i2c_arm=on
dtparam=spi=on
```

### 7.2 Character LCD Setup (I²C Bus)
Character LCD screens (e.g., 16x2 or 20x4 HD44780 displays using PCF8574 backpacks) display live operational status on the backend hardware enclosure.

1. **Scan I²C Bus:**
   Run the bus detector to verify the connected backpack address:
   ```bash
   i2cdetect -y 1
   ```
   *Expected Output:* The scanner highlights active addresses (typically `0x27` or `0x26`).

2. **Pinout Reference (I²C-1 Header):**
   * **VCC:** Pin 2 or Pin 4 (5V Power)
   * **GND:** Pin 6 (Ground)
   * **SDA:** Pin 3 (GPIO 2 / I2C1_SDA)
   * **SCL:** Pin 5 (GPIO 3 / I2C1_SCL)

### 7.3 E-Ink / E-Paper Display Setup (SPI Bus)
Low-power SPI E-Paper modules display system health statistics.

1. **Verify SPI Device Nodes:**
   ```bash
   ls -l /dev/spidev0.*
   ```
   *Expected Output:* Confirms `/dev/spidev0.0` and `/dev/spidev0.1` exist.

2. **Pinout Reference (SPI0 Header):**
   * **VCC:** Pin 1 (3.3V Power)
   * **GND:** Pin 9 or Pin 14 (Ground)
   * **DIN (MOSI):** Pin 19 (GPIO 10 / SPI0_MOSI)
   * **CLK (SCK):** Pin 23 (GPIO 11 / SPI0_SCLK)
   * **CS (Chip Select):** Pin 24 (GPIO 8 / SPI0_CE0_N)
   * **DC (Data/Command):** Pin 22 (GPIO 25)
   * **RST (Reset):** Pin 11 (GPIO 17)
   * **BUSY:** Pin 18 (GPIO 24)

---

## Phase 8: Administration Toolkit Inventory

Below is the standard toolkit used to develop, manage, and debug the WanOS ecosystem:

* **Text Editors & IDEs:**
  * Notepad++                            (Quick file editing & Unix EOL conversion)
  * PyCharm                              (Python core development & async debugging)
* **File Search & Management:**
  * Everything                           (Instant local desktop file search)
  * Super Finder XT                      (Advanced pattern search utility)
  * Robocopy                             (Command-line file mirroring)
* **Version Control & File Transfer:**
  * SmartGit                             (Git GUI repository client)
  * FileZilla                            (SFTP/FTP file management)
* **Terminal & Protocol Diagnostics:**
  * SecureCRT / SSH Client               (Linux terminal management)
  * MQTT Explorer                        (Real-time MQTT topic debugging)
  * Google Chrome                        (Web UI and browser DevTools)
* **Online Reference Utilities:**
  * [JSON Formatter & Validator]         (https://jsonformatter.org)
  * [Text Compare Tool]                  (https://text-compare.com)
  * [RFXcom Hardware Documentation]      (http://rfxcom.com)
  * [Raspberry Pi Software & Imager]     (https://www.raspberrypi.com/software)
  * [Balena Etcher]                      (https://etcher.balena.io)
  * [Rich Text to Markdown converter]    (https://www.rich-text-to-markdown.com)