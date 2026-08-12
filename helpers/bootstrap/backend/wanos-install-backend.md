# --- file: docs/wanos-install-backend.md ---
# ⚡ WanOS Backend Fresh Installation & Bootstrap Blueprint

This document is the master operational guide for deploying a fresh WanOS backend installation on a Raspberry Pi 4 host. It provides a complete, step-by-step walkthrough detailing how the system is bootstrapped using automated shell scripts (`wanos_bootstrap_phase1.sh` and `wanos_bootstrap_phase2.sh`), helper configuration files (`smb.conf`, `docker-compose.yml`, `mosquitto-st.conf`, `wanos.service`), and NGINX with Let's Encrypt SSL via ACME-DNS challenge delegation for Nomeo DNS.

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
Before executing Phase 1, you must transfer the bootstrap scripts and helper configuration files directly into `/home/wannes/` on the Pi via SCP or SFTP:
* `wanos_bootstrap_phase1.sh` (System bootstrap script)
* `wanos_bootstrap_phase2.sh` (Python environment script)
* `apt-packages.txt` (OS-level package dependency list)
* `requirements.txt` (Python virtual environment package list)
* `smb.conf` (Samba network share configuration)
* `docker-compose.yml` (Z-Wave JS UI container definition)
* `mosquitto-st.conf` (MQTT broker configuration)
* `wanos.service` (Systemd core service definition)

---

## Phase 1: System Bootstrapping & OS Tuning (Scripted + Manual Post-Actions)

Phase 1 optimizes the operating system, installs core packages from `apt-packages.txt`, disables onboard Bluetooth to free up hardware UART lanes, sets up `log2ram` to reduce SD card wear, and applies Samba network share parameters using `smb.conf`.

### 1.1 Execute Phase 1 Script
Run `wanos_bootstrap_phase1.sh` with superuser privileges:
```bash
# Ensure execution bit is assigned
chmod +x wanos_bootstrap_phase1.sh

# Run Phase 1 setup (Requires root)
sudo ./wanos_bootstrap_phase1.sh
```

> **What `wanos_bootstrap_phase1.sh` performs automatically:**
> * Updates APT repositories and upgrades system packages.
> * Installs core packages listed in `apt-packages.txt` (`vim`, `bat`, `samba`, `i2c-tools`, `python3-venv`, `python3-pip`, `python3-libgpiod`, `udev`, `curl`, `git`, `avahi-daemon`).
> * Modifies `/boot/firmware/config.txt` to add `dtoverlay=disable-bt` and `enable_uart=1`.
> * Disables and masks the `hciuart` service.
> * Sets up custom Bash aliases, console monitors, `.vimrc`, and `.config/bat` defaults.
> * Adds user `wannes` to groups `dialout`, `i2c`, and `gpio`.
> * Configures passwordless sudo policies for `log2ram write` and `systemctl restart wanos.service` (Admin “Reboot WanOS”).
> * Creates `/var/log/wanos` owned by `wannes:wannes`.
> * Downloads, installs, and configures `log2ram` with a 256M RAM buffer.
> * Copies external `smb.conf` to `/etc/samba/smb.conf` and enables `smbd`.

### 1.2 Manual Post-Phase 1 Actions
1. **Assign Samba Password for User `wannes`:**
   ```bash
   # Set the password used to access the SMB network share from Windows
   sudo smbpasswd -a wannes
   ```

2. **Reboot the System:**
   Rebooting is required to apply kernel overlays, enforce group memberships (`i2c`, `gpio`, `dialout`), and initialize `log2ram`:
   ```bash
   sudo reboot
   ```

3. **Mount Samba Network Share on Development Workstation (optional browse):**
   Samba is useful for Explorer browsing. **Day-to-day code sync does not use `Z:`** — use rsync over SSH instead (see step 4).
   From your Windows PC command prompt, map the share if you want it:
   ```cmd
   net use Z: "\\10.32.251.30\wanos_share" /user:wannes
   ```

4. **Sync codebase to the Pi (`/home/wannes/wanos/`):**
   On the Windows workstation, set up SSH keys + rsync, then push/pull with `helpers\wanos-sync.bat`.

   **Full fresh-PC procedure (OpenSSH, Scoop `rsync-msys2`, SSH key, first `test`/`run`):**  
   → [`docs/wanos-sync.md`](../../../docs/wanos-sync.md)

   After workstation setup:
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

---

## Phase 2: Python Virtual Environment & Hardware Rules (Scripted)

