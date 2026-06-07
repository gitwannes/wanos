# PHASE_3.md

================================================================================
WANOS PHASE 3: ENVIRONMENTAL STATE MACHINE & ABSOLUTE TIMERS
================================================================================

1. OVERVIEW
-----------
Phase 3 transforms WISC from a heater controller into a comprehensive Environmental 
State Machine. The system will now dictate auxiliary hardware (Hue lights, extraction 
ventilation, holding profiles) and enforce strict hardware safety interlocks.

To guarantee precision and survive unexpected reboots, time is managed via 
"Absolute Time & Smart Sleeps." The Bouncer tracks exact Unix timestamps for deadlines. 
Dedicated async sleeper tasks wait silently in the background and fire expiration 
events into the queue exactly when needed, while the frontend handles all visual 
second-by-second ticking locally.

2. VAULT EXPANSION (`core/models.py`)
-------------------------------------
The `SystemState.sauna` model will be expanded to track the entire room:
* `current_humidity`: Optional[float] = None
* `door_open`: bool = False
* `hold_mode`: str = "autohold" (Cycles: autohold -> hold -> nohold)
* `session_start_time`: Optional[int] = None (Unix timestamp)
* `session_end_time`: Optional[int] = None (Unix timestamp)
* `light_color`: str = "#FFD180" (Simulated Hue color, defaults to Warm White)
* `lcd_text`: str = "" (String to push to the physical/virtual screen)
* `ventilation_state`: str = "OFF" (States: OFF, WAITING, RUNNING)
* `ventilation_deadline`: Optional[int] = None (Unix timestamp for next vent stage)

3. CONFIGURATION UPDATES (`config.yaml`)
----------------------------------------
Move hardcoded constants into the global configuration:
* `session`:
  - `default_timer: 180`
* `ventilation`:
  - `delay_mins: 10`
  - `run_mins: 160`

4. NEW EVENT TOKENS
-------------------
* `HUMIDITY_UPDATED` (Lab mode slider or hardware sensor)
* `DOOR_CHANGED` (Lab mode toggle or hardware switch)
* `HOLD_TOGGLED` (UI button click)
* `TIMER_ADJUSTED` (UI +10/-10 mins button click)
* `SAUNA_TIMER_EXPIRED` (Fired by the sleep task when session ends)
* `VENT_WAIT_EXPIRED` (Fired when 10m vent delay finishes)
* `VENT_RUN_EXPIRED` (Fired when 160m vent runtime finishes)

5. NEW & UPDATED MODULES
------------------------
* **`logic/timers.py` (The Smart Sleepers):**
  A utility module that spawns cancellable `asyncio.Task` wrappers. When given a 
  deadline, it sleeps (`await asyncio.sleep(deadline - now)`), then posts an 
  expiration event (`SAUNA_TIMER_EXPIRED`) to the State Manager queue. If a timer 
  is adjusted, the active sleep task is cancelled and a new one is spawned.

* **`logic/sauna_controller.py` (The Heater Brain Updates):**
  Updated to intercept `door_open == True` OR `hold_mode == 'hold'`. If either is true, 
  the PID is bypassed and it instantly returns `[0, 0, 0]` modulation. Once `door_open` 
  returns to `False`, the loop resumes calculating normally (Instant Resume).

* **`logic/auxiliary_controller.py` (The Environment Brain):**
  A new business logic module evaluated by the State Manager.
  - **Color Math:** Evaluates temperature and state to return hex colors.
  - **LCD Math:** Formats the LCD screen strings based on state and timestamps.
  - **Ventilation Math:** Sets deadlines for the `WAITING` and `RUNNING` stages.

6. FRONTEND UPGRADES (LAB MODE)
-------------------------------
* **Door Interlock:** "Start Sauna" button disabled if the door is open. 
* **Virtual Hue Bulb & LCD:** Live UI elements reflecting the calculated states.
* **Dual-Display Timer:** A local Javascript `setInterval` loop compares the browser's 
  time to `session_start_time` and `session_end_time` to render:
  1. Smooth digital text readouts (`Elapsed: 00:15:30`, `Remaining: 02:44:30`).
  2. A visual progress bar filling from 0% to 100%.
* **Timer Adjustments:** [+10 Mins] and [-10 Mins] buttons that POST `TIMER_ADJUSTED` commands.