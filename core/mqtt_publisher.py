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

from logic.lcd_screen1 import compose_lcd_screen1, fit_to_16_cells, center_cells

if TYPE_CHECKING:
    from .mqtt_transport import MqttClientManager
    from .models import SystemState
    from .state_manager import StateManager

# How often to send the heartbear (seconds)
HEARTBEAT_INTERVAL = 60


class MqttPublisher:
    """
    Listens for state change notifications from StateManager and publishes
    domain-scoped payloads to the local WanOS broker using an Event-Driven Delta Architecture.
    """

    def __init__(self, mqtt_client: "MqttClientManager") -> None:
        self._client = mqtt_client
        self._sm: Optional["StateManager"] = None

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

        # -----------------------------------------------------------------
        # Remote WISC-compatible LCD (two I2C HD44780 screens via LCD Pi)
        # -----------------------------------------------------------------
        self._lcd_refresh_task: Optional[asyncio.Task] = None
        self._lcd_last_screen1: tuple[str, str] = ("", "")
        self._lcd_last_screen2: tuple[str, str] = ("", "")
        self._lcd_last_snapshot: Optional["SystemState"] = None

        self._lcd_screen2_init_sent: bool = False
        self._sauna_hue_entity_idx: Optional[int] = None
        # Admin/debug force text: do not let idle blank compose wipe it until live content returns.
        self._lcd_screen1_manual_hold: bool = False

        # Render cadence:
        # - keep LCD1 door timers fresh (WISC shows duration continuously)
        # - avoid hammering broker when everything is blank
        self._LCD_REFRESH_INTERVAL_SECS: float = 1.0

    def bind_state_manager(self, state_manager: "StateManager") -> None:
        """Inject StateManager so screen1 MQTT payloads mirror into WISC UI state."""
        self._sm = state_manager

    def start(self) -> None:
        """Spawns the background 60-second WanOS heartbeat task."""
        self._heartbeat_task = asyncio.create_task(self._wanos_heartbeat_loop())
        self._lcd_refresh_task = asyncio.create_task(self._lcd_refresh_loop())

    def stop(self) -> None:
        """Cancels the background heartbeat loop on shutdown."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._lcd_refresh_task:
            self._lcd_refresh_task.cancel()

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

        # Keep last snapshot for periodic LCD refresh cadence.
        # We update even when domains don't match so the refresh loop can
        # safely compute mm:ss / door durations from current epochs.
        self._lcd_last_snapshot = snapshot

        # Immediate screen1 publish only when LCD content can change.
        # Do NOT republish on every "system"/metrics tick — that wiped Admin
        # debug test text within a few seconds (compose blank while Hue/sauna idle).
        lcd1_domains = {"sauna", "ir", "devices", "sensors"}
        if changed_domains & lcd1_domains:
            try:
                line1, line2 = self._compose_lcd_screen1(snapshot)
                # Idle blank must not erase Admin debug / other force publishes.
                held_blank = (line1, line2) == ("", "") and self._lcd_screen1_manual_hold
                if not held_blank:
                    if line1 or line2:
                        self._lcd_screen1_manual_hold = False
                    if (line1, line2) != self._lcd_last_screen1:
                        self._lcd_last_screen1 = (line1, line2)
                        await self._client.publish(
                            "wanos/lcd/screen1",
                            {"line1": line1, "line2": line2},
                        )
                        await self._mirror_lcd_screen1_to_state(line1, line2)
            except Exception as e:
                print(f"⚠️ LCD screen1 immediate publish failed: {e}")

    async def _mirror_lcd_screen1_to_state(self, line1: str, line2: str) -> None:
        """Keep WISC sauna.lcd_line* aligned with the last MQTT screen1 payload."""
        if self._sm is None:
            return
        try:
            await self._sm.set_lcd_screen1_preview(line1, line2)
        except Exception as e:
            print(f"⚠️ LCD screen1 UI mirror failed: {e}")

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

    async def _lcd_refresh_loop(self) -> None:
        """Periodically renders/publishes LCD screen1 while sessions are active."""
        while True:
            try:
                await asyncio.sleep(self._LCD_REFRESH_INTERVAL_SECS)

                snap = self._lcd_last_snapshot
                if snap is None:
                    continue

                # Only refresh at a high cadence when something on LCD1 can change.
                lcd1_should_render = (
                    bool(snap.sauna.active) or bool(snap.ir.active)
                )
                if not lcd1_should_render:
                    continue

                line1, line2 = self._compose_lcd_screen1(snap)
                if (line1, line2) == ("", "") and self._lcd_screen1_manual_hold:
                    continue
                if line1 or line2:
                    self._lcd_screen1_manual_hold = False
                if (line1, line2) != self._lcd_last_screen1:
                    self._lcd_last_screen1 = (line1, line2)
                    await self._client.publish(
                        "wanos/lcd/screen1",
                        {"line1": line1, "line2": line2},
                    )
                    await self._mirror_lcd_screen1_to_state(line1, line2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Keep this loop resilient; do not kill MQTT publisher on LCD render bugs.
                print(f"⚠️ LCD refresh error: {e}")

    def _ensure_sauna_hue_idx(self, snapshot: "SystemState") -> None:
        """Cache IDX for hue.group.sauna_hue using device metadata entity_id."""
        if self._sauna_hue_entity_idx is not None:
            return
        for idx, meta in (snapshot.device_metadata or {}).items():
            if not isinstance(meta, dict):
                continue
            if meta.get("entity_id") == "hue.group.sauna_hue":
                try:
                    self._sauna_hue_entity_idx = int(idx)
                    return
                except (TypeError, ValueError):
                    continue

    def _compose_lcd_screen1(self, snapshot: "SystemState") -> tuple[str, str]:
        """Delegate to shared composer (MQTT + WISC UI must stay identical)."""
        self._ensure_sauna_hue_idx(snapshot)
        return compose_lcd_screen1(
            snapshot,
            sauna_hue_entity_idx=self._sauna_hue_entity_idx,
        )

    async def publish_lcd_screen1(self, line1: str, line2: str, *, force: bool = False) -> None:
        """Publishes screen 1 lines to the LCD Pi."""
        line1 = fit_to_16_cells(line1)
        line2 = fit_to_16_cells(line2)
        if not force and (line1, line2) == self._lcd_last_screen1:
            return
        self._lcd_last_screen1 = (line1, line2)
        # force=True (Admin debug): pin until compose has live sauna/IR/hue content.
        if force and (line1.strip() or line2.strip()):
            self._lcd_screen1_manual_hold = True
        elif not line1.strip() and not line2.strip():
            self._lcd_screen1_manual_hold = False
        await self._client.publish("wanos/lcd/screen1", {"line1": line1, "line2": line2})
        await self._mirror_lcd_screen1_to_state(line1, line2)

    async def publish_lcd_screen2(self, line1: str, line2: str, *, force: bool = False) -> None:
        """Publishes screen 2 lines to the LCD Pi (and wakes it from screensaver)."""
        line1 = fit_to_16_cells(line1)
        line2 = fit_to_16_cells(line2)
        if not force and (line1, line2) == self._lcd_last_screen2:
            return
        self._lcd_last_screen2 = (line1, line2)
        await self._client.publish("wanos/lcd/screen2", {"line1": line1, "line2": line2})

    async def _publish_telemetry(self, snapshot: "SystemState") -> None:
        """Publishes boot UNIX stamps once on wanos/system."""
        if not self._system_boot_sent and snapshot.system.ip_address != "0.0.0.0":
            await self._client.publish("wanos/system", {
                "app_boot_unix": self._app_boot_unix,
                "os_boot_unix": self._os_boot_unix,
                "ip_address": snapshot.system.ip_address
            })
            self._system_boot_sent = True

            # LCD Pi: initial control-kast screen status (WISC-style).
            if not self._lcd_screen2_init_sent:
                try:
                    now = int(time.time())
                    dt = time.localtime(now)
                    ts = time.strftime("%y%m%d %H:%M:%S", dt)
                    line1 = center_cells("EL init  §0§1")
                    line2 = ts.center(16)
                    await self.publish_lcd_screen2(line1, line2)
                    self._lcd_screen2_init_sent = True
                except Exception as e:
                    print(f"⚠️ LCD screen2 init failed: {e}")

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
