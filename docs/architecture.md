# --- file: architecture.md ---

# WanOS Home Control System - Architecture Blueprint

**Repository Link:** https://bitbucket.org/bitwannes/wanos  
**Target Environment:**

** Wanos backend
* Raspberry Pi 4 Model B Rev 1.5 (batcat -A /proc/device-tree/model)
* OS: Debian 13 Trixie Lite 64-bit

** Wanos frontend
* Raspberry Pi 3 Model B Rev 1.2 (cat /proc/device-tree/model)
* Waveshare 4.3inch IPS screen, 800 x 480 hardware resolution
* connected via DSI
* https://www.waveshare.com/wiki/4.3inch_DSI_LCD
* OS: Raspberry Pi OS Lite - Debian 12 Bookworm 32-bit
* kiosk stack: cage + chromium
* cage
* is a Wayland compositor built specifically for kiosks
* its entire job is to launch exactly one application and lock it to full-screen
* config.txt
* dtparam=audio=off            # saves RAM/CPU
* dtoverlay=disable-bt         # saves RAM/CPU & reduces electrical noise near the wifi antenna
* dtoverlay=vc4-kms-v3d        # DSI driver Wayland stack: Linux Kernel Mode Setting (KMS) 3D graphics driver
* On Debian 12 (Bookworm), the Wayland display server requires this driver to talk to the Pi's GPU.
* dtoverlay=vc4-kms-dsi-7inch  # destination: tells the GPU where to send the signal
* network connection rule: iw dev wlan0 set power_save off
* use swayidle for DSI power cutoff


---

## 1. Topography & Node Topology

The system operates on an isolated local network, separating intensive background processing loops from presentation display layers:

* **The Backend Node (The Processing Brain):** Deployed via a physical wired Ethernet interface for absolute connection stability. It houses the asynchronous event thread queue, executes the PID algorithms, binds to physical interfaces, and drives local hardware lines.
* **The Frontend Client Terminals:** Connected over local Wi-Fi or user devices. They function strictly as lightweight, stateless "dumb" presentation displays, translating user interactions into standard event frames and rendering updates from the server.

---

## 2. Greenfield Programming Philosophy & Stack Frameworks

WanOS is built from a 100% clean-slate modular architecture adhering strictly to object separation patterns and clean type hinting conventions:

* **The Core Backend Sandbox:** Built on Python 3.9+ (running production-validated Python 3.11+ patterns) utilizing **FastAPI**. It enforces strict data validation contracts through **Pydantic** structures and coordinates non-blocking background routines using the `asyncio` event loop engine.
* **The Presentation Interface:** Powered by **Alpine.js**. Paired with **TailwindCSS** and **DaisyUI**, it allows for instant reactive UI updates and theme matching without relying on intensive, long-compile node build bundles.
* **The Communication Layer:** Employs **Server-Sent Events (SSE)** for unidirectional backend-to-browser telemetry streams, and utilizes a **Dual MQTT Broker Architecture** to maintain clean network boundaries:
  1. A Local `localhost` Mosquitto broker handles high-frequency administrative diagnostic metrics and terminal log monitors.
  2. A Remote client bridge targets your secondary home hub node to handle long-distance external data exchanges.

---

## 3. Structural Design Patterns & Core Logic Boundaries

```text
  [Inbound Streams]       [The Central Processing Brain]      [Outbound Delivery]
  
  ┌─────────────────┐     ┌────────────────────────────┐     ┌────────────────────┐
  │  MqttTransport  │────>│         StateManager       │────>│   MqttPublisher    │
  └─────────────────┘     │    (Event Queue Router)    │     └────────────────────┘
                          │             │              │               │
  ┌─────────────────┐     │             ▼              │               ▼
  │   FastAPI App   │────>│   ┌────────────────────┐   │     ┌────────────────────┐
  └─────────────────┘     │   │   Event Handlers   │   │     │  Local Broker UI   │
                          │   │ (Strategy Pattern) │   │     └────────────────────┘
  ┌─────────────────┐     │   └────────────────────┘   │               │
  │ Physical Probes │────>└────────────────────────────┘               ▼
  └─────────────────┘                   │                    ┌────────────────────┐
                                        ▼                    │ Remote Hub Network │
    ┌─────────────────┐   ┌────────────────────────────┐     └────────────────────┘
    │  HealthMonitor  │   │     AutomationEngine       │     
    │  Env. Scheduler │   └────────────────────────────┘
    └─────────────────┘
```

### Unidirectional Event Flow & The Strategy Pattern
All internal transitions follow a strictly structured event routing path. Outbound network drivers, user button presses, and automated background timers never modify system states directly. Instead, they format an `Event` and push it to an asynchronous `Queue`. 

To prevent the `StateManager` from becoming a monolithic "God Object", it utilizes the **Strategy Pattern**. When an event is pulled from the queue, the StateManager acts as an ultra-fast proxy, instantly mapping the payload to an isolated function in the `core/event_handlers/` registry. This cleanly separates routing from business execution.

