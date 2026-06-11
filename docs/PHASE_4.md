# PHASE_4.md

================================================================================
WANOS PHASE 4: ADMINISTRATIVE TELEMETRY, NETWORKING & PERFORMANCE TUNE
================================================================================

## 1. Overview
Phase 4 transitions WanOS from an operational state machine into a silent, production-grade automation engine. This cycle focused heavily on extreme network optimization, memory management, and robust link watchdogs to prepare the software stack for physical deployment on the Raspberry Pi host node.

By migrating time-tracking ticks to the client side, stripping out rolling RAM log buffers, and enforcing a strict Single Source of Truth for peripherals, background network traffic has been cut to near-zero during idle stretches. Simultaneously, an application-level sliding watchdog enforces recovery frameworks to protect the interface against silent "dirty drops" on local Wi-Fi networks.

---

## 2. Vault Alignment & Unified Devices Dict (`core/models.py`)
To prevent data duplication and protect the structural integrity of the reactive state tree, all boolean switch attributes were completely purged from the `environment` subtree. Peripheral fixtures are now managed exclusively via a centralized catch-all map.

* **SystemAdminState (Expanded Telemetry Anchors):**
  * `os_boot_unix`: Optional[int] = None (Static Unix epoch representing OS start time)
  * `app_boot_unix`: Optional[int] = None (Static Unix epoch representing Python engine launch time)
* **EnvironmentState (Cleaned Framework):**
  * Purged `cinema_hue_on`, `sauna_hue_on`, `bathroom_vent_on`, and `sauna_extraction_vent_on` to eliminate dead references. Native safety sensors (such as `door_bathroom_open`) remain inside this core model.
* **SystemState.devices (Catch-All Dictionary):**
  * Acts as the unified storage map for all external binary components (`sauna_hue`, `cinema_hue`, `bathroom_ventilator`, `sauna_extrvent`, `safety_ssr`). States are managed purely as strings (`"ON"` / `"OFF"`).

---

## 3. Web Pipeline Optimization (The Network Silence Shift)
In legacy profiles, the backend event loop computed pre-formatted string indicators every 2 seconds, triggering a cascade of redundant Server-Sent Events (SSE) updates that saturated connections even when the ecosystem was completely idle. 

### The Client-Side Ticker Engine
* **The Backend Role:** Looks up static start thresholds via `psutil.boot_time()` and `time.time()` once on class instantiation, commits them to the schema tree, and goes completely silent.
* **The Frontend Role:** The browser pulls these static timestamps down once during the initial `fetchFullSnapshot()` handshake. The local Alpine script updates visual clocks inside a client-side 1-second interval task loop using a dedicated `formatExtendedUptime` utility.
* **The Result:** The web streaming channel (`/api/state/sse`) remains quiet unless an actual physical temperature, sensor, or relay transition occurs.

---

## 4. Production Watchdogs & Keep-Alive Handshakes
To handle silent hardware disconnects (e.g., pulling a network cable or losing Wi-Fi), an industrial watchdog framework was built directly into the web transport pipeline.

```text
  [ FastAPI Backend ]                                   [ Alpine.js Frontend ]
           |                                                      |
           |---- Data Snapshot or 5s Ping ({"domain":"ping"}) --->| --> Reset 10s Timer
           |                                                      |
     *Cable Pulled* |
           X                                                      |
           |                      [ 10s Watchdog Expiry ] --------+ --> Clear Tasks
           |                                                      |     Lock UI Modal
           |<--- Loop API Reconnect Attempts every 3 seconds -----|
```

* **Backend Idle Ping (5s):** In `main.py`, the `event_generator` tracks idle gaps. If no metric updates are sent for 5 seconds, it automatically pipes a lightweight `{"domain": "ping", "data": {}}` JSON frame down the pipe.
* **Frontend Watchdog Guardian (10s):** In `app.js`, any incoming frame (real data or ping) intercepts a sliding window handler, which instantly clears and schedules a 10-second timeout task. If the channel goes quiet for 10 seconds (2x the backend ping cadence), the watchdog triggers a timeout, forces the `eventSource` to close, and throws the UI behind the blurred safety interface.

---

## 5. Storage & Memory Overhead Removal (`core/logger.py`)
To eliminate arbitrary RAM consumption and maximize the lifespan of the host SD card, the rolling in-memory web console panel was completely decommissioned.

* **Logger Strip Down:** Removed the `history` collections `deque` object from the initialization step of `WanosLogger`. Logs are now piped straight to disk file locations (`/var/log/wisc/wanos.log`) via Loguru or broadcasted raw over MQTT.
* **Endpoint Deletion:** The route `@app.get("/api/console")` was completely removed from `main.py`.
* **Interface Cleanup:** Removed the sticky left-hand logging panel container from `index.html`, allowing the main application dashboards to expand to 100% full screen width.

---

## 6. Centralized Console Telemetry (`monitor.py`)
The split-screen terminal tool (`monitor.py`) was updated to align with the revised top-level logging namespace.

* **Subscription Routing Fix:** Shifted the background client subscription path from the legacy target topic over to the correct `wanos/console/#` wildcard wildcard hook.
* **Dual-Channel Split:** The terminal seamlessly segregates system data into standard operational execution logs (`wanos/console/status`) and developmental diagnostic logging chatter (`wanos/console/debug`).

---

## 7. New Event Tokens & Interface Extensions
* **`SYSTEM_METRICS_UPDATED` (Pruned Optimization):** Now acts strictly as a network connectivity gateway, tracking local broker state and IP addresses. Pushes outbound system state deltas *only* if network links or IP targets experience a real change.
* **`formatExtendedUptime(bootUnix, now)`:** Advanced client-side parser calculating zero-padded long duration components (`dd:HH:MM:ss`) coupled with local calendar translations `(YYYY-MM-DD HH:mm:ss)`.
* **`reloadFrontend()`:** Administrative hard-reload hook bypass cache buffers to force a complete browser reload (`window.location.reload(true)`).
```