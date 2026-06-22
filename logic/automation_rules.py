# --- file: logic/automation_rules.py ---
import time
from typing import List, Optional

from core.models import Event, EventType, SystemState
from core.config import load_config
from core.logger import automation_logger  # explicitly isolated logger for logic rules


class AutomationEngine:
    """
    Centralized Rule Engine for WanOS automations.
    Dynamically evaluates YAML-defined rules using strictly numeric IDXs.

    Logging Hierarchy:
    - Tier A (Invisible): If an event does not match a trigger, the engine remains 100% silent.
    - Tier B (DEBUG): [X-RAY] Traces the internal decision making of the "Bouncer" (Condition checks).
    - Tier C (INFO): [ACTION] Audit trails explaining exactly what the engine is commanding and why.
    """

    # Cache the config so we don't parse the YAML file on every single event iteration
    _config = None

    @classmethod
    def _get_config(cls):
        if cls._config is None:
            cls._config = load_config()
        return cls._config

    @staticmethod
    def _is_dark(state: SystemState) -> bool:
        """
        Helper function to resolve the 'time_of_day is dark' condition.
        Relies on the mathematical absolute UNIX bounds calculated by the Environmental Time-Series engine.
        """
        sunrise = state.sensors.sunrise_unix
        sunset = state.sensors.sunset_unix

        if not sunrise or not sunset:
            return False  # Failsafe: Default to 'daylight' if weather data hasn't synced

        now = int(time.time())
        # Standard day phase: "dark" means before sunrise OR after sunset.
        return now < sunrise or now > sunset

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> List[Event]:
        payload = event.payload or {}
        config = AutomationEngine._get_config()

        # 🛡️ THE GENERIC BOOT GUARD 🛡️
        # Prevent "Boot Storms": Devices broadcasting their initial state when the system
        # powers on should NOT trigger automations, otherwise the house goes crazy on reboot.
        if payload.get("is_initialization", False):
            return []

        follow_up_events: List[Event] = []
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)

        event_idx = payload.get("idx")
        new_state = payload.get("state")
        is_transition = payload.get("transitioned", False)

        # =========================================================================
        # 1. DYNAMIC YAML AUTOMATIONS (The Custom Rule Parser)
        # =========================================================================
        # This block parses the `automations:` list in config.yaml.
        # - Triggers can be a single item or a List (List = OR logic. If any trigger matches, it fires).
        # - Actions are a List (List = AND logic. All actions execute sequentially).
        # - "SYNC" modifier: The action dynamically mirrors the exact state of the trigger (e.g., Switch ON -> Light ON).
        # - "FORCE_" modifier: Bypasses the StateManager's duplicate-filter, forcing the RF/MQTT command to broadcast
        #   even if the backend thinks the device is already in that state.
        # =========================================================================
        for rule in config.automations:
            trigger_matched = False
            trigger_reason = ""

            # ⚡ Normalize trigger to a list so we can loop through it (Enabling OR logic)
            triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]

            for t in triggers:
                # Trigger Type A: Raw Numeric IDX State Change
                if t.idx is not None and t.state:
                    if event_name == "HUB_STATE_CHANGED" and is_transition:
                        if t.idx == event_idx and (t.state == "SYNC" or t.state == new_state):
                            trigger_matched = True
                            trigger_reason = f"IDX {event_idx} -> {new_state}"
                            break

                # Trigger Type B: Semantic System Event (e.g., SAUNA_ON, BLINDS_OPEN_TRIGGER)
                elif t.event:
                    rule_event_str = t.event.value if hasattr(t.event, 'value') else str(t.event)
                    if event_name == rule_event_str:
                        trigger_matched = True
                        trigger_reason = f"Event [{event_name}]"
                        break

            # --- TIER B: The Thought Process (DEBUG ONLY) ---
            if trigger_matched:
                automation_logger.debug(
                    f"[X-RAY] Rule '{rule.name}' triggered by {trigger_reason}. Evaluating conditions...")

                conditions_met = True
                if rule.conditions:
                    for condition in rule.conditions:
                        # --- Condition Type 1: Sun / Time of Day ---
                        if condition.type == "time_of_day":
                            is_dark = AutomationEngine._is_dark(state)
                            if condition.condition_is == "dark" and not is_dark:
                                conditions_met = False
                                automation_logger.debug(
                                    f"[X-RAY] -> ABORTED. Condition failed: It is daylight, but rule requires dark.")
                            elif condition.condition_is == "light" and is_dark:
                                conditions_met = False
                                automation_logger.debug(
                                    f"[X-RAY] -> ABORTED. Condition failed: It is dark, but rule requires daylight.")

                        # --- Condition Type 2: Hardware Device State ---
                        elif condition.type == "device_state" and condition.idx is not None:
                            current_state = state.devices.get(condition.idx)
                            if current_state != condition.condition_is:
                                conditions_met = False
                                automation_logger.debug(
                                    f"[X-RAY] -> ABORTED. Condition failed: Target IDX {condition.idx} is '{current_state}', but rule requires '{condition.condition_is}'.")

                # If all conditions pass, we calculate and dispatch the final actions
                if conditions_met:
                    automation_logger.debug(f"[X-RAY] -> Conditions MET for '{rule.name}'. Parsing actions...")

                    for action in rule.actions:
                        # ⚡ Resolve modifiers
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

                        # --- Action Type A: Raw IDX Execution ---
                        if action.idx is not None:
                            current_target_state = state.devices.get(action.idx)

                            # ⚡ UNINITIALIZED STATE GUARD
                            if current_target_state is None:
                                automation_logger.debug(
                                    f"[X-RAY] -> Action SKIPPED for target IDX {action.idx}: Current state is unknown (NULL).")
                                continue

                            # ⚡ STRING NORMALIZATION COMPARISON
                            # Coerced to uppercase strings to ensure integers (e.g., 100) and YAML strings (e.g., "100")
                            # or mixed-case status descriptors evaluate flawlessly, preventing duplicate command streams.
                            if str(current_target_state).upper() != str(target_action_state).upper() or is_force:
                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload={"idx": action.idx, "state": target_action_state, "force": is_force}
                                ))

                                # --- TIER C: The Action Audit Trail (INFO) ---
                                semantic_name = state.dashboard_map.get(action.idx, "Unknown")
                                final_state_str = f"{target_action_state} (FORCED)" if is_force else target_action_state
                                automation_logger.info(
                                    f"[ACTION] '{rule.name}' -> Set target IDX {action.idx} ({semantic_name}) to {final_state_str}")
                            else:
                                automation_logger.debug(
                                    f"[X-RAY] -> Target IDX {action.idx} is already {target_action_state}. Ignoring.")

                        # --- Action Type B: Nested Event Chaining ---
                        elif getattr(action, "event", None):
                            try:
                                evt_type = EventType[action.event]
                                follow_up_events.append(Event(
                                    type=evt_type,
                                    payload={}
                                ))
                                # --- TIER C: The Action Audit Trail (INFO) ---
                                automation_logger.info(
                                    f"[ACTION] '{rule.name}' -> Dispatched Internal Event [{action.event}]")
                            except KeyError:
                                automation_logger.error(
                                    f"🔴 [AUTOMATION ERROR] Rule '{rule.name}' failed: '{action.event}' is not a valid EventType Enum.")

        # =========================================================================
        # 2. SYSTEM SWEEPER: Time & Environment Audit (Option B Enforcer)
        # =========================================================================
        # When WanOS boots up, reloads its config, or recovers from a network outage,
        # it triggers a Sweeper. The sweeper looks at the clock and the live sensor data,
        # then explicitly commands the hardware to snap back to the mathematically correct state.
        # This prevents the house from staying "stuck" if an event fired while the hub was offline.
        # (Note: Environmental Blinds/Twilight are swept inside state_manager.py, but
        # transient timers and climate locks are swept here).
        # =========================================================================
        if event_name == "SYSTEM_SWEEP_REQUESTED":
            recovered_timers: int = 0
            recovered_vents: int = 0

            # --- Audit A: Lighting Timers ---
            if hasattr(config, "lighting") and config.lighting.managed_lights:
                for light_idx in config.lighting.managed_lights:
                    current_state = state.devices.get(light_idx)
                    if current_state == "ON":
                        timer_id = f"light_auto_off_{light_idx}"
                        if timer_id not in state.system.active_timers:
                            delay_mins: int = config.lighting.auto_off_delays.get(light_idx,
                                                                                  config.lighting.default_auto_off_minutes)
                            deadline: int = int(time.time()) + delay_mins * 60

                            follow_up_events.append(Event(
                                type=EventType.TIMER_SCHEDULED,
                                payload={
                                    "timer_id": timer_id,
                                    "deadline": deadline,
                                    "event_type": EventType.LIGHT_TIMER_EXPIRED.value,
                                    "event_payload": {"idx": light_idx}
                                }
                            ))
                            semantic_name: str = state.dashboard_map.get(light_idx, "Unknown")
                            automation_logger.info(
                                f"[System Sweeper] Recovered missing auto-off timer for light IDX {light_idx} ({semantic_name}). Turning OFF in {delay_mins} min.")
                            recovered_timers += 1

            # --- Audit B: Bathroom Climate Ventilation ---
            if hasattr(config, "bathroom1"):
                on_threshold: int = config.bathroom1.vent_on_humidity
                off_threshold: int = config.bathroom1.vent_off_humidity
                current_hum: Optional[int] = state.sensors.bathroom1_hum

                if current_hum is not None:
                    current_vent_state = state.devices.get(7558, "OFF")
                    is_locked: bool = state.devices.get(90001, False)
                    semantic_name: str = state.dashboard_map.get(7558, "Unknown")

                    if current_hum >= on_threshold and current_vent_state != "ON":
                        follow_up_events.append(
                            Event(type=EventType.HUB_STATE_CHANGED, payload={"idx": 7558, "state": "ON"})
                        )
                        automation_logger.info(
                            f"[System Sweeper] Recovered environment: Humidity ({current_hum}%) >= Threshold ({on_threshold}%). Forced {semantic_name} ON.")
                        recovered_vents += 1
                    elif current_hum <= off_threshold and current_vent_state == "ON" and not is_locked:
                        follow_up_events.append(
                            Event(type=EventType.HUB_STATE_CHANGED, payload={"idx": 7558, "state": "OFF"})
                        )
                        automation_logger.info(
                            f"[System Sweeper] Recovered environment: Humidity ({current_hum}%) <= Threshold ({off_threshold}%). Forced {semantic_name} OFF.")
                        recovered_vents += 1

            # Feedback Alert for the Web UI
            total_recovered: int = recovered_timers + recovered_vents
            if total_recovered == 0:
                msg: str = "🟢 Sweeper complete: Lighting and HVAC are perfectly synced."
            else:
                parts: List[str] = []
                if recovered_timers > 0: parts.append(f"{recovered_timers} timers")
                if recovered_vents > 0: parts.append(f"{recovered_vents} HVAC states")
                msg: str = f"🟢 Sweeper complete: Recovered {' and '.join(parts)}."

            follow_up_events.append(Event(
                type=EventType.TEST_ALERT_INJECTED,
                payload={"msg_text": msg}
            ))

        # =========================================================================
        # 3. CLIMATE HYSTERESIS LOOPS (Bathroom 1eV Ventilator)
        # =========================================================================
        # Hysteresis prevents "Flapping". If you set a fan to turn on at 80%, it will turn on at 80%,
        # instantly drop the humidity to 79.9%, turn off, the humidity will rise back to 80%, turn on, etc.
        # This breaks relays.
        # Solution:
        # - Turn ON when threshold > 80% (vent_on_humidity)
        # - Turn OFF ONLY when threshold < 74% (vent_off_humidity)
        # - ⚡ INTERNAL LOCK (IDX 90001): When the fan turns on, it locks itself "ON" for a minimum of
        #   5 minutes, regardless of humidity drops. This guarantees a full air cycle.
        # =========================================================================
        if event_name == "HUMIDITY_UPDATED":
            idx = payload.get("idx")
            if idx == 20004:  # Virtual SHT11 Bathroom Probe
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
                            Event(type=EventType.HUB_STATE_CHANGED, payload={"idx": 7558, "state": "ON"})
                        )
                        automation_logger.info(
                            f"[Bathroom Climate] Humidity crossed upper threshold ({val}% >= {on_threshold}%). Auto-engaging extraction fan (IDX 7558).")

                    elif val <= off_threshold and current_vent_state == "ON":
                        # Humidity is low: Auto-disengage ventilator (ONLY IF 5-MIN LOCK EXPIRED)
                        if not is_locked:
                            follow_up_events.append(
                                Event(type=EventType.HUB_STATE_CHANGED, payload={"idx": 7558, "state": "OFF"})
                            )
                            automation_logger.info(
                                f"[Bathroom Climate] Humidity dropped below lower threshold ({val}% <= {off_threshold}%). Auto-disengaging extraction fan (IDX 7558).")
                        else:
                            automation_logger.debug(
                                f"[X-RAY] Bathroom humidity ({val}%) is low enough to turn off, but 5-minute safety lock is still engaged. Waiting.")

        # =========================================================================
        # 4. LIGHTING AUTO-OFF TIMERS
        # =========================================================================
        # Prevents lights in transitive rooms (hallways, toilets, pantries) from being left on indefinitely.
        # - Only affects IDXs explicitly listed in `managed_lights` in config.yaml.
        # - Looks up specific time limits (e.g. Toilet = 15m, Hallway = 10m) from `auto_off_delays`.
        # - Re-schedules the deadline dynamically if motion is re-triggered while already ON.
        # =========================================================================
        if event_name == "HUB_STATE_CHANGED":
            idx = payload.get("idx")
            semantic_name: str = state.dashboard_map.get(idx, "Unknown")

            # Only track IDXs that are explicitly registered in the lighting YAML config
            if idx is not None and hasattr(config, "lighting") and idx in config.lighting.managed_lights:
                timer_id: str = f"light_auto_off_{idx}"

                if new_state == "ON":
                    # Look up specific delay, fallback to the global default
                    delay_mins: int = config.lighting.auto_off_delays.get(idx, config.lighting.default_auto_off_minutes)
                    deadline: int = int(time.time()) + delay_mins * 60

                    follow_up_events.append(Event(
                        type=EventType.TIMER_SCHEDULED,
                        payload={
                            "timer_id": timer_id,
                            "deadline": deadline,
                            "event_type": EventType.LIGHT_TIMER_EXPIRED.value,
                            "event_payload": {"idx": idx}
                        }
                    ))
                    automation_logger.info(
                        f"[Lighting Auto-Off] Device IDX {idx} ({semantic_name}) turned ON. Scheduling OFF timer for {delay_mins} minutes (ID: {timer_id}).")

                elif new_state == "OFF":
                    # Instantly cancel any pending countdowns for this light,
                    # but only if it's actually ticking (prevents phantom cancellations when the timer itself turned the light off)
                    if timer_id in state.system.active_timers:
                        follow_up_events.append(Event(
                            type=EventType.TIMER_CANCELLED,
                            payload={"timer_id": timer_id}
                        ))
                        automation_logger.info(
                            f"[Lighting Auto-Off] Device IDX {idx} ({semantic_name}) turned OFF. Cancelled pending auto-off timer.")

        return follow_up_events