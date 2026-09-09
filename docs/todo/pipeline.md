# WanOS — Implementation pipeline

Ordered backlog + closed history. Specs / DoD / locks live in the lettered phase files — not here.

**Last updated:** 2026-09-09 (S1 vent strip — hardcode removed; Library + Timers & types own post-OFF fan)
**Last updated:** 2026-09-09 (C37 close-out — Android PWA resume black screen; OnePlus 12 smoke OK)
**Last updated:** 2026-09-09 (C40 cancelled — PID v2 not open; C38/C41 already Done)
**Last updated:** 2026-09-09 (C41 close-out — sauna analytics + Admin/WISC polish + absolute house Wh)
**Last updated:** 2026-09-09 (Ship B7 / B14 part 1 close-out — Pi smoke OK)
**Last updated:** 2026-09-08 (S1 triage + kickoff — sauna vent strip + door start gate)

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
| **S** | Sauna plant (vent + start gate) | [`phaseS-sauna.md`](phaseS-sauna.md) |

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
| **C41** | First-boot DB order + learn window + Admin/WISC polish + absolute house Wh (`11001`) — **close-out 2026-09-09** — [`phaseC-shell.md`](phaseC-shell.md) § C41 |
| **C37** | bugfix: Android PWA resume black screen — **OnePlus 12 smoke 2026-09-09** — [`phaseC-shell.md`](phaseC-shell.md) § C37 |
| **C40** | Cancelled **2026-09-09** — PID v2 not open; re-triage when wanted — [`phaseC-shell.md`](phaseC-shell.md) § C40 |

---

## Sequence

All open items. **Detail** = phase file section.

```text
#   Status Size Id           What                                               Detail
──  ────── ──── ──────────── ────────────────────────────────────────────────── ──────────────────────────
1   open   mid  B14b         H6/H7/H9 + B5 rows 2–5 + B25 (after part 1)        phaseB § B14 part 2
2   open   low  B12          rule-list folder/tag                               phaseB § B12
3   open   mid  B26          independent If sequence under Then (all-match)     phaseB § B26
4   open   mid  B24          per-rule sweep reconcile (level-hold @ sweep)      phaseB § B24
5   open   high E            Gmail transport / outbox + Blockly Messages        phaseE
6   open   mid  C3           Force ALL-OFF                                      phaseC § C3
7   open   mid  C4           Rename HTML entrypoints (commander→wisc, blocky→blockly; login landing)  phaseC § C4
8   open   mid  C28          LG TV skins (explorer-tv + wisc-tv; gate from login) phaseC § C28
9   open   mid  C26          Frontend JS modularization + reference.md JS catalog phaseC § C26
10  hold   low  C11          Control vs History list membership (assess)        phaseC § C11
11  hold   low  C17          Alert banner dismiss vs reload (assess)            phaseC § C17
12  open   low  C15          Admin lab switch → Debug Commands row              phaseC § C15
13  open   mid  C13          Merge Hidden → Timers & types                      phaseC § C13
14  open   mid  C30          WISC douche session (live + last summary)           phaseC § C30
15  open   mid  G2           bugfix: Hue color/bri truth                        phaseG § G2
16  open   mid  G6           Admin scoped CONFIG_RELOAD modal + API scopes      phaseG § G6
17  open   low  G7           Integration log tags                               phaseG § G7
18  open   mid  G8           bugfix: Boot autostart timing (A+B)                phaseG § G8
19  open   mid  G14          bugfix: Manual enable status + ON bell             phaseG § G14
20  open   mid  G1           bugfix: Epson get_power_state                      phaseG § G1
21  open   mid  G4           OWM One Call + hot-sun cinema 60%                  phaseG § G4
22  open   high G11          Samsung SmartThings / Airco (kickoff locked)       phaseG § G11
23  open   high G9           Honeywell / Evohome                                phaseG § G9
24  open   high G10          HomeWizard energy                                  phaseG § G10
25  open   high G12          SMA solar                                          phaseG § G12
26  open   high G13          HomeConnect BSH                                    phaseG § G13
27  open   high F            Security bridge (F1→F7)                            phaseF
28  hold   mid  B20          Domoticz Time trigger (after F)                    phaseB § B20
29  hold   mid  B15          Demote schedule edges → user origin (after F)      phaseB § B15
30  hold   high B16          Full-bus UUID for internal EventTypes (after F)    phaseB § B16
31  hold   mid  B17          Sauna/IR hardcoded → automation (assess)           phaseB § B17
32  open   mid  B18          bugfix: Sauna session_end ≤ absolute_cutoff        phaseB § B18
33  hold   high P            Other homes / portability (assess)                 phaseP
34  open   mid  L2           LCDs on WanOS Pi; retire LCD Pi (.env→config_hardware) phaseL § L2
35  hold   high Ops2         assess: Pi Python runtime (3.12 vs 3.13; no lock)   pipeline Manual § Ops2
36  open   low  B27          bugfix: TV ON rule — Sonos OFF not applied / log2 gap phaseB § B27
37  open   mid  C33          Sauna/IR History + nameplates + house kWh (Admin timers→C39)  phaseC § C33
38  open   mid  C36          Device event history modal (right-click → table)     phaseC § C36
39  open   mid  S1           Sauna vent strip (rules+timers) + door closed start gate  phaseS § S1
```
Near-term: **S1** vent strip ✅ **2026-09-09** (door gate still open — kickoff Qs). **B14b** next Blockly ship → **B26** → **B24**. **B12** may run ∥ **B14b**. **C33** / **C36** / **B27** may run ∥ near-term cluster (kickoff each). **L2** after kickoff when ready. **C28** after **C4**; **C26** after **C4**. **C30** = WISC douche live + last summary. **E** may run beside **B14b**. Vendor bridges **G11→G9→G10→G12→G13** after **G4**, before **F**. **C37** ✅ **OnePlus 12 smoke 2026-09-09**. **B7 / B14 part 1** ✅ **Pi smoke 2026-09-09**. **C38** / **C41** ✅ **close-out**. **C40** cancelled (PID v2 not open). **Ops2** hold — large assess only; **do not** fix/target 3.13 until assess; **3.12** remains a valid outcome.

