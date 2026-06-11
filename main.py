# --- file: main.py ---
import asyncio
import json
import os
import signal
from fastapi import Response
from contextlib import asynccontextmanager
from typing import Union, Any, AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from loguru import logger

# WanOS specific
from core.models import Event, EventType
from core.mqtt_transport import MqttClientManager
from core.mqtt_publisher import MqttPublisher
from core.state_manager import StateManager
from core.config import load_config, AppConfig
from core.logger import WanosLogger
from hardware.simulator import lab_mode_thermodynamics_loop
from integrations.home_hub import DomoticzHomeHubBridge

# Create a global shutdown event kill switch
shutdown_event = asyncio.Event()

# 0. Configure Centralized File Logger
logger.remove()  # 🛑 Silences the default console output entirely
custom_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
logger.add("/var/log/wisc/wanos.log", rotation="5 MB", retention=3, format=custom_format)

# 1. Load and validate the configuration from YAML and .env
config: AppConfig = load_config()

# 2. Inject the config safely into the Local MQTT Transport (local Mosquitto broker)
mqtt_manager: MqttClientManager = MqttClientManager(
    broker_host=config.wanos.mqtt.broker_host,
    port=config.wanos.mqtt.port,
    username=config.wanos.mqtt.username,
    password=config.wanos.mqtt.password
)

# 3. Create a dedicated Remote MQTT Transport for Domoticz
# ARCHITECTURE NOTE: This is the "Network Postman". Its ONLY job is handling the TCP
# socket, authentication, and auto-reconnecting to the remote broker (10.32.251.181).
# It knows absolutely nothing about Domoticz JSON formats or sauna states.
domoticz_mqtt_manager: MqttClientManager = MqttClientManager(
    broker_host=config.domoticz.mqtt.broker_host,
    port=config.domoticz.mqtt.port,
    username=config.domoticz.mqtt.username,
    password=config.domoticz.mqtt.password
)

# 4. Initialize the Logger and State Manager
wanos_logger: WanosLogger = WanosLogger(mqtt_client=mqtt_manager)
state_manager: StateManager = StateManager(mqtt_client=mqtt_manager, logger=wanos_logger)

# 5. Initialize the domain-scoped MQTT Publisher
# ARCHITECTURE NOTE: This is the "WanOS Correspondent". It knows which domain maps to
# which topic, at which cadence. It receives post-drain snapshots from StateManager
# together with the set of changed domains, and routes each to the correct topic.
# The Postman (mqtt_manager) delivers the packets; this layer decides what to write.
mqtt_publisher: MqttPublisher = MqttPublisher(mqtt_client=mqtt_manager)

