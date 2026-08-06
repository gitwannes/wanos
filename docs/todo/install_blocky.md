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

**Current status:** Phase 0–5 **✅ DONE**. Phase **6A ✅ DONE**. Phase **6B ✅ DONE** (incl. SYNC→ON/OFF on Pi). Contextual Blockly pickers (type-aware states, case match by trigger, OR-edges toolbox) shipped as a **6B follow-on**. Next: **6C** (rich action UX). Phase 7 = soft-hide UI; Phase 8 = lighting UI; Phase **9** = full Blockly↔JSON parity (JSON no longer required for any authorable rule).

**Follow-up (pickers):** sensors / temp / power / energy / fluid are **excluded** from the browsing catalog. **Motion** is allowed as **When device** trigger only (garage/toilet); never as action. Soft-hidden / out-of-catalog eids that appear on the **open rule** are always listed for that picker role so Blockly does not fall back to the first device (e.g. `53?`). Actions = actuators only. Broader sensor / threshold authoring is **Phase 9** (after 6C rich actions).

### Phase 0 — Blocky prep (decisions at start of Blocky work) ✅ DONE

1. Define **automation device deny-list** (which `entity_id`s / prefixes must not appear in pickers: safety, SSR, system-only, hidden, etc.).
2. Automations / lighting / excludes already live in **`automations.auto.yaml`** — Blocky writes target that file (`ruamel` surgical write of `automations:`).
   - **Comment (locked for current phase):** Write scope is **only `automations:`**. Keep soft-hide (`deviceexplorer_exclude` / Z-Wave `hidden_nodes`) for **Phase 7**; keep `lighting:` for **Phase 8**.
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

### Phase 3 — Semantic dropdowns ✅ DONE

1. Device pickers from **`device_metadata`** (respect deny-list).
2. Event pickers from friendly event dictionary.
3. Users never type `entity_id`.
4. **Follow-up:** sensors / temp / power / energy / fluid omitted from pickers; motion = trigger-only; actions = actuators only — see status note above.

### Phase 4 — UI blocks (Blockly hybrid) ✅ DONE

1. WHEN (device / system event) — one trigger; ON/OFF branches (or flat Then).
2. AND IF (time of day / device state) — **per branch**.
3. THEN DO (device / event actions) — **per branch** / flat Then.
4. Canonical template: **`switch.pc_monitors`** (operator confidence check **OK**).
5. Snapping / uniqueness / Alpine-safe workspace — fixed and verified on minimal harness + live Blocky.

### Phase 5 — Hardening ✅ DONE

1. [x] Run Admin Debug entity/automation check after Blocky writes (auto after Save/Delete; banner shows GREEN/RED).
2. [x] Confirm unresolved ids still log+skip without taking down the engine (`resolve_device_ref` WARNING).
3. [x] Document operator workflow (create rule → save → hot-reload → verify) — see **E) Phase 5 operator runbook** below.

### Phase 6A — Unified schema v2 + migrator ✅ DONE

**Goal (locked — option B, storage cutover):**
- **One persisted schema for every automation** — not dual Y1 branched + flat forever. Y1 `on:`/`off:` and flat `conditions`/`actions` become **legacy migrator/API input** only.
- Engine expands v2 cases → flat evaluate (X1-style interim). **YAML on disk is v2 only** after migrator `--write`.

**Implemented:**
- `core/automations_schema_v2.py` — convert / expand / Cinema merge / canonical `name`…`id` last
- Loader dual-read via `expand_automations_for_engine`
- API POST/PUT persist **v2 only**; GET returns raw v2 (Phase 6B)
- `helpers/migrate_automations_v2.py` — `--dry-run` / `--write` (+ backup)
- Rich action fields preserved on canvas apply / API dump

**Operator on Pi (completed 2026-08-05):**
1. Deploy code; `python3 helpers/migrate_automations_v2.py --dry-run`
2. Review plan (Cinema OFF merge)
3. `--write` → Admin Debug GREEN + clean boot
4. Smoke: Cinema OFF dark/light cases, OR triggers, ex-mirror rules (now ON/OFF cases)

