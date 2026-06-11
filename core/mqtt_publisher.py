# --- file: core/mqtt_publisher.py ---
# WanOS-aware MQTT publishing layer. This is the only file that knows topic names.
# Receives state snapshots and a set of changed domain keys from StateManager,
# then routes each domain to its dedicated topic at the correct cadence.
#
# Topic schema (all outbound, local broker only):
#   wisc/system/telemetry    — OS/app uptime, IP, connection status (periodic, ~2s)
#   wisc/environment/sensors — temp & humidity per sensor zone (on value change)
#   wisc/sauna/state         — sauna active state, temps, PWM, timers (on change + 5s heartbeat)
#   wisc/devices/switches    — flat key/value snapshot of state.devices (on toggle)
#   wisc/metrics/pulses      — accumulated water liters (1 decimal) and Wh (on interval)
#
# Separation of concerns:
#   mqtt_transport.py  — raw TCP socket, auth, reconnect. Zero WanOS knowledge.
#   mqtt_publisher.py  — this file. Domain routing. Zero transport knowledge.
import asyncio
import time
from typing import Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .mqtt_transport import MqttClientManager
    from .models import SystemState


# How long between forced sauna state heartbeats when the sauna is active (seconds)
SAUNA_HEARTBEAT_INTERVAL = 5.0

# How often to flush accumulated pulse metrics to the broker (seconds)
PULSE_PUBLISH_INTERVAL = 5.0


