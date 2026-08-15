# ⚡ WanOS Phase C — Operator shell

Explorer / Admin / system UX polish **outside** Blocky, plus Admin force tools, HTML entrypoint renames, and Explorer History chart polish.

**Status:** Spec **LOCKED**. **C1 / C2 / C5 ✅ DONE** (Pi smoke **2026-08-09**). **C6–C9 ✅ DONE** (combined Pi smoke **2026-08-10**). **C10 ✅ DONE** (Pi smoke **2026-08-11**). Queued: **C3 → C4 → C11 → C12 → C17 → C20 → C18 → C19 → C21 → C22 → C16 → C15 → C13**. **C18** / **C19** / **C20** / **C21** / **C22** may run **∥ cluster**. Pipeline next: **B2** / **B9C** (see [`pipeline.md`](pipeline.md)).

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
| **C12 — Post-C10 polish** | Hue bri int; binary duration; alert `produced_at`; Z-Wave `-term`; scene favorites; shutter debounce; temp/hum frost line; Hidden preset admin-only | FE + log · mid |
| **C17 — Alert dismiss persist** | Banner dismiss vs reload — **assess at kickoff** | Admin alerts · low |
| **C18 — Sensor live lag** | Explorer **Control** live numbers lag **seconds** after a toggle (all sensors) — kickoff **2026-08-15**; **cause lead not locked** | SSE / event drain · low |
| **C19 — History auto-refresh blank** | Auto-refresh black / title-only; keep settings + window — **see C6** | History charts · low |
| **C20 — Bell Clear All** | Admin SYSTEM NOTIFICATIONS **Clear All** does nothing | Admin alerts · low |
| **C21 — AUTO OFF while OFF** | Explorer countdown runs on a device that is already OFF | Explorer live · low |
| **C22 — Host “(no history)”** | Three Host gauges tagged no history; siblings are not | Host / History · low |
| **C16 — Day chart sliding 24 h window** | Fixed 24 h viewport; pan over `hires_days` hi-res; zoom-in only | History charts · mid |
| **C15 — Admin lab switch** | Move Enable lab controls → Debug Commands row; lab pane iff switch ON | Admin · low |
| **C13 — Merge hide + Timers & types** | Soft-hide as column on Timers & types; retire `hiddendevices`; page rename TBD | Assess → decide · mid |
| **C3 — Force ALL-OFF** | Admin reconciliation sweep | Admin tool + integrations |
| **C4 — HTML renames** | `commander`→`wisc`; `blocky`→`automations` | Shell entrypoints |

**C1 → C2 → C5** shipped. **C6–C9** ✅ **2026-08-10**. **C10** ✅ Pi smoke **2026-08-11**. **C11** after **C4**. **C12** → **C17** → **C20** → **C18** → **C19** → **C21** → **C22** → **C16** → **C15** → **C13**. **C18** / **C19** / **C20** / **C21** / **C22** **∥ cluster** (may jump). NOT CONNECTED + admin **`vNN`** → **B10G ✅** (**2026-08-12**). **C3/C4** later unless needed sooner.

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

* Pages: **`hiddendevices`**, **`lightingautooff`** (Admin label **Timers & types** — **D** ✅ [`phaseD-typing.md`](phaseD-typing.md)), **`zwave`**.
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
* **`blocky` → `blockly` everywhere** — **locked 2026-08-12:** identifiers, text, **`blocky.html` → `blockly.html`**, **`blocky.js` → `blockly.js`**, nav/data attrs (`data-wanos-nav`, routes), shell label **Blockly**. **Do not** rename to **`automations.html`** / **`automations.js`** (prior C4 draft **withdrawn**).

**to be checked:** All links, redirects, shell nav, kiosk, nginx/static routes, bookmarks, cache-bust `?v=` query params. Shell chrome — not editor semantics (**B19**).

**C4 DoD:** New names live everywhere operators hit; no remaining `blocky` in paths/identifiers (except git history); no `automations.*` entrypoint names; old URLs redirect or 404 intentionally documented. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

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
* **`level=`** = UI alert severity already on the alert: `info` | `warning` | `error` | `critical` | `success` (not logger ERROR/WARNING). The log record itself is still **`info`**.
* Banner shows **`critical` only**. Integration connection transitions use UI `error` / `success` (bell only) and separately log ERROR / INFO to `wanos.log`.

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

