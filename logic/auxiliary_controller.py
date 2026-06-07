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
            state.light_color = AuxiliaryController._interpolate_color(
                temp=current, 
                min_temp=20.0, 
                max_temp=state.target_temp
            )

        # --------------------------------------------------------
        # 2. EVALUATE LCD TEXT
        # --------------------------------------------------------
        if not state.active:
            state.lcd_text = ""
            
        elif state.door_open:
            state.lcd_text = "PLEASE CLOSE DOOR"
            
        else:
            # The UI handles exact 1-second ticking, but the physical LCD
            # might only need minute-by-minute updates to avoid rapid screen flashing.
            if state.session_end_time:
                now = int(time.time())
                remaining_mins = max(0, int((state.session_end_time - now) / 60))
                state.lcd_text = f"REMAINING: {remaining_mins}M"
            else:
                state.lcd_text = "SAUNA ON"

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