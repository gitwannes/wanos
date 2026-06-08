# WanOS Codebase, API, and MQTT Reference

This document serves as the master blueprint and reference guide for the directory layouts, inbound/outbound communications, API endpoints, and Event-Driven payload schemas for the WanOS ecosystem.

## 1. Directory & File Structure Blueprint

**Root Directory (`C:\data\git\wanos\`)**
* `.gitignore`: Specifies intentionally untracked files to ignore for source control.
* `.env`: Secrets file holding sensitive infrastructure values (Excluded from Source Control).
* `config.yaml`: The unified production system configuration file.
* `config_lab.yaml`: Mock architecture states used to initialize variables during Lab Mode.
* `main.py`: The ASGI entry point. Initializes FastAPI, signal traps, and hardware threads.
* `requirements.txt`: Python package dependencies.

**core/**
* `__init__.py`: Package initializer.
* `config.py`: Configuration mapping models used for system verification checks.
* `logger.py`: Custom-tailored asynchronous system log engine.
* `models.py`: House-wide Pydantic modules handling validation layer targets. Defines distinct environmental targets (`outside`, `bathroom`, `cinema`, `sauna_high`, `sauna_low`).
* `mqtt_client.py`: System broker interface and outbound state broadcaster.
* `state_manager.py`: Runs the central system asynchronous event queue. Protects and limits state updates strictly within its single consumer loop execution context. Intercepts discrete sauna sensor updates to calculate true `sauna_calc_temp` and `sauna_calc_hum`.

**frontend/** * `app.js`: Vue application logic, store variables, and component definitions.
* `index.html`: Main HTML entry point and UI layout structure.

**hardware/** (Local Physical Interfaces)
* `sensors.py`: Thread polling managers watching for local physical environmental changes (SHT11 arrays, GPIO pulses).
* `simulator.py`: Implements mathematical thermal engines for Lab Mode. Simulates 24-hour outdoor sine waves, bathroom humidity decay, and complex sauna thermal stratification.

**logic/** (Core Business Rules)
* `auxiliary_controller.py`: Manages ancillary operations including dynamic lighting logic and active step timelines.
* `sauna_controller.py`: Tracks environmental steps, heater rotation algorithms, and multi-tier priority PID metrics.
* `timers.py`: Simple wrappers feeding tracking alerts directly to the core state manager queue upon expiration loops.

**integrations/** (Networked Physical Interfaces)
* `home_hub.py`: Target integration connector interfacing directly with Domoticz environments (reads outdoor temps, commands bathroom and extraction vents).
* `lighting.py`: Coordinates configuration updates directly to local color lighting environments (Hue Bridge).

---

## 2. MQTT Topics

| Topic | Direction | Payload | Trigger/Purpose |
| :--- | :--- | :--- | :--- |
| **`wisc/system/state`** | Outbound | Complete JSON dump of `SystemState` | Published on state mutation |
| **`wisc/system/command`** | Inbound | JSON representing an `Event` | Inject commands into the queue |
| **`wisc/system/console/status`** | Outbound | JSON containing `timestamp`, `level`, `message` | High-level user-facing events |
| **`wisc/system/console/debug`** | Outbound | JSON containing `timestamp`, `level`, `message` | Internal developer engine monologue |
| **`wisc/system/health`** | Outbound | JSON containing backend metrics | Heartbeat task verification |

---

## 3. URLs & Endpoints
The FastAPI server (running at `http://<backend-ip>:8000`) exposes the following primary HTTP and stream routes.

| Endpoint | Method | Purpose | Payload Requirements |
| :--- | :--- | :--- | :--- |
| **`/`** | GET | Serves compiled frontend static assets | N/A |
| **`/api/state`** | GET | Retrieves read-only JSON snapshot for instant sync | N/A |
| **`/api/state/sse`** | GET | Primary persistent real-time UI data pipeline | N/A |
| **`/api/console`** | GET | Retrieves JSON of last 100 log events | N/A |
| **`/api/event`** | POST | Universal endpoint to inject any command into queue | `{"type": "...", "payload": {}}` |
| **`/api/test/temp`** | POST | Dedicated lab endpoint for injecting dummy temps | `{"temp": float}` |
| **`/docs`** | GET | Auto-generated Swagger UI | N/A |

---

## 4. API Event Injection Reference (/api/event)
The `/api/event` endpoint acts as the universal command receiver for WanOS. It accepts HTTP POST requests containing a JSON body mapped to the internal `EventType` schema. These exact same JSON payloads can also be published to the `wisc/system/command` MQTT topic.

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
{ "type": "INITIAL_STATE_LOADED", "payload": {} }
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