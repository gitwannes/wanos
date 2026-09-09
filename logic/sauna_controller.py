# --- file: logic/sauna_controller.py ---
import time
from itertools import permutations
from typing import Tuple, Optional, Dict, Any, Set
from core.models import SystemState, normalize_phases_pwm


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
        # Last-compute diagnostics (session telemetry / PID debug)
        self.last_error: float = 0.0
        self.last_dt: float = 0.0
        self.last_p: float = 0.0
        self.last_i: float = 0.0
        self.last_d: float = 0.0
        self.last_output_raw: float = 0.0
        self.last_integral_reset_reason: str = "controller_reset"
        self.last_setpoint_bias: float = 0.0

    def compute(
            self,
            current_input: float,
            current_time: float,
            setpoint_bias: float = 0.0,
    ) -> float:
        """
        Computes the PID output based on an injected system timestamp.
        Allows deterministic calculations across live deployment and simulation environments.

        setpoint_bias is added to the configured setpoint (WISC parity). v1 autohold
        uses -1.0 so MOD reaches 0 one degree below the real target; inertia covers
        the last degree. nohold uses 0.0 (real setpoint).
        """
        error = (self.setpoint + setpoint_bias) - current_input

        # Check if this is the very first calculation tick
        if self._last_time is None or self._last_input is None:
            dt = 1e-16  # Tiny placeholder delta
            d_input = 0.0  # No change in input yet
        else:
            dt = current_time - self._last_time
            if dt <= 0:
                dt = 1e-16
            d_input = current_input - self._last_input

        integral_reset_reason = ""
        # Thermal Anti-Windup Logic for High Thermal Mass
        if error <= 0:
            # If temperature overshoots the target, wipe integral memory instantly
            if self._integral != 0.0:
                integral_reset_reason = "overshoot"
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
                if self._integral != 0.0:
                    integral_reset_reason = "error_band"
                self._integral = 0.0

        # Compute terms
        self._proportional = self.kp * error
        self._derivative = -(self.kd * d_input) / dt

        # Combine output (pre-clamp raw for telemetry)
        output_raw = self._proportional + self._integral + self._derivative
        output = output_raw

        # Final output clamping
        if self._max_output is not None and output > self._max_output:
            output = self._max_output
        if self._min_output is not None and output < self._min_output:
            output = self._min_output

        # Publish diagnostics for session telemetry
        self.last_error = float(error)
        self.last_dt = float(dt)
        self.last_p = float(self._proportional)
        self.last_i = float(self._integral)
        self.last_d = float(self._derivative)
        self.last_output_raw = float(output_raw)
        self.last_integral_reset_reason = integral_reset_reason
        self.last_setpoint_bias = float(setpoint_bias)

        # State tracking updates
        self._last_input = current_input
        self._last_time = current_time
        return output


