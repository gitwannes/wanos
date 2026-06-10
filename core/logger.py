import datetime
from collections import deque
from typing import Dict, List
from .mqtt_transport import MqttClientManager


class WanosLogger:
    """
    Centralized asynchronous logger for WanOS.
    Outputs color-coded text, broadcasts via MQTT on split topics, and stores history.
    """

    def __init__(self, mqtt_client: MqttClientManager) -> None:
        self.mqtt_client: MqttClientManager = mqtt_client
        self.topic_status: str = "wisc/system/console/status"
        self.topic_debug: str = "wisc/system/console/debug"
        # Rolling buffer: Remembers the last 100 log events in memory
        self.history: deque[Dict[str, str]] = deque(maxlen=100)

    async def _log(self, level: str, message: str, color_code: str, is_debug: bool = False) -> None:
        """Formats the message, prints to terminal, saves to history, and broadcasts."""
        timestamp: str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Print to local console with ANSI colors
        print(f"\033[{color_code}m[{timestamp}] {level}: {message}\033[0m")

        payload: Dict[str, str] = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }

        # 2. Save to internal memory
        self.history.append(payload)

        # 3. Broadcast to the correct MQTT topic
        target_topic = self.topic_debug if is_debug else self.topic_status
        await self.mqtt_client.publish(target_topic, payload)

    def get_recent_logs(self) -> List[Dict[str, str]]:
        """Returns the log history for the API endpoint."""
        return list(reversed(self.history))

    async def debug(self, message: str) -> None:
        # Dark Grey (90) for background noise. Routed to the debug topic.
        await self._log("DEBUG", message, "90", is_debug=True)

    async def info(self, message: str) -> None:
        # Blue (94)
        await self._log("INFO", message, "94", is_debug=False)

    async def success(self, message: str) -> None:
        # Green (92)
        await self._log("SUCCESS", message, "92", is_debug=False)

    async def warning(self, message: str) -> None:
        # Yellow (93)
        await self._log("WARNING", message, "93", is_debug=False)

    async def error(self, message: str) -> None:
        # Red (91)
        await self._log("ERROR", message, "91", is_debug=False)