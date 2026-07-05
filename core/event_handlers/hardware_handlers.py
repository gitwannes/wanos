# --- file: core/event_handlers/hardware_handlers.py ---
import asyncio
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from logic.alert_manager import AlertManager


async def handle_hardware_bus_health_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    bus = payload.get("bus")
    is_connected = payload.get("connected", False)

    if bus == "sht11" and manager._state.hardware.sht11_connected != is_connected:
        manager._state.hardware.sht11_connected = is_connected
        state_changed = True
        changed_domains.add("hardware")

        # Failsafe: If the SHT11 bus physically dies, we must instantly disable the software toggle
        if not is_connected and manager._state.hardware.sht11_enabled:
            manager._state.hardware.sht11_enabled = False
            asyncio.create_task(logger.error("🔴 SHT11 Bus dropped! Disabling sensor polling loop."))

    elif bus == "gpio_input" and manager._state.hardware.gpio_input_connected != is_connected:
        manager._state.hardware.gpio_input_connected = is_connected
        state_changed = True
        changed_domains.add("hardware")

    elif bus == "gpio_output" and manager._state.hardware.gpio_output_connected != is_connected:
        manager._state.hardware.gpio_output_connected = is_connected
        state_changed = True
        changed_domains.add("hardware")

    return state_changed, changed_domains


async def handle_sht11_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.hardware.sht11_connected:
        await manager.logger.warning("🟡 [SHT11] Autostart rejected: SHT11 Sensor Bus is unplugged.")
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: SHT11 Sensor Bus is unplugged.")
        state_changed |= ch
        changed_domains |= dom
    else:
        manager._state.hardware.sht11_enabled = is_enabled
        state_changed = True
        changed_domains.add("hardware")

    return state_changed, changed_domains


async def handle_gpio_input_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    if is_enabled and not manager._state.hardware.gpio_input_connected:
        await manager.logger.warning("🟡 [GPIO Input] Autostart rejected: GPIO Input Bus is offline.")
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: GPIO Input Bus is offline.")
        state_changed |= ch
        changed_domains |= dom
    else:
        manager._state.hardware.gpio_input_enabled = is_enabled
        state_changed = True
        changed_domains.add("hardware")

    return state_changed, changed_domains


async def handle_gpio_output_toggled(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()
    is_enabled = payload.get("enabled", False)

    # ⚡ PRE-FLIGHT CHECK 1: Is the physical chip alive?
    if is_enabled and not manager._state.hardware.gpio_output_connected:
        await manager.logger.warning("🟡 [GPIO Output] Autostart rejected: GPIO Output Bus is offline.")
        ch, dom = AlertManager.process_alert(manager._state, "🔴 Command rejected: GPIO Output Bus is offline.")
        state_changed |= ch
        changed_domains |= dom
    # ⚡ PRE-FLIGHT CHECK 2: Hardware Interlock Chain (Eyes & Ears must be verified)
    elif is_enabled and (
            not manager._state.hardware.gpio_input_enabled or manager._state.sensors.sauna_calc_temp is None):
        await manager.logger.warning(
            "🟡 [GPIO Output] Pre-Flight Interlock Failed: Cannot arm GPIO outputs while flying blind (Inputs or Telemetry offline).")
        ch, dom = AlertManager.process_alert(manager._state,
                                             "🔴 Safety Interlock: Cannot arm outputs without active sensors.")
        state_changed |= ch
        changed_domains |= dom
    else:
        manager._state.hardware.gpio_output_enabled = is_enabled
        # Master Safety Gate Link: The safety contactor ONLY engages if outputs are armed.
        manager._set_hardware_safety_gate(is_enabled)
        state_changed = True
        changed_domains.add("hardware")

        # 🛡️ FATAL DROP PROTECTION: If the user drops outputs while the sauna is running,
        # we must cascade the OFF signal to the software PID controller immediately!
        if not is_enabled:
            if manager._state.sauna.active:
                manager.dispatch(Event(type=EventType.SAUNA_OFF))
            if manager._state.ir.active:
                manager.dispatch(Event(type=EventType.IR_OFF))

    return state_changed, changed_domains


async def handle_sensor_error(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx = payload.get("idx")
    if idx not in manager._state.hardware.sensor_errors:
        manager._state.hardware.sensor_errors.append(idx)
        state_changed = True
        changed_domains.add("hardware")

    # 20001 & 20002 = Sauna SHT Probes
    if idx in [20001, 20002] and manager._state.sauna.active:
        await manager.logger.critical(f"Critical sensor failure on IDX {idx}. Emergency stopping heater elements.")
        manager.dispatch(Event(type=EventType.SAUNA_OFF))

    return state_changed, changed_domains