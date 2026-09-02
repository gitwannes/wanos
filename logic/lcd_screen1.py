# --- file: logic/lcd_screen1.py ---
"""
Compose 16x2 WISC-compatible text for sauna LCD screen1.

Shared by MQTT publisher (physical LCD) and SaunaState (WISC UI mirror).
Sends raw '§' escape sequences; the LCD agent / UI pretty-printer map them to glyphs.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from core.models import SystemState

FIFTEEN_MIN_SECS: int = 15 * 60


def format_remaining_mmss(end_unix: Optional[int], *, now: int) -> str:
    """mm:ss remaining until end_unix; --:-- if unknown/expired."""
    if end_unix is None:
        return "--:--"
    remaining = max(0, int(end_unix) - int(now))
    minutes, seconds = divmod(remaining, 60)
    return f"{minutes:02d}:{seconds:02d}"


def format_duration_ddhhmmss(
    total_secs: Optional[int],
    *,
    now: int,
    open_since: Optional[int],
) -> str:
    """
    Duration as dd:hh:mm:ss with WISC-style omission of leading zero fields.
    Prefer open_since+now when provided.
    """
    if open_since is None:
        return "--:--:--"
    duration = max(0, int(now) - int(open_since))
    days, rem = divmod(duration, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days > 0:
        return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def visible_cell_len(s: str) -> int:
    """Counts LCD cells: '§X' counts as 1 cell."""
    if not s:
        return 0
    n = 0
    i = 0
    while i < len(s):
        if s[i] == "§" and i + 1 < len(s) and s[i + 1].isdigit():
            n += 1
            i += 2
            continue
        n += 1
        i += 1
    return n


def fit_to_16_cells(s: str) -> str:
    """Truncate/pad so the LCD renders exactly 16 cells."""
    s = s or ""
    out: list[str] = []
    cells = 0
    i = 0
    while i < len(s) and cells < 16:
        if s[i] == "§" and i + 1 < len(s) and s[i + 1].isdigit():
            out.append(s[i:i + 2])
            cells += 1
            i += 2
            continue
        out.append(s[i])
        cells += 1
        i += 1
    rendered = "".join(out)
    if cells < 16:
        rendered += " " * (16 - cells)
    return rendered


def center_cells(s: str) -> str:
    s = s or ""
    cells = visible_cell_len(s)
    if cells >= 16:
        return fit_to_16_cells(s)
    pad_total = 16 - cells
    left = pad_total // 2
    right = pad_total - left
    return (" " * left) + s + (" " * right)


def right_align_timer(prefix: str, mmss: str) -> str:
    """Right-align mm:ss timer within 16 cells (C32 sauna line1)."""
    prefix = prefix or ""
    timer = mmss or "--:--"
    gap = 16 - len(prefix) - len(timer)
    if gap < 1:
        gap = 1
    return fit_to_16_cells(prefix + (" " * gap) + timer)


def compose_sauna_line1(mod: int, remaining_secs: int, mmss: str) -> str:
    """C32 sauna line1: lowercase sauna; timer when remaining <= 15 min."""
    mod = int(mod or 0)
    if remaining_secs > FIFTEEN_MIN_SECS:
        if mod == 0:
            return fit_to_16_cells("sauna HOLD")
        if mod >= 100:
            return fit_to_16_cells("sauna ON")
        return fit_to_16_cells(f"sauna ON  {mod}%")

    if mod == 0:
        return right_align_timer("sauna HOLD", mmss)
    if mod >= 100:
        return right_align_timer("sauna ON", mmss)
    return right_align_timer(f"sauna {mod}%", mmss)


def compose_ir_line1(mod: int, mmss: str) -> str:
    """C32/C34 IR line1: IR {mm:ss}; append ' - {mod}%' only when mod < 100; timer right-aligned @ 100%."""
    mod = int(mod or 0)
    if 0 < mod < 100:
        return fit_to_16_cells(f"IR {mmss} - {mod}%")
    return right_align_timer("IR", mmss)


def resolve_sauna_hue_on(snapshot: "SystemState", sauna_hue_entity_idx: Optional[int]) -> bool:
    """True when the configured sauna Hue light is physically ON."""
    if sauna_hue_entity_idx is None:
        return False
    dev = snapshot.devices.get(sauna_hue_entity_idx)
    return (dev == "ON") or (isinstance(dev, dict) and dev.get("state") == "ON")


def compose_lcd_screen1(
    snapshot: "SystemState",
    *,
    sauna_hue_entity_idx: Optional[int] = None,
    now: Optional[int] = None,
) -> Tuple[str, str]:
    """
    WISC-compatible 16x2 composer for sauna LCD screen1.

    Blank ("", "") when sauna and IR are off and sauna Hue is off.
    Must stay in lockstep with the physical MQTT screen1 payload.
    """
    now_i = int(time.time() if now is None else now)
    sauna_active = bool(snapshot.sauna.active)
    ir_active = bool(snapshot.ir.active)

    sauna_door_open = snapshot.door_sauna_open_since_unix is not None
    sauna_hue_on = resolve_sauna_hue_on(snapshot, sauna_hue_entity_idx)

    if not sauna_active and not ir_active and not sauna_hue_on:
        return ("", "")

    if sauna_active:
        end = snapshot.sauna.session_end_time
        remaining = max(0, int(end) - now_i) if end is not None else 0
        mmss = format_remaining_mmss(end, now=now_i)
        mod = int(snapshot.sauna.modulation_pwm or 0)
        line1 = compose_sauna_line1(mod, remaining, mmss)

        if sauna_door_open:
            door_dur = format_duration_ddhhmmss(
                None, now=now_i, open_since=snapshot.door_sauna_open_since_unix
            )
            prefix = "plz close sdoor"
            time_str = door_dur
            time_len = len(time_str)
            prefix_max = max(0, 16 - time_len)
            line2 = (prefix[:prefix_max] + time_str)[:16]
            line2 = line2.ljust(16)
        else:
            temp = snapshot.sensors.sauna_calc_temp
            hum = snapshot.sensors.sauna_calc_hum
            if temp is None or hum is None:
                line2 = fit_to_16_cells("--.-§1 --%")
            else:
                line2_raw = f"{int(temp)}§1 {int(hum)}%"
                line2 = center_cells(line2_raw)
        return (line1, line2)

    if ir_active:
        mmss = format_remaining_mmss(snapshot.ir.session_end_time, now=now_i)
        mod = int(snapshot.ir.modulation_pwm or 0)
        line1 = compose_ir_line1(mod, mmss)

        temp = snapshot.sensors.sauna_calc_temp
        hum = snapshot.sensors.sauna_calc_hum
        if temp is None or hum is None:
            line2 = fit_to_16_cells("--.-§1 --%")
        else:
            line2_raw = f"{int(temp)}§1 {int(hum)}%"
            line2 = center_cells(line2_raw)
        return (line1, line2)

    dt = time.localtime(now_i)
    date_str = time.strftime("%a %d %b %Y", dt)
    line1 = fit_to_16_cells(date_str)

    out_t = snapshot.sensors.outside_temp
    out_h = snapshot.sensors.outside_hum
    if out_t is None or out_h is None:
        line2 = fit_to_16_cells("--.-§1 --%")
    else:
        line2_raw = f"{int(out_t)}§1 {int(out_h)}%"
        line2 = center_cells(line2_raw)
    return (line1, line2)
