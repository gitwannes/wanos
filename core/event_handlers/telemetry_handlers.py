# --- file: core/event_handlers/telemetry_handlers.py ---
from typing import Any, Set, Tuple
from core.models import Event, EventType
from logic.alert_manager import AlertManager
from logic.environment_scheduler import EnvironmentScheduler
from logic.sauna_controller import SaunaController


async def handle_power_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx: int = payload.get("idx")
    raw_val: float = payload.get("value", 0.0)
    sns: Any = manager._state.sensors
    moving_avg = 10

    if idx not in manager._sensor_history:
        manager._sensor_history[idx] = []

    history = manager._sensor_history[idx]

    if raw_val == 0.0:
        # Flush the math buffer so the moving average drops to zero instantly
        history.clear()
        history.append(0.0)
    else:
        history.append(raw_val)
        if len(history) > moving_avg:
            history.pop(0)

    # Compute smoothed moving average aggregate
    avg_val = round(sum(history) / len(history), 1)

    # GENERIC CATCH-ALL: Universally store ALL power sensors in the generic registry
    if manager._state.devices.get(idx) != avg_val:
        manager._state.devices[idx] = avg_val
        state_changed = True
        changed_domains.add("devices")

    # Route explicitly mapped core IDXs to their semantic SensorsState variables
    if idx == 9:
        if avg_val == 0.0:
            sns.pc_power_history = [0.0] * moving_avg
        elif len(sns.pc_power_history) == 0:
            sns.pc_power_history = [avg_val] * moving_avg
        else:
            sns.pc_power_history.append(avg_val)
            if len(sns.pc_power_history) > moving_avg:
                sns.pc_power_history.pop(0)

        if sns.pc_power != avg_val:
            sns.pc_power = avg_val
            state_changed = True
            changed_domains.add("sensors")

    elif idx == 9622:
        if avg_val == 0.0:
            sns.pc_aux_power_history = [0.0] * moving_avg
        elif len(sns.pc_aux_power_history) == 0:
            sns.pc_aux_power_history = [avg_val] * moving_avg
        else:
            sns.pc_aux_power_history.append(avg_val)
            if len(sns.pc_aux_power_history) > moving_avg:
                sns.pc_aux_power_history.pop(0)

        if sns.pc_aux_power != avg_val:
            sns.pc_aux_power = avg_val
            state_changed = True
            changed_domains.add("sensors")

    return state_changed, changed_domains


async def handle_external_weather_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    manager._state.sensors.sunrise_unix = payload.get("sunrise")
    manager._state.sensors.sunset_unix = payload.get("sunset")

    # Trigger recalculation instantly when weather cycles shift
    EnvironmentScheduler.recalculate_schedule(manager._state, manager._config, manager._start_time, manager.dispatch)

    return True, {"sensors"}


