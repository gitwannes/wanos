# ⚡ WanOS Phase C — Operator shell

Explorer / Admin / system UX polish **outside** Blocky, plus Admin force tools, HTML entrypoint renames, and Explorer History chart polish.

**Status:** Spec **LOCKED**. **C1 / C2 / C5 ✅ DONE** (Pi smoke **2026-08-09**). **C6–C9 ✅ DONE** (combined Pi smoke **2026-08-10**). **C10 ✅ DONE** (Pi smoke **2026-08-11**). Queued: **C3 → C4 → C11**. Next sequence: **D** (see [`pipeline.md`](pipeline.md)).

**Related:** Blocky → [`phaseB-blocky.md`](phaseB-blocky.md) (**B10A** / **B10C** / **B10B+D+E** / **B10F** ✅). Soft-hide → **B7**; auto-off → **B8** (both done). Device typing → [`phaseD-typing.md`](phaseD-typing.md). Sequence → [`pipeline.md`](pipeline.md).

**DoD convention:** every open subphase ends with **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** (see [`pipeline.md`](pipeline.md) § DoD / close-out).

**Moved to Blocky (B10A/B10B/B10C):** events catalog / scenes, rule enable, Hue Blockly bugs, toolbar Delete, dirty leave (+ multi-flow → **B11**); soft-hide picker regression → **B10C** ✅.

---

## Size & subphases

| Subphase | Items | Character |
|---|---|---|
| **C1 — Explorer chrome** | Hidden + Favorites in presets pane; edit favorites | Frontend-only, fast |
| **C2 — Admin + system pages** | Planned Automations; bell; reboot; gear-only nav; leave-guards | Admin UI + one API |
| **C5 — History graphs** | Landscape filters; dew point; Y-axis snap; climate smooth (d/m/y) | Explorer History charts |
| **C6 — History flicker** | Soft auto-refresh without wipe/flicker (all chart families) | C5 soft-refresh follow-up · low |
| **C7 — Explorer follow-ups** | Favorites portrait; SSE filter restore; landscape chart chrome; legend dots | FE; C1/C5 leftovers · low |
| **C8 — Alert dismiss logs** | Banner + bell dismiss → `wanos.log` info (UX unchanged) | C2 dismiss follow-up · low |
| **C9 — Device-ref app logs** | All device-ref lines in `wanos.log` → `entity_id (name, idx N)` | Every integration · mid |
| **C10 — Explorer / History polish** | Plural Nodes; Planned past gone; Hue hex text; chart colors; binary/hits charts; omit scenes; filter+blinds | FE · mid |
| **C11 — Control vs History lists** | Re-assess Explorer Control vs History list membership (post–C10 scene omit) | Assess → decide · low |
| **C3 — Force ALL-OFF** | Admin reconciliation sweep | Admin tool + integrations |
| **C4 — HTML renames** | `commander`→`wisc`; `blocky`→`automations` | Shell entrypoints |

**C1 → C2 → C5** shipped. **C6–C9** ✅ **2026-08-10**. **C10** ✅ Pi smoke **2026-08-11**. **C11** after **C4** (or when list-membership pain wins). **C3/C4** later unless needed sooner.

---

## 📋 C1 — Explorer chrome ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-09**).

### Hidden + Favorites in presets pane

* Keep **both** in the **presets** pane (not the sticky filter pane).
* Each control: **label + toggle on one line** (not split / stacked).

### Favorites edit + Favorites filter

* **Edit / Done** (industry pattern): control next to Favorites (pencil / “Edit”).
  * **Idle:** no row checkboxes, no stars / indicators.
  * **Edit:** checkboxes on rows; tap toggles favorite; **Done** exits.
* Hide Favorites **filter** when there are **no favorites** (not when view-presets empty).
* Filter: show only when `actuatorFavorites.length > 0`; last favorite removed → clear filter + hide toggle.
* View-presets may store `favoritesOnly`; apply with zero favorites → ignore that bit + force filter off.

**C1 DoD:** Hidden + Favorites in presets pane (one line each); Edit/Done favorites; Favorites filter iff favorites exist. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (re-audit).

---

## 📋 C2 — Admin + system-command pages ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-09**).

### Planned Automations pane

* No IDX; show **name + type** (today’s metadata types; Phase **D** later for light vs switch).
* Keep action intent; **only remove the word “will”** → e.g. `CLOSE`, `turn ON`, `execute scene`.

### Critical alerts in bell