**Out of scope:** C10 polish items; Blocky Library UE/SE/SR; G2/G5; Host **(no history)** tag on three gauges → **C22**.

**C11 DoD:** Written decision in this file + pipeline; if impl: Pi smoke for Control + History list parity rules; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C12 — Post-C10 polish 🔜 TODO

**Origin:** operator inbox **2026-08-11**. Shell / History / Admin — **not** G2 bridge truth, **not** Blocky editor (**B10G** ✅ load checklist / timings / NOT CONNECTED / `vNN`; **B10H** ✅ cold-load shorten). **One ship** (default). Size **mid**. **Spec locked** (operator Q&A **2026-08-11**).

| # | Item |
|---|---|
| 1 | **Hue Explorer brightness** — display + slider: **integer only** (no decimals). Round **nearest**; **ON never `0`** (`0` = OFF). Slider floor **`1`** when ON. Range **`1–100`**. *(Display/formatting only — not G2 bridge sync.)* |
| 2 | **History binary (non-motion) month/year** — **total ON duration** aggregated from history intervals (ON→OFF). **Month:** `minutes_on` per bucket; **Year:** `hours_on` per bucket. **UI:** series/axis label **“duration ON”**; Y-axis **minutes** (month) / **hours** (year). **Day:** keep C10 binary ON/OFF chart (unchanged). |
| 3 | **Motion** — keep C10 **hits** model (not duration). **Visibility locked:** keep as-is — **75xxx stays soft-hidden**; not in Explorer/History list unless operator toggles **Hidden devices**; backend history unchanged. Document in ops/docs only (no list UX change). |
| 4 | **Alert dismiss log — `produced_at`** — extend **C8** line shape: add **when the alert was produced** (`produced_at` only — dismiss time stays implicit log timestamp). UX unchanged. |
| 5 | **Z-Wave config search — negative filter** — mirror Explorer: **`-term`** excludes (same `_parseTextQuery` semantics). Fields: **name, path, idx** (today’s Z-Wave positive match set). |
| 6 | **Scene favorites bug** — favoriting **one** dashboard scene must not favorite **all** scenes (likely UUID `id` vs numeric idx in `actuatorFavorites`). |
| 7 | **Shutters debounce — assess** — FE `getUiLockTime('blinds')` uses fixed **7s**; backend `hub_handlers` uses proportional delay from `blinds.travel_times` / `default_travel_time_secs`. Confirm gap; align FE lock (and/or rubberband) with travel math if needed. |
| 8 | **Temp/hum frost line** — see § item 8 below. |
| 9 | **Manage Presets — Hidden row admin-only** — see § item 9 below. |

### Item 8 — temp/hum frost styling (extends C5 dew)

* **Day chart:** where **temp < dew**, render that segment **red** and **thicker** (temp series only). Dew series stays on **day** temp/hum charts only.
* **Month / year — locked:** **no dew series** (remove consolidated dew min/max lines shipped in C5). **No** frost styling on aggregated charts.
* **Day point density (for kickoff):** rolling **`hires_days`** buffer once **C16** ships; until then API returns **24 h** only. Throttle: **≥0.5 °C** / **≥2 %RH** / **300 s** max interval. **~288 points/series/24 h** ceiling when flat; dew FE-paired on matching timestamps.

**Operator request (verbatim):**
> - in temp/hum graphs: when temp goes below dew point: change that part of the line in red and make it thicker -- Q: is it usefull to have this in month/year graphs as well? I think not, but verify&confirm -- general: is it usefull to have the consolidated dew point graph in month/year charts? again, I think not, but verify&confirm

**Operator lock-in (2026-08-12):** remove dew from **month & year**; keep dew (and frost styling) on **day** only.

### Item 9 — Hidden view-preset admin-only (Explorer Manage Presets)

**Covering operator request (verbatim):**
> - the modal after load for the automation page: don't display it after load but have a small button top-left (right of the page-version) that displays it
> - + 4 screenshots attached

