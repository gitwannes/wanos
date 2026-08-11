# ⚡ WanOS Phase B — Blocky

This document is the source of truth for (1) the **entity_id prerequisite** (done in code) and (2) the **Blocky** visual automation editor (Phases **B0–B8** + **B10A** + **B10C** **done**; **B10B+D+E** ✅ **complete 2026-08-10** — smoke/GREEN/kiosk + migrator deleted; **B10F** ✅ **Done 2026-08-11**; queued **B9A** / **B9B** / **B11–B18**). Operator shell → [`phaseC-shell.md`](phaseC-shell.md) (**C1/C2/C5** ✅; **C6–C9** ✅ **Done 2026-08-10**; **C10** next); device typing → [`phaseD-typing.md`](phaseD-typing.md); sequence → [`pipeline.md`](pipeline.md). Schedule admin model: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

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
| Scene | `scene.<slug>` | **Retired after B10B** — dashboard uses `events:` / `dashboard_events` (UUID), not `scene.*` entity births |
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

**Current status:** Phase B0–B5 **✅ DONE**. Phase **B6A–B6C ✅ DONE**. **Phase B7 ✅ DONE**. **Phase B8 ✅ DONE**. **Phase B10A ✅ DONE** (Pi smoke **2026-08-09**). **Phase B10C ✅ DONE** (Pi smoke **2026-08-09**). **Phase B10B+D+E ✅ DONE** (**2026-08-10** — Library UX UE/UR/SE/SR/D, UE form, When/Fire split, schedule display names, `SUNRISE_SUNSET_UPDATE`; operator Pi smoke + Admin Debug GREEN + kiosk; migrator + D1 aliases deleted). **Phase B10F ✅ DONE** (**2026-08-11** — Automations UX polish: save chrome, fire-status, evening skip, SE→SR/UE→UR, inline usages, CRUD INFO quoted, SR name = SE catalog). **Phase B9A** = Blockly parity + sensors/thresholds/host gauges + remove JSON — **spec locked**. **Phase B9B** = bathroom climate + **H4/H5/H12** (H4 expands: drop trigger “when any of” → condition and/or) — **deferred**. **B11–B18** = lettered ex–Later B (multi-flow, folder/tag, IF/ELSE, remaining HA, demote schedule, bus UUID, Sauna/IR assess, sauna session_end clamp).

**Follow-up (pickers):** sensors / temp / power / energy / fluid are **excluded** from the browsing catalog **until Phase B9A**. **Motion** = When-device trigger only; never as action. Soft-hidden / out-of-catalog sticky eids unchanged. Actions = actuators only. **B9A** = sensor/threshold/host-gauge authoring + JSON removal. **B9B** = bathroom climate + H4/H5/H12 (H4: drop trigger “when any of” → condition and/or; H5 notify→Gmail; H12 hysteresis).

### Phase B0 — Blocky prep (decisions at start of Blocky work) ✅ DONE

1. Define **automation device deny-list** (which `entity_id`s / prefixes must not appear in pickers: safety, SSR, system-only, hidden, etc.).
2. Automations / auto-off / soft-hide already live in **`automations.auto.yaml`** — Blocky writes target that file (`ruamel` surgical write of `automations:`).
   - **Comment (historical through B6C):** Blocky write scope was **only `automations:`**. Soft-hide → **`deviceexplorer_hide`** = **Phase B7** ✅; auto-off → **`auto_off_devices:`** (was `lighting:`) = **Phase B8** ✅.
3. Inventory system events for the event dropdown dictionary.
4. **ON/OFF merge model** — locked below (schema + migration of existing sibling pairs).

### Phase B1 — Backend API (CRUD & hot-reload) ✅ DONE

1. `GET/POST/PUT/DELETE /api/automations`.
2. `ruamel.yaml` surgical write of `automations:` in **`automations.auto.yaml`** only (preserve comments).
3. Persist **`entity_id`** on device triggers/conditions/actions (never raw idx).
4. Support **first-class branched rules** (Y1 `on:`/`off:`) in schema; **X1:** expand at load to flat engine rules (pair identity preserved for CRUD).
5. Migrate existing sibling ON/OFF (and event ON/OFF) pairs per **M1**; leave `SYNC` and multi-ON cases (`living_special`) alone.
6. Dispatch `CONFIG_RELOAD_REQUESTED`; clear `AutomationEngine` config cache.
   - **Follow-up (not B):** full Hue/Onkyo/Z-Wave recycle on every save → scoped reload **G6** ([`phaseG-integrations.md`](phaseG-integrations.md) § G6).
7. **Later:** promote expand path to **X2** native branch evaluate once Blocky CRUD is stable.

### Phase B2 — Frontend data model ✅ DONE

1. Alpine editor store: `name`, `scene`, trigger (device or event), optional **ON branch** / **OFF branch** (each: `conditions[]`, `actions[]`), or **SYNC** when applicable.
2. Add-trigger / add-action binds **`entity_id`**; UI shows **`name`**.
3. One-sided rules allowed (ON-only or OFF-only); missing branch simply does not match that edge.

### Phase B3 — Semantic dropdowns ✅ DONE

1. Device pickers from **`device_metadata`** (respect deny-list).
2. Event pickers from friendly event dictionary.
3. Users never type `entity_id`.
4. **Follow-up:** sensors / temp / power / energy / fluid omitted from pickers; motion = trigger-only; actions = actuators only — see status note above.

### Phase B4 — UI blocks (Blockly hybrid) ✅ DONE

1. WHEN (device / system event) — one trigger; ON/OFF branches (or flat Then).
2. AND IF (time of day / device state) — **per branch**.
3. THEN DO (device / event actions) — **per branch** / flat Then.
4. Canonical template: **`switch.pc_monitors`** (operator confidence check **OK**).
5. Snapping / uniqueness / Alpine-safe workspace — fixed and verified on minimal harness + live Blocky.

### Phase B5 — Hardening ✅ DONE

1. [x] Run Admin Debug entity/automation check after Blocky writes (auto after Save/Delete; banner shows GREEN/RED).
2. [x] Confirm unresolved ids still log+skip without taking down the engine (`resolve_device_ref` WARNING).
3. [x] Document operator workflow (create rule → save → hot-reload → verify) — see **E) Phase B5 operator runbook** below.

### Phase B6A — Unified schema v2 + migrator ✅ DONE

**Goal (locked — option B, storage cutover):**
- **One persisted schema for every automation** — not dual Y1 branched + flat forever. Y1 `on:`/`off:` and flat `conditions`/`actions` become **legacy migrator/API input** only.
- Engine expands v2 cases → flat evaluate (X1-style interim). **YAML on disk is v2 only** after migrator `--write`.

**Implemented:**
- `core/automations_schema_v2.py` — convert / expand / Cinema merge / canonical `name`…`id` last
- Loader dual-read via `expand_automations_for_engine`
- API POST/PUT persist **v2 only**; GET returns raw v2 (Phase B6B)
- One-shot migrator `helpers/migrate_automations_v2.py` (removed after Pi `--write` 2026-08-05)
- Rich action fields preserved on canvas apply / API dump

**Operator on Pi (completed 2026-08-05):**
1. Deploy code; migrator `--dry-run` (script since removed)
2. Review plan (Cinema OFF merge)
3. `--write` → Admin Debug GREEN + clean boot
4. Smoke: Cinema OFF dark/light cases, OR triggers, ex-mirror rules (now ON/OFF cases)

**Unified schema (v2) — conceptual shape:**
- `name`, … (pre-B10B also `scene`, `require_confirmation` on rules — **stripped in B10B**; confirm/dashboard live on `events:`)
- `enabled` — per-rule (B10B; default true)
- `trigger` — wake-up only: one device, one event **UUID** (after B10B), or **OR-list** (edge discrimination lives in `cases` when using cases). Pre-B10B family names removed on cutover.
- `cases` — ordered if / else-if / else: matchers (`to_state`, and/or `conditions`) + `actions`.
- Action payloads may include rich keys (`preset`, `bri`, `xy`, `volume`, `station`, numeric blinds `state`) — **preserved**; Blocky rich authoring shipped in Phase **B6C**. Fire-event actions store event **UUID** after B10B.
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

### Phase B6B — One Blockly canvas + list unity ✅ DONE

**Depends on:** B6A (v2 on disk + API).

**Goal:**
- **One Blockly experience** — `When (trigger) → if / else-if / else → actions`; no branched-vs-flat editor modes.
- **One list entry per logical automation** — Cinema OFF appears once; one flow. Dashboard `scene:` button behavior unchanged where applicable.
- Eliminate “Complex flat rule — JSON only” as the default for live rules (JSON = power-user override only).

**Implemented:**
1. Blockly read/write **v2 only**; retired branched/flat dual modes; schedule-window UX; one device root + cases; dashboard toggles only for event triggers.
2. API GET/POST/PUT return **raw v2**.
3. Cinema OFF (merged) + multi-trigger OR on one canvas; rich keys authored in Blockly (Phase **B6C**).
4. SYNC/SYNCOPPOSITE retired → ON/OFF cases (see cutover below).

**Operator smoke:** ✅ OK on Pi (2026-08-05) — Cinema, OR, ex-Y1/ex-mirror, schedule windows.

### SYNC cutover — migrate mirrors to ON/OFF cases ✅ DONE ON PI

**Goal:** delete trigger/action `SYNC` and `SYNCOPPOSITE`; pure mirrors = **one rule**, two cases (`to_state: ON` / `OFF`).

**Code + YAML + Pi (completed 2026-08-05):**
- `_migrate_sync_to_cases` + engine retirement + Blocky without SYNC dropdowns
- Four mirrors rewritten; deployed YAML; Admin Debug GREEN; smoke OK
  (`Slpk_Dries`, `PC ON/OFF -> PC Aux`, `toilet_gv_ventilatie_on`, `Slpk Wannes: Hue App Syncs to Switch`)

**Rollback (emergency):** restore pre-cutover `automations.auto.yaml` **and** a build that still understood SYNC (current engine will not run leftover SYNC actions).

### Phase B6C — Rich device action UX ✅ DONE

**Depends on:** B6B (one canvas).

**Goal:** author rich actions in Blocky without hand-YAML. Engine already supports these payloads; B6C is **editor UX + pickers** only.

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

**Out of scope for B6C:** new engine semantics, Phase B7 soft-hide UI (✅ done), Phase B8 auto-off config UI (✅ done), full JSON↔Blockly parity (Phase **B9** — B6C is the rich-action slice of that gap). XOR is enforced on the Blockly emit path; hand-edited JSON may still carry both `preset` and `bri`/`xy` until rewritten in Blockly.

### Phase B7 — Unified soft-hide (“hidden from Explorer / pickers”) ✅ DONE

**Shipped:** one soft-hide model — SoT = **`deviceexplorer_hide`** in `automations.auto.yaml`; Admin → **Explorer hidden devices** (`hiddendevices.html` + `/api/soft-hide`); shared nav gear (no notifications bell); Z-Wave page has no hide UX; hard-deny = **71040** only (code fence); **71036** soft-hide + commandable + Blocky-selectable.

**Historical (pre-cutover):** soft-hide was `deviceexplorer_exclude` ∪ Z-Wave `hidden_nodes`. One-shot `helpers/migrate_soft_hide.py` ran on Pi then was **removed** (same habit as B6A).

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
- D1 / Phase B0 historical prose: Phase B7 **supersedes** hard-deny to **71040 only** (+ `90001` skip unchanged); soft-hide key name = **`deviceexplorer_hide`**.

### Phase B8 — Auto-off timers config UI + engine ✅ DONE

**Operator smoke:** ✅ OK on Pi (**2026-08-08**).

**Shipped:** SoT = **`auto_off_devices:`** in `automations.auto.yaml` (`managed_auto_off` + general + per-type + per-device delays); Admin → **Auto-off timers** (`lightingautooff.html` + `/api/auto-off-timer`); engine honors membership + precedence device→type→general; legacy `lighting:` / `managed_lights` removed.

**Historical (pre-cutover):** auto-off lived under `lighting:` + `managed_lights`. One-shot `helpers/migrate_auto_off_devices.py` ran on Pi then was **removed** (same habit as Phase B7 / B6A).

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

