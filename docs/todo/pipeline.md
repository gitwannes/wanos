# ⚡ WanOS — Implementation pipeline

High-level **what’s next** and where the detailed specs live. This file does **not** hold phase DoD / locked-decision novels — those live in `phaseX-yyy.md`.

**Last updated:** 2026-08-10

---

## How to use

| Band | Meaning |
|---|---|
| **Done** | Shipped + Pi smoke OK — keep for history; not in Sequence |
| **Now / next** | Spec locked; implement when capacity allows |
| **Queued** | Spec exists; schedule after “now” |
| **Ops / Manual** | Operator / site work — stays in this file |

**One detail file per letter.** Pipeline links only to those filenames.

| Letter | Affinity | Detail file |
|---|---|---|
| **B** | Blocky / Blockly / automations | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **C** | Operator shell (Explorer, Admin, History charts, force sweep, HTML names) | [`phaseC-shell.md`](phaseC-shell.md) |
| **D** | Device typing (switch vs light) | [`phaseD-typing.md`](phaseD-typing.md) |
| **E** | Gmail transport (OAuth, outbox, spooler) | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **F** | Public bridge / perimeter security | [`phaseF-security.md`](phaseF-security.md) |
| **G** | Integrations reliability (Hue state, Epson, OWM poll / daily forecast / cinema sun) | [`phaseG-integrations.md`](phaseG-integrations.md) |

**Naming note:** Deny-list decision **D1** in Blocky ≠ phase **D**. When a phase completes: move it from **Sequence** → **Done**, and drop its bullet from **Why this order**.

### DoD / close-out (all phases)

**Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

Applies to every phase (and every future phase). Not only `docs/todo/*` — fix stale API/UX names, removed helpers, renamed events, Library kinds, etc. so markdown matches what shipped. Each phase checklist should end with this checkbox (wording above). Detail files own the checkbox; this rule is the standing convention.

---

## Done

| Phase | Notes |
|---|---|
| **B0–B8** | Schema v2, rich actions, soft-hide, auto-off — Pi smoke through **2026-08-08** |
| **B10A** | Blocky editor trust (Hue / Delete / dirty) — Pi smoke **2026-08-09** |
| **B10C** | Soft-hide action device picker (exclusive + sticky) — Pi smoke **2026-08-09** |
| **B10B+D+E** | Events catalog + Library UX + schedule labels — Pi smoke/GREEN/kiosk + migrator delete **2026-08-10** |
| **C1 / C2 / C5** | Explorer chrome · Admin/system pages · History graphs — Pi smoke **2026-08-09** |

Detail DoD → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md).

---

## Sequence

**Size** = relative delivery weight (rough): **low** = small/local · **mid** = multi-file or careful edge cases · **high** = schema/API/engine or large surface. Not calendar days.

```text
#  Size   Phase    What
1. mid    B10F     Automations UX polish (save chrome, connecting, library keys, schedule fire-time, unused-SE→SR, UE/SE filter defaults)
2. low    C6       History auto-refresh flicker
3. low    C7       Explorer follow-ups (favorites / filters / chart chrome)
4. low    C8       Alert dismiss → wanos.log info (banner + bell)
5. low    C9       Z-Wave Command Sent logs + type/name (automation-log parity)
6. mid    D        switch vs light typing
7. high   B9A      sensors / thresholds / sauna-session cond / remove JSON
8. high   E        Gmail transport / outbox
9. high   B9B      bathroom + H4/H5/H12  (H4 expands trigger any-of→cond and/or; H5 email needs E)
10. mid   C3       Force ALL-OFF
11. mid   C4       Rename HTML entrypoints
12. mid   G2       Hue color/bri truth (assess → fix)
13. mid   G1       Epson get_power_state (analysis → impl)
14. low   G3       OWM outside poll 10′ (config)
15. mid   G4       OWM One Call daily + hot-sun cinema 60% open
16. low   G5       Dashboard “rolluik zon half” (60% closed if not shut)
17. high  F        Security bridge (F1→F7 as deployed)
18. high  B11      Multi-flow one Blockly page
19. mid   B12      Rule-list folder/tag
20. high  B13      Blockly IF/ELSE / ELSEIF / ELSE
21. high  B14      Remaining HA patterns H1–H3, H6–H10
22. mid   B15      Demote schedule edges → user origin
23. high  B16      Full-bus UUID for internal EventTypes (decision → impl)
24. mid   B17      Sauna/IR hardcoded handlers → automation (assess only)
25. —     Ops      Inbox below when convenient
```

