# --- file: hardware/actuators.py ---
import asyncio
from typing import List
from core.models import Event, SystemState
from core.state_manager import StateManager
from core.logger import WanosComponent

try:
    import lgpio

    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False


class HardwareActuators(WanosComponent):
    """
    Domain C: High-Voltage Outputs (The Muscle)
    Pure lgpio output generation. Strictly enforces the Master Safety Contactor logic
    and safely distributes asymmetric PWM targets to U, V, W phases.
    """

    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)
        self.config = state_manager._config
        self.chip = None
        self.output_armed = False

        self.pin_safety = self.config.pins.safety_gpio
        self.pin_ir = self.config.pins.ir_relais
        self.pin_u = self.config.pins.sauna_relais_phase_U
        self.pin_v = self.config.pins.sauna_relais_phase_V
        self.pin_w = self.config.pins.sauna_relais_phase_W

        self.sauna_freq = getattr(self.config.sauna, "pwm_freq", 5)

    async def start(self):
        if not HARDWARE_AVAILABLE:
            await self.logger.warning("Hardware libraries missing. Actuators running in stub mode.")
            return

        try:
            self.chip = lgpio.gpiochip_open(0)

            # Claim all output pins for exclusive control
            lgpio.gpio_claim_output(self.chip, self.pin_safety)
            lgpio.gpio_claim_output(self.chip, self.pin_ir)
            lgpio.gpio_claim_output(self.chip, self.pin_u)
            lgpio.gpio_claim_output(self.chip, self.pin_v)
            lgpio.gpio_claim_output(self.chip, self.pin_w)

            # Ensure everything starts in a definitively OFF state
            self._force_all_off()

            # Broadcast successful physical hardware connection!
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_output", "connected": True}))

            # Subscribe to the core WanOS state engine
            self.state_manager.register_listener(self._on_state_changed)

            await self.logger.success("🟢 High-Voltage Physical Output Layer mounted.")

        except Exception as e:
            self.state_manager.dispatch(
                Event(type=EventType.HARDWARE_BUS_HEALTH_UPDATED, payload={"bus": "gpio_output", "connected": False}))
            await self.logger.critical(f"Failed to initialize lgpio actuators: {e}")

    def _force_all_off(self):
        """Forces all control pins LOW immediately. Safest default state."""
        if self.chip is None: return

        # 1. Stop all PWM flows and write pins LOW
        lgpio.tx_pwm(self.chip, self.pin_ir, 5, 0)
        lgpio.gpio_write(self.chip, self.pin_ir, 0)

        lgpio.tx_pwm(self.chip, self.pin_u, 5, 0)
        lgpio.gpio_write(self.chip, self.pin_u, 0)

        lgpio.tx_pwm(self.chip, self.pin_v, 5, 0)
        lgpio.gpio_write(self.chip, self.pin_v, 0)

        lgpio.tx_pwm(self.chip, self.pin_w, 5, 0)
        lgpio.gpio_write(self.chip, self.pin_w, 0)

        # 2. Drop Safety Contactor Relay
        lgpio.gpio_write(self.chip, self.pin_safety, 0)

    async def _aggressive_failsafe_check(self):
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

    async def stop(self):
        """Clean shutdown sequence with aggressive verification."""
        await self.logger.warning("Shutting down high-voltage hardware actuators...")
        self._force_all_off()

        if HARDWARE_AVAILABLE:
            await self._aggressive_failsafe_check()
            if self.chip is not None:
                lgpio.gpiochip_close(self.chip)

    async def _on_state_changed(self, state: SystemState, events: List[Event] = None):
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
            await self.logger.warning("⚠️ ARMING HIGH-VOLTAGE OUTPUT BUS! Driving Safety Contactor HIGH.")
            # Sequence: Drive Pin 4 HIGH first to close the physical contactor
            lgpio.gpio_write(self.chip, self.pin_safety, 1)
            # Give the mechanical relay 100ms to click shut before allowing PWM to pass
            await asyncio.sleep(0.1)
            self.output_armed = True

        elif not is_armed and self.output_armed:
            await self.logger.warning("🛑 DISARMING HIGH-VOLTAGE OUTPUT BUS! Safely draining lines.")
            # Sequence: Stop all PWM and set SSR lines to 0V first to prevent arcing
            self.output_armed = False
            self._force_all_off()  # This also drops the Safety pin
            return

        if not self.output_armed:
            return

        # ---------------------------------------------------------------------
        # 1. Update IR Single-Phase Modulation
        # ---------------------------------------------------------------------
        if state.ir.active:
            lgpio.tx_pwm(self.chip, self.pin_ir, state.ir.frequency, state.ir.modulation_pwm)
        else:
            lgpio.tx_pwm(self.chip, self.pin_ir, 5, 0)
            lgpio.gpio_write(self.chip, self.pin_ir, 0)

        # ---------------------------------------------------------------------
        # 2. Update Sauna 3-Phase Modulation
        # Explicit mapping ensures index errors cannot accidentally overload the elements!
        # ---------------------------------------------------------------------
        if state.sauna.active:
            phases = state.sauna.phases_pwm
            lgpio.tx_pwm(self.chip, self.pin_u, self.sauna_freq, phases.get("U", 0))
            lgpio.tx_pwm(self.chip, self.pin_v, self.sauna_freq, phases.get("V", 0))
            lgpio.tx_pwm(self.chip, self.pin_w, self.sauna_freq, phases.get("W", 0))
        else:
            lgpio.tx_pwm(self.chip, self.pin_u, self.sauna_freq, 0)
            lgpio.tx_pwm(self.chip, self.pin_v, self.sauna_freq, 0)
            lgpio.tx_pwm(self.chip, self.pin_w, self.sauna_freq, 0)

            lgpio.gpio_write(self.chip, self.pin_u, 0)
            lgpio.gpio_write(self.chip, self.pin_v, 0)
            lgpio.gpio_write(self.chip, self.pin_w, 0)