### Phase B9A — Full Blockly parity + sensors/thresholds + remove JSON 🔜 TODO (spec locked — impl not started)

**Depends on:** Phase **B6C** ✅ (rich actions). Phases **7** / **8** ✅ (orthogonal; not prerequisites).

**Goal:** every authorable schema-v2 automation is create/edit-able entirely on Blockly. **JSON mode is removed** (same PR as parity green). Sensors / thresholds / host gauges become first-class where engine-legal.

**Split:** **B9A** = parity audit + sensor/host pickers + compare + FORCE + E1 expand + **remove JSON**. **B9B** = bathroom climate + **H4** (condition AND/OR groups) + **H5** (notify/alert → extend with Gmail per `docs/todo/phaseE-gmail.md`) + **H12** (hysteresis block). Vent **min-runtime lock stays in hub code**.

#### Locked (2026-08-08 — do not re-litigate without explicit change)

1. **Delivery order** — **audit-first**, then build; **post-audit** propose HA-inspired patterns (adoption separate).
2. **Thresholds / compare** — **in B9A:** engine + Blockly. Operators = `==`, `!=`, `>`, `>=`, `<`, `<=`. **Hysteresis / for-duration = B9B only**.
3. **Sensor-class types IN** — `sensor`, `temp_hum`, `temp`, `hum`, `power`, `energy`, `fluid`, `door`, **plus host gauges** (`sensor.*.host_*`, DB size, etc.). Motion = **trigger OK, never action**.
4. **Roles** — **both** When + if (engine-legal per type).
5. **`temp_hum` attributes** — separate fields: `temperature` and `humidity`.
6. **Sensor When semantics** — **discrete** (door / motion): any change; **numeric**: compare **becomes** true (edge / threshold-cross).
7. **Value UX (O1)** — **discrete = dropdown**; **numeric = Blockly `FieldNumber`** (same pattern as volume / blinds open %).
8. **FORCE_*** — every origin engine already honors; RFX/Epson omit redundant FORCE.
9. **Silent-loss = B+C** — opaque preserve unknown-but-legal keys; **block Save** when a drop would be non-preservable or structure cannot load safely.
10. **JSON** — **remove in same PR** as parity green.
11. **Events (O2 = A)** — **pre-B10B:** curated E1 expand only. **After B10B:** pickable set = `events:` catalog (UUID); expand system seeds only by explicit review + constants. **`SAUNA_SETPOINT_REACHED`** seeded in B10B; further keys only by explicit review + code/docs.
12. **O9 (doc chore)** — when JSON is removed, update Phase B0 **decision #12** (Hybrid / JSON fallback) so it no longer says “keep JSON until Phase B9”. Not a product fork — mechanical supersession at B9A ship.
13. **B9B features** — bathroom climate (humidity band → Blockly); **H4** condition AND/OR groups; **H5** notify/alert action (**extend with Gmail** / `EMAIL_REQUESTED` per `docs/todo/phaseE-gmail.md`); **H12** generic hysteresis block. Feasibility for bathroom below. **Vent min-runtime lock (`90001` + timer) stays in hub code**.
14. **B9B scope** — bathroom climate + H4 + H5 + H12. Hot-water→vent / sauna grace / other sweeper = **out** unless reopened. Other HA patterns (**H1–H3, H6–H11**) = **future possibilities** only (not B9A/B9B).
15. **O7 disposition (2026-08-08)** — H4/H5/H12 → **B9B**; remaining H\* → future backlog. **No** new HA primitives in **B9A**. Post-audit step may still *note* gaps; it does not re-open this bucket without explicit change.
16. **Pi smoke** — operator broad smoke; DoD not exhaustive.
17. **Permanent exceptions** — hard-deny **71040** only; soft-hide / auto-off UIs stay 7/8.

#### Open

| ID | Topic | Status |
|----|--------|--------|
| *(none for B9A product locks)* | — | B9A ready to audit/impl; B9B ordering/details at BB9B kickoff |

#### O7 — HA-inspired patterns — **disposition locked**

**B9B (in):**

| # | Pattern | B9B note |
|---|---------|---------|
| **H4** | Condition AND/OR groups + retire trigger “when any of” | Schema + Blockly + engine; today conditions are flat AND; multi-device OR moves out of trigger into condition and/or |
| **H5** | Notify / alert action | UI alert first; **extend with Gmail** — Blockly/automation emits `EMAIL_REQUESTED` only (never calls Gmail). SoT: `docs/todo/phaseE-gmail.md` (OAuth outbox, producer hysteresis, transport dedup) |
| **H12** | Generic hysteresis / dual-threshold block | Vehicle for bathroom humidity band; reusable |

**Later lettered (not B9A/B9B):** H1–H3, H6–H10 → **B14**; H11 (IF/ELSE / ELSEIF / ELSE beyond ON/OFF cases) → **B13**. See § B11–B18.

#### Facts

- Engine `device_state` today = string equality only → B9A extends compares.
- Live YAML has no numeric-threshold rules yet.
- Host gauges may be soft-hidden → Hidden toggle / open-rule sticky unchanged.

#### Gap inventory (B9A targets)

| Gap | B9A target |
|-----|-----------|
| Rich B6C | verify no coerce/loss |
| Sensors + host gauges | When + if; UX = dropdown / FieldNumber |
| Sauna session condition | `state.sauna.active` in if; smoke rule sauna hue physical (71035→51002/72004) |
| Compare ops | `== != > >= < <=` (no hysteresis) |
| FORCE | all engine-honored origins |
| Events | After B10B: `events:` catalog; + `SAUNA_SETPOINT_REACHED` (seeded in B10B) |
| Silent loss | B+C |
| JSON | remove same PR; supersede decision #12 |

#### In scope (B9A)

1. Live-rule parity audit + gap list.
2. Post-audit: note any remaining gaps; **do not** adopt H\* into B9A (disposition locked).
3. Verify B6C rich / per-action / blinds mid.
4. Sensor + host-gauge pickers; motion trigger-only.
5. **Sauna session condition** (`sauna.active`) + author **sauna hue physical** smoke rule (entities: `switch.sauna_hue_physical`, `hue.group.sauna_hue`, `switch.sauna_zoutlamp`).
6. Compare conditions (no hysteresis — **H12 is B9B**).
7. FORCE completeness.
8. E1 + `SAUNA_SETPOINT_REACHED` (catalog via B10B).
9. JSON removal + B+C + update decision #12 prose.

**Out of scope for B9A:** bathroom climate; H4/H5/H12; vent-lock Blockly; H1–H3/H6–H11; schema v2 redesign; Phase B7/8 UIs; Gmail stack / Phase E (see `phaseE-gmail.md` — hooks land in **B9B H5**). Bathroom feasibility write-up lives under **Phase B9B** (not a B9A deliverable).

**Constraints:** Admin Debug GREEN; B+C no silent strip; hard-deny unchanged.

---

### Phase B9B — Bathroom climate + H4 / H5 / H12 🔜 DEFERRED (feasibility done for bathroom)

**Not B9A.** B9A supplies compare / sensor / `humidity` primitives only.

**Goal:**

1. **Bathroom climate** — humidity ON/OFF band in Blockly; retire hardcoded climate paths; **vent min-runtime lock stays in hub**.
2. **H12** — generic hysteresis / dual-threshold block (bathroom is the first consumer).
3. **H4** — condition AND/OR groups in schema + Blockly + engine; **remove “when any of” from trigger** and express multi-match via condition **and** / **or** instead.
4. **H5** — notify/alert action; **extend with Gmail** via `EMAIL_REQUESTED` only (see `docs/todo/phaseE-gmail.md`). Rules never call Gmail directly.

#### Assessment — packing H4/H5/H12 into B9B (2026-08-08)

| Item | Fits B9B? | Dependency / risk |
|------|----------|-------------------|
| **H12** + bathroom | **Strong** | Natural vehicle for 80/74 band; do H12 before or with bathroom cutover |
| **H4** OR groups + drop trigger “when any of” | **Useful** | Schema + trigger model change; bathroom may not need OR day-one, but notify rules (`CPU>80 OR mem>90`) will; migrates multi-device OR out of trigger; order after basic compares exist (B9A) |
| **H5** UI alert | **Small** | Wire Blockly → existing `ALERT_INJECTED` (or equivalent) |
| **H5** Gmail | **Larger / cross-doc** | Needs outbox + OAuth from `phaseE-gmail.md`; automation hook = emit `EMAIL_REQUESTED`. Gmail **transport** can ship outside Blocky; **B9B** owns the Blockly/action shape. Producer hysteresis in gmail MD aligns with **H12** (prefer stability before mail) |
| H1 sustained-for | **Out** (future) | Overlaps H12/for-duration — do not dual-build in B9B |
| H3 cooldown | **Out** (future) | Gmail MD already has **transport** dedup; rule-level cooldown can wait |
| H6 helpers | **Out** (future) | Would ease `bathroom1.vent_*` literals later; not required if literals OK for v1 band |

**Suggested B9B impl order (proposal, not locked):** H12 → bathroom cutover → H4 → H5 alert → H5 email (when Gmail spooler ready).

**Risk:** B9B scope grew from “bathroom only” — treat H4/H5 as explicit sub-deliverables; bathroom+H12 can DoD independently of Gmail if email lags.

#### Feasibility — bathroom climate / vent (2026-08-08) ✅ DONE

Pre-impl write-up (moved out of B9A in-scope; owned by **B9B**).

**What is hardcoded today**

1. **Event path** (`HUMIDITY_UPDATED` on bathroom SHT11): if `hum >= vent_on_humidity` → vent ON; if `hum <= vent_off_humidity` and vent ON and **not** lock → vent OFF. Thresholds from `config.yaml` → `bathroom1.vent_on_humidity` / `vent_off_humidity` (80 / 74).
2. **Min-runtime lock** (`90001`): on vent rising edge ON, hub sets `devices[90001]=True` and schedules `BATH1_VENT_LOCK_EXPIRED` after `vent_min_runtime_mins`; expiry clears lock and re-dispatches `HUMIDITY_UPDATED` to re-evaluate OFF. **Stays in code (locked 2026-08-08).**
3. **Sweeper recovery** (Audit B): same ON/OFF thresholds on manual sweep — recovers desynced vent state.
4. **Related (out of B9B scope):** hot-water pulse → vent ON — not part of this phase unless reopened.

**Can humidity band become Blockly-authorable?**

| Piece | Verdict |
|-------|---------|
| `humidity >= 80` → vent ON | **Yes after B9A** (numeric When + `humidity` + action) |
| `humidity <= 74` → vent OFF | **B9B** — hysteresis / dual-threshold (or two-rule pattern) |
| Min-runtime lock | **Keep in hub code** — Blockly-unaware side-effect on vent ON |
| Sweeper recovery | Decide at B9B impl: thin keep vs rely on next humidity event |
| `bathroom1.vent_*` in `config.yaml` | B9B migration: literals in automations and/or retire config keys |

**Verdict:** **Yes for B9B** for the humidity band, with lock remaining in code. Not a B9A deliverable.

**Locked B9B approach:** humidity band → Blockly via **H12**; **lock stays in hub**; plus **H4** + **H5** (alert → Gmail). Hot-water/sauna-grace still out.

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

> **Phase B6A–B6C supersession:** items below lock the **pre-v2** baseline (Y1 + X1) used through Phase B5. **Phase B6A** replaced dual Y1/flat **storage** with unified schema v2 (`trigger` + `cases`); **B6B** unified Blockly/list UX; **B6C** added rich action authoring (closed 2026-08-06). Production YAML is v2.

1. **Persistence = first-class branched rule** (proposal B): one YAML rule with ON/OFF (or event-pair) branches — not two sibling flat rules kept forever. Blocky CRUD reads/writes the branched shape; runtime starts as **X1 expand-at-load**, then **X2 native** once CRUD is stable.
2. **Pair key = same trigger `entity_id`** (device) or same event family for event pairs. Auto-group / migrate by that key.
3. **Canonical example:** `switch.pc_monitors` — ON branch (schemer + Sonos rich) / OFF branch (both off).
4. **`SYNC` only when ON and OFF are the same** (pure mirror: same targets, flipped state, no asymmetric rich payload or conditions). Otherwise use explicit ON/OFF branches.
5. **Event pairs merge too** (e.g. cinema / twilight / sauna ON↔OFF) under the same branched model.
6. **One-sided OK:** ON-only (or OFF-only) rules allowed; the absent edge simply does not match (e.g. `BuroCinemaPC_cosy`).

