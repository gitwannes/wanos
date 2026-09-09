# --- file: logic/sauna_session_telemetry.py ---
"""
Sauna session time-series telemetry: RAM buffer during the session, SQLite + CSV at end.

Sample triggers (locked): temp/hum change, MOD/phases change, every PID compute,
hold_mode / is_paused edge, and a 5 s heartbeat while the session is active.
"""
from __future__ import annotations

import asyncio
import csv
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from core.models import SystemState, normalize_phases_pwm
from core.well_known_entities import (
    ENTITY_MAINS_VOLTAGE,
    ENTITY_SAUNA_DOOR,
    ENTITY_SAUNA_HIGH,
    ENTITY_SAUNA_LOW,
)

# Heartbeat floor while sauna.active (locked).
_HEARTBEAT_SECS: float = 5.0

# CSV / DB column order (stable for exporters).
SAMPLE_FIELDS: List[str] = [
    "ts",
    "temp_low",
    "temp_high",
    "temp_calc",
    "hum_low",
    "hum_high",
    "hum_calc",
    "mod_u",
    "mod_v",
    "mod_w",
    "mod_total",
    "w_calc_u",
    "w_calc_v",
    "w_calc_w",
    "w_calc_total",
    "w_real_total",
    "w_measured_total",
    "pid_p",
    "pid_i",
    "pid_d",
    "pid_error",
    "pid_output_raw",
    "pid_dt_s",
    "integral_reset_reason",
    "setpoint_bias",
    "target_temp",
    "hold_mode",
    "is_paused",
    "door_state",
    "outside_temp",
    "r_th",
    "v_line",
    "p_leak",
    "trigger",
]

# Session-constant columns: live on sauna_sessions (and the CSV comment line), not per sample.
_SAMPLE_SESSION_CONST_COLS: Tuple[str, ...] = ("kp", "ki", "kd", "fireorder")

_SAMPLES_CREATE_SQL: str = """
            CREATE TABLE sauna_session_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                ts REAL NOT NULL,
                temp_low REAL,
                temp_high REAL,
                temp_calc REAL,
                hum_low REAL,
                hum_high REAL,
                hum_calc REAL,
                mod_u REAL,
                mod_v REAL,
                mod_w REAL,
                mod_total REAL,
                w_calc_u REAL,
                w_calc_v REAL,
                w_calc_w REAL,
                w_calc_total REAL,
                w_real_total REAL,
                w_measured_total REAL,
                pid_p REAL,
                pid_i REAL,
                pid_d REAL,
                pid_error REAL,
                pid_output_raw REAL,
                pid_dt_s REAL,
                integral_reset_reason TEXT,
                setpoint_bias REAL,
                target_temp REAL,
                hold_mode TEXT,
                is_paused INTEGER,
                door_state TEXT,
                outside_temp REAL,
                r_th REAL,
                v_line REAL,
                p_leak REAL,
                trigger TEXT
            )
            """


def _probe_dict(state: SystemState, idx: Optional[int]) -> Dict[str, Any]:
    if idx is None:
        return {}
    raw = state.devices.get(idx)
    return raw if isinstance(raw, dict) else {}


