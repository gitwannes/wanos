# ⚡ WanOS: Visual Automation Editor (IFTTT) Architecture Guide

This document is the source of truth for (1) the **entity_id prerequisite** (done in code) and (2) the **Blocky** visual automation editor (Phases 0–8 **done**; next = **9A** / **9B**).

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
* Automatic domains live in **`automations.auto.yaml`** (`deviceexplorer_hide`, `auto_off_devices`, `automations`).

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

**Current status:** Phase 0–5 **✅ DONE**. Phase **6A–6C ✅ DONE**. **Phase 7 ✅ DONE**. **Phase 8 ✅ DONE**. **Phase 9A** = Blockly parity + sensors/thresholds/host gauges + remove JSON — **spec locked**. **Phase 9B** = bathroom climate + **H4/H5/H12** (OR groups, notify→Gmail, hysteresis) — **deferred**. Future HA patterns (H1–H3, H6–H11) backlog only.

**Follow-up (pickers):** sensors / temp / power / energy / fluid are **excluded** from the browsing catalog **until Phase 9A**. **Motion** = When-device trigger only; never as action. Soft-hidden / out-of-catalog sticky eids unchanged. Actions = actuators only. **9A** = sensor/threshold/host-gauge authoring + JSON removal. **9B** = bathroom climate + H4/H5/H12 (OR groups, notify→Gmail, hysteresis).

### Phase 0 — Blocky prep (decisions at start of Blocky work) ✅ DONE

1. Define **automation device deny-list** (which `entity_id`s / prefixes must not appear in pickers: safety, SSR, system-only, hidden, etc.).
2. Automations / auto-off / soft-hide already live in **`automations.auto.yaml`** — Blocky writes target that file (`ruamel` surgical write of `automations:`).
   - **Comment (historical through 6C):** Blocky write scope was **only `automations:`**. Soft-hide → **`deviceexplorer_hide`** = **Phase 7** ✅; auto-off → **`auto_off_devices:`** (was `lighting:`) = **Phase 8** ✅.
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
- One-shot migrator `helpers/migrate_automations_v2.py` (removed after Pi `--write` 2026-08-05)
- Rich action fields preserved on canvas apply / API dump

**Operator on Pi (completed 2026-08-05):**
1. Deploy code; migrator `--dry-run` (script since removed)
2. Review plan (Cinema OFF merge)
3. `--write` → Admin Debug GREEN + clean boot
4. Smoke: Cinema OFF dark/light cases, OR triggers, ex-mirror rules (now ON/OFF cases)

**Unified schema (v2) — conceptual shape:**
- `name`, `scene`, `require_confirmation`, …
- `trigger` — wake-up only: one device, one event/family, or **OR-list** (edge discrimination lives in `cases` when using cases).
- `cases` — ordered if / else-if / else: matchers (`to_state`, and/or `conditions`) + `actions`.
- Action payloads may include rich keys (`preset`, `bri`, `xy`, `volume`, `station`, numeric blinds `state`) — **preserved**; Blocky rich authoring shipped in Phase **6C**.
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
3. Cinema OFF (merged) + multi-trigger OR on one canvas; rich keys authored in Blockly (Phase **6C**).
4. SYNC/SYNCOPPOSITE retired → ON/OFF cases (see cutover below).

**Operator smoke:** ✅ OK on Pi (2026-08-05) — Cinema, OR, ex-Y1/ex-mirror, schedule windows.

### SYNC cutover — migrate mirrors to ON/OFF cases ✅ DONE ON PI

**Goal:** delete trigger/action `SYNC` and `SYNCOPPOSITE`; pure mirrors = **one rule**, two cases (`to_state: ON` / `OFF`).

**Code + YAML + Pi (completed 2026-08-05):**
- `_migrate_sync_to_cases` + engine retirement + Blocky without SYNC dropdowns
- Four mirrors rewritten; deployed YAML; Admin Debug GREEN; smoke OK
  (`Slpk_Dries`, `PC ON/OFF -> PC Aux`, `toilet_gv_ventilatie_on`, `Slpk Wannes: Hue App Syncs to Switch`)

**Rollback (emergency):** restore pre-cutover `automations.auto.yaml` **and** a build that still understood SYNC (current engine will not run leftover SYNC actions).

### Phase 6C — Rich device action UX ✅ DONE

**Depends on:** 6B (one canvas).

**Goal:** author rich actions in Blocky without hand-YAML. Engine already supports these payloads; 6C is **editor UX + pickers** only.