**Unified schema (v2) — conceptual shape:**
- `name`, `scene`, `require_confirmation`, …
- `trigger` — wake-up only: one device, one event/family, or **OR-list** (edge discrimination lives in `cases` when using cases).
- `cases` — ordered if / else-if / else: matchers (`to_state`, and/or `conditions`) + `actions`.
- Action payloads may include rich keys (`preset`, `bri`, `xy`, `volume`, `station`, numeric blinds `state`) — **preserved**; authoring UX is Phase **6C**.
- `id` — last key in YAML.

**Legacy → v2 map (migrator):**

| Legacy | v2 |
|--------|-----|
| Y1 branched device | `trigger: { entity_id }` + case `to_state: ON` / `OFF` (one-sided = one case) |
| Y1 event-family | `trigger: { event: family }` + cases per ON/OFF edge |
| Flat `state: ON` (+ conditions) | `trigger: { entity_id }` + one case `to_state: ON` (+ conditions) |
| Cinema OFF dark + light (two rules) | **Merge** → one rule, two time cases |
| Multi-trigger OR | `trigger: [ … ]` (OR) + usually one case |
| SYNC / SYNCOPPOSITE | **Retired** → `trigger: { entity_id }` + cases `to_state: ON` / `OFF` (explicit action states); see SYNC cutover below |

### Phase 6B — One Blockly canvas + list unity ✅ DONE

**Depends on:** 6A (v2 on disk + API).

**Goal:**
- **One Blockly experience** — `When (trigger) → if / else-if / else → actions`; no branched-vs-flat editor modes.
- **One list entry per logical automation** — Cinema OFF appears once; one flow. Dashboard `scene:` button behavior unchanged where applicable.
- Eliminate “Complex flat rule — JSON only” as the default for live rules (JSON = power-user override only).

**Implemented:**
1. Blockly read/write **v2 only**; retired branched/flat dual modes; schedule-window UX; one device root + cases; dashboard toggles only for event triggers.
2. API GET/POST/PUT return **raw v2**.
3. Cinema OFF (merged) + multi-trigger OR on one canvas; rich keys pass through pending 6C.
4. SYNC/SYNCOPPOSITE retired → ON/OFF cases (see cutover below).

**Operator smoke:** ✅ OK on Pi (2026-08-05) — Cinema, OR, ex-Y1/ex-mirror, schedule windows.

### SYNC cutover — migrate mirrors to ON/OFF cases ✅ DONE ON PI

**Goal:** delete trigger/action `SYNC` and `SYNCOPPOSITE`; pure mirrors = **one rule**, two cases (`to_state: ON` / `OFF`).

**Code + YAML + Pi (completed 2026-08-05):**
- `_migrate_sync_to_cases` + engine retirement + Blocky without SYNC dropdowns
- Four mirrors rewritten; deployed YAML; Admin Debug GREEN; smoke OK
  (`Slpk_Dries`, `PC ON/OFF -> PC Aux`, `toilet_gv_ventilatie_on`, `Slpk Wannes: Hue App Syncs to Switch`)

**Rollback (emergency):** restore pre-cutover `automations.auto.yaml` **and** a build that still understood SYNC (current engine will not run leftover SYNC actions).

### Phase 6C — Rich device action UX 🔜 TODO

**Depends on:** 6B (one canvas) strongly preferred; can start after 6A if form/JSON still used, but ship Blockly UX against the unified canvas.

**Goal:** author rich actions in Blocky without hand-YAML. Engine already supports these payloads; 6C is **editor UX + pickers** only.

1. **Hue presets** — e.g. `preset: "relax_red"` (and related bri/xy if needed) via dropdown from known presets; round-trip with device ON/scene actions.
2. **Blinds position** — operator-facing **open %** (e.g. “open 10%” = 90% closed); map to stored 0–100 `state` per existing engine convention; document the mapping in-phase. (Interim: action dropdown already limits blinds to `0` / `100`.)
3. **Sonos** — `volume` and `station` fields (station keys from config dictionary); enough to edit live rules like `pc_monitors` ON branch without JSON.

