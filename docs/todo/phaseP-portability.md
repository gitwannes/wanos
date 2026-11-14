# ⚡ WanOS Phase P — Other homes / portability

Make WanOS **usable for another house**: engine stays generic; **home-specific** facts live only in clearly marked config (and docs). Today much of Borsbeek is YAML **and** duplicated in Python/HTML.

**Status:** Spec **stub**. **Very low prio** — last in pipeline (after **F** / **B15–B18**). **Assess at kickoff** before any extraction ship.

**Related:** Cursor rule [`.cursor/rules/general-purpose-code.mdc`](../../.cursor/rules/general-purpose-code.mdc). Sauna/IR handlers vs automations → **B17** (subset; do not double-implement). Sequence → [`pipeline.md`](pipeline.md).

**DoD convention:** **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## Operator request (verbatim)

> create a pipeline item, very low prio, which goal is to make wanos useable for other homes as well, in which case it needs to be very clear which config is home-specific - lots of changes need to be made, put the list above, both what you suggested in previous answers and my list in the in-scope -

**Operator list (verbatim, 2026-08-14 Q4):**

> environment-specific = ip address of py, url, username, all idxs, hue key path, all credentials, sauna & ir: sht sensor use, number & config, sauna heater control, etc

**Process lock (2026-08-14 Q3):** when moving hardcoded site facts into config — **propose, ask, do not apply** until operator confirms. Collaboration-standards still win (no unsolicited patches).

---

## Goal

1. A second install can run the **same code** with **different home config**.
2. Operators can see **at a glance** which files/keys are home-specific vs engine.
3. No new hardcodes of the in-scope list (rule already always-on).

**Kickoff first:** inventory + docs (what is home vs engine). Code extraction is **many ships** — split only at kickoff (not this triage).

---

## In scope (home-specific — config **and** current code leaks)

### Operator list

* Pi **IP**, **URLs**, **usernames**
* **All IDX** numbers
* **Hue key path**
* **All credentials**
* **Sauna / IR:** SHT11 use, sensor **count** and wiring/config, **heater control**, and similar plant-specific control

### Config files (correct place today — must stay clearly “home”)

| File | Home content |
|---|---|
| `config.yaml` | `10.32.251.x` (Epson, Sonos, Onkyo), RFX names/hex, OWM `Borsbeek,BE`, MQTT user, kWh/water/PC power links, sauna/IR/bathroom1 PID & times, blinds travel, env schedule clocks, IDX **band** comments |
| `config_hardware.yaml` | GPIO pins, SHT11 count/wiring (sauna high/low, cinema, badk 1e), 3-phase sauna + IR + safety relays, doors, `indicator_lights` Hue IDXs |
| `config_hue.yaml` | Bridge IP, Hue group/device UUIDs |
| `config_zwave.auto.yaml` | Z-Wave node map (Pi-owned) |
| `entity_registry.auto.yaml` | entity_id ↔ idx |
| `automations.auto.yaml` | Rules, hide, auto-off, product types |
| `config_hue_presets.auto.yaml` | Colour presets |
| `config_lab.yaml` | Lab boot seeds keyed to this house’s IDXs |
| `helpers/wanos-sync.config.txt` | Pi host, `wannes`, remote root |
| Bootstrap / sudoers docs | Linux user, unit names |
| `.env` (not in git) | OWM, MQTT password, Hue application key, `SECRET_KEY` |

### Code that still assumes this house (extract or parameterize)

* `state_manager.py` — sauna composite **0.7×20001 + 0.3×20002**, hum from 20001, virtual **20101**; SHT locks `[20001, 20002]`; lab inject `[20001–20004]`
* `logic/history_ids.py` — `SAUNA_CALC_IDX = 20101`; **`HOST_HISTORY_IDXS`** allowlist
* `logic/sensor_history_manager.py` — **`SENSOR_META`** (idx → label/kind/unit) — see **P1**
* `hardware/actuators.py` — **topology** fixed: 3 sauna phases + IR + one safety GPIO (pins from config)
* `core/well_known_entities.py` — sauna door/probes, badk 1e vent/hum, Epson, SSR/WISC 5V
* `logic/automation_rules.py` — shower `WATER_PULSE` → badk 1e vent ON only; humidity band → Library rule **`Badk 1e ventilatie`** (Ship **B5** ✅ **2026-08-17**)
* `logic/history_manager.py` — doors **10001 / 10002**
* `core/entity_id_list.py` — IDX band → origin
* WISC / kiosk / Admin lab **HTML/JS** — hardcoded IDXs (`10001`, `51002`, `71036`, `72004`, `71038`, `20001`…, `72001`, …) and house copy
* Helpers: `hue_discovery.py` default IP; sync/bootstrap Pi identity

