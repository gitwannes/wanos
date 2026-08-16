<!-- --- file: docs/integration-playbook.md --- -->
# WanOS new-integration playbook

Reusable checklist for adding a vendor bridge (G9–G13 and any later letter). Drawn from shipped Hue / Z-Wave / RFX / Sonos / Onkyo / Epson / OWM plus the locked **C18** command-commit contract.

This playbook is **not** a kickoff and does **not** pick libraries, IDX bands, or Admin / Blockly / G6 rows. Those stay **per-ship kickoff**. Ship-specific stubs: [`docs/todo/phaseG-integrations.md`](todo/phaseG-integrations.md) § G9–G13.

---

## 0. Gates (before any code)

1. The item is already in the pipeline (**G9→G13** or a later letter). If it is not: **triage** — do not invent a ship.
2. **Kickoff** that ship. Do not implement until kickoff answers are in the phase file **and** the operator says implement / ship / patch.
3. **One integration per code run.** Never combine G9–G13.
4. **Library choice is in-scope of that kickoff**, not this playbook.
5. Credentials / IPs / device maps = **home pack (P)**. Engine code stays generic.

---

## 1. Classify the bridge (kickoff, first)

| Kind | Examples | C18 outbound? | Typical events |
|---|---|---|---|
| **Telemetry-only** | OWM; likely G10 P1/kWh, G12 SMA | No | `TEMP_UPDATED` / `HUMIDITY_UPDATED` / `POWER_UPDATED` / `KWH_PULSE` / custom poll |
| **Commandable** | Hue, Z-Wave binary, RFX, Epson, Sonos, Onkyo; likely G9 HVAC fire, G11 power/setpoint | **Yes** | Outbound `HUB_STATE_CHANGED` + inbound echo with `origin: "<vendor>"` |
| **Mixed** | Hue (command + SSE); likely G13 cycle state + start/stop; G10 Energy Socket if it switches | C18 **only** on commandable idxs | Both |

C18 does **not** apply to GPIO PWM, OWM, or any poll that is not a WanOS-originated device command.

Also lock at kickoff (already called out in G9–G13):

- Admin enable row?
- Explorer Control widgets (ON/OFF vs setpoint vs kWh vs cycle text)?
- Blockly surface (existing `HUB_STATE_CHANGED` vs new action types)?
- G6 scoped-reload row? (**G6 catalog is locked at 12 rows today** — see § 8.)

---

## 2. General-purpose / home pack (hard rule)

**Engine (Python/JS)** may contain: protocol, mapping, health, C18, logging, UI *behavior*.

**Home pack (YAML / `.env` / registry)** must contain: IPs, URLs, usernames, **all IDX numbers**, tokens/keys, device maps, poll intervals, names.

Do **not**:

- Hardcode Pi IPs, Hue-key paths, credentials, or IDX literals in new code.
- Copy Epson’s `80001` pattern in `entity_id_list.py` — that is a known P leak; new bridges must enrich from **their config map**, not a magic idx.
- Put plant names (`badk 1e`, Borsbeek, cinema) in Python.
- Invent a second config system or settings UI.

**Config shape (existing pattern):**

- Block in `config.yaml` **or** a dedicated file like `config_hue.yaml` if the map is large.
- Secrets in `.env` (not git), read via `os.getenv` with optional YAML fallback — same as Hue `HUE_API_KEY`.
- `device_map` keyed by idx → vendor id + display name (Sonos / Onkyo / Hue style).
- Document every new YAML key **next to the key**.
- IDX **band comment** in `config.yaml` (the `# 500xx : Hue` block).

If an edit would *move* an existing hardcode into config: **propose, ask, do not apply**. Cursor rule: [`.cursor/rules/general-purpose-code.mdc`](../.cursor/rules/general-purpose-code.mdc). Portability phase: [`docs/todo/phaseP-portability.md`](todo/phaseP-portability.md).

---

## 3. IDX, `entity_id`, metadata

### Occupied bands (do not reuse)

