# --- file: logic/automation_rules.py ---
import datetime, time
from core.models import Event, EventType, SystemState
from core.config import load_config

# Load configuration into memory once when the module boots
_engine_config = load_config()


class AutomationEngine:
    """
    Centralized Rule Engine for WanOS automations.
    Dynamically evaluates YAML-defined rules instead of using hardcoded cascading logic.
    """
    @staticmethod
    def _log_execution(rule_name: str, target: str, new_state: str) -> None:
        """
        Temporary flat-file logger for executed automations.
        Will be replaced by MySQL integration in the future.
        Matches the exact Loguru formatting from main.py.
        """
        try:
            # Generate millisecond-precise timestamp: YYYY-MM-DD HH:mm:ss.SSS
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Construct the message payload
            message = f"[AUTOMATION] '{rule_name}' -> Set {target} to {new_state}"

            # Combine into the exact WanOS Loguru format (INFO is padded to 8 chars)
            log_line = f"{timestamp} | INFO     | {message}\n"

            with open("/var/log/wisc/wanos_automations.log", "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            # Silently catch permission errors so the automation loop never crashes
            pass

    @staticmethod
    def _is_dark(state: SystemState) -> bool:
        """
        Helper function to resolve the 'is_dark' condition.
        Uses OpenWeatherMap sunrise/sunset UNIX timestamps from the central state.
        """
        sunrise = state.sensors.sunrise_unix
        sunset = state.sensors.sunset_unix

        if not sunrise or not sunset:
            return False  # Failsafe: Default to 'daylight' if weather data hasn't synced

        now = int(time.time())
        # It is dark if the current time is BEFORE today's sunrise, or AFTER today's sunset.
        return now < sunrise or now > sunset

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> list[Event]:
        payload = event.payload or {}

        # 🛡️ THE GENERIC BOOT GUARD 🛡️
        if payload.get("is_initialization", False):
            return []

        follow_up_events = []
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)

        device_id = payload.get("device_id")
        event_idx = payload.get("idx")
        new_state = payload.get("state")
        is_transition = payload.get("transitioned", False)

        # 1. DYNAMIC YAML AUTOMATIONS
        for rule in _engine_config.automations:
            trigger_matched = False

            # Trigger Type A: Hardware State Transition
            if rule.trigger.device and rule.trigger.state:
                if event_name == "HUB_STATE_CHANGED" and is_transition:
                    if rule.trigger.device == device_id and rule.trigger.state == new_state:
                        trigger_matched = True

            # Trigger Type B: Raw Domoticz IDX
            elif rule.trigger.idx and rule.trigger.state:
                if event_name == "HUB_STATE_CHANGED" and is_transition:
                    if rule.trigger.idx == event_idx and rule.trigger.state == new_state:
                        trigger_matched = True

            # Trigger Type C: System Event (e.g., SAUNA_ON, SCENE_VERDIEP_OFF)
            elif rule.trigger.event:
                if event_name == rule.trigger.event:
                    trigger_matched = True

            # If the trigger matched, evaluate conditions and execute!
            if trigger_matched:
                conditions_met = True
                if rule.conditions:
                    for condition in rule.conditions:
                        if condition.type == "time_of_day":
                            is_dark = AutomationEngine._is_dark(state)
                            if condition.condition_is == "dark" and not is_dark:
                                conditions_met = False
                            elif condition.condition_is == "light" and is_dark:
                                conditions_met = False

                if conditions_met:
                    for action in rule.actions:

                        # --- Semantic Device ---
                        if action.device:
                            current_target_state = state.devices.get(action.device)
                            if current_target_state != action.state:
                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload={"device_id": action.device, "state": action.state}
                                ))
                                # Write to logfile
                                AutomationEngine._log_execution(rule.name, action.device, action.state)

                        # --- Raw IDX ---
                        elif action.idx:
                            # Map to our virtual string ID so StateManager handles it gracefully
                            virtual_id = f"idx_{action.idx}"
                            current_target_state = state.devices.get(virtual_id)

                            if current_target_state != action.state:
                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload={"device_id": virtual_id, "idx": action.idx, "state": action.state}
                                ))
                                # Write to logfile
                                AutomationEngine._log_execution(rule.name, f"IDX {action.idx}", action.state)

        return follow_up_events