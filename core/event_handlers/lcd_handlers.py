# --- file: core/event_handlers/lcd_handlers.py ---
import time
from typing import Any, Set, Tuple

from core.models import Event


def _visible_cell_len(s: str) -> int:
    """Counts LCD cells: '§X' counts as 1."""
    if not s:
        return 0
    n = 0
    i = 0
    while i < len(s):
        if s[i] == "§" and i + 1 < len(s) and s[i + 1].isdigit():
            n += 1
            i += 2
        else:
            n += 1
            i += 1
    return n


def _center_cells(s: str, width: int = 16) -> str:
    s = s or ""
    cells = _visible_cell_len(s)
    if cells >= width:
        return s[:width]
    pad_total = width - cells
    left = pad_total // 2
    right = pad_total - left
    return (" " * left) + s + (" " * right)


async def handle_lcd_easteregg_show(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """
    Admin-triggered LCD Screen 2 easter egg.

    The LCD Pi renders raw '§' escape sequences as custom glyphs.
    """
    payload = event.payload or {}
    variant = str(payload.get("variant") or "geertrui").strip().lower()

    # If mqtt publisher isn't ready (during boot), no-op safely.
    mqtt_pub = getattr(manager, "mqtt_publisher", None)
    if mqtt_pub is None:
        return False, set()

    # Geertrui variant (WISC: two-line status list, no timestamp)
    if variant in ("geertrui", "default", "normal"):
        line1_raw = " §0§0 Geertrui §0§0"
        line2_raw = "Wannes loves you"
        line1 = _center_cells(line1_raw, 16)
        line2 = _center_cells(line2_raw, 16)
        await mqtt_pub.publish_lcd_screen2(line1, line2)
        return False, set()

    # Secret variant: retain WISC intent.
    # WISC: "*{'* 038417 *':^14}*"
    inner = "* 038417 *"
    inner_centered = inner.center(14)
    line1 = _center_cells(f"*{inner_centered}*", 16)
    line2 = " " * 16
    await mqtt_pub.publish_lcd_screen2(line1, line2)
    return False, set()


async def handle_lcd_debug_test(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """
    Admin Debug: push the same test text to both LCD screens.

    Line 1 = local date/time (exactly 16 cells). Line 2 must also fit 16 —
    "operator debug test" is 19 chars, so use "operator debug--".
    """
    mqtt_pub = getattr(manager, "mqtt_publisher", None)
    if mqtt_pub is None:
        return False, set()

    # Exactly 16 chars: YYYY-MM-DD HH:MM
    line1 = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    line2 = "operator debug--"
    await mqtt_pub.publish_lcd_screen1(line1, line2, force=True)
    await mqtt_pub.publish_lcd_screen2(line1, line2, force=True)
    return False, set()
