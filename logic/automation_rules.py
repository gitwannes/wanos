# --- file: logic/automation_rules.py ---
import datetime, time
from core.models import Event, EventType, SystemState
from core.config import load_config
from loguru import logger  # ⚡ Added logger for troubleshooting

class AutomationEngine:
    """
    Centralized Rule Engine for WanOS automations.
    Dynamically evaluates YAML-defined rules using strictly numeric IDXs.
    """

    # Cache the config so we don't parse the YAML file on every single event iteration
    _config = None

    @classmethod
    def _get_config(cls):
        if cls._config is None:
            cls._config = load_config()
        return cls._config

    @staticmethod
    def _log_execution(rule_name: str, target: str, new_state: str) -> None:
        """
        Temporary flat-file logger for executed automations.
        Will be replaced by MySQL integration in the future.
        """
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            message = f"[AUTOMATION] '{rule_name}' -> Set {target} to {new_state}"
            log_line = f"{timestamp} | INFO     | {message}\n"
            with open("/var/log/wisc/wanos_automations.log", "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass

    @staticmethod
    def _is_dark(state: SystemState) -> bool:
        """
        Helper function to resolve the 'is_dark' condition.
        """
        sunrise = state.sensors.sunrise_unix
        sunset = state.sensors.sunset_unix

        if not sunrise or not sunset:
            return False  # Failsafe: Default to 'daylight' if weather data hasn't synced

        now = int(time.time())
        return now < sunrise or now > sunset

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> list[Event]:
        payload = event.payload or {}
        config = AutomationEngine._get_config()

        # 🛡️ THE GENERIC BOOT GUARD 🛡️
        if payload.get("is_initialization", False):
            return []

        follow_up_events = []
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)

        event_idx = payload.get("idx")
        new_state = payload.get("state")
        is_transition = payload.get("transitioned", False)

        # 1. DYNAMIC YAML AUTOMATIONS
        for rule in config.automations:
            trigger_matched = False

            # ⚡ Normalize trigger to a list so we can loop through it
            triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]

            for t in triggers:
                # Trigger Type A: Raw Numeric IDX
                if t.idx is not None and t.state:
                    if event_name == "HUB_STATE_CHANGED" and is_transition:
                        if t.idx == event_idx and (t.state == "SYNC" or t.state == new_state):
                            trigger_matched = True
                            break

                # Trigger Type B: System Event (e.g., SAUNA_ON, SCENE_VERDIEP1_OFF)
                elif t.event:
                    rule_event_str = t.event.value if hasattr(t.event, 'value') else str(t.event)
                    if event_name == rule_event_str:
                        trigger_matched = True
                        break

            # If the trigger matched, evaluate conditions and execute
            if trigger_matched:
                logger.debug(f"[X-RAY] -> TRIGGER MATCHED for rule: '{rule.name}'")
                conditions_met = True
                if rule.conditions:
                    for condition in rule.conditions:
                        if condition.type == "time_of_day":
                            is_dark = AutomationEngine._is_dark(state)
                            if condition.condition_is == "dark" and not is_dark:
                                conditions_met = False
                                logger.debug(f"[X-RAY] -> Condition FAILED (It is not dark)")
                            elif condition.condition_is == "light" and is_dark:
                                conditions_met = False
                                logger.debug(f"[X-RAY] -> Condition FAILED (It is not light)")

                if conditions_met:
                    logger.debug(f"[X-RAY] -> CONDITIONS MET for '{rule.name}'. Evaluating actions...")
                    for action in rule.actions:
                        logger.debug(f"[X-RAY]    -> Pydantic parsed this action: {action}")

                        # ⚡ Resolve target action state
                        raw_action_state = action.state
                        is_force = False
                        if isinstance(raw_action_state, str) and raw_action_state.startswith("FORCE_"):
                            is_force = True
                            raw_action_state = raw_action_state.replace("FORCE_", "")

                        if action.state == "SYNC":
                            target_action_state = new_state
                        elif action.state == "SYNCOPPOSITE":
                            target_action_state = "OFF" if new_state == "ON" else "ON"
                        else:
                            target_action_state = raw_action_state

                        # --- Raw IDX Execution ---
                        if action.idx is not None:
                            current_target_state = state.devices.get(action.idx)

                            # ⚡ UNINITIALIZED STATE GUARD
                            if current_target_state is None:
                                logger.debug(f"[X-RAY]    -> Action SKIPPED for IDX {action.idx}: Current state is None")
                                continue

                            logger.debug(
                                f"[X-RAY]    -> Checking IDX {action.idx}: Current state is {current_target_state}, Target is {target_action_state} (Force: {is_force})")

                            if current_target_state != target_action_state or is_force:
                                logger.debug (f"[X-RAY]    -> IDX {action.idx} switching to {target_action_state}")
                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload = {"idx": action.idx, "state": target_action_state, "force": is_force}
                                ))
                                AutomationEngine._log_execution(rule.name, f"IDX {action.idx}",
                                                                f"{target_action_state} (FORCED)" if is_force else target_action_state)
                            else:
                                logger.debug (f"[X-RAY]    -> IDX {action.idx} already {target_action_state}")

                        # --- Nested Event Chaining ---
                        elif getattr(action, "event", None):
                            logger.debug(f"[X-RAY]    -> Yielding internal event chain: {action.event}")
                            try:
                                evt_type = EventType[action.event]
                                follow_up_events.append(Event(
                                    type=evt_type,
                                    payload={}
                                ))
                                AutomationEngine._log_execution(rule.name, "Internal Event", action.event)
                            except KeyError:
                                logger.error(
                                    f"[AUTOMATION] Rule '{rule.name}' failed: '{action.event}' is not a valid EventType.")

        # -----------------------------------------------------------------
        # HYSTERESIS LOOPS: Bathroom 1eV Ventilator Auto-ON/OFF
        # -----------------------------------------------------------------
        # The SHT temp/hum sensor was assigned virtual IDX 20004
        # The extractor fan relay uses Domoticz IDX 7558
        # The ventilator lock timer uses virtual internal IDX 90001
        if event_name == "HUMIDITY_UPDATED":
            idx = payload.get("idx")
            if idx == 20004:
                config = AutomationEngine._get_config()
                val = payload.get("value", 0)

                if hasattr(config, "bathroom1"):
                    on_threshold = config.bathroom1.vent_on_humidity
                    off_threshold = config.bathroom1.vent_off_humidity

                    current_vent_state = state.devices.get(7558, "OFF")
                    is_locked = state.devices.get(90001, False)

                    if val >= on_threshold and current_vent_state != "ON":
                        # Humidity is high: Auto-engage ventilator
                        follow_up_events.append(
                            Event(type=EventType.HUB_STATE_CHANGED,
                                  payload={"idx": 7558, "state": "ON"})
                        )
                        AutomationEngine._log_execution("Bathroom 1eV Vent Auto-ON", "IDX 7558", "ON")
                    elif val <= off_threshold and current_vent_state == "ON":
                        # Humidity is low: Auto-disengage ventilator (IF 5-MIN LOCK EXPIRED)
                        if not is_locked:
                            follow_up_events.append(
                                Event(type=EventType.HUB_STATE_CHANGED,
                                      payload={"idx": 7558, "state": "OFF"})
                            )
                            AutomationEngine._log_execution("Bathroom 1eV Vent Auto-OFF", "IDX 7558", "OFF")

        return follow_up_events