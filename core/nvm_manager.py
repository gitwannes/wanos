# --- file: core/nvm_manager.py ---
import os
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger  # ⚡ Import native synchronous logger directly


class NVRAMManager:
    """
    Handles Non-Volatile Memory (NVM) persistence for cumulative counters.
    Uses Atomic Swaps to prevent file corruption during sudden power loss.
    """

    def __init__(self):
        # Resolve to the application root directory (two levels up from core/nvm_manager.py)
        self.base_dir = Path(__file__).resolve().parent.parent
        self.file_path = self.base_dir / "wanos-nvram.json"
        self.temp_path = self.base_dir / "wanos-nvram.json.tmp"
        self._last_flushed_state: str = ""

    def load(self) -> Dict[int, Any]:
        """Loads the persisted JSON file on boot."""
        if not self.file_path.exists():
            logger.info("No NVRAM file found. Initializing with blank counters.")
            return {}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Convert string keys back to integers for the StateManager
            parsed_data = {int(k): v for k, v in raw_data.items() if str(k).isdigit()}
            logger.success(f"NVRAM successfully loaded {len(parsed_data)} counters from disk.")

            # Cache the loaded state to prevent immediate redundant flushes
            self._last_flushed_state = json.dumps(raw_data, sort_keys=True)
            return parsed_data
        except Exception as e:
            logger.error(f"🔴 CRITICAL: Failed to load NVRAM file: {e}")
            return {}

    def flush(self, data: Dict[int, Any]) -> None:
        """
        Serializes the counter dictionary to disk.
        Bypasses flush if the data hasn't mathematically changed.
        """
        try:
            # Convert integer IDXs to strings for JSON compliance
            safe_data = {str(k): v for k, v in data.items()}
            serialized = json.dumps(safe_data, sort_keys=True, indent=4)

            # Only perform disk I/O if the numbers actually changed!
            if serialized == self._last_flushed_state:
                return

            # ⚡ ATOMIC SWAP: Write to a temporary file first
            with open(self.temp_path, "w", encoding="utf-8") as f:
                f.write(serialized)

            # ⚡ ATOMIC SWAP: Instantly replace the old file with the new one
            os.replace(self.temp_path, self.file_path)

            self._last_flushed_state = serialized
            logger.debug(f"[NVRAM] Flushed {len(data)} counters to physical disk.")

        except Exception as e:
            logger.error(f"🔴 CRITICAL: Failed to flush NVRAM to disk: {e}")