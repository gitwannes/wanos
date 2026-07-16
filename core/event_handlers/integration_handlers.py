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

    color = "🟢" if is_enabled else "⚪"
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
        await manager.logger.warning("🟡 [Domoticz] Command rejected: Remote broker is offline.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: Domoticz Hub is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.domoticz_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "⚪"
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
        await manager.logger.warning("🟡 [Native RFX] Command rejected: USB Transceiver is offline or unplugged.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: RFXCOM Transceiver is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.rfxcom_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "⚪"
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
        await manager.logger.warning("🟡 [OWM] Command rejected: Local WanOS broker is offline.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: WanOS Broker is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.owm_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "⚪"
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
        await manager.logger.warning("🟡 [Hue] Command rejected: Hue Bridge is offline.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: Hue Bridge is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.hue_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "⚪"
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
        await manager.logger.warning("🟡 [Epson] Command rejected: Epson Projector is offline.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: Epson Projector is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.epson_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "⚪"
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

    # Tier 1 Intercept: Physical Stick Missing
    if is_enabled and not manager._state.system.zwave_hardware_connected:
        await manager.logger.warning("🟡 [Z-Wave] Command rejected: USB Stick is unplugged.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: Z-Wave USB Stick is unplugged.")
        state_changed |= ch
        changed_domains |= dom
    # Tier 2 Intercept: Control Plane (Web Server) Offline
    elif is_enabled and not manager._state.system.zwave_web_alive:
        await manager.logger.warning("🟡 [Z-Wave] Command rejected: JS Web Panel (8091) is unreachable.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: Z-Wave JS Web Panel is offline.")
        state_changed |= ch
        changed_domains |= dom
    # Tier 3 Intercept: Data Plane (MQTT Data) Frozen
    elif is_enabled and not manager._state.system.zwave_data_alive:
        await manager.logger.warning("🟡 [Z-Wave] Command rejected: MQTT Data stream is frozen.")
        ch, dom = AlertManager.process_alert(manager._state, "🟡 Command rejected: Z-Wave Data stream is frozen.")
        state_changed |= ch
        changed_domains |= dom
    else:
        state_str = "ON" if is_enabled else "OFF"
        manager._state.system.zwave_integration_enabled = is_enabled
        state_changed = True
        changed_domains.add("system")

        color = "🟢" if is_enabled else "⚪"
        raw_error = payload.get("error_msg")
        error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None
        ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Z-Wave Integration turned {state_str}")
        state_changed |= ch
        changed_domains |= dom

    return state_changed, changed_domains


async def handle_sonos_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """Handles the UI master switch to enable/disable the local Sonos integration."""
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    state_str = "ON" if is_enabled else "OFF"
    manager._state.system.sonos_integration_enabled = is_enabled
    state_changed = True
    changed_domains.add("system")

    color = "🟢" if is_enabled else "⚪"
    raw_error = payload.get("error_msg")
    error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None

    # Notify the dashboard via AlertManager
    ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Sonos Integration turned {state_str}")
    state_changed |= ch
    changed_domains |= dom

    # Dynamically spin up or tear down the async polling bridge
    if is_enabled:
        if not getattr(manager, "sonos_bridge", None):
            from integrations.sonos import SonosBridge
            manager.sonos_bridge = SonosBridge(manager)
        await manager.sonos_bridge.start()
    else:
        if getattr(manager, "sonos_bridge", None):
            await manager.sonos_bridge.stop()

    return state_changed, changed_domains


async def handle_onkyo_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """Handles the UI master switch to enable/disable the local Onkyo integration."""
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    state_str = "ON" if is_enabled else "OFF"
    manager._state.system.onkyo_integration_enabled = is_enabled
    state_changed = True
    changed_domains.add("system")

    color = "🟢" if is_enabled else "⚪"
    raw_error = payload.get("error_msg")
    error_alert = f"🔴 {raw_error}" if (not is_enabled and raw_error) else None

    ch, dom = AlertManager.process_alert(manager._state, error_alert, f"{color} Onkyo Integration turned {state_str}")
    state_changed |= ch
    changed_domains |= dom

    # Dynamically spin up or tear down the async polling bridge
    if is_enabled:
        if not getattr(manager, "onkyo_bridge", None):
            from integrations.onkyo import OnkyoBridge
            manager.onkyo_bridge = OnkyoBridge(manager)
        await manager.onkyo_bridge.start()
    else:
        if getattr(manager, "onkyo_bridge", None):
            await manager.onkyo_bridge.stop()

    return state_changed, changed_domains


async def handle_sonos_command(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """Routes rich automation payloads (volume, radio station URI) to the Sonos bridge."""
    import asyncio

    if manager._state.system.sonos_integration_enabled and getattr(manager, "sonos_bridge", None):
        # Offload execution to prevent blocking the WanOS event loop
        asyncio.create_task(manager.sonos_bridge.execute_command(event.payload))
    else:
        from core.logger import automation_logger
        automation_logger.warning("🟡 [Sonos] Command rejected: Integration is disabled in UI.")

    return False, set()


async def handle_simulations_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.hardware.simulations_enabled = payload.get("enabled", False)
    return True, {"hardware"}