# --- file: core/event_handlers/hub_handlers.py ---
import time
import asyncio
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from core.logger import automation_logger
from logic.alert_manager import AlertManager


async def handle_door_changed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx = payload.get("idx")
    is_open = payload.get("is_open", False)
    new_state = "OPEN" if is_open else "CLOSED"

    if manager._state.devices.get(idx) != new_state:
        manager._state.devices[idx] = new_state
        state_changed = True
        changed_domains.add("devices")

        # Sauna safety interlock logic evaluation
        if idx == 10001 and is_open and manager._state.sauna.active:
            manager._state.sauna.active = False
            manager._state.sauna.modulation_pwm = 0
            manager._state.sauna.phases_pwm = [0, 0, 0]
            manager._state.sauna.ventilation_state = "OFF"
            changed_domains.add("sauna")
            asyncio.create_task(logger.warning("🚪 Sauna door opened while active! Emergency cutoff triggered."))

    return state_changed, changed_domains


async def handle_hub_state_changed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx = payload.get("idx")
    state_val = payload.get("state")  # "ON" or "OFF"
    old_val = manager._state.devices.get(idx)
    is_init = payload.get("is_initialization", False)

    # RICH PAYLOAD MERGE FOR ADVANCED DEVICES (Hue, Sonos)
    is_rich_payload = "bri" in payload or "xy" in payload or "volume" in payload
    new_val = state_val

    if isinstance(old_val, dict):
        new_val = old_val.copy()
        if state_val is not None:
            new_val["state"] = state_val
        if "bri" in payload:
            new_val["bri"] = payload["bri"]
        if "xy" in payload:
            new_val["xy"] = payload["xy"]
        if "volume" in payload:
            new_val["volume"] = payload["volume"]
    elif is_rich_payload:
        new_val = {"state": state_val}
        if "bri" in payload:
            new_val["bri"] = payload["bri"]
        if "xy" in payload:
            new_val["xy"] = payload["xy"]
        if "volume" in payload:
            new_val["volume"] = payload["volume"]

    # Hybrid Learning: Cache semantic names from Domoticz
    device_name = payload.get("name")
    if device_name and idx not in manager._state.dashboard_map and str(idx) not in manager._state.dashboard_map:
        manager._state.dashboard_map[idx] = device_name
        if not is_init:
            logger.info(f"Name for {idx} added to the dashboard map: {device_name}.")

    is_push_button = payload.get("is_push_button", False)
    is_force = payload.get("force", False)

    # RFXCOM FORCE GUARD
    meta_origin: str = manager._state.device_metadata.get(idx, {}).get("origin", "")
    if not is_force and meta_origin == "rfxcom":
        is_force = True
        payload["force"] = True

    if old_val != new_val or is_push_button or is_force:
        manager._state.devices[idx] = new_val
        state_changed = True
        changed_domains.add("devices")

        # Artificially inject 0.0W to instantly flush power graphs when switches turn off
        if state_val == "OFF":
            if idx == 8:  # pc
                manager.dispatch(Event(type=EventType.POWER_UPDATED, payload={
                    "idx": 9, "value": 0.0, "device_type": "power", "origin": "domoticz",
                    "name": manager._state.dashboard_map.get(9, "pc_power")
                }))
            elif idx == 9618:  # pc_aux
                manager.dispatch(Event(type=EventType.POWER_UPDATED, payload={
                    "idx": 9622, "value": 0.0, "device_type": "power", "origin": "domoticz",
                    "name": manager._state.dashboard_map.get(9622, "pc_aux_power")
                }))

        # Bathroom 1e ventilator timer lock
        if idx == 71034 and state_val == "ON" and old_val != "ON":
            manager._state.devices[90001] = True
            deadline = int(time.time()) + (manager._config.bathroom1.vent_min_runtime_mins * 60)
            manager._timer_manager.schedule("bath1_vent_lock", deadline, "BATH1_VENT_LOCK_EXPIRED")

        # EPSON INTERCEPTOR
        if idx == 80001 and (old_val != state_val or is_force):
            if manager._state.system.epson_integration_enabled:
                if getattr(manager, "epson_bridge", None):
                    asyncio.create_task(manager.epson_bridge.power(state_val))
                else:
                    automation_logger.error(
                        "Tried to trigger Epson projector, but bridge is offline or misconfigured.")
            else:
                automation_logger.warning("Epson command dropped: Integration is disabled in UI.")
                ch, dom = AlertManager.process_alert(manager._state,
                                                     "🔴 Epson command dropped: Integration is disabled.")
                state_changed |= ch
                changed_domains |= dom

        # SONOS INTERCEPTOR
        meta_origin = manager._state.device_metadata.get(idx, {}).get("origin", "")
        if meta_origin == "sonos" and (old_val != state_val or is_force):
            if manager._state.system.sonos_integration_enabled:
                if getattr(manager, "sonos_bridge", None):
                    # Route the entire rich payload containing volume and station parameters
                    asyncio.create_task(manager.sonos_bridge.execute_command(payload))
                else:
                    automation_logger.error(
                        "Tried to trigger Sonos speaker, but bridge is offline or misconfigured.")
            else:
                automation_logger.warning("Sonos command dropped: Integration is disabled in UI.")
                ch, dom = AlertManager.process_alert(manager._state,
                                                     "🔴 Sonos command dropped: Integration is disabled.")
                state_changed |= ch
                changed_domains |= dom

    return state_changed, changed_domains


async def handle_lighting_state_changed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx = payload.get("idx")
    state_val = payload.get("state")
    if manager._state.devices.get(idx) != state_val:
        manager._state.devices[idx] = state_val
        state_changed = True
        changed_domains.add("devices")

    return state_changed, changed_domains