class SaunaController:
    """The central business logic for sauna heating, fire-orders, and wear-leveling."""

    def __init__(
            self,
            initial_target_temp: float,
            kp: float = 1.0,
            ki: float = 0.1,
            kd: float = 0.0,
            setpoint_bias: float = 0.0,
    ):
        self.pid = PID(kp=kp, ki=ki, kd=kd, setpoint=initial_target_temp, output_limits=(0.0, 100.0))
        # Configured heat-up bias (applied only while hold_mode is autohold).
        self.setpoint_bias: float = float(setpoint_bias)
        # Frozen U/V/W permutation for the active session (midnight-safe).
        self._locked_fire_order: Optional[Tuple[int, int, int]] = None
        # Known mapping: Phase U = 3500W, Phase V = 3500W, Phase W = 2000W
        self.sp = (3500, 3500, 2000)
        self.total_p = sum(self.sp)
        self.current_total_pwm: int = 0
        self.current_phases: Dict[str, int] = {"U": 0, "V": 0, "W": 0}
        # Optional SaunaSessionTelemetry (wired by PowerAnalytics)
        self.telemetry: Any = None

    def _notify_telemetry(self, state: "SystemState", triggers: Set[str]) -> None:
        tel = self.telemetry
        if tel is not None and triggers:
            tel.capture(state, triggers=triggers)

    def _compute_fire_order(self) -> Tuple[int, int, int]:
        """Day-of-year wear-leveling permutation (not used while a session lock is held)."""
        doy = time.localtime().tm_yday
        fo_number = doy % 6
        return list(permutations((0, 1, 2)))[fo_number]

    def _get_fire_order(self) -> Tuple[int, int, int]:
        if self._locked_fire_order is not None:
            return self._locked_fire_order
        return self._compute_fire_order()

    def lock_fire_order(self) -> str:
        """
        Freeze the U/V/W fire order for the current session.
        Call on SAUNA_ON so a session that crosses midnight keeps the same waterfall.
        Returns the human-readable order string (e.g. 'W -> V -> U').
        """
        self._locked_fire_order = self._compute_fire_order()
        return self.get_current_order_string()

    def unlock_fire_order(self) -> None:
        """Clear the session fire-order lock (SAUNA_OFF)."""
        self._locked_fire_order = None

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

    @staticmethod
    def recalculate_sauna_metrics(state: SystemState) -> bool:
        """
        Mathematical calculation combining the two physical SHT11 temperature probes
        (Ceiling probe via virtual IDX 20001 and Bench probe via virtual IDX 20002)
        into a single smoothed virtual metric (sauna_calc_temp) used by the PID controller.
        """
        sns = state.sensors
        changed = False
        if sns.sauna_high_temp is not None and sns.sauna_low_temp is not None:
            raw_temp = (sns.sauna_high_temp + sns.sauna_low_temp) / 2
            calc_temp = round(raw_temp * 2) / 2
            if calc_temp != sns.sauna_calc_temp:
                sns.sauna_calc_temp = calc_temp
                changed = True
        if sns.sauna_high_hum is not None and sns.sauna_low_hum is not None:
            raw_hum = (sns.sauna_high_hum + (sns.sauna_low_hum * 4)) / 5
            calc_hum = round(raw_hum)
            if calc_hum != sns.sauna_calc_hum:
                sns.sauna_calc_hum = calc_hum
                changed = True
        return changed

    def evaluate(self, state: 'SystemState') -> Optional[Dict[str, Any]]:
        # --- Safety & Hold Interlocks ---
        # ⚡ EN 60335-2-53 Compliance: Evaluates the soft pause flag rather than raw door state.
        # This keeps elements active during brief exits while instantly dumping load if the grace window expires.
        if state.sauna.is_paused or state.sauna.hold_mode == "hold" or not state.sauna.active:
            if self.current_total_pwm != 0:
                self.current_total_pwm = 0
                self.current_phases = {"U": 0, "V": 0, "W": 0}
                # Mirror onto SystemState before capture so the sample sees dumped MOD.
                state.sauna.modulation_pwm = 0
                state.sauna.phases_pwm = normalize_phases_pwm(self.current_phases)
                self.pid.reset()  # Flushes integral memory to guarantee no windup spikes upon auto-resume
                self._notify_telemetry(state, {"mod"})
                return {"pwm": 0, "phases": {"U": 0, "V": 0, "W": 0}}
            return None

        # PID uses the explicitly calculated metric, guaranteeing identical behavior across real/simulated envs
        current_temp = state.sensors.sauna_calc_temp
        target_temp = state.sauna.target_temp
        now_ts = time.time()

        self.pid.setpoint = target_temp
        # v1: autohold uses configured bias (typically -1 C). nohold tracks the real setpoint.
        applied_bias = float(self.setpoint_bias) if state.sauna.hold_mode == "autohold" else 0.0
        calculated_pwm = self.pid.compute(
            current_input=current_temp,
            current_time=now_ts,
            setpoint_bias=applied_bias,
        )

        new_total_pwm = int(round(calculated_pwm))
        triggers: Set[str] = {"pid"}
        result: Optional[Dict[str, Any]] = None

        if abs(new_total_pwm - self.current_total_pwm) >= 1:
            self.current_total_pwm = new_total_pwm
            self.current_phases = self._calculate_waterfall(self.current_total_pwm)
            # Mirror onto SystemState before capture so PID+mod samples see new MOD.
            state.sauna.modulation_pwm = self.current_total_pwm
            state.sauna.phases_pwm = normalize_phases_pwm(self.current_phases)
            triggers.add("mod")
            result = {
                "pwm": self.current_total_pwm,
                "phases": self.current_phases
            }

        # One coalesced sample per evaluate tick (pid and optional mod).
        self._notify_telemetry(state, triggers)
        return result