async def handle_system_metrics_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}

    # ⚡ Trap the custom insights trigger to push debounced historical data up the SSE stream
    if payload.get("insights_trigger", False):
        return True, {"metrics"}

    state_changed = False
    changed_domains = set()

    wanos_conn = payload.get("wanos_connected", False)
    dom_conn = payload.get("domoticz_connected", False)
    rfx_conn = payload.get("rfxcom_connected", False)
    hue_conn = payload.get("hue_connected", False)
    epson_conn = payload.get("epson_connected", False)
    onkyo_conn = payload.get("onkyo_connected", False)
    zwave_hardware_conn = payload.get("zwave_hardware_connected", False)
    zwave_web_alive = payload.get("zwave_web_alive", False)
    zwave_data_alive = payload.get("zwave_data_alive", False)

    ip_addr = payload.get("ip_address", "0.0.0.0")

    prev_wanos = manager._state.system.wanos_mqtt_connected
    prev_dom = manager._state.system.domoticz_mqtt_connected
    prev_rfx = manager._state.system.rfxcom_connected
    prev_hue = manager._state.system.hue_connected
    prev_epson = manager._state.system.epson_connected
    prev_onkyo = manager._state.system.onkyo_connected
    prev_zwave_hw = manager._state.system.zwave_hardware_connected
    prev_zwave_web = manager._state.system.zwave_web_alive
    prev_zwave_data = manager._state.system.zwave_data_alive

    # --- UI CONNECTION TRANSITION ALERTS & RECOVERY ---

    # --- UI CONNECTION TRANSITION ALERTS & RECOVERY ---
    if prev_wanos and not wanos_conn:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Local MQTT Broker offline")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_wanos and wanos_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Local MQTT Broker back online")
        state_changed |= ch
        changed_domains |= dom

    if prev_dom and not dom_conn:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Domoticz MQTT Broker Connection down")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_dom and dom_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Domoticz MQTT Broker Connection back online")
        state_changed |= ch
        changed_domains |= dom
        if not manager._state.system.domoticz_integration_enabled:
            manager.dispatch(
                Event(type=EventType.DOMOTICZ_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

    if prev_rfx and not rfx_conn:
        ch, dom = AlertManager.process_alert(manager._state,
                                             "🔴 CRITICAL: Native RFXCOM USB Transceiver offline or disconnected")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_rfx and rfx_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Native RFXCOM USB Transceiver mounted")
        state_changed |= ch
        changed_domains |= dom
        if not manager._state.system.rfxcom_integration_enabled:
            manager.dispatch(Event(type=EventType.RFXCOM_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

    if prev_hue and not hue_conn:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Local Hue Bridge connection lost")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_hue and hue_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Local Hue Bridge connected via API v2")
        state_changed |= ch
        changed_domains |= dom
        if not manager._state.system.hue_integration_enabled:
            manager.dispatch(Event(type=EventType.HUE_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

    if prev_epson and not epson_conn:
        ch, dom = AlertManager.process_alert(manager._state,
                                             "🔴 CRITICAL: Epson Projector TCP connection lost (Unplugged?)")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_epson and epson_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Epson Projector TCP socket responding")
        state_changed |= ch
        changed_domains |= dom
        if not manager._state.system.epson_integration_enabled:
            manager.dispatch(Event(type=EventType.EPSON_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

    if prev_onkyo and not onkyo_conn:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Onkyo Receivers unreachable")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_onkyo and onkyo_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Onkyo Receivers online")
        state_changed |= ch
        changed_domains |= dom
        if not manager._state.system.onkyo_integration_enabled:
            manager.dispatch(Event(type=EventType.ONKYO_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

    if prev_zwave_hw and not zwave_hardware_conn:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Z-Wave USB Stick unplugged from the Pi!")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_zwave_hw and zwave_hardware_conn and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Z-Wave USB Stick mounted")
        state_changed |= ch
        changed_domains |= dom

    if prev_zwave_web and not zwave_web_alive:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Z-Wave JS Web Panel (8091) unreachable")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_zwave_web and zwave_web_alive and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Z-Wave JS Web Panel (8091) online")
        state_changed |= ch
        changed_domains |= dom

    if prev_zwave_data and not zwave_data_alive:
        ch, dom = AlertManager.process_alert(manager._state, "🔴 CRITICAL: Z-Wave MQTT Data stream frozen")
        state_changed |= ch
        changed_domains |= dom
    elif not prev_zwave_data and zwave_data_alive and manager._state.system.app_boot_unix is not None:
        ch, dom = AlertManager.process_alert(manager._state, "🟢 SUCCESS: Z-Wave MQTT Data stream active")
        state_changed |= ch
        changed_domains |= dom

        # Auto-Recovery only fires if ALL tiers are fully restored
    if (not prev_zwave_web or not prev_zwave_data) and (
            zwave_web_alive and zwave_data_alive) and manager._state.system.app_boot_unix is not None:
        if not manager._state.system.zwave_integration_enabled and zwave_hardware_conn:
            manager.dispatch(Event(type=EventType.ZWAVE_TOGGLED, payload={"enabled": True, "is_auto_recovery": True}))

        # GATEWAY FAILSAFE: Only trigger updates if real mutations occurred or boot variables are blank!
    if (prev_wanos != wanos_conn or
            prev_dom != dom_conn or
            prev_rfx != rfx_conn or
            prev_hue != hue_conn or
            prev_epson != epson_conn or
            prev_onkyo != onkyo_conn or
            prev_zwave_hw != zwave_hardware_conn or
            prev_zwave_web != zwave_web_alive or
            prev_zwave_data != zwave_data_alive or
            manager._state.system.ip_address != ip_addr or
            manager._state.system.app_boot_unix is None):
        manager._state.system.wanos_mqtt_connected = wanos_conn
        manager._state.system.domoticz_mqtt_connected = dom_conn
        manager._state.system.rfxcom_connected = rfx_conn
        manager._state.system.hue_connected = hue_conn
        manager._state.system.epson_connected = epson_conn
        manager._state.system.onkyo_connected = onkyo_conn
        manager._state.system.zwave_hardware_connected = zwave_hardware_conn
        manager._state.system.zwave_web_alive = zwave_web_alive
        manager._state.system.zwave_data_alive = zwave_data_alive
        manager._state.system.ip_address = ip_addr

        # Capture static Unix boot times once during host identification
        if manager._state.system.app_boot_unix is None and ip_addr != "0.0.0.0":
            import psutil
            manager._state.system.app_boot_unix = int(manager._start_time)
            manager._state.system.os_boot_unix = int(psutil.boot_time())

        state_changed = True
        changed_domains.add("system")

    return state_changed, changed_domains


async def handle_temp_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx: int = payload.get("idx")
    val: float = payload.get("value", 0.0)
    sns: Any = manager._state.sensors
    is_manual_lab_action = payload.get("lab_override", False)

    # GENERIC CATCH-ALL
    current = manager._state.devices.get(idx)
    if not isinstance(current, dict):
        current = {}
    if current.get("temp") != val:
        current["temp"] = val
        manager._state.devices[idx] = current
        state_changed = True
        changed_domains.add("devices")

    # --- CORE ENGINE TARGET ROUTING ---
    if idx == 30001:
        if sns.outside_temp != val:
            sns.outside_temp = val
            state_changed = True
            changed_domains.add("sensors")

        if current.get("temp") != val:
            current["temp"] = val
            manager._state.devices[idx] = current
            state_changed = True
            changed_domains.add("devices")

    return state_changed, changed_domains


async def handle_humidity_updated(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    state_changed = False
    changed_domains = set()

    idx: int = payload.get("idx")
    val: int = payload.get("value", 0)
    sns: Any = manager._state.sensors
    is_manual_lab_action = payload.get("lab_override", False)

    current = manager._state.devices.get(idx)
    if not isinstance(current, dict):
        current = {}
    if current.get("hum") != val:
        current["hum"] = val
        manager._state.devices[idx] = current
        state_changed = True
        changed_domains.add("devices")

    # --- CORE ENGINE TARGET ROUTING ---
    if idx == 30001:
        if sns.outside_hum != val:
            sns.outside_hum = val
            state_changed = True
            changed_domains.add("sensors")

        if current.get("hum") != val:
            current["hum"] = val
            manager._state.devices[idx] = current
            state_changed = True
            changed_domains.add("devices")

    return state_changed, changed_domains


async def handle_water_pulse(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    idx = payload.get("idx")
    count = payload.get("count", 1)

    state_changed = False
    changed_domains = set()

    if idx is not None:
        # 1. Fetch current liters from the universal device registry
        current_liters = manager._state.devices.get(idx)
        if not isinstance(current_liters, (float, int)):
            current_liters = 0.0

        # 2. Convert raw hardware pulses to physical units (396 pulses = 1 liter)
        added_liters = count / 396.0
        manager._state.devices[idx] = round(current_liters + added_liters, 3)

        state_changed = True
        changed_domains.add("devices")

        # 3. Maintain legacy Douche logic (Adding pulse ticks to the active session)
        if manager._state.metrics.douche_active:
            manager._state.metrics.douche_water_liters += count
            changed_domains.add("metrics")

        # 4. Forward to MQTT Publisher (Mapping IDX back to fluid type for legacy topics)
        if manager.mqtt_publisher:
            wtype = "cold" if idx == 11002 else "hot"
            manager.mqtt_publisher.accumulate_water(wtype, count)

    return state_changed, changed_domains


async def handle_kwh_pulse(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    payload = event.payload or {}
    idx = payload.get("idx")

    state_changed = False
    changed_domains = set()

    if idx is not None:
        # 1. Fetch current accumulated Watt-hours
        current_wh = manager._state.devices.get(idx)
        if not isinstance(current_wh, (float, int)):
            current_wh = 0.0

        # 2. Add raw pulse (1 pulse = 1 Wh)
        manager._state.devices[idx] = current_wh + 1.0

        state_changed = True
        changed_domains.add("devices")

    # 3. Maintain legacy Kiosk/UI metrics
    manager._state.metrics.kwh_wh_ticks += 1
    changed_domains.add("metrics")

    if manager.mqtt_publisher:
        manager.mqtt_publisher.accumulate_kwh(1)

    return state_changed, changed_domains

async def handle_nvram_flush_trigger(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    """
    Periodic 5-minute heartbeat to flush active 11xxx counters to physical storage.
    """
    import time

    # Extract only the targeted cumulative metric counters (11000 - 11999)
    nvm_payload = {
        k: v for k, v in manager._state.devices.items()
        if isinstance(k, int) and 11000 <= k < 12000
    }

    # Execute the Atomic Swap disk I/O
    manager.nvm.flush(nvm_payload)

    # Reschedule the next heartbeat
    manager._timer_manager.schedule(
        "nvram_flush",
        int(time.time()) + 300,  # every 5 minutes: check if flushing is needed
        EventType.NVRAM_FLUSH_TRIGGER.value
    )

    # Disk I/O does not mutate reactive UI state, so we stay completely silent
    return False, set()