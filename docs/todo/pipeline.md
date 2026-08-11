# ⚡ WanOS — Implementation pipeline

High-level **what’s next** and where the detailed specs live. This file does **not** hold phase DoD / locked-decision novels — those live in `phaseX-yyy.md`.

**Last updated:** 2026-08-11

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
| **C** | Operator shell (Explorer, Admin, History charts, force sweep, HTML names, C10/C11) | [`phaseC-shell.md`](phaseC-shell.md) |
| **D** | Device typing (switch vs light) | [`phaseD-typing.md`](phaseD-typing.md) |
| **E** | Gmail transport (OAuth, outbox, spooler) | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **F** | Public bridge / perimeter security | [`phaseF-security.md`](phaseF-security.md) |
| **G** | Integrations reliability (Hue state, Epson, OWM, cinema sun, scoped reload, log tags) | [`phaseG-integrations.md`](phaseG-integrations.md) |

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
| **C6–C9** | History flicker · Explorer follow-ups · alert dismiss logs · device-ref `wanos.log` — Pi smoke **2026-08-10** |
| **B10F** | Automations UX polish (save chrome, fire-status, evening skip, SE→SR/UE→UR, CRUD INFO) — Pi smoke **2026-08-11** |
| **C10** | Explorer/History polish (plural, Planned past-remove, Hue hex text, chart colors, binary/hits, omit scenes, filter+blinds) — Pi smoke **2026-08-11** |

Detail DoD → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md).

---

## Sequence

**Size** = relative delivery weight (rough): **low** = small/local · **mid** = multi-file or careful edge cases · **high** = schema/API/engine or large surface. Not calendar days.

```text
#  Size   Phase    What
1. mid    D        switch vs light typing
2. high   B9A      sensors / thresholds / sauna-session cond / remove JSON
3. high   E        Gmail transport / outbox
4. high   B9B      bathroom + H4/H5/H12  (H4 expands trigger any-of→cond and/or; H5 email needs E)
5. mid    C3       Force ALL-OFF
6. mid    C4       Rename HTML entrypoints
7. low    C11      Control vs History list membership (assess → decide) — post–C10 scene omit
8. mid    G2       Hue color/bri truth (assess → fix)
9. mid    G6       Scoped CONFIG_RELOAD (automations/hide/auto-off ≠ Hue·Onkyo·Z-Wave recycle)
10. low   G7       Integration log tags (`[Onkyo]` parity with `[HUE]`)
11. mid   G1       Epson get_power_state (analysis → impl)
12. low   G3       OWM outside poll 10′ (config)
13. mid   G4       OWM One Call daily + hot-sun cinema 60% open
14. low   G5       Dashboard “rolluik zon half” (60% closed if not shut) — TODO; partial Cinema rolluik half (Open→50) gap-documented
15. high  F        Security bridge (F1→F7 as deployed)
16. high  B11      Multi-flow one Blockly page
17. mid   B12      Rule-list folder/tag
18. high  B13      Blockly IF/ELSE / ELSEIF / ELSE
19. high  B14      Remaining HA patterns H1–H3, H6–H10
20. mid   B15      Demote schedule edges → user origin
21. high  B16      Full-bus UUID for internal EventTypes (decision → impl)
22. mid   B17      Sauna/IR hardcoded handlers → automation (assess only)
23. mid   B18      Sauna session_end ≤ absolute_cutoff (clamp on arm/adjust)
24. —     Ops      Inbox below when convenient
```

### Why this order

* **D next** — switch vs light typing; benefits Planned Automations and Blocky light/switch wording (**C10** ✅ **Done 2026-08-11**).
* **B10B before B9A** — events catalog shipped first (**done**); sensors/JSON removal is larger and can wait.
* **D after B10B / with C2 consumers** — typing benefits Planned Automations and Blocky light/switch wording; not a Blocky editor rewrite.
* **B9A then E then B9B** — compares/sensors first; Gmail transport (**E**) can start early but **B9B H5 email** waits on E; bathroom/H12/H4 sit on B9A primitives.
* **C3 / C4 later** — Admin force-sweep is powerful but not daily-path; HTML renames are mechanical and safer after shell churn settles.
* **C11 after C4** (default) — re-assess Explorer Control vs History list membership after C10 omits all History `scene` rows; assess → decide → impl if needed. May jump if list confusion hurts. Spec: `phaseC-shell.md` § C11.
* **G2 before G1** — Hue color lie affects daily Explorer; Epson boot query is analysis-gated and rarer. Swap if Epson pain wins. **G2 ≠ C10 Hue hex text** (chrome vs bridge truth; **C10** ✅).
* **G6 after G2** (default) — same integrations surface; scoped reload stops Hue/Onkyo/Z-Wave thrash on Blocky save. **May jump ahead of G2/G1** (or even before D) if save-side bridge flaps / auto-off re-arm hurt more than color lies. Spec: `phaseG-integrations.md` § G6. Kickoff picks scope payload vs YAML fingerprint skip.
* **G7 anytime** — low log-tag parity (`[Onkyo]`); may ship with G6 or alone.
* **G3 anytime** — OWM `poll_interval_mins` 30→10; config-only; only outside source is OWM 30001.
* **G4 after G3** — One Call 4.0 daily assess + hot/full-sun cinema opens to **60% open** (account subscribed ✅); same OWM thread, mid work.
* **G5 after G4** (or alone) — dashboard **“rolluik zon half”** → **60% closed** if cinema not fully closed; retires misnamed half rule. **Still TODO**; partial `Cinema rolluik half` (Open→50) live — gaps in `phaseG-integrations.md` § G5. Uses B10B+D+E `events:` / `dashboard_events`.
* **F when deploying remote access** — independent perimeter track; interleave only when exposing the bridge.
* **Do not fold B10\* into B9\*** — different jobs (trust/events vs sensors/climate). **G2 ≠ B10A** — runtime bridge truth vs Blockly editor chrome (B10A done). **G6 ≠ B10F** — reload *scope* vs Automations UX chrome. **C10 ≠ B10F** (**C10** ✅).
* **B11–B18 stay after F / day-to-day** — lettered ex–Later B; schedule when pain or architecture cutover wins. **B18** (sauna session_end clamp) may jump forward if safety pain wins. Spec: [`phaseB-blocky.md`](phaseB-blocky.md) § B11–B18.

