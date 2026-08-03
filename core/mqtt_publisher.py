# --- file: core/mqtt_publisher.py ---
# WanOS-aware MQTT publishing layer. This is the only file that knows topic names.
# Receives state snapshots and a set of changed domain keys from StateManager,
# then routes each domain to its dedicated topic at the correct cadence.
#
# Separation of concerns:
#   mqtt_transport.py  — raw TCP socket, auth, reconnect. Zero WanOS knowledge.
#   mqtt_publisher.py  — this file. Domain routing. Zero transport knowledge.
import asyncio
import time
import math
import psutil
from typing import Optional, Set, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .mqtt_transport import MqttClientManager
    from .models import SystemState

# How often to send the heartbear (seconds)
HEARTBEAT_INTERVAL = 60


class MqttPublisher:
    """
    Listens for state change notifications from StateManager and publishes
    domain-scoped payloads to the local WanOS broker using an Event-Driven Delta Architecture.
    """

    def __init__(self, mqtt_client: "MqttClientManager") -> None:
        self._client = mqtt_client

        # Application Boot Timestamp for wanos/system
        self._app_boot_unix = int(time.time())
        self._os_boot_unix = int(psutil.boot_time())
        self._system_boot_sent: bool = False

        # Metric threshold trackers
        self._water_cold_liters: float = 0.0
        self._water_hot_liters: float = 0.0
        self._kwh_wh: float = 0.0

        self._last_pub_cold_l: int = 0
        self._last_pub_hot_l: int = 0
        self._last_pub_kwh: float = 0.0

        # Sauna core cache for wanos
        self._sauna_cache: dict[str, Any] = {}
        self._sauna_was_active: bool = False

        self._heartbeat_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Spawns the background 60-second WanOS heartbeat task."""
        self._heartbeat_task = asyncio.create_task(self._wanos_heartbeat_loop())

    def stop(self) -> None:
        """Cancels the background heartbeat loop on shutdown."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    def accumulate_water(self, fluid: str, count: int) -> None:
        """
        Called synchronously by StateManager for each WATER_PULSE event.
        Accumulates raw counts and triggers a payload only when a 1L threshold is crossed.
        """
        liters = count / 396.0
        if fluid == "cold":
            self._water_cold_liters += liters
            current_l = int(math.floor(self._water_cold_liters))
            if current_l > self._last_pub_cold_l:
                self._last_pub_cold_l = current_l
                asyncio.create_task(self._client.publish("wanos/metrics/pulses", {"total_cold_liters": current_l}))
        else:
            self._water_hot_liters += liters
            current_l = int(math.floor(self._water_hot_liters))
            if current_l > self._last_pub_hot_l:
                self._last_pub_hot_l = current_l
                asyncio.create_task(self._client.publish("wanos/metrics/pulses", {"total_hot_liters": current_l}))

    def accumulate_kwh(self, ticks: int = 1) -> None:
        """
        Called synchronously by StateManager for each KWH_PULSE event.
        Triggers a payload only when a 0.1 kWh (100 Wh) threshold is crossed.
        """
        self._kwh_wh += ticks
        kwh = self._kwh_wh / 1000.0
        # Floor to nearest 0.1
        current_kwh_step = math.floor(kwh * 10) / 10.0

        if current_kwh_step > self._last_pub_kwh:
            self._last_pub_kwh = current_kwh_step
            asyncio.create_task(self._client.publish("wanos/metrics/pulses", {"total_kwh": current_kwh_step}))

    async def on_state_changed(self, snapshot: "SystemState", changed_domains: Set[str]) -> None:
        """
        State listener callback. Receives the post-drain snapshot and the set of
        domain keys that changed during the last event batch.
        """
        if "system" in changed_domains:
            await self._publish_telemetry(snapshot)

        if "sauna" in changed_domains:
            await self._publish_sauna(snapshot)

    async def _wanos_heartbeat_loop(self) -> None:
        """Fires the WanOS broker 'alive' heartbeat every 60 seconds."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self._client.publish("wanos/system", {"wanos_mqtt_connected": True})
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ Heartbeat error: {e}")

    async def _publish_telemetry(self, snapshot: "SystemState") -> None:
        """Publishes boot UNIX stamps once on wanos/system."""
        if not self._system_boot_sent and snapshot.system.ip_address != "0.0.0.0":
            await self._client.publish("wanos/system", {
                "app_boot_unix": self._app_boot_unix,
                "os_boot_unix": self._os_boot_unix,
                "ip_address": snapshot.system.ip_address
            })
            self._system_boot_sent = True

    async def _publish_sauna(self, snapshot: "SystemState") -> None:
        """
        Publishes sauna control math. Strips environmental sensors/vents.
        Fires a full baseline upon boot, then ONLY keys that change (deltas).
        """
        s = snapshot.sauna

        # Baseline dictionary mapping
        current_state = {
            "active": s.active,
            "setpoint_temp": s.target_temp,
            "modulation_pwm": s.modulation_pwm,
            "phases_pwm": s.phases_pwm,
            "fireorder": s.fireorder
        }

        if s.active and not self._sauna_was_active:
            # Sauna just turned ON: Send full baseline snapshot
            await self._client.publish("wanos", current_state)
            self._sauna_cache = current_state
        elif s.active:
            # Sauna is running: Send only modified keys
            deltas = {}
            for k, v in current_state.items():
                if self._sauna_cache.get(k) != v:
                    deltas[k] = v
                    self._sauna_cache[k] = v
            if deltas:
                await self._client.publish("wanos", deltas)

        self._sauna_was_active = s.active
