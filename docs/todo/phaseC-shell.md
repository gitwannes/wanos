# ⚡ WanOS Phase C — Operator shell

Explorer / Admin / system UX polish **outside** Blocky, plus Admin force tools, HTML entrypoint renames, and Explorer History chart polish.

**Status:** Spec **LOCKED**. **C1 / C2 / C5 ✅ DONE** (Pi smoke **2026-08-09**). **C6–C9 ✅ DONE** (combined Pi smoke **2026-08-10**). **C10 ✅ DONE** (Pi smoke **2026-08-11**). **C18** / **C23** / **C22** / **C19** ✅ **DONE** (**2026-08-16**). Queued: **C3 → C4 → C26 → C11 → C12 → C17 → C20 → C21 → C27 → C16 → C24 → C25 → C15 → C13**. **C20** / **C21** / **C27** may run **∥ cluster**. Pipeline Blockly next: **B7** / **B14** (see [`pipeline.md`](pipeline.md)).

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
| **C18 — Sensor live lag** | Explorer Control live lag after toggle — ✅ **Done 2026-08-16** | SSE / Q4–Q5 · mid |
| **C19 — History auto-refresh blank** | Auto-refresh black / title-only; keep settings + window — ✅ **Done 2026-08-16** | History charts · low |
| **C20 — Bell Clear All** | Admin SYSTEM NOTIFICATIONS **Clear All** does nothing | Admin alerts · low |
| **C21 — AUTO OFF while OFF** | Explorer countdown runs on a device that is already OFF | Explorer live · low |
| **C27 — Sunrise/sunset chrome** | Admin General Diagnostics + Explorer title area | Admin + shell · low |
| **C22 — Host “(no history)”** | Host CPU temp on history allowlist; load 5m/15m live-only — ✅ **Done 2026-08-16** | Host / History · low |
| **C23 — SSE SseClient unhashable** | EventSource dies ~25 ms — ✅ **Done 2026-08-16** (with **C18**) | SSE hub · low |
| **C16 — Day chart sliding 24 h window** | Fixed 24 h viewport; pan over `hires_days` hi-res; zoom-in only | History charts · mid |
| **C24 — Temp/hum day fullscreen** | Tab overlay; AH + CI overlay-only; 5 checkboxes; 3rd y-axis; CSV | History charts · mid |
| **C25 — Overlay dew likelihood** | OWM 2.5 clouds/wind; heuristic **dew likelihood %** in C24 overlay | History charts · mid |
| **C15 — Admin lab switch** | Move Enable lab controls → Debug Commands row; lab pane iff switch ON | Admin · low |
| **C13 — Merge hide + Timers & types** | Soft-hide as column on Timers & types; retire `hiddendevices`; page rename TBD | Assess → decide · mid |
| **C3 — Force ALL-OFF** | Admin reconciliation sweep | Admin tool + integrations |
| **C4 — HTML renames** | `commander`→`wisc`; `blocky`→`blockly` | Shell entrypoints |
| **C26 — Frontend JS modularization** | Split `app.js` + `blockly.js`; shared helpers; `login.js`; **`reference.md` JS catalog** | FE maintainability · mid · after **C4** |

**C1 → C2 → C5** shipped. **C6–C9** ✅ **2026-08-10**. **C10** ✅ Pi smoke **2026-08-11**. **C18** / **C23** / **C22** / **C19** ✅ **2026-08-16**. **C26** after **C4**; **C11** after **C26**. **C12** → **C17** → **C20** → **C21** → **C27** → **C16** → **C24** → **C25** → **C15** → **C13**. **C20** / **C21** / **C27** **∥ cluster** (may jump). NOT CONNECTED + admin **`vNN`** → **B10G ✅** (**2026-08-12**). **C3/C4** later unless needed sooner.

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

**C26 follows C4:** split **`blockly.js`** (post-rename) into `blockly-*` siblings — no interim `blocky-*` pass.

---

## 📋 C26 — Frontend JS modularization 🔜 TODO

**Letter:** **C26**. **Sequence #14**. **Depends on:** **C4** shipped (`blocky` → `blockly` rename live). **Cross-ref:** Automations Blockly scope → [`phaseB-blocky.md`](phaseB-blocky.md).

**Problem (verified):** post-**C4** `frontend/blockly.js` (today `blocky.js`) ≈ **6000** lines; `frontend/app.js` ≈ **5200** lines. Not a runtime crisis (Pi static serve, no bundler); **maintainability + page-weight** cost (navigation, merge conflicts, duplicated helpers). `login.html` loads all of `app.js` but uses only `loginApp()`.

#### Operator requests (verbatim)

> blocky.js and app.js are both approx 6000 lines long - is that a problem? if it is, is there a way to split or shorten these? no code  
> *(2026-08-22)*

> triage into pipeline, I would go with your recommendations  
> *(2026-08-22)*

#### Locked approach (triage **2026-08-22** — operator confirmed recommendations)

**Delivery style:** **Classic scripts** (not ES modules) — multi-`<script>` load order (same pattern as `wanos-shell.js`); shared helpers as **explicit globals** (`wanosGetAuthHeaders`, …). **No bundler** unless a later phase finds concrete need. ES modules deferred (Alpine `x-data="wanosApp()"` + inline HTML globals like `xyToHex` stay simpler on classic scripts).

**Incremental ship order (one seam per patch; Pi smoke between steps where behaviour touches UI):**

| Step | What | Notes |
|---|---|---|
| **1** | **`login.js`** | Peel `loginApp()` off `app.js`; `login.html` loads `login.js` only |
| **2** | **`wanos-common.js`** | `wanosRedirectIfNarrow`, `WANOS_WIDE_MIN_PX`, `wanosGetAuthHeaders`, `wanosLogout` — dedupe **`app.js`**, **`blockly.js`**, **`hiddendevices.js`**, **`lightingautooff.js`**, **`zwave.js`** (Alpine apps may keep thin `this.getAuthHeaders()` → common) |
| **3** | **`wanos-hue.js`** | Pure xy↔hex / preset wheel helpers (no DOM) — shared by app, blockly, commander inline |
| **4** | **Split `blockly.js`** | See **Locked filenames** below |
| **5** | **Split `app.js`** | See **Locked filenames** below |

#### Locked filenames (kickoff **2026-08-22**)

**Naming:** shared → `wanos-*.js`; Blockly siblings → **`blockly-*.js`** (post-**C4** names). Page Alpine apps stay single-file unless they grow.

**Shared**

| File | Role |
|---|---|
| `wanos-common.js` | Viewport redirect, auth headers, logout |
| `wanos-hue.js` | Hue xy↔hex math (pure functions) |
| `wanos-charts.js` | ECharts stale/dispose/resize (from `app.js` top) |
| `login.js` | `loginApp()` only |

**Blockly** (Automations page — load after `wanos-shell.js`, before Alpine binds):

