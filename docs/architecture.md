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
The system operates on a private home network and consists of two primary Raspberry Pi nodes. The **Backend Node** is connected via wired Ethernet for maximum stability. It acts as the brain of the system, handling all calculations, hardware I/O, and state management. The physical LCD displays are wired directly to this node. The **Frontend Node** (and other clients) connects over WiFi. These act strictly as "dumb" terminals, responsible only for rendering the UI and capturing user inputs.

## 2. Greenfield Development Philosophy & Frameworks
This project is a **100% clean-slate rewrite**. All new code adheres to modern best practices (SOLID principles, strict typing, modularity).

* **Backend:** Python 3.11+ utilizing **FastAPI**. Enforces strict data validation via **Pydantic** models. Manages the core async event loop.
* **Frontend:** **Vue 3 (Composition API)**. Component-based design allows the UI to be instantly adaptable. 
* **Communication:** **Server-Sent Events (SSE)** for frontend real-time tracking, and **MQTT over WebSockets** for external clients/hardware.
* **MQTT Broker:** **Eclipse Mosquitto**, hosted locally on the Backend Node, explicitly configured for WebSocket listeners.

## 3. Core Principles & Logic Separation
* **Thin Client Architecture:** The frontend holds zero business logic. All mathematical operations, session tracking, and timers exist purely on the backend.
* **Unidirectional Event Flow:** State is managed via an Event-Driven Architecture. Hardware callbacks, MQTT listeners, and timers post Events to a central queue. 
* **Time as an Event:** The State Manager does not track time directly. A dedicated background clock module fires `TIMER_TICK` events to progress state machines deterministically.
* **Logic/Hardware Decoupling:** Business logic modules never write to hardware directly. They compute targets and post state updates. Actuators are strictly divided: `hardware/` modules manage local GPIO (heaters, local SHT11 sensors), while `integrations/` modules bridge out to network hubs like Domoticz and Hue (bathroom vents, external weather).
* **Pessimistic UI:** The frontend employs a "pessimistic" update model. When a user toggles a light, the UI shows a loading state until the backend confirms the physical state change.
* **Lab Mode:** The backend supports a fully mocked hardware layer. Thermodynamic engines simulate complex states (e.g., sauna thermal stratification, bathroom humidity decay, outside 24h temperature cycles) allowing the system to be run and tested on a standard PC.
* **Thread-to-Async Bridging:** Threaded hardware interrupts cross into the FastAPI loop strictly via threadsafe methods.
* **Asynchronous Hardware I/O:** Synchronous hardware calls are isolated in dedicated background threads fed by queues to prevent blocking the async event loop.

## 4. State Broadcasting & Disconnect Strategy
State is broadcasted across distinct MQTT topics (e.g., `sauna/state`) and the `/api/state/sse` stream. 

If the WebSocket/SSE connection drops, the frontend disables all user inputs to prevent state mismatch and displays a "Reconnecting..." banner. Upon reconnect, the frontend fires a REST/WebSocket intent to request a full state dump from the backend to instantly synchronize, bypassing reliance on potentially missed stream updates. On backend boot, the system reads a `recovery_state.json` file to recover cumulative metrics and pushes an `INITIAL_STATE_LOADED` event to safely resume.

## 5. Configuration, Authentication, & Access
* **Separation of Concerns:** A `.env` file securely holds sensitive keys, while `config.yaml` controls structural properties. `config_lab.yaml` is used for injecting mock states during Lab Mode.
* **Remote Configuration:** Admins can edit structural YAML configuration directly from the frontend.
* **Authentication:** A single shared PIN code limits unauthorized physical access while maintaining a fast UX.

## 6. UI Structure (Vue 3 Component Tree)
The UI is built modularly using grid/flexbox layouts. A central store manages all SSE/MQTT subscriptions. Vue components read reactive state strictly from the store and never subscribe to streams directly. A dedicated "Switches" view centralizes all smart home lighting controls.

## 7. Safety Mechanisms, Watchdogs & Graceful Shutdown
* **Hardware Actuation Lock:** The GPIO controller must explicitly verify a global `hardware_live_mode` flag before asserting physical signals.
* **Door Interlock:** The Bouncer actively rejects `SAUNA_ON` commands if the door is open and bypasses the PID to drop heaters to 0% if the door opens mid-session.
* **Clean Exit Sequence:** The ASGI entry point registers handlers for `SIGINT` and `SIGTERM`. If the process exits or crashes, a guaranteed teardown sequence triggers to immediately shut off heating elements.

## 8. Core Event Type Catalogue
To enforce strict typing, all internal events must map to a predefined schema using an explicit `EventType` Enum. *(For full payload schemas, refer to `reference.md`)*

**Hardware Events:** `TEMP_UPDATED`, `HUMIDITY_UPDATED`, `WATER_PULSE`, `KWH_PULSE`, `DOOR_CHANGED`, `SENSOR_ERROR`, `TIMER_TICK`
**Sauna Events:** `SAUNA_ON`, `SAUNA_OFF`, `SETPOINT_CHANGED`, `MODULATION_UPDATED`, `SETPOINT_REACHED`, `SAUNA_HOLD`, `SAUNA_TIMER_EXPIRED`, `HOLD_TOGGLED`, `TIMER_ADJUSTED`, `VENT_WAIT_EXPIRED`, `VENT_RUN_EXPIRED`
**System Events:** `INITIAL_STATE_LOADED`, `BACKEND_SHUTDOWN`, `HARDWARE_LIVE_MODE_CHANGED`, `CONFIG_UPDATED`

## 9. Phased Implementation Roadmap
To mitigate risk and ensure logical separation from hardware quirks, development will proceed in the following phases:

* **Phase 1: Backend Core (COMPLETE)** - FastAPI + MQTT + `state_manager` + Pydantic models.
* **Phase 2: Lab Mode & Logic (COMPLETE)** - Hardware abstraction layer and core business logic (`sauna_controller`).
* **Phase 3: Environmental State Machine (COMPLETE)** - Door interlocks, Session Timers, Auxiliary Controller, and Thermodynamics Lab Engine. 
* **Phase 4: Vue Frontend & External Integrations (ACTIVE)** - Build the production UI, connect to the backend, test PIN authentication.
* **Phase 5: Hardware Migration (The Physical World)** - Map the physical GPIOs, transition the backend to the live Raspberry Pi, and finally migrate the LCD screens.

## 10. Technical Reference Guide
All implementation mapping blueprints—including **Codebase Directory Layouts**, **MQTT Topics**, **REST API URLs**, **SSE Endpoints**, and exact **API Event Injection JSON payloads**—have been centralized into a comprehensive system reference document.

**👉 See `reference.md`**