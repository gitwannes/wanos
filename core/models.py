# --- file: core/models.py ---
import math
from pydantic import BaseModel, Field, field_validator
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
    # C8: UI banner/bell dismiss → wanos.log info only (does not remove alert from state)
    ALERT_UI_DISMISSED = "ALERT_UI_DISMISSED"
    ALERT_CLEAR_NON_CRITICAL = "ALERT_CLEAR_NON_CRITICAL"  # Clear all info/success alerts
    ALERT_INJECTED = "ALERT_INJECTED"  # to test the teneral error message on top of the UI

    # Dynamic Hardware Bus Health Pings
    HARDWARE_BUS_HEALTH_UPDATED = "HARDWARE_BUS_HEALTH_UPDATED"
    ZWAVE_HEARTBEAT = "ZWAVE_HEARTBEAT"  # ⚡ Z-Wave JS UI Data Plane heartbeat

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
    IR_TIMER_ADJUSTED = "IR_TIMER_ADJUSTED"
    SAUNA_DOOR_GRACE_EXPIRED = "SAUNA_DOOR_GRACE_EXPIRED"  # Fired when the door remains open past the allowed threshold

    # IR Events
    IR_ON = "IR_ON"
    IR_OFF = "IR_OFF"
    IR_MODULATION_UPDATED = "IR_MODULATION_UPDATED"
    IR_TIMER_EXPIRED = "IR_TIMER_EXPIRED"

    # System Events
    SYSTEM_READY = "SYSTEM_READY"
    BACKEND_SHUTDOWN = "BACKEND_SHUTDOWN"
    CONFIG_UPDATED = "CONFIG_UPDATED"
    SYSTEM_METRICS_UPDATED = "SYSTEM_METRICS_UPDATED"

    # Toggles
    AUTOMATIONS_TOGGLED = "AUTOMATIONS_TOGGLED"  # Automation Rules
    SIMULATIONS_TOGGLED = "SIMULATIONS_TOGGLED"  # Simulation Physics Engine
    RFXCOM_TOGGLED = "RFXCOM_TOGGLED"  # Added to allow UI HTTP events to pass validation!
    OWM_TOGGLED = "OWM_TOGGLED"  # get OWM weather
    ZWAVE_TOGGLED = "ZWAVE_TOGGLED"  # Z-Wave integration toggle
    HUE_TOGGLED = "HUE_TOGGLED"  # Listen to local Hue Bridge messages
    EPSON_TOGGLED = "EPSON_TOGGLED"  # Block/allow Epson projector network commands
    LG_TOGGLED = "LG_TOGGLED"  # Block/allow LG webOS TV bridge (G16)
    SONOS_TOGGLED = "SONOS_TOGGLED"  # Block/allow local Sonos API control
    ONKYO_TOGGLED = "ONKYO_TOGGLED"  # Block/allow Onkyo TCP streaming
    LCD_TOGGLED = "LCD_TOGGLED"  # Block/allow MQTT LCD screen payloads

    # Integration Specific Commands
    SONOS_COMMAND = "SONOS_COMMAND"  # Rich payloads for automations (volume, station uri)

    # Physical Hardware Isolation Toggles
    SHT11_TOGGLED = "SHT11_TOGGLED"
    GPIO_INPUT_TOGGLED = "GPIO_INPUT_TOGGLED"
    GPIO_OUTPUT_TOGGLED = "GPIO_OUTPUT_TOGGLED"

    SYSTEM_SWEEP_REQUESTED = "SYSTEM_SWEEP_REQUESTED"  # Manual Time & Environment Audit
    CONFIG_RELOAD_REQUESTED = "CONFIG_RELOAD_REQUESTED"  # Hot-reload config.yaml configuration
    ZWAVE_DISCOVERY = "ZWAVE_DISCOVERY"  # Catch unmapped Z-Wave nodes

    # External Events
    HUB_STATE_CHANGED = "HUB_STATE_CHANGED"
    # B10E: sun-cycle refresh (was EXTERNAL_WEATHER_UPDATED)
    SUNRISE_SUNSET_UPDATE = "SUNRISE_SUNSET_UPDATE"
    # Legacy bus token — same handler as SUNRISE_SUNSET_UPDATE until emitters soak
    EXTERNAL_WEATHER_UPDATED = "EXTERNAL_WEATHER_UPDATED"
    # C25: last OWM climate poll snapshot (clouds/wind/score) for Admin + RAM
    OWM_CLIMATE_SNAPSHOT = "OWM_CLIMATE_SNAPSHOT"

    # Environment Schedule Events
    # Blinds: clamped daylight window (≠ raw sunrise/sunset — see logic/environment_scheduler.py).
    BLINDS_OPEN_TRIGGER = "BLINDS_OPEN_TRIGGER"
    BLINDS_CLOSE_TRIGGER = "BLINDS_CLOSE_TRIGGER"
    # Twilight window edges (canonical names). TWILIGHT_* aliases / SCHEDULE_EVENT_ALIASES
    # removed with B10B migrator delete (D1, 2026-08-10).
    MORNING_ON_TRIGGER = "MORNING_ON_TRIGGER"      # configured morning-on clock
    SUNRISE_TRIGGER = "SUNRISE_TRIGGER"            # end morning twilight (= sunrise); NOT blinds open
    SUNSET_TRIGGER = "SUNSET_TRIGGER"              # start evening twilight (= sunset); NOT blinds close
    EVENING_OFF_TRIGGER = "EVENING_OFF_TRIGGER"    # configured evening-off clock

    # Timer Events
    TIMER_SCHEDULED = "TIMER_SCHEDULED"
    TIMER_CANCELLED = "TIMER_CANCELLED"
    LIGHT_TIMER_EXPIRED = "LIGHT_TIMER_EXPIRED"
    # B14: Set for/after end (or deferred start) for a device action.
    AUTOMATION_TIMED_SET_EXPIRED = "AUTOMATION_TIMED_SET_EXPIRED"
    # B14 H1: sustained-for timer reached; replay wake so Compare can pass.
    AUTOMATION_SUSTAINED_READY = "AUTOMATION_SUSTAINED_READY"
    NVRAM_FLUSH_TRIGGER = "NVRAM_FLUSH_TRIGGER"  # ⚡ 5-minute heartbeat to flush counters to disk