**Out of scope for 6C:** new engine semantics, Phase 7 soft-hide UI, Phase 8 lighting config UI, full JSON↔Blockly parity (Phase **9** — 6C is the rich-action slice of that gap).

### Phase 7 — Unified soft-hide (“hidden from Explorer / pickers”) 🔜 TODO

**Today (no UI):** soft-hide is already one runtime concept (D1) — `deviceexplorer_exclude` ∪ Z-Wave `hidden_nodes` → `hidden_explorer_idxs` / `meta.hidden` — but operators still face two YAML homes (`automations.auto.yaml` vs `config_zwave.auto.yaml`).

**Phase 7 goal:** one operator-facing soft-hide model and admin UI (Blocky sibling page or Admin section):
1. **One mental model** — “hide this `entity_id` from Explorer / Blocky pickers” is one action (D1 soft-hide). Blocky respects soft-hide unless the **Hidden** toggle is on (currently selected eids stay sticky until cleared).
2. **One edit surface** — view/edit the full soft-hide set as a single list (or clear union), not an exclude editor plus a footnote about Z-Wave.
3. **Storage** — either collapse `hidden_nodes` into `deviceexplorer_exclude` (Z-Wave UI writes the same key), or keep dual files with the UI as the single writer of the union; runtime already treats them as one list.

**Constraints:** surgical `ruamel` writes of only soft-hide keys (same pattern as automations CRUD); never rewrite unrelated keys; Z-Wave map / other `config_zwave.auto.yaml` fields stay intact if dual storage remains; Admin Debug still GREEN after edits.

### Phase 8 — Config editor for `lighting` auto-off 🔜 TODO

**Today (no UI):** `lighting:` lives in **`automations.auto.yaml`** (top of file). Auto-off = `lighting.managed_lights` + `default_auto_off_minutes` + `auto_off_delays`.

**Phase 8 goal:** admin UI (Blocky sibling page or Admin section) to view/edit lighting auto-off — managed lights list, default minutes, per-entity delay overrides.

**Constraints:** surgical `ruamel` write of only `lighting:` (same pattern as automations CRUD); never rewrite unrelated keys; Admin Debug still GREEN after edits.

### Phase 9 — Full Blockly ↔ JSON parity 🔜 TODO

**Depends on:** Phase **6C** (rich action UX) must land first — that closes the largest live gap (`preset` / blinds open-% / Sonos `volume`+`station`). Phases **7** / **8** are orthogonal config UIs and may run in parallel; they are not prerequisites for 9.

**Goal:** every automation that is valid to **author and save** as schema v2 can be created and edited entirely on the Blockly canvas. JSON mode remains only as a **debug / inspect** escape hatch (or is removed once parity is proven) — never required for operator workflow.

**Today (gap inventory — JSON can, Blockly cannot or is unsafe):**

| Gap | JSON | Blockly now | Phase 9 target |
|-----|------|-------------|----------------|
| Hue `preset`, Sonos `volume`/`station`, raw `bri`/`xy` | author | round-trip only (no fields) | **done in 6C**; 9 verifies no leftover rich-only JSON paths |
| Blinds mid-position | author | 0/100 only (may coerce) | **done in 6C**; 9 verifies no coerce/loss |
| Rich fields keyed by `entity_id` only | per-action | collision if same device twice with different rich | **per-action** rich on each action block |
| Sensors / temp / power / energy / fluid as When / if | typeable | excluded from catalog | role-aware pickers + engine-legal ops only |
| Numeric / threshold conditions (e.g. “> 80”) | not really (engine = equality today) | none | **engine + blocks** if we want true thresholds; else document “equality only” and expose sensor state equality in Blockly |
| `FORCE_ON` / `FORCE_OFF` beyond switches | freeform | switches only | expose wherever engine already honors them |
| Events outside curated E1 list | freeform | curated (+ sticky if already on rule) | either expand E1 with review UX, or allow “custom event” block that still validates on save |
| Any other v2 field Blockly cannot emit | freeform | lost / stripped on canvas apply | inventory + block or explicit reject with message |

