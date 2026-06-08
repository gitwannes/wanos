# --- file: integrations/home_hub.py ---
import asyncio
import json
from typing import Any, Dict, Optional
from core.models import Event, EventType
from core.state_manager import StateManager


class DomoticzHomeHubBridge:
    def __init__(self, state_manager: StateManager, domoticz_mqtt_client: Any,
                 domoticz_in_topic: str = "domoticz/out",
                 domoticz_out_topic: str = "domoticz/in") -> None:
        self.state_manager = state_manager

        # Uses the dedicated remote broker client
        self.mqtt_client = domoticz_mqtt_client
        self.logger = state_manager.logger

        self._in_topic = domoticz_in_topic
        self._out_topic = domoticz_out_topic

        # Access nested .id attributes from the typed Pydantic models
        cfg = state_manager._config.domoticz
        self.IDX_OUTSIDE_TEMP = cfg.idx.outside_th.id
        self.IDX_BATHROOM_VENT = cfg.idx.bathroom_extrvent.id
        self.IDX_SAUNA_EXTRACTOR = cfg.idx.sauna_extrvent.id

        self._last_known_extractor_state: Optional[bool] = None
        self._last_known_bathroom_vent_state: Optional[bool] = None

        self._worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        await self.mqtt_client.subscribe(self._in_topic, self._parse_domoticz_inbound)
        self._worker_task = asyncio.create_task(self._outbound_monitor_loop())
        await self.logger.success("🏠 Domoticz HomeHub Bridge initialized and listening.")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self.logger.warning("🏠 Domoticz HomeHub Bridge stopped.")

    async def _parse_domoticz_inbound(self, topic: str, payload: str) -> None:
        try:
            data: Dict[str, Any] = json.loads(payload)
            idx = data.get("idx")

            if idx is None:
                return

            if idx == self.IDX_OUTSIDE_TEMP:
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

            elif idx == self.IDX_BATHROOM_VENT:
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
        while True:
            try:
                await asyncio.sleep(2.0)
                state = self.state_manager.get_state_snapshot()

                # --- SAUNA EXTRACTION FAN ---
                current_extractor_target = state.environment.sauna_extraction_vent_on
                if current_extractor_target != self._last_known_extractor_state:
                    domoticz_command = {
                        "command": "switchlight",
                        "idx": self.IDX_SAUNA_EXTRACTOR,
                        "switchcmd": "On" if current_extractor_target else "Off"
                    }
                    await self.mqtt_client.publish(self._out_topic, domoticz_command)
                    await self.logger.info(
                        f"🏠 Domoticz Sync: Sauna Extractor -> {'ON' if current_extractor_target else 'OFF'}")
                    self._last_known_extractor_state = current_extractor_target

                # --- BATHROOM FAN ---
                current_bathroom_vent = state.environment.bathroom_vent_on
                if current_bathroom_vent != self._last_known_bathroom_vent_state:
                    domoticz_command = {
                        "command": "switchlight",
                        "idx": self.IDX_BATHROOM_VENT,
                        "switchcmd": "On" if current_bathroom_vent else "Off"
                    }
                    await self.mqtt_client.publish(self._out_topic, domoticz_command)
                    await self.logger.info(
                        f"🏠 Domoticz Sync: Bathroom Vent -> {'ON' if current_bathroom_vent else 'OFF'}")
                    self._last_known_bathroom_vent_state = current_bathroom_vent

            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.logger.error(f"Error in Domoticz outbound command loops: {e}")