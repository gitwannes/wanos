# ⚡ WanOS: Visual Automation Editor (IFTTT) Architecture Guide

This document is the source of truth for (1) the **entity_id prerequisite** (done in code) and (2) the **Blocky** visual automation editor (next).

**Entity_id cutover:** **done and verified** — registry birth/freeze, automations + structured config on `entity_id`, engine schema entity_id-only, Admin Debug registry check. **Pi Admin Debug: GREEN** (live metadata included; 0 errors, 0 warnings). Blocky may start.  
**`dashboard_map` removal:** **done** — display names live only in `device_metadata` / `device_name()`.

---

## ✅ Prerequisite (done) — One Device Map + Stable `entity_id`

Blocky and automations must not store raw hardware idxs in rules. Humans see friendly **names**; saved rules use stable **`entity_id`s**; hardware still uses **idx**.

### Identity model (three layers)

| Layer | Example | Who sees / uses it |
|---|---|---|
| Display `name` | `buro licht` | UI dropdowns only — may be renamed |
| `entity_id` | `switch.buro_licht` / `hue.light.buro_spot` | Stored in automation rules — frozen after birth |
| Physical `idx` | `71001` | Z-Wave / RFX / GPIO / `devices[]` / event bus |

### Single map (DRY)

* **One registry:** `device_metadata[idx]` holds `name`, `type`, `origin`, and `entity_id`.
* **`dashboard_map` removed** — display names are `meta.name` / `device_name()` only.
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

### Persistence: `entity_registry.auto.yaml`

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
* Automatic domains live in **`automations.auto.yaml`** (`deviceexplorer_exclude`, `lighting`, `automations`).

### Migration & cutover tooling (complete)

| Tool | Role | Fate |
|---|---|---|
| **Script A** / **Cutover script** (`helpers/`) | One-off migrate + verify gate | **Deleted** |
| **Admin Debug check** | Permanent verify via `core/entity_registry_check.py` + **Admin → Debug** | **Keep** |

**Remap-all:** not implemented.

---

## ✅ Prerequisite gate — Pi Admin Debug GREEN

Confirmed from deployed Pi report (`ENTITY REGISTRY / CUTOVER CHECK`): **RESULT: GREEN**, no warnings. Live `device_metadata` included (`live_metadata_with_entity_id: 101`, `live_metadata_missing_entity_id: 0`). Local CLI check matches. **Prerequisite complete — start Blocky.**

---

## 📋 Blocky implementation checklist

**Current status:** Phase 1–2 **done**, MA migration **done on Pi**, Phase 3 **implemented** (pending Pi smoke), Phase 4 **code complete / not DoD-closed** — Blockly hybrid works (snap/uniqueness/non-reactive workspace); remaining Phase 4 gate is **operator round-trip + confidence checks on Pi**. Next: finish Phase 4 DoD, then Phase 5 hardening. Phase 6 = if/then/else + complex flat. Phase 7 = exclude/lighting UI.

### Phase 0 — Blocky prep (decisions at start of Blocky work)

1. Define **automation device deny-list** (which `entity_id`s / prefixes must not appear in pickers: safety, SSR, system-only, hidden, etc.).
2. Automations / lighting / excludes already live in **`automations.auto.yaml`** — Blocky writes target that file (`ruamel` surgical write of `automations:`).
   - **Comment (locked for current phase):** Write scope is **only `automations:`**. Keep `lighting:` and `deviceexplorer_exclude:` for **Phase 7**.
3. Inventory system events for the event dropdown dictionary.
4. **ON/OFF merge model** — locked below (schema + migration of existing sibling pairs).

### Phase 1 — Backend API (CRUD & hot-reload) ✅ DONE

1. `GET/POST/PUT/DELETE /api/automations`.
2. `ruamel.yaml` surgical write of `automations:` in **`automations.auto.yaml`** only (preserve comments).
3. Persist **`entity_id`** on device triggers/conditions/actions (never raw idx).
4. Support **first-class branched rules** (Y1 `on:`/`off:`) in schema; **X1:** expand at load to flat engine rules (pair identity preserved for CRUD).
5. Migrate existing sibling ON/OFF (and event ON/OFF) pairs per **M1**; leave `SYNC` and multi-ON cases (`living_special`) alone.
6. Dispatch `CONFIG_RELOAD_REQUESTED`; clear `AutomationEngine` config cache.
7. **Later:** promote expand path to **X2** native branch evaluate once Blocky CRUD is stable.

