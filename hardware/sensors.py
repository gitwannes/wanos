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
        error_counters = {}
        last_readings = {}
        sensor_status = {}  # ⚡ Tracks explicit ALIVE/DEAD state for clean logging
        MAX_RETRIES = 2

        # Helper method to run the blocking C-library code safely outside the asyncio loop
        def _read_sensor_sync(d_pin: int, c_pin: int) -> tuple[float, float]:
            s = SHT11(d_pin, c_pin, gpio_mode=GPIO.BCM, vdd='5V')
            t = s.read_temperature()
            h = s.read_humidity(t)
            return t, h

        while True:
            state = self.state_manager.get_state_snapshot()
            any_sensor_replied = False

            # ⚡ DYNAMIC LOOP: Iterate over the declarative entity map instead of hardcoded logic
            if hasattr(self.config, "sht11_sensors") and self.config.sht11_sensors:
                for key, node in self.config.sht11_sensors.items():
                    if node.idx not in error_counters:
                        error_counters[node.idx] = 0

                    try:
                        # ⚡ Offloaded blocking bit-bang operations to a background thread to prevent freezing the Asyncio Event Loop
                        temp, humidity = await asyncio.to_thread(_read_sensor_sync, node.pin_d, node.pin_c)

                        # If we got this far without throwing an exception, the physical bus is alive!
                        any_sensor_replied = True

                        # ⚡ STATE-CHANGE LOGGING: Only log on initial boot or recovery transition
                        if sensor_status.get(node.idx) is not True:
                            await self.logger.info(f"🟢 SHT11 sensor active: {node.name} (idx {node.idx}).")
                            sensor_status[node.idx] = True

                        error_counters[node.idx] = 0

                        # ⚡ Only pass the data to the brain if the user armed the SHT11 system in the UI
                        if state.hardware.sht11_enabled:
                            final_temp = round(temp * 2) / 2 if (0 <= temp < 99) else round(temp)
                            final_hum = round(humidity)

                            if last_readings.get(node.idx) != (final_temp, final_hum):
                                last_readings[node.idx] = (final_temp, final_hum)

                                self.state_manager.dispatch(
                                    Event(type=EventType.TEMP_UPDATED,
                                          payload={"idx": node.idx, "value": final_temp}))
                                self.state_manager.dispatch(Event(type=EventType.HUMIDITY_UPDATED,
                                                                  payload={"idx": node.idx, "value": final_hum}))

                    except Exception as e:
                        # ⚡ STATE-CHANGE LOGGING: Only log on initial boot or failure transition
                        if sensor_status.get(node.idx) is not False:
                            await self.logger.info(f"🛑 SHT11 sensor DEAD: {node.name} (idx {node.idx}).")
                            sensor_status[node.idx] = False

                        error_counters[node.idx] += 1

                        if error_counters[node.idx] >= MAX_RETRIES:
                            # ⚡ FAILSAFE POISON PILL: Force the temperature to None so the State Manager instantly kills the sauna!
                            if last_readings.get(node.idx) is not None:
                                last_readings[node.idx] = None
                                self.state_manager.dispatch(
                                    Event(type=EventType.TEMP_UPDATED, payload={"idx": node.idx, "value": None}))
                                self.state_manager.dispatch(
                                    Event(type=EventType.HUMIDITY_UPDATED,
                                          payload={"idx": node.idx, "value": None}))

                            # Only warn the user if they actually care about the sensors (enabled)
                            if state.hardware.sht11_enabled:
                                self.state_manager.dispatch(
                                    Event(type=EventType.SENSOR_ERROR, payload={"idx": node.idx,
                                                                                "error": f"Probe {node.name} unreachable: {str(e)}"}))

                    # Yield back to the event loop so the web server can process other requests
                    await asyncio.sleep(0.5)

                # ⚡ Dynamic Health Feedback: Alert the UI immediately if the physical wire gets unplugged
            if any_sensor_replied != self._is_physically_connected:
                self._is_physically_connected = any_sensor_replied
                self.state_manager.dispatch(Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED,
                                                  payload={"bus": "sht11", "connected": any_sensor_replied}))

            await asyncio.sleep(60.0)