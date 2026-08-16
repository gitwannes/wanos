# WanOS Codebase, API, and MQTT Reference

This document serves as the master blueprint and reference guide for the directory layouts, inbound/outbound communications, API endpoints, and Event-Driven payload schemas for the WanOS ecosystem.

## 1. Directory & File Structure Blueprint

**Root Directory (`/home/wannes/wanos/`)**
* `config.yaml`: The unified production system configuration file storing the dynamic semantic version string, dynamic runtime limits, hysteresis parameters, and manual integration settings. (Manual / human-edited; comments preserved.) Automatic domains (`deviceexplorer_hide`, `auto_off_devices`, `automations`) live in `automations.auto.yaml`.
* `automations.auto.yaml`: UI/system-owned automatic sections — Explorer soft-hide (`deviceexplorer_hide`), auto-off + product-type overrides (`auto_off_devices`, `device_product_types`), automation **rules**, and the `events:` catalog (system + user; bus token = UUID).
* `config_hue.yaml`: PC-owned Hue profile — bridge IP, `device_map`, `group_map`, `scene_map` (provision locally; mirrored to Pi).
* `config_hue_presets.auto.yaml`: Pi-owned **`hue.presets`** (text keys → `{ name, bri, xy|rgb }`; Explorer CRUD on Pi; **StatsRepoPull** into git). Runtime merge in `load_config()`. Explorer/Blocky consume `system.hue_presets`. **B9A:** CRUD via `/api/hue-presets` (add / rename display name / delete-when-unused; unique display names).
* `config_lab.yaml`: Mock architecture state profiles used to seed lab baseline metrics during detachment mode testing.
* `config_hardware.yaml`: Static, layered hardware-pin mapping defining local physical GPIO assignments and communication paths.
* `config_zwave.auto.yaml`: Z-Wave device map (UI/system-owned via `zwaveconfig.html`; not hand-edited as primary workflow).
* `entity_registry.auto.yaml`: System-owned stable `entity_id` ↔ `idx` registry. Auto-assigned at device birth, frozen across renames; not hand-edited for normal operation. See `docs/todo/phaseB-blocky.md`.

### Entity ID types (prefixes)

Stable automation identifiers. Pattern is `prefix.<slug>` or `prefix.<kind>.<slug>`. **Phase D** ✅ ([`phaseD-typing.md`](todo/phaseD-typing.md)): Z-Wave / RFX actuators use **`zwave.*`** / **`rfx.*`** (vent motors **`zwave.vent.*`**); product **`light`** \| **`switch`** comes from **`device_product_types`** (Timers & types), not the id prefix.

| Prefix / pattern | Used for | Example |
|---|---|---|
| `hue.light.<slug>` | Philips Hue lights | `hue.light.buro_spot` |
| `hue.group.<slug>` | Philips Hue groups | `hue.group.living` |
| `zwave.<slug>` | Z-Wave binary actuators | `zwave.buro_licht` |
| `zwave.vent.<slug>` | Z-Wave vent **motors** | `zwave.vent.badk_1e` |
| `rfx.<slug>` | RFX actuators | `rfx.cinema_schemer` |
| `switch.vent.<slug>` | Wall switch controlling a vent motor | `switch.vent.toilet_ventilatie` |
| `switch.epson` | Epson projector (was `switch.cinema_projector`) | `switch.epson` |
| `switch.ssr.<slug>` | SSR class | `switch.ssr.sauna` |
| `switch.safety.<slug>` | Safety / critical power class | `switch.safety.wisc` |
| `blinds.<slug>` | Roller shutters / rolluik (display: **shutter**) | `blinds.cinema` |
| `sensor.power.<slug>` | Power meters | `sensor.power.pc` |
| `sensor.temp_hum.<slug>` | Temperature / humidity | `sensor.temp_hum.sauna_high` |
| `sensor.energy.<slug>` | Energy pulse (kWh) | `sensor.energy.kwh_meter` |
| `sensor.fluid.<slug>` | Water / fluid pulse | `sensor.fluid.cold` |
| `sensor.door.<slug>` | Door contacts | `sensor.door.sauna` |
| `sensor.generic.<slug>` | Other sensors (motion, system status, etc.) | `sensor.generic.garage_motion` |
| `media_player.<slug>` | Sonos / Onkyo | `media_player.living` |
| `unknown.<slug>` | Tombstones / unclassified | `unknown.idx_71099` |