| Band | Origin |
|---|---|
| `100xx` | GPIO inputs |
| `200xx` | SHT11 |
| `20101`, `2100x` | Sauna/IR virtual |
| `220xx` | Host gauges |
| `30001` | OWM |
| `400xx` | RFX |
| `500xx` | Hue |
| `600xx` | Sonos |
| `610xx` | Onkyo |
| `7xxxx` | Z-Wave (sub-bands in `config_zwave.auto.yaml`) |
| `80001` | Epson |
| `900xxx` | Scene-history synthetic |

**Free (examples, not locked):** `31xxx–39xxx`, `62xxx–69xxx`, `81xxx–89xxx`. Pick **one unused band per vendor** at that ship’s kickoff. Do not invent a scheme in code before it is confirmed.

### What to do with the chosen band

1. Comment it in `config.yaml` IDX mapping.
2. Put idxs **only** in that integration’s YAML `device_map` (home pack).
3. `core/entity_id_list.py` → `origin_from_idx()` + `enrich_from_configs()` (read the map, like Sonos).
4. `core/entity_registry.py` → `classify_entity_prefix()` for the new origin / device type.
5. Birth via `EntityRegistry.ensure()` — slug from display name; **freeze** after first assign. Hardware replace keeps `entity_id`, changes idx.
6. `device_metadata[idx] = { name, type, origin, entity_id, … }` on map/sync (see Z-Wave / Hue).
7. Document the prefix in [`docs/reference.md`](reference.md) entity-id table.

**Prefix examples (proposals only — lock at kickoff):** `climate.honeywell.<slug>`, `sensor.energy.homewizard.<slug>`, `climate.samsung.<slug>`, `sensor.energy.sma.<slug>`, `homeconnect.<kind>.<slug>`. Reuse existing prefixes (`sensor.temp_hum`, `sensor.power`, `media_player`) when the device *is* that kind.

**Product type (D1):** Hue is forced `light`. Binary actuators default `switch` unless Timers & types override. Climate / energy / appliance types are **intrinsic** (read-only on Timers & types), same as speakers / shutters / sensors — unless kickoff says otherwise. See [`docs/todo/phaseD-typing.md`](todo/phaseD-typing.md).

---

## 4. Code / file checklist

Every new bridge touches some of these. Skip rows that do not apply (e.g. telemetry-only skips C18 + Blockly command blocks).

### Must (almost every bridge)

| File | What |
|---|---|
| `integrations/<vendor>.py` | Bridge class: `start` / `stop`, maps, inbound dispatch, outbound off-drain |
| `core/config.py` | Pydantic model + `AppConfig.<vendor>: Optional[...]` |
| `config.yaml` (or `config_<vendor>.yaml`) | Home facts + idx map + comments |
| `.env` | Tokens / passwords |
| `requirements.txt` | Chosen library |
| `main.py` | Construct if config present; `lifespan` start/stop; autostart toggle |
| `core/models.py` | `*_connected`, `*_integration_enabled`; `EventType.<VENDOR>_TOGGLED` |
| `core/event_handlers/integration_handlers.py` | Toggle handler (copy Hue/OWM pattern: reject if offline; ON/OFF bell; auto-recovery sweep) |
| `core/event_handlers/registry.py` | Map the toggle event |
| `logic/health_monitor.py` | Ping + strike counter + auto-kill dispatch |
| `core/event_handlers/telemetry_handlers.py` | Apply `*_connected`; disable integration + connection-transition bell/log when link drops |
| `frontend/admin.html` | Master switch + LIVE / DISABLED / OFFLINE |
| `frontend/app.js` | Alpine defaults; “integrations disabled” banner; Explorer origin filter; commandable check |
| `docs/integration_<vendor>.md` | Lifecycle (boot, listen, outbound, reload, health, off) — same job as [`docs/integration_hue.md`](integration_hue.md) |
| `docs/reference.md`, `docs/architecture.md`, root README | APIs, flags, file list |
| Phase file Last DoD | Audit **all** `docs/**/*.md` |