### Grey (call at kickoff)

* Auth tokens `user` / `kiosk` in `config.yaml`
* Timezone `Europe/Brussels`
* Overlap **B17** (sauna/IR hardcoded → automation assess)
* **G9–G13** new vendor bridges (IPs, tokens, device maps) — home pack when those ships land

---

## Out of scope (this triage)

* Implementing extraction now
* Inventing a second config system or settings UI unless operator asks at kickoff
* Changing Blockly cluster / F / G ships to wait on **P**
* Deleting working Borsbeek config

---

## Assess at kickoff

* Doc shape: which files are “home pack” vs engine (README / `docs/` inventory).
* Ship split (docs-only first vs code).
* Whether well-known eids stay as **names** in code (resolved via registry) vs all plant policy in YAML/rules.
* **B17** vs **P**: B17 may land first; **P** takes leftover plant-in-code.
* Sample `config.yaml` / hardware template without Borsbeek IPs (no secrets).
* **P1** first concrete extraction vs wait for full **P** inventory.

**P DoD (stub):** Kickoff assess recorded; home vs engine documented; extraction ships (if any) only after operator OK per item. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 P1 — Configurable sensor-history series 🔜 TODO

**Status:** open · size **high** · Sequence → [`pipeline.md`](pipeline.md)  
**Affinity:** Portability (hardcoded history contract → home config). Not Explorer chrome (**C**); not a new vendor bridge (**G**).

### Operator request (verbatim, 2026-09-10)

> triage this: we need to redesign this: now this is hardcoded, I need a configurable way of telling wanos which device to have history for and how

### Problem (today)

| Mechanism | Role | Pain |
|---|---|---|
| `SENSOR_META` in `logic/sensor_history_manager.py` | Hardcoded idx → `label` / `kind` / `unit` | Site IDXs + chart contract in Python |
| `HOST_HISTORY_IDXS` in `logic/history_ids.py` | Host/mains gauge allowlist | Same |
| `history.tracked_entities` in `config.yaml` | Opt-in entity_ids for utility ingest + History list | **Which** only — not **how** (kind/unit/ingest) |

Climate discovery and actuator `device_history` stay separate unless kickoff expands scope.

### Intent (delivery — lock at kickoff)

* One **config** place (prefer extend `history:` in `config.yaml`, not a second system / settings UI unless asked) that says **which** entity_ids get sensor-history **and how** (kind, unit, ingest mode: power W / absolute energy / fluid / host gauge / …).
* Remove (or shrink to engine defaults only) hardcoded `SENSOR_META` / `HOST_HISTORY_IDXS` site rows.
* Labels prefer live `device_metadata` / registry; config carries series contract, not house display names if avoidable.
* Product docs: [`docs/sensor_history.md`](../sensor_history.md).

### Out of scope (this triage)

* Implement / schema lock (needs **kickoff P1**)
* History UI redesign (**C**); HomeWizard-style power graphs (**C42**, ∥ this ship); actuator event history (**C36**); Sauna/IR History polish (**C33**)
* “Historize every device by default”

### P1 DoD (stub)

Kickoff locks config shape + migration of current Borsbeek rows; code reads config; `SENSOR_META` / host allowlist no longer site-hardcoded; docs match. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 P2 — sync: `[MirrorExcludeFiles]` for all three modes 🔜 TODO

**Status:** open · size **mid** · Sequence **#1** → [`pipeline.md`](pipeline.md)  
**Affinity:** Portability / deploy tooling (`helpers/wanos-sync.*`). Not product UI.

### Operator request (verbatim, 2026-09-15)

> put in triage for the sync-tool (in wanos repo) that the [MirrorExcludeFiles] section should be used for ALL three syncs

