# --- file: core/event_handlers/integration_handlers.py ---
import time
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from logic.alert_manager import AlertManager


async def handle_automations_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    is_enabled = payload.get("enabled", True)
    state_str = "ON" if is_enabled else "OFF"
    manager._state.system.automations_enabled = is_enabled
    state_changed = True
    changed_domains = {"system"}

    color = "🟢" if is_enabled else "🔴"
    ch, dom = AlertManager.process_alert(manager._state, f"{color} Automations engine turned {state_str}")
    state_changed |= ch
    changed_domains |= dom

    from core.logger import automation_logger
    automation_logger.info(f"Master Toggle -> Automations Engine set to {state_str}")
    return state_changed, changed_domains


async def handle_domoticz_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.system.domoticz_mqtt_connected:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: Domoticz Hub is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.domoticz_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "🔴"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Domoticz polling turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

        # --- THE UX WIPE (NULLIFICATION) ---
        if not is_enabled:
            for idx in list(manager._state.devices.keys()):
                if isinstance(idx, int) and idx < 10000:
                    if manager._state.devices[idx] is not None:
                        manager._state.devices[idx] = None
                        state_changed = True
                        changed_domains.add("devices")
        else:
            if payload.get("is_auto_recovery", False):
                deadline = int(time.time()) + 10
                manager._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED", {"reason": "network_recovery"})
                logger.info("Domoticz Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

    return state_changed, changed_domains


async def handle_rfxcom_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.system.rfxcom_connected:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: RFXCOM Transceiver is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.rfxcom_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "🔴"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Native RFXCOM Engine turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

        if is_enabled and payload.get("is_auto_recovery", False):
            deadline = int(time.time()) + 10
            manager._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED", {"reason": "network_recovery"})
            logger.info("RFXCOM Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

    return state_changed, changed_domains


async def handle_owm_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.system.wanos_mqtt_connected:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: WanOS Broker is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.owm_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "🔴"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} OWM Integration turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

        if is_enabled and payload.get("is_auto_recovery", False):
            deadline = int(time.time()) + 10
            manager._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED", {"reason": "network_recovery"})
            logger.info("OWM Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

    return state_changed, changed_domains


async def handle_hue_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.system.hue_connected:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: Hue Bridge is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.hue_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "🔴"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Hue Integration turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

        if is_enabled and payload.get("is_auto_recovery", False):
            deadline = int(time.time()) + 10
            manager._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED", {"reason": "network_recovery"})
            logger.info("Hue Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

    return state_changed, changed_domains


async def handle_epson_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.system.epson_connected:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: Epson Projector is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.epson_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "🔴"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Epson Integration turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

        if is_enabled and payload.get("is_auto_recovery", False):
            deadline = int(time.time()) + 10
            manager._timer_manager.schedule("post_recovery_sweep", deadline, "SYSTEM_SWEEP_REQUESTED", {"reason": "network_recovery"})
            logger.info("Epson Integration AUTO-RECOVERED. Scheduled debounced catch-up sweep in 10s.")

    return state_changed, changed_domains


async def handle_zwave_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.system.zwave_connected:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: Z-Wave Bridge is physically offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.zwave_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "🔴"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Z-Wave Integration turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

    return state_changed, changed_domains


async def handle_simulations_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.hardware.simulations_enabled = payload.get("enabled", False)
    return True, {"hardware"}