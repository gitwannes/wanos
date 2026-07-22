# ⚡ WanOS Architectural Upgrades: Home Assistant Patterns

This document provides the exact implementation steps to upgrade WanOS with three enterprise-grade smart home patterns:
* SQLite batching (to save your Pi's SD card)
* a Logical Entity Registry (for the upcoming GUI)
* Strict Payload Validation (to prevent bad data from crashing the engine).

---

## 💾 1. The SQLite Recorder Batching Pattern
**Goal:** Stop writing to `device_history.db` on every single light switch toggle. Instead, hold the data in RAM and write it to the disk in bulk every 60 seconds.

### File: `logic/history_manager.py`
Update your `DeviceHistoryManager` class to use a write queue and a background flusher.

```python
import sqlite3
import time
import asyncio
from datetime import datetime
from typing import Any, List, Tuple
from loguru import logger

class DeviceHistoryManager:
    def __init__(self, state_manager: Any):
        self.sm = state_manager
        self.db_path = "device_history.db"
        self._init_db()
        self._task = None
        
        # ⚡ NEW: The RAM buffer for unwritten database rows
        self._write_queue: List[Tuple[int, int, str]] = []
        self._flush_task = None

    def start(self) -> None:
        self.recalculate_all_insights()
        self._task = asyncio.create_task(self._daily_cull_loop())
        # ⚡ NEW: Start the background flusher loop
        self._flush_task = asyncio.create_task(self._batch_flush_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._flush_task:
            self._flush_task.cancel()
        
        # ⚡ NEW: Force one final flush when the WanOS service shuts down
        if self._write_queue:
            self._execute_batch_insert()

    def log_event(self, idx: int, state: str) -> None:
        """Appends the event to RAM instead of hitting the disk immediately."""
        now = int(time.time())
        # Add to our RAM queue
        self._write_queue.append((idx, now, state))
        # Instantly update UI insights so the frontend doesn't lag
        self._update_insight(idx, now, state)

    def _execute_batch_insert(self) -> None:
        """The actual SQL blocking execution, processing hundreds of rows at once."""
        if not self._write_queue:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # ⚡ executemany is highly optimized in SQLite for bulk inserts
            c.executemany("INSERT INTO device_events (idx, timestamp, state) VALUES (?, ?, ?)", self._write_queue)
            conn.commit()
            conn.close()
            
            # Clear the RAM buffer after successful write
            self._write_queue.clear()
        except Exception as e:
            logger.error(f"Failed bulk insert to history DB: {e}")

    async def _batch_flush_loop(self) -> None:
        """Background loop that writes RAM to disk every 60 seconds."""
        while True:
            try:
                await asyncio.sleep(60.0)
                # Offload the blocking disk I/O to a background thread
                await asyncio.to_thread(self._execute_batch_insert)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Recorder flush loop: {e}")
```

---

## 🏷️ 2. The Logical Entity Registry (For the GUI)
**Goal:** Automations in the GUI should use friendly IDs like `light.buro_main` instead of physical integer IDXs like `71001`. This way, if you replace a broken Z-Wave switch and it gets a new IDX, your automations don't break.

### Step A: Update `core/models.py`
Add the registry dictionary to your `SystemState`.

```python
class SystemState(BaseModel):
    # ... existing fields ...
    
    # ⚡ NEW: Maps logical GUI strings to physical backend integers
    # Example: {"light.buro_main": 71001, "sensor.sauna_temp": 20001}
    entity_registry: dict[str, int] = Field(default_factory=dict)
```

### Step B: Update `logic/automation_rules.py`
Teach the `AutomationEngine` to translate logical strings back into physical integers right before execution.

```python
class AutomationEngine:
    # ... existing code ...

    @staticmethod
    def _resolve_target_idx(target: Any, state: SystemState) -> Optional[int]:
        """Translates a GUI string to a physical IDX. Returns integers as-is."""
        if isinstance(target, int):
            return target
        if isinstance(target, str) and not target.isdigit():
            # Look up the string in the registry (e.g., "light.buro_main" -> 71001)
            return state.system.entity_registry.get(target)
        try:
            return int(target)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> List[Event]:
        # Inside your action loop, resolve the target before doing anything:
        for action in rule.actions:
            # ⚡ NEW: Resolve the physical target
            physical_idx = AutomationEngine._resolve_target_idx(getattr(action, "target_entity", action.idx), state)
            
            if physical_idx is not None and getattr(action, "target", None) != "hue_scene":
                raw_target_state = state.devices.get(physical_idx)
                # ... proceed with the existing action logic using physical_idx ...
```

---

## 3. Strict Payload Validation (Pydantic)
**Goal:** Prevent bad data from crashing the logic engine by using Pydantic's strict typing for specific event payloads.

checkout wanos_payload_validation_spec.md