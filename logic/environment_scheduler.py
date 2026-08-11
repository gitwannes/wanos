# --- file: logic/environment_scheduler.py ---
import time
import json
from datetime import datetime
from typing import Optional

from core.models import SystemState, Event, EventType
from core.config import AppConfig


class EnvironmentScheduler:
    """
    🌍 The Daily Time-Series Engine (Schedule Calculator)
    Responsible for dynamically calculating exact UNIX timestamps for today's environmental phases.
    """

    @staticmethod
    def recalculate_schedule(state: SystemState, config: AppConfig, start_time: float, dispatch_fn) -> None:
        """
        Runs after OWM sun-cycle refresh (daily / boot / enable), applying Min/Max clamps
        so blinds do not open at e.g. 4:30 AM in mid-summer. Deploys timeline events to the queue.
        """
        sns = state.sensors
        cfg = config.environmental_schedule
        if not sns.sunrise_unix or not sns.sunset_unix or not cfg:
            return

        def _get_unix_for_today(time_str: str) -> int:
            try:
                h, m = map(int, time_str.split(':'))
                now = datetime.now()
                target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                return int(target.timestamp())
            except (ValueError, AttributeError):
                return 0

        # --- Phase 1: BLINDS CLAMPING MATH ---
        mo_early = _get_unix_for_today(cfg.blinds.morning_open_earliest)
        mo_late = _get_unix_for_today(cfg.blinds.morning_open_latest)
        ec_early = _get_unix_for_today(cfg.blinds.evening_close_earliest)
        ec_late = _get_unix_for_today(cfg.blinds.evening_close_latest)

        # Open = Max(Sunrise, 07:30). If 09:00 limit exists, clamp Open = Min(Open, 09:00).
        blinds_open = max(sns.sunrise_unix, mo_early)
        if mo_late > 0: blinds_open = min(blinds_open, mo_late)

        # Close = Max(Sunset, 16:30). If 22:00 limit exists, clamp Close = Min(Close, 22:00).
        blinds_close = max(sns.sunset_unix, ec_early)
        if ec_late > 0: blinds_close = min(blinds_close, ec_late)

        # --- Phase 2: TWILIGHT LOGIC ---
        twi_eve_on = sns.sunset_unix
        twi_eve_off = _get_unix_for_today(cfg.twilight.evening_off_time)
        twi_morn_on = _get_unix_for_today(cfg.twilight.morning_on_time)
        twi_morn_off = sns.sunrise_unix

        # Store blinds clamps (always scheduled when sun is known).
        sns.env_schedule_blinds_open_unix = blinds_open
        sns.env_schedule_blinds_close_unix = blinds_close

        # Morning lights: skip whole window if sunrise ≤ morning-on clock.
        if twi_morn_off > twi_morn_on:
            sns.env_schedule_twilight_morning_on_unix = twi_morn_on
            sns.env_schedule_twilight_morning_off_unix = twi_morn_off
        else:
            sns.env_schedule_twilight_morning_on_unix = None
            sns.env_schedule_twilight_morning_off_unix = None

        # Evening lights (B10F): mirror morning — skip whole window if sunset ≥ evening-off.
        if twi_eve_on < twi_eve_off:
            sns.env_schedule_twilight_evening_on_unix = twi_eve_on
            sns.env_schedule_twilight_evening_off_unix = twi_eve_off
        else:
            sns.env_schedule_twilight_evening_on_unix = None
            sns.env_schedule_twilight_evening_off_unix = None

        # --- Phase 3: SCHEDULER DEPLOYMENT ---
        now_unix = int(time.time())
        uptime = now_unix - start_time

        def _is_redundant(timer_id: str, deadline: int) -> bool:
            """
            Checks if a timer with the exact ID and deadline is already in the active UI registry.
            This prevents the OWM 30-minute polling loop from flooding the event queue with identical timers.
            """
            for t_item in state.system.active_timers:
                # Timer objects can exist as dicts or serialized JSON strings in the active_timers list
                if isinstance(t_item, dict):
                    t_dict = t_item
                elif isinstance(t_item, str):
                    try:
                        t_dict = json.loads(t_item)
                    except json.JSONDecodeError:
                        continue
                else:
                    continue

                if t_dict.get("timer_id") == timer_id and t_dict.get("deadline") == deadline:
                    return True
            return False

        # Anti-NTP Jump Guard: Safely absorb Pi fake-hwclock skews during boot.
        # Only schedule time-series timers if they are safely in the future (> 5s),
        # or if the system has fully stabilized past its 3-minute boot window.
        # Enforces deduplication to prevent 30-minute OWM polling loops from flooding the event queue.
        def _should_schedule(timer_id: str, target_unix: Optional[int]) -> bool:
            if not target_unix:
                return False

            is_valid_future = target_unix > now_unix and (target_unix - now_unix > 5 or uptime > 180)
            if not is_valid_future:
                return False

            return not _is_redundant(timer_id, target_unix)

        # Dispatched dynamically to the bus so the Glass-Box Timeline UI registers them instantly.
        if _should_schedule("env_blinds_open", blinds_open):
            dispatch_fn(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_blinds_open", "deadline": blinds_open, "event_type": "BLINDS_OPEN_TRIGGER",
                "event_payload": {}
            }))
        if _should_schedule("env_blinds_close", blinds_close):
            dispatch_fn(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_blinds_close", "deadline": blinds_close, "event_type": "BLINDS_CLOSE_TRIGGER",
                "event_payload": {}
            }))
        if _should_schedule("env_twi_eve_on", sns.env_schedule_twilight_evening_on_unix):
            dispatch_fn(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_eve_on",
                "deadline": sns.env_schedule_twilight_evening_on_unix,
                "event_type": "SUNSET_TRIGGER",
                "event_payload": {}
            }))
        if _should_schedule("env_twi_eve_off", sns.env_schedule_twilight_evening_off_unix):
            dispatch_fn(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_eve_off",
                "deadline": sns.env_schedule_twilight_evening_off_unix,
                "event_type": "EVENING_OFF_TRIGGER",
                "event_payload": {}
            }))
        if _should_schedule("env_twi_morn_on", sns.env_schedule_twilight_morning_on_unix):
            dispatch_fn(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_morn_on", "deadline": sns.env_schedule_twilight_morning_on_unix,
                "event_type": "MORNING_ON_TRIGGER",
                "event_payload": {}
            }))
        if _should_schedule("env_twi_morn_off", sns.env_schedule_twilight_morning_off_unix):
            dispatch_fn(Event(type=EventType.TIMER_SCHEDULED, payload={
                "timer_id": "env_twi_morn_off", "deadline": sns.env_schedule_twilight_morning_off_unix,
                "event_type": "SUNRISE_TRIGGER",
                "event_payload": {}
            }))