Phase 2 builds the isolated Python execution environment, updates pip dependencies (including `certbot`), and sets up udev rules for external serial transceivers.

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
> * Creates a dedicated Python virtual environment (`wanos_venv`).
> * Upgrades `pip`, `setuptools`, and `wheel` inside the virtual environment.
> * Installs all Python dependencies listed in `requirements.txt` (including `certbot`).
> * Creates udev rule `/etc/udev/rules.d/99-rfxcom.rules` mapping vendor `0403:6001` to `/dev/rfxcom`.
> * Triggers `udevadm` rule reloading.

---

## Phase 3: MQTT Broker Installation & Authentication Setup (Manual Setup)

The bootstrap scripts do not install or configure Mosquitto. You must manually install the broker, apply your custom `mosquitto-st.conf`, and generate the user credentials file.

### 3.1 Install Mosquitto Broker Package
```bash
# Install Mosquitto broker and command-line diagnostic tools
sudo apt update && sudo apt install -y mosquitto mosquitto-clients
```

### 3.2 Deploy Custom Mosquitto Configuration
Copy `mosquitto-st.conf` into Mosquitto's configuration include directory:
```bash
sudo cp /home/wannes/wanos/mosquitto-st.conf /etc/mosquitto/conf.d/mosquitto-st.conf
```

> **Understanding `mosquitto-st.conf`:**
> * References `/etc/mosquitto/conf.d/st.pwd` for user authentication.
> * Establishes standard TCP Listener on **Port 1883** for Python backend events.
> * Establishes WebSockets Listener on **Port 9001** for browser clients.

### 3.3 Create Encrypted Password File (`st.pwd`)
Because `mosquitto-st.conf` requires `/etc/mosquitto/conf.d/st.pwd`, you must generate this file using `mosquitto_passwd` to prevent service startup crashes:
```bash
# Create the password file and assign credentials for user 'wannes'
sudo mosquitto_passwd -c /etc/mosquitto/conf.d/st.pwd wannes
```

### 3.4 Enable and Start Mosquitto
```bash
# Restart Mosquitto to parse the new configuration and password file
sudo systemctl restart mosquitto

# Enable Mosquitto to start automatically on system boot
sudo systemctl enable mosquitto

# Verify broker status
sudo systemctl status mosquitto
```

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

### 4.3 Deploy Z-Wave JS UI Container
Launch the containerized middleware using Docker Compose:
```bash
cd /home/wannes/wanos

# Launch Z-Wave JS UI container in detached background mode
docker compose up -d
```

### 4.4 Verify Middleware Container Health
```bash
# Confirm container is active and running
docker ps

# Verify web management port 8091 is open
ss -tulpn | grep 8091
```

---

## Phase 5: Systemd Core Service Registration (Manual Setup)

Register `wanos.service` to allow systemd to manage the core WanOS Python process, ensure automatic restarts on failure, and direct logs to journald. To prepare for NGINX reverse proxying, Uvicorn is explicitly bound ONLY to internal `127.0.0.1:8080`.

### 5.1 Review Service Definition (`wanos.service`)
Review the repo template `helpers/bootstrap/backend/wanos.service` (on the Pi: `/home/wannes/wanos/helpers/bootstrap/backend/wanos.service`). Ensure it contains the production parameters bound to `127.0.0.1:8080` before copying to the installed unit at `/etc/systemd/system/wanos.service`:
```ini
[Unit]
Description=WanOS Home Automation Core
After=network-online.target
Wants=network-online.target

[Service]
User=wannes
Group=wannes
WorkingDirectory=/home/wannes/wanos
# Forces unbuffered Python output so journald receives logs instantly
Environment=PYTHONUNBUFFERED=1
# Force Uvicorn to listen ONLY to internal localhost traffic on port 8080.
# [PRODUCTION NOTE]: Remove '--reload' in stable production to eliminate CPU scanning overhead.
ExecStart=/home/wannes/wanos/wanos_venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8080 --reload
Restart=always
RestartSec=5
TimeoutStopSec=10
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

### 5.2 Install and Enable Systemd Unit
```bash
# Copy unit file from the repo template to the systemd system directory
sudo cp /home/wannes/wanos/helpers/bootstrap/backend/wanos.service /etc/systemd/system/wanos.service

# Reload systemd manager configuration
sudo systemctl daemon-reload

# Enable and start the WanOS core service immediately
sudo systemctl enable --now wanos.service
```

### 5.3 Verify Execution & Monitor Logs
```bash
# Check service execution status (Confirm binding to 127.0.0.1:8080)
sudo systemctl status wanos.service

