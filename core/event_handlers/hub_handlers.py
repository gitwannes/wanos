# --- file: core/event_handlers/hub_handlers.py ---
import time
import asyncio
from typing import Any, Set, Tuple, Optional
from core.models import Event, EventType
from core.well_known_entities import ENTITY_SAUNA_DOOR
from logic.alert_manager import AlertManager
from logic.history_manager import normalize_level, level_max_for_idx

# 1. Standard System Logger: Handles general INFO, DEBUG, and ERROR terminal outputs and system health
from loguru import logger as system_logger
# 2. Automation Logger: Dedicated stream for tracing background logic engine decisions
from core.logger import automation_logger
# 3. IWHW Ledger: "Ik Wil Het Weten" - Dedicated behavioral audit trail for physical state transitions
from core.logger import iwhw_logger

_shutter_debounce_tasks = {}


def _log_actuator(manager: Any, idx: int, state: Any, device_snapshot: Any = None,
                  bri: Any = None, volume: Any = None, level: Optional[float] = None) -> None:
    """Persist actuator transition with normalized chart level (speakers use max_volume)."""
    if not hasattr(manager, "history_manager"):
        return
    if level is None:
        level = normalize_level(
            state, device_snapshot, bri=bri, volume=volume,
            level_max=level_max_for_idx(manager, idx),
        )
    manager.history_manager.log_event(
        idx, str(state) if state is not None else "", level,
        device_snapshot=device_snapshot, bri=bri, volume=volume,
    )


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

        if hasattr(manager, "history_manager"):
            _log_actuator(manager, idx, new_state)
            changed_domains.add("metrics")

        # Sauna safety interlock logic evaluation
        door_idx = manager.resolve_entity_id(ENTITY_SAUNA_DOOR)
        if door_idx is not None and idx == door_idx and is_open and manager._state.sauna.active:
            manager._state.sauna.active = False
            manager._state.sauna.modulation_pwm = 0
            manager._state.sauna.phases_pwm = [0, 0, 0]
            manager._state.sauna.ventilation_state = "OFF"
            changed_domains.add("sauna")
            asyncio.create_task(system_logger.warning("🚪 Sauna door opened while active! Emergency cutoff triggered."))

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

    # Hybrid Learning: Cache semantic names from inbound payloads into device_metadata
    device_name_payload = payload.get("name")
    if device_name_payload:
        meta = manager._state.device_metadata.get(idx)
        if not isinstance(meta, dict):
            manager._state.device_metadata[idx] = {
                "name": device_name_payload, "type": payload.get("device_type") or "unknown",
                "origin": payload.get("origin") or "system",
            }
            state_changed = True
            changed_domains.add("device_metadata")
            if not is_init:
                system.logger.info(f"Name for {idx} seeded into device_metadata: {device_name_payload}.")
        elif not meta.get("name"):
            meta["name"] = device_name_payload
            state_changed = True
            changed_domains.add("device_metadata")
            if not is_init:
                system.logger.info(f"Name for {idx} added to device_metadata: {device_name_payload}.")

    is_push_button = payload.get("is_push_button", False)
    is_force = payload.get("force", False)

    # Origin force policy (matches AutomationEngine):
    # RFX always; Sonos / Onkyo / Epson on OFF only.
    meta_origin: str = manager._state.device_metadata.get(idx, {}).get("origin", "")
    if not is_force and meta_origin == "rfxcom":
        is_force = True
        payload["force"] = True
    elif (
        not is_force
        and meta_origin in ("sonos", "onkyo", "epson")
        and str(state_val).upper() == "OFF"
    ):
        is_force = True
        payload["force"] = True

    # Host / mains gauge history (22002–22006/22009, 71046).
    # Sample on every poll tick — not only when the rounded string changes —
    # otherwise disk/log2ram/mains sit flat for hours with empty graphs.
    if not is_init and hasattr(manager, "sensor_history"):
        from logic.history_ids import HOST_HISTORY_IDXS, parse_numeric_state
        if idx in HOST_HISTORY_IDXS:
            num = parse_numeric_state(state_val if state_val is not None else new_val)
            if num is not None:
                manager.sensor_history.note_gauge(idx, num)

    if old_val != new_val or is_push_button or is_force:
        manager._state.devices[idx] = new_val
        state_changed = True
        changed_domains.add("devices")

        # --- ⚡ DEVICE INSIGHTS HISTORY LOGGING ---
        if not is_init and hasattr(manager, "history_manager"):
            device_meta = manager._state.device_metadata.get(idx, {})
            dev_type = device_meta.get("type", "")

            # Explicitly include hardware doors as binary switches, ignore other passive sensors
            if manager.history_manager.should_track(idx, dev_type):
                is_analog = dev_type in ["blinds", "shutter"] or isinstance(state_val, (int, float))

                old_log_state = old_val.get("state") if isinstance(old_val, dict) else old_val
                old_vol = old_val.get("volume") if isinstance(old_val, dict) else None
                old_bri = old_val.get("bri") if isinstance(old_val, dict) else None
                new_vol = new_val.get("volume") if isinstance(new_val, dict) else payload.get("volume")
                new_bri = new_val.get("bri") if isinstance(new_val, dict) else payload.get("bri")

                power_changed = old_log_state != state_val or is_push_button
                level_changed = (new_vol is not None and new_vol != old_vol) or (
                    new_bri is not None and new_bri != old_bri
                )

                if power_changed or level_changed:
                    if is_analog and power_changed:
                        if dev_type in ["blinds", "shutter"]:
                            def get_shutter_val(v) -> Optional[int]:
                                if v == "OPEN": return 0
                                if v == "CLOSED": return 100
                                if isinstance(v, str) and "%" in v: return int(v.replace("%", ""))
                                try:
                                    return int(v)
                                except (ValueError, TypeError):
                                    return None

                            def format_blind(v: int) -> str:
                                if v == 100: return "CLOSED"
                                if v == 0: return "OPEN"
                                return f"{v}%"

                            new_int = get_shutter_val(state_val)
                            old_int = get_shutter_val(old_log_state) if old_log_state is not None else 100

                            if new_int is not None:
                                # Resolve Origin Payload for IWHW
                                raw_origin = payload.get("origin")
                                if not raw_origin:
                                    raw_origin = "SYSTEM" if is_init else "MANUAL"
                                origin_tag = str(raw_origin).upper()[:10]

                                active_job = _shutter_debounce_tasks.get(idx)

                                # Early Release Check: Did the Z-Wave mesh report reaching our target before the timer expired?
                                if active_job and active_job.get("target") == new_int:
                                    active_job["task"].cancel()
                                    del _shutter_debounce_tasks[idx]

                                    _log_actuator(manager, idx, state_val, level=float(new_int))

                                    # Log to IWHW Terminal
                                    name = device_meta.get("name", f"idx_{idx}")
                                    idx_str = str(idx)[:5]
                                    new_bin_str = format_blind(new_int)[:10]
                                    iwhw_logger.info(
                                        f"{'SHUTTER':<10} | {origin_tag:<10} | {new_bin_str:<10} | {idx_str:<5} | {name}")

                                    manager.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED,
                                                           payload={"insights_trigger": True}))
                                else:
                                    # Calculate dynamic proportional delay based on specific travel limits
                                    delta = abs((old_int if old_int is not None else 100) - new_int)

                                    blinds_cfg = getattr(manager._config, "blinds", None)
                                    if blinds_cfg and hasattr(blinds_cfg, "travel_times"):
                                        blind_eid = device_meta.get("entity_id") if isinstance(device_meta, dict) else None
                                        default_tt = getattr(blinds_cfg, "default_travel_time_secs", 35)
                                        base_time = (
                                            blinds_cfg.travel_times.get(blind_eid, default_tt)
                                            if blind_eid else default_tt
                                        )
                                    else:
                                        base_time = 35  # Failsafe

                                    # Proportional time + 10% safety margin dead-reckoning
                                    delay_seconds = int(round((delta / 100.0) * base_time * 1.10))
                                    delay_seconds = max(1, delay_seconds)

                                    # Emit detailed diagnostic log to system debug log stream (/var/log/wanos/wanos_debug.log)
                                    shutter_name: str = device_meta.get("name", f"idx_{idx}")
                                    system_logger.debug(
                                        f"Shutter [{idx} | {shutter_name}] debounce scheduled: {delay_seconds}s (max: {base_time}s) | "
                                        f"moving from {old_int}% to {new_int}% (Δ{delta}%)"
                                    )

                                    if active_job:
                                        active_job["task"].cancel()

                                    async def proportional_debounced_log(target_idx: int, val: Any, delay: int,
                                                                         origin: str, target_int: int):
                                        try:
                                            await asyncio.sleep(delay)
                                            _log_actuator(manager, target_idx, val, level=float(target_int))

                                            # Log to IWHW
                                            meta = manager._state.device_metadata.get(target_idx, {})
                                            name = meta.get("name", f"idx_{target_idx}")
                                            idx_str = str(target_idx)[:5]
                                            new_bin_str = format_blind(target_int)[:10]
                                            iwhw_logger.info(
                                                f"{'SHUTTER':<10} | {origin:<10} | {new_bin_str:<10} | {idx_str:<5} | {name}")

                                            manager.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED,
                                                                   payload={"insights_trigger": True}))
                                        except asyncio.CancelledError:
                                            pass
                                        finally:
                                            # Clean up the dictionary if this exact task is the one finishing
                                            if target_idx in _shutter_debounce_tasks and _shutter_debounce_tasks[
                                                target_idx].get("target") == target_int:
                                                del _shutter_debounce_tasks[target_idx]

                                    new_task = asyncio.create_task(
                                        proportional_debounced_log(idx, state_val, delay_seconds, origin_tag, new_int))
                                    _shutter_debounce_tasks[idx] = {"task": new_task, "target": new_int,
                                                                    "origin": origin_tag}
                        else:
                            # Standard 30s Debounce for other generic analog sensors (e.g. Generic Dimmers without travel time logic)
                            if idx in _shutter_debounce_tasks:
                                _shutter_debounce_tasks[idx]["task"].cancel()

                            async def generic_debounced_log(target_idx, val):
                                try:
                                    await asyncio.sleep(30.0)
                                    _log_actuator(manager, target_idx, val)
                                    manager.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED,
                                                           payload={"insights_trigger": True}))
                                except asyncio.CancelledError:
                                    pass

                            task = asyncio.create_task(generic_debounced_log(idx, state_val))
                            _shutter_debounce_tasks[idx] = {"task": task, "target": state_val}
                    else:
                        # Binary switches + rich level (volume/bri) — immediate commit
                        snap = new_val if isinstance(new_val, dict) else None
                        log_state = state_val if state_val is not None else (
                            snap.get("state") if snap else old_log_state
                        )
                        _log_actuator(
                            manager, idx, log_state, device_snapshot=snap,
                            bri=new_bri, volume=new_vol,
                        )
                        changed_domains.add("metrics")

        # Bathroom 1e ventilator timer lock
        from core.well_known_entities import ENTITY_BATHROOM_VENT, ENTITY_EPSON

        vent_idx = None
        for k, meta in (manager._state.device_metadata or {}).items():
            if isinstance(meta, dict) and meta.get("entity_id") == ENTITY_BATHROOM_VENT:
                try:
                    vent_idx = int(k)
                except (TypeError, ValueError):
                    vent_idx = None
                break
        if vent_idx is not None and idx == vent_idx and state_val == "ON" and old_val != "ON":
            manager._state.devices[90001] = True
            deadline = int(time.time()) + (manager._config.bathroom1.vent_min_runtime_mins * 60)
            manager._timer_manager.schedule("bath1_vent_lock", deadline, "BATH1_VENT_LOCK_EXPIRED")

        # EPSON INTERCEPTOR
        epson_idx = None
        for k, meta in (manager._state.device_metadata or {}).items():
            if isinstance(meta, dict) and meta.get("entity_id") == ENTITY_EPSON:
                try:
                    epson_idx = int(k)
                except (TypeError, ValueError):
                    epson_idx = None
                break
        if epson_idx is not None and idx == epson_idx and (old_val != state_val or is_force):
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
        # Outbound only: ignore bridge confirmations (origin=sonos) and poll syncs
        # (is_initialization). Compare the binary power state inside rich dicts —
        # never dict vs plain string, which always looks like a change and re-fires play().
        meta_origin = manager._state.device_metadata.get(idx, {}).get("origin", "")
        old_state = old_val.get("state") if isinstance(old_val, dict) else old_val
        event_origin = payload.get("origin")
        if (meta_origin == "sonos"
                and event_origin != "sonos"
                and not is_init
                and (old_state != state_val or is_force)):
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

        # ONKYO INTERCEPTOR
        if meta_origin == "onkyo" and (old_val != state_val or is_force or "volume" in payload):
            if manager._state.system.onkyo_integration_enabled:
                if getattr(manager, "onkyo_bridge", None):
                    asyncio.create_task(manager.onkyo_bridge.execute_command(payload))
                else:
                    automation_logger.error(
                        "Tried to trigger Onkyo Receiver, but bridge is offline or misconfigured.")
            else:
                automation_logger.warning("Onkyo command dropped: Integration is disabled in UI.")
                ch, dom = AlertManager.process_alert(manager._state,
                                                     "🔴 Onkyo command dropped: Integration is disabled.")
                state_changed |= ch
                changed_domains |= dom

    return state_changed, changed_domains