**Operator request (verbatim from screenshot):**
> should not be visible when not logged in as admin

**Locked:** In Explorer **Manage Presets**, the **Hidden** preset row (screenshot: `5 Hidden • Sort: Name`) is **admin-only**. Non-admin must not see it (and must not be able to apply/save it). Hidden-devices **filter toggle** in the presets pane stays as C1 (admin already required for that chrome — confirm at impl that non-admin cannot reach Hidden).

### Item 2 — chart families (extends C10 item 5)

**A — Binary day** — unchanged (ON/OFF on Y).

**A′ — Binary month/year** — duration totals (not ON/OFF, not hit counts): sum ON segment lengths per bucket → **minutes** (month) / **hours** (year).

**C — Motion** — unchanged: day = hit spikes; month/year = **# hits** (not duration, not ON/OFF).

### Item 4 — locked log line shape (extends C8)

```text
Alert dismissed (banner): level=<level> produced_at=<iso-or-unix> "…message text…"
Alert dismissed (bell): level=<level> produced_at=<iso-or-unix> "…message text…"
```

*`produced_at` format — pick at impl (ISO local vs unix s).*

### Out of scope

* G2 Hue bri/xy **bridge** truth.
* B10G Automations load checklist / timings / NOT CONNECTED / `vNN` — ✅ **2026-08-12**; **B10H** cold-load shorten — ✅ **2026-08-12**.
* C11 Control vs History membership model (item 3 does not reopen it).
* Explorer **live** sensor lag after B10H / optimistic UI → **C18**.
* History auto-refresh blank / lost window → **C19** (see **C6**; do not reopen C6).

**C12 DoD:** Items 1–9 on Pi where relevant; binary month/year show duration ON with correct units; motion visibility documented (no UX change); alert dismiss lines include `produced_at`; Z-Wave `-term` works; scene favorites per-scene; shutter debounce assessed/fixed if confirmed; temp/hum day frost line; **dew removed from month/year**; Hidden preset admin-only in Manage Presets. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

*(Former **C14** — NOT CONNECTED investigate + admin page **`vNN`** — folded into **B10G** ✅ **2026-08-12**; see [`phaseB-blocky.md`](phaseB-blocky.md) § B10G.)*

---

## 📋 C15 — Admin lab switch relocation 🔜 TODO

**Origin:** operator inbox **2026-08-12**. Admin UI — **not** Blocky. Size **low**. Sequence: **after C12** (or with **C13** admin churn).

**Operator request (verbatim):**
> - move "enable lab controls" to system admin pane (the only one left on the admin page) under "debug commands" (no button, but a switch, sits in same row as buttons for other functions) - lab mode pane only opens / is visible when this switch is on

**Operator lock-in (2026-08-12):** Today the lab card **header is always visible** with the enable switch on the right. **Target:** move switch to **Debug Commands** row; **entire lab pane hidden by default** (no header, no simulator) until switch **ON**.

**Locked triage intent:**

* Move **Enable lab controls** from Lab card header → **System Commands** card, **Debug Commands** section — **toggle switch** on the right (same row pattern as Entity Registry Check / Test UI Alert; not a GO button).
* **Lab Mode Manual Simulator** (header + body) **`x-show` only when switch ON** — nothing lab-related visible when OFF.
* Disabled-when-hardware-live rules unchanged (SHT11/GPIO guard).

**C15 DoD:** Switch in Debug Commands row; **no lab UI when OFF**; full lab pane when ON; Pi smoke enable/disable + simulations guard. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C17 — Alert banner dismiss vs reload 🔜 TODO (assess)

**Origin:** operator inbox **2026-08-13** (screenshot 1 — Admin critical banners). Extends **C2** / **C8**. Size **low**. Sequence: **after C12**.

**Covering operator request (verbatim):**
> - the modal after load for the automation page: don't display it after load but have a small button top-left (right of the page-version) that displays it
> - + 4 screenshots attached

**Operator request (verbatim from screenshot):**
> msgs re-appear after dismissal and page reload

