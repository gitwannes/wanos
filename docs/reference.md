# --- file: reference.md ---

# WanOS Codebase, API, and MQTT Reference

This document serves as the master blueprint and reference guide for the directory layouts, inbound/outbound communications, API endpoints, and Event-Driven payload schemas for the WanOS ecosystem.

## 1. Directory & File Structure Blueprint

**Root Directory (`C:\data\git\wanos\`)**
* `.gitignore`: Specifies intentionally untracked files to ignore for source control.
* `.env`: Secrets file holding sensitive infrastructure values (Excluded from Source Control).
* `hardware.yaml`: Static, layered mapping of physical GPIO pins, MQTT network architectures, and external node IDXs.
* `config.yaml`: The unified production system configuration file (runtime logic properties).
* `config_lab.yaml`: Mock architecture states used to initialize variables during Lab Mode.
* `main.py`: The ASGI entry point. Initializes FastAPI, signal traps, external integrations, and hardware threads.
* `requirements.txt`: Python package dependencies.

**core/**
* `__init__.py`: Package initializer.
* `config.py`: Strict Pydantic parsing schemas assembling `hardware.yaml` and `config.yaml` into a validated state.
* `logger.py`: Custom-tailored asynchronous system log engine.
* `models.py`: House-wide Pydantic modules handling validation layer targets. Defines distinct environmental targets (`outside`, `bathroom`, `cinema`, `sauna_high`, `sauna_low`).
* `mqtt_client.py`: Async-native (`aiomqtt`) system broker wrapper supporting background stream subscriptions and publishing.
* `state_manager.py`: Runs the central system asynchronous event queue. Protects and limits state updates strictly within its single consumer loop execution context.

**frontend/** * `app.js`: Alpine.js reactive store, SSE stream handlers, and timestamp metronome loops.
* `index.html`: Main HTML entry point mapped to TailwindCSS + DaisyUI components.

**hardware/** (Local Physical Interfaces)
* `sensors.py`: Thread polling managers watching for local physical environmental changes (SHT11 arrays, GPIO pulses).
* `simulator.py`: Implements mathematical thermal engines for Lab Mode. Simulates 24-hour outdoor sine waves, bathroom humidity decay, and complex sauna thermal stratification.

**logic/** (Core Business Rules)
* `auxiliary_controller.py`: Manages ancillary operations including dynamic lighting logic and active step timelines.
* `sauna_controller.py`: Tracks environmental steps, heater rotation algorithms, and multi-tier priority PID metrics.
* `timers.py`: Simple wrappers feeding tracking alerts directly to the core state manager queue upon expiration loops.

**integrations/** (Networked Physical Interfaces)
* `home_hub.py`: Target integration connector interfacing via a dedicated remote MQTT broker connection directly to Domoticz environments (reads outdoor temps, syncs bathroom and extraction vents).
* `lighting.py`: Coordinates configuration updates directly to local color lighting environments (Hue Bridge).

---

## 2. MQTT Topic Architecture
*(Note: WanOS utilizes two distinct MQTT Client Manager instances. One binds to the local `localhost` broker for UI operations, while the other binds to external hubs like Domoticz).*

Outgoing topics:
`wanos/system`				Boot variables upon startup, Domoticz status & heartbeat
`wanos/domsensors/raw`		Filtered, raw packets received from Domoticz
`wanos/domsensors/parsed`	Human-readable format triggered ONLY on a real value/state change
`wanos/wisc`				A full "baseline" snapshot upon start, then deltas.
`wanos/metrics/pulses`		Cold & hot water: liters & energy: 0,1 kWh
`wanos/console/status`
`wanos/console/debug`

**TOPIC: `wanos/system`**
* **Rules:** - Boot variables upon startup & heartbeat.
  - Domoticz connection flag sent on change.
  - Heartbeat ping sent every 60 seconds.
* **Payload Examples:**
  - Boot: `{"app_boot_unix": 1718010000, "ip_address": "10.32.251.28"}`
  - Change: `{"domoticz_mqtt_connected": false}`
  - Heartbeat (60s): `{"wanos_mqtt_connected": true}`

**TOPIC: `wanos/domsensors/raw`**
* **Rules:** - Contains the exact, full JSON packet received from Domoticz.
  - ONLY includes sensors verified against `hardware.yaml`.
  - Passes through an early-gate filter: exact duplicates are silently dropped.
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
  - Human-readable format triggered ONLY on a real value/state change.
* **Payload Examples:**
  - `{"bathroom_temp": "20.4 -> 20.5"}`
  - `{"outside_hum": "75 -> 76"}`
  - `{"safety_ssr": "OFF -> ON"}`

**TOPIC: `wanos/wisc` (Core Sauna Engine)**
* **Rules:**
  - Temperature, humidity, and external vents are excluded from this payload.
  - Sends a full "baseline" snapshot when the sauna is turned ON.
  - Sends ONLY modified keys (deltas) whenever a value changes.
* **Payload Examples:**
  - Baseline: `{"active": true, "setpoint_temp": 80, "modulation_pwm": 0, "phases_pwm": [0,0,0], "fireorder": "--"}`
  - Delta: `{"modulation_pwm": 80}`
  - Delta: `{"setpoint_temp": 85}`

**TOPIC: `wanos/metrics/pulses`**
* **Rules:**
  - Internal RAM calculates fractional floats.
  - MQTT Payload is ONLY published when a whole integer threshold is crossed (1L or 0.1 kWh).
* **Payload Examples:**
  - `{"total_cold_liters": 154}`
  - `{"total_kwh": 12.3}`

---

## 3. URLs & Endpoints
The FastAPI server (running at `http://<backend-ip>:8000`) exposes the following primary HTTP and stream routes.

| Endpoint | Method | Purpose | Payload Requirements |
| :--- | :--- | :--- | :--- |
| **`/`** | GET | Serves compiled frontend static HTML assets | N/A |
| **`/api/state`** | GET | Retrieves read-only JSON snapshot for instant sync | N/A |
| **`/api/state/sse`** | GET | Primary persistent real-time UI data pipeline | N/A |
| **`/api/console`** | GET | Retrieves JSON of last 100 log events | N/A |
| **`/api/event`** | POST | Universal endpoint to inject any command into queue | `{"type": "...", "payload": {}}` |
| **`/api/test/temp`** | POST | Dedicated lab endpoint for injecting dummy temps | `{"temp": float}` |
| **`/docs`** | GET | Auto-generated Swagger UI | N/A |

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
Updates mapped from external hubs like Domoticz or Hue.

**Update Hub State (Domoticz - e.g., Bathroom Ventilator):**
```json
{ "type": "HUB_STATE_CHANGED", "payload": { "device_id": "bathroom_ventilator", "state": "ON" } }
```

**Update Lighting State (Hue):**
```json
{ "type": "LIGHTING_STATE_CHANGED", "payload": { "zone": "sauna", "state": "OFF" } }
```

---

## 5. Engine Boot Sequence Logs
The standard terminal output for a clean, cold boot of the WanOS engine:
```text
MQTT Connected to 10.32.251.181:1883
Subscribed to topic: domoticz/out on 10.32.251.181
Firing 12 MQTT state requests to Domoticz for cold-boot sync and awaiting asynchronous echo...
State Manager worker started.
Core systems online. Base state ready.
Simulation engine booting...
Simulation engine initialized.
[System] Internal Engine State validated and locked.
[System] Internal Event Processed: SYSTEM_READY
[System] Boot sequence complete. HTTP/SSE Web Interface online.
```