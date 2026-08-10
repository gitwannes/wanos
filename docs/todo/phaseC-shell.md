# ⚡ WanOS Phase C — Operator shell

Explorer / Admin / system UX polish **outside** Blocky, plus Admin force tools, HTML entrypoint renames, and Explorer History chart polish.

**Status:** Spec **LOCKED**. **C1 / C2 / C5 ✅ DONE** (Pi smoke **2026-08-09**). Remaining: **C6** (flicker) → **C7** (Explorer follow-ups) → **C3 → C4**.

**Related:** Blocky → [`phaseB-blocky.md`](phaseB-blocky.md) (**B10A** / **B10C** ✅; next Blocky = **B10B** — `events:` UUID catalog). Soft-hide → **B7**; auto-off → **B8** (both done). Device typing → [`phaseD-typing.md`](phaseD-typing.md). Sequence → [`pipeline.md`](pipeline.md).

**Moved to Blocky (B10A/B10B/B10C):** events catalog / scenes, rule enable, Hue Blockly bugs, toolbar Delete, dirty leave (+ multi-flow follow-up); soft-hide picker regression → **B10C** ✅.

---

## Size & subphases

| Subphase | Items | Character |
|---|---|---|
| **C1 — Explorer chrome** | Hidden + Favorites in presets pane; edit favorites | Frontend-only, fast |
| **C2 — Admin + system pages** | Planned Automations; bell; reboot; gear-only nav; leave-guards | Admin UI + one API |
| **C5 — History graphs** | Landscape filters; dew point; Y-axis snap; climate smooth (d/m/y) | Explorer History charts |
| **C6 — History flicker** | Auto-refresh redraw flash (all charts) | C5 soft-refresh follow-up |
| **C7 — Explorer follow-ups** | Favorites portrait layout; filter restore after SSE; landscape chart chrome; legend dots | FE; C1/C5 leftovers |
| **C3 — Force ALL-OFF** | Admin reconciliation sweep | Admin tool + integrations |
| **C4 — HTML renames** | `commander`→`wisc`; `blocky`→`automations` | Shell entrypoints |

**C1 → C2 → C5** shipped. **C6** then **C7**. **C3/C4** later unless needed sooner.

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

**C1 DoD:** Hidden + Favorites in presets pane (one line each); Edit/Done favorites; Favorites filter iff favorites exist.

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

**C2 DoD:** Timeline polish; bell/criticals with dual dismiss; reboot works on Pi (after Ops); three system pages gear-only; discard + leave-guard on hide / auto-off / zwave.

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

**C3 DoD:** Sweep runs on Pi with pacing; exclusions honored; Admin UX confirms + reports completion.

---

## 📋 C4 — Rename HTML entrypoints 🔜 TODO

* `commander.html` → `wisc.html`
* `blocky.html` → `automations.html`

**to be checked:** All links, redirects, shell nav, kiosk, nginx/static routes, bookmarks. Shell chrome — not Blocky logic.

**C4 DoD:** New names live everywhere operators hit; old URLs redirect or 404 intentionally documented.

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

**C5 DoD:** Landscape + chart open → filters compact; dew on temp/hum (formula above, 1 decimal); Y-axis from dataZoom window with snaps in table; climate day/month/year with `smooth: true` (no step); smoke phone + desktop.

---

## 📋 C6 — History auto-refresh flicker 🔜 TODO

**Origin:** operator report **2026-08-09**. C5 soft-refresh follow-up — **not** reopening C5 DoD.

* Explorer → History: on auto-refresh, chart **flickers** (line appears to reset then redraw).
* Scope: **all** History graphs (climate / actuators / host / utility; day/month/year as applicable).

**C6 DoD:** Auto-refresh updates series without visible reset/flicker; Pi smoke all chart families.

---

## 📋 C7 — Explorer follow-ups 🔜 TODO

**Origin:** operator reports **2026-08-10** (screenshots). C1/C5 leftovers — **not** reopening those DoDs. FE-only.

### Favorites row — smartphone portrait

* **Portrait:** Favorites chrome must **never** share one horizontal line with the favorite **number chips** (1–5) — Edit on **or** off. Chips wrap / sit on a row below (no overlap with “FAVORITES” label).
* **Landscape / desktop:** single-line layout OK (C1).

### Filters after SSE reconnect

* Bug: Device Explorer open; after **SSE drop/reconnect**, active filters (e.g. status **ON**) look inactive (not blue) and list not filtered; toggling away and back fixes it.
* Code today: `searchQuery` / `typeFilter` / `statusFilter` / `sortMode` saved in `sessionStorage` (`wanos_active_filters`); SSE `connectSSE` does **not** clear them — fix re-apply / select↔model sync after snapshot so **all four** restore with correct **blue active** styling.
* Scope: Control (and History list chrome if same bindings).

### Landscape chart — full bleed (C5 follow-on)

* Smartphone **landscape + chart open** (same gate as C5 filter collapse): also hide **Control | History** picker and the **“Filter collapsed · …”** hint row so the graph owns the screen.
* Portrait / no chart: unchanged.

### History legend — no marker dots

* All Explorer History chart legends: show **line style/color only** — **remove** legend marker dots (graph series stay lines without point markers).

**C7 DoD:** Portrait favorites no overlap; SSE reconnect restores filters + blue active; landscape+chart hides Control/History + collapsed hint; legends without dots; Pi smoke phone portrait/landscape.

---

## 🚦 Decisions locked (summary)

* **C1:** Hidden + Favorites stay in presets pane (one line each on landscape/desktop); Edit/Done favorites; idle = no indicators; filter iff favorites exist. **Portrait favorites layout → C7.**
* **C2:** Timeline name+type, strip “will”; dual banner/bell dismiss; service reboot via sudoers `NOPASSWD: systemctl restart wanos.service` + UI error on fail; gear-only on hide / auto-off / zwave; leave-guard on those three (Blocky-style). Types = today’s metadata until **D**.
* **C5:** Explorer History (not `sensorhistory`); compact filters only when chart open; dew via **Sonntag Magnus** (1 decimal) when temp+hum; Y from dataZoom; snaps per table (power **10 W**); climate day/month/year lines **`smooth: true`** (no `step`).
* **C6:** History auto-refresh must not flicker/reset the line (all chart families).
* **C7:** Portrait favorites wrap; SSE filter restore (all four + blue); landscape+chart hide Control/History + hint row; legend dots removed.
* **C3:** Force ALL-OFF parallel-per-integration + 300ms pace + exclusion tags + confirm UX.
* **C4:** Rename entrypoints; update all consumers.

## ❓ Residual Open Qs

* *(none for C1 / C2 / C5 — closed by Pi smoke **2026-08-09**. C6 / C7 / C3 / C4 open as above.)*