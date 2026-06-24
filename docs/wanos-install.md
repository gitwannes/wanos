# WanOS Ecosystem Setup Guide

This document outlines the complete, from-scratch installation procedure for both the **Backend Engine (WanOS)** and the **Frontend Wall Panels (Kiosk)**.

---

## Part 1: Flashing the Operating Systems

Both the Backend and Frontend require completely different base architectures for optimal performance.

### 1A. Backend Pi (The Engine)
* **Hardware:** Raspberry Pi 4 Model B Rev 1.5 (batcat -A /proc/device-tree/model)
* **OS Target:** Debian 13 (Trixie) Lite (64-Bit).

**Flash Raspberry Pi using the Raspberry Pi Imager:**
* **Hostname:** `wanos`
* **Username and password:** `wannes` / `xxx`
* **Configure Wi-Fi:** (country BE)
* **Locale/Timezone:** Europe / Brussels
* **Keyboard layout:** Generic 105 -> Belgian
* **Enable SSH**

### 1B. Frontend Pi (The Display Kiosk)
* **Hardware:** Raspberry Pi 3 Model B Rev 1.2 (cat /proc/device-tree/model)
* **Screen:** Waveshare 4.3inch IPS screen, 800 x 480 hardware resolution, DSI connected, https://www.waveshare.com/wiki/4.3inch_DSI_LCD
* **OS Target:** Raspberry Pi OS Lite (32-Bit) **Bookworm**. *(Must be Bookworm to support Wayland, must be 32-bit to save RAM on the Pi 3).*
* **Hostname:** `wanos-panel1`
* **Credentials:** `wannes` / `<password>`
* **Configuration:** Enable SSH, set Wi-Fi.

---

## Part 2: Backend Installation

1. Insert SDcard and boot.
2. Get IP and connect remotely with SSH.
3. Run the Phase 1 script to prepare the core OS, log2ram, and hardware parameters:
   ```bash
   sudo ./wanos_bootstrap_phase1.sh
   ```
4. Set your Samba password and reboot:
   ```bash
   sudo smbpasswd -a wannes
   sudo reboot
   ```
5. From your Windows PC, mount the shared drive and copy over your configuration files (`.env`, `requirements.txt`, and the WanOS python code):
   ```cmd
   # on Windows
   net use Z: "\\10.32.251.28\wanos_share" /user:wannes
   ```
6. SSH back in and run Phase 2 to compile the Python environment:
   ```bash
   ./wanos_bootstrap_phase2.sh
   ```
7. Post-script actions: Install the systemd file (`/etc/systemd/system/wanos.service`) and start the backend service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable wanos.service
   sudo systemctl start wanos.service
   
   ./wanoslog.sh 1  # for consolelog
   ```
8. *Optional Hardware:* Configure I²C, GPIO, and the Z-Wave JS middleware as detailed in `zwave migration.md`.

---

## Part 3: Frontend Kiosk Installation

1. Connect the DSI Ribbon cable from the Waveshare screen to the Pi 3 *before* applying power.
2. Insert SDcard, boot, get IP, and SSH into the Frontend Pi.
3. Run the Phase 1 script to install the Wayland display server, Chromium, and configure the Wi-Fi power overrides:
   ```bash
   sudo ./kiosk_bootstrap_phase1.sh
   ```
4. Set the Kiosk Samba password (optional, useful for debugging) and reboot:
   ```bash
   sudo smbpasswd -a wannes
   sudo reboot
   ```
5. SSH back in. Edit `./kiosk_bootstrap_phase2.sh` to ensure `BACKEND_IP` points to your WanOS Engine, then run it:
   ```bash
   ./kiosk_bootstrap_phase2.sh
   ```
6. Start the Kiosk display:
   ```bash
   sudo systemctl start kiosk.service
   ```

---

## Part 4: Tools used
* Notepad++
* Everything
* Super Finder XT
* PyCharm
* SmartGit
* FileZilla
* MQTT Explorer
* SecureCRT
* Robocopy
* Chrome
* https://jsonformatter.org
* https://text-compare.com

---

## Part 5: Waveshare 4.3" DSI Screen Emulation Guide (Google Chrome)

This guide outlines how to configure Google Chrome's Developer Tools to precisely replicate the resolution, physical constraints, and touch interactions of the frontend wall hardware.

## Step-by-Step Setup

1. **Open the Dashboard**
   Launch Google Chrome on your desktop computer and navigate to your panel's development address (e.g., `http://10.32.251.30:8000/kiosk.html` or your backend Pi's temporary address).

2. **Open Developer Tools**
   Press **`F12`** (or `Ctrl + Shift + I` on Windows / `Cmd + Option + I` on Mac) to slide open the Developer Tools window.

3. **Toggle Device Toolbar**
   Click the **Device Emulation Icon** located at the top-left corner of the Developer Tools panel (it resembles a small smartphone overlapping a larger tablet screen). This forces Chrome into viewport simulation mode.

4. **Create the Custom Waveshare Profile**
   * Click the **Dimensions** dropdown menu at the top of the viewport area (it typically defaults to *Responsive*, *Dimensions*, or a specific phone model).
   * Scroll to the bottom of the list and select **Edit...**.
   * In the device settings sidebar that appears, click **Add custom device...**.
   * Configure the device parameters exactly as follows:
     * **Device Name:** `Waveshare 4.3" DSI`
     * **Width:** `800`
     * **Height:** `480`
     * **Device pixel ratio:** `1` *(Crucial: This locks down a 1:1 pixel grid mapping, preventing high-DPI desktop scaling anomalies)*
     * **User agent string:** Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
     * **Device type:** Select **Touch** from the dropdown menu
   * Click **Save** and close the settings sidebar.

5. **Activate the Simulation**
   Select your newly created `Waveshare 4.3" DSI` profile from the top dimensions dropdown menu. Set the zoom scale factor adjacent to it to **100%**.

## Verifying Kiosk Behavior

* **Touch Physics:** Your standard mouse pointer will transform into a translucent gray circle. This simulates a physical finger print. Dragging will act as a finger touch-swipe rather than a mouse-click selection.
* **Layout Constraints:** Because the layout relies on strict viewport locking, look closely around the edges. There should be **no horizontal or vertical scrollbars** visible anywhere on the screen canvas.
* **Chunky Hit Areas:** Test the button layout with your cursor. Every element must be large enough to target comfortably with the translucent circle to ensure a smooth real-world tactile response on the wall panel.