from pydantic import BaseModel, Field
from typing import Any, Optional
from enum import Enum

class EventType(str, Enum):
    """Strict enumeration of all permitted system events."""
    # Hardware Events
    TEMP_UPDATED = "TEMP_UPDATED"
    HUMIDITY_UPDATED = "HUMIDITY_UPDATED"
    WATER_PULSE = "WATER_PULSE"
    KWH_PULSE = "KWH_PULSE"
    DOOR_CHANGED = "DOOR_CHANGED"
    SENSOR_ERROR = "SENSOR_ERROR"
    # Sauna Events
    SAUNA_ON = "SAUNA_ON"
    SAUNA_OFF = "SAUNA_OFF"
    SETPOINT_CHANGED = "SETPOINT_CHANGED"
    MODULATION_UPDATED = "MODULATION_UPDATED"
    SETPOINT_REACHED = "SETPOINT_REACHED"
    SAUNA_HOLD = "SAUNA_HOLD"
    SAUNA_TIMER_EXPIRED = "SAUNA_TIMER_EXPIRED"
    # IR Events
    IR_ON = "IR_ON"
    IR_OFF = "IR_OFF"
    IR_MODULATION_UPDATED = "IR_MODULATION_UPDATED"
    IR_TIMER_EXPIRED = "IR_TIMER_EXPIRED"
    # System Events
    INITIAL_STATE_LOADED = "INITIAL_STATE_LOADED"
    BACKEND_SHUTDOWN = "BACKEND_SHUTDOWN"
    HARDWARE_LIVE_MODE_CHANGED = "HARDWARE_LIVE_MODE_CHANGED"
    CONFIG_UPDATED = "CONFIG_UPDATED"
    # External Events
    HUB_STATE_CHANGED = "HUB_STATE_CHANGED"
    LIGHTING_STATE_CHANGED = "LIGHTING_STATE_CHANGED"
    EXTERNAL_WEATHER_UPDATED = "EXTERNAL_WEATHER_UPDATED"

# --- Nested Sub-States ---

class HardwareState(BaseModel):
    live_mode: bool = False
    door_open: bool = False
    safety_pin_active: bool = False

class SaunaState(BaseModel):
    active: bool = False
    current_temp: Optional[float] = None
    target_temp: float = 80.0
    modulation_pwm: int = 0  # 0 to 100%

class LightingState(BaseModel):
    bathroom_light_on: bool = False
    relax_room_light_on: bool = False

# --- Master Vault ---

class SystemState(BaseModel):
    """The strictly typed, single source of truth for the system."""
    hardware: HardwareState = Field(default_factory=HardwareState)
    sauna: SaunaState = Field(default_factory=SaunaState)
    lighting: LightingState = Field(default_factory=LightingState)

class Event(BaseModel):
    """The strict schema for all events entering the State Manager queue."""
    type: EventType = Field(..., description="The explicitly typed event category")
    payload: dict[str, Any] = Field(default_factory=dict)