**In scope:**

1. **Parity audit** — every live rule in `automations.auto.yaml` opens, edits, and saves in Blockly with **zero semantic drift** (including rich, OR, multi-case, soft-hidden sticky, schedule families). Any rule that still needs JSON is a Phase 9 bug or an explicit hard-deny exception.
2. **Finish / harden 6C leftovers** — confirm rich authoring is complete; fix per-action rich storage (no `entity_id`-only map); no silent coerce of blinds mid-values or rich keys on load/save.
3. **Sensor-class devices in pickers (role-aware)** — allow sensors / temp / power / energy / fluid where the engine can evaluate them (trigger and/or condition). Motion policy stays: trigger OK, never action. Actions remain actuators (+ event fire).
4. **Threshold / compare conditions (optional engine slice)** — if operators need “above/below” (not only `device_state` equality), add engine support **and** Blockly blocks together; do not leave compare-only in JSON.
5. **Action/condition completeness** — every engine-supported action key and condition type has a Blockly control; unknown keys on load surface a clear warning instead of silent drop.
6. **Event dictionary completeness** — curated list covers all events used in production; path to add a new event without hand-JSON (admin list edit or reviewed “custom event” field).
7. **JSON demotion** — after DoD: Blockly is default and sufficient; JSON labeled debug-only (or removed). Doc + UI copy updated.

**Intentional permanent exceptions (not Phase 9 “gaps”):**

- **Hard deny** (`switch.safety.*`, `switch.ssr.*`, host/infra sensors, etc.) — never selectable in Blockly; save still rejects. JSON must not become a bypass (keep the same validation).
- **Non-automation config** (`deviceexplorer_exclude`, `lighting:`) — Phases 7 / 8, not Blockly rule canvas.

**Out of scope for 9:** redesign of schema v2 shape; Phase 7/8 storage UIs; kiosk/dashboard UX beyond existing `scene` / `require_confirmation` toggles.

**Constraints:** Admin Debug GREEN after representative CRUD; no silent field loss on Blockly apply; hard-deny enforcement unchanged; prefer extending blocks over teaching operators JSON.

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

> **Phase 6A–6C supersession:** items below lock the **pre-v2** baseline (Y1 + X1) used through Phase 5. **Phase 6A** replaces dual Y1/flat **storage** with unified schema v2 (`trigger` + `cases`); **6B** unifies Blockly/list UX; **6C** adds rich action authoring. Until 6A migrates the file, these locks still describe production YAML.

1. **Persistence = first-class branched rule** (proposal B): one YAML rule with ON/OFF (or event-pair) branches — not two sibling flat rules kept forever. Blocky CRUD reads/writes the branched shape; runtime starts as **X1 expand-at-load**, then **X2 native** once CRUD is stable.
2. **Pair key = same trigger `entity_id`** (device) or same event family for event pairs. Auto-group / migrate by that key.
3. **Canonical example:** `switch.pc_monitors` — ON branch (schemer + Sonos rich) / OFF branch (both off).
4. **`SYNC` only when ON and OFF are the same** (pure mirror: same targets, flipped state, no asymmetric rich payload or conditions). Otherwise use explicit ON/OFF branches.
5. **Event pairs merge too** (e.g. cinema / twilight / sauna ON↔OFF) under the same branched model.
6. **One-sided OK:** ON-only (or OFF-only) rules allowed; the absent edge simply does not match (e.g. `BuroCinemaPC_cosy`).

## 🚦 Decisions locked (Blocky — Phase 0 open items)