class MqttPublisher:
    """
    Listens for state change notifications from StateManager and publishes
    domain-scoped payloads to the local WanOS broker at the correct cadence.

    Registered as a state listener in StateManager so it receives every
    post-queue-drain snapshot together with the set of domains that changed.
    """

    def __init__(self, mqtt_client: "MqttClientManager") -> None:
        self._client = mqtt_client

        # Sauna heartbeat: track when we last published sauna state
        self._last_sauna_publish: float = 0.0

        # Pulse accumulation: internal counters that grow with every pulse event.
        # Values are flushed to the broker on PULSE_PUBLISH_INTERVAL, not per tick.
        self._water_cold_liters: float = 0.0
        self._water_hot_liters: float = 0.0
        self._kwh_wh: float = 0.0

        # Track last published pulse values to avoid redundant publishes
        self._last_pulse_snapshot: Optional[dict] = None

        # Background task handle for the pulse flush loop
        self._pulse_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Spawns the background pulse flush loop. Call once after the event loop is running."""
        self._pulse_task = asyncio.create_task(self._pulse_flush_loop())

    def stop(self) -> None:
        """Cancels the background pulse flush loop on shutdown."""
        if self._pulse_task:
            self._pulse_task.cancel()

    def accumulate_water(self, fluid: str, count: int) -> None:
        """
        Called by StateManager for each WATER_PULSE event.
        Accumulates raw pulse counts into liters (396 pulses = 1 liter).
        The frontend receives pre-rounded liters, never raw tick counts.
        """
        liters = count / 396.0
        if fluid == "cold":
            self._water_cold_liters += liters
        else:
            self._water_hot_liters += liters

    def accumulate_kwh(self, ticks: int = 1) -> None:
        """
        Called by StateManager for each KWH_PULSE event.
        Accumulates raw pulse ticks into Wh (1 pulse = 1 Wh).
        """
        self._kwh_wh += ticks

    async def on_state_changed(self, snapshot: "SystemState", changed_domains: Set[str]) -> None:
        """
        State listener callback. Receives the post-drain snapshot and the set of
        domain keys that changed during the last event batch.

        Routing rules:
          "system"      → wisc/system/telemetry
          "environment" → wisc/environment/sensors
          "sauna"       → wisc/sauna/state  (also fires on 5s heartbeat)
          "devices"     → wisc/devices/switches
          (pulses are handled independently by _pulse_flush_loop)
        """
        now = time.monotonic()

        if "system" in changed_domains:
            await self._publish_telemetry(snapshot)

        if "environment" in changed_domains:
            await self._publish_environment(snapshot)

        if "devices" in changed_domains:
            await self._publish_devices(snapshot)

        # Publish sauna state on any sauna domain change, OR on heartbeat if active
        sauna_due = (now - self._last_sauna_publish) >= SAUNA_HEARTBEAT_INTERVAL
        if "sauna" in changed_domains or (snapshot.sauna.active and sauna_due):
            await self._publish_sauna(snapshot)
            self._last_sauna_publish = now

    async def _publish_telemetry(self, snapshot: "SystemState") -> None:
        """Publishes OS/app uptime and connection status. Driven by the telemetry loop (~2s)."""
        await self._client.publish("wisc/system/telemetry", {
            "wanos_mqtt_connected": snapshot.system.wanos_mqtt_connected,
            "domoticz_mqtt_connected": snapshot.system.domoticz_mqtt_connected,
            "ip_address": snapshot.system.ip_address,
            "os_uptime": snapshot.system.os_uptime_formatted,
            "app_uptime": snapshot.system.app_uptime_formatted,
        })

    async def _publish_environment(self, snapshot: "SystemState") -> None:
        """Publishes raw sensor readings keyed by zone. Fires only on value change."""
        env = snapshot.environment
        await self._client.publish("wisc/environment/sensors", {
            "outside_temp": env.outside_temp,
            "outside_hum": env.outside_hum,
            "bathroom_temp": env.bathroom_temp,
            "bathroom_hum": env.bathroom_hum,
            "cinema_temp": env.cinema_temp,
            "cinema_hum": env.cinema_hum,
            "sauna_high_temp": env.sauna_high_temp,
            "sauna_high_hum": env.sauna_high_hum,
            "sauna_low_temp": env.sauna_low_temp,
            "sauna_low_hum": env.sauna_low_hum,
            "sauna_calc_temp": env.sauna_calc_temp,
            "sauna_calc_hum": env.sauna_calc_hum,
        })

    async def _publish_sauna(self, snapshot: "SystemState") -> None:
        """
        Publishes sauna control state. Fires on any sauna domain change,
        plus a forced heartbeat every SAUNA_HEARTBEAT_INTERVAL seconds while active.
        """
        s = snapshot.sauna
        await self._client.publish("wisc/sauna/state", {
            "active": s.active,
            "target_temp": s.target_temp,
            "current_temp": s.current_temp,
            "current_humidity": s.current_humidity,
            "hold_mode": s.hold_mode,
            "modulation_pwm": s.modulation_pwm,
            "phases_pwm": s.phases_pwm,
            "fireorder": s.fireorder,
            "session_start_time": s.session_start_time,
            "session_end_time": s.session_end_time,
            "ventilation_state": s.ventilation_state,
            "ventilation_deadline": s.ventilation_deadline,
        })

    async def _publish_devices(self, snapshot: "SystemState") -> None:
        """
        Publishes a flat key/value snapshot of all generic switch devices
        (hues, ventilators, SSR relays). Fires only when a device toggles.
        """
        await self._client.publish("wisc/devices/switches", snapshot.devices)

    async def _pulse_flush_loop(self) -> None:
        """
        Background loop that flushes accumulated pulse metrics every PULSE_PUBLISH_INTERVAL.
        Publishes rounded liter values — never raw tick counts.
        Only publishes when values have changed since the last flush.
        """
        while True:
            try:
                await asyncio.sleep(PULSE_PUBLISH_INTERVAL)

                snapshot = {
                    # Round to 1 decimal place: frontend displays liters, not ticks
                    "water_cold_liters": round(self._water_cold_liters, 1),
                    "water_hot_liters": round(self._water_hot_liters, 1),
                    # Wh as integer; divide by 1000 for kWh display on the consumer side
                    "kwh_total_wh": int(self._kwh_wh),
                }

                # Only publish if values changed since the last flush
                if snapshot != self._last_pulse_snapshot:
                    await self._client.publish("wisc/metrics/pulses", snapshot)
                    self._last_pulse_snapshot = snapshot

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ [MqttPublisher] Pulse flush error: {e}")