* Bell **Admin-only**; criticals also in bell.
* **Two independent dismiss states** per alert: banner dismiss ≠ bell dismiss.

### Admin Debug: “Reboot Wanos”

* Restart **WanOS service only** (not host). Confirm modal. `POST /api/admin/restart` → 202 on accept.
* **Locked ops path:** passwordless sudo for the exact restart unit command (same pattern as existing `wisc-kivy` NOPASSWD). Not a stored password/hash; not silent process-exit as primary.
* Backend invokes `systemctl restart wanos.service` via that NOPASSWD grant (or equivalent thin wrapper later if desired).
* On failure: **UI error message**.
* Client reconnect UX (~60–90s timeout) after accepted restart.

### System-command header nav

* Pages: **`hiddendevices`**, **`lightingautooff`**, **`zwave`**.
* Gear → Admin only; **no** Explorer / WISC / History / Automation joins. Clear page title.

### Discard + leave-guard

* Same pattern as **Blocky**: dirty → Cancel / Discard / Save on gear/browser leave.
* Applies to: soft-hide, auto-off, **and Z-Wave**.

**C2 DoD:** Timeline polish; bell/criticals with dual dismiss; reboot works on Pi (after Ops); three system pages gear-only; discard + leave-guard on hide / auto-off / zwave. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (re-audit).

### Ops — passwordless restart (prereq for reboot DoD)

**Best / locked option:** sudoers NOPASSWD for the single restart command (narrow). Alternatives (polkit, self-exit + `Restart=always`, root helper) rejected as primary for C2.

**Bootstrap / procedure (source of truth for installs):**

* Script: [`helpers/bootstrap/backend/wanos_bootstrap_phase1.sh`](../../helpers/bootstrap/backend/wanos_bootstrap_phase1.sh) → `/etc/sudoers.d/wannes_sudo_policy`
* Guide: [`helpers/bootstrap/backend/wanos-install-backend.md`](../../helpers/bootstrap/backend/wanos-install-backend.md) § **5.4**

```text
wannes ALL=(root) NOPASSWD: /usr/bin/systemctl restart wanos.service
```

Verify as `wannes` (must exit 0, no password prompt):

```bash
sudo -n systemctl restart wanos.service
echo "exit=$?"
```

Checked on Pi (`wannes`, 2026-08-09): was **missing** (only `wisc-kivy` / `log2ram` NOPASSWD). Apply via bootstrap or §5.4 upgrade steps before reboot DoD.

---

## 📋 C3 — Force ALL-OFF synchronization sweep 🔜 TODO

**Admin shell tool.** Spec locked; schedule after **C2** unless needed sooner.

### Core philosophy

Due to the simplex nature of RF hardware (RFX) and the mesh fragility of Z-Wave, WanOS can experience **state desynchronization** — software reports OFF while hardware remains ON.

The **Admin Force Sweep** bypasses idempotency checks and transmits physical OFF commands so hardware matches software.

### Execution architecture

* **Integration isolation (parallel):** spawn independent async tasks per integration (Z-Wave, RFX, Onkyo, …).
* **Internal queuing (sequential):** within each integration, devices one-by-one.
* **300ms pacing:** `await asyncio.sleep(0.3)` after each OFF payload.

### Exclusion filter (safety)

* Explicit exclusion tag on critical devices (e.g. `ignore_global_off: true` / `admin_sweep_exclude: true`).
* Skip read-only / system monitoring integrations entirely.

### Trigger & flow

1. Kiosk / Admin fires e.g. `ADMIN_FORCE_SWEEP`.
2. Handler scans controllable devices, groups by `integration_id`, strips excluded.
3. Dispatch paced OFF sequences per integration.

### UI/UX

* Confirmation (modal or long-press).
* Toast on start; toast on completion (~10–20s for large Z-Wave nets).

### Success metrics

* RFX sniffer: clean spaced TX, no overlap.
* Z-Wave JS: no Dropped Message / Queue Full from the sweep.
* Excluded criticals untouched.

### Implementation blueprint

* **`config.yaml` / metadata:** exclusion flag on router plugs, Pi power, sauna controllers, etc.
* **`core/models.py`:** `ADMIN_FORCE_SWEEP` (or equivalent) event type.
* **`core/event_handlers/admin_handlers.py`:** aggregate, filter, `asyncio.create_task` per integration.
* **Integrations / dispatcher:** 300ms pace after each OFF.
* **Frontend:** Admin/Kiosk button, confirm modal, start/complete toasts.

