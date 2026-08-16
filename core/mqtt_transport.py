# --- file: core/mqtt_transport.py ---
# Pure async MQTT transport layer. Manages the TCP socket, authentication,
# reconnection, subscriptions, and raw message routing to registered callbacks.
# This class has zero knowledge of WanOS domain concepts (states, events, topics).
# Swap this file to change broker library without touching any business logic.
import json
import asyncio
import aiomqtt
from typing import Optional, Callable, Dict, Awaitable
from loguru import logger


class MqttClientManager:
    # ⚡ ZERO DEFAULTS: Forces the app to provide the network config from hardware.yaml
    def __init__(
            self,
            broker_host: str,
            port: int,
            username: Optional[str] = None,
            password: Optional[str] = None
    ):
        self.broker_host = broker_host
        self.port = port
        self.username = username
        self.password = password

        self.client: Optional[aiomqtt.Client] = None
        self.is_connected: bool = False
        self.failed_attempts: int = 0
        self._stop_requested: bool = False

        # Routing table: matches MQTT topics to specific async parsing functions
        self._callbacks: Dict[str, Callable[[str, str], Awaitable[None]]] = {}
        self._manager_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._stop_requested = False
        self._manager_task = asyncio.create_task(self._connection_manager_loop())

    async def stop(self) -> None:
        # Gracefully shut down the background loop
        self._stop_requested = True
        if self._manager_task:
            self._manager_task.cancel()
            try:
                await self._manager_task
            except asyncio.CancelledError:
                pass

        self.is_connected = False
        self.client = None
        logger.warning(f"MQTT Disconnected ({self.broker_host}).")

    async def publish(self, topic: str, payload: dict) -> bool:
        """Publish JSON to MQTT. Returns False if skipped or the broker write failed."""
        if not self.is_connected or not self.client:
            logger.warning(f"MQTT publish skipped ({self.broker_host}): no connection.")
            return False

        try:
            await self.client.publish(topic, payload=json.dumps(payload))
            return True
        except aiomqtt.MqttError as e:
            logger.error(f"MQTT Publish error: {e}")
            return False

    async def subscribe(self, topic: str, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """Registers a topic and maps it to an async callback function."""
        self._callbacks[topic] = callback
        if self.is_connected and self.client:
            try:
                await self.client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic} on {self.broker_host}")
            except aiomqtt.MqttError as e:
                logger.error(f"MQTT Subscribe error on {topic}: {e}")

    async def _connection_manager_loop(self) -> None:
        """Tier 1: Permanent auto-reconnecting background loop."""
        while not self._stop_requested:
            try:
                async with aiomqtt.Client(
                        hostname=self.broker_host,
                        port=self.port,
                        username=self.username,
                        password=self.password
                ) as client:
                    self.client = client
                    self.is_connected = True
                    self.failed_attempts = 0
                    logger.success(f"MQTT Connected to {self.broker_host}:{self.port}")

                    # If we reconnect, resubscribe to all previously registered topics
                    for topic in self._callbacks.keys():
                        await self.client.subscribe(topic)

                    # Launch the background loop that listens for incoming traffic
                    # It will block here until the socket dies or is cancelled
                    await self._listen_loop()

            except asyncio.CancelledError:
                break
            except aiomqtt.MqttError as e:
                self.is_connected = False
                self.client = None
                self.failed_attempts += 1
                if self.failed_attempts == 1:
                    logger.warning(
                        f"MQTT Connection dropped ({self.broker_host}): {e}. Retry in 5s (Attempt {self.failed_attempts})")
                await asyncio.sleep(5.0)
            except Exception as e:
                self.is_connected = False
                self.client = None
                self.failed_attempts += 1
                if self.failed_attempts == 1:
                    logger.error(
                        f"MQTT Unexpected Error ({self.broker_host}): {e}. Retry in 5s (Attempt {self.failed_attempts})")
                await asyncio.sleep(5.0)
            finally:
                self.is_connected = False
                self.client = None

    async def _listen_loop(self) -> None:
        """Continuously pulls messages from the broker and routes them to the right callback."""
        if not self.client:
            return

        # Exception handling for MqttError is done in the parent _connection_manager_loop
        async for message in self.client.messages:
            topic_str = str(message.topic)
            # Decode the raw byte payload into a usable UTF-8 string
            payload = message.payload.decode('utf-8')

            # Route the message to the registered callback(s) supporting MQTT wildcards
            for sub_topic, callback in self._callbacks.items():
                if message.topic.matches(sub_topic):
                    try:
                        await callback(topic_str, payload)
                    except Exception as cb_error:
                        logger.error(f"Error executing callback for topic {sub_topic}: {cb_error}")