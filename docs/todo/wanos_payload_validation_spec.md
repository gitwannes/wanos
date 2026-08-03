# WanOS: Event Payload Validation — Implementation Spec

## 1. Background & Problem Statement

`core/models.py` currently defines:

```python
class Event(BaseModel):
    type: Union[EventType, str]
    payload: Dict[str, Any] = Field(default_factory=dict)
```

Every handler across `core/event_handlers/*.py`, `state_manager.py`, and `logic/automation_rules.py` reads
this payload the same way: `payload = event.payload or {}` followed by `payload.get("key", default)`.
This protects against **missing keys**, but not against **wrong types or out-of-range values**. Two
confirmed, concrete crash points in the current codebase:

- **`core/event_handlers/telemetry_handlers.py::handle_power_updated`** — `raw_val: float =
  payload.get("value", 0.0)` is pushed straight into a rolling-average buffer and summed. A single
  malformed reading (e.g. a sensor glitch producing a string instead of a float) will raise a
  `TypeError` inside `sum(history)` and crash that event-loop tick.
- **`core/event_handlers/sauna_handlers.py::handle_sauna_setpoint_changed`** — `float(new_target)` is
  called with no `try/except`. A malformed setpoint payload raises `ValueError` in the **safety-critical
  sauna thermal control path**.

By contrast, `integrations/sonos.py::execute_command` already wraps its payload handling in a
`try/except Exception`, so it degrades gracefully today — it does **not** need to be part of this work.

This tells us two things: (1) the underlying concern — bad data crashing the loop — is real, not
hypothetical, but (2) it's isolated to specific event types, not systemic. The fix should be scoped
accordingly, not applied as a blanket rewrite of the shared `Event` model.

## 2. Decisions Made (and why)

Two AI-generated suggestions were reviewed before this spec. Their designs were rejected:

1. **Rejected: `Event.payload: Union[LightPayload, AudioPayload, dict]`.** Putting a union of
   strict sub-models directly on the shared `Event` envelope is unsafe: Pydantic v2's "smart union"
   resolution can silently coerce a payload into the wrong sibling model, or fall through to the
   permissive `dict` member and skip validation entirely, with no visible error either way. It also
   doesn't scale — WanOS has 40+ `EventType`s with heterogeneous payload shapes, and this approach
   only ever covered two of them.
2. **Rejected as a framework, accepted as a pattern: per-handler validation.** A second suggestion
   proposed keeping `Event` as a lightweight routing envelope and validating inside each handler with
   its own dedicated Pydantic model. This is architecturally correct and is what this spec builds on.
   However, its example code assumed `state.devices[idx]` is a dict of named attributes
   (`devices[idx]["brightness"] = ...`). In WanOS, `SystemState.devices` is `Dict[int, Any]` holding a
   **flat scalar value per idx** (see `handle_lighting_state_changed`, `handle_power_updated`). Any
   implementation must match this real shape, not the example's.

**Decision: validate at the handler level, per event type, only where it earns its cost.** Do not touch
`core/models.py::Event`. Do not attempt full coverage of all 40+ event types in one pass.

## 3. Scope — What Gets Validated First

