import asyncio
import aiohttp
from core.models import Event, EventType
from core.state_manager import StateManager


async def weather_polling_loop(state_manager: StateManager) -> None:
    """Polls OpenWeatherMap for outside temp, humidity, and sun cycle times."""
    config = state_manager._config.weather

    if not config.api_key:
        await state_manager.logger.warning("No OWM_API_KEY found in .env. Skipping weather integration.")
        return

    url = f"https://api.openweathermap.org/data/2.5/weather?q={config.location}&appid={config.api_key}&units=metric"
    poll_seconds = config.poll_interval_mins * 60

    await state_manager.logger.success(f"[OWM] polling initialized for {config.location}.")

    # ⚡ EARLY GATE DUPLICATE FILTER ⚡
    last_temp = None
    last_hum = None

    last_enabled_state = False
    seconds_since_last_fetch = poll_seconds  # Max out counter to force immediate fetch on start

    async with aiohttp.ClientSession() as session:
        while True:
            # Fast 2-second background evaluation loop instead of blocking for 30 minutes!
            await asyncio.sleep(2.0)

            is_enabled = state_manager._state.system.owm_integration_enabled

            # Catch OFF -> ON transition
            if is_enabled and not last_enabled_state:
                await state_manager.logger.success("[OWM] Integration ENABLED via UI.")
                await state_manager.logger.info("[OWM] Fetching weather...")
                seconds_since_last_fetch = poll_seconds  # Force instant fetch execution

            # Catch ON -> OFF transition
            elif not is_enabled and last_enabled_state:
                await state_manager.logger.info("[OWM] Integration DISABLED via UI.")

            last_enabled_state = is_enabled

            if not is_enabled:
                continue

            seconds_since_last_fetch += 2.0

            if seconds_since_last_fetch >= poll_seconds:
                seconds_since_last_fetch = 0.0
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()

                            # Extract 1: Temperature & Humidity
                            temp = round(float(data['main']['temp']) * 2) / 2
                            hum = int(data['main']['humidity'])

                            # Extract 2: Sunrise & Sunset
                            sunrise = int(data['sys']['sunrise'])
                            sunset = int(data['sys']['sunset'])

                            # Check if the weather actually changed
                            if temp == last_temp and hum == last_hum:
                                await state_manager.logger.debug(
                                    f"[OWM] Weather update ignored (duplicate: already {temp}°C, {hum}%)")
                            else:
                                last_temp = temp
                                last_hum = hum

                                # Dispatch Temperature
                                state_manager.dispatch(Event(
                                    type=EventType.TEMP_UPDATED,
                                    payload={"sensor_id": "outside", "value": temp}
                                ))

                                # Dispatch Humidity
                                state_manager.dispatch(Event(
                                    type=EventType.HUMIDITY_UPDATED,
                                    payload={"sensor_id": "outside", "value": hum}
                                ))

                                # Dispatch Sun Cycle
                                state_manager.dispatch(Event(
                                    type=EventType.EXTERNAL_WEATHER_UPDATED,
                                    payload={"sunrise": sunrise, "sunset": sunset}
                                ))

                                await state_manager.logger.debug(f"[OWM] Weather updated: {temp}°C, {hum}%")
                        else:
                            await state_manager.logger.error(f"[OWM] HTTP Error {response.status}")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    await state_manager.logger.error(f"[OWM] Connection failed: {e}")