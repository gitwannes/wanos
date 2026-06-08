# --- file: core/mqtt_client.py ---
import json
import asyncio
import aiomqtt
from typing import Optional, Callable, Dict, Awaitable
from contextlib import AsyncExitStack


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
        self._exit_stack = AsyncExitStack()

        # Routing table: matches MQTT topics to specific parsing functions
        self._callbacks: Dict[str, Callable[[str, str], Awaitable[None]]] = {}
        self._listen_task: Optional[asyncio.Task] = None

    async def start(self):
        self.client = aiomqtt.Client(
            hostname=self.broker_host,
            port=self.port,
            username=self.username,
            password=self.password
        )
        try:
            await self._exit_stack.enter_async_context(self.client)
            print(f"✅ MQTT Connected to {self.broker_host}:{self.port}")

            # If we reconnect, make sure we resubscribe to all active topics
            for topic in self._callbacks.keys():
                await self.client.subscribe(topic)

            # Launch the background loop that listens for incoming traffic
            self._listen_task = asyncio.create_task(self._listen_loop())

        except Exception as e:
            print(f"❌ MQTT Connect failed: {e}")
            self.client = None

    async def stop(self):
        # Gracefully shut down the background listening loop
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await self._exit_stack.aclose()
        self.client = None
        print(f"🛑 MQTT Disconnected ({self.broker_host}).")

    async def publish(self, topic: str, payload: dict):
        if not self.client:
            print(f"⚠️ MQTT publish skipped ({self.broker_host}): no connection.")
            return

        try:
            await self.client.publish(topic, payload=json.dumps(payload))
        except aiomqtt.MqttError as e:
            print(f"⚠️ MQTT Publish error: {e}")

    async def subscribe(self, topic: str, callback: Callable[[str, str], Awaitable[None]]):
        """Registers a topic and maps it to an async callback function."""
        self._callbacks[topic] = callback
        if self.client:
            try:
                await self.client.subscribe(topic)
                print(f"🎧 Subscribed to topic: {topic} on {self.broker_host}")
            except aiomqtt.MqttError as e:
                print(f"⚠️ MQTT Subscribe error on {topic}: {e}")

    async def _listen_loop(self):
        """Continuously pulls messages from the broker and routes them to the right callback."""
        if not self.client:
            return

        try:
            async for message in self.client.messages:
                topic = str(message.topic)
                # Decode the raw byte payload into a usable UTF-8 string
                payload = message.payload.decode('utf-8')

                # If we have a bridge waiting for this topic, pass the data to it!
                if topic in self._callbacks:
                    try:
                        await self._callbacks[topic](topic, payload)
                    except Exception as cb_error:
                        print(f"⚠️ Error executing callback for topic {topic}: {cb_error}")

        except asyncio.CancelledError:
            # Task was intentionally cancelled during a shutdown
            pass
        except aiomqtt.MqttError as e:
            print(f"⚠️ MQTT Listen loop connection dropped: {e}")