# Stream live application console output using the helper logger script
/home/wannes/wanos/wanoslog.sh 1
```

### 5.4 Passwordless service restart (Admin “Reboot WanOS”)

Phase 1 writes this into `/etc/sudoers.d/wannes_sudo_policy`. Required so the Admin API can restart the **WanOS service only** (not the host) without a password prompt:

```text
wannes ALL=(root) NOPASSWD: /usr/bin/systemctl restart wanos.service
```

**Fresh install:** already applied by `wanos_bootstrap_phase1.sh`. After the unit is enabled (5.2), verify as user `wannes`:

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

### 6.2 Install NGINX, Symlink Certbot & Download ACME-DNS Hook Script
1. Install NGINX web server:
   ```bash
   sudo apt update && sudo apt install nginx -y
   ```

2. Symlink the virtual environment's `certbot` binary (installed via `requirements.txt` in Phase 2) so `sudo certbot` works globally:
   ```bash
   sudo ln -sf /home/wannes/wanos/wanos_venv/bin/certbot /usr/local/bin/certbot
   ```

3. Create the configuration directory, download the official ACME-DNS authentication hook script, and set permissions:
   ```bash
   sudo mkdir -p /etc/letsencrypt
   sudo curl -o /etc/letsencrypt/acme-dns-auth.py [https://raw.githubusercontent.com/joohoi/acme-dns-certbot-joohoi/master/acme-dns-auth.py](https://raw.githubusercontent.com/joohoi/acme-dns-certbot-joohoi/master/acme-dns-auth.py)
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

### 6.5 Deploy NGINX Virtual Host Configuration for `app.wanos.be`
Create `/etc/nginx/sites-available/wanos`:
```bash
sudo vi /etc/nginx/sites-available/wanos
```

Paste the following configuration pointing to your live Let's Encrypt keys:

```nginx
# ==============================================================================
# 1. LEGACY BACKWARD COMPATIBILITY (Port 8000)
# ==============================================================================
# If any old tablets or bookmarks hit port 8000, NGINX intercepts it 
# and instantly forces a 301 redirect to the secure 443 port.
server {
    listen 8000;
    server_name app.wanos.be;
    return 301 https://$host$request_uri;
}

# ==============================================================================
# 2. STANDARD HTTP REDIRECT (Port 80)
# ==============================================================================
# Forces standard HTTP traffic to upgrade to HTTPS automatically.
server {
    listen 80;
    server_name app.wanos.be;
    return 301 https://$host$request_uri;
}

# ==============================================================================
# 3. MAIN WANOS HTTPS SERVER (Port 443)
# ==============================================================================
server {
    listen 443 ssl http2;
    server_name app.wanos.be;

    # Point to live Let's Encrypt SSL keys issued via ACME-DNS
    ssl_certificate /etc/letsencrypt/live/app.wanos.be/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.wanos.be/privkey.pem;

    location / {
        # THE REVERSE PROXY
        # NGINX takes the 443 traffic and safely pipes it to Uvicorn on localhost
        proxy_pass http://127.0.0.1:8080;
        
        # Pass the original client IPs and Headers through to WanOS
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CRITICAL FOR WANOS SSE STREAM (Server-Sent Events)
        # NGINX buffers HTTP traffic by default. If we don't turn this off, 
        # the live telemetry stream to the UI will freeze.
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        
        # Prevent NGINX from dropping the SSE connection if no data is sent
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

### 6.6 Enable Configuration, Test Syntax & Verify Listening Ports
```bash
# Link configuration to sites-enabled
sudo ln -s /etc/nginx/sites-available/wanos /etc/nginx/sites-enabled/

# Remove default NGINX placeholder site
sudo rm /etc/nginx/sites-enabled/default

# Verify NGINX syntax
sudo nginx -t

# Restart NGINX to apply proxy rules
sudo systemctl restart nginx

# Verify active listening sockets
sudo ss -tulpn | grep -E '8000|8080|443|80'
```

*Expected Port Assignment Output:*
* **`127.0.0.1:8080`** ➔ `python` (WanOS Uvicorn Backend)
* **`0.0.0.0:8000`** ➔ `nginx` (Legacy 301 Redirect to HTTPS)
* **`0.0.0.0:80`** ➔ `nginx` (Standard HTTP 301 Redirect)
* **`0.0.0.0:443`** ➔ `nginx` (Secure HTTPS Reverse Proxy)

### Completion
Navigate to `https://app.wanos.be` and the UI will load securely.
Any requests to `http://app.wanos.be:8000` (or the Pi's IP on port 8000) will be instantly redirected to the secure portal.

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