class SystemAdminState(BaseModel):
    version_major: str = "v0.0"  # Exposes major layout semantic configuration strings to dashboard layout
    version_full: str = "v0.0-build_unknown"  # Exposes consolidated full runtime version mapping strings to admin layout
    wanos_mqtt_connected: bool = False
    rfxcom_connected: bool = False  # Tracks native USB RFX transceiver health
    rfxcom_integration_enabled: bool = False  # Switch to block/allow native RFXCOM transmission/reception
    zwave_hardware_connected: bool = False  # Tracks physical USB stick presence
    zwave_web_alive: bool = False  # ⚡ Tracks if Z-Wave JS UI web server answers on port 8091 (Control Plane)
    zwave_data_alive: bool = False  # ⚡ Tracks if Z-Wave JS UI is broadcasting data (Data Plane)
    last_zwave_heartbeat_unix: Optional[int] = None  # ⚡ Tracks the Z-Wave JS UI MQTT data stream staleness
    zwave_integration_enabled: bool = False  # Switch to block/allow Z-Wave processing
    hue_connected: bool = False  # Tracks local Hue API v2 connection
    hue_integration_enabled: bool = False  # Switch to block/allow Hue API v2 bidirectional commands
    epson_connected: bool = False  # Tracks physical TCP availability of the Epson Projector
    epson_integration_enabled: bool = False  # Master UI switch to block/allow Epson commands
    lg_connected: bool = False  # LG bridge healthy (independent of TV power ON/OFF)
    lg_integration_enabled: bool = False  # Master UI switch for LG webOS commands (G16)
    sonos_integration_enabled: bool = False  # Master UI switch to block/allow Sonos commands
    onkyo_connected: bool = False  # Tracks physical TCP availability of Onkyo Receivers
    onkyo_integration_enabled: bool = False  # Master UI switch to block/allow Onkyo Receivers
    ip_address: str = "0.0.0.0"
    os_boot_unix: Optional[int] = None
    app_boot_unix: Optional[int] = None
    automations_enabled: bool = False  # Master switch for the logic engine
    owm_integration_enabled: bool = False  # Default OFF, controls OpenWeatherMap polling
    lcd_integration_enabled: bool = False  # Master UI switch to block/allow LCD MQTT publishes
    system_alert_msgs: list[dict[str, Any]] = Field(default_factory=list)  # {id, level, message, timestamp, produced_at, count}; level: critical|error|warning|success|info
    active_timers: list[str] = Field(default_factory=list)  # Glass-box exposure of currently ticking timers
    native_rfx_devices: list[dict] = Field(default_factory=list)  # Pushed dynamically to UI panel
    # B10B: Explorer dashboard buttons from events: catalog
    # (show ∧ enabled-listener). Shape: {id, name, require_confirmation}.
    dashboard_events: list[dict[str, Any]] = Field(default_factory=list)
    hidden_explorer_idxs: list[int] = Field(default_factory=list)  # Devices explicitly hidden from Device Explorer
    hue_presets: dict[str, Any] = Field(default_factory=dict)  # UI Button Configurations pushed from YAML
    sonos_stations: dict[str, str] = Field(default_factory=dict)  # TuneIn station key → URI (Blocky / Explorer)
    lg_apps: dict[str, str] = Field(default_factory=dict)  # G16 Blockly catalog key → display label
    zwave_mapped: dict[int, str] = Field(default_factory=dict)  # ⚡ Existing config passed to UI to prevent overwrites
    zwave_inbox: dict[str, dict[str, Any]] = Field(default_factory=dict)  # ⚡ Transient inbox for unmapped devices
    zwave_usb_path: str = ""  # ⚡ Passed to UI for YAML generation
    # B23: saved automation/event YAML not yet applied to the rules engine.
    rules_activation_pending: dict[str, Any] = Field(default_factory=dict)
    # Auto-off timers + product types (Automations device table; same shape as GET /api/auto-off-timer).
    auto_off_timer: dict[str, Any] = Field(default_factory=dict)
    # C12: blinds travel times for Explorer FE ui-lock (mirrors hub proportional debounce).
    blinds_default_travel_time_secs: int = 35
    blinds_travel_times: dict[str, int] = Field(default_factory=dict)


