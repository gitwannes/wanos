# --- file: core/event_handlers/registry.py ---
from .integration_handlers import (
    handle_automations_toggled, handle_domoticz_toggled, handle_rfxcom_toggled,
    handle_owm_toggled, handle_hue_toggled, handle_epson_toggled, handle_zwave_toggled,
    handle_simulations_toggled
)
from .hardware_handlers import (
    handle_hardware_bus_health_updated, handle_sht11_toggled, handle_gpio_input_toggled,
    handle_gpio_output_toggled, handle_sensor_error
)
from .telemetry_handlers import (
    handle_power_updated, handle_external_weather_updated, handle_system_metrics_updated,
    handle_temp_updated, handle_humidity_updated, handle_water_pulse, handle_kwh_pulse,
    handle_nvram_flush_trigger
)
from .timer_handlers import (
    handle_timer_scheduled, handle_timer_cancelled, handle_light_timer_expired,
    handle_vent_wait_expired, handle_vent_run_expired, handle_bath1_vent_lock_expired
)
from .hub_handlers import (
    handle_door_changed, handle_hub_state_changed, handle_lighting_state_changed
)
from .sauna_handlers import (
    handle_sauna_on, handle_sauna_off, handle_sauna_timer_adjusted, handle_sauna_hold_toggled,
    handle_sauna_timer_expired, handle_sauna_setpoint_changed, handle_sauna_modulation_updated,
    handle_ir_on, handle_ir_off, handle_ir_timer_expired, handle_ir_modulation_updated
)
from .system_handlers import (
    handle_system_ready, handle_alert_dismissed, handle_alert_clear_non_critical,
    handle_alert_injected, handle_config_reload_requested, handle_system_sweep_requested,
    handle_zwave_discovery
)

# Registry dictionary mapping event string identifiers to their asynchronous handler functions.
EVENT_ROUTERS = {
    "AUTOMATIONS_TOGGLED": handle_automations_toggled,
    "DOMOTICZ_TOGGLED": handle_domoticz_toggled,
    "RFXCOM_TOGGLED": handle_rfxcom_toggled,
    "OWM_TOGGLED": handle_owm_toggled,
    "HUE_TOGGLED": handle_hue_toggled,
    "EPSON_TOGGLED": handle_epson_toggled,
    "ZWAVE_TOGGLED": handle_zwave_toggled,
    "SIMULATIONS_TOGGLED": handle_simulations_toggled,

    "HARDWARE_BUS_HEALTH_UPDATED": handle_hardware_bus_health_updated,
    "SHT11_TOGGLED": handle_sht11_toggled,
    "GPIO_INPUT_TOGGLED": handle_gpio_input_toggled,
    "GPIO_OUTPUT_TOGGLED": handle_gpio_output_toggled,
    "SENSOR_ERROR": handle_sensor_error,
    "NVRAM_FLUSH_TRIGGER": handle_nvram_flush_trigger,

    "POWER_UPDATED": handle_power_updated,
    "EXTERNAL_WEATHER_UPDATED": handle_external_weather_updated,
    "SYSTEM_METRICS_UPDATED": handle_system_metrics_updated,
    "TEMP_UPDATED": handle_temp_updated,
    "HUMIDITY_UPDATED": handle_humidity_updated,
    "WATER_PULSE": handle_water_pulse,
    "KWH_PULSE": handle_kwh_pulse,

    "TIMER_SCHEDULED": handle_timer_scheduled,
    "TIMER_CANCELLED": handle_timer_cancelled,
    "LIGHT_TIMER_EXPIRED": handle_light_timer_expired,
    "VENT_WAIT_EXPIRED": handle_vent_wait_expired,
    "VENT_RUN_EXPIRED": handle_vent_run_expired,
    "BATH1_VENT_LOCK_EXPIRED": handle_bath1_vent_lock_expired,

    "DOOR_CHANGED": handle_door_changed,
    "HUB_STATE_CHANGED": handle_hub_state_changed,
    "LIGHTING_STATE_CHANGED": handle_lighting_state_changed,

    "SAUNA_ON": handle_sauna_on,
    "SAUNA_OFF": handle_sauna_off,
    "SAUNA_TIMER_ADJUSTED": handle_sauna_timer_adjusted,
    "SAUNA_HOLD_TOGGLED": handle_sauna_hold_toggled,
    "SAUNA_TIMER_EXPIRED": handle_sauna_timer_expired,
    "SAUNA_SETPOINT_CHANGED": handle_sauna_setpoint_changed,
    "SAUNA_MODULATION_UPDATED": handle_sauna_modulation_updated,

    "IR_ON": handle_ir_on,
    "IR_OFF": handle_ir_off,
    "IR_TIMER_EXPIRED": handle_ir_timer_expired,
    "IR_MODULATION_UPDATED": handle_ir_modulation_updated,

    "SYSTEM_READY": handle_system_ready,
    "ALERT_DISMISSED": handle_alert_dismissed,
    "ALERT_CLEAR_NON_CRITICAL": handle_alert_clear_non_critical,
    "ALERT_INJECTED": handle_alert_injected,
    "CONFIG_RELOAD_REQUESTED": handle_config_reload_requested,
    "SYSTEM_SWEEP_REQUESTED": handle_system_sweep_requested,
    "ZWAVE_DISCOVERY": handle_zwave_discovery
}