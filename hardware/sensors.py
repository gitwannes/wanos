# --- file: hardware/sensors.py ---
import asyncio
from typing import Dict, Any
from core.models import Event, EventType
from core.state_manager import StateManager

try:
    import RPi.GPIO as GPIO
    from pi_sht1x import SHT1x as SHT11

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False


class HardwareSensors:
    """
    Domain B: Active Polling (pi_sht1x)
    Bit-bangs the physical temperature probes. Isolated into its own file because
    this library blocks its thread to read clock edges, preventing interference with the lgpio inputs.
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.logger = state_manager.logger
        self.config = state_manager._config
        self._polling_task = None
        self._is_physically_connected = False

    async def start(self):
        if not HARDWARE_AVAILABLE:
            await self.logger.warning("Hardware libraries missing. SHT11 polling running in stub mode.")
            return

        await self.logger.info("Initializing SHT11 active polling background sequence...")
        self._polling_task = asyncio.create_task(self._sht11_polling_loop())

    async def stop(self):
        if self._polling_task:
            self._polling_task.cancel()
        if HARDWARE_AVAILABLE:
            # ONLY clean up the specific pins used by SHT11 so we don't nuke the lgpio inputs
            GPIO.cleanup()

    async def _sht11_polling_loop(self):
        """
        Runs infinitely in the background. It ALWAYS queries the pins to verify physical connection health,
        but it ONLY dispatches the temperature reading to the engine if the UI toggle is ON!
        """
        SENSOR_MAP = {
            0: (self.config.sensors["bathroom1"].pin_d, self.config.sensors["bathroom1"].pin_c, "bathroom1", 20004),
            1: (self.config.sensors["cinema"].pin_d, self.config.sensors["cinema"].pin_c, "cinema", 20003),
            2: (self.config.sensors["sauna_high"].pin_d, self.config.sensors["sauna_high"].pin_c, "sauna_high", 20001),
            3: (self.config.sensors["sauna_low"].pin_d, self.config.sensors["sauna_low"].pin_c, "sauna_low", 20002)
        }

        error_counters = {0: 0, 1: 0, 2: 0, 3: 0}
        last_readings = {}
        MAX_RETRIES = 2

        while True:
            state = self.state_manager.get_state_snapshot()

            any_sensor_replied = False

            for sensor_idx, (pin_d, pin_c, semantic_name, virtual_idx) in SENSOR_MAP.items():
                try:
                    # Instantiating the object natively touches the RPi.GPIO pins
                    sensor = SHT11(pin_d, pin_c, gpio_mode=GPIO.BCM, vdd='5V')
                    temp = sensor.read_temperature()
                    humidity = sensor.read_humidity(temp)

                    # If we got this far without throwing an exception, the physical bus is alive!
                    any_sensor_replied = True
                    error_counters[sensor_idx] = 0

                    # ⚡ Only pass the data to the brain if the user armed the SHT11 system in the UI
                    if state.hardware.sht11_enabled:
                        final_temp = round(temp * 2) / 2 if (0 <= temp < 99) else round(temp)
                        final_hum = round(humidity)

                        if last_readings.get(virtual_idx) != (final_temp, final_hum):
                            last_readings[virtual_idx] = (final_temp, final_hum)

                            self.state_manager.dispatch(
                                Event(type=EventType.TEMP_UPDATED, payload={"idx": virtual_idx, "value": final_temp}))
                            self.state_manager.dispatch(Event(type=EventType.HUMIDITY_UPDATED,
                                                              payload={"idx": virtual_idx, "value": final_hum}))

                except Exception as e:
                    error_counters[sensor_idx] += 1

                    if error_counters[sensor_idx] >= MAX_RETRIES:
                        # Only warn the user if they actually care about the sensors (enabled)
                        if state.hardware.sht11_enabled:
                            self.state_manager.dispatch(
                                Event(type=EventType.SENSOR_ERROR, payload={"idx": virtual_idx, "error": str(e)}))

                await asyncio.sleep(0.5)

                # ⚡ Dynamic Health Feedback: Alert the UI immediately if the physical wire gets unplugged
            if any_sensor_replied != self._is_physically_connected:
                self._is_physically_connected = any_sensor_replied
                self.state_manager.dispatch(Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED,
                                                  payload={"bus": "sht11", "connected": any_sensor_replied}))

            await asyncio.sleep(60.0)