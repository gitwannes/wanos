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

# WanOS specific
from core.models import Event, EventType
from core.mqtt_client import MqttClientManager
from core.state_manager import StateManager
from core.config import load_config, AppConfig
from core.logger import WanosLogger
from hardware.simulator import lab_mode_thermodynamics_loop
from integrations.home_hub import DomoticzHomeHubBridge

# Create a global shutdown event kill switch
shutdown_event = asyncio.Event()

# 1. Load and validate the configuration from YAML and .env
config: AppConfig = load_config()

# 2. Inject the config safely into the Local MQTT Manager
mqtt_manager: MqttClientManager = MqttClientManager(
    broker_host=config.wanos.mqtt.broker_host,
    port=config.wanos.mqtt.port,
    username=config.wanos.mqtt.username,
    password=config.wanos.mqtt.password
)

# 3. Create a dedicated Remote MQTT Manager for Domoticz
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

# 5. Bind the integration Bridge
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

    print("⏳ [WanOS Boot] Initializing pre-boot sequence...")

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
        print("⏳ [WanOS Boot] Connecting to local Mosquitto MQTT Broker ('localhost')...")
        await mqtt_manager.start()

        print(f"⏳ [WanOS Boot] Connecting to Domoticz Broker ({config.domoticz.mqtt.broker_host})...")
        await domoticz_mqtt_manager.start()

        # 2. Initialize the state engines
        print("⏳ [WanOS Boot] Spinning up Centralized State Engine...")
        await state_manager.start()

        # Start external bridges
        await domoticz_bridge.start()

        # 3. Seed initial state parameters
        state_manager.dispatch(Event(type=EventType.INITIAL_STATE_LOADED))
        print("🟢 [WanOS Boot] Core Managers active. Base state dispatched successfully.")

        # 4. Start the thermodynamics engine in the background
        print("🧪 [WanOS Boot] Launching detached background Lab Mode Thermodynamics loop...")
        physics_task = asyncio.create_task(lab_mode_thermodynamics_loop(state_manager))

        print("🧪 [WanOS Boot] Lab Mode Physics Engine initialized.")
        await wanos_logger.info("🧪 Lab Mode Physics Engine initialized.")

    except Exception as startup_err:
        print(f"\n💥 [CRITICAL BOOT FAIL] Core initialization collapsed: {startup_err}")
        print("👉 Check that a local MQTT broker is running ('sudo systemctl status mosquitto')")
        print("👉 Ensure both 'config.yaml' and 'hardware.yaml' exist in the project root.\n")
        os._exit(1)

    print("🚀 [WanOS Boot] Pre-boot checks passed. Opening network lines to HTTP/SSE web interface...")
    yield

    # Shutdown sequence
    print("🛑 [WanOS Shutdown] Tearing down background engines...")
    shutdown_event.set()
    physics_task.cancel()
    await domoticz_bridge.stop()
    await state_manager.stop()
    await domoticz_mqtt_manager.stop()
    await mqtt_manager.stop()
    print("🛑 [WanOS Shutdown] Clean teardown complete. Goodbye.")


# Initialize FastAPI
app: FastAPI = FastAPI(lifespan=lifespan, title="WanOS Backend API")


class DummyTempRequest(BaseModel):
    temp: float


class GenericEventRequest(BaseModel):
    type: EventType
    payload: dict[str, Any] = {}


@app.get("/api/state")
async def get_state() -> dict[str, Any]:
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


@app.get("/api/console")
async def get_console_logs() -> Response:
    data = {"logs": wanos_logger.get_recent_logs()}
    pretty_json = json.dumps(data, indent=4)
    return Response(content=pretty_json, media_type="application/json")


@app.get("/api/state/sse")
async def sse_state_stream(request: Request):
    async def event_generator():
        try:
            last_state_json = None
            while not shutdown_event.is_set():
                if await request.is_disconnected():
                    break
                current_state = state_manager.get_state_snapshot().model_dump()
                current_state_json = json.dumps(current_state)

                if current_state_json != last_state_json:
                    yield f"data: {current_state_json}\n\n"
                    last_state_json = current_state_json
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"⚠️ Warning: Frontend directory not found at {frontend_path}")