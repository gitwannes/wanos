# --- file: logic/history_manager.py ---
"""
Actuator / switch / shutter / door / speaker history.
Retention aligned with utility history (see docs/sensor_history.md):
  raw events 7d | hourly 31d | daily 1y
"""
from __future__ import annotations

import asyncio
import calendar
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from loguru import logger

# Types excluded from hub auto-logging (climate / utility / event-only)
EXCLUDED_TYPES = {
    "temp", "hum", "temp_hum", "motion", "scene",
    "power", "energy", "fluid", "sensor",
}

# Types that must not appear in actuator history list (climate goes via sensor history)
LIST_EXCLUDED_TYPES = {
    "temp", "hum", "temp_hum",
    "power", "energy", "fluid", "sensor",
}


def normalize_level(
    state: Any,
    device_snapshot: Any = None,
    *,
    bri: Any = None,
    volume: Any = None,
    level_max: float = 100.0,
) -> Optional[float]:
    """
    Map device state to chart level (0–level_max).
    OFF/OPEN -> 0; ON -> volume/bri if present else level_max; CLOSED -> level_max; numeric as-is.
    Speakers use device meta max_volume as level_max (Sonos/Onkyo); lights/blinds stay on 100.
    """
    ceiling = float(level_max) if level_max and level_max > 0 else 100.0

    # Prefer explicit level from rich payload when power is ON
    power = None
    if isinstance(device_snapshot, dict):
        power = device_snapshot.get("state")
        if volume is None:
            volume = device_snapshot.get("volume")
        if bri is None:
            bri = device_snapshot.get("bri")
    if power is None and isinstance(state, str):
        power = state

    if isinstance(state, (int, float)):
        return float(max(0, min(ceiling, state)))

    if isinstance(state, str):
        s = state.strip().upper()
        if s in ("OFF", "OPEN"):
            return 0.0
        if s == "CLOSED":
            return ceiling
        if s == "ON":
            for cand in (volume, bri):
                if isinstance(cand, (int, float)):
                    return float(max(0, min(ceiling, cand)))
            if isinstance(device_snapshot, dict):
                for key in ("volume", "bri"):
                    v = device_snapshot.get(key)
                    if isinstance(v, (int, float)):
                        return float(max(0, min(ceiling, v)))
            return ceiling
        if s.endswith("%"):
            try:
                return float(max(0, min(ceiling, float(s.replace("%", "")))))
            except ValueError:
                return None
        try:
            return float(max(0, min(ceiling, float(s))))
        except ValueError:
            return None

    if power is not None:
        return normalize_level(
            power, device_snapshot, bri=bri, volume=volume, level_max=ceiling
        )
    return None


def level_max_for_idx(manager: Any, idx: int) -> float:
    """Chart/history ceiling: speaker max_volume from meta, else 100."""
    try:
        meta = (getattr(manager, "_state", None) and manager._state.device_metadata or {}).get(idx) or {}
        mv = meta.get("max_volume")
        if mv is not None:
            n = float(mv)
            if n > 0:
                return n
    except (TypeError, ValueError):
        pass
    return 100.0


