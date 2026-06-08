# --- file: core/config.py ---
import os
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv


class MQTTConfig(BaseModel):
    broker_host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class PinMappingConfig(BaseModel):
    safety_gpio: int
    kwh_pin: int
    ir_relais: int
    sauna_relais: List[int]
    water_cold: int
    water_hot: int
    door_sauna: int
    door_bathroom: int


class SHT11SensorNode(BaseModel):
    pin_d: int
    pin_c: int
    idx: int


class SaunaRuntimeConfig(BaseModel):
    default_setpoint: int
    max_temp: int
    default_timer: int
    vent_delay_mins: int
    vent_run_mins: int
    pwm_freq: int
    kp: float
    ki: float
    kd: float


class IRRuntimeConfig(BaseModel):
    min_time_mins: int
    max_time_mins: int


class LabSeedConfig(BaseModel):
    """Strictly maps to config_lab.yaml. No fallbacks allowed."""
    sauna_high_temp: float
    sauna_low_temp: float
    sauna_high_hum: float
    sauna_low_hum: float
    door_open: bool
    bathroom_temp: float
    bathroom_hum: float
    cinema_temp: float
    cinema_hum: float
    outside_temp: float
    outside_hum: float
    outside_tick: int


class AppConfig(BaseModel):
    """The unified master configuration model."""
    mqtt: MQTTConfig
    domoticz: MQTTConfig
    auth: Dict[str, str]
    pins: PinMappingConfig
    sensors: Dict[str, SHT11SensorNode]
    sauna: SaunaRuntimeConfig
    ir: IRRuntimeConfig
    lab_seed: Optional[LabSeedConfig] = None


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Reads dynamic runtime config and static hardware mappings, injects secrets,
    and returns a unified validation object.
    """
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / ".env"
    runtime_yaml_path = Path(config_path) if Path(config_path).is_absolute() else BASE_DIR / config_path
    hardware_yaml_path = BASE_DIR / "hardware.yaml"
    lab_yaml_path = BASE_DIR / "config_lab.yaml"

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
        "mqtt": runtime_data["mqtt"],
        "domoticz": runtime_data["domoticz"],
        "auth": {"shared_pin": os.getenv("AUTH_PIN", "0000")},
        "pins": hardware_data["pins"],
        "sensors": hardware_data["sht11_sensors"],
        "sauna": runtime_data["sauna"],
        "ir": runtime_data["ir"]
    }

    # 4. Inject secrets
    compiled_data["mqtt"]["password"] = os.getenv("MQTT_PASSWORD")
    compiled_data["domoticz"]["password"] = os.getenv("DOMOTICZ_PASSWORD")

    # 5. Extract Lab Seeding if present
    if lab_yaml_path.exists():
        with open(lab_yaml_path, "r", encoding="utf-8") as lab_file:
            lab_data_raw = yaml.safe_load(lab_file)
            if isinstance(lab_data_raw, dict) and "lab_seed" in lab_data_raw:
                compiled_data["lab_seed"] = lab_data_raw["lab_seed"]

    return AppConfig(**compiled_data)