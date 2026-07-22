# WanOS Admin: Force "ALL OFF" Synchronization Sweep (Spec)

## 1. Core Philosophy & Problem Statement
Due to the simplex nature of RF hardware (RFX) and the mesh fragility of Z-Wave, WanOS can experience "State Desynchronization"—where the software database reports a device as "OFF", but the physical hardware remains "ON". 

The **Admin Force Sweep** acts as a reconciliation tool. It intentionally bypasses idempotency checks (skipping the "is it already off?" filter) and blindly transmits physical "OFF" commands to the network to force physical reality to match the software state.

## 2. Execution Architecture: Parallel Spawning + Sequential Pacing
To prevent network flooding while minimizing total execution time, the system will utilize asynchronous parallel queues.

*   **Integration Isolation (Parallel):** When the global command is triggered, WanOS will spawn independent, non-blocking asynchronous tasks for each target integration (e.g., Task A for Z-Wave, Task B for RFX, Task C for Onkyo).
*   **Internal Queuing (Sequential):** Inside each integration's task, the execution loop will iterate through its assigned devices sequentially. 
*   **The 300ms Pacing:** After transmitting an "OFF" payload, the loop will explicitly suspend itself (`await asyncio.sleep(0.3)`) before addressing the next device in the integration list.

## 3. The Exclusion Filter (Safety Guardrails)
A blind sweep is highly dangerous if it targets critical infrastructure (e.g., the router powering the network, the Pi's own power supply, or a safety-critical 24V relay). 

*   **Metadata Tagging:** The system must respect an explicit exclusion tag (e.g., `ignore_global_off: true` or `admin_sweep_exclude: true`) located in the device's configuration YAML or database entry.
*   **Hardcoded Integration Bypasses:** Some integrations (like system monitoring endpoints or read-only weather sensors) must be completely skipped by the sweep generator to prevent unnecessary logic processing.

## 4. Trigger & Payload Flow
1.  **The Trigger:** The Kiosk UI or Admin Dashboard fires a unique event (e.g., `ADMIN_FORCE_SWEEP`).
2.  **The Aggregator:** A dedicated handler intercepts this event. It scans the `SystemState` for all controllable devices, groups them by their parent `integration_id`, and strips out any device carrying the exclusion tag.
3.  **The Dispatch:** The handler passes these filtered lists to the respective integration controllers, commanding them to execute their specific "OFF" sequence using the 300ms paced loop.

## 5. UI/UX Feedback Requirements
Because a system with 60 Z-Wave devices pacing at 300ms will take roughly 18 seconds to complete its sweep, the UI must inform the admin of the ongoing process.

*   **Action Confirmation:** The button should require a deliberate action (e.g., a long-press or a confirmation modal) to prevent accidental triggering.
*   **Execution Toast:** Upon triggering, display a non-blocking UI alert: *"Force Sweep Initiated: Transmitting sync commands to all integrations..."*
*   **Completion Toast:** Once all asynchronous queues yield, dispatch a success event to the frontend: *"Force Sweep Complete."*

## 6. Success Metrics & Validation
This feature is considered successfully implemented when:
*   An RFX packet sniffer shows clean, spaced transmissions without overlap.
*   The Z-Wave JS UI logs show linear command execution without "Dropped Message" or "Queue Full" warnings.
*   Critical devices (tagged for exclusion) remain unaffected during the sweep.

---

## 7. Implementation: File Modification Blueprint

To implement this dispatcher safely without congesting your core state manager, the logic will be distributed across the following layers:

### The Data & Configuration Layer
*   **`config.yaml` / Device Database:** You must add a boolean flag (e.g., `ignore_global_off: true`) to the metadata of critical infrastructure devices (router plugs, Raspberry Pi power relays, sauna controllers).
*   **`core/models.py`:** Add the new event type (e.g., `ADMIN_FORCE_SWEEP`) to your core `EventType` enumerator to allow the routing engine to recognize the command.

### The Aggregation & Dispatch Layer
*   **`core/event_handlers/admin_handlers.py` (NEW or Existing):** Create a dedicated handler function to intercept the `ADMIN_FORCE_SWEEP` event. 
    *   This function will read `SystemState.devices`, filter out read-only sensors and excluded devices, and group the remaining IDXs by integration.
    *   It will utilize `asyncio.create_task()` to spawn parallel execution queues for Z-Wave, RFX, Onkyo, etc., preventing the main thread from blocking.

### The Execution Layer
*   **`integrations/zwave.py`, `integrations/rfxcom.py`, etc.:** (Or within the `admin_handlers.py` dispatcher itself). The logic iterating over the filtered device lists must be updated to include `await asyncio.sleep(0.3)` immediately after executing the "OFF" transmission to guarantee the hardware buffers have time to clear.

### The Frontend (Kiosk/Dashboard) Layer
*   **`frontend/kiosk.html` & `frontend/app.js` (or equivalent Vue/JS files):** 
    *   Add the "Force Sync All OFF" admin button.
    *   Implement a confirmation modal (e.g., "Are you sure you want to sweep all integrations?").
    *   Add toast notifications that listen for the backend dispatch and completion events to give the user visual feedback during the ~10-20 second execution window.