## 🚦 Decisions locked (Blocky — Phase B0 open items)

1. **Deny-list = D1 (role-aware)** — **Phase B7 supersession:**  
   * **Hard deny** (never in Explorer / soft-hide page / Blocky pickers; never commandable): **`switch.safety.safety_wisc_5v` (71040) only** — code fence, not in `deviceexplorer_hide`.  
   * **Soft hide** (picker/Explorer default off; “Show Explorer-hidden” / soft-hide page): **`deviceexplorer_hide`** only. Soft-hidden devices stay out of Blocky pickers unless the checkbox is on. **Exception:** eids already used in the **open rule** (same picker role) remain listed so that rule can still round-trip / edit.  
   * **Internal:** idx `90001` vent lock skipped in Explorer (unchanged).  
   * Everything else in live `device_metadata` (status ≠ removed) is allow (subject to role-aware picker filters).
2. **YAML branch keys = Y1:** trigger without edge state; top-level `on:` / `off:` each with optional `conditions` + `actions`. One-sided = omit the unused key. Event pairs use the same ON/OFF metaphor (mapped via curated event dictionary **pre-B10B**; after B10B cutover each edge is its own catalog UUID / rule).
3. **Event dropdown = E1 (historical):** curated allow-list with friendly labels (not full `EventType`). **Superseded by B10B+D+E:** pickers = `events:` UUID catalog (system + enabled user); labels = catalog names. Starter set / exclude toggles-telemetry was the pre-cutover E1 policy.
4. **Migration = M1 (conservative):** auto-merge only when exactly one ON + one OFF sibling share the same trigger `entity_id` (or mapped event-ON + event-OFF), and neither is `SYNC`. Do **not** auto-merge when multiple ON (or multiple OFF) rules share an eid — leave for operator / later Blocky UX. Known case today: `switch.living_special` (3 rules × OR ON|OFF, condition-discriminated).
5. **Engine = X1 first, then X2:** YAML stores Y1 `on:`/`off:`; loader **expands at load** to today’s flat ON/OFF rules for `AutomationEngine.evaluate` (preserve pair identity for CRUD round-trip). **Promote to native branch evaluate (X2)** once Blocky CRUD is stable — one in-memory rule, select branch from `new_state` / event; clearer logs; no shadow duplicates.
6. **CRUD identity = A:** persist stable per-rule `id` in YAML and use it for `PUT/DELETE`; never key mutations by `name` or list index.
7. **X1 pair round-trip = P1:** keep expansion metadata runtime-only (`<id>#on`, `<id>#off` or equivalent); never persist generated child rules back to YAML.
8. **Migration timing = MA:** run an explicit one-shot M1 migration step before enabling Blocky editing in production (review diff, then proceed).
9. **E1 dictionary scope = E1-v1 (historical):** start with approved schedule/scene/sauna trigger set used by automations; add new entries only by explicit review. **After B10B:** expand system seeds only by explicit review + code constants; operator scenes are **user** `events:` rows (no curated `SCENE_*` bus tokens).
10. **Hard-deny extras = H1:** keep hard-deny minimal in v1 (safety/SSR/internal classes only); avoid broader hard-deny expansion until real operator pain appears.
11. **UI scope = new page, admin-only:** Blocky is a dedicated admin route/page, not mixed into end-user pages.
12. **UI strategy = Option 2 (Hybrid):** keep the current JSON/form editor as fallback + debugging path, and add Blockly visual mode incrementally. Do not remove the fallback editor until Blockly covers all live rule patterns and proves stable — that exit gate is **Phase B9A**. **Supersession:** when B9A removes JSON, rewrite this bullet to “Blockly-only; JSON removed” (doc chore **O9** — locked as mechanical, not a product reopen).

## ✅ Final spec lock checklist (no code)

Mark each item `LOCKED` before implementation starts.

### A) Already locked

- [x] **Scope:** Blocky writes only `automations:` through B6C; soft-hide → **`deviceexplorer_hide`** in **Phase B7**; auto-off → **`auto_off_devices:`** in **Phase B8**.
- [x] **UI access:** new page, admin-only.
- [x] **Persistence model:** branched YAML (`on:` / `off:`), one-sided allowed.
- [x] **Pairing rule:** same trigger `entity_id` (device) or mapped event family (**pre-B10B**). **After B10B:** each schedule/sauna edge is its own catalog UUID + rule (families deleted).
- [x] **SYNC policy:** keep SYNC for pure mirrors; do not force split.
- [x] **Migration policy:** M1 conservative merge; skip `SYNC` and multi-ON/OFF cases (e.g. `living_special`).
- [x] **Engine rollout:** X1 expand-at-load first, then X2 native branch evaluate after CRUD is stable.
- [x] **CRUD identity model:** stable per-rule `id` (A), not `name` or list index.
- [x] **X1 round-trip:** runtime-only expansion metadata (P1), never persisted.
- [x] **Deny-list posture:** D1 + H1 (minimal hard-deny in v1).
- [x] **Events posture:** E1-v1 curated dictionary (**pre-B10B**). **Shipped:** `events:` UUID catalog (B10B+D+E).

### B) Spec precision — locked / open

#### B1 Rule `id` — LOCKED

- [x] Format = **UUIDv4**.
- [x] Generation = **backend-only** (create + MA backfill); PUT cannot change `id`; rename does not change `id`.
- [x] Missing `id` on legacy YAML = **MA must backfill before Blocky enable**; refuse to enable editor if any rule still lacks `id` after MA.
- [x] Duplicate `id` = **do not invent a new id**. Surface as **WARNING** (see note below); engine stays up; Blocky/API must not treat duplicates as healthy.
  - **Comment:** Agree with WARNING for **load / runtime / Admin Debug** (aligns with WanOS “log + skip, engine stays up”). For **Blocky save (POST/PUT)**, still **reject** a write that would create/keep a duplicate `id` — WARNING alone must not allow persisting known-bad identity.

#### B2 E1-v1 event dictionary — LOCKED (pre-B10B; superseded on cutover)

- [x] Scope = **C**: curated allow-list covering schedule / scene / sauna / **IR** even if some keys are unused today (not “live YAML only”).
- [x] UI labels = **friendly** (not raw keys).
- [x] Event-pair families = **explicit map** (no `_ON`/`_OFF` suffix inference).
- [x] Concrete table + usage + pair families approved (below).

**B10B cutover:** bus + Blockly use **`events:` UUIDs** (see § B10B). `SCENE_*` leave code → user events. Families / `SCHEDULE_WINDOW_EDGES` / `TWILIGHT_*` aliases **removed**. Table below = historical pre-cutover dictionary.

| Key | Label | Usage | After B10B |
|---|---|---|---|
| `BLINDS_OPEN_TRIGGER` | Blinds open | trigger-only | system seed UUID |
| `BLINDS_CLOSE_TRIGGER` | Blinds close | trigger-only | system seed UUID |
| `MORNING_ON_TRIGGER` | Morning lights on (clock) | trigger-only | system seed UUID |
| `SUNRISE_TRIGGER` | Morning lights off (astro sunrise) | trigger-only | system seed UUID |
| `SUNSET_TRIGGER` | Evening lights on (astro sunset) | trigger-only | system seed UUID |
| `EVENING_OFF_TRIGGER` | Evening lights off (clock) | trigger-only | system seed UUID |
| `SAUNA_ON` | Sauna ON | trigger-only | system seed UUID |
| `SAUNA_OFF` | Sauna OFF | trigger-only | system seed UUID |
| `IR_ON` | IR ON | trigger-only | system seed UUID |
| `IR_OFF` | IR OFF | trigger-only | system seed UUID |
| `SCENE_CINEMA_ON` | Cinema scene ON | trigger-only | **user** event (config only) |
| `SCENE_CINEMA_OFF` | Cinema scene OFF | trigger-only | **user** event (config only) |
| `SCENE_ALL_OFF` | All OFF scene | both | **user** event (config only) |
| `SCENE_GOCOSY` | Go Cosy scene | both | **user** event (config only) |
| `SCENE_GV_OFF` | Ground floor OFF | both | **user** event (config only) |
| `SCENE_VERDIEP1_OFF` | Floor 1 OFF | both | **user** event (config only) |
| `SCENE_VERDIEP2_OFF` | Floor 2 OFF | both | **user** event (config only) |

**Pre-B10B schedule window edges (`SCHEDULE_WINDOW_EDGES`) — deleted after B10B migrate:**

| Family | Enter edge | Exit edge |
|---|---|---|
| `blinds` | `BLINDS_OPEN_TRIGGER` | `BLINDS_CLOSE_TRIGGER` |
| `twilight_morning` | `MORNING_ON_TRIGGER` | `SUNRISE_TRIGGER` |
| `twilight_evening` | `SUNSET_TRIGGER` | `EVENING_OFF_TRIGGER` |
| `sauna` | `SAUNA_ON` | `SAUNA_OFF` |
| `ir` | `IR_ON` | `IR_OFF` |
| `cinema` | `SCENE_CINEMA_ON` | `SCENE_CINEMA_OFF` |

