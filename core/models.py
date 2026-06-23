# --- file: core/models.py ---
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List, Union
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
    ALERT_CLEAR_NON_CRITICAL = "ALERT_CLEAR_NON_CRITICAL"  # ⚡ Clear all info/success alerts
    ALERT_INJECTED = "ALERT_INJECTED"  # to test the teneral error message on top of the UI

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
    RFXCOM_TOGGLED = "RFXCOM_TOGGLED"  # ⚡ Added to allow UI HTTP events to pass validation!
    OWM_TOGGLED = "OWM_TOGGLED"  # get OWM weather
    HUE_TOGGLED = "HUE_TOGGLED"  # ⚡ Listen to local Hue Bridge messages
    EPSON_TOGGLED = "EPSON_TOGGLED"  # ⚡ Block/allow Epson projector network commands
    SYSTEM_SWEEP_REQUESTED = "SYSTEM_SWEEP_REQUESTED"  # Manual Time & Environment Audit
    CONFIG_RELOAD_REQUESTED = "CONFIG_RELOAD_REQUESTED"  # Hot-reload config.yaml configuration

    # External Events
    HUB_STATE_CHANGED = "HUB_STATE_CHANGED"
    LIGHTING_STATE_CHANGED = "LIGHTING_STATE_CHANGED"
    EXTERNAL_WEATHER_UPDATED = "EXTERNAL_WEATHER_UPDATED"

    # 🌍 Environment Schedule Events
    BLINDS_OPEN_TRIGGER = "BLINDS_OPEN_TRIGGER"
    BLINDS_CLOSE_TRIGGER = "BLINDS_CLOSE_TRIGGER"
    TWILIGHT_EVENING_ON_TRIGGER = "TWILIGHT_EVENING_ON_TRIGGER"
    TWILIGHT_EVENING_OFF_TRIGGER = "TWILIGHT_EVENING_OFF_TRIGGER"
    TWILIGHT_MORNING_ON_TRIGGER = "TWILIGHT_MORNING_ON_TRIGGER"
    TWILIGHT_MORNING_OFF_TRIGGER = "TWILIGHT_MORNING_OFF_TRIGGER"

    # Timer & Generic Engine Events
    TIMER_SCHEDULED = "TIMER_SCHEDULED"
    TIMER_CANCELLED = "TIMER_CANCELLED"
    LIGHT_TIMER_EXPIRED = "LIGHT_TIMER_EXPIRED"

class SystemAdminState(BaseModel):
    version_major: str = "v0.0"  # ⚡ Exposes major layout semantic configuration strings to dashboard layout
    version_full: str = "v0.0-build_unknown"  # ⚡ Exposes consolidated full runtime version mapping strings to admin layout
    wanos_mqtt_connected: bool = False
    domoticz_mqtt_connected: bool = False
    rfxcom_connected: bool = False  # ⚡ Tracks native USB RFX transceiver health
    rfxcom_integration_enabled: bool = False  # ⚡ Switch to block/allow native RFXCOM transmission/reception
    hue_connected: bool = False  # ⚡ Tracks local Hue API v2 connection
    hue_integration_enabled: bool = False  # ⚡ Switch to block/allow Hue API v2 bidirectional commands
    epson_connected: bool = False  # ⚡ Tracks physical TCP availability of the Epson Projector
    epson_integration_enabled: bool = False  # ⚡ Master UI switch to block/allow Epson commands
    ip_address: str = "0.0.0.0"
    os_boot_unix: Optional[int] = None
    app_boot_unix: Optional[int] = None
    automations_enabled: bool = False  # Master switch for the logic engine
    domoticz_integration_enabled: bool = False  # ⚡ Default OFF, controls whether we process Domoticz messages
    owm_integration_enabled: bool = False  # ⚡ Default OFF, controls OpenWeatherMap polling
    system_alert_msgs: list[dict[str, Any]] = Field(default_factory=list)  # ⚡ Upgraded to structured dicts {id, level, message, timestamp, count}
    active_timers: list[str] = Field(default_factory=list)  # Glass-box exposure of currently ticking timers
    native_rfx_devices: list[dict] = Field(default_factory=list)  # ⚡ Pushed dynamically to UI panel
    available_scenes: list[dict[str, str]] = Field(default_factory=list)  # ⚡ Extracted stateless triggers for UI
    hidden_explorer_idxs: list[int] = Field(default_factory=list)  # ⚡ Devices explicitly hidden from Device Explorer


class Event(BaseModel):
    type: Union[EventType, str]  # Let custom scene strings live in the core event bus
    payload: Dict[str, Any] = Field(default_factory=dict)


class SensorsState(BaseModel):
    outside_temp: Optional[float] = None
    outside_hum: Optional[int] = None
    sunrise_unix: Optional[int] = None
    sunset_unix: Optional[int] = None

    # 🌍 Environmental Daily Target Epochs
    env_schedule_blinds_open_unix: Optional[int] = None
    env_schedule_blinds_close_unix: Optional[int] = None
    env_schedule_twilight_evening_on_unix: Optional[int] = None
    env_schedule_twilight_evening_off_unix: Optional[int] = None
    env_schedule_twilight_morning_on_unix: Optional[int] = None
    env_schedule_twilight_morning_off_unix: Optional[int] = None

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
    devices: Dict[int, Any] = Field(default_factory=dict)

    # Dictionary loaded from config.yaml to map numeric IDXs back to semantic names for the UI.
    # The frontend parses this on boot.
    dashboard_map: Dict[int, str] = Field(default_factory=dict)

    # ⚡ The dynamic device registry. Maps IDXs to a dictionary containing {name: str, type: str}
    # to allow the frontend to know exactly how to render a dynamic list element.
    device_metadata: Dict[int, Dict[str, Any]] = Field(default_factory=dict)

    # Allows the baseline validation rules parsed out of config_lab.yaml
    # to be passed seamlessly down to the web UI without strict compilation loop blocks.
    boot_seed: Optional[Any] = None