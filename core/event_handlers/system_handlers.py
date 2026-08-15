# --- file: core/event_handlers/system_handlers.py ---
import time
from typing import Any, Set, Tuple
from loguru import logger
from core.models import Event, EventType
from core.config import load_config
from core.reload_alerts import (
    reload_alert_complete,
    reload_alert_failed,
    reload_alert_in_progress,
    resolve_reload_alert_scope,
)
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


async def handle_alert_ui_dismissed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """
    C8: log-only UI dismiss (banner or bell). Does not remove the alert from shared state
    (C2 dual-dismiss stays FE-local).
    """
    payload = event.payload or {}
    surface = str(payload.get("surface") or "unknown").strip().lower()
    if surface not in ("banner", "bell"):
        surface = "unknown"
    level = str(payload.get("level") or "info").strip() or "info"
    text = str(payload.get("message") or "").strip()
    logger.info(f'Alert dismissed ({surface}): level={level} "{text}"')
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
    # Distinguish Admin "Reload" button from surgical API writes (Blocky save, soft-hide, …).
    payload = event.payload or {}
    source = str(payload.get("source") or "").strip().lower()
    scope = str(payload.get("scope") or "").strip().lower()
    alert_scope = resolve_reload_alert_scope(payload)
    if not source and str(payload.get("origin") or "").upper() == "MANUAL":
        source = "ui_button"
    if source in ("ui_button", "ui", "manual", "button"):
        await manager.logger.info("🔄 Configuration hot-reload requested via UI button.")
    elif scope in ("auto_off_metadata", "timers_types", "product_types"):
        await manager.logger.info("🔄 Scoped reload (auto-off + product types + metadata).")
    else:
        await manager.logger.info("🔄 Configuration hot-reload (auto — after config write).")

    state_changed = False
    changed_domains: Set[str] = set()

    ch_start, dom_start = AlertManager.process_alert(
        manager._state, reload_alert_in_progress(alert_scope)
    )
    state_changed |= ch_start
    changed_domains |= dom_start

    try:
        # B9A / B10G: Hue preset CRUD must be lightning fast.
        # Avoid full load_config() + rebuild_core_metadata() (which triggers NVRAM + all integration reloads).
        if scope == "hue_presets":
            try:
                from core.hue_presets_store import read_presets
                from core.config import HuePresetConfig
                from logic.automation_rules import AutomationEngine

                raw_presets = read_presets()
                new_presets: dict[str, HuePresetConfig] = {}
                for key, raw in raw_presets.items():
                    if not isinstance(raw, dict):
                        continue
                    xy = raw.get("xy")
                    xy_val = xy if isinstance(xy, list) and len(xy) >= 2 else None
                    rgb_val = raw.get("rgb")
                    new_presets[str(key)] = HuePresetConfig(
                        name=str(raw.get("name") or key),
                        bri=int(raw.get("bri") or 0),
                        xy=xy_val,
                        rgb=rgb_val,
                    )

                # Update in-memory config (used by automation rules at runtime)
                if getattr(manager._config, "hue", None) is not None:
                    manager._config.hue.presets = new_presets

                # Update UI-facing state only (no metadata rebuild, no NVRAM reload)
                manager._state.system.hue_presets = {k: v.model_dump() for k, v in new_presets.items()}

                # Reset any cached config reference in rules engine
                AutomationEngine._config = None

                ch_done, dom_done = AlertManager.process_alert(
                    manager._state, reload_alert_complete(alert_scope)
                )
                state_changed |= ch_done
                changed_domains |= dom_done
                changed_domains.add("system")
                return state_changed, changed_domains
            except Exception as e:
                await manager.logger.error(f"Fast hue_presets reload failed; falling back to full reload: {e}")
                alert_scope = "full"

        from logic.automation_rules import AutomationEngine
        new_config = load_config()
        manager._config = new_config
        AutomationEngine._config = None  # Reset rules engine cached reference copy

        # Delegate metadata assembly to the atomic rebuilder
        manager.rebuild_core_metadata()

        # D1: scoped reload — skip bridge recycle for Timers & types saves.
        full_recycle = scope not in ("auto_off_metadata", "timers_types", "product_types", "hue_presets")
        if full_recycle:
            # RECYCLE HUE INTEGRATION MAPPINGS & CONNECTIONS
            if manager.hue_bridge:
                await manager.hue_bridge.stop()
                manager.hue_bridge._config = new_config
                manager.hue_bridge._initialize_mappings()
                await manager.hue_bridge.start()

            # Rebuild RFX hex translation maps from the new native_rfx list
            if getattr(manager, "rfxcom_bridge", None):
                manager.rfxcom_bridge._outbound_map.clear()
                manager.rfxcom_bridge._inbound_map.clear()
                manager.rfxcom_bridge._last_known_states.clear()
                manager.rfxcom_bridge._build_translation_maps()

            # Refresh Sonos device/station maps and speaker sockets
            if getattr(manager, "sonos_bridge", None):
                import soco
                bridge = manager.sonos_bridge
                sonos_cfg = new_config.sonos
                bridge.device_map = sonos_cfg.device_map if sonos_cfg else {}
                bridge.stations = sonos_cfg.stations if sonos_cfg else {}
                bridge.max_vol = sonos_cfg.max_volume if sonos_cfg else 70
                new_speakers = {}
                for idx, node in bridge.device_map.items():
                    existing = bridge.speakers.get(idx)
                    new_speakers[idx] = existing if existing is not None else soco.SoCo(node.ip)
                bridge.speakers = new_speakers

            # Recycle Onkyo TCP listeners against the new device map
            if getattr(manager, "onkyo_bridge", None):
                was_running = getattr(manager.onkyo_bridge, "_running", False)
                if was_running:
                    await manager.onkyo_bridge.stop()
                manager.onkyo_bridge.config = new_config.onkyo
                manager.onkyo_bridge.device_map = (
                    new_config.onkyo.device_map if new_config.onkyo else {}
                )
                manager.onkyo_bridge.max_vol = (
                    new_config.onkyo.max_volume if new_config.onkyo else 60
                )
                if was_running and manager._state.system.onkyo_integration_enabled:
                    await manager.onkyo_bridge.start()

        state_changed = True
        changed_domains.update({"system", "devices", "device_metadata"})

        ch_done, dom_done = AlertManager.process_alert(
            manager._state, reload_alert_complete(alert_scope)
        )
        state_changed |= ch_done
        changed_domains |= dom_done

        # Automatically trigger a system sweep 2 seconds after a full config reload
        if full_recycle:
            manager._timer_manager.schedule("post_reload_sweep", int(time.time()) + 2, "SYSTEM_SWEEP_REQUESTED",
                                            {"reason": "config_reload"})
    except Exception as e:
        ch_fail, dom_fail = AlertManager.process_alert(
            manager._state, reload_alert_failed(alert_scope, str(e))
        )
        state_changed |= ch_fail
        changed_domains |= dom_fail

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
        logger.debug(
            f"[Sweeper] Skipping time-series hardware alignment to respect passive baseline (Uptime: {uptime}s).")
    else:
        if sns.env_schedule_blinds_open_unix and sns.env_schedule_blinds_close_unix:
            if sns.env_schedule_blinds_open_unix <= now < sns.env_schedule_blinds_close_unix:
                manager.dispatch(Event(type=EventType.BLINDS_OPEN_TRIGGER))
            else:
                manager.dispatch(Event(type=EventType.BLINDS_CLOSE_TRIGGER))

        if sns.env_schedule_twilight_morning_on_unix and sns.env_schedule_twilight_morning_off_unix:
            if sns.env_schedule_twilight_morning_on_unix <= now < sns.env_schedule_twilight_morning_off_unix:
                manager.dispatch(Event(type=EventType.MORNING_ON_TRIGGER))
            else:
                manager.dispatch(Event(type=EventType.SUNRISE_TRIGGER))

        if sns.env_schedule_twilight_evening_on_unix and sns.env_schedule_twilight_evening_off_unix:
            if sns.env_schedule_twilight_evening_on_unix <= now < sns.env_schedule_twilight_evening_off_unix:
                manager.dispatch(Event(type=EventType.SUNSET_TRIGGER))
            else:
                manager.dispatch(Event(type=EventType.EVENING_OFF_TRIGGER))

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

