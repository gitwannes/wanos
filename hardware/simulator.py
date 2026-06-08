# --- file: hardware/simulator.py ---
import asyncio
from core.state_manager import StateManager
from core.models import Event, EventType


async def lab_mode_thermodynamics_loop(state_mgr: StateManager):
    """
    Simulates realistic sauna thermodynamics when physical hardware is detached.
    Listens to the PID output and calculates simulated heat gain and loss.
    """
    await asyncio.sleep(5.0)  # Give the server a few seconds to boot before starting

    while True:
        try:
            await asyncio.sleep(2.0)  # Evaluate physics every 2 seconds

            state = state_mgr.get_state_snapshot()

            # If we transition to live hardware, or temp hasn't been seeded yet, skip physics
            if state.hardware.live_mode or state.sauna.current_temp is None:
                continue

            current_temp = state.sauna.current_temp
            pwm = state.sauna.modulation_pwm
            door_open = state.sauna.door_open

            # --- Thermodynamic Math ---
            AMBIENT = 20.0

            # 1. Heat injection (Increased to 0.5°C per 2-second tick at 100% power)
            # Simulates a powerful 9kW system heating the air volume quickly.
            heat_added = (pwm / 100.0) * 0.5

            # 2. Ambient heat loss (Properly insulated wooden room)
            # A factor of 0.002 means at 80°C (60°C difference from ambient),
            # the room loses 0.12°C per tick.
            # To counteract this, the PID only needs exactly 24% PWM to maintain 80°C!
            temp_diff = max(0, current_temp - AMBIENT)
            heat_lost = temp_diff * 0.002

            # 3. Door open heat dump (Massive heat loss if door is opened)
            if door_open:
                heat_lost += 1.0  # Increased from 0.5 so opening the door really crashes the temp

            # Calculate new temperature
            delta = heat_added - heat_lost
            new_temp = round(current_temp + delta, 2)

            # Floor the temperature at room ambient (sauna can't cool below the room temp)
            new_temp = max(AMBIENT, new_temp)

            # If the temperature changed, inject it into the bouncer
            if new_temp != current_temp:
                state_mgr.dispatch(Event(type=EventType.TEMP_UPDATED, payload={"value": new_temp}))

        except asyncio.CancelledError:
            # Catch shutdown signal gracefully
            break
        except Exception:
            # Silently catch math errors so the simulator doesn't crash the loop
            pass