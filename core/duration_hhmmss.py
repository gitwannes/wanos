# --- file: core/duration_hhmmss.py ---
"""B14 part 1 — shared HH:MM:SS duration parse/validate (Set for/after, H1, H3)."""
from __future__ import annotations

from typing import Optional, Tuple

# Locked: min 1 minute, max 4 hours inclusive.
DURATION_MIN_SECONDS: int = 60
DURATION_MAX_SECONDS: int = 4 * 3600


def parse_hhmmss(value: Optional[str]) -> int:
    """
    Parse ``HH:MM:SS`` into seconds.

    Raises:
        ValueError: missing, malformed, or outside ``00:01:00``…``04:00:00``.
    """
    if value is None:
        raise ValueError("Duration is required (HH:MM:SS).")
    s = str(value).strip()
    if not s:
        raise ValueError("Duration is required (HH:MM:SS).")
    parts = s.split(":")
    if len(parts) != 3:
        raise ValueError(f"Duration must be HH:MM:SS (got {s!r}).")
    try:
        hh_s, mm_s, ss_s = parts[0], parts[1], parts[2]
        if not (hh_s.isdigit() and mm_s.isdigit() and ss_s.isdigit()):
            raise ValueError("non-digit")
        # Reject odd widths that are not zero-padded but still numeric (allow 0:1:0? lock says HH:MM:SS)
        if len(mm_s) != 2 or len(ss_s) != 2:
            raise ValueError("MM and SS must be two digits.")
        if len(hh_s) < 1 or len(hh_s) > 2:
            raise ValueError("HH must be one or two digits.")
        hh = int(hh_s)
        mm = int(mm_s)
        ss = int(ss_s)
    except ValueError as exc:
        if "Duration must" in str(exc) or "must be" in str(exc):
            raise
        raise ValueError(f"Duration must be HH:MM:SS (got {s!r}).") from exc
    if hh < 0 or hh > 4:
        raise ValueError(f"Duration hours must be 0..4 (got {s!r}).")
    if mm < 0 or mm > 59 or ss < 0 or ss > 59:
        raise ValueError(f"Duration minutes/seconds out of range (got {s!r}).")
    total = hh * 3600 + mm * 60 + ss
    if total < DURATION_MIN_SECONDS:
        raise ValueError(
            f"Duration min is 00:01:00 (got {s!r})."
        )
    if total > DURATION_MAX_SECONDS:
        raise ValueError(
            f"Duration max is 04:00:00 (got {s!r})."
        )
    if hh == 4 and (mm != 0 or ss != 0):
        raise ValueError(
            f"Duration max is 04:00:00 (got {s!r})."
        )
    return total


def format_hhmmss(total_seconds: int) -> str:
    """Format seconds as zero-padded HH:MM:SS (no range check)."""
    if total_seconds < 0:
        total_seconds = 0
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def try_parse_hhmmss(value: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """Return (seconds, None) or (None, error_message)."""
    try:
        return parse_hhmmss(value), None
    except ValueError as exc:
        return None, str(exc)
