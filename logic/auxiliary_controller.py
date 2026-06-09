# --- logic/auxiliary_controller.py ---
import time
from core.models import SaunaState

class AuxiliaryController:
    """
    Pure business logic for the environmental state machine.
    Evaluates the current state to dictate lighting colors and LCD text.
    """

    @staticmethod
    def evaluate(state: SaunaState) -> SaunaState:
        # --------------------------------------------------------
        # 1. EVALUATE LIGHT COLOR (Hue Simulation)
        # --------------------------------------------------------
        if state.door_open:
            # Safety Warning: Solid Green
            state.light_color = "#00FF00"
            
        elif not state.active:
            # Standby Mode: Warm White
            state.light_color = "#FFD180"
            
        else:
            # Heating Mode: Dynamic Thermal Gradient (Blue -> Red)
            # We assume a starting blue floor of 20.0C up to the target_temp.
            current = state.current_temp if state.current_temp is not None else 20.0
            safe_max = state.target_temp if state.target_temp is not None else 90.0
            state.light_color = AuxiliaryController._interpolate_color(
                temp=current, 
                min_temp=20.0,
                max_temp=state.safe_max
            )

        # --------------------------------------------------------
        # 2. EVALUATE LCD TEXT
        # --------------------------------------------------------
        if state.active:
            # Format the target string, defaulting if physical sensors are detached
            temp_display: str = f"{int(state.current_temp)}°C" if state.current_temp is not None else "--°C"

            if state.door_open:
                state.lcd_text = f"CLOSE DOOR | {temp_display}"
            elif state.hold_mode == "hold":
                state.lcd_text = f"SAUNA HOLD | {temp_display}"
            else:
                state.lcd_text = f"SAUNA ON | {temp_display} ({state.modulation_pwm}%)"

        elif state.ventilation_state == "RUNNING":
            state.lcd_text = "VENT RUNNING"
        elif state.ventilation_state == "WAITING":
            state.lcd_text = "VENT WAITING"
        else:
            state.lcd_text = ""

        return state

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