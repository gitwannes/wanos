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


class WanosConfig(BaseModel):
    """Internal broker configuration block."""
    mqtt: MQTTConfig


class DomoticzConfig(BaseModel):
    """Configuration mapping for the remote Domoticz broker."""
    mqtt: MQTTConfig


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


class RFXSwitchConfig(BaseModel):
    """Declarative translation model mapping stateless RFX commands to virtual states.
    --> FALLBACK for use of RFXCom with Domoticz
    This will have to be removed when the RFXCom is physically moved to the WanOS Pi"""
    virtual_idx: int
    on_trigger_idx: int
    off_trigger_idx: int


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
    condition_is: str = Field(alias="is")


class ActionConfig(BaseModel):
    idx: Optional[int] = None
    state: Optional[str] = None
    event: Optional[str] = None


class AutomationRuleConfig(BaseModel):
    name: str
    trigger: Union[TriggerConfig, List[TriggerConfig]]
    conditions: Optional[List[ConditionConfig]] = None
    actions: List[ActionConfig]


class AppConfig(BaseModel):
    """The unified master configuration model."""
    wanos: WanosConfig
    domoticz: DomoticzConfig
    dashboard: Dict[int, str]
    auth: Dict[str, str]
    pins: PinMappingConfig
    sensors: Dict[str, SHT11SensorNode]
    sauna: SaunaRuntimeConfig
    ir: IRRuntimeConfig
    bathroom1: BathroomConfig
    lighting: LightingConfig
    weather: WeatherConfig
    boot_seed: Dict[Union[int, str], Any] = {}
    rfx_switches: List[RFXSwitchConfig] = Field(default_factory=list)
    native_rfx: List[NativeRFXConfig] = Field(default_factory=list)
    automations: List[AutomationRuleConfig] = Field(default_factory=list)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / ".env"
    runtime_yaml_path = Path(config_path) if Path(config_path).is_absolute() else BASE_DIR / config_path
    hardware_yaml_path = BASE_DIR / "hardware.yaml"
    lab_yaml_path = BASE_DIR / "config_lab.yaml"

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

    # 3. Consolidate payloads for unified validation assembly
    compiled_data = {
        "wanos": runtime_data["wanos"],
        "domoticz": runtime_data["domoticz"],
        "dashboard": runtime_data.get("dashboard", {}), # Load the UI mapping dictionary
        "auth": {"shared_pin": os.getenv("AUTH_PIN", "0000")},
        "pins": hardware_data["pins"],
        "sensors": hardware_data["sht11_sensors"],
        "sauna": runtime_data["sauna"],
        "ir": runtime_data["ir"],
        "bathroom1": runtime_data["bathroom1"],
        "lighting": runtime_data.get("lighting", {}),
        "weather": runtime_data["weather"],
        "rfx_switches": runtime_data.get("rfx_switches", []),
        "native_rfx": runtime_data.get("native_rfx", []),
        "automations": runtime_data.get("automations", [])
    }

    # STRICT CHECK 2: Extract & validate required secret keys
    wanos_pass = os.getenv("WANOS_MQTT_PASSWORD")
    dom_pass = os.getenv("DOM_MQTT_PASSWORD")
    compiled_data["weather"]["api_key"] = os.getenv("OWM_API_KEY")

    if not wanos_pass:
        raise ValueError("CRITICAL: Missing required environment variable 'WANOS_MQTT_PASSWORD' in .env")
    if not dom_pass:
        raise ValueError("CRITICAL: Missing required environment variable 'DOM_MQTT_PASSWORD' in .env")

    # 4. Inject verified secrets into the nested MQTT objects
    compiled_data["wanos"]["mqtt"]["password"] = wanos_pass
    compiled_data["domoticz"]["mqtt"]["password"] = dom_pass

    # 5. Extract Lab Seeding if present
    if lab_yaml_path.exists():
        with open(lab_yaml_path, "r", encoding="utf-8") as lab_file:
            lab_data_raw = yaml.safe_load(lab_file)
            if isinstance(lab_data_raw, dict) and "boot_seed" in lab_data_raw:
                compiled_data["boot_seed"] = lab_data_raw["boot_seed"]

    return AppConfig(**compiled_data)