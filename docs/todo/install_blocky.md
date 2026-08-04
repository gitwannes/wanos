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

## 📋 NEXT — Blocky implementation checklist

### Phase 0 — Blocky prep (decisions at start of Blocky work)

1. Define **automation device deny-list** (which `entity_id`s / prefixes must not appear in pickers: safety, SSR, system-only, hidden, etc.).
2. Automations / lighting / excludes already live in **`automations.auto.yaml`** — Blocky writes target that file (`ruamel` surgical write of `automations:`).
   - **Comment (locked for current phase):** Write scope is **only `automations:`**. Keep `lighting:` and `deviceexplorer_exclude:` untouched for later phase.
3. Inventory system events for the event dropdown dictionary.
4. **ON/OFF merge model** — locked below (schema + migration of existing sibling pairs).

### Phase 1 — Backend API (CRUD & hot-reload)

1. `GET/POST/PUT/DELETE /api/automations`.
2. `ruamel.yaml` surgical write of `automations:` in **`automations.auto.yaml`** only (preserve comments).
3. Persist **`entity_id`** on device triggers/conditions/actions (never raw idx).
4. Support **first-class branched rules** (Y1 `on:`/`off:`) in schema; **X1:** expand at load to flat engine rules (pair identity preserved for CRUD).
5. Migrate existing sibling ON/OFF (and event ON/OFF) pairs per **M1**; leave `SYNC` and multi-ON cases (`living_special`) alone.
6. Dispatch `CONFIG_RELOAD_REQUESTED`; clear `AutomationEngine` config cache.
7. **Later:** promote expand path to **X2** native branch evaluate once Blocky CRUD is stable.

### Phase 2 — Frontend data model

1. Alpine editor store: `name`, `scene`, trigger (device or event), optional **ON branch** / **OFF branch** (each: `conditions[]`, `actions[]`), or **SYNC** when applicable.
2. Add-trigger / add-action binds **`entity_id`**; UI shows **`name`**.
3. One-sided rules allowed (ON-only or OFF-only); missing branch simply does not match that edge.

### Phase 3 — Semantic dropdowns

1. Device pickers from **`device_metadata`** (respect deny-list).
2. Event pickers from friendly event dictionary.
3. Users never type `entity_id`.

### Phase 4 — UI blocks (DaisyUI)

1. WHEN (device / system event) — one trigger; UI asks ON vs OFF (or shows both branches).
2. AND IF (time of day / device state) — **per branch** when conditions differ.
3. THEN DO (device / scene / event; force; rich light/speaker payloads for `hue.light.*` / `media_player.*` as applicable) — **per branch**.
4. Canonical template: **`switch.pc_monitors`** (ON: schemer + Sonos with volume/station; OFF: both off).

### Phase 5 — Hardening

1. Run Admin Debug entity/automation check after Blocky writes.
2. Confirm unresolved ids still log+skip without taking down the engine.
3. Document operator workflow (create rule → save → hot-reload → verify).

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

### B) Lock now before coding (precision items)

- [ ] **Rule `id` format and policy**
  - Choose one: `UUIDv4` / `ULID` / other.
  - Lock generation source (backend-only recommended), immutability, duplicate handling, and backfill behavior.
- [ ] **E1-v1 concrete event table**
  - Lock exact event keys and labels.
  - Lock allowed usage per event: trigger-only / action-only / both.
  - Lock event-pair family mappings used by merge/UI.
- [ ] **X1 log/debug naming contract**
  - Lock internal branch naming (`<id>#on|off` or equivalent) and log format.
  - Lock deterministic branch evaluation order.
- [ ] **MA operational runbook**
  - Lock operator, environment, pre-backup, dry-run/write mode, rollback, and sign-off checks.

### C) MA execution checklist (operational gate)

- [ ] Backup `automations.auto.yaml`.
- [ ] Run M1 migration once (explicit MA step).
- [ ] Review diff: only eligible ON/OFF sibling pairs merged; `SYNC` and `living_special` unchanged.
- [ ] Dispatch `CONFIG_RELOAD_REQUESTED`.
- [ ] Run Admin Debug entity-registry check (must be GREEN).
- [ ] Smoke test canonical scenarios: `switch.pc_monitors`, bathroom ON/OFF pairs, spare-button scenarios.
- [ ] Record operator/date + result in release notes or deployment log.

### D) Implementation readiness gate

- [ ] All items in section **B** are marked locked.
- [ ] MA checklist section **C** is approved by operator.
- [ ] This file is frozen as the implementation baseline for Blocky v1.

### SYNC — keep or split to ON/OFF?

**Keep `SYNC` as a first-class mode** when ON and OFF are pure mirrors (same targets, flipped/mirrored state, no asymmetric rich payload or conditions). That matches your locked rule and industry practice:

* HA: one automation, trigger on any state change, action sets target to `trigger.to_state` (mirror) — not two duplicated halves.
* openHAB / many hubs: “follow” / mirror profiles for 1:1 coupling.
* Splitting pure mirrors into identical `on:`/`off:` trees invites drift (edit ON, forget OFF).

**Do not use SYNC** when branches differ (e.g. `switch.pc_monitors` → Sonos volume/station on ON only) — use Y1 `on:`/`off:`.

Current pure-SYNC rules (leave as SYNC under M1): `Slpk_Dries`, `PC ON/OFF -> PC Aux`, `toilet_gv_ventilatie_on`, `Slpk Wannes: Hue App Syncs to Switch`.