**Sunrise/sunset ≠ blinds:** `SUNRISE_TRIGGER` / `SUNSET_TRIGGER` are twilight-window edges at raw astronomical sunrise/sunset. `BLINDS_OPEN_TRIGGER` / `BLINDS_CLOSE_TRIGGER` use **clamped** times (`max(sunrise|sunset, earliest)` ± optional latest). Do not wire them interchangeably. **Admin model + post-B10E labels:** [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

**Pre-B10B legacy aliases (`TWILIGHT_*`) — removed in B10B (D1).** Canonical names only after cutover.

**Unpaired (do not auto-merge):** `SCENE_ALL_OFF`, `SCENE_GOCOSY`, `SCENE_GV_OFF`, `SCENE_VERDIEP1_OFF`, `SCENE_VERDIEP2_OFF`.

#### B3 X1 log/debug — LOCKED

- [x] Internal branch naming = **`<id>#on` / `<id>#off`** (runtime-only; never written to YAML).
- [x] Log format = **`rule=<id> branch=on|off|- name="<name>"`** (implemented in `AutomationEngine.format_rule_ref`; flat rules use `branch=-`).
- [x] Expansion order = **ON then OFF** (deterministic).
- [x] Missing branch = **A**: emit only the present branch (no empty stub). Absent edge simply does not match.

#### B4 MA operational runbook — LOCKED

**What “MA” means:** explicit one-shot operator-run M1 migration of `automations.auto.yaml` before enabling Blocky editing in production (not boot-auto, not first-save).

- [x] Who runs MA = **Johan on the Pi** (after Phase B1 Y1/X1 loader is deployed).
- [x] Dry-run = **mandatory** (`--dry-run` review, then separate `--write`).
- [x] Backup = **`automations.auto.yaml.bak.<UTC>`** next to the live file.
- [x] Rollback = restore `.bak.*` → reload → Admin Debug GREEN.
- [x] Timing vs code = **after** Phase B1 Y1/X1 loader can load branched YAML; **before** enabling Blocky UI in prod.

### C) MA migration — your steps (operator) ✅ COMPLETED ON PI

Run **once** on the Pi, **after** Phase B1 (Y1 loader) is deployed, **before** you enable the Blocky UI.

**Completion note:** migration helper was executed (`--dry-run` then `--write`), service restarted, Admin Debug check returned GREEN, and runtime logs confirmed branch ids (`<id>#on/#off`) and expected automation behavior.

1. Confirm WanOS on the Pi can load branched `on:` / `off:` rules (Phase B1 deployed).
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
- [x] MA section **C** completed by operator (after Phase B1 deploy).
- [x] This file is frozen as the **spec baseline** for Blocky v1 (implementation may start; MA still gated on Phase B1).

### E) Phase B5 operator runbook

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

Mark **Pass / Fail** after each smoke (historical checklist; Phase B5 DoD closed with operator smoke OK).

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

Phase B5 does **not** require a rollback rehearsal that depends on hand-edit + Admin reload.

#### E6 — X2 readiness checkpoint (2026-08-05)

**Decision: stay on X1** (expand-at-load to flat `#on`/`#off` engine rules).

**Rationale:** Phase B0–B5 closed on X1. **Revisit X2 in Phase B6A:** native **case** evaluate on unified schema v2 — not a separate forever-Y1 feature.

## 🧭 Next TODO (Option 2 roadmap)

1. **Phase B6A:** ✅ schema v2 + one-shot migrator + key order + preserve rich action fields on round-trip.
2. **Phase B6B:** ✅ one Blockly canvas + Cinema one list entry + OR-trigger + SYNC→ON/OFF on Pi; JSON power-user only.
3. **Phase B6C:** ✅ rich action UX — Hue preset XOR custom color (iro → bri/xy), blinds open % (incl. mid), Sonos/Onkyo volume, Sonos station, per-action rich; smoke OK Pi **2026-08-06**.
4. **Phase B7:** ✅ unified soft-hide — **`deviceexplorer_hide`**; `hiddendevices.html` + `/api/soft-hide`; hard-deny = 71040 (A); 71036 soft-hide + commandable + Blocky-selectable; migrator removed after cutover.
5. **Phase B8:** ✅ auto-off timers UI + engine — `auto_off_devices:`; `lightingautooff.html` + `/api/auto-off-timer`; migrator removed after cutover.
6. **Phase B9A:** Blockly parity + sensor/threshold/host-gauge authoring + **remove JSON** — **spec locked**.
7. **Phase B9B:** bathroom climate + **H12** hysteresis + **H4** condition and/or (+ drop trigger “when any of”) + **H5** notify (→ Gmail per `phaseE-gmail.md`); vent lock stays in hub — deferred.
8. **Phase B10A:** ✅ Blockly editor fixes (Hue picker-only a/b/c, toolbar Delete, dirty leave; Hue/blinds rich survive save→reload); smoke OK Pi **2026-08-09**.
9. **Phase B10C:** ✅ soft-hide action device picker (exclusive + sticky load); smoke OK Pi **2026-08-09**.
10. **Phase B10B+D:** `events:` catalog (UUID-on-bus) + per-rule enable + family/`SCENE_*` cutover + unique rule names — ✅ **DONE 2026-08-10** (Pi migrate 7A + smoke/GREEN + migrator deleted).
11. **Phase B10D:** unique rule names (case-insensitive; Blocky + API) — **ships inside B10B+D** (enforced in code; Pi smoke ✅ **2026-08-10**).
12. **Phase B10E:** Automations **Library** (UE/UR/SE/SR/D + C), New user event form, When/Fire user vs system, schedule display names, wipe Sunset listeners — ✅ **DONE 2026-08-10**.
13. **Phase B10F:** Automations UX polish (save chrome, connecting, library keys, schedule fire-time status) — ✅ **Done 2026-08-11**.
14. **Phase B11–B18:** multi-flow; folder/tag; IF/ELSE; remaining HA; demote schedule; bus UUID; Sauna/IR assess; sauna session_end clamp — see § B11–B18.

## ✅ Definition of Done (Option 2)

Use this as strict phase gates. Do not mark a phase complete unless all items are checked.

### Phase B3 DoD — Semantic pickers + policy enforcement ✅

- [x] **Device picker policy:** D1 is enforced in UI and backend-facing payload shaping:
  - hard-deny eids never appear/selectable,
  - soft-hidden eids are hidden by default and visible only via “Show Explorer-hidden devices”,
  - eids already used by the **open rule** (same picker role) remain listed so that rule can edit/round-trip.
- [x] **Event picker policy:** E1-v1 curated events are rendered with friendly labels (no raw key-only UX by default). **Superseded by B10B+D+E:** pickers = `events:` UUID catalog; labels = catalog names.
- [x] **Event family behavior:** explicit pair families are respected for branched event trigger UX (no suffix heuristics). **Superseded by B10B:** families deleted; each edge is its own catalog UUID / rule.
- [x] **No free-text dependency for normal flow:** standard rule authoring works end-to-end without typing raw `entity_id` or raw event keys (flat fallback mode remains available by design).
- [x] **Validation UX:** blocked selections show clear user feedback (why blocked + what to do).
- [x] **Compatibility:** existing rules load/edit/save without semantic drift.
- [x] **Regression smoke (operator run on Pi):** create/edit/delete one branched device rule, one branched event-family rule, one flat SYNC rule — **OK**.

### Phase B4 DoD — Blockly visual mode (hybrid) ✅

- [x] **Second editor mode exists:** Blockly canvas mode is available alongside the current JSON/form editor.
- [x] **Fallback preserved:** JSON/form editor remains fully functional and selectable at all times.
- [x] **Round-trip safety:** Blockly -> saved YAML -> reload -> reopened in Blockly preserves semantics for:
  - one-sided ON-only/OFF-only,
  - full ON+OFF branched rules,
  - event-family branched rules,
  - flat SYNC/multi-trigger rules (either editable or clearly marked fallback-only).
- [x] **Mode boundary clarity:** UI clearly indicates when a rule must be edited in fallback mode (if Blockly cannot represent it yet).
- [x] **No schema mutation (pre-B6A):** persisted shape remained Y1 + flat compatible through Phase B4–5 (no ad-hoc schema). Phase **B6A** replaces this baseline with unified schema v2 by design.
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

### Phase B6A DoD — Unified schema v2 + migrator ✅

- [x] **Schema v2 locked & implemented:** trigger + ordered `cases`; API writes v2 only after deploy.
- [x] **Migrator on Pi (no lazy converge):** dry-run → backup → `--write`; Cinema pair merged; Admin Debug GREEN + clean boot (2026-08-05).
- [x] **Engine:** expand v2 cases → flat evaluate (interim); case labels in runtime ids (`#on`/`#off`/`#cN`).
- [x] **YAML key order:** **`name` → body → `id` last** on write/migrate.
- [x] **Rich fields preserved:** Blockly apply keeps preset/volume/station/bri/xy from prior editor state; API/v2 dump keeps them.

### Phase B6B DoD — One Blockly canvas + list unity ✅

- [x] **One Blockly canvas:** all production rules use if/else-if/else on v2; no branched-vs-flat mode split; JSON-only is opt-in.
- [x] **One list entry:** Cinema OFF (merged) once in the list; one flow; dashboard `scene:` behavior unchanged where applicable.
- [x] **Multi-trigger OR:** e.g. `KeukenLivingEetk_EetkHue` editable in Blockly without JSON.
- [x] **Round-trip (Pi smoke):** ex-Y1, ex-flat/ex-mirror, merged Cinema — OK (2026-08-05).

### Phase B6C DoD — Rich device action UX ✅

**Operator smoke:** ✅ OK on Pi (**2026-08-06**).

- [x] **Hue preset + custom color:** Blockly can set/show `preset` (display name from `hue_presets`) **or** custom color via Explorer iro wheel → `bri` (1–100 UI) / `xy` — **not both**; OFF clears color rows; wheel Apply/Cancel close cleanly; round-trip.
- [x] **Blinds open % (incl. mid):** operator sets open percentage (not only 0/100); stored = closed % (`100 − open`); Blocky UI = open %, Explorer UI = closed %, same storage.
- [x] **Sonos volume + station:** editable in Blocky; volume **0–`max_volume`** (`config.sonos.max_volume`, currently 70); stations from `state.system.sonos_stations`; sufficient for live rules such as `pc_monitors`.
- [x] **Onkyo volume:** editable in Blocky; volume **0–`max_volume`** (device meta / `config.onkyo.max_volume`, currently 60); no station field.
- [x] **Per-action rich:** two actions on the same `entity_id` with different preset/volume/etc. round-trip independently (no `richByEntity` collision); uniqueness scoped by case so ON/OFF cases do not fight.
- [x] **Stations exposed:** Sonos station keys on `/api/state` as `system.sonos_stations`.

### Phase B7 DoD — Unified soft-hide UI ✅

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

### Phase B8 DoD — Auto-off timers UI + engine ✅

- [x] **Cutover:** `lighting:` → `auto_off_devices:`; `managed_lights` → `managed_auto_off`; migrator `--dry-run` / `--write` on Pi then **removed**; runtime does not read old keys.
- [x] **Engine:** auto-off only for eids in `managed_auto_off`; delay = per-device → `default_pertype_auto_off_minutes[type]` → `default_auto_off_minutes`.
- [x] **Admin entry:** System Commands → **“Auto-off timers”** (under Hidden Devices) → `lightingautooff.html` (admin-only; no shell nav).
- [x] **API:** `GET` + full-replace `PUT /api/auto-off-timer`; surgical write of **`auto_off_devices:`** only; hot-reload on save; reject unresolved / orphan / ineligible / bad type keys; enforce `auto_off_delays` ⊆ `managed_auto_off`; sorted unique lists/maps; minutes 1–720.
- [x] **UI:** general + type rows (`switch` / `light` / `speaker`) + eligible device list (checkbox + **Effective** minutes); blank = inherit (muted italic resolved); typed = per-device pin; uncheck clears delay; soft-hide All / Hidden / Non-hidden; **Auto-off ON / OFF / All** membership filter; sort Name / Type / Effective (resolved; unmanaged last); 71040 omitted; vents + speakers eligible.
- [x] **Eligibility:** denylist + device extras enforced in inventory and on PUT; migrator stripped ineligible leftovers (kept vents).
- [x] **Comments:** block rewritten without preserving hand comments.
- [x] **Docs:** `phaseB-blocky.md` Phase B8 closed + `docs/reference.md` API line.
- [x] **Admin Debug GREEN** after cutover / representative saves.
- [x] **Pi smoke:** migrator/rename; Auto-off timers page; general / type / per-device Effective pin; blank inherit (muted); uncheck clears delay; membership Auto-off ON/OFF filter; ON→timer uses expected delay; Debug GREEN — **OK on Pi (2026-08-08)** (Effective-column UX follow-up after that date).

### Phase B9A DoD — Blockly parity + sensors/thresholds + remove JSON

- [ ] **Live-rule audit:** every production rule opens / edits / saves in Blockly with no semantic drift; written gap list.
- [ ] **Post-audit note:** confirm no pressure to pull H\* into B9A (H4/H5/H12 wait for B9B).
- [ ] **Per-action rich:** verify B6C round-trip independence.
- [ ] **Silent-loss B+C:** unknown-legal keys preserved; Save blocked when a non-preservable drop would occur.
- [ ] **Sensor + host-gauge pickers:** When + if; motion trigger-only; hard-deny blocked; discrete dropdown / numeric `FieldNumber`.
- [ ] **Sauna session condition:** Blockly + engine can test **sauna active** (`state.sauna.active`) as a condition (not only `device_state`). Needed for rules such as **sauna hue physical** (below).
- [ ] **Example / smoke rule — sauna hue physical:** trigger `switch.sauna_hue_physical` (**71035**) on **any** change (ON or OFF edge); if sauna **on** → if `hue.group.sauna_hue` (**51002**) already on → no-op, else **OFF** sauna hue + `switch.sauna_zoutlamp` (**72004**); if sauna **off** → if hue already on → **OFF** hue + zoutlamp, else **ON** hue + zoutlamp. (Not authorable today: no sauna-session condition.)
- [ ] **Thresholds:** ops `== != > >= < <=` in engine **and** Blockly; no hysteresis; `temp_hum` → separate temperature / humidity; numeric When = edge-cross, discrete = any change.
- [ ] **FORCE:** all engine-honored origins.
- [ ] **Events:** pickable from `events:` (B10B); `SAUNA_SETPOINT_REACHED` present.
- [ ] **JSON removed** in same PR as parity green; decision #12 prose updated to Blockly-only.
- [ ] **Pi smoke:** operator broad smoke + Admin Debug GREEN.
- [ ] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

### Phase B9B DoD — Bathroom climate + H4 / H5 / H12

- [x] **Bathroom feasibility:** write-up under Phase B9B (**2026-08-08**).
- [ ] **H12:** generic hysteresis / dual-threshold authorable in Blockly + engine.
- [ ] **Bathroom:** humidity ON/OFF band via H12; hardcoded climate paths retired; **vent min-runtime lock remains in hub**.
- [ ] **`bathroom1.vent_*` cutover** decided and applied.
- [ ] **Sweeper** climate recovery: keep-thin or drop — explicit at impl.
- [ ] **H4:** condition AND/OR groups in schema + Blockly + engine; remove trigger “when any of”; multi-match via condition and/or.
- [ ] **H5 alert:** Blockly notify/alert action (UI path).
- [ ] **H5 Gmail:** action emits `EMAIL_REQUESTED` only; aligns with `docs/todo/phaseE-gmail.md` (outbox/OAuth may land in parallel; email DoD can trail alert if needed).
- [ ] Hot-water/sauna-grace still out unless reopened.
- [ ] Pi smoke + Admin Debug GREEN.
- [ ] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

### Phase B10A — Blockly editor fixes ✅ DONE

**Origin:** intermediary Blocky slice (now in this file). FE-only; no schema/migrator.

**Operator smoke:** ✅ OK on Pi (**2026-08-09**).

| ID | Issue | Intent (locked) |
|---|---|---|
| **Hue a** | Custom color: hex + dead `-` dropdown | **Picker only** — swatch on same row as color mode; re-select **custom color** opens wheel (no extra “edit color” row) |
| **Hue b** | Blinds → Hue leaves Position; no color UI | Full STATE/rich rebuild on **any** device-type change; blinds→Hue defaults **ON**; Hue→blinds defaults **OPEN** |
| **Hue c** | Save/load reopens color picker | Restore custom **without** opening modal |
| **Delete** | Tablet: trash/select delete broken | Toolbar **Delete** next to Full screen; **disabled** when nothing selected; **remove** trashcan; Del/Backspace stay on desktop; update help copy |
| **Dirty** | Canvas edits never set dirty (name OK) | Blockly workspace edits must set `editorDirty`; leave modal on select/New/Reset/shell/logout; `beforeunload` when dirty; clean after save/discard |

#### Phase B10A DoD

- [x] Hue a/b/c fixed on Pi smoke (picker-only custom; type-switch rebuild; no modal on restore).
- [x] Toolbar Delete works (incl. tablet); trashcan removed; Del/Backspace OK on desktop; help text updated.
- [x] Canvas edits show **Unsaved changes**; dirty leave prompts on all leave paths; clean after save/discard.
- [x] Hue named preset / custom color and blinds CLOSED / position % survive save→reload (dropdown option cache + load microtask).
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (re-audit with B10B+D+E close-out pass).

---

### Phase B10C — Soft-hide device picker ✅ DONE

**Origin:** operator report **2026-08-09** (rule **`all off gv`**). B7/B3 picker regression — not folded into B9\*. FE action-device dropdown only; YAML not corrupted.

**Operator smoke:** ✅ OK on Pi (**2026-08-09**).

#### Locked intent (exclusive Hidden, sticky current)

Blockly **HIDDEN** toggle filters **action** `set device` dropdowns only (When-device / condition out of scope for this DoD):

| HIDDEN | Dropdown contents |
|---|---|
| **OFF** | Device(s) **already configured on that block** (even if soft-hidden) **+ all non-hidden** devices |
| **ON** | Device(s) **already configured on that block** (even if non-hidden) **+ all soft-hidden** devices |

Hard-deny (**71040**) never appears. Not inclusive “show everything when ON”.

#### Failure fixed

HIDDEN ON → leave rule → re-open **`all off gv`** showed **`53?`** on non-hidden actions (mid-load sticky used partial workspace → FieldDropdown snapped to `options[0]`). Soft-hidden actions stayed correct.

**Shipped:** sticky during `BlockyRT.loading` uses full `ruleJson` action eids; load pass re-asserts ENTITY. (Cache bust: use current `blocky.js?v=` from deploy; smoke used `?v≥4.56`.)

#### Phase B10C DoD

- [x] HIDDEN OFF/ON match the table above for **action** device pickers (sticky current + exclusive catalog).
- [x] Repro path: HIDDEN ON → leave rule → re-open **`all off gv`** → labels stay correct (no `53?` / blank / snap).
- [x] Untouched save does not change action `entity_id`s; Pi smoke both toggle states + leave/reopen.
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (re-audit with B10B+D+E close-out pass).

---

### Phase B10B+D — Events catalog + rule enable + unique rule names ✅ DONE (2026-08-10)

**Origin:** intermediary split → Blocky. **Prereqs:** B10A ✅ + B10C ✅ (Pi smoke **2026-08-09**). May run before/parallel/after B9A — not folded into B9A/B9B.

**Delivery:** one ship (**B10B+D**). Letter DoDs below stay separate for checklist clarity; **B10D uniqueness is enforced from the first live API/Blocky save** in this delivery (not a follow-up PR). Treat as **one phase** in sequence/pipeline.

**Operator smoke:** ✅ OK on Pi (**2026-08-10**) — combined B10B+D+E; Admin Debug **GREEN**; kiosk + B10D name smoke.

**Status (2026-08-10):** Implementation + **Pi cutover 7A** (migrator write) done. **B10E Automations Library UX** shipped in the same code pass (UE/UR/SE/SR/D). Kiosk UUID paste done. Combined operator smoke (B10B+D+E) + Admin Debug **GREEN** + kiosk ✅ **2026-08-10**. Migrator + D1 soak leftovers deleted (**2026-08-10** close-out). **Shipped intentional:** `HUB_STATE_CHANGED` not pickable; entity-registry check skips history idxs ≥900000. **Non-DoD follow-up:** Blockly FS save banners.

**Relationship to B10E (locked 2026-08-10):** B10B’s **core** (UUID `events:` catalog, bus tokens, `/api/events`, family/`SCENE_*` cutover, rule `enabled`, B10D names) stays. B10E **revises the operator-facing Automations UX and some product rules** that B10B first shipped (list chrome, Event flags panel, system `show_on_dashboard`, fire-picker allowlist, schedule **display** names, SE view-only / SR name bind). See § B10E “Supersedes from B10B”.

**One ship ✅ complete 2026-08-10:** **B10B + B10D + B10E** — code, Pi smoke/GREEN/kiosk, migrator delete.

**Known non-DoD follow-up:** soft-hidden doors (`sensor.door.*` on `deviceexplorer_hide`) only appear in “if device” when Hidden ON — optional always-merge for condition/trigger.

**Supersedes (after cutover):** B2 curated `SCENE_*` strings, Blockly event-family triggers, `SCHEDULE_WINDOW_EDGES` / `EVENT_FAMILY_TO_ON_OFF`, `TWILIGHT_*` aliases, `available_scenes` / `rule.scene`, bus tokens `USER_*` / `SCENE_*` for operator scenes.

#### Locked operator decisions (2026-08-10)

| # | Decision |
|---|---|
| Cutover | **7A** — stop service → run migrator on YAML → deploy/start new code → smoke → remove migrator script |
| System seed UUIDs | Generate + lock in code constants (identity authority) |
| User event UUIDs | Random at migrate; **UI shows name only** (UUID still in YAML / API wire / kiosk source) |
| User event names | Migrator copies from matching `scene: true` **rule** `name` (not E1 labels) |
| Family splits | `Blinds open` / `Blinds close`; morning/evening lights edges (see seed names); `Sauna ON` / `Sauna OFF` — new rule ids; old family rules retired |
| Live families | Confirmed in YAML: only `blinds`, `twilight_morning`, `sauna` (no cinema/ir/twilight_evening family rules) |
| Cinema | Not a family migrate; `SCENE_CINEMA_*` → user events; manual only |
| Kiosk (K1) | Hardcoded literal UUIDs in `kiosk.html` — **in B10B DoD** |
| `/api/events` | **8A** — automations twin (GET list + POST/PUT/DELETE); **B10E:** system PUT rejects dashboard-on (system never on Explorer); user confirm coerced off when dashboard off |
| Internals | Non-catalog bus stays `EventType` strings this phase; full-bus UUID → **B16** in [`pipeline.md`](pipeline.md) / § B16 |
| Pre-clean | Duplicate `test` rules removed (repo + Pi); B10D “no current duplicates” holds |
| System seed **names** | Full table in § B10B+D — **approved 2026-08-10**; schedule display renames **shipped in B10E** (**2026-08-10**) — [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md) |

---

#### Model — pure signal + rules

| Piece | Role |
|---|---|
| **Event** (`events:` row) | Named bus signal + flags. **No** conditions or actions. |
| **Automation rule** | `trigger` (event **UUID** or device) + `cases` — **one schema**. Simple = empty conditions; branched = conditions (e.g. dark/light). |
| **Engine** | On bus emit of event UUID, runs matching **enabled** rules. |

**Bus token = event `id` (UUID only).** UI shows **name** only. No readable `USER_*` / `SCENE_*` on the bus after cutover.

---

#### Catalog — one table `events:`

In `automations.auto.yaml` (alongside `automations`, soft-hide, auto-off):

```yaml
events:
  - id: <uuid>                 # bus token; immutable
    name: "Cinema on"          # UI; unique trim+case-insensitive
    origin: user               # system | user
    show_on_dashboard: false
    require_confirmation: false
    enabled: true              # user only; system always true / not editable
```

| | **system** | **user** |
|---|---|---|
| Create / delete from Blockly | No | Yes (delete rules below) |
| **name** editable | No (constants) | Yes |
| **require_confirmation** editable | No (always false) | Yes — dashboard taps only; **B10E:** usable only with `show_on_dashboard`; clearing dashboard **must** clear confirm |
| **enabled** editable | **No** (always on) | Yes — false ⇒ hide from dashboard + pickers |
| **show_on_dashboard** editable | **No** (always false after B10E) | Yes |

**Y1 — system seeds:** Fixed UUID + name in **code constants** (identity authority). Boot/merge into YAML: insert missing ids; on existing rows force name/origin/confirm/enabled from constants; **B10E:** force `show_on_dashboard: false` (system never on Explorer).

**API `/api/events` (8A):** Admin. Surgical write + `CONFIG_RELOAD_REQUESTED`.

* `GET` → `{ "events": [ …rows ] }`
* `POST` → create **user** row (server assigns UUID); body: `name`, `show_on_dashboard`, `require_confirmation`, `enabled` (default true)
* `PUT` → replace by `id` — **user:** those fields; **system (B10E):** no operator field edits — identity forced from constants; `show_on_dashboard` always false (**reject** attempts to set true); other system fields not writable from API
* `DELETE` → `{ "id" }` — **user** only; delete guards → 409 with reason
* Errors: 400 validate / name clash, 403 non-admin, 404 missing, 409 delete blocked / duplicate id

**Names:** unique among all events (trim + case-insensitive), same spirit as B10D for rules.

**Picker sort:** **user** events first (alpha by name), then **system** (alpha by name). Labels: catalog name only (no `system:` prefix — badges mark origin).

---

#### System seed names — **approved** (2026-08-10; schedule display renames locked for **B10E**)

UUIDs: locked in `core/event_catalog.py`. **Name** = Blockly / catalog display string (Y1 boot merge forces system names from constants). Schedule window model: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

| EventType key | `name` | Notes |
|---|---|---|
| `BLINDS_OPEN_TRIGGER` | Blinds open | Unchanged; blinds window START |
| `BLINDS_CLOSE_TRIGGER` | Blinds close | Unchanged; blinds window STOP |
| `MORNING_ON_TRIGGER` | **Morning lights on** | Was “Morning on”; **B10E** catalog/UI rename (UUID unchanged) |
| `SUNRISE_TRIGGER` | **Morning lights off** | Was “Sunrise”; **B10E** rename |
| `SUNSET_TRIGGER` | **Evening lights on** | Was “Sunset”; **B10E** rename |
| `EVENING_OFF_TRIGGER` | **Evening lights off** | Was “Evening off”; **B10E** rename |
| `SAUNA_ON` | Sauna ON | E1 |
| `SAUNA_OFF` | Sauna OFF | E1 |
| `IR_ON` | IR ON | E1 |
| `IR_OFF` | IR OFF | E1 |
| `SAUNA_SETPOINT_CHANGED` | Sauna setpoint changed | |
| `SAUNA_MODULATION_UPDATED` | Sauna modulation updated | |
| `SAUNA_SETPOINT_REACHED` | Sauna setpoint reached | Seeded even if emit lands later / B9A |
| `SAUNA_HOLD` | Sauna hold | |
| `SAUNA_TIMER_EXPIRED` | Sauna timer expired | |
| `SAUNA_HOLD_TOGGLED` | Sauna hold toggled | |
| `SAUNA_TIMER_ADJUSTED` | Sauna timer adjusted | |
| `SAUNA_DOOR_GRACE_EXPIRED` | Sauna paused (door open) | Door open too long while sauna active → heaters pause |
| `VENT_WAIT_EXPIRED` | Sauna ventilator run start | After `SAUNA_OFF` delay: vent → ON, start run timer |
| `VENT_RUN_EXPIRED` | Sauna ventilator run expired | Vent run finished → vent OFF |
| `IR_MODULATION_UPDATED` | IR modulation updated | |
| `TEMP_UPDATED` | Temperature updated | Not SHT-only (SHT + Z-Wave + OWM climate + lab/sim) |
| `HUMIDITY_UPDATED` | Humidity updated | Same sources as temp |
| `POWER_UPDATED` | Power updated | |
| `WATER_PULSE` | Water pulse | |
| `KWH_PULSE` | kWh pulse | |
| `DOOR_CHANGED` | Door state changed | |
| `HUB_STATE_CHANGED` | Hub state changed | Seeded / on bus; **not pickable** in Blockly |
| `EXTERNAL_WEATHER_UPDATED` → **`SUNRISE_SUNSET_UPDATE`** (**B10E** ✅) | Sunrise/sunset update | **Shipped:** bus key renamed (UUID unchanged). Sun times only → env schedule; not climate. Legacy bus alias still mapped in catalog/handler until soak ends. See [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md) |
| `SENSOR_ERROR` | Sensor error | |

**Not seeded / not pickable:**

| EventType key | Status |
|---|---|
| `IR_TIMER_EXPIRED` | Internal only — only `dispatch(IR_OFF)`; rules use **IR OFF** |
| `HUB_STATE_CHANGED` | Catalog + bus yes; Blockly pickers exclude (`NON_PICKABLE_SYSTEM_UUIDS`) — high-chatter telemetry |
| `LIGHTING_STATE_CHANGED` | **Removed** from codebase (enum + handler + registry); lights use `HUB_STATE_CHANGED` |

(`SAUNA_SETPOINT_REACHED` remains seeded even if emit lands later / B9A.)

**Not in catalog (internal bus only):** timers/infra (incl. `IR_TIMER_EXPIRED`), integration toggles, alerts. **`EMAIL_REQUESTED`:** wait for phase **E**.

**User events (config only — leave code):** migrate from live `scene: true` rules / SCENE_* keys:

`SCENE_CINEMA_ON`, `SCENE_CINEMA_OFF`, `SCENE_ALL_OFF`, `SCENE_GOCOSY`, `SCENE_GV_OFF`, `SCENE_VERDIEP1_OFF`, `SCENE_VERDIEP2_OFF`

Migrator: new UUID per key; **name / confirm / dashboard** from the matching `scene: true` rule; dedupe by old event key.

**Core emitters** for system pickables publish the **fixed UUID** (handlers registered on that UUID).

---

#### Blockly / rules UX

* **Create user event:** **B10E** — **New user event** form (not via rule flags); name required; Appear on explorer (± confirm only usable if explorer on; turning explorer off **forces confirm off**). Save = user `events` row only.  
* **Pickers:** trigger + fire-action = pickable catalog (system + enabled user). Labels: catalog name only (no `system:` prefix). System always listed except `NON_PICKABLE_SYSTEM_UUIDS` (currently `HUB_STATE_CHANGED`). **B10E:** split When/Fire user vs system; fire allowlist for unused system; When-system trigger lists unused SEs only (+ current when editing SR).  
* **Reuse:** same event id as trigger and as fire-action. **No** confirm on fire-action (confirm = Explorer GO only).
* **Fire system UUID from a rule:** allowed.
* **Event-triggered cases:** drop useless “if” chrome; **keep conditions** (empty = always).
* **Edit event flags:** when viewing a rule whose trigger is that event (Blockly-only path for user CRUD).
* **Per-rule `enabled`:** default `true`; missing → true. UI: Automations **list + editor** (L+E). Engine skips disabled rules. Global `automations_enabled` unchanged.
* **Orphan / unused user event** (not dashboard, no rule trigger/fire refs): left-list rule row **muted amber**; message when viewing. Delete allowed only when unused + not dashboard (confirm). **Block delete** if any rule uses event as trigger or fire-action → modal. Dashboard-shown ⇒ not deletable.
* **Unique rule names (B10D):** trim + case-insensitive; enforce on Blocky Save + API create/update from day one of this delivery.

---

#### Dashboard

State field rename: `available_scenes` → **`dashboard_events`**.

Show button iff: `show_on_dashboard` ∧ (user ⇒ `enabled`) ∧ **≥1 enabled rule** listens to that event id.  
Payload: `{ id, name, require_confirmation }`. Explorer uses this list — **no** parallel `scene.*` device rows after cutover.

---

#### Re-entrancy

* Evaluating rule = **depth 1**.
* Fire-action that emits an event starts **depth 2**.
* At depth 2, further event-emitting fire-actions = **no-op** (log once).
* Sibling fires (e.g. ALL OFF → three floor events) all at depth 2 = OK. Floor rules must not fire further events.

Cinema ON/OFF: **manual only** (no clock today; unchanged).

---

#### Families — remove (this phase)

* Delete Blockly `b_trig_family` / family UI.
* Delete `SCHEDULE_WINDOW_EDGES` / `EVENT_FAMILY_TO_ON_OFF` from code after migration — ✅ **2026-08-10** (with migrator delete).
* **D1:** remove `TWILIGHT_*` enum members, `SCHEDULE_EVENT_ALIASES` / canonicalize shim, Blockly labels, docs aliases — ✅ **2026-08-10**.
* **Migrate** live family rules → **two rules** (one per concrete edge); new rule ids; old retired:

| Old rule | Family | New rule names |
|---|---|---|
| `Blinds Open/Close` | `blinds` | `Blinds open` + `Blinds close` |
| `Kerstverlichting voor & achter aan 's morgens` | `twilight_morning` | `Morning lights on` + `Morning lights off` (was Morning on + Sunrise) |
| `Sauna ON/OFF` | `sauna` | `Sauna ON` + `Sauna OFF` |

Env scheduler still emits concrete schedule edges (then as UUIDs); it does not use family sugar.

---

#### Kiosk (K1)

Hardcoded page OK. Buttons dispatch **literal event UUIDs** (Cinema on/off, Verdiep1 off, …) after migrate — migrator prints ids for paste into `kiosk.html`. **Updating `kiosk.html` is in DoD.** No `SCENE_*` strings in code.

---

#### History

Synthetic series keyed by **event UUID** (not name, not old `crc32(SCENE_*)`). Migrator remaps old scene idxs → new; **no** long dual-read. UI resolves id → current name.

---

#### Migrator (one-shot, then remove — B7/B8 style)

Cutover order **7A:** stop → migrate YAML → start new code → smoke → remove script.

1. Seed/merge system `events` from constants (Y1).  
2. Create **user** `events` for seven SCENE_* (new UUIDs; copy name / confirm / dashboard from `scene: true` rules; **dedupe by old event key**).  
3. Rewrite all rule triggers/actions from strings/families → **UUIDs**.  
4. Split family rules → two rules (names in table above).  
5. Strip `scene` / `require_confirmation` from rules; add `enabled: true` where missing.  
6. History idx remap; retire `entity_registry` `scene.*` path / rows as needed.  
7. Drop family maps, `TWILIGHT_*` aliases, curated SCENE allowlists.  
8. Print kiosk UUIDs for K1 paste into `kiosk.html`.

No grandfathering of `SCENE_*` bus strings.

---

#### Phase B10B DoD

- [x] `events:` catalog + `/api/events` (8A); Y1 boot merge; system/user flag rules honored.
- [x] ID-on-bus; Blockly trigger/fire pickers (user then system, alpha within; catalog-name labels); no family trigger; no “if” chrome on event cases (conditions kept). `HUB_STATE_CHANGED` seeded but **not pickable**.
- [x] Dashboard from `dashboard_events` (enabled∧show∧≥1 enabled listener); no `rule.scene` / no `SCENE_*` in code.
- [x] Migrator: SCENE_* → user events; families → two rules; history remap; strip scene flags; kiosk UUID note; **`kiosk.html` hardcoded UUIDs** (Pi map). **Script remove** ✅ **2026-08-10** (after soak; also `helpers/b10b_cutover_map.json` + D1 aliases / `SCHEDULE_WINDOW_EDGES`).
- [x] Per-rule `enabled` (engine + list + editor); user-event enable/disable + delete guards + orphan tint/message.
- [x] Re-entrancy depth 2 (code); **Pi smoke** (create user event, dashboard fire, fire-from-action, nested ALL OFF, disable rule, system dashboard flag); Admin Debug GREEN; kiosk Cinema/Verdiep1 via UUID — ✅ **2026-08-10**.
- [x] System seed **names** match the approved constants table.

#### Phase B10D DoD (same delivery; checks from the start)

- [x] Create/rename colliding with another rule (trim + case-insensitive) blocked in Blocky + API (code).
- [x] Update same rule keeping its name OK; **Pi smoke** collide + rename-away — ✅ **2026-08-10**.
- [x] No pre-existing duplicate rule names on Pi (confirmed after `test` rule removal).

#### Operator smoke checklist (B10B+D close-out)

Run on **Pi** after deploying latest (`entity_registry_check` skip ≥900000, Blocky `?v≥4.56`). **Operator confirmed Pass 2026-08-10** (items 1–12, incl. soak + migrator delete).

1. **Boot / Debug** — clean boot (no `scene.*` birth storm); Admin Debug entity-registry **GREEN** (synthetic history count OK, not ERROR). ✅
2. **Kiosk** — Cinema on/off + Verdiep1 off fire via UUID (confirm listeners run). ✅
3. **Create user event** — **B10E:** **New user event** → form → name → Save → **UE** in Library + picker (user section) + optional Appear on explorer. (Historical B10B path “New rule → Create new user event” superseded.) ✅
4. **Dashboard fire** — **B10E:** `show_on_dashboard` **user** event only (system never on Explorer); tap fires; confirm gate if set (dashboard only). ✅
5. **Fire-from-action** — rule A fires event UUID → rule B trigger; no confirm on fire-action. ✅
6. **Nested / re-entrancy** — ALL OFF (or similar) that fires another catalog event; depth-2 OK, no loop blow-up. ✅
7. **Rule enabled** — disable rule → event does not run it; re-enable → runs. ✅
8. **System dashboard flag** — **superseded by B10E:** system events must **never** be on dashboard (clear YAML + reject API). Smoke instead: confirm no system row in `dashboard_events`. ✅
9. **B10D names** — Save with duplicate name (case/trim) rejected; rename-away then collide OK; same-id keep name OK. ✅
10. **Pickers** — Hub state changed **absent**; catalog-name labels (no `system:` prefix); user events listed above system. (**B10E** further restricts **fire** picker for unused system except Sauna/IR ON/OFF; When-system = unused SEs only.) ✅
11. **Family gone** — no family trigger block; Blinds open/close, Morning/Evening lights edges, Sauna ON/OFF as separate rules. ✅
12. **Delete migrator** — remove `helpers/migrate_events_b10b.py` (+ cutover map / D1 soak leftovers) from tree — ✅ **2026-08-10**.

*(Combined Pi smoke for B10B+D+E lives under § B10E DoD after the one-ship delivery.)*

#### After B10B+D (not DoD)

Pointers only — detail under § B10F / § B11–B18:

* **B10F** — Automations UX polish — ✅ **Done 2026-08-11** (does not reopen B10E DoD).
* **C10** — Explorer/History polish — [`phaseC-shell.md`](phaseC-shell.md); **next** in sequence.
* **G6** — Scoped `CONFIG_RELOAD` after CRUD (no bridge thrash) — [`phaseG-integrations.md`](phaseG-integrations.md); not B10F.
* **G7** — Integration log prefixes (`[Onkyo]` parity) — [`phaseG-integrations.md`](phaseG-integrations.md); not B10F.
* **B11** — Multi-flow in one Blockly page.
* **B12** — Rule-list folder/tag.
* **`EMAIL_REQUESTED`:** seed with phase **E** (not B10B).
* **B15** — Demote schedule edges → user origin.
* **B16** — Full-bus UUID for internal `EventType`s.
* **B17** — Sauna/IR hardcoded → automation (assess only).
* **B18** — Sauna `session_end_time` ≤ `absolute_cutoff_unix`.

---

### Phase B10D — Unique rule names (ships inside B10B+D)

**Origin:** operator request **2026-08-09**. Spec kept here for the uniqueness contract; **implementation is not a separate ship** — see § B10B+D.

* Automation **rule `name`** must be unique among all rules.
* Compare: **trim** + **case-insensitive** (e.g. `All off` ≡ `all off`).
* Enforce on **Blocky Save** and **API** create/update (reject with clear error). Same `id` update may keep its own name.
* No name-uniqueness migrator: duplicates cleared before cutover (`test` rules removed).

*(DoD checkboxes live under § B10B+D.)*

---

### Phase B10E — Automations list UX + schedule display names ✅ DONE (2026-08-10)

**Origin:** operator list model (D/S/U/C) + schedule naming approval **2026-08-10**.  
**Delivery:** **one ship with B10B+D** — code + **Pi smoke** ✅ **2026-08-10**; migrator delete ✅ **2026-08-10**.  
**Detail (schedule):** [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

**Operator smoke:** ✅ OK on Pi (**2026-08-10**).

**Supersedes** the earlier thin B10E “sort only” (`event → dashboard → other`).

#### Supersedes from B10B (UX / product rules — core catalog stays)

| B10B shipped | B10E target |
|---|---|
| Event flags panel on rules | **Remove**; **UE** rows use a form (not Blockly); no dash/confirm on normal rules |
| Create user event via rule checkbox | Separate **New user event** (next to **New rule**) |
| System may `show_on_dashboard` | System **never** on dashboard (API reject + clear YAML) |
| List = “rules” + orphan badges | **Library** of UE / UR / SE / SR / D (+ C) |
| Single “When event” | Split **When user event** / **When system event** (+ fire actions split) |
| Fire picker ≈ all pickable system | Unused system **not** fireable except Sauna/IR ON/OFF |
| Schedule labels Morning on / Sunrise / Sunset / Evening off | Morning/Evening **lights** on/off (UUIDs unchanged) |
| `EXTERNAL_WEATHER_UPDATED` bus key | Rename → **`SUNRISE_SUNSET_UPDATE`** |

#### Library (left column)

* Page title stays **Automations**. Left list name: **Library**.  
* Buttons above list, side by side: **New rule** | **New user event**.

#### Icons (letter badges)

| Badge | Meaning | Circle |
|---|---|---|
| **UE** | User **event** (catalog) | Teal |
| **UR** | **Rule** triggered by a **user** event | Sky blue |
| **SE** | **System** event (catalog, immutable) | Slate |
| **SR** | **Rule** triggered by a **system** event | Darker slate |
| **D** | **Device**-triggered rule | Amber |
| **C** | Confirm (2nd icon on **UE** only) | Rose |

Default sort: **UE → UR → SE → SR → D**, then name; toggle ↔ name-only.  
Filter: text + checkboxes **UE / UR / SE / SR / D** (default all on).

#### Locked list model

| Kind | Editor | Explorer / confirm | Enable / names |
|---|---|---|---|
| **UE** user event | **Not Blockly** — name; **Appear on explorer** (always shown, default OFF); **Require confirmation** (always shown; **usable only when** appear-on-explorer is ON, otherwise **blocked**; default OFF); Disable. **Invariant:** turning Appear on explorer **OFF** while confirmation is ON **must clear confirmation** (UI + persisted `require_confirmation: false`). | Explorer GO when appear-on-explorer | Disable only if unused (no listening UR + no fire-refs); Show usages |
| **UR** user-event rule | Blockly (**When user event**); name may differ from UE | Never (only **UE** on Explorer) | Can disable (blocked while trigger UE is fire-referenced) |
| **SE** system event | **View-only** catalog (name + id); **no** create/edit/delete of the event; **no** Save that edits SE | **Never** | **Cannot** disable (no toggle). Unused SE = no listening SR — **not** called disabled. **Show disabled/unused** XOR for SE: OFF = used only; ON = unused only |
| **SR** system-event rule | Blockly (**When system event**); **name always equals** companion SE catalog name (list label + locked name field; API overwrites on POST/PUT) | **Never** | Can disable. New SR: When-system picker lists **unused** SEs only (+ current when editing). One SR max per SE |
| **D** device rule | Blockly (**When device**) | Never | Manual |

**New user event** → form → `POST /api/events` → **UE** in Library (no rule).  
**New rule** → Blockly roots: When device | When user event | When system event. **No** “New system event”.  
**Fire:** Fire user event | Fire system event (Sauna/IR ON/OFF always; other unused system excluded).

**UE form — explorer / confirmation (locked)**

* **Appear on explorer** always available (default OFF).  
* **Require confirmation** always visible; **usable only when** Appear on explorer is ON; otherwise **blocked**.  
* If confirmation is ON and the operator turns Appear on explorer **OFF** → confirmation is **forced OFF** immediately (checkbox + save/`PUT` must persist `require_confirmation: false`). API: rejecting or coercing `require_confirmation: true` when `show_on_dashboard: false` is required.  
* Rose **C** icon only when confirmation is ON (implies explorer ON).

**Disable / usages:** referenced **UE** (as fire-action) → cannot disable **UE** or listening **UR** rules; Show usages = rule names. **SR** disable is free of that fire-ref guard. **SE** has no enable toggle.

**General:** one column; exclusive **Show disabled/unused** — UE/UR/SR/D enabled↔disabled, SE used↔unused; Event flags panel gone; one rule max per system event; GO dispatches event UUID (all listeners run); Soft-hide device picker label = **Show hidden devices**.

#### Schedule display + cleanup (same phase)

* Seed/YAML display names Morning/Evening lights…; wipe Sunset listeners; restore GoCosy on user event; clear system dashboard.  
* `EXTERNAL_WEATHER_UPDATED` → **`SUNRISE_SUNSET_UPDATE`**. Aliases D1 deleted with migrator (**2026-08-10**).

#### Phase B10E DoD (+ B10B+D close-out in same ship)

- [x] Catalog/UI schedule names + `SUNRISE_SUNSET_UPDATE`; UUIDs unchanged where required.
- [x] Library: **New rule** | **New user event**; UE form; badges UE/UR/SE/SR/D (+ C); sort UE→UR→SE→SR→D; filters; exclusive Show disabled/unused (UE/UR/SR/D disabled XOR; SE used/unused XOR).
- [x] SE catalog view-only (**no** auto-created SR shells in YAML or UI memory); unused SE = catalog row only until operator **New rule** → When system event → Save; SR name = SE; When/Fire user vs system split; Sunset wipe; GoCosy; system dashboard rejected.
- [x] Appear on explorer always on UE form; confirm always visible but **blocked** unless explorer ON; **disabling explorer while confirm ON forces confirm OFF** (UI + API coerce); disable + Show usages when referenced.
- [x] Fire allowlist Sauna/IR ON/OFF.
- [x] B10B+D close-out on Pi (Admin Debug GREEN, kiosk smoke, B10D name smoke) + combined B10E operator smoke — ✅ **2026-08-10**.
- [x] Delete migrator `helpers/migrate_events_b10b.py` (+ `helpers/b10b_cutover_map.json`; D1 `TWILIGHT_*` / `SCHEDULE_EVENT_ALIASES` / `SCHEDULE_WINDOW_EDGES`) — ✅ **2026-08-10** after soak.
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (B10B+D+E close-out); re-audit ✅ **2026-08-10** (retired `install_blocky.md` stub + E1/smoke/status drift).

---

### Phase B10F — Automations UX polish ✅ DONE

**Origin:** operator inbox **2026-08-10**; expanded **2026-08-11**. After B10B+D+E smoke; **does not reopen B10E DoD**. **Sequence:** after **C6–C9** ✅. **Spec locked** (operator Q&A **2026-08-10** + **2026-08-11**). **One ship.** **Code + Pi smoke ✅ 2026-08-11** (SR name = SE catalog; CRUD INFO names quoted).

| # | Item |
|---|---|
| 1 | **Save busy indicator** — content-wide dim overlay + `loading-lg` + “Saving…”; Save button `loading-md` (not `xs`) |
| 2 | **Save lock** — while a **rule** is saving, block **all** Automations UI; stay locked until **retry** / **dismiss** (those two stay enabled); unlock after success |
| 3 | **Connecting** — yellow **Loading automation editor...** while loading; red Explorer unreachable copy only when backend unreachable |
| 4 | **Library keyboard** — with a Library item selected/focused, ↑/↓ changes selection in the **currently filtered** list; **no wrap** at ends |
| 5 | **Schedule / timer SE status** — for **SR** whose trigger SE is in scope (below): status line **right above “Full screen”**; copy **Will fire at HH:MM** / **Has fired at HH:MM** / **Doesn't fire today** (local Pi clock) |
| 6 | **Unused SE → create SR** — unused **SE** view: button **Create System Rule for this System Event** → opens **New rule** with that SE preselected (**draft only**; nothing POSTed until Save). **Disabled** when SE already has an SR / is used |
| 7 | **Library filters UE & SE default OFF** — kind checkboxes **UE** and **SE** default **OFF** on every `blocky.html` load; **UR / SR / D** stay default ON; **no** persistence for kind filters |
| 8 | **Empty new rule** — New rule starts empty (no default “When device badk 1e Hue light”) |
| 9 | **Unused UE → create UR** — same pattern as SE→SR: unused **UE** view button **Create User Rule for this User Event** → New rule with that UE preselected (draft); **disabled** when a listening UR already exists |
| 10 | **Disable blocked — usages inline** — when disable is blocked (“rules still listen to or fire this event”), **list usages beneath the message** (rule names); **no** separate “Show usages” button |
| 11 | **CRUD INFO app log** — `/var/log/wanos/wanos.log` `INFO` for user event/rule (and peer) create/update/delete: e.g. `user event "X" added`, `user rule "Cinema rolluik half" changed`, and **all other combinations** (system rule/event where applicable); **name always quoted** |

#### Locked decisions (2026-08-10)

**Save (1–2)**

* Applies to **rule (Blocky) save** only — not UE form save.
* While saving: lock **all** UI (editor, Library selection, filters, New rule / New user event, etc.).
* On failure: remain locked except **retry** and **dismiss** (enabled). **Retry** = re-attempt the same save. **Dismiss** = unlock and **keep editor edits**. Success → unlock.

**Connecting (3)**

* **Loading (normal):** yellow / warning — **`Loading automation editor...`** while the page fetches Library data.
* **Unreachable only:** red / error — same copy as Device Explorer — **`Establishing connection stream to WanOS backend...`** — only when the backend cannot be reached (initial load failed). Do **not** show the red message on a healthy reload.

**Library ↑/↓ (4)**

* Navigate selection within the **filtered** list only; stop at first/last (no wrap).

**Fire status (5)**

* **In-scope SEs:** the **six** env-schedule edges ([`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md)) **plus** **Sauna OFF** / **IR OFF** when a session timer is armed. **Sauna ON** / **IR ON** are never timed — no status line.
* **Where:** only when editing an **SR** whose **When** trigger is one of those SEs. Placement: message **right above “Full screen”**.
* **Sauna/IR OFF deadline (this phase):** use **`session_end_time`** when the session timer is armed (unix end). Do **not** clamp to `absolute_cutoff_unix` in B10F. Engine clamp → **B18**.
* **Data — new read API (locked):**

  * **`GET /api/automations/fire-status`** (same auth as other Automations admin APIs).
  * **Response** (local Pi clock; no client-side schedule math):

    ```json
    {
      "server_now_unix": 1710000000,
      "entries": [
        {
          "event_uuid": "<catalog uuid>",
          "state": "will_fire",
          "at_hhmm": "21:54",
          "at_unix": 1710003294
        }
      ]
    }
    ```

  * **`state`:** `will_fire` | `has_fired` | `doesnt_fire_today` | `not_armed`.
  * Always include the **six** env-schedule event UUIDs. Include **Sauna OFF** / **IR OFF** UUIDs always: `will_fire` / `has_fired` when session timer armed with a unix end; else `not_armed` (`at_hhmm` / `at_unix` null). UI omits the status line when `not_armed` or SE out of scope.
  * **`will_fire` / `has_fired`:** compare `server_now_unix` to `at_unix` (wall-clock). Past → `has_fired`; else `will_fire`. `at_hhmm` = local Pi `HH:MM`.
  * **`doesnt_fire_today`:** morning skip (sunrise ≤ morning-on → both morning edges) / evening skip (sunset ≥ evening-off → both evening edges); `at_*` null. Blinds never use this from skip logic (always clamped schedule).
  * **No sun yet** (rare: before first successful OWM sun fetch, or OWM down/disabled): six env-schedule entries → `not_armed` (`at_*` null); Automations editor shows **no** fire-status line. (Normal path: OWM sun once daily ≥ `sun_refresh_hour` + boot/enable — not on climate polls.)
  * Fetch on editor open + full page reload; no extra poll in B10F.
* **Scheduler (locked with status API):** evening skip must **mirror morning** — if sunset ≥ evening-off, set both evening unix times to `None` and **do not arm** `env_twi_eve_on` / `env_twi_eve_off`. Status and live timers stay aligned. (Today’s code still arms inverted evening timers; fix in this ship.) See [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

**Save busy chrome (1) — locked**

* Today Save uses DaisyUI `loading-xs` (barely visible).
* While rule-save `busy`: **content-wide dim overlay** with centered **`loading-lg`** spinner + **“Saving…”** text; Save control uses **`loading-md`** (not `xs`). Failure banner: **Retry** | **Dismiss** only.

**Unused SE → SR (6)**

* **Draft only (A):** button opens **New rule** with When-system = that SE preselected; **no** immediate POST. Cancel/navigate away → no SR; SE stays unused. Prefill counts as unsaved → **editor dirty ON**.
* Button **disabled** if companion SR already exists / SE is used.
* DoD wording: opens New rule with SE preselected; **Save** creates the companion SR.

**Filters (7)**

* UE + SE default **OFF** on cold load; UR/SR/D unchanged (default ON). Kind filters are **not** session-/localStorage-persisted today — keep it that way in B10F.

**Empty new rule / UE→UR / usages / CRUD logs (8–11) — locked 2026-08-11**

* **(8)** New rule draft has **no** pre-filled device trigger (empty When).
* **(9)** Mirror item 6 for **UE**: draft New rule with When-user-event = that UE; no POST until Save; disabled when UE already has a listening UR / is used; prefill → **editor dirty ON**.
* **(10)** Replace “Show usages” control with an **inline list** under the disable-blocked message (same rule-name set as today’s usages).
* **(11)** App log `INFO` on Automations Library CRUD: cover **user event** / **user rule** / **system rule** (and event where mutable) × **added** / **changed** / **deleted** (wording may use those verbs; **name quoted**, e.g. `user rule "Cinema rolluik half" changed`). Not a substitute for G7 integration bridge tags.
* **SR name = SE catalog:** Library / editor / usages / delete-blocked / CRUD logs / YAML use the companion SE catalog name (bind on POST/PUT; boot merge rewrites drifted free-text; GET list also normalizes for display).

**Out of scope**

* Do not reopen B10E DoD. Do not fold **B15** (demote schedule edges). Other env-scheduler math (blinds clamps, morning skip, clock sources) unchanged except the **evening skip** above. Sauna `session_end_time` vs absolute cutoff clamp → **B18** (not B10F). Scoped `CONFIG_RELOAD` / no Hue·Onkyo·Z-Wave recycle on save → **G6** (not B10F). Explorer/History screenshot polish → **C10**. Integration log `[Onkyo]` tag → **G7**.

#### Phase B10F DoD

- [x] Save busy chrome: content-wide dim overlay + `loading-lg` + “Saving…”; Save button `loading-md` (not `xs`).
- [x] During rule save: **all** Automations UI locked; **retry** / **dismiss** remain enabled on failure (**dismiss** = unlock, keep edits); unlock after success or dismiss.
- [x] Automations: yellow **Loading automation editor...** while loading; red Explorer unreachable copy only when backend unreachable.
- [x] Library ↑/↓ changes selection in the filtered list; no wrap.
- [x] Env scheduler: sunset ≥ evening-off → schedule **neither** evening edge (no inverted timers); status API agrees.
- [x] New read API **`GET /api/automations/fire-status`** supplies today’s fire status for the six env-schedule SEs + Sauna/IR OFF (`not_armed` when idle); deadline = **`session_end_time`** when armed.
- [x] In-scope **SR** editor shows Will fire at / Has fired at / Doesn't fire today **right above “Full screen”** (local Pi `HH:MM`).
- [x] Unused SE view: **Create System Rule for this System Event** opens New rule with SE preselected (draft); disabled when SE used; Save creates SR.
- [x] Library filters: **UE** and **SE** default OFF on load; UR/SR/D default ON; no kind-filter persistence.
- [x] New rule starts empty (no default Hue/device When).
- [x] Unused UE view: **Create User Rule for this User Event** opens New rule with UE preselected (draft); disabled when used; Save creates UR.
- [x] Disable-blocked message lists usages inline (no Show usages button).
- [x] CRUD `INFO` lines in `wanos.log` for event/rule added/changed/deleted combinations (**name quoted**).
- [x] SR display/YAML name always equals companion SE catalog (usages + bind + boot rewrite).
- [x] Pi smoke (items 1–11 + evening skip day if exercisable).
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-11**.

---

### Phase B11 — Multi-flow one Blockly page 🔜 TODO (deferred)

**Not now.** N independent trigger→action graphs under one Library entry. High cost; tensions with Phase B6B one-trigger canvas. Prefer **B12** folder/tag first if list organization is the real pain.

**B11 DoD (stub):** multi-flow authoring + load/save + engine semantics locked before impl; Pi smoke; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B12 — Rule-list folder/tag 🔜 TODO (deferred)

**Not now.** Library organization via folder and/or tag without multi-flow.

**B12 DoD (stub):** folder/tag model + list UX + persistence; Pi smoke; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B13 — Blockly IF/ELSE / ELSEIF / ELSE 🔜 TODO (deferred)

**Origin:** operator inbox **2026-08-10** (was HA **H11**). Beyond today’s ON/OFF cases: authorable IF / ELSE / addable ELSEIF chains in Blockly.

**B13 DoD (stub):** schema + Blockly + engine for IF/ELSEIF/ELSE; Pi smoke. Spec lock at kickoff (vs ON/OFF cases coexistence). **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B14 — Remaining HA patterns H1–H3, H6–H10 🔜 TODO (deferred)

**Not B9A/B9B.** H1 sustained-for · H2 delay/wait · H3 cooldown · H6 input_number · H7 presence/mode · H8 area trigger · H9 sun elevation · H10 blueprints. (**H11** → **B13**; **H4/H5/H12** stay **B9B**.)

**B14 DoD (stub):** pick subset + lock order at kickoff; do not pull into B9\*. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B15 — Demote schedule edges → user origin 🔜 TODO (deferred)

**Not now.** Blinds open/close, Morning/Evening lights edges, and sibling schedule seeds stay **`origin: system`** with fixed UUIDs and env-scheduler / sweeper emitters. Display names: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md).

**Goal:** selected schedule edges become normal **user** catalog rows (enable / confirm / delete policy like Cinema) while **keeping the same timed behaviour**.

**Must preserve:**

1. Same bus UUIDs (or explicit remap) so existing rules/kiosk keep working
2. Env scheduler + sweeper still emit those edges on the same formulas
3. One-flow-per-system-event invariant either drops or is replaced by an explicit product rule

**Do not** fold into B10E / B10F.

**B15 DoD (stub):** cutover plan + Pi smoke; schedule behaviour unchanged. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B16 — Full-bus UUID for internal `EventType`s 🔜 TODO (deferred)

**Not in B10B.** Catalog / pickable events are UUID-on-bus; internals stay readable `EventType` strings until this phase.

**Internal** (examples): timers / infra (`TIMER_*`, health), integration arming (`*_TOGGLED`), alerts, config reload — never in `events:` / Blockly pickers.

| Option | Idea |
|---|---|
| **Keep strings** | Internals remain `EventType` names indefinitely |
| **UUID all bus traffic** | Every `EventType` gets a fixed UUID; emitters/handlers migrate |
| **Hybrid map** | Enum names in code; wire carries UUID via central table (internals never in `events:` YAML) |

**Decision inputs at kickoff:** dual-mode pain after B10 soak; goal (wire uniformity vs ergonomics vs catalog); internals in `events:` or code-only; compat window; log/SSE display policy.

**B16 DoD (stub):** option locked + impl (or explicit keep-strings close); Pi smoke if impl. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B17 — Sauna/IR hardcoded → automation (assess only) 🔜 TODO (deferred)

**Origin:** operator inbox **2026-08-10**. **Assess only** — no cutover in this phase.

**Question:** which lights/devices do Sauna ON/OFF and IR ON/OFF switch in code today, and can/should those device actions move from hardcoded handlers to automation rules?

**Constraints to respect in the write-up:** live safety / start gates / max-runtime in [`sauna-ir.md`](../sauna-ir.md) stay authoritative; catalog events + fire allowlist already in B10E.

**B17 DoD:** written assessment (devices switched; keep-in-code vs rule candidates; recommended disposition). **No code cutover** unless a later phase is opened. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B18 — Sauna session_end ≤ absolute cutoff 🔜 TODO (deferred)

**Origin:** B10F lock Q&A **2026-08-10**. **Not B10F** (fire-status uses raw `session_end_time`). **Not B17** (B17 = assess hardcoded→automation only).

**Gap today:** `absolute_cutoff_unix` = session start + 6h (EN 60335-2-53); `HealthMonitor` hard-kills independently. Timer arm / `SAUNA_TIMER_ADJUSTED` do **not** clamp `session_end_time`, so the soft session timer can be set **past** the absolute wall.

**Goal:** enforce **`session_end_time` ≤ `absolute_cutoff_unix`** whenever both are set (i.e. session end cannot run past the start+6h absolute cutoff). Clamp on arm and on timer adjust; reschedule `sauna_main` if needed. Document in [`sauna-ir.md`](../sauna-ir.md).

**B18 DoD (stub):** clamp on set/adjust; Pi smoke (extend timer toward/past 6h wall → ends at cutoff); docs. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B5 DoD — Hardening + rollout readiness ✅

- [x] **Docs complete:** operator workflow and troubleshooting in `phaseB-blocky.md` §E (+ pointer in `docs/reference.md`).
- [x] **Regression matrix complete:** pass/fail table for critical patterns in §E3; operator smoke **OK**.
- [x] **Runtime stability:** smoke OK on Pi (boot / Blocky CRUD auto-reload); no validation failures observed.
- [x] **Observability clarity:** `format_rule_ref` emits `rule=<id> branch=on|off|- name="…"` on X-RAY/ACTION (verified in live traces).
- [x] **Policy verification:** Blocky Save/Delete auto-runs Admin Debug; GREEN after representative CRUD.
- [x] **Hand-edit / manual Admin reload:** **retired** for normal ops (§E5) — Blocky API auto-reloads; no Phase B5 rollback rehearsal required.
- [x] **X2 readiness review:** **stay on X1** — rationale in §E6 (revisit in **Phase B6A** with schema v2 cases).


### SYNC — retired (use ON/OFF cases) ✅ DONE ON PI

**Retired:** trigger/action `SYNC` and `SYNCOPPOSITE`. Pure mirrors are one rule with `to_state: ON` + `to_state: OFF` cases (same targets).

**DoD:**
- [x] Schema migrator `_migrate_sync_to_cases` + YAML rewrite of four live mirrors.
- [x] Engine no longer honors SYNC trigger/action (leftover action → WARNING + skip).
- [x] Blocky UI no longer offers SYNC / SYNCOPPOSITE.
- [x] **Pi:** deploy + grep-clean YAML + Admin Debug GREEN + smoke four ex-mirrors (2026-08-05).