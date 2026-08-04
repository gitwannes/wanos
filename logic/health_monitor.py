# --- file: logic/health_monitor.py ---
from __future__ import annotations

import asyncio
import socket
import os
import time
import psutil
from typing import Any
from core.models import Event, EventType, SystemState
from core.well_known_entities import (
    ENTITY_HOST_CPU_TEMP,
    ENTITY_HOST_CPU_USAGE,
    ENTITY_HOST_DISK_FREE,
    ENTITY_HOST_LOAD_15M,
    ENTITY_HOST_LOAD_1M,
    ENTITY_HOST_LOAD_5M,
    ENTITY_HOST_LOG2RAM_FREE,
    ENTITY_HOST_MEMORY_FREE,
)
from loguru import logger


class HealthMonitor:
    """
    Background worker service that polls physical connection sockets, MQTT clients,
    and external integrations. Emits metrics updates and executes the Auto-Kill Strike protocols.
    """

    def __init__(self, state_manager: Any) -> None:
        self.state_manager = state_manager
        self._task: asyncio.Task | None = None

        # Dedicated Strike Counters for Auto-Kill thresholds
        # Network integrations get 3 strikes (6 seconds) to survive minor TCP blips.
        # USB hardware gets 1 strike (2 seconds) because a missing /dev/tty is immediately fatal.
        self.strikes = {"hue": 0, "epson": 0, "rfxcom": 0, "zwave": 0, "onkyo": 0, "sonos": 0}

        # ⚡ Stateful Hysteresis Tracker for System Telemetry
        # Debounces alerts so the UI isn't spammed every 60 seconds during a persistent load spike.
        self._alert_states = {
            "cpu_temp": "normal",
            "mem_free": "normal",
            "disk_free": "normal",
            "log2ram_free": "normal",
            "load_15m": "normal"
        }

    @staticmethod
    def _get_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def _is_connected(client_mgr: Any) -> bool:
        if client_mgr is not None and hasattr(client_mgr, "is_connected"):
            return client_mgr.is_connected
        return False

    async def _ping_zwave_web(self) -> bool:
        """
        Asynchronously checks if the local Z-Wave JS UI web server (Port 8091) is responsive.
        This serves as the Control Plane verification without needing Docker socket privileges.
        """
        try:
            # Non-blocking TCP ping to 127.0.0.1:8091
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", 8091),
                timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _ping_epson(self) -> bool:
        config = self.state_manager._config
        if not getattr(config, "epson", None) or not config.epson.ip_address:
            return False
        try:
            # Non-blocking TCP ping to check if the projector's network stack is alive
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(config.epson.ip_address, 3629),
                timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _ping_onkyo(self) -> bool:
        config = self.state_manager._config
        if not getattr(config, "onkyo", None) or not config.onkyo.device_map:
            return False

        # If the integration is enabled, DO NOT steal the TCP socket.
        # Just check if the bridge currently holds active connections.
        if self.state_manager._state.system.onkyo_integration_enabled:
            bridge = getattr(self.state_manager, "onkyo_bridge", None)
            if bridge and getattr(bridge, "_running", False):
                if bridge.receivers:
                    return True
                # Grace period: prevent instant "Offline" alert while sockets are handshaking
                import time
                if time.time() - getattr(bridge, "start_time", 0) < 8:
                    return True  # Assume healthy during the 8s boot window
            return False

        # If disabled, safely TCP ping to see if they are online
        for idx, node in config.onkyo.device_map.items():
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(node.ip, 60128), timeout=1.0
                )
                writer.close()
                await writer.wait_closed()
                return True
            except Exception:
                pass
        return False

    async def _ping_sonos(self) -> bool:
        config = self.state_manager._config
        if not getattr(config, "sonos", None) or not config.sonos.device_map:
            return False

        # TCP ping port 1400 (Sonos API). Returns True if AT LEAST ONE speaker answers.
        for idx, node in config.sonos.device_map.items():
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(node.ip, 1400), timeout=1.0
                )
                writer.close()
                await writer.wait_closed()
                return True
            except Exception:
                pass
        return False

    async def _telemetry_loop(self) -> None:
        """Continuous polling loop executing every 2 seconds."""
        while True:
            try:
                await asyncio.sleep(2.0)
                sm = self.state_manager
                sys_state: SystemState = sm.get_state_snapshot()
                config = sm._config  # Dynamically pull config to survive hot-reloads

                wanos_conn = self._is_connected(sm.mqtt_client)
                rfx_conn = self._is_connected(sm.rfxcom_bridge)
                hue_conn = self._is_connected(getattr(sm, "hue_bridge", None))
                epson_conn = await self._ping_epson()
                onkyo_conn = await self._ping_onkyo()
                sonos_conn = await self._ping_sonos()

                # Z-Wave health is a multi-tiered verification matrix:
                # 1. Physical USB stick presence (Tier 1 - Physical)
                zwave_conf = getattr(config, "zwave", None)
                zwave_usb_path = zwave_conf.usb_path if zwave_conf else ""
                zwave_physical = os.path.exists(zwave_usb_path)

                # 2. Control Plane: Z-Wave JS UI Web Server responding on port 8091
                zwave_web = await self._ping_zwave_web()

                # 3. Data Plane: MQTT Engine & Heartbeat Check
                # First, ensure the internal bridge claims MQTT is up
                zwave_engine = getattr(sm.zwave_bridge, "is_mqtt_engine_alive", False)

                # Check for heartbeat staleness (e.g., frozen driver despite a running container)
                now_ts = int(time.time())
                last_hb = sys_state.system.last_zwave_heartbeat_unix

                # Assume data plane is active if we received a heartbeat within the last 90 seconds.
                # If last_hb is None, we haven't received a heartbeat yet since boot.
                zwave_data = zwave_engine and (last_hb is not None and (now_ts - last_hb) <= 90)

                # Combined connection boolean for overall logic flow
                zwave_conn = zwave_physical and zwave_web and zwave_data

                # Update strike tracking based on physical socket availability
                self.strikes["hue"] = 0 if hue_conn else self.strikes["hue"] + 1
                self.strikes["epson"] = 0 if epson_conn else self.strikes["epson"] + 1
                self.strikes["onkyo"] = 0 if onkyo_conn else self.strikes["onkyo"] + 1
                self.strikes["sonos"] = 0 if sonos_conn else self.strikes["sonos"] + 1
                self.strikes["rfxcom"] = 0 if rfx_conn else self.strikes["rfxcom"] + 1

                # Z-Wave USB drop is fatal immediately (1 strike). Web/Data drops get 3 strikes (network blips).
                self.strikes["zwave"] = 0 if zwave_conn else self.strikes["zwave"] + 1

                # Evaluate Auto-Kill thresholds against the live RAM state intent
                if self.strikes["hue"] >= 3 and sys_state.system.hue_integration_enabled:
                    sm.dispatch(Event(type=EventType.HUE_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 Hue Bridge connection lost after 3 retries. Integration disabled."}))

                if self.strikes["epson"] >= 3 and sys_state.system.epson_integration_enabled:
                    sm.dispatch(Event(type=EventType.EPSON_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 Epson Projector connection lost after 3 retries. Integration disabled."}))

                if self.strikes["onkyo"] >= 3 and sys_state.system.onkyo_integration_enabled:
                    sm.dispatch(Event(type=EventType.ONKYO_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 Onkyo connection lost after 3 retries. Integration disabled."}))

                if self.strikes["sonos"] >= 3 and sys_state.system.sonos_integration_enabled:
                    sm.dispatch(Event(type=EventType.SONOS_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 Sonos connection lost after 3 retries. Integration disabled."}))

                if self.strikes["rfxcom"] >= 1 and sys_state.system.rfxcom_integration_enabled:
                    sm.dispatch(Event(type=EventType.RFXCOM_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 USB RFXCOM disconnected. Integration disabled."}))

                # Tiered Z-Wave Auto-Kill Execution
                if (not zwave_physical and self.strikes["zwave"] >= 1) or (self.strikes["zwave"] >= 3):
                    if sys_state.system.zwave_integration_enabled:
                        if not zwave_physical:
                            error_reason = "USB Stick disconnected"
                        elif not zwave_web:
                            error_reason = "Z-Wave JS Web UI Offline"
                        else:
                            error_reason = "Z-Wave Data Stream Frozen"

                        sm.dispatch(Event(type=EventType.ZWAVE_TOGGLED, payload={
                            "enabled": False,
                            "error_msg": f"伯 Z-Wave connection lost ({error_reason}). Integration disabled."}))

                # ⚡ ACTIVE OUT-OF-BAND SAUNA SAFETY WATCHDOG (EN 60335-2-53 Compliance)
                # Operates completely separate from the core event queue loop to intercept frozen process blocks.
                if sys_state.sauna.active:
                    now_ts = int(time.time())

                    # Watchdog Check A: 6-Hour Cumulative Maximum Continuous Running Limit Wall
                    if sys_state.sauna.absolute_cutoff_unix and now_ts > sys_state.sauna.absolute_cutoff_unix:
                        logger.critical(
                            "🚨 EN 60335-2-53 Violation: Sauna exceeded continuous 6-hour limit! Tripping circuit breaker.")
                        sm.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": "🚨 EMERGENCY SHUTDOWN: Absolute 6-hour safety run limit exceeded!",
                            "level": "critical"
                        }))
                        sm.dispatch(Event(type=EventType.SAUNA_OFF, payload={}))

                    # Watchdog Check B: 90-Second Hardware Communication Link Staleness Guard
                    elif sys_state.sauna.last_heartbeat_unix and (
                            now_ts - sys_state.sauna.last_heartbeat_unix) > 90:
                        logger.critical(
                            "🚨 EMERGENCY SHUTDOWN: Sauna SHT11 sensor bus frozen or dropped for >90 seconds! Cutting power.")
                        sm.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": "🚨 EMERGENCY SHUTDOWN: Sauna sensor communication link failure!",
                            "level": "critical"
                        }))
                        sm.dispatch(Event(type=EventType.SAUNA_OFF, payload={}))

                        # Watchdog Check C: Disaggregated Heating Element Health Anomalies
                        # Compares the active phase wattages solved by the RLS regression against the 10% drift threshold
                    p_u = sys_state.metrics.extracted_p_u
                    p_v = sys_state.metrics.extracted_p_v
                    p_w = sys_state.metrics.extracted_p_w

                    if p_u is not None and p_v is not None and p_w is not None:
                        # Baseline power constants defined in structural system spec
                        if p_u < 3150.0 or p_v < 3150.0 or p_w < 1800.0:
                            logger.warning(
                                "⚠️ HARDWARE DEGRADATION: Solving matrices indicate one or more elements have dropped >10% nominal power capacity!")
                            sm.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                                "msg_text": "⚠️ Element Fatigue Detected: Internal regression models indicate phase rating drift.",
                                "level": "warning"
                            }))

                metrics_payload = {
                    "wanos_connected": wanos_conn,
                    "rfxcom_connected": rfx_conn,
                    "hue_connected": hue_conn,
                    "epson_connected": epson_conn,
                    "onkyo_connected": onkyo_conn,
                    "sonos_connected": sonos_conn,
                    "zwave_hardware_connected": zwave_physical,
                    "zwave_web_alive": zwave_web,
                    "zwave_data_alive": zwave_data,
                    "ip_address": self._get_ip()
                }
                sm.dispatch(Event(type=EventType.SYSTEM_METRICS_UPDATED, payload=metrics_payload))

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Silently absorb minor loop crashes to prevent total health engine failure
                print(f"Health Monitor Loop Exception: {e}")

    def _host_idx(self, entity_id: str) -> int | None:
        """Resolve a host-gauge entity_id; None if registry row is missing."""
        return self.state_manager.resolve_entity_id(entity_id)

    def _dispatch_host_gauge(self, entity_id: str, state: str) -> None:
        idx = self._host_idx(entity_id)
        if idx is None:
            return
        self.state_manager.dispatch(Event(
            type=EventType.HUB_STATE_CHANGED,
            payload={"idx": idx, "state": state, "origin": "system"},
        ))

    async def _system_hardware_loop(self) -> None:
        """Isolated 60-second polling loop reading native Linux kernel telemetry via psutil."""
        while True:
            try:
                # 1. CPU Usage
                cpu_perc = psutil.cpu_percent(interval=None)
                self._dispatch_host_gauge(ENTITY_HOST_CPU_USAGE, f"{round(cpu_perc)} %")

                # 2. RAM Free %
                ram_free_perc = 100.0 - psutil.virtual_memory().percent
                self._dispatch_host_gauge(ENTITY_HOST_MEMORY_FREE, f"{round(ram_free_perc)} %")

                # ⚡ Hysteresis Evaluation: RAM Free
                if ram_free_perc <= 5.0 and self._alert_states["mem_free"] != "critical":
                    self._alert_states["mem_free"] = "critical"
                    self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                        "msg_text": "🚨 Host Memory CRITICALLY low (< 5% Free)!", "level": "critical"}))
                elif ram_free_perc <= 10.0 and ram_free_perc > 5.0 and self._alert_states["mem_free"] == "normal":
                    self._alert_states["mem_free"] = "warning"
                    self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                        "msg_text": "⚠️ Host Memory running low (< 10% Free).", "level": "warning"}))
                elif ram_free_perc >= 15.0:
                    self._alert_states["mem_free"] = "normal"

                # 3. Disk Free % (Root)
                disk_free_perc = 100.0 - psutil.disk_usage('/').percent
                self._dispatch_host_gauge(ENTITY_HOST_DISK_FREE, f"{round(disk_free_perc)} %")

                # ⚡ Hysteresis Evaluation: Disk Free
                if disk_free_perc <= 5.0 and self._alert_states["disk_free"] != "critical":
                    self._alert_states["disk_free"] = "critical"
                    self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                        "msg_text": "🚨 Root SD Card CRITICALLY full (< 5% Free)!", "level": "critical"}))
                elif disk_free_perc <= 10.0 and disk_free_perc > 5.0 and self._alert_states[
                    "disk_free"] == "normal":
                    self._alert_states["disk_free"] = "warning"
                    self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                        "msg_text": "⚠️ Root SD Card running out of space (< 10% Free).", "level": "warning"}))
                elif disk_free_perc >= 15.0:
                    self._alert_states["disk_free"] = "normal"

                # 4. Log2Ram Free % (Mounts directly to /var/log)
                try:
                    log2ram_free_perc = 100.0 - psutil.disk_usage('/var/log').percent
                    self._dispatch_host_gauge(ENTITY_HOST_LOG2RAM_FREE, f"{round(log2ram_free_perc)} %")
                    # ⚡ Hysteresis Evaluation: Log2Ram
                    if log2ram_free_perc <= 5.0 and self._alert_states["log2ram_free"] != "critical":
                        self._alert_states["log2ram_free"] = "critical"
                        self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": "🚨 Log2Ram partition CRITICALLY full (< 5% Free)!", "level": "critical"}))
                    elif log2ram_free_perc <= 10.0 and log2ram_free_perc > 5.0 and self._alert_states[
                        "log2ram_free"] == "normal":
                        self._alert_states["log2ram_free"] = "warning"
                        self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": "⚠️ Log2Ram partition filling up (< 10% Free).", "level": "warning"}))
                    elif log2ram_free_perc >= 15.0:
                        self._alert_states["log2ram_free"] = "normal"
                except Exception:
                    pass  # Fail silently if log2ram is completely unmounted

                # 5. Load Averages (1m, 5m, 15m)
                # os.getloadavg() returns a tuple: (1m, 5m, 15m)
                try:
                    load1, load5, load15 = os.getloadavg()
                    # ⚡ The Math Fix: Multiply by 100 BEFORE rounding to correctly calculate percentages based on a 4-core processor
                    self._dispatch_host_gauge(ENTITY_HOST_LOAD_1M, f"{round((load1 / 4) * 100)} %")
                    self._dispatch_host_gauge(ENTITY_HOST_LOAD_5M, f"{round((load5 / 4) * 100)} %")
                    self._dispatch_host_gauge(ENTITY_HOST_LOAD_15M, f"{round((load15 / 4) * 100)} %")

                    # ⚡ Hysteresis Evaluation: 15-Minute Load Average
                    if load15 >= 4.0 and self._alert_states["load_15m"] == "normal":
                        self._alert_states["load_15m"] = "warning"
                        self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": f"⚠️ System CPU chronically overloaded (15m Load: {round(load15, 2)}).",
                            "level": "warning"}))
                    elif load15 <= 3.0:
                        self._alert_states["load_15m"] = "normal"
                except Exception:
                    pass

                # 6. CPU Temperature
                # Reads natively from the Pi's hardware thermal zone without executing a bash shell
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        temp_c = int(f.read()) / 1000.0
                    self._dispatch_host_gauge(ENTITY_HOST_CPU_TEMP, f"{round(temp_c)} °C")

                    # ⚡ Hysteresis Evaluation: CPU Temp
                    if temp_c >= 85.0 and self._alert_states["cpu_temp"] != "critical":
                        self._alert_states["cpu_temp"] = "critical"
                        self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": f"🚨 CPU Hard Thermal Limit ({round(temp_c)} °C)! Device at risk.",
                            "level": "critical"}))
                    elif temp_c >= 80.0 and temp_c < 85.0 and self._alert_states["cpu_temp"] == "normal":
                        self._alert_states["cpu_temp"] = "warning"
                        self.state_manager.dispatch(Event(type=EventType.ALERT_INJECTED, payload={
                            "msg_text": f"⚠️ CPU Soft Thermal Throttle active ({round(temp_c)} °C).",
                            "level": "warning"}))
                    elif temp_c <= 75.0:
                        self._alert_states["cpu_temp"] = "normal"
                except Exception:
                    pass

                # 7. WanOS SQLite footprint (sensor_history + device_history + sauna_sessions)
                try:
                    from logic.history_ids import WANOS_DB_SIZE_IDX, wanos_db_size_mib
                    mib = wanos_db_size_mib()
                    self.state_manager.dispatch(Event(
                        type=EventType.HUB_STATE_CHANGED,
                        payload={
                            "idx": WANOS_DB_SIZE_IDX,
                            "state": f"{mib} MB",
                            "origin": "system",
                        },
                    ))
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Hardware Telemetry Loop Exception: {e}")

            await asyncio.sleep(60.0)

    def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._telemetry_loop())
        # Spin up the isolated hardware loop
        if not hasattr(self, "_hardware_task") or self._hardware_task is None:
            self._hardware_task = asyncio.create_task(self._system_hardware_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if hasattr(self, "_hardware_task") and self._hardware_task:
            self._hardware_task.cancel()
            try:
                await self._hardware_task
            except asyncio.CancelledError:
                pass
            self._hardware_task = None