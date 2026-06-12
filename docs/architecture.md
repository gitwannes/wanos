# --- file: architecture.md ---

# WanOS Home Control System - Architecture Blueprint

GIT: https://bitbucket.org/bitwannes/wanos

## Definitions
WanOS = Wannes OS = backend system: interfaces with Domoticz, listens to temp&hum sensors, gets outside temperature, etc.
WISC = Wannes Incredible Sauna Control = part of the system that controls the sauna & IR
Logo or name placement to be defined.

## 1. Topography & Hardware Overview
The system operates on a private home network and consists of two primary Raspberry Pi nodes. The **Backend Node** is connected via wired Ethernet for maximum stability. It acts as the brain of the system, handling all calculations, hardware I/O, and state management. The physical LCD displays are wired directly to this node.
The **Frontend Node** (and other clients) connects over the network (WiFi or other). These act strictly as "dumb" terminals, responsible only for rendering the UI and capturing user inputs.

## 2. Greenfield Development Philosophy & Frameworks
This project is a 100% clean-slate rewrite.
All new code adheres to modern best practices (SOLID principles, strict typing, modularity).

* **Backend:** Python 3.11+ utilizing **FastAPI**. Enforces strict data validation via **Pydantic** models. Manages the core async event loop.
* **Frontend:** **Alpine.js**. A lightweight, reactive framework paired with **TailwindCSS** and **DaisyUI** allows the UI to be instantly adaptable without a heavy build step.
* **Communication:** **Server-Sent Events (SSE)** for frontend real-time tracking, and **MQTT** for external clients/hardware.
* **Dual MQTT Brokers:** The system utilizes a dual-client architecture.
	A local Mosquitto broker handles internal diagnostic monitoring and telemetry tools.
	While a dedicated secondary client bridges to Domoticz.

## 3. Core Principles & Logic Separation
* **Thin Client Architecture:** The frontend holds zero business logic. All mathematical operations, session tracking, and timers exist purely on the backend.
* **Unidirectional Event Flow:** State is managed via an Event-Driven Architecture. Hardware callbacks, MQTT listeners, and timers post Events to a central queue. 
* **Logic/Hardware Decoupling:** Business logic modules never write to hardware directly. They compute targets and post state updates. Actuators are strictly divided: `hardware/` modules manage local GPIO (heaters, local SHT11 sensors), while `integrations/` modules bridge out to network hubs like Domoticz and Hue (bathroom vents, external weather).
* **Pessimistic UI:** The frontend employs a "pessimistic" update model. When a user toggles a light, the UI shows a loading/disabled state until the backend confirms the physical state change.
* **Lab Mode:** The backend supports a fully mocked hardware layer. Thermodynamic engines simulate complex states (e.g., sauna thermal stratification, bathroom humidity decay, outside 24h temperature cycles) allowing the system to be run and tested on a standard PC.
* **Thread-to-Async Bridging:** Threaded hardware interrupts cross into the FastAPI loop strictly via threadsafe methods.
* **Asynchronous Hardware I/O:** Synchronous hardware calls are isolated in dedicated background threads fed by queues to prevent blocking the async event loop.

## 4. State Broadcasting & Disconnect Strategy
State is broadcasted across **seven domain-scoped MQTT topics** rather than a single monolithic dump. Each topic fires independently at its own cadence.
Ref. reference.md ## 2. MQTT Topic Architecture
Ref. reference.md ## 3. URLs & Endpoints

-*-*-*

The backend SSE loop evaluates data frames every 0.5 seconds; it suppresses transmissions unless a state change occurs, or a 5-second silence barrier is reached—at which point it pipes a lightweight `{"domain": "ping"}` frame down the pipe. The frontend maintains an internal 10-second sliding watchdog. If the channel goes quiet (e.g., a dirty drop where a cable is pulled and no TCP FIN packet is broadcast), the watchdog clears active loops, forces connection termination, and flashes a blurred "LINK INTERRUPTED" modal.

Pulse metrics (`WATER_PULSE`, `KWH_PULSE`) are accumulated internally and emitted as rounded integer values on the delta streams. Incoming duplicate raw sensor packets are explicitly filtered and dropped before hitting the state manager to prevent echo loops and network spam.

