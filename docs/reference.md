# WanOS Codebase, API, and MQTT Reference

This document serves as the master blueprint and reference guide for the directory layouts, inbound/outbound communications, API endpoints, and Event-Driven payload schemas for the WanOS ecosystem.

## 1. Directory & File Structure Blueprint

**Root Directory (`/home/wannes/wanos/`)**
* `config.yaml`: The unified production system configuration file storing the dynamic semantic version string, dynamic runtime limits, hysteresis parameters, and automation rules at the file root.
* `config_hue.yaml`: Segregated lighting profile path tracking local network Philips Hue Bridge API endpoints and structural group/scene UUID allocations.
* `config_lab.yaml`: Mock architecture state profiles used to seed lab baseline metrics during detachment mode testing.
* `hardware.yaml`: Static, layered hardware-pin mapping defining local physical GPIO assignments and communication paths.
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
* `state_manager.py`: The ultra-fast core engine driving the unidirectional event execution loop. It acts as a pure memory router, delegating payload processing to the Strategy Pattern registry.

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
* `dashboard.html`: The Device Explorer panel. Implements search query matrices, type exclusions, and cascading alphanumeric sorting algorithms.
* `index.html`: Primary operational web interface layout structured around side-by-side grids, 4-column responsive admin panels, and physical action safety interceptors.

**hardware/** (Local Peripherals)
* `sensors.py`: Production worker loop handling physical SHT11 bus scanning and consecutive hardware timeout counters.
* `simulator.py`: Lab Mode thermodynamics loop executing 2-second physics iterations, water accretion ticks, and cyclic day/night weather trends.

**logic/** (Pure Business Rules & Background Services)
* `alert_manager.py`: Centralized UI Notification Engine handling timestamping, deduplication, and severity classification of frontend banners.
* `automation_rules.py`: Dynamically evaluates declarative YAML rules.
* `auxiliary_controller.py`: Computes dynamic thermal color gradients (Blue -> Red) and structures active serial LCD display text steps.
* `environment_scheduler.py`: Calculates mathematical bounds clamping and dynamically schedules blind/twilight timers based on external weather.
* `health_monitor.py`: Detached async worker pinging physical TCP/USB sockets, executing auto-kill strike protocols on failed hardware, and natively polling Linux kernel telemetry (CPU, RAM, Disk, Load) via `psutil`.
* `history_ids.py`: Shared virtual IDX constants (`20101` sauna calc, scene synthetic `900000+`, host/mains gauge IDXs, `22009` DB size helper) and helpers for scene hashing / numeric state parsing.
* `history_manager.py`: Actuator / motion / scene event history (`device_history.db`) with retention tiers and insights tallies.
* `power_analytics.py`: Sauna/IR session energy accounting, background leak baseline, and session SQLite persistence.
* `sauna_controller.py`: Manages element priority wear-leveling algorithms, probe math aggregation, and handles anti-windup loops for high thermal mass zones.
* `sensor_history_manager.py`: Utility / climate / host time-series history (`sensor_history.db`) with hi-res, hourly, and daily rollups.
* `timers.py`: An absolute timestamp scheduler running asynchronous sleepers that fire expiration events back to the primary central queue.

**integrations/** (Network Hub Gateways)
* `open_weather.py`: REST polling framework capturing outside climate metrics and tripwiring integrations off if connections fail.
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
* **`GET /api/state`** | Compiles a full, read-only system snapshot used by Alpine.js to bootstrap the client memory.
* **`GET /api/state/sse`** | Persistent HTTP stream channel pushing partial domain JSON frames (`system`, `sensors`, `sauna`, `ir`, `metrics`, `hardware`, `devices`) immediately upon queue draining. Fires a `domain: ping` block if quiet for 5 seconds.
* **`POST /api/event`** | Universal application entry point. Accepts standard `type` and `payload` properties to inject commands onto the async bus. Protects admin-only payloads via RBAC token inspection.

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
  * Internally reserved block for host machine health. Hidden via `deviceexplorer_exclude`.
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
* **External Weather Synchronization:**
  ```json
  { "type": "EXTERNAL_WEATHER_UPDATED", "payload": { "sunrise": 1782201000, "sunset": 1782256000 } }
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