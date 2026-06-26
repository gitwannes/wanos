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
* **Screen:** Waveshare 4.3inch IPS screen, 800 x 480 hardware resolution
* The display is DSI while the touch is SPI
* Touchscreen controller is ADS7846, connected via SPI0.1
*	interrupt pin is IRQ 166 (GPIO 6)
*	uses legacy FKMS overlays

*	touch driver:	dtoverlay=ads7846,penirq=6,speed=2000000,keep_vref_on=1,swapxy=1,pmax=255,xmin=200,xmax=3900,ymin=200,ymax=3900
*	DSI:			dtoverlay=WS_4_3inch_DSI
*	FKMS driver: dtoverlay=vc4-fkms-v3d

*	https://www.waveshare.com/wiki/4.3inch_DSI_LCD
* **OS Target:** Raspberry Pi OS (Legacy) Lite (32-Bit) **Bookworm**. *(Must be Bookworm to support Wayland, must be 32-bit to save RAM on the Pi 3).*
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

0. Connect the DSI Ribbon cable from the Waveshare screen to the Pi 3 *before* applying power.
1. Flash an SDcard with the buster 2021-05-07-raspios-buster-armhf-lite.img
2. change line endings for the /boot/firstboot.sh file in Notepad++:
	Menu: Edit → EOL Conversion → Unix (LF)
	Menu: Encoding → Encode in UTF‑8 (NOT “UTF‑8 BOM”)
3. copy these files on the sdcard
4. eject & insert into Pi
3. get IP and connect remotely with SSH
	credentials wannes/changeme
x.	change pw for wannes
   ```
	passwd wannes
   ```
x.	reboot
7.	create the wanos_bootstrap_phase1.sh script and paste the contents
	in vi, use :set paste
x.	give exec
   ```
	chmod +x wanos_bootstrap_phase1.sh
   ```
3. Create the .env file with these contents
   ```
	BACKEND_IP=10.32.251.30
	KIOSK_USER=wanospanel
   ```
3. Run the script
   ```bash
   sudo ./kiosk_bootstrap.sh
   ```
4. Start the Kiosk display
----- check from kiosk.md
5. To monitor the consolelog of the application
----- check from kiosk.md

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
* https://www.raspberrypi.com/software
* https://etcher.balena.io
* https://minify-js.com

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


## Part 6: Touchscreen research

* Hardware: Raspberry Pi 3 Model B Rev 1.2
* Screen: Waveshare 4.3inch IPS screen, 800 x 480 hardware resolution
# (NOT https://www.waveshare.com/wiki/4.3inch_DSI_LCD !! (this is for a newer verion of the board))
the display is DSI while the touch is SPI
touchscreen controller is ADS7846, connected via SPI0.1
interrupt pin is IRQ 166, GPIO 25
* /boot/config.txt
dtparam=i2c_arm=on
dtparam=spi=on
enable_uart=1
dtoverlay=vc4-fkms-v3d
# dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=50000,keep_vref_on=0,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=2000000,keep_vref_on=1,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900

detailed information on the dtoverlay:
cs=1
	Meaning: Use SPI chip select 1 (i.e., spi0.1).
	Status: Correct for your spi0.1 device.
	penirq=25
	Meaning: GPIO number used for the PENIRQ (touch interrupt).
penirq_pull=2
	Meaning: Sets internal pull resistor for the PENIRQ GPIO. Values vary by overlay implementation.
	Advice: If your PENIRQ line is floating when idle, try penirq_pull=2 (often means pull-down) or penirq_pull=1 (pull-up) depending on wiring. If you see spurious interrupts, flip the pull setting. Test by observing dmesg while touching and not touching.
speed=50000
	Meaning: SPI clock speed in Hz.
	Tradeoff: Lower speed (50 kHz) is very safe but can feel sluggish. Higher speeds (e.g., 2000000) are commonly used and make touch more responsive.
	Recommendation: Try speed=2000000 (2 MHz) if touch is slow; if you see corrupted samples or instability, revert to 50000.
keep_vref_on=0
	Meaning: Power the ADS7846 reference only during touch (0 = off between touches).
	Tradeoff: 0 saves power but can increase latency and cause calibration drift; 1 keeps Vref on for faster, more stable readings.
	Recommendation: For a kiosk with continuous uptime, use keep_vref_on=1 unless you have a power reason not to.
swapxy=0
	Meaning: Swap X/Y axes.
	Action: Keep as-is if touch axes match display orientation. If X/Y are swapped, set swapxy=1. You can test with evtest or by touching corners.
pmax=255 and xohms=150
	Meaning: pmax is pressure max; xohms is stylus resistance hint. These are fine as defaults; adjust only if calibration or pressure behavior is odd.
xmin/xmax/ymin/ymax
	Meaning: Raw ADC calibration bounds.
	Advice: These look reasonable. If touches map incorrectly, run a calibration tool and update these values.

* Kiosk stack on Buster:
Try native Wayland first. Launch Chromium with:
	WAYLAND_DISPLAY=wayland-1 chromium-browser --ozone-platform=wayland --kiosk ...
Ensure VA‑API drivers are installed (vainfo) and test chrome://gpu. 
If you see software rendering or video decode failures, switch to XWayland by removing --ozone-platform=wayland and confirm behavior. 
Fallback plan: Use XWayland only for problematic pages; otherwise keep Wayland for the kiosk.

add a specific udev rule for the ADS7846 input device so the kiosk user can read the input device without root and so the compositor can map it correctly:
/etc/udev/rules.d/99-ads7846.rules:
	# Allow kiosk user to read ADS7846 input device
	KERNEL=="event[0-9]*", SUBSYSTEM=="input", ATTRS{name}=="ADS7846 Touchscreen", MODE="0660", GROUP="input"

on windows to open a port forward
	ssh -L 9222:127.0.0.1:9222 wanospanel@10.32.251.106
then browse to http://localhost:9222/


** tests
cat /proc/device-tree/model
dmesg | grep -i touch
dmesg | grep -i ads
grep -i dtoverlay /boot/firmware/config.txt
cat /proc/bus/input/devices
ls -l /dev/input/event*
systemctl --user show-environment
cat /proc/interrupts | grep ads7846
grep -r "" /sys/kernel/irq/166/

sudo apt install libinput-tools
libinput list-devices | grep -i touch
libinput debug-events --device=/dev/input/event0
libinput debug-events --device=/dev/input/event0
systemctl status seatd

lsb_release -a
cat /etc/*-release
cat /proc/version


## Part 6: other snippets & code info

ls /dev/serial/by-id/
lrwxrwxrwx 1 root root 13 Jun 25 10:12 usb-Nabu_Casa_ZBT-2_14C19FC70CC4-if00 -> ../../ttyACM0
lrwxrwxrwx 1 root root 13 Jun 25 08:17 usb-RFXCOM_RFXtrx433_A1Z68UAV-if00-port0 -> ../../ttyUSB0
