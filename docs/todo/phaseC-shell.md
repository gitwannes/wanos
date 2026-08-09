# ⚡ WanOS Phase C — Operator shell

Explorer / Admin / system UX polish **outside** Blocky, plus Admin force tools, HTML entrypoint renames, and Session History chart polish.

**Status:** Spec **LOCKED**. Subphases **C1 → C2 → C5 → C3 → C4** (C5 with shell chrome; C3/C4 later unless needed sooner).

**Related:** Blocky → [`phaseB-blocky.md`](phaseB-blocky.md) (**B10A** then **B10B**). Soft-hide → **B7**; auto-off → **B8** (both done). Device typing → [`phaseD-typing.md`](phaseD-typing.md). Sequence → [`pipeline.md`](pipeline.md).

**Moved to Blocky (B10A/B10B):** former user events, rule enable, Hue Blockly bugs, toolbar Delete, dirty leave (+ multi-flow follow-up).

---

## Size & subphases

| Subphase | Items | Character |
|---|---|---|
| **C1 — Explorer chrome** | Hidden filter; favorites edit/filter | Frontend-only, fast |
| **C2 — Admin + system pages** | Planned Automations; bell; reboot; gear-only nav; leave-guards | Admin UI + one API |
| **C5 — History graphs** | Landscape filters; dew point; Y-axis snap | Session History charts |
| **C3 — Force ALL-OFF** | Admin reconciliation sweep | Admin tool + integrations |
| **C4 — HTML renames** | `commander`→`wisc`; `blocky`→`automations` | Shell entrypoints |

Ship **C1 → C2** near-term; **C5** after C2 (same letter, History page); **C3/C4** later unless needed sooner.

---

## 📋 C1 — Explorer chrome 🔜 TODO

### Hidden switch → filter pane

* **Hidden** label + toggle on **one line**.
* Move from presets / toolbar into the sticky **filter** pane.

### Favorites edit + Favorites filter

* Hide Favorites **filter** when there are **no favorites** (not when view-presets empty).
* **Edit favorites** mode: selection UI only while editing; outside = low-emphasis indicator (or none).
* Filter: show only when `actuatorFavorites.length > 0`; last favorite removed → clear filter + hide toggle.
* View-presets may store `favoritesOnly`; apply with zero favorites → ignore that bit.

**C1 DoD:** Hidden in filter pane (one line); edit-favorites safe; Favorites filter iff favorites exist.

---

## 📋 C2 — Admin + system-command pages 🔜 TODO

### Planned Automations pane

* No IDX; show **name + type**; drop/rename **“will …”**.

### Critical alerts in bell

* Bell **Admin-only**; criticals also in bell; banner dismiss ≠ bell dismiss.

### Admin Debug: “Reboot Wanos”

* Restart **WanOS service** (not host). Confirm modal. `POST /api/admin/restart` → 202.
* Primary: `startwanos.sh restart` / `systemctl restart wanos.service` (Pi sudo/polkit as needed).
* Fallback: process exit + unit `Restart=always`. Client reconnect UX (~60–90s timeout).

### System-command header nav

* Gear → Admin only; no Explorer / WISC / History / Automation joins. Clear page title.

### Discard + leave-guard (hidden devices + auto-off)

* Discard when dirty + confirm; leave-guard on gear/browser leave (Cancel / Discard / Save).

**C2 DoD:** Timeline polish; bell/criticals; reboot works on Pi; system-command shells gear-only; discard + leave-guard on soft-hide + auto-off.

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

## 📋 C5 — History graphs 🔜 TODO

Session History (`sensorhistory`) chart polish — not Blocky, not B9A sensors-in-automations.

### Landscape filters

* Smartphone **landscape**: filter boxes must not consume ~half the viewport.
* Find a compact pattern (collapse / drawer / icon-only / overlay) so the **chart owns** the screen.

### Dew point

* Add **dew point** on temp/hum graphs (derived from temp + humidity; FE series is enough unless storage is needed later).

### Y-axis autoscale

* Min/max from the **visible** graph series (not a fixed full-scale).
* Snap: **temperature** ticks / bounds on **5°**; **humidity** on **10%**.

**C5 DoD:** Landscape phone: chart primary, filters compact; dew point visible on temp/hum; Y-axis tracks visible data with 5° / 10% snap. Smoke on phone + desktop.

---

## 🚦 Decisions locked (summary)

* **C1:** Hidden → filter; edit favorites; filter iff favorites.
* **C2:** Planned Automations name+type; bell/criticals; service reboot; gear-only system pages; discard + leave-guard.
* **C5:** History landscape filters compact; dew point on temp/hum; Y-axis from visible series (temp/5°, hum/10%).
* **C3:** Force ALL-OFF parallel-per-integration + 300ms pace + exclusion tags + confirm UX.
* **C4:** Rename entrypoints; update all consumers.

## ❓ Residual Open Qs

**None.** *(Ops: Pi passwordless restart for primary reboot path. C5 filter chrome pattern = impl choice.)*