Near-term = **D**. Then **B9A** flexible. **E** may run parallel to B9A; B9B email DoD needs E. **G2** can jump forward if color truth is blocking. **G6** can jump if Blocky-save recycle pain wins. **G7** whenever. **G3** whenever convenient. **G4/G5** when summer heat / cinema sun is the pain.

---

## Now / next (pointers only)

| Step | Detail |
|---|---|
| **D** | [`phaseD-typing.md`](phaseD-typing.md) — infer + override · freeze `entity_id` · 71/72 |
| **B9A** | [`phaseB-blocky.md`](phaseB-blocky.md) § B9A — sensors / thresholds / remove JSON |

---

## Queued

| Phase | Detail file |
|---|---|
| **B9A** / **B9B** / **B11–B18** | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **E** | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **C3** / **C4** / **C11** | [`phaseC-shell.md`](phaseC-shell.md) |
| **G2** / **G6** / **G7** / **G1** / **G3** / **G4** / **G5** | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **F1–F7** | [`phaseF-security.md`](phaseF-security.md) |

### B11–B18 — lettered ex–Later B (pointers)

Detail + DoD stubs: [`phaseB-blocky.md`](phaseB-blocky.md) § B11–B18. Schedule math / demotion constraints: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md). Sauna/IR live safety still: [`sauna-ir.md`](../sauna-ir.md).

| Phase | What |
|---|---|
| **B11** | Multi-flow one Blockly page |
| **B12** | Rule-list folder/tag |
| **B13** | Blockly IF/ELSE / ELSEIF / ELSE |
| **B14** | Remaining HA patterns H1–H3, H6–H10 |
| **B15** | Demote schedule edges → user origin |
| **B16** | Full-bus UUID for internal `EventType`s (decision → impl) |
| **B17** | Sauna/IR hardcoded handlers → automation — **assess only** |
| **B18** | Sauna `session_end_time` ≤ `absolute_cutoff_unix` (clamp on arm/adjust) |

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
| 2026-08-10 | **C6–C9 lock + docs:** one ship ahead of **B10F**. C6 inspect (notMerge wipe) + approach locked. C7 SSE = shared Control+History. C8 log-only line shape (keep `level=`, no id). C9 widened = all device-ref lines in `wanos.log` (mid). No open Qs for C6–C9. |
| 2026-08-10 | **C6–C9 code ship:** soft-merge charts; Explorer C7; `ALERT_UI_DISMISSED`; `core.models.format_device_ref` across integrations. Docs audited. **Open:** combined Pi smoke → then mark Done / resume **B10F**. |
| 2026-08-10 | **C6–C9 → Done** — combined Pi smoke ✅. Sequence starts at **B10F**. |
| 2026-08-10 | **B10F** spec fully locked (fire-status API, evening skip, save chrome, Create SR draft). Sauna session_end clamp → **B18** (not B10F). |
| 2026-08-11 | Inbox triage: **G6** scoped `CONFIG_RELOAD` — Blocky/automations save must not recycle Hue·Onkyo·Z-Wave; Sequence after **G2** (may jump). Spec + DoD in `phaseG-integrations.md` § G6. |
| 2026-08-11 | **B10F code ship:** evening skip; `GET /api/automations/fire-status`; Automations save chrome/lock; Library ↑/↓; UE/SE filters default OFF; empty New rule; SE→SR / UE→UR drafts; inline usages; CRUD INFO logs. **Open:** Pi smoke + Last Docs. |
| 2026-08-11 | **B10F → Done** — Pi smoke ✅. SR name = SE catalog (bind + boot rewrite + usages); CRUD INFO names quoted. Sequence starts at **C10**. |
| 2026-08-11 | **G5** partial live: UE/UR `Cinema rolluik half` (Open→50, dashboard on) — **gaps vs DoD** documented in `phaseG-integrations.md` § G5; phase stays TODO. |
| 2026-08-11 | **C10 spec locked** (operator Q&A): Planned past/done **removed** from list; binary vs non-binary set; motion hits (day Y + month/year counts); History omit all `type === "scene"`. **C11** queued — Control vs History list membership assess (after C4 default). |
| 2026-08-11 | **C10 code** — FE: plural Nodes; Planned past filter; Hue hex text removed; climate legend color pin; binary/hits actuator charts; History omit scenes; blinds search-drag keep. **Open:** Pi smoke + Last Docs → Done. |
| 2026-08-11 | **C10 → Done** — Pi smoke ✅. Last Docs audit ✅. Sequence starts at **D**. |

Detail chronology / DoD checkboxes → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md), [`phaseG-integrations.md`](phaseG-integrations.md).
