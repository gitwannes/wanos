# --- file: hardware/inputs.py ---
import asyncio
import functools
from typing import Dict, Any, Optional
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
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        self.chip = None
        self.callbacks = []
        self._is_active = False

    async def start(self):
        """Pre-claims GPIO pins without enabling callbacks yet."""
        if not HARDWARE_AVAILABLE:
            await self.logger.warning("Hardware libraries missing. GPIO Inputs running in stub mode.")
            return

        try:
            # ⏱️ Active Event Loop Retrieval:
            # Captures the running event loop instance managed by Uvicorn rather than an import-time loop.
            self.loop = asyncio.get_running_loop()

            # ⚡ Shared Chip Registry Pattern:
            # Reuses an existing open chip handle from the state manager context to avoid resource conflicts.
            # This completely circumvents libgpiod resource locks and eliminates the startup hang.
            if hasattr(self.state_manager, "_shared_gpio_chip") and getattr(self.state_manager,
                                                                            "_shared_gpio_chip") is not None:
                self.chip = getattr(self.state_manager, "_shared_gpio_chip")
            else:
                self.chip = lgpio.gpiochip_open(0)
                setattr(self.state_manager, "_shared_gpio_chip", self.chip)

            # Track active references to the shared chip to prevent premature closure during shutdown
            if not hasattr(self.state_manager, "_shared_chip_users"):
                setattr(self.state_manager, "_shared_chip_users", set())
            getattr(self.state_manager, "_shared_chip_users").add("inputs")

            # Broadcast successful physical hardware connection immediately to satisfy the bouncer!
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_input", "connected": True}))

            # The event loop listens to the UI toggle to actually arm/disarm the interrupts
            self.state_manager.register_listener(self._on_state_changed)
            await self.logger.success("🟢 Physical Input Layer initialized (Standby).")

        except Exception as e:
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_input", "connected": False}))
            await self.logger.critical(f"Failed to initialize lgpio inputs: {e}")

    async def stop(self):
        """Gracefully releases resources to prevent memory leaks or locked pins on restart."""
        self._disarm_interrupts()

        # ⚡ Reference-Counting Teardown Strategy:
        # Removes this component from the active user registry. The absolute last hardware component
        # to stop takes responsibility for closing the shared kernel chip handle, preventing deadlocks.
        if hasattr(self.state_manager, "_shared_chip_users"):
            getattr(self.state_manager, "_shared_chip_users").discard("inputs")
            if not getattr(self.state_manager, "_shared_chip_users"):
                if self.chip is not None:
                    lgpio.gpiochip_close(self.chip)
                    setattr(self.state_manager, "_shared_gpio_chip", None)

    def _arm_interrupts(self):
        """Binds the high-speed background C-Thread edge detectors dynamically from config."""
        # ⚡ ZERO-EVALUATION FIX: Explicitly check for None so valid handles of `0` are not skipped
        if self.chip is None or self._is_active:
            return

        try:
            # ⚡ DYNAMIC CALLBACK FACTORY
            # Loops through the declarative config and binds C-thread interrupts using functools.partial
            # to safely lock the specific IDX into the memory of the callback.
            if hasattr(self.config, "gpio_inputs") and self.config.gpio_inputs:
                for key, node in self.config.gpio_inputs.items():
                    if node.idx is None:
                        continue

                    # 1. Determine electrical edge requirement based on semantic type
                    # Doors need both edges (open/close). Pulse meters only need the falling edge.
                    edge = lgpio.BOTH_EDGES if node.type == "door" else lgpio.FALLING_EDGE

                    # 2. Claim the pin
                    lgpio.gpio_claim_alert(self.chip, node.pin, edge, lgpio.SET_PULL_UP)

                    # 3. Bind and store the callback
                    cb_func = functools.partial(self._on_gpio_edge, idx=node.idx, node_type=node.type)
                    self.callbacks.append(lgpio.callback(self.chip, node.pin, edge, cb_func))

                    # 4. If it's a stateful door, instantly read and dispatch its physical baseline
                    if node.type == "door":
                        initial_level = lgpio.gpio_read(self.chip, node.pin)
                        self._dispatch_door(node.idx, initial_level)

            self._is_active = True

        except Exception as e:
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
    def _on_gpio_edge(self, chip: int, gpio: int, level: int, tick: int, idx: int, node_type: str) -> None:
        """Universal edge handler bound to specific IDXs via functools.partial."""
        if node_type == "door":
            self._dispatch_door(idx, level)
        elif node_type == "fluid":
            self.loop.call_soon_threadsafe(self.state_manager.dispatch,
                                           Event(type=EventType.WATER_PULSE, payload={"idx": idx, "count": 1}))
        elif node_type == "energy":
            self.loop.call_soon_threadsafe(self.state_manager.dispatch,
                                           Event(type=EventType.KWH_PULSE, payload={"idx": idx}))

    def _dispatch_door(self, idx: int, level: int) -> None:
        is_open = bool(level)
        self.loop.call_soon_threadsafe(self.state_manager.dispatch,
                                       Event(type=EventType.DOOR_CHANGED, payload={"idx": idx, "is_open": is_open}))