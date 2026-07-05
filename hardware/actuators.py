# --- file: hardware/actuators.py ---
import asyncio
from typing import List, Dict
from core.models import Event, SystemState, EventType
from core.state_manager import StateManager
from core.logger import WanosComponent

try:
    import lgpio

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False


class HardwareActuators(WanosComponent):
    """
    Domain C: GPIO Outputs (The Muscle)
    Software-Timed PWM output generation. Strictly enforces the Master Safety Contactor logic
    and safely distributes asymmetric PWM targets to U, V, W phases without invoking kernel hardware-PWM locks.
    """

    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)
        self.config = state_manager._config
        self.chip = None
        self.output_armed: bool = False

        self.pin_safety: int = self.config.pins.safety_gpio
        self.pin_ir: int = self.config.pins.ir_relais
        self.pin_u: int = self.config.pins.sauna_relais_phase_U
        self.pin_v: int = self.config.pins.sauna_relais_phase_V
        self.pin_w: int = self.config.pins.sauna_relais_phase_W

        self.sauna_freq: int = getattr(self.config.sauna, "pwm_freq", 5)

        # ⚡ RAM targets for the software PWM background workers
        self.pwm_targets: Dict[str, int] = {"IR": 0, "U": 0, "V": 0, "W": 0}
        self.pwm_tasks: List[asyncio.Task] = []

    async def _software_pwm_worker(self, pin: int, channel: str, freq: int) -> None:
        """
        Background task that manually toggles a GPIO pin to simulate PWM.
        Uses asyncio.sleep() to yield control back to the main event loop,
        preventing hardware lockups on shared kernel peripheral blocks.
        """
        period = 1.0 / freq
        while True:
            try:
                target_pwm = self.pwm_targets.get(channel, 0)

                # If disarmed or 0%, hold LOW and sleep for the entire cycle
                if not self.output_armed or target_pwm <= 0:
                    if self.chip is not None:
                        lgpio.gpio_write(self.chip, pin, 0)
                    await asyncio.sleep(period)
                    continue

                # If 100%, hold HIGH and sleep for the entire cycle
                if target_pwm >= 100:
                    if self.chip is not None:
                        lgpio.gpio_write(self.chip, pin, 1)
                    await asyncio.sleep(period)
                    continue

                # Calculate fractional ON and OFF times for the cycle
                on_time = period * (target_pwm / 100.0)
                off_time = period - on_time

                # Execute PWM HIGH phase
                if self.chip is not None:
                    lgpio.gpio_write(self.chip, pin, 1)
                await asyncio.sleep(on_time)

                # If the system disarmed mid-pulse, abort the HIGH cycle immediately
                if not self.output_armed:
                    if self.chip is not None:
                        lgpio.gpio_write(self.chip, pin, 0)
                    await asyncio.sleep(off_time)
                    continue

                # Execute PWM LOW phase
                if self.chip is not None:
                    lgpio.gpio_write(self.chip, pin, 0)
                await asyncio.sleep(off_time)

            except asyncio.CancelledError:
                # Guarantee the pin drops to 0V when task is terminated during shutdown
                if self.chip is not None:
                    lgpio.gpio_write(self.chip, pin, 0)
                break
            except Exception as e:
                await self.logger.error(f"Error in Software PWM worker {channel}: {e}")
                await asyncio.sleep(1.0)  # Prevent tight loop on error

    async def start(self) -> None:
        if not HARDWARE_AVAILABLE:
            await self.logger.warning("Hardware libraries missing. Actuators running in stub mode.")
            return

        try:
            # ⚡ UNIFIED HARDWARE HANDLE REGISTRY PATTERN:
            # Reuses an existing open chip handle stored on the state manager context if available.
            if hasattr(self.state_manager, "_shared_gpio_chip") and getattr(self.state_manager,
                                                                            "_shared_gpio_chip") is not None:
                self.chip = getattr(self.state_manager, "_shared_gpio_chip")
            else:
                self.chip = lgpio.gpiochip_open(0)
                setattr(self.state_manager, "_shared_gpio_chip", self.chip)

            # Track active references to the shared chip to prevent premature closure during shutdown
            if not hasattr(self.state_manager, "_shared_chip_users"):
                setattr(self.state_manager, "_shared_chip_users", set())
            getattr(self.state_manager, "_shared_chip_users").add("actuators")

            # Claim all output pins for exclusive control as standard digital outputs
            lgpio.gpio_claim_output(self.chip, self.pin_safety)
            lgpio.gpio_claim_output(self.chip, self.pin_ir)
            lgpio.gpio_claim_output(self.chip, self.pin_u)
            lgpio.gpio_claim_output(self.chip, self.pin_v)
            lgpio.gpio_claim_output(self.chip, self.pin_w)

            # Ensure everything starts in a definitively OFF state
            self._force_all_off()

            # ⚡ Spin up the 4 asynchronous Software PWM Workers (Locked at 5 Hz)
            self.pwm_tasks = [
                asyncio.create_task(self._software_pwm_worker(self.pin_ir, "IR", 5)),
                asyncio.create_task(self._software_pwm_worker(self.pin_u, "U", self.sauna_freq)),
                asyncio.create_task(self._software_pwm_worker(self.pin_v, "V", self.sauna_freq)),
                asyncio.create_task(self._software_pwm_worker(self.pin_w, "W", self.sauna_freq))
            ]

            # Broadcast successful physical hardware connection!
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_output", "connected": True}))

            # Subscribe to the core WanOS state engine
            self.state_manager.register_listener(self._on_state_changed)

            await self.logger.success("🟢 GPIO Output pins claimed (Bus is safely DISARMED). Software PWM active.")

        except Exception as e:
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_output", "connected": False}))
            await self.logger.critical(f"Failed to initialize lgpio actuators: {e}")

    def _force_all_off(self) -> None:
        """Forces all control targets and physical pins LOW immediately. Safest default state."""
        self.pwm_targets = {"IR": 0, "U": 0, "V": 0, "W": 0}
        if self.chip is None: return

        # Stop all physical flows by writing pins LOW
        lgpio.gpio_write(self.chip, self.pin_ir, 0)
        lgpio.gpio_write(self.chip, self.pin_u, 0)
        lgpio.gpio_write(self.chip, self.pin_v, 0)
        lgpio.gpio_write(self.chip, self.pin_w, 0)

        # Drop Safety Contactor Relay
        lgpio.gpio_write(self.chip, self.pin_safety, 0)

    async def _aggressive_failsafe_check(self) -> None:
        """Legacy 250-sample loop over 1 second to physically guarantee the SSR pins dropped."""
        if self.chip is None: return

        tst = 0
        for _ in range(250):
            tst += lgpio.gpio_read(self.chip, self.pin_ir)
            tst += lgpio.gpio_read(self.chip, self.pin_u)
            tst += lgpio.gpio_read(self.chip, self.pin_v)
            tst += lgpio.gpio_read(self.chip, self.pin_w)
            await asyncio.sleep(0.004)  # 4ms * 250 = 1000ms (1 sec)

        if tst > 0:
            await self.logger.critical(
                "🚨 HARDWARE FAILSAFE: SSRs detected HIGH after shutdown sequence! Check relays immediately.")
        else:
            await self.logger.success("Hardware Failsafe: All SSRs verified LOW.")

    async def stop(self) -> None:
        """Clean shutdown sequence with aggressive verification."""
        await self.logger.warning("Shutting down GPIO hardware actuators...")
        self.output_armed = False

        # 1. Cancel background Software PWM worker tasks
        for task in self.pwm_tasks:
            task.cancel()
        if self.pwm_tasks:
            await asyncio.gather(*self.pwm_tasks, return_exceptions=True)

        # 2. Force physical lines low
        self._force_all_off()

        if HARDWARE_AVAILABLE:
            await self._aggressive_failsafe_check()

            # ⚡ Reference-Counting Teardown Strategy:
            if hasattr(self.state_manager, "_shared_chip_users"):
                getattr(self.state_manager, "_shared_chip_users").discard("actuators")
                if not getattr(self.state_manager, "_shared_chip_users"):
                    if self.chip is not None:
                        lgpio.gpiochip_close(self.chip)
                        setattr(self.state_manager, "_shared_gpio_chip", None)

    async def _on_state_changed(self, state: SystemState, events: List[Event] = None) -> None:
        """
        Called automatically by WanOS whenever any state changes.
        """
        if not HARDWARE_AVAILABLE or self.chip is None:
            return

        # ---------------------------------------------------------------------
        # MASTER OUTPUT ARMING CIRCUIT
        # ---------------------------------------------------------------------
        is_armed = state.hardware.gpio_output_enabled

        if is_armed and not self.output_armed:
            await self.logger.warning("⚠️ ARMING GPIO OUTPUT BUS! Driving Safety Contactor HIGH.")
            # Sequence: Drive Pin 4 HIGH first to close the physical contactor
            lgpio.gpio_write(self.chip, self.pin_safety, 1)
            # Give the mechanical relay 100ms to click shut before allowing PWM to pass
            await asyncio.sleep(0.1)
            self.output_armed = True

        elif not is_armed and self.output_armed:
            await self.logger.warning("🛑 DISARMING GPIO OUTPUT BUS! Safely draining lines.")
            # Sequence: Drop targets to 0 and set SSR lines to 0V first to prevent arcing
            self.output_armed = False
            self._force_all_off()  # This also drops the Safety pin
            return

        if not self.output_armed:
            self.pwm_targets = {"IR": 0, "U": 0, "V": 0, "W": 0}
            return

        # ---------------------------------------------------------------------
        # 1. Update IR Single-Phase Modulation Targets
        # ---------------------------------------------------------------------
        if state.ir.active:
            self.pwm_targets["IR"] = state.ir.modulation_pwm
        else:
            self.pwm_targets["IR"] = 0

        # ---------------------------------------------------------------------
        # 2. Update Sauna 3-Phase Modulation Targets
        # Explicit mapping ensures index errors cannot accidentally overload the elements!
        # ---------------------------------------------------------------------
        if state.sauna.active:
            phases = state.sauna.phases_pwm
            self.pwm_targets["U"] = phases.get("U", 0)
            self.pwm_targets["V"] = phases.get("V", 0)
            self.pwm_targets["W"] = phases.get("W", 0)
        else:
            self.pwm_targets["U"] = 0
            self.pwm_targets["V"] = 0
            self.pwm_targets["W"] = 0