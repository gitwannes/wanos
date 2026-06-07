# WanOS Home Control System - Architecture Blueprint

GIT: https://bitbucket.org/bitwannes/wanos

## Definitions
WanOS = Wannes OS = backend system
    This name will only be visible in the admin pages
WISC = Wannes Incredible Sauna Control = part of the system that controls the sauna
    The WISC logo will be visible on the sauna screen
Wome = Wannes home = Home Control, interfaces with Domoticz, listens to temp&hum sensors, gets outside temperature, etc.
    Logo or name placement to be defined.
    In the future, this part will interface with (or be replaced by) HomeAssistant.

## 1. Topography & Hardware Overview
The system operates on a private home network and consists of two primary Raspberry Pi nodes:
* **Backend Node:** Connected via wired Ethernet for maximum stability.
It acts as the brain of the system, handling all calculations, hardware I/O, and state management.
The physical LCD displays are wired directly to this node.
* **Frontend Node (and other clients):** Connected over WiFi.
These act strictly as "dumb" terminals, responsible only for rendering the UI and capturing user inputs.

## 2. Greenfield Development Philosophy & Frameworks
This project is a **100% clean-slate rewrite**.
All new code adheres to modern best practices (SOLID principles, strict typing, modularity).
* **Backend:** Python 3.11+ utilizing **FastAPI**.
Enforces strict data validation via **Pydantic** models. Manages the core async event loop.
* **Frontend:** **Vue 3 (Composition API)** (with a Native HTML5/Tailwind Lab Mode UI during development).
Component-based design allows the UI to be instantly adaptable. State is managed centrally via **Pinia**.
* **Communication:** **MQTT over WebSockets** (using `MQTT.js` on the client side) and Server-Sent Events (SSE) for Lab Mode tracking.
* **MQTT Broker:** **Eclipse Mosquitto**, hosted locally on the Backend Node, explicitly configured for WebSocket listeners.

## 3. Core Principles & Logic Separation
* **Thin Client Architecture:** The frontend holds zero business logic.
All mathematical operations, session tracking, and timers exist purely on the backend.
* **Unidirectional Event Flow:** State is managed via an Event-Driven Architecture.
Hardware callbacks, MQTT listeners, and timers post *Events* to a central `asyncio.Queue`. A State Manager consumes this queue sequentially.
State variables are strictly private attributes mutated only within this event consumer loop.
All external reads go through typed getter methods or Pydantic snapshot models.
* **Time as an Event:** The State Manager does not track time directly. A dedicated background clock module (`HardwareTimer`) fires `TIMER_TICK` events into the queue to progress state machines and count downs deterministically.
* **Logic/Hardware Decoupling:** Business logic modules never write to hardware directly.
They compute targets (e.g., 0-100% PWM, LCD strings, Hex colors) and post state updates.
Hardware controllers subscribe to these targets and perform physical actuation, making logic purely testable without hardware.
* **Smart Home Intermediary:** The existing home automation hub (Domoticz) remains the single source of truth for Z-Wave light switches.
The frontend only communicates with the backend, which proxies commands to the hub.
* **Pessimistic UI:** The frontend employs a "pessimistic" update model.
When a user toggles a light, the UI shows a loading state until the backend confirms the physical state change.
* **Lab Mode:** The backend supports a fully mocked hardware layer, allowing the entire system to be run, tested, and developed on a standard PC.
* **Thread-to-Async Bridging:** Threaded hardware interrupts (e.g., GPIO pulses) cross into the FastAPI `asyncio` loop strictly via `loop.call_soon_threadsafe()`.
* **Asynchronous Hardware I/O:** Synchronous hardware calls (like LCD `sleep()` delays) are isolated in dedicated background threads fed by queues to prevent blocking the async event loop.

## 4. State Broadcasting & Disconnect Strategy
* **Topic Routing:** State is broadcasted across distinct MQTT topics (e.g., `sauna/state`, `bathroom/state`) and the `/api/state/sse` stream.
* **Handling Disconnects (WiFi Drops & Broker Deaths):**
    * The frontend listens for WebSocket connection drops.
    * Upon disconnect, it disables all user inputs to prevent state mismatch and displays a "Reconnecting..." banner.
    * *Shared Failure Domain:* A backend crash severs both the API and MQTT connections.
    The frontend loops until the backend is fully restored.
    * Upon reconnect, the frontend fires a REST/WebSocket intent to request a full state dump from the backend to instantly synchronize, bypassing reliance on potentially missed MQTT stream updates.