### Phase 2 — Frontend data model ✅ DONE

1. Alpine editor store: `name`, `scene`, trigger (device or event), optional **ON branch** / **OFF branch** (each: `conditions[]`, `actions[]`), or **SYNC** when applicable.
2. Add-trigger / add-action binds **`entity_id`**; UI shows **`name`**.
3. One-sided rules allowed (ON-only or OFF-only); missing branch simply does not match that edge.

### Phase 3 — Semantic dropdowns ✅ IMPLEMENTED (pending operator validation)

1. Device pickers from **`device_metadata`** (respect deny-list).
2. Event pickers from friendly event dictionary.
3. Users never type `entity_id`.

### Phase 4 — UI blocks (Blockly hybrid) ✅ CODE COMPLETE (DoD open — operator validation)

1. WHEN (device / system event) — one trigger; ON/OFF branches (or flat Then).
2. AND IF (time of day / device state) — **per branch**.
3. THEN DO (device / event actions) — **per branch** / flat Then.
4. Canonical template: **`switch.pc_monitors`** (operator confidence check still open).
5. Snapping / uniqueness / Alpine-safe workspace — fixed and verified on minimal harness + live Blocky.

### Phase 5 — Hardening 🟡 IN PROGRESS / TODO

1. Run Admin Debug entity/automation check after Blocky writes.
2. Confirm unresolved ids still log+skip without taking down the engine.
3. Document operator workflow (create rule → save → hot-reload → verify).

### Phase 6 — Blockly advanced flat patterns 🔜 TODO

**Goal:** reduce JSON-only flat rules and split-rule pairs; keep Y1 branched + flat compatibility (no ad-hoc schema).

**Scope note — unified if/then/else (Phase 6 goal):**
- **Yes — include branched rules in the same if/then/else model for unity.** Today’s ON-branch / OFF-branch containers are a temporary Blockly shape; Phase 6 should converge on one mental model for all rule kinds:
  - **Branched device / event-family:** trigger → **if ON** … **else if OFF** … (maps to stored Y1 `on:`/`off:`; engine stays X1/X2).
  - **Flat companions (Cinema OFF):** trigger event → **if dark** … **else if light** … (merge UX; persistence TBD).
  - **Complex flat:** multi-trigger OR, etc. → Blockly (no JSON-only dead-end).
- Until Phase 6 ships that unified canvas, keep the current ON/OFF branch blocks working (connection/snap fixes are Phase 4 hotfixes, not the final UX).

1. **Unified if/then/else canvas (HIGH PRIORITY):** one Blockly vocabulary for branched Y1 and flat companions; remove confusing dual list rows for Cinema-style pairs; keep dashboard = single scene button.
2. **Multi-trigger flat rules:** Blockly support for `trigger:` as a list (e.g. `KeukenLivingEetk_EetkHue` — three devices ON → one action). Start with **“when any of”** (OR) block; defer **“when all of”** (AND) if not needed in live rules.
3. **Single-trigger list normalization:** YAML `trigger: [{ entity_id, state }]` (one element) is already Blockly-compatible after normalize — ensure round-trip preserves list-vs-object shape if operator cares (or always emit object form on save).
4. **Remove “complex flat rule” JSON-only path:** audit live flat automations; extend Blockly (OR-trigger, if/else companions, any remaining shapes) so no production rule falls back to generic **“Complex flat rule — JSON only”**. Keep JSON editor only as explicit power-user override, not the default for unrecognized patterns.

**Examples to validate in Phase 6:**

| Rule | Current Blocky | Phase 6 target |
|------|----------------|----------------|
| `BuroCinemaPC_cosy` | Blockly (device trigger; was list-wrapped) | ✅ maintain round-trip |
| `KeukenLivingEetk_EetkHue` | JSON only (3 triggers) | Blockly OR-trigger |
| `--- CINEMA OFF` + `CINEMA OFF (Day)` | Two flat Blockly rules | Optional merged if/else canvas + operator merge procedure |
| Any rule still showing “Complex flat rule” | JSON fallback | Blockly or documented exception |

