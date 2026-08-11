# WanOS Sauna and Infrared (IR) Architecture, Safety, & Analytics Reference

This document serves as the master specification for the physical topography, operational lifecycle, safety interlocks, thermodynamic equations, and analytics pipelines governing the Sauna and Infrared (IR) heating systems within WanOS.

**Related:** Long-term utility and session **history** (power/water time-series tiers, retention, Sensor History UI, gap policy, and session field `temp_outside_start`) is specified in [sensor_history.md](sensor_history.md). This document remains authoritative for live sauna/IR safety, leak filtering, RLS extraction, and the core session schemas. Sauna ON/OFF and IR ON/OFF are **system catalog events (SE)** with hardcoded handlers; fire-action allowlist + Library (**UE/UR/SE/SR/D**) rules: [`env-schedule-and-system-events.md`](env-schedule-and-system-events.md) and [`todo/phaseB-blocky.md`](todo/phaseB-blocky.md) § B10E. **Assess** whether device actions can move to rules: [`todo/phaseB-blocky.md`](todo/phaseB-blocky.md) § **B17** (assess only). **Future:** clamp soft `session_end_time` to `absolute_cutoff_unix` (start+6h wall) on arm/adjust → § **B18**.

---

## 1. System Topography & Hardware Infrastructure

The sauna and infrared heating infrastructure operates on a high-power, multi-phase electrical topology managed through direct microsecond GPIO actuation and localized protocol bridges.

### 1.1 Electrical Phase Layout & Element Capacities
The sauna heating system operates on a balanced 3x400V+N star configuration where every independent resistor phase draws load across a dedicated line conductor and Neutral, operating at a 230V nominal AC rating.
* **Phase U (Heater Element 1):** Nominal 3500 Watts capacity.
* **Phase V (Heater Element 2):** Nominal 3500 Watts capacity.
* **Phase W (Heater Element 3):** Nominal 2000 Watts capacity.
* **Infrared (IR) Array:** Single-phase pulse-width modulated (PWM) heater zone operating independently or in combined mode.

### 1.2 Measurement Infrastructure & System Asset Identifiers (IDXs)
* **Real-Time Energy Tracking (Pulse Meter):** Physically wired to GPIO Input Pin 12 and mapped as Virtual Identifier (IDX) `11001`. Operates at a resolution of 1000 pulses per kWh (exactly 1.0 Watt-hour per pulse tick).
* **Mains Voltage Monitoring:** Ingests live AC voltage telemetry from Z-Wave Node 50 (Endpoint 0, Value ID `66561`), mapped as Virtual Identifier (IDX) `71046`. Acts as a real-time line voltage proxy across the house bus structure.
* **Master Safety Relays:** 
  * 5V Master Safety Relay: Virtual Identifier (IDX) `71036`.
  * 12V Safety Relay: Virtual Identifier (IDX) `71040`.
* **Magnetic Door Contact Interlock:** Physical frame contact sensor mapped as Virtual Identifier (IDX) `10001`.
* **Volumetric SHT11 Climate Sensors:**
  * High Cabin Temperature Probe: Virtual Identifier (IDX) `20001`.
  * Low Cabin Temperature Probe: Virtual Identifier (IDX) `20002`.
  * High Cabin Humidity Probe: Virtual Identifier (IDX) `20004`.
  * Sauna composite (Explorer / history): Virtual Identifier (IDX) `20101` (`sauna temp` = 0.7×20001 + 0.3×20002; hum from 20001).

---

## 2. Start Preconditions & Operational State Machine

To prevent hazardous activation, the WanOS `StateManager` enforces a strict multi-point verification checklist before ignition commands are dispatched to the solid-state relays (SSRs).

### 2.1 Dynamic Start Gate Interceptor (`SAUNA_ON`)
When a user or automated timer dispatches a `SAUNA_ON` event payload to `/api/event`, the system verifies five mandatory hardware criteria:
1. **Master Relay Power:** The 5V Master Safety Relay (IDX `71036`) must report an active `ON` state.
2. **Hardware Bus Arming:** The physical local Raspberry Pi GPIO output bus state (`gpio_output_enabled`) must be explicitly set to `True` following a valid administrator PIN entry.
3. **Sensor Validity:** Composite temperature calculation (`sauna_calc_temp`) must be non-null and actively receiving live telemetry.
4. **Physical Seal Verification:** The magnetic door safety sensor (IDX `10001`) must detect a sealed `CLOSED` condition.
5. **Session Authorization:** Inbound REST payloads must contain a valid, unexpired JWT token.

