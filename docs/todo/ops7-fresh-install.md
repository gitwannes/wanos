# --- file: docs/todo/ops7-fresh-install.md ---
# Ops7 — Fresh main Pi install (OS / PHP / Python)

**Status:** coding · **Size:** high · **Pipeline:** [`pipeline.md`](pipeline.md) Sequence **#1** / Manual § Ops7  
**Date:** 2026-10-22 (CET) · **Kickoff:** 2026-10-22 · **Scripts implement:** 2026-10-22  
**Hardware:** Raspberry Pi 4 Model B Rev 1.5 · role: WanOS **main** + WLW co-host at **`10.32.251.30`**  
**Product guide (as-is / operator):** [`docs/bootstrap-main-pi.md`](../bootstrap-main-pi.md)  
**WLW follow-on:** sibling repo **be90webserver** — `docs/todo/ops7-fresh-install.md` (overlay only) + `docs/bootstrap-host.md` (mention)

**Absorbs:** former **Ops2** (Pi Python 3.12 vs 3.13 assess) — superseded by OS lock (Trixie → system **Python 3.13**).

**Prereqs:** none blocking (same Pi, re-image). WLW overlay + **B30** wait on this host Done. LCD `.51` / kiosk site out of scope.

---

## Goals

1. Re-image `.30` to the **latest** official Raspberry Pi OS for this board.
2. Host packages: **highest current** PHP (patched for PHP2Shell) + **Trixie system Python** for WanOS venv.
3. One incorporated **main-Pi** bootstrap doc + script path in **this repo** (WanOS + PHP apt + shared Nginx baseline).
4. **No Samba** (unused; sync is rsync/SSH).
5. After host green: WLW additive overlay in **be90webserver** (not flash).

**Out of scope:** LCD Pi `.51` (stays as-is / L1); unfinished kiosk **website** (not a separate Pi); in-place Bullseye→Trixie (re-image only).

---

## Locked decisions (operator 2026-10-22)

| # | Topic | Lock |
|---|---|---|
| 1 | OS | **Raspberry Pi OS Lite (64-bit), Debian 13 Trixie** — latest official for Pi 4 (image line as of 2026-10). |
| 1b | PHP | Trixie apt **8.4**; gate **≥ 8.4.27** (PHP2Shell). Do not expose `:443` until verified. |
| 1c | Fallback | **Bookworm 64-bit** only if WanOS fails on Trixie → PHP **8.2** (≥ **8.2.35**). |
| 1d | Python | Trixie **`python3` = 3.13** for WanOS `wanos_venv` + WLW SSH bridge. Soak GPIO/SHT11/wheels in DoD. |
| 2 | Host / IP | **Same** Pi + **`10.32.251.30`**. LCD **`.51`** unchanged. |
| 3 | SSH | **Renew** keys (do not copy old card `wlw_ed25519` / known_hosts). |
| 4 | Co-tenancy | Flash → **this Ops7 host baseline** → sync WLW → be90webserver overlay. |
| 5 | Samba | **Do not install** (not used). |
| 6 | Ownership | Host flash / PHP apt / system Python / WanOS baseline = **wanos**. WLW nginx site + `/var/lib/wlw` + bridge unit = **be90webserver** overlay. |
| 7 | Ops2 | **Folded into Ops7** — no separate 3.12-vs-3.13 assess row. |
| 8 | LE certs | **Re-issue** with certbot on new OS (do not reuse old-card live files). |
| 9 | Nginx / host apt | **Automate as much as possible** in wanos phase1 (`nginx`, certbot tooling, PHP stack). |
| 10 | `smb.conf` | **Remove** from bootstrap tree at implement (not leave unused). |
| 11 | PHP apt ownership | **wanos only.** Strip PHP apt install from WLW `wlw_bootstrap` / `apt-packages.txt` at implement (overlay keeps FPM detect, nginx site, state dirs). |
| 12 | WLW state | Prefer **restore** from sync-pulled DBs + offline **`.env`** (operator has `.env` backup — Q1b). **A1 re-seed** only if auth restore impossible. |
| 13 | WLW state pull set | **Pull only** (not mirror): `wlw.sqlite`; `budget*.sql`/`budget*.zip`; `budget/*.sqlite`; `budget/*.json`; `obio/credentials.json`. Drop legacy `budget.sqlite`. Engine allows `.sqlite`/`.sql`/`.zip`/`.json` (**shipped** in sync tool). |

### PHP2Shell

- CVEs: **CVE-2026-109618**, **CVE-2026-109619**.
- Patched builds include **8.4.27** / **8.2.35** (+ higher). App cannot patch — **OS packages** must.
- DoD: `php -v` ≥ patched micro-release before public `:443`.

