# --- file: logic/auxiliary_controller.py ---
from core.models import SaunaState


class AuxiliaryController:
    """
    Pure business logic for the environmental state machine.
    Evaluates the current state to dictate lighting colors.
    LCD screen1 text is owned by logic.lcd_screen1 (MQTT + WISC mirror).
    """

    @staticmethod
    def evaluate(state: 'SystemState') -> 'SaunaState':
        sauna = state.sauna
        door_sauna_open = state.devices.get("door_sauna") == "OPEN"
        current_temp = state.sensors.sauna_calc_temp

        # --------------------------------------------------------
        # EVALUATE LIGHT COLOR (Hue Simulation)
        # --------------------------------------------------------
        if door_sauna_open:
            # Safety Warning: Solid Green
            sauna.light_color = "#00FF00"

        elif not sauna.active:
            # Standby Mode: Warm White
            sauna.light_color = "#FFD180"

        else:
            # Heating Mode: Dynamic Thermal Gradient (Blue -> Red)
            # We assume a starting blue floor of 20.0C up to the target_temp.
            current = current_temp if current_temp is not None else 20.0
            safe_max = sauna.target_temp if sauna.target_temp is not None else 90.0
            sauna.light_color = AuxiliaryController._interpolate_color(
                temp=current,
                min_temp=20.0,
                max_temp=safe_max
            )

        return sauna

    @staticmethod
    def _interpolate_color(temp: float, min_temp: float, max_temp: float) -> str:
        """Calculates a hex color sliding from pure Blue to pure Red."""
        # Clamp the temperature within the boundaries
        temp = max(min_temp, min(temp, max_temp))

        # Calculate how close we are to the target (0.0 to 1.0)
        ratio = (temp - min_temp) / (max_temp - min_temp) if max_temp > min_temp else 1.0

        # Calculate Red and Blue RGB values
        red = int(ratio * 255)
        blue = int((1.0 - ratio) * 255)

        # Format as Hex (e.g., #FF0000 for pure red, #0000FF for pure blue)
        return f"#{red:02X}00{blue:02X}"