def _parse_voltage(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        text = str(raw).replace(" V", "").strip()
        if text.replace(".", "", 1).isdigit():
            return float(text)
    except (TypeError, ValueError):
        return None
    return None


class SaunaSessionTelemetry:
    """In-session sample buffer + flush helpers (owned by PowerAnalytics)."""

    def __init__(self, power_analytics: Any) -> None:
        self._pa = power_analytics
        self._sm = power_analytics.sm
        self._buffer: List[Dict[str, Any]] = []
        self._active: bool = False
        self._session_start_unix: Optional[int] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Edge detectors
        self._last_temp_low: Optional[float] = None
        self._last_temp_high: Optional[float] = None
        self._last_temp_calc: Optional[float] = None
        self._last_hum_low: Optional[float] = None
        self._last_hum_high: Optional[float] = None
        self._last_hum_calc: Optional[float] = None
        self._last_mod_u: Optional[int] = None
        self._last_mod_v: Optional[int] = None
        self._last_mod_w: Optional[int] = None
        self._last_mod_total: Optional[int] = None
        self._last_hold_mode: Optional[str] = None
        self._last_is_paused: Optional[bool] = None
        # Session-constant snapshot for CSV comment + sauna_sessions parent row.
        self.session_kp: Optional[float] = None
        self.session_ki: Optional[float] = None
        self.session_kd: Optional[float] = None
        self.session_fireorder: Optional[str] = None

        self._repo_root: Path = Path(__file__).resolve().parent.parent
        self._sessionlog_dir: Path = self._repo_root / "sessionlog"

    def ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Create/migrate sauna_session_samples and session-constant columns on sauna_sessions."""
        self._ensure_session_const_columns(conn)
        c = conn.cursor()
        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sauna_session_samples'"
        )
        exists = c.fetchone() is not None
        if not exists:
            conn.execute(_SAMPLES_CREATE_SQL)
        else:
            c.execute("PRAGMA table_info(sauna_session_samples)")
            cols = {row[1] for row in c.fetchall()}
            if any(name in cols for name in _SAMPLE_SESSION_CONST_COLS):
                self._backfill_session_constants_from_samples(conn)
                self._rebuild_samples_table(conn, cols)
            elif "setpoint_bias" not in cols:
                conn.execute("ALTER TABLE sauna_session_samples ADD COLUMN setpoint_bias REAL")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sauna_samples_session "
            "ON sauna_session_samples(session_id)"
        )

    @staticmethod
    def _ensure_session_const_columns(conn: sqlite3.Connection) -> None:
        """Add kp/ki/kd/fireorder to sauna_sessions when missing."""
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sauna_sessions'")
        if c.fetchone() is None:
            return
        c.execute("PRAGMA table_info(sauna_sessions)")
        cols = {row[1] for row in c.fetchall()}
        for name, decl in (
            ("kp", "REAL"),
            ("ki", "REAL"),
            ("kd", "REAL"),
            ("fireorder", "TEXT"),
        ):
            if name not in cols:
                conn.execute(f"ALTER TABLE sauna_sessions ADD COLUMN {name} {decl}")

    @staticmethod
    def _backfill_session_constants_from_samples(conn: sqlite3.Connection) -> None:
        """Copy kp/ki/kd/fireorder from historical sample rows onto sauna_sessions."""
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sauna_sessions'")
        if c.fetchone() is None:
            return
        c.execute("PRAGMA table_info(sauna_session_samples)")
        sample_cols = {row[1] for row in c.fetchall()}
        if not any(name in sample_cols for name in _SAMPLE_SESSION_CONST_COLS):
            return
        # Gains were constant per session; take the earliest usable sample per column.
        assignments: List[str] = []
        if "kp" in sample_cols:
            assignments.append(
                """kp = COALESCE(kp, (
                    SELECT s.kp FROM sauna_session_samples s
                    WHERE s.session_id = sauna_sessions.session_id AND s.kp IS NOT NULL
                    ORDER BY s.ts ASC LIMIT 1
                ))"""
            )
        if "ki" in sample_cols:
            assignments.append(
                """ki = COALESCE(ki, (
                    SELECT s.ki FROM sauna_session_samples s
                    WHERE s.session_id = sauna_sessions.session_id AND s.ki IS NOT NULL
                    ORDER BY s.ts ASC LIMIT 1
                ))"""
            )
        if "kd" in sample_cols:
            assignments.append(
                """kd = COALESCE(kd, (
                    SELECT s.kd FROM sauna_session_samples s
                    WHERE s.session_id = sauna_sessions.session_id AND s.kd IS NOT NULL
                    ORDER BY s.ts ASC LIMIT 1
                ))"""
            )
        if "fireorder" in sample_cols:
            assignments.append(
                """fireorder = COALESCE(fireorder, (
                    SELECT s.fireorder FROM sauna_session_samples s
                    WHERE s.session_id = sauna_sessions.session_id
                      AND s.fireorder IS NOT NULL
                      AND s.fireorder != ''
                      AND s.fireorder != '--'
                    ORDER BY s.ts ASC LIMIT 1
                ))"""
            )
        if assignments:
            c.execute("UPDATE sauna_sessions SET " + ", ".join(assignments))

    def _rebuild_samples_table(self, conn: sqlite3.Connection, old_cols: Set[str]) -> None:
        """Drop kp/ki/kd/fireorder from samples; keep setpoint_bias (NULL on old rows)."""
        dest_cols = ["id", "session_id"] + list(SAMPLE_FIELDS)
        select_parts: List[str] = []
        for name in dest_cols:
            if name in old_cols:
                select_parts.append(name)
            elif name == "setpoint_bias":
                select_parts.append("NULL AS setpoint_bias")
            else:
                select_parts.append(f"NULL AS {name}")
        conn.execute("DROP TABLE IF EXISTS sauna_session_samples_new")
        conn.execute(_SAMPLES_CREATE_SQL.replace(
            "CREATE TABLE sauna_session_samples",
            "CREATE TABLE sauna_session_samples_new",
            1,
        ))
        dest_sql = ",".join(dest_cols)
        src_sql = ",".join(select_parts)
        conn.execute(
            f"INSERT INTO sauna_session_samples_new ({dest_sql}) "
            f"SELECT {src_sql} FROM sauna_session_samples"
        )
        conn.execute("DROP TABLE sauna_session_samples")
        conn.execute("ALTER TABLE sauna_session_samples_new RENAME TO sauna_session_samples")

    def start_session(self, start_unix: int) -> None:
        """Begin buffering for a new sauna session."""
        self.stop_heartbeat()
        self._buffer.clear()
        self._active = True
        self._session_start_unix = int(start_unix)
        self._reset_edges()
        self._snapshot_session_constants()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Sauna session telemetry buffer started.")

    def _snapshot_session_constants(self) -> None:
        """Capture kp/ki/kd/fireorder at SAUNA_ON for the parent row and CSV comment."""
        logic = getattr(self._sm, "sauna_logic", None)
        pid_obj = getattr(logic, "pid", None) if logic is not None else None
        self.session_kp = getattr(pid_obj, "kp", None) if pid_obj is not None else None
        self.session_ki = getattr(pid_obj, "ki", None) if pid_obj is not None else None
        self.session_kd = getattr(pid_obj, "kd", None) if pid_obj is not None else None
        fo = getattr(self._sm._state.sauna, "fireorder", None)
        if not fo or fo == "--":
            if logic is not None:
                fo = logic.get_current_order_string()
        if fo:
            fo = str(fo).replace(" -> ", "").replace("->", "")
        self.session_fireorder = fo if fo and fo != "--" else None

    def _reset_edges(self) -> None:
        self._last_temp_low = None
        self._last_temp_high = None
        self._last_temp_calc = None
        self._last_hum_low = None
        self._last_hum_high = None
        self._last_hum_calc = None
        self._last_mod_u = None
        self._last_mod_v = None
        self._last_mod_w = None
        self._last_mod_total = None
        self._last_hold_mode = None
        self._last_is_paused = None

    def stop_heartbeat(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        try:
            while self._active:
                await asyncio.sleep(_HEARTBEAT_SECS)
                if not self._active:
                    break
                state = self._sm.get_state_snapshot()
                if state.sauna.active:
                    self.capture(state, triggers={"heartbeat"})
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error(f"Sauna telemetry heartbeat failed: {exc}")

    def observe_climate(self, state: SystemState) -> None:
        """Call after sauna probe / composite climate updates while session may be active."""
        if not self._active or not state.sauna.active:
            return
        triggers: Set[str] = set()
        high_idx = self._sm.resolve_entity_id(ENTITY_SAUNA_HIGH)
        low_idx = self._sm.resolve_entity_id(ENTITY_SAUNA_LOW)
        high = _probe_dict(state, high_idx)
        low = _probe_dict(state, low_idx)
        t_high = high.get("temp")
        t_low = low.get("temp")
        h_high = high.get("hum")
        h_low = low.get("hum")
        t_calc = state.sensors.sauna_calc_temp
        h_calc = state.sensors.sauna_calc_hum

        if t_low != self._last_temp_low or t_high != self._last_temp_high or t_calc != self._last_temp_calc:
            triggers.add("climate_temp")
        if h_low != self._last_hum_low or h_high != self._last_hum_high or h_calc != self._last_hum_calc:
            triggers.add("climate_hum")
        if triggers:
            self.capture(state, triggers=triggers)

    def observe_mode(self, state: SystemState) -> None:
        """Call when hold_mode or is_paused may have changed."""
        if not self._active or not state.sauna.active:
            # Still allow capture on the tick that ends the session? skip — flush handles end.
            return
        triggers: Set[str] = set()
        if state.sauna.hold_mode != self._last_hold_mode:
            triggers.add("hold_mode")
        if state.sauna.is_paused != self._last_is_paused:
            triggers.add("is_paused")
        if triggers:
            self.capture(state, triggers=triggers)

    def observe_pid_tick(self, state: SystemState) -> None:
        """Call after every PID.compute (even when MOD unchanged)."""
        if not self._active or not state.sauna.active:
            return
        self.capture(state, triggers={"pid"})

    def observe_mod(self, state: SystemState) -> None:
        """Call when modulation / phases were written."""
        if not self._active or not state.sauna.active:
            return
        phases = normalize_phases_pwm(state.sauna.phases_pwm)
        mod_total = int(state.sauna.modulation_pwm or 0)
        if (
            phases.get("U") != self._last_mod_u
            or phases.get("V") != self._last_mod_v
            or phases.get("W") != self._last_mod_w
            or mod_total != self._last_mod_total
        ):
            self.capture(state, triggers={"mod"})

    def capture(self, state: SystemState, triggers: Set[str]) -> None:
        """Append one coalesced sample row for the given trigger set."""
        if not self._active:
            return
        if not triggers:
            return

        high_idx = self._sm.resolve_entity_id(ENTITY_SAUNA_HIGH)
        low_idx = self._sm.resolve_entity_id(ENTITY_SAUNA_LOW)
        door_idx = self._sm.resolve_entity_id(ENTITY_SAUNA_DOOR)
        mains_idx = self._sm.resolve_entity_id(ENTITY_MAINS_VOLTAGE)

        high = _probe_dict(state, high_idx)
        low = _probe_dict(state, low_idx)
        phases = normalize_phases_pwm(state.sauna.phases_pwm)
        mod_u = int(phases.get("U", 0))
        mod_v = int(phases.get("V", 0))
        mod_w = int(phases.get("W", 0))
        mod_total = int(state.sauna.modulation_pwm or 0)

        w_u, w_v, w_w = self._pa._sauna_effective_watts()
        v_line = _parse_voltage(state.devices.get(mains_idx) if mains_idx is not None else None)
        voltage_scaler = ((v_line / 230.0) ** 2) if v_line is not None else 1.0
        w_calc_u = voltage_scaler * (mod_u / 100.0) * float(w_u)
        w_calc_v = voltage_scaler * (mod_v / 100.0) * float(w_v)
        w_calc_w = voltage_scaler * (mod_w / 100.0) * float(w_w)
        w_calc_total = w_calc_u + w_calc_v + w_calc_w

        p_leak = float(getattr(self._pa, "_locked_leak_watts", 0.0) or 0.0)
        w_real = float(state.metrics.p_elements_real_watts or 0.0)
        w_measured = w_real + p_leak

        r_th: Optional[float] = None
        if state.sauna.active and w_real > 500.0:
            t_in = state.sensors.sauna_calc_temp
            t_out = state.sensors.outside_temp
            if t_in is not None and t_out is not None:
                try:
                    r_th = round((float(t_in) - float(t_out)) / w_real, 6)
                except (TypeError, ValueError, ZeroDivisionError):
                    r_th = None

        pid = getattr(self._sm, "sauna_logic", None)
        pid_obj = getattr(pid, "pid", None) if pid is not None else None

        def _pid_attr(name: str, default: Any = None) -> Any:
            return getattr(pid_obj, name, default) if pid_obj is not None else default

        row: Dict[str, Any] = {
            "ts": time.time(),
            "temp_low": low.get("temp"),
            "temp_high": high.get("temp"),
            "temp_calc": state.sensors.sauna_calc_temp,
            "hum_low": low.get("hum"),
            "hum_high": high.get("hum"),
            "hum_calc": state.sensors.sauna_calc_hum,
            "mod_u": mod_u,
            "mod_v": mod_v,
            "mod_w": mod_w,
            "mod_total": mod_total,
            "w_calc_u": round(w_calc_u, 2),
            "w_calc_v": round(w_calc_v, 2),
            "w_calc_w": round(w_calc_w, 2),
            "w_calc_total": round(w_calc_total, 2),
            "w_real_total": round(w_real, 2),
            "w_measured_total": round(w_measured, 2),
            "pid_p": _pid_attr("last_p"),
            "pid_i": _pid_attr("last_i"),
            "pid_d": _pid_attr("last_d"),
            "pid_error": _pid_attr("last_error"),
            "pid_output_raw": _pid_attr("last_output_raw"),
            "pid_dt_s": _pid_attr("last_dt"),
            "integral_reset_reason": _pid_attr("last_integral_reset_reason") or "",
            "setpoint_bias": _pid_attr("last_setpoint_bias"),
            "target_temp": state.sauna.target_temp,
            "hold_mode": state.sauna.hold_mode,
            "is_paused": 1 if state.sauna.is_paused else 0,
            "door_state": state.devices.get(door_idx) if door_idx is not None else None,
            "outside_temp": state.sensors.outside_temp,
            "r_th": r_th,
            "v_line": v_line,
            "p_leak": round(p_leak, 2),
            "trigger": "+".join(sorted(triggers)),
        }
        self._buffer.append(row)

        # Update edge memory after capture
        self._last_temp_low = row["temp_low"]
        self._last_temp_high = row["temp_high"]
        self._last_temp_calc = row["temp_calc"]
        self._last_hum_low = row["hum_low"]
        self._last_hum_high = row["hum_high"]
        self._last_hum_calc = row["hum_calc"]
        self._last_mod_u = mod_u
        self._last_mod_v = mod_v
        self._last_mod_w = mod_w
        self._last_mod_total = mod_total
        self._last_hold_mode = state.sauna.hold_mode
        self._last_is_paused = state.sauna.is_paused

    @staticmethod
    def _fmt_gain(value: Optional[float]) -> str:
        if value is None:
            return ""
        return f"{float(value):.1f}"

    def _csv_session_comment(self) -> str:
        """First CSV line: session-constant gains + frozen fireorder (not a data row)."""
        kp = self._fmt_gain(self.session_kp)
        ki = self._fmt_gain(self.session_ki)
        kd = self._fmt_gain(self.session_kd)
        fo = self.session_fireorder or "--"
        return f"# kp={kp} ki={ki} kd={kd} fireorder={fo}"

    def flush_blocking(self, session_id: int) -> Optional[str]:
        """
        Write buffer to SQLite + CSV. Returns CSV path or None.
        Must run off the event loop (to_thread).
        Clears the RAM buffer only after a successful write.
        """
        self._active = False
        rows = list(self._buffer)
        start_unix = self._session_start_unix or int(time.time())

        if not rows:
            logger.info("Sauna session telemetry: no samples to flush.")
            self._session_start_unix = None
            return None

        db_path = self._pa._db_path
        conn = sqlite3.connect(db_path)
        try:
            self.ensure_schema(conn)
            cols = [f for f in SAMPLE_FIELDS]
            placeholders = ",".join("?" for _ in cols)
            col_sql = ",".join(cols)
            insert_sql = (
                f"INSERT INTO sauna_session_samples (session_id,{col_sql}) "
                f"VALUES (?,{placeholders})"
            )
            payload = []
            for row in rows:
                payload.append(tuple([session_id] + [row.get(c) for c in cols]))
            conn.executemany(insert_sql, payload)
            conn.commit()
        finally:
            conn.close()

        self._sessionlog_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(start_unix).strftime("%Y%m%d_%H%M%S")
        csv_path = self._sessionlog_dir / f"sauna_session_{stamp}.csv"
        comment = self._csv_session_comment()
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            fh.write(comment + "\n")
            writer = csv.DictWriter(fh, fieldnames=SAMPLE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        # Only drop RAM after both SQLite and CSV succeeded.
        self._buffer.clear()
        self._session_start_unix = None

        logger.info(
            f"Sauna session telemetry flushed: {len(rows)} samples -> "
            f"session_id={session_id} csv={csv_path}"
        )
        return str(csv_path)

    def end_session_async(self, session_id: int) -> None:
        """Stop heartbeat and schedule blocking flush off the loop."""
        self.stop_heartbeat()
        # Freeze new samples; keep buffer until flush_blocking succeeds.
        self._active = False

        async def _run() -> None:
            try:
                path = await asyncio.to_thread(self.flush_blocking, session_id)
                if path:
                    await self._sm.logger.success(
                        f"Sauna session CSV written: {os.path.basename(path)}"
                    )
            except Exception as exc:
                await self._sm.logger.error(f"Sauna session telemetry flush failed: {exc}")

        asyncio.create_task(_run())