### Phase 7 — Config editors for `deviceexplorer_exclude` + `lighting` 🔜 TODO

**Today (no UI):** both live in **`automations.auto.yaml`** (top of file). Soft-hide in Blocky/Explorer = that list ∪ Z-Wave `hidden_nodes` (see D1). Auto-off = `lighting.managed_lights` + `default_auto_off_minutes` + `auto_off_delays`.

**Phase 7 goal:** admin UI (Blocky sibling page or Admin section) to view/edit:
1. **Device Explorer exclude** — which `entity_id`s are soft-hidden (with clear note that Z-Wave `hidden_nodes` still come from `config_zwave.auto.yaml`).
2. **Lighting auto-off** — managed lights list, default minutes, per-entity delay overrides.

**Constraints:** surgical `ruamel` writes of only those keys (same pattern as automations CRUD); never rewrite unrelated keys; Admin Debug still GREEN after edits.

---

## 🚦 Decisions locked (prerequisite)

1. `entity_registry.auto.yaml`; freeze after birth; no remap-all.
2. Full cutover; zero dual support; Script A + Cutover script (delete after); Admin Debug check (keep).
3. Id patterns as table above (`hue.light` / `hue.group`; `switch` / `switch.vent|ssr|safety`; RFX = `switch`; sensors dotted).
4. Z-Wave slug from `| name |` only.
5. Orphans: `status: removed`.
6. Unresolved: log + skip; engine stays up.
7. Every device idx gets an `entity_id`; Python **always resolve** via registry (`core/well_known_entities.py` + `resolve_entity_id`). Magic-idx scan cleared (allowlist: `90001` vent lock).
8. ~~Remove `dashboard_map`~~ — **done**.
9. Blocky next; deny-list decided at Blocky start.
10. Auto domains extracted to **`automations.auto.yaml`**; Z-Wave map is **`config_zwave.auto.yaml`**.
11. **Pi Admin Debug GREEN** — entity_id prerequisite closed.

## 🚦 Decisions locked (Blocky — ON/OFF merge)

1. **Persistence = first-class branched rule** (proposal B): one YAML rule with ON/OFF (or event-pair) branches — not two sibling flat rules kept forever. Blocky CRUD reads/writes the branched shape; runtime starts as **X1 expand-at-load**, then **X2 native** once CRUD is stable.
2. **Pair key = same trigger `entity_id`** (device) or same event family for event pairs. Auto-group / migrate by that key.
3. **Canonical example:** `switch.pc_monitors` — ON branch (schemer + Sonos rich) / OFF branch (both off).
4. **`SYNC` only when ON and OFF are the same** (pure mirror: same targets, flipped state, no asymmetric rich payload or conditions). Otherwise use explicit ON/OFF branches.
5. **Event pairs merge too** (e.g. cinema / twilight / sauna ON↔OFF) under the same branched model.
6. **One-sided OK:** ON-only (or OFF-only) rules allowed; the absent edge simply does not match (e.g. `BuroCinemaPC_cosy`).

## 🚦 Decisions locked (Blocky — Phase 0 open items)

1. **Deny-list = D1 (role-aware):**
   * **Hard deny** (never in trigger / condition / action pickers): `switch.safety.*`, `switch.ssr.*`, host/infra sensors (`sensor.generic.host_*`, `sensor.temp_hum.host_*`, `sensor.generic.wanos_db_size`), virtual/internal (`90001` vent lock).
   * **Soft hide** (picker default off; “Show hidden” / advanced): union of `deviceexplorer_exclude` ∪ zwave `hidden_nodes`, **except** any `entity_id` already referenced in automations (auto-unhide so bathroom physicals / `living_special` / `switch.pc` stay editable).
   * Everything else in live `device_metadata` (status ≠ removed) is allow.
