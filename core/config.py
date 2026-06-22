# --- file: core/config.py ---
import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Union, Any
from dotenv import load_dotenv


class WeatherConfig(BaseModel):
    location: str
    poll_interval_mins: int
    api_key: Optional[str] = None


class MQTTConfig(BaseModel):
    broker_host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class HTTPConfig(BaseModel):
    """Configuration mapping for the Domoticz HTTP JSON API."""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class WanosConfig(BaseModel):
    """Internal broker configuration block."""
    mqtt: MQTTConfig


class DomoticzConfig(BaseModel):
    """Configuration mapping for the remote Domoticz broker."""
    mqtt: MQTTConfig
    http: HTTPConfig


class PinMappingConfig(BaseModel):
    safety_gpio: int
    kwh_pin: int
    ir_relais: int
    sauna_relais: List[int]
    water_cold: int
    water_hot: int
    door_sauna: int
    door_bathroom1: int


class SHT11SensorNode(BaseModel):
    pin_d: int
    pin_c: int


class SaunaRuntimeConfig(BaseModel):
    default_sauna_setpoint: int
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
    default_auto_off_minutes: int
    managed_lights: List[int]
    auto_off_delays: Dict[int, int]


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
    """Declarative translation model mapping native hex IDs to virtual WanOS states."""
    name: str
    virtual_idx: int
    protocol: str
    on_id: str
    off_id: str


# --- Automation Models ---
class TriggerConfig(BaseModel):
    idx: Optional[int] = None
    state: Optional[str] = None
    event: Optional[str] = None


class ConditionConfig(BaseModel):
    type: str
    idx: Optional[int] = None
    condition_is: str = Field(alias="is")


class ActionConfig(BaseModel):
    idx: Optional[int] = None
    state: Optional[str] = None
    event: Optional[str] = None
    # ⚡ Rich Hue Automation Properties
    target: Optional[str] = None
    scene: Optional[str] = None
    preset: Optional[str] = None
    bri: Optional[int] = None
    xy: Optional[List[float]] = None


class AutomationRuleConfig(BaseModel):
    name: str
    scene: bool = False  # ⚡ Expose this automation rule as a manually triggerable scene in the UI
    trigger: Union[TriggerConfig, List[TriggerConfig]]
    conditions: Optional[List[ConditionConfig]] = None
    actions: List[ActionConfig]


# --- ⚡ Philips Hue Modular Models ⚡ ---
class HuePresetConfig(BaseModel):
    """Data blueprint verifying individual preset properties."""
    xy: List[float]
    bri: int


class HueConfig(BaseModel):
    """Configuration mapping for the segregated local Hue API v2 settings."""
    bridge_ip: str
    application_key: Optional[str] = None
    device_map: Dict[int, str] = Field(default_factory=dict)
    group_map: Dict[int, str] = Field(default_factory=dict)
    scene_map: Dict[str, str] = Field(default_factory=dict)
    presets: Dict[str, HuePresetConfig] = Field(default_factory=dict)


class AppConfig(BaseModel):
    """The unified master configuration model."""
    wanos: WanosConfig
    domoticz: DomoticzConfig
    rfxcom: Optional[RFXComSettings] = None
    hue: Optional[HueConfig] = None  # ⚡ Added modular lighting reference mapping
    dashboard: Dict[int, str]
    deviceexplorer_exclude: List[int] = Field(default_factory=list)  # ⚡ Hide explicitly excluded IDXs from UI
    auth: Dict[str, str]
    pins: PinMappingConfig
    sensors: Dict[str, SHT11SensorNode]
    sauna: SaunaRuntimeConfig
    ir: IRRuntimeConfig
    bathroom1: BathroomConfig
    lighting: LightingConfig
    environmental_schedule: Optional[EnvironmentalScheduleConfig] = None
    weather: WeatherConfig
    boot_seed: Dict[Union[int, str], Any] = {}
    native_rfx: List[NativeRFXConfig] = Field(default_factory=list)
    automations: List[AutomationRuleConfig] = Field(default_factory=list)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / ".env"
    runtime_yaml_path = Path(config_path) if Path(config_path).is_absolute() else BASE_DIR / config_path
    hardware_yaml_path = BASE_DIR / "hardware.yaml"
    lab_yaml_path = BASE_DIR / "config_lab.yaml"
    hue_yaml_path = BASE_DIR / "config_hue.yaml"  # ⚡ Segregated lighting profile path entry

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
                # Clean encapsulation: Supports both nested 'hue:' definitions and root declarations
                hue_data = hue_file_raw.get("hue", hue_file_raw)

    # 4. Consolidate payloads for unified validation assembly
    compiled_data = {
        "wanos": runtime_data["wanos"],
        "domoticz": runtime_data["domoticz"],
        "rfxcom": runtime_data.get("rfxcom"),  # Load native RFX USB settings
        "hue": hue_data,  # ⚡ Injecting modular Hue configuration profile mapping to eliminate KeyErrors
        "dashboard": runtime_data.get("dashboard", {}), # Load the UI mapping dictionary
        "deviceexplorer_exclude": runtime_data.get("deviceexplorer_exclude", []),  # ⚡ Load the UI exclusion list
        "auth": {"shared_pin": os.getenv("AUTH_PIN", "0000")},
        "pins": hardware_data["pins"],
        "sensors": hardware_data["sht11_sensors"],
        "sauna": runtime_data["sauna"],
        "ir": runtime_data["ir"],
        "bathroom1": runtime_data["bathroom1"],
        "lighting": runtime_data.get("lighting", {}),
        "environmental_schedule": runtime_data.get("environmental_schedule"),
        "weather": runtime_data["weather"],
        "native_rfx": runtime_data.get("native_rfx", []),
        "automations": runtime_data.get("automations", [])
    }

    # STRICT CHECK 2: Extract & validate required secret keys
    wanos_pass = os.getenv("WANOS_MQTT_PASSWORD")
    dom_pass = os.getenv("DOM_MQTT_PASSWORD")
    dom_http_pass = os.getenv("DOM_HTTP_PASSWORD")
    compiled_data["weather"]["api_key"] = os.getenv("OWM_API_KEY")

    if not wanos_pass:
        raise ValueError("CRITICAL: Missing required environment variable 'WANOS_MQTT_PASSWORD' in .env")
    if not dom_pass:
        raise ValueError("CRITICAL: Missing required environment variable 'DOM_MQTT_PASSWORD' in .env")
    if not dom_http_pass:
        raise ValueError("CRITICAL: Missing required environment variable 'DOM_HTTP_PASSWORD' in .env")

    # 4. Inject verified secrets into the nested MQTT objects
    compiled_data["wanos"]["mqtt"]["password"] = wanos_pass
    compiled_data["domoticz"]["mqtt"]["password"] = dom_pass
    compiled_data["domoticz"]["http"]["password"] = dom_http_pass

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