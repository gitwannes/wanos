# ⚡ WanOS — Implementation pipeline

High-level **what’s next** and where the detailed specs live. This file does **not** hold phase DoD / locked-decision novels — those live in `phaseX-yyy.md`.

**Last updated:** 2026-08-12

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
| **C** | Operator shell (Explorer, Admin, History charts, force sweep, HTML names, C10–C13) | [`phaseC-shell.md`](phaseC-shell.md) |
| **D** | Device typing (switch vs light) | [`phaseD-typing.md`](phaseD-typing.md) |
| **E** | Gmail transport (OAuth, outbox, spooler) | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **F** | Public bridge / perimeter security | [`phaseF-security.md`](phaseF-security.md) |
| **G** | Integrations reliability (Hue state, Epson, OWM, cinema sun, scoped reload, log tags) | [`phaseG-integrations.md`](phaseG-integrations.md) |

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

Detail DoD → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md), [`phaseD-typing.md`](phaseD-typing.md).

---

## Blockly ship groups — **finish before C / G / F**

One PR per row. Detail → [`phaseB-blocky.md`](phaseB-blocky.md) § Domoticz goal.

**B10G** ships **after B1 (B9A closeout)** — before **B2–B8**. **B10H** after **B10G**. **B10I** anytime after **B10F**.

| Ship | Phase(s) | Size | One go? |
|---|---|---|---|
| **B1** | **B9A** closeout | low | ✅ alone — Pi smoke + GREEN + docs |
| **B2** | **B9C** legacy bridge | mid | ✅ alone — temp/hum picker, blinds/audio **if** %; unblocks **G5** |
| **B3** | **B19** Domoticz canvas | **high** | ✅ **alone** — If/Do, Compare, Device trigger, typed toolbox, Set, migrator |
| **B4** | **B13** + **B9B H4** | high | ✅ together — Else-if/Else + nested AND/OR in Compare |
| **B5** | **B9B H12** + bathroom | mid | ✅ alone |
| **B6** | **B9B H5** Messages | mid | ✅ alert alone; Gmail half when **E** ready |
| **B7** | **B14** (no Time trigger) | high | ✅ together — timed Set, delay, cooldown, … |
| **B8** | **B11** + **B12** | mid | ✅ together — multi-flow + folder/tag |

**After F:** **B20** — Domoticz **Time** trigger (every-minute model). **Not** in cluster above.

**Not Blockly UX:** **B15** · **B16** · **B17** (assess) · **B18** — general pipeline after cluster / **F** as today.

---

## Sequence

**Size** = relative delivery weight (rough): **low** = small/local · **mid** = multi-file or careful edge cases · **high** = schema/API/engine or large surface. Not calendar days.

```text
#  Size   Phase / Ship   What
─── Post-B9A: load/shell UX, then Blockly cluster ───
1.  mid    B10G         load checklist + timings + log; NOT CONNECTED assess; admin vNN; hue preset-only reload (Part D)
2.  low    B10H         cold-load shorten wait (after B10G)
─── Blockly cluster (operator: B9C → B19…B8 before shell/integrations/F) ───
3.  mid    B2 / B9C     legacy-canvas bridge — picker + blinds/audio if %
4.  high   B3 / B19     Domoticz If/Do + Compare + Device trigger + toolbox + Set
5.  high   B4           B13 Else-if/Else + B9B H4 AND/OR in Compare
6.  mid    B5           B9B H12 hysteresis + bathroom climate cutover
7.  mid    B6           B9B H5 Messages (alert; + email when E)
8.  high   B7 / B14     timed Set, delay, cooldown, remaining HA patterns (no Time trigger)
9.  mid    B8           B11 multi-flow + B12 folder/tag
─── G5 may land after B2; prefer re-author on B19 canvas when B3 done ───
11. low    G5           dashboard “rolluik zon half” — after B2; full Domoticz UX after B3
11b. low   B10I         used SE → Go to SR (anytime after B10F)
─── After Blockly cluster ───
12. high   E            Gmail transport / outbox
13. mid    C3           Force ALL-OFF
14. mid    C4           Rename HTML entrypoints (`blocky`→`blockly`; not `automations`)
15. low    C11          Control vs History list membership (assess → decide)
16. mid    C12          Post-C10 polish (+ scene favorites, shutter debounce assess)
17. mid    C13          Merge Hidden → Timers & types
18. mid    G2           Hue color/bri truth
19. mid    G6           Scoped CONFIG_RELOAD + Admin scoped-reload modal (hue_presets handler → **B10G Part D** first)
20. low    G7           Integration log tags
20b. mid   G8           Boot autostart timing — shorten real enable + honest Admin UX (A+B)
21. mid    G1           Epson get_power_state
22. low    G3           OWM outside poll 10′
23. mid    G4           OWM One Call + hot-sun cinema 60% open
24. high   F            Security bridge (F1→F7)
─── After F ───
25. mid    B20          Domoticz Time trigger + time-compare blocks
26. mid    B15          Demote schedule edges → user origin
27. high   B16          Full-bus UUID for internal EventTypes
28. mid    B17          Sauna/IR hardcoded → automation (assess only)
29. mid    B18          Sauna session_end ≤ absolute_cutoff
30. —      Ops          Inbox below when convenient
```