*(Pre-B10B `scene.<slug>` entity rows for dashboard scenes are **retired**. Explorer buttons come from `dashboard_events` built from `events:` — UUID catalog rows with `show_on_dashboard`, not `scene.*` devices.)*

Birth is automatic; ids freeze after first assignment. Hardware replace keeps `entity_id` and changes `idx`. Orphans keep a registry row with `status: removed`.
* `main.py`: The ASGI web server entry point hosting the FastAPI application instance, lifespan initialization hooks, delta SSE streaming loops, and app-level connection heartbeats.
* `requirements.txt`: Master Python package configuration file locking dependencies for strict type validation and async execution.
* `wanos_boot.sh`: Universal production Bash infrastructure utility script handling process control loops, graceful termination sequences, and multi-file tail debugging routing.
* `wanos-nvram.json`: Atomic Non-Volatile Memory (NVM) store bypassing `log2ram` to persist cumulative hardware metrics (e.g., liters, kWh) across unexpected power losses.

**core/** (Central Coordination Kernel)
* `__init__.py`: Package initialization contract.
* `config.py`: Strict validation layer powered by Pydantic models to ingest, consolidate, and compile configuration files into type-safe Python data structures.
* `logger.py`: Centralized multi-sink logging architecture managing file rotators on RAM drives and custom async MQTT string broadcasters.
* `models.py`: House-wide data structures storing the unified `SystemState`, system administration parameters, sensor arrays, and device matrices.
* `mqtt_transport.py`: Pure, transport-agnostic client wrapper managing network sockets, keep-alives, subscriptions, and automatic hardware retry loops.
* `mqtt_publisher.py`: The domain-scoped MQTT correspondent. Monitors the coordination worker and transforms state updates into target broker topics.
* `nvm_manager.py`: Dedicated I/O engine managing atomic file swaps (`.tmp` to `.json`) for zero-corruption data persistence on the physical SD card.
* `entity_registry.py`: System-owned `entity_id` ↔ idx persistence (`entity_registry.auto.yaml`), birth/freeze, and always-resolve helpers used by `StateManager`.
* `product_type_policy.py`: Resolved product type (`light`|`switch`) — Hue forced light; overrides from `device_product_types`; birth default switch.
* `entity_registry_check.py`: Shared cutover / health checks (registry collisions, automation + structured config entity_id refs, Python magic-idx warnings). Used by Admin Debug and the one-off CLI gate.
* `state_manager.py`: The ultra-fast core engine driving the unidirectional event execution loop. It acts as a pure memory router, delegating payload processing to the Strategy Pattern registry.
* `sse_hub.py`: Event-driven SSE fan-out — domain deltas on queue drain + immediate connect **ping** + **5 s** quiet ping (**B10H** / **C23**). `SseClient` is `@dataclass(eq=False)` (hashable in the client `set`). Also pushes `c18_commit` per-idx apply/revert frames (**C18**).
* `command_commit.py`: **C18** ✅ — drain snapshot holds Explorer Control sibling idxs at the pre-command value until outbound **request** success or **0.5 s**, then reveal RAM. Fail before that: do not reveal. Fail after: snap RAM + UI back, error bell, app-log ERROR. Integrations must not await I/O on the event-worker drain (`create_task`).

**core/event_handlers/** (Strategy Pattern Routers)
* `registry.py`: The central dictionary mapping linking string EventTypes to their asynchronous handler functions.
* `integration_handlers.py`: Manages network toggles, including permissive interlocks that reject commands if hardware is offline.
* `hardware_handlers.py`: Processes GPIO, SHT11, and physical bus health state mutations.
* `telemetry_handlers.py`: Handles high-frequency data streams, rolling power buffers, weather synchronization, and NVM buffer flushing loops.
* `timer_handlers.py`: Routes scheduled structural events, expiration boundaries, and time-series automation drops.
* `hub_handlers.py`: Handles generic device state mutations and advanced Hue color payload dictionaries.
* `sauna_handlers.py`: Dedicated routers for sauna heating activation, setpoints, and element modulation tracking.
* `system_handlers.py`: Oversees boot lifecycles, configuration hot-reloads, and UI alert routing.

**frontend/** (Dumb Asset Interfaces)
* `app.js`: Master Alpine.js reactive interface store managing SSE channel bindings, connection watchdogs, dynamic client-side uptimes, local UI layout persistence, and JWT role routing.
* `dashboard.html`: The Device Explorer panel. Implements search query matrices, type exclusions, and cascading alphanumeric sorting algorithms. (**Shipped UI:** `deviceexplorer.html` — Control + History modes.)
* Explorer History (**C10**): omits `type === "scene"` catalog-event rows from the History list; actuator charts use binary ON/OFF, Level (Hue/Sonos/Onkyo/blinds), or motion hits; Planned Automations drops past/done timers (no stale `imminent`).
* `index.html`: Primary operational web interface layout structured around side-by-side grids, 4-column responsive admin panels, and physical action safety interceptors.

**hardware/** (Local Peripherals)
* `sensors.py`: Production worker loop handling physical SHT11 bus scanning and consecutive hardware timeout counters.
* `simulator.py`: Lab Mode thermodynamics loop executing 2-second physics iterations, water accretion ticks, and cyclic day/night weather trends.

**logic/** (Pure Business Rules & Background Services)
* `alert_manager.py`: Centralized UI notification engine (timestamping, dedup, severity). Levels: `critical` (red banner + bell), `error` / `warning` / `success` / `info` (bell only). Integration **connection transitions** (health telemetry up/down) use `error`/`success` + `wanos.log` ERROR/INFO — not the banner.
* `automation_rules.py`: Dynamically evaluates declarative YAML rules.
* `auxiliary_controller.py`: Computes dynamic thermal color gradients (Blue -> Red) and structures active serial LCD display text steps.
* `environment_scheduler.py`: Daily shutters + morning/evening **lights** windows (clamped shutters vs raw sunset for evening-lights on). Catalog / UI labels: Shutters open/close, Morning lights on/off, Evening lights on/off. Admin model + math: [`docs/env-schedule-and-system-events.md`](env-schedule-and-system-events.md). Code keys remain `BLINDS_*` / `MORNING_ON` / `SUNRISE` / `SUNSET` / `EVENING_OFF` until a later key rename.
* `health_monitor.py`: Detached async worker pinging physical TCP/USB sockets, executing auto-kill strike protocols on failed hardware, and natively polling Linux kernel telemetry (CPU, RAM, Disk, Load) via `psutil`. Connection up/down flags ride `SYSTEM_METRICS_UPDATED` (event log silenced); transition UI/log side-effects live in `telemetry_handlers`.
* `history_ids.py`: Shared virtual IDX constants (`20101` sauna calc, **event-UUID** synthetic history `900000+`, host/mains gauge IDXs, `22009` DB size helper) and helpers for event-history hashing / numeric state parsing.
* `history_manager.py`: Actuator / motion / **event-UUID** history (`device_history.db`) with retention tiers and insights tallies.
* `power_analytics.py`: Sauna/IR session energy accounting, background leak baseline, and session SQLite persistence.
* `sauna_controller.py`: Manages element priority wear-leveling algorithms, probe math aggregation, and handles anti-windup loops for high thermal mass zones.
* `sensor_history_manager.py`: Utility / climate / host time-series history (`sensor_history.db`) with hi-res, hourly, and daily rollups.
* `timers.py`: An absolute timestamp scheduler running asynchronous sleepers that fire expiration events back to the primary central queue.

**integrations/** (Network Hub Gateways)
* `open_weather.py`: OWM loop — climate (temp/humidity) on `weather.poll_interval_mins` (**10** after **G3**; takes effect on cold boot); sunrise/sunset once daily at `sun_refresh_hour` (plus boot/enable). Climate no longer emits sun events. Tripwires off on HTTP failure.
* `onkyo.py`: Persistent asynchronous bridge maintaining zero-latency TCP sockets with Onkyo/Pioneer AV receivers, handling legacy hardware protocol variations.
* `rfxcom.py`: Direct asyncio serial protocol driving the 433MHz antenna transceiver, utilizing custom packet generation blocks to protect against library crashes.
* `sonos.py`: Asynchronous network integration tracking UPnP/HTTP topologies for Sonos speakers.
* `zwave.py`: MQTT bridge to Z-Wave JS UI for mesh switch/sensor/power telemetry and command routing.
* `hue.py`: Local Philips Hue Bridge API v2 SSE/HTTP client.
* `epson.py`: TCP control for Epson projectors.

---

## 2. MQTT Topic Architecture
WanOS uses a single MQTT client bound to the local `localhost` Mosquitto broker for UI heartbeats, console logs, metrics, and sauna telemetry.

Summary Outgoing topics:

`wanos/system`                   Boot variables upon startup & heartbeat
`wanos`                          Sauna baseline snapshot upon start, then deltas
`wanos/metrics/pulses`           Cold & hot water: liters & energy: 0.1 kWh
`wanos/console/status`           Standard operational engine execution logs
`wanos/console/debug`            High-frequency developmental logging chatter
A dedicated `mqtt_publisher.py`  layer owns all topic routing logic.

WanOS operates on an Event-Driven Delta Architecture. Topic paths are completely separated by structural purpose:

### TOPIC: `wanos/system`
* **Cadence:** Dispatched once on initial startup handshake, and continuously every 60 seconds as a connection heartbeat.
* **Rules:** Injects system parameters and handles live status tracking.
* **Payload Examples:**
  * Process Startup: `{"app_boot_unix": 1782200000, "os_boot_unix": 1782100000, "ip_address": "10.32.251.30"}`
  * Heartbeat Metronome: `{"wanos_mqtt_connected": true}`

### TOPIC: `wanos` (Core Sauna Telemetry)
* **Cadence:** Sends a full baseline definition map when the sauna activates, then fires partial dictionaries (deltas) *only* if values change during execution.
* **Rules:** Isolates heater PID loops and element priority tracking. Ancillary fans or room sensors are strictly excluded.
* **Payload Examples:**
  * Baseline Activation: `{"active": true, "setpoint_temp": 80.0, "modulation_pwm": 0, "phases_pwm": [0,0,0], "fireorder": "UVW"}`
  * Delta Power Shift: `{"modulation_pwm": 75, "phases_pwm": [25, 100, 100]}`

### TOPIC: `wanos/metrics/pulses`
* **Cadence:** Suppresses transmission, accumulating counts in memory until absolute whole number increments are crossed.
* **Rules:** Throttles high-frequency pulse meters. Emits updates on a 1 Liter boundary for liquids and a 0.1 kWh step boundary for grid monitors.
* **Payload Examples:**
  * Water Aggregator: `{"total_cold_liters": 154}`
  * Power Grid Step: `{"total_kwh": 12.3}`

### TOPIC: `wanos/console/status` & `wanos/console/debug`
* **Cadence:** Dispatched on demand whenever system modules execute actions or log telemetry diagnostics.
* **Rules:** Standard logs go to `status`; development chatter and duplicate drops are routed to `debug`.
* **Payload Example:**
  ```json
  {
    "timestamp": "2026-06-23 10:45:12",
    "level": "SUCCESS",
    "message": "[Z-Wave] Bridge started. Subscribed to zwave/#."
  }
  ```

---

## 3. Web REST Endpoints & Stream Channels

The backend engine exposes a lightweight HTTP REST and SSE data pipeline layer on port `8000`:

* **`GET /`** | Serves static UI views with aggressive no-cache response headers to bypass browser caching. Redirects to `/login.html` via middleware.
* **`POST /api/auth/login`** | Authenticates PINs/Tokens, implements strike-based IP bans, and issues signed JWT payload objects.
* **`POST /api/auth/logout`** | Nullifies the backend session route (Client is responsible for wiping `localStorage` tab memory).
* **`GET /api/state`** | Full read-only system snapshot for Alpine bootstrap. **B10H:** returns cached `model_dump` refreshed on state-queue drain (and warmed at boot); handlers use `asyncio.to_thread` so the event loop stays free. **C18:** cached `devices` holds uncommitted outbound idxs at the pre-command value until success or 0.5 s (`hold_pending_on_snapshot` on the copy — live RAM is already new).
* **`GET /api/state/sse`** | Persistent HTTP stream pushing partial domain JSON frames (`system`, `sensors`, `sauna`, `ir`, `metrics`, `hardware`, `devices`, `device_metadata`) on queue drain via event-driven hub (`core/sse_hub.py`). **C23:** `SseClient` is `@dataclass(eq=False)` (identity-hashable in the client `set`). Immediate `domain: ping` on connect; another ping when quiet for **5 s**. **C18:** also emits `domain: c18_commit` with `{idx: value}` to apply/revert Control rows (Explorer bypasses `uiLocks` for this domain). Hosted as pure ASGI (JWT/RBAC + static no-cache); no `Connection: keep-alive` (HTTP/2). **B10H:** `wanosApp` reconnect skips full REST snapshot when last snapshot is &lt;30 s old; does not flash NOT CONNECTED while snapshot is &lt;60 s old.
* **`POST /api/event`** | Universal application entry point. Accepts standard `type` and `payload` properties to inject commands onto the async bus. Protects admin-only payloads via RBAC token inspection.
* **`GET /api/debug/entity-registry-check`** | Admin-only. Runs `run_entity_cutover_checks` (plus live `device_metadata`) and returns JSON including annotated `report_text` for the Admin Debug modal. Blocky also calls this after automation Save/Delete and shows GREEN/RED in-page.
* **`GET/PUT /api/soft-hide`** | Admin. Full-list replace of `deviceexplorer_hide` in `automations.auto.yaml` (`entity_ids: string[]`). PUT dispatches `CONFIG_RELOAD_REQUESTED`. Hard-deny `switch.safety.safety_wisc_5v` rejected. Admin UI: `hiddendevices.html`.
* **`GET/PUT /api/auto-off-timer`** | Admin. Full-replace of `auto_off_devices` + **`device_product_types`** in `automations.auto.yaml`. PUT validates eligibility / orphans / minutes 1–720; dispatches scoped reload (`auto_off` + metadata). Admin UI: `lightingautooff.html` (nav label **Timers & types**).
* **`GET/POST/PUT/DELETE /api/automations`** | Admin CRUD. **Persists schema v2** (`trigger` + `cases`, `name`…`id` last). GET returns v2 (**SR `name` normalized to companion SE catalog**). **B10H:** GET does **one** YAML round-trip (bind uses in-memory events map — no N+1). Each write dispatches `CONFIG_RELOAD_REQUESTED`. Event triggers/fire-actions store **event UUID** after **B10B** (see `docs/todo/phaseB-blocky.md` § B10B). Pre-B10B schedule families (`SCHEDULE_WINDOW_EDGES`) removed on that cutover. **B10F:** successful CRUD also writes `INFO` lines to `wanos.log` with **quoted** names (`user rule "…" changed`, etc.). System-rule titles always bind to the SE catalog on POST/PUT; boot merge rewrites drifted YAML free-text.
* **`GET /api/events`** | Admin. Read-only list of `events:` catalog rows. **B10H:** no per-request seed merge (seeds merged at boot via `load_config`).
* **`GET /api/automations/fire-status`** | Admin. Today's fire status for the six env-schedule system events + Sauna OFF / IR OFF (`will_fire` / `has_fired` / `doesnt_fire_today` / `not_armed`). Local Pi clock; used by Automations SR editor (**B10F** ✅). **B10H:** cold Automations load fetches this **after** library TTI (deferred). Deadline for Sauna/IR OFF = `session_end_time` when armed (no absolute-cutoff clamp — **B18**).
* **`GET/POST /api/hue-presets`**, **`PUT/DELETE /api/hue-presets/{key}`** | Admin. **B9A** + **B10G Part D** ✅ — CRUD for `hue.presets` in `config_hue_presets.auto.yaml` (text keys; rename = display `name` only; unique display names). Delete **409** when automations still reference `preset: <key>` (usages listed). Create never overwrites an existing key. Hot-reload: **`hue_presets` scope only** — sync `system.hue_presets` + in-memory `config.hue.presets`; **no** full bridge recycle (**G6** Admin modal still open for other scopes).

---

## 4. Inbound API Event Reference (`POST /api/event`)

To communicate with the system, payloads must align with the exact structural data keys expected by the internal controllers:

### 🧖‍♂️ Wellness & Sauna Controls
* **Sauna Power Execution:**
  ```json
  { "type": "SAUNA_ON", "payload": {} }
  ```
* **Setpoint Manipulation:**
  ```json
  { "type": "SAUNA_SETPOINT_CHANGED", "payload": { "target": 82.5 } }
  ```
* **Session Clock Adjustment:**
  ```json
  { "type": "SAUNA_TIMER_ADJUSTED", "payload": { "minutes": 10 } }
  ```
* **IR Array Control with Snapping Frequency:**
  ```json
  { "type": "IR_MODULATION_UPDATED", "payload": { "pwm": 75, "freq": 25 } }
  ```

### 🔌 Physical Peripheral & Sensor Intercepts
* All physical hardware devices, digital probes, switches, relays, and cumulative fluid/power meters are addressed using their unique, raw integer **`idx`** derived from the dashboard hardware map.
* **System Telemetry / Virtual Sensors (IDXs 22001-22009):**
  * Internally reserved block for host machine health. Soft-hidden via `deviceexplorer_hide` in `automations.auto.yaml`.
  * `22009` = WanOS DB size (MiB): sum of `sensor_history.db`, `device_history.db`, `sauna_sessions.db` plus `-wal`/`-shm` sidecars.
  * E.g., `{ "type": "HUB_STATE_CHANGED", "payload": { "idx": 22002, "state": "20.0 %", "origin": "system" } }`
  * E.g., `{ "type": "HUB_STATE_CHANGED", "payload": { "idx": 22009, "state": "12.4 MB", "origin": "system" } }`
* **Temperature Update:**
  ```json
  { "type": "TEMP_UPDATED", "payload": { "idx": 20001, "value": 24.5 } }
  ```
* **Humidity Update:**
  ```json
  { "type": "HUMIDITY_UPDATED", "payload": { "idx": 20004, "value": 68 } }
  ```
* **Magnetic Door Interlock Change:**
  ```json
  { "type": "DOOR_CHANGED", "payload": { "idx": 10001, "is_open": true } }
  ```
* **Electrical Load Wattage Reading:**
  ```json
  { "type": "POWER_UPDATED", "payload": { "idx": 9, "value": 185.2 } }
  ```
* **Water Meter Analog Pulse Injection (Translates pulses directly to liters via internal math):**
  ```json
  { "type": "WATER_PULSE", "payload": { "idx": 11002, "count": 396, "lab_override": true } }
  ```
* **Cumulative Grid Pulse Injection (1 Pulse = 1 Wh):**
  ```json
  { "type": "KWH_PULSE", "payload": { "idx": 11001 } }
  ```
* **Universal Hardware State Control:**
  ```json
  { "type": "HUB_STATE_CHANGED", "payload": { "idx": 141, "state": "ON" } }
  ```
* **Advanced Hue Color Control:**
  ```json
  { "type": "HUB_STATE_CHANGED", "payload": { "idx": 51005, "state": "ON", "bri": 254, "xy": [0.6915, 0.3083], "force": true } }
  ```
* **Sun cycle / env schedule refresh** (daily ≥ `sun_refresh_hour`, and on OWM enable/boot — not on climate polls). Bus type **`SUNRISE_SUNSET_UPDATE`** (legacy alias `EXTERNAL_WEATHER_UPDATED` still accepted by the handler until emitters soak; same catalog UUID; display **Sunrise/sunset update**). Schedule windows: [`docs/env-schedule-and-system-events.md`](env-schedule-and-system-events.md).
  ```json
  { "type": "SUNRISE_SUNSET_UPDATE", "payload": { "sunrise": 1782201000, "sunset": 1782256000 } }
  ```

### ⚙️ System Administration Actions
* **Force Maintenance Sweep:**
  ```json
  { "type": "SYSTEM_SWEEP_REQUESTED", "payload": {} }
  ```
* **Trigger Live Configuration Hot-Reload:**
  ```json
  { "type": "CONFIG_RELOAD_REQUESTED", "payload": {} }
  ```
* **General Automation Loop Kill Switch:**
  ```json
  { "type": "AUTOMATIONS_TOGGLED", "payload": { "enabled": false } }
  ```
```st
🟢 Validation Rule: If any outbound or inbound payload structure deviates from these exact parameter properties (e.g. using 'sensor_id' or 'device_id' strings instead of raw integer 'idx' markers), the validation schemas will fail and drop the frame to protect runtime loop operations.
```