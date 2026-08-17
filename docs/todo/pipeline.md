# ⚡ WanOS — Implementation pipeline

High-level **what’s next** and where the detailed specs live. This file does **not** hold phase DoD / locked-decision novels — those live in `phaseX-yyy.md`.

**Last updated:** 2026-08-17

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
| **C** | Operator shell (Explorer, Admin, History charts, force sweep, HTML names, C10–C25) | [`phaseC-shell.md`](phaseC-shell.md) |
| **D** | Device typing (switch vs light) | [`phaseD-typing.md`](phaseD-typing.md) |
| **E** | Gmail transport (OAuth, outbox, spooler) | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **F** | Public bridge / perimeter security | [`phaseF-security.md`](phaseF-security.md) |
| **G** | Integrations (existing reliability G1–G8 + G14 + new vendor bridges G9–G13) | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **P** | Other homes / portability (home vs engine config) | [`phaseP-portability.md`](phaseP-portability.md) |

**Naming note:** Deny-list decision **D1** in Blocky ≠ phase **D**. When a phase completes: move it from **Sequence** → **Done**, and drop its bullet from **Why this order**.

### DoD / close-out (all phases)

**Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

Applies to every phase (and every future phase). Not only `docs/todo/*` — fix stale API/UX names, removed helpers, renamed events, Library kinds, etc. so markdown matches what shipped. Each phase checklist should end with this checkbox (wording above). Detail files own the checkbox; this rule is the standing convention.

### Domoticz Blockly goal — **LOCKED 2026-08-12**

Match [Domoticz Blockly](https://wiki.domoticz.com/Blockly) **look & feel** (If/Do, Compare in If, **Device** trigger, typed device toolbox, Set in Do) — not “same semantics” on the legacy `When` + `case` canvas. Detail → [`phaseB-blocky.md`](phaseB-blocky.md) § Domoticz goal.

**Out of Blockly scope (operator):** user variables · debug/log block · Domoticz **Time** trigger until **after F** (**B20**).

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
| **B1 / B9A** | Blockly parity closeout — Pi smoke + Admin Debug GREEN + docs close-out **2026-08-12** |
| **C10** | Explorer/History polish (plural, Planned past-remove, Hue hex text, chart colors, binary/hits, omit scenes, filter+blinds) — Pi smoke **2026-08-11** |
| **D1 + D2** | Timers & types + `device_product_types`; `zwave.*` / `rfx.*` / vent rehome — Pi smoke + Debug GREEN + migrator delete **2026-08-11** |
| **B10G** | Shell connection + load UX + admin `vNN` + hue preset scoped reload — Pi smoke (A/B/C/D) + docs close-out **2026-08-12** |
| **B10H** | Automations cold-load shorten (~39 s → ~2.1 s TTI) + SSE reconnect flicker fix — Pi smoke + docs close-out **2026-08-12** |
| **B10K + G3** | Timings stopwatch + shutter OPEN/CLOSED + RFX ON/OFF; OWM poll 10′ — Pi smoke + docs close-out **2026-08-15** |
| **B10N** | Closed **2026-08-15** — no dedicated code; operator cannot reproduce; covered by **B10K** Item 3 (`wantHue` excludes `rfxcom`) |
| **C23** | SSE `SseClient` unhashable — `@dataclass(eq=False)` + live EventSource; closed **with C18** (Explorer smoke) **2026-08-16** |
| **C18** | Explorer Control live lag after toggle — Q4/Q5 + live SSE; Pi smoke **2026-08-16** |
| **C19** | Explorer History auto-refresh blank — stale ECharts rebind + soft `replaceMerge` series/dataZoom; Pi smoke + docs close-out **2026-08-16** |
| **C22** | Host CPU temp → `HOST_HISTORY_IDXS`; load 5m/15m live-only — docs close-out **2026-08-16** |
| **Ops1** | log2ram / rsyslog cap — drop `daemon.log`; `$outchannel` wipes `syslog` at 20 MiB; no rsyslog archives — Pi smoke + docs close-out **2026-08-16** |
| **B2 / B9C** | Legacy-canvas bridge — temp/hum ATTR; shutters OPEN/CLOSED/open-% When+if + Set open %; audio ON/OFF/volume; op flip open↔closed — Pi smoke + docs close-out **2026-08-16** |
| **G5** | Dashboard `Cinema rolluik half` — open % > 50 → set 50%; legacy + B9C; DoD revised to live Pi rule — docs close-out **2026-08-16** |
| **B3 / B19+B13** | Domoticz If/Do + Else-if/Else + branches cutover — Pi smoke **2026-08-17**; migrator 7A deleted — docs close-out **2026-08-17** |
| **B4 / H4** | Nested AND/OR/NOT in Compare + OR-list migrator (KeukenLiving + Spare ×3) — Pi smoke + Admin Debug GREEN + migrator deleted — docs close-out **2026-08-17** |

Detail DoD → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md), [`phaseD-typing.md`](phaseD-typing.md), [`phaseG-integrations.md`](phaseG-integrations.md).

---

## Blockly ship groups — **finish before C / G / F**

One PR per row. Detail → [`phaseB-blocky.md`](phaseB-blocky.md) § Domoticz goal.

**B10G** / **B10H** / **B10K+G3** / **B10N** / **C18** / **C19** / **C22** / **C23** / **B2 (B9C)** / **B3 (B19+B13)** / **B4 (H4)** ✅ **Done**. Next: **B5** (**H12** + bathroom). **B10I** / **B10J** / **B10L** / **B10M** / **C20** / **C21** anytime after **B10F** / **B10B** / **B10G** / **B10H** / **B10K** / **C6**.

| Ship | Phase(s) | Size | One go? |
|---|---|---|---|
| **B1** | **B9A** closeout | low | ✅ alone — Pi smoke + GREEN + docs |
| **B2** | **B9C** legacy bridge | mid | ✅ **Done 2026-08-16** — temp/hum ATTR; shutters OPEN/CLOSED/% + Set open %; audio ON/OFF/volume; enabled **G5** (✅ Done same day) |
| **B3** | **B19** + **B13** | **high** | ✅ **Done 2026-08-17** — If/Do canvas + Else-if; Pi smoke OK |
| **B4** | **B9B H4** only | high | ✅ **Done 2026-08-17** — nested AND/OR/NOT in Compare; 4 OR-list leftovers migrated; `b_trig_or` removed |
| **B5** | **B9B H12** + bathroom | mid | ✅ alone |
| **B6** | **B9B H5** Messages | mid | ✅ alert alone; Gmail half when **E** ready |
| **B7** | **B14** (no Time trigger) | high | ✅ together — timed Set, delay, cooldown, … |
| **B8** | **B11** + **B12** | mid | ✅ together — multi-flow (**all matching If/Do fire**) + folder/tag |

