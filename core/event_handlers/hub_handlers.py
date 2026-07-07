# --- file: core/event_handlers/hub_handlers.py ---
import time
import asyncio
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from core.logger import automation_logger
from logic.alert_manager import AlertManager

_shutter_debounce_tasks = {}

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
            # ⚡ HUE NORMALIZER: Compress legacy 0-254 integers into 0-100% metrics to prevent Echo bounces
            raw_bri = payload["bri"]
            if isinstance(raw_bri, (int, float)) and raw_bri > 100:
                new_val["bri"] = round((raw_bri / 254.0) * 100.0)
            else:
                new_val["bri"] = raw_bri
        if "xy" in payload:
            new_val["xy"] = payload["xy"]
        if "volume" in payload:
            new_val["volume"] = payload["volume"]
    elif is_rich_payload:
        new_val = {"state": state_val}
        if "bri" in payload:
            raw_bri = payload["bri"]
            if isinstance(raw_bri, (int, float)) and raw_bri > 100:
                new_val["bri"] = round((raw_bri / 254.0) * 100.0)
            else:
                new_val["bri"] = raw_bri
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

        # --- ⚡ DEVICE INSIGHTS HISTORY LOGGING ---
        if not is_init and hasattr(manager, "history_manager"):
            device_meta = manager._state.device_metadata.get(idx, {})
            dev_type = device_meta.get("type", "")

            # Explicitly include hardware doors as binary switches, ignore other passive sensors
            if dev_type not in ["temp", "hum", "temp_hum", "motion", "scene"] or idx in [10001, 10002]:
                is_analog = dev_type in ["blinds", "shutter"] or isinstance(state_val, (int, float))

                # Check if the fundamental binary power state actually changed
                old_log_state = old_val.get("state") if isinstance(old_val, dict) else old_val

                if old_log_state != state_val or is_push_button:
                    if is_analog:
                        # Debounce analog slider values: Wait 30 seconds of no movement before committing
                        if idx in _shutter_debounce_tasks:
                            _shutter_debounce_tasks[idx].cancel()

                        async def debounced_log(target_idx, val):
                            try:
                                await asyncio.sleep(30.0)
                                manager.history_manager.log_event(target_idx, str(val))
                                # Trigger frontend SSE update via dummy injection
                                manager.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED,
                                                       payload={"insights_trigger": True}))
                            except asyncio.CancelledError:
                                pass

                        _shutter_debounce_tasks[idx] = asyncio.create_task(debounced_log(idx, state_val))
                    else:
                        # Binary switches (ON/OFF) commit immediately without debounce
                        manager.history_manager.log_event(idx, str(state_val))
                        changed_domains.add("metrics")

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