1. **Deny-list = D1 (role-aware):**
   * **Hard deny** (never in trigger / condition / action pickers): `switch.safety.*`, `switch.ssr.*`, host/infra sensors (`sensor.generic.host_*`, `sensor.temp_hum.host_*`, `sensor.generic.wanos_db_size`), virtual/internal (`90001` vent lock).
   * **Soft hide** (picker default off; “Show Explorer-hidden devices”): union of `deviceexplorer_exclude` ∪ zwave `hidden_nodes`. Soft-hidden devices stay out of pickers unless the checkbox is on. **Exception:** eids already used in the **open rule** (same picker role) remain listed so that rule can still round-trip / edit.
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
12. **UI strategy = Option 2 (Hybrid):** keep the current JSON/form editor as fallback + debugging path, and add Blockly visual mode incrementally. Do not remove the fallback editor until Blockly covers all live rule patterns and proves stable — that exit gate is **Phase 9** (after **6C** rich actions).

## ✅ Final spec lock checklist (no code)

Mark each item `LOCKED` before implementation starts.

### A) Already locked

- [x] **Scope:** Blocky writes only `automations:` (leave soft-hide for **Phase 7**, `lighting:` for **Phase 8**).
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
| `MORNING_ON_TRIGGER` | Morning on (clock) | trigger-only |
| `SUNRISE_TRIGGER` | Sunrise (end morning twilight) | trigger-only |
| `SUNSET_TRIGGER` | Sunset (start evening twilight) | trigger-only |
| `EVENING_OFF_TRIGGER` | Evening off (clock) | trigger-only |
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

**Schedule window edges (`SCHEDULE_WINDOW_EDGES` in `core/schedule_events.py`):**

| Family | Enter edge | Exit edge |
|---|---|---|
| `blinds` | `BLINDS_OPEN_TRIGGER` | `BLINDS_CLOSE_TRIGGER` |
| `twilight_morning` | `MORNING_ON_TRIGGER` | `SUNRISE_TRIGGER` |
| `twilight_evening` | `SUNSET_TRIGGER` | `EVENING_OFF_TRIGGER` |
| `sauna` | `SAUNA_ON` | `SAUNA_OFF` |
| `ir` | `IR_ON` | `IR_OFF` |
| `cinema` | `SCENE_CINEMA_ON` | `SCENE_CINEMA_OFF` |

**Sunrise/sunset ≠ blinds:** `SUNRISE_TRIGGER` / `SUNSET_TRIGGER` are twilight-window edges at raw astronomical sunrise/sunset. `BLINDS_OPEN_TRIGGER` / `BLINDS_CLOSE_TRIGGER` use **clamped** times (`max(sunrise|sunset, earliest)` ± optional latest). Do not wire them interchangeably.

**Legacy aliases (still accepted on load / match / timers / API):**  
`TWILIGHT_MORNING_ON_TRIGGER` → `MORNING_ON_TRIGGER`, `TWILIGHT_MORNING_OFF_TRIGGER` → `SUNRISE_TRIGGER`, `TWILIGHT_EVENING_ON_TRIGGER` → `SUNSET_TRIGGER`, `TWILIGHT_EVENING_OFF_TRIGGER` → `EVENING_OFF_TRIGGER`.  
Deprecated map name: `EVENT_FAMILY_TO_ON_OFF` (= `SCHEDULE_WINDOW_EDGES`).

**Unpaired (do not auto-merge):** `SCENE_ALL_OFF`, `SCENE_GOCOSY`, `SCENE_GV_OFF`, `SCENE_VERDIEP1_OFF`, `SCENE_VERDIEP2_OFF`.

#### B3 X1 log/debug — LOCKED

- [x] Internal branch naming = **`<id>#on` / `<id>#off`** (runtime-only; never written to YAML).
- [x] Log format = **`rule=<id> branch=on|off|- name="<name>"`** (implemented in `AutomationEngine.format_rule_ref`; flat rules use `branch=-`).
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

### E) Phase 5 operator runbook

#### E1 — Create → save → verify (hot-reload is automatic)