**Fact (today):** Banner dismiss is **FE-session only** (C2 dual dismiss; C8 does not call server `ALERT_DISMISSED`). Reload restores still-active criticals.

**Assess at kickoff (not locked):**

* Persist dismiss across reload **while the fault is still true** vs only hide until that incident is gone / next new occurrence.
* Bell vs banner (C2 dual dismiss) — whether persist applies to both.
* Store: localStorage vs server instance id — pick with the semantics above.
* Do not reopen C8 log shape except as needed for an instance key.

**C17 DoD:** Assess decision recorded in this file; if impl: Pi smoke Admin dismiss + reload per that decision. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

**Out of scope:** Admin bell **Clear All** no-op → **C20**.

---

## 📋 C18 — Sensor live update lag 🔜 TODO (kickoff 2026-08-15)

**Origin:** operator inbox **2026-08-15**. Size **low** (may bump **mid** if cause locks on event-worker drain). Sequence: **∥ cluster** anytime after **B10H** ✅; default after **C17** if not jumped.

**Operator request (verbatim):**
> did i already put this in the pipeline? sensors seems lagged since the "positivistic" fix (and the bug that came before that)? it seems that the sensors don't always update direcctly (they did before)

*(“positivistic” = **optimistic** UI lock — see below.)*

### Pipeline check (2026-08-15) — was **not** already queued

Checked Sequence, Inbox, and phase files: **no** existing item for sensor live-lag after the optimistic toggle fix. This subphase is the first record.

### Related shipped work (not this item)

| When | What | Where |
|---|---|---|
| **B10H** ✅ **2026-08-12** | Event-driven SSE replaced the **0.5 s poll**. Operator later described this as **the bug that came before**: stale **ON** echoes became visible on light toggles. Shipped as cold-load / flicker fix — **not** as remaining sensor lag. | [`phaseB-blocky.md`](phaseB-blocky.md) § B10H; [`pipeline.md`](pipeline.md) Done |
| **Optimistic UI + `uiLocks`** **2026-08-14** | Explorer light/switch toggle: mutate local `state.devices` immediately + short **`uiLocks`** so SSE cannot snap the checkbox back. Implemented **immediately** (not parked). Docs never mentioned a sensor-lag follow-up. | `frontend/app.js` `injectLabHubStateChange` + devices-domain SSE filter; chat [Item triage and adjustments](8196459f-b496-49cd-8ab9-181ed445571e) |

**B10H effect (from that triage):** device deltas hit the browser in tens of milliseconds. The same stale ON report arrived **before** the lamp had moved. Alpine rebound `:checked="item.is_on"` → OFF→ON flicker. Speakers/shutters already had optimistic local state + locks; lights/switches did not — until the 2026-08-14 fix.

### Kickoff Q&A (operator 2026-08-15) — surface / symptom **locked**

| # | Question | Answer |
|---|---|---|
| 1 | Surface | Explorer **Control** live numbers |
| 2 | Which sensors | **All** |
| 3 | What lag looks like | Value **does** update, but **(lots of) seconds later** |
| 4 | Correlate with toggle? | **Mostly after something is toggled** |

Quiet Explorer (no recent ON/OFF) is **not** the main repro. History **charts** stay **C19**. History-tab live numbers and WISC/kiosk were **not** reported — out of C18 unless a later repro says otherwise.

### Cause — ranked lead, **not locked**

Code review against the four answers (not Pi-traced):

| Rank | Lead | Fits answers? |
|---|---|---|
| **1** | Event worker drains only when the queue is empty, then **`await`s every state listener before SSE** (`state_manager._process_events`). Hue **`await _send_light_command`**, RFX **`await _transmit_physical`**, Z-Wave **`await mqtt publish`** run **on that drain**. Sensor events sit in the queue until that I/O finishes; Control then jumps. Optimistic toggle makes the freeze obvious (light instant, sensors wait). | **Yes** — all sensors, seconds later, mostly after toggle |
| 2 | SSE 10 s watchdog + reconnect snapshot — only if pings also stall (sync block, not `await`) | Possible amplifier; **unconfirmed** (no overlay report) |
| — | `uiLocks` dropping **other** idxs | **No** — lock is per-idx, **2 s** for switch/light, would not delay **all** sensors |
| — | Temp/hum exact `!=` skip | **No** — not all sensors, not “seconds later”, not toggle-correlated |
| — | Climate history deadband | **No** — History DB, not Control live |

