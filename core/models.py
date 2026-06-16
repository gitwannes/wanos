# --- file: core/models.py ---
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from enum import Enum


class EventType(str, Enum):
    # Hardware & Sensor Events
    TEMP_UPDATED = "TEMP_UPDATED"
    HUMIDITY_UPDATED = "HUMIDITY_UPDATED"
    POWER_UPDATED = "POWER_UPDATED"
    WATER_PULSE = "WATER_PULSE"
    KWH_PULSE = "KWH_PULSE"
    DOOR_CHANGED = "DOOR_CHANGED"
    SENSOR_ERROR = "SENSOR_ERROR"
    BATH1_VENT_LOCK_EXPIRED = "BATH1_VENT_LOCK_EXPIRED"  # Fired when the bathroom vent minimum runtime ends
    ALERT_DISMISSED = "ALERT_DISMISSED"  # General error message on top of the UI
    TEST_ALERT_INJECTED = "TEST_ALERT_INJECTED"  # to test the teneral error message on top of the UI

    # Macro & Scene Events
    SCENE_GV_OFF = "SCENE_GV_OFF"
    SCENE_VERDIEP1_OFF = "SCENE_VERDIEP1_OFF"
    SCENE_VERDIEP2_OFF = "SCENE_VERDIEP2_OFF"
    SCENE_ALL_OFF = "SCENE_ALL_OFF"

    # Sauna & Logic Events
    SAUNA_ON = "SAUNA_ON"
    SAUNA_OFF = "SAUNA_OFF"
    SAUNA_SETPOINT_CHANGED = "SAUNA_SETPOINT_CHANGED"
    SAUNA_MODULATION_UPDATED = "SAUNA_MODULATION_UPDATED"
    SAUNA_SETPOINT_REACHED = "SAUNA_SETPOINT_REACHED"
    SAUNA_HOLD = "SAUNA_HOLD"
    SAUNA_TIMER_EXPIRED = "SAUNA_TIMER_EXPIRED"
    SAUNA_HOLD_TOGGLED = "SAUNA_HOLD_TOGGLED"
    SAUNA_TIMER_ADJUSTED = "SAUNA_TIMER_ADJUSTED"
    VENT_WAIT_EXPIRED = "VENT_WAIT_EXPIRED"
    VENT_RUN_EXPIRED = "VENT_RUN_EXPIRED"

    # IR Events
    IR_ON = "IR_ON"
    IR_OFF = "IR_OFF"
    IR_MODULATION_UPDATED = "IR_MODULATION_UPDATED"
    IR_TIMER_EXPIRED = "IR_TIMER_EXPIRED"

    # System Events
    SYSTEM_READY = "SYSTEM_READY"
    BACKEND_SHUTDOWN = "BACKEND_SHUTDOWN"
    HARDWARE_LIVE_MODE_CHANGED = "HARDWARE_LIVE_MODE_CHANGED"  # SHT sensors, Sauna & IR controls, LCD text
    CONFIG_UPDATED = "CONFIG_UPDATED"
    SYSTEM_METRICS_UPDATED = "SYSTEM_METRICS_UPDATED"
    AUTOMATIONS_TOGGLED = "AUTOMATIONS_TOGGLED"  # Automation Rules
    SIMULATIONS_TOGGLED = "SIMULATIONS_TOGGLED"  # Simulation Physics Engine
    DOMOTICZ_TOGGLED = "DOMOTICZ_TOGGLED"  # Listen to Domoticz messages
    OWM_TOGGLED = "OWM_TOGGLED"  # get OWM weather

    # External Events
    HUB_STATE_CHANGED = "HUB_STATE_CHANGED"
    LIGHTING_STATE_CHANGED = "LIGHTING_STATE_CHANGED"
    EXTERNAL_WEATHER_UPDATED = "EXTERNAL_WEATHER_UPDATED"


class SystemAdminState(BaseModel):
    wanos_mqtt_connected: bool = False
    domoticz_mqtt_connected: bool = False
    ip_address: str = "0.0.0.0"
    os_boot_unix: Optional[int] = None
    app_boot_unix: Optional[int] = None
    automations_enabled: bool = False  # Master switch for the logic engine
    domoticz_integration_enabled: bool = False  # ⚡ Default OFF, controls whether we process Domoticz messages
    owm_integration_enabled: bool = False  # ⚡ Default OFF, controls OpenWeatherMap polling
    system_alert_msgs: list[str] = Field(default_factory=list)  # A list to hold multiple stacked alert messages


class Event(BaseModel):
    type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)


class SensorsState(BaseModel):
    outside_temp: Optional[float] = None
    outside_hum: Optional[int] = None
    sunrise_unix: Optional[int] = None
    sunset_unix: Optional[int] = None

    bathroom1_temp: Optional[float] = None
    bathroom1_hum: Optional[int] = None

    cinema_temp: Optional[float] = None
    cinema_hum: Optional[int] = None

    sauna_high_temp: Optional[float] = None
    sauna_high_hum: Optional[int] = None
    sauna_low_temp: Optional[float] = None
    sauna_low_hum: Optional[int] = None
    sauna_calc_temp: Optional[float] = None
    sauna_calc_hum: Optional[int] = None

    pc_power: Optional[float] = None
    pc_power_history: List[float] = Field(default_factory=list)
    pc_aux_power: Optional[float] = None
    pc_aux_power_history: List[float] = Field(default_factory=list)

    # Water metrics are analog sensor aggregations
    water_cold_liters: float = 0.0
    water_hot_liters: float = 0.0


class SaunaState(BaseModel):
    active: bool = False
    target_temp: Optional[float] = None
    max_temp: Optional[float] = None
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
    kwh_wh_ticks: int = 0
    douche_active: bool = False
    douche_start_time: Optional[int] = None
    douche_duration_secs: int = 0
    douche_water_liters: int = 0


class HardwareState(BaseModel):
    live_mode: bool = False
    simulations_enabled: bool = False  # Master switch for thesimulation engine
    safety_pin_active: bool = False
    sensor_errors: List[str] = Field(default_factory=list)

class SystemState(BaseModel):
    system: SystemAdminState = Field(default_factory=SystemAdminState)
    sensors: SensorsState = Field(default_factory=SensorsState)
    sauna: SaunaState = Field(default_factory=SaunaState)
    ir: IRState = Field(default_factory=IRState)
    metrics: MetricsState = Field(default_factory=MetricsState)
    hardware: HardwareState = Field(default_factory=HardwareState)

    # The generic "Peripheral Catch-all" dictionary for the Sorting Office
    devices: Dict[str, Any] = Field(default_factory=dict)

    # Allows the baseline validation rules parsed out of config_lab.yaml
    # to be passed seamlessly down to the web UI without strict compilation loop blocks.
    boot_seed: Optional[Any] = None