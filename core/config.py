import os
import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv


class MQTTConfig(BaseModel):
    broker_host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


class AuthConfig(BaseModel):
    shared_pin: str


class SaunaConfig(BaseModel):
    default_setpoint: int
    max_temp: int
    # These values act as an immediate default upon instantiation, they will be overwritten from config.yaml
    kp: float = 1.0
    ki: float = 0.1
    kd: float = 0.0
    default_timer: int = 180
    vent_delay_mins: int = 10
    vent_run_mins: int = 160


class AppConfig(BaseModel):
    """The master configuration model that holds everything."""
    mqtt: MQTTConfig
    auth: AuthConfig
    sauna: SaunaConfig


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Reads the YAML file, injects .env secrets, and validates against Pydantic models.
    """
    # Anchor paths relative to the project root
    BASE_DIR = Path(__file__).resolve().parent.parent
    env_path = BASE_DIR / ".env"
    yaml_path = Path(config_path) if Path(config_path).is_absolute() else BASE_DIR / config_path

    # Load environment variables (secrets)
    load_dotenv(dotenv_path=env_path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as file:
        yaml_data = yaml.safe_load(file)

    # Inject secrets safely without committing them to git
    yaml_data["mqtt"]["password"] = os.getenv("MQTT_PASSWORD")

    if "auth" not in yaml_data:
        yaml_data["auth"] = {}
    yaml_data["auth"]["shared_pin"] = os.getenv("AUTH_PIN")

    return AppConfig(**yaml_data)