(Context from same thread: `ssh-term-full.js` was added under `[MirrorExcludeFiles]` but `wlw` ignored it because WLW/LCD use hardcoded `$WlwMirrorExcludeFiles` / `$LcdMirrorExcludeFiles` in `wanos-sync.ps1`.)

### Kickoff (2026-11-14) — verified facts

| Mode | Exclude source today |
|---|---|
| **main** | Config `[MirrorExcludeDirs]` + `[MirrorExcludeFiles]` |
| **lcd** | Hardcoded `$LcdMirrorExcludeDirs` / `$LcdMirrorExcludeFiles` in `.ps1` (small: `.git`, `docs`, `wanos_venv`, `__pycache__`, `.env*`, `*.pyc`) |
| **wlw** | Hardcoded `$WlwMirrorExcludeDirs` / `$WlwMirrorExcludeFiles` in `.ps1` — **must stay matched** to be90 `helpers/wlw-sync.sh` `EXCLUDE_DIRS` / `EXCLUDE_FILES` (pair rule) |

**Danger if naive union:** main config dir `bootstrap` would skip be90 `helpers/bootstrap/` on WLW. Main file excludes (`*.ps1`, `*.bat`, `*.auto.yaml`, `LICENSE`, …) are WanOS-shaped — not a drop-in for WLW.

**Interim (2026-09-15):** `ssh-term-full.js` duplicated in config **and** `$WlwMirrorExcludeFiles`.

**Prereqs:** none vs P3 (Done). Pair rule applies when WLW exclude lists change.

### Where excludes live today (inventory 2026-11-14)

| Mode | Dirs | Files |
|---|---|---|
| **main** | Config `[MirrorExcludeDirs]` in `helpers/wanos-sync.config.txt` | Config `[MirrorExcludeFiles]` same file |
| **lcd** | Hardcoded `$LcdMirrorExcludeDirs` in `helpers/wanos-sync.ps1` | Hardcoded `$LcdMirrorExcludeFiles` same |
| **wlw** (PC) | Hardcoded `$WlwMirrorExcludeDirs` in `helpers/wanos-sync.ps1` | Hardcoded `$WlwMirrorExcludeFiles` same |
| **wlw** (Pi pair) | `EXCLUDE_DIRS` in be90 `helpers/wlw-sync.sh` | `EXCLUDE_FILES` same (must match PC WLW) |

**main dirs (config):** `.git` `.cursor` `.idea` `.venv` `docs` `code-import` `bootstrap` `backup*` `logs` `temp` `_lcd-agent` `wanos_venv` `migration_venv` `billit_venv` `__pycache__` `sessionlog`

**main files (config):** auto.yaml / nvram / `.lgd-nfy0` / `*.db` / sync tooling (`*.bat` `*.ps1` …) / `LICENSE` / `*.md` / `.env*` / gitignore / zip/bak/tmp / `lg_webos_client_keys.json` / `ssh-term-full.js` …

**lcd (hardcoded):** dirs `wanos_venv` `__pycache__` `docs` `.git` · files `.env*` `*.pyc`

**wlw PC + Pi pair (hardcoded, matched):** dirs `.git` `.cursor` `docs` `__pycache__` `.venv` `aistudio-preview` `_archive` · files `.env*` `*.md` `.gitignore` `.gitattributes` `db+credentials` `logs` `ssh-term-full.js` `*.lnk` `_tmp*` `server.ts` `tsconfig.json` `metadata.json` `package.json`

### Kickoff locks (2026-11-14)

