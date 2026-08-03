# --- file: logic/power_analytics.py ---
import asyncio
import time
import sqlite3
import os
from typing import Any, Dict, Optional, List
from datetime import datetime
from loguru import logger
from core.models import SaunaSessionRecord, IrSessionRecord, SystemState


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

        # Deduplication tracker to prevent identical consecutive log lines
        self._last_log_content: str = ""

        # Outdoor temp snapshot at session start (see docs/sensor_history.md)
        self._temp_outside_start: Optional[float] = None

        self._init_sqlite()

    def note_session_start(self) -> None:
        """Capture outdoor temperature when a sauna/IR session begins."""
        self._temp_outside_start = self.sm._state.sensors.outside_temp

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
            if s_row:
                self.sm._state.metrics.last_sauna_session = dict(s_row)

            c.execute("SELECT * FROM ir_sessions ORDER BY session_id DESC LIMIT 1")
            i_row = c.fetchone()
            if i_row:
                self.sm._state.metrics.last_ir_session = dict(i_row)

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

                # Reset ephemeral session running tallies
                self.sm._state.metrics.running_energy_real_wh = 0.0
                self.sm._state.metrics.running_energy_calc_wh = 0.0
            else:
                # ⚡ ACTIVE DECOUPLING: Isolate true element loads from frozen baseline
                real_element_load = instant_watts - self._locked_leak_watts
                # Clamp zero-crossings resulting from micro-voltage natural variances
                self.sm._state.metrics.p_elements_real_watts = max(0.0, real_element_load)

                # ⚡ LIVE INTEGRATION: Convert instantaneous wattage intervals to cumulative Watt-hours
                step_real_wh = max(0.0, real_element_load) * (delta_t / 3600.0)
                self.sm._state.metrics.running_energy_real_wh += step_real_wh
                self.sm._state.metrics.total_energy_real_wh += step_real_wh

                v_raw = state.devices.get(71046)
                if v_raw is not None and str(v_raw).replace(" V", "").strip().replace('.', '', 1).isdigit():
                    v_live = float(str(v_raw).replace(" V", "").strip())
                    mod_u = state.sauna.phases_pwm.get("U", 0) / 100.0
                    mod_v = state.sauna.phases_pwm.get("V", 0) / 100.0
                    mod_w = state.sauna.phases_pwm.get("W", 0) / 100.0

                    calc_load = ((v_live / 230.0) ** 2) * ((mod_u * 3500) + (mod_v * 3500) + (mod_w * 2000))
                    step_calc_wh = calc_load * (delta_t / 3600.0)
                    self.sm._state.metrics.running_energy_calc_wh += step_calc_wh

                # Capture dynamic moving averages per tick during sessions
                if state.sensors.sauna_calc_temp is not None:
                    self._session_temp_history.append(state.sensors.sauna_calc_temp)
                if state.sensors.sauna_calc_hum is not None:
                    self._session_hum_history.append(float(state.sensors.sauna_calc_hum))

                self._session_mod_u_history.append(float(state.sauna.phases_pwm.get("U", 0)))
                self._session_mod_v_history.append(float(state.sauna.phases_pwm.get("V", 0)))
                self._session_mod_w_history.append(float(state.sauna.phases_pwm.get("W", 0)))

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
                record = SaunaSessionRecord(
                    start_timestamp=start_ts,
                    total_runtime_secs=now_ts - start_ts,
                    runtime_u_secs=now_ts - start_ts,  # Simplified for demonstration
                    runtime_v_secs=now_ts - start_ts,
                    runtime_w_secs=now_ts - start_ts,
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
                    mod_u_min=_safe_min(self._session_mod_u_history),
                    mod_u_max=_safe_max(self._session_mod_u_history),
                    mod_u_avg=_safe_avg(self._session_mod_u_history),
                    mod_v_min=_safe_min(self._session_mod_v_history),
                    mod_v_max=_safe_max(self._session_mod_v_history),
                    mod_v_avg=_safe_avg(self._session_mod_v_history),
                    mod_w_min=_safe_min(self._session_mod_w_history),
                    mod_w_max=_safe_max(self._session_mod_w_history),
                    mod_w_avg=_safe_avg(self._session_mod_w_history),
                    energy_real_wh=round(state.metrics.running_energy_real_wh, 2),
                    energy_calc_wh=round(state.metrics.running_energy_calc_wh, 2),
                    extracted_p_u=round(self._p_u_extracted, 1),
                    extracted_p_v=round(self._p_v_extracted, 1),
                    extracted_p_w=round(self._p_w_extracted, 1),
                )

                # Offload DB transaction to background thread to prevent halting the master loop
                await asyncio.to_thread(self._commit_sauna_record, record)
                await asyncio.to_thread(self._fetch_last_sessions)
                await self.logger.success("✅ Sauna Session metrics evaluated and flushed to SQLite.")

            elif session_type == "ir":
                start_ts = state.ir.session_start_time or now_ts
                record = IrSessionRecord(
                    start_timestamp=start_ts,
                    total_runtime_secs=now_ts - start_ts,
                    temp_start=self._session_temp_history[0] if self._session_temp_history else 0.0,
                    temp_end=self._session_temp_history[-1] if self._session_temp_history else 0.0,
                    temp_outside_start=self._temp_outside_start,
                    hum_start=int(self._session_hum_history[0]) if self._session_hum_history else 0,
                    hum_end=int(self._session_hum_history[-1]) if self._session_hum_history else 0,
                    mod_min=_safe_min(self._session_mod_u_history),
                    mod_max=_safe_max(self._session_mod_u_history),
                    mod_avg=_safe_avg(self._session_mod_u_history),
                    energy_real_wh=round(state.metrics.running_energy_real_wh, 2),
                    energy_calc_wh=round(state.metrics.running_energy_calc_wh, 2)
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
                extracted_p_u, extracted_p_v, extracted_p_w
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            record.extracted_p_u, record.extracted_p_v, record.extracted_p_w
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
                energy_real_wh, energy_calc_wh
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.start_timestamp, record.total_runtime_secs,
            record.temp_start, record.temp_end, record.temp_outside_start,
            record.hum_start, record.hum_end,
            record.mod_min, record.mod_max, record.mod_avg,
            record.energy_real_wh, record.energy_calc_wh
        ))
        conn.commit()
        conn.close()

    async def _log_flush_loop(self) -> None:
        """Every 60 seconds, evaluates the Disaggregation Regression Matrix and appends an isolated log line."""
        while True:
            try:
                await asyncio.sleep(60.0)
                state: SystemState = self.sm.get_state_snapshot()

                v_raw = state.devices.get(71046)
                real_power = state.metrics.p_elements_real_watts

                # ⚡ STRICT VOLTAGE INTERLOCK
                # Safely aborts mathematical capacity modeling if live Z-Wave telemetry is disconnected
                if v_raw is not None and str(v_raw).replace(" V", "").strip().replace('.', '', 1).isdigit():
                    v_live = float(str(v_raw).replace(" V", "").strip())

                    # Extract live PWM duty cycles
                    mod_u = state.sauna.phases_pwm.get("U", 0) / 100.0
                    mod_v = state.sauna.phases_pwm.get("V", 0) / 100.0
                    mod_w = state.sauna.phases_pwm.get("W", 0) / 100.0

                    # ⚡ MOCK RLS MATRIX SOLVER
                    # Placeholder for complex NumPy matrices: Maps direct power if 100% load is detected to update capacities
                    if real_power > 0 and mod_u == 1.0 and mod_v == 1.0 and mod_w == 1.0:
                        voltage_scaler = (v_live / 230.0) ** 2
                        if voltage_scaler > 0:
                            total_nominal = real_power / voltage_scaler
                            # Proportionally distribute the observed wattage array updates
                            self._p_u_extracted = total_nominal * (3500 / 9000)
                            self._p_v_extracted = total_nominal * (3500 / 9000)
                            self._p_w_extracted = total_nominal * (2000 / 9000)
                else:
                    v_live = "AWAITING"

                # Push solved states back to RAM for UI dashboards
                self.sm._state.metrics.extracted_p_u = round(self._p_u_extracted, 1)
                self.sm._state.metrics.extracted_p_v = round(self._p_v_extracted, 1)
                self.sm._state.metrics.extracted_p_w = round(self._p_w_extracted, 1)

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