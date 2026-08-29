# --- file: _lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md ---
# WanOS LCD Pi — install guide

Target: Raspberry Pi with two HD44780 I2C backpacks (`0x27` sauna, `0x26` control).  
App root on the Pi: **`/home/wannes/wanos`** (same path as WanOS; only LCD-agent files live here).  
Host (site): **`10.32.251.51`**. User: **`wannes`**.

Day-to-day deploy: `helpers\wanos-sync.bat test|run lcd` from the Windows workstation.  
Product display rules: [`docs/sauna-ir.md`](../../../docs/sauna-ir.md) § 3.7.  
Phase: [`docs/todo/phaseL-lcd.md`](../../../docs/todo/phaseL-lcd.md) — **L1 Done** (Pi smoke 2026-08-24); **L2** queued.

---

## 0. Prerequisites

* Fresh Raspberry Pi OS (64-bit) with SSH and user `wannes`.
* WanOS MQTT broker reachable (usually main Pi `10.32.251.30:1883`).
* Windows sync already works for the **main** WanOS Pi (Scoop `rsync-msys2` + MSYS `ssh` + `id_ed25519`). See [`docs/wanos-sync.md`](../../../docs/wanos-sync.md).

---

## 1. Reuse the same SSH key (PC → LCD Pi)

Use the **same** `%USERPROFILE%\.ssh\id_ed25519` already authorized on `10.32.251.30`. Install the pubkey on the LCD Pi once (password OK for this step):

```powershell
$PiUser = "wannes"
$LcdHost = "10.32.251.51"
$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519"

Get-Content "$KeyPath.pub" | ssh "${PiUser}@${LcdHost}" `
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

ssh -o BatchMode=yes -o ConnectTimeout=10 "${PiUser}@${LcdHost}" "echo ok"
```

If `Host key verification failed`: `ssh-keygen -R 10.32.251.51` then reconnect once.

---

## 2. First copy of bootstrap files

Until `run lcd` works, copy the bootstrap folder once (example from repo):

```powershell
scp -r C:\data\git\wanos\_lcd-agent\helpers\bootstrap\* wannes@10.32.251.51:~/lcd-bootstrap/
```

Or sync after SSH works:

```text
helpers\wanos-sync.bat test lcd
helpers\wanos-sync.bat run lcd
```

That mirrors `_lcd-agent/` **contents** into `/home/wannes/wanos/` on `.51`.

---

## 3. Run bootstrap (on the LCD Pi)

```bash
cd ~/lcd-bootstrap   # or: cd /home/wannes/wanos/helpers/bootstrap after first sync
chmod +x wanos_bootstrap_lcdpi.sh
sudo ./wanos_bootstrap_lcdpi.sh
```

What it does:

* apt: python3/venv/pip, i2c-tools, **rsync**, …
* enables `dtparam=i2c_arm=on` in `/boot/firmware/config.txt` **or** legacy `/boot/config.txt`
* adds `wannes` to `i2c`
* creates `/home/wannes/wanos`, **`wanos_venv`**, `/var/log/wanos`
* installs `aiomqtt` + `smbus2` (+ `python-dotenv`)
* seeds `/home/wannes/wanos/.env` if missing (never git; same path as WanOS main)
* installs/enables `wanos-lcd-agent.service`

Edit secrets (never in git):

```bash
nano /home/wannes/wanos/.env
# WANOS_LCD_MQTT_BROKER_HOST=10.32.251.30
# WANOS_LCD_MQTT_PASSWORD=...
```

Reboot (I2C overlay + group membership):

```bash
sudo reboot
```

---

## 4. Hardware check

```bash
sudo i2cdetect -y 1
# Expect addresses 26 and 27 in the grid.
```

---

## 5. Deploy + start

From Windows:

```text
helpers\wanos-sync.bat run lcd
```

On the LCD Pi:

```bash
# After sync: scripts land in /home/wannes/wanos/
chmod +x ~/wanos/startwanoslcd.sh ~/wanos/wanoslcdlog.sh
./startwanoslcd.sh restart
./startwanoslcd.sh status
```

Or:

```bash
sudo systemctl restart wanos-lcd-agent.service
systemctl status wanos-lcd-agent.service --no-pager
```

Logs (LCD Pi has **only** choices **1** and **2** — no debug/automation/power/iwhw):

| # | Channel | Path / command | Sync? |
|---|---------|----------------|-------|
| 1 | Console | `journalctl -u wanos-lcd-agent -f` / `./wanoslcdlog.sh log 1` | **No** |
| 2 | App file | `/var/log/wanos/wanos.log` / `./wanoslcdlog.sh log 2` | **Yes** (`wanos*`) |

Pull logs to OneDrive `logs\lcd-agent`:

```text
helpers\wanos-sync.bat run lcd
helpers\wanos-sync.bat logcopy lcd
```

(`run` always logcopies into `C:\data\git\wanos\_lcd-agent\docs\logs` — gitignored. Mode `logcopy` does log pull + that copy only, no mirror.)

---

## 6. MQTT smoke

With WanOS main publishing LCD topics, screens should update. Admin → System Commands → **Show Easter Egg** hits screen 2.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Permission denied (publickey)` | §1 pubkey on `.51` |
| Empty `/var/log/wanos` after sync | Agent not started / no writes yet; restart service |
| I2C empty | Reboot after bootstrap; check wiring / `i2c` group |
| MQTT connect fail | Host/password in `/home/wannes/wanos/.env`; broker allows LAN |
| Sync deletes unexpected files | LCD `--delete` only under `/home/wannes/wanos`; `wanos_venv` and `.env` are excluded |
| Old `/etc/default/wanos-lcd-agent` | Unused now — move keys into `/home/wannes/wanos/.env`, then remove the default file |