```text
wanos-common.js → wanos-hue.js →
blockly-constants.js → blockly-entity.js → blockly-condition.js → blockly-action.js →
blockly-blocks.js → blockly-yaml.js → blockly-app.js
```

| File | Role |
|---|---|
| `blockly-constants.js` | Role sets, `BLOCKY_*` constants, opaque bag helpers |
| `blockly-entity.js` | Entity meta, allowed-for-role, dropdown option builders |
| `blockly-condition.js` | Condition/trigger shape, numeric compare, wake/gate wording |
| `blockly-action.js` | Action rich fields, Hue modal, Sonos/blinds/volume |
| `blockly-blocks.js` | `Blockly.Blocks.*`, toolbox, workspace resize/scroll |
| `blockly-yaml.js` | Read/write YAML, legacy v2 projection, orphan assert |
| `blockly-app.js` | `blockyApp()` Alpine only |

No monolithic `blockly.js` stub — **HTML lists script order** (classic scripts cannot auto-chain).

**Explorer shell** (per-page subset; full explorer/admin/history stack):

```text
wanos-common.js → wanos-hue.js → wanos-charts.js → wanos-sse.js →
app-explorer.js → app-history.js → app-admin.js → app.js
```

| File | Role |
|---|---|
| `wanos-sse.js` | `connectSSE`, reconnect guards, snapshot freshness (B10G/H) |
| `app-explorer.js` | List/filter/presets, control dispatch, device rows, Hue preset UI |
| `app-history.js` | History charts, session history, dew/AH helpers |
| `app-admin.js` | Admin toggles, alerts bell, lab, reboot (pathname-gated methods) |
| `app.js` | Thin `wanosApp()` composer + `init*Page()` router |

**Other page scripts** (unchanged names; load `wanos-common.js`):

| File | Pages |
|---|---|
| `hiddendevices.js` | Hidden devices |
| `lightingautooff.js` | Timers & types |
| `zwave.js` | Z-Wave config |
| `wanos-shell.js` | Shared shell (existing) |
| `iro.min.js` | Third-party colour wheel (vendor; note in catalog, no split) |

**Explicitly out of scope for C26:**

* Big-bang rewrite or framework migration
* Splitting into many tiny files without clear ownership seams
* Changing Blockly/YAML semantics or Alpine/ECharts integration rules (ECharts instances stay **outside** Alpine reactive data — see `app.js` header comment)

**HTML / cache-bust:** each new script gets a `?v=` bump on every page that loads it; update `PAGE_VERSIONS` in `wanos-shell.js` where applicable.

#### Docs — `reference.md` frontend catalog (in scope)

