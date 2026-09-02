# --- file: logic/power_analytics.py ---
import asyncio
import time
import sqlite3
import os
from typing import Any, Dict, Optional, List
from datetime import datetime
from loguru import logger
from core.models import SaunaSessionRecord, IrSessionRecord, SystemState
from core.well_known_entities import ENTITY_MAINS_VOLTAGE
from logic.element_power_store import ElementPowerRow, bootstrap_if_empty, load_row, save_row

# Max inter-pulse gap used for calc Wh integration (real Wh uses meter interval).
_MAX_CALC_PULSE_DELTA_SECS: float = 30.0
# Min seconds at one IR mod plateau before it contributes to segmented learn.
_IR_PLATEAU_MIN_SECS: float = 30.0


class PowerAnalytics:
    """
    Volatile Software-Defined Disaggregation Service.
    Isolates background leak metrics, solves linear regressions for element capacities,
    and handles file I/O for persistent analytics tracking.
    """

    def __init__(self, state_manager: Any) -> None:
        self.sm = state_manager
        self.logger = state_manager.logger
        self._log_path: str = "/var/log/wanos/wanos_power.log"
        self._db_path: str = "sauna_sessions.db"  # Defaults to current runtime root directory
        self._task: Optional[asyncio.Task] = None

        # High-Frequency Pulse Time Variables
        self._last_pulse_ts: float = 0.0

        # Operational Baselines
        self._locked_leak_watts: float = 0.0
        self._p_u_extracted: float = 3500.0  # Safe initial baseline
        self._p_v_extracted: float = 3500.0
        self._p_w_extracted: float = 2000.0

        # Session tracking lists for averages
        self._session_temp_history: List[float] = []
        self._session_hum_history: List[int] = []
        self._session_mod_u_history: List[float] = []
        self._session_mod_v_history: List[float] = []
        self._session_mod_w_history: List[float] = []
        self._session_mod_ir_history: List[float] = []

        # C34: per-mod IR plateau accumulators (time-weighted segmented learn)
        self._ir_plateau_wh: Dict[int, float] = {}
        self._ir_plateau_secs: Dict[int, float] = {}

        # Deduplication tracker to prevent identical consecutive log lines
        self._last_log_content: str = ""

        # Outdoor temp snapshot at session start (see docs/sensor_history.md)
        self._temp_outside_start: Optional[float] = None

        # C32: learned element W @ 100% mod (DB singleton)
        self._element_power: ElementPowerRow = load_row(self._db_path)
        self._session_baseline_u: float = self._element_power.w_u
        self._session_baseline_v: float = self._element_power.w_v
        self._session_baseline_w: float = self._element_power.w_w
        self._session_baseline_ir: float = self._element_power.w_ir

        self._init_sqlite()
        self._sync_extracted_to_metrics()

    def _sync_extracted_to_metrics(self) -> None:
        """Mirror DB nameplates to live metrics for Admin display."""
        row = self._element_power
        self._p_u_extracted = row.w_u
        self._p_v_extracted = row.w_v
        self._p_w_extracted = row.w_w
        self.sm._state.metrics.extracted_p_u = round(row.w_u, 1)
        self.sm._state.metrics.extracted_p_v = round(row.w_v, 1)
        self.sm._state.metrics.extracted_p_w = round(row.w_w, 1)

    def _reload_element_power(self) -> None:
        self._element_power = load_row(self._db_path)
        self._sync_extracted_to_metrics()

    def restore_leak_baseline(self, watts: float) -> None:
        """Boot / reload: restore last known idle leak W from NVRAM."""
        if not isinstance(watts, (int, float)):
            return
        w = max(0.0, float(watts))
        self._locked_leak_watts = w
        self.sm._state.metrics.p_leak_baseline_watts = w

    def _sauna_effective_watts(self) -> tuple[float, float, float]:
        """Per-phase model baselines for Calc integration (from DB)."""
        row = self._element_power
        return (float(row.w_u), float(row.w_v), float(row.w_w))

    def _ir_effective_watts(self) -> float:
        """IR model baseline at 100% modulation (from DB)."""
        return float(self._element_power.w_ir)

    @staticmethod
    def _ema_commit(baseline: float, measured: float) -> tuple[float, bool]:
        """EMA 0.7/0.3 with ±25% outlier reject. Returns (new_value, committed)."""
        if measured <= 0 or baseline <= 0:
            return baseline, False
        if abs(measured - baseline) / baseline > 0.25:
            return baseline, False
        new_val = 0.7 * baseline + 0.3 * measured
        return new_val, True

    def _record_ir_learn(
        self,
        status: str,
        measured: Optional[float],
        *,
        committed_w: Optional[float] = None,
    ) -> None:
        """Persist last IR learn outcome (+ optional nameplate commit)."""
        row = self._element_power
        now = int(time.time())
        row.last_learn_ir_status = status
        row.last_learn_ir_measured_w = measured
        row.last_learn_ir_at = now
        if status == "accepted" and committed_w is not None:
            row.w_ir = committed_w
            row.updated_at = now
            row.source = "session"
            row.learn_count_ir = int(row.learn_count_ir or 0) + 1
        elif status == "rejected":
            row.source = "rejected"
        save_row(self._db_path, row)
        self._element_power = row

    def _record_sauna_learn(
        self,
        status: str,
        detail: str,
        *,
        committed: bool = False,
    ) -> None:
        """Persist last sauna learn outcome (+ bump count when EMA committed)."""
        row = self._element_power
        now = int(time.time())
        row.last_learn_sauna_status = status
        row.last_learn_sauna_detail = detail
        row.last_learn_sauna_at = now
        if committed:
            row.updated_at = now
            row.source = "session"
            row.learn_count_sauna = int(row.learn_count_sauna or 0) + 1
        elif status == "rejected":
            row.source = "rejected"
        save_row(self._db_path, row)
        self._element_power = row

    def _learn_ir(
        self,
        runtime_secs: int,
        mod_min: float,
        mod_max: float,
        mod_avg: float,
        energy_real_wh: float,
        plateau_wh: Optional[Dict[int, float]] = None,
        plateau_secs: Optional[Dict[int, float]] = None,
    ) -> tuple[float, Optional[float], float]:
        baseline = self._session_baseline_ir
        if runtime_secs < 120:
            self._record_ir_learn("skipped", None)
            return baseline, None, baseline

        measured: Optional[float] = None

        if (mod_max - mod_min) > 10 and plateau_wh and plateau_secs:
            # Segmented: time-weighted implied 100% W per mod plateau (C34).
            weighted_sum = 0.0
            weight_total = 0.0
            for mod_pct, secs in plateau_secs.items():
                if secs < _IR_PLATEAU_MIN_SECS or mod_pct <= 0:
                    continue
                wh = float(plateau_wh.get(mod_pct, 0.0))
                if wh <= 0:
                    continue
                avg_w = wh * 3600.0 / secs
                implied_100 = avg_w * 100.0 / float(mod_pct)
                weighted_sum += implied_100 * secs
                weight_total += secs
            if weight_total > 0:
                measured = weighted_sum / weight_total

        if measured is None:
            if mod_avg <= 0:
                self._record_ir_learn("skipped", None)
                return baseline, None, baseline
            if (mod_max - mod_min) > 10:
                self._record_ir_learn("skipped", None)
                return baseline, None, baseline
            avg_w = energy_real_wh * 3600.0 / runtime_secs
            measured = avg_w * 100.0 / mod_avg

        new_w, committed = self._ema_commit(baseline, measured)
        if committed:
            self._record_ir_learn("accepted", measured, committed_w=new_w)
        else:
            self._record_ir_learn("rejected", measured)
            new_w = baseline
        return baseline, measured, new_w

    def _learn_sauna_phases(
        self,
        runtime_secs: int,
        mod_u_min: float,
        mod_u_avg: float,
        mod_u_max: float,
        mod_v_min: float,
        mod_v_avg: float,
        mod_v_max: float,
        mod_w_min: float,
        mod_w_avg: float,
        mod_w_max: float,
        energy_real_wh: float,
    ) -> dict[str, tuple[float, Optional[float], float]]:
        """Returns per-phase (baseline, measured, new) audit triples."""
        baselines = {
            "u": self._session_baseline_u,
            "v": self._session_baseline_v,
            "w": self._session_baseline_w,
        }
        result: dict[str, tuple[float, Optional[float], float]] = {
            k: (baselines[k], None, baselines[k]) for k in baselines
        }
        if runtime_secs < 180:
            self._record_sauna_learn("skipped", "runtime < 180s")
            return result

        avg_w = energy_real_wh * 3600.0 / runtime_secs if runtime_secs > 0 else 0.0
        row = self._element_power
        total_name = row.w_u + row.w_v + row.w_w

        def _detail_from_result(res: dict[str, tuple[float, Optional[float], float]]) -> str:
            parts: List[str] = []
            for key in ("u", "v", "w"):
                _base, meas, _new = res[key]
                if meas is not None:
                    parts.append(f"{key.upper()} {meas:.0f} W")
            return " / ".join(parts) if parts else "no phase measure"

        # Full-load all phases >= 30 s (approximated via session min mods)
        if (
            mod_u_min >= 95 and mod_v_min >= 95 and mod_w_min >= 95
            and runtime_secs >= 30
            and total_name > 0
            and avg_w > 0
        ):
            any_commit = False
            any_reject = False
            for key, share in (("u", row.w_u), ("v", row.w_v), ("w", row.w_w)):
                measured = avg_w * (share / total_name)
                new_w, committed = self._ema_commit(baselines[key], measured)
                if committed:
                    setattr(row, f"w_{key}", new_w)
                    any_commit = True
                else:
                    any_reject = True
                result[key] = (baselines[key], measured, new_w if committed else baselines[key])
            detail = _detail_from_result(result)
            if any_commit:
                self._element_power = row
                self._record_sauna_learn("accepted", detail, committed=True)
            elif any_reject:
                self._record_sauna_learn("rejected", detail)
            else:
                self._record_sauna_learn("skipped", detail)
            return result

        # Single-phase windows (>= 60 s session, one phase dominant)
        singles = (
            ("u", mod_u_avg, mod_u_max, mod_v_max, mod_w_max),
            ("v", mod_v_avg, mod_v_max, mod_u_max, mod_w_max),
            ("w", mod_w_avg, mod_w_max, mod_u_max, mod_v_max),
        )
        any_commit = False
        any_reject = False
        for key, phase_avg, _phase_max, other_a, other_b in singles:
            if phase_avg <= 50 or max(other_a, other_b) >= 5:
                continue
            measured = avg_w * 100.0 / phase_avg if phase_avg > 0 else 0.0
            new_w, committed = self._ema_commit(baselines[key], measured)
            if committed:
                setattr(row, f"w_{key}", new_w)
                any_commit = True
            else:
                any_reject = True
            result[key] = (baselines[key], measured, new_w if committed else baselines[key])
        detail = _detail_from_result(result)
        if any_commit:
            self._element_power = row
            self._record_sauna_learn("accepted", detail, committed=True)
        elif any_reject:
            self._record_sauna_learn("rejected", detail)
        else:
            self._record_sauna_learn("skipped", "no eligible single-phase window")
        return result

    def note_session_start(self, session_type: str) -> None:
        """Capture outdoor temperature and reset ephemeral session counters."""
        self._reload_element_power()
        self._session_baseline_u = self._element_power.w_u
        self._session_baseline_v = self._element_power.w_v
        self._session_baseline_w = self._element_power.w_w
        self._session_baseline_ir = self._element_power.w_ir
        self._temp_outside_start = self.sm._state.sensors.outside_temp
        self.sm._state.metrics.running_energy_real_wh = 0.0
        self.sm._state.metrics.running_energy_calc_wh = 0.0
        # Avoid attributing pre-session idle gap to calc Wh on the first pulse (C34).
        self._last_pulse_ts = time.time()
        self._session_temp_history.clear()
        self._session_hum_history.clear()
        if session_type == "sauna":
            self._session_mod_u_history.clear()
            self._session_mod_v_history.clear()
            self._session_mod_w_history.clear()
        elif session_type == "ir":
            self._session_mod_ir_history.clear()
            self._ir_plateau_wh.clear()
            self._ir_plateau_secs.clear()

    def _init_sqlite(self) -> None:
        """Constructs tracking schema tables synchronously on boot if they do not exist."""
        try:
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS sauna_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_timestamp INTEGER,
                    total_runtime_secs INTEGER,
                    runtime_u_secs INTEGER,
                    runtime_v_secs INTEGER,
                    runtime_w_secs INTEGER,
                    temp_start REAL,
                    temp_end REAL,
                    temp_min REAL,
                    temp_max REAL,
                    temp_avg REAL,
                    temp_outside_start REAL,
                    hum_start INTEGER,
                    hum_end INTEGER,
                    hum_min INTEGER,
                    hum_max INTEGER,
                    hum_avg INTEGER,
                    mod_system_min REAL,
                    mod_system_max REAL,
                    mod_system_avg REAL,
                    mod_u_min REAL,
                    mod_u_max REAL,
                    mod_u_avg REAL,
                    mod_v_min REAL,
                    mod_v_max REAL,
                    mod_v_avg REAL,
                    mod_w_min REAL,
                    mod_w_max REAL,
                    mod_w_avg REAL,
                    energy_real_wh REAL,
                    energy_calc_wh REAL,
                    extracted_p_u REAL,
                    extracted_p_v REAL,
                    extracted_p_w REAL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS ir_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_timestamp INTEGER,
                    total_runtime_secs INTEGER,
                    temp_start REAL,
                    temp_end REAL,
                    temp_outside_start REAL,
                    hum_start INTEGER,
                    hum_end INTEGER,
                    mod_min REAL,
                    mod_max REAL,
                    mod_avg REAL,
                    energy_real_wh REAL,
                    energy_calc_wh REAL
                )
            ''')
            # Migrate older DBs that lack temp_outside_start
            for table in ("sauna_sessions", "ir_sessions"):
                c.execute(f"PRAGMA table_info({table})")
                cols = {row[1] for row in c.fetchall()}
                if "temp_outside_start" not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN temp_outside_start REAL")
            bootstrap_if_empty(conn)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize Analytics SQLite database: {e}")

    def _fetch_last_sessions(self) -> None:
        """Reads the most recent completed records from the database and loads them into RAM."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT * FROM sauna_sessions ORDER BY session_id DESC LIMIT 1")
            s_row = c.fetchone()
            self.sm._state.metrics.last_sauna_session = dict(s_row) if s_row else None

            c.execute("SELECT * FROM ir_sessions ORDER BY session_id DESC LIMIT 1")
            i_row = c.fetchone()
            self.sm._state.metrics.last_ir_session = dict(i_row) if i_row else None

            c.execute("SELECT COUNT(*) FROM sauna_sessions")
            self.sm._state.metrics.session_count_sauna = int(c.fetchone()[0] or 0)
            c.execute("SELECT COUNT(*) FROM ir_sessions")
            self.sm._state.metrics.session_count_ir = int(c.fetchone()[0] or 0)

            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch historical session readbacks: {e}")

    def start(self) -> None:
        # Pre-load historical summaries into UI state on boot
        asyncio.create_task(asyncio.to_thread(self._fetch_last_sessions))

        # Guarantee parent log directory exists to prevent file stream crashes
        log_dir = os.path.dirname(self._log_path)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Cannot create log directory {log_dir}: {e}")

        if not self._task:
            self._task = asyncio.create_task(self._log_flush_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def process_pulse_tick(self) -> None:
        """
        Calculates exact wattages from hardware tick intervals.
        Because this intercepts high-frequency ticks, math operations must be highly optimized.
        """
        now = time.time()
        if self._last_pulse_ts > 0:
            delta_t = now - self._last_pulse_ts
            if delta_t <= 0:
                delta_t = 0.001  # Math failsafe to prevent divide-by-zero crashes

            # Hardware quantum: 1000 pulses/kWh = 1 pulse per 3.6 seconds for exactly 1000W load
            instant_watts = 3600.0 / delta_t
            state: SystemState = self.sm.get_state_snapshot()

            if not state.sauna.active and not state.ir.active:
                # ⚡ IDLE FINGERPRINTING: Track natural household baseline leak
                self.sm._state.metrics.p_leak_baseline_watts = instant_watts
                self._locked_leak_watts = instant_watts
                self.sm._state.metrics.p_elements_real_watts = 0.0
                self.sm._state.metrics.p_elements_calc_watts = 0.0

                # Reset ephemeral session running tallies
                self.sm._state.metrics.running_energy_real_wh = 0.0
                self.sm._state.metrics.running_energy_calc_wh = 0.0
            else:
                # ACTIVE DECOUPLING: Isolate true element loads from frozen baseline
                real_element_load = instant_watts - self._locked_leak_watts
                # Clamp zero-crossings resulting from micro-voltage natural variances
                self.sm._state.metrics.p_elements_real_watts = max(0.0, real_element_load)

                # LIVE INTEGRATION: Convert instantaneous wattage intervals to cumulative Watt-hours
                step_real_wh = max(0.0, real_element_load) * (delta_t / 3600.0)
                self.sm._state.metrics.running_energy_real_wh += step_real_wh
                self.sm._state.metrics.total_energy_real_wh += step_real_wh

                mains_idx = self.sm.resolve_entity_id(ENTITY_MAINS_VOLTAGE)
                v_raw = state.devices.get(mains_idx) if mains_idx is not None else None
                v_live: Optional[float] = None
                if v_raw is not None and str(v_raw).replace(" V", "").strip().replace('.', '', 1).isdigit():
                    v_live = float(str(v_raw).replace(" V", "").strip())

                w_u, w_v, w_w = self._sauna_effective_watts()
                mod_u = state.sauna.phases_pwm.get("U", 0) / 100.0
                mod_v = state.sauna.phases_pwm.get("V", 0) / 100.0
                mod_w = state.sauna.phases_pwm.get("W", 0) / 100.0
                voltage_scaler = ((v_live / 230.0) ** 2) if v_live is not None else 1.0

                calc_load = voltage_scaler * (
                    (mod_u * w_u) + (mod_v * w_v) + (mod_w * w_w)
                )
                if state.ir.active:
                    ir_mod = state.ir.modulation_pwm / 100.0
                    calc_load += self._ir_effective_watts() * ir_mod * voltage_scaler

                self.sm._state.metrics.p_elements_calc_watts = max(0.0, calc_load)

                calc_delta_t = min(delta_t, _MAX_CALC_PULSE_DELTA_SECS)
                step_calc_wh = calc_load * (calc_delta_t / 3600.0)
                self.sm._state.metrics.running_energy_calc_wh += step_calc_wh

                # Capture dynamic moving averages per tick during sessions
                if state.sensors.sauna_calc_temp is not None:
                    self._session_temp_history.append(state.sensors.sauna_calc_temp)
                if state.sensors.sauna_calc_hum is not None:
                    self._session_hum_history.append(float(state.sensors.sauna_calc_hum))

                if state.sauna.active:
                    self._session_mod_u_history.append(float(state.sauna.phases_pwm.get("U", 0)))
                    self._session_mod_v_history.append(float(state.sauna.phases_pwm.get("V", 0)))
                    self._session_mod_w_history.append(float(state.sauna.phases_pwm.get("W", 0)))
                if state.ir.active:
                    ir_mod = int(round(float(state.ir.modulation_pwm or 0)))
                    self._session_mod_ir_history.append(float(ir_mod))
                    self._ir_plateau_wh[ir_mod] = (
                        self._ir_plateau_wh.get(ir_mod, 0.0) + step_real_wh
                    )
                    self._ir_plateau_secs[ir_mod] = (
                        self._ir_plateau_secs.get(ir_mod, 0.0) + delta_t
                    )

        self._last_pulse_ts = now

    async def terminate_session(self, session_type: str) -> None:
        """Aggregates all tracking data when a session shuts down and commits cleanly to SQLite."""
        state: SystemState = self.sm.get_state_snapshot()

        # Safely compute structural array mathematics avoiding division by zero
        def _safe_avg(arr: List[float]) -> float:
            return round(sum(arr) / len(arr), 2) if arr else 0.0

        def _safe_min(arr: List[float]) -> float:
            return round(min(arr), 2) if arr else 0.0

        def _safe_max(arr: List[float]) -> float:
            return round(max(arr), 2) if arr else 0.0

        now_ts = int(time.time())

        try:
            if session_type == "sauna":
                start_ts = state.sauna.session_start_time or now_ts
                runtime = now_ts - start_ts
                mod_u_min = _safe_min(self._session_mod_u_history)
                mod_u_max = _safe_max(self._session_mod_u_history)
                mod_u_avg = _safe_avg(self._session_mod_u_history)
                mod_v_min = _safe_min(self._session_mod_v_history)
                mod_v_max = _safe_max(self._session_mod_v_history)
                mod_v_avg = _safe_avg(self._session_mod_v_history)
                mod_w_min = _safe_min(self._session_mod_w_history)
                mod_w_max = _safe_max(self._session_mod_w_history)
                mod_w_avg = _safe_avg(self._session_mod_w_history)
                energy_real = round(state.metrics.running_energy_real_wh, 2)

                audits = self._learn_sauna_phases(
                    runtime, mod_u_min, mod_u_avg, mod_u_max,
                    mod_v_min, mod_v_avg, mod_v_max,
                    mod_w_min, mod_w_avg, mod_w_max,
                    energy_real,
                )
                self._sync_extracted_to_metrics()

                record = SaunaSessionRecord(
                    start_timestamp=start_ts,
                    total_runtime_secs=runtime,
                    runtime_u_secs=runtime,
                    runtime_v_secs=runtime,
                    runtime_w_secs=runtime,
                    temp_start=self._session_temp_history[0] if self._session_temp_history else 0.0,
                    temp_end=self._session_temp_history[-1] if self._session_temp_history else 0.0,
                    temp_min=_safe_min(self._session_temp_history),
                    temp_max=_safe_max(self._session_temp_history),
                    temp_avg=_safe_avg(self._session_temp_history),
                    temp_outside_start=self._temp_outside_start,
                    hum_start=int(self._session_hum_history[0]) if self._session_hum_history else 0,
                    hum_end=int(self._session_hum_history[-1]) if self._session_hum_history else 0,
                    hum_min=int(_safe_min(self._session_hum_history)),
                    hum_max=int(_safe_max(self._session_hum_history)),
                    hum_avg=int(_safe_avg(self._session_hum_history)),
                    mod_system_min=0.0,
                    mod_system_max=100.0,
                    mod_system_avg=50.0,
                    mod_u_min=mod_u_min,
                    mod_u_max=mod_u_max,
                    mod_u_avg=mod_u_avg,
                    mod_v_min=mod_v_min,
                    mod_v_max=mod_v_max,
                    mod_v_avg=mod_v_avg,
                    mod_w_min=mod_w_min,
                    mod_w_max=mod_w_max,
                    mod_w_avg=mod_w_avg,
                    energy_real_wh=energy_real,
                    energy_calc_wh=round(state.metrics.running_energy_calc_wh, 2),
                    extracted_p_u=round(self._element_power.w_u, 1),
                    extracted_p_v=round(self._element_power.w_v, 1),
                    extracted_p_w=round(self._element_power.w_w, 1),
                    audit_baseline_w_u=audits["u"][0],
                    audit_measured_w_u=audits["u"][1],
                    audit_new_w_u=audits["u"][2],
                    audit_baseline_w_v=audits["v"][0],
                    audit_measured_w_v=audits["v"][1],
                    audit_new_w_v=audits["v"][2],
                    audit_baseline_w_w=audits["w"][0],
                    audit_measured_w_w=audits["w"][1],
                    audit_new_w_w=audits["w"][2],
                )

                # Offload DB transaction to background thread to prevent halting the master loop
                await asyncio.to_thread(self._commit_sauna_record, record)
                await asyncio.to_thread(self._fetch_last_sessions)
                await self.logger.success("✅ Sauna Session metrics evaluated and flushed to SQLite.")

            elif session_type == "ir":
                start_ts = state.ir.session_start_time or now_ts
                runtime = now_ts - start_ts
                mod_min = _safe_min(self._session_mod_ir_history)
                mod_max = _safe_max(self._session_mod_ir_history)
                mod_avg = _safe_avg(self._session_mod_ir_history)
                energy_real = round(state.metrics.running_energy_real_wh, 2)

                b_ir, m_ir, n_ir = self._learn_ir(
                    runtime, mod_min, mod_max, mod_avg, energy_real,
                    plateau_wh=dict(self._ir_plateau_wh),
                    plateau_secs=dict(self._ir_plateau_secs),
                )
                self._sync_extracted_to_metrics()

                record = IrSessionRecord(
                    start_timestamp=start_ts,
                    total_runtime_secs=runtime,
                    temp_start=self._session_temp_history[0] if self._session_temp_history else 0.0,
                    temp_end=self._session_temp_history[-1] if self._session_temp_history else 0.0,
                    temp_outside_start=self._temp_outside_start,
                    hum_start=int(self._session_hum_history[0]) if self._session_hum_history else 0,
                    hum_end=int(self._session_hum_history[-1]) if self._session_hum_history else 0,
                    mod_min=mod_min,
                    mod_max=mod_max,
                    mod_avg=mod_avg,
                    energy_real_wh=energy_real,
                    energy_calc_wh=round(state.metrics.running_energy_calc_wh, 2),
                    audit_baseline_w_ir=b_ir,
                    audit_measured_w_ir=m_ir,
                    audit_new_w_ir=n_ir,
                )
                await asyncio.to_thread(self._commit_ir_record, record)
                await asyncio.to_thread(self._fetch_last_sessions)
                await self.logger.success("✅ IR Session metrics evaluated and flushed to SQLite.")

        except Exception as e:
            await self.logger.error(f"Failed to compile session SQL teardown metrics: {e}")

        # Clear ephemeral tracking lists entirely for the next session
        self._session_temp_history.clear()
        self._session_hum_history.clear()
        self._session_mod_u_history.clear()
        self._session_mod_v_history.clear()
        self._session_mod_w_history.clear()
        self._session_mod_ir_history.clear()
        self._ir_plateau_wh.clear()
        self._ir_plateau_secs.clear()
        self._temp_outside_start = None

    def _commit_sauna_record(self, record: SaunaSessionRecord) -> None:
        """Blocking SQLite write operation (Safely executed in an offloaded thread)."""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO sauna_sessions (
                start_timestamp, total_runtime_secs, runtime_u_secs, runtime_v_secs, runtime_w_secs,
                temp_start, temp_end, temp_min, temp_max, temp_avg, temp_outside_start,
                hum_start, hum_end, hum_min, hum_max, hum_avg,
                mod_system_min, mod_system_max, mod_system_avg,
                mod_u_min, mod_u_max, mod_u_avg,
                mod_v_min, mod_v_max, mod_v_avg,
                mod_w_min, mod_w_max, mod_w_avg,
                energy_real_wh, energy_calc_wh,
                extracted_p_u, extracted_p_v, extracted_p_w,
                audit_baseline_w_u, audit_measured_w_u, audit_new_w_u,
                audit_baseline_w_v, audit_measured_w_v, audit_new_w_v,
                audit_baseline_w_w, audit_measured_w_w, audit_new_w_w
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.start_timestamp, record.total_runtime_secs, record.runtime_u_secs, record.runtime_v_secs,
            record.runtime_w_secs,
            record.temp_start, record.temp_end, record.temp_min, record.temp_max, record.temp_avg,
            record.temp_outside_start,
            record.hum_start, record.hum_end, record.hum_min, record.hum_max, record.hum_avg,
            record.mod_system_min, record.mod_system_max, record.mod_system_avg,
            record.mod_u_min, record.mod_u_max, record.mod_u_avg,
            record.mod_v_min, record.mod_v_max, record.mod_v_avg,
            record.mod_w_min, record.mod_w_max, record.mod_w_avg,
            record.energy_real_wh, record.energy_calc_wh,
            record.extracted_p_u, record.extracted_p_v, record.extracted_p_w,
            record.audit_baseline_w_u, record.audit_measured_w_u, record.audit_new_w_u,
            record.audit_baseline_w_v, record.audit_measured_w_v, record.audit_new_w_v,
            record.audit_baseline_w_w, record.audit_measured_w_w, record.audit_new_w_w,
        ))
        conn.commit()
        conn.close()

    def _commit_ir_record(self, record: IrSessionRecord) -> None:
        """Blocking SQLite write operation (Safely executed in an offloaded thread)."""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO ir_sessions (
                start_timestamp, total_runtime_secs,
                temp_start, temp_end, temp_outside_start, hum_start, hum_end,
                mod_min, mod_max, mod_avg,
                energy_real_wh, energy_calc_wh,
                audit_baseline_w_ir, audit_measured_w_ir, audit_new_w_ir
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.start_timestamp, record.total_runtime_secs,
            record.temp_start, record.temp_end, record.temp_outside_start,
            record.hum_start, record.hum_end,
            record.mod_min, record.mod_max, record.mod_avg,
            record.energy_real_wh, record.energy_calc_wh,
            record.audit_baseline_w_ir, record.audit_measured_w_ir, record.audit_new_w_ir,
        ))
        conn.commit()
        conn.close()

    async def _log_flush_loop(self) -> None:
        """Every 60 seconds, evaluates the Disaggregation Regression Matrix and appends an isolated log line."""
        while True:
            try:
                await asyncio.sleep(60.0)
                state: SystemState = self.sm.get_state_snapshot()

                mains_idx = self.sm.resolve_entity_id(ENTITY_MAINS_VOLTAGE)
                v_raw = state.devices.get(mains_idx) if mains_idx is not None else None
                real_power = state.metrics.p_elements_real_watts

                # ⚡ STRICT VOLTAGE INTERLOCK
                # Safely aborts mathematical capacity modeling if live Z-Wave telemetry is disconnected
                if v_raw is not None and str(v_raw).replace(" V", "").strip().replace('.', '', 1).isdigit():
                    v_live = float(str(v_raw).replace(" V", "").strip())
                else:
                    v_live = "AWAITING"

                self._sync_extracted_to_metrics()

                # Calculate Normalized Thermal Integrity (R_th)
                r_th = "N/A"
                if state.sauna.active and real_power > 500:
                    t_in = state.sensors.sauna_calc_temp
                    t_out = state.sensors.outside_temp
                    if t_in is not None and t_out is not None:
                        r_th = round((t_in - t_out) / real_power, 6)
                        self.sm._state.metrics.r_th_insulation_coefficient = r_th

                # Append strictly to our specialized file stream
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Extract the raw content without the timestamp to evaluate for duplicates
                # Note: Safely parse v_live just in case the Z-Wave network drops and returns the "AWAITING" string
                v_display = round(v_live, 1) if isinstance(v_live, float) else v_live
                log_content = (f"[DEBUG] P_Leak: {round(self._locked_leak_watts, 1)}W | "
                               f"P_Real: {round(real_power, 1)}W | V_Line: {v_display}V | "
                               f"R_th: {r_th} | Extracted [U:{round(self._p_u_extracted)}W V:{round(self._p_v_extracted)}W W:{round(self._p_w_extracted)}W]\n")

                if log_content == self._last_log_content:
                    continue  # Silently skip logging if the exact same physics parameters were just logged

                self._last_log_content = log_content
                log_entry = f"[{now_str}] {log_content}"

                try:
                    with open(self._log_path, "a") as f:
                        f.write(log_entry)
                except Exception as e:
                    logger.error(f"Failed to append to isolated Analytics file {self._log_path}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception in PowerAnalytics loop: {e}")