# 6. Bind the integration Bridge
# ARCHITECTURE NOTE: This is the "Bilingual Translator". It takes the raw network stream
# from the Postman (domoticz_mqtt_manager) and translates specific 'idx' JSON payloads
# into WanOS internal events. Keeping this completely separate from the network client
# ensures we can easily swap Domoticz for Home Assistant later without touching networking code.
domoticz_bridge: DomoticzHomeHubBridge = DomoticzHomeHubBridge(
    state_manager=state_manager,
    domoticz_mqtt_client=domoticz_mqtt_manager
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages startup and shutdown sequences safely without silent deadlocks."""

    logger.info("Initializing pre-boot sequence...")

    # Intercept the exact CTRL-C signal to instantly drop the SSE stream
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            original_handler = signal.getsignal(sig)

            def make_handler(orig=original_handler):
                def custom_handler(signum, frame):
                    loop.call_soon_threadsafe(shutdown_event.set)
                    if callable(orig):
                        orig(signum, frame)

                return custom_handler

            signal.signal(sig, make_handler())
    except Exception:
        pass  # Windows compatibility failsafe

    try:
        # 1. Start Network Transports
        logger.info("Connecting to local Mosquitto MQTT Broker...")
        await mqtt_manager.start()

        logger.info(f"Connecting to Domoticz Broker ({config.domoticz.mqtt.broker_host})...")
        await domoticz_mqtt_manager.start()

        # 2. Initialize the state engine and wire up the publisher
        await state_manager.start()

        # Inject the publisher reference so StateManager can forward pulse accumulation
        # and the publisher receives post-drain snapshots with changed domain sets
        state_manager.mqtt_publisher = mqtt_publisher
        mqtt_publisher.start()

        # Start external bridges
        await domoticz_bridge.start()

        # 3. Seed initial state parameters
        state_manager.dispatch(Event(type=EventType.SYSTEM_READY))
        logger.info("Core systems online. Base state ready.")

        # 4. Start the thermodynamics engine in the background
        logger.info("Simulation engine booting...")
        physics_task = asyncio.create_task(lab_mode_thermodynamics_loop(state_manager))

        logger.info("Simulation engine initialized.")

    except Exception as startup_err:
        logger.error(f"Core initialization collapsed: {startup_err}")
        os._exit(1)

    logger.success("Boot sequence complete. HTTP/SSE Web Interface online.")
    yield

    # Shutdown sequence
    logger.warning("Tearing down background engines...")
    shutdown_event.set()
    physics_task.cancel()
    mqtt_publisher.stop()
    await domoticz_bridge.stop()
    await state_manager.stop()
    await domoticz_mqtt_manager.stop()
    await mqtt_manager.stop()
    logger.success("Clean teardown complete. Goodbye.")

# Initialize FastAPI
app: FastAPI = FastAPI(lifespan=lifespan, title="WanOS Backend API")


class DummyTempRequest(BaseModel):
    temp: float


class GenericEventRequest(BaseModel):
    type: EventType
    payload: dict[str, Any] = {}


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Returns a full state snapshot. Called by the frontend on initial connect and reconnect."""
    return state_manager.get_state_snapshot().model_dump()


@app.post("/api/test/temp")
async def inject_dummy_temp(request: DummyTempRequest) -> dict[str, Union[str, Event]]:
    event: Event = Event(type=EventType.TEMP_UPDATED, payload={"value": request.temp})
    state_manager.dispatch(event)
    return {"status": "Event dispatched to queue", "event": event}


@app.post("/api/event")
async def inject_event(request: GenericEventRequest) -> dict[str, Union[str, Event]]:
    event: Event = Event(type=request.type, payload=request.payload)
    state_manager.dispatch(event)
    return {"status": "Event dispatched", "event": event}


@app.get("/api/state/sse")
async def sse_state_stream(request: Request):
    """
    Delta SSE stream. Emits only changed domain subtrees after each event queue drain.
    Payload format: {"domain": "<key>", "data": { ... }}
    The frontend fetches /api/state on connect for the full snapshot, then
    applies these partial updates by domain key as they arrive.
    """

    async def event_generator():
        # Track the last emitted snapshot per domain to suppress redundant pushes
        last_domain_snapshots: dict[str, str] = {}

        import time
        last_ping_time = time.time()

        try:
            while not shutdown_event.is_set():
                if await request.is_disconnected():
                    break

                current_state = state_manager.get_state_snapshot()
                data_sent = False

                # Emit only domains whose serialized content has changed since last push
                for domain in ["system", "environment", "sauna", "ir", "metrics", "hardware", "devices"]:
                    domain_data = getattr(current_state, domain, None)
                    if domain_data is None:
                        continue

                    # Serialize the domain subtree for diffing
                    if hasattr(domain_data, "model_dump"):
                        domain_json = json.dumps(domain_data.model_dump())
                    else:
                        domain_json = json.dumps(domain_data)

                    if last_domain_snapshots.get(domain) != domain_json:
                        payload = json.dumps({"domain": domain, "data": json.loads(domain_json)})
                        yield f"data: {payload}\n\n"
                        last_domain_snapshots[domain] = domain_json
                        data_sent = True

                # 💓 INTUITIVE APP-LEVEL HEARTBEAT MONITOR
                now = time.time()
                if data_sent:
                    # If live structural state updates went out, they double as our keep-alive
                    last_ping_time = now
                elif now - last_ping_time >= 5.0:
                    # Pipe an explicit, silent data block if the channel remains quiet for 5 seconds
                    ping_payload = json.dumps({"domain": "ping", "data": {}})
                    yield f"data: {ping_payload}\n\n"
                    last_ping_time = now

                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning("⚠️ Warning: Frontend directory not found at {frontend_path}")