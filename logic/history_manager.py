# --- file: logic/history_manager.py ---
import sqlite3
import time
import asyncio
from datetime import datetime
from typing import Any
from loguru import logger


class DeviceHistoryManager:
    """
    Manages persistent time-series data for UI insights.
    Tracks switch events over a rolling 30-day window.
    """

    def __init__(self, state_manager: Any):
        self.sm = state_manager
        self.db_path = "device_history.db"
        self._init_db()
        self._task = None

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS device_events (
                        idx INTEGER,
                        timestamp INTEGER,
                        state TEXT
                     )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ts ON device_events(idx, timestamp)')
        conn.commit()
        conn.close()

    def start(self) -> None:
        self.recalculate_all_insights()
        self._task = asyncio.create_task(self._daily_cull_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def log_event(self, idx: int, state: str) -> None:
        now = int(time.time())
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO device_events (idx, timestamp, state) VALUES (?, ?, ?)", (idx, now, state))
            conn.commit()
            conn.close()

            # Update insights for this idx immediately in RAM
            self._update_insight(idx, now, state)
        except Exception as e:
            logger.error(f"Failed to log device history for IDX {idx}: {e}")

    def _update_insight(self, idx: int, last_changed: int, state: str) -> None:
        now = int(time.time())
        now_dt = datetime.now()
        start_of_day = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        thirty_days_ago = now - (30 * 86400)

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM device_events WHERE idx = ? AND timestamp >= ?", (idx, start_of_day))
            today_count = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM device_events WHERE idx = ? AND timestamp >= ?", (idx, thirty_days_ago))
            month_count = c.fetchone()[0]
            conn.close()

            # Strictly divide by the full 30 days window
            daily_avg = round(month_count / 30.0, 1)

            if idx not in self.sm._state.metrics.device_insights:
                self.sm._state.metrics.device_insights[idx] = {}

            self.sm._state.metrics.device_insights[idx].update({
                "last_changed": last_changed,
                "today_count": today_count,
                "daily_avg": daily_avg,
                "state": state
            })
        except Exception as e:
            logger.error(f"Failed to calculate insights for IDX {idx}: {e}")

    def recalculate_all_insights(self) -> None:
        """Called on boot to populate the dictionary for all historically known devices."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT DISTINCT idx FROM device_events")
            rows = c.fetchall()
            conn.close()

            idxs = [row[0] for row in rows]
            for idx in idxs:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute("SELECT timestamp, state FROM device_events WHERE idx = ? ORDER BY timestamp DESC LIMIT 1",
                          (idx,))
                row = c.fetchone()
                conn.close()
                if row:
                    self._update_insight(idx, row[0], row[1])
        except Exception as e:
            logger.error(f"Failed to recalculate history insights on boot: {e}")

    async def _daily_cull_loop(self) -> None:
        """Background loop that deletes records older than 30 days to prevent DB bloat."""
        while True:
            try:
                await asyncio.sleep(86400)  # Check once a day
                thirty_days_ago = int(time.time()) - (30 * 86400)
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute("DELETE FROM device_events WHERE timestamp < ?", (thirty_days_ago,))
                conn.commit()
                conn.close()
                logger.info("Device history DB culled records older than 30 days.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily cull: {e}")