**Working theory (pending operator confirm):** after a Control toggle, the event-worker drain waits on outbound integration I/O; Explorer Control sensor rows stay stale until that drain completes.

### Out of scope

* **C12** item 7 shutter debounce / **C12** frost line.
* **C16** sliding 24 h History window.
* **C19** History auto-refresh blank chart (points at **C6**; do not reopen C6).
* **G3** ✅ OWM outside poll cadence (**10′**; was 30′).
* **B10H** deferred list/v2 cache; **G8** boot autostart.
* Reopening the optimistic **light/switch** toggle fix unless cause lock proves the lock itself delays sensors (code says it does not).

**C18 DoD:** Assess decision recorded in this file (surface **locked**; cause **locked**). If impl: Pi smoke — Explorer Control live sensors keep updating during/after a toggle (no multi-second freeze of all sensor rows). **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C19 — History auto-refresh blank chart 🔜 TODO

**Origin:** operator inbox **2026-08-15**. Explorer History charts — **not** C18 live sensor lag, **not** C16 sliding window (keep window on refresh). Size **low**. **Regression of C6** (Done) — **do not reopen C6 DoD**. Soft-refresh intent: § **C6**. Sequence: **∥ cluster** (C6 ✅); default after **C18** if not jumped.

**Operator request (verbatim):**
> bug: when graph updates automatically, shows nothing: black, only title, eg "Temperature / humidity last 24 hours" no graph at all - re-opening the graph: visible again // auto-refresh should keep ALL graph settings without flicker! also window

**Locked triage intent:**

* Auto-refresh must **not** blank the chart (black / title-only). Re-open working is the workaround, not the fix.
* Keep **all** graph settings on refresh, **including window** — no flicker. Details: **C6** (merge soft `setOption`, axes/zoom/selection kept).
* C16 window/pan, when it ships, must keep that same no-wipe refresh.

**Out of scope:** Reopening **C6** as a Done phase; **C18** live Explorer numbers; **C12** frost line.

**C19 DoD:** Auto-refresh keeps series + settings + window; no blank title-only chart; Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C20 — Admin bell “Clear All” does nothing 🔜 TODO

**Origin:** operator screenshot **2026-08-14** (Admin **SYSTEM NOTIFICATIONS**). Extends **C2** / **C8** — **not** C17 (banner dismiss vs reload). Size **low**. Sequence: **after C17** (same Admin alert surface); **∥ cluster** OK.

**Operator request (verbatim from screenshot):**
> clicking 'clear all' doesnt do anything

**Locked triage intent:** Admin bell **Clear All** must clear the notification list (same effect as dismissing the visible rows). Individual **X** is not this bug. Do not reopen **C2** / **C8** DoD.

**Out of scope:** **C17** persist dismiss across reload; **C12** item 4 `produced_at` log; **G14** ON bell copy.

**C20 DoD:** Clear All empties the Admin SYSTEM NOTIFICATIONS list; Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C21 — AUTO OFF countdown while device is OFF 🔜 TODO

**Origin:** operator screenshot **2026-08-15** (Explorer Control, **cinema licht**). Explorer live row — **not** C10 item 2 (Planned Automations stale timers), **not** reopening **B8**. Size **low**. Sequence: **∥ cluster**.

**Operator request (verbatim from screenshot):**
> IS OFF, but timer runs!??

**Locked triage intent:** If the device is **OFF**, Explorer must **not** show a running **AUTO OFF IN …** countdown. Screenshot: **cinema licht** toggle OFF + red **AUTO OFF IN 01:43:36**. Do not reopen **B8** (auto-off engine/config). Kickoff: UI leftover vs engine timer still armed.

**Out of scope:** **C10** Planned Automations past-remove; **C3** Force ALL-OFF; **G6** reload re-arm (unless kickoff proves that path).

