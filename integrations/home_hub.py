# --- file: integrations/home_hub.py ---
import asyncio
import json
from typing import Any, Dict, Optional
from core.models import Event, EventType
from core.state_manager import StateManager


class DomoticzHomeHubBridge:
    """
    Bidirectional Bridge between the WanOS State Manager and the Domoticz MQTT API.
    Handles inbound updates (Outside Weather, Bathroom Vent overrides) and
    outbound controls (Sauna Extraction Fan switching).
    """

    def __init__(self, state_manager: StateManager, domoticz_in_topic: str = "domoticz/out",
                 domoticz_out_topic: str = "domoticz/in") -> None:
        self.state_manager = state_manager
        self.mqtt_client = state_manager.mqtt_client
        self.logger = state_manager.logger

        # Topics from Domoticz's perspective:
        # 'domoticz/out' is published BY Domoticz (Inbound to WanOS)
        # 'domoticz/in' is read BY Domoticz (Outbound from WanOS)
        self._in_topic = domoticz_in_topic
        self._out_topic = domoticz_out_topic

        # Explicit hardware idx mapping matching your physical Domoticz setup
        self.IDX_OUTSIDE_TEMP = 42  # Example Domoticz IDX for outdoor temp+hum sensor
        self.IDX_BATHROOM_VENT = 88  # Example Domoticz IDX for bathroom fan relay
        self.IDX_SAUNA_EXTRACTOR = 99  # Example Domoticz IDX for sauna extraction fan relay

        self._last_known_extractor_state: Optional[bool] = None
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Subscribes to Domoticz traffic and starts the outbound monitor loop."""
        # 1. Register our inbound parser callback directly with the MQTT client manager
        await self.mqtt_client.subscribe(self._in_topic, self._parse_domoticz_inbound)

        # 2. Run the outbound state sync loop in the background
        self._worker_task = asyncio.create_task(self._outbound_monitor_loop())
        await self.logger.success("🏠 Domoticz HomeHub Bridge initialized and listening.")

    async def stop(self) -> None:
        """Cleans up background monitoring tasks securely."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.logger.warning("🏠 Domoticz HomeHub Bridge stopped.")

    async def _parse_domoticz_inbound(self, topic: str, payload: str) -> None:
        """
        Parses incoming raw JSON strings from Domoticz.
        Converts flat IDX messages into deeply structured WanOS engine Events.
        """
        try:
            data: Dict[str, Any] = json.loads(payload)
            idx = data.get("idx")

            if idx is None:
                return

            # --------------------------------------------------------
            # 1. PARSE OUTSIDE WEATHER DATA
            # --------------------------------------------------------
            if idx == self.IDX_OUTSIDE_TEMP:
                # Domoticz typically bundles temp/hum in strings or distinct keys depending on sensor type
                # e.g., {"idx": 42, "svalue1": "12.5", "svalue2": "65"}
                raw_temp = data.get("svalue1")
                raw_hum = data.get("svalue2")

                if raw_temp is not None:
                    self.state_manager.dispatch(Event(
                        type=EventType.TEMP_UPDATED,
                        payload={"sensor_id": "outside", "value": float(raw_temp)}
                    ))
                if raw_hum is not None:
                    self.state_manager.dispatch(Event(
                        type=EventType.HUMIDITY_UPDATED,
                        payload={"sensor_id": "outside", "value": int(float(raw_hum))}
                    ))

            # --------------------------------------------------------
            # 2. PARSE BATHROOM VENTILATOR STATUS OVERRIDES
            # --------------------------------------------------------
            elif idx == self.IDX_BATHROOM_VENT:
                # e.g., {"idx": 88, "nvalue": 0} (OFF) or {"idx": 88, "nvalue": 1} (ON)
                nvalue = data.get("nvalue", 0)
                status_string = "ON" if nvalue > 0 else "OFF"

                self.state_manager.dispatch(Event(
                    type=EventType.HUB_STATE_CHANGED,
                    payload={"device_id": "bathroom_ventilator", "state": status_string}
                ))

        except ValueError as val_err:
            await self.logger.error(f"Domoticz parser dropped invalid JSON payload: {val_err}")
        except Exception as e:
            await self.logger.error(f"Error handling Domoticz inbound translation: {e}")

    async def _outbound_monitor_loop(self) -> None:
        """
        Periodically reviews the State Vault targets.
        If WanOS modifies the sauna extraction vent flag, it sends an command payload to Domoticz.
        """
        while True:
            try:
                # Polling interval to check the safe deep copy snapshot
                await asyncio.sleep(2.0)
                state = self.state_manager.get_state_snapshot()

                # Extract our dynamic validation metric target
                current_extractor_target = state.environment.sauna_extraction_vent_on

                # Direct switch orchestration only triggers on state change boundaries
                if current_extractor_target != self._last_known_extractor_state:
                    # Formulate standard Domoticz switch interface protocol JSON
                    # nvalue: 0 = Off, 1 = On
                    domoticz_command = {
                        "command": "switchlight",
                        "idx": self.IDX_SAUNA_EXTRACTOR,
                        "switchcmd": "On" if current_extractor_target else "Off"
                    }

                    # Push outbound to Domoticz input broker stream
                    await self.mqtt_client.publish(self._out_topic, domoticz_command)
                    await self.logger.info(
                        f"🏠 Sent command to Domoticz: Sauna Extractor -> {'ON' if current_extractor_target else 'OFF'}"
                    )

                    # Lock state boundaries to minimize network saturation bursts
                    self._last_known_extractor_state = current_extractor_target

            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"Error in Domoticz outbound command loops: {e}")