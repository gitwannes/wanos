# --- file: hardware/sensors.py ---
import asyncio
from typing import Dict, Any
from core.models import Event, EventType, format_device_ref
from core.state_manager import StateManager
from logic.history_ids import SAUNA_CALC_IDX

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
        self._poll_wake = asyncio.Event()

    async def start(self):
        if not HARDWARE_AVAILABLE:
            await self.logger.warning("Hardware libraries missing. SHT11 polling running in stub mode.")
            return

        await self.logger.info("Initializing SHT11 active polling background sequence...")
        setattr(self.state_manager, "_sht11_poll_wake", self._poll_wake)
        self._polling_task = asyncio.create_task(self._sht11_polling_loop())

    def wake_poll(self) -> None:
        """Interrupt idle sleep so the next SHT11 read runs immediately (e.g. after UI arm)."""
        self._poll_wake.set()

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
                            await self.logger.info(
                                f"🟢 SHT11 sensor active: "
                                f"{format_device_ref(self.state_manager._state, node.idx)}."
                            )
                            sensor_status[node.idx] = True

                        error_counters[node.idx] = 0

                        # ⚡ Only pass the data to the brain if the user armed the SHT11 system in the UI
                        if state.hardware.sht11_enabled:
                            final_temp = round(temp * 2) / 2 if (0 <= temp < 99) else round(temp)
                            final_hum = round(humidity)
                            reading = (final_temp, final_hum)

                            if last_readings.get(node.idx) != reading:
                                last_readings[node.idx] = reading

                                self.state_manager.dispatch(
                                    Event(type=EventType.TEMP_UPDATED,
                                          payload={"idx": node.idx, "value": final_temp}))
                                self.state_manager.dispatch(Event(type=EventType.HUMIDITY_UPDATED,
                                                                  payload={"idx": node.idx, "value": final_hum}))
                            elif hasattr(self.state_manager, "sensor_history"):
                                # Stable T/RH: paired heartbeat (same ts for dew pairing).
                                self.state_manager.sensor_history.note_climate_reading(
                                    node.idx, final_temp, final_hum
                                )

                                # Reconcile sauna composite history (virtual idx 20101).
                                # The composite is normally updated only when TEMP/HUMIDITY events are dispatched,
                                # but stable heartbeat reads bypass those events.
                                if node.idx in [20001, 20002]:
                                    high = last_readings.get(20001)
                                    low = last_readings.get(20002)
                                    if (
                                        isinstance(high, tuple)
                                        and isinstance(low, tuple)
                                        and len(high) == 2
                                        and len(low) == 2
                                    ):
                                        t_high, h_high = high
                                        t_low, _h_low = low
                                        try:
                                            calc_t = round((float(t_high) * 0.7) + (float(t_low) * 0.3), 1)
                                            calc_h = int(float(h_high))
                                            self.state_manager.sensor_history.note_climate_reading(
                                                SAUNA_CALC_IDX, calc_t, float(calc_h)
                                            )
                                        except (TypeError, ValueError):
                                            pass

                    except Exception as e:
                        # ⚡ STATE-CHANGE LOGGING: Only log on initial boot or failure transition
                        if sensor_status.get(node.idx) is not False:
                            await self.logger.info(
                                f"🛑 SHT11 sensor DEAD: "
                                f"{format_device_ref(self.state_manager._state, node.idx)}."
                            )
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

            # Fast poll while armed but sauna composite not ready yet; else normal cadence.
            if state.hardware.sht11_enabled and state.sensors.sauna_calc_temp is None:
                sleep_cadence = 2.0
            elif state.sauna.active:
                sleep_cadence = 10.0
            else:
                sleep_cadence = 60.0
            self._poll_wake.clear()
            try:
                await asyncio.wait_for(self._poll_wake.wait(), timeout=sleep_cadence)
            except asyncio.TimeoutError:
                pass