### Why this order

* **B1 B9A** — ✅ **Done 2026-08-12** (Pi smoke + Debug GREEN + docs close-out). Hue preset **reload/perf** issues (15–20s, integration recycle, NOT CONNECTED) → **B10G Part D**, not B9A scope.
* **B10G** — **one ship** (after **B1**): Part A load checklist; Part B SSE **A+B+C** (Pi repro **confirmed 2026-08-12**); Part C **`vNN` Automation only**; **Part D** `hue_presets`-only reload (first **G6** slice — Admin modal remains **G6**).
* **G8** — boot autostart timing (~30s “integrations disabled”) — **A+B** ship; separate from **B10G** / **B10H** — detail § **G8** below.
* **Blockly cluster B2–B8** — operator lock **2026-08-12**: [Domoticz Blockly](https://wiki.domoticz.com/Blockly) **look & feel** before Explorer/integrations/F churn. **B3 (B19) is mandatory**, not optional UX polish.
* **B2 B9C** — patch **legacy** canvas only; unblocks **G5** “not fully closed”; superseded visually by **B19**.
* **B3 B19 alone** — canvas + engine projection + rule migrator; do **not** combine with B4.
* **B4** — Domoticz **Logic** (Else-if + AND/OR) on new canvas.
* **B5–B6** — bathroom / notify on Domoticz blocks; **H5 email** still waits on **E** (can ship alert first).
* **B7 B14** — timed **Set**, delays, cooldowns — **excludes** Time trigger (**B20**).
* **B8** — library organization after canvas stable.
* **G5 after B2** — dashboard button + rule; re-touch rule on B19 canvas when **B3** lands.
* **C\*, G\*, E, F** — **after Blockly cluster** (default). **G2/G6** may jump on operator pain (**G6** — Admin full vs scoped reload; see [`phaseG-integrations.md`](phaseG-integrations.md) § G6).
* **B20 after F** — Domoticz **Time** trigger; catalog schedule events unchanged until then.
* **B15–B18** — not Domoticz L&F; **B18** may jump on sauna safety pain.

Near-term = **B10G** → **B2** (B9C) → **B3** (B19) → **B4…B8**. **E** after cluster or parallel to B5–B8. **No** user-variable or debug Blockly blocks.

---

## B10G — connection + load UX (spec + assess)

**Ship:** **B10G** after **B1** (B9A closeout). **One PR** — Parts A + B + C + **D**. Detail DoD checkboxes → [`phaseB-blocky.md`](phaseB-blocky.md) § B10G.

| Part | What |
|---|---|
| **A** | Automations **load checklist** + per-step duration; **browser** timings + small admin debug modal (B10G); `wanos_debug.log` **deferred** |
| **B** | **NOT CONNECTED** assess (**done 2026-08-12**); fix **A+B+C** — Pi repro **confirmed 2026-08-12** |
| **C** | Admin-only **`vNN`** on **Automation** page only (`blocky.html`) |
| **D** | Hue preset CRUD: **`hue_presets`-only** reload — no full `CONFIG_RELOAD` / NVRAM / bridge recycle; Explorer chip + save/wheel UX (operator inbox **2026-08-12**) |

**Part D Pi smoke:** add/rename/delete presets with Explorer open — each op **&lt;2s**; logs show **no** `NVRAM successfully loaded`, **no** `[Z-Wave] Core config reload detected`, **no** Onkyo recycle; **no** spurious NOT CONNECTED.

### Automations — two overlays (locked)

**Automation (`blocky.html`) must have two separate overlays** — not one combined screen:

| # | Overlay | Source | When | Copy / UX |
|---|---|---|---|---|
| **1** | **Shared offline** | `data-wanos-offline` → `wanos-shell.js` `offlineOverlay()` — **same chrome as Explorer / Admin** | Backend unreachable while page is open | Red **NOT CONNECTED** — `Establishing connection stream to WanOS backend...` |
| **2** | **Loading config** (Automations only) | Page-local checklist (Part A) | Cold `init()` → `refreshAll()` only — **not** post-save refresh | Yellow — friendly-label **checklist + checkboxes** + duration per step at completion |

**Today (gap):** `blocky.html` has **no** `data-wanos-offline`; a **single** inline `!connected` overlay covers **both** loading and unreachable and reuses the **NOT CONNECTED** heading during normal yellow load. **B10G** splits these and wires overlay **1** through shared shell code.

**Blockly workspace** (`loadV2IntoBlockly` / `scheduleBlocklyLoad`) stays **after** overlay **2** clears.

**Alpine flags (locked T2):** **`shellConnected`** drives overlay **1** (`data-wanos-offline`); **`editorLoading`** drives overlay **2** (checklist).

### System — check backend connection (locked)

Two **phases** on Automation; one **continuous** model on SSE pages.

#### Automation (`blockyApp`)

| Phase | When | How backend is checked | Overlay |
|---|---|---|---|
| **Load** | `editorLoading === true` — cold `init()` → `refreshAll()` | **Each load step is a live check** — parallel `GET /api/state`, `/api/automations`, `/api/events`, then fire-status, etc. | **2** (yellow checklist) while steps run |
| **Running** | After `refreshAll()` succeeds — `editorLoading === false` | **REST heartbeat** — `GET /api/state` (auth) **every 15000ms** when tab visible + on `visibilitychange` (no polling while hidden) | **1** (red shared offline) if heartbeat fails |

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

**Part B fix (locked T4 — A+B+C):** debounce SSE `onerror` (3000ms grace); clear on first reconnect `ping` (cancel pending debounce offline display); **suppress shared offline overlay on all pages using the shared offline overlay (including `zwaveconfig.html`) during config reload** (see T4 C below). Pi repro script → § **Part B — operator repro**; ship fix if flash confirmed.

### Part A — load checklist (locked)

| # | Friendly label (overlay) | API (in log / modal line) |
|---|---|---|
| 1 | Device state | `GET /api/state` |
| 2 | Automations | `GET /api/automations` |
| 3 | Events | `GET /api/events` |
| 4 | Building library | *(step name — parse + rebuild)* |
| 5 | Schedule status | `GET /api/automations/fire-status` |

Steps 1–3 parallel; check off in completion order.

**Timings (locked T3 — B10G ship):** record in **browser console** + small **admin-only debug modal** during load (step name, API, ms) — easy to remove later. **`wanos_debug.log` server logging deferred** (stay in spec as follow-up; not B10G DoD).

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

**T4 C detail (locked):** suppress overlay while reload is in progress on **any** page (incl. `zwaveconfig.html`) — signal via **`system_alert_msgs` on SSE** (`system` domain), **not** Admin-local `configReloading` / GO-button flag. Window: from alert text containing **`Reloading all config`** (or equivalent reload-in-progress message) until **`Config reloaded`** or **`Config reload failed`**.

**Code check (2026-08-12):** only Admin `requestConfigReload()` injects the “Reloading…” alert today; API `CONFIG_RELOAD` paths (Automations save, events, soft-hide, …) dispatch reload **without** that in-progress alert. Part B impl must use a **shared** reload-in-progress signal for **all** reload sources (UI button, API writes, and scoped reloads) by extending backend/alert behavior so the same `system_alert_msgs` in-progress message is emitted for every `CONFIG_RELOAD_REQUESTED` source — do **not** wire suppress only to Admin’s button state.

**Recap:** SSE problem = **client reconnect policy**, not backend down. Automation = **two overlays** + load-as-check + post-load heartbeat (§ **System — check backend connection**).

### Part C — admin `vNN` (Automation only)

**Locked:** **`vNN` on Automation page only** (`blocky.html` / title block) — **not** login, kiosk, or other operator pages in B10G. Admin-only visibility; integer; bump when that page’s HTML/JS changes; start **`v1`** unless operator says otherwise; agent reports bump on ship. (`html-standards.mdc` applies to future page-version work elsewhere — B10G scope is Automation only.)

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
| **B10G** | Below § **B10G** + [`phaseB-blocky.md`](phaseB-blocky.md) § B10G DoD |
| **B2 / B9C** | [`phaseB-blocky.md`](phaseB-blocky.md) § B9C — legacy bridge |
| **B3 / B19** | [`phaseB-blocky.md`](phaseB-blocky.md) § B19 — Domoticz canvas |
| **Domoticz goal** | [`phaseB-blocky.md`](phaseB-blocky.md) § Domoticz goal + ship groups |

---

## Queued

| Phase | Detail file |
|---|---|
| **B9A** / **B9C** / **B19** / **B9B** / **B10G** / **B10H** / **B10I** / **B11–B20** | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **E** | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **C3** / **C4** / **C11** / **C12** / **C13** | [`phaseC-shell.md`](phaseC-shell.md) |
| **G2** / **G6** / **G7** / **G8** / **G1** / **G3** / **G4** / **G5** | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **F1–F7** | [`phaseF-security.md`](phaseF-security.md) |

### B11–B20 — lettered Blocky / automation (pointers)

Detail + DoD stubs: [`phaseB-blocky.md`](phaseB-blocky.md) § B11–B20. Schedule math: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

| Phase | What | Ship |
|---|---|---|
| **B10I** | Used SE → Go to SR | anytime after B10F |
| **B11** | Multi-flow one Blockly page | **B8** |
| **B12** | Rule-list folder/tag | **B8** |
| **B13** | Domoticz Else-if / Else | **B4** |
| **B14** | Timed Set, delay, HA patterns (no Time trigger) | **B7** |
| **B15** | Demote schedule edges → user origin | after **F** |
| **B16** | Full-bus UUID internals | after **F** |
| **B17** | Sauna/IR → automation assess | after **F** |
| **B18** | Sauna session_end clamp | may jump |
| **B19** | **Domoticz If/Do canvas** | **B3** |
| **B20** | Domoticz **Time** trigger | after **F** |

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
| **Cinema — merge ON/OFF rules** | Collapse **`--- CINEMA ON`** + **`--- CINEMA OFF`** → one **`switch cinema`** rule. **Pickable “cinema state”** (likely **`switch.epson`**) as condition — **to be checked**; may need **B9C** device-state on projector before rule rewrite. Operator YAML on Pi. |
| Background Leak = **0.0 W** | Verify — **check!** |
| Where is the **3-phase kWh meter** connected? | Site / wiring — **manual** |
| Where do the **Pis** get power? | Site / UPS / circuit — **manual** |

*(Hue badkamer red / color truth → **G2**. Hue preset CRUD → **B9A**.)*

---

## Change log (short)

| When | What |
|---|---|
| 2026-08 | **B0–B8** done on Pi. **B9A/B9B** + **B10A/B10B** specs locked. |
| 2026-08-09 | Intermediary shell/typing + pipeline; letter rename B/C/D/E/F/G. |
| 2026-08-10 | **B10B+D+E** done. **G4/G5** triage. |
| 2026-08-11 | **B10F**, **C10**, **D** done. **B9A** code ship. **B10G/H** split. |
| 2026-08-12 | **Domoticz Blockly goal locked** — … Detail → `phaseB-blocky.md`. |
| 2026-08-12 | Inbox triage: **B10I**; **C12** extras; **B10G** += NOT CONNECTED + admin `vNN` (ex–C14, one ship); **C4** locked `blockly` not `automations`; Ops cinema; cursor rules. |
| 2026-08-12 | **B10G triage:** overlay 2 copy locked; `vNN` Automation only; T4 C = SSE reload suppress all pages (not Admin button flag); Part B repro script + skip-if-no-repro. |
| 2026-08-12 | **G8** boot autostart timing (A+B): shorten real enable + honest Admin UX; separate from B10G/B10H. Part B repro **confirmed** — B10G ships A+B+C. |

Detail chronology / DoD checkboxes → [`phaseB-blocky.md`](phaseB-blocky.md), [`phaseC-shell.md`](phaseC-shell.md), [`phaseD-typing.md`](phaseD-typing.md), [`phaseG-integrations.md`](phaseG-integrations.md).
