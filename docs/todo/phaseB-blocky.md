# ⚡ WanOS Phase B — Blocky

This document is the source of truth for (1) the **entity_id prerequisite** (done in code) and (2) the **Blocky** visual automation editor (Phases **B0–B8** + **B10A** + **B10C** **done**; **B10B+D+E** ✅ **complete 2026-08-10**; **B10F** ✅ **Done 2026-08-11**; **B9A** ✅ **Done 2026-08-12**; **B10G** / **B10H** ✅ **Done 2026-08-12**; **B9C** (Ship **B2**) ✅ **Done 2026-08-16**; **B19+B13** (Ship **B3**) ✅ **Done 2026-08-17**; **H4** (Ship **B4**) ✅ **Done 2026-08-17**; **H12 + bathroom** (Ship **B5**) ✅ **Done 2026-08-17**; **Blockly cluster next** = **B6 (H5) → …** — see § **Domoticz goal** + [`pipeline.md`](pipeline.md) § Blockly ship groups). Operator shell → [`phaseC-shell.md`](phaseC-shell.md) (**C1/C2/C5** ✅; **C6–C9** ✅ **Done 2026-08-10**; **C10** ✅ **Done 2026-08-11**); device typing → [`phaseD-typing.md`](phaseD-typing.md) (**D** ✅ **Done 2026-08-11**); sequence → [`pipeline.md`](pipeline.md). Schedule admin model: [`env-schedule-and-system-events.md`](../env-schedule-and-system-events.md). Gmail transport (H5) → [`phaseE-gmail.md`](phaseE-gmail.md). API / events catalog → [`../reference.md`](../reference.md).

**Historical:** `docs/todo/install_blocky.md` was an early Blocky install / phase pointer. It still described pre-**B10B** surface (E1 families, `SCHEDULE_WINDOW_EDGES`, `TWILIGHT_*`, old schedule labels, next = Phase 9A/9B). Retired to a stub at **B10B+D+E** close-out (**2026-08-10**); **deleted 2026-08-12** — this file is the only SoT. Bus pickers = `events:` UUIDs; schedule display = Morning/Evening **lights** on/off; sun refresh = `SUNRISE_SUNSET_UPDATE`; actuator ids `zwave.*` / `rfx.*` / `zwave.vent.*`; product light|switch via Timers & types.

**Entity_id cutover:** **done and verified** — registry birth/freeze, automations + structured config on `entity_id`, engine schema entity_id-only, Admin Debug registry check. **Pi Admin Debug: GREEN** (live metadata included; 0 errors, 0 warnings). Blocky may start.  
**`dashboard_map` removal:** **done** — display names live only in `device_metadata` / `device_name()`.

---

## ✅ Prerequisite (done) — One Device Map + Stable `entity_id`

Blocky and automations must not store raw hardware idxs in rules. Humans see friendly **names**; saved rules use stable **`entity_id`s**; hardware still uses **idx**.

### Identity model (three layers)

| Layer | Example | Who sees / uses it |
|---|---|---|
| Display `name` | `buro licht` | UI dropdowns only — may be renamed |
| `entity_id` | `zwave.buro_licht` / `hue.light.buro_spot` | Stored in automation rules — frozen after birth |
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

### `entity_id` patterns (locked at B0; **D2** updates Z-Wave/RFX — see [`phaseD-typing.md`](phaseD-typing.md))

| Kind | `entity_id` pattern | Example |
|---|---|---|
| Hue light | `hue.light.<slug>` | `hue.light.buro_spot` |
| Hue group | `hue.group.<slug>` | `hue.group.living` |
| Z-Wave binary | `zwave.<slug>` | `zwave.buro_licht` |
| RFX | `rfx.<slug>` | `rfx.kerstboom` |
| Z-Wave vent motor | `zwave.vent.<slug>` | `zwave.vent.sauna` |
| Vent wall switch | `switch.vent.<slug>` | `switch.vent.toilet_ventilatie` |
| SSR class | `switch.ssr.<slug>` | `switch.ssr.sauna` |
| Safety class | `switch.safety.<slug>` | `switch.safety.wisc` |
| Epson | `switch.epson` | `switch.epson` |
| Shutters / rolluik | `blinds.<slug>` | `blinds.cinema` |
| Power | `sensor.power.<slug>` | `sensor.power.pc` |
| Temp/hum | `sensor.temp_hum.<slug>` | `sensor.temp_hum.sauna_high` |
| Energy | `sensor.energy.<slug>` | `sensor.energy.kwh_meter` |
| Fluid | `sensor.fluid.<slug>` | `sensor.fluid.cold` |
| Door | `sensor.door.<slug>` | `sensor.door.sauna` |
| Speaker | `media_player.<slug>` | `media_player.living` |
| Scene | `scene.<slug>` | **Retired after B10B** — dashboard uses `events:` / `dashboard_events` (UUID), not `scene.*` entity births |
| Unknown / tombstone | `unknown.<slug>` | |

**Historical (pre–Phase D):** plain Z-Wave/RFX actuators used `switch.<slug>`. **Product type** `light`|`switch` is **not** in the id — **`device_product_types`** via Timers & types ([`phaseD-typing.md`](phaseD-typing.md) ✅).

**Confirm:** Vent **motors** → `zwave.vent.*`; wall switch → `switch.vent.*`. SSR / safety keep `switch.ssr|safety.*`. RFX → `rfx.*`.

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

**Current status:** Phase B0–B5 **✅ DONE**. Phase **B6A–B6C ✅ DONE**. **Phase B7 ✅ DONE**. **Phase B8 ✅ DONE**. **Phase B10A ✅ DONE** (Pi smoke **2026-08-09**). **Phase B10C ✅ DONE** (Pi smoke **2026-08-09**). **Phase B10B+D+E ✅ DONE** (**2026-08-10**). **Phase B10F ✅ DONE** (**2026-08-11**). **Phase B9A ✅ DONE** (**2026-08-12**). **Phase B10G / B10H ✅ DONE** (**2026-08-12**). **Phase B10K + B10N ✅ DONE** (**2026-08-15**). **Phase B9C (Ship B2) ✅ DONE** (**2026-08-16**). **Ship B3 (B19+B13) ✅ DONE** (**2026-08-17**). **Ship B4 (H4) ✅ DONE** (**2026-08-17**). **Ship B5 (H12 + bathroom) ✅ DONE** (**2026-08-17** — If/Else-if edge-cross; `Badk 1e ventilatie`; climate loop removed; Pi smoke + Admin Debug GREEN). **Next cluster:** **B6** (H5 Messages) → **B7** → **B8**. **B11–B18** / **B20** = lettered backlog.

**Follow-up (pickers):** **B9A** opens sensors / temp / power / energy / fluid / host gauges / status sensors in Blockly (**G2** — see § B9A). **Motion** = When-device trigger only; never as action. Soft-hidden / out-of-catalog sticky eids unchanged. Actions = actuators only. **B9B:** **H4** ✅ **B4**; **H12 + bathroom** ✅ **B5**; **H5** notify → **B6** (Gmail when **E**).

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

**Shipped:** SoT = **`auto_off_devices:`** in `automations.auto.yaml` (`managed_auto_off` + general + per-type + per-device delays); Admin → **Timers & types** (`lightingautooff.html` + `/api/auto-off-timer`; renamed from Auto-off timers in **D1**); engine honors membership + precedence device→type→general; legacy `lighting:` / `managed_lights` removed. Product-type overrides (**D1**) live beside auto-off in the same API — see [`phaseD-typing.md`](phaseD-typing.md).

**Historical (pre-cutover):** auto-off lived under `lighting:` + `managed_lights`. One-shot `helpers/migrate_auto_off_devices.py` ran on Pi then was **removed** (same habit as Phase B7 / B6A).

#### Locked (as implemented)

1. **Placement** — `lightingautooff.html`; Admin System Commands **“Timers & types”** (was “Auto-off timers”) under Explorer hidden devices; Admin-link only.
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

### Phase B9A — Full Blockly parity + sensors/thresholds + remove JSON ✅ DONE (2026-08-12)

**Depends on:** Phase **B6C** ✅ (rich actions). **B10B+D+E** ✅ (`events:` catalog). **D** ✅ (typing / `zwave.*`·`rfx.*` ids). Phases **7** / **8** ✅ (orthogonal).

**Goal:** every authorable schema-v2 automation is create/edit-able entirely on Blockly. **JSON mode is removed** (same PR as parity green). Sensors / thresholds / host gauges / sauna·IR status conditions / Explorer Hue preset CRUD become first-class where engine-legal.

**Split:** **B9A** = parity audit + sensor/host pickers (**G2**) + compare + sauna/IR status conditions + Hue preset CRUD + **remove JSON**. **B9B** = bathroom climate + **H4** (condition AND/OR groups) + **H5** (notify/alert → extend with Gmail per `docs/todo/phaseE-gmail.md`) + **H12** (hysteresis block). Vent **min-runtime lock stays in hub code**.

**FORCE / Epson:** out of B9A → **[`phaseG-integrations.md`](phaseG-integrations.md) § G1** (keep Epson OFF-only force as today; RFX already always-force).

**Events / `SAUNA_SETPOINT_REACHED`:** **moot for B9A** — seeded + pickable since B10B. Further system seeds = explicit review + constants (standing process, not a B9A deliverable).

#### Locked (2026-08-08 base + 2026-08-11 operator lock pass — do not re-litigate without explicit change)

