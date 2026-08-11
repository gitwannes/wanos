# ⚡ WanOS Phase D — Device typing

Product **light** vs **switch** for binary actuators, plus origin-neutral **`entity_id`** rehome for Z-Wave / RFX. Cross-cuts Explorer, **Timers & types** (renamed from Auto-off timers), Planned Automations, auto-off, and Blocky consumers — **not** Blocky editor chrome.

**Status:** ✅ **DONE** — D1 + D2 Pi smoke OK **2026-08-11** (Admin Debug GREEN; automations / auto-off / hide / Epson / vent). Migrators + D2 backup folder deleted **2026-08-11**.

**Related:** Shell → [`phaseC-shell.md`](phaseC-shell.md) (**C2** Planned Automations). Blocky → [`phaseB-blocky.md`](phaseB-blocky.md). Sequence → [`pipeline.md`](pipeline.md).

**Sequence (historical):** **D1** then **D2** (hard cutover migrator on Pi; no dual-read). Next in pipeline = **B9A**.

---

## Sub-phases

| Sub-phase | Delivers | Size |
|---|---|---|
| **D1 — Timers & types + resolved type** | Product type SoT, page rename, Explorer filters/labels, Z-Wave read-only resolved type, scoped reload | mid |
| **D2 — Entity id rehome** | `zwave.*` / `rfx.*` / `zwave.vent.*` migrator; birth rules; Admin Debug GREEN | mid |

---

## Core model

### Two “types” (do not conflate)

| Concept | Meaning | Where set |
|---|---|---|
| **Provisioning type** | Z-Wave idx band / endpoint class (binary, shutter, motion, power, temp_hum, …) | Z-Wave Config (`zwaveconfig.html`) |
| **Product type** | Operator **`light`** \| **`switch`** for policy/UI | **Timers & types** only (override); birth default **`switch`** |

### Resolved product type

```text
resolvedType(eid) =
  if origin == hue          → light   (no override)
  else if override[eid]   → override value
  else                    → switch    (birth default)
```

- **No name-token infer** (`licht`, `lamp`, … not used).
- One-shot **D1 migrator** seeded `device_product_types` overrides for eligible devices (deleted after soak). **No re-infer on rename.**

### SoT — `device_product_types`

In **`automations.auto.yaml`** (surgical write from Timers & types API):

```yaml
device_product_types:
  # Optional overrides only; omit → birth default switch
  zwave.buro_licht: light
```

- Save → scoped reload: **`auto_off` + metadata** (not full G6 recycle).

---

## D1 — Timers & types + resolved type

### Page rename

- Admin label: **Auto-off timers** → **Timers & types**.
- File `lightingautooff.html` may keep filename (C4 HTML renames are separate); **nav/title** use **Timers & types**.

### Timers & types UI

| Row kind | On page | Product type column | Auto-off |
|---|---|---|---|
| Z-Wave / RFX binary actuators (in scope) | Yes | **Editable** `light` \| `switch` | Editable (if eligible) |
| Hue physical relays (`*hue_physical*`, Z-Wave) | Yes | **Editable** `switch` (Hue in name only) | As today |
| `switch.vent.toilet_ventilatie` | Yes | **Editable** (normal switch) | As today |
| `zwave.vent.*` motors | Yes | Read-only **`switch`** | As today |
| SSR / safety | Yes | Read-only **`switch`** | Denied / as today |
| `switch.epson` | Yes | Read-only **`switch`** | Denied (projector) |
| Speakers | Yes | Read-only (speaker) | Out of auto-off |
| Shutters, motion, temp/power/voltage sensors, door, fluid, Hue mesh | Yes | Read-only (intrinsic type) | Out of auto-off / intrinsic rules |

**Hue physical relays:** **`switch`**, not Hue devices. **Soft-hide** via `deviceexplorer_hide` only — **not** hardcoded hidden; operator can un-hide on Hidden devices page.

**Unsaved UX:** dirty fields (Auto-OFF active, Type, Effective, General/Type defaults, Hide checkbox) use amber highlight until Save.

### Z-Wave Config (`zwaveconfig.html`)

- **Unified binary pool** **71000–72999** — keep **existing idxs** (no moves); drop Light(71x) vs Switch(72x) product split → single **Binary (71–72x)** provisioning option.
- **Read-only** resolved product type (default / override from Timers & types); **no write** to `device_product_types`.
- **Inbox (unmapped):** default provisioning **`switch`**; drop **CC 25** from inference surface (remove `cc === "25"` branch).
- **Provisioning dropdown:** keep **Temp&Hum (76x)**; drop generic **Sensor (76x)** duplicate. Future CC49 illuminance (e.g. `87/49/0/Illuminance`) → **`sensor.generic`** (out of product typing).
- Existing **type column** shows resolved product type (no extra column).

### Explorer filters & labels

