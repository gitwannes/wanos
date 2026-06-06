import json
import aiomqtt
from typing import Optional
from contextlib import AsyncExitStack

class MqttClientManager:
    def __init__(
        self, 
        broker_host: str = "localhost", 
        port: int = 1883, 
        username: Optional[str] = None, 
        password: Optional[str] = None
    ):
        self.broker_host = broker_host
        self.port = port
        self.username = username
        self.password = password
        self.client: Optional[aiomqtt.Client] = None
        self._exit_stack = AsyncExitStack()

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
        except Exception as e:
            print(f"❌ MQTT Connect failed: {e}")
            self.client = None

    async def stop(self):
        await self._exit_stack.aclose()
        self.client = None
        print("🛑 MQTT Disconnected.")

    async def publish(self, topic: str, payload: dict):
        if not self.client:
            print("⚠️ MQTT publish skipped: no connection.")
            return

        try:
            await self.client.publish(topic, payload=json.dumps(payload))
        except aiomqtt.MqttError as e:
            print(f"⚠️ MQTT Publish error: {e}")