**C3 DoD:** Sweep runs on Pi with pacing; exclusions honored; Admin UX confirms + reports completion. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C4 — Rename HTML entrypoints 🔜 TODO

* `commander.html` → `wisc.html`
* `blocky.html` → `automations.html`

**to be checked:** All links, redirects, shell nav, kiosk, nginx/static routes, bookmarks. Shell chrome — not Blocky logic.

**C4 DoD:** New names live everywhere operators hit; old URLs redirect or 404 intentionally documented. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C5 — History graphs ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-09**).

**Explorer → History** chart polish (`deviceexplorer` / climate + host + utility charts) — **not** `sensorhistory` (sauna/IR session table), not Blocky, not B9A.

### Landscape filters

* Smartphone **landscape**: when a **chart is open**, filter chrome must not consume ~half the viewport.
* Compact pattern (collapse / drawer / icon-only / overlay) so the **chart owns** the screen.
* When no chart open: leave filter layout as today.

### Dew point

* On **temp/hum** graphs only; **hide dew** when humidity is missing (temp-only).
* FE-derived series (no DB storage required for C5).
* Values rounded to **1 decimal**.
* **Locked:** Sonntag Magnus (\(T\) in °C, \(RH\) 0–100). Buck-style constants considered, not used.

\[
\gamma(T, RH) = \ln\left(\frac{RH}{100}\right) + \frac{b\, T}{c + T}
\qquad
T_{dp} = \frac{c \cdot \gamma}{b - \gamma}
\]

Constants: \(b = 17.62\), \(c = 243.12\) °C (\(a\) unused in this form; no \(d\)).

### Y-axis autoscale

* Min/max from series in the **dataZoom window** (not full loaded series / fixed full-scale).
* Snap bounds / ticks by unit:

| Series / unit | Snap |
|---|---|
| Temperature (°C) — climate + host CPU temp | **5°** |
| Humidity (%) | **10%** |
| Host % (CPU, mem free, disk, log2ram, load) | **10%** |
| Power (W) | **10 W** |
| Water (L) | **10 L** (day); **50 L** (month/year) |
| Mains (V) | **5 V** |
| DB size (MB) | **50 MB** |
| Actuator level (0–100) | **10** |
| Actuator event counts | integer / auto (no fixed snap) |

### Climate line smoothing (day / month / year) ✅

**Why:** Day temp / humidity / dew charts used ECharts `step: "end"` plus sparse deadband samples → stair-step “jumps”.

**Locked / shipped:**

* **Day / month / year** climate series (temp, humidity, dew min/max): ECharts **`smooth: true`** — no `step`.
* FE draw style only (no extra DB samples).
* Actuator day `step: "end"`: out of scope.

**C5 DoD:** Landscape + chart open → filters compact; dew on temp/hum (formula above, 1 decimal); Y-axis from dataZoom window with snaps in table; climate day/month/year with `smooth: true` (no step); smoke phone + desktop. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (re-audit).

---

## 📋 C6 — History auto-refresh flicker ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-10**).

**Origin:** operator report **2026-08-09**. C5 soft-refresh follow-up — **not** reopening C5 DoD. **Inspect done 2026-08-10**; approach locked below. **Code + Pi smoke 2026-08-10.**

* Explorer → History: on **60s auto-refresh**, chart **flickers** (line appears to reset then redraw).
* Scope: **all** History graphs (climate / actuators / host / utility; day/month/year as applicable).
* **Success bar:** series update in place; axes / zoom / selection preserved; no blank or wipe flash.
* **Out of scope:** first paint, chart family / row switch, manual range change (hard path unchanged).

### Inspect findings (locked)

* Soft path already exists: `refreshExplorerHistory` → `reloadSelectedSensorDetail({ soft: true })` — keeps ECharts instances and restores dataZoom %.
* Happy path does **not** dispose / `x-if`-remount; flash is elsewhere.
* **Primary cause:** soft updates still call `chart.setOption(opt, true)` (**notMerge**) in `_setHistoryChartOption` (and water / actuator period paths) → full wipe then redraw; default animation amplifies it.
* **Amplifiers:** triple `resize()` on soft path; `_bindHistoryYSnap` re-bind + immediate Y `setOption` (second tick).

### Locked approach (soft === true only) — shipped