| Filter | Rule |
|---|---|
| **HUE** | `origin === 'hue'` |
| **LIGHT** | `resolvedType === 'light'` **and not Hue** |
| **SWITCH** | `resolvedType === 'switch'` (includes vents, SSR, safety, Epson, Hue physical, …) |
| **SHUTTER** | shutter / rolluik devices (user-facing rename from BLINDS) |
| **SENSOR** | temp, temp_hum, hum, power, energy, voltage, motion, generic sensor, **door**, **fluid**, … |

- **Door** (`10001`, `10002` from `config_hardware.yaml`, `type: door`) and **fluid** (`11002`, `11003`) → **SENSOR** filter only.
- **Display:** Hue origin → **“Hue light”**; all other `light` → **“light”**. History type chips follow the same rule.

### Terminology — shutters (rolluik)

- User-facing docs/UI: **shutter** / **rolluik**, not “blinds”.
- **`blinds.*` entity_ids** and internal `device_type: blinds` unchanged in **D2** (typing phase only); rename display strings and Explorer **SHUTTER** filter in **D1**.

### Consumers (D1)

| Consumer | Behavior |
|---|---|
| Auto-off type tier | Uses **resolvedType** |
| Planned Automations | Show resolved type (`light` / `switch`) |
| Blocky color UI | **`origin === 'hue'`** only — not `resolvedType === 'light'` |
| Blocky ON/OFF wording | Non-Hue `light` = ON/OFF only |

### D1 DoD

- [x] **Timers & types** page live (rename + editable product type for in-scope rows).
- [x] **`device_product_types`** SoT + API; scoped reload on save.
- [x] Birth default **`switch`**; Hue always **`light`**.
- [x] Z-Wave Config: unified 71–72 binary pool; read-only resolved type; CC25 removed from inbox heuristic.
- [x] Explorer **HUE** + **LIGHT** + **SWITCH** + **SHUTTER** filters; door/fluid under SENSOR.
- [x] Labels: Hue → “Hue light”; other lights → “light”.
- [x] D1 one-shot migrator (optional overrides seed) run on Pi; deleted after soak.
- [x] Pi smoke: Timers & types, Explorer filters, Planned Automations type, Blocky no color on non-Hue light.
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** (with D2 close-out)

---

## D2 — Entity id rehome

**Cutover:** one-shot migrator on Pi; **hard cutover** (no alias map / dual-read). Migrator deleted after soak (same habit as B10B).

### Id map (locked)

| Class | Before | After |
|---|---|---|
| Z-Wave binary actuators | `switch.<slug>` | `zwave.<slug>` |
| RFX actuators | `switch.<slug>` | `rfx.<slug>` |
| Vent **motors** | see table below | `zwave.vent.*` |
| Wall switch → vent motor | `switch.vent.toilet_ventilatie` | **`switch.vent.toilet_ventilatie`** (unchanged) |
| SSR / safety | `switch.ssr.*`, `switch.safety.*` | **unchanged** |
| Epson | `switch.cinema_projector` | **`switch.epson`** |
| Hue, doors, fluids, sensors, shutters, speakers | existing prefixes | **unchanged** |

**Vent motor slugs (D2):**

| Old | New |
|---|---|
| `switch.vent.toilet_ventilatie_motor` | `zwave.vent.toilet_motor` |
| `switch.vent.badk_2e_ventilatie` | `zwave.vent.badk_2e` |
| `switch.vent.badk_1e_ventilatie` | `zwave.vent.badk_1e` |
| `switch.vent.sauna_ventilator` | `zwave.vent.sauna` |

**Examples:** `switch.53` → `zwave.53`; `switch.buro_licht` → `zwave.buro_licht`; RFX `switch.cinema_schemer` → `rfx.cinema_schemer`.

### Migrator rewrite scope (from code audit)

**YAML / registry**

| File | Keys / refs |
|---|---|
| `entity_registry.auto.yaml` | All remapped `entity_id` rows |
| `automations.auto.yaml` | `automations:` rule `entity_id` refs; `auto_off_devices:` (`managed_auto_off`, `auto_off_delays`); `deviceexplorer_hide`; **`device_product_types`** (D1) |
| `config.yaml` | `hardware_links.power_meters` **keys** (`switch.pc` → `zwave.pc`, etc.) |

**Python**

| File | Why |
|---|---|
| `core/entity_registry.py` | `classify_entity_prefix()` birth rules for `zwave.*`, `rfx.*`, `zwave.vent.*` |
| `core/entity_id_list.py` | Origin / enrichment helpers |
| `core/well_known_entities.py` | `ENTITY_BATHROOM_VENT` → `zwave.vent.badk_1e`; Epson constant → `switch.epson` |
| `core/auto_off_policy.py` | `AUTO_OFF_DEVICE_DENY_EIDS` projector entry; **`metadata_type_for_eid()`** recognizes `zwave.*` / `rfx.*` |
| `core/event_handlers/hub_handlers.py` | Epson `entity_id` intercept |
| `core/entity_registry_check.py` | Unchanged logic; must pass on new ids |