1. Open **Blocky** (admin JWT). Prefer Blockly mode for supported shapes; JSON/form remains available.
2. **New** or select a rule → edit → **Save**.
3. Backend **POST/PUT/DELETE `/api/automations`** writes YAML surgically and dispatches **`CONFIG_RELOAD_REQUESTED`** automatically — **no manual Admin “reload config”** and no hand-edit of `automations.auto.yaml` for normal ops.
4. Blocky banner: save/delete confirmation + **Admin Debug** result (`GREEN` / `RED`). On RED → Admin → Debug for the full report; do not leave production RED.
5. **Verify behavior:** toggle the trigger device / fire the scene/event; confirm expected ON/OFF (or SYNC) actions.
6. **Verify logs** (automation logger): look for
   `rule=<parent-id> branch=on|off|- name="<base name>"`
   on `[X-RAY]` / `[ACTION]` lines. Branched rules never log the raw `#on`/`#off` id as the primary `rule=` field.

#### E2 — Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Save rejected | Duplicate `id`, validation, auth | Read API `error`; fix payload; re-save |
| Admin Debug RED after save | Bad `entity_id` ref / registry drift | Admin → Debug; fix eid or restore backup |
| Rule saved but nothing fires | Unresolved eid (logged+skipped), wrong branch, conditions | Grep `[AUTOMATION] Unresolved` / `[X-RAY]`; fix eid or conditions |
| YAML bool / state weirdness | Unquoted `ON`/`OFF` in old hand-edits | Prefer Blocky save (quotes); engine coerces bool→string on load |
| Blockly won't snap | Stale cache / old JS | Hard-refresh (`blocky.js?v=…`); confirm panel not `display:none` |
| Sync Local↔Pi fight on automations | Old sync mirroring automations | `automations.auto.yaml` is **MirrorExclude**; Pi is source of truth for live rules |
| Expecting Admin reload after Blocky save | Not needed | CRUD already dispatches `CONFIG_RELOAD_REQUESTED` |

#### E3 — Regression matrix (operator fill on Pi)

Mark **Pass / Fail** after each smoke (historical checklist; Phase 5 DoD closed with operator smoke OK).

| Pattern | Example | Create | Edit | Delete | Fire ON/edge | Fire OFF/edge | Admin Debug after CRUD | Logs `rule=… branch=…` |
|---------|---------|--------|------|--------|--------------|---------------|------------------------|------------------------|
| Branched device ON+OFF | `switch.pc_monitors` | | | | | | | |
| One-sided ON-only or OFF-only | bathroom / spare | | | | | | | |
| Flat SYNC | `Slpk_Dries` or PC Aux | | | | | | | |
| Event-family branched | blinds / twilight / cinema family | | | | | | | |
| Scene-triggered | dashboard scene button rule | | | | | | | |

#### E4 — Runtime stability notes

- Migrated Y1 branched YAML + flat SYNC/scene rules must load clean on **boot** and on every **automatic** `CONFIG_RELOAD` after Blocky CRUD.
- Unresolved `entity_id` → **WARNING + skip** that device ref; engine keeps running (never crash the evaluate loop).
- State fields `ON`/`OFF` are coerced/quoted so YAML 1.1 bools cannot poison Pydantic on reload.
- X1 expansion is deterministic (ON then OFF); runtime ids `#on`/`#off` are never written back to YAML.

#### E5 — Hand-edit / manual Admin reload — RETIRED for normal ops

**Operator policy:** do **not** hand-edit `automations.auto.yaml`. All rule changes go through Blocky → API (auto hot-reload). Routine **Admin → reload config** is **not part of the Blocky workflow**.

**Emergency only** (corrupt file / restore `.bak.<UTC>` on disk outside Blocky): copy backup over the live file, then **restart WanOS** so config is re-read. (A subsequent Blocky Save also forces reload via the API — still not a reason to keep manual Admin reload in the runbook.)

Phase 5 does **not** require a rollback rehearsal that depends on hand-edit + Admin reload.

#### E6 — X2 readiness checkpoint (2026-08-05)

**Decision: stay on X1** (expand-at-load to flat `#on`/`#off` engine rules).

**Rationale:** Phase 0–5 closed on X1. **Revisit X2 in Phase 6A:** native **case** evaluate on unified schema v2 — not a separate forever-Y1 feature.