**C21 DoD:** OFF device has no AUTO OFF countdown; Pi smoke Explorer. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C22 — Host gauges tagged “(no history)” 🔜 TODO

**Origin:** operator screenshot **2026-08-15** (Explorer Host metrics). **Not** C11 (Control vs History **list membership**), **not** C19 (blank chart). Size **low**. Sequence: **∥ cluster**; default near **C16** if not jumped.

**Operator request (verbatim from screenshot):**
> how come these 3 have no history?

**Locked triage intent:** Three Host rows show **(no history)** while siblings do not: **Host CPU Temperature**, **Host Load Average (15m)**, **Host Load Average (5m)**. Others (CPU Usage, Disk, Load 1m, Log2Ram, Memory) have no such tag. Kickoff: should they record history, or should the tag/list be consistent — **ask**, do not assume.

**Out of scope:** **C11** membership model; **C19** auto-refresh wipe; **C5** / **C10** chart styling already shipped.

**C22 DoD:** Assess recorded (record vs hide tag); impl if decided; Pi smoke those three Host rows. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C16 — Day chart sliding 24 h window 🔜 TODO

**Origin:** operator inbox **2026-08-12**. Explorer → History day panels — extends **C5** / **C6** (not Blocky). Size **mid**. Sequence: **after C12** (same chart surface; pairs with item 8 frost line).

**Operator request (verbatim):**
> - can we change the rolling hi-res window to 1 week? what would that mean for code, for DB size?
> - on the daily chart: I want a windows of 24hrs (can be shortened to see more detail but not made bigger) - but I Want to slide this window up to the available hi-res data, so 1 week ago

**Locked triage intent:**

* **Viewport:** fixed **maximum 24 h** wide; **zoom-in** allowed (keep today’s ~**1 h** floor via `minValueSpan`); **cannot zoom out** past 24 h (`maxValueSpan`).
* **Data buffer:** load full hi-res retention — **`history.retention.hires_days`** (default **7**) — not a wider chart axis. **Do not** extend DB retention for this item.
* **Default view:** viewport **right-aligned to now** (most recent 24 h).
* **Pan:** user slides the 24 h window back across stored hi-res (up to **`hires_days` ago**) via inside-drag + bottom slider.
* **Backend (`range=day`):** return hi-res samples for **`now − hires_days × 86400`** (climate / power / host `sensor_samples`; actuator `device_events`) — replace hardcoded **`86400`** query window only. Optional response metadata: `retention_days`, `default_window_hours: 24`.
* **Frontend:** `xAxis` spans full buffer `[now − hires_days, now]`; ECharts `dataZoom` with **`maxValueSpan = 24 h`**, initial **`startValue` / `endValue`** = last 24 h (not `start:0 end:100` on a 24 h axis). Reuse/adapt `_applyTimeWindow` / `_applyClimateTimeWindow`.
* **Soft refresh (C6):** preserve pan position on merge; if viewport was **live** (end ≈ now), keep pinned to now.
* **Y-axis snap (C5):** unchanged — snap from values inside current dataZoom window.
* **Copy:** panel title stays **24 hour window** (not “last 24 hours” when panned); optional subtitle with visible from/to when not live.
* **DB size:** **unchanged** — hi-res already retained 7 days; cost is ~**7×** day-chart API payload + FE points (~2k/series ceiling at 300 s climate throttle).
* **Water day chart — assess at kickoff:** today uses **`sensor_hourly`** (24 h bars), not hi-res — decide whether to expose **7×24 h** hourly bars with same pan UX or leave water on live 24 h only.
* **Out of scope:** windowed API (`?end=`) per pan (unless Pi perf forces it); changing `hires_days` retention; month/year charts; `sensorhistory.html` utility page (unless explicitly included at kickoff).

**C16 DoD:** Day hi-res charts (climate, power, host, actuators) load `hires_days` buffer; 24 h max viewport; pan to oldest hi-res; zoom-in only; soft refresh preserves pan/live pin; water decision recorded; Pi smoke pan + live refresh. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C13 — Merge Hidden devices into Timers & types 🔜 TODO (assess)

