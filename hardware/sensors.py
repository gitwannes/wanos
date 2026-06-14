# --- file: hardware/sensors.py ---
import asyncio
from typing import Dict
from core.models import Event, EventType
from core.state_manager import StateManager

# Conditional import for physical hardware. Fails safely on PC/Lab environments.
try:
    import RPi.GPIO as GPIO
    from pi_sht1x import SHT1x as SHT11

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False


async def physical_sensor_polling_loop(state_manager: StateManager) -> None:
    """
    Production Mode: Polls the physical SHT11 sensors on the Raspberry Pi GPIOs.
    Retains the legacy polling logic and error retry mechanisms but routes data
    via the new Unidirectional Event Queue.
    """
    if not HARDWARE_AVAILABLE:
        await state_manager.logger.warning("SHT11 library or GPIO not found. Skipping physical sensor loop.")
        return

    await state_manager.logger.success("🟢 Physical SHT11 sensor polling started.")

    # Mapped from legacy ws['fix']['sht11-sensors']
    # Format: { index: (Data_Pin, Clock_Pin, sensor_id_string) }
    SENSOR_MAP: Dict[int, tuple] = {
        0: (11, 23, "bathroom"),
        1: (15, 24, "cinema"),
        2: (16, 25, "sauna_high"),
        3: (18, 8, "sauna_low")
    }

    # Track consecutive failures per sensor (legacy maxpoltrieslev2 logic)
    error_counters = {0: 0, 1: 0, 2: 0, 3: 0}

    # ⚡ EARLY GATE DUPLICATE FILTER ⚡
    last_readings = {}
    MAX_RETRIES = 2

    while True:
        state = state_manager.get_state_snapshot()

        # Only poll if we are in live hardware mode
        if state.hardware.live_mode:
            for sensor_idx, (pin_d, pin_c, sensor_id) in SENSOR_MAP.items():
                try:
                    # Legacy SHT11 Initialization
                    sensor = SHT11(pin_d, pin_c, gpio_mode=GPIO.BCM, vdd='5V')
                    temp = sensor.read_temperature()
                    humidity = sensor.read_humidity(temp)

                    # Rounding logic from legacy codebase
                    final_temp = round(temp * 2) / 2 if (0 <= temp < 99) else round(temp)
                    final_hum = round(humidity)

                    # Check if the environment actually changed
                    if last_readings.get(sensor_id) == (final_temp, final_hum):
                        await state_manager.logger.debug(
                            f"[SHT11] Node '{sensor_id}' update ignored (duplicate: already {final_temp}°C, {final_hum}%)")
                    else:
                        last_readings[sensor_id] = (final_temp, final_hum)

                        # Dispatch explicit events for this specific sensor target
                        state_manager.dispatch(Event(
                            type=EventType.TEMP_UPDATED,
                            payload={"sensor_id": sensor_id, "value": final_temp}
                        ))
                        state_manager.dispatch(Event(
                            type=EventType.HUMIDITY_UPDATED,
                            payload={"sensor_id": sensor_id, "value": final_hum}
                        ))

                    # Reset error counter on success
                    error_counters[sensor_idx] = 0

                except Exception as e:
                    error_counters[sensor_idx] += 1
                    await state_manager.logger.error(
                        f"Poll failed for sensor {sensor_id} (D{pin_d}/C{pin_c}). Attempt {error_counters[sensor_idx]}/{MAX_RETRIES}. Error: {e}"
                    )

                    if error_counters[sensor_idx] >= MAX_RETRIES:
                        # Report persistent sensor error to the core queue
                        state_manager.dispatch(Event(
                            type=EventType.SENSOR_ERROR,
                            payload={"sensor": sensor_id, "error": str(e)}
                        ))
                        # If critical sauna sensors fail, the StateManager can trigger an emergency stop

                # Small delay between polling individual sensors to prevent bus collision
                await asyncio.sleep(0.5)

        # Main polling interval (1 minute default, adjust based on active states)
        await asyncio.sleep(60.0)