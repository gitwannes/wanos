# WanOS Sauna and Infrared (IR) Architecture, Safety, & Analytics Reference

This document serves as the master specification for the physical topography, operational lifecycle, safety interlocks, thermodynamic equations, and analytics pipelines governing the Sauna and Infrared (IR) heating systems within WanOS.

**Related:** Long-term utility and session **history** (power/water time-series tiers, retention, Sensor History UI, gap policy, and session field `temp_outside_start`) is specified in [sensor_history.md](sensor_history.md). This document remains authoritative for live sauna/IR safety, leak filtering, RLS extraction, and the core session schemas. Sauna ON/OFF and IR ON/OFF are **system catalog events (SE)** with hardcoded handlers; fire-action allowlist + Library (**UE/UR/SE/SR/D**) rules: [`env-schedule-and-system-events.md`](env-schedule-and-system-events.md) and [`todo/phaseB-blocky.md`](todo/phaseB-blocky.md) § B10E. **Assess** whether device actions can move to rules: [`todo/phaseB-blocky.md`](todo/phaseB-blocky.md) § **B17** (assess only). **Future:** clamp soft `session_end_time` to `absolute_cutoff_unix` (start+6h wall) on arm/adjust → § **B18**.

---

## 1. System Topography & Hardware Infrastructure

The sauna and infrared heating infrastructure operates on a high-power, multi-phase electrical topology managed through direct microsecond GPIO actuation and localized protocol bridges.

