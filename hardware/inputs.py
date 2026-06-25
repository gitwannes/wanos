# --- file: hardware/inputs.py ---
import asyncio
from typing import Dict, Any
from core.models import Event, EventType
from core.state_manager import StateManager

try:
    import lgpio

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False


class HardwareInputs:
    """
    Domain A: Passive Inputs
    Pure lgpio C-threaded callbacks for extremely fast edge detection (Water, kWh, Doors).
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.logger = state_manager.logger
        self.config = state_manager._config
        self.loop = asyncio.get_event_loop()

        self.chip = None
        self.callbacks = []
        self._is_active = False

    async def start(self):
        """Pre-claims GPIO pins without enabling callbacks yet."""
        if not HARDWARE_AVAILABLE:
            await self.logger.warning("Hardware libraries missing. GPIO Inputs running in stub mode.")
            return

        try:
            self.chip = lgpio.gpiochip_open(0)

            # The event loop listens to the UI toggle to actually arm/disarm the interrupts
            self.state_manager.register_listener(self._on_state_changed)
            await self.logger.success("🟢 Physical Input Layer initialized (Standby).")

        except Exception as e:
            await self.logger.critical(f"Failed to initialize lgpio inputs: {e}")

    async def stop(self):
        """Gracefully releases resources to prevent memory leaks or locked pins on restart."""
        self._disarm_interrupts()
        if self.chip is not None:
            lgpio.gpiochip_close(self.chip)

    def _arm_interrupts(self):
        """Binds the high-speed background C-Thread edge detectors."""
        if not self.chip or self._is_active:
            return

        try:
            pin_cold = self.config.pins.water_cold
            pin_hot = self.config.pins.water_hot
            lgpio.gpio_claim_alert(self.chip, pin_cold, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
            lgpio.gpio_claim_alert(self.chip, pin_hot, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
            self.callbacks.append(lgpio.callback(self.chip, pin_cold, lgpio.FALLING_EDGE, self._on_water_cold))
            self.callbacks.append(lgpio.callback(self.chip, pin_hot, lgpio.FALLING_EDGE, self._on_water_hot))

            pin_kwh = self.config.pins.kwh_pin
            lgpio.gpio_claim_alert(self.chip, pin_kwh, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
            self.callbacks.append(lgpio.callback(self.chip, pin_kwh, lgpio.FALLING_EDGE, self._on_kwh))

            pin_door_sauna = self.config.pins.door_sauna
            pin_door_bath = self.config.pins.door_bathroom1
            lgpio.gpio_claim_alert(self.chip, pin_door_sauna, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
            lgpio.gpio_claim_alert(self.chip, pin_door_bath, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
            self.callbacks.append(lgpio.callback(self.chip, pin_door_sauna, lgpio.BOTH_EDGES, self._on_door_sauna))
            self.callbacks.append(lgpio.callback(self.chip, pin_door_bath, lgpio.BOTH_EDGES, self._on_door_bath))

            # Dispatch initial door states so the UI knows exactly how they stand upon arming
            self._dispatch_door(10001, lgpio.gpio_read(self.chip, pin_door_sauna))
            self._dispatch_door(10002, lgpio.gpio_read(self.chip, pin_door_bath))

            self._is_active = True

            # Broadcast successful physical hardware connection!
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_input", "connected": True}))

        except Exception as e:
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_input", "connected": False}))
            asyncio.create_task(self.logger.error(f"Failed to arm GPIO inputs: {e}"))

    def _disarm_interrupts(self):
        """Detaches callbacks so physics events are ignored."""
        for cb in self.callbacks:
            cb.cancel()
        self.callbacks.clear()
        self._is_active = False

    async def _on_state_changed(self, state, events):
        """Listens for the user explicitly turning the Input Bus ON or OFF in the Admin Panel."""
        if not HARDWARE_AVAILABLE:
            return

        enabled = state.hardware.gpio_input_enabled
        if enabled and not self._is_active:
            self._arm_interrupts()
        elif not enabled and self._is_active:
            self._disarm_interrupts()

    # =========================================================================
    # LGPIO Interrupt Handlers (Running in Background C-Thread)
    # MUST push via threadsafe!
    # =========================================================================
    def _on_water_cold(self, chip, gpio, level, tick):
        self.loop.call_soon_threadsafe(self.state_manager.dispatch,
                                       Event(type=EventType.WATER_PULSE, payload={"fluid": "cold", "count": 1}))

    def _on_water_hot(self, chip, gpio, level, tick):
        self.loop.call_soon_threadsafe(self.state_manager.dispatch,
                                       Event(type=EventType.WATER_PULSE, payload={"fluid": "hot", "count": 1}))

    def _on_kwh(self, chip, gpio, level, tick):
        self.loop.call_soon_threadsafe(self.state_manager.dispatch, Event(type=EventType.KWH_PULSE, payload={}))

    def _on_door_sauna(self, chip, gpio, level, tick):
        self._dispatch_door(10001, level)

    def _on_door_bath(self, chip, gpio, level, tick):
        self._dispatch_door(10002, level)

    def _dispatch_door(self, idx: int, level: int):
        is_open = bool(level)
        self.loop.call_soon_threadsafe(self.state_manager.dispatch,
                                       Event(type=EventType.DOOR_CHANGED, payload={"idx": idx, "is_open": is_open}))