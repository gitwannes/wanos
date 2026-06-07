import time
from itertools import permutations
from typing import List, Tuple, Optional, Dict


class PID:
    """
    Integrated Wisc PID Controller.
    Merges legacy clamping, initialization mechanics, and tracking
    with high-mass thermal protections to prevent overshoot.
    """

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

    def compute(self, current_input: float) -> float:
        now = time.monotonic()

        if self._last_time is None or self._last_input is None:
            self._last_time = now
            self._last_input = current_input
            return 0.0

        dt = now - self._last_time
        if dt <= 0:
            dt = 1e-16

        error = self.setpoint - current_input
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
        self._last_time = now

        return output


class SaunaController:
    """The central business logic for sauna heating, fire-orders, and wear-leveling."""

    def __init__(self, initial_target_temp: float, kp: float = 1.0, ki: float = 0.1, kd: float = 0.0):
        self.pid = PID(kp=kp, ki=ki, kd=kd, setpoint=initial_target_temp, output_limits=(0.0, 100.0))
        self.sp = (3500, 3500, 2000)  # Physical element capacities in Watts
        self.total_p = sum(self.sp)
        self.current_total_pwm: int = 0
        self.current_phases: List[int] = [0, 0, 0]

    def _get_fire_order(self) -> Tuple[int, int, int]:
        """Calculates the daily rotating fire order to wear-level the SSRs."""
        doy = time.localtime().tm_yday
        fo_number = doy % 6
        return list(permutations((0, 1, 2)))[fo_number]

    def _calculate_waterfall(self, total_pwm: int) -> List[int]:
        """Distributes the total required power across the 3 phases using a waterfall."""
        fo = self._get_fire_order()

        # Calculate what percentage of total power each element represents
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

        mp = [0, 0, 0]
        mp[fo[0]] = mfo[0]
        mp[fo[1]] = mfo[1]
        mp[fo[2]] = mfo[2]

        return mp

    def get_current_order_string(self) -> str:
        """Returns a human-readable string of the current daily element wear-leveling priority."""
        fo = self._get_fire_order()
        phase_names = ["U", "V", "W"]
        return " -> ".join(phase_names[idx] for idx in fo)

    def evaluate(self, active: bool, current_temp: float, target_temp: float) -> Optional[Dict[str, any]]:
        """
        Called by the State Manager when temps or targets change.
        Returns pure numeric state data if the modulation needs updating, or None if no change.
        """
        # --- Safety & Hold Interlocks ---
        if state.door_open or state.hold_mode == "hold" or not state.active:
            # Safety override: instantly drop all power and bypass PID updates.
            # Returning 0.0 total modulation, and 0.0 for U, V, and W phases.
            return 0.0, [0.0, 0.0, 0.0]

        current_temp = state.current_temp
        target_temp = state.target_temp

        if not active:
            if self.current_total_pwm != 0:
                self.current_total_pwm = 0
                self.current_phases = [0, 0, 0]
                self.pid.reset()
                return {"pwm": 0, "phases": [0, 0, 0]}
            return None

        self.pid.setpoint = target_temp
        calculated_pwm = self.pid.compute(current_input=current_temp)

        new_total_pwm = int(round(calculated_pwm))

        if abs(new_total_pwm - self.current_total_pwm) >= 1:
            self.current_total_pwm = new_total_pwm
            self.current_phases = self._calculate_waterfall(self.current_total_pwm)

            return {
                "pwm": self.current_total_pwm,
                "phases": self.current_phases
            }

        return None