## 5. Configuration, Authentication, & Access
* **Separation of Concerns:** - `.env`: Securely holds sensitive keys and passwords.
  - `hardware.yaml`: Layered static definitions of physical/virtual node IDXs, MQTT targets, and GPIO pins.
  - `config.yaml`: Controls dynamic structural and runtime properties (default setpoints, PIDs).
  - `config_lab.yaml`: Injects mock states during Lab Mode.
* **Remote Configuration:** Admins can edit structural YAML configuration directly from the frontend.
* **Authentication:** A single shared PIN code limits unauthorized physical access while maintaining a fast UX.

## 6. UI Structure (Alpine.js Component Tree)
The UI is built modularly using CSS Grid and Flexbox layouts via Tailwind CSS. A central `wanosApp()` store manages all SSE/MQTT subscriptions. HTML views read reactive state strictly from the Alpine `x-data` object and inject changes via REST endpoints. The main layout snapping model spans to 100% display widths following the complete removal of the rolling in-memory logs panel.

## 7. Safety Mechanisms, Watchdogs & Graceful Shutdown
* **Hardware Actuation Lock:** The GPIO controller must explicitly verify a global `hardware_live_mode` flag before asserting physical signals.
* **Door Interlock:** The Bouncer actively rejects `SAUNA_ON` commands if the door is open and bypasses the PID to drop heaters to 0% if the door opens mid-session.
* **Network Link Watchdog:** A sliding 10-second watchdog actively monitors the health of the underlying SSE HTTP stream connection, triggering immediate data recovery cycles on failure.
* **Clean Exit Sequence:** The ASGI entry point registers handlers for `SIGINT` and `SIGTERM`. If the process exits or crashes, a guaranteed teardown sequence triggers to safely shut off heating elements and cleanly disconnect MQTT streams.

## 8. Core Event Type Catalogue
To enforce strict typing, all internal events must map to a predefined schema using an explicit `EventType` Enum. *(For full payload schemas, refer to `reference.md`)*

**Hardware Events:** `TEMP_UPDATED`, `HUMIDITY_UPDATED`, `WATER_PULSE`, `KWH_PULSE`, `DOOR_CHANGED`, `SENSOR_ERROR`, `TIMER_TICK`
**Sauna Events:** `SAUNA_ON`, `SAUNA_OFF`, `SETPOINT_CHANGED`, `MODULATION_UPDATED`, `SETPOINT_REACHED`, `SAUNA_HOLD`, `SAUNA_TIMER_EXPIRED`, `HOLD_TOGGLED`, `TIMER_ADJUSTED`, `VENT_WAIT_EXPIRED`, `VENT_RUN_EXPIRED`
**System Events:** `SYSTEM_READY`, `BACKEND_SHUTDOWN`, `HARDWARE_LIVE_MODE_CHANGED`, `CONFIG_UPDATED`, `SYSTEM_METRICS_UPDATED`

## 9. Phased Implementation Roadmap
To mitigate risk and ensure logical separation from hardware quirks, development proceeds in the following phases:

* **Phase 1: Backend Core (COMPLETE)** - FastAPI + MQTT + `state_manager` + Pydantic models.
* **Phase 2: Lab Mode & Logic (COMPLETE)** - Hardware abstraction layer and core business logic (`sauna_controller`).
* **Phase 3: Environmental State Machine & Integrations (COMPLETE)** - Door interlocks, Session Timers, Thermodynamics Lab Engine, Alpine.js layout overhaul, and the Domoticz network bridge.
* **Phase 4: Administrative UI & Telemetry (COMPLETE)** - Built the System Administration panel, shifted uptime calculations completely to client-side tickers, optimized web layouts to full width, and stabilized connection watchdog frameworks.
* **Phase 5: Hardware Migration (ACTIVE)** - Map the physical Raspberry Pi GPIOs, build live SHT11 hardware retry/failure loops, transition backend to physical node, and migrate LCD hardware screens.

## 10. Technical Reference Guide
All implementation mapping blueprints—including **Codebase Directory Layouts**, **MQTT Topics**, **REST API URLs**, **SSE Endpoints**, and exact **API Event Injection JSON payloads**—have been centralized into a comprehensive system reference document.

**👉 See `reference.md`**
```