If any single condition fails, the execution loop aborts, drops the start command, and dispatches a high-priority banner notification to the web client via `AlertManager`.

---

## 3. Sauna Safety Subsystems & Compliance Framework

The sauna infrastructure operates under a zero-trust safety framework distributed across event-driven verification logic and out-of-band background guardians.

### 3.1 Dual-Probe Volumetric Atmosphere Validation
To capture accurate thermal mass dynamics across the vertical gradient of the cabin, WanOS relies on a split dual-sensor topology. The calculation implements a strict mathematical rule:

$$\text{Sauna Calc Temp} = (\text{Probe}_{20001} \times 0.7) + (\text{Probe}_{20002} \times 0.3)$$

* **Strict Fail-Fast Condition:** If *either* the high sensor (IDX `20001`) or the low sensor (IDX `20002`) encounters a hardware error, reports a null state, or fails a Pydantic structure filter, the engine instantly voids the composite variable.
* **Core Failsafe Execution:** The moment `sauna_calc_temp` resolves to `None` while the elements are active, the system fires an emergency cutoff command to kill all relay modulation blocks.

### 3.2 Absolute Cumulative Runtime Limit (EN 60335-2-53 Compliant)
In strict compliance with EN 60335-2-53 standards, infinite heating is forbidden regardless of setpoint targets. The moment a `SAUNA_ON` command passes validation, an un-bypassable epoch cutoff timestamp is saved to memory:

$$\text{Absolute Cutoff} = \text{TimeNow} + (6 \times 3600)$$

This limit runs continuously from process activation and executes an immediate hard kill command exactly 6 hours later, completely independent of software timers or cabin metrics.

### 3.3 Out-of-Band Data Link Staleness Watchdog
If low-level physical I/O threads freeze due to electrical noise, memory registers can lock onto their last valid numbers, blinding event-gated emergency cuts. 
To mitigate this, the isolated `HealthMonitor` task audits data age out-of-band every 2 seconds. Every incoming packet from the SHT11 probes refreshes `last_heartbeat_unix`. If the sauna is active and this timestamp ages past 90 seconds, the monitor steps in, bypasses the main event queue, kills all heater relays, and logs a critical emergency alarm.

### 3.4 Magnetic Door Interlock State Machine
* **Grace Period Countdown:** If an occupant opens the sauna door while heating is active, the state manager schedules a 30-second `sauna_door_grace` timer. If the door closes before expiration, the countdown cancels with zero impact on heating operations.
* **Safety Pause Override:** If the grace window expires with the door left open, the engine switches into an automated `PAUSE` state, cutting element modulation.
* **SCADA Visual Annunciator:** Upon entering a safety pause, the core overrides ambient room lights (IDXs `51002`, `51004`, `51005`) and forces a SCADA Green color payload ($x: 0.1700, y: 0.7000$) down the network to visually alert occupants that the space is unsealed.

### 3.5 Cascade Circuit Breaker Protection
Hardware loops are linked via strict programmatic dependencies. If the physical 5V master safety loop relay drops due to an unexpected hardware shutdown or manual override, an internal interceptor instantly triggers inside the state manager:

```python
if event_name == "HUB_STATE_CHANGED" and p_idx == 71036 and payload.get("state") != "ON":
    # Cascades emergency output disarm and kills heater modulation
```

This forces a software fallback shutdown, locking out sauna GPIO output commands until the core infrastructure resets.

### 3.6 Zero-State Hardware Sanitization Pass (Cold Boot Guard)
To eliminate the threat of a "Split-Brain" ghost runtime—where physical relays remain hardware-latched `ON` after an unexpected application crash while software registers default to `OFF`—the system mandates a hardware-level sanitization phase at boot.
Before registering any listener hooks, the actuator controller claims exclusive control of physical GPIO handles, forcefully clamps all solid-state relay phase lines ($U, V, W$) and the IR channel to a 0% PWM duty cycle, drives digital pins to 0V (`LOW`), and drops the primary physical safety contactor relay. 
Because Pydantic definitions default `gpio_output_enabled` to `False` on launch, the hardware layer ignores incoming control states until an administrator inputs a valid session PIN.