### Why this order

* **B10F after B10B+D+E** — Automations polish on the shipped Library/editor; does not reopen B10E DoD. Spec: `phaseB-blocky.md` § B10F. (**B10B+D+E** ✅ **Done 2026-08-10** — smoke/GREEN/kiosk + migrator/D1 deleted.)
* **C6 after B10*** — History soft-refresh flicker (all charts); shell follow-up, not Blocky. May swap ahead if flicker pain wins.
* **C7 after C6** — Explorer portrait favorites, SSE filter restore, landscape chart chrome, legend dots; may swap ahead of C6 if Control pain wins.
* **C8 after C7** — banner + bell dismiss → `info` in `/var/log/wanos/wanos.log` (C2 follow-up); low; anytime with other C leftovers.
* **B10B before B9A** — events catalog shipped first (**done**); sensors/JSON removal is larger and can wait.
* **D after B10B / with C2 consumers** — typing benefits Planned Automations and Blocky light/switch wording; not a Blocky editor rewrite.
* **B9A then E then B9B** — compares/sensors first; Gmail transport (**E**) can start early but **B9B H5 email** waits on E; bathroom/H12/H4 sit on B9A primitives.
* **C3 / C4 later** — Admin force-sweep is powerful but not daily-path; HTML renames are mechanical and safer after shell churn settles.
* **G2 before G1** — Hue color lie affects daily Explorer; Epson boot query is analysis-gated and rarer. Swap if Epson pain wins.
* **G3 anytime** — OWM `poll_interval_mins` 30→10; config-only; only outside source is OWM 30001.
* **G4 after G3** — One Call 4.0 daily assess + hot/full-sun cinema opens to **60% open** (account subscribed ✅); same OWM thread, mid work.
* **G5 after G4** (or alone) — dashboard **“rolluik zon half”** → **60% closed** if cinema not fully closed; retires misnamed half rule. Uses B10B+D+E `events:` / `dashboard_events` (cutover done **2026-08-10**).
* **C9 with other C leftovers** — Z-Wave send-log type/name parity; anytime after C8 or with C7/C8. Spec: `phaseC-shell.md` § C9.
* **F when deploying remote access** — independent perimeter track; interleave only when exposing the bridge.
* **Do not fold B10\* into B9\*** — different jobs (trust/events vs sensors/climate). **G2 ≠ B10A** — runtime bridge truth vs Blockly editor chrome (B10A done).
* **B11–B17 stay after F / day-to-day** — lettered ex–Later B; schedule when pain or architecture cutover wins. Spec: [`phaseB-blocky.md`](phaseB-blocky.md) § B11–B17.

Near-term = **B10F → C6 → C7 → C8 → C9**. Then **D** / **B9A** flexible. **E** may run parallel to B9A; B9B email DoD needs E. **G2** can jump forward if color truth is blocking. **G3** whenever convenient. **G4/G5** when summer heat / cinema sun is the pain.

---

## Now / next (pointers only)

| Step | Detail |
|---|---|
| **B10F** | [`phaseB-blocky.md`](phaseB-blocky.md) § B10F — Automations UX polish |
| **C6** | [`phaseC-shell.md`](phaseC-shell.md) § C6 — History auto-refresh flicker |
| **C7** | [`phaseC-shell.md`](phaseC-shell.md) § C7 — Favorites portrait · SSE filters · landscape chart chrome · legend dots |
| **C8** | [`phaseC-shell.md`](phaseC-shell.md) § C8 — Banner + bell dismiss → `wanos.log` info |
| **C9** | [`phaseC-shell.md`](phaseC-shell.md) § C9 — Z-Wave Command Sent logs + type/name |
| **D** | [`phaseD-typing.md`](phaseD-typing.md) — infer + override · freeze `entity_id` · 71/72 |

---

## Queued

