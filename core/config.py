# --- file: core/config.py ---
import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Union, Any
from dotenv import load_dotenv


class WeatherConfig(BaseModel):
    idx: int
    name: str
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
    name: str
    virtual_idx: int
    protocol: str
    on_id: str
    off_id: str


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
    target: Optional[str] = None
    scene: Optional[str] = None
    preset: Optional[str] = None
    bri: Optional[int] = None
    xy: Optional[List[float]] = None


class AutomationRuleConfig(BaseModel):
    name: str
    scene: bool = False  # ⚡ Expose this automation rule as a manually triggerable scene in the UI
    require_confirmation: bool = False  # ⚡ Prevents accidental misclicks by requiring a modal confirmation
    trigger: Union[TriggerConfig, List[TriggerConfig]]
    conditions: Optional[List[ConditionConfig]] = None
    actions: List[ActionConfig]


class HuePresetConfig(BaseModel):
    name: str
    xy: List[float]
    bri: int


class HueConfig(BaseModel):
    bridge_ip: str
    application_key: Optional[str] = None
    device_map: Dict[int, str] = Field(default_factory=dict)
    group_map: Dict[int, str] = Field(default_factory=dict)
    scene_map: Dict[str, str] = Field(default_factory=dict)
    presets: Dict[str, HuePresetConfig] = Field(default_factory=dict)


class EpsonConfig(BaseModel):
    ip_address: str


class ZwaveConfig(BaseModel):
    """Configuration mapping for the Z-Wave JS UI hardware stick and node map."""
    usb_path: str
    mqtt_prefix: str = "zwave"  # ⚡ Global prefix for dynamic MQTT routing
    device_map: Dict[int, str] = Field(default_factory=dict)
    hidden_nodes: List[int] = Field(default_factory=list)  # ⚡ Admin-only UI exclusions specifically for Z-Wave


class AuthConfig(BaseModel):
    shared_pin: str
    admin_pin: str
    user_pin: str
    secret_key: str
    cookie_expiry_days: int
    ban_timeout_mins: int
    user_token: str
    kiosk_token: str


class AppConfig(BaseModel):
    version: str
    wanos: WanosConfig
    domoticz: Optional[DomoticzConfig] = None
    rfxcom: Optional[RFXComSettings] = None
    hue: Optional[HueConfig] = None
    epson: Optional[EpsonConfig] = None
    zwave: Optional[ZwaveConfig] = None
    deviceexplorer_exclude: List[int] = Field(default_factory=list)  # ⚡ Hide explicitly excluded IDXs from UI
    auth: AuthConfig
    pins: PinMappingConfig
    gpio_inputs: Dict[str, GPIOInputNode]
    sht11_sensors: Dict[str, SHT11SensorNode]
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
    hardware_yaml_path = BASE_DIR / "config_hardware.yaml"
    lab_yaml_path = BASE_DIR / "config_lab.yaml"
    hue_yaml_path = BASE_DIR / "config_hue.yaml"  # ⚡ Segregated lighting profile path entry
    zwave_yaml_path = BASE_DIR / "config_zwave.yaml"  # ⚡ Segregated Z-Wave profile path entry

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

    # 4. Consolidate payloads for unified validation assembly
    compiled_data = {
        "version": runtime_data.get("version", "1.0"),  # ⚡ Pull semantic baseline from absolute file root
        "wanos": runtime_data["wanos"],
        "domoticz": runtime_data["domoticz"],
        "rfxcom": runtime_data.get("rfxcom"),  # Load native RFX USB settings
        "hue": hue_data,  # ⚡ Injecting modular Hue configuration profile mapping to eliminate KeyErrors
        "epson": runtime_data.get("epson"),
        "zwave": zwave_data,  # ⚡ Injecting modular Z-Wave configuration profile
        "deviceexplorer_exclude": runtime_data.get("deviceexplorer_exclude", []),  # ⚡ Load the UI exclusion list
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