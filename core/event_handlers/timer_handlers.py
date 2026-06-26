# --- file: core/event_handlers/timer_handlers.py ---
import json
from typing import Any, Set, Tuple, Optional
from core.models import Event, EventType
from core.logger import automation_logger


async def handle_timer_scheduled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    timer_id: Optional[str] = payload.get("timer_id")
    deadline: Optional[int] = payload.get("deadline")
    tgt_event_type: Optional[str] = payload.get("event_type")
    tgt_payload: dict[str, Any] = payload.get("event_payload", {})

    if timer_id and deadline and tgt_event_type:
        manager._timer_manager.schedule(timer_id, deadline, tgt_event_type, tgt_payload)
        active = manager._state.system.active_timers

        # Clear old instances safely before injecting new ones
        manager._state.system.active_timers = manager._remove_timer_robustly(active, timer_id)

        # SUBSCRIBER FAN-OUT LOGIC
        matched_rules = False
        if hasattr(manager._config, "automations"):
            for rule in manager._config.automations:
                rule_triggered = False
                triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]

                for t in triggers:
                    if getattr(t, "event", None):
                        rule_evt = t.event.value if hasattr(t.event, 'value') else str(t.event)
                        if rule_evt == tgt_event_type:
                            rule_triggered = True
                            break

                if rule_triggered:
                    matched_rules = True
                    name_suffix = " (conditional)" if getattr(rule, "conditions", None) else ""
                    timeline_obj = {
                        "timer_id": timer_id,
                        "deadline": deadline,
                        "event_type": tgt_event_type,
                        "idx": None,
                        "name": f"{rule.name}{name_suffix}",
                        "type": "scene",
                        "target_state": "Execute"
                    }
                    manager._state.system.active_timers.append(json.dumps(timeline_obj))

        # FALLBACK LOGIC
        if not matched_rules:
            target_idx = tgt_payload.get("idx")
            timeline_obj = {
                "timer_id": timer_id,
                "deadline": deadline,
                "event_type": tgt_event_type,
                "idx": target_idx,
                "name": tgt_payload.get("name", manager._state.dashboard_map.get(target_idx, "System Macro")),
                "type": tgt_payload.get("type", "scene" if target_idx is None else "switch"),
                "target_state": tgt_payload.get("target_state", "Execute")
            }
            manager._state.system.active_timers.append(json.dumps(timeline_obj))

        state_changed = True
        changed_domains.add("system")

    return state_changed, changed_domains


async def handle_timer_cancelled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    timer_id: Optional[str] = payload.get("timer_id")
    if timer_id:
        manager._timer_manager.cancel(timer_id)
        active = manager._state.system.active_timers
        original_len = len(active)

        manager._state.system.active_timers = manager._remove_timer_robustly(active, timer_id)

        if len(manager._state.system.active_timers) < original_len:
            state_changed = True
            changed_domains.add("system")

    return state_changed, changed_domains


async def handle_light_timer_expired(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx: Optional[int] = payload.get("idx")
    if idx is not None:
        timer_id = f"light_auto_off_{idx}"
        active = manager._state.system.active_timers
        original_len = len(active)

        manager._state.system.active_timers = manager._remove_timer_robustly(active, timer_id)

        if len(manager._state.system.active_timers) < original_len:
            state_changed = True
            changed_domains.add("system")

        automation_logger.info(f"Auto-off timer expired for light IDX {idx}, turning off light.")
        manager.dispatch(Event(
            type=EventType.HUB_STATE_CHANGED,
            payload={"idx": idx, "state": "OFF", "force": True}
        ))

    return state_changed, changed_domains


async def handle_vent_wait_expired(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    import time
    manager._state.sauna.ventilation_state = "RUNNING"
    manager._state.devices[8577] = "ON"
    manager._state.sauna.ventilation_deadline = int(time.time()) + (manager._config.sauna.vent_run_mins * 60)
    manager._timer_manager.schedule("vent_run", manager._state.sauna.ventilation_deadline, "VENT_RUN_EXPIRED")
    return True, {"sauna", "devices"}


async def handle_vent_run_expired(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.sauna.ventilation_state = "OFF"
    manager._state.devices[8577] = "OFF"
    manager._state.sauna.ventilation_deadline = None
    return True, {"sauna", "devices"}


async def handle_bath1_vent_lock_expired(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.devices[90001] = False
    state_changed = True
    changed_domains = {"devices"}

    # Immediately force an artificial humidity update to evaluate if it should turn off NOW
    if manager._state.sensors.bathroom1_hum is not None:
        manager.dispatch(Event(
            type=EventType.HUMIDITY_UPDATED,
            payload={"idx": 20004, "value": manager._state.sensors.bathroom1_hum}
        ))

    return state_changed, changed_domains