class Event(BaseModel):
    type: Union[EventType, str]
    payload: Dict[str, Any] = Field(default_factory=dict)


class SaunaSetpointPayload(BaseModel):
    """Validated target for SAUNA_SETPOINT_CHANGED (handler-owned, not on Event envelope)."""

    target: float

    @field_validator("target", mode="before")
    @classmethod
    def coerce_finite_target(cls, v: Any) -> float:
        try:
            val = float(v)
        except (TypeError, ValueError):
            raise ValueError("non-numeric target")
        if not math.isfinite(val):
            raise ValueError("non-finite target")
        return val


class SensorsState(BaseModel):
    outside_temp: Optional[float] = None
    outside_hum: Optional[int] = None
    sunrise_unix: Optional[int] = None
    sunset_unix: Optional[int] = None

    # C25: last OWM Current 2.5 climate-poll snapshot (Admin Outside weather)
    owm_clouds: Optional[float] = None
    owm_wind_ms: Optional[float] = None
    owm_weather_summary: Optional[str] = None
    owm_raining: Optional[bool] = None
    owm_dew_likelihood: Optional[int] = None
    owm_last_poll_unix: Optional[int] = None

    env_schedule_blinds_open_unix: Optional[int] = None
    env_schedule_blinds_close_unix: Optional[int] = None
    env_schedule_twilight_evening_on_unix: Optional[int] = None
    env_schedule_twilight_evening_off_unix: Optional[int] = None
    env_schedule_twilight_morning_on_unix: Optional[int] = None
    env_schedule_twilight_morning_off_unix: Optional[int] = None

    # ⚡ VIRTUAL COMPOSITE Sauna data (Preserved Exception)
    sauna_calc_temp: Optional[float] = None
    sauna_calc_hum: Optional[int] = None

    # ⚡ UNIVERSAL HISTORY TRACKER
    # Completely replaces hardcoded power/temperature history arrays.
    # Automatically manages rolling windows for ANY idx that reports values.
    sensor_history: Dict[int, List[float]] = Field(default_factory=dict)

    water_cold_liters: float = 0.0
    water_hot_liters: float = 0.0


# Canonical zero modulation map for the three sauna heater phases.
ZERO_PHASES_PWM: Dict[str, int] = {"U": 0, "V": 0, "W": 0}


def normalize_phases_pwm(raw: Any) -> Dict[str, int]:
    """
    Coerce phase modulation to the canonical {"U","V","W"} dict.

    Historical paths and MQTT examples used a list [U, V, W]; actuators and
    power analytics call .get on phases_pwm and crash if a list leaks in.
    """
    if isinstance(raw, dict):
        try:
            return {
                "U": int(raw.get("U", 0) or 0),
                "V": int(raw.get("V", 0) or 0),
                "W": int(raw.get("W", 0) or 0),
            }
        except (TypeError, ValueError):
            return dict(ZERO_PHASES_PWM)
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        try:
            return {"U": int(raw[0] or 0), "V": int(raw[1] or 0), "W": int(raw[2] or 0)}
        except (TypeError, ValueError):
            return dict(ZERO_PHASES_PWM)
    return dict(ZERO_PHASES_PWM)


