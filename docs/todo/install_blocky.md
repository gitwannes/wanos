# ⚡ WanOS: Visual Automation Editor (IFTTT) Architecture Guide

This document is the source of truth for (1) the **entity_id prerequisite** (current step) and (2) the **Blocky** visual automation editor (later).

**Todo hygiene:** `docs/todo/install_enhancements_260718.md` is a superseded sketch — **delete it when the prerequisite below is complete and verified**.  
**Operator checklist for this cutover:** `docs/todo/260803_migration.md`.  
**`dashboard_map` removal:** immediate **follow-up PR** after the cutover check is green (see migration doc Phase 7).

---

## 🧬 CURRENT STEP — Prerequisite: One Device Map + Stable `entity_id`

Blocky and automations must not store raw hardware idxs in rules. Humans see friendly **names**; saved rules use stable **`entity_id`s**; hardware still uses **idx**.

### Identity model (three layers)

| Layer | Example | Who sees / uses it |
|---|---|---|
| Display `name` | `buro licht` | UI dropdowns only — may be renamed |
| `entity_id` | `switch.buro_licht` / `hue.light.buro_spot` | Stored in automation rules — frozen after birth |
| Physical `idx` | `71001` | Z-Wave / RFX / GPIO / `devices[]` / event bus |

### Single map (DRY)

* **One registry:** `device_metadata[idx]` holds `name`, `type`, `origin`, and `entity_id`.
* **Remove `dashboard_map`** after call sites migrate — it is a duplicate of `meta.name`.
* **Do not** add a third in-memory dict on `SystemState` as a parallel source of truth.
* Reverse lookup (`entity_id → idx`) is **derived** at metadata rebuild time.
* Python device references: **always resolve** via the registry (no parallel magic idxs / no frozen string constants as source of truth).

### Birth, freeze, storage

* Users **never** type `entity_id`.
* On first registration (“birth”), the backend auto-assigns `entity_id` from the patterns below + slug of name.
* After birth, **renaming `name` does not change `entity_id`**.
* Hardware replace = change `idx`, **keep** `entity_id`.
* **Do not** re-derive `entity_id` from `name` on every boot.
* **Remap-all (regen ids from names):** **do not implement**.

### Persistence: `entity_registry.yaml`

* System-owned file at WanOS root. Backend reads/writes it.
* **Not** in hand-edited `config.yaml`.
* Boot: load → merge into `device_metadata` → birth unknowns → write back.
* Orphans: **keep** row with **`status: removed`**.
* Documented in `docs/reference.md` and `docs/architecture.md`.

### `entity_id` patterns (locked)

| Kind | `entity_id` pattern | Example |
|---|---|---|
| Hue light | `hue.light.<slug>` | `hue.light.buro_spot` |
| Hue group | `hue.group.<slug>` | `hue.group.living` |
| Z-Wave / RFX actuators (incl. “licht”) | `switch.<slug>` | `switch.buro_licht` |
| Vent / fan class | `switch.vent.<slug>` | `switch.vent.badk_1e` |
| SSR class | `switch.ssr.<slug>` | `switch.ssr.sauna` |
| Safety class | `switch.safety.<slug>` | `switch.safety.wisc` |
| Blinds | `blinds.<slug>` | `blinds.cinema` |
| Power | `sensor.power.<slug>` | `sensor.power.pc` |
| Temp/hum | `sensor.temp_hum.<slug>` | `sensor.temp_hum.sauna_high` |
| Energy | `sensor.energy.<slug>` | `sensor.energy.kwh_meter` |
| Fluid | `sensor.fluid.<slug>` | `sensor.fluid.cold` |
| Door | `sensor.door.<slug>` | `sensor.door.sauna` |
| Speaker | `media_player.<slug>` | `media_player.living` |
| Scene | `scene.<slug>` | |
| Unknown / tombstone | `unknown.<slug>` | |

**Confirm:** RFX = `switch.*`. Vents / SSR / safety use the dedicated `switch.vent|ssr|safety.*` prefixes (not plain `switch.<slug>`). Classification from name keywords / known idxs as implemented.

Z-Wave slug source: **`| name |` segment only**.

### Automations: `entity_id` only

