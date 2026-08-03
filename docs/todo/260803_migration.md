# WanOS entity_id cutover — 2026-08-03

Operator checklist for the **prerequisite** step (stable `entity_id`, full cutover).  
Architecture source of truth: `docs/todo/install_blocky.md` (CURRENT STEP).  
When this cutover is verified OK → **delete** `docs/todo/install_enhancements_260718.md`.

Blocky UI work starts only **after** this document’s “Done” criteria are met.

---

## Goals

* One device map: `device_metadata` + `entity_id` (no parallel registry dict).
* Persist ids in system-owned **`entity_registry.yaml`** (not in commented `config.yaml`).
* Automations and Python use **`entity_id` only** (zero dual support for device idxs).
* Hardware / `devices[]` / event bus still use **idx**.
* Birth once from name → **freeze**; no remap-all.
* Unresolved id → log + skip; **do not** kill the engine.

---

## Locked id patterns (quick reference)

| Kind | Pattern | Example |
|---|---|---|
| Hue light | `hue.light.<slug>` | `hue.light.buro_spot` |
| Hue group | `hue.group.<slug>` | `hue.group.living` |
| Z-Wave / RFX actuator | `switch.<slug>` | `switch.buro_licht` |
| Vent | `switch.vent.<slug>` | `switch.vent.badk_1e` |
| SSR | `switch.ssr.<slug>` | `switch.ssr.sauna` |
| Safety | `switch.safety.<slug>` | `switch.safety.wisc` |
| Blinds | `blinds.<slug>` | `blinds.cinema` |
| Power / temp_hum / energy / fluid / door | `sensor.<kind>.<slug>` | `sensor.power.pc`, `sensor.fluid.cold`, `sensor.door.sauna` |
| Speaker | `media_player.<slug>` | |
| Scene / unknown | `scene.<slug>` / `unknown.<slug>` | |

* Z-Wave slug from `| name |` segment only.  
* RFX → `switch.*`.  
* Python → **always resolve** via registry.  
* Orphans → keep row, `status: removed`.

---

## Artifacts involved

| Artifact | Role | After success |
|---|---|---|
| `entity_registry.yaml` | Runtime registry | **Keep** |
| Script A (`helpers/…`) | One-off migrate / rewrite | **Delete** |
| Cutover script (`helpers/…`) | One-off verify gate (migration day) | **Delete** (with A) |
| Admin → Debug “entity/automation check” | Same verify logic, permanent | **Keep** |
| `docs/todo/install_enhancements_260718.md` | Old sketch | **Delete** when cutover OK |
| `docs/todo/install_blocky.md` | Architecture + Blocky-after steps | **Keep** |
| `dashboard_map` removal | Cleanup | **Immediate follow-up PR** after green check (not required to finish this cutover day) |

---

## Pre-flight

1. [ ] Read `docs/todo/install_blocky.md` (CURRENT STEP) once more.
2. [ ] Schedule a window where automations can be briefly wrong if something fails.
3. [ ] Backup on the Pi (and/or workstation copy):
   * `config.yaml`
   * `config_zwave.yaml`
   * `config_hardware.yaml`
   * `config_hue.yaml` (if present)
   * any existing `entity_registry.yaml`
4. [ ] Confirm git branch / deploy path for the registry + always-resolve code (engine may still accept idxs until cutover script is green and entity_id-only build is deployed).

---

## Phase 1 — Deploy birth + registry (still safe to roll back)

1. [ ] Deploy code that:
   * loads/saves `entity_registry.yaml` (`core/entity_registry.py`)
   * births `entity_id` with the patterns above
   * merges into `device_metadata`
   * provides **always-resolve** helpers (`StateManager.resolve_entity_id` / `ensure_entity_id`)
2. [ ] Boot WanOS once (or run Script A birth-only mode).
3. [ ] Confirm `entity_registry.yaml` exists and has a row per known device idx.
4. [ ] Spot-check: Hue → `hue.light.*` / `hue.group.*`; RFX → `switch.*`; a vent → `switch.vent.*`; SSR/safety → matching prefixes.

**Phase 1 code status:** registry module + `StateManager` / Z-Wave wiring landed. Automations still use numeric idxs until Phase 2–4.

---

## Phase 2 — Script A (rewrite)

1. [x] Run **Script A** (dry-run first if available; then apply).
   * Script: `helpers/migrate_entity_ids_script_a.py`
   * Applied against `entity_registry.yaml` (copied from operator export; door/fluid/`72006` ids corrected).
   * Backup: `config.yaml.pre_entity_migrate_*` / `config_zwave.yaml.pre_entity_migrate_*`