1. Merge-style `setOption` via `_setHistoryChartOption(..., { soft: true })` — `{ notMerge: false, replaceMerge: ['series'] }`; hard path keeps `notMerge: true`.
2. Soft opts set `animation: false` / `animationDurationUpdate: 0`.
3. Soft path skips per-chart resize in ensure/setOption; **one** resize pass after draw in `reloadSelectedSensorDetail`.
4. Water + actuator period charts use the same soft helper.
5. Hard open/switch unchanged.

**C6 DoD:** Soft auto-refresh updates series without visible reset/flicker; axes/zoom/selection kept; Pi smoke all chart families. **Bundle Last DoD** with C7–C9: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior. — ✅ **2026-08-10** (Pi smoke + docs).

---

## 📋 C7 — Explorer follow-ups ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-10**).

**Origin:** operator reports **2026-08-10** (screenshots). C1/C5 leftovers — **not** reopening those DoDs. FE-only. **All four bullets in this ship.** **Code + Pi smoke 2026-08-10.**

### Favorites row — smartphone portrait

* **Smartphone portrait only** (`max-width: 640px` + `orientation: portrait`): two rows — (1) clear + chips **1–5** + pencil; (2) **Show Favorites** + Edit/Done + **Hidden devices** — row 2 **must not wrap**; **smaller** label/control chrome so the full labels fit.
* Labels: filter = **Show Favorites**; admin toggle = **Hidden devices**.
* **PC / landscape:** single row (chips left; Show Favorites + Edit + Hidden devices + pencil right) — unchanged from pre-portrait layout.

### Filters after SSE reconnect

* Bug: Device Explorer open; after **SSE drop/reconnect**, active filters (e.g. status **ON**) look inactive (not blue) and list not filtered; toggling away and back fixes it.
* Code today: `searchQuery` / `typeFilter` / `statusFilter` / `sortMode` saved in `sessionStorage` (`wanos_active_filters`); SSE `connectSSE` does **not** clear them — fix re-apply / select↔model sync after snapshot so **all four** restore with correct **blue active** styling.
* **Scope (locked):** Control **and** History — they share one Alpine app and the same four filter fields; one fix covers both. Smoke both after SSE drop/reconnect. No History-only filter feature.

### Landscape chart — full bleed (C5 follow-on)

* Smartphone **landscape + chart open** (same gate as C5 filter collapse): also hide **Control | History** picker and the **“Filter collapsed · …”** hint row so the graph owns the screen.
* Smartphone **landscape** (same gate): filter bar is **not sticky** — scrolls away with the list (vertical room too tight).
* Portrait / no chart / PC: sticky filters unchanged. Portrait / no chart: Control|History visible as before.

### History legend — no marker dots

* All Explorer History chart legends: show **line style/color only** — **remove** legend marker dots (graph series stay lines without point markers).

**C7 DoD:** Portrait favorites no overlap; SSE reconnect restores filters + blue active (Control + History); landscape+chart hides Control/History + collapsed hint; legends without dots; Pi smoke phone portrait/landscape. **Bundle Last DoD** with C6/C8/C9. — ✅ **2026-08-10** (Pi smoke + docs).

---

## 📋 C8 — Alert dismiss → app log ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-10**).

**Origin:** operator request **2026-08-10**. C2 dual-dismiss follow-up — **not** reopening C2 DoD. **Code + Pi smoke 2026-08-10.**

* When an operator dismisses a **UI banner alert** or a **bell alert**, write an **`info`** line to the WanOS app log (`/var/log/wanos/wanos.log`).
* Both dismiss paths (independent per C2).
* **Pure log only:** banner/bell dismiss **UX and FE-local dual-dismiss state unchanged**. Do **not** call server `ALERT_DISMISSED` / `AlertManager.dismiss_alert` for this (that removes the alert from shared state and fights dual dismiss). Fire-and-forget log write; log failure must not undo UI dismiss.
* **No alert id** in the log line (UI uuid only — not useful for ops).
* **`level=`** = UI alert severity already on the alert: `info` | `warning` | `critical` | `success` (not logger ERROR/WARNING). The log record itself is still **`info`**.

**Locked line shape:**

```text
Alert dismissed (banner): level=<level> "…message text…"
Alert dismissed (bell): level=<level> "…message text…"
```

**Shipped mechanism:** FE `dismissBannerAlert` / `dismissBellAlert` → `publishEvent("ALERT_UI_DISMISSED", { surface, level, message })` → `handle_alert_ui_dismissed` logs `info` and returns no state change. Existing non-critical bell `ALERT_DISMISSED` clear path unchanged.

