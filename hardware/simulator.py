# --- file: hardware/simulator.py ---
"""
================================================================================
WANOS LAB MODE THERMODYNAMICS SIMULATION PROFILE REFERENCE
================================================================================

1. CORE INFRASTRUCTURE POWER MONITORS (KWH_PULSE)
--------------------------------------------------------------------------------
* Handles synthetic electricity monitoring metrics by integrating active loads over 2-second integration window slices.
* Simulates a dynamic resistive heater load for the main Sauna element scaling from 0W up to a maximum capacity of 9000W based on the current system modulation PWM.
* Simulates a constant step load profile for the Infrared radiant panel array dropping a solid 3000W load while toggled active.
* Accumulates integration steps internally into standard Watt-hours (Wh) and dispatches distinct integer KWH_PULSE event ticks down the StateManager pipeline whenever a whole Wh threshold is breached.

2. OUTSIDE ATMOSPHERE DOMAIN (outside)
--------------------------------------------------------------------------------
* Generates continuous day/night weather fluctuations by driving a localized timeline ticker loop against macro parameter anchors configuration.
* Models external ambient temperature patterns shifting up and down over time along a customized +/- 5.0°C sinusoidal weather wave cycle.
* Models external ambient humidity shifts moving conversely along a +/- 20% cosinusoidal weather cycle.
* Continually broadcasts macro ambient values down the human-readable network bus using specialized outside domain TEMP_UPDATED and HUMIDITY_UPDATED event keys.

3. BATHROOM ATMOSPHERE MANAGEMENT (bathroom)
--------------------------------------------------------------------------------
* Models dynamic internal relative humidity environment extraction variables.
* Evaluates active state dictionaries to track the operational toggle configuration of the virtual peripheral extractor fan hardware.
* Forces an accelerated exponential ambient humidity extraction decay speed parameter index of 1.0 units per calculation frame while the ventilator relay reads ON.
* Restricts dissipation speeds to a residual evaporation decay scale coefficient of 0.1 units per calculation frame when the extraction hardware relay reads OFF until moisture baselines hit baseline seed configuration metrics.
* Regularly pushes adjusted humidity constraints back into centralized memory via localized bathroom token tracking keys.

4. SAUNA THERMODYNAMIC ENGINES (sauna_high & sauna_low)
--------------------------------------------------------------------------------
* Models multi-tier thermal stratification layer metrics based on a defined baseline room tracking environment default of 20.0°C ambient room temperature.
* Discharges high-mass thermal injection profiles splitting calculated energy gains evenly across separate tracking sensors (allocating 70% heat retention profiles directly into the ceiling probe zone and 30% down over the lower bench probe layer).
* Models real-world ambient structural energy loss configurations calculating dissipation rates based on differences between local zone values and external constants (multiplying ceiling loss factor by 0.002 and lower bench loss factor by 0.001).
* Executes emergency draft dumps checking magnetic mechanical sensor inputs; if the door reads open, the loop injects a massive override penalty factor dumping 1.0 units of thermal energy off the ceiling and 0.5 units off the lower bench layers.
* Simulates relative moisture compression properties tracking dynamic moisture level reductions matching rapid heat ramps, while enabling a gradual moisture recovery rate tracking toward baseline metrics when elements power off.
* Concurrently feeds distinct telemetry streams into the core queue processing split individual temp and humidity definitions for both the sauna_high and sauna_low physical sensor targets.

5. CINEMA ROOM STATIONARY ENVIRONMENT (cinema)
--------------------------------------------------------------------------------
* Acts as a stable control environment for the simulation. Unlike the sauna or outside environments, the cinema room's climate metrics do not drift or decay over time.
* Sets the initial room temperature and relative humidity at startup by reading the `cinema_temp` and `cinema_hum` constants directly from the dynamic lab configuration seed (`config_lab.yaml` via `config.lab_seed`).
* Dispatches these static baseline values to the central state manager immediately upon boot. This prevents missing data (null values) in the UI dashboard and guarantees a reliable, flat reference point while running in lab emulation mode.
"""


import asyncio
import math
from core.state_manager import StateManager
from core.models import Event, EventType
from core.config import load_config