**After F:** **B20** — Domoticz **Time** trigger (every-minute model). **Not** in cluster above.

**Not Blockly UX:** **B15** · **B16** · **B17** (assess) · **B18** — general pipeline after cluster / **F** as today.

### Parallel tracks (within / beside cluster)

**Hard gates (no parallel — same PR surface or migrator risk):**

| Gate | Rule |
|---|---|
| **B3** (B19+B13) | ✅ **Done 2026-08-17** |
| **B10H → B2** | ✅ **B10H Done** → ✅ **B2 Done** |
| **B2 → B3** | ✅ **B9C Done** → ✅ **B3 Done** |
| **B3 → B4** | ✅ **B3 Done** → ✅ **B4 Done** (H4 + OR-list cutover) |
| **B4 → B7** | Timed Set / delay patterns prefer Logic stable (**B14** stub) |
| **B7 → B8** | Library org (multi-flow + folder) after canvas + control blocks stable |

**Safe to parallel (separate surfaces or explicit operator lock):**

| Track | When | Notes |
|---|---|---|
| **B10I** | Anytime after **B10F** | Library navigation only — parallel to **B2–B8** |
| **B10J** | Anytime after **B10B** | Backend log polish — **`Event Received`** catalog name; parallel to **B2–B8** |
| **B10L** | Anytime after **B10G** | Shared NOT CONNECTED overlay status + copy **Re-connecting to WanOS...**; parallel to **B2–B8** |
| **B10M** | Anytime after **B10G** Part D | Explorer Hue preset duplicate settings; parallel to **B2–B8** |
| **C20** | Anytime after **C2** / **C8** | bugfix: Admin bell Clear All does nothing — kickoff **locked** 2026-08-15; parallel to **B2–B8** |
| **C21** | Anytime | bugfix: Explorer AUTO OFF countdown while device already OFF; parallel to **B2–B8** |
| **E** (Gmail transport) | After **B3** or default after cluster | Parallel to **B5–B8**; **B6** alert ships without **E**; H5 email half waits **E** |
| **Ship B5 ∥ Ship B6** | After **B4** | Bathroom/H12 vs Messages alert — independent; OR-heavy notify rules still want **B4** first |

**Default pipeline order** below is the conservative merge sequence when not running parallel tracks.

---

## Sequence

**Size** = relative delivery weight (rough): **low** = small/local · **mid** = multi-file or careful edge cases · **high** = schema/API/engine or large surface. Not calendar days.

```text
#  Size   Phase / Ship   What
─── Blockly cluster (operator: B5…B8 before shell/integrations/F; B3–B4 ✅) ───
1.  mid    B5           B9B H12 hysteresis + bathroom climate cutover
2.  mid    B6           B9B H5 Messages (alert; + email when E)
3.  high   B7 / B14     timed Set, delay, cooldown, remaining HA patterns (no Time trigger)
4.  mid    B8           B11 multi-flow (all matching If/Do) + B12 folder/tag
─── Parallel beside cluster (after gates above) ───
7b. low    B10I         used SE → Go to SR — **∥ cluster** (anytime after B10F)
7c. low    B10J         Event Received log — catalog display name (not raw UUID) — **∥ cluster** (anytime after B10B)
7e. low    B10L         NOT CONNECTED overlay status + copy “Re-connecting to WanOS...” — **∥ cluster**
7h. low    B10M         bugfix: Explorer Hue preset duplicate settings — **∥ cluster** (after B10G Part D)
7j. low    C20          bugfix: Admin SYSTEM NOTIFICATIONS Clear All does nothing — kickoff **locked** — **∥ cluster**
7k. low    C21          bugfix: Explorer AUTO OFF countdown while device already OFF — **∥ cluster**
─── After Blockly cluster (E may start ∥ B5–B8 instead — see Parallel tracks) ───
8.  high   E            Gmail transport / outbox — default slot; **∥ B5–B8** OK
9.  mid    C3           Force ALL-OFF
10. mid    C4           Rename HTML entrypoints (`blocky`→`blockly`; not `automations`)
11. low    C11          Control vs History list membership (assess → decide)
12. mid    C12          Post-C10 polish (+ Hidden preset admin-only)
12b. low   C17          Alert banner dismiss vs reload (assess at kickoff)
13b. mid   C16          Day chart sliding 24 h window over hires_days hi-res
13c. mid   C24          Temp/hum day fullscreen + AH/CI + checkboxes + CSV (after C16)
13d. mid   C25          Overlay dew-likelihood % (OWM 2.5 clouds/wind; after C24)
13e. low   C15          Admin lab switch → Debug Commands row; lab pane iff ON
14. mid    C13          Merge Hidden → Timers & types
15. mid    G2           bugfix: Hue color/bri truth
16. mid    G6           bugfix: Scoped CONFIG_RELOAD + Admin modal + Automations deferred Save config (`hue_presets` path ✅ B10G Part D)
17. low    G7           Integration log tags
17b. mid   G8           bugfix: Boot autostart timing — shorten real enable + honest Admin UX (A+B)
17c. mid   G14          bugfix: Manual integration enable — enabling status + ON bell (assess all)
18. mid    G1           bugfix: Epson get_power_state
19. mid    G4           OWM One Call + hot-sun cinema 60% open
19b. high  G9           Honeywell / Evohome — **own ship** (1/5)
19c. high  G10          HomeWizard energy — **own ship** (2/5)
19d. high  G11          Samsung Airco — **own ship** (3/5)
19e. high  G12          SMA solar — **own ship** (4/5)
19f. high  G13          HomeConnect BSH — **own ship** (5/5)
20. high   F            Security bridge (F1→F7)
─── After F ───
21. mid    B20          Domoticz Time trigger + time-compare blocks
22. mid    B15          Demote schedule edges → user origin
23. high   B16          Full-bus UUID for internal EventTypes
24. mid    B17          Sauna/IR hardcoded → automation (assess only)
25. mid    B18          bugfix: Sauna session_end ≤ absolute_cutoff
26. —      Ops          **Ops1** ✅ Done; remaining **Ops1 later** + other Inbox when convenient
─── Very low (after everything above) ───
27. high   P            Other homes / portability — home-specific config vs engine (assess)
```

