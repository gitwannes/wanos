# --- file: logic/health_monitor.py ---
import asyncio
import socket
from typing import Any
from core.models import Event, EventType, SystemState


class HealthMonitor:
    """
    Background worker service that polls physical connection sockets, MQTT clients,
    and external integrations. Emits metrics updates and executes the Auto-Kill Strike protocols.
    """

    def __init__(self, state_manager: Any) -> None:
        self.state_manager = state_manager
        self.config = state_manager._config
        self._task: asyncio.Task | None = None

        # Dedicated Strike Counters for Auto-Kill thresholds
        # Network integrations get 3 strikes (6 seconds) to survive minor TCP blips.
        # USB hardware gets 1 strike (2 seconds) because a missing /dev/tty is immediately fatal.
        self.strikes = {"domoticz": 0, "hue": 0, "epson": 0, "rfxcom": 0, "zwave": 0}

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

    async def _ping_epson(self) -> bool:
        if not getattr(self.config, "epson", None) or not self.config.epson.ip_address:
            return False
        try:
            # Non-blocking TCP ping to check if the projector's network stack is alive
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.epson.ip_address, 3629),
                timeout=1.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _telemetry_loop(self) -> None:
        """Continuous polling loop executing every 2 seconds."""
        while True:
            try:
                await asyncio.sleep(2.0)
                sm = self.state_manager
                sys_state: SystemState = sm.get_state_snapshot()

                wanos_conn = self._is_connected(sm.mqtt_client)
                dom_conn = self._is_connected(sm.domoticz_client)
                rfx_conn = self._is_connected(sm.rfxcom_bridge)
                hue_conn = self._is_connected(getattr(sm, "hue_bridge", None))
                epson_conn = await self._ping_epson()

                # Z-Wave physical health is tracked explicitly by the Z-Wave JS UI Bridge.
                zwave_conn = getattr(sm.zwave_bridge, "is_physically_connected", False)

                # Update strike tracking based on physical socket availability
                self.strikes["domoticz"] = 0 if dom_conn else self.strikes["domoticz"] + 1
                self.strikes["hue"] = 0 if hue_conn else self.strikes["hue"] + 1
                self.strikes["epson"] = 0 if epson_conn else self.strikes["epson"] + 1
                self.strikes["rfxcom"] = 0 if rfx_conn else self.strikes["rfxcom"] + 1
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

                if self.strikes["rfxcom"] >= 1 and sys_state.system.rfxcom_integration_enabled:
                    sm.dispatch(Event(type=EventType.RFXCOM_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 USB RFXCOM disconnected. Integration disabled."}))

                if self.strikes["zwave"] >= 3 and sys_state.system.zwave_integration_enabled:
                    sm.dispatch(Event(type=EventType.ZWAVE_TOGGLED, payload={
                        "enabled": False,
                        "error_msg": "🔌 Z-Wave MQTT connection lost. Integration disabled."}))

                metrics_payload = {
                    "wanos_connected": wanos_conn,
                    "domoticz_connected": dom_conn,
                    "rfxcom_connected": rfx_conn,
                    "hue_connected": hue_conn,
                    "epson_connected": epson_conn,
                    "zwave_connected": zwave_conn,
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