async def lab_mode_thermodynamics_loop(state_mgr: StateManager):
    """
    Simulates realistic multi-zone thermodynamics when physical hardware is detached.
    Dynamically responds to user dashboard slider overrides and accumulates energy power draw.
    """
    await asyncio.sleep(5.0)  # Give the server a few seconds to boot before starting

    # 1. Load the dynamic lab configuration
    config = load_config()
    seed = config.lab_seed

    # SAFETY GUARD: If config_lab.yaml doesn't exist (e.g., in production), exit the simulator cleanly.
    if not seed:
        await state_mgr.logger.warning("No lab_seed found in config. Halting thermodynamics simulator.")
        return

    # 2. Seed baseline environmental states from config_lab.yaml
    sauna_high = seed.sauna_high_temp
    sauna_low = seed.sauna_low_temp
    sauna_high_hum = seed.sauna_high_hum
    sauna_low_hum = seed.sauna_low_hum
    bathroom_hum = seed.bathroom_hum
    outside_tick = seed.outside_tick

    # Local UI metric tracking anchors
    last_calculated_out_temp = None
    last_calculated_out_hum = None

    # ⏱️ OUTSIDE SIMULATION TIMER
    # 150 ticks * 2 seconds = 300 seconds (5 minutes). Set to 150 initially to trigger on first run.
    outside_counter = 150

    # ⚡ VIRTUAL POWER INTAKE ACCUMULATOR ⚡
    wh_accumulator = 0.0

    # 3. Push static baselines instantly (These don't drift in Lab Mode)
    state_mgr.dispatch(Event(type=EventType.DOOR_CHANGED, payload={"is_open": seed.door_open}))
    state_mgr.dispatch(Event(type=EventType.TEMP_UPDATED, payload={"sensor_id": "cinema", "value": seed.cinema_temp}))
    state_mgr.dispatch(
        Event(type=EventType.HUMIDITY_UPDATED, payload={"sensor_id": "cinema", "value": int(seed.cinema_hum)}))
    state_mgr.dispatch(
        Event(type=EventType.TEMP_UPDATED, payload={"sensor_id": "bathroom", "value": seed.bathroom_temp}))

    while True:
        try:
            await asyncio.sleep(2.0)  # Evaluate physics every 2 seconds

            state = state_mgr.get_state_snapshot()

            # If we transition to live hardware, skip physics
            if state.hardware.live_mode:
                continue

            # --------------------------------------------------------
            # LIVE UI INTERCEPT SYNCHRONIZER
            # --------------------------------------------------------
            # Read straight from the central state vault. If a human dragged a slider,
            # capture that manual adjustment instantly as our new physics baseline!
            if state.sensors.sauna_high_temp is not None and round(sauna_high, 1) != round(
                    state.sensors.sauna_high_temp, 1):
                sauna_high = state.sensors.sauna_high_temp
            if state.sensors.sauna_low_temp is not None and round(sauna_low, 1) != round(
                    state.sensors.sauna_low_temp, 1):
                sauna_low = state.sensors.sauna_low_temp
            if state.sensors.sauna_high_hum is not None and int(
                    sauna_high_hum) != state.sensors.sauna_high_hum:
                sauna_high_hum = float(state.sensors.sauna_high_hum)
            if state.sensors.sauna_low_hum is not None and int(
                    sauna_low_hum) != state.sensors.sauna_low_hum:
                sauna_low_hum = float(state.sensors.sauna_low_hum)
            if state.sensors.bathroom_hum is not None and int(bathroom_hum) != state.sensors.bathroom_hum:
                bathroom_hum = float(state.sensors.bathroom_hum)

            # Dynamic re-anchoring for outside atmosphere sliders
            if last_calculated_out_temp is not None and state.sensors.outside_temp is not None:
                if round(state.sensors.outside_temp, 1) != round(last_calculated_out_temp, 1):
                    # User moved the outside temperature slider! Re-adjust base anchor and update tracking target
                    seed.outside_temp = state.sensors.outside_temp - (5.0 * math.sin(outside_tick / 10.0))
                    last_calculated_out_temp = state.sensors.outside_temp

            if last_calculated_out_hum is not None and state.sensors.outside_hum is not None:
                if int(state.sensors.outside_hum) != int(last_calculated_out_hum):
                    # User moved the outside humidity slider! Re-adjust base anchor and update tracking target
                    seed.outside_hum = state.sensors.outside_hum - (20.0 * math.cos(outside_tick / 15.0))
                    last_calculated_out_hum = state.sensors.outside_hum

            # --------------------------------------------------------
            # AUTOMATED ELECTRICAL POWER ACCRETION STEP
            # --------------------------------------------------------
            # Sauna Element Load: Scaling dynamically up to 9000W max total output
            active_sauna_w = 9000.0 * (state.sauna.modulation_pwm / 100.0) if state.sauna.active else 0.0
            # Infrared Array Load: Scaling dynamically up to 750W max based on UI slider
            active_ir_w = 750.0 * (state.ir.modulation_pwm / 100.0) if state.ir.active else 0.0
            
            # Formulate current consolidated load step integration parameter
            total_active_load_w = active_sauna_w + active_ir_w
            # Convert Watts over a 2.0 second time delta window slice into absolute Watt-hours (Wh)
            accumulated_step_wh = total_active_load_w * (2.0 / 3600.0)
            wh_accumulator += accumulated_step_wh

            # Flush complete integer steps directly down into the StateManager pulse router
            if wh_accumulator >= 1.0:
                whole_ticks = int(wh_accumulator)
                wh_accumulator -= whole_ticks
                for _ in range(whole_ticks):
                    state_mgr.dispatch(Event(type=EventType.KWH_PULSE))

            # --------------------------------------------------------
            # 1. OUTSIDE SIMULATOR (Gated to run once every 5 minutes)
            # --------------------------------------------------------
            outside_counter += 1
            if outside_counter >= 150:
                outside_counter = 0
                outside_tick += 1

                # Drifts up and down from the dynamic macro baseline anchor
                current_out_temp = seed.outside_temp + (5.0 * math.sin(outside_tick / 10.0))
                current_out_hum = seed.outside_hum + (20.0 * math.cos(outside_tick / 15.0))

                # Lock these values in memory so we can track manual variations on the next frame execution
                last_calculated_out_temp = current_out_temp
                last_calculated_out_hum = current_out_hum

                state_mgr.dispatch(
                    Event(type=EventType.TEMP_UPDATED,
                          payload={"sensor_id": "outside", "value": round(current_out_temp, 1)}))
                state_mgr.dispatch(
                    Event(type=EventType.HUMIDITY_UPDATED,
                          payload={"sensor_id": "outside", "value": int(current_out_hum)}))

            # --------------------------------------------------------
            # 2. BATHROOM SIMULATOR (Humidity decay)
            # --------------------------------------------------------
            # If vent is running, decay faster. Otherwise, decay slowly to the baseline
            decay_rate = 1.0 if state.devices.get("bathroom_ventilator") == "ON" else 0.1
            if bathroom_hum > seed.bathroom_hum:
                bathroom_hum = max(seed.bathroom_hum, bathroom_hum - decay_rate)

            state_mgr.dispatch(
                Event(type=EventType.HUMIDITY_UPDATED, payload={"sensor_id": "bathroom", "value": int(bathroom_hum)}))

            # --------------------------------------------------------
            # 3. SAUNA THERMODYNAMICS (Thermal stratification)
            # --------------------------------------------------------
            AMBIENT = 20.0
            pwm = state.sauna.modulation_pwm
            door_open = state.devices.get("door_sauna") == "OPEN"

            # 1. Heat injection
            heat_added = (pwm / 100.0) * 0.5

            # 2. Ambient heat loss
            temp_diff_high = max(0, sauna_high - AMBIENT)
            temp_diff_low = max(0, sauna_low - AMBIENT)
            heat_lost_high = temp_diff_high * 0.002
            heat_lost_low = temp_diff_low * 0.001

            # 3. Door open heat dump
            if door_open:
                heat_lost_high += 1.0
                heat_lost_low += 0.5

            # Calculate new temperatures based on stratification logic
            delta_high = (heat_added * 0.7) - heat_lost_high
            delta_low = (heat_added * 0.3) - heat_lost_low

            sauna_high = max(AMBIENT, round(sauna_high + delta_high, 2))
            sauna_low = max(AMBIENT, round(sauna_low + delta_low, 2))

            # Simple humidity physics: Relative humidity drops as temperature rises
            if heat_added > 0 and sauna_high_hum > 10.0:
                sauna_high_hum -= 0.1
                sauna_low_hum -= 0.05
            elif heat_added == 0 and sauna_high_hum < seed.sauna_high_hum:
                sauna_high_hum += 0.05
                sauna_low_hum += 0.02

            # Inject physical sensor data; the StateManager handles standard calculations
            state_mgr.dispatch(
                Event(type=EventType.TEMP_UPDATED, payload={"sensor_id": "sauna_high", "value": sauna_high}))
            state_mgr.dispatch(
                Event(type=EventType.TEMP_UPDATED, payload={"sensor_id": "sauna_low", "value": sauna_low}))
            state_mgr.dispatch(
                Event(type=EventType.HUMIDITY_UPDATED,
                      payload={"sensor_id": "sauna_high", "value": int(sauna_high_hum)}))
            state_mgr.dispatch(
                Event(type=EventType.HUMIDITY_UPDATED, payload={"sensor_id": "sauna_low", "value": int(sauna_low_hum)}))

        except asyncio.CancelledError:
            break
        except Exception:
            # Silently catch math errors so the simulator doesn't crash the loop
            pass