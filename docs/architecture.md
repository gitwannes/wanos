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
* **The Presentation Interface:** Powered by **Alpine.js**. Paired with **TailwindCSS** and **DaisyUI**, it allows for instant reactive UI updates and theme matching without relying on intensive, long-compile node build bundles. The interface utilizes `localStorage` to persist dynamic UX layouts (like the Lab Control panels) and JWT Session roles independently of the backend.
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
Heavy, non-blocking operational tasks are extracted into dedicated service classes under the `logic/` directory, supported by specific memory managers in the `core/` directory:
* **The Health Monitor:** Pings sockets and external bridges continuously, dispatching Auto-Kill commands if hardware is dropped.
* **The Environment Scheduler:** Performs mathematical bounds clamping for sun cycles.
* **The NVRAM Manager:** Operates an isolated disk I/O class executing atomic file swaps for cumulative hardware meters.

### The NVM Buffer-and-Flush Architecture (Atomic Swaps)
To protect the Raspberry Pi's physical SD card from wear-leveling death caused by high-frequency water and power pulses, WanOS actively bypasses `log2ram`. 
1. The engine buffers incoming meter pulses in high-speed RAM. 
2. A recurring 5-minute `NVRAM_FLUSH_TRIGGER` heartbeat analyzes the memory. 
3. If the math has changed, it writes to a temporary file (`wanos-nvram.json.tmp`) and executes a native `os.replace` to atomically swap it. This mathematically guarantees data cannot be corrupted if the Pi loses power mid-write.

### Client-Side State Memory & Route Bouncing
The backend serves raw HTML assets openly, relying on JWT verification only for API endpoint hits. To prevent broken views when a smartphone auto-completes to a previously visited URL (e.g., `/admin.html`), the `app.js` initialization loop acts as a Role-Based Bouncer. It inspects the JWT stored in the browser's `localStorage` and forcibly redirects unauthorized users to their correct layout scope before rendering the DOM.

### Noisy Metric Smoothing (Rolling Average Buffers)
To combat network pollution caused by highly erratic device telemetry (such as high-frequency electrical plug updates), the system uses a **RAM Moving Average Array**. Incoming telemetry metrics (like raw computer power draw) are collected into a rolling window. The backend processes a smoothed aggregate value and suppresses downstream SSE updates unless the final rounded value shifts, preventing UI flashing.

### Logic-to-Hardware Decoupling (The Boundary Rule)
Core software algorithms have no direct awareness of physical circuit links. They calculate target metrics and update state models. Outbound actions are separated into clean directory paths: `hardware/` modules manage local GPIO lines (relays and local SHT11 probes), while `integrations/` handle the networking protocols for external platforms.

### Boot Storm Protector (The First-Sync Tracking Set)
When the system boots, hardware integrations dump their current states into the event queue (The "Boot Storm"). To prevent automation rules from misfiring during this chaos, WanOS decouples boot logic from raw RAM values. 
The engine maintains a definitive **First-Sync Tracking Set** (`_initialized_idxs`). When an event arrives, the engine queries the set. If the IDX is missing, it is flagged as `is_initialization` to block automations and then added to the ledger, allowing the UI to safely pre-seed default values without triggering ghost actions.

---

## 4. Life-Cycle Telemetry, Version Tracking & Security

### Hot/Warm/Cold/Persistent Data Lifecycles
System operations use an tiered storage structure based on performance demands:
* **Hot Storage (RAM):** The active event queue and moving average history windows process inputs at microsecond speeds.
* **Warm Storage (Local Filesystem):** Critical system states and structural configuration models read directly from highly readable YAML profiles (`config.yaml`, `hardware.yaml`, `config_lab.yaml`).
* **Persistent State (NVRAM):** Cumulative, irreversible home metrics (Liters, kWh) are saved via explicit Atomic Swaps to the root directory to survive hard power cuts.
* **Cold Storage (System Logs):** Structured diagnostic traces are handled via a multi-sink Loguru wrapper that splits inputs into distinct file outputs using non-blocking background worker threads to keep disk execution from freezing the runtime loops.

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


## 6. Sauna Safety Subsystems

To prevent catastrophic component failure, fire hazards, or code violations, the sauna infrastructure operates under a multi-layered, zero-trust safety framework distributed across event-driven verification logic and out-of-band background guardians:

### 1. The Dynamic Start Gate Interceptor
The engine blocks any active heating ignition intent (`SAUNA_ON`) if any physical criteria are unfulfilled before routing commands to the PID controller. The session is rejected and dispatches critical alert flags to the user interface if:
* The 5V Master Safety Relay (IDX `71036`) is unpowered or reporting an `OFF` state.
* The physical local Raspberry Pi GPIO output bus driver state is marked as disabled.
* The composite temperature calculation is uninitialized or missing active telemetry entries.
* The magnetic frame safety door contact sensor (IDX `10001`) detects an unsealed, `OPEN` condition.