---

## Verbatim (operator)

**2026-10-22 (this triage):**

> goal = upgrade to PHP 8.\<highest\>  
> following the PHP2Shell incident  
> look at this repo - also look at the be90webserver (wlw) repo: look at the pipeline there, and especially ops7-fresh-install.md  
> look at both bootstrap MD files, all bootstrap scripts in \helpers\bootstrap - create 1 incorporated bootstraip documentation & script, since both wanos and be90webserver run on the same hardware  
> when done, pull out all bootstrap info from be90webserver repo and put a single mention file in there indicating that bootstrap happens in this repo  
> take all you need and create a new phase in this repo - main goal: fresh install, highest Python & PHP versions available now  
> …  
> samba isn't used (confirm)  
> goal will be to install the latest OS available for Raspberry Pi 4 Model B Rev 1.5  
> … fold ops2 into ops7  
> rewrite ops7 in wlw repo docs to reflect this  
> triage - write all docs in both repos

**Earlier Ops7 locks (be90webserver prep, carried):**

> 1: Raspberry Pi 4 Model B Rev 1.5: which OS is recommended?  
> 2: same  
> 3: renew SSH keys  
> right, wlw runs on the same pi that wanos does

**Ops2 (absorbed) verbatim 2026-08-27:**

> triage this move to 3.13 into pipeline - don't fix on 3.13 - assess will be a big task, if 3.12 is eventually the better option, we will go for that

*(Superseded: latest OS = Trixie ⇒ system Python 3.13; soak replaces the open assess.)*

---

## Delivery scope (implement when commanded)

| Deliverable | Notes |
|---|---|
| [`docs/bootstrap-main-pi.md`](../bootstrap-main-pi.md) | Canonical operator cutover (A–F host slices) |
| `helpers/bootstrap/backend/*` | Unify: drop Samba; add PHP-FPM apt + version gate; keep phase1/2 WanOS path |
| Badge / architecture Python | Align to **3.13** after ship (soak first) |
| WLW | Overlay stays in be90webserver; host mention file only |

**Not this ship:** rewriting kiosk panel bootstrap; LCD `.51` install; B30 SQLCipher.

---

## Cutover checklist (host — this repo)

### A — Backup (old card)

- [ ] Deco 80/443 → `.30`
- [ ] Offline WanOS state (operator practice)
- [ ] Offline `/var/lib/wlw/` (for WLW restore) + optional LE files
- [ ] Do not rely on old SSH keys

### B — Flash

- [ ] Imager → **Lite 64-bit Trixie**; user `wannes`; SSH; CET; static **`10.32.251.30/24`**
- [ ] `apt update && full-upgrade`
- [ ] Verify Trixie + `aarch64`

### C — WanOS + host packages (Ops7 scripts)

- [ ] Phase 1/2 (no Samba); PHP-FPM + extensions; `php -v` ≥ **8.4.27**
- [ ] `python3 -V` → **3.13.x**; create `wanos_venv`; `wanos.service`; Nginx `app.wanos.be`
- [ ] Mosquitto / Z-Wave Docker / ACME-DNS as current install guide
- [ ] Smoke WanOS on LAN

### D–F — WLW

Hand off to be90webserver Ops7 overlay (sync → `wlw_bootstrap.sh` → keys/certs/AIS → smoke).

---

## Kickoff (2026-10-22)

### Prereqs / gates

| Check | Result |
|---|---|
| In pipeline Sequence / Manual | Yes — Ops7 open/high |
| Ops2 folded | Yes — superseded |
| Docs triage present | Yes — this file + `bootstrap-main-pi.md` + WLW pointer |
| Blocked on other letters | No |
| Code allowed | **No** until operator says `implement` / `ship` / `patch` |

### Verified (repo / locks)

- Same Pi `.30`; Trixie Lite 64-bit; PHP ≥ 8.4.27; Python 3.13; no Samba; re-image only.
- Host ownership = wanos; WLW = additive overlay after host green.
- Phase1 still **installs Samba** + enables `smbd` — must change at implement.
- `apt-packages.txt` has **no PHP/nginx** yet; WLW `apt-packages.txt` still lists `php-*` / `nginx` for overlay idempotency.
- Nginx/`app.wanos.be` / Mosquitto / Z-Wave / ACME-DNS are largely **manual** in `wanos-install-backend.md` today (not fully in phase1/2).
- Path segment `bootstrap` excluded from main `wanos-sync` — first-boot still needs SCP/copy of helpers.

### Implement plan