2. **YAML branch keys = Y1:** trigger without edge state; top-level `on:` / `off:` each with optional `conditions` + `actions`. One-sided = omit the unused key. Event pairs use the same ON/OFF metaphor (mapped via curated event dictionary).
3. **Event dropdown = E1:** curated allow-list with friendly labels (not full `EventType`). Starter set = events already used in automations + intentional scene/schedule hooks; exclude toggles, telemetry, heartbeats, config/bus internals.
4. **Migration = M1 (conservative):** auto-merge only when exactly one ON + one OFF sibling share the same trigger `entity_id` (or mapped event-ON + event-OFF), and neither is `SYNC`. Do **not** auto-merge when multiple ON (or multiple OFF) rules share an eid — leave for operator / later Blocky UX. Known case today: `switch.living_special` (3 rules × OR ON|OFF, condition-discriminated).
5. **Engine = X1 first, then X2:** YAML stores Y1 `on:`/`off:`; loader **expands at load** to today’s flat ON/OFF rules for `AutomationEngine.evaluate` (preserve pair identity for CRUD round-trip). **Promote to native branch evaluate (X2)** once Blocky CRUD is stable — one in-memory rule, select branch from `new_state` / event; clearer logs; no shadow duplicates.
6. **CRUD identity = A:** persist stable per-rule `id` in YAML and use it for `PUT/DELETE`; never key mutations by `name` or list index.
7. **X1 pair round-trip = P1:** keep expansion metadata runtime-only (`<id>#on`, `<id>#off` or equivalent); never persist generated child rules back to YAML.
8. **Migration timing = MA:** run an explicit one-shot M1 migration step before enabling Blocky editing in production (review diff, then proceed).
9. **E1 dictionary scope = E1-v1:** start with approved schedule/scene/sauna trigger set used by automations; add new entries only by explicit review.
10. **Hard-deny extras = H1:** keep hard-deny minimal in v1 (safety/SSR/internal classes only); avoid broader hard-deny expansion until real operator pain appears.
11. **UI scope = new page, admin-only:** Blocky is a dedicated admin route/page, not mixed into end-user pages.
12. **UI strategy = Option 2 (Hybrid):** keep the current JSON/form editor as fallback + debugging path, and add Blockly visual mode incrementally. Do not remove the fallback editor until Blockly covers all live rule patterns and proves stable.

## ✅ Final spec lock checklist (no code)

Mark each item `LOCKED` before implementation starts.

### A) Already locked

- [x] **Scope:** Blocky writes only `automations:` (leave `lighting:` / `deviceexplorer_exclude:` for later phase).
- [x] **UI access:** new page, admin-only.
- [x] **Persistence model:** branched YAML (`on:` / `off:`), one-sided allowed.
- [x] **Pairing rule:** same trigger `entity_id` (device) or mapped event family.
- [x] **SYNC policy:** keep SYNC for pure mirrors; do not force split.
- [x] **Migration policy:** M1 conservative merge; skip `SYNC` and multi-ON/OFF cases (e.g. `living_special`).
- [x] **Engine rollout:** X1 expand-at-load first, then X2 native branch evaluate after CRUD is stable.
- [x] **CRUD identity model:** stable per-rule `id` (A), not `name` or list index.
- [x] **X1 round-trip:** runtime-only expansion metadata (P1), never persisted.
- [x] **Deny-list posture:** D1 + H1 (minimal hard-deny in v1).
- [x] **Events posture:** E1-v1 curated dictionary.

### B) Spec precision — locked / open

#### B1 Rule `id` — LOCKED

- [x] Format = **UUIDv4**.
- [x] Generation = **backend-only** (create + MA backfill); PUT cannot change `id`; rename does not change `id`.
- [x] Missing `id` on legacy YAML = **MA must backfill before Blocky enable**; refuse to enable editor if any rule still lacks `id` after MA.
- [x] Duplicate `id` = **do not invent a new id**. Surface as **WARNING** (see note below); engine stays up; Blocky/API must not treat duplicates as healthy.
  - **Comment:** Agree with WARNING for **load / runtime / Admin Debug** (aligns with WanOS “log + skip, engine stays up”). For **Blocky save (POST/PUT)**, still **reject** a write that would create/keep a duplicate `id` — WARNING alone must not allow persisting known-bad identity.

#### B2 E1-v1 event dictionary — LOCKED

