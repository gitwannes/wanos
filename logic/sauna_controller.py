# --- file: logic/sauna_controller.py ---
import time
from itertools import permutations
from typing import Tuple, Optional, Dict, Any
from core.models import SystemState


class PID:
    """Integrated Wisc PID Controller for Sauna Heating."""

    def __init__(
            self,
            kp: float = 1.0,
            ki: float = 0.0,
            kd: float = 0.0,
            setpoint: float = 0.0,
            output_limits: Tuple[Optional[float], Optional[float]] = (0.0, 100.0)
    ):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.setpoint = setpoint
        self._min_output, self._max_output = output_limits
        self.reset()

    def reset(self) -> None:
        """Resets controller internals back to clean baseline states."""
        self._proportional = 0.0
        self._integral = 0.0
        self._derivative = 0.0
        self._last_time: Optional[float] = None
        self._last_input: Optional[float] = None

    def compute(self, current_input: float, current_time: float) -> float:
        """
        Computes the PID output based on an injected system timestamp.
        Allows deterministic calculations across live deployment and simulation environments.
        """
        error = self.setpoint - current_input

        # Check if this is the very first calculation tick
        if self._last_time is None or self._last_input is None:
            dt = 1e-16  # Tiny placeholder delta
            d_input = 0.0  # No change in input yet
        else:
            dt = current_time - self._last_time
            if dt <= 0:
                dt = 1e-16
            d_input = current_input - self._last_input

        # Thermal Anti-Windup Logic for High Thermal Mass
        if error <= 0:
            # If temperature overshoots the target, wipe integral memory instantly
            self._integral = 0.0
        else:
            # Only accumulate integral when within a reasonable control band (10°C)
            # This keeps the integral from saturating during the initial cold heat-up ramp
            if error < 10.0:
                self._integral += self.ki * error * dt
                # Clamp the integral term to output limits
                if self._max_output is not None:
                    self._integral = min(self._max_output, self._integral)
                if self._min_output is not None:
                    self._integral = max(self._min_output, self._integral)
            else:
                self._integral = 0.0

        # Compute terms
        self._proportional = self.kp * error
        self._derivative = -(self.kd * d_input) / dt

        # Combine output
        output = self._proportional + self._integral + self._derivative

        # Final output clamping
        if self._max_output is not None and output > self._max_output:
            output = self._max_output
        if self._min_output is not None and output < self._min_output:
            output = self._min_output

        # State tracking updates
        self._last_input = current_input
        self._last_time = current_time
        return output


class SaunaController:
    """The central business logic for sauna heating, fire-orders, and wear-leveling."""

    def __init__(self, initial_target_temp: float, kp: float = 1.0, ki: float = 0.1, kd: float = 0.0):
        self.pid = PID(kp=kp, ki=ki, kd=kd, setpoint=initial_target_temp, output_limits=(0.0, 100.0))
        # Known mapping: Phase U = 3500W, Phase V = 3500W, Phase W = 2000W
        self.sp = (3500, 3500, 2000)
        self.total_p = sum(self.sp)
        self.current_total_pwm: int = 0
        self.current_phases: Dict[str, int] = {"U": 0, "V": 0, "W": 0}

    def _get_fire_order(self) -> Tuple[int, int, int]:
        doy = time.localtime().tm_yday
        fo_number = doy % 6
        return list(permutations((0, 1, 2)))[fo_number]

    def _calculate_waterfall(self, total_pwm: int) -> Dict[str, int]:
        """
        Distributes the total required power across the 3 phases using a waterfall.
        Returns an explicit, self-describing dictionary for absolute electrical safety.
        """
        fo = self._get_fire_order()

        spfp = [
            round((self.sp[fo[0]] / self.total_p) * 100),
            round((self.sp[fo[1]] / self.total_p) * 100),
            round((self.sp[fo[2]] / self.total_p) * 100)
        ]

        mfo = [0, 0, 0]

        if total_pwm >= 100:
            mfo = [100, 100, 100]
        elif (total_pwm - spfp[2] - spfp[1]) > 0:
            mfo[0] = int((total_pwm - spfp[2] - spfp[1]) / spfp[0] * 100)
            mfo[1] = 100
            mfo[2] = 100
        elif (total_pwm - spfp[2]) > 0:
            mfo[0] = 0
            mfo[1] = int((total_pwm - spfp[2]) / spfp[1] * 100)
            mfo[2] = 100
        elif total_pwm <= 0:
            mfo = [0, 0, 0]
        else:
            mfo[0] = 0
            mfo[1] = 0
            mfo[2] = int(total_pwm / spfp[2] * 100)

        # ⚡ Secure Dictionary Return Structure ⚡
        mp_dict = {"U": 0, "V": 0, "W": 0}
        phase_keys = ["U", "V", "W"]

        mp_dict[phase_keys[fo[0]]] = mfo[0]
        mp_dict[phase_keys[fo[1]]] = mfo[1]
        mp_dict[phase_keys[fo[2]]] = mfo[2]

        return mp_dict

    def get_current_order_string(self) -> str:
        """Returns a human-readable string of the current daily element wear-leveling priority."""
        fo = self._get_fire_order()
        phase_names = ["U", "V", "W"]
        return " -> ".join(phase_names[idx] for idx in fo)

    def evaluate(self, state: 'SystemState') -> Optional[Dict[str, Any]]:
        door_sauna_open = state.devices.get(10001) == "OPEN"

        # --- Safety & Hold Interlocks ---
        if door_sauna_open or state.sauna.hold_mode == "hold" or not state.sauna.active:
            if self.current_total_pwm != 0:
                self.current_total_pwm = 0
                self.current_phases = {"U": 0, "V": 0, "W": 0}
                self.pid.reset()
                return {"pwm": 0, "phases": {"U": 0, "V": 0, "W": 0}}
            return None

        current_temp = state.sensors.sauna_calc_temp
        target_temp = state.sauna.target_temp
        now_ts = time.time()

        self.pid.setpoint = target_temp
        calculated_pwm = self.pid.compute(current_input=current_temp, current_time=now_ts)

        new_total_pwm = int(round(calculated_pwm))

        if abs(new_total_pwm - self.current_total_pwm) >= 1:
            self.current_total_pwm = new_total_pwm
            self.current_phases = self._calculate_waterfall(self.current_total_pwm)

            return {
                "pwm": self.current_total_pwm,
                "phases": self.current_phases
            }

        return None