1. [x] `apt-packages.txt`: no samba; PHP-FPM + nginx + certbot + extensions
2. [x] `wanos_bootstrap_phase1.sh`: no Samba; PHP enable + version gate; purge leftover samba
3. [x] Delete `smb.conf`
4. [x] Phase2: print `python3 -V`; sync hint (no Samba)
5. [x] Docs: `wanos-install-backend.md` + `bootstrap-main-pi.md` + WLW bootstrap
6. [x] WLW: strip PHP/nginx apt; require wanos phase1
7. [x] Sync state pull `.zip`/`.json`/`obio/credentials.json`
8. [ ] Cutover smoke + 3.13 soak; WLW restore + overlay + smoke; Last DoD docs audit

### DoD (kickoff)

**Docs (prep — largely Done at triage):**

- [x] Locks recorded; Ops2 superseded in pipeline
- [x] Product [`bootstrap-main-pi.md`](../bootstrap-main-pi.md) + WLW `bootstrap-host.md` / Ops7 pointer
- [x] Product docs match scripts (no Samba; PHP gate) — **2026-10-22** (cutover smoke still open)

**Code / host (after `implement`):**

- [x] Phase1/apt scripts: no Samba; PHP-FPM stack + gate in wanos (**2026-10-22** — not yet run on Pi)
- [ ] Fresh flash smoked end-to-end (phase0 → phase1/2 → WanOS green)
- [ ] Live `php -v` ≥ **8.4.27** before public PHP `:443`
- [ ] Live `python3 -V` → **3.13.x**; `wanos_venv` works; `wanos.service` up
- [ ] WanOS LAN smoke (`app.wanos.be` / operator checks)
- [ ] Soak: sauna SHT11 + pulse inputs + critical wheels on 3.13
- [x] Sync: `[WlwSqlitePullFiles]` + engine pull `.zip`/`.json`/`obio/credentials.json`; no legacy `budget.sqlite` (**2026-10-22**)
- [ ] Hand off: restore state + `.env`; re-issue LE; renew keys; WLW overlay smoke
- [ ] **Last DoD:** audit all `docs/**/*.md` + root README vs shipped host (both repos as touched)

---

## Kickoff answers (operator 2026-10-22) — locked

| # | Answer | Lock / note |
|---|---|---|
| **Q1** | Prefer **restore** when sync/PC state usable | A1 only if auth cannot be restored |
| **Q1b** | **`.env` is backed up** (operator) | Sync still never pulls `.env` — offline copy is SoT for secrets |
| **Q2** | **Re-issue** LE after reflash | No old-card `/etc/letsencrypt` reuse |
| **Q3** | Automate as much as possible | wanos phase1: `nginx` + certbot tooling + PHP |
| **Q4** | Remove SMB | apt + phase1 + **delete `smb.conf`** |
| **Q5 / Q5b** | Sync **pull** (not mirror) set locked | See table; config + engine updated |
| **Q6** | wanos does OS-level | Strip PHP apt from WLW overlay (still at full Ops7 implement) |
| **Q7** | Include `/var/lib/wlw/obio/credentials.json` | **Yes** — in pull list |

### What is A1?

**A1** (be90webserver phase A, Done) = first-time **auth seed**: `/var/lib/wlw/.env` + `seed_wlw_user.php` + new TOTP. Not a backup. Guide: be90webserver `wlw_bootstrap.md` § A1.

### Sync backup coverage (locked — code shipped)

**Pull only** → OneDrive `logs\wlw\state\` (`[WlwSqlitePullFiles]` + `Invoke-WlwSqlitePullJob`):

| Include | Exclude |
|---|---|
| `/var/lib/wlw/wlw.sqlite` | **`.env`** (never sync; operator offline backup) |
| `/var/lib/wlw/budget*.sql` | Whole-dir mirror of `/var/lib/wlw/` |
| `/var/lib/wlw/budget*.zip` | Legacy **`/var/lib/wlw/budget.sqlite`** (removed) |
| `/var/lib/wlw/budget/*.sqlite` | |
| `/var/lib/wlw/budget/*.json` | |
| `/var/lib/wlw/obio/credentials.json` | |

**WanOS:** `[StatsRepoPull]` autos; logs/session per sync docs; WanOS `.env` not mirrored.

### Remaining open (kickoff)

**None** for sync/state. Full Ops7 host bootstrap (Samba out / PHP+nginx in / WLW overlay strip) still waits on **`implement Ops7`**.

**Still locked:** Trixie Lite; PHP ≥ 8.4.27; Python 3.13; same IP; renew SSH; no Samba; LCD/kiosk OOS; re-image only; LE re-issue; automate host apt.