| Phase | Detail file |
|---|---|
| **B9A** / **B9B** / **B11–B17** | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **E** | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **C3** / **C4** / **C6** / **C7** / **C8** / **C9** | [`phaseC-shell.md`](phaseC-shell.md) |
| **G2** / **G1** / **G3** / **G4** / **G5** | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **F1–F7** | [`phaseF-security.md`](phaseF-security.md) |

### B11–B17 — lettered ex–Later B (pointers)

Detail + DoD stubs: [`phaseB-blocky.md`](phaseB-blocky.md) § B11–B17. Schedule math / demotion constraints: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md). Sauna/IR live safety still: [`sauna-ir.md`](../sauna-ir.md).

| Phase | What |
|---|---|
| **B11** | Multi-flow one Blockly page |
| **B12** | Rule-list folder/tag |
| **B13** | Blockly IF/ELSE / ELSEIF / ELSE |
| **B14** | Remaining HA patterns H1–H3, H6–H10 |
| **B15** | Demote schedule edges → user origin |
| **B16** | Full-bus UUID for internal `EventType`s (decision → impl) |
| **B17** | Sauna/IR hardcoded handlers → automation — **assess only** |

---

## Inbox — Ops / Manual (2026-08-09)

Not lettered product phases. Unclear parts marked **to be checked**.

### Ops — pull from Pi

| Label | Source (Pi) | Destination (stated) |
|---|---|---|
| REPO1 | `entity_registry.auto.yaml` | `C:\data\git\wanos` |
| REPO2 | `automations.auto.yaml` | `C:\data\git\wanos` |
| STATS | telemetry | `C:\data\OneDrive\data\professional\wanos\logs` |
| LOGS | `wannes@10.32.251.30:/var/log/wanos/wanos*` (rsync) | `C:\data\OneDrive\data\professional\wanos\logs` |

**Open decision — auto.yaml into `git\wanos`?** Overwriting the working tree from Pi can fight local edits / git history.

