# --- file: docs/bootstrap-main-pi.md ---
# Main Pi fresh install (WanOS + shared host for WLW)

**Role:** Raspberry Pi 4 Model B · LAN **`10.32.251.30`** · WanOS backend + shared Nginx/PHP host for **WLW** (be90webserver).  
**Delivery:** [`docs/todo/ops7-fresh-install.md`](todo/ops7-fresh-install.md) (**Ops7**).  
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

**Until Ops7 cutover**, the live Pi may still be older (e.g. Bullseye). Do not treat this page as “current live inventory” until Ops7 ships.

---

## Order of operations

```text
A  Sync pull fresh (wanos + wlw); offline copy /var/lib/wlw/.env (+ obio creds if any)
B  Flash Trixie Lite 64-bit → static 10.32.251.30 → full-upgrade
C  This repo: host bootstrap (OS tune, nginx, PHP-FPM, WanOS venv/service, app.wanos.be) — no Samba
D  be90webserver: wanos-sync wlw → overlay (no PHP apt); restore DBs + .env
E  Renew SSH keys; re-issue LE via certbot; AIS sidecar as needed
F  Smoke WanOS + WLW
```

Re-image only — **no** in-place Bullseye → Trixie upgrade.

---

## Phase 0 — Flash (operator)

1. Raspberry Pi **Imager** → hardware **Pi 4** → **Raspberry Pi OS Lite (64-bit)** / **Trixie**.
2. Customisation: user **`wannes`**, SSH on, locale/timezone **CET**, hostname e.g. `wanos`.
3. Prefer ethernet; set static **`10.32.251.30/24`** after first boot (or Imager if used).
4. First boot: `sudo apt update && sudo apt full-upgrade -y`.
5. Verify: `cat /etc/os-release` → Trixie; `uname -m` → `aarch64`.

Copy bootstrap helpers onto the Pi (path segment `bootstrap` is **excluded** from main `wanos-sync` mirror — SCP or one-shot copy into `~/` / tree as today). Then run Phase 1/2 scripts from [`helpers/bootstrap/backend/`](../helpers/bootstrap/backend/).

**Long-form walkthrough** (Mosquitto, Docker/Z-Wave, ACME-DNS, `app.wanos.be` site): [`helpers/bootstrap/backend/wanos-install-backend.md`](../helpers/bootstrap/backend/wanos-install-backend.md). Prefer this page for locks + order.

---

## Phase 1–2 — Host + WanOS (this repo)

| Script / file | Intent |
|---|---|
| `wanos_bootstrap_phase1.sh` | apt (nginx + PHP-FPM), PHP version gate, UART/BT, log2ram, sudoers — **no Samba** |
| `apt-packages.txt` | Host package list (PHP stack + nginx + certbot; no samba) |
| `wanos_bootstrap_phase2.sh` | `wanos_venv` from system `python3` (3.13 on Trixie), requirements, RFX udev |
| `wanos.service` | uvicorn via venv |
| Nginx site / ACME-DNS | Still in install guide (phase1 installs **packages** only) |

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
| Sync / first deploy | [`wanos-sync.md`](wanos-sync.md) |
| Architecture | [`architecture.md`](architecture.md) |
| LCD agent install | [`_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`](../_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md) |
| Ops7 delivery | [`todo/ops7-fresh-install.md`](todo/ops7-fresh-install.md) |