- [x] Scope = **C**: curated allow-list covering schedule / scene / sauna / **IR** even if some keys are unused today (not “live YAML only”).
- [x] UI labels = **friendly** (not raw keys).
- [x] Event-pair families = **explicit map** (no `_ON`/`_OFF` suffix inference).
- [x] Concrete table + usage + pair families approved (below).

| Key | Label | Usage |
|---|---|---|
| `BLINDS_OPEN_TRIGGER` | Blinds open | trigger-only |
| `BLINDS_CLOSE_TRIGGER` | Blinds close | trigger-only |
| `TWILIGHT_EVENING_ON_TRIGGER` | Twilight evening ON | trigger-only |
| `TWILIGHT_EVENING_OFF_TRIGGER` | Twilight evening OFF | trigger-only |
| `TWILIGHT_MORNING_ON_TRIGGER` | Twilight morning ON | trigger-only |
| `TWILIGHT_MORNING_OFF_TRIGGER` | Twilight morning OFF | trigger-only |
| `SAUNA_ON` | Sauna ON | trigger-only |
| `SAUNA_OFF` | Sauna OFF | trigger-only |
| `IR_ON` | IR ON | trigger-only |
| `IR_OFF` | IR OFF | trigger-only |
| `SCENE_CINEMA_ON` | Cinema scene ON | trigger-only |
| `SCENE_CINEMA_OFF` | Cinema scene OFF | trigger-only |
| `SCENE_ALL_OFF` | All OFF scene | both |
| `SCENE_GOCOSY` | Go Cosy scene | both |
| `SCENE_GV_OFF` | Ground floor OFF | both |
| `SCENE_VERDIEP1_OFF` | Floor 1 OFF | both |
| `SCENE_VERDIEP2_OFF` | Floor 2 OFF | both |

**Pair families (explicit):**

| Family | ON / open | OFF / close |
|---|---|---|
| `blinds` | `BLINDS_OPEN_TRIGGER` | `BLINDS_CLOSE_TRIGGER` |
| `twilight_evening` | `TWILIGHT_EVENING_ON_TRIGGER` | `TWILIGHT_EVENING_OFF_TRIGGER` |
| `twilight_morning` | `TWILIGHT_MORNING_ON_TRIGGER` | `TWILIGHT_MORNING_OFF_TRIGGER` |
| `sauna` | `SAUNA_ON` | `SAUNA_OFF` |
| `ir` | `IR_ON` | `IR_OFF` |
| `cinema` | `SCENE_CINEMA_ON` | `SCENE_CINEMA_OFF` |

**Unpaired (do not auto-merge):** `SCENE_ALL_OFF`, `SCENE_GOCOSY`, `SCENE_GV_OFF`, `SCENE_VERDIEP1_OFF`, `SCENE_VERDIEP2_OFF`.

#### B3 X1 log/debug — LOCKED

- [x] Internal branch naming = **`<id>#on` / `<id>#off`** (runtime-only; never written to YAML).
- [x] Log format = **`rule=<id> branch=on|off name="<name>"`**.
- [x] Expansion order = **ON then OFF** (deterministic).
- [x] Missing branch = **A**: emit only the present branch (no empty stub). Absent edge simply does not match.

#### B4 MA operational runbook — LOCKED

**What “MA” means:** explicit one-shot operator-run M1 migration of `automations.auto.yaml` before enabling Blocky editing in production (not boot-auto, not first-save).

- [x] Who runs MA = **Johan on the Pi** (after Phase 1 Y1/X1 loader is deployed).
- [x] Dry-run = **mandatory** (`--dry-run` review, then separate `--write`).
- [x] Backup = **`automations.auto.yaml.bak.<UTC>`** next to the live file.
- [x] Rollback = restore `.bak.*` → reload → Admin Debug GREEN.
- [x] Timing vs code = **after** Phase 1 Y1/X1 loader can load branched YAML; **before** enabling Blocky UI in prod.

### C) MA migration — your steps (operator) ✅ COMPLETED ON PI

Run **once** on the Pi, **after** Phase 1 (Y1 loader) is deployed, **before** you enable the Blocky UI.