class SaunaState(BaseModel):
    active: bool = False
    target_temp: Optional[float] = None
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    hold_mode: str = "nohold"
    modulation_pwm: int = 0
    phases_pwm: Dict[str, int] = Field(default_factory=lambda: dict(ZERO_PHASES_PWM))
    fireorder: str = "--"
    session_start_time: Optional[int] = None
    session_end_time: Optional[int] = None
    light_color: str = "#FFD180"  # Warm White Baseline
    # Screen1 mirror (same compose as MQTT wanos/lcd/screen1). Blank → WISC shows standby.
    lcd_line1: str = ""
    lcd_line2: str = ""
    lcd_text: str = ""  # Legacy one-liner; unused by WISC LCD preview (kept for older clients)
    is_paused: bool = False  # Track safety cutout state independently from manual overrides
    last_light_temp: Optional[float] = None  # Enforces a 1.0°C quantization throttle to prevent Zigbee mesh DDoS storms
    absolute_cutoff_unix: Optional[int] = None  # ⚡ EN 60335-2-53 hard 6-hour limit epoch wall
    last_heartbeat_unix: Optional[int] = None  # ⚡ Active SHT11 bus reception timestamp marker


class IRState(BaseModel):
    active: bool = False
    modulation_pwm: int = 0
    frequency: int = 0
    session_start_time: Optional[int] = None
    session_end_time: Optional[int] = None


class SaunaSessionRecord(BaseModel):
    """Structured Pydantic model for SQLite session storage validation"""
    session_id: Optional[int] = None
    start_timestamp: int
    total_runtime_secs: int
    runtime_u_secs: int
    runtime_v_secs: int
    runtime_w_secs: int
    temp_start: float
    temp_end: float
    temp_min: float
    temp_max: float
    temp_avg: float
    temp_outside_start: Optional[float] = None
    hum_start: int
    hum_end: int
    hum_min: int
    hum_max: int
    hum_avg: int
    mod_system_min: float
    mod_system_max: float
    mod_system_avg: float
    mod_u_min: float
    mod_u_max: float
    mod_u_avg: float
    mod_v_min: float
    mod_v_max: float
    mod_v_avg: float
    mod_w_min: float
    mod_w_max: float
    mod_w_avg: float
    energy_real_wh: float
    energy_calc_wh: float
    extracted_p_u: float
    extracted_p_v: float
    extracted_p_w: float
    # Session-constant PID gains + frozen fire order (not duplicated on sample rows).
    kp: Optional[float] = None
    ki: Optional[float] = None
    kd: Optional[float] = None
    fireorder: Optional[str] = None
    audit_baseline_w_u: Optional[float] = None
    audit_measured_w_u: Optional[float] = None
    audit_new_w_u: Optional[float] = None
    audit_baseline_w_v: Optional[float] = None
    audit_measured_w_v: Optional[float] = None
    audit_new_w_v: Optional[float] = None
    audit_baseline_w_w: Optional[float] = None
    audit_measured_w_w: Optional[float] = None
    audit_new_w_w: Optional[float] = None


class IrSessionRecord(BaseModel):
    """Structured Pydantic model for SQLite IR session storage validation"""
    session_id: Optional[int] = None
    start_timestamp: int
    total_runtime_secs: int
    temp_start: float
    temp_end: float
    temp_outside_start: Optional[float] = None
    hum_start: int
    hum_end: int
    mod_min: float
    mod_max: float
    mod_avg: float
    energy_real_wh: float
    energy_calc_wh: float
    audit_baseline_w_ir: Optional[float] = None
    audit_measured_w_ir: Optional[float] = None
    audit_new_w_ir: Optional[float] = None