1. **Delivery order** — **audit-first**, then build; **post-audit** propose HA-inspired patterns (adoption separate).
2. **Thresholds / compare** — **in B9A:** engine + Blockly. Operators = `==`, `!=`, `>`, `>=`, `<`, `<=`. **Hysteresis / for-duration = B9B only**.
3. **Picker policy (G2)** — When+if for typed classes: `temp_hum`, `temp`, `hum`, `power`, `energy`, `fluid`, `door`, **plus every metadata `type: sensor`** (host gauges, mains, sauna/IR status, …). **Motion** = When-device trigger only; never as action; never as condition.
4. **Roles** — typed classes + numeric/`type: sensor` gauges: **both** When + if (engine-legal). **Exception:** `sensor.generic.sauna_status` + `sensor.generic.ir_status` = **condition (if) only** — **not** When.
5. **`temp_hum` attributes** — separate fields: `temperature` and `humidity`.
6. **Sensor When semantics** — **discrete** (door / motion): any change; **numeric**: compare **becomes** true (edge / threshold-cross).
7. **Value UX (O1)** — **discrete = dropdown**; **numeric = Blockly `FieldNumber`** (same pattern as volume / blinds open %).
8. **FORCE_*** — **out of B9A** → **G1**. Current code: RFX always-force; Epson/Sonos/Onkyo force **OFF only**. Blockly already omits FORCE_* for RFX/Epson.
9. **Silent-loss = B+C** — opaque preserve unknown-but-legal keys; **block Save** when a drop would be non-preservable or structure cannot load safely.
10. **JSON** — **remove in same PR** as parity green (Automations page Editor → “JSON (power-user)” only; internal `ruleJson` transport may remain).
11. **Events** — pickable set = `events:` catalog (B10B). **`SAUNA_SETPOINT_REACHED` already seeded/pickable** — no B9A expand work. Further system keys by explicit review + constants only.
12. **O9 (doc chore)** — when JSON is removed, update Phase B0 **decision #12** (Hybrid / JSON fallback) so it no longer says “keep JSON until Phase B9”. Not a product fork — mechanical supersession at B9A ship.
13. **B9B features** — bathroom climate (humidity band → Blockly); **H4** condition AND/OR groups; **H5** notify/alert action (**extend with Gmail** / `EMAIL_REQUESTED` per `docs/todo/phaseE-gmail.md`); **H12** generic hysteresis block. Feasibility for bathroom below. **Vent min-runtime lock (`90001` + timer) stays in hub code**.
14. **B9B scope** — bathroom climate + H4 + H5 + H12. Hot-water→vent / sauna grace / other sweeper = **out** unless reopened. Other HA patterns (**H1–H3, H6–H11**) = **future possibilities** only (not B9A/B9B).
15. **O7 disposition (2026-08-08)** — H4/H5/H12 → **B9B**; remaining H\* → future backlog. **No** new HA primitives in **B9A**. Post-audit step may still *note* gaps; it does not re-open this bucket without explicit change.
16. **Pi smoke** — operator broad smoke; DoD not exhaustive.
17. **Permanent exceptions** — hard-deny **71040** only; soft-hide / auto-off UIs stay 7/8.
18. **Sauna / IR session condition** — use **`sensor.generic.sauna_status`** / **`sensor.generic.ir_status`** as `device_state` **if** ON/OFF (mirrors session active). **No** new `state.sauna.active` condition type.
19. **Host gauges — Blockly visibility** — closed **visible** set (soft-hidden devices still use Hidden toggle / sticky). Load **1m** and **5m** remain published but **hidden from Blockly pickers only** (not unpublished).

| entity_id | Blockly label |
|---|---|
| `sensor.temp_hum.host_cpu_temperature` | Host CPU Temperature |
| `sensor.generic.host_cpu_usage` | Host CPU Usage |
| `sensor.generic.host_memory_free` | Host Memory Free |
| `sensor.generic.host_disk_free_root` | Host Disk Free (Root) |
| `sensor.generic.host_log2ram_free` | Host Log2Ram Free |
| `sensor.generic.host_load_average_15m` | **Host average load %** |
| `sensor.generic.wanos_db_size` | WanOS DB size |
| `sensor.generic.mains_voltage` | Mains voltage |

20. **Hue presets CRUD (in B9A)** — SoT `config_hue_presets.auto.yaml` → `hue.presets` (text **keys**; display `name`; unique display names). Maps stay in `config_hue.yaml`. Automations/Blocky store the **key**.
    - **Add:** Explorer Hue detail — save **current** wheel color as a **new** preset (unique text slug from name; never overwrite an existing key’s color).
    - **Rename:** Explorer Edit mode next to preset chips — change **display `name` only** (YAML key unchanged).
    - **Delete:** same Edit mode — remove preset. **If any automation still references `preset: <key>` → Delete control disabled** (API reject if forced); show usages (rule names) so operator can clear refs first.
    - **No** “replace existing key with another color.”
    - **Reload path (✅ B10G Part D):** CRUD must **not** run full `CONFIG_RELOAD` (`load_config` + `rebuild_core_metadata` + bridge recycle). Shipped: **`hue_presets`-only** sync — re-read `.auto` → `system.hue_presets` + in-memory `config.hue.presets`; SSE `system` domain only; **no** Hue bridge / Z-Wave / Onkyo / NVRAM / passive sweep. See **G6** [`phaseG-integrations.md`](phaseG-integrations.md) scope row `hue_presets`.
21. **Smoke rule — sauna hue physical (in B9A DoD)** — author on Pi: trigger `zwave.sauna_hue_physical` (**71035**) on **any** change (duplicate when ON + when OFF cases); conditions via `sensor.generic.sauna_status` + `hue.group.sauna_hue` (**51002**); actions on sauna hue + `zwave.sauna_zoutlamp`. Logic: sauna ON → if hue already ON → no-op, else OFF hue + zoutlamp; sauna OFF → if hue ON → OFF hue + zoutlamp, else ON hue + zoutlamp.
22. **G5 blinds dashboard half** — **out of B9A** → [`phaseG-integrations.md`](phaseG-integrations.md) § G5 ✅ **Done 2026-08-16**.

#### Open

| ID | Topic | Status |
|----|--------|--------|
| **B9A-ops** | Pi smoke + Admin Debug GREEN + docs audit | ✅ **Closed 2026-08-12** |
| **B10G-D** | Hue preset CRUD: verify+finish lightning reload, Explorer chip refresh, save-disable | ✅ **B10G Part D** (**2026-08-12**) |

**Moved out of B9A (operator inbox 2026-08-12):** preset add/rename/delete taking 15–20s; spurious NOT CONNECTED during preset CRUD; Z-Wave/Onkyo reload cascade; inconsistent “Save current” disable. Root cause class = **full `CONFIG_RELOAD_REQUESTED`** on every preset write — same failure mode as **B10G Part B** (config reload stalls SSE). Product CRUD **shipped in B9A**; reliability/perf polish = **B10G Part D** ✅ **2026-08-12**. *(Wheel pointer drift after save→apply — **fixed**; not B10G scope.)*

#### O7 — HA-inspired patterns — **disposition locked**

**B9B (in):**

| # | Pattern | B9B note |
|---|---------|---------|
| **H4** | Condition AND/OR groups + retire trigger “when any of” | ✅ **Ship B4** **2026-08-17** — schema + Blockly Logic + engine; OR-list migrator |
| **H5** | Notify / alert action | UI alert first; **extend with Gmail** — Blockly/automation emits `EMAIL_REQUESTED` only (never calls Gmail). SoT: `docs/todo/phaseE-gmail.md` (OAuth outbox, producer hysteresis, transport dedup) |
| **H12** | Dual-threshold humidity band | ✅ **Done (Ship B5 2026-08-17)** — If/Else-if **edge-cross** (no new block). Dedicated Schmitt / hygrostat / min-runtime → **B14**. |

**Later lettered (not B9A/B9B):** H1–H3, H6–H10 → **B14** (Ship B7); H11 → **B13** (Ship **B3** with **B19**). Domoticz canvas → **B19** (Ship B3). Time trigger → **B20** (after F). See § B11–B20.

#### Facts

- Engine `device_state` + numeric When: compare ops `== != > >= < <=` (B9A); **H12** bathroom = If/Else-if edge-cross (**B5**); extra hysteresis primitives → **B14**.
- Live YAML still has no numeric-threshold rules (smoke uses discrete status/hue); engine + Blockly ready.
- Host gauges / many sensors may be soft-hidden → Hidden toggle / open-rule sticky unchanged; Blockly additionally hides host 1m/5m load eids.
- `sauna_status` / `ir_status` mirror session ON/OFF; Blockly allows them as **condition (if) only**.
- Hue presets: Explorer CRUD via `/api/hue-presets` (`relax_red` / `my_white` remain seed keys).

#### Live-rule parity audit (2026-08-11, pre-Pi)

Scanned `automations.auto.yaml` production rules against Blockly v2 canvas:

| Check | Result |
|-------|--------|
| Condition types | Only `device_state` + `time_of_day` — both supported |
| Action rich | `preset` / `bri`+`xy` / `volume`+`station` — B6C round-trip |
| Triggers | Device / event UUID / OR-device — supported; no mixed device+event OR in live set |
| Rule-level `scene` / `require_confirmation` | Deprecated (B10B); intentionally omitted on Save — not action opaque |
| Gaps deferred | H4 and/or, H5 notify, H12 hysteresis, FORCE completeness (G1); G5 (✅ Done 2026-08-16) — **not** B9A |
| **Post-audit:** no pressure to pull H\* into B9A | Confirmed |

#### Gap inventory (B9A targets)

