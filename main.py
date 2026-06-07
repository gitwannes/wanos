import asyncio
import json
from fastapi import Response
from contextlib import asynccontextmanager
from typing import Union, Any, AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core.models import Event, EventType
from core.mqtt_client import MqttClientManager
from core.state_manager import StateManager
from core.config import load_config, AppConfig
from core.logger import WanosLogger
from hardware.sensors import mock_temperature_sensor
from fastapi.staticfiles import StaticFiles

# 1. Load and validate the configuration from YAML and .env
config: AppConfig = load_config()

# 2. Inject the config safely into the MQTT Manager
mqtt_manager: MqttClientManager = MqttClientManager(
    broker_host=config.mqtt.broker_host,
    port=config.mqtt.port,
    username=config.mqtt.username,
    password=config.mqtt.password
)

# 3. Initialize the Logger and State Manager
wanos_logger: WanosLogger = WanosLogger(mqtt_client=mqtt_manager)
state_manager: StateManager = StateManager(mqtt_client=mqtt_manager, logger=wanos_logger)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages startup and shutdown sequences safely."""
    await mqtt_manager.start()
    await state_manager.start()

    # Start the Lab Mode background tasks
    sensor_task: asyncio.Task = asyncio.create_task(mock_temperature_sensor(state_manager))

    # Prime the system state safely on boot
    state_manager.dispatch(Event(type=EventType.INITIAL_STATE_LOADED))

    yield

    # Shutdown sequence: Cancel background tasks and stop managers
    sensor_task.cancel()
    try:
        await sensor_task
    except asyncio.CancelledError:
        pass

    await state_manager.stop()
    await mqtt_manager.stop()

# Initialize FastAPI
app: FastAPI = FastAPI(lifespan=lifespan, title="WanOS Backend API")

class DummyTempRequest(BaseModel):
    temp: float

class GenericEventRequest(BaseModel):
    type: EventType
    payload: dict[str, Any] = {}

@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """Fetch the current state snapshot via HTTP."""
    return state_manager.get_state_snapshot().model_dump()

@app.post("/api/test/temp")
async def inject_dummy_temp(request: DummyTempRequest) -> dict[str, Union[str, Event]]:
    """Inject a dummy event using a JSON request body."""
    event: Event = Event(type=EventType.TEMP_UPDATED, payload={"value": request.temp})
    state_manager.dispatch(event)
    return {"status": "Event dispatched to queue", "event": event}

@app.post("/api/event")
async def inject_event(request: GenericEventRequest) -> dict[str, Union[str, Event]]:
    """Universal endpoint to inject any system event."""
    event: Event = Event(type=request.type, payload=request.payload)
    state_manager.dispatch(event)
    return {"status": "Event dispatched", "event": event}

@app.get("/api/console")
async def get_console_logs() -> Response:
    """Fetch the rolling log history directly via HTTP (Pretty Printed)."""
    data = {"logs": wanos_logger.get_recent_logs()}
    # Format with 4 spaces of indentation
    pretty_json = json.dumps(data, indent=4)
    # Return it as a raw string so the browser respects the spaces
    return Response(content=pretty_json, media_type="application/json")

@app.get("/api/state/sse")
async def sse_state_stream(request: Request):
    """
    Maintains a persistent connection with the web UI and pushes
    JSON state updates instantly whenever the vault changes.
    """

    async def event_generator():
        last_state_json = None
        while True:
            # If the user closes the browser tab, cleanly break the loop
            if await request.is_disconnected():
                break

            # Grab a safe, read-only snapshot from the Bouncer
            # (Assuming your StateManager instance in main.py is named `state_manager`)
            current_state = state_manager.get_state_snapshot().model_dump()
            current_state_json = json.dumps(current_state)

            # Only push data through the network if the state actually changed
            if current_state_json != last_state_json:
                yield f"data: {current_state_json}\n\n"
                last_state_json = current_state_json

            # Check for updates every 0.5 seconds for a highly responsive UI
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- FRONTEND UI MOUNT ---
# This must remain at the bottom of the routing list so it doesn't swallow /api/ paths!
# The html=True flag tells FastAPI to automatically serve index.html when visiting the root url.
import os

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"⚠️ Warning: Frontend directory not found at {frontend_path}")