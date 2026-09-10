# --- file: core/event_handlers/sauna_handlers.py ---
import time
from typing import Any, Set, Tuple
from pydantic import ValidationError
from core.models import Event, EventType, SaunaSetpointPayload, normalize_phases_pwm, ZERO_PHASES_PWM
from logic.alert_manager import AlertManager
from core.well_known_entities import (
    ENTITY_IR_STATUS,
    ENTITY_SAFETY_SSR,
    ENTITY_SAUNA_DOOR,
    ENTITY_SAUNA_STATUS,
)


async def handle_sauna_on(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    if manager._state.ir.active:
        await manager.logger.warning("🌡️ Bouncer rejected SAUNA_ON: IR session is active.")
        return False, set()
    door_idx = manager.resolve_entity_id(ENTITY_SAUNA_DOOR)
    door_sauna_open = (
        door_idx is not None and manager._state.devices.get(door_idx) == "OPEN"
    )
    if door_sauna_open:
        await manager.logger.warning("🌡️ Bouncer rejected SAUNA_ON: Door is open.")
        return False, set()
    # Door must have been closed recently (config sauna.door_closed_max_mins); null = never seen close.
    closed_since = manager._state.doors.sauna_closed_since_unix
    max_mins = int(getattr(manager._config.sauna, "door_closed_max_mins", 5) or 5)
    if closed_since is None or (int(time.time()) - int(closed_since)) > (max_mins * 60):
        await manager.logger.warning(
            "🌡️ Bouncer rejected SAUNA_ON: Door closed too long (or closed_since unknown)."
        )
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

    # Freeze U/V/W fire order for this session (waterfall + display + session record).
    if hasattr(manager, "sauna_logic"):
        order = manager.sauna_logic.lock_fire_order()
        manager._state.sauna.fireorder = order.replace(" -> ", "")

    # ⚡ Mirror status to the virtual dashboard sensor
    status_idx = manager.resolve_entity_id(ENTITY_SAUNA_STATUS)
    if status_idx is not None:
        manager._state.devices[status_idx] = "ON"

    if hasattr(manager, "_power_analytics"):
        manager._power_analytics.note_session_start("sauna")

    return True, {"sauna", "devices"}


async def handle_sauna_off(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.sauna.active = False
    manager._state.sauna.modulation_pwm = 0
    manager._state.sauna.phases_pwm = dict(ZERO_PHASES_PWM)
    manager._timer_manager.cancel("sauna_main")
    manager._sauna_timer_triggered = False
    if hasattr(manager, "sauna_logic"):
        manager.sauna_logic.unlock_fire_order()

    # Post-OFF extraction fan: Library rule (Set after) + Timers & types auto-off — not hub timers.

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
            # Soft session end: fire Sauna OFF directly (no SAUNA_TIMER_EXPIRED hop).
            manager._timer_manager.schedule("sauna_main", manager._state.sauna.session_end_time, "SAUNA_OFF")
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


async def handle_sauna_setpoint_changed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    new_target = payload.get("target")
    if new_target is None:
        return False, set()

    try:
        parsed = SaunaSetpointPayload(target=new_target)
    except ValidationError:
        await manager.logger.error(
            f"Command rejected: invalid sauna setpoint payload (target={new_target!r})"
        )
        return AlertManager.process_alert(
            manager._state, "🟡 Command rejected: invalid sauna setpoint"
        )

    min_temp = manager._state.sauna.min_temp or float(manager._config.sauna.min_temp)
    max_temp = manager._state.sauna.max_temp or float(manager._config.sauna.max_temp)
    manager._state.sauna.target_temp = max(min_temp, min(parsed.target, max_temp))
    return True, {"sauna"}


async def handle_sauna_modulation_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.sauna.modulation_pwm = payload.get("pwm", 0)
    manager._state.sauna.phases_pwm = normalize_phases_pwm(
        payload.get("phases", ZERO_PHASES_PWM)
    )
    if hasattr(manager, "_power_analytics") and manager._power_analytics is not None:
        manager._power_analytics.apply_mod_real_power_gate(manager._state)
    return True, {"sauna"}


async def handle_ir_timer_adjusted(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    minutes_to_add = int(payload.get("minutes", 0))

    if not manager._state.ir.active:
        return False, set()

    now = int(time.time())
    cfg = manager._config.ir
    start_ts = manager._state.ir.session_start_time or now
    cur_end = manager._state.ir.session_end_time or now
    new_end = cur_end + (minutes_to_add * 60)
    min_end = start_ts + (int(cfg.min_time_mins) * 60)
    max_end = start_ts + (int(cfg.max_time_mins) * 60)
    manager._state.ir.session_end_time = max(min_end, min(max_end, new_end))

    manager._timer_manager.cancel("ir_main")
    # Soft IR session end: fire IR OFF directly (no IR_TIMER_EXPIRED hop).
    manager._timer_manager.schedule(
        "ir_main", manager._state.ir.session_end_time, "IR_OFF"
    )
    return True, {"ir"}


async def handle_ir_on(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    if manager._state.sauna.active:
        await manager.logger.warning("🌡️ Bouncer rejected IR_ON: Sauna session is active.")
        return False, set()
    if manager._state.sensors.sauna_calc_temp is None:
        await manager.logger.warning("🌡️ Bouncer rejected IR_ON: Temperature data is currently missing (NULL).")
        return False, set()

    manager._state.ir.active = True
    now = int(time.time())
    manager._state.ir.session_start_time = now
    default_mins = getattr(manager._config.ir, "default_time_mins", 7)
    manager._state.ir.session_end_time = now + (int(default_mins) * 60)

    # C35: each IR_ON resets mod to site default (do not inherit last session).
    default_mod = int(getattr(manager._config.ir, "default_ir_modulation", 75))
    # Stepped IR duty/freq for ZC SSRs (keep in sync with frontend irStepFreqs / actuators).
    freq_map = {0: 0, 25: 25, 33: 33, 50: 50, 67: 33, 75: 25, 100: 5}
    manager._state.ir.modulation_pwm = default_mod
    manager._state.ir.frequency = freq_map.get(default_mod, 0)

    manager._timer_manager.schedule("ir_main", manager._state.ir.session_end_time, "IR_OFF")

    # ⚡ Mirror status to the virtual dashboard sensor
    ir_status_idx = manager.resolve_entity_id(ENTITY_IR_STATUS)
    if ir_status_idx is not None:
        manager._state.devices[ir_status_idx] = "ON"

    if hasattr(manager, "_power_analytics"):
        manager._power_analytics.note_session_start("ir")

    return True, {"ir", "devices"}


async def handle_ir_off(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.ir.active = False
    manager._timer_manager.cancel("ir_main")

    # ⚡ Mirror status to the virtual dashboard sensor
    ir_status_idx = manager.resolve_entity_id(ENTITY_IR_STATUS)
    if ir_status_idx is not None:
        manager._state.devices[ir_status_idx] = "OFF"

    return True, {"ir", "devices"}


async def handle_ir_modulation_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.ir.modulation_pwm = payload.get("pwm", 0)
    manager._state.ir.frequency = payload.get("freq", 0)
    return True, {"ir"}