**C8 DoD:** Banner dismiss and bell dismiss each produce an `info` line as above in `wanos.log`; dismiss UX unchanged; Pi smoke both paths. **Bundle Last DoD** with C6/C7/C9. — ✅ **2026-08-10** (Pi smoke + docs).

---

## 📋 C9 — Device-ref lines in app log ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-10**).

**Origin:** operator inbox **2026-08-10** (started as Z-Wave Command Sent; **widened 2026-08-10**). Shell/ops visibility — **not** Blocky. Size **mid**. **Code + Pi smoke 2026-08-10.**

* **Target log:** `/var/log/wanos/wanos.log` (app / integrations).
* **Scope:** **every** app-log line that **references a device**, across **every integration** (Z-Wave, RFX, Hue, media/Onkyo, …) — not only Z-Wave Command Sent / FORCED.
* **Canonical shape** (same as automation `format_device_ref`): `entity_id (name, idx N)`  
  Example: `Set media_player.buro (buro, idx 60006) to OFF`  
  Z-Wave examples today that must gain the ref:  
  `⚡ [FORCED] Z-Wave Command Sent: 66/37/2 -> OFF` / `[Z-Wave] Command Sent: 31/37/1 -> ON`.
* **Automation log:** already uses `format_device_ref` — audit only for stragglers; main work is app/`wanos.log` integration lines.
* Fallbacks when name/entity_id missing: follow existing `format_device_ref` thin-meta rules (`entity_id (idx N)`, `idx N (name)`, `idx N`).
* **Shipped:** `format_device_ref` / `device_entity_id` live in `core/models.py`; integrations (Z-Wave, RFX, Hue, Onkyo, Sonos), hardware SHT11, sensor-failure handler, and automation sweeper/shower lines use it. `AutomationEngine.format_device_ref` delegates to the core helper.

**C9 DoD:** All device-ref lines in `wanos.log` use `entity_id (name, idx N)` (or thin fallbacks); every integration covered; Pi smoke representative paths (incl. Z-Wave forced + normal). **Bundle Last DoD** with C6–C8. — ✅ **2026-08-10** (Pi smoke + docs).

---

## 📋 C10 — Explorer / History polish ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-11**).

**Origin:** operator screenshots + inbox **2026-08-11**; decisions locked **2026-08-11**. Shell only — **not** Blocky (**B10F**), **not** G2 bri/bridge truth. **One ship.** Size **mid**. **Spec LOCKED**. **Code + Pi smoke ✅ 2026-08-11**.

| # | Item |
|---|---|
| 1 | **Plural** — Explorer count badge: `1 Node` / `N Nodes` (not `1 Nodes`) |
| 2 | **Planned Automations** — when a timer is **done** (will not run again / deadline past), **remove it from the list**. Must not stay visible as **`imminent`** (pre-fix: UI mapped `diff <= 0` → `imminent` while stale `active_timers` could linger). **Not** Automations SR/UR fire-status copy (`Will fire` / `Has fired` / …). Future relative labels (`in N sec` / `in N min` / …) **unchanged**. |
| 3 | **Hue detail** — remove **COLOR OUTPUT** hex **text** row only; **keep** color wheel + presets (match Hue app) |
| 4 | **Climate chart** — series line colors must match legend/tooltip (temp ↔ dew-point swap observed) |
| 5 | **History charts — Level / ON·OFF / hits** — see locked rules below |
| 6 | **History list** — omit **all** rows with `type === "scene"` (UE **and** SE synthetic catalog-event history, e.g. cinema). Keep real devices (incl. motion). Control vs History membership divergence → **C11** (not this ship). |
| 7 | **Search edge** — filter matching state text (e.g. `60` → 60% closed blinds): dragging the slider must not drop the row from the list mid-edit / lose the change |

### Item 5 — locked chart rules (shipped)

**A — Binary (ON/OFF on Y, not numeric Level)** — all History actuator charts **except** the non-binary set and motion: switches, non-Hue lights, door, Epson/projector, and any other actuator not listed in B/C.

**B — Non-binary (keep numeric / existing continuous charts)** — Hue; Sonos; Onkyo; blinds; temp; hum; host CPU temp; memory; disk; voltage; cpu; kWh/energy; load; DB size; Power (W); Water (L); log2ram.