| # | Topic | Lock |
|---|---|---|
| 1 | Files | **One** `[MirrorExcludeFiles]` in `helpers/wanos-sync.config.txt` — all three PC modes |
| 2 | Dirs | **One** `[MirrorExcludeDirs]` same file — all three PC modes |
| 3 | LCD | Same exclusions config (no lcd-only list) |
| 4 / SSoT | **`wanos-sync.config.txt` = SSoT.** Pi WLW clone→live tool **moves** from be90 → **wanos** `helpers/` (same family as PC sync). `wlw-sync.sh` (new home) **reads that config** for excludes — no hardcoded EXCLUDE_* pair drift. Retire be90 copy (remove or one-line pointer). Docs + `wlw-sync-pair.mdc` both repos. |
| 5 | Sequence | Bump to **top** (**#1**) |
| **A** | `bootstrap` | Always mirror `helpers/bootstrap/**`. Not in exclude list. |
| **B** | Unified list shape (2026-11-14) | **Merge** all current excludes (main + lcd + wlw), **including `*.md`**, then **omit:** `bootstrap`, `aistudio-preview` (gone from git — obsolete exclude), `LICENSE`, `_lcd-agent`. Keep `*.ps1` excluded. |

### Locked unified exclude set (target)

**Dirs:** `.git` `.cursor` `.idea` `.venv` `docs` `code-import` `backup*` `logs` `temp` `wanos_venv` `migration_venv` `billit_venv` `__pycache__` `sessionlog` `_archive`  
**(not excluded):** `bootstrap`, `_lcd-agent` · **obsolete (do not re-add):** `aistudio-preview`

**Files:** `.env*` `*.md` `.gitignore` `.gitattributes` `ssh-term-full.js` `*.pyc` + main Pi-owned/runtime (`entity_registry.auto.yaml` `automations.auto.yaml` `config_hue_presets.auto.yaml` `wanos-nvram.json` `wanos-nvram.json.tmp` `.lgd-nfy0` `*.db`) + sync tooling (`wanos-sync.bat` `wanos-sync.ps1` `wanos-sync.config.txt` `*.bat` `*.rcj` `*.ps1`) + `entity_id-list.txt` + junk (`* - Copy.py` `*.zip` `dhcpcd.conf` `*.bak` `*.bak-*` `*.tmp`) + `lg_webos_client_keys.json` + wlw (`db+credentials` `logs` `*.lnk` `_tmp*` `server.ts` `tsconfig.json` `metadata.json` `package.json`)  
**(not excluded):** `LICENSE` (wanted on Pi)

### Still open

None for list shape — ready to implement when commanded.  

### Out of scope

* Changing RemoteRoot / SSH hosts
* P3 console quiet (Done)

### P2 DoD (stub)

Kickoff locks merge schema (remaining Qs closed); all three modes read the single config sections; dry-run proves `ssh-term-full.js` excluded on `wlw` via config alone; WLW pair lists stay matched; docs match. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## ✅ P3 — sync: quiet normal output (logs / sql / zip / LogCopy) — Done 2026-11-14

**Status:** Done · size **low** · Sequence → Done table in [`pipeline.md`](pipeline.md)  
**Affinity:** Portability / deploy tooling (`helpers/wanos-sync.*`).

### Operator request (verbatim, 2026-11-14)

> normal sync give too much info: I don't want to see a list of all logs or sqls or zips or whatever already copied - leave that for verbose (for both wanos and wlw):

### Kickoff locks (kept)

| # | Lock |
|---|---|
| 1–3 | Mirror / stats / log pulls still list in **normal** |
| 4 | WLW STATE: **normal** only when transferred; **verbose** every path |
| 5 | LogCopy / STATE **count** on done |
| 6 | `lcd` same as main / `wlw` |

### Shipped

| Area | Behaviour |
|---|---|
| LogCopy | Normal: `LOGCOPY: N files` + done; per-file only with `verbose` |
| WLW STATE | Normal: header/files only when rsync names the leaf + `(N transferred)`; verbose: every path |
| Docs | [`docs/wanos-sync.md`](../wanos-sync.md) § Normal vs `verbose` |

**Follow-up fix (2026-11-14):** duplicate rsync lines — `Invoke-Rsync` was returning the transfer array into the PS pipeline after `Write-SyncFileLine` (echo twice). Return only with `-CaptureOnly`; dedupe stdout/stderr; STATE counts only leaf-named transfers.

**Product reference:** [`docs/wanos-sync.md`](../wanos-sync.md). Code: `helpers/wanos-sync.ps1` (`Invoke-Rsync -CaptureOnly`, `Copy-WanosLogSnapshot`, `Invoke-WlwSqlitePullJob`).

### P3 DoD

[x] LogCopy quiet in normal (count + done); per-file only with `verbose` — main / lcd / wlw  
[x] WLW STATE: normal lists only actual transfers; no idle per-path spam  
[x] Mirror / stats / log pulls still list in normal  
[x] `docs/wanos-sync.md` matches  
[x] **Last DoD:** audit & update ALL `docs/**/*.md` (and root README) against shipped behavior (**2026-11-14**)  