| Option | Idea |
|---|---|
| **1** | Pull to a **non-repo** dir (OneDrive `…\wanos\pi-pull\`) — **recommended for inspect-Pi** |
| **2** | gitignore `*.auto.yaml` and treat Pi as sole author — **to be checked** vs cutover workflow |

### Read SQLite history DBs on Windows

Copy DBs off Pi (include `-wal`/`-shm` if present) → DB Browser / `sqlite3` / VS Code SQLite. Prefer **copies**, not live files. **to be checked:** exact Pi paths.

### Manual / site

| Item | Notes |
|---|---|
| Background Leak = **0.0 W** | Verify — **check!** |
| Where is the **3-phase kWh meter** connected? | Site / wiring — **manual** |
| Where do the **Pis** get power? | Site / UPS / circuit — **manual** |

*(Hue badkamer red / preset checks → folded into **G2** assess in [`phaseG-integrations.md`](phaseG-integrations.md). Blocky preset picker gap → confirm under **B6C** / **B9A** if still missing.)*

---

## Change log (short)

| When | What |
|---|---|
| 2026-08 | **B0–B8** done on Pi (schema v2, rich actions, soft-hide, auto-off). **B9A/B9B** + **B10A/B10B** specs locked. |
| 2026-08-09 | Intermediary shell/typing + pipeline; letter rename B/C/D/E/F/G. |
| 2026-08-09 | Specs collapsed to `phaseX-yyy.md`; this file = sequence + ops only. |
| 2026-08-09 | Added **C5** History graphs; **G2** Hue state; renamed G file → `phaseG-integrations.md`. |
| 2026-08-09 | **B10A** → **Done**; Sequence starts at **C1**. Rule: completed phases leave Sequence + Why-this-order. |
| 2026-08-09 | **C5** + climate smooth day/month/year (drop stair-step draw). |
| 2026-08-09 | **C1 / C2 / C5** → **Done**; Sequence starts at **B10B**. |
| 2026-08-09 | Inbox triage: **B10C** soft-hide picker bug; **C6** History flicker; **G3** OWM poll 10′. Sequence → **B10C**. |
| 2026-08-09 | **B10C** → **Done**; Sequence starts at **B10B**. |
| 2026-08-09 | Inbox: **B10D** unique rule names (case-insensitive; FE + API). |
| 2026-08-09 | Inbox: **B10E** Automations sidebar sort (name ↔ type+name via AUTOMATIONS header). |
| 2026-08-09 | Sequence: added **Size** column (low / mid / high). |
| 2026-08-09 | **B10B** spec fully locked: `events:` UUID bus, family/`SCENE_*` cutover, rule enable; `EMAIL_REQUESTED` waits for **E**. |
| 2026-08-10 | Inbox triage: **C7** Explorer follow-ups; **B9A** sauna-session condition + sauna hue physical smoke rule. |
| 2026-08-10 | **B10B+D** this pass (B10D bundled). Internals stay `EventType` strings in B10B; full-bus UUID follow-up = **B16** (ex–Later B; still to be decided at kickoff). |
| 2026-08-10 | **B10B+D** treated as **one phase**: B10D checks from start; cutover **7A**; API **8A**; system seed **names** **approved** in `phaseB-blocky.md`. `LIGHTING_STATE_CHANGED` removed from code. |
| 2026-08-10 | Inbox triage: **G4** OWM One Call daily + hot-sun cinema 60% open; **G5** dashboard “rolluik zon half” (60% closed). One Call by Call 4.0 subscribed. |
| 2026-08-10 | Inbox triage: **C8** banner + bell alert dismiss → `info` in `/var/log/wanos/wanos.log`. |
| 2026-08-10 | **B10B+D** code + Pi migrator **7A** done; kiosk UUIDs; Hub not pickable; registry check skips ≥900000. **Open:** operator smoke + GREEN + delete migrator. |
| 2026-08-10 | Schedule model **locked**: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md) (single file). **B10E** expanded = list UX + catalog display renames + wipe Sunset listeners. **B15** (ex–Later B): demote schedule edges → user origin — deferred. |
| 2026-08-10 | B10E locks: empty S auto-create disabled; list unused user events; S title = system name; `EXTERNAL_WEATHER_UPDATED` → `SUNRISE_SUNSET_UPDATE`. |
| 2026-08-10 | **One ship B10B+D+E.** B10E revises B10B Automations UX. Empty SE = catalog-only until operator creates SR (no auto shells). User-event disable blocked when fire-referenced + Show usages. |
| 2026-08-10 | E form: Appear on explorer always; confirm blocked unless explorer ON; **clearing explorer while confirm ON forces confirm OFF** (UI + API). |
| 2026-08-10 | **B10B+D+E code ship done** (Library E/U/S/D+C, E form, When/Fire split, schedule labels, `SUNRISE_SUNSET_UPDATE`, fire allowlist). **Open:** Pi combined smoke + GREEN + delete migrator. Schedule edges stay system (demotion deferred). |
| 2026-08-10 | Inbox triage: **B10F** Automations UX polish; **B9B H4** expand (drop trigger “when any of” → cond and/or); **Later B → B11–B17**; **C9** Z-Wave send-log type/name; Sauna/IR → **B17** assess-only. |
| 2026-08-10 | **B10F** +2: unused SE → Create System Rule button; Library filters UE & SE default OFF. |
| 2026-08-10 | **B10B+D+E** operator Pi smoke + Admin Debug **GREEN** + kiosk / B10D name smokes ✅. **Open:** delete `helpers/migrate_events_b10b.py` after soak. |
| 2026-08-10 | **B10B+D+E close-out:** migrator + `b10b_cutover_map.json` deleted; D1 (`TWILIGHT_*` / `SCHEDULE_EVENT_ALIASES` / `SCHEDULE_WINDOW_EDGES`) removed; phase → **Done**. Sequence starts at **B10F**. |
| 2026-08-10 | **Standing DoD:** every phase ends with audit & update of ALL `docs/**/*.md` (+ root README) against shipped behavior (`pipeline.md` § DoD / close-out). B10B+D+E docs pass executed. |
| 2026-08-10 | **Docs re-audit:** retired stale `install_blocky.md` → pointer stub; fixed E1/smoke/status drift in `phaseB-blocky.md`; G5 cutover gate; C1/C2/C5 + B10A/C Last DoD; empty-SE = no shells. |

Detail chronology / DoD checkboxes → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md), [`phaseG-integrations.md`](phaseG-integrations.md).