### Single Responsibility Background Services
Heavy, non-blocking operational tasks are extracted into dedicated service classes under the `logic/` directory:
* **The Health Monitor:** Pings sockets and external bridges continuously, dispatching Auto-Kill commands if hardware is dropped.
* **The Environment Scheduler:** Performs mathematical bounds clamping for sun cycles.
* **The Alert Manager:** Centralizes all UI notification generation and deduplication.

### Thin Client Architecture
The frontend web browser holds zero business or processing logic. All mathematical filtering, time thresholds, hysteresis loops, and scheduler parameters exist purely inside the backend Python environment. The client simply receives the processed data snapshot and prints it to the viewport frames.

### Noisy Metric Smoothing (Rolling Average Buffers)
To combat network pollution caused by highly erratic device telemetry (such as high-frequency electrical plug updates), the system uses a **RAM Moving Average Array**. Incoming telemetry metrics (like raw computer power draw) are collected into a rolling 10-point window. The backend processes a smoothed aggregate value and suppresses downstream SSE updates unless the final rounded value shifts, preventing UI flashing.

### Logic-to-Hardware Decoupling (The Boundary Rule)
Core software algorithms have no direct awareness of physical circuit links. They calculate target metrics and update state models. Outbound actions are separated into clean directory paths: `hardware/` modules manage local GPIO lines (relays and local SHT11 probes), while `integrations/` handle the networking protocols for external platforms like your Hue Bridge, Domoticz instance, and the Epson Projector TCP socket.

### Pessimistic Presentation Rendering & Permissive Interlocks
The web dashboard follows a pessimistic update path. When a toggle is clicked, the switch locks and changes to a "SYNCING..." loading state until the verified state pushes back down the SSE telemetry stream. Furthermore, the backend employs **Permissive Interlocks** (ICS standards): if a user attempts to arm an integration whose physical socket is offline, the handlers immediately reject the payload and trigger a red UI alert before state corruption can occur.

---

## 4. Life-Cycle Telemetry, Version Tracking & Security

### Hot/Warm/Cold Data Lifecycles
System operations use an tiered storage structure based on performance demands:
* **Hot Storage (RAM):** The active event queue and moving average history windows process inputs at microsecond speeds.
* **Warm Storage (Local Filesystem):** Critical system states and structural configuration models read directly from highly readable YAML profiles (`config.yaml`, `hardware.yaml`, `config_lab.yaml`).
* **Cold Storage (System Logs):** Structured diagnostic traces are handled via a multi-sink Loguru wrapper that splits inputs into three distinct file outputs (`wanos.log`, `wanos_debug.log`, `wanos_automations.log`) using non-blocking background worker threads to keep disk execution from freezing the runtime loops.

### Option C Lifecycle Tracking
To trace exactly what version of the code is executing across your deployment pipelines without incurring constant SD-card wear, WanOS implements an intelligent runtime string builder pattern:
1. The semantic layout number (`version: "0.6"`) is managed manually at the absolute top of `config.yaml`.
2. When the application initializes `main.py`, it computes a standard, immutable system execution build stamp based on the process initiation date (`datetime.now().strftime("%Y%m%d%H%M")`).
3. These variables are saved in RAM inside the state engine as `version_major` and `version_full` and transmitted down the SSE line. If a hot-reload is triggered, the engine refreshes the semantic configuration file parameters but locks the original boot timestamp in place.

---

## 5. Connection Stability, Time Guards & Sweeper Restraints

### The Sliding WATCHDOG Guardian
The backend stream loop monitors client health every 0.5 seconds, suppressing heavy transmissions unless a true state mutation occurs. If the channel remains quiet for 5 seconds, it pipes a lightweight keep-alive heartbeat frame. The client-side Alpine engine runs a sliding 10-second timer watchdog. If a network cable drop or socket death disrupts the heartbeat, the watchdog triggers, displays a "NOT CONNECTED" blur screen, and attempts to re-link.

### The Absolute Uptime and Anti-NTP Jump Guard
To prevent your physical window shutters or light arrays from executing unexpected actions on startup due to network clock skew (e.g., when a reboot occurs and a local software utility like `fake-hwclock` temporarily shifts system time back an hour before an NTP server connects), the `StateManager` implements an **Absolute Uptime Guard**. 

During the initial 3 minutes (180 seconds) of the application's process life, all digital timers and environment calculator engines compile timeline boundaries in memory, but they are strictly blocked from broadcasting automated triggers to the hardware layer.

### The Catch-Up Sweeper Protection
The maintenance sweeper (`SYSTEM_SWEEP_REQUESTED`) performs an environmental health audit by analyzing your daily 6-point time-series profiles via the `EnvironmentScheduler`. To ensure a manual administrative click or an automatic reconnection sweep does not cause physical roller shutter movements across your rooms, the loop evaluates an explicit `is_passive_sweep` validation rule. If the sweep reason matches a network recovery or configuration hot-reload, the fan and climate parameters synchronize, but the physical blinds are bypassed.