**Completion note:** migration helper was executed (`--dry-run` then `--write`), service restarted, Admin Debug check returned GREEN, and runtime logs confirmed branch ids (`<id>#on/#off`) and expected automation behavior.

1. Confirm WanOS on the Pi can load branched `on:` / `off:` rules (Phase 1 deployed).
2. Admin → Debug → entity-registry check → **GREEN**.
3. Copy `automations.auto.yaml` → `automations.auto.yaml.bak.<UTC>` (e.g. `20260805T090000Z`).
4. Run migration helper **`python3 helpers/migrate_automations_m1.py --dry-run`**. Read the plan. Stop if anything looks wrong.
5. Dry-run must show: merges for clean ON/OFF pairs (e.g. `pc_monitors`, bathrooms); **no** merge for `SYNC` or `living_special`.
6. Run migration helper **`python3 helpers/migrate_automations_m1.py --write`**.
7. Diff backup vs new file. `lighting:` and `deviceexplorer_exclude:` must be unchanged.
8. Admin → reload config (`CONFIG_RELOAD_REQUESTED`).
9. Admin → Debug → entity-registry check → **GREEN**.
10. Smoke test: `pc_monitors` ON/OFF; bathroom 1e/2e; spare button (`living_special`); one SYNC rule; one scene if easy.
11. Note date, backup filename, and result in your deployment log.
12. Enable / link Blocky admin page.

**If something fails after step 6:** copy `.bak.<UTC>` back over `automations.auto.yaml` → reload → registry GREEN → re-smoke → fix before retry.

### D) Implementation readiness gate

- [x] All items in section **B** are marked locked.
- [x] MA section **C** completed by operator (after Phase 1 deploy).
- [x] This file is frozen as the **spec baseline** for Blocky v1 (implementation may start; MA still gated on Phase 1).

## 🧭 Next TODO (Option 2 roadmap)

1. **Phase 4 closeout:** operator round-trip + confidence checks on Pi (DoD below).
2. **Phase 5:** finalize operator docs + regression matrix; keep X1 stable, then schedule X2 promotion when CRUD/editor usage is stable.
3. **Phase 6:** Unified if/then/else Blockly for branched Y1 + flat companions (Cinema OFF) + complex flat (multi-trigger OR); eliminate generic “complex flat rule” JSON-only path.
4. **Phase 7:** admin UI for `deviceexplorer_exclude` + `lighting` in `automations.auto.yaml`.

## ✅ Definition of Done (Option 2)

Use this as strict phase gates. Do not mark a phase complete unless all items are checked.

### Phase 3 DoD — Semantic pickers + policy enforcement

- [x] **Device picker policy:** D1 is enforced in UI and backend-facing payload shaping:
  - hard-deny eids never appear/selectable,
  - soft-hidden eids are hidden by default and visible only via explicit toggle,
  - eids already used by automations remain visible/editable.
- [x] **Event picker policy:** E1-v1 curated events are rendered with friendly labels (no raw key-only UX by default).
- [x] **Event family behavior:** explicit pair families are respected for branched event trigger UX (no suffix heuristics).
- [x] **No free-text dependency for normal flow:** standard rule authoring works end-to-end without typing raw `entity_id` or raw event keys (flat fallback mode remains available by design).
- [x] **Validation UX:** blocked selections show clear user feedback (why blocked + what to do).
- [x] **Compatibility:** existing rules load/edit/save without semantic drift.
- [ ] **Regression smoke (operator run on Pi):** create/edit/delete one branched device rule, one branched event-family rule, one flat SYNC rule.

### Phase 4 DoD — Blockly visual mode (hybrid)

- [x] **Second editor mode exists:** Blockly canvas mode is available alongside the current JSON/form editor.
- [x] **Fallback preserved:** JSON/form editor remains fully functional and selectable at all times.
- [ ] **Round-trip safety:** Blockly -> saved YAML -> reload -> reopened in Blockly preserves semantics for:
  - one-sided ON-only/OFF-only,
  - full ON+OFF branched rules,
  - event-family branched rules,
  - flat SYNC/multi-trigger rules (either editable or clearly marked fallback-only).
