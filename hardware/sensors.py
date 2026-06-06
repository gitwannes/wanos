import asyncio
from core.models import Event, EventType
from core.state_manager import StateManager

async def mock_temperature_sensor(state_manager: StateManager):
    """
    Phase 2 Lab Mode: Simulates a physical temperature probe.
    Gradually warms up if the sauna is active and emitting PWM.
    """
    print("🔬 [LAB MODE] Mock temperature sensor started.")
    current_mock_temp = 20.0  # Start at room temperature

    while True:
        try:
            # 1. Get a read-only snapshot of the state
            state = state_manager.get_state_snapshot()
            
            # 2. Simulate environmental physics
            if state.sauna.active and state.sauna.modulation_pwm > 0:
                # If heater is on, temperature goes up based on PWM power
                heating_factor = (state.sauna.modulation_pwm / 100.0) * 0.5
                current_mock_temp += heating_factor
            else:
                # If heater is off, natural heat loss occurs
                if current_mock_temp > 20.0:
                    current_mock_temp -= 0.1

            current_mock_temp = round(current_mock_temp, 1)

            # 3. Dispatch the reading to the central queue
            event = Event(
                type=EventType.TEMP_UPDATED, 
                payload={"value": current_mock_temp}
            )
            state_manager.dispatch(event)

        except Exception as e:
            print(f"⚠️ Mock sensor error: {e}")

        # 4. Sleep to prevent blocking the async event loop
        await asyncio.sleep(2.0)