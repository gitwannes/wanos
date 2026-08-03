# --- file: logic/automation_rules.py ---
import time
import json
from typing import List, Optional, Any

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

    # Rolling array tracking absolute timestamps of hot water pulses for sensory debouncing
    _hot_water_pulses: List[float] = []

    @classmethod
    def _get_config(cls):
        if cls._config is None:
            cls._config = load_config()
        return cls._config

    @staticmethod
    def _timer_exists(active_timers: List[Any], target_timer_id: str) -> bool:
        """Robustly checks if a timer exists by safely parsing serialized JSON strings."""
        for t in active_timers:
            if isinstance(t, dict) and t.get("timer_id") == target_timer_id:
                return True
            if isinstance(t, str):
                try:
                    parsed = json.loads(t)
                    if isinstance(parsed, dict) and parsed.get("timer_id") == target_timer_id:
                        return True
                except json.JSONDecodeError:
                    if t == target_timer_id:
                        return True
        return False

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
        BATHROOM_VENT_IDX: int = 71034

        payload = event.payload or {}
        config = AutomationEngine._get_config()

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

        # 🛡️ THE GENERIC BOOT GUARD 🛡️
        # Prevent "Boot Storms": We skip custom YAML rules if this is a boot initialization.
        # We do NOT return early so System Timers and Hysteresis loops can safely arm on boot!
        active_rules = [] if payload.get("is_initialization", False) else config.automations

        for rule in active_rules:
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
                    # ⚡ Support Native Door Telemetry: Map the semantic is_open boolean to standard ON/OFF string states
                    # Note: Hardware door events are inherently edge-triggered transitions, so is_transition is bypassed.
                    elif event_name == "DOOR_CHANGED":
                        is_open = payload.get("is_open")
                        mapped_state = "ON" if is_open else "OFF"
                        if t.idx == event_idx and (t.state == "SYNC" or t.state == mapped_state):
                            trigger_matched = True
                            trigger_reason = f"Door Sensor {event_idx} -> {mapped_state}"
                            # Temporarily inject the mapped state into the local loop context
                            # so downstream Action resolving doesn't fail if it relies on 'new_state'
                            new_state = mapped_state
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
                            # ⚡ Extract state safely whether it's a flat string or a rich Hue dictionary
                            raw_state = state.devices.get(condition.idx)
                            current_state = raw_state.get("state") if isinstance(raw_state, dict) else raw_state

                            if str(current_state).upper() != str(condition.condition_is).upper():
                                conditions_met = False
                                automation_logger.debug(
                                    f"[X-RAY] -> ABORTED. Condition failed: Target IDX {condition.idx} is '{current_state}', but rule requires '{condition.condition_is}'.")

                # If all conditions pass, we calculate and dispatch the final actions
                if conditions_met:
                    automation_logger.debug(f"[X-RAY] -> Conditions MET for '{rule.name}'. Parsing actions...")

                    # Scene history: log once when a scene:true rule actually fires
                    # (manual UI event, automation IDX trigger, or nested event)
                    if getattr(rule, "scene", False) is True:
                        try:
                            from logic.history_ids import scene_history_idx
                            scene_evt = None
                            for st in triggers:
                                if getattr(st, "event", None):
                                    scene_evt = st.event.value if hasattr(st.event, "value") else str(st.event)
                                    break
                            hist_key = scene_evt or rule.name
                            hm = getattr(AutomationEngine, "_history_manager", None)
                            if hm is not None:
                                hm.log_event(scene_history_idx(hist_key), "ON", level=100.0)
                        except Exception:
                            pass

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

                            # ⚡ STRICT STATE FILTER: Prevent 'None' states from propagating to physical hardware.
                            # Drops ghost payloads (e.g., Hue brightness slides without binary power states)
                            # before they hit the execution blocks.
                            # We safely bypass this filter for Native Events and Hue Scenes which inherently do not require binary states.
                        is_pure_event: bool = getattr(action, "event", None) is not None
                        is_hue_scene: bool = getattr(action, "target", None) == "hue_scene"

                        if target_action_state is None and not is_pure_event and not is_hue_scene:
                            automation_logger.debug(
                                f"[X-RAY] -> Action SKIPPED: Target state resolved to None (Ghost Payload)."
                            )
                            continue

                        # --- Action Type A: Raw IDX Execution ---
                        if getattr(action, "idx", None) is not None and getattr(action, "target", None) != "hue_scene":
                            # ⚡ Extract state safely whether it's a flat string or a rich Hue dictionary
                            raw_target_state = state.devices.get(action.idx)
                            current_target_state = raw_target_state.get("state") if isinstance(raw_target_state,
                                                                                               dict) else raw_target_state

                            # ⚡ UNINITIALIZED STATE GUARD
                            if current_target_state is None:
                                automation_logger.debug(
                                    f"[X-RAY] -> Action SKIPPED for target IDX {action.idx}: Current state is unknown (NULL).")
                                continue

                            # ⚡ RICH PAYLOAD EXTRACTION (Hue Presets & Direct Overrides)
                            bri = getattr(action, "bri", None)
                            xy = getattr(action, "xy", None)
                            preset_name = getattr(action, "preset", None)

                            # Load preset if specified
                            if preset_name and hasattr(config, "hue") and hasattr(config.hue, "presets"):
                                presets_col = config.hue.presets
                                # Safely extract from Pydantic dictionary or object
                                preset = presets_col.get(preset_name) if isinstance(presets_col, dict) else getattr(
                                    presets_col, preset_name, None)

                                if preset:
                                    # Support both dict and Pydantic model access for the payload claims
                                    bri = getattr(preset, "bri", bri) if hasattr(preset, "bri") else preset.get(
                                        "bri", bri)
                                    xy = getattr(preset, "xy", xy) if hasattr(preset, "xy") else preset.get("xy",
                                                                                                            xy)

                            # Extract Sonos rich parameters if provided in the YAML rule
                            volume = getattr(action, "volume", None)
                            station = getattr(action, "station", None)

                            # If rich attributes are provided, we must force the command because the power state
                            # might already be "ON", but we still need to apply the changes.
                            is_rich_action = bri is not None or xy is not None or volume is not None or station is not None
                            if is_rich_action:
                                is_force = True

                            # ⚡ RFXCOM FORCE GUARD ⚡
                            # 433MHz is a stateless protocol. We automatically apply the FORCE flag
                            # behind the scenes to guarantee the radio transmits the signal every time the rule executes.
                            meta_origin: str = state.device_metadata.get(action.idx, {}).get("origin", "")
                            if meta_origin == "rfxcom":
                                is_force = True

                            # STRING NORMALIZATION COMPARISON
                            # Coerced to uppercase strings to ensure integers (e.g., 100) and YAML strings (e.g., "100")
                            # or mixed-case status descriptors evaluate flawlessly, preventing duplicate command streams.
                            if str(current_target_state).upper() != str(
                            target_action_state).upper() or is_force:
                            # Use a distinct variable name to prevent shadowing the original event payload!
                            # Explicitly tags the origin as "AUTOMATION" for the IWHW Ledger
                                action_payload = {"idx": action.idx, "state": target_action_state,
                                                  "force": is_force, "origin": "AUTOMATION"}
                                if bri is not None:
                                    action_payload["bri"] = bri
                                if xy is not None:
                                    action_payload["xy"] = xy
                                if volume is not None:
                                    action_payload["volume"] = volume
                                if station is not None:
                                    action_payload["station"] = station

                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload=action_payload
                                ))

                                # --- TIER C: The Action Audit Trail (INFO) ---
                                semantic_name = state.dashboard_map.get(action.idx, "Unknown")
                                final_state_str = f"{target_action_state} (FORCED)" if is_force else target_action_state
                                preset_str = f" [Rich Payload]" if is_rich_action else ""
                                automation_logger.info(
                                    f"[ACTION] '{rule.name}' -> Set target IDX {action.idx} ({semantic_name}) to {final_state_str}{preset_str}")
                            else:
                                automation_logger.debug(
                                    f"[X-RAY] -> Target IDX {action.idx} is already {target_action_state}. Ignoring.")

                        # --- Action Type B: Native Hue Scene Trigger ---
                        elif getattr(action, "target", None) == "hue_scene":
                            scene_name = getattr(action, "scene", None)
                            idx = getattr(action, "idx", None)

                            # ⚡ 2-PART PAYLOAD: Requires both the string name AND the room IDX
                            if scene_name and idx is not None:
                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload={"target": "hue_scene", "scene": scene_name, "idx": idx,
                                             "origin": "AUTOMATION"}
                                ))
                                automation_logger.info(
                                    f"[ACTION] '{rule.name}' -> Dispatched Native Hue Scene [{scene_name}] on IDX {idx}")
                            else:
                                automation_logger.error(
                                    f"🔴 [AUTOMATION ERROR] Rule '{rule.name}' failed: Missing 'scene' or 'idx' for hue_scene target.")

                        # --- Action Type C: Nested Event Chaining ---
                        elif getattr(action, "event", None):
                            # ⚡ Dynamically accept known Enums or fallback to raw strings
                            try:
                                evt_type = EventType[action.event]
                            except KeyError:
                                evt_type = action.event
                                automation_logger.error(
                                    f"🔴 [AUTOMATION ERROR] Rule '{rule.name}' failed: '{action.event}' is not a valid EventType Enum.")

                            # ⚡ DYNAMIC PAYLOAD INJECTION
                            # Automatically map all provided YAML keys (idx, volume, station, etc.) into the event payload
                            action_payload = {}
                            if hasattr(action, "model_dump"):
                                action_payload = action.model_dump(exclude_none=True)
                                action_payload.pop("event",
                                                   None)  # Strip the event type itself out of the payload body

                            follow_up_events.append(Event(
                                type=evt_type,
                                payload=action_payload
                            ))

                            payload_str = f" with payload: {action_payload}" if action_payload else ""
                            automation_logger.info(
                                f"[ACTION] '{rule.name}' -> Dispatched Internal Event [{action.event}]{payload_str}")

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

                    # ⚡ RICH PAYLOAD SUPPORT: Safely extract state from dictionary objects
                    extracted_state = current_state.get("state") if isinstance(current_state, dict) else current_state

                    if extracted_state == "ON":
                        timer_id = f"light_auto_off_{light_idx}"

                        # Secure parsing to detect JSON structured active_timers
                        timer_exists = AutomationEngine._timer_exists(state.system.active_timers, timer_id)

                        if not timer_exists:
                            delay_mins: int = config.lighting.auto_off_delays.get(light_idx,
                                                                                  config.lighting.default_auto_off_minutes)
                            deadline: int = int(time.time()) + delay_mins * 60
                            semantic_name: str = state.dashboard_map.get(light_idx, "Unknown")

                            # ⚡ Structured Payload for UI Timeline Processing
                            follow_up_events.append(Event(
                                type=EventType.TIMER_SCHEDULED,
                                payload={
                                    "timer_id": timer_id,
                                    "deadline": deadline,
                                    "event_type": EventType.LIGHT_TIMER_EXPIRED.value,
                                    "event_payload": {
                                        "idx": light_idx,
                                        "name": semantic_name,
                                        "type": "switch",
                                        "target_state": "OFF",
                                        "origin": "TIMER"
                                    }
                                }
                            ))
                            automation_logger.info(
                                f"[System Sweeper] Recovered missing auto-off timer for light IDX {light_idx} ({semantic_name}). Turning OFF in {delay_mins} min.")
                            recovered_timers += 1

            # --- Audit B: Bathroom Climate Ventilation ---
            if hasattr(config, "bathroom1"):
                on_threshold: int = config.bathroom1.vent_on_humidity
                off_threshold: int = config.bathroom1.vent_off_humidity

                d_bath = state.devices.get(20004)
                current_hum: Optional[int] = d_bath.get("hum") if isinstance(d_bath, dict) else None

                if current_hum is not None:
                    current_vent_state = state.devices.get(BATHROOM_VENT_IDX, "OFF")
                    is_locked: bool = state.devices.get(90001, False)
                    semantic_name: str = state.dashboard_map.get(BATHROOM_VENT_IDX, "Unknown")

                    if current_hum >= on_threshold and current_vent_state != "ON":
                        follow_up_events.append(
                            Event(type=EventType.HUB_STATE_CHANGED,
                                  payload={"idx": BATHROOM_VENT_IDX, "state": "ON", "origin": "SYSTEM"})
                        )
                        automation_logger.info(
                            f"[System Sweeper] Recovered environment: Humidity ({current_hum}%) >= Threshold ({on_threshold}%). Forced {semantic_name} ON.")
                        recovered_vents += 1
                    elif current_hum <= off_threshold and current_vent_state == "ON" and not is_locked:
                        follow_up_events.append(
                            Event(type=EventType.HUB_STATE_CHANGED,
                                  payload={"idx": BATHROOM_VENT_IDX, "state": "OFF", "origin": "SYSTEM"})
                        )
                        automation_logger.info(
                            f"[System Sweeper] Recovered environment: Humidity ({current_hum}%) <= Threshold ({off_threshold}%). Forced {semantic_name} OFF.")
                        recovered_vents += 1

            # Feedback Alert for the Web UI
            total_recovered: int = recovered_timers + recovered_vents
            if total_recovered == 0:
                msg: str = "🟢 Sweeper complete: all synced."
            else:
                parts: List[str] = []
                if recovered_timers > 0: parts.append(f"{recovered_timers} timers")
                if recovered_vents > 0: parts.append(f"{recovered_vents} HVAC states")
                msg: str = f"🟢 Sweeper complete: Recovered {' and '.join(parts)}."

            follow_up_events.append(Event(
                type=EventType.ALERT_INJECTED,
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

                    current_vent_state = state.devices.get(BATHROOM_VENT_IDX, "OFF")
                    is_locked = state.devices.get(90001, False)

                    if val >= on_threshold and current_vent_state != "ON":
                        # Humidity is high: Auto-engage ventilator
                        follow_up_events.append(
                            Event(type=EventType.HUB_STATE_CHANGED,
                                  payload={"idx": BATHROOM_VENT_IDX, "state": "ON", "origin": "AUTOMATION"})
                        )
                        automation_logger.info(
                            f"[Bathroom Climate] Humidity crossed upper threshold ({val}% >= {on_threshold}%). Auto-engaging extraction fan.")

                    elif val <= off_threshold and current_vent_state == "ON":
                        # Humidity is low: Auto-disengage ventilator (ONLY IF 5-MIN LOCK EXPIRED)
                        if not is_locked:
                            follow_up_events.append(
                                Event(type=EventType.HUB_STATE_CHANGED,
                                      payload={"idx": BATHROOM_VENT_IDX, "state": "OFF", "origin": "AUTOMATION"})
                            )
                            automation_logger.info(
                                f"[Bathroom Climate] Humidity dropped below lower threshold ({val}% <= {off_threshold}%). Auto-disengaging extraction fan.")
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

                # ⚡ Extract state safely whether it's a flat string or a rich Hue dictionary
                raw_state = state.devices.get(idx)
                current_state = raw_state.get("state") if isinstance(raw_state, dict) else raw_state

                # Normalize string to uppercase to catch mixed-case "On"/"Off" states
                safe_state = str(current_state).upper() if current_state else ""

                if safe_state == "ON":
                    # Look up specific delay, fallback to the global default
                    delay_mins: int = config.lighting.auto_off_delays.get(idx, config.lighting.default_auto_off_minutes)
                    deadline: int = int(time.time()) + delay_mins * 60

                    follow_up_events.append(Event(
                        type=EventType.TIMER_SCHEDULED,
                        payload={
                            "timer_id": timer_id,
                            "deadline": deadline,
                            "event_type": EventType.LIGHT_TIMER_EXPIRED.value,
                            "event_payload": {
                                "idx": idx,
                                "name": semantic_name,
                                "type": "switch",
                                "target_state": "OFF",
                                "origin": "TIMER"
                            }
                        }
                    ))
                    automation_logger.info(
                        f"[Lighting Auto-Off] Device IDX {idx} ({semantic_name}) turned ON. Scheduling OFF timer for {delay_mins} minutes (ID: {timer_id}).")

                elif safe_state == "OFF":
                    # Instantly cancel any pending countdowns for this light,
                    # but only if it's actually ticking (prevents phantom cancellations when the timer itself turned the light off)
                    timer_exists = AutomationEngine._timer_exists(state.system.active_timers, timer_id)

                    if timer_exists:
                        follow_up_events.append(Event(
                            type=EventType.TIMER_CANCELLED,
                            payload={"timer_id": timer_id}
                        ))
                        automation_logger.info(
                            f"[Lighting Auto-Off] Device IDX {idx} ({semantic_name}) turned OFF. Cancelled pending auto-off timer.")

            # =========================================================================
            # 5. SHOWER VENTILATION WATCHDOG (Hot Water Overrun)
            # =========================================================================
            # Automatically activates the bathroom ventilator when a shower
            # is detected, filtering out transient spikes (hand washing) and extending
            # the runtime as a rolling debounced watchdog.
            # =========================================================================
            if event_name == "WATER_PULSE":
                idx = payload.get("idx")
                if idx == 11003:  # Hot Water Meter IDX
                    now_ts = time.time()
                    # Record current pulse timestamp
                    AutomationEngine._hot_water_pulses.append(now_ts)
                    # Evict pulse entries older than 10 seconds (Sliding Window filter)
                    AutomationEngine._hot_water_pulses = [
                        t for t in AutomationEngine._hot_water_pulses if now_ts - t <= 10.0
                    ]

                    # Enforce Hand-Washing Filter: Requires a minimum velocity of 5 pulses within 10 seconds
                    if len(AutomationEngine._hot_water_pulses) >= 5:
                        current_vent_state = state.devices.get(BATHROOM_VENT_IDX, "OFF")
                        semantic_name = state.dashboard_map.get(BATHROOM_VENT_IDX, "Unknown")

                        # Phase A: Force-engage the fan if it is currently offline
                        if current_vent_state != "ON":
                            follow_up_events.append(Event(
                                type=EventType.HUB_STATE_CHANGED,
                                payload = {"idx": BATHROOM_VENT_IDX, "state": "ON", "origin": "AUTOMATION"}
                            ))
                            automation_logger.info(
                                f"[Shower Automation] Hot water sustained flow verified ({len(AutomationEngine._hot_water_pulses)} pulses/10s). Auto-engaging {semantic_name}."
                            )

                        # Phase B: Manual Override Hijack & Rolling Overrun Extension
                        # Dynamically pushes the 5-minute safety lock deadline forward into the future.
                        # This establishes the rolling高度 debounce loop until the flow completely halts.
                        deadline = int(now_ts) + 300  # 5 minutes from the current pulse tick
                        follow_up_events.append(Event(
                            type=EventType.TIMER_SCHEDULED,
                            payload={
                                "timer_id": "bath1_vent_lock",
                                "deadline": deadline,
                                "event_type": "BATH1_VENT_LOCK_EXPIRED",
                                "event_payload": {
                                    "idx": BATHROOM_VENT_IDX,
                                    "name": semantic_name,
                                    "type": "switch",
                                    "target_state": "Climate Safe"
                                }
                            }
                        ))
                        # Downgrade rolling watchdog logs to DEBUG to protect the terminal from high-frequency pulse text noise
                        automation_logger.debug(
                            f"[X-RAY] Shower active. Extended ventilator tracking lock 'bath1_vent_lock' deadline to absolute UNIX: {deadline}."
                        )

        return follow_up_events