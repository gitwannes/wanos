# --- file: core/config.py ---
import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, Dict, List, Union, Any, Tuple
from dotenv import load_dotenv

from core.schedule_events import (  # noqa: F401 — re-export for existing imports
    EVENT_FAMILY_TO_ON_OFF,
    SCHEDULE_EVENT_ALIASES,
    SCHEDULE_WINDOW_EDGES,
    canonicalize_schedule_event,
)


class WeatherConfig(BaseModel):
    idx: int
    name: str
    location: str
    poll_interval_mins: int
    # Local wall-clock hour for the once-daily sun/schedule refresh (default 03:00).
    sun_refresh_hour: int = 3
    api_key: Optional[str] = None


class MQTTConfig(BaseModel):
    broker_host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class WanosConfig(BaseModel):
    """Internal broker configuration block."""
    mqtt: MQTTConfig


class GPIOInputNode(BaseModel):
    idx: Optional[int] = None
    name: Optional[str] = None
    pin: int
    type: str  # "door", "fluid", "energy"


class SHT11SensorNode(BaseModel):
    idx: int
    name: str
    pin_d: int
    pin_c: int


class PinMappingConfig(BaseModel):
    # ⚡ Explicit Semantic Hardware Keys directly mapping to config_hardware.yaml
    safety_gpio: int
    ir_relais: int
    sauna_relais_phase_U: int
    sauna_relais_phase_V: int
    sauna_relais_phase_W: int


class SaunaRuntimeConfig(BaseModel):
    default_sauna_setpoint: int
    min_temp: int
    max_temp: int
    kp: float
    ki: float
    kd: float
    default_timer: int
    vent_delay_mins: int
    vent_run_mins: int
    timer_offset_temp: float


class IRRuntimeConfig(BaseModel):
    min_time_mins: int
    max_time_mins: int
    default_ir_modulation: int


class BathroomConfig(BaseModel):
    vent_on_humidity: int
    vent_off_humidity: int
    vent_min_runtime_mins: int


class LightingConfig(BaseModel):
    default_auto_off_minutes: int = 300
    managed_lights: List[str] = Field(default_factory=list)
    auto_off_delays: Dict[str, int] = Field(default_factory=dict)

    @field_validator("auto_off_delays", mode="before")
    @classmethod
    def coerce_delay_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {str(k): int(v) for k, v in value.items()}


class BlindsConfig(BaseModel):
    default_travel_time_secs: int = 35
    travel_times: Dict[str, int] = Field(default_factory=dict)

    @field_validator("travel_times", mode="before")
    @classmethod
    def coerce_travel_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {str(k): int(v) for k, v in value.items()}


class BlindsScheduleConfig(BaseModel):
    morning_open_earliest: str
    morning_open_latest: str
    evening_close_earliest: str
    evening_close_latest: str


class TwilightScheduleConfig(BaseModel):
    evening_off_time: str
    morning_on_time: str


class EnvironmentalScheduleConfig(BaseModel):
    blinds: BlindsScheduleConfig
    twilight: TwilightScheduleConfig


class RFXComSettings(BaseModel):
    """Configuration for the physical USB RFXCOM transceiver."""
    serial_port: str


class NativeRFXConfig(BaseModel):
    name: str
    virtual_idx: int
    protocol: str
    on_id: str
    off_id: str


class TriggerConfig(BaseModel):
    """Automation trigger — device refs use entity_id only (no numeric idx)."""
    model_config = ConfigDict(extra="forbid")

    entity_id: Optional[str] = None
    state: Optional[str] = None
    event: Optional[str] = None

    @field_validator("state", mode="before")
    @classmethod
    def _coerce_state(cls, v: Any) -> Any:
        # YAML 1.1: unquoted ON/OFF/Yes/No become bool — restore device states.
        if isinstance(v, bool):
            return "ON" if v else "OFF"
        return v


