================================================================================
WANOS PHASE 2: LAB MODE & HARDWARE ABSTRACTION
================================================================================

1. OVERVIEW
-----------
With Phase 1 handling the underlying event loop, data protection, and MQTT 
broadcasting, Phase 2 introduces the actual intelligence of Wanos. 

The goal of Phase 2 is to build the Hardware Abstraction Layer (HAL) and the 
core Business Logic (Sauna PID Controller). Crucially, this phase is built entirely 
in "Lab Mode." This means we will mock the physical sensors and GPIO pins so you 
can run, test, and debug the complete sauna heating logic on your local machine 
without needing to wire up real hardware.

PHASE 2 ROADMAP
* **Phase 2A (Current):** Nested state models and the `sensors.py` Lab Mode mock loop.
* **Phase 2B (REMINDER - LEGACY INTEGRATION):** Implement `logic/sauna_controller.py` 
  and `hardware/gpio_controller.py`. 
  *CRITICAL REQUISITES:* 1. Review and port the legacy PID logic.
  2. Implement sequential fire-order logic for the 3 distinct heater elements to 
     balance load and prevent main breaker trips.

2. CORE CONCEPTS
----------------
* **Hardware Abstraction Layer (HAL):**
  Business logic should never know about 
  physical GPIO pins. The HAL acts as a translator. The logic says "Heat at 50%," 
  and the HAL figures out which physical pin to pulse.
* **Lab Mode:**
  A software toggle that replaces physical I2C/GPIO reads with 
  simulated data (e.g., a fake temperature probe that slowly warms up when the 
  fake heater is on).
* **Decoupled Logic:**
  The `sauna_controller.py` module will contain pure Python 
  math. It will not import any hardware libraries. It simply listens to the 
  state, does the math, and dispatches new target states.

3. FILES TO BUILD IN PHASE 2
----------------------------
Below are the files we will flesh out during this phase:

* `hardware/sensors.py`
  - Runs a background `asyncio` task.
  - In Lab Mode: Generates dummy temperature data that simulates a heating curve 
    and dispatches `TEMP_UPDATED` events to the queue.
  - In Live Mode (Phase 5): Will read actual I2C/1-Wire sensors.

* `logic/sauna_controller.py`
  - The brain. Runs a background loop that monitors `SystemState`.
  - Compares `current_temp` to `target_temp`.
  - Calculates the required heating power (PID math) and dispatches 
    `MODULATION_UPDATED` events (e.g., "Set heater PWM to 75%").

* `hardware/gpio_controller.py`
  - The muscle. Subscribes to the State Manager.
  - When it sees the modulation state change to 75%, it physically toggles 
    the Solid State Relay (SSR) pins.
  - In Lab Mode: Simply prints "💡 [MOCK GPIO] SSR toggled to 75%" to the console.
  - Enforces the `hardware_live_mode` safety lock.

4. UPDATES TO EXISTING FILES
----------------------------
* `core/models.py`:
  Expand `SystemState` using the "Russian Doll" nesting strategy 
  to include `SaunaState` and `HardwareState`.
* `core/state_manager.py`:
  Update `_handle_event` to route the new business logic events correctly.
* `main.py`:
  Import and start the new background tasks (`sensors.py`, 
  `sauna_controller.py`, `gpio_controller.py`) inside the FastAPI lifespan block.

5. HOW PHASE 2 WORKS (THE SIMULATED HEATING CYCLE)
--------------------------------------------------
Once Phase 2 is complete, here is the lifecycle you will observe running locally 
on your screen:

1. **Start:** You boot Wanos. `sensors.py` starts sending a mock temperature of 
   20.0°C every 2 seconds via `TEMP_UPDATED` events.
2. **Command:** You send an API request (or an MQTT message) to turn the sauna ON 
   with a target of 85.0°C.
3. **Logic:** `sauna_controller.py` sees the massive difference between 20°C and 
   85°C. It calculates 100% power is needed and dispatches `MODULATION_UPDATED` 
   with a payload of 100.
4. **Action:** `gpio_controller.py` sees the new modulation state. In Lab Mode, 
   it prints "🔥 SSR PIN 17 HIGH (100%)" to your terminal.
5. **Feedback Loop:** `sensors.py` sees the heater is at 100%, so it artificially 
   starts increasing the mock temperature (20.5, 21.0, 21.5...).
6. **Modulation:** As the mock temperature approaches 85°C, `sauna_controller.py` 
   calculates a lower power requirement, dropping the modulation to 50%, then 20%. 
   `gpio_controller.py` mimics this by pulsing the simulated pins.
================================================================================