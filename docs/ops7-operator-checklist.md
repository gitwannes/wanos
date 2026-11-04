# --- file: docs/ops7-operator-checklist.md ---
# Ops7 — operator checklist (cutover)

Telegram-style. Delivery: [`todo/ops7-fresh-install.md`](todo/ops7-fresh-install.md) · host: [`bootstrap-main-pi.md`](bootstrap-main-pi.md) · long form: [`../helpers/bootstrap/backend/wanos-install-backend.md`](../helpers/bootstrap/backend/wanos-install-backend.md) · WLW: be90webserver Ops7 pointer.

**Do not** open public PHP `:443` until `php -v` ≥ **8.4.27**.

**Pre-cutover (old card):** Bullseye PHP 7.4 PHP2Shell bridge = **Ops8** (**Done 2026-11-04**) — [`ops8-operator-checklist.md`](ops8-operator-checklist.md). Discarded with the old SD at flash.

---

## A — Before pull card

- [ ] Deco 80/443 → `.30` (or leave closed)
- [ ] `wanos-sync` **run** (main) + **run wlw** — fresh pulls
- [ ] Offline copy `/var/lib/wlw/.env` (sync never pulls it)
- [ ] Confirm WLW state under OneDrive `logs\wlw\state\` (sqlite / budget* / obio json)
- [ ] **Z-Wave backup (mandatory, operator-manual)** — not in wanos-sync  
  - Path: Pi `/opt/zwave-js-ui` → PC (e.g. OneDrive / USB)  
  - Prefer: `docker stop zwave-js-ui` then  
    `rsync -a wannes@10.32.251.30:/opt/zwave-js-ui/ <backup>\zwave-js-ui\`  
  - Verify store / NVM / `nodes.json` (or equiv) before flash  
  - Do **not** pull the card without this
- [ ] Optional offline: Mosquitto `st.pwd`, WanOS `.env` (LE = re-issue anyway)

---

## B — Flash

- [ ] Imager → Pi 4 → **Lite 64-bit Trixie** · user `wannes` · SSH · CET · hostname `wanos`
- [ ] Static **`10.32.251.30/24`**
- [ ] First boot: `sudo apt update && sudo apt full-upgrade -y`
- [ ] `cat /etc/os-release` → Trixie · `uname -m` → `aarch64`

---

## C — Host + WanOS

- [ ] SCP `helpers/bootstrap/backend/*` (bootstrap path **not** mirrored) — at least: `wanos_bootstrap_phase1.sh`, `wanos_bootstrap_phase2.sh`, `apt-packages.txt`, `wanos.nginx.conf`, `mosquitto-st.conf`, `wanos.service`, `docker-compose.yml`
- [ ] `sudo ./wanos_bootstrap_phase1.sh` → PHP gate · nginx `app.wanos.be` site · Mosquitto apt+conf · no Samba
- [ ] Reboot
- [ ] `wanos-sync` **run** → `/home/wannes/wanos`
- [ ] Restore WanOS `.env` / configs as needed
- [ ] `./wanos_bootstrap_phase2.sh` (as `wannes`) → venv · **`wanos.service`** · nginx refresh (LE if present)
- [ ] Mosquitto **`st.pwd`** (operator): `mosquitto_passwd -c …` or restore offline → `systemctl start mosquitto`
- [ ] Docker + Z-Wave (**operator**):
  - [ ] Install Docker · `docker` group for `wannes`
  - [ ] **Z-Wave restore:** PC backup → `/opt/zwave-js-ui` **before** compose up
  - [ ] Confirm stick path in `docker-compose.yml` (`/dev/serial/by-id/…`)
  - [ ] `docker compose up -d` · UI `:8091` · nodes match pre-cutover
- [ ] ACME-DNS + LE for **`app.wanos.be`** (re-issue · Nomeo) → re-run phase2 (or phase1 nginx) to point site at LE
- [ ] Smoke WanOS LAN / `https://app.wanos.be`

---

## D — WLW overlay

- [ ] `wanos-sync` **test wlw** / **run wlw**
- [ ] `php -v` ≥ **8.4.27** · FPM sock up
- [ ] `sudo bash ~/be90webserver/helpers/bootstrap/wlw_bootstrap.sh`
- [ ] Restore `/var/lib/wlw` from sync state + offline `.env` (A1 only if auth dead)
- [ ] **GoogleAuthenticator:** pull latest PHP 8.x–safe class from maintained fork  
  [sethadam1/GoogleAuthenticator](https://github.com/sethadam1/GoogleAuthenticator)  
  → replace `be90webserver/app/GoogleAuthenticator.php` (keep `PHPGangsta_GoogleAuthenticator` / verifyCode / createSecret behaviour; drop `${width}` path). Then `run wlw` again if edited on PC.
- [ ] Overlay `nginx` mode if templates changed

---

## E — Keys / certs / AIS

- [ ] Renew SSH keys (Ops3-style) — do **not** copy old-card `wlw_ed25519`
- [ ] Re-issue LE for WLW hostnames (no old-card `/etc/letsencrypt` reuse)
- [ ] Bridge + `/wss/` smoke
- [ ] `wlw_obio_setup.sh` + restore `credentials.json` if used
- [ ] H4 sshd Match CIDRs

---

## F — Smoke

- [ ] Public login OTP + TOTP
- [ ] LAN `:9443`
- [ ] WanOS still healthy
- [ ] Budget / gateway / SSH tiles
- [ ] Z-Wave nodes present (restored store)
- [ ] Keep `:443` closed until PHP gate + smoke green

---

## Done when

- Host Trixie · PHP ≥ 8.4.27 · Python 3.13 · no Samba
- WanOS + Z-Wave + MQTT + `app.wanos.be` up
- WLW overlay + state + GA file refreshed · public smoke OK
- Last DoD docs audit (both repos)
