# --- file: core/logger.py ---
import datetime
import os
from typing import Dict, TYPE_CHECKING
from loguru import logger as sys_logger
from .mqtt_transport import MqttClientManager
if TYPE_CHECKING:
    from .state_manager import StateManager

class WanosComponent:
    """Base class for all system components to ensure state/logger access."""
    def __init__(self, state_manager: 'StateManager') -> None:
        self.state_manager = state_manager
        self.logger = state_manager.logger

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


def setup_wanos_logging():
    """Initializes the multi-sink logging strategy for WanOS."""
    # 1. Clean the environment
    sys_logger.remove()

    custom_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
    log_dir = "/var/log/wisc"

    # Ensure directory exists
    os.makedirs(log_dir, exist_ok=True)

    # 2. Sink for INFO and above
    sys_logger.add(
        f"{log_dir}/wanos.log",
        rotation="5 MB",
        retention=3,
        format=custom_format,
        level="INFO",
        filter=lambda record: record["level"].name != "DEBUG"
    )

    # 3. Sink specifically for DEBUG
    sys_logger.add(
        f"{log_dir}/wanos_debug.log",
        rotation="5 MB",
        retention=3,
        format=custom_format,
        level="DEBUG",
        filter=lambda record: record["level"].name == "DEBUG"
    )