**Every WanOS-authored `frontend/*.js` file** must appear in [`docs/reference.md`](../reference.md) § **frontend/** when C26 ships — not only the new splits.

For each file, document at minimum:

| Field | Content |
|---|---|
| **Path** | `frontend/<name>.js` |
| **One-line role** | What the file owns |
| **Loaded by** | Which HTML entrypoint(s) and relative script order when non-obvious |
| **Key globals** | Functions/objects other scripts or inline HTML depend on (e.g. `wanosApp`, `xyToHex`) |

Include **`wanos-shell.js`**, all **`blockly-*` / `app-*` / `wanos-*`**, page apps (`hiddendevices.js`, …), and **`login.js`**. **`iro.min.js`**: vendor bundle — one line (third-party, not maintained in-repo). Remove or rewrite stale entries (today `reference.md` lists only `app.js` under frontend).

Script load matrices may live in `reference.md` (preferred SoT for operators/devs) with a short pointer from this section.

**C26 DoD:** Steps 1–5 shipped; no duplicate redirect/auth/Hue xy helpers across app + blockly + page scripts; login page no longer loads explorer/admin JS; all shell pages smoke OK; **`docs/reference.md` § frontend lists every shipped `frontend/*.js` file** per table above; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

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

**C19 amendment (2026-08-16, does not reopen this DoD):** soft `replaceMerge` is `['series', 'dataZoom']` (saved zoom copied onto the option first); ECharts rebinds when `getDom()` ≠ the live node. See § **C19**.

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

* G2 Hue bri/xy bridge truth; G5 ✅ cinema rolluik half; B10F Automations chrome; integration log prefixes → **G7**.
* Control vs History list membership product model → **C11**.
* Automations SR/UR fire-status timing strings (different surface).

**C10 DoD:** Items 1–7 fixed on Pi (phone + desktop where relevant); all `type === "scene"` gone from History list; binary charts read ON/OFF; motion day = hit Y-labels, month/year = hit counts; Planned past/done entries absent from list (not stuck `imminent`); Hue hex text gone, wheel remains; filter+blinds drag keeps row + applies command. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-11** (Pi smoke + docs).

---

## 📋 C11 — Control vs History list membership 🔜 TODO

**Origin:** C10 item 6 lock (**2026-08-11**). **Not** part of C10 ship.

**Problem:** Explorer **Control** membership (`dashboard_events` / devices) and Explorer **History** list membership (history DB idxs + metadata, incl. former `type === "scene"` catalog rows) are **not the same model**. C10 only omits all History `scene` rows; it does not unify the two lists.

**Scope (assess → decide → impl if needed):** document current divergence; decide whether Control and History should share one membership rule (and what happens to SE/UE event history, hidden devices, utilities, etc.); then implement or explicitly defer with rationale.

**Out of scope:** C10 polish items; Blocky Library UE/SE/SR; G2; **G5** ✅; Host history allowlist (**C22** ✅ — CPU temp recorded; load 5m/15m live-only).

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
* Explorer **live** Control lag after B10H / optimistic UI → **C18** ✅.
* History auto-refresh blank / lost window → **C19** ✅ (**2026-08-16**; see **C6**; did not reopen C6).
* Temp/hum day fullscreen + AH/CI + checkboxes + CSV → **C24** (after **C16**; do not reopen **C5**). Overlay dew likelihood → **C25**.

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

## 📋 C18 — Sensor live update lag ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-16**) — both locked repros (Hue OFF → wastafel Control; Hidden physical ON → Hue + Sonos). No NOT CONNECTED.

**Origin:** operator inbox **2026-08-15**. Size **mid**. Sequence: **∥ cluster** after **B10H** ✅ (needed live EventSource — **C23** ✅ same day).

**Operator request (verbatim):**
> did i already put this in the pipeline? sensors seems lagged since the "positivistic" fix (and the bug that came before that)? it seems that the sensors don't always update direcctly (they did before)

*(“positivistic” = **optimistic** UI lock — see below.)*

### Shipped (2026-08-16)

Live Control siblings follow RAM at **request success** or **0.5 s** (`core/command_commit.py`). Clicked row stays **t = 0** optimistic (`uiLocks`). Integrations **`create_task`** I/O (drain does not `await` Hue PUT). YAML follow-ups run in the **same drain**. Drain SSE snapshot **holds** in-flight idxs at `old_val` until apply; `c18_commit` applies/reverts (bypasses `uiLocks` on snap-back). Fail before reveal: siblings stay old. Fail after: snap RAM + UI + bell `ERROR: Command failed: {format_device_ref} → ON|OFF`.

**Why ~10 s (measured, not the kickoff Hue-PUT lock):** B10H `SseClient` in a `set` was unhashable (**C23**). EventSource died in ~25 ms; UI caught up on REST reconnect/watchdog. Pipe repair: `@dataclass(eq=False)`, immediate SSE `ping`, pure ASGI middleware, no HTTP/2 `Connection` header.

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

Quiet Explorer (no recent ON/OFF) is **not** the main repro. History **charts** stay **C19** ✅. History-tab live numbers and WISC/kiosk were **not** reported — out of C18 unless a later repro says otherwise.

### Pi repros (operator 2026-08-15) — **locked**

**Repro 1**

> example: I switch on "badk 1e Hue" and then switch on "badk 1e wastafel"
> all ok - then I switch off "badk 1e Hue", the automation immediately switches "badk 1e wastafel" off, but the UI lags quite a while
> no disconnetion appears, just the "OLD" state

Clicked: Hue `hue.group.badk_1e_hue` (optimistic OFF). Sibling: Z-Wave `zwave.badk_1e_wastafel` stays OLD ON in Control. Physical OFF is immediate. No overlay.

**Repro 2**

> another example: I switch on "badk 1e hue physical" (in "hidden devices",) then move immediately to the non-hidden devices view: "badk 1e hue" and "badk 1e sonos" should be ON, but they are not - only after a few seconds they seems to switch on
> this was not the case in the past - the switch was immediate

Clicked: Hidden-view Z-Wave `zwave.badk_1e_hue_physical` (Explorer **Hidden devices** toggle, `showHiddenNodes` — row is in `deviceexplorer_hide`). Then Hidden off. Hue group + Sonos (`media_player.badk_1e`) still show OFF for seconds. Used to be immediate (pre-B10H 0.5 s poll).

### Cause **locked** (2026-08-15) — **superseded at ship**

Kickoff lock: drain awaits Hue PUT before SSE. **Shipped finding (2026-08-16):** that was real drain hygiene (`create_task` kept) but the ~10 s UI lag was a **dead EventSource** (**C23**). Keep the Q4/Q5 contract below; do not treat Hue-PUT-await as the 10 s generator.

**DoD width locked:** Explorer **Control live rows** that were not the optimistic click — Hue, Z-Wave lights, Sonos, climate sensors, any sibling updated in the same drain. Not climate-only. Not History charts (**C19** ✅).

### UI timing contract (operator 2026-08-15) — **locked**

| # | Decision |
|---|---|
| **1** | **Clicked** row flips at **t = 0** (optimistic, as today). 0.5 s rule is for **other** Control rows. |
| **2** | Switch other rows to RAM at **0.5 s**, or **earlier** if the outbound command reports **success** before 0.5 s. |
| **3** | Same policy for **all** commandable devices (not Hue-only). |
| **4** | Success/fail = **request-level** (table below). Silent skip = **fail**. Not “device did it.” |
| **5** | Bell + log copy locked below. |

Fail **before** 0.5 s (and before any success): **do not** switch those rows. Fail **after** they already switched: **snap back** + error bell + app-log ERROR.

#### Q4 — success / fail (**locked** 2026-08-15)

Request-level only. Device echo is out of C18.

| Integration | **Success** | **Fail** |
|---|---|---|
| **Hue** | PUT **200** or **207** (207 body errors **not** parsed — today’s meaning) | HTTP not 200/207; network/exception; **no UUID / no session / empty payload** |
| **Z-Wave** | `publish()` returns without exception (MQTT connected) | MQTT down (publish skipped); `MqttError` |
| **Sonos** | OFF: `_pause_speaker` returns; ON: `_start_playback` is **true** | Exception; ON and playback did **not** start |
| **Onkyo** | `write` + `drain` complete | Exception; **no TCP writer** |
| **Epson** | `power()` returns **True** (includes today’s read-timeout → True) | `power()` returns **False** |
| **RFX** | `transport.write` completed | Port dead; parse/protocol error; write exception |

GPIO local PWM is not this confirm path. OWM is not a device command. Hue 207 and Epson timeout stay today’s meaning (not extra C18 scope).

#### Q5 — bell / log (**locked** 2026-08-15)

Bell **error** (not banner): `ERROR:` prefix so AlertManager stays bell-only.

* Bell: `ERROR: Command failed: {format_device_ref} → ON` (or `OFF` / the attempted state).
* App log ERROR: same + integration tag + reason (`HTTP 503`, `MQTT publish skipped`, exception text).

Example bell: `ERROR: Command failed: hue.group.badk_1e_hue (badk 1e Hue, idx 51001) → OFF`

### Out of scope

* **C12** item 7 shutter debounce / **C12** frost line.
* **C16** sliding 24 h History window.
* **C19** History auto-refresh blank chart — ✅ **2026-08-16** (points at **C6**; did not reopen C6).
* **G3** ✅ OWM outside poll cadence (**10′**; was 30′).
* **B10H** deferred list/v2 cache; **G8** boot autostart.
* Reopening the optimistic **light/switch** toggle on the **clicked** row (that path is working in these repros).

**C18 DoD:** ✅ **2026-08-16** — kickoff contract shipped; both Pi repros OK; live EventSource (**C23**); Last DoD docs audit this close-out.

---

## 📋 C19 — History auto-refresh blank chart ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-16**) — leave-open >60s; series stay drawn.

**Origin:** operator inbox **2026-08-15**. Explorer History charts — **not** C18 live sensor lag, **not** C16 sliding window. Size **low**. **Regression of C6** (Done) — **did not reopen C6 DoD**. Soft-refresh intent: § **C6**.

**Operator request (verbatim):**
> bug: when graph updates automatically, shows nothing: black, only title, eg "Temperature / humidity last 24 hours" no graph at all - re-opening the graph: visible again // auto-refresh should keep ALL graph settings without flicker! also window

### Shipped (2026-08-16)

Explorer History 60s auto-refresh (`refreshExplorerHistory` → soft `reloadSelectedSensorDetail`) keeps series in the chart box (no title + dark-empty plot). Settings + titled windows (last 24h / month / year) and zoom/selection kept. Hard open/switch unchanged. **C16** (when it ships) must keep this no-wipe refresh.

Both 60s-path defects were patched (cause not isolated on Pi; combined fix smoked OK):

* **Stale instance:** `_ensureHistoryChart` / `_ensureActuatorChart` dispose + re-init when `getDom() !== el`; skip `setOption` / `resize` on detached nodes; `$nextTick` after list reload and before soft draw.
* **Soft merge:** `setOption` `{ notMerge: false, replaceMerge: ['series', 'dataZoom'] }` (saved zoom copied onto the option); series `id`s; if merge drops drawable series, full `notMerge` replace (no dispose).

### Kickoff Q&A (operator 2026-08-15) — **locked**

| # | Question | Answer |
|---|---|---|
| 1 | Which charts | **All** Explorer History charts (climate / host / utility / actuator; day / month / year as shown) |
| 2 | Cadence | **Every** auto-refresh (~**60s**), not intermittent |
| 3 | What “blank” looks like | Title stays; **dark empty chart box** (plot gone, box still there) |
| 4 | Zoom / pan needed? | **No** — default window; still **keep** window + settings on refresh (**C6**) |
| 5 | Which page | **Explorer History** only — not `sensorhistory.html` |

**Out of scope (unchanged):** Reopening **C6** as a Done phase; **C18** live Explorer numbers; **C12** frost line; **C16** sliding window; standalone **`sensorhistory.html`**.

**C19 DoD:** ✅ **2026-08-16** — Pi smoke leave-open >60s; series + window kept; Last DoD docs audit this close-out.

---

## 📋 C20 — Admin bell “Clear All” does nothing 🔜 TODO (kickoff **locked** 2026-08-15)

**Origin:** operator screenshot **2026-08-14** (Admin **SYSTEM NOTIFICATIONS**). Extends **C2** / **C8** — **not** C17 (banner dismiss vs reload). Size **low**. Sequence: **after C17** (same Admin alert surface); **∥ cluster** OK.

**Operator request (verbatim from screenshot):**
> clicking 'clear all' doesnt do anything

**Kickoff answers (operator 2026-08-15):**

* **Session:** dismiss **every currently visible** bell row (critical + non-critical), same semantics as **X** on each row. Criticals stay on the server (banner can remain). Non-criticals are removed from shared state.
* **C8:** one `Alert dismissed (bell):` line per cleared row.
* **Button:** shown whenever the bell list is non-empty (including criticals-only).
* **Reload:** same as per-row X — non-criticals stay gone (server-removed); criticals can reappear. Persist-across-reload stays **C17**.

**Locked contract:**

* After **Clear All**: list empty, badge **0**, *No recent system events.*
* Per-row **X** unchanged. Do not reopen **C2** / **C8** DoD.
* **Banner** stays independent (C2 dual dismiss). This button is the bell only.

**Fact (today, not locked as cause):** `clearNonCriticalAlerts()` only fires `ALERT_CLEAR_NON_CRITICAL` (leaves criticals; no local dismiss; no C8). Individual X uses `dismissBellAlert`. Implement when commanded.

**Out of scope:** **C17** persist dismiss across reload; **C12** item 4 `produced_at` log; **G14** ON bell copy.

**C20 DoD:** Clear All empties the Admin SYSTEM NOTIFICATIONS list (all visible rows); Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C21 — AUTO OFF countdown while device is OFF 🔜 TODO

**Origin:** operator screenshot **2026-08-15** (Explorer Control, **cinema licht**). Explorer live row — **not** C10 item 2 (Planned Automations stale timers), **not** reopening **B8**. Size **low**. Sequence: **∥ cluster**.

**Operator request (verbatim from screenshot):**
> IS OFF, but timer runs!??

**Locked triage intent:** If the device is **OFF**, Explorer must **not** show a running **AUTO OFF IN …** countdown. Screenshot: **cinema licht** toggle OFF + red **AUTO OFF IN 01:43:36**. Do not reopen **B8** (auto-off engine/config). Kickoff: UI leftover vs engine timer still armed.

**Out of scope:** **C10** Planned Automations past-remove; **C3** Force ALL-OFF; **G6** reload re-arm (unless kickoff proves that path).

**C21 DoD:** OFF device has no AUTO OFF countdown; Pi smoke Explorer. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C27 — Sunrise/sunset chrome 🔜 TODO

**Origin:** operator inbox **2026-08-22**. Admin **General Diagnostics** + Explorer shell title — **not** Blocky, **not** new backend (data already in `/api/state`). Size **low**. Sequence: **∥ cluster** (with **C20** / **C21**); no deps on **B23**.

**Operator request (verbatim):**
> triage: add sunrise & -set to both sysadmin page (show as 1st item in general diagnostics pane) and explorer page as tooltip on the title "device explorer" (how is this tooltip visible on smartphones)?

### Verified (code)

* **`state.sensors.sunrise_unix`** / **`sunset_unix`** — already in `/api/state` (updated on schedule events).
* **`app.js`** — `sunriseRelativeText` / `sunsetRelativeText` computed each tick via **`getRelativeTime`** → `(in HH:MM:SS)` / `(HH:MM:SS ago)`; **not displayed** on Admin or Explorer today.
* **Admin** — `frontend/admin.html` **General Diagnostics** first rows today: OS Uptime, Engine Uptime (`~355`).
* **Explorer title** — `frontend/wanos-shell.js` explorer branch: **`⚡ WanOS // Device Explorer`** span (`~155`); no sunrise/sunset yet.

### Locked triage intent

| Surface | Placement |
|---|---|
| **Admin (sysadmin)** | **First row** in **General Diagnostics** (above OS Uptime). Label + value consistent with existing mono/uppercase rows. |
| **Explorer** | On **Device Explorer** title chrome only (not History mode title). Show sunrise + sunset in the same relative format as Admin. |

**Mobile / tooltip (operator lock-in 2026-08-22):** Native HTML **`title`** tooltips **do not work reliably on touch** — there is no hover on phones; iOS may show `title` only after a **long-press** (inconsistent); many Android browsers never show it. **Do not ship Explorer as `title`-only.**

**Explorer — locked:** Small **ℹ** control beside **Device Explorer** title; **tap** opens popover (or modal) with sunrise + sunset (same relative format as Admin). Optional **`title`** on desktop for hover is fine as secondary hint only.

**Admin — locked:** Always-visible **first row** in General Diagnostics (no popover needed).

**Format (kickoff Q):** Relative only (reuse **`getRelativeTime`**) vs also absolute local clock time (e.g. `06:42`).

### Out of scope

* Blockly / automation editor.
* New OWM or schedule backend (unless kickoff finds missing `sunrise_unix` / `sunset_unix` on Pi — then bugfix elsewhere).
* History mode title chrome (unless operator expands scope at kickoff).

**C27 DoD:** Admin General Diagnostics shows sunrise + sunset as **first** item; Explorer Device Explorer title has **ℹ** → popover with both (works on phone tap); values track live state; Pi smoke Admin + Explorer. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C22 — Host gauges tagged “(no history)” ✅ DONE

**Operator smoke / close:** ✅ **2026-08-16** — operator close-out after allowlist ship.

**Origin:** operator screenshot **2026-08-15** (Explorer Host metrics). **Not** C11 (Control vs History **list membership**), **not** C19 (blank chart). Size **low**.

**Operator request (verbatim from screenshot):**
> how come these 3 have no history?

### Shipped summary

Cause was a **hardcoded allowlist** (`HOST_HISTORY_IDXS` in `logic/history_ids.py` + `SENSOR_META` / `note_gauge`), not a special UI flag. Explorer `(no history)` = idx missing from `/api/history/sensors`.

| IDX | Gauge | Decision |
|-----|--------|----------|
| `22001` | Host CPU Temperature | **Record** — added to `HOST_HISTORY_IDXS` + `SENSOR_META` (`kind: host`, `unit: °C`) |
| `22007` | Host Load Average (5m) | **Live only** — stay off allowlist |
| `22008` | Host Load Average (15m) | **Live only** — stay off allowlist |

Ingest unchanged: `HUB_STATE_CHANGED` → `note_gauge` when `idx in HOST_HISTORY_IDXS`. Detail → [`docs/sensor_history.md`](../sensor_history.md) §17.

**Out of scope (unchanged):** **C11** membership model; **C19** auto-refresh wipe ✅; **C5** / **C10** chart styling.

**C22 DoD:** ✅ **2026-08-16** — locked decision shipped; Last DoD docs audit this close-out.

---

## 📋 C23 — SSE `SseClient` unhashable ✅ DONE

**Operator smoke:** ✅ live EventSource **with C18** Pi smoke **2026-08-16** (Explorer: pending `sse` row, `ping` + domain frames, no `SSE stream broke` loop). Closed **with C18** — not a separate all-pages SSE tour.

**Origin:** operator inbox **2026-08-16** (Pi journal + log2ram 100%). Size **low**. Sequence: **∥ cluster**. Product contract is the EventSource **pipe**, not C18 Q4/Q5 / `command_commit`.

**Operator request (verbatim):**
> put these 3 "What actually prevents a repeat" in triage

Item 1 (verbatim from that turn):
> **Stop the flood** — fix `SseClient` in a `set` (and keep SSE up). That is the real generator.

Placement (verbatim **2026-08-16**):
> C23 bugfix

**Fact (Pi 2026-08-16):** `GET /api/state/sse` 200 then ASGI exception: `TypeError: unhashable type: 'SseClient'` at `core/sse_hub.py` `self._clients.add(client)`. Browser: EventSource ~25 ms, `SSE stream broke. Re-linking context in 3s...` loop. That reconnect storm filled rsyslog (`syslog`/`daemon.log`) → log2ram ENOSPC. `/var/log/wanos` stayed ~39M.

### Kickoff Q&A (operator 2026-08-16) — **locked**

| # | Question | Answer |
|---|---|---|
| 1 | Fix shape | Keep `_clients` as a **`set`**; `@dataclass(eq=False)` (identity hash). Not a `list`. Companion pipe (already in `main.py`): immediate first `ping`, pure ASGI, no `Connection: keep-alive`. |
| 2 | Smoke pages | **Explorer** with **C18**. Other SSE pages share the hub; Z-Wave config not required. |
| 3 | C18 | Closed **together**. C23 is the live EventSource, not Control lag. |
| 4 | Journal traceback | **Not** a C23 DoD item. Live EventSource implies `subscribe()` is not throwing. Rsyslog cap → **Ops1** (✅); uvicorn JWT → **Ops1 later** Item 3. |

### Shipped (2026-08-16)

* `@dataclass(eq=False)` on `SseClient` — identity hash in the hub `set`.
* SSE generator yields an immediate `ping` (B10H could return 200 with no first byte behind nginx).
* RBAC + static no-cache are **pure ASGI** (not `BaseHTTPMiddleware` around `StreamingResponse`).
* Do **not** send `Connection: keep-alive` (HTTP/2 protocol error on nginx `listen http2`).

Rsyslog cap **Ops1 ✅ Done 2026-08-16** (pipeline Done + Inbox detail): `daemon.log` off; rsyslog truncates `syslog` at 20 MiB; no `syslog` archives. **Ops1 later:** Item 3 (uvicorn access/JWT), ForwardToSyslog, log2ram SIZE, auth/kern no-archive.

**Out of scope (unchanged):** **C18** sibling RAM timing / `command_commit` (shipped separately, closed same day); **Ops1 later**; **B10H** reconnect overlay policy.

**C23 DoD:** ✅ **2026-08-16** — `subscribe()` does not raise; Explorer pending EventSource; EventStream `ping` then domain lines; no repeating `SSE stream broke`. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-16** (closed **with C18**).

---

## 📋 C16 — Day chart sliding 24 h window 🔜 TODO

**Origin:** operator inbox **2026-08-12**. Explorer → History day panels — extends **C5** / **C6** (not Blocky). Size **mid**. Sequence: **after C12** (same chart surface; pairs with item 8 frost line). **C24** follows this ship.

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
* **Out of scope:** windowed API (`?end=`) per pan (unless Pi perf forces it); changing `hires_days` retention; month/year charts; `sensorhistory.html` utility page (unless explicitly included at kickoff); temp/hum fullscreen + extra series + CSV → **C24**.

**C16 DoD:** Day hi-res charts (climate, power, host, actuators) load `hires_days` buffer; 24 h max viewport; pan to oldest hi-res; zoom-in only; soft refresh preserves pan/live pin; water decision recorded; Pi smoke pan + live refresh. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C24 — Temp/hum day fullscreen + extra climate lines 🔜 TODO

**Origin:** operator inbox **2026-08-16**. Explorer → History **temp/hum** charts — extends **C5** dew (Done) and **C16** day buffer; **not** C12 #8 frost styling; **not** C19 auto-refresh; **not** `sensorhistory.html`. Size **mid**. Sequence: **after C16** (CSV of `hires_days` buffer). Default **after Blockly cluster** (not ∥). Kickoff Q&A **locked 2026-08-16**.

**Operator request (verbatim, 2026-08-16):**
> - in alle grafieken die temperatuur EN vochtigheid combineren
> - in de DAG grafiek: voeg een button toe "open detail in full screen"
> - wanneer klik: de dag-grafiek opent in full-screen (nog steeds in de browser, die nog steeds zichtbaar is)
> - zelfde grafiek, maar bijkomende knoppen/mogelijkheden:
> - 2 bijkomende grafieklijnen, zie hierbeneden
> - 5 checkboxes voor de 5 grafiek-lijnen: default staan ze allemaal aan
> - knop export naar xls van alle gegevens (5 waarden per tijdstip) van de volledige set (7 dagen)
>
> # Weerdata Berekeningen voor 5 Grafieklijnen
> Temperatuur · Relatieve luchtvochtigheid · Dauwpunt · Absolute luchtvochtigheid · Gevoelsvochtigheid
>
> Dit document beschrijft alle formules en berekeningsstappen die nodig zijn om uit ruwe weerdata automatisch vijf grafieklijnen te genereren.
>
> ---
>
> ## 1. Inputdata per tijdstip
> Voor elk tijdstip moeten minstens deze waarden beschikbaar zijn:
>
> - Temperatuur T (°C)
> - Relatieve luchtvochtigheid RH (%)
> - Dauwpunt Td (°C)
>
> ---
>
> ## 3. Berekening van absolute luchtvochtigheid (g/m³)
> Absolute luchtvochtigheid wordt berekend via de waterdampdruk bij het dauwpunt.
>
> ### Stap 1 — Dampdruk uit dauwpunt
>
> e = 6.112 * exp((17.67 * Td) / (Td + 243.5))
>
> ### Stap 2 — Absolute luchtvochtigheid
>
> AH = (216.7 * e) / (T + 273.15)
>
> ---
>
> ## 4. Berekening van gevoelsvochtigheid (comfort-index)
> Gevoelsvochtigheid is gebaseerd op het dauwpunt, omdat dat bepaalt hoe moeilijk zweet verdampt.
>
> ### Aanbevolen vloeiende schaal (0–100%)
>
> CI = 4.5 * Td - 30
>
> ### Grenzen toepassen
>
> if CI < 0: CI = 0
> if CI > 100: CI = 100
>
> ---
>
> ## 6. Grafiekopbouw (5 lijnen)
> Plot de volgende lijnen:
>
> 1. Temperatuur (°C)
> 2. Relatieve luchtvochtigheid (%)
> 3. Dauwpunt (°C)
> 4. Absolute luchtvochtigheid (g/m³)
> 5. Gevoelsvochtigheid (%)
>
> ### Aanbevolen assen
>
> - Linker y-as: temperatuur, dauwpunt
> - Rechter y-as: relatieve luchtvochtigheid, absolute luchtvochtigheid, gevoelsvochtigheid
>
> ---
>
> ## 7. Berekeningspipeline (samenvatting)
>
> Input: T, RH, Td(optional)
>
> If Td missing:
>     compute Td
>
> Compute e (dampdruk)
> Compute AH (absolute luchtvochtigheid)
> Compute CI (gevoelsvochtigheid)
>
> Output: T, RH, Td, AH, CI
>
> ---
>
> ## 9. Visuele aanpassing van de gevoelsvochtigheid-lijn (comfortlijn)
>
> De gevoelsvochtigheid (CI) wordt bepaald op basis van het dauwpunt.
> Om de grafiek intuïtiever te maken voor menselijke interpretatie, kan de comfortlijn visueel aangepast worden afhankelijk van de comfortcategorie.
>
> Gebruik de volgende tabel als referentie:
>
> | Dauwpunt (°C) | Comfortcategorie | CI (%) | Aanbevolen visuele stijl |
> |---------------|------------------|--------|---------------------------|
> | < 10          | Droog            | 0–20   | Dunne lijn, koele kleur (lichtblauw) |
> | 10–15         | Comfortabel      | 20–40  | Normale dikte, groene kleur |
> | 15–18         | Matig vochtig    | 40–60  | Iets dikkere lijn, geelgroen |
> | 18–21         | Vochtig          | 60–75  | Dikkere lijn, oranje |
> | 21–24         | Zeer vochtig     | 75–90  | Dikke lijn, rood |
> | > 24          | Tropisch vochtig | 90–100 | Zeer dikke lijn, donkerrood |
>
> ### Implementatie-aanwijzingen
>
> Voor elk datapunt:
>
> 1. Bepaal de comfortcategorie op basis van het dauwpunt.
> 2. Pas de stijl van de comfortlijn aan:
>    - **Kleur** volgens de tabel hierboven.
>    - **Lijndikte** volgens de tabel hierboven.
> 3. Indien de grafiekbibliotheek het ondersteunt:
>    - Gebruik **gradientkleur** wanneer de lijn door meerdere comfortzones loopt.
>    - Gebruik **markers** (bijv. cirkels) die dezelfde kleur krijgen als de comfortcategorie.
>    - Optioneel: toon een **tooltip** met tekst zoals “Vochtig – 68% CI”.
>
> ### Voorbeeld pseudocode
>
> ```
> if Td < 10:
>     color = "lightblue"
>     width = 1
> elif Td < 15:
>     color = "green"
>     width = 2
> elif Td < 18:
>     color = "yellowgreen"
>     width = 3
> elif Td < 21:
>     color = "orange"
>     width = 4
> elif Td < 24:
>     color = "red"
>     width = 5
> else:
>     color = "darkred"
>     width = 6
> ```
>
> ### Doel
>
> Door de comfortlijn visueel te koppelen aan hoe mensen vochtigheid ervaren, wordt de grafiek:
>
> - intuïtiever,
> - direct leesbaar,
> - en bruikbaar voor comfortanalyse.

**Triage placement:**

* **New C24** — not merged into **C12 #8** (frost when temp < dew) or **C16** (sliding 24 h window). Same day temp/hum surface; different work.
* **C5 already ships** temp, RH, dew on the **inline** temp/hum day chart. The two extra lines are **AH** (g/m³) and **CI** (gevoelsvochtigheid %). Five checkboxes in fullscreen: T / RH / Td / AH / CI. Do **not** reopen C5 DoD.
* **After C16** because export is “de volledige set (7 dagen)” and C16 loads the `hires_days` day buffer.

**Operator lock-in (2026-08-16):**
> extra series only in the fullscreen mode
> month/year graphs not affected
> fullscreen -> meaning: the full chrome tab
>
> close overlay: there will be an "X" in the right top corner
> missing dew: this is handled in the original code already - confiurm - if there is missing dew info, that means that either temp or hum is not available - we will not be able to calculate the 4th and 5th graph item - confirm

| Topic | Locked |
|---|---|
| Extra series / 5 checkboxes / CSV / comfort-line styling | **Fullscreen only.** Inline day chart stays C5 (T, RH, dew) + **C12 #8** frost when that ships. |
| Month / year | **Not affected.** No button, no AH/CI, no overlay. Matches **C12 #8** (dew already off month/year). |
| Fullscreen | Fills the **entire browser tab** (page viewport). Browser chrome (tab strip, URL bar) **stays visible**. **Not** F11 / `requestFullscreen()` (that hides the browser UI). WanOS Explorer chrome (list, filters, nav) is covered by the overlay. |
| Close | **X** in the **top-right** of the overlay. |
| Missing dew / AH / CI | **Confirmed from shipped C5** (`frontend/app.js` `_dewPointC` / `_dewSeriesFromTempHum`). Dew is **never stored** — FE Sonntag Magnus from **T + RH at the same timestamp**. No dew when T is missing/invalid, RH is missing/invalid (`RH <= 0` or `RH > 100`), or T and RH do not share a timestamp. Overlay **reuses that same pairing**; no second Td formula. At those timestamps **Td, AH, and CI are omitted** (gaps; do not invent). AH needs T+Td; **CI needs T+Td** (formula **2026-08-17**). Td needs T+RH — so 4th and 5th cannot be calculated without dew. T and/or RH still plot if present. |
| Overlay time window | **Same 24 h viewport as C16** (pan over `hires_days`). Export is the **full** `hires_days` buffer, not only the visible window. |
| Export format | **CSV** (Excel-openable). No `.xls` / `.xlsx` library. Button/file: **Export CSV**. Empty cells where Td/AH/CI cannot be computed. Span = `history.retention.hires_days` (not a hardcoded 7). |
| Axes | Left **°C** (T + Td). Right **%** (RH + CI). **Third** y-axis **g/m³** (AH). Each y-axis **shown only when at least one series on that axis is checked**. |
| Toggles | Overlay **checkboxes only** (default all on). **No** ECharts legend in the overlay. |

**Comfort-line (§9) — locked 2026-08-16 (operator accept):**

1. Color the CI line by comfort band (piecewise, table colors) — one CI series, one checkbox.
2. Tooltip on CI hover: category + CI% (e.g. `Vochtig – 68%`).
3. One line width for CI (same as humidity, width **2**).
4. No point markers.
5. No smooth gradient; no per-band width.

**CI formula — locked 2026-08-17** (replaces the simpler Td-only line in the 2026-08-16 inbox). Band **colors** stay Td table (§9). Plotted **CI %** uses T + Td:

```
CI_base = 4.5 * Td - 30
if CI_base < 0: CI_base = 0
if CI_base > 100: CI_base = 100
TC = 0.8 * (T - 20)
CI = CI_base + TC
if CI < 0: CI = 0
if CI > 100: CI = 100
```

**Superseded (inbox 2026-08-16, simpler):** `CI = 4.5 * Td - 30` then clamp 0–100 — no temperature correction.

**Operator request (verbatim, screenshot 2026-08-17):**
> 4. In plain tekst (klaar voor code)
>
> Input:
> - T (°C) = luchttemperatuur
> - Td (°C) = dauwpunt
>
> Stap 1 – Basis op dauwpunt
> CI_base = 4.5 * Td - 30
> if CI_base < 0: CI_base = 0
> if CI_base > 100: CI_base = 100
>
> Stap 2 – Temperatuurcorrectie
> TC = 0.8 * (T - 20)
>
> Stap 3 – Totale comfortindex
> CI = CI_base + TC
> if CI < 0: CI = 0
> if CI > 100: CI = 100

**Operator (2026-08-16):**
> accept - any other open items?
>
> 1: keep 24h window in fullscreen graph - 7d (or whatever is in config) export to xls
> 2: CSV is ok
> 3: 3rd Y is ok (show only when relevant graph lines are picked via checkboxes)
> 4: ok

**Impl defaults (standing):** English series names matching C5 (`Temperature`, `Humidity`, `Dew point`) plus `Absolute humidity` and `Apparent humidity`; overlay follows **C6** soft refresh (keep checkboxes + window); overlay inherits **C12 #8** frost on temp when C12 has shipped.

### Comfort-line — bands (locked colors; width unused)

| Band (Td °C) | Category | CI % | Doc style |
|---|---|---|---|
| < 10 | Droog | 0–20 | thin, lightblue |
| 10–15 | Comfortabel | 20–40 | normal, green |
| 15–18 | Matig vochtig | 40–60 | slightly thicker, yellowgreen |
| 18–21 | Vochtig | 60–75 | thicker, orange |
| 21–24 | Zeer vochtig | 75–90 | thick, red |
| > 24 | Tropisch vochtig | 90–100 | very thick, darkred |

**Constraint (verified):** ECharts `lineStyle.width` is **per series**, not per point. Overlay uses **one** CI width and piecewise **color** only.

**Rejected 2026-08-16:** six CI series for variable width; always-on circles; F11 fullscreen; smooth gradient; Excel `.xls`/`.xlsx` dependency.

**Out of scope**

* Extra series on the **inline** day chart.
* Month / year temp/hum charts.
* **C12 #8** frost styling of the temperature line.
* **C16** viewport / pan / `maxValueSpan`.
* **C19** auto-refresh blank — ✅ **2026-08-16**.
* Reopening **C5**.
* F11 / Fullscreen API.
* `.xls` / `.xlsx` library.
* Standalone `sensorhistory.html` unless kickoff includes it.
* Overlay **dew likelihood %** / persist OWM clouds/wind → **C25**.

**C24 DoD:** Kickoff Q&A **locked 2026-08-16**. CI formula **locked 2026-08-17** (`CI_base` from Td + `TC = 0.8*(T-20)`, clamp). Temp/hum **day** chart has “open detail in full screen”; overlay fills the browser tab with **X** top-right; 24 h viewport (C16 pan); five checkboxes default on, no overlay legend; third y-axis g/m³ for AH, axes hidden when their series are unchecked; CSV export of five columns for the full `hires_days` buffer; month/year unchanged; Td/AH/CI reuse C5 pairing; CI piecewise comfort colors (Td bands) + tooltip (new CI %), one width, no markers; Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 C25 — Overlay dew likelihood % 🔜 TODO

**Origin:** operator inbox **2026-08-16**. Explorer History **C24 fullscreen day overlay** only — **not** inline day, **not** month/year, **not** C24 five-series lock. Size **mid**. Sequence: **after C24**. Default **after Blockly cluster** (not ∥).

**Operator request (verbatim, 2026-08-16):**
> triage as new item: additional graph in the fullscreen day view -- get additional info from that 2.5 json (clouds/wind) and with your list (which i accept): plot another line "dew likelihood %"

**Accepted heuristic (operator 2026-08-16 — dew, not rain):**

* **Night** (after sunset, before sunrise) — otherwise ~0
* **T − Td** small → higher
* **Low cloud** → higher
* **Light wind** → higher
* **Rain / drizzle now** → **0**

**Triage placement:**

* **New C25** — do **not** reopen **C24** (five series / three axes / CSV-of-five stay C24 DoD).
* Overlay-only extra line, series name **`Dew likelihood %`**. Honest **heuristic index 0–100**, not a calibrated meteorological probability.
* **OWM Current 2.5** (`integrations/open_weather.py` today uses `main.temp` / `main.humidity` only). Persist **clouds** + **wind** from that JSON (and enough **weather/rain** to zero the score). Indoor temp/hum has no 2.5 payload → **no** dew-likelihood series there.
* Night gate can use existing OWM sunrise/sunset already stored for schedule (`SUNRISE_SUNSET_UPDATE`).
* History line over `hires_days` needs those extra fields **stored** (today they are discarded). How (units on `sensor_samples` vs other) → **kickoff**. Numeric weights for T−Td / cloud / wind → **kickoff**. Sixth checkbox + CSV column + which y-axis (right **%** vs own) → **kickoff**.

**Out of scope**

* Reopening **C24** / **C5** / **C12 #8**.
* Inline day chart; month/year.
* Leaf-wetness / IR grass sensor.
* G4 One Call (this is Current 2.5).
* Calling the line a true probability.

**C25 DoD:** Kickoff locks storage, formula weights, checkbox/CSV/axis. C24 overlay shows **Dew likelihood %** on OWM/outside temp/hum using persisted 2.5 clouds/wind and the accepted heuristic (night, T−Td, cloud, wind, rain→0); indoor climate unchanged; Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

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
* **C6:** Soft refresh — merge `setOption` (no notMerge wipe), no soft animation, ≤1 resize, water/actuator period via soft helper; hard path unchanged. Bar: in-place series update; axes/zoom/selection kept. **C19** ✅: `replaceMerge` also `dataZoom`; rebind stale ECharts nodes.
* **C19:** ✅ **Done 2026-08-16** — Explorer History 60s auto-refresh keeps series + window (stale instance rebind + soft `replaceMerge` series/dataZoom). Did not reopen **C6**.
* **C7:** All four: smartphone-portrait two-row presets only (chips+pencil / Show Favorites+Edit+Hidden devices, compact text, no wrap; PC/landscape single row); SSE filter restore (shared Control+History bindings, all four + blue); landscape phone filters **not sticky** + chart-open hide Control/History + hint; legend dots removed.
* **C8:** Log-only dismiss lines — `Alert dismissed (banner|bell): level=<ui-severity> "…text…"`; no alert id; no `ALERT_DISMISSED` state removal; UX unchanged.
* **C9:** All device-ref lines in `wanos.log`, every integration → `entity_id (name, idx N)` (automation-log parity / `format_device_ref`).
* **C10:** Plural Nodes; Planned past/done **removed** from list (not relabeled); Hue COLOR OUTPUT text-only remove; climate legend/line parity; binary ON/OFF vs non-binary set vs motion hits (day Y + month/year counts); History omit **all** `type === "scene"`; filter+blinds drag stable. ✅ **Done 2026-08-11**.
* **C11:** Assess/decide Control vs History list membership (queued; after C4 default).
* **C12:** item **8** — day frost line; dew removed from month/year; item **9** Hidden preset admin-only. Extra climate lines / fullscreen / CSV → **C24**.
* **C17:** banner dismiss vs reload — **assess at kickoff** (not locked).
* **C20:** kickoff **locked** 2026-08-15 — **Clear All** dismisses every visible bell row (same as each X); C8 per row; button iff list non-empty; reload same as X (**C17**). Implement when commanded.
* **C18:** ✅ **Done 2026-08-16** — Explorer Control live rows; Q4/Q5; live SSE (**C23**); drain `create_task` I/O.
* **C23:** ✅ **Done 2026-08-16** (closed **with C18**) — `SseClient` `eq=False` in the hub `set`; first ping; pure ASGI; no HTTP/2 `Connection` header. Explorer EventSource smoke; journal not a DoD.
* **C21:** Explorer AUTO OFF countdown must not run when the device is already OFF.
* **C27:** sunrise/sunset — Admin General Diagnostics **first** row; Explorer **ℹ tap → popover** on Device Explorer title (not `title`-only). Kickoff Q: relative vs absolute clock.
* **C22:** ✅ **Done 2026-08-16** — Host CPU temp (`22001`) on `HOST_HISTORY_IDXS`; load 5m/15m (`22007`/`22008`) live-only; not C11.
* **C16:** sliding 24 h viewport over `hires_days` hi-res; zoom-in only; pan back to retention limit. Blank auto-refresh → **C19** ✅. Fullscreen + extra climate lines → **C24**.
* **C24:** temp/hum **day** overlay fills the **browser tab** (not F11) with **X** top-right; 24 h window (C16); CSV of full `hires_days`; 3rd y-axis AH (axes iff series checked); checkboxes only; month/year unchanged; **after C16**; not C12 #8 frost; do not reopen **C5**. Kickoff Q&A **locked 2026-08-16**. CI **2026-08-17:** Td base + T correction. Dew likelihood → **C25**.
* **C25:** overlay **Dew likelihood %** (heuristic); OWM 2.5 clouds/wind; rain→0; **after C24**; do not reopen C24. Storage/weights/checkbox/CSV/axis → kickoff.
* **C15:** lab switch in Debug Commands; entire lab pane hidden when OFF.
* **C13:** Merge hide into Timers & types …
* **C4:** **`blocky`→`blockly`** — **`blockly.html` / `blockly.js`**; shell label **Blockly**; **not** `automations.*`.

## ❓ Residual Open Qs

* *(none for **C1 / C2 / C5 / C6 / C7 / C8 / C9 / C10 / C18 / C19 / C22 / C23** — **C18**/**C23**/**C19** Pi smoke **2026-08-16**; **C22** closed **2026-08-16**.)*
* **C11** assess open until kickoff (queued).
* **C12:** item **8** locked — day frost line; **dew removed from month/year** (day only). Item **9** — Hidden Manage Presets row **admin-only**. Extra climate lines / fullscreen / CSV → **C24**.
* **C17:** **assess at kickoff** — persist while fault still true vs new occurrence; bell vs banner; store.
* **C20:** kickoff + contract **locked** 2026-08-15 — implement when commanded.
* **C21:** AUTO OFF countdown while toggle OFF.
* **C27:** Explorer **ℹ popover** locked **2026-08-22**; relative-only vs +clock time — kickoff Q; History title out of scope unless expanded.
* **C16:** locked — 24 h max viewport; pan over **`hires_days`**; water day chart **assess at kickoff**.
* **C24:** kickoff Q&A **locked 2026-08-16** — overlay = full browser tab (not F11); **X** top-right; extra series overlay-only; month/year untouched; 24 h window + CSV of `hires_days`; 3rd y-axis AH (hide axis when series off); checkboxes only; CI piecewise color + tooltip. CI formula **locked 2026-08-17** (Td base + `TC = 0.8*(T-20)`). Implement when commanded. Dew likelihood → **C25**.
* **C25:** **not locked** — persist OWM clouds/wind/rain; formula weights; 6th checkbox/CSV; axis. Placement: after **C24**, overlay-only, OWM/outside only.
* **C15:** locked — switch in Debug Commands; **entire lab pane hidden when OFF**.
* **C26:** kickoff **locked 2026-08-22** — after **C4**; classic scripts; `blockly-*` siblings; page-script dedupe; **`reference.md` § frontend catalogs all `frontend/*.js`**.
* **C3 / C4** remain open as specified above (later in sequence).
* **Ops — cinema rule merge:** confirm pickable state = **`switch.epson`** (or other) before YAML rewrite.
* NOT CONNECTED + admin **`vNN`** → **B10G** ✅ (**2026-08-12**).