**Locked decisions (2026-08-06):**

1. **Hue** — color mode on light **ON** actions: **named preset** | **custom color** (Explorer **iro** wheel → payload `bri`/`xy`) | **(no color)**. **Mutually exclusive on one action:** either `preset` **or** `bri`/`xy`, never both (named presets stay first-class; engine would overwrite bri/xy from preset anyway). Operator bri slider **1–100** (Explorer parity); engine clamp remains **0–100**. `xy` = numeric pair (same payload shape as YAML / engine).
2. **Per-action rich storage** — rich keys live on each action block; retire `richByEntity[entity_id]` collision (same device twice with different rich must round-trip independently).
3. **Sonos stations dictionary** — expose station keys to Blocky (mirror `hue_presets` onto `/api/state` as `system.sonos_stations`); keys from `config.yaml` → `sonos.stations`.
4. **Volume bounds** — same ceilings as Device Explorer / bridges (device meta `max_volume`):
   - **Sonos:** **0–`max_volume`** from `config.sonos.max_volume` (currently **70**).
   - **Onkyo:** **0–`max_volume`** from `config.onkyo.max_volume` (currently **60**).
5. **Onkyo in scope** — same volume authoring as Sonos. **`station` is Sonos-only** (no Onkyo station dictionary in code).
6. **Blinds mid-position** — in scope: operator-facing **open %** including intermediate values (not only 0/100).

**Shipped:**