## 🧭 Next TODO (Option 2 roadmap)

1. **Phase 6A:** ✅ schema v2 + one-shot migrator + key order + preserve rich action fields on round-trip.
2. **Phase 6B:** ✅ one Blockly canvas + Cinema one list entry + OR-trigger + SYNC→ON/OFF on Pi; JSON power-user only.
3. **Phase 6C:** rich action UX — Hue preset, blinds open %, Sonos volume + station.
4. **Phase 7:** unified soft-hide UI (“hidden from Explorer / pickers”) — one surface for `deviceexplorer_exclude` ∪ Z-Wave `hidden_nodes`.
5. **Phase 8:** admin UI for `lighting` auto-off in `automations.auto.yaml`.
6. **Phase 9:** full Blockly ↔ JSON parity — every authorable v2 rule editable on canvas; JSON debug-only (or removed).

## ✅ Definition of Done (Option 2)

Use this as strict phase gates. Do not mark a phase complete unless all items are checked.

### Phase 3 DoD — Semantic pickers + policy enforcement ✅

- [x] **Device picker policy:** D1 is enforced in UI and backend-facing payload shaping:
  - hard-deny eids never appear/selectable,
  - soft-hidden eids are hidden by default and visible only via “Show Explorer-hidden devices”,
  - eids already used by the **open rule** (same picker role) remain listed so that rule can edit/round-trip.
- [x] **Event picker policy:** E1-v1 curated events are rendered with friendly labels (no raw key-only UX by default).
- [x] **Event family behavior:** explicit pair families are respected for branched event trigger UX (no suffix heuristics).
- [x] **No free-text dependency for normal flow:** standard rule authoring works end-to-end without typing raw `entity_id` or raw event keys (flat fallback mode remains available by design).
- [x] **Validation UX:** blocked selections show clear user feedback (why blocked + what to do).
- [x] **Compatibility:** existing rules load/edit/save without semantic drift.
- [x] **Regression smoke (operator run on Pi):** create/edit/delete one branched device rule, one branched event-family rule, one flat SYNC rule — **OK**.

### Phase 4 DoD — Blockly visual mode (hybrid) ✅

- [x] **Second editor mode exists:** Blockly canvas mode is available alongside the current JSON/form editor.
- [x] **Fallback preserved:** JSON/form editor remains fully functional and selectable at all times.
- [x] **Round-trip safety:** Blockly -> saved YAML -> reload -> reopened in Blockly preserves semantics for:
  - one-sided ON-only/OFF-only,
  - full ON+OFF branched rules,
  - event-family branched rules,
  - flat SYNC/multi-trigger rules (either editable or clearly marked fallback-only).
- [x] **Mode boundary clarity:** UI clearly indicates when a rule must be edited in fallback mode (if Blockly cannot represent it yet).
- [x] **No schema mutation (pre-6A):** persisted shape remained Y1 + flat compatible through Phase 4–5 (no ad-hoc schema). Phase **6A** replaces this baseline with unified schema v2 by design.
- [x] **Operator confidence checks:** `pc_monitors`, bathroom pair, scene-triggered rule from Blockly — **OK**.
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

### Phase 6A DoD — Unified schema v2 + migrator ✅

- [x] **Schema v2 locked & implemented:** trigger + ordered `cases`; API writes v2 only after deploy.
- [x] **Migrator on Pi (no lazy converge):** dry-run → backup → `--write`; Cinema pair merged; Admin Debug GREEN + clean boot (2026-08-05).
- [x] **Engine:** expand v2 cases → flat evaluate (interim); case labels in runtime ids (`#on`/`#off`/`#cN`).
- [x] **YAML key order:** **`name` → body → `id` last** on write/migrate.
- [x] **Rich fields preserved:** Blockly apply keeps preset/volume/station/bri/xy from prior editor state; API/v2 dump keeps them.

### Phase 6B DoD — One Blockly canvas + list unity ✅

