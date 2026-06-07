# --- file: main.py ---
import asyncio
from contextlib import asynccontextmanager
from typing import Union, Any, AsyncGenerator
from fastapi import FastAPI
from pydantic import BaseModel
from core.models import Event, EventType
from core.mqtt_client import MqttClientManager
from core.state_manager import StateManager
from core.config import load_config, AppConfig
from hardware.sensors import mock_temperature_sensor

# 1. Load and validate the configuration from YAML and .env
config: AppConfig = load_config()

# 2. Inject the config safely into the MQTT Manager
mqtt_manager: MqttClientManager = MqttClientManager(
    broker_host=config.mqtt.broker_host,
    port=config.mqtt.port,
    username=config.mqtt.username,
    password=config.mqtt.password
)

# 3. Initialize the State Manager
state_manager: StateManager = StateManager(mqtt_client=mqtt_manager)


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