### If commandable (C18)

| File | What |
|---|---|
| `core/command_commit.py` | Add origin to `_INBOUND_ORIGINS` so echoes do **not** open a hold |
| Bridge `_on_state_changed` | `claim_payload` then `asyncio.create_task(...)` — **never `await` I/O on the drain** |
| Same | `claim_and_finish(..., ok, "[Vendor] reason")` — silent skip = fail |

Prefer the **Hue / Z-Wave / RFX listener** pattern. Avoid adding another origin interceptor in `hub_handlers.py` (Epson / Sonos / Onkyo are the old special cases). C18 contract: [`docs/todo/phaseC-shell.md`](todo/phaseC-shell.md) § C18.

### If it has a config map that must hot-reload

| File | What |
|---|---|
| `core/event_handlers/system_handlers.py` | Recycle on **full** reload (stop/remap/start or refresh maps) |
| G6 (later) | New scope row — **not** silently stuffed into the locked 12 |

### If climate / energy / gauges

| File | What |
|---|---|
| `logic/sensor_history_manager.py` | Deadband / interval; do not invent a second history DB |
| `frontend/app.js` History | Kind: `climate` vs `utility` vs actuator |
| `config.yaml` `history.tracked_entities` | Only if this entity should be in the default tracked list (home pack) |

### Usually do **not** touch unless kickoff says so

- `core/well_known_entities.py` — plant-specific names; prefer registry + config.
- Blockly toolbox / new block types — assess; most commandable devices already ride `HUB_STATE_CHANGED`.
- WISC / kiosk HTML — no new hardcoded idxs.
- `logic/history_ids.py` — virtual idx constants are a P leak; do not add vendor magic idxs there.

---

## 5. Runtime contract (how the bridge must behave)

### Event flow

1. Never mutate `SystemState` from the network thread as a side channel. **Dispatch an `Event`.**
2. Inbound telemetry: `origin: "<vendor>"` (and `is_initialization: true` on first sync) so automations do not ghost-fire (boot-storm / `_initialized_idxs`).
3. Outbound commands: **no** `origin` in that inbound set (empty / ui / automation). That is what C18 treats as a command.
4. Echo guard: listener ignores `origin == self`.

### Enable / disable

- `*_integration_enabled` defaults **false** (`SystemState`).
- Admin toggle → `*_TOGGLED`. Reject ON if not connected (Hue pattern).
- Health monitor: typically **3 strikes / ~6 s** then auto-kill with `error_msg` (USB RFX = 1 strike).
- Connection up/down: bell-only `error`/`success` + `wanos.log` ERROR/INFO — **not** the red Admin banner (`alert_manager` / telemetry handlers).
- **G8** (not shipped): boot should show STARTING, not DISABLED. New rows must follow whatever G8 locks — do not invent a third vocabulary.
- **G14** (assess): after manual re-enable, status **enabling** until live + ON bell. Apply the pattern G14 picks, not a one-off.

### Boot sync

- If the vendor can be queried: initial sync into RAM **before** or as part of `start()`, tagged `is_initialization`.
- Epson `get_power_state` at boot is **G1** (analysis-gated). New bridges: only query when the protocol says it is safe; document when **not** to call.

### Force policy (today)

- RFX: always force.
- Epson / Sonos / Onkyo: force **OFF only**.
- Blockly omits FORCE for RFX/Epson.

New commandable devices: **ask at kickoff**. Do not copy force-OFF silently.

---

## 6. C18 — success / fail / UI / log (locked 2026-08-15)

Applies to **every commandable idx**, not Hue-only. Code: `core/command_commit.py`. Detail: [`phaseC-shell.md`](todo/phaseC-shell.md) § C18.

### Timing

| Row | When it may show the new value |
|---|---|
| **Clicked** Control row | **t = 0** (optimistic, client `uiLocks`) |
| **Sibling** Control rows | Request **success**, or **0.5 s**, whichever first |
| Fail **before** 0.5 s (and before success) | Do **not** reveal RAM |
| Fail **after** reveal | Snap RAM + UI back + error bell + app-log ERROR |