**PCB / carrier board:** KiCad design, connector pinouts, and JLCPCB fabrication are tracked in the separate [**wanos-pcb**](https://github.com/gitwannes/wanos-pcb) repository. GPIO idx and BCM assignments for the running WanOS Pi remain in root `config_hardware.yaml`. Full WISC BCM inventory: [wanos-pcb `docs/gpio-map.md`](https://github.com/gitwannes/wanos-pcb/blob/main/docs/gpio-map.md). New carrier map: [wanos-pcb `docs/gpio-interface.md`](https://github.com/gitwannes/wanos-pcb/blob/main/docs/gpio-interface.md).

### 1.1 Electrical Phase Layout & Element Capacities
The sauna heating system operates on a balanced 3x400V+N star configuration where every independent resistor phase draws load across a dedicated line conductor and Neutral, operating at a 230V nominal AC rating.
* **Phase U (Heater Element 1):** Nominal 3500 Watts capacity.
* **Phase V (Heater Element 2):** Nominal 3500 Watts capacity.
* **Phase W (Heater Element 3):** Nominal 2000 Watts capacity.
* **Infrared (IR) Array:** Single-phase pulse-width modulated (PWM) heater zone operating independently or in combined mode.

### 1.1a SSR modulation (sauna vs IR)

Heaters use **zero-crossing SSRs** on 50 Hz mains (100 ZC/s, 10 ms between crossings). Integer MOD is meaningful only when on/off times map to whole AC cycles.

**Sauna (U/V/W) — software PWM** (`hardware/actuators.py`, `config.sauna.pwm_freq`, default **0.5 Hz**):
* Period = **2 s**. Integer MOD 0–100 from the PID waterfall.
* **1% = 20 ms ON** = 2 zero-crossings = **one full sinus** (matches ZC SSR quantum).
* Timing uses `asyncio.sleep` (not mains-edge locked); on-time length matches one cycle per percent.

**IR — hardware `lgpio.tx_pwm`** with stepped duty + frequency (WISC / UI slider):
* `100%` → DC 100%, 5 Hz (freq irrelevant): all on  
* `75%` → DC 75%, 25 Hz: 3 ZC on, 1 off  
* `67%` → DC 67%, 33 Hz: 2 ZC on, 1 off  
* `50%` → DC 50%, 50 Hz: 1 ZC on, 1 off  
* `33%` → DC 33%, 33 Hz: 1 ZC on, 2 off  
* `25%` → DC 25%, 25 Hz: 1 ZC on, 3 off  

Frontend `irStepValues` / `irStepFreqs` and backend `freq_map` must stay aligned.

### 1.2 Measurement Infrastructure & System Asset Identifiers (IDXs)
* **Real-Time Energy Tracking (Pulse Meter):** Sauna-circuit kWh meter (not whole-house). Physically wired to GPIO Input Pin 12 and mapped as Virtual Identifier (IDX) `11001`. Operates at a resolution of 1000 pulses per kWh (exactly 1.0 Watt-hour per pulse tick). Whole-house energy is HomeWizard P1 (**G10**).
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
When a user or automated timer dispatches a `SAUNA_ON` event payload to `/api/event`, the system verifies these hardware / session criteria:
1. **Master Relay Power:** The 5V Master Safety Relay (IDX `71036`) must report an active `ON` state (Start Gate row may be soft-disabled in code for dry-run; bouncer still checks `switch.safety` / SSR entity).
2. **Hardware Bus Arming:** The physical local Raspberry Pi GPIO output bus state (`gpio_output_enabled`) must be explicitly set to `True` following a valid administrator PIN entry.
3. **Sensor Validity:** Composite temperature calculation (`sauna_calc_temp`) must be non-null and actively receiving live telemetry.
4. **Physical Seal Verification:** The magnetic door safety sensor (IDX `10001` / `sensor.door.sauna_deur`) must detect a sealed `CLOSED` condition.
5. **Recent door close:** `doors.sauna_closed_since_unix` must be set and not older than `sauna.door_closed_max_mins` (default **5**). Null (no close seen this process) **blocks** start. WISC: `Cannot start sauna, open sauna door first and check if all is ok`; Start Gate banner fragment `Door closed too long`. Door **OPEN** still uses `Cannot start sauna, please close door` / `Door open`.
6. **Mutual exclusion:** IR must not be active.
7. **Session Authorization:** Inbound REST payloads must contain a valid, unexpired JWT token.

If any single condition fails, the execution loop aborts, drops the start command, and dispatches a high-priority banner notification to the web client via `AlertManager`.

**Soft session timers:** When the sauna/IR soft countdown reaches zero, the hub schedules **`SAUNA_OFF` / `IR_OFF` directly** (no `*_TIMER_EXPIRED` catalog hop). Library rules that listen to Sauna OFF / IR OFF still run.

### 2.2 Post-OFF extraction fan (Library + Timers & types)

Hub code does **not** arm sauna vent wait/run timers after `SAUNA_OFF`. Operator-owned behaviour:

* **Delayed ON:** Library rule on **Sauna OFF** → **Set after** (e.g. `00:10:00`) → `zwave.vent.sauna` **ON**.
* **Auto OFF:** Timers & types membership for `zwave.vent.sauna` with a per-device delay (e.g. **180** minutes).

WISC Extraction Fan row shows live device ON/OFF only (no WAITING/RUNNING hub countdown).

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
To mitigate this, the isolated `HealthMonitor` task audits data age out-of-band every 2 seconds. Every successful SHT11 poll of the sauna probes (`20001` / `20002`) refreshes `last_heartbeat_unix` — including **stable** reads where T/RH did not change (those skip `TEMP_UPDATED` / `HUMIDITY_UPDATED` to avoid event spam, but must still tick the safety heartbeat). Value-change events also refresh it via the state manager. If the sauna is active and this timestamp ages past 90 seconds, the monitor steps in, bypasses the main event queue, kills all heater relays, and logs a critical emergency alarm.

### 3.4 Magnetic Door Interlock State Machine
Door transitions update device state only in `handle_door_changed`. The interlock itself lives in `StateManager` (do **not** hard-kill `sauna.active` on open — that bypassed pause/resume).

* **Grace Period Countdown:** If an occupant opens the sauna door while heating is active, the state manager schedules a **30-second** `sauna_door_grace` timer (`config_hardware.yaml` → `sauna_safety.door_grace_period_secs`). Heaters keep running during the window. If the door closes before expiration, the countdown cancels with zero impact on heating.
* **Safety Pause Override:** If the grace window expires with the door left open, the engine sets `is_paused = True` (session stays active), cutting element modulation via the PID interlock.
* **Auto-resume:** When the door closes while paused, `is_paused` clears and heating resumes automatically.
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

### 3.7 Remote LCD Status Screens (WISC-Compatible)
WanOS keeps the two character LCDs on a dedicated Wi-Fi Pi (`10.32.251.51`) and treats that node as a render target only. The LCD Pi runs a small Python agent that subscribes to WanOS MQTT topics (`wanos/lcd/screen1`, `wanos/lcd/screen2`) and writes lines to the physical I2C displays.

**Deploy / install (L1 shipped 2026-08-24):**
* Repo tree: [`_lcd-agent/`](../_lcd-agent/) (agent + `helpers/bootstrap/`).
* Pi path: `/home/wannes/wanos` (venv `wanos_venv`). Sync: `helpers\wanos-sync.bat test|run|logcopy lcd` — see [`wanos-sync.md`](wanos-sync.md). Modes `test` / `run` / `logcopy` / `codeimport` are mutually exclusive.
* Secrets: `/home/wannes/wanos/.env` (`WANOS_LCD_*`; never git). Unit `wanos-lcd-agent.service` loads that file via `EnvironmentFile`.
* Boot I2C: `dtparam=i2c_arm=on` in `/boot/firmware/config.txt` **or** legacy `/boot/config.txt`.
* Install guide: [`_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`](../_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md).
* Delivery track: [`todo/phaseL-lcd.md`](todo/phaseL-lcd.md) (**L1** Done; **L2** = screens on WanOS Pi + `.env` → `config_hardware.yaml`, queued).

**I2C addresses on LCD Pi (confirmed):**
* `0x27` = Screen 1 (sauna status)
* `0x26` = Screen 2 (control/status)

#### 3.7.1 Door Duration Tracking Contract
WanOS tracks open/close timing for all configured doors (currently two) under nested `state.doors` (SSE domain **`doors`**):
* Sauna door: entity `sensor.door.sauna_deur` (device OPEN/CLOSED + `doors.sauna_open_since_unix` / `doors.sauna_closed_since_unix`)
* Bathroom door: entity `sensor.door.badkamer_deur` (device OPEN/CLOSED + `doors.bathroom_open_since_unix` / `doors.bathroom_closed_since_unix`)

`DOOR_CHANGED` reconciles stamps on every event (including GPIO cold-boot baseline when device state does not change): clears the opposite-mode stamp; seeds the current-mode stamp only when it is still null (does not reset an existing same-mode age).

Duration format is canonical:
* `[dd:][hh:]mm:ss`
* show `dd:` only when `dd > 0`
* show `hh:` only when `hh > 0` (or when `dd > 0`)

Sauna LCD screen1 shows **closed** duration on line2 (with temp/hum); when the door is **open**, line2 is `plz close sdoor` with **no** duration. Admin **Site info** door rows: label from live device OPEN/CLOSED; timer from the matching stamp (or `—` if unset).

#### 3.7.2 Screen 1 (`0x27`) Display Rules
Screen 1 follows WISC text intent (shared composer [`logic/lcd_screen1.py`](../logic/lcd_screen1.py)), not legacy one-line `AuxiliaryController` text. The same lines are mirrored into `sauna.lcd_line1` / `sauna.lcd_line2` for the WISC sauna panel and Admin **LCD mirror** (green VT323 16×2 preview via `.wanos-lcd-screen`), spaces preserved so centered rows match the physical LCD. When both lines are blank, WISC shows `WanOS Wisc standby`. When Admin **LCD screens** integration is off, WISC shows `no LCD text:` / `integration off` and WanOS does not publish `wanos/lcd/*` (compose still runs internally until a future phase).

**LCD agent logging (C34):** `wanos.log` DEBUG lines pretty-print `§1` as `°C` (wire MQTT unchanged). Countdown-only mm:ss ticks are not logged; blank transitions, mod/temp/hum changes are.

**Integration master switch (Admin):** `system.lcd_integration_enabled` — `LCD_TOGGLED`. Requires local WanOS MQTT broker online to enable (same gate as OpenWeather). When off: no MQTT to the LCD Pi; debug/easter-egg Admin actions are also blocked at the publisher.

Priority:
1. **Sauna active**
   * Line 1: `sauna ON` / `sauna HOLD` / `sauna ON  {mod}%` while remaining ≥ **15 min**; when remaining **&lt; 15 min**, show mm:ss (WISC). Pre-arm, `session_end_time` is frozen duration seconds (not unix) — LCD must not treat it as an absolute end (that produced a false `00:00`).
   * Remaining arms when `sauna_calc_temp >= target - timer_offset_temp` (`config.yaml`), same as WISC `sstimerstarted`.
   * Line 2 default = temp/hum **left** + **door-closed duration right-aligned** (`doors.sauna_closed_since_unix`).
   * If sauna door is open, line 2 becomes `plz close sdoor` **without** open/closed duration.
2. **IR active** (when sauna is not active): line 1 `IR {mm:ss}`; append ` - {mod}%` only when `0 < mod < 100`; at 100% mod the timer is right-aligned (`IR` left). Line 2 = temp/hum.
3. **Sauna Hue ON only** (when sauna+IR inactive): use date/outside-info fallback text (`shue` equivalent = `hue.group.sauna_hue` ON).
4. **Blank screen 1** when sauna inactive, IR inactive, and sauna Hue is OFF.

#### 3.7.3 Screen 2 (`0x26`) Display Rules
Screen 2 is status-only (no live sauna/IR timer view):
* Init/boot/status/easter-egg messages
* Screen saver timeout blanks screen 2

#### 3.7.4 `lcdpower` Support
Legacy WISC code includes `lcdpower` handling in the LCD receiver.
In WanOS, blanking can be fully implemented via explicit blank-screen commands (clear + backlight off). `lcdpower` remains optional as a future manual override primitive (backlight control decoupled from content).

#### 3.7.5 Easter Egg (Admin)
An Admin page "System Commands" action can send a Screen 2 easter-egg status message. No additional role-gate is needed in the frontend because `admin.html` is already admin-only.
Secret variant should be retained in WISC-compatible formatting.

#### 3.7.6 Debug LCD test (Admin)
Admin → **Debug Commands** → **Test LCD screens** publishes the same payload to `wanos/lcd/screen1` and `wanos/lcd/screen2`: line 1 = local `YYYY-MM-DD HH:MM` (16 cells); line 2 = `operator debug` (≤16). Used to verify MQTT → LCD Pi path without a sauna session. Empty both-lines MQTT payloads blank the physical screen (`clear` + backlight off). Forced debug text is **held** until live screen1 content exists (sauna / IR / sauna Hue) — idle blank compose must not wipe it on the next door/sensor tick.

### 3.8 Sauna PID heat-up (v1)
Heat-up uses a P-only loop with a virtual setpoint, matching the WISC `PID.py` caller (`setpointbias = -1.0`, gains 12 / 0 / 0).

* **Gains** (`config.yaml` `sauna.kp` / `ki` / `kd`): **12.0 / 0.0 / 0.0**. Proportional band is `100 / kp` °C (~8.3 °C). With Ki = Kd = 0, MOD stays at 100% until about 8 °C below the *virtual* setpoint, then ramps linearly to 0.
* **Bias** (`sauna.setpoint_bias`): °C added to the PID setpoint. **−1.0 while `hold_mode` is `autohold`**. Error is `(target + bias) − T`, so at target 80 °C the PID aims at 79 °C and MOD reaches 0 at 79 °C; cabin inertia is expected to finish the last degree (about 1 °C overshoot is acceptable). **`nohold` uses bias 0** (real setpoint). `hold` / pause still dump MOD and reset the PID (unchanged).
* **Autohold:** when `sauna_calc_temp >= target`, WanOS still switches `autohold → hold` and cuts heaters. With v1 bias, that dump happens when PID output is already ~0.
* **Fire order:** the U/V/W permutation is calculated at `SAUNA_ON` and frozen for the session (waterfall, live `fireorder`, and the session record). A session that crosses midnight does not rotate phases.

v2 (not this ship): drop autohold and use I (and possibly D / a different bias) to hold temperature.

---

## 4. Mathematical Formulations & Power Analytics Engine

The power analytics engine (`logic/power_analytics.py`) calculates high-frequency electrical performance, decouples background system noise, and isolates individual heating element degradation.

### 4.1 Power Leak Filtering (Background Consumption Isolation)
To isolate sauna element loads from auxiliary home infrastructure drawing power from the same pulse rail (such as Raspberry Pi controllers, active ventilation fans, or solid-state electronics), the system operates a dynamic filter.

#### Phase A: Idle Fingerprinting (Heaters Inactive)
When `state.sauna.active` and `state.ir.active` are both `False`, the system measures the time delta ($\Delta t$) between consecutive pulse ticks arriving at IDX `11001`. Instantaneous candidate leak power is:

$$P_{candidate} = \frac{3600}{\Delta t}$$

Samples above **2000 W** are rejected (GPIO bounce / clustered ticks cannot be household baseline — those values were poisoning Real W to 0 by locking 9–18 kW “leak”). Accepted samples EMA into $P_{leak}$ (`alpha = 0.35`) and persist to `wanos-nvram.json` (restored on boot with the same sanity cap; flushed with the 5-minute NVRAM heartbeat). While the **sauna extraction fan** (`zwave.vent.sauna`) is **ON**, idle leak updates **freeze** (vent load must not raise the household baseline).

#### Phase B: Active Decoupling (Heaters Firing)
While a heating session is active, idle fingerprinting pauses and the last accepted $P_{leak}$ stays locked. For every subsequent pulse tick, the isolated real wattage consumed purely by the heating elements ($P_{elements\_real}$) is computed as:

$$P_{measured} = \frac{3600}{\Delta t}$$

$$P_{elements\_real} = P_{measured} - P_{leak}$$

**MOD=0 Real W gate:** while a session is active but heaters are commanded off (`sauna.modulation_pwm == 0` and IR not drawing), displayed `p_elements_real_watts` is forced to **0** immediately (clears stale last-pulse samples). If leak-subtracted meter load is **&gt; 1 W** (i.e. raw &gt; leak + 1 W), WanOS logs a **warning** (60 s cooldown): treat as possible stuck SSR / unexpected load on the same rail — **no auto cutoff**. Session Real Wh still integrates the measured pulses so unexplained energy remains auditable.

### 4.2 Disaggregated Dynamic Power Rating Extraction
Because the `StateManager` drives the physical heating elements using an asymmetric PWM strategy across phases U, V, and W via the PID controller (software PWM at **0.5 Hz** by default — see §1.1a), duty ratios drift continuously. The relationship between real power, live voltage sags, and heating element capacity is modeled linearly as:

$$P_{elements\_real} = \left(\frac{V_{live}}{230}\right)^2 \times ((D_U \cdot P_U) + (D_V \cdot P_V) + (D_W \cdot P_W))$$

**Session Energy (Calc)** integrates the software model over time (Admin `energy_calc_wh` in SQLite). Inter-pulse gaps for calc integration are capped and reset at session start so idle gaps before the first pulse are not charged at full nominal load (C34). Element **W @ 100% mod** live in SQLite table `element_power_w` (singleton row in `sauna_sessions.db`); bootstrap defaults U/V/W/IR = 3500/3500/2000/525 W until sessions refine them (EMA 0.7/0.3, ±25% outlier reject).

**Sauna learn (full-load window):** on each energy pulse while sauna is active, WanOS tracks contiguous time where **U, V, and W are all ≥ 95%**. If the best contiguous run is **≥ 30 s**, nameplate learn uses average real W from **all** pulse intervals that met that condition (not whole-session average, and not session-wide phase mins — heat-up / PID ramp-down no longer disqualify a long MOD-100 stretch). Fallback remains a single-phase-dominant session window.

**IR learn (C34):** when modulation spans more than 10 points in one session (e.g. 75% then 100%), learn uses **time-weighted** implied 100% W per mod plateau (min 30 s per plateau) instead of skipping. Stable single-plateau sessions use the session-average formula.

| Source | Role |
|--------|------|
| `element_power_w` DB row | Calc baselines for U, V, W, IR @ 100% mod |
| `ir_sessions` / `sauna_sessions` audit cols | Session ℹ popover; **learn counts** in Admin = sessions with non-null `audit_measured_w_*` |
| Pulse meter + leak subtract | Real session energy |

Sauna calc: $\sum (D_{phase} \times P_{db,phase}) \times (V/230)^2$. IR-only sessions add $(IR\_mod/100) \times P_{db,ir} \times (V/230)^2$. **Real** session energy always comes from the pulse meter minus locked leak.

**Thermal Index ($R_{th}$):** computed only while sauna is active and $P_{real} > 500$ W; Admin shows **N/A** until first valid sample, then retains the last value when idle. Stored as °C/W; Admin label **Rth** displays **2 decimals** in **°C/kW** (×1000), e.g. `0.98 °C/kW`. Tooltip: cabin ΔT per kW of real heat — downward drift means worse seals/insulation.

**Admin — Sauna / IR pane:** one card grouping Site info (mains, leak, Total kWh, session counts, Rth, sauna/bathroom door open|closed + duration), LCD mirror (VT323), element nameplates (vertical stack) + **learn counts** (from session audit rows; refreshed when last session updates over SSE) + last session detail (energy · W · runtime **HH:MM:SS** · smart when), Probes & SSR (ceiling/bench, Safety SSR, fireorder), and a live sub-panel that expands when a session runs — MOD total + U/V/W % (sauna) or IR MOD, runtime + remaining, Real W, **Calc W (V-adj)** (voltage-scaled model; not equal to nameplate @ 100%), energy real/calc (Wh for IR-only, kWh otherwise), deltas, est. U/V/W when sauna active. Sauna remaining arms at `target − timer_offset_temp`, not exact setpoint. `GET /api/admin/analytics/element-power`. Total kWh = NVRAM `11001` Wh / 1000 (absolute **sauna** meter face; reseed to that physical meter — not whole-house; whole-house → HomeWizard P1 / **G10**).

**Admin — General Diagnostics:** lifetime **Total water** (cold / hot / sum liters from NVRAM counters).

**Admin — GPIO outputs arm gate:** status shows `OFFLINE` → `NEED INPUTS` → `NEED SHT11` → `WAIT TEMP` → `READY` → `ARMED` (Admin label refreshed on the 1 Hz client ticker). Arming SHT11 triggers an immediate sensor poll (2 s fast cadence until `sauna_calc_temp` is valid). SSE subscribe **seeds** current `hardware` / `sensors` domains so LIVE/READY is not stuck after a missed one-shot bus-health event.

**WISC:** while sauna/IR active — Real W + **Energy real/calc** on one line under the control; Bathroom shows **cold/hot water today** (not lifetime totals). Idle — last sauna / last IR one-liners (smart date/time only). Each `IR_ON` resets modulation to `config.ir.default_ir_modulation` (site default 75%).

**Session audit (SQLite + Session History i popover):** each session stores baseline / measured / new @100% W per element (nullable when not computed).

**Session History UI:** Sauna tab Energy in **kWh**; IR tab in **Wh**; Avg W derived; IR temp/hum/mod columns; **i** popover for audit triple on both tabs. Admin may delete individual session rows.

Where:
* $V_{live}$ = Current line voltage read from Z-Wave Node 50 (IDX `71046`).
* $D_U, D_V, D_W$ = Current active PWM duty cycle scalars ($0.00$ to $1.00$).
* $P_U, P_V, P_W$ = Unknown physical element power capacities to extract in Watts.

By feeding these high-frequency operational parameters into a Recursive Least Squares (RLS) linear regression window inside RAM, the engine solves for real operating capacities ($P_U, P_V, P_W$) directly in Watts without requiring per-phase physical hardware current transformer (CT) clamps.

### 4.3 Normalized Thermal Insulation Health Index ($R_{th}$)
To track changes in cabin insulation performance without seasonal weather variations corrupting data, the system normalizes thermal rise metrics against outdoor temperatures. The Thermal Resistance Coefficient ($R_{th}$) is calculated continuously as:

$$R_{th} = \frac{\text{Sauna\_Calc\_Temp} - \text{Outside\_Temp}}{P_{elements\_real}}$$

A downward drift in this coefficient over time signals failing physical door seals, wall insulation degradation, or water retention inside the panel structure. Admin renders the live value as **Rth** `0.00 °C/kW` (two decimal places; stored °C/W ×1000) with a one-line tooltip on the label.

---

## 5. Storage Schema & Data Lifecycle

To maximize performance while preventing wear-leveling failure on the Raspberry Pi's physical SD card, high-frequency time-series math is kept strictly in volatile RAM. Completed session analytics are written to a local SQLite database (`sauna_sessions.db`) upon session termination.

Utility power/water **time-series history** (hi-res / hourly / daily rollups, Sensor History UI) is **not** stored here — see [sensor_history.md](sensor_history.md). Session rows remain in `sauna_sessions.db` with forever retention; that document also defines the planned `temp_outside_start` column and how sessions are listed in the UI.

### 5.1a Sauna session sample telemetry (PID / climate debug)
While `sauna.active`, WanOS buffers time-series samples in RAM (`logic/sauna_session_telemetry.py`) and flushes them on `SAUNA_OFF` into:

1. SQLite table **`sauna_session_samples`** (same `sauna_sessions.db`, keyed by `session_id`)
2. CSV **`sessionlog/sauna_session_YYYYMMDD_HHMMSS.csv`** (app root; local wall clock of session start)

**Sample triggers:** climate temp/hum change; every PID `compute` (coalesced with MOD change on the same tick); `hold_mode` / `is_paused` edges; **5 s** heartbeat while active (including paused). Keep sampling through door grace / pause.

**Session constants** (not copied on every sample row): `kp`, `ki`, `kd`, and `fireorder` live on **`sauna_sessions`**. CSV files put the same four values on a commented first line, e.g. `# kp=12.0 ki=0.0 kd=0.0 fireorder=WVU`. On boot, if an older `sauna_session_samples` table still has those columns, WanOS copies the first usable value onto the parent session row, then rebuilds samples without them. Pre-v1 sample rows get `setpoint_bias` = NULL.

**Sample columns:** `ts`, probe + calc T/RH, `mod_u/v/w` + `mod_total`, calc W per phase + total, **Real W total only**, `w_measured_total` (real+leak), PID `p/i/d/error/output_raw/dt`, `integral_reset_reason`, **`setpoint_bias`** (applied that tick: −1.0 in autohold, 0 otherwise), `target_temp`, `hold_mode`, `is_paused`, `door_state`, `outside_temp`, `r_th`, `v_line`, `p_leak`, `trigger`.

Mid-session crash loses the RAM buffer (flush-at-end). Folder `sessionlog/` is gitignored. Sync pulls `sessionlog/*` into OneDrive `logs\` and (with logcopy) into git `docs\logs` — see [wanos-sync.md](wanos-sync.md).

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
    extracted_p_w        REAL NOT NULL, -- Solved capacity for Phase W (Watts)
    kp                   REAL,        -- Session-constant PID gain (from samples for pre-v1 rows)
    ki                   REAL,
    kd                   REAL,
    fireorder            TEXT         -- Frozen at SAUNA_ON (e.g. WVU)
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
* Intercept `EventType.KWH_PULSE` (IDX `11001`) inputs to maintain the running Power Leak baseline. KWH_PULSE is not written to `wanos.log` (high-frequency).
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
* Admin **Sauna / IR** card (`admin.html`) groups Site info (incl. door open/closed ages), LCD mirror, learned nameplates, Probes & SSR, and the live session sub-panel (MOD / timers / power).
* Bind live session metrics and extracted power integers into Alpine's reactive state engine (`formatRthInsulation`, live energy helpers).
* WISC bathroom Cold/Hot water keeps value + unit on one line on narrow viewports.