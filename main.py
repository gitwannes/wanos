import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from core.models import Event, EventType
from core.mqtt_client import MqttClientManager
from core.state_manager import StateManager
from core.config import load_config

# 1. Load and validate the configuration from YAML and .env
config = load_config()

# 2. Inject the config safely into the MQTT Manager
mqtt_manager = MqttClientManager(
    broker_host=config.mqtt.broker_host,
    port=config.mqtt.port,
    username=config.mqtt.username,
    password=config.mqtt.password
)

# 3. Initialize the State Manager
state_manager = StateManager(mqtt_client=mqtt_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages startup and shutdown sequences safely."""
    await mqtt_manager.start()
    await state_manager.start()

    # Start the Lab Mode background tasks
    sensor_task = asyncio.create_task(mock_temperature_sensor(state_manager))

    state_manager.dispatch(Event(type=EventType.INITIAL_STATE_LOADED))

    yield

    # Shutdown sequence
    sensor_task.cancel()
    try:
        await sensor_task
    except asyncio.CancelledError:
        pass

    await state_manager.stop()
    await mqtt_manager.stop()

# Initialize FastAPI
app = FastAPI(lifespan=lifespan, title="Wanos Backend API")


class DummyTempRequest(BaseModel):
    temp: float


@app.get("/api/state")
async def get_state():
    """Fetch the current state snapshot via HTTP."""
    return state_manager.get_state_snapshot()


@app.post("/api/test/temp")
async def inject_dummy_temp(request: DummyTempRequest):
    """Inject a dummy event using a JSON request body."""
    event = Event(type=EventType.TEMP_UPDATED, payload={"value": request.temp})
    state_manager.dispatch(event)
    return {"status": "Event dispatched to queue", "event": event}