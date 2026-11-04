# --- file: docs/bootstrap-main-pi.md ---
# Main Pi fresh install (WanOS + shared host for WLW)

**Role:** Raspberry Pi 4 Model B · LAN **`10.32.251.30`** · WanOS backend + shared Nginx/PHP host for **WLW** (be90webserver).  
**Delivery:** [`docs/todo/ops7-fresh-install.md`](todo/ops7-fresh-install.md) (**Ops7**).  
**Cutover runbook (short):** [`ops7-operator-checklist.md`](ops7-operator-checklist.md).  
**Pre-Ops7 PHP2Shell bridge (live Bullseye 7.4):** **Done 2026-11-04** — [`ops8-operator-checklist.md`](ops8-operator-checklist.md) · archive [`todo/_archive/ops8-php2shell-bridge.md`](todo/_archive/ops8-php2shell-bridge.md) · [`../helpers/ops8-php2shell/`](../helpers/ops8-php2shell/).  
**LCD Pi (`.51`):** separate — [`_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`](../_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md).  
**WLW app overlay (after this host is green):** be90webserver `helpers/bootstrap/wlw_bootstrap.md` + `docs/todo/ops7-fresh-install.md` (pointer).

This is the **incorporated** operator guide for the shared main Pi. Scripted pieces live under [`helpers/bootstrap/backend/`](../helpers/bootstrap/backend/). Day-to-day code sync: [`wanos-sync.md`](wanos-sync.md) (rsync/SSH — **no Samba**).

---

## Target platform (Ops7 locks)

| Item | Target |
|---|---|
| OS | **Raspberry Pi OS Lite (64-bit), Debian 13 Trixie** (latest official for Pi 4) |
| PHP | **8.4**, patched **≥ 8.4.27** (PHP2Shell: CVE-2026-109618 / CVE-2026-109619) |
| Python | Trixie system **`python3` = 3.13** → WanOS `wanos_venv` |
| Samba | **Not installed** (unused; sync is rsync over SSH) |
| Fallback | Bookworm 64-bit + PHP ≥ 8.2.35 only if Trixie blocks WanOS |

**Until Ops7 cutover**, the live Pi remains Bullseye **PHP 7.4** with **Ops8** bridge (mitigation + B2 binary replace; `dpkg` may still show `deb11u12`) — not this page’s Trixie inventory.

---

## Order of operations

```text
A  Sync pull (wanos + wlw); Z-Wave /opt/zwave-js-ui backup = operator rsync; offline .env
B  Flash Trixie Lite 64-bit → static 10.32.251.30 → full-upgrade
C  phase1 (PHP/nginx site/Mosquitto apt) → sync → phase2 (venv/wanos.service/nginx refresh)
   then operator: st.pwd, Z-Wave restore+Docker, ACME-DNS LE
D  wanos-sync wlw → overlay; restore DBs + .env; refresh GoogleAuthenticator (operator)
E  Renew SSH keys; re-issue LE; AIS sidecar as needed
F  Smoke WanOS + WLW (+ Z-Wave nodes)
```

Tick-list: [`ops7-operator-checklist.md`](ops7-operator-checklist.md).

Re-image only — **no** in-place Bullseye → Trixie upgrade.

---

## Phase 0 — Flash (operator)

1. Raspberry Pi **Imager** → hardware **Pi 4** → **Raspberry Pi OS Lite (64-bit)** / **Trixie**.
2. Customisation: user **`wannes`**, SSH on, locale/timezone **CET**, hostname e.g. `wanos`.
3. Prefer ethernet; set static **`10.32.251.30/24`** after first boot (or Imager if used).
4. First boot: `sudo apt update && sudo apt full-upgrade -y`.
5. Verify: `cat /etc/os-release` → Trixie; `uname -m` → `aarch64`.

Copy bootstrap helpers onto the Pi (path segment `bootstrap` is **excluded** from main `wanos-sync` mirror — SCP or one-shot copy into `~/` / tree as today). Then run Phase 1/2 scripts from [`helpers/bootstrap/backend/`](../helpers/bootstrap/backend/).

**Long-form walkthrough** (ACME-DNS LE, Z-Wave Docker, hardware checks): [`helpers/bootstrap/backend/wanos-install-backend.md`](../helpers/bootstrap/backend/wanos-install-backend.md). Cutover ticks: [`ops7-operator-checklist.md`](ops7-operator-checklist.md). Prefer this page for locks + order; checklist for A–F.

---

## Phase 1–2 — Host + WanOS (this repo)

| Script / file | Intent |
|---|---|
| `wanos_bootstrap_phase1.sh` | apt (nginx + PHP-FPM + **mosquitto**), PHP gate, **`app.wanos.be` nginx site**, Mosquitto conf, UART/BT, log2ram, sudoers — **no Samba** |
| `apt-packages.txt` | Host packages (PHP + nginx + certbot + mosquitto; no samba) |
| `wanos.nginx.conf` | Template → `/etc/nginx/sites-available/wanos` (self-signed until LE) |
| `mosquitto-st.conf` | Deployed to `/etc/mosquitto/conf.d/`; **`st.pwd` = operator** |
| `wanos_bootstrap_phase2.sh` | venv + RFX udev + **install/enable `wanos.service`** + nginx site refresh (prefer LE) |
| `wanos.service` | uvicorn via venv (installed by phase2) |
| ACME-DNS first LE | Still operator (Nomeo CNAME); then re-run phase2 to swap certs |

**PHP gate (host DoD):** phase1 exits non-zero unless `php -v` ≥ **8.4.27** (or ≥ **8.2.35** on Bookworm fallback).

**Python soak (host DoD):** sauna SHT11 + pulse inputs + critical wheels on 3.13.

---

## After host green — WLW

1. From workstation: `helpers\wanos-sync.bat test wlw` then `run wlw`.
2. On Pi: `sudo bash ~/be90webserver/helpers/bootstrap/wlw_bootstrap.sh` (additive overlay only).
3. Follow be90webserver Ops7 overlay checklist (state restore, keys, LE, AIS, smoke).

Host flash and PHP/Python OS packages are **not** owned by the WLW repo — see be90webserver `docs/bootstrap-host.md`.

---

## Related

| Topic | Doc |
|---|---|
| Ops7 operator checklist | [`ops7-operator-checklist.md`](ops7-operator-checklist.md) |
| Sync / first deploy | [`wanos-sync.md`](wanos-sync.md) |
| Z-Wave middleware | [`integration_zwave.md`](integration_zwave.md) § store backup |
| Architecture | [`architecture.md`](architecture.md) |
| LCD agent install | [`_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`](../_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md) |
| Ops7 delivery | [`todo/ops7-fresh-install.md`](todo/ops7-fresh-install.md) |
