# WanOS: Event Payload Validation — Scoped Spec

**Status:** Deferred until after Blocky (`docs/todo/install_blocky.md`).  
**Urgency:** Low. No production evidence of bad payloads causing failures.  
**Do not implement until Blocky work is done.**

---

## 1. Problem (revised)

`Event.payload` is an untyped `Dict[str, Any]`. Handlers use `.get(...)` and ad-hoc `float(...)`.

What is **true**:

- `handle_sauna_setpoint_changed` calls `float(new_target)` with no local guard.
- `handle_power_updated` feeds `payload.get("value")` into `sum(history)` without coercing.
- `/api/event` accepts any `payload: dict` (`GenericEventRequest`).

What is **not** true (earlier draft overstated this):

- Bad payloads do **not** kill the event worker. `_process_events` already catches `Exception`, logs, and continues. The cost is a **dropped event** (and, for sauna commands, an operator who may not notice).

What is **already mitigated** on the main sensor path:

- Z-Wave coerces with `float(raw_val)` in a `try` **before** dispatching `POWER_UPDATED` / `TEMP_UPDATED`. Handler-only validation is defense-in-depth there, not the first line of defense.

---

## 2. Decisions

| Topic | Decision |
|---|---|
| When | After Blocky / entity_id cutover only. |
| Shared `Event` model | **Do not change.** Keep `payload: Dict[str, Any]`. No union of payload models on the envelope. |
| Pattern | Narrow Pydantic model(s) validated **inside the handler** that owns the event type. |
| Out-of-range numerics | **Clamp** to agreed limits: setpoint **`[min_temp, max_temp]`** everywhere (server + UIs). Floor defaults to **50**; prefer config `min_temp` so it cannot drift. |
| Non-numeric / non-coercible / non-finite values | **Reject** the event (do not apply). Log at error. For sauna **commands**, also surface via `AlertManager`. Treat `NaN` / `±Inf` as reject (they coerce via `float()` / Pydantic but are not valid setpoints). |
| Alert on reject | Call `AlertManager.process_alert(...)` and **merge** its `(changed, domains)` into the handler return (same pattern as `hardware_handlers`). Never return bare `(False, set())` after writing an alert — the banner will not broadcast. |
| Telemetry fail mode | **Drop reading + keep last-good + log** (warning). **No** AlertManager spam. |
| Coverage | Only what is listed in §3. Not all 40+ event types. Not Tier‑2 device hubs / Sonos / Onkyo in this pass. |

### Rejected approaches (still rejected)

1. `Event.payload: Union[LightPayload, …, dict]` on the shared envelope — unsafe with Pydantic smart unions; does not scale.
2. Blanket validation of every handler in one PR.
3. Treating telemetry like safety commands (reject + UI alert per bad sample).

---

## 3. Scope for this pass (when unblocked)

### In scope

1. **`SAUNA_SETPOINT_CHANGED`** (`sauna_handlers.handle_sauna_setpoint_changed`)
   - Parse with a small `SaunaSetpointPayload` (field name stays `target`, matching today’s `.get("target")`).
   - Non-coercible **or non-finite** `target` (`NaN` / `±Inf`) → reject, log, `AlertManager` alert. Return the merged `(changed, domains)` from `process_alert` (typically `(True, {"system"})`), **not** bare `(False, set())`.
   - Coercible finite but out-of-range → **clamp**, then apply (same spirit as today’s `min(..., max_temp)`).
   - Do not invent new field names.
   - Alert copy: mirror existing style, e.g. `🟡 Command rejected: invalid sauna setpoint`.

### Out of scope for this pass

- Changing `core/models.py::Event`.
- Hue / Z-Wave hub / Sonos / Onkyo / toggle / automation / config events.
- Standing up a full test suite as a prerequisite (none exists today). If tests are added later, cover: valid setpoint, non-numeric reject + alert path, out-of-range clamp, untouched handlers unchanged.
- **`SAUNA_MODULATION_UPDATED`** — not in this pass unless a later review finds a real producer of bad PWM from outside the PID path (today PWM is largely controller-sourced).

### Telemetry (policy locked; implementation optional / later)

Same pattern only if/when touched after setpoint work proves useful:

- Attempt coerce to float (or int for humidity/pulses as handlers expect).
- On failure: **do not write** `devices[idx]`; leave previous value (last-good); log warning; **no** alert.
- On success with absurd magnitude: clamp only if a domain limit is explicitly defined; otherwise accept (sensors are not commands).

Rationale for this telemetry policy vs reject+alert: see §5.

---

## 4. Clamp limits — when out-of-range occurs

**Clamp is correct here** because the normal producers are UI controls with bounds; a hard reject would punish boundary bugs and UI/config drift more often than malice.