| Gap | B9A target |
|-----|-----------|
| Rich B6C | verify no coerce/loss |
| Sensors + host gauges (**G2**) | typed classes + all `type: sensor`; UX = dropdown / FieldNumber; host 1m/5m FE-hidden |
| Sauna/IR session condition | `sauna_status` / `ir_status` if ON/OFF; smoke rule sauna hue physical |
| Compare ops | `== != > >= < <=` (no hysteresis) |
| Hue presets | Explorer add / rename name / delete (disabled if used); text keys |
| Silent loss | B+C |
| JSON | remove same PR; supersede decision #12 |

#### In scope (B9A)

1. Live-rule parity audit + gap list.
2. Post-audit: note any remaining gaps; **do not** adopt H\* into B9A (disposition locked).
3. Verify B6C rich / per-action / blinds mid.
4. Sensor pickers per **G2**; motion trigger-only; host visibility table above; status if-only.
5. Sauna/IR status conditions + author **sauna hue physical** smoke rule.
6. Compare conditions (no hysteresis — **H12 is B9B**).
7. Hue preset CRUD (Explorer; text keys; name-only rename).
8. JSON removal + B+C + update decision #12 prose.

**Out of scope for B9A:** bathroom climate; H4/H5/H12; vent-lock Blockly; H1–H3/H6–H11; schema v2 redesign; Phase B7/8 UIs; Gmail stack / Phase E (see `phaseE-gmail.md` — hooks land in **B9B H5**); **FORCE completeness / Epson force policy** (→ **G1**); events catalog expand / `SAUNA_SETPOINT_REACHED` (already done); G5 blinds dashboard (→ **G5** ✅). Bathroom feasibility write-up lives under **Phase B9B** (not a B9A deliverable).

**Constraints:** Admin Debug GREEN; B+C no silent strip; hard-deny unchanged.