Prioritize by **trust boundary** (is the data coming from outside WanOS's own trusted config/UI?) and
**consequence of failure** (does bad data hit a safety-critical or physically-actuating path?).

### Tier 1 — Do first (safety-critical and/or already-proven crash risk)
| Event type | Handler | Why |
|---|---|---|
| `SAUNA_SETPOINT_CHANGED` | `sauna_handlers.handle_sauna_setpoint_changed` | Confirmed unguarded `float()` crash; feeds the thermal/PID control path. |
| `POWER_UPDATED`, `TEMP_UPDATED`, `HUMIDITY_UPDATED`, `WATER_PULSE`, `KWH_PULSE` | `telemetry_handlers.py` | Confirmed unguarded numeric coercion; sensor/hardware data is inherently noisy (loose wiring, serial glitches). |
| `SAUNA_MODULATION_UPDATED` | `sauna_handlers.handle_sauna_modulation_updated` | Directly sets `phases_pwm` / `modulation_pwm`, which drive real 3-phase wattage distribution. |

### Tier 2 — Do next (external network devices, moderate consequence)
| Event type | Handler | Why |
|---|---|---|
| `LIGHTING_STATE_CHANGED`, `HUB_STATE_CHANGED` | `hub_handlers.py` | Payloads originate from Hue/Z-Wave/RFX bridges — external network services, not WanOS's own config. |
| `SONOS_COMMAND` | `integration_handlers.handle_sonos_command` | Already has a `try/except` at the execution layer (`sonos.py`), but adding a model here gives clearer rejection logging and consistent behavior with Onkyo. Lower priority since it doesn't currently crash. |
| Onkyo-related events (if/when `onkyo.py` dispatches structured events into the same queue) | `integrations/onkyo.py` / relevant handler | Same class of external TCP/eISCP device as Sonos; align with whatever pattern Sonos ends up using. |

### Tier 3 — Skip for now (internally-sourced, already safe enough)
Toggle events (`*_TOGGLED`), `AUTOMATIONS_TOGGLED`, `CONFIG_UPDATED`, timer events, and anything
constructed by `automation_rules.py` from your own YAML config. These are either boolean toggles with
sane `.get(key, default)` fallbacks already, or sourced from trusted config rather than the network.
Don't spend effort here until Tier 1 and 2 are done and proven useful in practice.

## 4. Files To Be Modified

| File | Change |
|---|---|
| `core/models.py` | Add new narrow Pydantic models: `SaunaSetpointPayload`, `SaunaModulationPayload`, a shared telemetry model (e.g. `SensorReadingPayload` for `POWER_UPDATED`/`TEMP_UPDATED`/`HUMIDITY_UPDATED`/`WATER_PULSE`/`KWH_PULSE`), and — for Tier 2 — `LightPayload`/`HubStatePayload`. **Do not modify the existing `Event` class.** |
| `core/event_handlers/sauna_handlers.py` | `handle_sauna_setpoint_changed` — validate with `SaunaSetpointPayload`, hard-reject + `AlertManager` alert on failure. `handle_sauna_modulation_updated` — validate with `SaunaModulationPayload`, same fail behavior. |
| `core/event_handlers/telemetry_handlers.py` | `handle_power_updated` and the sibling handlers for `TEMP_UPDATED`, `HUMIDITY_UPDATED`, `WATER_PULSE`, `KWH_PULSE` — validate `idx`/`value` with the shared telemetry model before they reach the rolling-average buffer. |
| `core/event_handlers/hub_handlers.py` | *(Tier 2 — after Tier 1 is proven out)* `handle_lighting_state_changed` and `handle_hub_state_changed` — validate Hue/Z-Wave-sourced `idx`/`state` payloads. |
| `core/event_handlers/integration_handlers.py` | *(Tier 2, lower priority)* `handle_sonos_command` — add a model for consistent rejection logging, even though `integrations/sonos.py` already catches exceptions downstream. |
| `logic/alert_manager.py` | No logic changes expected — just confirm `AlertManager.process_alert(...)`'s signature matches how Tier 1 handlers call it when rejecting a payload. |
| `tests/test_event_validation.py` *(new, or wherever the existing suite lives)* | Add the 4–5 test cases per hardened event type described in section 6 (valid payload, missing optional field, wrong type, out-of-range clamping, no regression on untouched handlers). |

Out of scope for this pass — no changes needed: `main.py`, `state_manager.py`, `integrations/*.py` (aside
from the note above), and the frontend.

## 5. Design Pattern To Implement

**Keep `core/models.py::Event` exactly as it is today** (`payload: Dict[str, Any]`). Add new, narrow
Pydantic models in `core/models.py` — one per event type being hardened, not a shared union. Each
model:

- Declares only the fields that event type actually needs (see WanOS's own `payload.get(...)` calls
  as the source of truth for what fields exist).
- Uses `field_validator` (Pydantic v2 API — `@field_validator("field")` + `@classmethod`, not the
  deprecated `@validator`) for clamping/range checks (brightness, volume, PWM percentages).
- Has no `Union` with `dict` or with sibling models. One model, one shape.

Inside the handler:

```python
from pydantic import ValidationError
from core.models import SaunaSetpointPayload  # example new model

async def handle_sauna_setpoint_changed(event: Event, manager: Any) -> Tuple[bool, Set[str]]:
    try:
        data = SaunaSetpointPayload(**(event.payload or {}))
    except ValidationError as e:
        logger.error(f"Dropped invalid SAUNA_SETPOINT_CHANGED payload: {e}")
        # Tier 1 events: also raise an AlertManager alert so this is visible in the UI,
        # not just the log — a dropped setpoint change should not fail silently.
        AlertManager.process_alert(manager._state, "🔴 Rejected invalid sauna setpoint command.")
        return False, set()

    manager._state.sauna.target_temp = min(data.target, manager._state.sauna.max_temp)
    return True, {"sauna"}
```

Key implementation details specific to WanOS:

- Match real field names exactly as currently read via `.get(...)` in each handler (e.g. `target` for
  setpoint, `idx`/`value` for telemetry, `pwm`/`phases` for modulation) — don't invent new field names.
- `manager._state.devices` is `Dict[int, Any]` with flat scalar values. Any model touching it should
  produce a single validated scalar (e.g. `data.state_val`), assigned the same way the handler already
  does it: `manager._state.devices[idx] = data.state_val`.
- For Tier 1 numeric sensor events, validate with a `field_validator` that attempts `float(v)` inside a
  `try/except` and raises Pydantic's own `ValueError` on failure — this makes bad numeric strings
  rejected cleanly instead of throwing an uncaught `TypeError`/`ValueError` deep in the averaging logic.
- Decide **fail behavior per tier**, not uniformly:
  - **Tier 1 (safety-critical):** hard reject on `ValidationError`, log at `error` level, and raise a
    visible `AlertManager` alert. Silent failure is not acceptable for sauna/thermal control — the
    operator should know a command was dropped.
  - **Tier 2 (external device state):** reject and log at `warning` level; an alert is optional, since
    stale/rejected Hue or Sonos state is lower-stakes than a rejected sauna command.

## 6. Testing Requirements

For each hardened event type, add tests (co-located with existing tests if a test suite exists, or in a
new `tests/` directory if not) covering:

1. A valid payload — confirm the model parses and the handler applies the expected state change.
2. A payload with a missing optional field — confirm default handling still matches current behavior.
3. A payload with a wrong-type value (e.g. `"value": "N/A"` for a telemetry event, `"target": "warm"`
   for a sauna setpoint) — confirm `ValidationError` is raised and caught, the handler returns
   `(False, set())` (or whatever no-op tuple applies), and **no exception propagates out of the
   handler**.
4. A payload with an out-of-range value (e.g. `bri: 500` or `volume: -20`) — confirm clamping in the
   validator produces the expected clamped result, not a rejection.
5. Confirm existing WanOS behavior (e.g. the moving-average logic in `handle_power_updated`,
   or RFX force-transmit behavior) is unaffected by handlers that are **not**
   being touched in this pass — this is a scoped change, and regression risk should be checked
   accordingly.

## 7. Explicitly Out of Scope for This Pass

- Do not modify `Event.type` or `Event.payload`'s declared type in `core/models.py`.
- Do not attempt to validate all 40+ `EventType`s in one PR. Ship Tier 1, confirm it works and doesn't
  introduce regressions, then move to Tier 2.
- Do not change the toggle-event handlers (`*_TOGGLED`) — they're internally sourced and already
  defensive enough.
- Do not add validation to `automation_rules.py`'s own event construction — those payloads come from
  your own YAML, not the network.

## 8. Summary for the Implementer

Add small, single-purpose Pydantic v2 models per event type (starting with `SaunaSetpointPayload`,
telemetry payload(s), and `SaunaModulationPayload`), validate inside the specific handler that already
owns that event type, fail loudly (log + alert) for Tier 1 safety-critical events, fail quietly (log
only) for Tier 2 external-device events, and leave the shared `Event` envelope and Tier 3 handlers
untouched. This directly closes two confirmed crash points (`handle_power_updated`,
`handle_sauna_setpoint_changed`) without a wide, risky refactor of the whole event system.
