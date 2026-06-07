# PHASE_2.md

================================================================================
WANOS PHASE 2: LAB MODE, LOGIC & UI (COMPLETED)
================================================================================

1. OVERVIEW
-----------
With Phase 1 handling the underlying event loop, data protection, and MQTT 
broadcasting, Phase 2 introduced the actual intelligence of Wanos. 

The goal of Phase 2 was to build the Hardware Abstraction Layer (HAL) and the 
core Business Logic (Sauna PID Controller). Crucially, this phase was built entirely 
in "Lab Mode." We mocked the physical sensors and built a reactive web UI so you 
can run, test, and debug the complete sauna heating logic on your local machine 
without needing to wire up real hardware.

PHASE 2 ROADMAP (COMPLETED)
* **Phase 2A:** Nested state models and the `sensors.py` Lab Mode mock loop.
* **Phase 2B (LEGACY INTEGRATION):** Implemented `logic/sauna_controller.py` 
  using async-friendly PID math, sequential rotating fire-order, and a 3-phase waterfall 
  distribution to balance load and prevent main breaker trips.
* **Phase 2C (UI REPLACEMENT):** Deferred physical `gpio_controller.py` to Phase 5. 
  Instead, built a real-time Native Web Dashboard to visualize the complex waterfall 
  math and control Lab Mode parameters.

2. CORE CONCEPTS
----------------
* **Hardware Abstraction Layer (HAL):**
  Business logic never knows about physical GPIO pins. The HAL acts as a translator. 
  The logic says "Heat at 50%," and the HAL figures out which physical pin to pulse.
* **Lab Mode:**
  A software toggle that replaces physical reads with simulated data (e.g., a slider 
  that injects mock temperatures into the event queue).
* **Decoupled Logic:**
  The `sauna_controller.py` module contains pure Python math. It does not format strings 
  or import hardware libraries. It simply listens to the state, calculates boundaries, 
  and dispatches pure numerical target states.

3. FILES BUILT IN PHASE 2
-------------------------
* `logic/sauna_controller.py`
  - The brain. Runs a background loop that evaluates `SystemState`.
  - Compares `current_temp` to `target_temp` using an anti-windup PID loop.
  - Calculates the required heating power and dispatches `MODULATION_UPDATED` events 
    containing both total PWM and the specific phase array `[U, V, W]`.

* `frontend/` (Native Web UI)
  - Built an HTML5/Tailwind/Alpine.js interface.
  - Connects to a Server-Sent Events (SSE) stream for zero-refresh state binding.
  - Uses `/api/event` POST commands to inject triggers (`SAUNA_ON`, `TEMP_UPDATED`).

* `hardware/gpio_controller.py` *(DEFERRED TO PHASE 5)*
  - The muscle. Will subscribe to the State Manager and physically toggle SSR pins.
  - Temporarily skipped to focus on UI and logic simulation.

4. UPDATES TO EXISTING FILES
----------------------------
* `core/models.py`:
  Expanded `SystemState` using the "Russian Doll" nesting strategy to include 
  `SaunaState` with variables like `active`, `modulation_pwm`, and `phases_pwm`.
* `core/state_manager.py`:
  Updated `_handle_event` to route new business logic events cleanly. Formats and prints 
  daily fire-orders strictly upon activation to prevent log flooding.
* `main.py`:
  Mounted FastAPI `StaticFiles` and created an async generator for the `/api/state/sse` stream.

5. HOW PHASE 2 WORKS (THE SIMULATED HEATING CYCLE)
--------------------------------------------------
1. **Start:** Uvicorn boots Wanos. The UI connects to `/api/state/sse`.
2. **Command:** You click the Sauna ON button. The UI sends a `SAUNA_ON` token. The Bouncer 
   logs the daily element priority (e.g., `V -> U -> W`).
3. **Lab Override:** You drag the yellow Lab Mode slider to 45°C. The UI posts `TEMP_UPDATED`.
4. **Logic:** `sauna_controller.py` evaluates the gap between 45°C and 85°C. It calculates 
   power needed, factors in the 3-phase element capacities (3.5kW, 3.5kW, 2.0kW), and 
   dispatches `MODULATION_UPDATED`.
5. **Feedback Loop:** The Bouncer updates the State Vault. The SSE stream instantly pushes the 
   JSON to the frontend.
6. **Visualization:** The Alpine.js engine catches the payload and animates the Master PWM 
   bar and individual U/V/W phase rails dynamically on your screen.