---

## Manual checks

Not lettered product phases. Detail stays here (no `phaseX` file) unless re-homed.

| Item | Status | Notes |
|---|---|---|
| **Ops1 later** | hold | uvicorn `--no-access-log` / no `?jwt=`; ForwardToSyslog; log2ram SIZE; auth/kern no-archive |
| **Ops2 — Pi Python runtime** | hold | **Assess only** (high). Target **not** locked to 3.13 — compare **3.12 vs 3.13** (and current Pi version); pick winner at kickoff/assess close. See § Ops2 below |
| **PCB / carrier board (KiCad, JLCPCB)** | open | **Not in this pipeline.** Design + fab backlog → [**wanos-pcb**](https://github.com/gitwannes/wanos-pcb) (`docs/todo/pipeline.md`). This repo: `config_hardware.yaml` runtime pin map only. |
| **Pull auto.yaml from Pi** | hold | Prefer non-repo pull dir — see [`wanos-sync.md`](../wanos-sync.md) |
| **Cinema merge ON/OFF rules** | open | Operator YAML — pickable cinema state **to be checked** |
| **Background Leak = 0.0 W** | hold | Verify |
| **3-phase kWh meter / Pi power** | hold | Site / manual |
| **energy.meter_baseline_kwh** | superseded | **C41 2026-09-09** — dual baseline/`energy:` config removed. Canonical = NVRAM IDX `11001` absolute Wh; Admin **Total kWh** = `11001/1000`. Reseed `11001` to `round(face_kWh*1000)` after deploy (e.g. 1715.5 → 1715500). SoT: [`sensor_history.md`](../sensor_history.md) §3 |
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

### Ops2 — Pi Python runtime (3.12 vs 3.13) — assess

**Status:** hold · size **high** · Sequence #44  
**Letter file:** none (Ops / Manual) — re-home only if operator asks.

**Operator request (verbatim, 2026-08-27):**

> triage this move to 3.13 into pipeline - don't fix on 3.13 - assess will be a big task, if 3.12 is eventually the better option, we will go for that

**Intent (placement, not locked target):**

* Large **assess** of moving the WanOS Pi venv / runtime to a newer CPython.
* **Do not** lock or implement “fix on 3.13.”
* Assess must keep **3.12 as a first-class outcome** if it is the better fit (wheels, GPIO/SHT path, ops cost).
* Outcome of assess = recommended target (3.12 or 3.13 or stay) + install story + risk list — **then** a later implement ship only when commanded.

**Assess scope (stub — expand at kickoff):**

* Confirm live Pi: OS (Trixie/Bookworm), `python3 --version`, venv interpreter, systemd unit paths.
* Full `requirements.txt` + `_lcd-agent` deps: wheels vs source on candidate versions.
* Hardware Domain A (`lgpio` inputs) and Domain B (`pi-sht1x` / `RPi.GPIO` vs `rpi-lgpio` / bit-bang port) — install story per candidate.
* Downstream pins: **G11** `pysmartthings` (3.12+ / 3.13+); **G16** shipped on **3.9** with `pywebostv` (not `aiowebostv`); badge/docs `3.9+`.
* Effort/risk: venv recreate, bootstrap docs, soak (sauna SHT11 + pulse inputs).

**Out of scope (this triage):**

* Choosing 3.13 (or 3.12) as locked target
* Implementing runtime upgrade, GPIO stack rewrite, or dependency bumps
* Folding into **P** (other homes) — runtime platform, not home-pack extraction

**Ops2 DoD (stub):** Assess recorded with recommended target + rationale; hardware/deps matrix; no code until implement command. **Last DoD (only if a later ship lands):** audit & update ALL `docs/**/*.md` (+ root README) against shipped behavior.
