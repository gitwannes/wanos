# WanOS — Implementation pipeline

Ordered backlog + closed history. Specs / DoD / locks live in the lettered phase files — not here.

**Last updated:** 2026-08-22

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
| **B23** | Automations page polish (scoped reload + UX) — Pi smoke **2026-08-22** |

---

## Sequence

All open items. **Detail** = phase file section.

```text
#   Status Size Id           What                                               Detail
──  ────── ──── ──────────── ────────────────────────────────────────────────── ──────────────────────────
1   open   mid  G15          bugfix: evening twilight cross-day orphan ON       phaseG § G15
2   open   high B7 / B14     timed Set, delay, cooldown + B5-deferred           phaseB § B14 / Ship B7
3   open   mid  B8           B11 multi-flow + B12 folder/tag                    phaseB § B11 / B12
4   open   mid  B22          nested If/Do (rescinds B19 no-nested lock)         phaseB § B22
5   open   low  B10I         used SE → Go to SR                                 phaseB § B10I
6   open   low  B10J         bugfix: Event Received → catalog display name      phaseB § B10J
7   open   low  B10L         NOT CONNECTED overlay + Re-connecting copy         phaseB § B10L
8   open   low  B10M         bugfix: Explorer Hue preset duplicate settings     phaseB § B10M
9   open   low  C20          bugfix: Admin Clear All no-op (kickoff locked)     phaseC § C20
10  open   low  C21          bugfix: AUTO OFF countdown while already OFF       phaseC § C21
11  open   low  C27          sunrise/sunset Admin + Explorer chrome             phaseC § C27
12  open   high E            Gmail transport / outbox + Blockly Messages        phaseE
13  open   mid  C3           Force ALL-OFF                                      phaseC § C3
14  open   mid  C4           Rename HTML entrypoints (blocky→blockly)           phaseC § C4
15  open   mid  C26          Frontend JS modularization + reference.md JS catalog phaseC § C26
16  hold   low  C11          Control vs History list membership (assess)        phaseC § C11
17  open   mid  C12          Post-C10 polish (+ Hidden preset admin-only)       phaseC § C12
18  hold   low  C17          Alert banner dismiss vs reload (assess)            phaseC § C17
19  open   mid  C16          Day chart sliding 24 h over hires_days             phaseC § C16
20  open   mid  C24          Temp/hum day fullscreen + AH/CI + CSV              phaseC § C24
21  open   mid  C25          Overlay dew-likelihood % (after C24)               phaseC § C25
22  open   low  C15          Admin lab switch → Debug Commands row              phaseC § C15
23  open   mid  C13          Merge Hidden → Timers & types                      phaseC § C13
24  open   mid  G2           bugfix: Hue color/bri truth                        phaseG § G2
25  open   mid  G6           Admin scoped CONFIG_RELOAD modal + API scopes      phaseG § G6
26  open   low  G7           Integration log tags                               phaseG § G7
27  open   mid  G8           bugfix: Boot autostart timing (A+B)                phaseG § G8
28  open   mid  G14          bugfix: Manual enable status + ON bell             phaseG § G14
29  open   mid  G1           bugfix: Epson get_power_state                      phaseG § G1
30  open   mid  G4           OWM One Call + hot-sun cinema 60%                  phaseG § G4
31  open   high G11          Samsung SmartThings / Airco (kickoff locked)       phaseG § G11
32  open   high G9           Honeywell / Evohome                                phaseG § G9
33  open   high G10          HomeWizard energy                                  phaseG § G10
34  open   high G12          SMA solar                                          phaseG § G12
35  open   high G13          HomeConnect BSH                                    phaseG § G13
36  open   high F            Security bridge (F1→F7)                            phaseF
37  hold   mid  B20          Domoticz Time trigger (after F)                    phaseB § B20
38  hold   mid  B15          Demote schedule edges → user origin (after F)      phaseB § B15
39  hold   high B16          Full-bus UUID for internal EventTypes (after F)    phaseB § B16
40  hold   mid  B17          Sauna/IR hardcoded → automation (assess)           phaseB § B17
41  open   mid  B18          bugfix: Sauna session_end ≤ absolute_cutoff        phaseB § B18
42  hold   high P            Other homes / portability (assess)                 phaseP
```
Near-term: **G15** (kickoff **2026-08-22**) → **B7 → B8 → B22**. **C26** after **C4** (HTML/JS rename, then split). **E** may run beside B7–B8. Vendor bridges **G11→G9→G10→G12→G13** after **G4**, before **F**.

---

## Manual checks

Not lettered product phases. Detail stays here (no `phaseX` file) unless re-homed.

| Item | Status | Notes |
|---|---|---|
| **Ops1 later** | hold | uvicorn `--no-access-log` / no `?jwt=`; ForwardToSyslog; log2ram SIZE; auth/kern no-archive |
| **Pull auto.yaml from Pi** | hold | Prefer non-repo pull dir — see [`wanos-sync.md`](../wanos-sync.md) |
| **Cinema merge ON/OFF rules** | open | Operator YAML — pickable cinema state **to be checked** |
| **Background Leak = 0.0 W** | hold | Verify |
| **3-phase kWh meter / Pi power** | hold | Site / manual |
