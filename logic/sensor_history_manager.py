# --- file: logic/sensor_history_manager.py ---
"""Utility / power / water time-series history (see docs/sensor_history.md)."""
from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from loguru import logger

SENSOR_META: Dict[int, Dict[str, str]] = {
    11001: {"label": "House energy", "kind": "energy", "unit": "Wh"},
    11002: {"label": "Cold water", "kind": "water", "unit": "L"},
    11003: {"label": "Hot water", "kind": "water", "unit": "L"},
    74001: {"label": "PC power", "kind": "power", "unit": "W"},
    74003: {"label": "PC monitors power", "kind": "power", "unit": "W"},
}


def _resolve_tz(name: str):
    """Load IANA zone; requires OS package tzdata. Falls back to UTC if missing."""
    try:
        return ZoneInfo(name), name
    except Exception as e:
        logger.warning(f"zoneinfo unavailable for '{name}' ({e}); trying Europe/Brussels")
    try:
        return ZoneInfo("Europe/Brussels"), "Europe/Brussels"
    except Exception as e:
        logger.error(
            f"tzdata missing or unreadable ({e}); sensor history using UTC. "
            "Install: sudo apt install -y tzdata"
        )
        return timezone.utc, "UTC"



@dataclass
class _HourBucket:
    w_min: Optional[float] = None
    w_max: Optional[float] = None
    w_sum: float = 0.0
    w_count: int = 0
    consumption: float = 0.0  # Wh or liters
    incomplete: int = 0

    def note_watts(self, w: float) -> None:
        self.w_min = w if self.w_min is None else min(self.w_min, w)
        self.w_max = w if self.w_max is None else max(self.w_max, w)
        self.w_sum += w
        self.w_count += 1


@dataclass
class _DayBucket:
    w_min: Optional[float] = None
    w_max: Optional[float] = None
    w_sum: float = 0.0
    w_count: int = 0
    consumption: float = 0.0
    incomplete: int = 0
    counter_start: Optional[float] = None
    counter_end: Optional[float] = None

    def note_watts(self, w: float) -> None:
        self.w_min = w if self.w_min is None else min(self.w_min, w)
        self.w_max = w if self.w_max is None else max(self.w_max, w)
        self.w_sum += w
        self.w_count += 1


@dataclass
class _IdxRuntime:
    # kWh window for hi-res W samples
    window_start_ts: float = 0.0
    window_wh: float = 0.0
    # water liters since last history step
    pending_liters: float = 0.0
    # Z-Wave throttle / Wh integration
    last_zwave_ts: float = 0.0
    last_zwave_watts: Optional[float] = None
    # Gap tracking
    last_seen_ts: float = 0.0