* Full cutover; **zero dual support** for numeric device idxs in rules.
* Event-only triggers (`event: …`) unchanged.
* Unresolved `entity_id` at runtime: **log + skip — do not kill the engine**.
* **Do not split `config.yaml` yet.**

### Migration & cutover tooling

| Tool | Role | Fate |
|---|---|---|
| **Script A** (`helpers/`) | One-off: birth assist + rewrite `automations:` + Python idxs → resolve/`entity_id` | **Delete after successful migration** |
| **Cutover script** (`helpers/`) | One-off gate for migration day: run full verify, confirm ready for entity_id-only engine (exit non-zero on failure) | **Delete together with Script A** after success |
| **Admin Debug check** | Same verify logic, permanent **Admin → Debug commands** button | **Keep** |

**Remap-all:** not implemented.

### Prerequisite procedure (this step)

1. Backup configs + any `entity_registry.yaml`.
2. Deploy registry birth/load/save + id patterns + always-resolve helpers; engine may still be on idxs until cutover script passes.
3. Populate registry (boot / Script A birth-only).
4. Run **Script A** (rewrite YAML + code refs).
5. Run **Cutover script** (verify gate). Fix until green.
6. Ship entity_id-only engine/schema; smoke-test on Pi.
7. Delete Script A + Cutover script from `helpers/`.
8. **Delete `docs/todo/install_enhancements_260718.md`.**
9. Admin Debug “entity registry / automations check” remains available anytime.

---

## 📋 AFTER THIS STEP — Blocky implementation checklist

Do these only after the prerequisite is live, enhancements todo is deleted, and Admin check is green.

### Phase 0 — Blocky prep (decisions at start of Blocky work)

1. Define **automation device deny-list** (which `entity_id`s / prefixes must not appear in pickers: safety, SSR, system-only, hidden, etc.).
2. Confirm whether automations stay in `config.yaml` (surgical `ruamel`) or are extracted later — default remains **in `config.yaml`** until explicitly changed.
3. Inventory system events for the event dropdown dictionary.

### Phase 1 — Backend API (CRUD & hot-reload)

1. `GET/POST/PUT/DELETE /api/automations`.
2. `ruamel.yaml` surgical write of `automations:` only (preserve comments).
3. Persist **`entity_id`** on device triggers/conditions/actions (never raw idx).
4. Dispatch `CONFIG_RELOAD_REQUESTED`; clear `AutomationEngine` config cache.

### Phase 2 — Frontend data model

1. Alpine editor store: `name`, `scene`, `trigger[]`, `conditions[]`, `actions[]`.
2. Add-trigger / add-action binds **`entity_id`**; UI shows **`name`**.

### Phase 3 — Semantic dropdowns

1. Device pickers from **`device_metadata`** (respect deny-list).
2. Event pickers from friendly event dictionary.
3. Users never type `entity_id`.

### Phase 4 — UI blocks (DaisyUI)

1. WHEN (device / system event).
2. AND IF (time of day / device state).
3. THEN DO (device / scene / event; force; rich light/speaker payloads for `hue.light.*` / `media_player.*` as applicable).

### Phase 5 — Hardening

1. Run Admin Debug entity/automation check after Blocky writes.
2. Confirm unresolved ids still log+skip without taking down the engine.
3. Document operator workflow (create rule → save → hot-reload → verify).

---

## 🚦 Decisions locked (prerequisite)

1. `entity_registry.yaml`; freeze after birth; no remap-all.
2. Full cutover; zero dual support; Script A + Cutover script (delete after); Admin Debug check (keep).
3. Id patterns as table above (`hue.light` / `hue.group`; `switch` / `switch.vent|ssr|safety`; RFX = `switch`; sensors dotted).
4. Z-Wave slug from `| name |` only.
5. Orphans: `status: removed`.
6. Unresolved: log + skip; engine stays up.
7. Every device idx gets an `entity_id`; Python **always resolve**.
8. Remove `dashboard_map` in an **immediate follow-up PR** after cutover check is green (see `260803_migration.md` Phase 7).
9. Blocky later; deny-list decided at Blocky start.
10. Do not split `config.yaml` in this step.
11. Delete `install_enhancements_260718.md` when this step is OK.

## 🚦 Open for Blocky start (not blocking prerequisite)

1. Exact deny-list contents.
2. Whether to extract `automations:` out of `config.yaml` before/during Blocky.