### What counts as success / fail

**Request-level only.** “Did the physical device actually move?” is out of C18.

| Result | Meaning |
|---|---|
| **Success** | The outbound request completed as that protocol defines “accepted” (HTTP 2xx, MQTT `publish()` returned, TCP write+drain, library `True`, …) |
| **Fail** | HTTP not accepted; exception; network; **no session / no mapping / empty payload**; MQTT skipped because down |
| **Silent skip** | Integration disabled, idx not in map, dropped interceptor → **fail** (`fail_unclaimed`: `"not sent (unmapped, disabled, or empty payload)"`) |

Existing locked table (pattern to extend at each kickoff):

| Integration | Success | Fail |
|---|---|---|
| Hue | PUT **200** or **207** (207 body **not** parsed) | Not 200/207; exception; no UUID / no session / empty payload |
| Z-Wave | `publish()` no exception (MQTT connected) | MQTT down (skipped); `MqttError` |
| Sonos | OFF: pause returns; ON: `_start_playback` is **true** | Exception; ON and playback did not start |
| Onkyo | `write` + `drain` complete | Exception; no TCP writer |
| Epson | `power()` **True** (today’s read-timeout → True) | `power()` **False** |
| RFX | `transport.write` completed | Port dead; parse/protocol error; write exception |

For G9–G13, **fill this row at kickoff** from the chosen library (e.g. Honeywell: HTTPS 200 vs 401; SMA: Modbus exception vs poll). Do not leave it implicit.

### Implementation rules (shipped **C18** ✅ 2026-08-16)

1. `hub_handlers` registers a C18 token on outbound `HUB_STATE_CHANGED` (`is_outbound_hub_command`).
2. Sender **claims** as soon as it owns the payload (`claim_payload`) — even if I/O is later — so unclaimed-fail does not fire while the PUT is in flight.
3. I/O runs in `asyncio.create_task`, **not** `await`ed on `_process_events`.
4. Then `claim_and_finish(manager, payload, ok, reason)`.
5. Echoes (`origin` in `_INBOUND_ORIGINS`) must **not** register a hold.
6. Drain snapshot (`hold_pending_on_snapshot`) keeps in-flight idxs at `old_val` for SSE/REST until apply; `c18_commit` + `devices` push on success/fail/0.5 s.
7. YAML automation follow-ups run in the **same drain** (do not re-queue).

### Bell / log copy (locked)

- Bell **error** (not banner), `ERROR:` prefix:  
  `ERROR: Command failed: {format_device_ref} → ON` (or `OFF` / attempted state)
- App log **ERROR**: same line + **`[Vendor]`** + reason (`HTTP 503`, `MQTT publish skipped`, exception text)

Example:  
`ERROR: Command failed: hue.group.badk_1e_hue (badk 1e Hue, idx 51001) → OFF`

`format_device_ref` already exists — use it; do not format idxs by hand.

---

## 7. Logging (G7 parity)

Every operational line from the bridge uses a bracket tag:

`[Hue]` `[Z-Wave]` `[Sonos]` `[Onkyo]` `[Epson]` `[Native RFX]` `[OWM]`

New: `[Honeywell]`, `[HomeWizard]`, `[Samsung]`, `[SMA]`, `[HomeConnect]` (or whatever kickoff locks).

- Start / stop / remap / auto-kill / command fail all tagged.
- C18 fail reason **includes** the same tag.
- Do not log secrets, tokens, or full `.env`.

---

## 8. G6 scoped reload (sequencing warning)

**Today:** Admin **Reload Config** = **full** recycle (Hue stop/start, Onkyo TCP bounce, RFX/Sonos maps, Z-Wave remap, …). Wire the new bridge into that full path in `handle_config_reload_requested`.