class ConditionConfig(BaseModel):
    """Automation condition — device refs use entity_id only (no numeric idx)."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str
    entity_id: Optional[str] = None
    condition_is: str = Field(alias="is")

    @field_validator("condition_is", mode="before")
    @classmethod
    def _coerce_is(cls, v: Any) -> Any:
        if isinstance(v, bool):
            return "ON" if v else "OFF"
        return v


class ActionConfig(BaseModel):
    """Automation action — device refs use entity_id only (no numeric idx)."""
    model_config = ConfigDict(extra="forbid")

    entity_id: Optional[str] = None
    state: Optional[str] = None
    event: Optional[str] = None
    target: Optional[str] = None
    scene: Optional[str] = None
    preset: Optional[str] = None
    bri: Optional[int] = None
    xy: Optional[List[float]] = None
    volume: Optional[int] = None  # Sonos
    station: Optional[str] = None  # Sonos

    @field_validator("state", mode="before")
    @classmethod
    def _coerce_state(cls, v: Any) -> Any:
        if isinstance(v, bool):
            return "ON" if v else "OFF"
        return v

class AutomationRuleConfig(BaseModel):
    # Stable per-rule identity used by Blocky CRUD.
    # Expanded X1 engine clones use runtime-only ids like "<id>#on"/"<id>#off".
    id: Optional[str] = None

    name: str
    scene: bool = False  # ⚡ Expose this automation rule as a manually triggerable scene in the UI
    require_confirmation: bool = False  # ⚡ Prevents accidental misclicks by requiring a modal confirmation
    trigger: Union[TriggerConfig, List[TriggerConfig]]
    conditions: Optional[List[ConditionConfig]] = None
    actions: List[ActionConfig]


def _expand_branched_automations_for_engine(raw_automations: Any) -> List[dict]:
    """
    Dual-read expand for the engine (Phase 6A):
    v2 cases, Y1 on/off, and flat → flat AutomationRuleConfig list.
    """
    from core.automations_schema_v2 import expand_automations_for_engine
    return expand_automations_for_engine(raw_automations)


def _srgb_channel_to_linear(c: float) -> float:
    return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else (c / 12.92)


def rgb_bytes_to_xy(r: int, g: int, b: int) -> List[float]:
    """
    sRGB 0-255 -> CIE xy using the same Wide-RGB / Hue matrix as frontend hexToXY.
    """
    rl = _srgb_channel_to_linear(max(0, min(255, int(r))) / 255.0)
    gl = _srgb_channel_to_linear(max(0, min(255, int(g))) / 255.0)
    bl = _srgb_channel_to_linear(max(0, min(255, int(b))) / 255.0)

    X = rl * 0.664511 + gl * 0.154324 + bl * 0.162028
    Y = rl * 0.283881 + gl * 0.668433 + bl * 0.047685
    Z = rl * 0.000088 + gl * 0.072310 + bl * 0.986039
    s = X + Y + Z
    if s <= 0:
        return [0.3127, 0.3290]
    return [round(X / s, 4), round(Y / s, 4)]


def _parse_preset_rgb(value: Any) -> Tuple[int, int, int]:
    """
    Accept:
      - "#FF8C00" / "FF8C00"
      - ["#FF8C00"]
      - [255, 140, 0]
    """
    if isinstance(value, str):
        h = value.strip().lstrip("#")
        if len(h) != 6:
            raise ValueError(f"rgb hex must be 6 digits, got {value!r}")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], str):
            return _parse_preset_rgb(value[0])
        if len(value) == 3:
            try:
                r, g, b = (int(value[0]), int(value[1]), int(value[2]))
            except (TypeError, ValueError) as e:
                raise ValueError(f"rgb triple must be three integers, got {value!r}") from e
            for c in (r, g, b):
                if c < 0 or c > 255:
                    raise ValueError(f"rgb channel out of range 0-255: {value!r}")
            return r, g, b

    raise ValueError(
        "rgb must be \"#RRGGBB\", [\"#RRGGBB\"], or [r, g, b] with 0-255 ints"
    )


class HuePresetConfig(BaseModel):
    """
    Hue scene/button preset. Author with xy and/or rgb; runtime always has xy.

    Accepted colour forms (exactly one of xy or rgb):
      xy: [0.5958, 0.3881]
      rgb: "#FF8C00"
      rgb: [255, 140, 0]
    """
    name: str
    bri: int
    xy: Optional[List[float]] = None
    rgb: Optional[Union[str, List[Any]]] = None

    @model_validator(mode="after")
    def _normalize_colour(self) -> "HuePresetConfig":
        has_xy = self.xy is not None
        has_rgb = self.rgb is not None
        if has_xy and has_rgb:
            raise ValueError("preset must set only one of xy or rgb")
        if not has_xy and not has_rgb:
            raise ValueError("preset requires xy or rgb")

        if has_rgb:
            r, g, b = _parse_preset_rgb(self.rgb)
            self.xy = rgb_bytes_to_xy(r, g, b)
            self.rgb = f"#{r:02X}{g:02X}{b:02X}"
        else:
            if not isinstance(self.xy, list) or len(self.xy) != 2:
                raise ValueError("xy must be [x, y]")
            self.xy = [float(self.xy[0]), float(self.xy[1])]
            if self.xy[0] + self.xy[1] > 1.0 + 1e-6:
                raise ValueError(f"invalid CIE xy (x+y must be <= 1): {self.xy}")

        return self


class HueConfig(BaseModel):
    bridge_ip: str
    application_key: Optional[str] = None
    device_map: Dict[int, str] = Field(default_factory=dict)
    group_map: Dict[int, str] = Field(default_factory=dict)
    scene_map: Dict[str, str] = Field(default_factory=dict)
    presets: Dict[str, HuePresetConfig] = Field(default_factory=dict)


class EpsonConfig(BaseModel):
    ip_address: str


class SonosDeviceNode(BaseModel):
    ip: str
    name: str


class SonosConfig(BaseModel):
    max_volume: int = 70
    device_map: Dict[int, SonosDeviceNode] = Field(default_factory=dict)
    stations: Dict[str, str] = Field(default_factory=dict)


class OnkyoDeviceNode(BaseModel):
    ip: str
    name: str
    legacy: bool = False  # ⚡ Flag to enable the legacy 2012 malformed packet dialect and strict TCP pacing


class OnkyoConfig(BaseModel):
    max_volume: int = 60
    device_map: Dict[int, OnkyoDeviceNode] = Field(default_factory=dict)


class ZwaveConfig(BaseModel):
    """Configuration mapping for the Z-Wave JS UI hardware stick and node map."""
    model_config = ConfigDict(extra="ignore")

    usb_path: str
    mqtt_prefix: str = "zwave"  # ⚡ Global prefix for dynamic MQTT routing
    device_map: Dict[int, str] = Field(default_factory=dict)


class AuthConfig(BaseModel):
    shared_pin: str
    admin_pin: str
    user_pin: str
    secret_key: str
    cookie_expiry_days: int
    ban_timeout_mins: int
    user_token: str
    kiosk_token: str


class HardwareLinksConfig(BaseModel):
    """Maps switches to linked hardware (e.g. power meters flushed to 0W on OFF). Keys/values are entity_ids."""
    power_meters: Dict[str, str] = Field(default_factory=dict)

    @field_validator("power_meters", mode="before")
    @classmethod
    def coerce_str_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {str(k): str(v) for k, v in value.items()}


class HistoryRetentionConfig(BaseModel):
    hires_days: int = 7
    hourly_days: int = 31
    daily_days: int = 365


class HistorySampleConfig(BaseModel):
    kwh_step_wh: float = 100.0
    water_step_l: float = 1.0
    zwave_min_interval_secs: float = 60.0
    climate_temp_deadband: float = 0.5
    climate_hum_deadband: float = 2.0
    climate_max_interval_secs: float = 300.0


class HistoryConfig(BaseModel):
    """Sensor / utility time-series history (see docs/sensor_history.md)."""
    timezone: str = "Europe/Brussels"
    retention: HistoryRetentionConfig = Field(default_factory=HistoryRetentionConfig)
    sample: HistorySampleConfig = Field(default_factory=HistorySampleConfig)
    tracked_entities: List[str] = Field(default_factory=lambda: [
        "sensor.energy.kwh_meter",
        "sensor.fluid.koud_water",
        "sensor.fluid.warm_water",
        "sensor.power.pc_power",
        "sensor.power.pc_monitors_power",
    ])


class AppConfig(BaseModel):
    version: str
    wanos: WanosConfig
    rfxcom: Optional[RFXComSettings] = None
    hue: Optional[HueConfig] = None
    epson: Optional[EpsonConfig] = None
    sonos: Optional[SonosConfig] = None
    onkyo: Optional[OnkyoConfig] = None
    zwave: Optional[ZwaveConfig] = None
    deviceexplorer_hide: List[str] = Field(default_factory=list)  # entity_ids soft-hidden from Explorer/History/Blocky pickers
    hardware_links: Optional[HardwareLinksConfig] = None
    history: HistoryConfig = Field(default_factory=HistoryConfig)
    auth: AuthConfig
    pins: PinMappingConfig
    gpio_inputs: Dict[str, GPIOInputNode]
    sht11_sensors: Dict[str, SHT11SensorNode]
    sauna: SaunaRuntimeConfig
    ir: IRRuntimeConfig
    bathroom1: BathroomConfig
    lighting: LightingConfig
    blinds: Optional[BlindsConfig] = None
    environmental_schedule: Optional[EnvironmentalScheduleConfig] = None
    weather: WeatherConfig
    boot_seed: Dict[Union[int, str], Any] = {}
    native_rfx: List[NativeRFXConfig] = Field(default_factory=list)
    automations: List[AutomationRuleConfig] = Field(default_factory=list)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / ".env"
    runtime_yaml_path = Path(config_path) if Path(config_path).is_absolute() else BASE_DIR / config_path
    hardware_yaml_path = BASE_DIR / "config_hardware.yaml"
    lab_yaml_path = BASE_DIR / "config_lab.yaml"
    hue_yaml_path = BASE_DIR / "config_hue.yaml"  # ⚡ Segregated lighting profile path entry
    zwave_yaml_path = BASE_DIR / "config_zwave.auto.yaml"  # ⚡ UI/system-owned Z-Wave profile
    automations_yaml_path = BASE_DIR / "automations.auto.yaml"  # ⚡ UI/system-owned exclude/lighting/rules

    # STRICT CHECK 1: Ensure .env file physically exists
    if not env_path.exists():
        raise FileNotFoundError(f"Environment configuration file not found: {env_path}")
    load_dotenv(dotenv_path=env_path)

    if not runtime_yaml_path.exists():
        raise FileNotFoundError(f"Runtime configuration file not found: {runtime_yaml_path}")
    if not hardware_yaml_path.exists():
        raise FileNotFoundError(f"Hardware mapping file not found: {hardware_yaml_path}")

    # 1. Read Runtime Config
    with open(runtime_yaml_path, "r", encoding="utf-8") as file:
        runtime_data = yaml.safe_load(file)

    # 2. Read Static Hardware Config
    with open(hardware_yaml_path, "r", encoding="utf-8") as file:
        hardware_data = yaml.safe_load(file)

    # 3. Read Segregated Lighting Config Profile if available
    hue_data: Optional[Dict[str, Any]] = None
    if hue_yaml_path.exists():
        with open(hue_yaml_path, "r", encoding="utf-8") as file:
            hue_file_raw = yaml.safe_load(file)
            if isinstance(hue_file_raw, dict):
                hue_data = hue_file_raw.get("hue", hue_file_raw)
                if hue_data:
                    for map_key in ["device_map", "group_map", "scene_map", "presets"]:
                        if hue_data.get(map_key) is None:
                            hue_data[map_key] = {}

    # 3b. Read Segregated Z-Wave Config Profile if available
    zwave_data: Optional[Dict[str, Any]] = None
    if zwave_yaml_path.exists():
        with open(zwave_yaml_path, "r", encoding="utf-8") as file:
            zwave_file_raw = yaml.safe_load(file)
            if isinstance(zwave_file_raw, dict):
                zwave_data = zwave_file_raw.get("zwave", zwave_file_raw)

    # 3c. Read automatic automations / lighting / soft-hide profile
    auto_data: Dict[str, Any] = {}
    if automations_yaml_path.exists():
        with open(automations_yaml_path, "r", encoding="utf-8") as file:
            auto_raw = yaml.safe_load(file)
            if isinstance(auto_raw, dict):
                auto_data = auto_raw

    deviceexplorer_hide = auto_data.get(
        "deviceexplorer_hide", runtime_data.get("deviceexplorer_hide", [])
    )
    lighting_data = auto_data.get("lighting", runtime_data.get("lighting", {}))
    automations_data = auto_data.get("automations", runtime_data.get("automations", []))

    # X1 expansion (Y1 branched -> flat engine rules)
    automations_expanded_for_engine = _expand_branched_automations_for_engine(automations_data)

    # 4. Consolidate payloads for unified validation assembly
    compiled_data = {
        "version": runtime_data.get("version", "1.0"),  # ⚡ Pull semantic baseline from absolute file root
        "wanos": runtime_data["wanos"],
        "rfxcom": runtime_data.get("rfxcom"),  # Load native RFX USB settings
        "hue": hue_data,  # ⚡ Injecting modular Hue configuration profile mapping to eliminate KeyErrors
        "epson": runtime_data.get("epson"),
        "sonos": runtime_data.get("sonos"),
        "onkyo": runtime_data.get("onkyo"),
        "zwave": zwave_data,  # ⚡ Injecting modular Z-Wave configuration profile
        "deviceexplorer_hide": deviceexplorer_hide,  # ⚡ From automations.auto.yaml
        "hardware_links": runtime_data.get("hardware_links"),
        "history": runtime_data.get("history") or {},
        "auth": {
            "shared_pin": os.getenv("AUTH_PIN", "0000"),
            "admin_pin": os.getenv("ADMIN_PIN", "0000"),
            "user_pin": os.getenv("USER_PIN", "1111"),
            "secret_key": os.getenv("SECRET_KEY", "wanos_fallback_insecure_key_change_in_prod"),
            "cookie_expiry_days": runtime_data.get("auth", {}).get("cookie_expiry_days", 30),
            "ban_timeout_mins": runtime_data.get("auth", {}).get("ban_timeout_mins", 30),
            "user_token": runtime_data.get("auth", {}).get("user_token", "default_user_token"),
            "kiosk_token": runtime_data.get("auth", {}).get("kiosk_token", "default_kiosk_token")
        },
        "pins": {
            "safety_gpio": hardware_data["gpio_output"]["safety_gpio"],
            "ir_relais": hardware_data["gpio_output"]["ir_relais"],
            "sauna_relais_phase_U": hardware_data["gpio_output"]["sauna_relais_phase_U"],
            "sauna_relais_phase_V": hardware_data["gpio_output"]["sauna_relais_phase_V"],
            "sauna_relais_phase_W": hardware_data["gpio_output"]["sauna_relais_phase_W"]
        },
        "gpio_inputs": hardware_data.get("gpio_input", {}),
        "sht11_sensors": hardware_data.get("sht11_sensors", {}),
        "sauna": runtime_data["sauna"],
        "ir": runtime_data["ir"],
        "bathroom1": runtime_data["bathroom1"],
        "lighting": lighting_data,
        "blinds": runtime_data.get("blinds"),
        "environmental_schedule": runtime_data.get("environmental_schedule"),
        "weather": runtime_data["weather"],
        "native_rfx": runtime_data.get("native_rfx", []),
        "automations": automations_expanded_for_engine,
    }

    # STRICT CHECK 2: Extract & validate required secret keys
    wanos_pass = os.getenv("WANOS_MQTT_PASSWORD")
    compiled_data["weather"]["api_key"] = os.getenv("OWM_API_KEY")

    if not wanos_pass:
        raise ValueError("CRITICAL: Missing required environment variable 'WANOS_MQTT_PASSWORD' in .env")

    # 4. Inject verified secrets into the nested MQTT objects
    compiled_data["wanos"]["mqtt"]["password"] = wanos_pass

    # ⚡ Safe Credential Fallback Strategy: Populate key from environment using safe .get() to prevent KeyErrors
    if compiled_data.get("hue") is not None and isinstance(compiled_data["hue"], dict):
        if not compiled_data["hue"].get("application_key"):
            compiled_data["hue"]["application_key"] = os.getenv("HUE_API_KEY")

    # 6. Extract Lab Seeding if present
    if lab_yaml_path.exists():
        with open(lab_yaml_path, "r", encoding="utf-8") as lab_file:
            lab_data_raw = yaml.safe_load(lab_file)
            if isinstance(lab_data_raw, dict) and "boot_seed" in lab_data_raw:
                compiled_data["boot_seed"] = lab_data_raw["boot_seed"]

    return AppConfig(**compiled_data)