---

## 4. Mathematical Formulations & Power Analytics Engine

The power analytics engine (`logic/power_analytics.py`) calculates high-frequency electrical performance, decouples background system noise, and isolates individual heating element degradation.

### 4.1 Power Leak Filtering (Background Consumption Isolation)
To isolate sauna element loads from auxiliary home infrastructure drawing power from the same pulse rail (such as Raspberry Pi controllers, active ventilation fans, or solid-state electronics), the system operates a dynamic filter.

#### Phase A: Idle Fingerprinting (Heaters Inactive)
When `state.sauna.active` and `state.ir.active` are both `False`, the system measures the time delta ($\Delta t$) between consecutive pulse ticks arriving at IDX `11001`. Instantaneous Background Leak Power ($P_{leak}$) is derived continuously in RAM:

$$P_{leak} = \frac{3600}{\Delta t}$$

#### Phase B: Active Decoupling (Heaters Firing)
The millisecond a heating session initializes, $P_{leak}$ locks its last known stable value. For every subsequent pulse tick during active operation, the isolated real wattage consumed purely by the heating elements ($P_{elements\_real}$) is computed as:

$$P_{measured} = \frac{3600}{\Delta t}$$

$$P_{elements\_real} = P_{measured} - P_{leak}$$

### 4.2 Disaggregated Dynamic Power Rating Extraction
Because the `StateManager` drives the physical heating elements using an asymmetric PWM strategy across phases U, V, and W via the PID controller, duty ratios drift continuously. The relationship between real power, live voltage sags, and heating element capacity is modeled linearly as:

$$P_{elements\_real} = \left(\frac{V_{live}}{230}\right)^2 \times ((D_U \cdot P_U) + (D_V \cdot P_V) + (D_W \cdot P_W))$$

Where:
* $V_{live}$ = Current line voltage read from Z-Wave Node 50 (IDX `71046`).
* $D_U, D_V, D_W$ = Current active PWM duty cycle scalars ($0.00$ to $1.00$).
* $P_U, P_V, P_W$ = Unknown physical element power capacities to extract in Watts.

By feeding these high-frequency operational parameters into a Recursive Least Squares (RLS) linear regression window inside RAM, the engine solves for real operating capacities ($P_U, P_V, P_W$) directly in Watts without requiring per-phase physical hardware current transformer (CT) clamps.

### 4.3 Normalized Thermal Insulation Health Index ($R_{th}$)
To track changes in cabin insulation performance without seasonal weather variations corrupting data, the system normalizes thermal rise metrics against outdoor temperatures. The Thermal Resistance Coefficient ($R_{th}$) is calculated continuously as:

$$R_{th} = \frac{\text{Sauna\_Calc\_Temp} - \text{Outside\_Temp}}{P_{elements\_real}}$$

A downward drift in this coefficient over time signals failing physical door seals, wall insulation degradation, or water retention inside the panel structure.

---

## 5. Storage Schema & Data Lifecycle

To maximize performance while preventing wear-leveling failure on the Raspberry Pi's physical SD card, high-frequency time-series math is kept strictly in volatile RAM. Completed session analytics are written to a local SQLite database (`sauna_sessions.db`) upon session termination.

House-level power/water **time-series history** (hi-res / hourly / daily rollups, Sensor History UI) is **not** stored here — see [sensor_history.md](sensor_history.md). Session rows remain in `sauna_sessions.db` with forever retention; that document also defines the planned `temp_outside_start` column and how sessions are listed in the UI.

