from __future__ import annotations

import asyncio
import time
from datetime import date, datetime

import aiohttp

from core.models import Event, EventType
from core.state_manager import StateManager


async def weather_polling_loop(state_manager: StateManager) -> None:
    """OWM loop: climate on poll_interval; sun cycle once daily (+ boot/enable)."""
    config = state_manager._config.weather

    if not config.api_key:
        await state_manager.logger.warning("No OWM_API_KEY found in .env. Skipping weather integration.")
        return

    url = f"https://api.openweathermap.org/data/2.5/weather?q={config.location}&appid={config.api_key}&units=metric"
    poll_seconds = config.poll_interval_mins * 60
    sun_hour = int(getattr(config, "sun_refresh_hour", 3) or 3)
    climate_idx = int(getattr(config, "idx", None) or 30001)

    await state_manager.logger.success(
        f"[OWM] polling initialized for {config.location} "
        f"(climate every {config.poll_interval_mins}m; sun daily ≥{sun_hour:02d}:00)."
    )

    last_temp = None
    last_hum = None
    last_enabled_state = False
    last_sun_refresh_date: date | None = None
    seconds_since_last_climate = float(poll_seconds)  # force climate on first enabled tick
    force_sun = True  # boot / enable always refresh sun once
    sun_backoff_until = 0.0

    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(2.0)

            is_enabled = state_manager._state.system.owm_integration_enabled

            if is_enabled and not last_enabled_state:
                await state_manager.logger.success("[OWM] Integration ENABLED via UI.")
                await state_manager.logger.info("[OWM] Fetching climate + sun cycle...")
                seconds_since_last_climate = float(poll_seconds)
                force_sun = True
                sun_backoff_until = 0.0
            elif not is_enabled and last_enabled_state:
                await state_manager.logger.info("[OWM] Integration DISABLED via UI.")

            last_enabled_state = is_enabled
            if not is_enabled:
                continue

            seconds_since_last_climate += 2.0
            now_local = datetime.now()
            today = now_local.date()
            now_mono = time.monotonic()

            need_climate = seconds_since_last_climate >= poll_seconds
            need_sun = force_sun or (
                last_sun_refresh_date != today and now_local.hour >= sun_hour
            )
            if need_sun and now_mono < sun_backoff_until:
                need_sun = False

            if not need_climate and not need_sun:
                continue

            # Consume climate budget up front (same as legacy: wait a full interval after any attempt).
            if need_climate:
                seconds_since_last_climate = 0.0

            try:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        await state_manager.logger.error(f"[OWM] HTTP Error {response.status}")
                        if need_sun:
                            sun_backoff_until = time.monotonic() + poll_seconds
                        continue

                    data = await response.json()

                    if need_climate:
                        temp = round(float(data["main"]["temp"]) * 2) / 2
                        hum = int(data["main"]["humidity"])

                        if temp == last_temp and hum == last_hum:
                            await state_manager.logger.debug(
                                f"[OWM] Climate ignored (duplicate: already {temp}°C, {hum}%)"
                            )
                        else:
                            last_temp = temp
                            last_hum = hum
                            state_manager.dispatch(Event(
                                type=EventType.TEMP_UPDATED,
                                payload={"idx": climate_idx, "value": temp}
                            ))
                            state_manager.dispatch(Event(
                                type=EventType.HUMIDITY_UPDATED,
                                payload={"idx": climate_idx, "value": hum}
                            ))
                            await state_manager.logger.debug(
                                f"[OWM] Climate updated: {temp}°C, {hum}%"
                            )

                    if need_sun:
                        sunrise = int(data["sys"]["sunrise"])
                        sunset = int(data["sys"]["sunset"])
                        state_manager.dispatch(Event(
                            type=EventType.SUNRISE_SUNSET_UPDATE,
                            payload={"sunrise": sunrise, "sunset": sunset}
                        ))
                        last_sun_refresh_date = today
                        force_sun = False
                        sun_backoff_until = 0.0
                        sunrise_hm = datetime.fromtimestamp(sunrise).strftime("%H:%M")
                        sunset_hm = datetime.fromtimestamp(sunset).strftime("%H:%M")
                        await state_manager.logger.info(
                            f"[OWM] Sun cycle refreshed for {today.isoformat()} "
                            f"(sunrise={sunrise_hm}, sunset={sunset_hm})"
                        )

            except asyncio.CancelledError:
                break

            except Exception as e:
                await state_manager.logger.error(f"Error fetching OpenWeatherMap data: {e}")
                if need_sun:
                    sun_backoff_until = time.monotonic() + poll_seconds

                if state_manager._state.system.owm_integration_enabled:
                    owm_err = "🌩️ OpenWeatherMap HTTP Connection lost! Integration disabled."
                    state_manager.dispatch(Event(
                        type=EventType.OWM_TOGGLED,
                        payload={"enabled": False, "error_msg": owm_err}
                    ))
                    await state_manager.logger.error(owm_err)
