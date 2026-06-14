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
* **Modern IoT Telemetry Pipeline:** Session metrics follow a three-tier Hot/Warm/Cold architecture. Active sessions accumulate accurate *time-weighted averages* in RAM (`SessionAggregator` - Hot). Upon session end, the structured Pydantic payload is dumped to `last_sessions.json` for instant UI boot restoration (Warm), and logged concurrently into a self-contained `wanos_history.db` SQLite database for long-term analytics and graphing (Cold).
* **Logic/Hardware Decoupling:** Business logic modules never write to hardware directly. They compute targets and post state updates. Actuators are strictly divided: `hardware/` modules manage local GPIO (heaters, local SHT11 sensors), while `integrations/` modules bridge out to network hubs like Domoticz and external APIs.
* **Pessimistic UI:** The frontend employs a "pessimistic" update model. When a user toggles a light, the UI shows a loading/disabled state until the backend confirms the physical state change. Core safety elements (like PC power or Hardware Bus) require bidirectional DaisyUI modal confirmation before emitting payloads.
* **Lab Mode:** The backend supports a fully mocked hardware layer. Thermodynamic engines simulate complex states (sauna thermal stratification, bathroom humidity decay, outside 24h temperature cycles, and dynamic kW tracking scaling exactly to UI Setpoints) allowing the system to be run and tested on a standard PC.

## 4. State Broadcasting & Disconnect Strategy
State is broadcasted across **seven domain-scoped MQTT topics** rather than a single monolithic dump. Each topic fires independently at its own cadence.

To combat the "Smart Plug Firehose" (where noisy, high-frequency wattage fluctuations spam the network), WanOS utilizes a **Deep Rolling Average Buffer**. Inbound metrics (e.g., PC Power) are captured into a x-point moving array. The backend calculates smoothed aggregates in RAM and strictly throttles SSE UI updates, only broadcasting when the rounded median mathematically shifts.

The backend SSE loop evaluates data frames every 0.5 seconds; it suppresses transmissions unless a state change occurs, or a 5-second silence barrier is reached—at which point it pipes a lightweight `{"domain": "ping"}` frame down the pipe. The frontend maintains an internal 10-second sliding watchdog to guard against dirty socket drops.

## 5. Configuration, Authentication, & Access
* **Separation of Concerns:** - `.env`: Securely holds sensitive keys, passwords, and external API tokens.
  - `hardware.yaml`: Layered static definitions of physical/virtual node IDXs, MQTT targets, and GPIO pins.
  - `config.yaml`: Controls dynamic structural and runtime properties (default setpoints, PIDs, IR defaults, API polling intervals).
  - `config_lab.yaml`: Injects mock states during Lab Mode.

## 6. UI Structure (Alpine.js Component Tree)
The UI is built modularly using CSS Grid and Flexbox layouts via Tailwind CSS. 
* **50/50 Split Layout:** The Sauna/IR setpoints utilize a horizontal side-by-side split grid.
* **Zero-Crossing Modulation:** The IR Setpoint employs a snapping Alpine slider that strictly maps percentages (0, 25, 33, 50, 67, 75, 100) to safe 50Hz AC zero-crossing frequencies to prevent physical Solid State Relay (SSR) flickering on the home electrical grid.
* **Visual Data Overlays:** Lightweight, auto-scaling SVG sparklines are dynamically mapped on the client side using 10-point historical telemetry arrays pushed by the backend.

## 7. Safety Mechanisms, Watchdogs & Graceful Shutdown
* **Hardware Actuation Lock:** The GPIO controller must explicitly verify a global `hardware_live_mode` flag before asserting physical signals.
* **Door Interlock:** The Bouncer actively rejects `SAUNA_ON` commands if the door is open and bypasses the PID to drop heaters to 0% if the door opens mid-session.
* **Network Link Watchdog:** A sliding 10-second watchdog actively monitors the health of the underlying SSE HTTP stream connection.
* **Clean Exit Sequence:** The ASGI entry point registers handlers for `SIGINT` and `SIGTERM`.

## 8. Core Event Type Catalogue
For payload schemas, refer to `reference.md`.

## 9. Phased Implementation Roadmap
To mitigate risk and ensure logical separation from hardware quirks, development proceeds in the following phases:

* **Phase 1: Backend Core (COMPLETE)** - FastAPI + MQTT + `state_manager` + Pydantic models.
* **Phase 2: Lab Mode & Logic (COMPLETE)** - Hardware abstraction layer and core business logic (`sauna_controller`).
* **Phase 3: Environmental State Machine & Integrations (COMPLETE)** - Door interlocks, Session Timers, Thermodynamics Lab Engine, Alpine.js layout overhaul, and the Domoticz network bridge.
* **Phase 4: Administrative UI, Telemetry & REST APIs (COMPLETE)** - Built the System Administration panel, dynamic SVG sparklines, shifted uptime calculations to client-side tickers, and stabilized connection watchdog frameworks.
* **Phase 5: Hardware Migration (COMPLETE)** - Map the physical Raspberry Pi GPIOs, bi-directional interceptor modals, zero-crossing frequency matrices for SSRs, and sliding 40-point buffers for noisy electrical firehoses.
* **Phase 6: Data Telemetry (ACTIVE)** - Finalize the Hot/Warm/Cold data lifecycle. Implement the RAM `SessionAggregator`, `last_sessions.json` boot restoration, and the `wanos_history.db` SQLite analytics engine.

## 10. Technical Reference Guide
All implementation mapping blueprints—including **Codebase Directory Layouts**, **MQTT Topics**, **REST API URLs**, **SSE Endpoints**, and exact **API Event Injection JSON payloads**—have been centralized into a comprehensive system reference document.

**👉 See `reference.md`**