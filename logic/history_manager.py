# --- file: logic/history_manager.py ---
import sqlite3
import time
import asyncio
from datetime import datetime, timedelta
from typing import Any, List, Tuple, Dict, Optional
from loguru import logger


class DeviceHistoryManager:
    """
    Manages persistent time-series data for UI insights.
    Uses a Write-Ahead Logging (WAL) SQLite pattern with an in-memory queue
    to batch writes and prevent SD card degradation. Tracks switch events over a rolling 30-day window.
    """

    # Default fallback constants (can be overridden by config if implemented later)
    MAX_QUEUE_SIZE: int = 500
    FLUSH_INTERVAL: float = 60.0

    def __init__(self, state_manager: Any):
        self.sm = state_manager
        self.db_path = "device_history.db"

        # ⚡ IN-MEMORY TRACKING
        # Holds the baseline tallies to completely bypass SQLite SELECTs during live state changes
        self._today_counts: Dict[int, int] = {}
        self._month_counts: Dict[int, int] = {}

        # ⚡ RAM BUFFER
        # Stores unwritten database rows before they are flushed to disk
        self._write_queue: List[Tuple[int, int, str]] = []

        # Asyncio background tasks and synchronization primitives
        self._task: Optional[asyncio.Task] = None  # Midnight cull loop
        self._flush_task: Optional[asyncio.Task] = None  # Background flusher
        self._flush_event: asyncio.Event = asyncio.Event()  # Threshold trigger event

        self._init_db()

    def _init_db(self) -> None:
        """Initializes the SQLite schema and enables WAL mode for high concurrency."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # ⚡ WAL MODE
        # Write-Ahead Logging prevents 'database is locked' errors by allowing
        # simultaneous read and write operations.
        c.execute("PRAGMA journal_mode=WAL;")

        c.execute('''CREATE TABLE IF NOT EXISTS device_events (
                        idx INTEGER,
                        timestamp INTEGER,
                        state TEXT
                     )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_ts ON device_events(idx, timestamp)')

        conn.commit()
        conn.close()

    def start(self) -> None:
        """Boots the history manager, calculates baselines, and starts background loops."""
        # Calculate the initial baseline from the DB synchronously on boot
        self.recalculate_all_insights()

        # Bind the background loops to the running asyncio event loop
        self._task = asyncio.create_task(self._daily_cull_loop())
        self._flush_task = asyncio.create_task(self._batch_flush_loop())

    async def stop(self) -> None:
        """Safely tears down the history manager and flushes remaining RAM to disk."""
        if self._task:
            self._task.cancel()
        if self._flush_task:
            self._flush_task.cancel()

        # ⚡ ASYNC SHUTDOWN FLUSH
        # If there are leftovers in RAM, perform one final list swap and offload the write
        # to a background thread so we don't block the main event loop during shutdown.
        if self._write_queue:
            final_batch = self._write_queue
            self._write_queue = []
            logger.info(f"History Manager shutting down. Flushing final {len(final_batch)} records to disk.")
            await asyncio.to_thread(self._execute_batch_insert, final_batch)

    def log_event(self, idx: int, state: str) -> None:
        """
        Captures a device state transition. Appends to the RAM queue and immediately
        updates the UI insights using in-memory mathematics (zero disk I/O).
        """
        now = int(time.time())

        # 1. Add to the RAM queue for eventual DB insertion
        self._write_queue.append((idx, now, state))

        # 2. Instantly update UI insights via RAM
        self._update_insight_in_memory(idx, now, state)

        # 3. Storm Threshold Trigger: If queue exceeds maximum size, force an immediate flush
        if len(self._write_queue) >= self.MAX_QUEUE_SIZE:
            self._flush_event.set()

    def _update_insight_in_memory(self, idx: int, last_changed: int, state: str) -> None:
        """
        Increments the tracking metrics mathematically in RAM without querying SQLite.
        Pushes the result straight to the StateManager's metrics dashboard.
        """
        # Increment tallies
        self._today_counts[idx] = self._today_counts.get(idx, 0) + 1
        self._month_counts[idx] = self._month_counts.get(idx, 0) + 1

        # Calculate trailing 30-day average
        daily_avg = round(self._month_counts[idx] / 30.0, 1)

        # Ensure the dictionary node exists for this device
        if idx not in self.sm._state.metrics.device_insights:
            self.sm._state.metrics.device_insights[idx] = {}

        # Push instantly to UI state
        self.sm._state.metrics.device_insights[idx].update({
            "last_changed": last_changed,
            "today_count": self._today_counts[idx],
            "daily_avg": daily_avg,
            "state": state
        })

    def recalculate_all_insights(self) -> None:
        """
        Called on boot (and exactly at midnight). Runs the heavy SQL COUNT(*) queries
        once to populate the RAM tracking dictionaries for all historically known devices.
        """
        now = int(time.time())
        now_dt = datetime.now()
        start_of_day = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        thirty_days_ago = now - (30 * 86400)

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # Fetch all known devices
            c.execute("SELECT DISTINCT idx FROM device_events")
            rows = c.fetchall()
            idxs = [row[0] for row in rows]

            for idx in idxs:
                # Get the most recent state
                c.execute("SELECT timestamp, state FROM device_events WHERE idx = ? ORDER BY timestamp DESC LIMIT 1",
                          (idx,))
                latest_row = c.fetchone()

                # Baseline Today's count
                c.execute("SELECT COUNT(*) FROM device_events WHERE idx = ? AND timestamp >= ?", (idx, start_of_day))
                today_count = c.fetchone()[0]
                self._today_counts[idx] = today_count

                # Baseline Month's count
                c.execute("SELECT COUNT(*) FROM device_events WHERE idx = ? AND timestamp >= ?", (idx, thirty_days_ago))
                month_count = c.fetchone()[0]
                self._month_counts[idx] = month_count

                if latest_row:
                    # Sync the RAM metrics to the state manager
                    self._update_insight_in_memory(idx, latest_row[0], latest_row[1])

            conn.close()
            logger.info("Successfully calculated Device History insights baselines.")
        except Exception as e:
            logger.error(f"Failed to recalculate history insights on boot/midnight: {e}")

    def _execute_batch_insert(self, batch: List[Tuple[int, int, str]]) -> None:
        """
        The blocking SQLite execution. Processes hundreds of rows at once.
        WARNING: This should only ever be called via asyncio.to_thread()
        """
        if not batch:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # executemany is highly optimized in SQLite for bulk inserts
            c.executemany("INSERT INTO device_events (idx, timestamp, state) VALUES (?, ?, ?)", batch)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed bulk insert to history DB: {e}")

    async def _batch_flush_loop(self) -> None:
        """
        Background loop that writes RAM to disk. Triggers either when the timer
        expires (60s) or when the event queue size threshold is hit.
        """
        while True:
            try:
                # Wait for the threshold event OR the 60-second timeout
                await asyncio.wait_for(self._flush_event.wait(), timeout=self.FLUSH_INTERVAL)
                self._flush_event.clear()
            except asyncio.TimeoutError:
                # Timeout is normal (60 seconds passed). Proceed to flush.
                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Recorder flush loop: {e}")

            if self._write_queue:
                # ⚡ ATOMIC LIST SWAP (Fixes the Race Condition)
                # Capture the current queue and instantly reset the class attribute
                # to a fresh list before yielding thread control.
                batch_to_write = self._write_queue
                self._write_queue = []

                # Offload the blocking disk I/O to a background thread
                await asyncio.to_thread(self._execute_batch_insert, batch_to_write)

    async def _daily_cull_loop(self) -> None:
        """
        Background loop that aligns exactly with midnight.
        Deletes DB records older than 30 days and recalculates RAM tracking baselines.
        """
        while True:
            try:
                # Dynamically calculate exact seconds until the next midnight rollover
                now_dt = datetime.now()
                next_midnight = (now_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_seconds = (next_midnight - now_dt).total_seconds()

                await asyncio.sleep(sleep_seconds)

                # Midnight struck! Cull the database in a background thread
                thirty_days_ago = int(time.time()) - (30 * 86400)

                def _cull_db() -> None:
                    conn = sqlite3.connect(self.db_path)
                    c = conn.cursor()
                    c.execute("DELETE FROM device_events WHERE timestamp < ?", (thirty_days_ago,))
                    conn.commit()
                    conn.close()

                await asyncio.to_thread(_cull_db)
                logger.info("Device history DB successfully culled records older than 30 days.")

                # ⚡ RESET DAILY BASELINES
                # Recalculate all insights from scratch to properly reset `_today_counts` to 0
                await asyncio.to_thread(self.recalculate_all_insights)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily cull: {e}")
                # Fallback sleep to prevent infinite rapid-fire loops on error
                await asyncio.sleep(60.0)