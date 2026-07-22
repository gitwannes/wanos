# 📱 wanos-install-frontent-draft.md

This document contains the frontend wall panel (Kiosk) installation guide, display/touchscreen hardware driver configurations, Chrome emulation setups, and diagnostic procedures for the WanOS ecosystem[cite: 11].

---

## 1. Target Hardware & Display Specifications

* **Frontend Panel Host:** Raspberry Pi 3 Model B Rev 1.2[cite: 7, 11]
* **Target Screen:** Waveshare 4.3-inch IPS LCD Screen, 800 x 480 hardware resolution[cite: 7, 11]
  * *Important Note:* This is for the original board version (Display driven over DSI ribbon, Touch controller driven over SPI)[cite: 11].
* **Touchscreen Controller:** ADS7846 chip connected via SPI bus `spi0.1`[cite: 11]
  * **Interrupt Pin:** IRQ 166 (GPIO 25)[cite: 11]
* **OS Target:** Raspberry Pi OS (Legacy) Lite 32-Bit **Bookworm** or **Buster**[cite: 7, 11]. *(Must be Bookworm for native Wayland/Cage compositor support, 32-bit recommended to minimize RAM usage on the Pi 3)*[cite: 7, 11].
* **Target Hostname:** `wanos-panel1`[cite: 11]
* **Default Credentials:** `wannes` / `<password>`[cite: 11]
* **Kiosk Display Stack:** `cage` (Wayland compositor) + `chromium-browser`[cite: 7, 11]

---

## 2. Step-by-Step Frontend Kiosk Installation

### Step 0: Physical Hardware Assembly
1. Connect the DSI flexible ribbon cable from the Waveshare 4.3" screen to the Raspberry Pi 3 DSI port **before** connecting power[cite: 11].
2. Ensure the SPI touch pins are firmly seated onto the Raspberry Pi 3 GPIO header block[cite: 11].

### Step 1: Flashing Operating System
1. Flash an SD card using Raspberry Pi Imager with **Raspberry Pi OS Lite 32-Bit**[cite: 11].
2. If using custom initialization scripts (e.g. `/boot/firstboot.sh`), verify EOL line endings in Notepad++[cite: 11]:
   * **EOL Conversion:** `Edit → EOL Conversion → Unix (LF)`[cite: 11]
   * **Encoding:** `Encoding → Encode in UTF-8` (Do NOT use UTF-8 BOM)[cite: 11]

### Step 2: Initial Access & Credentials
1. Eject SD card and insert into the Pi 3[cite: 11].
2. Power on, obtain the IP address, and connect over SSH[cite: 11]:
   ```bash
   ssh wannes@<KIOSK_PI_IP>
   ```
3. Change default password immediately[cite: 11]:
   ```bash
   passwd wannes
   sudo reboot
   ```[cite: 11]

### Step 3: Deployment Scripts & Environment Parameters
1. Create the `wanos_bootstrap_phase1.sh` or `kiosk_bootstrap.sh` script in `/home/wannes/`[cite: 11].
2. Assign execution permissions[cite: 11]:
   ```bash
   chmod +x kiosk_bootstrap.sh
   ```[cite: 11]
3. Create the local `.env` configuration file[cite: 11]:
   ```ini
   BACKEND_IP=10.32.251.30
   KIOSK_USER=wanospanel
   ```[cite: 11]
4. Run the kiosk bootstrap script with root privileges[cite: 11]:
   ```bash
   sudo ./kiosk_bootstrap.sh
   ```[cite: 11]

---

## 3. Touchscreen & Overlay Configuration (`/boot/config.txt`)

To ensure modern kernel Wayland drivers and the ADS7846 touch controller communicate cleanly over SPI, apply these parameters to `/boot/config.txt` (or `/boot/firmware/config.txt` on Bookworm)[cite: 7, 11]:

```text
# Enable ARM hardware interfaces
dtparam=i2c_arm=on
dtparam=spi=on
enable_uart=1

# Display Graphics Overlays
# Use vc4-kms-v3d on Debian 12 Bookworm, or vc4-fkms-v3d on legacy setups
dtoverlay=vc4-fkms-v3d

# ADS7846 Touchscreen SPI Controller Driver
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=2000000,keep_vref_on=1,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900
```[cite: 7, 11]

### Technical Parameter Breakdown:
* **`cs=1`:** Binds to SPI chip select 1 (`spi0.1`)[cite: 11].
* **`penirq=25`:** Designates GPIO 25 as the hardware interrupt line[cite: 11].
* **`penirq_pull=2`:** Sets internal pull resistor mode to prevent floating interrupt signals[cite: 11].
* **`speed=2000000`:** Sets SPI clock speed to 2MHz for low-latency touch response[cite: 11].
* **`keep_vref_on=1`:** Keeps internal ADC voltage reference enabled to prevent calibration drift during continuous kiosk operation[cite: 11].
* **`swapxy=0`:** Keeps default X/Y axis orientation (set to `1` if touches are inverted)[cite: 11].
* **`xmin=200, xmax=3900, ymin=200, ymax=3900`:** Calibrated raw ADC bounding coordinates[cite: 11].