**Frontend**

| File | Why |
|---|---|
| `frontend/lightingautooff.js` | `DEVICE_DENY` projector eid |
| `frontend/blocky.js` | **`blockyEntityTypeOf` / `blockyIsActuatorEntity`**: `zwave.*` / `rfx.*` |
| `frontend/app.js` | Explorer filters: **HUE**, **LIGHT**, **SHUTTER**; resolved-type rules (D1) |

**Other**

| File | Why |
|---|---|
| `hardware/simulator.py` | `ENTITY_BATHROOM_VENT` |
| `docs/**`, `readme.md` | Reference tables, examples |

**Not in migrator** (no `switch.*` D2 renames): `history.tracked_entities` (uses `sensor.power.*` only); hard-deny `switch.safety.safety_wisc_5v`; `switch.ssr.*`; rules referencing only Hue / door / sensor ids.

### Birth rules (post-D2)

| Origin | New `entity_id` pattern |
|---|---|
| Z-Wave binary | `zwave.<slug>` |
| Z-Wave vent motor | `zwave.vent.<slug>` |
| RFX | `rfx.<slug>` |
| Epson | `switch.epson` |
| SSR / safety | `switch.ssr.*` / `switch.safety.*` |
| Hue | `hue.light.*` / `hue.group.*` (unchanged) |

### D2 DoD

- [x] Migrator `--dry-run` / `--write` (`helpers/migrate_d2_entity_ids.py`); workspace + Pi YAML rewritten.
- [x] Pi deploy + restart; **Admin Debug GREEN**.
- [x] Automations + auto-off + hide + hardware_links smoke on Pi.
- [x] Migrator (+ D2 backup folder) deleted after soak (**2026-08-11**).
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## Z-Wave MQTT path defaults (reference)

Paths from **Z-Wave JS UI** MQTT: `{nodeId}/{commandClass}/…` — **not Hue**.

| CC | Class | Inbox default (unmapped) | Runtime mapped | Idx band |
|---|---|---|---|---|
| **37** | Binary switch | **`switch`** (F4) | `switch` | 71000–72999 |
| **38** | Multilevel switch | `shutter` | `shutter`* | 73000–73999 |
| **48** | Binary sensor | `motion` | `motion` | 75000–75999 |
| **49** | Multilevel sensor | path: power → `power`; temp/humid/air → `temp&hum` | power / sensor formatting | 74000 or 76000 |
| **50** | Meter | `66561` → voltage sensor; else `power` | same | 74000 / 76000 |

\* User-facing **shutter**; runtime metadata may still use legacy `blinds` until enum rename lands.

**CC 25:** not used — removed from inbox heuristic.

**Sensor families (product typing out of scope):**

| Family | Example idx / source |
|---|---|
| `sensor.temp_hum` | SHT11 **20001/20002** (temp **and** hum); Z-Wave **76002/76003** (temp-only ok) |
| `sensor.motion` | Z-Wave **75001/75002** |
| `sensor.power` | Z-Wave **74001/74003** |
| `sensor.voltage` | **71046** mains |
| `sensor.generic` | Future illuminance CC49 |
| `sensor.door` | **10001/10002** hardware YAML |
| `sensor.fluid` | **11002/11003** hardware YAML |

---

## Out of scope for product light/switch override

Shutters, **`zwave.vent.*` motors** (read-only switch), SSR, safety, Epson (read-only switch), speakers, motion, temp/power/voltage/generic sensors, door, fluid, Hue mesh.

**In scope for override:** Z-Wave + RFX **binary actuators**, plus normal switches (`switch.vent.toilet_ventilatie`, Hue physical relays).

---

## 🚦 Decisions locked (summary)

1. **D1** then **D2**; hard cutover migrator(s).
2. **Timers & types**; override only there; Z-Wave Config read-only resolved type.
3. Birth product default **`switch`** (F4); no name-token infer.
4. **`device_product_types`** SoT (D4 confirmed); scoped reload.
5. Explorer **HUE** + **LIGHT** (non-Hue) + **SWITCH**; door/fluid → **SENSOR**.
6. Hue physical = **`switch`**, soft-hide only (operator can un-hide).
7. **`switch.vent.toilet_ventilatie`** stays, editable; four vent **motors** → **`zwave.vent.*`**.
8. Epson → **`switch.epson`**; treated as switch (auto-off denied as today).
9. D2: **`zwave.*`**, **`rfx.*`**, vent motor map; keep **`switch.ssr/safety`**, **`switch.vent.toilet_ventilatie`**.
10. CC25 removed; unified 71–72 binary pool; drop Sensor(76x) duplicate.
11. User-facing **shutter/rolluik** terminology (D1 display).

## ❓ Residual Open Qs

**None.**