1. **Hue** — color mode named preset | custom color (wheel) | (no color) on light ON; presets from `state.system.hue_presets`; custom emits `bri`/`xy` only.
2. **Blinds** — operator **open %** field; stored `state` = closed % (`100 − open`). Same **storage** convention as Device Explorer (Explorer UI is closed %; Blocky UI is open %).
3. **Sonos + Onkyo** — `volume` when ON (bounds per #4). Sonos also `station` from `state.system.sonos_stations`.
4. **Per-action rich** — fields on each `b_action_device` block (no `richByEntity`).

**Operator smoke:** ✅ OK on Pi (**2026-08-06**) — Hue OFF clears color rows; named preset; custom color wheel Apply/Cancel; blinds mid open %; Sonos volume+station; Onkyo volume; uniqueness scoped by case (e.g. `pc_monitors`).

**Out of scope for 6C:** new engine semantics, Phase 7 soft-hide UI (✅ done), Phase 8 auto-off config UI (✅ done), full JSON↔Blockly parity (Phase **9** — 6C is the rich-action slice of that gap). XOR is enforced on the Blockly emit path; hand-edited JSON may still carry both `preset` and `bri`/`xy` until rewritten in Blockly.

### Phase 7 — Unified soft-hide (“hidden from Explorer / pickers”) ✅ DONE

**Shipped:** one soft-hide model — SoT = **`deviceexplorer_hide`** in `automations.auto.yaml`; Admin → **Explorer hidden devices** (`hiddendevices.html` + `/api/soft-hide`); shared nav gear (no notifications bell); Z-Wave page has no hide UX; hard-deny = **71040** only (code fence); **71036** soft-hide + commandable + Blocky-selectable.

**Historical (pre-cutover):** soft-hide was `deviceexplorer_exclude` ∪ Z-Wave `hidden_nodes`. One-shot `helpers/migrate_soft_hide.py` ran on Pi then was **removed** (same habit as 6A).

#### Locked (as implemented)

1. **Storage key = `deviceexplorer_hide`** in `automations.auto.yaml` (renamed from `deviceexplorer_exclude`). Soft-hide SoT = this key only. **No** dual-read of the old key.
2. **`zwave.hidden_nodes` deleted** — membership migrated into `deviceexplorer_hide`. Runtime does **not** read `hidden_nodes`.
3. **UI** — Admin → System Commands → **“Explorer hidden devices”** → **`hiddendevices.html`** (admin-only).
4. **Z-Wave page** — map / USB / mesh only; must not emit soft-hide.
5. **API** — admin **`GET` + full-list `PUT /api/soft-hide`**; body/response **`entity_ids: string[]`**; surgical `ruamel` write of **only** `deviceexplorer_hide:`; `CONFIG_RELOAD_REQUESTED` on save. Reject unknown eids; reject **71040** if present in PUT. Sorted unique eids on write.
6. **List UX** — name + type; Explorer-equivalent search/filter; All / Hidden only / Non-hidden only; select / deselect all visible; clickable Name/Type sort. Inventory omits **71040** and internal `90001`; checked = hidden.
7. **Hard-deny = 71040 only** — `switch.safety.safety_wisc_5v`: stays in Z-Wave `device_map`; **never** visible / selectable / switchable in Explorer, soft-hide page, or Blocky; bridge **keeps** outbound command drop. Hide via **code only (A)** — **not** in `deviceexplorer_hide`.
8. **71036 SSR** — soft-hidden (in `deviceexplorer_hide`); **commandable**; **Blocky-selectable**.
9. **Host / DB gauges** — soft-hide only (in `deviceexplorer_hide`); not hard-deny.
10. **Hot-reload** — yes (same policy as Blocky Save).

#### Constraints / notes

- Surgical write of **only** `deviceexplorer_hide:` (never `automations:` / `auto_off_devices:` / unrelated keys).
- D1 / Phase 0 historical prose: Phase 7 **supersedes** hard-deny to **71040 only** (+ `90001` skip unchanged); soft-hide key name = **`deviceexplorer_hide`**.

### Phase 8 — Auto-off timers config UI + engine ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-08**).

**Shipped:** SoT = **`auto_off_devices:`** in `automations.auto.yaml` (`managed_auto_off` + general + per-type + per-device delays); Admin → **Auto-off timers** (`lightingautooff.html` + `/api/auto-off-timer`); engine honors membership + precedence device→type→general; legacy `lighting:` / `managed_lights` removed.

**Historical (pre-cutover):** auto-off lived under `lighting:` + `managed_lights`. One-shot `helpers/migrate_auto_off_devices.py` ran on Pi then was **removed** (same habit as Phase 7 / 6A).

#### Locked (as implemented)

1. **Placement** — `lightingautooff.html`; Admin System Commands **“Auto-off timers”** under Explorer hidden devices; Admin-link only.
2. **API** — admin **`GET` + full-replace `PUT /api/auto-off-timer`**; hot-reload on save.
3. **YAML** — `auto_off_devices:` with `managed_auto_off`, `default_auto_off_minutes`, `default_pertype_auto_off_minutes`, `auto_off_delays`. No dual-read of `lighting:`.
4. **Precedence** — per-device → type → general. Minutes **1–720**.
5. **Membership** — checkbox → `managed_auto_off`; uncheck clears `auto_off_delays` entry; empty list allowed. Enable leaves per-device blank (inherit).
6. **UI** — general + type rows (`switch` / `light` / `speaker`) + device list; single **Effective** column (no separate Override): blank = inherit type/general shown muted italic until first keystroke; typed value = per-device pin; clear field → inherit; soft-hide All/Hidden/Non-hidden; **Auto-off ON/OFF/All** membership filter (checkbox, not lamp power); sort Name/Type/Effective by resolved minutes (unmanaged last); unmanaged Effective empty/disabled.
7. **Eligibility** — types `switch`/`light`/`speaker`; vents in; projector/SSR/71040/denylist out.
8. **Validation** — reject unresolved / orphan / ineligible / bad type keys; sorted unique writes.
9. **Comments** — not preserved under the block (UI-owned).

#### Operator cutover (Pi) — completed ✅

Dry-run reviewed (26 managed, 14 delays, vents kept) → `--write` → restart → Debug GREEN → **operator smoke OK** (**2026-08-08**). Migrator **deleted** from tree after cutover.

### Phase 9A — Full Blockly parity + sensors/thresholds + remove JSON 🔜 TODO (spec locked — impl not started)

**Depends on:** Phase **6C** ✅ (rich actions). Phases **7** / **8** ✅ (orthogonal; not prerequisites).

**Goal:** every authorable schema-v2 automation is create/edit-able entirely on Blockly. **JSON mode is removed** (same PR as parity green). Sensors / thresholds / host gauges become first-class where engine-legal.

**Split:** **9A** = parity audit + sensor/host pickers + compare + FORCE + E1 expand + **remove JSON**. **9B** = bathroom climate + **H4** (condition AND/OR groups) + **H5** (notify/alert → extend with Gmail per `docs/todo/integration_gmail.md`) + **H12** (hysteresis block). Vent **min-runtime lock stays in hub code**.

#### Locked (2026-08-08 — do not re-litigate without explicit change)

1. **Delivery order** — **audit-first**, then build; **post-audit** propose HA-inspired patterns (adoption separate).
2. **Thresholds / compare** — **in 9A:** engine + Blockly. Operators = `==`, `!=`, `>`, `>=`, `<`, `<=`. **Hysteresis / for-duration = 9B only**.
3. **Sensor-class types IN** — `sensor`, `temp_hum`, `temp`, `hum`, `power`, `energy`, `fluid`, `door`, **plus host gauges** (`sensor.*.host_*`, DB size, etc.). Motion = **trigger OK, never action**.
4. **Roles** — **both** When + if (engine-legal per type).
5. **`temp_hum` attributes** — separate fields: `temperature` and `humidity`.
6. **Sensor When semantics** — **discrete** (door / motion): any change; **numeric**: compare **becomes** true (edge / threshold-cross).
7. **Value UX (O1)** — **discrete = dropdown**; **numeric = Blockly `FieldNumber`** (same pattern as volume / blinds open %).
8. **FORCE_*** — every origin engine already honors; RFX/Epson omit redundant FORCE.
9. **Silent-loss = B+C** — opaque preserve unknown-but-legal keys; **block Save** when a drop would be non-preservable or structure cannot load safely.
10. **JSON** — **remove in same PR** as parity green.
11. **Events (O2 = A)** — **curated E1 expand only** (no custom-event field). Add **`SAUNA_SETPOINT_REACHED`** now; further keys only by explicit review + code/docs.
12. **O9 (doc chore)** — when JSON is removed, update Phase 0 **decision #12** (Hybrid / JSON fallback) so it no longer says “keep JSON until Phase 9”. Not a product fork — mechanical supersession at 9A ship.
13. **9B features** — bathroom climate (humidity band → Blockly); **H4** condition AND/OR groups; **H5** notify/alert action (**extend with Gmail** / `EMAIL_REQUESTED` per `docs/todo/integration_gmail.md`); **H12** generic hysteresis block. Feasibility for bathroom below. **Vent min-runtime lock (`90001` + timer) stays in hub code**.
14. **9B scope** — bathroom climate + H4 + H5 + H12. Hot-water→vent / sauna grace / other sweeper = **out** unless reopened. Other HA patterns (**H1–H3, H6–H11**) = **future possibilities** only (not 9A/9B).
15. **O7 disposition (2026-08-08)** — H4/H5/H12 → **9B**; remaining H\* → future backlog. **No** new HA primitives in **9A**. Post-audit step may still *note* gaps; it does not re-open this bucket without explicit change.
16. **Pi smoke** — operator broad smoke; DoD not exhaustive.
17. **Permanent exceptions** — hard-deny **71040** only; soft-hide / auto-off UIs stay 7/8.

#### Open

| ID | Topic | Status |
|----|--------|--------|
| *(none for 9A product locks)* | — | 9A ready to audit/impl; 9B ordering/details at 9B kickoff |

#### O7 — HA-inspired patterns — **disposition locked**

**9B (in):**

| # | Pattern | 9B note |
|---|---------|---------|
| **H4** | Condition AND/OR groups | Schema + Blockly; today conditions are flat AND |
| **H5** | Notify / alert action | UI alert first; **extend with Gmail** — Blockly/automation emits `EMAIL_REQUESTED` only (never calls Gmail). SoT: `docs/todo/integration_gmail.md` (OAuth outbox, producer hysteresis, transport dedup) |
| **H12** | Generic hysteresis / dual-threshold block | Vehicle for bathroom humidity band; reusable |

**Future possibilities (not 9A/9B):** H1 sustained-for · H2 delay/wait sequence · H3 cooldown · H6 input_number helper · H7 presence/mode · H8 area trigger · H9 sun elevation · H10 blueprints · H11 general choose/switch beyond ON/OFF cases.

#### Facts

- Engine `device_state` today = string equality only → 9A extends compares.
- Live YAML has no numeric-threshold rules yet.
- Host gauges may be soft-hidden → Hidden toggle / open-rule sticky unchanged.

#### Gap inventory (9A targets)

| Gap | 9A target |
|-----|-----------|
| Rich 6C | verify no coerce/loss |
| Sensors + host gauges | When + if; UX = dropdown / FieldNumber |
| Compare ops | `== != > >= < <=` (no hysteresis) |
| FORCE | all engine-honored origins |
| Events | E1 expand only; + `SAUNA_SETPOINT_REACHED` |
| Silent loss | B+C |
| JSON | remove same PR; supersede decision #12 |

#### In scope (9A)

1. Live-rule parity audit + gap list.
2. Post-audit: note any remaining gaps; **do not** adopt H\* into 9A (disposition locked).
3. Verify 6C rich / per-action / blinds mid.
4. Sensor + host-gauge pickers; motion trigger-only.
5. Compare conditions (no hysteresis — **H12 is 9B**).
6. FORCE completeness.
7. E1 + `SAUNA_SETPOINT_REACHED`.
8. JSON removal + B+C + update decision #12 prose.

**Out of scope for 9A:** bathroom climate; H4/H5/H12; vent-lock Blockly; H1–H3/H6–H11; schema v2 redesign; Phase 7/8 UIs; Gmail stack (see `integration_gmail.md` — hooks land in **9B H5**). Bathroom feasibility write-up lives under **Phase 9B** (not a 9A deliverable).

**Constraints:** Admin Debug GREEN; B+C no silent strip; hard-deny unchanged.

---

### Phase 9B — Bathroom climate + H4 / H5 / H12 🔜 DEFERRED (feasibility done for bathroom)

**Not 9A.** 9A supplies compare / sensor / `humidity` primitives only.

**Goal:**

1. **Bathroom climate** — humidity ON/OFF band in Blockly; retire hardcoded climate paths; **vent min-runtime lock stays in hub**.
2. **H12** — generic hysteresis / dual-threshold block (bathroom is the first consumer).
3. **H4** — condition AND/OR groups in schema + Blockly.
4. **H5** — notify/alert action; **extend with Gmail** via `EMAIL_REQUESTED` only (see `docs/todo/integration_gmail.md`). Rules never call Gmail directly.

#### Assessment — packing H4/H5/H12 into 9B (2026-08-08)

| Item | Fits 9B? | Dependency / risk |
|------|----------|-------------------|
| **H12** + bathroom | **Strong** | Natural vehicle for 80/74 band; do H12 before or with bathroom cutover |
| **H4** OR groups | **Useful** | Schema change; bathroom may not need OR day-one, but notify rules (`CPU>80 OR mem>90`) will; order after basic compares exist (9A) |
| **H5** UI alert | **Small** | Wire Blockly → existing `ALERT_INJECTED` (or equivalent) |
| **H5** Gmail | **Larger / cross-doc** | Needs outbox + OAuth from `integration_gmail.md`; automation hook = emit `EMAIL_REQUESTED`. Gmail **transport** can ship outside Blocky; **9B** owns the Blockly/action shape. Producer hysteresis in gmail MD aligns with **H12** (prefer stability before mail) |
| H1 sustained-for | **Out** (future) | Overlaps H12/for-duration — do not dual-build in 9B |
| H3 cooldown | **Out** (future) | Gmail MD already has **transport** dedup; rule-level cooldown can wait |
| H6 helpers | **Out** (future) | Would ease `bathroom1.vent_*` literals later; not required if literals OK for v1 band |

**Suggested 9B impl order (proposal, not locked):** H12 → bathroom cutover → H4 → H5 alert → H5 email (when Gmail spooler ready).

**Risk:** 9B scope grew from “bathroom only” — treat H4/H5 as explicit sub-deliverables; bathroom+H12 can DoD independently of Gmail if email lags.

#### Feasibility — bathroom climate / vent (2026-08-08) ✅ DONE

Pre-impl write-up (moved out of 9A in-scope; owned by **9B**).

**What is hardcoded today**

1. **Event path** (`HUMIDITY_UPDATED` on bathroom SHT11): if `hum >= vent_on_humidity` → vent ON; if `hum <= vent_off_humidity` and vent ON and **not** lock → vent OFF. Thresholds from `config.yaml` → `bathroom1.vent_on_humidity` / `vent_off_humidity` (80 / 74).
2. **Min-runtime lock** (`90001`): on vent rising edge ON, hub sets `devices[90001]=True` and schedules `BATH1_VENT_LOCK_EXPIRED` after `vent_min_runtime_mins`; expiry clears lock and re-dispatches `HUMIDITY_UPDATED` to re-evaluate OFF. **Stays in code (locked 2026-08-08).**
3. **Sweeper recovery** (Audit B): same ON/OFF thresholds on manual sweep — recovers desynced vent state.
4. **Related (out of 9B scope):** hot-water pulse → vent ON — not part of this phase unless reopened.

**Can humidity band become Blockly-authorable?**

| Piece | Verdict |
|-------|---------|
| `humidity >= 80` → vent ON | **Yes after 9A** (numeric When + `humidity` + action) |
| `humidity <= 74` → vent OFF | **9B** — hysteresis / dual-threshold (or two-rule pattern) |
| Min-runtime lock | **Keep in hub code** — Blockly-unaware side-effect on vent ON |
| Sweeper recovery | Decide at 9B impl: thin keep vs rely on next humidity event |
| `bathroom1.vent_*` in `config.yaml` | 9B migration: literals in automations and/or retire config keys |

**Verdict:** **Yes for 9B** for the humidity band, with lock remaining in code. Not a 9A deliverable.

**Locked 9B approach:** humidity band → Blockly via **H12**; **lock stays in hub**; plus **H4** + **H5** (alert → Gmail). Hot-water/sauna-grace still out.

**Not started (impl).**

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

> **Phase 6A–6C supersession:** items below lock the **pre-v2** baseline (Y1 + X1) used through Phase 5. **Phase 6A** replaced dual Y1/flat **storage** with unified schema v2 (`trigger` + `cases`); **6B** unified Blockly/list UX; **6C** added rich action authoring (closed 2026-08-06). Production YAML is v2.

1. **Persistence = first-class branched rule** (proposal B): one YAML rule with ON/OFF (or event-pair) branches — not two sibling flat rules kept forever. Blocky CRUD reads/writes the branched shape; runtime starts as **X1 expand-at-load**, then **X2 native** once CRUD is stable.
2. **Pair key = same trigger `entity_id`** (device) or same event family for event pairs. Auto-group / migrate by that key.
3. **Canonical example:** `switch.pc_monitors` — ON branch (schemer + Sonos rich) / OFF branch (both off).
4. **`SYNC` only when ON and OFF are the same** (pure mirror: same targets, flipped state, no asymmetric rich payload or conditions). Otherwise use explicit ON/OFF branches.
5. **Event pairs merge too** (e.g. cinema / twilight / sauna ON↔OFF) under the same branched model.
6. **One-sided OK:** ON-only (or OFF-only) rules allowed; the absent edge simply does not match (e.g. `BuroCinemaPC_cosy`).

## 🚦 Decisions locked (Blocky — Phase 0 open items)

1. **Deny-list = D1 (role-aware)** — **Phase 7 supersession:**  
   * **Hard deny** (never in Explorer / soft-hide page / Blocky pickers; never commandable): **`switch.safety.safety_wisc_5v` (71040) only** — code fence, not in `deviceexplorer_hide`.  
   * **Soft hide** (picker/Explorer default off; “Show Explorer-hidden” / soft-hide page): **`deviceexplorer_hide`** only. Soft-hidden devices stay out of Blocky pickers unless the checkbox is on. **Exception:** eids already used in the **open rule** (same picker role) remain listed so that rule can still round-trip / edit.  
   * **Internal:** idx `90001` vent lock skipped in Explorer (unchanged).  
   * Everything else in live `device_metadata` (status ≠ removed) is allow (subject to role-aware picker filters).
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
12. **UI strategy = Option 2 (Hybrid):** keep the current JSON/form editor as fallback + debugging path, and add Blockly visual mode incrementally. Do not remove the fallback editor until Blockly covers all live rule patterns and proves stable — that exit gate is **Phase 9A**. **Supersession:** when 9A removes JSON, rewrite this bullet to “Blockly-only; JSON removed” (doc chore **O9** — locked as mechanical, not a product reopen).

## ✅ Final spec lock checklist (no code)

Mark each item `LOCKED` before implementation starts.

### A) Already locked

- [x] **Scope:** Blocky writes only `automations:` through 6C; soft-hide → **`deviceexplorer_hide`** in **Phase 7**; auto-off → **`auto_off_devices:`** in **Phase 8**.
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
7. Diff backup vs new file. Auto domains (`deviceexplorer_hide:` / then-`lighting:` now `auto_off_devices:`) must be unchanged by M1.
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
| Sync Local↔Pi fight on automations | Old sync mirroring automations | `automations.auto.yaml` is **MirrorExclude** + **StatsRepoPull** (Pi wins); never push Local→Pi for hide/auto-off/rules |
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
3. **Phase 6C:** ✅ rich action UX — Hue preset XOR custom color (iro → bri/xy), blinds open % (incl. mid), Sonos/Onkyo volume, Sonos station, per-action rich; smoke OK Pi **2026-08-06**.
4. **Phase 7:** ✅ unified soft-hide — **`deviceexplorer_hide`**; `hiddendevices.html` + `/api/soft-hide`; hard-deny = 71040 (A); 71036 soft-hide + commandable + Blocky-selectable; migrator removed after cutover.
5. **Phase 8:** ✅ auto-off timers UI + engine — `auto_off_devices:`; `lightingautooff.html` + `/api/auto-off-timer`; migrator removed after cutover.
6. **Phase 9A:** Blockly parity + sensor/threshold/host-gauge authoring + **remove JSON** — **spec locked**.
7. **Phase 9B:** bathroom climate + **H12** hysteresis + **H4** condition OR groups + **H5** notify (→ Gmail per `integration_gmail.md`); vent lock stays in hub — deferred.
8. **Later:** HA patterns H1–H3, H6–H11 (future possibilities).

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
- [x] **Drag/connect correctness:** conditions and actions snap into the branch slots and can be dragged out again; verified on live Blocky (Alpine-safe `BlockyRT` workspace).
- [x] **Uniqueness:** one trigger / one ON / one OFF / one Then; no duplicate condition/action fingerprints on the canvas (toolbox hides singletons).

#### Snapping / un-snapping — root cause and fix

Symptom: blocks rendered and chained to each other, but would not drop into the `conditions`
/ `actions` slot of a branch, and could not be pulled back out.

Root causes (fixed):
1. Inject / layout while hidden (`x-show` → `display:none`) or zero-size host → broken hit-testing.
2. Storing `WorkspaceSvg` on Alpine reactive state (Proxy) → drag/snap broken.
3. Tailwind `svg { max-width: 100% }` distorting Blockly SVG metrics.

Fix: non-reactive `BlockyRT` workspace, park panel off-screen instead of `display:none`, correct inject options, `svgResize` + ResizeObserver, typed Condition/Action sockets.

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

### Phase 6C DoD — Rich device action UX ✅

**Operator smoke:** ✅ OK on Pi (**2026-08-06**).

- [x] **Hue preset + custom color:** Blockly can set/show `preset` (display name from `hue_presets`) **or** custom color via Explorer iro wheel → `bri` (1–100 UI) / `xy` — **not both**; OFF clears color rows; wheel Apply/Cancel close cleanly; round-trip.
- [x] **Blinds open % (incl. mid):** operator sets open percentage (not only 0/100); stored = closed % (`100 − open`); Blocky UI = open %, Explorer UI = closed %, same storage.
- [x] **Sonos volume + station:** editable in Blocky; volume **0–`max_volume`** (`config.sonos.max_volume`, currently 70); stations from `state.system.sonos_stations`; sufficient for live rules such as `pc_monitors`.
- [x] **Onkyo volume:** editable in Blocky; volume **0–`max_volume`** (device meta / `config.onkyo.max_volume`, currently 60); no station field.
- [x] **Per-action rich:** two actions on the same `entity_id` with different preset/volume/etc. round-trip independently (no `richByEntity` collision); uniqueness scoped by case so ON/OFF cases do not fight.
- [x] **Stations exposed:** Sonos station keys on `/api/state` as `system.sonos_stations`.

### Phase 7 DoD — Unified soft-hide UI ✅

- [x] **One source + rename:** soft-hide = **`deviceexplorer_hide`** only in `automations.auto.yaml`; legacy `deviceexplorer_exclude` removed; `hidden_nodes` migrated + deduped then **deleted**; runtime does not read old keys.
- [x] **Helpers migrator:** ran on Pi then **removed** from tree; 71040 stripped from hide list; Debug GREEN after restart.
- [x] **Admin entry:** System Commands → **“Explorer hidden devices”** opens **`hiddendevices.html`** (admin-only).
- [x] **Z-Wave UX removed:** Z-Wave config page no longer edits or writes `hidden_nodes`.
- [x] **API:** `GET` + full-list `PUT /api/soft-hide` (`entity_ids`); surgical write of `deviceexplorer_hide:` only; hot-reload on save.
- [x] **List UX:** name + type; Explorer-equivalent search/filter; select/deselect all **visible**.
- [x] **Hard-deny (A):** only `switch.safety.safety_wisc_5v` (**71040**) — code-filtered from Explorer / soft-hide page / Blocky; **not** in `deviceexplorer_hide`; outbound commands still dropped.
- [x] **71036:** soft-hidden via `deviceexplorer_hide` / new page; **commandable** (no bridge outbound drop); **Blocky-selectable**; host_* / `wanos_db_size` soft-hidden only (not hard-deny).
- [x] **Surgical write + hot-reload:** save writes only `deviceexplorer_hide:`; dispatches `CONFIG_RELOAD_REQUESTED`; no routine Admin reload.
- [x] **Runtime / Explorer / Blocky:** soft-hide set matches saved list after reload; 71040 never appears; Explorer Hidden toggle + Blocky soft-hide / sticky behavior still correct for soft-hidden eids.
- [x] **Admin Debug GREEN** after representative hide/unhide.
- [x] **Pi smoke:** hide/unhide path exercised; Z-Wave save does not write soft-hide; 71040 absent from operator UIs.

### Phase 8 DoD — Auto-off timers UI + engine ✅

- [x] **Cutover:** `lighting:` → `auto_off_devices:`; `managed_lights` → `managed_auto_off`; migrator `--dry-run` / `--write` on Pi then **removed**; runtime does not read old keys.
- [x] **Engine:** auto-off only for eids in `managed_auto_off`; delay = per-device → `default_pertype_auto_off_minutes[type]` → `default_auto_off_minutes`.
- [x] **Admin entry:** System Commands → **“Auto-off timers”** (under Hidden Devices) → `lightingautooff.html` (admin-only; no shell nav).
- [x] **API:** `GET` + full-replace `PUT /api/auto-off-timer`; surgical write of **`auto_off_devices:`** only; hot-reload on save; reject unresolved / orphan / ineligible / bad type keys; enforce `auto_off_delays` ⊆ `managed_auto_off`; sorted unique lists/maps; minutes 1–720.
- [x] **UI:** general + type rows (`switch` / `light` / `speaker`) + eligible device list (checkbox + **Effective** minutes); blank = inherit (muted italic resolved); typed = per-device pin; uncheck clears delay; soft-hide All / Hidden / Non-hidden; **Auto-off ON / OFF / All** membership filter; sort Name / Type / Effective (resolved; unmanaged last); 71040 omitted; vents + speakers eligible.
- [x] **Eligibility:** denylist + device extras enforced in inventory and on PUT; migrator stripped ineligible leftovers (kept vents).
- [x] **Comments:** block rewritten without preserving hand comments.
- [x] **Docs:** `install_blocky.md` Phase 8 closed + `docs/reference.md` API line.
- [x] **Admin Debug GREEN** after cutover / representative saves.
- [x] **Pi smoke:** migrator/rename; Auto-off timers page; general / type / per-device Effective pin; blank inherit (muted); uncheck clears delay; membership Auto-off ON/OFF filter; ON→timer uses expected delay; Debug GREEN — **OK on Pi (2026-08-08)** (Effective-column UX follow-up after that date).

### Phase 9A DoD — Blockly parity + sensors/thresholds + remove JSON

- [ ] **Live-rule audit:** every production rule opens / edits / saves in Blockly with no semantic drift; written gap list.
- [ ] **Post-audit note:** confirm no pressure to pull H\* into 9A (H4/H5/H12 wait for 9B).
- [ ] **Per-action rich:** verify 6C round-trip independence.
- [ ] **Silent-loss B+C:** unknown-legal keys preserved; Save blocked when a non-preservable drop would occur.
- [ ] **Sensor + host-gauge pickers:** When + if; motion trigger-only; hard-deny blocked; discrete dropdown / numeric `FieldNumber`.
- [ ] **Thresholds:** ops `== != > >= < <=` in engine **and** Blockly; no hysteresis; `temp_hum` → separate temperature / humidity; numeric When = edge-cross, discrete = any change.
- [ ] **FORCE:** all engine-honored origins.
- [ ] **Events:** E1 expand only; `SAUNA_SETPOINT_REACHED` present.
- [ ] **JSON removed** in same PR as parity green; decision #12 prose updated to Blockly-only.
- [ ] **Pi smoke:** operator broad smoke + Admin Debug GREEN.

### Phase 9B DoD — Bathroom climate + H4 / H5 / H12

- [x] **Bathroom feasibility:** write-up under Phase 9B (**2026-08-08**).
- [ ] **H12:** generic hysteresis / dual-threshold authorable in Blockly + engine.
- [ ] **Bathroom:** humidity ON/OFF band via H12; hardcoded climate paths retired; **vent min-runtime lock remains in hub**.
- [ ] **`bathroom1.vent_*` cutover** decided and applied.
- [ ] **Sweeper** climate recovery: keep-thin or drop — explicit at impl.
- [ ] **H4:** condition AND/OR groups in schema + Blockly + engine.
- [ ] **H5 alert:** Blockly notify/alert action (UI path).
- [ ] **H5 Gmail:** action emits `EMAIL_REQUESTED` only; aligns with `docs/todo/integration_gmail.md` (outbox/OAuth may land in parallel; email DoD can trail alert if needed).
- [ ] Hot-water/sauna-grace still out unless reopened.
- [ ] Pi smoke + Admin Debug GREEN.

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