### Why this order

* **B1 B9A** — ✅ **Done 2026-08-12** (Pi smoke + Debug GREEN + docs close-out). Hue preset **reload/perf** polish → **B10G Part D** (✅).
* **B10G** — ✅ **Done 2026-08-12** (Parts A–D Pi smoke + docs).
* **B10H** — ✅ **Done 2026-08-12** — cold open ~**2.1 s** TTI; SSE reconnect flicker fixed; detail → [`phaseB-blocky.md`](phaseB-blocky.md) § B10H.
* **B10H follow-up (deferred)** — list / v2 cache for sub-**500 ms** cold open — **triage 2026-08-12: defer**; detail § **B10H — deferred list cache** below.
* **G8** — boot autostart timing (~30s “integrations disabled”) — **A+B** ship; separate from **B10H** — detail § **G8** below.
* **Blockly cluster B3–B8** — operator lock **2026-08-12**: [Domoticz Blockly](https://wiki.domoticz.com/Blockly) **look & feel** before Explorer/integrations/F churn. **B2 (B9C)** ✅. **B3 (B19+B13)** ✅ **Done 2026-08-17**.
* **B2 B9C** — ✅ **Done 2026-08-16** — today’s canvas (temp/hum + shutters/audio `%` When+if + Set open %).
* **B3 B19+B13** — ✅ **Done 2026-08-17** — Domoticz If/Do + Else-if/Else (first-match) + branches; migrator 7A deleted.
* **B4 H4** — ✅ **Done 2026-08-17** — nested AND/OR/NOT in Compare; KeukenLiving + Spare Button ×3 migrated; Admin Debug GREEN; migrator deleted.
* **B5–B6** — bathroom / notify on Domoticz blocks; **Ship B5 ∥ Ship B6** if capacity allows; **H5 email** still waits on **E** (alert ships first).
* **B7 B14** — timed **Set**, delays, cooldowns — **excludes** Time trigger (**B20**).
* **B8** — library organization + multi-flow (all matching If/Do) after canvas + **B7** stable.
* **G5** — ✅ **Done 2026-08-16** — `Cinema rolluik half` on legacy + **B9C** (DoD revised to live Pi rule; not after B19).
* **B10I** — Library **Go to SR**; **parallel to cluster** (no B19 dependency).
* **B10J** — **`Event Received`** log lines: resolve catalog **display name**; **parallel to cluster**.
* **B10K + G3** — ✅ **Done 2026-08-15** — timings stopwatch; shutter OPEN/CLOSED; RFX ON/OFF no color; OWM poll 10′.
* **B10N** — ✅ **Done 2026-08-15** — closed without dedicated code; operator cannot reproduce; covered by **B10K** Item 3.
* **B10L** — Shared NOT CONNECTED overlay richer status; establishing line → **Re-connecting to WanOS...**
* **B10M** — Explorer Hue preset: allow new preset with same settings as an existing one; **∥ cluster**.
* **C18** — ✅ **Done 2026-08-16** — Explorer Control live lag. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C18.
* **C19** — ✅ **Done 2026-08-16** — Explorer History 60s auto-refresh keeps series + window (**C6** soft path; stale instance rebind + `replaceMerge` series/dataZoom). Detail → [`phaseC-shell.md`](phaseC-shell.md) § C19.
* **C20** — Admin bell **Clear All** no-op; **∥ cluster**. Kickoff + contract **locked** 2026-08-15. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C20.
* **C21** — Explorer **AUTO OFF** countdown while device already OFF; **∥ cluster**. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C21.
* **C22** — ✅ **Done 2026-08-16** — Host CPU temp (`22001`) history; load 5m/15m live-only. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C22.
* **C23** — ✅ **Done 2026-08-16** — closed **with C18**; `SseClient` `@dataclass(eq=False)` in the hub `set`; Explorer EventSource. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C23.
* **C24** — temp/hum **day** overlay fills the **browser tab** (not F11); 24 h window; CSV of `hires_days`; AH 3rd y-axis; checkboxes only; **after C16**. Frost line stays **C12 #8**. Do not reopen **C5**. Kickoff **locked** 2026-08-16. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C24.
* **C25** — overlay **dew likelihood %** (heuristic, not calibrated probability); OWM Current 2.5 clouds/wind + rain→0; **after C24**; do not reopen C24. Detail → [`phaseC-shell.md`](phaseC-shell.md) § C25.
* **G14** — Manual enable after network-failure disable: **enabling** → **Live** + ON bell; assess all integrations (not G8 boot).
* **C\*, G\*, E, F** — **after Blockly cluster** (default). **E** may start **parallel to B5–B8**. **G2/G6** may jump on operator pain. **G9→G13** — one new vendor bridge per run, after **G4**, before **F**.
* **B20 after F** — Domoticz **Time** trigger; catalog schedule events unchanged until then.
* **B15–B18** — not Domoticz L&F; **B18** may jump on sauna safety pain.
* **P** — other homes / portability — **very low**; after **F** and **B15–B18**. Home vs engine must be obvious; extraction **propose + ask**. Overlaps **B17** (sauna/IR). Detail → [`phaseP-portability.md`](phaseP-portability.md).

Near-term = **B5** (H12 + bathroom) → (**B5** ∥ **B6**) → **B7** → **B8**. **B10I** / **B10J** / **B10L** / **B10M** / **C20** / **C21** / **E** may run beside cluster per § Parallel tracks. **No** user-variable or debug Blockly blocks.

---

## B10G — connection + load UX ✅ Done 2026-08-12

**Shipped:** Parts A + B + C + D — Pi smoke OK (operator **2026-08-12**). Detail / archive → [`phaseB-blocky.md`](phaseB-blocky.md) § B10G. Cold-load shorten → **B10H** ✅.

| Part | What shipped |
|---|---|
| **A** | Two overlays; yellow load checklist + Resource Timing admin modal + console; REST heartbeat 10s; `wanos_debug.log` **out of DoD** |
| **B** | SSE **A+B+C** (`wanosApp` + `zwaveconfig`); scope-specific reload alerts; suppress during reload |
| **C** | Admin-only **`v1`** on eight shell pages (`kiosk` / `login` excluded) |
| **D** | `hue_presets` scoped reload + Explorer chip/save-disable; Pi smoke &lt;2s / no recycle |

### Automations — two overlays (shipped)

**Automation (`blocky.html`) has two separate overlays:**

| # | Overlay | Source | When | Copy / UX |
|---|---|---|---|---|
| **1** | **Shared offline** | `data-wanos-offline` → `wanos-shell.js` `offlineOverlay()` — **same chrome as Explorer / Admin** | Backend unreachable while page is open | Red **NOT CONNECTED** — `Establishing connection stream to WanOS backend...` |
| **2** | **Loading config** (Automations only) | Page-local checklist (Part A) | Cold `init()` → `refreshAll()` only — **not** post-save refresh | Yellow — friendly-label **checklist + checkboxes** + duration per step at completion |

**Blockly workspace** (`loadV2IntoBlockly` / `scheduleBlocklyLoad`) stays **after** overlay **2** clears.

**Alpine flags:** **`connected`** drives overlay **1** (`data-wanos-offline`); **`editorLoading`** drives overlay **2** (checklist).

### System — check backend connection (locked)

Two **phases** on Automation; one **continuous** model on SSE pages.

#### Automation (`blockyApp`)

| Phase | When | How backend is checked | Overlay |
|---|---|---|---|
| **Load** | `editorLoading === true` — cold `init()` → `refreshAll()` | **Each load step is a live check** — parallel `GET /api/state`, `/api/automations`, `/api/events`, then fire-status, etc. | **2** (yellow checklist) while steps run |
| **Running** | After `refreshAll()` succeeds — `editorLoading === false` | **REST heartbeat** — `GET /api/state` (auth) **every 10000ms** when tab visible + on `visibilitychange` (no polling while hidden) | **1** (red shared offline) if heartbeat fails |

**Periodic heartbeat does not run during `editorLoading`** — avoids a second poller racing the load fetches and flipping overlay **1** while overlay **2** is active. **Load fetches are the connection check during config load.**

**Failure rules (locked):**

* Any `refreshAll()` HTTP/network failure → **hide overlay 2**, show overlay **1** (`shellConnected=false`) — no stuck yellow checklist.
* Heartbeat failure while editor is open → overlay **1** only.

**Example — reload Automation page after `wanos` stopped:**

1. `init()` → `editorLoading=true` → overlay **2** (checklist) may appear briefly.
2. `refreshAll()` fetches fail immediately (connection refused / network error).
3. `editorLoading=false`; `shellConnected=false` → overlay **1** red **NOT CONNECTED** (shared `data-wanos-offline`).
4. REST heartbeat does not start (load never succeeded).

**Example — backend dies after successful load:**

1. Editor open; heartbeat running.
2. Next heartbeat `GET /api/state` fails → `shellConnected=false` → overlay **1**.

#### SSE pages (`wanosApp` — Explorer, Admin, WISC, History)

| Phase | How | Overlay |
|---|---|---|
| **Connect** | `GET /api/state` snapshot, then `EventSource /api/state/sse` | **1** until snapshot or first SSE frame |
| **Running** | SSE stream + **10s watchdog** (reset on any message incl. **5s ping**) | **1** on sustained loss / `onerror` (see Part B fix) |

**Part B fix (shipped T4 — A+B+C):** debounce SSE `onerror` (3000ms grace); clear on first reconnect `ping` (cancel pending debounce offline display); **suppress shared offline overlay** during config reload (exact per-scope alert strings).

### Part A — load checklist (locked)

| # | Friendly label (overlay) | API (in log / modal line) |
|---|---|---|
| 1 | Device state | `GET /api/state` |
| 2 | Automations | `GET /api/automations` |
| 3 | Events | `GET /api/events` |
| 4 | Building library | *(step name — parse + rebuild)* |
| 5 | Schedule status | `GET /api/automations/fire-status` |

Steps 1–3 parallel; check off in completion order.

**Timings (B10G shipped; open trigger changed in B10K):** browser console + admin-only floating modal (Resource Timing: wire TTFB / fetch→byte / nav→byte / queue / dl / before fetch). **B10K:** no auto-open — stopwatch right of `vNN`. **`wanos_debug.log` — out of B10G DoD**.

HTTP/network failure on cold load → **red shared offline** (overlay **1**) immediately — no lingering yellow checklist. **Cold `init()` only** for overlay **2**.

**Overlay 2 copy (locked):** heading **`Loading automation editor...`** + friendly-label checklist rows with **checkboxes** + duration per line at completion. **No** NOT CONNECTED heading on overlay **2** (that belongs to overlay **1** only).

**`data-wanos-offline` binding (locked):** shared shell injects `x-show="!connected"`. On Automation, expose **`connected`** on `blockyApp` as the driver for overlay **1** (may alias `shellConnected` internally — one public `connected` for shell parity with other pages).

### Part B — NOT CONNECTED assess + fix (2026-08-12)

**Assess:** code review — findings below (**done 2026-08-12**). **Fix:** **A+B+C** — Pi repro **confirmed 2026-08-12** (~4s NOT CONNECTED, multiple times per config reload).

**Operator report:** NOT CONNECTED appears regularly — **including on Admin config reload**, not only cold open or true outage.

#### How `connected` works (SSE pages — Explorer, Admin, WISC, History)

* Shell injects overlay via `data-wanos-offline` + `x-show="!connected"`.
* `wanosApp().connectSSE()`: `GET /api/state` snapshot → `EventSource /api/state/sse` → **10s watchdog** (no frame → `connected=false` + reconnect).
* `connected=false` on: initial load, **SSE `onerror`**, watchdog timeout.
* `connected=true` on: snapshot applied **or** any SSE message (incl. **5s `ping`** when domains quiet).
* Reconnect: `onerror`/watchdog → wait **3s** → new snapshot + new SSE — overlay stays until snapshot/SSE proves alive.

**Config reload path:** Admin `CONFIG_RELOAD_REQUESTED` (`source: ui_button`) → full bridge recycle (Hue, RFX, Sonos, Onkyo, …) + domain deltas + passive sweep 2s later. Does **not** set `connected=false` on the button — but heavy handler can coincide with SSE stall → **onerror** or slow `/api/state` on reconnect → overlay flash.

#### Root causes (ranked — assess 2026-08-12; repro **confirmed**)

| Rank | Cause | Mechanism |
|---|---|---|
| **1** | **SSE reconnect flash** | Brief `onerror` → full NOT CONNECTED until reconnect + snapshot — backend may be fine |
| **2** | **Slow `/api/state` on reconnect** | Overlay duration = snapshot latency, not outage |
| **3** | **10s watchdog** | No SSE frame 10s (load, tab throttle, Pi spike during reload/sweep) |
| **4** | **Automations UX confusion** | Today single overlay says NOT CONNECTED during yellow load (~15s) — fixed by **two-overlay** split (Part A) |
| **5** | Timers/Hidden REST-only pages | Yellow “Loading…” on first fetch only — lower risk for config-reload report |

**Verdict:** Spurious NOT CONNECTED is **plausible without backend down** — primarily **client reconnect policy** (`connected=false` on transient SSE error + mandatory snapshot before clear). Config reload is a **likely trigger**, not a separate server bug.

**Pi smoke (Part B):** Admin **config reload** while Explorer (or Admin) open — no spurious shared offline overlay if fix shipped.

#### Part B — operator repro (before shipping fix)

Run on **Pi** with browser devtools console open. Record **Y/N** flash, page, and any `SSE stream broke` / `Watchdog Timeout` lines.

| Step | Action |
|---|---|
| 1 | Open **Device Explorer** (or **Admin**); wait until fully loaded (no overlay). |
| 2 | Open **Admin** in same or second tab → **Reload config** (GO). |
| 3 | Watch Explorer (or stay on Admin): did full-screen **NOT CONNECTED** appear when backend was still up? |
| 4 | Repeat with **Automation** open in one tab, Admin reload in another (optional). |
| 5 | Note `wanos.log` / console timestamp vs `Config reloaded` alert. |

**Decision (2026-08-12):** Flash **confirmed** — ship Part B **A+B+C** (see operator repro below).

**Operator repro 2026-08-12:** **Confirmed** — after Admin config reload, NOT CONNECTED shows for **~4s** (not a brief flash), **multiple times** per reload (2nd shorter, 3rd longer). Part B **A+B+C** is in scope for B10G.

#### Part B fix — SSE pages (locked T4: **A + B + C**)

| Option | Ship? |
|---|---|
| **A** Debounce showing shared offline overlay on SSE `onerror` (**3000ms** grace; no offline UI during grace) | ✅ |
| **B** Clear `connected` on first reconnect `ping` (**within the grace window**, before full snapshot) and cancel the pending offline display | ✅ |
| **C** Suppress shared offline during **config reload** on **all** pages that use the shared offline overlay (including `zwaveconfig.html`) | ✅ |

Apply **A+B+C** on `wanosApp` (Explorer, Admin, WISC, History) **and** on `zwaveconfig.html` (`zwaveApp`).

**REST-only admin pages (`hiddendevices.html`, `lightingautooff.html`) — out of Part B (locked 2026-08-12):** no SSE stream; `connected` set once on initial REST load (not on stream `onerror`); yellow Loading overlay only. Operator: **no NOT CONNECTED repro** on those pages. Part B targets the SSE reconnect flash — not applicable here unless a future repro says otherwise.

**T4 C detail (locked):** suppress overlay while reload is in progress on **any** page (incl. `zwaveconfig.html`) — signal via **`system_alert_msgs` on SSE** (`system` domain), **not** Admin-local `configReloading` / GO-button flag.

**Reload alert copy (locked 2026-08-12 — scope-specific text, three alert levels):** each reload emits a **scope-specific** in-progress → complete/failed pair. **Three UI levels** (bell colours): in-progress = **`info`** (🔄), complete = **`success`** (🟢), failed = **`error`** (`ERROR:` prefix — bell only, not banner).

| Scope key | In-progress (`info`, 🔄) | Complete (`success`, 🟢) | Failed (`error`, `ERROR:`) |
|---|---|---|---|
| **`full`** (Admin button; API `source: api` **without** `scope`; unscoped writers until G6) | `🔄 Reloading all config…` | `🟢 All config reloaded.` | `ERROR: All config reload failed: …` |
| **`hue_presets`** | `🔄 Reloading hue presets…` | `🟢 Hue presets reloaded.` | `ERROR: Hue presets reload failed: …` |
| **`timers_types`** | `🔄 Reloading timers & types…` | `🟢 Timers & types reloaded.` | `ERROR: Timers & types reload failed: …` |

**Unscoped API writers (locked 2026-08-12 — Option A):** automations CRUD, events CRUD, soft-hide save, Z-Wave config save dispatch **without** `scope` and run **full** recycle → use **`full`** alert row until **G6** migrates each writer (**scope payload + scoped handler + scope alert row together** — see [`phaseG-integrations.md`](phaseG-integrations.md) § G6 reload alerts follow-up). **Do not** emit intent-specific alerts while handler still full-recycles.

Suppress window (T4 C): match **exact per-scope strings** from the table (after `AlertManager` emoji strip) for in-progress → complete/failed — **not** a generic `Reloading` prefix. **`hue_presets` fast path must emit its scope row** (re-run Pi smoke — B9A code shipped; verify on Pi).

Admin GO: replace legacy `🔄 Reloading all config yaml configurations…` with locked **`full`** in-progress row (`🔄 Reloading all config…`).

**Code check (2026-08-12):** only Admin `requestConfigReload()` injects a reload-in-progress alert today; API `CONFIG_RELOAD` paths dispatch reload **without** it. Part B + Part D must emit the **scope-specific** in-progress + complete/failed alerts for **every** `CONFIG_RELOAD_REQUESTED` source — do **not** wire suppress only to Admin’s button state.

**Recap:** SSE problem = **client reconnect policy**, not backend down. Automation = **two overlays** + load-as-check + post-load heartbeat (§ **System — check backend connection**).

### Part C — admin `vNN` (eight shell pages)

**Locked 2026-08-12:** **Every operator HTML page** — integer **`vNN`** right of title; **admin-only**; **each page starts at `v1` with its own counter**; bump that page when **its** HTML or **its** linked JS changes (shared `wanos-shell.js` / `app.js` → bump **every HTML page that includes them** at ship). **No separate JS file version badge** — not visible in UI; page `vNN` is the operator cache-bust indicator (see Q6 note in phase file). Placement: right of page title per [`html-standards.mdc`](../.cursor/rules/html-standards.mdc). Agent reports bumped `vNN` per touched page on ship.

**Pages (each `v1` at B10G ship):** `blocky.html`, `deviceexplorer.html`, `admin.html`, `sensorhistory.html`, `commander.html`, `zwaveconfig.html`, `lightingautooff.html`, `hiddendevices.html`. **`login.html` excluded** (auth gate). **`kiosk.html` excluded** (no admin shell; operator lock **2026-08-12**).

---

## B10H — deferred list cache (step 7c) — triage 2026-08-12

**Origin:** B10H Pi smoke after step 7 (N+1 YAML fix) — cold open ~**2.1 s**; remaining wall ≈ parallel `GET /api/automations` + `GET /api/events` (~**2 s** wire TTFB each). Operator asked to triage in-memory list cache at boot.

| Factor | Assessment |
|---|---|
| **Current TTI** | ~**2.1 s** — meets ~**2 s** aspirational goal |
| **Remaining cost** | One YAML parse + `legacy_to_v2` × ~79 rules (Pi CPU) — not N+1 |
| **Cache benefit** | Warm **repeat** opens → ~100 ms class; **first** cold open unchanged unless pre-warmed before any UI hit |
| **Cache cost** | Invalidate on every automations/events CRUD; stale-list risk if a writer is missed; more B10H surface |
| **Verdict** | **Defer** — do **not** ship in B10H close-out. Revisit only if operator wants **&lt; 500 ms** cold open or faster rule-save → library refresh |

**Cheaper future lever (if reopened):** pre-convert v2 once at boot (same invalidation story; no double cache layer). Detail → [`phaseB-blocky.md`](phaseB-blocky.md) § B10H.

**Not this item:** reconnect policy / Admin flicker → **B10H** ✅ (SSE R1–R3); post-restart ~10 s offline → **G8**; Explorer Control live lag → **C18** ✅.

---

## G8 — Boot autostart timing (integrations “disabled” ~30s)

**Origin:** operator inbox **2026-08-12** (bootlog `bootlog.log`). **Separate from B10G** (Automations overlays / NOT CONNECTED) and **B10H** (Automations cold-load shorten). Detail stub → [`phaseG-integrations.md`](phaseG-integrations.md) § G8.

**Problem:** After `wanos` restart with `WANOS_AUTOSTART=true`, Admin shows integration master switches **DISABLED** for **~26–30s** after HTTP/SSE is already online — even when autostart eventually succeeds. Bootlog (2026-08-12): HTTP **10:53:56** → Master Start **10:54:01** (+5s delay) → first toggle **10:54:11** (simulator sync `load_config()` blocks event loop ~10s) → remaining toggles **10:54:22** (~11s after first). Bridges (Hue, RFX, Z-Wave) already `start()` in `lifespan` before autostart; Admin reads `*_integration_enabled` flags, which default **false** until toggle events drain.

**Ship:** **A + B** together (one PR). **Out of scope for G8:** persist enabled flags to NVM across reboot (design fork — track separately if wanted).

### Option A — shorten real enablement (backend)

| Lever | Where | Effect |
|---|---|---|
| **Offload `load_config()`** | `hardware/simulator.py`, `core/event_handlers/system_handlers.py` | `await asyncio.to_thread(load_config)` — unblocks autostart queue (~10s on Pi bootlog) |
| **Single `MASTER_START` event** | `main.py`, new handler + `registry.py` | Set all `*_integration_enabled` atomically; **one** SSE/MQTT broadcast — avoids staggered “Automations first, rest 11s later” |
| **Trim / overlap 5s autostart delay** | `main.py` `delayed_autostart` | Saves 5s; trade network/USB settle time |
| **Non-blocking bridge spin-up** | `integration_handlers.py` (Sonos / Onkyo) | `create_task(bridge.start())` instead of `await` inside toggle handler |
| **Boot timing logs** | `main.py` / autostart handler | Master Start → each flag true → first full snapshot — confirms fix on Pi |

**Assess at kickoff:** profile `state_manager` post-toggle `on_state_changed` if gap persists after thread offload.

### Option B — honest Admin UX (perceived fix)

| Lever | Where | Effect |
|---|---|---|
| **`system.autostart_in_progress`** | `core/models.py`, `main.py`, SSE `system` domain | Cross-tab signal while `WANOS_AUTOSTART` sequence runs |
| **Admin integration rows** | `frontend/admin.html`, `app.js` | Third state: **STARTING** / **ARMING** (Z-Wave defer) vs plain **DISABLED** |
| **Z-Wave copy** | Admin + alerts | Match “deferred until MQTT data” log — not “disabled” |

**Schedule:** default **after Blockly cluster** (with **G2–G7**); may jump if boot UX pain wins (like **G6**). **Not** blocked on **B10G**.

---

## Now / next (pointers only)

| Step | Detail |
|---|---|
| **B5 / H12** | [`phaseB-blocky.md`](phaseB-blocky.md) § Phase B9B — bathroom + hysteresis (H4 ✅ in **B4**) |
| **Domoticz goal** | [`phaseB-blocky.md`](phaseB-blocky.md) § Domoticz goal + ship groups |

---

## Queued

| Phase | Detail file |
|---|---|
| **B19** / **B9B** / **B10I** / **B10J** / **B10L** / **B10M** / **B11–B20** | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **E** | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **C3** / **C4** / **C11** / **C12** / **C17** / **C20** / **C21** / **C16** / **C24** / **C25** / **C15** / **C13** | [`phaseC-shell.md`](phaseC-shell.md) |
| **G2** / **G6** / **G7** / **G8** / **G1** / **G4** / **G9** / **G10** / **G11** / **G12** / **G13** / **G14** | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **F1–F7** | [`phaseF-security.md`](phaseF-security.md) |
| **P** | [`phaseP-portability.md`](phaseP-portability.md) |

### B11–B20 — lettered Blocky / automation (pointers)

Detail + DoD stubs: [`phaseB-blocky.md`](phaseB-blocky.md) § B11–B20. Schedule math: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

| Phase | What | Ship |
|---|---|---|
| **B10I** | Used SE → Go to SR | anytime after B10F |
| **B10J** | Event Received log — catalog name | anytime after B10B |
| **B10L** | NOT CONNECTED overlay status + **Re-connecting to WanOS...** | anytime after B10G |
| **B10M** | Explorer Hue preset duplicate settings | anytime after B10G Part D |
| **B11** | Multi-flow one Blockly page — **all matching If/Do fire** (reunite CINEMA OFF / Evening lights on) | **B8** |
| **B12** | Rule-list folder/tag | **B8** |
| **B13** | Domoticz Else-if / Else | ✅ **Done** with **B19** / **B3** |
| **B14** | Timed Set, delay, HA patterns (no Time trigger) | **B7** |
| **B15** | Demote schedule edges → user origin | after **F** |
| **B16** | Full-bus UUID internals | after **F** |
| **B17** | Sauna/IR → automation assess | after **F** |
| **B18** | Sauna session_end clamp | may jump |
| **B19** | **Domoticz If/Do canvas** | ✅ **Done** Ship **B3** **2026-08-17** |
| **B20** | Domoticz **Time** trigger | after **F** |

---

## Inbox — Ops / Manual (2026-08-09)

Not lettered product phases. Unclear parts marked **to be checked**.

### Ops1 — log2ram / rsyslog ✅ **Done 2026-08-16**

**Code:** **Ops1** (Ops band — not B/C/D/E/F/G/P). Detail stays in this file (no `phaseX-*.md`). **Done** table + shipped summary below. Optional follow-ups stay here as **Ops1 later** (not Sequence).

**Origin (verbatim 2026-08-16):** put these 3 "What actually prevents a repeat" in triage — (1) SSE flood → **C23** ✅ · (2) cap rsyslog → **Ops1** ✅ · (3) uvicorn access/JWT → **Ops1 later**.

**Shipped:** drop `daemon.log`; rsyslog `$outchannel wanos_syslog_cap` truncates `/var/log/syslog` at **20 MiB** (no `.1`/`.gz`); weekly logrotate for other rsyslog files only. Repo: `helpers/wanos_rsyslog_logcap.sh` + `wanos-syslog-truncate.sh` + `logrotate.rsyslog` (mirrored). Phase 1 **6b**. Apply: `sudo bash /home/wannes/wanos/helpers/wanos_rsyslog_logcap.sh`. Install: [`wanos-install-backend.md`](../../helpers/bootstrap/backend/wanos-install-backend.md) § **1.3**.

**Pi smoke:** rsyslog 8.2102.0; log2ram **16%**; `wanos.log` + `journalctl -u wanos.service` live; outchannel + commented `daemon.log` confirmed (`sudo grep`).

**DoD / Last DoD:** ✅ **2026-08-16**.

#### Ops1 later (optional; not Sequence)

| Later | What |
|---|---|
| **Item 3** | uvicorn `--no-access-log` / no `?jwt=` (`wanos.service` / bootstrap). Not **F** unless re-homed. |
| **ForwardToSyslog** | Stop journald → rsyslog forwarding. |
| **log2ram SIZE** | Shrink live **1.0G** toward bootstrap **256M**. |
| **auth.log / kern.log** | Same “no archive” policy as `syslog`. |

### Ops — sync Local → Pi

**Done 2026-08-15:** **`.cursor`** is in `[MirrorExcludeDirs]` (`helpers/wanos-sync.config.txt`). IDE rules are not mirrored Local→Pi. Documented in [`docs/wanos-sync.md`](../wanos-sync.md). If an older run already copied `.cursor` to the Pi, exclude will not delete it — one-time remove on the Pi if needed.

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
| **Cinema — merge ON/OFF rules** | Collapse **`--- CINEMA ON`** + **`--- CINEMA OFF`** → one **`switch cinema`** rule. **Pickable “cinema state”** (likely **`switch.epson`**) as condition — **to be checked**. Shutter **%** compares ✅ **B9C**. Operator YAML on Pi. |
| Background Leak = **0.0 W** | Verify — **check!** |
| Where is the **3-phase kWh meter** connected? | Site / wiring — **manual** |
| Where do the **Pis** get power? | Site / UPS / circuit — **manual** |

*(Hue badkamer red / color truth → **G2**. Hue preset CRUD → **B9A**.)*

---

## Change log (short)

| When | What |
|---|---|
| 2026-08-17 | **B4 / H4 ✅ Done** — nested AND/OR/NOT; Pi migrator (4 rules); Admin Debug GREEN; `b_trig_or` removed; `blocky.js?v=26` / schema 54; migrator deleted post-soak. Docs close-out. Next **B5**. |
| 2026-08-17 | **B3 / B19+B13 close-out** — operator Pi smoke OK; Last DoD docs audit; post-smoke polish (branch load, save persist, registry banner, duplicate error). Four OR leftovers closed same day under **B4**. |
| 2026-08-16 | **B4 / H4 kickoff locked (Domoticz-faithful)** — nested AND/OR/NOT; level Compare only (no became); Pi migrator KeukenLiving level-OR + Spare ×3; skip+report; remove `b_trig_or`. Detail → [`phaseB-blocky.md`](phaseB-blocky.md) § Ship B4 / H4. |
| 2026-08-16 | Inbox triage: **B11** (Ship **B8**) — multi-flow must support **all matching If/Do fire** so one Library rule can reunite B19 migrator splits (**CINEMA OFF**, Evening lights on). Not H4; Else-if stays first-match. Operator: *“this should be possible - put that in the pipeline where it fits”*. |
| 2026-08-16 | **B19+B13 kickoff locked** — Ship **B3** = Domoticz If/Do + Else-if/Else (first-match); no authoring trigger; Compare/event wake; hybrid branch YAML; **B4** = H4 only. Detail → [`phaseB-blocky.md`](phaseB-blocky.md) § B19. |
| 2026-08-16 | **G5 ✅ Done** — DoD revised to live Pi rule `Cinema rolluik half` (open % > 50 → set 50%; legacy + B9C); docs close-out. |
| 2026-08-16 | **B2/B9C ✅ Done** — Pi smoke OK; temp/hum ATTR; shutters OPEN/CLOSED/open-% When+if + Set open %; audio ON/OFF/volume; `blockyInvertCompareOp`; `wanoslog.sh log 4 debug`; docs close-out. Next **B3** (B19). |
| 2026-08-16 | Inbox triage: **C25** overlay **dew likelihood %** from OWM 2.5 clouds/wind (heuristic list accepted); **after C24**; do not reopen C24. |
| 2026-08-16 | **Ops1 ✅ Done** — log2ram/rsyslog cap coded **Ops1**; Done table; Pi smoke + docs close-out. **Ops1 later:** Item 3, ForwardToSyslog, log2ram SIZE, auth/kern. |
| 2026-08-16 | **C24** lock-in: extra series overlay-only; month/year untouched; fullscreen = full browser tab (not F11). |
| 2026-08-16 | **C24** lock-in: overlay **X** top-right; missing dew = C5 T+RH pairing (AH/CI omitted); comfort-line proposal pending. |
| 2026-08-16 | **C24** comfort-line **accepted**; remaining open: overlay window, xls vs CSV, AH axis, checkboxes vs legend. |
| 2026-08-16 | **C24** kickoff Q&A **locked**: 24 h overlay window; CSV of `hires_days`; 3rd y-axis AH (hide if series off); checkboxes only (no legend). Implement when commanded. |
| 2026-08-16 | Inbox triage: **C24** temp/hum day fullscreen + AH/CI + checkboxes + 7-day xls — **after C16**; not C12 #8 frost; do not reopen **C5**. |
| 2026-08-16 | **C23** kickoff locked then closed **with C18**: Explorer EventSource; `eq=False` in `set`; journal not a DoD; Last DoD docs audit. |
| 2026-08-16 | **C18** + **C23** ✅ Done — Pi smoke OK; live SSE (`eq=False` + first ping + pure ASGI); Q4/Q5 command-commit; docs close-out. |
| 2026-08-16 | Inbox triage: log2ram full / rsyslog — **C23** `bugfix:` SSE `SseClient` unhashable (**∥ cluster**; C18 smoke waits); **Ops** size-based `logrotate` (`syslog`/`daemon.log`); **Ops** optional uvicorn `--no-access-log` / no JWT query. |
| 2026-08 | **B0–B8** done on Pi. **B9A/B9B** + **B10A/B10B** specs locked. |
| 2026-08-09 | Intermediary shell/typing + pipeline; letter rename B/C/D/E/F/G. |
| 2026-08-10 | **B10B+D+E** done. **G4/G5** triage. |
| 2026-08-11 | **B10F**, **C10**, **D** done. **B9A** code ship. **B10G/H** split. |
| 2026-08-12 | **Domoticz Blockly goal locked** — … Detail → `phaseB-blocky.md`. |
| 2026-08-13 | Inbox triage: **B10K** timings button + blinds OPEN; **B10L** NOT CONNECTED status; **C12 #9** Hidden preset admin-only; **C17** alert dismiss vs reload (**assess at kickoff**). |
| 2026-08-15 | Inbox triage (screenshots): **C20** Admin Clear All no-op; **C21** AUTO OFF while OFF; **C22** Host “(no history)” on CPU temp / load 5m / 15m. Sequence **bugfix:** prefix in triage rule. |
| 2026-08-15 | Inbox triage: **B10M** Explorer Hue preset same-settings; **G6** += Automations deferred Save config + overlay-2 timings; **B10N** RFX living schemer color (split off **B10K** so B10K stays closed); **B10L** copy **Re-connecting to WanOS...**; **C19** History auto-refresh blank (**see C6**); **G14** manual enable status + ON bell. |
| 2026-08-15 | **B10N ✅ Done** — closed without dedicated code; operator cannot reproduce; probably fixed in earlier phases, likely **B10K**. Docs close-out. |
| 2026-08-15 | Ops **`.cursor`** sync exclude shipped (`[MirrorExcludeDirs]`). |
| 2026-08-15 | **C18** Q4/Q5 **locked**: request-level success/fail per integration (silent skip = fail); bell `ERROR: Command failed: {ref} → ON\|OFF`. Fix contract complete — implement when commanded. |
| 2026-08-16 | **C19 ✅ Done** — Pi smoke OK; Explorer History 60s auto-refresh keeps series + window; docs close-out. |
| 2026-08-15 | **B10K + G3 ✅ Done** — Pi smoke OK; timings stopwatch; shutter OPEN/CLOSED; RFX ON/OFF no color; OWM poll 10′; docs close-out. |
| 2026-08-15 | **B10K + G3** spec Q&A locked — one code run; detail → `phaseB-blocky.md` § B10K, `phaseG-integrations.md` § G3. |
| 2026-08-15 | Sequence: prefix **bugfix:** on defect ships (**B10K**, **G2**, **G6**, **G8**, **G1**, **B18**). |
| 2026-08-14 | **P** other homes / portability — very low; in-scope = operator env list + site inventory (config + code leaks). |
| 2026-08-14 | Inbox: **G9–G13** five new integrations (Honeywell → HomeWizard → Samsung → SMA → HomeConnect); one ship each, that order. Library pick = **phase kickoff**, not now. |
| 2026-08-12 | Inbox triage (batch 4): **C12 #8** frost/dew; **C15** lab switch; **B10J** Event Received catalog name; Ops **`.cursor`** sync exclude. |
| 2026-08-12 | Inbox triage: **B10I**; **C12** extras; **B10G** += NOT CONNECTED + admin `vNN` (ex–C14, one ship); **C4** locked `blockly` not `automations`; Ops cinema; cursor rules. |
| 2026-08-12 | **B10G triage:** overlay 2 copy locked; `vNN` Automation only; T4 C = SSE reload suppress all pages (not Admin button flag); Part B repro script + skip-if-no-repro. |
| 2026-08-12 | **G8** boot autostart timing (A+B): shorten real enable + honest Admin UX; separate from B10G/B10H. Part B repro **confirmed** — B10G ships A+B+C. |
| 2026-08-12 | **B10G operator Q&A (2):** exclude kiosk from `vNN`; Admin → `Reloading all config…`; suppress = exact per-scope strings; Part D re-run Pi smoke (B9A shipped); all 8 shell HTML @ `v1`; unscoped API alerts **Option A** → **G6** follow-up. |
| 2026-08-12 | **B10G ✅ Done** — Pi smoke A/B/C/D OK; docs close-out. **B10H** next — cold-load root cause locked (asyncio SSE/`get_state` contention + duplicate FE; nginx ruled out). |
| 2026-08-12 | **B10H approved** — kickoff profiling complete (case A Network: double cold `/api/state`; case C Y); code unblocked. |
| 2026-08-12 | **B10H list-cache triage (step 7c):** defer — TTI ~**2.1 s** meets goal; revisit only for **&lt; 500 ms** cold open. § **B10H — deferred list cache**. |
| 2026-08-12 | **B10H ✅ Done** — cold open ~**2.1 s**; YAML N+1 + SSE reconnect flicker fixed; docs close-out. Next **B2** (B9C). |
| 2026-08-12 | Deleted retired stub `docs/todo/install_blocky.md` — historical note folded into [`phaseB-blocky.md`](phaseB-blocky.md) intro. |
| 2026-08-12 | **Blockly cluster audit:** parallel tracks table (B10I, G5, E, B5∥B6); fixed Depends-on ✅ misuse in phase file; B9B ship order locked vs stale proposal. |

Detail chronology / DoD checkboxes → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md), [`phaseD-typing.md`](phaseD-typing.md), [`phaseG-integrations.md`](phaseG-integrations.md).
