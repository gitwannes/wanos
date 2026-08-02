## 🏷️ The Logical Entity Registry (For the GUI)
**Goal:** Automations in the GUI should use friendly IDs like `light.buro_main` instead of physical integer IDXs like `71001`. This way, if you replace a broken Z-Wave switch and it gets a new IDX, your automations don't break.

### Step A: Update `core/models.py`
Add the registry dictionary to your `SystemState`.

```python
class SystemState(BaseModel):
    # ... existing fields ...
    
    # ⚡ NEW: Maps logical GUI strings to physical backend integers
    # Example: {"light.buro_main": 71001, "sensor.sauna_temp": 20001}
    entity_registry: dict[str, int] = Field(default_factory=dict)
```

### Step B: Update `logic/automation_rules.py`
Teach the `AutomationEngine` to translate logical strings back into physical integers right before execution.

```python
class AutomationEngine:
    # ... existing code ...

    @staticmethod
    def _resolve_target_idx(target: Any, state: SystemState) -> Optional[int]:
        """Translates a GUI string to a physical IDX. Returns integers as-is."""
        if isinstance(target, int):
            return target
        if isinstance(target, str) and not target.isdigit():
            # Look up the string in the registry (e.g., "light.buro_main" -> 71001)
            return state.system.entity_registry.get(target)
        try:
            return int(target)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> List[Event]:
        # Inside your action loop, resolve the target before doing anything:
        for action in rule.actions:
            # ⚡ NEW: Resolve the physical target
            physical_idx = AutomationEngine._resolve_target_idx(getattr(action, "target_entity", action.idx), state)
            
            if physical_idx is not None and getattr(action, "target", None) != "hue_scene":
                raw_target_state = state.devices.get(physical_idx)
                # ... proceed with the existing action logic using physical_idx ...
```