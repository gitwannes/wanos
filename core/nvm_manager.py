# --- file: core/nvm_manager.py ---
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from loguru import logger  # Import native synchronous logger directly

# Non-IDX keys stored alongside 11xxx pulse counters in the same atomic JSON file.
NVRAM_META_LEAK_WATTS = "p_leak_baseline_watts"


class NVRAMManager:
    """
    Handles Non-Volatile Memory (NVM) persistence for cumulative counters
    and small analytics baselines (e.g. leak W).
    Uses Atomic Swaps to prevent file corruption during sudden power loss.
    """

    def __init__(self):
        # Resolve to the application root directory (two levels up from core/nvm_manager.py)
        self.base_dir = Path(__file__).resolve().parent.parent
        self.file_path = self.base_dir / "wanos-nvram.json"
        self.temp_path = self.base_dir / "wanos-nvram.json.tmp"
        self._last_flushed_state: str = ""
        self._meta: Dict[str, Any] = {}

    def load(self) -> Dict[int, Any]:
        """Loads counters (digit keys) and caches non-digit meta keys for restore."""
        self._meta = {}
        if not self.file_path.exists():
            logger.info("No NVRAM file found. Initializing with blank counters.")
            return {}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                logger.error("CRITICAL: NVRAM file root is not an object.")
                return {}

            parsed_data: Dict[int, Any] = {}
            meta: Dict[str, Any] = {}
            for k, v in raw_data.items():
                sk = str(k)
                if sk.isdigit():
                    parsed_data[int(sk)] = v
                else:
                    meta[sk] = v

            self._meta = meta
            logger.success(
                f"NVRAM successfully loaded {len(parsed_data)} counters"
                f" and {len(meta)} meta keys from disk."
            )

            # Cache the loaded state to prevent immediate redundant flushes
            self._last_flushed_state = json.dumps(raw_data, sort_keys=True)
            return parsed_data
        except Exception as e:
            logger.error(f"CRITICAL: Failed to load NVRAM file: {e}")
            return {}

    def get_meta(self) -> Dict[str, Any]:
        """Return non-IDX NVRAM fields from the last load (or last successful flush)."""
        return dict(self._meta)

    def flush(self, data: Dict[int, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        """
        Serializes counters (+ optional meta) to disk.
        Bypasses flush if the data hasn't mathematically changed.
        Meta defaults to the last known meta so callers that only pass counters
        do not wipe leak / other non-IDX keys.
        """
        try:
            safe_data: Dict[str, Any] = {str(k): v for k, v in data.items()}
            merged_meta = dict(self._meta if meta is None else meta)
            for mk, mv in merged_meta.items():
                # Never let a non-digit meta key collide with an IDX string key.
                if str(mk).isdigit():
                    continue
                safe_data[str(mk)] = mv

            serialized = json.dumps(safe_data, sort_keys=True, indent=4)

            # Only perform disk I/O if the numbers actually changed!
            if serialized == self._last_flushed_state:
                return

            # ATOMIC SWAP: Write to a temporary file first
            with open(self.temp_path, "w", encoding="utf-8") as f:
                f.write(serialized)

            # ATOMIC SWAP: Instantly replace the old file with the new one
            os.replace(self.temp_path, self.file_path)

            self._last_flushed_state = serialized
            self._meta = merged_meta
            logger.debug(
                f"[NVRAM] Flushed {len(data)} counters"
                f" + {len(merged_meta)} meta keys to physical disk."
            )

        except Exception as e:
            logger.error(f"CRITICAL: Failed to flush NVRAM to disk: {e}")

    def build_flush_parts(
        self,
        devices: Dict[Any, Any],
        leak_watts: Optional[float] = None,
    ) -> Tuple[Dict[int, Any], Dict[str, Any]]:
        """Build counter + meta payloads for a flush from live state."""
        counters = {
            k: v for k, v in devices.items()
            if isinstance(k, int) and 11000 <= k < 12000
        }
        meta = dict(self._meta)
        if leak_watts is not None and isinstance(leak_watts, (int, float)):
            meta[NVRAM_META_LEAK_WATTS] = round(float(leak_watts), 3)
        return counters, meta