class DeviceHistoryManager:
    """
    WAL + batched writes for actuator state transitions and rollups.
    """

    MAX_QUEUE_SIZE: int = 500
    FLUSH_INTERVAL: float = 60.0

    def __init__(self, state_manager: Any):
        self.sm = state_manager
        self.db_path = "device_history.db"

        cfg = getattr(getattr(state_manager, "_config", None), "history", None)
        tz_name = getattr(cfg, "timezone", None) or "Europe/Brussels"
        try:
            self.tz = ZoneInfo(tz_name)
            self.timezone_name = tz_name
        except Exception:
            self.tz = ZoneInfo("Europe/Brussels")
            self.timezone_name = "Europe/Brussels"

        retention = getattr(cfg, "retention", None)
        self.hires_days = int(getattr(retention, "hires_days", 7) or 7)
        self.hourly_days = int(getattr(retention, "hourly_days", 31) or 31)
        self.daily_days = int(getattr(retention, "daily_days", 365) or 365)

        self._today_counts: Dict[int, int] = {}
        self._month_counts: Dict[int, int] = {}

        # (idx, ts, state, level)
        self._write_queue: List[Tuple[int, int, str, Optional[float]]] = []
        # RAM rollups until flush: (idx, key) -> {count, level_min, level_max, level_last}
        self._hour_buckets: Dict[Tuple[int, str], Dict[str, Any]] = {}
        self._day_buckets: Dict[Tuple[int, str], Dict[str, Any]] = {}

        self._task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._flush_event: asyncio.Event = asyncio.Event()

        self._init_db()

    def _now_local(self) -> datetime:
        return datetime.now(self.tz)

    def _hour_key(self, ts: Optional[int] = None) -> str:
        dt = datetime.fromtimestamp(ts or time.time(), self.tz)
        return dt.strftime("%Y-%m-%dT%H")

    def _day_key(self, ts: Optional[int] = None) -> str:
        dt = datetime.fromtimestamp(ts or time.time(), self.tz)
        return dt.strftime("%Y-%m-%d")

    def _days_in_month(self, dt: Optional[datetime] = None) -> int:
        d = dt or self._now_local()
        return calendar.monthrange(d.year, d.month)[1]

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute(
            """CREATE TABLE IF NOT EXISTS device_events (
                idx INTEGER,
                timestamp INTEGER,
                state TEXT,
                level REAL
            )"""
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_ts ON device_events(idx, timestamp)")
        # Migrate older DBs missing level
        c.execute("PRAGMA table_info(device_events)")
        cols = {row[1] for row in c.fetchall()}
        if "level" not in cols:
            c.execute("ALTER TABLE device_events ADD COLUMN level REAL")

        c.execute(
            """CREATE TABLE IF NOT EXISTS device_hourly (
                idx INTEGER NOT NULL,
                hour_key TEXT NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0,
                level_min REAL,
                level_max REAL,
                level_last REAL,
                PRIMARY KEY (idx, hour_key)
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS device_daily (
                idx INTEGER NOT NULL,
                day_key TEXT NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0,
                level_min REAL,
                level_max REAL,
                level_last REAL,
                PRIMARY KEY (idx, day_key)
            )"""
        )
        conn.commit()
        conn.close()

    def start(self) -> None:
        self.recalculate_all_insights()
        self._task = asyncio.create_task(self._daily_cull_loop())
        self._flush_task = asyncio.create_task(self._batch_flush_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._flush_task:
            self._flush_task.cancel()
        if self._write_queue or self._hour_buckets or self._day_buckets:
            await self._flush_all()

    def should_track(self, idx: int, dev_type: str) -> bool:
        if idx in (10001, 10002):
            return True
        return (dev_type or "") not in EXCLUDED_TYPES

    def should_list(self, idx: int, dev_type: str) -> bool:
        """Include motion/scene in history list; exclude continuous climate/utility."""
        if idx in (10001, 10002):
            return True
        dtype = dev_type or ""
        if dtype in ("motion", "scene"):
            return True
        return dtype not in LIST_EXCLUDED_TYPES

    def log_event(
        self,
        idx: int,
        state: str,
        level: Optional[float] = None,
        *,
        device_snapshot: Any = None,
        bri: Any = None,
        volume: Any = None,
    ) -> None:
        """Queue a state transition and update RAM insights + rollup buckets."""
        now = int(time.time())
        state_str = str(state) if state is not None else ""
        if level is None:
            level = normalize_level(
                state_str, device_snapshot, bri=bri, volume=volume,
                level_max=level_max_for_idx(self.sm, idx),
            )

        self._write_queue.append((idx, now, state_str, level))
        self._bump_rollup(idx, now, level)
        self._update_insight_in_memory(idx, now, state_str, increment=True)

        if len(self._write_queue) >= self.MAX_QUEUE_SIZE:
            self._flush_event.set()

    def _bump_rollup(self, idx: int, ts: int, level: Optional[float]) -> None:
        hk = (idx, self._hour_key(ts))
        dk = (idx, self._day_key(ts))
        for store, key in ((self._hour_buckets, hk), (self._day_buckets, dk)):
            b = store.get(key)
            if b is None:
                b = {"event_count": 0, "level_min": None, "level_max": None, "level_last": None}
                store[key] = b
            b["event_count"] += 1
            if level is not None:
                b["level_min"] = level if b["level_min"] is None else min(b["level_min"], level)
                b["level_max"] = level if b["level_max"] is None else max(b["level_max"], level)
                b["level_last"] = level

    def _update_insight_in_memory(
        self, idx: int, last_changed: int, state: str, *, increment: bool = True
    ) -> None:
        if increment:
            self._today_counts[idx] = self._today_counts.get(idx, 0) + 1
            self._month_counts[idx] = self._month_counts.get(idx, 0) + 1

        days = max(1, self._days_in_month())
        daily_avg = round(self._month_counts.get(idx, 0) / float(days), 1)

        if idx not in self.sm._state.metrics.device_insights:
            self.sm._state.metrics.device_insights[idx] = {}

        self.sm._state.metrics.device_insights[idx].update({
            "last_changed": last_changed,
            "today_count": self._today_counts.get(idx, 0),
            "daily_avg": daily_avg,
            "state": state,
        })

    def recalculate_all_insights(self) -> None:
        """Rebuild RAM tallies from DB (does not double-count)."""
        now_dt = self._now_local()
        start_of_day = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        start_of_month = int(now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        days = max(1, self._days_in_month(now_dt))

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT DISTINCT idx FROM device_events")
            idxs = [row[0] for row in c.fetchall()]

            self._today_counts = {}
            self._month_counts = {}

            for idx in idxs:
                c.execute(
                    "SELECT timestamp, state FROM device_events WHERE idx = ? ORDER BY timestamp DESC LIMIT 1",
                    (idx,),
                )
                latest = c.fetchone()

                c.execute(
                    "SELECT COUNT(*) FROM device_events WHERE idx = ? AND timestamp >= ?",
                    (idx, start_of_day),
                )
                today = int(c.fetchone()[0])
                self._today_counts[idx] = today

                # Prefer daily rollup for month if present
                month_prefix = now_dt.strftime("%Y-%m")
                c.execute(
                    "SELECT COALESCE(SUM(event_count), 0) FROM device_daily WHERE idx = ? AND day_key LIKE ?",
                    (idx, month_prefix + "%"),
                )
                month_from_daily = int(c.fetchone()[0])
                if month_from_daily > 0:
                    month = month_from_daily
                else:
                    c.execute(
                        "SELECT COUNT(*) FROM device_events WHERE idx = ? AND timestamp >= ?",
                        (idx, start_of_month),
                    )
                    month = int(c.fetchone()[0])
                self._month_counts[idx] = month

                if latest:
                    self.sm._state.metrics.device_insights[idx] = {
                        "last_changed": latest[0],
                        "today_count": today,
                        "daily_avg": round(month / float(days), 1),
                        "state": latest[1],
                    }

            conn.close()
            logger.info("Device History insights baselines recalculated.")
        except Exception as e:
            logger.error(f"Failed to recalculate history insights: {e}")

    async def _flush_all(self) -> None:
        batch = self._write_queue
        self._write_queue = []
        hours = self._hour_buckets
        days = self._day_buckets
        self._hour_buckets = {}
        self._day_buckets = {}
        await asyncio.to_thread(self._execute_flush, batch, hours, days)

    def _execute_flush(
        self,
        batch: List[Tuple[int, int, str, Optional[float]]],
        hours: Dict[Tuple[int, str], Dict[str, Any]],
        days: Dict[Tuple[int, str], Dict[str, Any]],
    ) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            if batch:
                c.executemany(
                    "INSERT INTO device_events (idx, timestamp, state, level) VALUES (?, ?, ?, ?)",
                    batch,
                )
            for (idx, hour_key), b in hours.items():
                if b.get("event_count", 0) <= 0 and b.get("level_last") is None:
                    continue
                c.execute(
                    """INSERT INTO device_hourly(idx, hour_key, event_count, level_min, level_max, level_last)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(idx, hour_key) DO UPDATE SET
                         event_count = device_hourly.event_count + excluded.event_count,
                         level_min = CASE
                           WHEN device_hourly.level_min IS NULL THEN excluded.level_min
                           WHEN excluded.level_min IS NULL THEN device_hourly.level_min
                           ELSE MIN(device_hourly.level_min, excluded.level_min) END,
                         level_max = CASE
                           WHEN device_hourly.level_max IS NULL THEN excluded.level_max
                           WHEN excluded.level_max IS NULL THEN device_hourly.level_max
                           ELSE MAX(device_hourly.level_max, excluded.level_max) END,
                         level_last = COALESCE(excluded.level_last, device_hourly.level_last)
                    """,
                    (idx, hour_key, b["event_count"], b["level_min"], b["level_max"], b["level_last"]),
                )
            for (idx, day_key), b in days.items():
                if b.get("event_count", 0) <= 0 and b.get("level_last") is None:
                    continue
                c.execute(
                    """INSERT INTO device_daily(idx, day_key, event_count, level_min, level_max, level_last)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(idx, day_key) DO UPDATE SET
                         event_count = device_daily.event_count + excluded.event_count,
                         level_min = CASE
                           WHEN device_daily.level_min IS NULL THEN excluded.level_min
                           WHEN excluded.level_min IS NULL THEN device_daily.level_min
                           ELSE MIN(device_daily.level_min, excluded.level_min) END,
                         level_max = CASE
                           WHEN device_daily.level_max IS NULL THEN excluded.level_max
                           WHEN excluded.level_max IS NULL THEN device_daily.level_max
                           ELSE MAX(device_daily.level_max, excluded.level_max) END,
                         level_last = COALESCE(excluded.level_last, device_daily.level_last)
                    """,
                    (idx, day_key, b["event_count"], b["level_min"], b["level_max"], b["level_last"]),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed bulk flush to device history DB: {e}")

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
                logger.error(f"Error in device history flush loop: {e}")

            if self._write_queue or self._hour_buckets or self._day_buckets:
                await self._flush_all()

    async def _daily_cull_loop(self) -> None:
        while True:
            try:
                now_dt = self._now_local()
                next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                await asyncio.sleep(max(1.0, (next_midnight - now_dt).total_seconds()))
                await self._flush_all()
                await asyncio.to_thread(self._cull_db)
                await asyncio.to_thread(self.recalculate_all_insights)
                logger.info("Device history midnight cull + insights reset complete.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in device history daily cull: {e}")
                await asyncio.sleep(60.0)

    def _cull_db(self) -> None:
        now = int(time.time())
        hires_cut = now - self.hires_days * 86400
        hourly_cut = (self._now_local() - timedelta(days=self.hourly_days)).strftime("%Y-%m-%dT%H")
        daily_cut = (self._now_local() - timedelta(days=self.daily_days)).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM device_events WHERE timestamp < ?", (hires_cut,))
        c.execute("DELETE FROM device_hourly WHERE hour_key < ?", (hourly_cut,))
        c.execute("DELETE FROM device_daily WHERE day_key < ?", (daily_cut,))
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------ queries
    def _format_status(self, idx: int, raw: Any, meta: Dict[str, Any]) -> str:
        dtype = meta.get("type", "")
        if isinstance(raw, dict):
            st = raw.get("state", "?")
            if dtype == "speaker" and raw.get("volume") is not None and st == "ON":
                return f"ON {raw.get('volume')}%"
            if dtype in ("light", "switch") and raw.get("bri") is not None and st == "ON":
                return f"ON {raw.get('bri')}%"
            return str(st)
        if dtype in ("blinds", "shutter"):
            try:
                v = int(raw)
                if v == 0:
                    return "OPEN"
                if v == 100:
                    return "CLOSED"
                return f"{v}%"
            except (TypeError, ValueError):
                return str(raw)
        if raw in ("OPEN", "CLOSED"):
            return str(raw)
        return str(raw) if raw is not None else "—"

    def list_actuators(self) -> List[Dict[str, Any]]:
        """Overview rows for devices that have at least one history event."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT DISTINCT idx FROM device_events")
        idxs = [r[0] for r in c.fetchall()]
        # Also include from daily if events culled
        c.execute("SELECT DISTINCT idx FROM device_daily")
        for r in c.fetchall():
            if r[0] not in idxs:
                idxs.append(r[0])
        conn.close()

        days = max(1, self._days_in_month())
        out: List[Dict[str, Any]] = []
        for idx in idxs:
            meta = self.sm._state.device_metadata.get(idx, {}) or {}
            dtype = meta.get("type", "")
            if not self.should_list(idx, dtype):
                continue
            name = meta.get("name") or f"IDX {idx}"
            raw = self.sm._state.devices.get(idx)
            insight = self.sm._state.metrics.device_insights.get(idx, {})
            if dtype in ("motion", "scene"):
                status = "—"
                if insight.get("last_changed"):
                    status = "hit"
            else:
                status = self._format_status(idx, raw, meta)
            out.append({
                "idx": idx,
                "name": name,
                "type": dtype or "switch",
                "status": status,
                "last_changed": insight.get("last_changed"),
                "today_count": insight.get("today_count", self._today_counts.get(idx, 0)),
                "daily_avg": insight.get(
                    "daily_avg",
                    round(self._month_counts.get(idx, 0) / float(days), 1),
                ),
                "month_count": self._month_counts.get(idx, 0),
                "hidden": bool(meta.get("hidden")),
            })
        out.sort(key=lambda r: (str(r["name"]).lower(), r["idx"]))
        return out

    def _impulse_level_series(self, events: List[Tuple[int, Any, Optional[float]]]) -> List[Dict[str, Any]]:
        """Expand rising-edge hits into short spikes for day charts."""
        points: List[Dict[str, Any]] = []
        for ts, state, level in events:
            lv = level if level is not None else normalize_level(state)
            if lv is None:
                lv = 100.0
            t_ms = ts * 1000
            points.append({"t": t_ms - 1, "v": 0.0})
            points.append({"t": t_ms, "v": float(lv)})
            points.append({"t": t_ms + 1, "v": 0.0})
        return points

    def _step_level_series(
        self,
        events: List[Tuple[int, Any, Optional[float]]],
        since_ts: int,
        until_ts: int,
        prev_level: Optional[float],
        *,
        level_max: float = 100.0,
    ) -> List[Dict[str, Any]]:
        """
        Build a hold-last step series spanning the full window.
        Without start/end anchors, ECharts only draws through the last event and
        sparse switch toggles look crushed into a thin left-hand spike.
        """
        if not events and prev_level is None:
            return []

        points: List[Dict[str, Any]] = []
        level = 0.0 if prev_level is None else float(prev_level)
        points.append({"t": since_ts * 1000, "v": level})

        for ts, state, raw_level in events:
            lv = raw_level if raw_level is not None else normalize_level(
                state, level_max=level_max
            )
            if lv is None:
                continue
            level = float(lv)
            t_ms = int(ts) * 1000
            # Keep step edges sharp even when multiple events share a second.
            if points and points[-1]["t"] >= t_ms:
                t_ms = points[-1]["t"] + 1
            points.append({"t": t_ms, "v": level})

        end_ms = max(until_ts * 1000, points[-1]["t"] + 1)
        if points[-1]["t"] < end_ms:
            points.append({"t": end_ms, "v": level})
        return points

    def get_actuator_series(self, idx: int, range_name: str) -> Dict[str, Any]:
        range_name = (range_name or "day").lower()
        meta = self.sm._state.device_metadata.get(idx, {}) or {}
        name = meta.get("name") or f"IDX {idx}"
        dtype = meta.get("type", "")
        impulse = dtype in ("motion", "scene")
        ceiling = level_max_for_idx(self.sm, idx)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if range_name == "day":
            until_ts = int(time.time())
            since = until_ts - 86400
            c.execute(
                "SELECT timestamp, state, level FROM device_events WHERE idx = ? AND timestamp >= ? ORDER BY timestamp",
                (idx, since),
            )
            rows = list(c.fetchall())
            prev_level: Optional[float] = None
            if not impulse:
                c.execute(
                    """SELECT state, level FROM device_events
                       WHERE idx = ? AND timestamp < ?
                       ORDER BY timestamp DESC LIMIT 1""",
                    (idx, since),
                )
                prev = c.fetchone()
                if prev:
                    prev_level = prev[1] if prev[1] is not None else normalize_level(
                        prev[0], level_max=ceiling
                    )
            conn.close()
            if impulse:
                level_pts = self._impulse_level_series(rows)
            else:
                level_pts = self._step_level_series(
                    rows, since, until_ts, prev_level, level_max=ceiling
                )
            return {
                "idx": idx,
                "name": name,
                "type": dtype,
                "range": "day",
                "series": {"level": level_pts},
            }

        if range_name == "month":
            since_day = (self._now_local() - timedelta(days=31)).strftime("%Y-%m-%d")
            c.execute(
                """SELECT day_key, event_count, level_min, level_max, level_last
                   FROM device_daily WHERE idx = ? AND day_key >= ? ORDER BY day_key""",
                (idx, since_day),
            )
            counts, mins, maxs = [], [], []
            for day_key, cnt, lmin, lmax, _llast in c.fetchall():
                ts_ms = int(datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=self.tz).timestamp() * 1000)
                counts.append({"t": ts_ms, "v": cnt})
                mins.append({"t": ts_ms, "v": lmin})
                maxs.append({"t": ts_ms, "v": lmax})
            conn.close()
            return {
                "idx": idx,
                "name": name,
                "type": dtype,
                "range": "month",
                "series": {"event_count": counts, "level_min": mins, "level_max": maxs},
            }

        # year
        since_day = (self._now_local() - timedelta(days=366)).strftime("%Y-%m-%d")
        c.execute(
            """SELECT substr(day_key, 1, 7) AS ym,
                      SUM(event_count), MIN(level_min), MAX(level_max)
               FROM device_daily WHERE idx = ? AND day_key >= ?
               GROUP BY ym ORDER BY ym""",
            (idx, since_day),
        )
        counts, mins, maxs = [], [], []
        for ym, cnt, lmin, lmax in c.fetchall():
            ts_ms = int(datetime.strptime(ym + "-01", "%Y-%m-%d").replace(tzinfo=self.tz).timestamp() * 1000)
            counts.append({"t": ts_ms, "v": cnt})
            mins.append({"t": ts_ms, "v": lmin})
            maxs.append({"t": ts_ms, "v": lmax})
        conn.close()
        return {
            "idx": idx,
            "name": name,
            "type": dtype,
            "range": "year",
            "series": {"event_count": counts, "level_min": mins, "level_max": maxs},
        }