- [x] **Mode boundary clarity:** UI clearly indicates when a rule must be edited in fallback mode (if Blockly cannot represent it yet).
- [ ] **No schema mutation:** persisted shape remains aligned with locked Y1 + flat compatibility (no ad-hoc new schema).
- [ ] **Operator confidence checks:** test at least `pc_monitors`, one bathroom pair, one scene-triggered rule from Blockly mode.
- [x] **Drag/connect correctness:** conditions and actions snap into the branch slots and can be dragged out again; verified on `helpers/blockly_minimal_test.html` and live Blocky (Alpine-safe `BlockyRT` workspace).
- [x] **Uniqueness:** one trigger / one ON / one OFF / one Then; no duplicate condition/action fingerprints on the canvas (toolbox hides singletons).

#### Snapping / un-snapping — root cause and fix

Symptom: blocks rendered and chained to each other, but would not drop into the `conditions`
/ `actions` slot of a branch, and could not be pulled back out.

Root causes (fixed):
1. Inject / layout while hidden (`x-show` → `display:none`) or zero-size host → broken hit-testing.
2. Storing `WorkspaceSvg` on Alpine reactive state (Proxy) → drag/snap broken vs the plain-`ws` minimal test.
3. Tailwind `svg { max-width: 100% }` distorting Blockly SVG metrics.

Fix: non-reactive `BlockyRT` workspace, park panel off-screen instead of `display:none`, inject options matching the minimal test, `svgResize` + ResizeObserver, typed Condition/Action sockets.

Regression harness (keep): `helpers/blockly_minimal_test.html` (double-click or serve locally).

### Phase 6 DoD — Blockly advanced flat patterns

- [ ] **Split-rule if/else:** `SCENE_CINEMA_OFF` dark + light companions editable as one Blockly flow (or documented one-click merge to single persisted rule).
- [ ] **Multi-trigger flat:** at least one live OR-trigger rule (e.g. `KeukenLivingEetk_EetkHue`) editable in Blockly without JSON.
- [ ] **List trigger round-trip:** `BuroCinemaPC_cosy` saves/reloads in Blockly without semantic drift.
- [ ] **Scene vs flat clarity:** UI/docs explain why companion rules omit `scene:` (not shown on dashboard) vs primary scene button rule.
- [ ] **No generic complex-flat fallback:** production flat rules open in Blockly; JSON-only is opt-in, not “Complex flat rule — JSON only” for live automations.

### Phase 5 DoD — Hardening + rollout readiness

- [ ] **Docs complete:** operator workflow and troubleshooting steps updated in `install_blocky.md` and reference docs.
- [ ] **Regression matrix complete:** pass/fail table for critical automation patterns (branched, one-sided, SYNC, event-family, scene).
- [ ] **Runtime stability:** no startup/reload validation failures on migrated YAML in repeated restarts.
- [ ] **Observability clarity:** branch-aware logs (`<id>#on/#off`, branch labels) are readable and verified in real traces.
- [ ] **Policy verification:** Admin Debug check remains GREEN after representative create/update/delete operations.
- [ ] **Rollback rehearsal:** backup/restore + reload procedure tested once and documented with timings/outcome.
- [ ] **X2 readiness review:** explicit checkpoint recorded (stay on X1 vs schedule X2 promotion), with decision rationale.


### SYNC — keep or split to ON/OFF?

**Keep `SYNC` as a first-class mode** when ON and OFF are pure mirrors (same targets, flipped/mirrored state, no asymmetric rich payload or conditions). That matches your locked rule and industry practice:

* HA: one automation, trigger on any state change, action sets target to `trigger.to_state` (mirror) — not two duplicated halves.
* openHAB / many hubs: “follow” / mirror profiles for 1:1 coupling.
* Splitting pure mirrors into identical `on:`/`off:` trees invites drift (edit ON, forget OFF).

**Do not use SYNC** when branches differ (e.g. `switch.pc_monitors` → Sonos volume/station on ON only) — use Y1 `on:`/`off:`.

Current pure-SYNC rules (leave as SYNC under M1): `Slpk_Dries`, `PC ON/OFF -> PC Aux`, `toilet_gv_ventilatie_on`, `Slpk Wannes: Hue App Syncs to Switch`.
