# --- file: docs/todo/ops7-fresh-install.md ---
# Ops7 — Fresh main Pi install (OS / PHP / Python)

**Status:** open · **Size:** high · **Pipeline:** [`pipeline.md`](pipeline.md) Sequence / Manual § Ops7  
**Date:** 2026-10-22 (CET)  
**Hardware:** Raspberry Pi 4 Model B Rev 1.5 · role: WanOS **main** + WLW co-host at **`10.32.251.30`**  
**Product guide (as-is / operator):** [`docs/bootstrap-main-pi.md`](../bootstrap-main-pi.md)  
**WLW follow-on:** sibling repo **be90webserver** — `docs/todo/ops7-fresh-install.md` (overlay only) + `docs/bootstrap-host.md` (mention)

**Absorbs:** former **Ops2** (Pi Python 3.12 vs 3.13 assess) — superseded by OS lock (Trixie → system **Python 3.13**).

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

## DoD (stub — expand at kickoff)

- [ ] Locks above recorded; Ops2 Sequence/Manual closed as superseded
- [ ] Product doc [`bootstrap-main-pi.md`](../bootstrap-main-pi.md) matches scripts
- [ ] be90webserver pointer + mention file accurate
- [ ] Implement (when commanded): scripts drop Samba; install PHP; gate version
- [ ] Pi smoke: OS, `php -v`, `python3 -V`, WanOS, then WLW overlay smoke
- [ ] Soak: sauna SHT11 + pulse inputs + key wheels on 3.13
- [ ] **Last DoD:** audit all `docs/**/*.md` + root README vs shipped host

---

## Open (do not assume)

1. Restore `/var/lib/wlw` vs A1 re-seed (WLW)?
2. Reuse LE vs fresh certbot?
3. Any Trixie package/path breaks vs current Bullseye WanOS install (discover at implement/smoke)?
