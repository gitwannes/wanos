# --- file: core/event_handlers/system_handlers.py ---
import time
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from core.config import load_config
from logic.alert_manager import AlertManager
from logic.environment_scheduler import EnvironmentScheduler


async def handle_system_ready(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    manager._state.hardware.sht11_enabled = False
    manager._state.hardware.gpio_input_enabled = False
    manager._state.hardware.gpio_output_enabled = False
    manager._set_hardware_safety_gate(False)
    manager._set_hardware_safety_gate(False)
    return True, {"hardware"}


async def handle_alert_dismissed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    if AlertManager.dismiss_alert(manager._state, payload.get("id")):
        return True, {"system"}
    return False, set()


async def handle_alert_clear_non_critical(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    if AlertManager.clear_non_critical(manager._state):
        return True, {"system"}
    return False, set()


async def handle_alert_injected(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    errmsg_to_send = payload.get("msg_text", "")
    ch, dom = AlertManager.process_alert(manager._state, errmsg_to_send)
    return ch, dom


async def handle_config_reload_requested(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    await manager.logger.info("🔄 Configuration hot-reload requested via UI button.")
    state_changed = False
    changed_domains = set()

    try:
        from logic.automation_rules import AutomationEngine
        new_config = load_config()
        manager._config = new_config
        AutomationEngine._config = None  # Reset rules engine cached reference copy

        # Delegate metadata assembly to the atomic rebuilder
        manager.rebuild_core_metadata()

        # RECYCLE HUE INTEGRATION MAPPINGS & CONNECTIONS
        if manager.hue_bridge:
            await manager.hue_bridge.stop()
            manager.hue_bridge._config = new_config
            manager.hue_bridge._initialize_mappings()
            await manager.hue_bridge.start()

        state_changed = True
        changed_domains.add("system")

        msg: str = f"🟢 Config reloaded."
        ch, dom = AlertManager.process_alert(manager._state, msg)
        state_changed |= ch
        changed_domains |= dom

        # Automatically trigger a system sweep 2 seconds after a config reload
        manager._timer_manager.schedule("post_reload_sweep", int(time.time()) + 2, "SYSTEM_SWEEP_REQUESTED",
                                        {"reason": "config_reload"})
    except Exception as e:
        ch, dom = AlertManager.process_alert(manager._state, f"🔴 Config reload failed: {e}")
        state_changed |= ch
        changed_domains |= dom

    return state_changed, changed_domains


async def handle_system_sweep_requested(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    EnvironmentScheduler.recalculate_schedule(manager._state, manager._config, manager._start_time, manager.dispatch)

    sns = manager._state.sensors
    now = int(time.time())

    # ENHANCED RECOVERY GUARD
    reason = payload.get("reason")
    is_passive_sweep = reason in ["network_recovery", "config_reload", None]
    uptime = int(time.time() - manager._start_time)

    if is_passive_sweep or uptime < 180:
        logger.info(
            f"[Sweeper] Skipping time-series hardware alignment to respect passive baseline (Uptime: {uptime}s).")
    else:
        if sns.env_schedule_blinds_open_unix and sns.env_schedule_blinds_close_unix:
            if sns.env_schedule_blinds_open_unix <= now < sns.env_schedule_blinds_close_unix:
                manager.dispatch(Event(type=EventType.BLINDS_OPEN_TRIGGER))
            else:
                manager.dispatch(Event(type=EventType.BLINDS_CLOSE_TRIGGER))

        if sns.env_schedule_twilight_morning_on_unix and sns.env_schedule_twilight_morning_off_unix:
            if sns.env_schedule_twilight_morning_on_unix <= now < sns.env_schedule_twilight_morning_off_unix:
                manager.dispatch(Event(type=EventType.TWILIGHT_MORNING_ON_TRIGGER))
            else:
                manager.dispatch(Event(type=EventType.TWILIGHT_MORNING_OFF_TRIGGER))

        if sns.env_schedule_twilight_evening_on_unix and sns.env_schedule_twilight_evening_off_unix:
            if sns.env_schedule_twilight_evening_on_unix <= now < sns.env_schedule_twilight_evening_off_unix:
                manager.dispatch(Event(type=EventType.TWILIGHT_EVENING_ON_TRIGGER))
            else:
                manager.dispatch(Event(type=EventType.TWILIGHT_EVENING_OFF_TRIGGER))

    ch, dom = AlertManager.process_alert(manager._state,
                                         "🟢 System Sweeper complete. Suntime-based events synchronized.")
    state_changed |= ch
    changed_domains |= dom

    return state_changed, changed_domains


async def handle_zwave_discovery(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """Places newly discovered Z-Wave endpoints into the Inbox for UI provisioning."""
    payload = event.payload or {}
    path = payload.get("path")
    if not path:
        return False, set()

    # Use the path as the unique key to deduplicate noise and instantly overwrite old values
    manager._state.system.zwave_inbox[path] = {
        "node_name": payload.get("node_name"),
        "command_class": payload.get("command_class"),
        "value": payload.get("value"),
        "last_seen": int(time.time())
    }
    return True, {"system"}