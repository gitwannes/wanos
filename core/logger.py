# --- file: core/logger.py ---
import datetime
from typing import Dict
from loguru import logger as sys_logger
from .mqtt_transport import MqttClientManager


class WanosLogger:
    """
    Centralized asynchronous logger for WanOS.
    """

    def __init__(self, mqtt_client: MqttClientManager) -> None:
        self.mqtt_client: MqttClientManager = mqtt_client
        self.topic_status: str = "wanos/console/status"
        self.topic_debug: str = "wanos/console/debug"

    async def _log(self, level: str, message: str) -> None:
        """Pipes to Loguru and broadcasts to MQTT."""
        timestamp: str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Pipe to standard Loguru file/console system
        is_debug = False
        if level == "SUCCESS":
            sys_logger.success(message)
        elif level == "WARNING":
            sys_logger.warning(message)
        elif level == "ERROR":
            sys_logger.error(message)
        elif level == "DEBUG":
            sys_logger.debug(message)
            is_debug = True
        else:
            sys_logger.info(message)

        payload: Dict[str, str] = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }

        # 2. Broadcast to the correct MQTT topic
        target_topic = self.topic_debug if is_debug else self.topic_status
        await self.mqtt_client.publish(target_topic, payload)

    async def debug(self, message: str) -> None:
        await self._log("DEBUG", message)

    async def info(self, message: str) -> None:
        await self._log("INFO", message)

    async def success(self, message: str) -> None:
        await self._log("SUCCESS", message)

    async def warning(self, message: str) -> None:
        await self._log("WARNING", message)

    async def error(self, message: str) -> None:
        await self._log("ERROR", message)