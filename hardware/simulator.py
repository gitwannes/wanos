# --- file: hardware/simulator.py ---
import asyncio
import math
from core.state_manager import StateManager
from core.models import Event, EventType
from core.config import load_config


async def lab_mode_thermodynamics_loop(state_mgr: StateManager):
    """
    Simulates realistic multi-zone thermodynamics when physical hardware is detached.
    Dynamically responds to user dashboard slider overrides on every evaluation tick.
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

    # Track historical metrics to handle outside climate slider baseline shifts smoothly
    last_calculated_out_temp = None
    last_calculated_out_hum = None

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
            if state.environment.sauna_high_temp is not None:
                sauna_high = state.environment.sauna_high_temp
            if state.environment.sauna_low_temp is not None:
                sauna_low = state.environment.sauna_low_temp
            if state.environment.sauna_high_hum is not None:
                sauna_high_hum = state.environment.sauna_high_hum
            if state.environment.sauna_low_hum is not None:
                sauna_low_hum = state.environment.sauna_low_hum
            if state.environment.bathroom_hum is not None:
                bathroom_hum = state.environment.bathroom_hum

            # Dynamic re-anchoring for outside atmosphere sliders
            if last_calculated_out_temp is not None and state.environment.outside_temp is not None:
                if round(state.environment.outside_temp, 1) != round(last_calculated_out_temp, 1):
                    # User moved the outside temperature slider! Re-adjust our base seed anchor
                    seed.outside_temp = state.environment.outside_temp - (5.0 * math.sin(outside_tick / 10.0))

            if last_calculated_out_hum is not None and state.environment.outside_hum is not None:
                if int(state.environment.outside_hum) != int(last_calculated_out_hum):
                    # User moved the outside humidity slider! Re-adjust our base seed anchor
                    seed.outside_hum = state.environment.outside_hum - (20.0 * math.cos(outside_tick / 15.0))

            # --------------------------------------------------------
            # 1. OUTSIDE SIMULATOR (Sine wave over time)
            # --------------------------------------------------------
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
                Event(type=EventType.HUMIDITY_UPDATED, payload={"sensor_id": "outside", "value": int(current_out_hum)}))

            # --------------------------------------------------------
            # 2. BATHROOM SIMULATOR (Humidity decay)
            # --------------------------------------------------------
            # If vent is running, decay faster. Otherwise, decay slowly to the baseline
            decay_rate = 1.0 if state.environment.bathroom_vent_on else 0.1
            if bathroom_hum > seed.bathroom_hum:
                bathroom_hum = max(seed.bathroom_hum, bathroom_hum - decay_rate)

            state_mgr.dispatch(
                Event(type=EventType.HUMIDITY_UPDATED, payload={"sensor_id": "bathroom", "value": int(bathroom_hum)}))

            # --------------------------------------------------------
            # 3. SAUNA THERMODYNAMICS (Thermal stratification)
            # --------------------------------------------------------
            AMBIENT = 20.0
            pwm = state.sauna.modulation_pwm
            door_open = state.sauna.door_open

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