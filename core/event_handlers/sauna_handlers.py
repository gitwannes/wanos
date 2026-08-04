# --- file: core/event_handlers/sauna_handlers.py ---
import time
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from core.well_known_entities import (
    ENTITY_IR_STATUS,
    ENTITY_SAFETY_SSR,
    ENTITY_SAUNA_DOOR,
    ENTITY_SAUNA_STATUS,
)


async def handle_sauna_on(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    door_idx = manager.resolve_entity_id(ENTITY_SAUNA_DOOR)
    door_sauna_open = (
        door_idx is not None and manager._state.devices.get(door_idx) == "OPEN"
    )
    if door_sauna_open:
        await manager.logger.warning("🌡️ Bouncer rejected SAUNA_ON: Door is open.")
        return False, set()
    if manager._state.sensors.sauna_calc_temp is None:
        await manager.logger.warning("🌡️ Bouncer rejected SAUNA_ON: Temperature data is currently missing (NULL).")
        return False, set()

    # ⚡ Master Z-Wave Safety Interlock
    # Verifies the 5V power supply to the SSRs is actively engaged by the Z-Wave network
    safety_idx = manager.resolve_entity_id(ENTITY_SAFETY_SSR)
    if safety_idx is None or manager._state.devices.get(safety_idx) != "ON":
        await manager.logger.warning(
            f"🌡️ Bouncer rejected SAUNA_ON: Master relay ({ENTITY_SAFETY_SSR}) is OFF.")
        manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={"msg_text": "🚨 Sauna start blocked: Master relay is disengaged!", "level": "critical"}))
        return False, set()

    manager._state.sauna.active = True
    manager._state.sauna.hold_mode = "autohold"
    manager._state.sauna.session_start_time = int(time.time())
    manager._sauna_timer_triggered = False
    manager._sauna_timer_duration_secs = manager._config.sauna.default_timer * 60
    manager._state.sauna.session_end_time = manager._sauna_timer_duration_secs

    # ⚡ Mirror status to the virtual dashboard sensor
    status_idx = manager.resolve_entity_id(ENTITY_SAUNA_STATUS)
    if status_idx is not None:
        manager._state.devices[status_idx] = "ON"

    if hasattr(manager, "_power_analytics"):
        manager._power_analytics.note_session_start()

    return True, {"sauna", "devices"}


async def handle_sauna_off(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.sauna.active = False
    manager._state.sauna.modulation_pwm = 0
    manager._state.sauna.phases_pwm = [0, 0, 0]
    manager._timer_manager.cancel("sauna_main")
    manager._sauna_timer_triggered = False

    manager._state.sauna.ventilation_state = "WAITING"
    manager._state.sauna.ventilation_deadline = int(time.time()) + (manager._config.sauna.vent_delay_mins * 60)
    manager._timer_manager.schedule("vent_wait", manager._state.sauna.ventilation_deadline, "VENT_WAIT_EXPIRED")

    # ⚡ Mirror status to the virtual dashboard sensor
    status_idx = manager.resolve_entity_id(ENTITY_SAUNA_STATUS)
    if status_idx is not None:
        manager._state.devices[status_idx] = "OFF"

    return True, {"sauna", "devices"}


async def handle_sauna_timer_adjusted(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    minutes_to_add = payload.get("minutes", 0)

    if manager._state.sauna.active:
        manager._sauna_timer_duration_secs += (minutes_to_add * 60)
        if manager._sauna_timer_triggered:
            manager._state.sauna.session_end_time += (minutes_to_add * 60)
            manager._timer_manager.cancel("sauna_main")
            manager._timer_manager.schedule("sauna_main", manager._state.sauna.session_end_time, "SAUNA_TIMER_EXPIRED")
        else:
            manager._state.sauna.session_end_time = manager._sauna_timer_duration_secs
        return True, {"sauna"}

    return False, set()


async def handle_sauna_hold_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    current_mode = manager._state.sauna.hold_mode
    if current_mode == "autohold" or current_mode == "hold":
        manager._state.sauna.hold_mode = "nohold"
    else:
        manager._state.sauna.hold_mode = "hold"
    return True, {"sauna"}


async def handle_sauna_timer_expired(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    logger.warning("Sauna session limit countdown reached 0.")
    manager.dispatch(Event(type=EventType.SAUNA_OFF))
    return False, set()


async def handle_sauna_setpoint_changed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    new_target = payload.get("target")
    if new_target is not None:
        manager._state.sauna.target_temp = min(float(new_target), manager._state.sauna.max_temp)
        return True, {"sauna"}
    return False, set()


async def handle_sauna_modulation_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.sauna.modulation_pwm = payload.get("pwm", 0)
    manager._state.sauna.phases_pwm = payload.get("phases", [0, 0, 0])
    return True, {"sauna"}


async def handle_ir_on(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    if manager._state.sensors.sauna_calc_temp is None:
        await manager.logger.warning("🌡️ Bouncer rejected IR_ON: Temperature data is currently missing (NULL).")
        return False, set()

    manager._state.ir.active = True
    now = int(time.time())
    manager._state.ir.session_start_time = now
    manager._state.ir.session_end_time = now + (manager._config.ir.max_time_mins * 60)

    manager._timer_manager.schedule("ir_main", manager._state.ir.session_end_time, "IR_TIMER_EXPIRED")

    # ⚡ Mirror status to the virtual dashboard sensor
    ir_status_idx = manager.resolve_entity_id(ENTITY_IR_STATUS)
    if ir_status_idx is not None:
        manager._state.devices[ir_status_idx] = "ON"

    if hasattr(manager, "_power_analytics"):
        manager._power_analytics.note_session_start()

    return True, {"ir", "devices"}


async def handle_ir_off(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.ir.active = False
    manager._timer_manager.cancel("ir_main")

    # ⚡ Mirror status to the virtual dashboard sensor
    ir_status_idx = manager.resolve_entity_id(ENTITY_IR_STATUS)
    if ir_status_idx is not None:
        manager._state.devices[ir_status_idx] = "OFF"

    return True, {"ir", "devices"}


async def handle_ir_timer_expired(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager.dispatch(Event(type=EventType.IR_OFF))
    return False, set()


async def handle_ir_modulation_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.ir.modulation_pwm = payload.get("pwm", 0)
    manager._state.ir.frequency = payload.get("freq", 0)
    return True, {"ir"}