### Where out-of-range can come from today (verified)

| Source | Behavior | Risk |
|---|---|---|
| Commander slider | Today: `min="40"`, `:max="state.sauna.max_temp \|\| 110"` | Change floor to **50** when implementing. |
| Kiosk ±5 buttons | Today: `Math.max(20, …)` / `Math.min(100, …)` | Change floor to **50**; ceiling should follow `max_temp`, not hard `100`. |
| Handler today | `min(float(target), max_temp)` only | Add floor **50** and keep upper `max_temp`. |
| `/api/event` | Any dict payload | Can send any number or non-number if an authenticated client does. |
| `parseFloat` on UI | Can yield `NaN` if state is corrupted | Reject path (non-finite), not clamp. Server must check `math.isfinite` after coerce — `float("nan")` / `float("inf")` succeed. |

So out-of-range is not theoretical: **kiosk vs commander already disagree on legal range.** Locked policy: one shared floor and ceiling **`max_temp`** on server and both UIs so they cannot diverge.

### Clamp policy to implement (setpoint)

- **Upper bound:** `state.sauna.max_temp` (already config-driven; today `95` in `config.yaml`).
- **Lower bound:** **`50` everywhere** — server clamp, Commander slider, and Kiosk ± controls. Replace today’s inconsistent floors (`40` Commander / `20` Kiosk) when this work is implemented.
- **Why 50:** sauna setpoints below ~50 °C are not useful operating targets (heater still runs; UI/kiosk drift already allowed 20–40). Prefer a single source of truth: add `min_temp: 50` next to `max_temp` in `config.yaml` / sauna state and drive server + both UIs from that, so the floor cannot drift again across three surfaces. If adding a config key is too much for this pass, hardcode `50` in all three places and note the follow-up.

PWM (if ever hardened later): PID already uses `(0.0, 100.0)` — clamp to `0..100`.

### Implementer must-dos (locked)

1. **Alert domain merge** — after `process_alert`, return its `(changed, domains)` (or `|=` merge). Bare `(False, set())` after an alert leaves the banner in state but never broadcasts.
2. **Finite check** — reject non-finite values with the same path as non-coercible; do not rely on Pydantic `float` alone.
3. **Floor source of truth** — prefer `min_temp` in config/state; otherwise hardcode `50` on server + Commander + Kiosk in the same change set.

---

## 5. Telemetry: compare and recommendation

| Approach | Pros | Cons |
|---|---|---|
| **A. Reject + AlertManager** | Visible; matches “safety” tone | Alert spam on flaky meters; false urgency; Z-Wave already drops bad floats before dispatch |
| **B. Drop reading, keep last-good, log** | Stable UI/PID inputs; no spam; standard SCADA-ish “hold last good” | Silent if nobody watches logs; need occasional log review |
| **C. Coerce aggressively (`float()` / default 0)** | Simple | `0` can be a real reading (power flush already special-cases 0); wrong default can skew averages |

**Recommendation: B** for telemetry streams; **reject + alert** only for **operator commands** (setpoint).

Do **not** put telemetry in the same “Tier 1 alert” bucket as sauna setpoint. Given no observed incidents and producer-side float coercion on Z-Wave, telemetry hardening is **optional follow-up**, not part of the minimum pass in §3.

---

## 6. Files (when implementing)

| File | Change |
|---|---|
| `core/models.py` | Add `SaunaSetpointPayload` only (`target: float` + finite check). **Do not** modify `Event`. Optionally add `min_temp` on sauna config/state if using config as floor source of truth. |
| `core/event_handlers/sauna_handlers.py` | Validate in `handle_sauna_setpoint_changed`; reject non-numeric / non-finite + alert (**merge** `process_alert` domains); clamp to `[min_temp or 50, max_temp]`; keep `devices` / state write shape unchanged. |
| `logic/alert_manager.py` | No API change expected — reuse `AlertManager.process_alert(...)`. |
| `config.yaml` (if adopting `min_temp`) | Add `min_temp: 50` next to `max_temp`. |
| Frontend (same change set) | Set Commander and Kiosk floors to **50** (or `state.sauna.min_temp`); ceilings follow `max_temp` (drop kiosk’s hard `100` if it fights config). |

Out of scope: `main.py` envelope, `state_manager.py` loop, integrations, telemetry handlers (unless doing the optional follow-up in §3).

---

## 7. Implementer summary

After Blocky: add one payload model for `SAUNA_SETPOINT_CHANGED`, validate in its handler, **alert on non-numeric / non-finite reject** (merge alert domains into the return), **clamp to `[50, max_temp]`** (prefer config `min_temp`), leave `Event` alone. Align Commander and Kiosk floors in the same change set. Telemetry, if touched later, uses drop + last-good + log — never per-sample alerts.