### 5.1 SQLite Schema: `sauna_sessions`
```sql
CREATE TABLE sauna_sessions (
    session_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    start_timestamp      INTEGER NOT NULL, -- Unix Epoch Time
    total_runtime_secs   INTEGER NOT NULL,
    runtime_u_secs       INTEGER NOT NULL,
    runtime_v_secs       INTEGER NOT NULL,
    runtime_w_secs       INTEGER NOT NULL,
    temp_start           REAL NOT NULL,
    temp_end             REAL NOT NULL,
    temp_min             REAL NOT NULL,
    temp_max             REAL NOT NULL,
    temp_avg             REAL NOT NULL,
    temp_outside_start   REAL,            -- °C at start (OWM/outside); see sensor_history.md
    hum_start            INTEGER NOT NULL,
    hum_end              INTEGER NOT NULL,
    hum_min              INTEGER NOT NULL,
    hum_max              INTEGER NOT NULL,
    hum_avg              INTEGER NOT NULL,
    mod_system_min       REAL NOT NULL,
    mod_system_max       REAL NOT NULL,
    mod_system_avg       REAL NOT NULL,
    mod_u_min            REAL NOT NULL,
    mod_u_max            REAL NOT NULL,
    mod_u_avg            REAL NOT NULL,
    mod_v_min            REAL NOT NULL,
    mod_v_max            REAL NOT NULL,
    mod_v_avg            REAL NOT NULL,
    mod_w_min            REAL NOT NULL,
    mod_w_max            REAL NOT NULL,
    mod_w_avg            REAL NOT NULL,
    energy_real_wh       REAL NOT NULL, -- Pulse meter integration minus leak baseline
    energy_calc_wh       REAL NOT NULL, -- Integration of software math model over time
    extracted_p_u        REAL NOT NULL, -- Solved capacity for Phase U (Watts)
    extracted_p_v        REAL NOT NULL, -- Solved capacity for Phase V (Watts)
    extracted_p_w        REAL NOT NULL  -- Solved capacity for Phase W (Watts)
);
```

### 5.2 SQLite Schema: `ir_sessions`
```sql
CREATE TABLE ir_sessions (
    session_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    start_timestamp      INTEGER NOT NULL, -- Unix Epoch Time
    total_runtime_secs   INTEGER NOT NULL,
    temp_start           REAL NOT NULL,
    temp_end             REAL NOT NULL,
    temp_outside_start   REAL,            -- °C at start; see sensor_history.md
    hum_start            INTEGER NOT NULL,
    hum_end              INTEGER NOT NULL,
    mod_min              REAL NOT NULL,
    mod_max              REAL NOT NULL,
    mod_avg              REAL NOT NULL,
    energy_real_wh       REAL NOT NULL,
    energy_calc_wh       REAL NOT NULL
);
```

---

## 6. Targeted File Refactor Impact Matrix

The integration of power analytics, safety guards, and dynamic session recording impacts the following core files:

### 6.1 `core/models.py`
* Refactor `MetricsState` to track active in-memory counters for running session aggregates.
* Append structural `SaunaSessionRecord` and `IrSessionRecord` Pydantic models to validate incoming history packets.
* Expose live arrays for real-time power element capacity outputs to ensure the web UI receives reactive SSE streams.

### 6.2 `core/state_manager.py`
* Route incoming filtered Z-Wave payload values from Node 50 (Value ID `66561`) to bind natively as line voltage on IDX `71046`.
* Intercept `EventType.KWH_PULSE` (IDX `11001`) inputs to maintain the running Power Leak baseline.
* Enforce cascade cutoff interlocks when Master Relay (IDX `71036`) toggles.

### 6.3 `logic/power_analytics.py`
* Handles high-frequency pulse timer calculations, dynamic background leak parsing, and execution of linear RLS regression loops.
* Routes live operational updates every 60 seconds into `/var/log/wanos/wanos_power.log`.
* Intercepts session termination events to compute final statistics and trigger asynchronous commits to SQLite tables.

### 6.4 `logic/health_monitor.py`
* Monitors extracted element wattage outputs ($P_U, P_V, P_W$) inside background check loops.
* If any phase capacity drifts more than 10% below nominal thresholds ($3500\text{W}, 3500\text{W}, 2000\text{W}$), dispatches an automated system warning alert.
* Audits SHT11 sensor heartbeats out-of-band every 2 seconds.

### 6.5 `frontend/app.js` & Presentation Files
* Update Device Explorer panel (`admin.html`) to map "Sauna Probes & Heater Relays" to "Sauna Statistics".
* Bind live session metrics and extracted power integers into Alpine's reactive state engine.
* Render real-time element performance badges (e.g., `P_U: 3450W / Baseline: 3500W`) alongside real vs calculated energy comparison charts.