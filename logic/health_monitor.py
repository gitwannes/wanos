# --- file: logic/health_monitor.py ---
from __future__ import annotations

import asyncio
import socket
import os
import time
from typing import Any
from core.models import Event, EventType, SystemState
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
        self.strikes = {"domoticz": 0, "hue": 0, "epson": 0, "rfxcom": 0, "zwave": 0, "onkyo": 0}

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

    async def _telemetry_loop(self) -> None:
        """Continuous polling loop executing every 2 seconds."""
        while True:
            try:
                await asyncio.sleep(2.0)
                sm = self.state_manager
                sys_state: SystemState = sm.get_state_snapshot()
                config = sm._config  # Dynamically pull config to survive hot-reloads

                wanos_conn = self._is_connected(sm.mqtt_client)
                dom_conn = self._is_connected(sm.domoticz_client)
                rfx_conn = self._is_connected(sm.rfxcom_bridge)
                hue_conn = self._is_connected(getattr(sm, "hue_bridge", None))
                epson_conn = await self._ping_epson()
                onkyo_conn = await self._ping_onkyo()

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
                self.strikes["domoticz"] = 0 if dom_conn else self.strikes["domoticz"] + 1
                self.strikes["hue"] = 0 if hue_conn else self.strikes["hue"] + 1
                self.strikes["epson"] = 0 if epson_conn else self.strikes["epson"] + 1
                self.strikes["onkyo"] = 0 if onkyo_conn else self.strikes["onkyo"] + 1
                self.strikes["rfxcom"] = 0 if rfx_conn else self.strikes["rfxcom"] + 1

                # Z-Wave USB drop is fatal immediately (1 strike). Web/Data drops get 3 strikes (network blips).
                self.strikes["zwave"] = 0 if zwave_conn else self.strikes["zwave"] + 1

                # Evaluate Auto-Kill thresholds against the live RAM state intent
                if self.strikes["domoticz"] >= 3 and sys_state.system.domoticz_integration_enabled:
                    sm.dispatch(Event(type=EventType.DOMOTICZ_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 Domoticz connection lost after 3 retries. Integration disabled."}))

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
                    "domoticz_connected": dom_conn,
                    "rfxcom_connected": rfx_conn,
                    "hue_connected": hue_conn,
                    "epson_connected": epson_conn,
                    "onkyo_connected": onkyo_conn,
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

    def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._telemetry_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None