**C — Motion = hits (not ON/OFF, not “Level”)**  
* **Day:** keep impulse/hit spikes; Y labels: **blank** at bottom (idle), **`hit`** at top; **no** series/axis name **Level**; **no** numeric **0** / **100** labels.  
* **Month / year:** **# hits** per bucket only (not binary); drop Level min/max for motion; axis/series = hits language.

### Out of scope

* G2 Hue bri/xy bridge truth; G5 rolluik; B10F Automations chrome; integration log prefixes → **G7**.
* Control vs History list membership product model → **C11**.
* Automations SR/UR fire-status timing strings (different surface).

**C10 DoD:** Items 1–7 fixed on Pi (phone + desktop where relevant); all `type === "scene"` gone from History list; binary charts read ON/OFF; motion day = hit Y-labels, month/year = hit counts; Planned past/done entries absent from list (not stuck `imminent`); Hue hex text gone, wheel remains; filter+blinds drag keeps row + applies command. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-11** (Pi smoke + docs).

---

## 📋 C11 — Control vs History list membership 🔜 TODO

**Origin:** C10 item 6 lock (**2026-08-11**). **Not** part of C10 ship.

**Problem:** Explorer **Control** membership (`dashboard_events` / devices) and Explorer **History** list membership (history DB idxs + metadata, incl. former `type === "scene"` catalog rows) are **not the same model**. C10 only omits all History `scene` rows; it does not unify the two lists.

**Scope (assess → decide → impl if needed):** document current divergence; decide whether Control and History should share one membership rule (and what happens to SE/UE event history, hidden devices, utilities, etc.); then implement or explicitly defer with rationale.

**Out of scope:** C10 polish items; Blocky Library UE/SE/SR; G2/G5.

**C11 DoD:** Written decision in this file + pipeline; if impl: Pi smoke for Control + History list parity rules; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 🚦 Decisions locked (summary)

* **C1:** Hidden + Favorites stay in presets pane (one line each on landscape/desktop); Edit/Done favorites; idle = no indicators; filter iff favorites exist. **Portrait favorites layout → C7.**
* **C2:** Timeline name+type, strip “will”; dual banner/bell dismiss; service reboot via sudoers `NOPASSWD: systemctl restart wanos.service` + UI error on fail; gear-only on hide / auto-off / zwave; leave-guard on those three (Blocky-style). Types = today’s metadata until **D**.
* **C5:** Explorer History (not `sensorhistory`); compact filters only when chart open; dew via **Sonntag Magnus** (1 decimal) when temp+hum; Y from dataZoom; snaps per table (power **10 W**); climate day/month/year lines **`smooth: true`** (no `step`).
* **C6–C9 ship:** one code run / one deploy; combined Pi smoke ✅ **2026-08-10**; one Last Docs audit ✅.
* **C6:** Soft refresh — merge `setOption` (no notMerge wipe), no soft animation, ≤1 resize, water/actuator period via soft helper; hard path unchanged. Bar: in-place series update; axes/zoom/selection kept.
* **C7:** All four: smartphone-portrait two-row presets only (chips+pencil / Show Favorites+Edit+Hidden devices, compact text, no wrap; PC/landscape single row); SSE filter restore (shared Control+History bindings, all four + blue); landscape phone filters **not sticky** + chart-open hide Control/History + hint; legend dots removed.
* **C8:** Log-only dismiss lines — `Alert dismissed (banner|bell): level=<ui-severity> "…text…"`; no alert id; no `ALERT_DISMISSED` state removal; UX unchanged.
* **C9:** All device-ref lines in `wanos.log`, every integration → `entity_id (name, idx N)` (automation-log parity / `format_device_ref`).
* **C10:** Plural Nodes; Planned past/done **removed** from list (not relabeled); Hue COLOR OUTPUT text-only remove; climate legend/line parity; binary ON/OFF vs non-binary set vs motion hits (day Y + month/year counts); History omit **all** `type === "scene"`; filter+blinds drag stable. ✅ **Done 2026-08-11**.
* **C11:** Assess/decide Control vs History list membership (queued; after C4 default).
* **C3:** Force ALL-OFF parallel-per-integration + 300ms pace + exclusion tags + confirm UX.
* **C4:** Rename entrypoints; update all consumers.

## ❓ Residual Open Qs

* *(none for **C1 / C2 / C5 / C6 / C7 / C8 / C9 / C10** — C10 closed by Pi smoke **2026-08-11**.)*
* **C11** assess open until kickoff (queued).
* **C3 / C4** remain open as specified above (later in sequence).