# --- file: logic/automation_rules.py ---
from core.models import Event, EventType, SystemState


class AutomationEngine:
    """
    Centralized Rule Engine for WanOS automations.
    Evaluates incoming events and system state to trigger automated follow-up commands
    (Cascading State, Master/Slave interlocks, Macros/Scenes).
    """

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> list[Event]:
        follow_up_events = []
        event_name = event.type.value if hasattr(event.type, 'value') else str(event.type)
        payload = event.payload or {}

        # -----------------------------------------------------------------
        # 1. SAUNA AUTOMATION: Bind Sauna Hue and Zoutlamp to Sauna state
        # -----------------------------------------------------------------
        if event_name == "SAUNA_ON":
            follow_up_events.append(
                Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": "sauna_hue", "state": "ON"}))
            follow_up_events.append(
                Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": "sauna_zoutlamp", "state": "ON"}))

        elif event_name == "SAUNA_OFF":
            follow_up_events.append(
                Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": "sauna_hue", "state": "OFF"}))
            follow_up_events.append(
                Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": "sauna_zoutlamp", "state": "OFF"}))

        # -----------------------------------------------------------------
        # 2. DEVICE CASCADES: PC Master/Slave & Buro Schemer
        # -----------------------------------------------------------------
        elif event_name == "HUB_STATE_CHANGED":
            device_id = payload.get("device_id")
            new_state = payload.get("state")  # "ON" or "OFF"

            # Rule 2A: PC (Master) overrides PC Aux (Slave)
            if device_id == "pc":
                follow_up_events.append(
                    Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": "pc_aux", "state": new_state}))

            # Rule 2B: PC Aux overrides Buro Schemer
            elif device_id == "pc_aux":
                follow_up_events.append(
                    Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": "buro_schemer", "state": new_state}))

        # -----------------------------------------------------------------
        # 3. MACROS / SCENES: 1e Verdiep All Off
        # -----------------------------------------------------------------
        elif event_name == "SCENE_VERDIEP_OFF":
            # Hardcoded list of devices to turn off.
            # Intentionally ignores pc, sauna, ir, sauna_hue, and sauna_zoutlamp.
            target_devices = [
                "cinema_main", "cinema_hue", "buro", "buro_schemer", "pc_aux",
                "bathroom_main", "bathroom_wastafel",
                "gang_boven"
            ]
            for device in target_devices:
                # Only dispatch OFF command if the device is currently ON to save network bandwidth
                if state.devices.get(device) == "ON":
                    follow_up_events.append(
                        Event(type=EventType.HUB_STATE_CHANGED, payload={"device_id": device, "state": "OFF"}))

        return follow_up_events