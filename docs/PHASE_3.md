# PHASE_3.md

================================================================================
WANOS PHASE 3: ENVIRONMENTAL STATE MACHINE & INTEGRATIONS
================================================================================

1. OVERVIEW
-----------
Phase 3 transforms WISC from a heater controller into a comprehensive Environmental 
State Machine and integrates it with the external smart home. The system now dictates 
auxiliary hardware (Hue lights, extraction ventilation, holding profiles) and enforces 
strict hardware safety interlocks (magnetic door sensors).

To guarantee precision and survive unexpected reboots, time is managed via 
"Absolute Time & Smart Sleeps." The Bouncer tracks exact Unix timestamps for deadlines. 
Dedicated async sleeper tasks wait silently in the background and fire expiration 
events into the queue exactly when needed, while the Alpine.js frontend handles all visual 
second-by-second ticking locally.

2. VAULT EXPANSION (`core/models.py`)
-------------------------------------
The Pydantic core models have been significantly expanded to track entire rooms.

**SystemState.sauna:**
* `current_humidity`: Optional[float] = None
* `door_open`: bool = False
* `hold_mode`: str = "autohold" (Cycles: autohold -> hold -> nohold)
* `session_start_time`: Optional[int] = None (Unix timestamp)
* `session_end_time`: Optional[int] = None (Unix timestamp)
* `light_color`: str = "#FFD180"
* `lcd_text`: str = ""
* `ventilation_state`: str = "OFF" (States: OFF, WAITING, RUNNING)
* `ventilation_deadline`: Optional[int] = None

**SystemState.environment:**
* `door_bathroom_open`: bool = False (Hardware magnetic interlock)
* `cinema_hue_on`: bool = False (Tracked lighting state)

3. CONFIGURATION OVERHAUL (`hardware.yaml` & `config.yaml`)
-----------------------------------------------------------
Configuration has been split to enforce strict layering and "zero magic numbers":
* **`hardware.yaml`**: Static physical network mapping. Defines dual MQTT broker addresses (WanOS local vs. Domoticz hub), explicitly maps `idx` virtual devices, and assigns Raspberry Pi GPIO pins.
* **`config.yaml`**: Runtime parameters (e.g., `default_timer`, `vent_delay_mins`, default PID values).

4. NEW EVENT TOKENS
-------------------
* `HUMIDITY_UPDATED` (Lab mode slider or hardware sensor)
* `DOOR_CHANGED` (Lab mode toggle or physical interlock. Payload: `sensor_id`, `is_open`)
* `HOLD_TOGGLED` (UI button click)
* `TIMER_ADJUSTED` (UI +10/-10 mins button click)
* `SAUNA_TIMER_EXPIRED` (Fired by the sleep task when session ends)
* `VENT_WAIT_EXPIRED` (Fired when 10m vent delay finishes)
* `VENT_RUN_EXPIRED` (Fired when 160m vent runtime finishes)

5. NEW & UPDATED MODULES
------------------------
* **`integrations/home_hub.py` (The Bilingual Translator):**
  A bi-directional bridge binding WanOS to Domoticz. Evaluates inbound flat `idx` streams from a dedicated remote MQTT client and dispatches nested Engine Events. Synchronizes local automated hardware (Bathroom Vent) outbound to Domoticz.
* **`core/mqtt_client.py` (Async Streams Upgrade):**
  Rebuilt around `aiomqtt` to support robust background `.subscribe()` listening tasks and automatic connection recovery.
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
  A new business logic module handling dynamic Color Math, LCD strings, and Ventilation timelines.

6. FRONTEND UPGRADES (LAB MODE & ALPINE.JS)
-------------------------------------------
* **Alpine.js Pivot:** The frontend was entirely rewritten using Alpine.js and Tailwind CSS (DaisyUI) to enforce a simpler, build-free deployment pipeline.
* **Modular CSS Grid Dashboard:** Separated into distinct command panels (Sauna, IR, Cinema, Bathroom, Energy, Lab Simulation).
* **Dual-Display Timer:** A local Javascript `setInterval` loop evaluates absolute Unix timestamps to calculate smooth digital readout tickers and progress bars without saturating the SSE network.
* **Door Interlock Failsafes:** Virtual magnetic switches in Lab Mode instantly disable "Start Sauna" functionality and drop heating elements.



================================================================================
WANOS PHASE 3b: Some refinements
================================================================================

## Objective
Refine the core architecture by decoupling state rendering, optimizing internal communications via an Observer pattern, and protecting network layers from echo loops and event flooding.

---

### Phase 3B.1: Display Logic Consolidation
**Goal:** Establish a Single Source of Truth for all aesthetic and peripheral rendering logic.
* **Action A:** Extract the `_update_lcd_text` logic currently residing in `core/state_manager.py`.
* **Action B:** Inject this "smart" logic into the `EVALUATE LCD TEXT` block within `logic/auxiliary_controller.py`, ensuring it handles temperature displays, hold modes, and ventilation states.
* **Action C:** Delete `_update_lcd_text` from the `StateManager`. Replace its usage at the bottom of `_process_events` with a direct call to `AuxiliaryController.evaluate(self._state.sauna)`.

### Phase 3B.2: Bridge Observer & Echo Prevention
**Goal:** Transition the Domoticz integration from a continuous polling model to a reactive push model, while preventing infinite MQTT feedback loops.
* **Action A:** Add a simple callback registry list to the `StateManager`. Execute these callbacks at the end of `_process_events` if `pending_broadcast` is True.
* **Action B:** Modify `DomoticzHomeHubBridge.start()` to register a listener callback with the `StateManager`.
* **Action C:** Delete `_outbound_monitor_loop` entirely. Move the outbound MQTT publishing logic inside the newly registered listener function.
* **Action D (Circuit Breaker):** Modify the `_parse_domoticz_inbound` method. When an external change is received (e.g., Bathroom Vent ON), the bridge must explicitly update its internal `_last_known_bathroom_vent_state` *before* dispatching the `HUB_STATE_CHANGED` event to the core. This ensures the outbound listener will abort the subsequent echo broadcast.

### Phase 3B.3: Frontend Event Throttling
**Goal:** Improve slider responsiveness in Lab Mode without overwhelming the backend API queue.
* **Action A:** In `frontend/index.html`, locate all Lab Mode `<input type="range">` elements.
* **Action B:** Replace the `@change` directives with `@input.debounce.250ms`.
* **Action C:** Verify that the UI bindings (`x-model` or `:value`) update smoothly during the drag interaction, while the network payload is throttled.