- [x] **One Blockly canvas:** all production rules use if/else-if/else on v2; no branched-vs-flat mode split; JSON-only is opt-in.
- [x] **One list entry:** Cinema OFF (merged) once in the list; one flow; dashboard `scene:` behavior unchanged where applicable.
- [x] **Multi-trigger OR:** e.g. `KeukenLivingEetk_EetkHue` editable in Blockly without JSON.
- [x] **Round-trip (Pi smoke):** ex-Y1, ex-flat/ex-mirror, merged Cinema — OK (2026-08-05).

### Phase 6C DoD — Rich device action UX

- [ ] **Hue presets:** Blockly (or unified form on the same canvas) can set/show `preset` (e.g. `relax_red`) and round-trip.
- [ ] **Blinds open %:** operator sets open percentage; stored value matches engine convention; documented mapping.
- [ ] **Sonos volume + station:** editable in Blocky; stations from config; sufficient for live rules such as `pc_monitors`.

### Phase 9 DoD — Full Blockly ↔ JSON parity

- [ ] **Live-rule audit:** every rule in production `automations.auto.yaml` opens / edits / saves in Blockly with no semantic drift (rich, OR, multi-case, schedule families, soft-hidden sticky).
- [ ] **No required JSON:** operator can create and change any authorable v2 rule without opening JSON mode.
- [ ] **Per-action rich:** two actions on the same `entity_id` with different preset/volume/etc. round-trip independently (no entity-keyed collision).
- [ ] **No silent loss:** load→save in Blockly does not coerce away blinds mid-positions, rich keys, or unknown-but-legal fields without an explicit warning.
- [ ] **Sensor-class pickers:** sensors / temp / power / energy / fluid selectable where engine-legal; motion remains trigger-only; hard-deny still blocked in UI and on save.
- [ ] **Thresholds (if in scope):** compare conditions work in engine **and** Blockly together — or explicitly documented as out and not available in JSON either.
- [ ] **Events:** all production events reachable from Blockly (curated expansion and/or reviewed custom-event path).
- [ ] **JSON demoted:** UI/docs mark JSON as debug-only (or remove it); copy no longer says “power-user required for rich rules”.
- [ ] **Pi smoke:** edit `pc_monitors` (rich), one sensor/condition rule (if enabled), one OR multi-case rule — Admin Debug GREEN.

### Phase 5 DoD — Hardening + rollout readiness ✅

- [x] **Docs complete:** operator workflow and troubleshooting in `install_blocky.md` §E (+ pointer in `docs/reference.md`).
- [x] **Regression matrix complete:** pass/fail table for critical patterns in §E3; operator smoke **OK**.
- [x] **Runtime stability:** smoke OK on Pi (boot / Blocky CRUD auto-reload); no validation failures observed.
- [x] **Observability clarity:** `format_rule_ref` emits `rule=<id> branch=on|off|- name="…"` on X-RAY/ACTION (verified in live traces).
- [x] **Policy verification:** Blocky Save/Delete auto-runs Admin Debug; GREEN after representative CRUD.
- [x] **Hand-edit / manual Admin reload:** **retired** for normal ops (§E5) — Blocky API auto-reloads; no Phase 5 rollback rehearsal required.
- [x] **X2 readiness review:** **stay on X1** — rationale in §E6 (revisit in **Phase 6A** with schema v2 cases).


### SYNC — retired (use ON/OFF cases) ✅ DONE ON PI

**Retired:** trigger/action `SYNC` and `SYNCOPPOSITE`. Pure mirrors are one rule with `to_state: ON` + `to_state: OFF` cases (same targets).

**DoD:**
- [x] Schema migrator `_migrate_sync_to_cases` + YAML rewrite of four live mirrors.
- [x] Engine no longer honors SYNC trigger/action (leftover action → WARNING + skip).
- [x] Blocky UI no longer offers SYNC / SYNCOPPOSITE.
- [x] **Pi:** deploy + grep-clean YAML + Admin Debug GREEN + smoke four ex-mirrors (2026-08-05).