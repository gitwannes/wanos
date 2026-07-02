# --- file: hardware/simulator.py ---
"""
================================================================================
WANOS LAB MODE THERMODYNAMICS SIMULATION PROFILE REFERENCE
================================================================================
(Docs preserved... see implementation below for dynamic IDX injection)
"""

import asyncio
import math
from typing import Optional
from core.state_manager import StateManager
from core.models import Event, EventType
from core.config import load_config


async def lab_mode_thermodynamics_loop(state_mgr: StateManager) -> None:
    """
    Simulates realistic multi-zone thermodynamics when physical hardware is detached.
    Dynamically injects ANY sensor or device found in the lab configuration seed!
    """
    await asyncio.sleep(5.0)  # Give the server a few seconds to boot before starting

    # 1. Load the dynamic lab configuration
    config = load_config()
    seed = config.boot_seed

    # SAFETY GUARD: If config_lab.yaml doesn't exist (e.g., in production), exit the simulator cleanly.
    if not seed:
        await state_mgr.logger.warning("No boot_seed found in config. Halting thermodynamics simulator.")
        return

    await state_mgr.logger.warning("boot_seed config initialized. Executing dynamic IDX injection...")

    # Safely convert the config seed to a dictionary (handles both dicts and Pydantic models)
    seed_dict = seed if isinstance(seed, dict) else (seed.model_dump() if hasattr(seed, "model_dump") else seed.__dict__)

    def get_val(idx: int, prop: str, default: float) -> float:
        """Helper to extract nested dictionary properties from the parsed YAML."""
        node = seed_dict.get(idx) or seed_dict.get(str(idx)) or {}
        return node.get(prop, default)

    # 2. Extract baseline "Anchors" for the continuous physics loop math
    anchor_sauna_high_hum: float = float(get_val(20001, "hum", 45.0))
    anchor_bathroom1_hum: float = float(get_val(20004, "hum", 45.0))
    anchor_outside_temp: float = float(get_val(30001, "temp", 15.0))
    anchor_outside_hum: float = float(get_val(30001, "hum", 60.0))
    outside_tick: int = int(seed_dict.get("outside_tick", 0))

    # Active tracking variables (initialized to anchors)
    sauna_high: float = float(get_val(20001, "temp", 21.0))
    sauna_low: float = float(get_val(20002, "temp", 20.0))
    sauna_high_hum: float = anchor_sauna_high_hum
    sauna_low_hum: float = float(get_val(20002, "hum", 48.0))
    bathroom1_hum: float = anchor_bathroom1_hum

    # Local UI metric tracking anchors
    last_calculated_out_temp: Optional[float] = None
    last_calculated_out_hum: Optional[float] = None

    # ⏱️ OUTSIDE SIMULATION TIMER (300 seconds)
    outside_counter: int = 150

    # ⚡ VIRTUAL POWER INTAKE ACCUMULATOR ⚡
    wh_accumulator: float = 0.0

    # -------------------------------------------------------------------------
    # 3. CONTINUOUS PHYSICS LOOP
    # -------------------------------------------------------------------------
    while True:
        try:
            await asyncio.sleep(2.0)  # Evaluate physics every 2 seconds

            state = state_mgr.get_state_snapshot()

            # Master Simulator Power Switch
            if not state.hardware.simulations_enabled:
                continue

            # ⚡ Auto-Kill Engine Gate
            # If BOTH primary hardware sensor buses are armed, the automated physics engine
            # has no test surface left to manipulate. It self-terminates to preserve CPU.
            if state.hardware.gpio_input_enabled and state.hardware.sht11_enabled:
                state_mgr.dispatch(Event(type=EventType.SIMULATIONS_TOGGLED, payload={"enabled": False}))
                continue

            # --- LIVE UI INTERCEPT SYNCHRONIZER ---
            # Automatically pulls from local state variable (initialized by the seed_dict)
            # if the master state is completely None.
            if state.sensors.sauna_high_temp is not None and round(sauna_high, 1) != round(state.sensors.sauna_high_temp, 1):
                sauna_high = state.sensors.sauna_high_temp
            if state.sensors.sauna_low_temp is not None and round(sauna_low, 1) != round(state.sensors.sauna_low_temp, 1):
                sauna_low = state.sensors.sauna_low_temp
            if state.sensors.sauna_high_hum is not None and int(sauna_high_hum) != state.sensors.sauna_high_hum:
                sauna_high_hum = float(state.sensors.sauna_high_hum)
            if state.sensors.sauna_low_hum is not None and int(sauna_low_hum) != state.sensors.sauna_low_hum:
                sauna_low_hum = float(state.sensors.sauna_low_hum)
            if state.sensors.bathroom1_hum is not None and int(bathroom1_hum) != state.sensors.bathroom1_hum:
                bathroom1_hum = float(state.sensors.bathroom1_hum)

            # Dynamic re-anchoring for outside atmosphere sliders
            if last_calculated_out_temp is not None and state.sensors.outside_temp is not None:
                if round(state.sensors.outside_temp, 1) != round(last_calculated_out_temp, 1):
                    anchor_outside_temp = state.sensors.outside_temp - (5.0 * math.sin(outside_tick / 10.0))
                    last_calculated_out_temp = state.sensors.outside_temp

            if last_calculated_out_hum is not None and state.sensors.outside_hum is not None:
                if int(state.sensors.outside_hum) != int(last_calculated_out_hum):
                    anchor_outside_hum = state.sensors.outside_hum - (20.0 * math.cos(outside_tick / 15.0))
                    last_calculated_out_hum = state.sensors.outside_hum

            # --- AUTOMATED ELECTRICAL POWER ACCRETION STEP ---
            active_sauna_w = 9000.0 * (state.sauna.modulation_pwm / 100.0) if state.sauna.active else 0.0
            active_ir_w = 750.0 * (state.ir.modulation_pwm / 100.0) if state.ir.active else 0.0
            total_active_load_w = active_sauna_w + active_ir_w
            accumulated_step_wh = total_active_load_w * (2.0 / 3600.0)
            wh_accumulator += accumulated_step_wh

            if wh_accumulator >= 1.0:
                whole_ticks = int(wh_accumulator)
                wh_accumulator -= whole_ticks
                for _ in range(whole_ticks):
                    state_mgr.dispatch(Event(type=EventType.KWH_PULSE))

            # --- 1. OUTSIDE SIMULATOR ---
            outside_counter += 1
            if outside_counter >= 150:
                outside_counter = 0
                outside_tick += 1

                current_out_temp = anchor_outside_temp + (5.0 * math.sin(outside_tick / 10.0))
                current_out_hum = anchor_outside_hum + (20.0 * math.cos(outside_tick / 15.0))

                last_calculated_out_temp = current_out_temp
                last_calculated_out_hum = current_out_hum

                state_mgr.dispatch(Event(type=EventType.TEMP_UPDATED, payload={"idx": 30001, "value": round(current_out_temp, 1), "from_simulator": True}))
                state_mgr.dispatch(Event(type=EventType.HUMIDITY_UPDATED, payload={"idx": 30001, "value": int(current_out_hum), "from_simulator": True}))

            # --- 2. BATHROOM 1eV SIMULATOR ---
            decay_rate = 1.0 if state.devices.get(71034) == "ON" else 0.1
            if bathroom1_hum > anchor_bathroom1_hum:
                bathroom1_hum = max(anchor_bathroom1_hum, bathroom1_hum - decay_rate)

            state_mgr.dispatch(Event(type=EventType.HUMIDITY_UPDATED, payload={"idx": 20004, "value": int(bathroom1_hum), "from_simulator": True}))

            # --- 3. SAUNA THERMODYNAMICS ---
            AMBIENT = 20.0
            pwm = state.sauna.modulation_pwm
            door_sauna_open = state.devices.get(10001) == "OPEN"

            heat_added = (pwm / 100.0) * 0.5
            temp_diff_high = max(0, sauna_high - AMBIENT)
            temp_diff_low = max(0, sauna_low - AMBIENT)
            heat_lost_high = temp_diff_high * 0.002
            heat_lost_low = temp_diff_low * 0.001

            if door_sauna_open:
                heat_lost_high += 1.0
                heat_lost_low += 0.5

            delta_high = (heat_added * 0.7) - heat_lost_high
            delta_low = (heat_added * 0.3) - heat_lost_low

            sauna_high = max(AMBIENT, round(sauna_high + delta_high, 2))
            sauna_low = max(AMBIENT, round(sauna_low + delta_low, 2))

            if heat_added > 0 and sauna_high_hum > 10.0:
                sauna_high_hum -= 0.1
                sauna_low_hum -= 0.05
            elif heat_added == 0 and sauna_high_hum < anchor_sauna_high_hum:
                sauna_high_hum += 0.05
                sauna_low_hum += 0.02

            state_mgr.dispatch(Event(type=EventType.TEMP_UPDATED, payload={"idx": 20001, "value": sauna_high, "from_simulator": True}))
            state_mgr.dispatch(Event(type=EventType.TEMP_UPDATED, payload={"idx": 20002, "value": sauna_low, "from_simulator": True}))
            state_mgr.dispatch(Event(type=EventType.HUMIDITY_UPDATED, payload={"idx": 20001, "value": int(sauna_high_hum), "from_simulator": True}))
            state_mgr.dispatch(Event(type=EventType.HUMIDITY_UPDATED, payload={"idx": 20002, "value": int(sauna_low_hum), "from_simulator": True}))

        except asyncio.CancelledError:
            break
        except Exception:
            pass