**G6 target:** 12 locked checkboxes. **G9–G13 are not in that catalog.** Options at kickoff (do not invent a 13th row in G6 without asking):

- Recycle only on **Full reload** until a later G6 follow-up adds a row, or
- Expand the modal when the first new vendor ships (that is a G6 scope change — ask).

`.env` changes still need a **service restart**. `entity_registry.auto.yaml` is never a reload disk-read (runtime births). G6 catalog: [`phaseG-integrations.md`](todo/phaseG-integrations.md) § G6.

---

## 9. UI / Blockly / History (assess per ship)

**Admin:** one row — connected vs enabled, same LIVE/DISABLED/OFFLINE (and later G8 STARTING / G14 enabling).

**Explorer Control:**

- Binary → existing checkbox.
- Level (bri/volume) → existing slider.
- Climate setpoint / HVAC mode / cycle state → **new widget only if kickoff says so**; do not silently reuse a light toggle.
- Filter rows when that origin’s integration is disabled (`app.js` origin skip list).

**Blockly:** existing device pickers already iterate `device_metadata`. New origins appear if metadata + entity_id exist — **unless** the picker filters by origin/type. Confirm at kickoff. New **block types** (setpoint, start program) are extra scope.

**History:**

- Actuator ON/OFF / level → `history_manager` (`should_track`).
- Temp/hum → `sensor_history` deadband (do not treat as C18 lag; that’s C19/C16).
- Energy / solar → utility kind; ask whether it joins `history.tracked_entities`.

**Soft-hide / auto-off:** hide via `deviceexplorer_hide` (entity_id), not hardcoded. Auto-off eligibility is D1 policy — climate/energy usually out.

---

## 10. Suggested ship order of work (once implement is commanded)

1. Kickoff locks: library, devices in scope, idx band, entity prefix, C18 success/fail row, Admin/Explorer/Blockly/G6.
2. Config model + YAML comments + `.env` key (no secrets in git).
3. Bridge module: maps, start/stop, inbound dispatch, echo `origin`.
4. Wire `main.py` + toggle + health + telemetry flags.
5. Metadata + registry birth + Explorer visibility.
6. If commandable: C18 claim/report + `_INBOUND_ORIGINS` + no drain-await.
7. Full-reload recycle path.
8. Admin row + `app.js` filters.
9. `docs/integration_<vendor>.md` + reference/architecture + phase Last DoD.
10. Pi smoke: enable, inbound truth, outbound + C18 sibling timing, auto-kill, reload, disable.

---

## 11. G9–G13 — what this playbook does **not** decide

| Ship | Intent (already in phase G) | Still kickoff |
|---|---|---|
| **G9 Honeywell** | Setpoints, ambient, HVAC fire over HTTPS | `somecomfort` vs `evohomeclient` vs `aiolyric`; which thermostats; commandable vs read-only |
| **G10 HomeWizard** | Local P1 / kWh / sockets | Which meters; whether sockets are commandable (C18) |
| **G11 Samsung** | Climate power/setpoint | SmartThings cloud vs local `samsungrac` |
| **G12 SMA** | Live production | `pysma` vs SunSpec Modbus |
| **G13 HomeConnect** | Cycle state (oven/dishwasher/laundry) | Which appliances; commands vs telemetry |

Default sequence remains: after **G4**, before **F**; **one ship each**. Stubs: [`phaseG-integrations.md`](todo/phaseG-integrations.md) § G9–G13.

---

## 12. Definition of done (every new vendor ship)

- One vendor path live on Pi; not bundled with the next letter.
- No new site hardcodes (IPs, idxs, creds) in Python/JS.
- C18 row locked **and** implemented if any idx is commandable; silent skip = fail; drain never awaits I/O.
- Logs tagged; command-fail bell/log match § 6.
- Admin enable + health auto-kill + Explorer origin filter.
- Full reload remaps the bridge.
- Docs: `docs/integration_<vendor>.md` + audit of **all** `docs/**/*.md` and root README.
- Phase file updated to shipped summary; the operator moves the archive copy.