class MetricsState(BaseModel):
    kwh_wh_ticks: int = 0
    douche_active: bool = False
    douche_start_time: Optional[int] = None
    douche_duration_secs: int = 0
    douche_water_liters: int = 0

    # ⚡ EPHEMERAL MOTION LEDGER
    # Tracks the number of times 75xxx motion sensors fire per boot session.
    # Data lives purely in RAM and intentionally does not survive reboots.
    motion_triggers: Dict[int, int] = Field(default_factory=dict)

    # ⚡ DYNAMIC POWER DISAGGREGATION TRACKERS
    # Retains isolated variables in RAM for frontend real-time reactivity
    p_leak_baseline_watts: float = 0.0
    p_elements_real_watts: float = 0.0
    p_elements_calc_watts: float = 0.0
    r_th_insulation_coefficient: Optional[float] = None
    # Optimistically initialized to factory nominals until the background matrix proves degradation
    extracted_p_u: Optional[float] = 3500.0
    extracted_p_v: Optional[float] = 3500.0
    extracted_p_w: Optional[float] = 2000.0

    # ⚡ LIVE ENERGY ACCUMULATORS
    running_energy_real_wh: float = 0.0
    running_energy_calc_wh: float = 0.0
    total_energy_real_wh: float = 0.0  # Element-only Wh since reboot (analytics; not meter total)
    meter_total_kwh: float = 0.0  # Absolute house meter kWh (NVRAM 11001 Wh / 1000)

    # Bathroom water day totals (liters; from sensor_history day buckets)
    water_cold_today_l: float = 0.0
    water_hot_today_l: float = 0.0

    # ⚡ HISTORICAL READBACK CACHES
    last_sauna_session: Optional[Dict[str, Any]] = None
    last_ir_session: Optional[Dict[str, Any]] = None
    session_count_sauna: int = 0
    session_count_ir: int = 0

    # ⚡ DEVICE INSIGHTS
    # Persisted ledger for UI analysis (last changed timestamp, daily switches, averages)
    device_insights: Dict[int, Dict[str, Any]] = Field(default_factory=dict)


class HardwareState(BaseModel):
    sht11_connected: bool = False
    sht11_enabled: bool = False
    gpio_input_connected: bool = False
    gpio_input_enabled: bool = False
    gpio_output_connected: bool = False
    gpio_output_enabled: bool = False

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

    # ---------------------------------------------------------------------
    # LCD-specific door duration tracking (WISC parity)
    # ---------------------------------------------------------------------
    # Tracks open/close durations for the configured door sensors so the
    # LCD Pi can render the "plz close sdoor dd:hh:mm:ss" warnings.
    #
    # Updated on DOOR_CHANGED events in core/event_handlers/hub_handlers.py.
    door_sauna_open_since_unix: Optional[int] = None
    door_bathroom_open_since_unix: Optional[int] = None
    door_sauna_closed_since_unix: Optional[int] = None
    door_bathroom_closed_since_unix: Optional[int] = None

    # The dynamic device registry. Maps IDXs to a dictionary containing
    # {name: str, type: str, origin: str, entity_id: str, ...}
    # entity_id is assigned once by core/entity_registry.py and frozen across renames.
    # Display names always come from device_metadata[idx]["name"] (no parallel dashboard_map).
    device_metadata: Dict[int, Dict[str, Any]] = Field(default_factory=dict)

    # Allows the baseline validation rules parsed out of config_lab.yaml
    # to be passed seamlessly down to the web UI without strict compilation loop blocks.
    boot_seed: Optional[Any] = None


def device_name(state: "SystemState", idx: Optional[int], default: str = "Unknown") -> str:
    """Resolve display name from device_metadata (single source of truth)."""
    if idx is None:
        return default
    meta = (state.device_metadata or {}).get(idx)
    if isinstance(meta, dict):
        name = meta.get("name")
        if name:
            return str(name)
    return default


def device_entity_id(state: "SystemState", idx: Optional[int]) -> Optional[str]:
    """idx → entity_id from device_metadata (None if missing)."""
    if idx is None:
        return None
    meta = (state.device_metadata or {}).get(idx)
    if isinstance(meta, dict):
        eid = meta.get("entity_id")
        return str(eid) if eid else None
    return None


def format_device_ref(state: "SystemState", idx: Optional[int]) -> str:
    """
    Operator-facing device ref for logs: entity_id (name, idx N).
    Thin-meta fallbacks when entity_id and/or name are missing.
    """
    if idx is None:
        return "unknown (idx —)"
    eid = device_entity_id(state, idx)
    name = device_name(state, idx, "")
    if eid and name:
        return f"{eid} ({name}, idx {idx})"
    if eid:
        return f"{eid} (idx {idx})"
    if name:
        return f"idx {idx} ({name})"
    return f"idx {idx}"