### 2. Dual-Probe Volumetric Atmosphere Validation
To capture accurate thermal mass dynamics across the high vertical gradient of the cabin, WanOS relies on a split dual-sensor topology. The calculation implements a strict mathematical rule:
$$\text{Sauna Calc Temp} = (\text{Probe}_{20001} \times 0.7) + (\text{Probe}_{20002} \times 0.3)$$
* **Strict Fail-Fast Condition**: If *either* the high sensor (IDX `20001`) or the low sensor (IDX `20002`) encounters an hardware error, reports a null state, or fails a Pydantic structure filter, the engine instantly voids the entire composite variable. 
* **Core Failsafe Execution**: The moment `sauna_calc_temp` resolves to `None` while the heaters are running, the system fires an event-driven emergency cutoff command to kill all active relay modulation blocks.

### 3. Absolute Cumulative Runtime Limit (EN 60335-2-53 Compliant)
While user-comfort countdown timers delay activation until the room reaches operating thresholds, compliance standards strictly forbid infinite heating if structural factors block thermal rise. The moment `SAUNA_ON` passes validation, an un-bypassable epoch wall is stamped into RAM:
$$\text{Absolute Cutoff} = \text{TimeNow} + (6 \times 3600)$$
This limit runs continuously from the second of activation and executes an immediate hard kill command exactly 6 hours later, completely independent of cabin metrics.

### 4. Out-of-Band Data Link Staleness Watchdog
If the low-level physical I/O threads hook or freeze due to electrical noise, values in the system registry can lock onto their last valid numbers, blinding the event-gated emergency cuts. 
To mitigate this, the isolated `HealthMonitor` task loop monitors data age out-of-band every 2 seconds. Every incoming packet from the SHT11 probes refreshes `last_heartbeat_unix` even if the temperature digits stay flat. If the sauna is active and this timestamp ages past 10 seconds, the monitor steps in, bypasses the main event queue, kills the heater relays, and logs a critical emergency system alarm.

Core State Sandbox ]                        [ Out-of-Band Guard ]
  (StateManager)                                (HealthMonitor Loop)
        │                                                │
        ├──> Sets absolute_cutoff = now + 6 * 3600       │ Every 2s:
        │                                                ├─> Is cutoff exceeded?
        └──> Refreshes last_sensor_heartbeat ───> ───────┼─> Is heartbeat > 10s old?
                                                         │       │
                                                         ▼       ▼
                                                  [ Hard Emergency Shutdown ]

### 5. Magnetic Door Interlock State Machine
* **Grace Period Countdown**: If an occupant opens the sauna door while heating is live, the state manager schedules a 30-second `sauna_door_grace` timer. If the door closes before expiration, the countdown cancels with zero impact on system operations.
* **Safety Pause Override**: If the grace window expires with the door left open, the engine switches into an automated `PAUSE` state, completely cutting element modulation.
* **SCADA Visual Annunciator**: Upon transition to a safety pause, the core overrides the ambient room lights (IDXs `51002`, `51004`, `51005`) and forces a vibrant SCADA Green color payload ($[x: 0.1700, y: 0.7000]$) down the Zigbee mesh to visually notify occupants that the thermal space is unsealed.

### 6. Cascade Circuit Breaker Protection
Hardware loops are linked via strict programmatic dependencies. If the physical 5V master safety loop relay drops due to an unexpected hardware shutdown or manual override tap, an internal interceptor instantly triggers inside the state manager:
```python
if event_name == "HUB_STATE_CHANGED" and p_idx == 71036 and payload.get("state") != "ON":
    # Cascades emergency output disarm
```
This forces a clean software fallback shutdown, locking out sauna GPIO output commands until the core infrastructure resets.

### 7. Zero-State Hardware Sanitization Pass (Cold Boot Guard)
To eliminate the threat of a "Split-Brain" ghost runtime—where physical relays remain hardware-latched `ON` after an unexpected application crash while new software memory registers default to a dormant `OFF` state—the system mandates a hardware-level sanitization phase at boot.
Before the software registers any listener hooks to the core asynchronous event bus, the underlying actuator controller claims exclusive control of the physical kernel GPIO chip handles. It immediately invokes a hardware flush that forcefully clamps all solid-state relay (SSR) phase lines ($U, V, W$) and the single-phase IR channel to a 0% PWM duty cycle, drives their digital pins to a flat 0V (`LOW`) state, and drops the primary physical safety contactor relay.
Furthermore, because the backend Pydantic definitions default the output bus armed state (`gpio_output_enabled`) to `False` on launch, the hardware layer will drop and ignore any incoming network tracking states until an administrator consciously inputs a valid session PIN to re-verify and authorize the physical environment.