2. [x] Confirm `config.yaml` `automations:` device refs are `entity_id: …` (no numeric device `idx:` left). Pure `event:` triggers unchanged. (weather `idx` outside automations intentionally left.)
3. [x] Also migrated to `entity_id` keys/lists (consumers resolve → idx at runtime):
   * `deviceexplorer_exclude`
   * `hardware_links.power_meters`
   * `blinds.travel_times`
   * `lighting.managed_lights` / `auto_off_delays`
   * `history.tracked_idxs` → `tracked_entities`
   * `config_zwave.yaml` `hidden_nodes` (+ zwaveconfig UI writes entity_ids)
4. [x] Python bathroom vent / humidity / hot-water / Epson paths resolve via `entity_id` (legacy idx fallback remains in engine until Phase 4 cutover removes it).
5. [x] Confirm `docs/todo/install_enhancements_260718.md` deleted (superseded by this doc + `install_blocky.md`).
6. [x] Dropped local `*.pre_entity_migrate_*` config backups (Pi green; live configs are source of truth).

**Phase 2 code status:** Script A applied (automations + structured config blocks); consumers resolve `entity_id` → idx; always-resolve helpers in use for known fixtures.

---

## Phase 3 — Cutover script (gate)

1. [x] **Cutover script:** `helpers/cutover_entity_ids_verify.py` (shared core: `core/entity_registry_check.py`). Exit non-zero on errors.
2. [x] Checks:
   * [x] Registry rows have entity_ids; collision detection
   * [x] Automation device refs are entity_ids that resolve (not `status: removed`)
   * [x] No leftover numeric device `idx:` under automations
   * [x] Structured config blocks (`deviceexplorer_exclude`, `hardware_links`, `blinds.travel_times`, `lighting`, `history.tracked_entities`, `zwave.hidden_nodes`) are entity_ids that resolve
   * [x] Python magic idxs reported as **warnings** (non-blocking follow-up; system/sauna/simulator)
   * [x] Live `device_metadata` coverage when run via Admin API
3. [x] Run on the Pi after deploy: `python3 helpers/cutover_entity_ids_verify.py` — GREEN (warnings = Python magic idxs, non-blocking).

**Phase 3 code status:** CLI gate + shared checker landed. Admin Debug button uses the same core (Phase 5).

---

## Phase 4 — Entity_id-only engine

1. [ ] Deploy / enable **zero dual support** (schema + `AutomationEngine` resolve by `entity_id` only).
2. [ ] Restart WanOS; confirm service healthy.
3. [ ] Smoke-test critical automations (blinds twilight, a light/switch rule, a vent rule if any, Hue if used in rules).
4. [ ] Confirm an intentionally bad `entity_id` (if tested) logs and skips without crashing the process.

---

## Phase 5 — Admin Debug button

1. [x] **Admin → Debug → Entity Registry Check** → `GET /api/debug/entity-registry-check` (same `run_entity_cutover_checks`, plus live metadata).
2. [ ] Run it once from the UI after deploy; expect green toast + **modal** with the full CLI-style report.

---

## Phase 6 — Delete temporary migration tooling & old todo

1. [ ] Delete **Script A** from `helpers/` (after Phase 4).
2. [ ] Delete the **Cutover script** from `helpers/` (after Phase 4; Admin Debug check stays).
3. [x] Delete **`docs/todo/install_enhancements_260718.md`**.
4. [ ] Commit/deploy those deletions (Admin Debug check remains).

---

## Phase 7 — Immediate follow-up PR (after green check)

Separate PR, right after this cutover is green:

1. [ ] Remove `dashboard_map` from models, state_manager, integrations, handlers, frontend, SSE domain list.
2. [ ] All name lookups via `device_metadata[idx]["name"]` (or helper).
3. [ ] Run Admin Debug check again; smoke UI labels.

---

## Done criteria (this cutover)

* [ ] `entity_registry.yaml` populated and stable across reboot  
* [ ] Automations entity_id-only; cutover script was green before engine cutover  
* [ ] Python always-resolve in use  
* [ ] Admin Debug check green  
* [ ] Script A + Cutover script deleted  
* [x] `install_enhancements_260718.md` deleted  
* [ ] Follow-up PR for `dashboard_map` opened/queued  

Then proceed to **AFTER THIS STEP** in `docs/todo/install_blocky.md` (Blocky).

---

## Do not do in this cutover

* Remap-all / regenerate all entity_ids from current names  
* Split `config.yaml` / extract automations file  
* Blocky UI / deny-list implementation (deny-list decided at Blocky start)  
* Mixing entity ids into hand-edited comments as the source of truth  