**Follow-up (2026-08-12):** operator triage vs [Domoticz Blockly wiki](https://wiki.domoticz.com/Blockly). **Locked goal:** Domoticz **look & feel** (not “equivalent semantics” on today’s canvas). See § **Domoticz goal**, **Blockly ship groups**, **B9C** (bridge), **B19** (canvas cutover).

---

### Domoticz goal — **LOCKED 2026-08-12**

**North star:** [Domoticz Blockly](https://wiki.domoticz.com/Blockly) — match **block layout, toolbox, and trigger model**, not only runtime behaviour on the current WanOS wire shape.

**Operator locks:**

| Topic | Intent |
|---|---|
| **Canvas structure** | **If/Do** control block; **Compare** blocks plug into **If**; **Set** (and Messages) in **Do** — retire `When device` + `case MATCH` + flat `if device` chain as the primary authoring model (**B19**). |
| **Device trigger** | Domoticz **Device** mode: device change wakes the rule; **all** discrimination lives in **Compare** inside **If** — not on case `when ON/OFF` or a threshold row on the trigger block. |
| **Toolbox** | Device blocks **by class** (Switch, **Temperature**, **Humidity**, Blinds level, …) like Domoticz § Devices — not one generic `if device` row per entity. |
| **Logic** | **Else-if** / **Else** on control block (**B13** — **Ship B3** with **B19** ✅); nested **AND/OR/NOT** inside Compare (**B9B H4** — **Ship B4** ✅). |
| **Actions** | **Set** blocks in **Do** (incl. level / open % / volume / Hue); timed Set variants (**B14**). **Messages** notify (**B9B H5**). |
| **Time trigger** | Domoticz **Time** trigger (evaluate every minute) — **out of Blockly cluster**; schedule **after F** (**B20**). Until then: system catalog events + `if time` / twilight conditions (B10B+E). |
| **Explicitly out of scope** | **User variables**; **Debug/Log** Blockly block; Security panel trigger (unless product adds alarm). |

**Sequence:** finish **B9A** → **B9C** ✅ → **Blockly cluster** Ships **B3–B8** (**B19+B13** → **H4** → H12/bathroom → H5 → B14 → B11+B12) → then shell (**C\***), integrations (**G\***), **E**, **F** → **B20** time trigger. Parallel options → [`pipeline.md`](pipeline.md) § Parallel tracks.

---

### Domoticz alignment — assessment (2026-08-12)

**Legacy WanOS model (B9A canvas — superseded by B19):** `When (trigger root)` → ordered **cases** (`when ON/OFF/transitions` or numeric threshold on trigger) → flat **if** condition chain (AND only) → **set device** / fire event.

#### Already close (keep through B19 cutover / migrator)

| Domoticz pattern | WanOS today | After B19 |
|---|---|---|
| Set switch/light ON/OFF | `set device` | **Set** block in **Do** |
| Dimmer/blinds **Set** to level | Blinds open %, Hue bri, volume (B6C) | **Set** block + level fields |
| Time / twilight in **If** | `if time is dark/light` | **Time** compare in **If** (unchanged) |
| Fire scene / dashboard | UE/UR + fire event (B10B+D+E) | **Fire event** in **Do** (or parallel track) |
| User/system catalog events | When user/system event roots | **Event Compare** (+ fire in Do) — no authoring trigger (**B19** kickoff locked) |

#### Gaps — **require Blockly cluster** (not “good enough” on legacy canvas)

| Gap | Domoticz | Pipeline |
|---|---|---|
| **If/Do + Compare canvas** | Control + Compare in If | **B19** |
| **Device trigger = any change** | Device mode; logic in Compare | **B19** |
| **Temperature vs Humidity blocks** | Separate toolbox entries | **B19** (B9C ✅ patched legacy picker) |
| **Level compare in If** | Dimmer ≠ 0, blinds % | **B19** (B9C ✅ bridge on legacy When/if) |
| **AND/OR in If** | Nested Compare | **B9B H4** — **Ship B4** ✅ |
| **Else-if / Else** | Control gear | **B13** — **Ship B3** with **B19** |
| **Set for X min / delay** | Set + timer | **B14** — **Ship B7** |
| **Notifications** | Messages | **B9B H5** — **Ship B6** |
| **Time trigger (every minute)** | Time mode | **B20** — **after F** |

**Out of scope (operator):** user variables · debug/log block.

#### Blockly ship groups — **one PR each**

| Ship | Phases | Size | Notes |
|---|---|---|---|
| **B1** | **B9A** closeout | low | Pi smoke + Debug GREEN + docs. **Alone.** |
| **B2** | **B9C** | mid | ✅ **Done 2026-08-16** — legacy bridge: temp/hum ATTR; shutters OPEN/CLOSED/% + Set open %; audio ON/OFF/volume When+if. Enabled **G5** (✅ Done same day). |
| **B3** | **B19** + **B13** | **high** | ✅ **Done 2026-08-17** — If/Do + Else-if/Else, Compare, toolbox, Set, branch cutover; Pi smoke OK. |
| **B4** | **B9B H4** only | high | ✅ **Done 2026-08-17** — nested AND/OR/NOT in Compare; OR-list migrator; `b_trig_or` removed; Debug GREEN. |
| **B5** | **B9B H12** + bathroom | mid | ✅ **Done 2026-08-17** — If/Else-if edge-cross; `Badk 1e ventilatie`; climate loop removed; Pi smoke + Admin Debug GREEN |
| **B6** | **B9B H5** notify | mid | **Alert** in Messages block; **Gmail** half waits on **E** (can split: alert first). |
| **B7** | **B14** (excl. time) | high | H1–H3 · H6–H10 subset + **B5-deferred** (min-runtime, level Compare, Auto switch, hygrostat, Schmitt block, sweeper replay). **No** Time trigger (→ **B20**). Pick subset at kickoff. |
| **B8** | **B11** + **B12** | mid | Multi-flow (**all matching If/Do fire** — reunite CINEMA OFF / Evening lights on splits) + folder/tag — after B19 canvas stable. |

**Not in Blockly cluster:** **B15** (schedule demotion), **B16** (internal bus UUID), **B17** (assess), **B18** (sauna clamp) — stay in general pipeline after **F** unless safety jumps **B18**.

**Parallel (beside ships — detail in [`pipeline.md`](pipeline.md) § Parallel tracks):** **B10I** anytime after **B10F**; **C18** ✅ after **B10H**; **G5** ✅ **Done 2026-08-16** (legacy + **B9C**, not after B19); **E** transport ∥ Ships **B5–B8**; Ships **B5 ∥ B6** after **B4** if capacity allows (H5 email half still waits **E**).

**After F:** **B20** — Domoticz **Time** trigger + time-compare blocks (every-minute evaluation model).

---

### Phase B9C — Legacy-canvas bridge (pre-B19) ✅ DONE (2026-08-16)

**Origin:** operator triage vs [Domoticz Blockly](https://wiki.domoticz.com/Blockly) + live gaps during B9A polish (**2026-08-12**). Kickoff Q&A **2026-08-16**. Ship **B2**.

**Shipped summary:** Pi smoke OK (operator **2026-08-16**). Legacy `When` + `case` canvas: dual **temp_hum** ATTR (temp + hum); shutters **OPEN / CLOSED / open %** on When+if; **Set** open % restored (B6C); Sonos/Onkyo **ON / OFF / volume** on When+if (0…`max_volume`). Blockly UI = **open %**; YAML/`state` = **closed %**; inequalities flip via `blockyInvertCompareOp`. Native sensor/speaker types win over rpt `switch` fallback. **G5** dashboard rule authored on this canvas (✅ **Done 2026-08-16** — see [`phaseG-integrations.md`](phaseG-integrations.md) § G5). Cache at close: `blocky.js?v=16`, Automations **v10**. Also: `wanoslog.sh log 4 debug` tails automation log including DEBUG/X-RAY.

| # | Shipped |
|---|---|
| **1** | Dual `temp_hum` temperature + humidity ATTR on When + if (temp-only / host CPU → °C only) |
| **2–3** | Shutters + audio level MODE on When + if (OPEN/CLOSED/% · ON/OFF/volume) |
| **4** | Numeric / % / volume When = edge-cross (B9A); discrete OPEN/CLOSED/ON/OFF keep edge/MATCH |
| **5** | Volume = audio only; shutters = open % |
| **8–9** | Open-% UI + Set open %; closed-% storage + op flip |

**Out of scope (unchanged):** If/Do (**B19**); AND/OR (**B4**); Messages (**B6**); Hue bri on if. (**G5** closed separately on this canvas.)

**B9C DoD:**

- [x] Pi smoke on today’s canvas (temp+hum; shutter OPEN/CLOSED/% When+if; Set open %; audio ON/OFF/volume When+if)
- [x] Admin Debug GREEN (operator)
- [x] G5 rule/dashboard not required in this ship (landed as **G5** ✅ same day)
- [x] **Last DoD:** audit & update ALL `docs/**/*.md` (and root README) against shipped behavior (**2026-08-16**)

---

### Phase B19 — Domoticz Blockly canvas ✅ DONE (2026-08-17)

**Ship B3** with **B13**. Pi smoke OK (**2026-08-17**). Migrator 7A deleted after soak. Four OR-list leftovers migrated under **Ship B4/H4** (same day).

#### Shipped summary

- Authoring: **If/Do** + **Else-if** / **Else** (first-match); no When/case; wake derived from device/event Compares; time Compare = gate only until B20. **No nested If/Do** — use flat Else-if/Else chain; multi-root parallel fire → **B11** (Ship **B8**).
- On-disk: `branches: [{ when, conditions, actions }]`; API hard-rejects legacy `trigger`+`cases` writes.
- Toolbox: Control · Logic · Time · Events (legacy When/case removed).
- UX polish: branch load from `branches` (not legacy trigger/cases); SE/event sticky from Compares; motion = fixed “motion” (`is: ON`); discrete **transitioned** (`is: ANY`); leaner block labels.
- Post-save: registry check GREEN after **B4/H4** OR-list cutover.
- Cutover: 7A migrator ran on Pi; four OR-list rules migrated under **Ship B4/H4** (**2026-08-17**):
  - `KeukenLivingEetk_EetkHue` — nested **OR** of three level `is: ON` Compares → Hue ON
  - Spare Button ×3 — `is: ANY` on `zwave.living_special` + Else-if gates (night rule keeps Hue ON → ALL OFF branch)
- **Hotfix (2026-08-16):** `append_automation` / `update_automation` must persist `branches` (do not run B19 rules through `legacy_to_v2` — that rewrote Saves to trigger+cases).
- Non-exclusive splits kept as separate rules (CINEMA OFF ×3, Evening lights on ×2) → reunite under **B11** (Ship **B8**). Optional operator hand-merge **Evening lights on** + `(2)` → one If/Else chain (living ON → GoCosy + lights; Else → lights only); delete duplicate Library row before save.
- Sync: `*.bak-*` mirror-exclude so Pi migrator backups are not deleted.
- Cache at close: `blocky.js?v=26`.

#### Locked decisions (kickoff 2026-08-16) — archived

| Topic | Lock |
|---|---|
| **Authoring model** | **If/Do only** — no When/case, no page-level Device/Event/Time mode in B19. |
| **Wake** | Runtime-derived from device/event Compares; not persisted; time = gate until **B20**. |
| **Branches** | One If/Do + Else-if* + optional Else; **first match wins**. |
| **Conditions** | Flat AND at branch top level; nested Logic groups (**B4** ✅). |
| **Schema** | Hybrid branches; no authoring `trigger`. |
| **OR-list** | Retired — migrated to nested Compare + branches (**B4** ✅). |
| **Out of scope (B19)** | Messages (**B6**); Time trigger (**B20**); timed Set (**B14**); multi-root (**B11**). |

#### DoD

- [x] New rule authored only on Domoticz canvas (If/Do + Compare + Set)
- [x] Else-if / Else gear works (first-match); migrated ON/OFF → If/Else-if smoke
- [x] Event Compare + fire + dashboard bind smoke
- [x] Sauna hue physical works (migrate or re-author on Pi)
- [x] Toolbox class split + legacy When/case gone
- [x] Migrator 7A + backup + skip+report; API rejects legacy shape — migrator **deleted** post-soak
- [x] Pi smoke (**2026-08-17**); leftover OR-list migrated same day under **B4/H4** (Admin Debug GREEN)
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-17**

---

### Ship B4 / H4 — Nested AND/OR in Compare ✅ DONE (2026-08-17)

**Ship B4** = **B9B H4** only (not bathroom / H12 / H5). Historical Phase B4 (hybrid UI) remains ✅ Done separately.

**Depends on:** **B19+B13** (Ship **B3**) ✅ **Done 2026-08-17** — gate cleared.

#### Shipped summary

- **Schema / engine:** `ConditionGroupConfig` + nested `{ op: and|or|not, children: [...] }`; branch top-level list = implicit AND; `core/condition_tree.py` eval + validation + wake recursion.
- **Blockly:** Logic **AND/OR/NOT** blocks on If Compare sockets; YAML round-trip; `blocky.js?v=26`, `blocklySchemaVersion: 54`.
- **Compare semantics:** Domoticz-faithful **level** Compare (`is: ON/OFF/…`); wake = B19 any transition on mentioned devices/events.
- **Migrator:** one-shot on live Pi — KeukenLiving nested level-OR + Spare Button ×3; `legacy_remaining=0`; backup beside YAML; helper **deleted post-soak 2026-08-17**.
- **Cleanup:** `b_trig_or` / legacy When/case / OR-list FE paths removed.
- **Hotfix:** Pydantic group validator uses `model_dump(by_alias=True)` so nested leaf `is` validates correctly on boot.

#### Locked decisions (kickoff 2026-08-16) — archived

| # | Topic | Lock |
|---|---|---|
| **1** | **YAML / engine** | Nested condition tree. Flat leaf list under a branch = **AND** shorthand. |
| **1b** | **Wire shape** | Group nodes `{ op: and\|or\|not, children: [...] }` (`not` = one child); leaves keep today’s `type: device_state\|time_of_day\|event` shape. |
| **2** | **Blockly UX** | Domoticz-style Logic **AND/OR/NOT** blocks; sockets take Compare or nested logic. No hard nesting-depth cap. |
| **2b** | **Compare semantics** | **Domoticz-faithful:** discrete device Compare = **level only** (`is: ON` / `OFF` / …) after wake — **no** `became` / edge mode in Blockly. |
| **3** | **KeukenLiving** | Nested **OR** of three **level** `is: ON` → Set eetkamer Hue ON. |
| **4** | **Spare Button ×3** | **transitioned** (`is: ANY`) on `zwave.living_special` + Else-if gates; three Library rules. |
| **5** | **Cutover** | Pi migrator + backup; skip+report unknown leftover; repo YAML not migrator target. |
| **6** | **Cleanup** | Remove dead `b_trig_or` / legacy OR-list paths once leftovers gone. |

**Superseded (do not implement):** ON-edge-only KeukenLiving; Blockly **is/became** dropdown.

#### Ship B4 / H4 DoD

- [x] Nested AND/OR/NOT in schema + Blockly Logic + engine; flat AND shorthand; wire shape per lock **1b**
- [x] Domoticz-style AND/OR/NOT authorable on If/Do Compare sockets
- [x] Discrete Compare stays **level** (Domoticz-faithful); no is/became UI
- [x] Migrator on **live Pi** — KeukenLiving + Spare ×3; backup; `legacy_remaining=0`; Debug GREEN
- [x] Dead `b_trig_or` / OR-list authoring paths removed from FE
- [x] Pi smoke (KeukenLiving nested OR + Spare Button paths)
- [x] Admin Debug **GREEN**
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-17**
- [x] Migrator deleted after soak — ✅ **2026-08-17**

---

### Phase B9B — Bathroom climate + H5 / H12 🔜 NEXT (H5 only)

**Not B9A.** **H4 ✅ Done** (Ship **B4**). **H12 + bathroom ✅ Done** (Ship **B5**). Remaining: **Ship B6** (H5).

**Depends on:** **B19+B13** (Ship **B3**) ✅ **Done 2026-08-17**; **H4** ✅ **Done 2026-08-17** (§ Ship B4 / H4); **H12 + bathroom** ✅ **Done 2026-08-17** (§ Ship B5 / H12 below).

**Locked ship order (2026-08-16):** Ship **B5** ✅ → Ship **B6** (H5 alert; Gmail when **E** ready). Ships **B5 ∥ B6** was allowed — **B5** closed **2026-08-17**; **B6** is next.

**Goal:**

1. **Bathroom climate** — ✅ **Done (Ship B5)** — humidity ON/OFF band as Library If/Else-if `Badk 1e ventilatie`; hardcoded climate paths + sweeper Audit B removed.
2. **H12 (B5)** — ✅ **Done** — dual-threshold via numeric Compare (**edge-cross**); no new Blockly block. Dedicated Schmitt / hygrostat / min-runtime / Auto switch → **B14**.
3. **H4** — ✅ **Done 2026-08-17** (Ship **B4**) — nested AND/OR in Compare; OR-list leftovers migrated.
4. **H5** — **Messages** block (Domoticz); alert + Gmail via `EMAIL_REQUESTED` — **Ship B6** (email waits on **E**).

### Ship B5 / H12 — If/Else-if edge-cross + bathroom cutover ✅ DONE (2026-08-17)

**Ship B5** = bathroom 1e humidity band in Blockly + delete hardcoded climate loop. Historical Phase B5 (hardening) remains ✅ Done separately.

#### Shipped summary (2026-08-17)

- **Library rule** `Badk 1e ventilatie` (`id: a7c4e8f2-3b6d-4e91-9c0a-5f1d8e2b4c73`) in `automations.auto.yaml`: If hum **≥ 80** → `zwave.vent.badk_1e` ON; Else-if hum **≤ 74** → OFF; numeric Compare **edge-cross** on `sensor.temp_hum.badk_1e`.
- **Removed:** hardcoded `HUMIDITY_UPDATED` climate loop + sweeper Audit B in `logic/automation_rules.py`.
- **Config:** retired `bathroom1.vent_on_humidity` / `vent_off_humidity`; kept `vent_min_runtime_mins` (shower / hub `90001`).
- **Unchanged:** shower `WATER_PULSE` watchdog + hub vent lock on rising ON.

**Kickoff Q&A — locked 2026-08-17 (operator):**

| # | Topic | Lock |
|---|---|---|
| **1** | **H12 authoring** | **Option A** — one If / Else-if; **no** new hysteresis block. Numeric Compare stays **edge-cross** (B9A). |
| **2** | **Rule shape** | If bathroom humidity **≥ 80** → Set `zwave.vent.badk_1e` ON. Else-if humidity **≤ 74** → Set OFF. Humidity-only (vent not in If) so manual ON does not wake the rule. |
| **3** | **5 min / 90001** | **Dropped** for climate. Manual ON at 50% stays ON until humidity **crosses** 74 from above (or the operator turns it off). |
| **4** | **Sweeper Audit B** | **Drop** — next real humidity **crossing** runs the rule. No climate copy in the sweeper. |
| **5** | **config.yaml** | Retire `bathroom1.vent_on_humidity` / `vent_off_humidity` (literals **80 / 74** in the rule). Keep `vent_min_runtime_mins` while shower / hub `90001` remain (out of this ship). |
| **6** | **Other vents** | Pattern is authorable for any numeric sensor / vent. **DoD is 1e only** (`sensor.temp_hum.badk_1e` → `zwave.vent.badk_1e`). |
| **7** | **Cutover** | **Same ship:** add the 1e rule under `automations:` in `automations.auto.yaml` + delete hardcoded climate loop (`HUMIDITY_UPDATED` 80/74) + sweeper Audit B. |
| **8** | **Out of B5** | Hot-water shower watchdog; hub `90001` path used by shower; sauna grace; **B14** list below. |
| **9** | **Engine numeric edge** | **Leave as-is.** Humidity Compare may also wake on `TEMP_UPDATED` for that SHT11 (temp-only tick can Set OFF while hum stays ≤74). |
| **10** | **First sample** | **Accept.** Missing `old_value` counts as an edge — first humidity publish after boot can Set ON (≥80) or OFF (≤74). |
| **11** | **Shower vs Blockly OFF** | **Accept for B5.** Humidity **crossing 74** may Set OFF while `90001` / shower overrun is still running. **Fix → B14** row 1. |
| **12** | **Library name** | **Proposed** `Badk 1e ventilatie` (same pattern as `Toilet gv ventilatie`). Confirm before implement. `id` minted at write like other rows. |

**Superseded (do not implement in B5):** new Schmitt/H12 block; numeric **level** Compare; `AND vent is ON/OFF`; Auto/Manual switch; hygrostat helper; hub defer-OFF for 90001; sweeper humidity replay; restrict humidity Compare to `HUMIDITY_UPDATED` only.

**Deferred → Ship B7 / B14** (operator 2026-08-17: *“A for now — put the rest in the pipeline in the existing future phases”*): § Phase B14.

#### Ship B5 / H12 DoD

- [x] 1e Library rule: If hum ≥80 → vent ON; Else-if hum ≤74 → vent OFF; edge-cross numeric Compare
- [x] Hardcoded climate loop + sweeper Audit B removed
- [x] `vent_on_humidity` / `vent_off_humidity` retired from `config.yaml` + `BathroomConfig`
- [x] Shower `WATER_PULSE` path **unchanged**; do not delete `90001` hub lock in this ship
- [x] Pi smoke: rise through 80 → ON; fall through 74 → OFF; humidity 50→51 with vent already ON does **not** auto-OFF (edge-cross). First-sample / temp-only tick / shower 74-cross OFF = accepted B5.
- [x] Admin Debug GREEN
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-17**

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

**Superseded proposal (pre-Domoticz lock 2026-08-08):** ~~H12 → bathroom → H4 → H5 alert → H5 email~~ — replaced by locked ship order (**B4** H4 before **B5**; **B13** moved into Ship **B3** with **B19** on **2026-08-16**).

**Risk:** B9B scope grew from “bathroom only” — treat H4/H5 as explicit sub-deliverables; bathroom+H12 can DoD independently of Gmail if email lags.

#### Feasibility — bathroom climate / vent (2026-08-08) ✅ DONE — shipped **B5 2026-08-17**

Pre-impl write-up (moved out of B9A in-scope; owned by **B9B**). **Cutover complete** — see § Ship B5 shipped summary above.

**Pre-ship state (removed in Ship B5)**

1. **Event path** (`HUMIDITY_UPDATED` on bathroom SHT11): if `hum >= vent_on_humidity` → vent ON; if `hum <= vent_off_humidity` and vent ON and **not** lock → vent OFF. Thresholds from `config.yaml` → `bathroom1.vent_on_humidity` / `vent_off_humidity` (80 / 74).
2. **Min-runtime lock** (`90001`): on vent rising edge ON, hub sets `devices[90001]=True` and schedules `BATH1_VENT_LOCK_EXPIRED` after `vent_min_runtime_mins`; expiry clears lock and re-dispatches `HUMIDITY_UPDATED` to re-evaluate OFF. **Stays in code for shower** (locked 2026-08-08); climate path no longer uses it (**B5**).
3. **Sweeper recovery** (Audit B): same ON/OFF thresholds on manual sweep — **dropped in B5**.
4. **Related (out of B9B scope):** hot-water pulse → vent ON — shower watchdog **unchanged** in `logic/automation_rules.py`.

**Shipped state (2026-08-17)**

| Piece | Where |
|-------|--------|
| Humidity band ≥80 / ≤74 | Library rule **`Badk 1e ventilatie`** in `automations.auto.yaml` (If/Else-if edge-cross) |
| Shower `WATER_PULSE` → vent ON | `logic/automation_rules.py` |
| Hub `90001` min-runtime lock | `hub_handlers.py` (shower / rising ON only) |
| `bathroom1.vent_min_runtime_mins` | `config.yaml` (shower lock duration) |

**Can humidity band become Blockly-authorable?**

| Piece | Verdict |
|-------|---------|
| `humidity >= 80` → vent ON | **Yes after B9A** (numeric When + `humidity` + action) |
| `humidity <= 74` → vent OFF | **B9B** — hysteresis / dual-threshold (or two-rule pattern) |
| Min-runtime lock | **B5: drop for climate** (→ **B14**). Hub `90001` remains for shower until that ship. |
| Sweeper recovery | **B5: drop** Audit B. |
| `bathroom1.vent_*` in `config.yaml` | **B5:** retire on/off humidity keys; keep `vent_min_runtime_mins` while shower lock remains. |

**Verdict:** **Yes for B9B** for the humidity band. Not a B9A deliverable.

**Locked B9B approach (updated 2026-08-17):** humidity band → Blockly **Option A** (If/Else-if edge-cross) ✅ **shipped B5**; climate 5 min lock **dropped**; **H4** ✅ + **H5** (alert → Gmail) → **B6**. Hot-water/sauna-grace still out.

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
12. **UI strategy = Blockly-only:** Automations editor is Blockly canvas only (**Phase B9A** removed the JSON/form power-user fallback). Internal `ruleJson` remains the Blockly↔API transport. **Historical:** Option 2 Hybrid (JSON fallback until B9A) — superseded 2026-08-11.

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
| `BLINDS_OPEN_TRIGGER` | Shutters open | trigger-only | system seed UUID; **B10K** ✅ display rename |
| `BLINDS_CLOSE_TRIGGER` | Shutters close | trigger-only | system seed UUID; **B10K** ✅ display rename |
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
6. **Phase B9A:** Blockly parity + sensor/threshold/host-gauge authoring + sauna/IR status conditions + Hue preset CRUD + **remove JSON** — ✅ **Done 2026-08-12** (Pi smoke + Debug GREEN + docs close-out).
7. **Phase B9B:** bathroom climate + **H12** (B5 = If/Else-if edge-cross) + **H4** ✅ + **H5** notify (→ Gmail per `phaseE-gmail.md`); climate 5 min lock dropped → **B14**.
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
- [x] **Admin entry:** System Commands → **“Timers & types”** (under Hidden Devices; was Auto-off timers) → `lightingautooff.html` (admin-only; no shell nav).
- [x] **API:** `GET` + full-replace `PUT /api/auto-off-timer`; surgical write of **`auto_off_devices:`** only; hot-reload on save; reject unresolved / orphan / ineligible / bad type keys; enforce `auto_off_delays` ⊆ `managed_auto_off`; sorted unique lists/maps; minutes 1–720.
- [x] **UI:** general + type rows (`switch` / `light` / `speaker`) + eligible device list (checkbox + **Effective** minutes); blank = inherit (muted italic resolved); typed = per-device pin; uncheck clears delay; soft-hide All / Hidden / Non-hidden; **Auto-off ON / OFF / All** membership filter; sort Name / Type / Effective (resolved; unmanaged last); 71040 omitted; vents + speakers eligible.
- [x] **Eligibility:** denylist + device extras enforced in inventory and on PUT; migrator stripped ineligible leftovers (kept vents).
- [x] **Comments:** block rewritten without preserving hand comments.
- [x] **Docs:** `phaseB-blocky.md` Phase B8 closed + `docs/reference.md` API line.
- [x] **Admin Debug GREEN** after cutover / representative saves.
- [x] **Pi smoke:** migrator/rename; Auto-off timers page; general / type / per-device Effective pin; blank inherit (muted); uncheck clears delay; membership Auto-off ON/OFF filter; ON→timer uses expected delay; Debug GREEN — **OK on Pi (2026-08-08)** (Effective-column UX follow-up after that date).

### Phase B9A DoD — Blockly parity + sensors/thresholds + remove JSON

- [x] **Live-rule audit:** every production rule opens / edits / saves in Blockly with no semantic drift; written gap list. *(YAML audit 2026-08-11 — see § B9A Live-rule parity audit; Pi open/save confirmation still required.)*
- [x] **Post-audit note:** confirm no pressure to pull H\* into B9A (H4/H5/H12 wait for B9B).
- [x] **Per-action rich:** verify B6C round-trip independence. *(live rules use preset/bri/xy/volume/station only — covered by B6C + opaque B+C.)*
- [x] **Silent-loss B+C:** unknown-legal keys preserved; Save blocked when a non-preservable drop would occur.
- [x] **Sensor pickers (G2):** typed classes When+if; all metadata `type: sensor` When+if **except** sauna/IR status (**if only**); motion trigger-only; hard-deny blocked; host 1m/5m Blockly-hidden; discrete dropdown / numeric `FieldNumber`; host 15m label **Host average load %**.
- [x] **Sauna / IR session condition:** Blockly can pick `sensor.generic.sauna_status` / `sensor.generic.ir_status` as **if** ON/OFF (`device_state`). No `state.sauna.active` condition type.
- [x] **Example / smoke rule — sauna hue physical:** rule seeded in `automations.auto.yaml` (`Sauna hue physical`); Pi operator confirm still required.
- [x] **Thresholds:** ops `== != > >= < <=` in engine **and** Blockly; no hysteresis; `temp_hum` → separate temperature / humidity; numeric When = edge-cross, discrete = any change.
- [x] **Hue presets CRUD:** Explorer add (new key from current color); Edit-mode rename (**name** only); Edit-mode delete **disabled when any rule references that key** (show usages; API reject); text keys; no overwrite color on existing key; Blocky dropdown refreshes. *(Reload perf + Explorer UX polish → **B10G Part D** ✅.)*
- [x] **JSON removed** in same PR as parity green; decision #12 prose updated to Blockly-only.
- [x] **Pi smoke:** operator broad smoke + Admin Debug GREEN. *(Operator confirmed 2026-08-12.)*
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** *(Completed 2026-08-12 during B9A close-out.)*

*(FORCE / Epson force policy → **G1**. Events / `SAUNA_SETPOINT_REACHED` → already shipped; not a B9A checkbox.)*

### Phase B9B DoD — Bathroom climate + H4 / H5 / H12

- [x] **Bathroom feasibility:** write-up under Phase B9B (**2026-08-08**).
- [x] **H12 / bathroom:** → § **Ship B5 / H12 DoD** (shipped **2026-08-17** — Option A).
- [x] **`bathroom1.vent_on/off_humidity`** retired; min-runtime key stays while shower lock remains. (**Ship B5**)
- [x] **Sweeper Audit B** dropped. (**Ship B5**)
- [x] **H4:** → § **Ship B4 / H4** ✅ **2026-08-17**
- [ ] **H5 alert:** Blockly notify/alert action (UI path). (**Ship B6**)
- [ ] **H5 Gmail:** action emits `EMAIL_REQUESTED` only; aligns with `docs/todo/phaseE-gmail.md` (outbox/OAuth may land in parallel; email DoD can trail alert if needed). (**Ship B6**)
- [ ] Hot-water/sauna-grace still out unless reopened.
- [ ] Pi smoke + Admin Debug GREEN (per ship)
- [ ] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** (per ship close-out)

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
| `BLINDS_OPEN_TRIGGER` | **Shutters open** | **B10K** ✅ catalog/UI rename (UUID unchanged); shutters window START |
| `BLINDS_CLOSE_TRIGGER` | **Shutters close** | **B10K** ✅ rename; shutters window STOP |
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
| `SAUNA_SETPOINT_REACHED` | Sauna setpoint reached | Seeded + Blocky-pickable (B10B); emit may land later |
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

(`SAUNA_SETPOINT_REACHED` remains seeded + pickable; emit may land later — not a B9A gate.)

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
| `Blinds Open/Close` | `blinds` | `Blinds open` + `Blinds close` *(display **Shutters open/close** after **B10K** ✅)* |
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
* **B10G** — ✅ **Done 2026-08-12** — load checklist + timings + NOT CONNECTED (SSE A+B+C) + admin **`vNN`** + hue preset scoped reload.
* **B10H** — Automations cold-load shorten wait — ✅ **Done 2026-08-12**.
* **B10I** — Used SE → **Go to SR** — **∥ cluster** (anytime after B10F).
* **B10J** — **`Event Received`** catalog display name — **∥ cluster** (anytime after B10B).
* **B10K** — ✅ **Done 2026-08-15** — timings stopwatch + shutter OPEN/CLOSED + RFX ON/OFF (no color); **one code run with G3**.
* **B10L** — Shared **NOT CONNECTED** overlay: richer connect status + copy **Re-connecting to WanOS...** — **∥ cluster**.
* **B10M** — Explorer Hue preset duplicate settings — **∥ cluster** (after **B10G** Part D).
* **B10N** — ✅ **Done 2026-08-15** — closed without dedicated code; covered by **B10K** Item 3.
* **C18** — Explorer Control live lag — ✅ **Done 2026-08-16**; [`phaseC-shell.md`](phaseC-shell.md) § C18.
* **C19** — History auto-refresh blank — ✅ **Done 2026-08-16**; [`phaseC-shell.md`](phaseC-shell.md) § C19.
* **C10** — Explorer/History polish — [`phaseC-shell.md`](phaseC-shell.md); ✅ **Done 2026-08-11**.
* **G6** — Scoped `CONFIG_RELOAD` + Automations deferred Save config — [`phaseG-integrations.md`](phaseG-integrations.md); not a new B item.
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
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-10** (B10B+D+E close-out); re-audit ✅ **2026-08-10** (`install_blocky.md` retired to stub + E1/smoke/status drift); stub **deleted** ✅ **2026-08-12** (content folded into this file intro).

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

* Do not reopen B10E DoD. Do not fold **B15** (demote schedule edges). Other env-scheduler math (blinds clamps, morning skip, clock sources) unchanged except the **evening skip** above. Sauna `session_end_time` vs absolute cutoff clamp → **B18** (not B10F). Scoped `CONFIG_RELOAD` / no Hue·Onkyo·Z-Wave recycle on save → **G6** (not B10F). Explorer/History screenshot polish → **C10** ✅. Integration log `[Onkyo]` tag → **G7**.

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

### Phase B10G — Shell connection + load UX + admin page version + hue preset reload ✅ DONE (2026-08-12)

**Shipped summary:** One PR — Parts A–D. Pi smoke OK (operator **2026-08-12**). Full locked-decision archive kept below for G6 / shell reference. Cold-load latency fixed in **B10H** ✅ (**2026-08-12**).

| Part | Shipped |
|---|---|
| **A** | `data-wanos-offline` + yellow checklist; Resource Timing admin modal + console; REST heartbeat 10s; cold `init()` only |
| **B** | SSE debounce + reload-suppress (`wanosApp` + `zwaveconfig`); `core/reload_alerts.py`; scope rows `full` / `hue_presets` / `timers_types` |
| **C** | `PAGE_VERSIONS` **v1** × eight shell pages (`wanos-shell.js`); kiosk/login excluded |
| **D** | `hue_presets` fast path + Explorer chip/save-disable; &lt;2s CRUD; no full recycle |

**B10G DoD:**

- [x] Part A: **two overlays** — shared `data-wanos-offline` + yellow load checklist; per-step durations on checklist + dismissable floating admin debug modal + console; **`wanos_debug.log` out of DoD**; load failure → red shared offline; post-save refresh uses B10F busy overlay only (not checklist). *(B10G shipped auto-open after load; **B10K** ✅ superseded — stopwatch right of `vNN`, no auto-open.)*
- [x] Part B: SSE **A+B+C** (Pi repro **confirmed 2026-08-12**); T4 C exact per-scope suppress strings; alerts on **all** reload sources; unscoped API → **`full`** row (Option A); Admin GO **`full`** copy; `wanosApp` + `zwaveconfig.html`.
- [x] Part C: **Eight shell pages** show admin-only **`vNN`** (each **`v1`** at ship); **`kiosk.html` excluded**; agent reports bump per touched page.
- [x] **Part D:** Re-run Pi smoke on shipped B9A scoped path; verify + finish alerts, Explorer chip/save-disable UX; **&lt;2s** add/rename/delete; no integration recycle logs.
- [x] Pi smoke: cold open on slow path (checklist + modal); **config reload** — no spurious NOT CONNECTED if Part B landed; **hue preset CRUD** — no spurious NOT CONNECTED if Part D landed.
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

#### A — Automations load checklist + timings + log (shipped)

**Two overlays on Automation** (see [`pipeline.md`](pipeline.md) § B10G — **Automations — two overlays**):

1. **Shared offline** — `data-wanos-offline` + `wanos-shell.js` (same as Explorer); real backend/stream down.
2. **Load only** — yellow checklist; cold `init()` → `refreshAll()`; **not** post-save refresh.

**Checklist steps (shipped — Option A):**

| # | Friendly label (overlay) | Work | API (log line) |
|---|---|---|---|
| 1 | Device state | `GET /api/state` | `GET /api/state` |
| 2 | Automations | `GET /api/automations` | `GET /api/automations` |
| 3 | Events | `GET /api/events` | `GET /api/events` |
| 4 | Building library | Parse JSON; `rebuildLibraryRows()`; `rebuildEntityOptions()`; presets; rule reselect | *(no single API — log as step name)* |
| 5 | Schedule status | `GET /api/automations/fire-status` | `GET /api/automations/fire-status` |

Steps **1–3** run in parallel (`Promise.all`). Overlay **2** clears after library build (**B10H** — fire-status deferred). REST heartbeat **10s**. Timings: console + admin modal with Resource Timing breakdown (wire TTFB / nav→byte / before fetch / totals) + **`coldTimeToInteractiveMs`**. Open via **B10K** stopwatch (no auto-open). **`(parallel)` label removed** (**B10H**). **`wanos_debug.log` — out of DoD**.

#### B — “NOT CONNECTED” — assess + fix (shipped)

SSE **A+B+C** on `wanosApp` + `zwaveconfig.html`. Reload alerts: scope-specific, 3 levels; unscoped writers → **`full`** until **G6**. Detail → [`pipeline.md`](pipeline.md) § B10G Part B.

#### C — Admin page version badge (shipped)

Eight shell pages @ **`v1`**; `login` / `kiosk` excluded. Bump per page when HTML or linked JS changes.

#### D — Hue preset CRUD lightning reload (shipped)

`hue_presets` scope only — no full bridge recycle. Explorer chips + save-disable. Pi smoke &lt;2s / no NOT CONNECTED / no NVRAM/Z-Wave/Onkyo recycle logs.

**Out of scope (unchanged):** boot autostart → **G8**; **G6** Admin 12-checkbox modal. Cold-load shorten → **B10H** ✅.

---

### Phase B10H — Automations cold-load shorten wait ✅ DONE (2026-08-12)

**Shipped summary:** Cut Automations cold open from ~**39 s** → ~**2.1 s** TTI. Operator ship bar accepted (**2026-08-12**); Admin/Explorer SSE flicker fixed. List/v2 cache for sub-**500 ms** **deferred** (pipeline § deferred list cache). Post-restart ~10 s offline → **G8**.

| Lever / fix | Shipped |
|---|---|
| **1a** | `asyncio.to_thread` on `GET /api/state`; REST snapshot **cache** refreshed on queue drain + boot warm |
| **1b** | Event-driven SSE hub (`core/sse_hub.py`) — push on drain; **5 s ping**; no 0.5 s poll. **C23** (2026-08-16): `SseClient` `@dataclass(eq=False)` + immediate connect ping + pure ASGI (B10H `set.add` was unhashable) |
| **2** | `refreshAll` in-flight guard (`blocky.js`) |
| **3** | SSE connect guard (`app.js` / `wanosApp` only) |
| **4** | Clear yellow overlay after library; defer fire-status; **`coldTimeToInteractiveMs`** |
| **5+** | YAML N+1 fix (`GET /api/automations` one load + catalog map); `GET /api/events` read-only (seeds at boot) |
| **Reconnect** | Fresh snapshot (&lt;60 s) → no NOT CONNECTED flash; skip REST on reconnect if &lt;30 s; `EventSource.onopen` marks alive |
| **UX** | Removed `(parallel)` checklist labels |

**Pi smoke actuals (operator 2026-08-12):**

| Metric | Baseline | Shipped |
|---|---|---|
| Cold open / TTI | ~**39 s** | ~**2.1 s** |
| `GET /api/state` | ~19 s under load | ~**20–30 ms** |
| `GET /api/automations` / `events` | ~19–21 s | ~**2 s** (one YAML parse) |
| Admin SSE flicker during Blocky load | Yes (~3 s) | **Fixed** (operator) |

**B10H DoD:**

- [x] **Operator approved** § B10H design — Wannes — **2026-08-12**
- [x] Kickoff profiling: baseline + case **A** + case **C** (**Y**) — **2026-08-12**
- [x] Levers **1–4** (+ snapshot cache, YAML N+1, reconnect R1–R3, label cleanup) shipped
- [x] Pi smoke: actuals vs ~**2 s** goals — TTI ~**2.1 s**; ship bar OK; flicker fixed — **2026-08-12**
- [x] Instrumentation updated (TTI, deferred fire-status, no parallel labels)
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-12**

#### Deferred (not DoD)

List / v2 cache at boot — triage **2026-08-12**: defer until **&lt; 500 ms** cold open wanted. → [`pipeline.md`](pipeline.md) § **B10H — deferred list cache**.

#### Locked decisions archive (kickoff)

| # | Decision |
|---|----------|
| 1 | Operator approved design before code |
| 2 | Ship bar = minimum improvement — operator states at ship (**accepted 2026-08-12**) |
| 3 | `editorLoading` until library displayable; fire-status deferred |
| 4 | TTI = empty canvas OK |
| 5 | Lever #3 = `wanosApp` only (not Z-Wave) |
| 6 | Acceptance = case B (Admin open) |
| 7 | Page-scoped reload writers → **G6** |

**Root cause (locked):** (1) sync `get_state_snapshot` + SSE poll blocked single worker; (2) double cold `refreshAll`; (3) later: N+1 YAML on automations list + merge-on-every-events-GET.

**Out of scope (unchanged):** **G8** boot autostart; **G6** scoped reload; nginx as primary fix; list cache (deferred). Explorer Control live lag after event-driven SSE / optimistic UI → **C18** ✅. Hub `SseClient` unhashable / dead EventSource → **C23** ✅.

---

### Phase B10I — Used SE → Go to SR 🔜 TODO

**Origin:** operator inbox **2026-08-12**. **After B10F** ✅. Size **low**. **Parallel:** may run beside **B10H** and Ships **B2–B8** — no B19 dependency ([`pipeline.md`](pipeline.md) § Parallel tracks). **One SR per SE** (catalog invariant) — mirror of B10F item 6 (**unused SE → create SR**).

**Intent:** When viewing a **used** **SE** (listening SR exists), add **Go to SR** — selects/opens the companion **SR** in the Library (scroll + focus editor).

**Out of scope:** Multi-SR per SE; changing SR/SE bind rules.

**B10I DoD:** Used SE view shows **Go to SR**; opens the single companion SR; Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B10J — Event Received log catalog name 🔜 TODO

**Origin:** operator inbox **2026-08-12**. Backend logging — **not** Blockly UI. Size **low**. **After B10B** ✅ (catalog UUID bus). **Parallel:** may run beside **B10H** and Ships **B2–B8** ([`pipeline.md`](pipeline.md) § Parallel tracks).

**Operator request (verbatim):**
> - log: "2026-08-12 12:06:26.315 | INFO     | Event Received [856d0f0d-1f6b-4a1a-ace8-a5856a5ee491]: {'origin': 'MANUAL'}" add proper name

**Locked triage intent:**

* When `state_manager` logs **`Event Received […]`** at INFO, bracket text = **catalog display name only** (e.g. **`Cinema rolluik half`**) — **no UUID**.
* Internal enum events (`HUB_STATE_CHANGED`, …) unchanged.
* **Out of scope:** full **B16** full-bus UUID refactor; **G7** integration log tags.

**B10J DoD:** Manual/catalog events log readable name on Pi smoke; internal events unchanged. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B10K — Automations timings + shutter OPEN/CLOSED + RFX ON/OFF ✅ DONE (2026-08-15)

**Shipped summary:** One code run with **G3**. Pi smoke OK (operator **2026-08-15**). Automations timings modal no longer auto-opens — **stopwatch** immediately right of `vNN`. Shutter Blockly **OPEN / CLOSED** only (no FORCE, no POS). Visible UI **shutters** (Library titles **Shutters open/close**; catalog display names; Hidden-devices type column). RFX **ON/OFF**, no Hue color (`wantHue` excludes `rfxcom`). Identifiers unchanged (`blinds.*`, `BLINDS_*`, UUIDs). YAML leftovers coerce in UI until Save. Load-fail red NOT CONNECTED unchanged → **B10L**. Inbox leftover **living schemer color** → **B10N** (closed **2026-08-15** as already covered by Item 3).

| Item | Shipped |
|---|---|
| **1** | Stopwatch right of `vNN`; disabled while `editorLoading` / no snapshot; modal + console unchanged; no auto-open |
| **2** | Native `blinds`/`shutter` and `blinds.*` win typing before switch; Set/if OPEN/CLOSED; YAML ON→OPEN, OFF→CLOSED, mid-%→OPEN |
| **3** | Origin `rfxcom` even when typed light: ON/OFF, no Hue color/preset (`wantHue` excludes `rfxcom`) |

**B10K DoD:**

- [x] Timings only via stopwatch after successful load (no auto-open; not clickable while loading)
- [x] Load-fail NOT CONNECTED unchanged (**B10L**)
- [x] Shutter Blockly OPEN/CLOSED (no FORCE, no POS); visible “blinds” → “shutters” including Library rule titles
- [x] RFX ON/OFF no color
- [x] G3 interval in same code run
- [x] Pi smoke — **2026-08-15**
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-15**

#### Locked decisions archive (Q&A 2026-08-15)

**Item 1 — load-timings modal (B10G follow-up):** No auto-open. Stopwatch immediately right of `vNN`. Automation already admin-only — no extra `isAdmin`. Not clickable while yellow load (`editorLoading`). After successful load: button enabled; modal content unchanged. Load failure / red NOT CONNECTED: no change this run → **B10L**. Do not put `errorMessage` in the timings modal.

**Item 2 — shutters:** Root cause was `rebuildEntityOptions` defaulting missing `resolved_product_type` to `switch` so `blockyEntityTypeOf` returned switch before `blinds.*`. Operator-facing **shutters** on all visible UI. Do **not** rename `blinds.*` eids, `config.yaml` `blinds:`, `BLINDS_*` keys, UUIDs, internals. Strip FORCE only on shutter devices; Z-Wave switches keep FORCE. No POS / open % this ship — later **B9C** ✅ (**2026-08-16**). Engine + Explorer already do closed-% including mid.

**Item 3 — RFX (separate from shutters):** Origin `rfxcom` even when `device_product_types` is light: ON/OFF only, no Hue color. Engine already always-force RFX — Blockly must not show FORCE. Inbox **2026-08-15** living schemer still shows color → **B10N** (closed **2026-08-15** as already covered here; do not reopen this Done ship).

**Out of scope (unchanged):** Domoticz Set (**B19**); Hidden preset (**C12 #9**); alert persist (**C17**); NOT CONNECTED copy (**B10L**); entity_id / config key / EventType renames. (B9C if-% ✅ shipped **2026-08-16**.)

---

### Phase B10L — NOT CONNECTED overlay status 🔜 TODO

**Origin:** operator inbox **2026-08-13** (screenshot 2). **Copy line 2026-08-15.** Shared shell overlay (`data-wanos-offline`) — **all SSE pages** that use it (Automations, Explorer, Admin, WISC, History, …). Size **low**. **Parallel:** beside **B2–B8**. Extends **B10G** overlay **1** (not overlay **2** yellow checklist).

**Covering operator request (verbatim):**
> - the modal after load for the automation page: don't display it after load but have a small button top-left (right of the page-version) that displays it
> - + 4 screenshots attached

**Operator request (verbatim from screenshot):**
> possible to put some info: connected, receiving x%, ...?

**Operator request (verbatim, triage 2026-08-15):**
> change "Establishing connection stream to WanOS backend..." to "Re-connecting to WanOS..."

**Locked triage intent:**

* Keep heading **NOT CONNECTED**.
* Establishing line becomes **`Re-connecting to WanOS...`** (replaces `Establishing connection stream to WanOS backend...`). Same string on every shared-overlay page.
* Add **honest status** under it: e.g. connecting / snapshot received / SSE open / waiting — **not** a fake percentage.
* Real **%** only if a true progress metric exists at kickoff (otherwise omit %; use milestones).
* Same copy on every page that uses the shared overlay.

**Out of scope:** Yellow Automations load checklist (overlay **2**); timings modal (**B10K** ✅). Do not respec overlay 1 in **B10G** shipped notes — this ship supersedes the establishing line.

**B10L DoD:** Overlay copy **Re-connecting to WanOS...**; live connect milestone (and % only if real); Pi smoke reconnect + cold open. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B10M — Explorer Hue preset duplicate settings 🔜 TODO

**Origin:** operator inbox **2026-08-15**. Explorer Hue preset CRUD (B9A / B10G Part D) — **not** Automations save (**G6**), **not** G2 color truth. Size **low**. **Parallel:** beside **B2–B8** (after **B10G** Part D ✅).

**Operator request (verbatim):**
> bugfix: cannot save another preset with the same settings as an already existing preset

**Locked triage intent:** Operator can save a **new** Explorer Hue preset whose color/bri/xy **matches** an existing preset (new name/key). Display-name uniqueness (B9A) stays. Not a second G6/B10G-D ship.

**B10M DoD:** New preset with same settings as an existing one saves; Pi smoke Explorer. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B10N — RFX living schemer still shows color ✅ DONE (2026-08-15)

**Closed without a dedicated code run.** Operator **2026-08-15:** cannot reproduce; **probably fixed in earlier phases, likely B10K**. Same RFX no-color rule as **B10K** Item 3 (`wantHue` excludes origin `rfxcom`, including `rfx.living_schemer` typed `light`).

**Operator request (verbatim, inbox 2026-08-15):**
> bug: automation editor: for rfx device "living schemer switch" a 'color' is selectable: that is wrong

**Why closed:** Split off closed **B10K** so that ship stayed Done. No extra Blockly hole was found after the operator re-checked. Do not reopen **B10K**.

**B10N DoD:**
- [x] No dedicated code — covered by **B10K** Item 3
- [x] Operator cannot reproduce (close command **2026-08-15**)
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-15**

---

### Phase B11 — Multi-flow one Blockly page (Ship B8) 🔜 TODO

**Depends on:** **B19** (Ship **B3**) — gate before kickoff. N independent If/Do graphs under one Library entry — reassess tension with B6B **after** Domoticz canvas lands.

**Ship with B12** — one PR.

**Operator request (2026-08-16, verbatim):**
> this should be possible - put that in the pipeline where it fits

**Intent (locked into B11 — not H4 / not soften B13 first-match):** After B19 migrator, rules with **non-exclusive parallel cases** (legacy “all matching cases run”) were split into multiple Library rows — e.g. **`--- CINEMA OFF`** + `(2)` + `(3)`, **Evening lights on** + `(2)`. Operator wants **one Library rule / one Blockly page** that can express that again.

**Engine / authoring target (stub — lock at kickoff):**
- Multiple **If/Do** roots on one page (multi-flow).
- On wake: **every matching If/Do runs** (non-exclusive). Else-if / Else **within** one chain stays **first-match** (B13 / B19 — unchanged).
- **Not** Ship **B4** (H4 = nested AND/OR in Compare only).
- Cutover: hand-merge or helper to reunite migrator splits after B11 lands.

**B11 DoD (stub):** multi-flow authoring + load/save + engine semantics locked (**all matching If/Do fire**); reunite smoke for CINEMA OFF-style + Evening lights on-style; Pi smoke; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B12 — Rule-list folder/tag (Ship B8) 🔜 TODO

**Depends on:** **B19** (Ship **B3**) — gate before kickoff. Library organization via folder and/or tag.

**Ship with B11** — one PR.

**B12 DoD (stub):** folder/tag model + list UX + persistence; Pi smoke; **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B13 — Domoticz Else-if / Else (Ship B3 with B19) ✅ DONE (2026-08-17)

**Origin:** operator inbox **2026-08-10** (HA **H11**). Shipped with **B19**.

**Shipped:** Else-if / Else gear; **first match wins** (intentional Domoticz divergence). Covered by B19 DoD + Pi smoke (**2026-08-17**).

**Last DoD:** with B19 docs audit **2026-08-17**.

---

### Phase B14 — Domoticz timed Set & HA patterns (Ship B7) 🔜 TODO

**Not B9A/B9B.** H1 sustained-for · H2 delay/wait · H3 cooldown · H6 input_number · H7 presence/mode · H8 area trigger · H9 sun elevation · H10 blueprints. (**H11** → **B13** with **B19** / Ship **B3**; **H4** ✅ **B4**; **H5** → **B6**; **H12 bathroom** → **B5** Option A.)

**Excludes:** Domoticz **Time trigger** (every minute) → **B20** after **F**. User variables · debug block.

**Depends on:** **B19+B13** (Ship **B3**) ✅; **Ship B4** (H4) ✅ — gate before kickoff.

#### B5 kickoff deferred here (2026-08-17)

**Origin (verbatim 2026-08-17):** ok, A for now - put the rest in the pipeline in the existing future phases

Pick subset + order at **B14 kickoff**. Not in Ship **B5**.

| # | What | Maps to |
|---|---|---|
| **1** | Bathroom **5 min min-runtime** / `90001` / HA `min_cycle_duration` (minimum ON, then re-eval humidity — **not** Domoticz Set-for-X which forces OFF at timeout). **Includes:** B5 humidity rule Set OFF **ignores** `90001`, so a **74-crossing can turn the vent OFF while shower rolling overrun is still running** — restore so climate/shower OFF waits out the lock. Optional: generalize beyond 1e. | H1 / H3 / timed Set — pick at kickoff |
| **2** | Explicit numeric Compare **level vs edge-cross** (B5 keeps edge-cross only) | Compare mode; not B9A reopen |
| **3** | **Auto / Manual** override switch so a level (or hygrostat) rule does not kill Explorer ON | H7 presence/mode |
| **4** | **Generic hygrostat** helper (sensor + switch + high/low or target+band) — not a Library If/Else-if | H6 helpers |
| **5** | Dedicated **H12 Schmitt** Blockly block (latch on high, clear on low; act on latch edges) | original H12 block; B5 uses If/Else-if instead |
| **6** | Boot / sweeper **replay** of current humidity so a missed crossing recovers without waiting for the next edge | sweeper; B5 drops Audit B |

**B14 DoD (stub):** pick subset + lock order at kickoff; Domoticz **Set for X minutes** / **Set after X seconds** where selected; include or explicitly skip the B5-deferred rows above. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

### Phase B20 — Domoticz Time trigger 🔜 TODO (after **F**)

**Origin:** operator lock **2026-08-12**. Domoticz **Time** trigger mode — evaluate script on schedule (e.g. every minute) with time compares in **If** ([Domoticz Triggers — Time](https://wiki.domoticz.com/Blockly#Triggers)).

**Depends on:** **F** — gate before kickoff; **B19** (Ship **B3**) — gate before kickoff.

**Until B20:** system catalog events (blinds open/close, twilight, …) + `if time` / dark-light conditions — unchanged (B10B+E).

**Out of scope:** user variables · debug block.

**B20 DoD (stub):** Time trigger mode + time-compare blocks on Domoticz canvas; Pi smoke; no regression on catalog schedule events. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

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

**B17 DoD:** written assessment (devices switched; keep-in-code vs rule candidates; recommended disposition). **No code cutover** unless a later phase is opened. Leftover plant-in-code after B17 → **P** [`phaseP-portability.md`](phaseP-portability.md). **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

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