# --- file: reference.md ---

# WanOS Codebase, API, and MQTT Reference

This document serves as the master blueprint and reference guide for the directory layouts, inbound/outbound communications, API endpoints, and Event-Driven payload schemas for the WanOS ecosystem.

## 1. Directory & File Structure Blueprint

**Root Directory (`C:\data\git\wanos\`)**
* `.gitignore`: Specifies intentionally untracked files to ignore for source control.
* `.env`: Secrets file holding sensitive infrastructure values (Shared PIN, MQTT passwords, and OWM API Keys).
* `hardware.yaml`: Static, layered mapping of physical GPIO pins, MQTT network architectures, and external node IDXs.
* `config.yaml`: The unified production system configuration file (runtime limits, hysteresis boundaries, PID terms, and weather API settings).
* `config_lab.yaml`: Mock architecture states used to seed lab baseline metrics during emulation mode.
* `main.py`: The ASGI web entry point. Hosts the FastAPI app instance, lifespans, and the keep-alive ping SSE stream loops.
* `requirements.txt`: Python package dependencies.

**core/**
* `__init__.py`: Package initializer.
* `config.py`: Strict Pydantic parsing schemas assembling the configuration files into a validated state.
* `logger.py`: Centralized async middleware engine piping logs simultaneously to Loguru disk files and the local MQTT pipeline.
* `models.py`: House-wide Pydantic data contract definitions representing the reactive multi-zone system states.
* `mqtt_publisher.py`: The Event-Driven delta router. Translates snapshot mutations into domain-scoped MQTT packets.
* `mqtt_transport.py`: Pure async transport layer managing the low-level TCP socket context and connection keep-alives.
* `state_manager.py`: Runs the central system asynchronous event queue. Restricts all data mutations strictly to a single, safe worker thread.

**frontend/**
* `app.js`: Alpine.js master reactive store controller. Manages HTTP handshakes, the sliding 10s SSE watchdog, and extended timestamp formatting uptime trackers.
* `index.html`: Main HTML entry point bound directly to DaisyUI + Tailwind layouts.

**hardware/** (Local Physical Interfaces)
* `sensors.py`: Thread polling managers watching for local physical environmental changes (SHT11 arrays, GPIO pulses).
* `simulator.py`: Implements mathematical thermal engines for Lab Mode (weather trends, bathroom ventilation decay, and sauna thermal stratification).

**logic/** (Core Business Rules)
* `auxiliary_controller.py`: Manages ancillary operations including dynamic lighting color mapping and active LCD display steps.
* `sauna_controller.py`: Tracks environmental steps, phase element prioritization cascades, and multi-tier PID algorithms.
* `timers.py`: Simple wrappers feeding tracking alerts directly to the core state manager queue upon expiration loops.

**integrations/** (Networked Physical Interfaces & APIs)
* `home_hub.py`: Target integration connector bridging raw external Domoticz state packets cleanly onto the internal WanOS bus.
* `open_weather.py`: Asynchronous REST polling engine fetching real-time outside temperature, humidity, and UNIX sun cycles from OpenWeatherMap.

---

## 2. MQTT Topic Architecture
*(Note: WanOS utilizes two distinct MQTT Client Manager instances. One binds to the local `localhost` broker for UI operations, while the other binds to external hubs like Domoticz).*

Outgoing topics:
`wanos/system`				Boot variables upon startup, Domoticz status & heartbeat
`wanos/domsensors/raw`		Filtered, raw packets received from Domoticz
`wanos/domsensors/parsed`	Human-readable format triggered ONLY on a real value/state change
`wanos/wisc`				A full "baseline" snapshot upon start, then deltas.
`wanos/metrics/pulses`		Cold & hot water: liters & energy: 0.1 kWh
`wanos/console/status`		Standard operational engine execution logs
`wanos/console/debug`		High-frequency developmental logging chatter
A dedicated `mqtt_publisher.py` layer owns all topic routing logic.

**TOPIC: `wanos/system`**
* **Rules:** - Publishes static application and OS boot Unix timestamps upon startup.
  - Broadcasts Domoticz link tracking statuses instantly on network change.
  - Fires an implicit connection keep-alive heartbeat every 60 seconds.
* **Payload Examples:**
  - Startup Handshake: `{"app_boot_unix": 1781182950, "os_boot_unix": 1780822950, "ip_address": "10.32.251.28"}`
  - Connection Flip: `{"domoticz_mqtt_connected": false}`
  - Metronome Heartbeat: `{"wanos_mqtt_connected": true}`

**TOPIC: `wanos/domsensors/raw`**
* **Rules:** - Relays the exact, unedited JSON packet received from the remote Domoticz broker.
  - Restricted to devices explicitly mapped inside `hardware.yaml`.
  - Blocks duplicate sequential packets at an early gateway cache filter.
* **Payload Example:**
  ```json
  {
    "idx": 7436,
    "svalue1": "20.5",
    "svalue2": "54",
    "Battery": 255
  }
  ```

**TOPIC: `wanos/domsensors/parsed`**
* **Rules:**
  - Evaluates internal state caches and logs human-readable delta transition strings *only* when a real value modification occurs.
* **Payload Examples:**
  - `{"bathroom_temp": "20.4 -> 20.5"}`
  - `{"sauna_extrvent": "OFF -> ON"}`

**TOPIC: `wanos/wisc` (Core Sauna Engine)**
* **Rules:**
  - Environmental multi-probe sensors and ventilation switches are completely excluded from this track.
  - Pushes a full baseline control map the exact moment the sauna toggles `active = true`.
  - Publishes precise partial dictionaries (deltas) on intermediate frames if values drift.
* **Payload Examples:**
  - Baseline Output: `{"active": true, "setpoint_temp": 80, "modulation_pwm": 0, "phases_pwm": [0,0,0], "fireorder": "UVW"}`
  - Step Modulation: `{"modulation_pwm": 82, "phases_pwm": [46, 100, 100]}`

**TOPIC: `wanos/metrics/pulses`**
* **Rules:**
  - The automation engine calculates raw fractional quantities in local RAM.
  - Suppresses transmission until absolute whole integer step barriers are scaled (1 Liter for fluid sensors or 0.1 kWh / 100 Wh for energy monitors).
* **Payload Examples:**
  - Flow Meter: `{"total_cold_liters": 154}`
  - Power Meter: `{"total_kwh": 12.3}`

**TOPIC: `wanos/console/status`**
* **Rules:**
  - Subscribes directly to standard operational logger notifications.
  - Pipes all standard business updates carrying severities of `INFO`, `SUCCESS`, `WARNING`, and `ERROR`.
* **Payload Example:**
  ```json
  {
    "timestamp": "2026-06-11 16:15:00",
    "level": "SUCCESS",
    "message": "Boot sequence complete. HTTP/SSE Web Interface online."
  }
  ```

**TOPIC: `wanos/console/debug`**
* **Rules:**
  - Segregates high-frequency development chatter from standard notification streams to minimize local broker pipeline overhead.
  - Captures inbound diagnostic confirmation packets, sensor parsing thresholds, and duplicate drop logs.
* **Payload Example:**
  ```json
  {
    "timestamp": "2026-06-11 13:50:53",
    "level": "DEBUG",
    "message": "[Domoticz] Node 'sauna_extrvent' (IDX 8577) sensor update received -> ON"
  }
  ```

---

## 3. URLs & Endpoints
The FastAPI server (running at `http://<backend-ip>:8000`) exposes the following primary HTTP and stream routes.

**`/`**					| GET
	Serves compiled frontend static HTML assets
**`/api/state`**		| GET
	Retrieves read-only JSON snapshot for instant client bootstrapping
**`/api/state/sse`**	| GET
	Primary persistent real-time data pipeline. Emits real-time domain deltas
**`/docs`**				| GET
	Auto-generated interactive Swagger UI API explorer
**`/api/event`**		| POST
	Universal command entry point to inject operations directly into queue.
	On first connect, the frontend calls `/api/state` to retrieve a full snapshot.
	`{"type": "...", "payload": {}}`
**`/api/test/temp`**	| POST
	Dedicated lab endpoint for forcing test environment temps
	`{"temp": float}`

---

## 4. API Event Injection Reference (/api/event)
The `/api/event` endpoint acts as the universal command receiver for WanOS. It accepts HTTP POST requests containing a JSON body mapped to the internal `EventType` schema.

### Sauna & Timer Events
**Turn Sauna ON:**
```json
{ "type": "SAUNA_ON", "payload": {} }
```

**Turn Sauna OFF:**
```json
{ "type": "SAUNA_OFF", "payload": {} }
```

**Change Target Temperature:**
```json
{ "type": "SETPOINT_CHANGED", "payload": { "target": 85.0 } }
```

**Manually Override Heater Modulation (PWM):**
```json
{ "type": "MODULATION_UPDATED", "payload": { "pwm": 100.0 } }
```

**Notify Setpoint Reached:**
```json
{ "type": "SETPOINT_REACHED", "payload": {} }
```

**Trigger Sauna Hold (Maintain temp for X minutes):**
```json
{ "type": "SAUNA_HOLD", "payload": { "minutes": 60 } }
```

**Toggle Hold Mode (Cycles autohold -> hold -> nohold):**
```json
{ "type": "HOLD_TOGGLED", "payload": {} }
```

**Adjust Main Session Timer:**
```json
{ "type": "TIMER_ADJUSTED", "payload": { "minutes": 10 } }
```

**Notify Sauna Timer Expired:**
```json
{ "type": "SAUNA_TIMER_EXPIRED", "payload": {} }
```

**Notify Ventilation Wait Period Expired (Triggers Extractor Fan):**
```json
{ "type": "VENT_WAIT_EXPIRED", "payload": {} }
```

**Notify Ventilation Run Period Expired (Shuts Off Extractor Fan):**
```json
{ "type": "VENT_RUN_EXPIRED", "payload": {} }
```

### Hardware & Sensor Events
**Update Temperature (requires sensor_id target):**
```json
{ "type": "TEMP_UPDATED", "payload": { "sensor_id": "sauna_high", "value": 82.5 } }
```

**Update Humidity (requires sensor_id target):**
```json
{ "type": "HUMIDITY_UPDATED", "payload": { "sensor_id": "bathroom", "value": 75.0 } }
```

**Trigger Magnetic Door Interlocks:**
```json
{ "type": "DOOR_CHANGED", "payload": { "sensor_id": "bathroom", "is_open": true } }
```

**Report Sensor Error:**
```json
{ "type": "SENSOR_ERROR", "payload": { "sensor": "sauna_high", "error": "timeout" } }
```

**System Metronome Tick (One minute passed):**
```json
{ "type": "TIMER_TICK", "payload": {} }
```

### System Events
**Engine Boot Complete:**
```json
{ "type": "SYSTEM_READY", "payload": {} }
```

**Trigger Graceful Shutdown:**
```json
{ "type": "BACKEND_SHUTDOWN", "payload": {} }
```

**Notify Config Updated:**
```json
{ "type": "CONFIG_UPDATED", "payload": {} }
```

### External Integrations
Updates mapped from external REST APIs or hubs like Domoticz and Hue.

**Update Hub State (Domoticz - e.g., Bathroom Ventilator):**
```json
{ "type": "HUB_STATE_CHANGED", "payload": { "device_id": "bathroom_ventilator", "state": "ON" } }
```

**Update External Weather (OpenWeatherMap):**
```json
{ "type": "EXTERNAL_WEATHER_UPDATED", "payload": { "sunrise": 1781234798, "sunset": 1781294237 } }
```

**Update Lighting State (Hue):**
```json
{ "type": "LIGHTING_STATE_CHANGED", "payload": { "zone": "sauna", "state": "OFF" } }
```