class SensorHistoryManager:
    """
    Persists hi-res / hourly / daily utility history with WAL + batched writes.
    """

    MAX_QUEUE_SIZE: int = 400
    FLUSH_INTERVAL: float = 60.0

    def __init__(self, state_manager: Any) -> None:
        self.sm = state_manager
        self.db_path = "sensor_history.db"
        cfg = getattr(getattr(state_manager, "_config", None), "history", None)
        self.timezone_name = getattr(cfg, "timezone", None) or "Europe/Brussels"
        self.tz, self.timezone_name = _resolve_tz(self.timezone_name)

        retention = getattr(cfg, "retention", None)
        sample = getattr(cfg, "sample", None)
        self.hires_days = int(getattr(retention, "hires_days", 7) or 7)
        self.hourly_days = int(getattr(retention, "hourly_days", 31) or 31)
        self.daily_days = int(getattr(retention, "daily_days", 365) or 365)
        self.kwh_step_wh = float(getattr(sample, "kwh_step_wh", 100.0) or 100.0)
        self.water_step_l = float(getattr(sample, "water_step_l", 1.0) or 1.0)
        self.zwave_min_interval = float(getattr(sample, "zwave_min_interval_secs", 60.0) or 60.0)
        tracked = getattr(cfg, "tracked_idxs", None)
        self.tracked_idxs: List[int] = list(tracked) if tracked else [11001, 11002, 11003, 74001, 74003]

        self._runtime: Dict[int, _IdxRuntime] = {i: _IdxRuntime() for i in self.tracked_idxs}
        self._hour_buckets: Dict[Tuple[int, str], _HourBucket] = {}
        self._day_buckets: Dict[Tuple[int, str], _DayBucket] = {}

        self._sample_queue: List[Tuple[int, int, float, str]] = []
        self._flush_event: asyncio.Event = asyncio.Event()
        self._flush_task: Optional[asyncio.Task] = None
        self._midnight_task: Optional[asyncio.Task] = None
        self._boot_gap_incomplete: bool = False

        self._init_db()
        self._detect_boot_gap()

    # ------------------------------------------------------------------ DB
    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute(
            """CREATE TABLE IF NOT EXISTS sensor_samples (
                idx INTEGER NOT NULL,
                ts INTEGER NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL
            )"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_samples_idx_ts ON sensor_samples(idx, ts)")
        c.execute(
            """CREATE TABLE IF NOT EXISTS sensor_hourly (
                idx INTEGER NOT NULL,
                hour_key TEXT NOT NULL,
                w_min REAL,
                w_max REAL,
                w_avg REAL,
                consumption REAL NOT NULL DEFAULT 0,
                incomplete INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (idx, hour_key)
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS sensor_daily (
                idx INTEGER NOT NULL,
                day_key TEXT NOT NULL,
                w_min REAL,
                w_max REAL,
                w_avg REAL,
                consumption REAL NOT NULL DEFAULT 0,
                incomplete INTEGER NOT NULL DEFAULT 0,
                counter_start REAL,
                counter_end REAL,
                PRIMARY KEY (idx, day_key)
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS history_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
        )
        conn.commit()
        conn.close()

    def _meta_get(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT value FROM history_meta WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def _meta_set(self, key: str, value: str) -> None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "INSERT INTO history_meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()
        conn.close()

    def _detect_boot_gap(self) -> None:
        """Option B: if last heartbeat was long ago, mark next buckets incomplete."""
        raw = self._meta_get("last_heartbeat_ts")
        if not raw:
            return
        try:
            last = float(raw)
        except ValueError:
            return
        gap = time.time() - last
        if gap > 3600:
            self._boot_gap_incomplete = True
            logger.info(f"Sensor history: boot gap of {int(gap)}s — marking next buckets incomplete")

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._flush_task = asyncio.create_task(self._batch_flush_loop())
        self._midnight_task = asyncio.create_task(self._midnight_loop())
        logger.info(
            f"SensorHistoryManager started (tz={self.timezone_name}, "
            f"hires={self.hires_days}d, hourly={self.hourly_days}d, daily={self.daily_days}d)"
        )

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
        if self._midnight_task:
            self._midnight_task.cancel()
        await self._flush_all()
        self._meta_set("last_heartbeat_ts", str(time.time()))

    # ------------------------------------------------------------------ time keys
    def _now_local(self) -> datetime:
        return datetime.now(self.tz)

    def _hour_key(self, ts: Optional[float] = None) -> str:
        dt = datetime.fromtimestamp(ts or time.time(), self.tz)
        return dt.strftime("%Y-%m-%dT%H")

    def _day_key(self, ts: Optional[float] = None) -> str:
        dt = datetime.fromtimestamp(ts or time.time(), self.tz)
        return dt.strftime("%Y-%m-%d")

    def _get_hour(self, idx: int, hour_key: Optional[str] = None) -> _HourBucket:
        key = (idx, hour_key or self._hour_key())
        if key not in self._hour_buckets:
            b = _HourBucket()
            if self._boot_gap_incomplete:
                b.incomplete = 1
            self._hour_buckets[key] = b
        return self._hour_buckets[key]

    def _get_day(self, idx: int, day_key: Optional[str] = None) -> _DayBucket:
        key = (idx, day_key or self._day_key())
        if key not in self._day_buckets:
            b = _DayBucket()
            if self._boot_gap_incomplete:
                b.incomplete = 1
            self._day_buckets[key] = b
        return self._day_buckets[key]

    def _clear_boot_gap_flag_if_needed(self) -> None:
        if self._boot_gap_incomplete:
            self._boot_gap_incomplete = False

    # ------------------------------------------------------------------ ingest API
    def note_kwh_pulse(self, idx: int = 11001, wh: float = 1.0, instant_watts: Optional[float] = None) -> None:
        if idx not in self.tracked_idxs:
            return
        now = time.time()
        rt = self._runtime[idx]
        if rt.window_start_ts <= 0:
            rt.window_start_ts = now

        hour = self._get_hour(idx)
        day = self._get_day(idx)
        hour.consumption += wh
        day.consumption += wh
        if day.counter_start is None:
            cur = self.sm._state.devices.get(idx)
            if isinstance(cur, (int, float)):
                day.counter_start = float(cur) - wh
        if isinstance(self.sm._state.devices.get(idx), (int, float)):
            day.counter_end = float(self.sm._state.devices[idx])

        rt.window_wh += wh
        rt.last_seen_ts = now

        if rt.window_wh >= self.kwh_step_wh:
            dt = max(now - rt.window_start_ts, 0.001)
            watts = instant_watts if instant_watts is not None else (3600.0 * rt.window_wh / dt)
            self._enqueue_sample(idx, int(now), watts, "W")
            hour.note_watts(watts)
            day.note_watts(watts)
            rt.window_wh = 0.0
            rt.window_start_ts = now
            self._clear_boot_gap_flag_if_needed()

    def note_water_pulse(self, idx: int, added_liters: float) -> None:
        if idx not in self.tracked_idxs or added_liters <= 0:
            return
        now = time.time()
        rt = self._runtime[idx]
        rt.pending_liters += added_liters
        rt.last_seen_ts = now

        # Accrue all liters into buckets immediately
        hour = self._get_hour(idx)
        day = self._get_day(idx)
        hour.consumption += added_liters
        day.consumption += added_liters
        if day.counter_start is None:
            cur = self.sm._state.devices.get(idx)
            if isinstance(cur, (int, float)):
                day.counter_start = float(cur) - added_liters
        if isinstance(self.sm._state.devices.get(idx), (int, float)):
            day.counter_end = float(self.sm._state.devices[idx])

        # History "sample" cadence: every whole liter step (no W series)
        while rt.pending_liters >= self.water_step_l:
            rt.pending_liters -= self.water_step_l
            self._clear_boot_gap_flag_if_needed()

    def note_power_watts(self, idx: int, watts: float) -> None:
        if idx not in self.tracked_idxs:
            return
        meta = SENSOR_META.get(idx, {})
        if meta.get("kind") != "power":
            return

        now = time.time()
        rt = self._runtime[idx]

        # Integrate Wh since last accepted sample (even if we throttle the write)
        if rt.last_zwave_ts > 0 and rt.last_zwave_watts is not None:
            dt = now - rt.last_zwave_ts
            if dt > 0 and dt < 3600 * 6:
                # Gap policy: long silence → incomplete, still attribute energy to recovery interval
                if dt > self.zwave_min_interval * 3:
                    self._get_hour(idx).incomplete = 1
                    self._get_day(idx).incomplete = 1
                wh = max(0.0, rt.last_zwave_watts) * (dt / 3600.0)
                self._get_hour(idx).consumption += wh
                self._get_day(idx).consumption += wh

        if rt.last_zwave_ts > 0 and (now - rt.last_zwave_ts) < self.zwave_min_interval:
            # Still update last watts for smoother integration on next accept
            rt.last_zwave_watts = watts
            return

        self._enqueue_sample(idx, int(now), watts, "W")
        hour = self._get_hour(idx)
        day = self._get_day(idx)
        hour.note_watts(watts)
        day.note_watts(watts)
        rt.last_zwave_ts = now
        rt.last_zwave_watts = watts
        rt.last_seen_ts = now
        self._clear_boot_gap_flag_if_needed()

    def _enqueue_sample(self, idx: int, ts: int, value: float, unit: str) -> None:
        self._sample_queue.append((idx, ts, float(value), unit))
        if len(self._sample_queue) >= self.MAX_QUEUE_SIZE:
            self._flush_event.set()

    # ------------------------------------------------------------------ flush / cull
    async def _batch_flush_loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._flush_event.wait(), timeout=self.FLUSH_INTERVAL)
                self._flush_event.clear()
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sensor history flush loop error: {e}")
            await self._flush_all()

    async def _flush_all(self) -> None:
        samples = self._sample_queue
        self._sample_queue = []
        hours = dict(self._hour_buckets)
        days = dict(self._day_buckets)
        # Keep current hour/day in RAM; still upsert them
        await asyncio.to_thread(self._execute_flush, samples, hours, days)
        self._meta_set("last_heartbeat_ts", str(time.time()))

    def _execute_flush(
        self,
        samples: List[Tuple[int, int, float, str]],
        hours: Dict[Tuple[int, str], _HourBucket],
        days: Dict[Tuple[int, str], _DayBucket],
    ) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            if samples:
                c.executemany(
                    "INSERT INTO sensor_samples(idx, ts, value, unit) VALUES (?, ?, ?, ?)",
                    samples,
                )
            for (idx, hour_key), b in hours.items():
                w_avg = (b.w_sum / b.w_count) if b.w_count else None
                c.execute(
                    """INSERT INTO sensor_hourly(idx, hour_key, w_min, w_max, w_avg, consumption, incomplete)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(idx, hour_key) DO UPDATE SET
                         w_min=excluded.w_min,
                         w_max=excluded.w_max,
                         w_avg=excluded.w_avg,
                         consumption=excluded.consumption,
                         incomplete=CASE WHEN excluded.incomplete > sensor_hourly.incomplete
                                         THEN excluded.incomplete ELSE sensor_hourly.incomplete END
                    """,
                    (idx, hour_key, b.w_min, b.w_max, w_avg, b.consumption, b.incomplete),
                )
            for (idx, day_key), b in days.items():
                w_avg = (b.w_sum / b.w_count) if b.w_count else None
                c.execute(
                    """INSERT INTO sensor_daily(idx, day_key, w_min, w_max, w_avg, consumption, incomplete,
                                                counter_start, counter_end)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(idx, day_key) DO UPDATE SET
                         w_min=excluded.w_min,
                         w_max=excluded.w_max,
                         w_avg=excluded.w_avg,
                         consumption=excluded.consumption,
                         incomplete=CASE WHEN excluded.incomplete > sensor_daily.incomplete
                                         THEN excluded.incomplete ELSE sensor_daily.incomplete END,
                         counter_start=COALESCE(sensor_daily.counter_start, excluded.counter_start),
                         counter_end=excluded.counter_end
                    """,
                    (
                        idx,
                        day_key,
                        b.w_min,
                        b.w_max,
                        w_avg,
                        b.consumption,
                        b.incomplete,
                        b.counter_start,
                        b.counter_end,
                    ),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Sensor history flush failed: {e}")

    async def _midnight_loop(self) -> None:
        while True:
            try:
                now = self._now_local()
                nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                await asyncio.sleep(max(1.0, (nxt - now).total_seconds()))
                await self._flush_all()
                await asyncio.to_thread(self._cull_old)
                # Drop closed day/hour RAM keys older than today
                today = self._day_key()
                self._day_buckets = {k: v for k, v in self._day_buckets.items() if k[1] >= today}
                cur_hour = self._hour_key()
                self._hour_buckets = {k: v for k, v in self._hour_buckets.items() if k[1] >= cur_hour[:10]}
                logger.info("Sensor history midnight close + cull complete")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sensor history midnight loop error: {e}")
                await asyncio.sleep(60.0)

    def _cull_old(self) -> None:
        now = int(time.time())
        hires_cut = now - self.hires_days * 86400
        hourly_cut_dt = self._now_local() - timedelta(days=self.hourly_days)
        daily_cut_dt = self._now_local() - timedelta(days=self.daily_days)
        hourly_cut = hourly_cut_dt.strftime("%Y-%m-%dT%H")
        daily_cut = daily_cut_dt.strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM sensor_samples WHERE ts < ?", (hires_cut,))
        c.execute("DELETE FROM sensor_hourly WHERE hour_key < ?", (hourly_cut,))
        c.execute("DELETE FROM sensor_daily WHERE day_key < ?", (daily_cut,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ queries
    def list_sensors(self) -> List[Dict[str, Any]]:
        out = []
        for idx in self.tracked_idxs:
            meta = SENSOR_META.get(idx, {"label": f"IDX {idx}", "kind": "unknown", "unit": ""})
            out.append({"idx": idx, **meta})
        return out

    def get_series(self, idx: int, range_name: str) -> Dict[str, Any]:
        meta = SENSOR_META.get(idx, {"label": f"IDX {idx}", "kind": "unknown", "unit": ""})
        kind = meta.get("kind", "unknown")
        range_name = (range_name or "day").lower()
        if kind == "water":
            return self._series_water(idx, range_name, meta)
        return self._series_power(idx, range_name, meta)

    def _series_power(self, idx: int, range_name: str, meta: Dict[str, str]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if range_name == "day":
            since = int(time.time()) - 86400
            c.execute(
                "SELECT ts, value FROM sensor_samples WHERE idx = ? AND unit = 'W' AND ts >= ? ORDER BY ts",
                (idx, since),
            )
            points = [{"t": r[0] * 1000, "v": r[1]} for r in c.fetchall()]
            conn.close()
            return {"idx": idx, "range": "day", "kind": meta["kind"], "series": {"usage": points}, **meta}

        if range_name == "month":
            since_day = (self._now_local() - timedelta(days=31)).strftime("%Y-%m-%d")
            c.execute(
                "SELECT day_key, w_min, w_max, incomplete FROM sensor_daily WHERE idx = ? AND day_key >= ? ORDER BY day_key",
                (idx, since_day),
            )
            mins, maxs = [], []
            for day_key, w_min, w_max, incomplete in c.fetchall():
                ts_ms = int(datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=self.tz).timestamp() * 1000)
                # Gap: omit points when incomplete and no watt stats
                if w_min is None and w_max is None:
                    mins.append({"t": ts_ms, "v": None})
                    maxs.append({"t": ts_ms, "v": None})
                else:
                    mins.append({"t": ts_ms, "v": w_min})
                    maxs.append({"t": ts_ms, "v": w_max})
            conn.close()
            return {
                "idx": idx,
                "range": "month",
                "kind": meta["kind"],
                "series": {"usage_min": mins, "usage_max": maxs},
                **meta,
            }

        # year — monthly min-of-mins / max-of-maxes
        since_day = (self._now_local() - timedelta(days=366)).strftime("%Y-%m-%d")
        c.execute(
            """SELECT substr(day_key, 1, 7) AS ym,
                      MIN(w_min), MAX(w_max)
               FROM sensor_daily
               WHERE idx = ? AND day_key >= ? AND w_min IS NOT NULL
               GROUP BY ym ORDER BY ym""",
            (idx, since_day),
        )
        mins, maxs = [], []
        for ym, w_min, w_max in c.fetchall():
            ts_ms = int(datetime.strptime(ym + "-01", "%Y-%m-%d").replace(tzinfo=self.tz).timestamp() * 1000)
            mins.append({"t": ts_ms, "v": w_min})
            maxs.append({"t": ts_ms, "v": w_max})
        conn.close()
        return {
            "idx": idx,
            "range": "year",
            "kind": meta["kind"],
            "series": {"usage_min": mins, "usage_max": maxs},
            **meta,
        }

    def _series_water(self, idx: int, range_name: str, meta: Dict[str, str]) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if range_name == "day":
            since_hour = (self._now_local() - timedelta(hours=24)).strftime("%Y-%m-%dT%H")
            c.execute(
                "SELECT hour_key, consumption FROM sensor_hourly WHERE idx = ? AND hour_key >= ? ORDER BY hour_key",
                (idx, since_hour),
            )
            bars = []
            for hour_key, consumption in c.fetchall():
                ts_ms = int(datetime.strptime(hour_key, "%Y-%m-%dT%H").replace(tzinfo=self.tz).timestamp() * 1000)
                bars.append({"t": ts_ms, "v": consumption})
            conn.close()
            return {"idx": idx, "range": "day", "kind": meta["kind"], "series": {"liters": bars}, **meta}

        if range_name == "month":
            since_day = (self._now_local() - timedelta(days=31)).strftime("%Y-%m-%d")
            c.execute(
                "SELECT day_key, consumption FROM sensor_daily WHERE idx = ? AND day_key >= ? ORDER BY day_key",
                (idx, since_day),
            )
            bars = []
            for day_key, consumption in c.fetchall():
                ts_ms = int(datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=self.tz).timestamp() * 1000)
                bars.append({"t": ts_ms, "v": consumption})
            conn.close()
            return {"idx": idx, "range": "month", "kind": meta["kind"], "series": {"liters": bars}, **meta}

        since_day = (self._now_local() - timedelta(days=366)).strftime("%Y-%m-%d")
        c.execute(
            """SELECT substr(day_key, 1, 7) AS ym, SUM(consumption)
               FROM sensor_daily WHERE idx = ? AND day_key >= ?
               GROUP BY ym ORDER BY ym""",
            (idx, since_day),
        )
        bars = []
        for ym, total in c.fetchall():
            ts_ms = int(datetime.strptime(ym + "-01", "%Y-%m-%d").replace(tzinfo=self.tz).timestamp() * 1000)
            bars.append({"t": ts_ms, "v": total})
        conn.close()
        return {"idx": idx, "range": "year", "kind": meta["kind"], "series": {"liters": bars}, **meta}

    def get_summary(self, idx: int) -> Dict[str, Any]:
        meta = SENSOR_META.get(idx, {"label": f"IDX {idx}", "kind": "unknown", "unit": ""})
        kind = meta.get("kind")
        today = self._day_key()
        month_prefix = today[:7]
        year_prefix = today[:4]

        # Live RAM day bucket + DB
        today_cons = 0.0
        day_b = self._day_buckets.get((idx, today))
        if day_b:
            today_cons = day_b.consumption

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT consumption FROM sensor_daily WHERE idx = ? AND day_key = ?", (idx, today))
        row = c.fetchone()
        if row:
            today_cons = max(today_cons, float(row[0] or 0))

        c.execute(
            "SELECT COALESCE(SUM(consumption), 0) FROM sensor_daily WHERE idx = ? AND day_key LIKE ? AND day_key != ?",
            (idx, month_prefix + "%", today),
        )
        month_cons = float(c.fetchone()[0] or 0) + today_cons

        c.execute(
            "SELECT COALESCE(SUM(consumption), 0) FROM sensor_daily WHERE idx = ? AND day_key LIKE ? AND day_key != ?",
            (idx, year_prefix + "%", today),
        )
        year_cons = float(c.fetchone()[0] or 0) + today_cons
        conn.close()

        total = None
        cur = self.sm._state.devices.get(idx)
        if isinstance(cur, (int, float)):
            total = float(cur)

        # Normalize display units
        if kind == "energy":
            return {
                "idx": idx,
                **meta,
                "today": today_cons / 1000.0,
                "month": month_cons / 1000.0,
                "year": year_cons / 1000.0,
                "total": (total / 1000.0) if total is not None else None,
                "display_unit": "kWh",
            }
        if kind == "power":
            return {
                "idx": idx,
                **meta,
                "today": today_cons / 1000.0,
                "month": month_cons / 1000.0,
                "year": year_cons / 1000.0,
                "total": None,
                "display_unit": "kWh",
            }
        return {
            "idx": idx,
            **meta,
            "today": today_cons,
            "month": month_cons,
            "year": year_cons,
            "total": total,
            "display_unit": "L",
        }

    def get_sessions(self, session_type: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        table = "sauna_sessions" if session_type == "sauna" else "ir_sessions"
        db_path = getattr(self.sm._power_analytics, "_db_path", "sauna_sessions.db")
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) AS n FROM {table}")
            total = int(c.fetchone()["n"])
            c.execute(
                f"SELECT * FROM {table} ORDER BY session_id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return {"type": session_type, "total": total, "limit": limit, "offset": offset, "sessions": rows}
        except Exception as e:
            logger.error(f"Failed to read {table}: {e}")
            return {"type": session_type, "total": 0, "limit": limit, "offset": offset, "sessions": [], "error": str(e)}
