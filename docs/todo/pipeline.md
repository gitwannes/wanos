# WanOS — Implementation pipeline

Ordered backlog + closed history. Specs / DoD / locks live in the lettered phase files — not here.

**Last updated:** 2026-11-05 (**G24** Water-Link bridge Done; Ops7 Sequence #1)

---

## How to use

| Band | Meaning |
|---|---|
| **Done** | Closed (shipped or cancelled) — archive only |
| **Sequence** | All open work, in order. Status: **open** \| **coding** \| **hold** |
| **Ops** | Operator / site / non-lettered leftovers |

**Status:** `open` = eligible · `coding` = actively being implemented right now · `hold` = parked (prereq, assess-only, or pause).

**Size:** `low` · `mid` · `high` (delivery weight, not calendar days).

**Detail files:**

| Letter | Affinity | File |
|---|---|---|
| **B** | Blocky / Blockly / automations | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **C** | Operator shell | [`phaseC-shell.md`](phaseC-shell.md) |
| **D** | Device typing | [`phaseD-typing.md`](phaseD-typing.md) |
| **E** | Gmail + Messages (H5) | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **F** | Security bridge | [`phaseF-security.md`](phaseF-security.md) |
| **G** | Integrations | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **P** | Portability | [`phaseP-portability.md`](phaseP-portability.md) |
| **L** | Local character LCDs | [`phaseL-lcd.md`](phaseL-lcd.md) |
| **S** | Sauna plant (vent + start gate) | [`_archive/phaseS-sauna.md`](_archive/phaseS-sauna.md) (archived) |
| **Ops8** | PHP2Shell bridge (current Pi PHP, pre-Ops7) | [`_archive/ops8-php2shell-bridge.md`](_archive/ops8-php2shell-bridge.md) (archived) · product [`../ops8-operator-checklist.md`](../ops8-operator-checklist.md) |
| **Ops7** | Fresh main Pi (OS / PHP / Python) | [`ops7-fresh-install.md`](ops7-fresh-install.md) · product [`../bootstrap-main-pi.md`](../bootstrap-main-pi.md) |

**DoD (every phase):** Last step = audit & update all `docs/**/*.md` (+ root README) against shipped behavior.

**Domoticz Blockly goal** (locked 2026-08-12): match Domoticz L&F — detail → phaseB § Domoticz goal. Out of scope until **B20**: Time trigger; never: user variables / debug block.

When a phase finishes: Sequence → **Done**; trim Sequence only.

---

## Done

| Phase | Notes |
|---|---|
| **B0–B8** | Schema v2, rich actions, soft-hide, auto-off — Pi smoke through **2026-08-08** |
| **B10A** | Blocky editor trust — Pi smoke **2026-08-09** |
| **B10C** | Soft-hide action picker — Pi smoke **2026-08-09** |
| **B10B+D+E** | Events catalog + Library UX — Pi smoke **2026-08-10** |
| **C1 / C2 / C5** | Explorer · Admin · History — Pi smoke **2026-08-09** |
| **C6–C9** | History / Explorer / alerts / device-ref logs — Pi smoke **2026-08-10** |
| **B10F** | Automations UX polish — Pi smoke **2026-08-11** |
| **B1 / B9A** | Blockly parity closeout — Pi smoke **2026-08-12** |
| **C10** | Explorer/History polish — Pi smoke **2026-08-11** |
| **D1 + D2** | Timers & types + `zwave.*` / `rfx.*` — Pi smoke **2026-08-11** |
| **B10G** | Connection + load UX + `vNN` + hue preset scope — Pi smoke **2026-08-12** |
| **B10H** | Automations cold-load + SSE flicker — Pi smoke **2026-08-12** |
| **B10K + G3** | Timings + shutter/RFX polish; OWM 10′ — Pi smoke **2026-08-15** |
| **B10N** | Closed without code — covered by B10K (**2026-08-15**) |
| **C23** | SSE `SseClient` unhashable — with C18 (**2026-08-16**) |
| **C18** | Explorer Control live lag — Pi smoke **2026-08-16** |
| **C19** | History auto-refresh blank — Pi smoke **2026-08-16** |
| **C22** | Host CPU temp history — docs close-out **2026-08-16** |
| **Ops1** | log2ram / rsyslog cap — Pi smoke **2026-08-16** |
| **Ops2** | Pi Python 3.12 vs 3.13 assess — **superseded 2026-10-22** by **Ops7** (Trixie → system Python **3.13**) |
| **B2 / B9C** | Legacy-canvas bridge (temp/hum, shutters, audio) — Pi smoke **2026-08-16** |
| **G5** | `Cinema rolluik half` — docs close-out **2026-08-16** |
| **B3 / B19+B13** | Domoticz If/Do + Else-if — Pi smoke **2026-08-17** |
| **B4 / H4** | Nested AND/OR in Compare — Pi smoke **2026-08-17** |
| **B5 / H12** | Bathroom If/Else-if edge-cross — Pi smoke **2026-08-17** |
| **B9B** | H4+H12 done; H5 → **E** — close-out **2026-08-20** |
| **B21** | Cancelled **2026-08-21** — bare Else retired; no If+Else wake engine fix |
| **B11** | Cancelled **2026-08-22** — multi-flow not wanted; keep separate Library rows per rule |
| **B23** | Automations page polish (scoped reload + UX) — Pi smoke **2026-08-22** |
| **G15** | Evening twilight cross-day orphan ON (+ **C27** + Admin timeline UX in same ship) — Pi smoke **2026-08-22** |
| **C27** | Sunrise/sunset Admin + Explorer chrome — shipped with **G15** — Pi smoke **2026-08-22** |
| **B22** | Nested If/Do via branch `then:` (+ mixed leading/trailing Sets) — Pi smoke **2026-08-22** |
| **C12** | Post-C10 polish (duration ON, frost/dew, Hidden preset, …) — Pi smoke **2026-08-23** |
| **C16 + C24** | Day sliding 24 h over `hires_days` + temp/hum fullscreen AH/CI/CSV — **Pi smoke 2026-08-23** |
| **L1** | LCD Pi agent (`_lcd-agent`) + sync `lcd`/`logcopy` + WISC screen1 mirror — **Pi smoke 2026-08-24** |
| **C29** | Timers/Hidden NameError missing imports — **Pi smoke 2026-08-27** |
| **G16** | LG webOS TV power + Blockly apps — **Pi smoke 2026-08-27** |
| **C31 + C32** | Sauna/IR analytics + power model DB + Admin/WISC UX + IR PWM — **Pi smoke 2026-08-30** (combined ship) |
| **R1** | Source-available license (personal use OK, no redistribution) — **2026-09-01** |
| **C25** | Overlay dew% + compare + Admin Outside weather — **Pi smoke 2026-09-01** |
| **C34 + L3** | Sauna/IR analytics polish + LCD logging (combined ship) — **close-out 2026-09-02** — [`phaseC-shell.md`](phaseC-shell.md) § C34 · [`phaseL-lcd.md`](phaseL-lcd.md) § L3 |
| **C35** | WISC/Admin live IR UX + learn refresh + mod default/layout — **Pi smoke 2026-09-03** — [`phaseC-shell.md`](phaseC-shell.md) § C35 |
| **B10I / B10J / B10L / B10M + C20 / C21** | ∥ LOW cluster — Go to SR; Event Received name; NOT CONNECTED copy; Hue preset dup settings; Clear All; AUTO OFF while OFF — **Pi smoke 2026-09-05** |
| **C38 + L4** | Sauna session telemetry + LCD WISC timer/door-closed + Real W MOD gate + Admin last-poll/GPIO/ARM modal — **close-out 2026-09-08** — [`phaseC-shell.md`](phaseC-shell.md) § C38 · [`phaseL-lcd.md`](phaseL-lcd.md) § L4 |
| **C39** | Admin Sauna/IR unified pane + R_th `0.000 °C/W` + WISC water one-line — **close-out 2026-09-08** — [`phaseC-shell.md`](phaseC-shell.md) § C39 |
| **B7 / B14 part 1** | Set for/after + H1/H3 + 90001 gate — **Pi smoke 2026-09-09** — [`phaseB-blocky.md`](phaseB-blocky.md) § B14 part 1 |
| **C41** | First-boot DB order + learn window + Admin/WISC polish + absolute sauna Wh (`11001`) — **close-out 2026-09-09** — [`phaseC-shell.md`](phaseC-shell.md) § C41 |
| **C37** | bugfix: Android PWA resume black screen — **OnePlus 12 smoke 2026-09-09** — [`phaseC-shell.md`](phaseC-shell.md) § C37 |
| **C40** | Cancelled **2026-09-09** — PID v2 not open; re-triage when wanted — [`phaseC-shell.md`](phaseC-shell.md) § C40 |
| **S1** | Sauna vent strip + door closed ≤5 min start gate + timer-hop removal — **Pi smoke 2026-09-10** — [`_archive/phaseS-sauna.md`](_archive/phaseS-sauna.md) |
| **G10** | HomeWizard Energy P1 + PV (`810xx`) — **Done 2026-09-10** (Pi smoke OK; sockets deferred) — [`phaseG-integrations.md`](phaseG-integrations.md) § G10 · [`integration_homewizard.md`](../integration_homewizard.md) |
| **G20** | bugfix: LG web OFF bounce — commanded-OFF latch — **close-out 2026-09-22** — [`phaseG-integrations.md`](phaseG-integrations.md) § G20 · [`integration_lg.md`](../integration_lg.md) |
| **G21** | bugfix: HomeWizard P1 TimeoutError flaps — A+B+D health — **close-out 2026-09-22** — [`phaseG-integrations.md`](phaseG-integrations.md) § G21 · [`integration_homewizard.md`](../integration_homewizard.md) |
| **G22** | bugfix: Onkyo power-ON must not force volume / SYNC — **close-out 2026-10-01** — [`phaseG-integrations.md`](phaseG-integrations.md) § G22 · [`integration_onkyo.md`](../integration_onkyo.md) |
| **B14b / B25** | Library complexity score + tier (sort/filter) — **close-out 2026-10-05** — [`phaseB-blocky.md`](phaseB-blocky.md) § B14 part 2 · § B25 · [`reference.md`](../reference.md) § automations API |
| **Ops8** | PHP2Shell bridge on live Bullseye PHP 7.4 (B2 pristine + mitigation) — **close-out 2026-11-04** — [`_archive/ops8-php2shell-bridge.md`](_archive/ops8-php2shell-bridge.md) · [`../ops8-operator-checklist.md`](../ops8-operator-checklist.md) |
| **G23** | Water-Link portal scout (`waterlink_scout.py`) — **close-out 2026-11-04** — [`phaseG-integrations.md`](phaseG-integrations.md) § G23 · [`../integration_waterlink.md`](../integration_waterlink.md) |
| **G24** | Water-Link WanOS bridge (poll 6h → idx 82001) — **close-out 2026-11-05** — [`phaseG-integrations.md`](phaseG-integrations.md) § G24 · [`../integration_waterlink.md`](../integration_waterlink.md) |

---

## Sequence

All open items. **Detail** = phase file section.

```text
#   Status Size Id           What                                               Detail
──  ────── ──── ──────────── ────────────────────────────────────────────────── ──────────────────────────
1   coding high Ops7         fresh main Pi: Trixie + PHP≥8.4.27 + Python 3.13 (scripts) ops7-fresh-install.md
2   open   low  B12          rule-list folder/tag                               phaseB § B12
3   open   mid  B26          independent If sequence under Then (all-match)     phaseB § B26
4   open   mid  B24          per-rule sweep reconcile (level-hold @ sweep)      phaseB § B24
5   hold   high B28          assess: auto-off SoT → singular automation rules   phaseB § B28
6   hold   mid  B29          H7 Auto/Manual override (entry model undecided)    phaseB § B29
7   open   high E            Gmail transport / outbox + Blockly Messages        phaseE
8   open   mid  C3           Force ALL-OFF                                      phaseC § C3
9   open   mid  C4           Rename HTML entrypoints (commander→wisc, blocky→blockly; login landing)  phaseC § C4
10  open   mid  C28          LG TV skins (explorer-tv + wisc-tv; gate from login) phaseC § C28
11  open   mid  C26          Frontend JS modularization + reference.md JS catalog phaseC § C26
12  hold   low  C11          Control vs History list membership (assess)        phaseC § C11
13  hold   low  C17          Alert banner dismiss vs reload (assess)            phaseC § C17
14  open   low  C15          Admin lab switch → Debug Commands row              phaseC § C15
15  open   mid  C13          Merge Hidden → Timers & types                      phaseC § C13
16  open   mid  C30          WISC douche session (live + last summary)           phaseC § C30
17  open   mid  G2           bugfix: Hue color/bri truth                        phaseG § G2
18  open   mid  G6           Admin scoped CONFIG_RELOAD modal + API scopes      phaseG § G6
19  open   low  G7           Integration log tags                               phaseG § G7
20  open   mid  G8           bugfix: Boot autostart timing (A+B)                phaseG § G8
21  open   mid  G14          bugfix: Manual enable status + ON bell             phaseG § G14
22  open   mid  G1           bugfix: Epson get_power_state                      phaseG § G1
23  open   mid  G4           OWM One Call + hot-sun cinema 60%                  phaseG § G4
24  open   high G11          Samsung SmartThings / Airco (kickoff locked)       phaseG § G11
25  open   high G9           Honeywell / Evohome                                phaseG § G9
26  open   high G12          SMA solar                                          phaseG § G12
27  open   high G13          HomeConnect BSH                                    phaseG § G13
28  open   high G17          HomeWizard map UI (Z-Wave-style picker + add devices)  phaseG § G17
29  open   high F            Security bridge (F1→F7)                            phaseF
30  hold   mid  B20          Domoticz Time trigger / clock rules (after F)       phaseB § B20
31  hold   mid  B15          Demote schedule edges → user origin (after F)      phaseB § B15
32  hold   high B16          Full-bus UUID for internal EventTypes (after F)    phaseB § B16
33  hold   mid  B17          Sauna/IR hardcoded → automation (assess)           phaseB § B17
34  open   mid  B18          bugfix: Sauna session_end ≤ absolute_cutoff        phaseB § B18
35  hold   high P            Other homes / portability (assess)                 phaseP
36  open   high P1           Configurable sensor-history series (replace SENSOR_META)  phaseP § P1
37  open   mid  P2           sync: [MirrorExcludeFiles] for main + lcd + wlw      phaseP § P2
38  open   mid  L2           LCDs on WanOS Pi; retire LCD Pi (.env→config_hardware) phaseL § L2
39  open   low  B27          bugfix: TV ON rule — Sonos OFF not applied / log2 gap phaseB § B27
40  open   mid  C33          Sauna/IR History + nameplates + sauna kWh (Admin timers→C39)  phaseC § C33
41  open   mid  C36          Device event history modal (right-click → table)     phaseC § C36
42  open   mid  C42          HomeWizard-style power graphs (Explorer History)     phaseC § C42
43  open   low  C43          Explorer view presets: Control/History + clear on filter drift  phaseC § C43
44  open   mid  C44          bugfix: UI SSE reconnect after backend reboot                 phaseC § C44
45  open   mid  G18          bugfix: zwave.vent.badk_1e OFF not sent (unmapped/empty)    phaseG § G18
46  hold   mid  G19          assess: empty wanos_iwhw.log (Grok: missing self.iwhw_logger)  phaseG § G19
47  open   low  B30          numeric Compare edge vs level (was B14b row 2)     phaseB § B30
48  open   low  B31          H6 number helpers (was B14b)                       phaseB § B31
49  open   low  B32          H9 sun elevation (was B14b)                        phaseB § B32
```
Near-term: **Ops7** (fresh `.30`; scripts coding; WLW overlay after host green). Then **B26** → **B24**. **B12** may run ∥ after Ops7 host green (or earlier if no Pi cutover conflict). **B30**/**B31**/**B32** low. **B29** hold (H7). **B28** hold assess. Vendor bridges: **G11→G9→G12→G13→G17**. **G23**/**G24** Water-Link Done. **Ops8** Done (live PHP bridge until cutover).

---

## Manual checks

Not lettered product phases. Detail stays here (no `phaseX` file) unless re-homed.

| Item | Status | Notes |
|---|---|---|
| **Ops1 later** | hold | uvicorn `--no-access-log` / no `?jwt=`; ForwardToSyslog; log2ram SIZE; auth/kern no-archive |
| **Ops8 — PHP2Shell bridge** | **done** | **2026-11-04** B2 pristine + mitigation on `.30`. Archive [`_archive/ops8-php2shell-bridge.md`](_archive/ops8-php2shell-bridge.md) · product [`../ops8-operator-checklist.md`](../ops8-operator-checklist.md) · helpers [`../../helpers/ops8-php2shell/`](../../helpers/ops8-php2shell/) |
| **Ops7 — Fresh main Pi** | coding · Sequence **#1** | Trixie Lite 64-bit + PHP ≥ **8.4.27** + Python **3.13**; no Samba; folds **Ops2**. Scripts **2026-10-22**; cutover open. Checklist [`../ops7-operator-checklist.md`](../ops7-operator-checklist.md) · [`ops7-fresh-install.md`](ops7-fresh-install.md) · [`../bootstrap-main-pi.md`](../bootstrap-main-pi.md) |
| **Ops2 — Pi Python runtime** | superseded | **2026-10-22** → **Ops7** (Trixie locks system Python 3.13; soak in Ops7 DoD) |
| **PCB / carrier board (KiCad, JLCPCB)** | open | **Not in this pipeline.** Design + fab backlog → [**wanos-pcb**](https://github.com/gitwannes/wanos-pcb) (`docs/todo/pipeline.md`). This repo: `config_hardware.yaml` runtime pin map only. |
| **Pull auto.yaml from Pi** | hold | Prefer non-repo pull dir — see [`wanos-sync.md`](../wanos-sync.md) |
| **Cinema merge ON/OFF rules** | open | Operator YAML — pickable cinema state **to be checked** |
| **Background Leak = 0.0 W** | hold | Verify |
| **3-phase kWh meter / Pi power** | hold | Site / manual |
| **energy.meter_baseline_kwh** | superseded | **C41 2026-09-09** — dual baseline/`energy:` config removed. Canonical = NVRAM IDX `11001` **sauna-circuit** Wh (not whole-house); Admin **Total kWh** = `11001/1000`. Reseed `11001` to `round(face_kWh*1000)` after deploy (e.g. 1715.5 → 1715500). Whole-house → **G10** HomeWizard P1. SoT: [`sensor_history.md`](../sensor_history.md) §3 |
| **R1 — source-available license** | done | **2026-09-01** — see § R1 below |

### R1 — Source-available license — Done 2026-09-01

**Status:** done · repo meta (no lettered phase file) · **Done** table row above.

**Operator request (verbatim, 2026-08-31):**

> Q: is the license choice for wanos correct?

**Lock (2026-08-31):** **Personal use OK, no redistribution** (custom source-available notice — not GPL, not MIT).

**Shipped:**

| File | Change |
|---|---|
| `LICENSE` | Custom six-section notice (grant, no redistribution, no commercial use, attribution, no warranty, contact) |
| `readme.md` | Badge + License section |
| `main.py` | Copyright header |

**Product reference (canonical):** [`readme.md`](../../readme.md) § License + [`LICENSE`](../../LICENSE). `LICENSE` is repo meta only — not mirrored to Pi ([`wanos-sync.md`](../wanos-sync.md)).

**Out of scope:** SPDX headers on every source file; `_lcd-agent` per-file notices; **wanos-pcb** repo (separate LICENSE there).

**R1 DoD:** [x] Operator lock recorded · [x] `LICENSE` / `readme.md` / `main.py` shipped · [x] Last DoD: audit `docs/**/*.md` + root README — no GPL drift (**2026-09-01**).

### Ops8 — PHP2Shell bridge — Done 2026-11-04

**Status:** done · size **mid** · archived  
**Archive:** [`_archive/ops8-php2shell-bridge.md`](_archive/ops8-php2shell-bridge.md) · product [`../ops8-operator-checklist.md`](../ops8-operator-checklist.md) · helpers [`../../helpers/ops8-php2shell/`](../../helpers/ops8-php2shell/)  
**Shipped:** B2 pristine php.net 7.4.33 + security patch + `--enable-fpm` / `--with-fpm-systemd` binary replace + FPM mitigation + apt hold. Pi smoke **`OK_bridged_and_mitigated`**.

### Ops7 — Fresh main Pi (OS / PHP / Python) — coding

**Status:** coding · size **high** · Sequence **#1**  
**Detail:** [`ops7-fresh-install.md`](ops7-fresh-install.md) · product [`../bootstrap-main-pi.md`](../bootstrap-main-pi.md)  
**WLW overlay after host:** be90webserver Ops7 (pointer).

**Folds Ops2** (2026-08-27 assess verbatim retained in Ops7 detail file). Lock: latest Pi OS → Trixie → system **Python 3.13**; PHP ≥ **8.4.27**; no Samba.

**DoD / locks / cutover:** see detail file — **Ops8 bridge Done**; cutover when operator ready.

### Ops2 — Pi Python runtime — superseded 2026-10-22

Former assess (3.12 vs 3.13) closed into **Ops7**. Do not re-open a separate Ops2 Sequence row.