* **Reboot Recovery:** On boot, the backend reads a `recovery_state.json` file to recover cumulative metrics and logs, pushing an `INITIAL_STATE_LOADED` event to safely resume operations.

## 5. Configuration, Authentication, & Access
* **Separation of Concerns:** Configuration utilizes two parallel systems. A `.env` file securely holds sensitive keys (MQTT Passwords, PIN codes), while `config.yaml` controls structural properties (Ports, Heating Parameters, Ventilation Timers, Session Defaults).
* **Remote Configuration:** Admins can edit structural YAML configuration directly from the Vue 3 frontend.
* **Authentication:** A single shared PIN code limits unauthorized physical access while maintaining a fast UX.

## 6. UI Structure (Vue 3 Component Tree)
* The UI is built modularly using grid/flexbox layouts.
* **MQTT Subscription Strategy:** A central **Pinia store** manages all MQTT subscriptions.
Vue components read reactive state strictly from the store and never subscribe to MQTT topics directly.
* A dedicated "Switches" view centralizes all smart home lighting controls.

## 7. Directory Structure
**backend/**
* `main.py`: The ASGI entry point.
Initializes FastAPI, signal traps, and hardware threads.
* `.env`: Secrets file (Excluded from Source Control).
* `config.yaml`: The unified configuration file.
* `recovery_state.json`: Local state recovery file.

**core/** (System Foundation)
* `state_manager.py`: Runs the central `asyncio.Queue`. Mutates protected state variables only within the consumer loop.
* `models.py`: Pydantic models for strict state validation (`SystemState`, `SaunaState` containing environmental metrics like humidity, door state, light color, LCD text, and timers).
* `mqtt_client.py`: Mosquitto connection and topic broadcaster.
* `config.py`: Pydantic models for configuration validation.
* `logger.py`: Modernized asynchronous logger.
* `utils.py`: Hardware-agnostic helper functions (formatting, exception handling).

**api/** (Web Layer)
* `server.py`: FastAPI setup and static file hosting.
* `auth.py`: PIN validation logic.
* `routes.py`: Endpoints for initial state dumps and config updates.

**hardware/** (Physical Layer - Lab Mode Ready)
* `hardware_timer.py`: The system metronome. Fires `TIMER_TICK` events every minute.
* `gpio_controller.py`: Manages SSRs, PWM, and pulses using safe async bridging.
Subscribes to State Manager events to handle physical writes.
* `sensors.py`: Temperature/Humidity polling. Sensor read failures post `SENSOR_ERROR` events.
The State Manager escalates persistent failures on critical sensors to a controlled shutdown sequence.
* `lcd_display.py`: Threaded LCD queue consumer.

**logic/** (Business Rules - Pure Python, No Hardware Imports)
* `sauna_controller.py`: PID math, fire-order generation, waterfall distribution, and safety limits (door open lockouts, hold mode logic).
* `auxiliary_controller.py`: Environmental state machine. Calculates Hue lighting color math, LCD text formatting, and ventilation staging based on timers.
* `shower_tracker.py`: Cost calculation and shower log management.
* `timers.py`: Timers are `asyncio.Task` wrappers that post expiry events (e.g., `SAUNA_TIMER_EXPIRED`) to the central queue on completion.
They do not call logic functions directly.

**integrations/** (External Services)
* `home_hub.py`: API client for Domoticz/Z-Wave communication.
* `lighting.py`: Color math and Hue Bridge API client.

## 8. Safety Mechanisms, Watchdogs & Graceful Shutdown
* **Hardware Actuation Lock:** `gpio_controller.py` must explicitly verify a global `hardware_live_mode` flag before asserting physical PWM signals.
On boot, `hardware_live_mode` defaults to `False` regardless of `recovery_state.json` contents.
The operator must explicitly re-enable live operation via the frontend after confirming the hardware state.
* **Door Interlock:** The Bouncer actively rejects `SAUNA_ON` commands if `door_open == True` and bypasses the PID to drop heaters to 0% if the door opens mid-session.
* **The Safety Heartbeat Pin:** A dedicated GPIO pin is pulled high as a physical heartbeat indicating the software is in control.
This pin only goes high *after* the `INITIAL_STATE_LOADED` event is successfully processed.
* **Clean Exit Sequence:** `main.py` registers handlers for `SIGINT` and `SIGTERM`.
If the process exits or crashes, a guaranteed teardown sequence pulls SSR pins LOW, zeroes PWM channels, and releases the heartbeat pin to immediately shut off heating elements.

## 9. Core Event Type Catalogue
To enforce strict typing in the `asyncio.Queue`, all internal events must map to a predefined schema using an explicit `EventType` Enum.

**Hardware Events:** `TEMP_UPDATED`, `HUMIDITY_UPDATED`, `WATER_PULSE`, `KWH_PULSE`, `DOOR_CHANGED`, `SENSOR_ERROR`, `TIMER_TICK`

**Sauna Events:**
`SAUNA_ON`, `SAUNA_OFF`, `SETPOINT_CHANGED`, `MODULATION_UPDATED`, `SETPOINT_REACHED`, `SAUNA_HOLD`, `SAUNA_TIMER_EXPIRED`, `HOLD_TOGGLED`

**IR Events:**
`IR_ON`, `IR_OFF`, `IR_MODULATION_UPDATED`, `IR_TIMER_EXPIRED`

**System Events:**
`INITIAL_STATE_LOADED`, `BACKEND_SHUTDOWN`, `HARDWARE_LIVE_MODE_CHANGED`, `CONFIG_UPDATED`

**External Events:**
`HUB_STATE_CHANGED`, `LIGHTING_STATE_CHANGED`, `EXTERNAL_WEATHER_UPDATED`

## 10. Phased Implementation Roadmap
To mitigate risk and ensure logical separation from hardware quirks, development will proceed in the following phases:

* **Phase 1: Backend Core (COMPLETE)**
  FastAPI + MQTT + `state_manager` + Pydantic models.
  No frontend, no business logic, no GPIO changes. Verify it boots, processes a dummy event via the queue, and communicates out over MQTT.
* **Phase 2: Lab Mode & Logic (COMPLETE)**
  Implement the hardware abstraction layer and core business logic (`sauna_controller`, `shower_tracker`). 3-Phase Waterfall PID Controller, Wear-Leveling, Frontend Lab Mode UI.
  Ensure mock sensors correctly trigger the PID loop and output state changes without physical hardware attached.
* **Phase 3: Environmental State Machine (ACTIVE)**
  Door interlocks, Session Timers, Auxiliary Controller (Hue/LCD simulation), and Timer Ticks via a dedicated `HardwareTimer` module.
* **Phase 4: Vue.js Frontend & External Integrations**
  Build the production UI, connect to the backend, test PIN authentication, and ensure the pessimistic update patterns function smoothly. Wire up `home_hub.py` (Domoticz) and `lighting.py` (Hue).
* **Phase 5: Hardware Migration (The Physical World)**
  Map the physical GPIOs, transition the backend to the live Raspberry Pi, and finally migrate the LCD screens (direct I²C).
  Isolated to the end to clearly separate logic bugs from hardware threading/blocking issues.
  
## 11. MQTT Topics
WanOS utilizes a strict topic structure for broadcasting data and receiving commands.

* **`wisc/system/state`**
  * **Direction:** Outbound (Backend -> Frontend/Clients)
  * **Payload:** Complete JSON dump of the nested `SystemState` Pydantic model.
  * **Trigger:** Published any time a state mutation occurs within the `StateManager` consumer loop.
* **`wisc/system/command`**
  * **Direction:** Inbound (Clients -> Backend)
  * **Payload:** JSON representing an `Event` (`{"type": "...", "payload": {...}}`).
  * **Purpose:** Allows external tools (Home Assistant, scripts) to inject commands directly into the State Manager queue.
* **`wisc/system/console/status`**
  * **Direction:** Outbound
  * **Payload:** JSON containing `timestamp`, `level` (INFO, SUCCESS, WARNING, ERROR), and `message`.
  * **Purpose:** High-level, user-facing events (e.g., "Sauna activated"). Used by the main frontend dashboard for live updates.
* **`wisc/system/console/debug`**
  * **Direction:** Outbound
  * **Payload:** JSON containing `timestamp`, `level` (DEBUG), and `message`.
  * **Purpose:** Internal engine monologue (e.g., event processing, queue routing) used strictly for developer troubleshooting and background monitoring.
* **`wisc/system/health`**
  * **Direction:** Outbound
  * **Payload:** JSON containing backend metrics (e.g., CPU temp, active async tasks, queue depth).
  * **Purpose:** Broadcasted periodically by a heartbeat task to verify the engine is healthy and responsive.

## 12. URLs & Endpoints
The FastAPI server (running at `http://<backend-ip>:8000`) exposes the following primary routes.

* **`/` (Root)**
  * **Method:** GET
  * **Purpose:** Will eventually serve the compiled Vue 3 frontend static assets.
* **`/api/state`**
  * **Method:** GET
  * **Purpose:** Retrieves a safe, read-only JSON snapshot of the current `SystemState`. Used by the frontend immediately upon connection/reconnection to synchronize before relying on the MQTT stream.
* **`/api/console`**
  * **Method:** GET
  * **Purpose:** Retrieves a pretty-printed JSON snapshot of the last 100 log events held in the backend's rolling memory buffer. Acts as the REST/HTTP alternative to the MQTT WebSocket stream for viewing system history.
* **`/api/event`**
  * **Method:** POST
  * **Payload Structure:** `{"type": "EVENT_TYPE_STRING", "payload": {}}`
  * **Purpose:** Universal endpoint to inject any system command into the internal `asyncio.Queue`. Allows UI actions to trigger backend logic.
* **`/api/test/temp`**
  * **Method:** POST
  * **Payload Structure:** `{"temp": float}`
  * **Purpose:** Dedicated development endpoint for injecting dummy temperature readings during Lab Mode testing.
* **`/docs`**
  * **Method:** GET
  * **Purpose:** Auto-generated Swagger UI. Provides an interactive web interface to view, test, and validate all API endpoints.

## 13. API Event Injection Reference (/api/event)
The `/api/event` endpoint acts as the universal command receiver for WanOS. It accepts HTTP POST requests containing a JSON body mapped to the internal `EventType` schema. 

Below is the complete catalogue of valid JSON payloads for every event in the Wanos architecture. These exact same JSON payloads can also be published to the `wisc/system/command` MQTT topic.

### Sauna Events
Commands and state updates for the main sauna logic.

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

**Notify Sauna Timer Expired:**
```json
{ "type": "SAUNA_TIMER_EXPIRED", "payload": {} }
```

### Infrared (IR) Events
Commands and state updates for the secondary IR heating logic.

**Turn IR ON:**
```json
{ "type": "IR_ON", "payload": {} }
```

**Turn IR OFF:**
```json
{ "type": "IR_OFF", "payload": {} }
```

**Manually Override IR Modulation (PWM):**
```json
{ "type": "IR_MODULATION_UPDATED", "payload": { "pwm": 80.0 } }
```

**Notify IR Timer Expired:**
```json
{ "type": "IR_TIMER_EXPIRED", "payload": {} }
```

### Hardware & Sensor Events
Used by hardware controllers (or Lab Mode) to update the system on physical environment changes.

**Update Temperature:**
```json
{ "type": "TEMP_UPDATED", "payload": { "value": 45.5 } }
```

**Update Humidity:**
```json
{ "type": "HUMIDITY_UPDATED", "payload": { "value": 30.0 } }
```

**Register Water Flow Pulse (Shower tracking):**
```json
{ "type": "WATER_PULSE", "payload": { "liters": 1.0 } }
```

**Register Power Consumption Pulse (kWh tracking):**
```json
{ "type": "KWH_PULSE", "payload": { "kwh": 0.001 } }
```

**Update Door State:**
```json
{ "type": "DOOR_CHANGED", "payload": { "is_open": true } }
```

**Report Sensor Error:**
```json
{ "type": "SENSOR_ERROR", "payload": { "sensor": "DHT22", "error": "timeout" } }
```

**System Metronome Tick (One minute passed):**
```json
{ "type": "TIMER_TICK", "payload": {} }
```

### System Events
Core system lifecycle commands.

**Engine Boot Complete:**
```json
{ "type": "INITIAL_STATE_LOADED", "payload": {} }
```

**Trigger Graceful Shutdown:**
```json
{ "type": "BACKEND_SHUTDOWN", "payload": {} }
```

**Enable/Disable Hardware Live Mode:**
```json
{ "type": "HARDWARE_LIVE_MODE_CHANGED", "payload": { "live_mode": true } }
```

**Notify Config Updated:**
```json
{ "type": "CONFIG_UPDATED", "payload": {} }
```

### External Integrations
Updates from the broader Wome ecosystem (Domoticz/Hue).

**Update Hub State (Domoticz):**
```json
{ "type": "HUB_STATE_CHANGED", "payload": { "device_id": "12", "state": "ON" } }
```

**Update Lighting State (Hue):**
```json
{ "type": "LIGHTING_STATE_CHANGED", "payload": { "zone": "bathroom", "state": "OFF" } }
```

**Update External Weather:**
```json
{ "type": "EXTERNAL_WEATHER_UPDATED", "payload": { "temp": 15.0, "condition": "rain" } }
```