### Non-Root Input Udev Permissions
To allow the non-privileged kiosk user (`wanospanel`) to read physical input events without root permissions, add `/etc/udev/rules.d/99-ads7846.rules`[cite: 11]:

```ini
# Allow kiosk user group to access the ADS7846 touchscreen input
KERNEL=="event[0-9]*", SUBSYSTEM=="input", ATTRS{name}=="ADS7846 Touchscreen", MODE="0660", GROUP="input"
```[cite: 11]

Reload rules via:
```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```[cite: 11, 13]

---

## 4. Kiosk Window Manager & Browser Launch Stack

The kiosk setup uses **Cage** (a lightweight Wayland compositor) to run Chromium full-screen[cite: 7].

### 4.1 Native Wayland Launch Command
Launch Chromium using Wayland native ozone flags[cite: 11]:
```bash
WAYLAND_DISPLAY=wayland-1 chromium-browser \
  --ozone-platform=wayland \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  [http://10.32.251.30:8000/kiosk.html](http://10.32.251.30:8000/kiosk.html)
```[cite: 11]

*Fallback Execution:* If VA-API hardware video acceleration fails or causes software rendering glitches, drop `--ozone-platform=wayland` to fallback to XWayland[cite: 11].

### 4.2 Remote Chrome DevTools Debugging
To inspect and debug the live kiosk browser session remotely from your workstation[cite: 11]:
1. Launch Chromium with debugging enabled on the Pi: `--remote-debugging-port=9222`[cite: 11].
2. Open an SSH port-forwarding tunnel from your Windows/Mac terminal[cite: 11]:
   ```bash
   ssh -L 9222:127.0.0.1:9222 wanospanel@10.32.251.106
   ```[cite: 11]
3. Open desktop Chrome and browse to: `http://localhost:9222/`[cite: 11]

---

## 5. Waveshare 4.3" DSI Screen Emulation Guide (Desktop Chrome)

Replicate the exact resolution, touch interaction, and target constraints of the wall panel directly on your desktop workstation using Google Chrome Developer Tools[cite: 11].

### Step-by-Step Profile Setup
1. Launch Chrome and navigate to the application endpoint (e.g. `http://10.32.251.30:8000/kiosk.html`)[cite: 11].
2. Press **`F12`** to open Developer Tools[cite: 11].
3. Click the **Toggle Device Toolbar** icon (`Ctrl + Shift + M`)[cite: 11].
4. In the **Dimensions** dropdown, choose **Edit...** -> **Add custom device...**[cite: 11].
5. Configure parameters[cite: 11]:
   * **Device Name:** `Waveshare 4.3" DSI`[cite: 11]
   * **Width:** `800`[cite: 11]
   * **Height:** `480`[cite: 11]
   * **Device Pixel Ratio:** `1` *(Locks 1:1 pixel mapping, disabling high-DPI scaling)*[cite: 11]
   * **User Agent:** `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`[cite: 11]
   * **Device Type:** Select **Touch**[cite: 11]
6. Save and select the profile at **100% Zoom**[cite: 11].

### Viewport Verification Checklist:
* **Touch Physics:** Mouse cursor becomes a translucent circle simulating finger touches[cite: 11].
* **Layout Locking:** Confirm **no horizontal or vertical scrollbars** appear anywhere on screen[cite: 11].
* **Tactile Targets:** Ensure all buttons and touch sliders have large hit targets comfortable for touch interaction[cite: 11].

---

## 6. Hardware & Touch Diagnostics Command Suite

Use these terminal commands on the frontend Pi to troubleshoot touch inputs, drivers, and compositor state[cite: 11]:

```bash
# Verify hardware model
cat /proc/device-tree/model[cite: 11]

# Inspect kernel touch initialization logs
dmesg | grep -i touch[cite: 11]
dmesg | grep -i ads[cite: 11]

# Verify active overlays in firmware configuration
grep -i dtoverlay /boot/firmware/config.txt[cite: 11]

# List active kernel input devices
cat /proc/bus/input/devices[cite: 11]
ls -l /dev/input/event*[cite: 11]

# Check hardware interrupts for ADS7846
cat /proc/interrupts | grep ads7846[cite: 11]

# Real-time touch event testing
sudo apt install libinput-tools -y[cite: 11]
libinput list-devices | grep -i touch[cite: 11]
libinput debug-events --device=/dev/input/event0[cite: 11]

# Verify Wayland seat management service status
systemctl status seatd[cite: 11]
```