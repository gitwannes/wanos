# --- file: core/models.py ---
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from enum import Enum


class EventType(str, Enum):
    # Hardware & Sensor Events
    TEMP_UPDATED = "TEMP_UPDATED"
    HUMIDITY_UPDATED = "HUMIDITY_UPDATED"
    WATER_PULSE = "WATER_PULSE"
    KWH_PULSE = "KWH_PULSE"
    DOOR_CHANGED = "DOOR_CHANGED"
    SENSOR_ERROR = "SENSOR_ERROR"
    TIMER_TICK = "TIMER_TICK"

    # Sauna & Logic Events
    SAUNA_ON = "SAUNA_ON"
    SAUNA_OFF = "SAUNA_OFF"
    SETPOINT_CHANGED = "SETPOINT_CHANGED"
    MODULATION_UPDATED = "MODULATION_UPDATED"
    SETPOINT_REACHED = "SETPOINT_REACHED"
    SAUNA_HOLD = "SAUNA_HOLD"
    SAUNA_TIMER_EXPIRED = "SAUNA_TIMER_EXPIRED"
    HOLD_TOGGLED = "HOLD_TOGGLED"
    TIMER_ADJUSTED = "TIMER_ADJUSTED"
    VENT_WAIT_EXPIRED = "VENT_WAIT_EXPIRED"
    VENT_RUN_EXPIRED = "VENT_RUN_EXPIRED"

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
    LAB_SIMULATION_LOG = "LAB_SIMULATION_LOG"
    SYSTEM_METRICS_UPDATED = "SYSTEM_METRICS_UPDATED"

    # External Events
    HUB_STATE_CHANGED = "HUB_STATE_CHANGED"
    LIGHTING_STATE_CHANGED = "LIGHTING_STATE_CHANGED"
    EXTERNAL_WEATHER_UPDATED = "EXTERNAL_WEATHER_UPDATED"


class SystemAdminState(BaseModel):
    wanos_mqtt_connected: bool = False
    domoticz_mqtt_connected: bool = False
    ip_address: str = "0.0.0.0"
    os_uptime_formatted: str = "00:00:00"
    app_uptime_formatted: str = "00:00:00"


class Event(BaseModel):
    type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)


class EnvironmentState(BaseModel):
    outside_temp: Optional[float] = None
    outside_hum: Optional[int] = None

    bathroom_temp: Optional[float] = None
    bathroom_hum: Optional[int] = None
    bathroom_vent_on: bool = False
    door_bathroom_open: bool = False

    cinema_temp: Optional[float] = None
    cinema_hum: Optional[int] = None
    cinema_hue_on: bool = False

    sauna_high_temp: Optional[float] = None
    sauna_high_hum: Optional[int] = None
    sauna_low_temp: Optional[float] = None
    sauna_low_hum: Optional[int] = None
    sauna_calc_temp: Optional[float] = None
    sauna_calc_hum: Optional[int] = None
    sauna_extraction_vent_on: bool = False
    sauna_hue_on: bool = False


class SaunaState(BaseModel):
    active: bool = False
    target_temp: Optional[float] = None
    current_temp: Optional[float] = None
    max_temp: Optional[float] = None
    current_humidity: Optional[int] = None
    door_open: bool = False
    hold_mode: str = "nohold"
    modulation_pwm: int = 0
    phases_pwm: List[int] = Field(default_factory=lambda: [0, 0, 0])
    fireorder: str = "--"
    session_start_time: Optional[int] = None
    session_end_time: Optional[int] = None
    ventilation_state: str = "OFF"
    ventilation_deadline: Optional[int] = None
    light_color: str = "#FFD180"  # Warm White Baseline
    lcd_text: str = ""


class IRState(BaseModel):
    active: bool = False
    modulation_pwm: int = 0
    frequency: int = 0
    session_start_time: Optional[int] = None
    session_end_time: Optional[int] = None


class MetricsState(BaseModel):
    water_cold_liters: float = 0.0
    water_hot_liters: float = 0.0
    kwh_wh_ticks: int = 0
    douche_active: bool = False
    douche_start_time: Optional[int] = None
    douche_duration_secs: int = 0
    douche_water_liters: int = 0


class HardwareState(BaseModel):
    live_mode: bool = False
    safety_pin_active: bool = False
    sensor_errors: List[str] = Field(default_factory=list)
    lab_simulation_logs: List[str] = Field(default_factory=list)


class SystemState(BaseModel):
    system: SystemAdminState = Field(default_factory=SystemAdminState)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)
    sauna: SaunaState = Field(default_factory=SaunaState)
    ir: IRState = Field(default_factory=IRState)
    metrics: MetricsState = Field(default_factory=MetricsState)
    hardware: HardwareState = Field(default_factory=HardwareState)

    # The generic "Peripheral Catch-all" dictionary for the Sorting Office
    devices: Dict[str, Any] = Field(default_factory=dict)

    # Allows the baseline validation rules parsed out of config_lab.yaml
    # to be passed seamlessly down to the web UI without strict compilation loop blocks.
    lab_seed: Optional[Any] = None