**Origin:** operator inbox **2026-08-11**. Admin system pages — **not** Blocky, **not** reopening **B7**/**B8**/**D** product model. Size **mid**. Sequence: **after C15** (or with C15 admin churn).

### Locked triage intent

* Keep **Timers & types** as the **single** Admin page for soft-hide + auto-off + product type.
* Add soft-hide as an **extra column** (Hidden) on that device list.
* **Retire** separate **Explorer hidden devices** page (`hiddendevices.html` + Admin nav entry). Soft-hide SoT stays **`deviceexplorer_hide`** (B7).
* **Page rename** required (Admin label / title; HTML filename may follow **C4** or C13 — **name TBD at assess/impl**, not this triage). Track as open todo under this phase.
* **Save model** (one Save vs two APIs under one UI) — **leave for assess**.

### Assess at kickoff

* Column UX (checkbox vs toggle; which rows editable; interaction with existing All/Hidden/Non-hidden filters).
* Dirty / leave-guard once hide + timers/types share a page.
* Whether rename lands in C13 or rides **C4** HTML rename wave.
* Docs consumers of “Explorer hidden devices” / `hiddendevices` links.

### Out of scope

* Changing soft-hide or auto-off YAML keys / engine semantics.
* Reopening **D1** product-type rules (still edited on Timers & types).
* Explorer Control **Hidden devices** toggle (C1/C7) — separate surface.

**C13 DoD:** Assess decision recorded; if impl: one Admin page with Hidden column; `hiddendevices` retired; page renamed (name chosen); save/dirty model as decided; Pi smoke hide + timers/types; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

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
* **C12:** item **8** — day frost line; dew removed from month/year; item **9** Hidden preset admin-only.
* **C17:** banner dismiss vs reload — **assess at kickoff** (not locked).
* **C20:** Admin bell **Clear All** must clear the list (not C17).
* **C18:** Explorer **Control** live numbers — **all** sensors; updates **seconds later**; **mostly after a toggle**. Cause lead = event-worker drain awaits Hue/RFX/Z-Wave I/O before SSE (**not locked**).
* **C19:** History auto-refresh blank — keep settings + window; **see C6**; do not reopen C6.
* **C21:** Explorer AUTO OFF countdown must not run when the device is already OFF.
* **C22:** three Host rows **(no history)** — assess record vs tag; not C11.
* **C16:** sliding 24 h viewport over `hires_days` hi-res; zoom-in only; pan back to retention limit. Blank auto-refresh → **C19**.
* **C15:** lab switch in Debug Commands; entire lab pane hidden when OFF.
* **C13:** Merge hide into Timers & types …
* **C4:** **`blocky`→`blockly`** — **`blockly.html` / `blockly.js`**; shell label **Blockly**; **not** `automations.*`.

## ❓ Residual Open Qs

* *(none for **C1 / C2 / C5 / C6 / C7 / C8 / C9 / C10** — C10 closed by Pi smoke **2026-08-11**.)*
* **C11** assess open until kickoff (queued).
* **C12:** item **8** locked — day frost line; **dew removed from month/year** (day only). Item **9** — Hidden Manage Presets row **admin-only**.
* **C17:** **assess at kickoff** — persist while fault still true vs new occurrence; bell vs banner; store.
* **C20:** Clear All currently no-op.
* **C18:** surface/symptom locked **2026-08-15**; **cause** still open (working theory: drain awaits outbound I/O).
* **C19:** auto-refresh must not blank; keep settings + window (**C6**).
* **C21:** AUTO OFF countdown while toggle OFF.
* **C22:** **assess at kickoff** — Host CPU temp / load 5m / load 15m missing history vs inconsistent tag.
* **C16:** locked — 24 h max viewport; pan over **`hires_days`**; water day chart **assess at kickoff**.
* **C15:** locked — switch in Debug Commands; **entire lab pane hidden when OFF**.
* **C3 / C4** remain open as specified above (later in sequence).
* **Ops — cinema rule merge:** confirm pickable state = **`switch.epson`** (or other) before YAML rewrite.
* NOT CONNECTED + admin **`vNN`** → **B10G** ✅ (**2026-08-12**).