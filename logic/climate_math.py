# --- file: logic/climate_math.py ---
"""Climate helpers shared by OWM / history (Sonntag dew point + dew-likelihood heuristic)."""
from __future__ import annotations

import math
from typing import Optional


def dew_point_c(temp_c: float, rh_pct: float) -> Optional[float]:
    """
    Sonntag Magnus dew point (°C). Matches FE `_dewPointC` (b=17.62, c=243.12).
    Returns None when RH is missing/invalid.
    """
    try:
        t = float(temp_c)
        rh = float(rh_pct)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(t) or not math.isfinite(rh) or rh <= 0.0 or rh > 100.0:
        return None
    b = 17.62
    c = 243.12
    gamma = math.log(rh / 100.0) + (b * t) / (c + t)
    if not math.isfinite(gamma) or abs(b - gamma) < 1e-12:
        return None
    tdp = (c * gamma) / (b - gamma)
    if not math.isfinite(tdp):
        return None
    return round(tdp * 10.0) / 10.0


def clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def is_raining_from_owm(weather_list: object, rain_obj: object) -> bool:
    """
    C25 rain gate: weather id 200–599, or rain.1h / rain.3h > 0.
    Snow (6xx) does not force raining.
    """
    if isinstance(weather_list, list):
        for item in weather_list:
            if not isinstance(item, dict):
                continue
            try:
                wid = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if 200 <= wid <= 599:
                return True
    if isinstance(rain_obj, dict):
        for key in ("1h", "3h"):
            try:
                mm = float(rain_obj.get(key))
            except (TypeError, ValueError):
                continue
            if math.isfinite(mm) and mm > 0.0:
                return True
    return False


def is_night_local(now_unix: int, sunrise_unix: Optional[int], sunset_unix: Optional[int]) -> bool:
    """True after sunset and before sunrise (same calendar night using stored OWM sun times)."""
    if sunrise_unix is None or sunset_unix is None:
        return False
    try:
        now_i = int(now_unix)
        rise = int(sunrise_unix)
        set_ = int(sunset_unix)
    except (TypeError, ValueError):
        return False
    # Typical same-day: night is now >= sunset OR now < sunrise.
    return now_i >= set_ or now_i < rise


def dew_likelihood_pct(
    *,
    temp_c: float,
    rh_pct: float,
    clouds: float,
    wind_ms: float,
    raining: bool,
    is_night: bool,
) -> int:
    """
    C25 heuristic dew likelihood 0–100 (not a meteorological probability).
    See docs/env-schedule-and-system-events.md §9.
    """
    if raining or not is_night:
        return 0
    td = dew_point_c(temp_c, rh_pct)
    if td is None:
        return 0
    try:
        t = float(temp_c)
        clouds_f = float(clouds)
        wind_f = float(wind_ms)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(t) or not math.isfinite(clouds_f) or not math.isfinite(wind_f):
        return 0
    d_t = max(0.0, t - td)
    sat = clamp(1.0 - d_t / 4.0, 0.0, 1.0)
    clear = clamp(1.0 - clouds_f / 100.0, 0.0, 1.0)
    calm = clamp(1.0 - wind_f / 5.0, 0.0, 1.0)
    score = round(100.0 * (0.50 * sat + 0.30 * clear + 0.20 * calm))
    if score < 0:
        return 0
    if score > 100:
        return 100
    return int(score)


def weather_summary_from_owm(weather_list: object) -> str:
    """Short OWM weather description for Admin (first entry main + description)."""
    if not isinstance(weather_list, list) or not weather_list:
        return ""
    first = weather_list[0]
    if not isinstance(first, dict):
        return ""
    main = str(first.get("main") or "").strip()
    desc = str(first.get("description") or "").strip()
    if main and desc:
        return f"{main}: {desc}"
    return main or desc
