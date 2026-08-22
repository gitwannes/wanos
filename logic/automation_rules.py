# --- file: logic/automation_rules.py ---
import time
import json
from typing import List, Optional, Any, Tuple

from core.models import Event, EventType, SystemState, device_name, device_entity_id, format_device_ref as core_format_device_ref
from core.config import load_config
from core.logger import automation_logger  # explicitly isolated logger for logic rules
from core.event_catalog import to_bus_token, legacy_key_for_bus_token
from core.auto_off_policy import resolve_auto_off_minutes
from core.well_known_entities import (
    ENTITY_BATHROOM_VENT,
    ENTITY_WATER_HOT,
)


class AutomationEngine:
    """
    Centralized Rule Engine for WanOS automations.
    YAML device refs use stable entity_id only (resolved to idx via device_metadata).
    Unresolved entity_id → log + skip; never crash the engine.

    Logging Hierarchy:
    - Tier A (Invisible): If an event does not match a trigger, the engine remains 100% silent.
    - Tier B (DEBUG): [X-RAY] Traces the internal decision making of the "Bouncer" (Condition checks).
    - Tier C (INFO): [ACTION] Audit trails explaining exactly what the engine is commanding and why.
    """

    # Cache the config so we don't parse the YAML file on every single event iteration
    _config = None

    # Rolling array tracking absolute timestamps of hot water pulses for sensory debouncing
    _hot_water_pulses: List[float] = []

    # B10B re-entrancy: outer bus evaluate = depth 1. Fire-action events are stamped
    # with _wanos_fire_depth=2 because they are queued (not nested call stacks).
    # At depth >= 2, further event-emitting fire-actions are no-op (siblings OK).
    _event_fire_depth: int = 0

    # Well-known system fixtures: re-exported from core.well_known_entities.
    ENTITY_BATHROOM_VENT = ENTITY_BATHROOM_VENT
    ENTITY_WATER_HOT = ENTITY_WATER_HOT

    @classmethod
    def _get_config(cls):
        if cls._config is None:
            cls._config = load_config()
        return cls._config

    @staticmethod
    def resolve_entity_id(state: SystemState, entity_id: str) -> Optional[int]:
        """Always-resolve: entity_id → idx via device_metadata. None if missing/removed."""
        if not entity_id:
            return None
        for key, meta in (state.device_metadata or {}).items():
            if not isinstance(meta, dict):
                continue
            if meta.get("entity_id") == entity_id:
                try:
                    return int(key)
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def entity_id_for(state: SystemState, idx: Optional[int]) -> Optional[str]:
        """Reverse lookup: idx → entity_id from device_metadata."""
        return device_entity_id(state, idx)

    @staticmethod
    def resolve_device_ref(obj: Any, state: SystemState) -> Optional[int]:
        """Resolve a trigger/condition/action device ref by entity_id only."""
        # Branch wake passes condition leaves as dicts (_cond_as_dict); getattr misses entity_id.
        if isinstance(obj, dict):
            eid = obj.get("entity_id")
        else:
            eid = getattr(obj, "entity_id", None)
        if not eid:
            return None
        idx = AutomationEngine.resolve_entity_id(state, eid)
        if idx is None:
            automation_logger.warning(
                f"[AUTOMATION] Unresolved entity_id '{eid}' — skipping device ref "
                f"(engine continues; rule action/condition ignored)."
            )
        return idx

    @staticmethod
    def format_device_ref(state: SystemState, idx: Optional[int]) -> str:
        """Operator-facing device ref: entity_id (name, idx N) — core helper."""
        return core_format_device_ref(state, idx)

    @staticmethod
    def format_rule_name(rule: Any) -> str:
        """INFO/ACTION rule label — quoted name only (no uuid)."""
        name = getattr(rule, "name", None) or "?"
        return f'"{name}"'

    @staticmethod
    def format_rule_ref(rule: Any) -> str:
        """
        DEBUG / ERROR observability — keep uuid + branch + name:
        rule=<id> branch=on|off|if|elifN|else|- name="<base name>"
        """
        rid = getattr(rule, "id", None)
        name = getattr(rule, "name", None) or ""
        branch = "-"
        base_id = str(rid) if rid is not None else "-"
        if isinstance(rid, str):
            if rid.endswith("#on"):
                branch = "on"
                base_id = rid[:-3]
            elif rid.endswith("#off"):
                branch = "off"
                base_id = rid[:-4]
            elif "#elif" in rid:
                # B19: <uuid>#elif0
                base_id, _, suf = rid.partition("#")
                branch = suf or "-"
            elif rid.endswith("#if"):
                branch = "if"
                base_id = rid[:-3]
            elif rid.endswith("#else"):
                branch = "else"
                base_id = rid[:-5]
        display = name
        if display.endswith(" [ON]"):
            display = display[:-5]
        elif display.endswith(" [OFF]"):
            display = display[:-6]
        return f'rule={base_id} branch={branch} name="{display}"'


    @staticmethod
    def _timer_exists(active_timers: List[Any], target_timer_id: str) -> bool:
        """Robustly checks if a timer exists by safely parsing serialized JSON strings."""
        for t in active_timers:
            if isinstance(t, dict) and t.get("timer_id") == target_timer_id:
                return True
            if isinstance(t, str):
                try:
                    parsed = json.loads(t)
                    if isinstance(parsed, dict) and parsed.get("timer_id") == target_timer_id:
                        return True
                except json.JSONDecodeError:
                    if t == target_timer_id:
                        return True
        return False

    @staticmethod
    def _is_dark(state: SystemState) -> bool:
        """
        Helper function to resolve the 'time_of_day is dark' condition.
        Relies on the mathematical absolute UNIX bounds calculated by the Environmental Time-Series engine.
        """
        sunrise = state.sensors.sunrise_unix
        sunset = state.sensors.sunset_unix

        if not sunrise or not sunset:
            return False  # Failsafe: Default to 'daylight' if weather data hasn't synced

        now = int(time.time())
        # Standard day phase: "dark" means before sunrise OR after sunset.
        return now < sunrise or now > sunset

    @staticmethod
    def _normalize_edge_state(raw: Any, meta: Any = None) -> str:
        """Normalize trigger/event states for comparison (blinds OPEN↔0, CLOSED↔100)."""
        if isinstance(raw, dict):
            raw = raw.get("state")
        if isinstance(raw, bool):
            raw = "ON" if raw else "OFF"
        s = str(raw).strip() if raw is not None else ""
        su = s.upper()
        dtype = ""
        if isinstance(meta, dict):
            dtype = str(meta.get("type") or "").lower()
        if dtype in ("blinds", "shutter"):
            if su in ("0", "OPEN"):
                return "OPEN"
            if su in ("100", "CLOSED"):
                return "CLOSED"
            return su
        return su

    @staticmethod
    def _states_match(expected: Any, actual: Any, meta: Any = None) -> bool:
        return AutomationEngine._normalize_edge_state(expected, meta) == AutomationEngine._normalize_edge_state(
            actual, meta)

    @staticmethod
    def _attr_ram_key(attribute: Optional[str]) -> Optional[str]:
        """Map schema attribute → devices[] dict key (temp/hum/bri/volume/position)."""
        if not attribute:
            return None
        a = str(attribute).strip().lower()
        if a in ("temperature", "temp"):
            return "temp"
        if a in ("humidity", "hum"):
            return "hum"
        if a in ("brightness", "bri"):
            return "bri"
        if a in ("volume", "vol"):
            return "volume"
        # position / closed % lives in dict.state (or scalar state string)
        if a in ("position", "closed", "closed_pct", "open_pct"):
            return None
        return a

    @staticmethod
    def _extract_device_value(raw: Any, attribute: Optional[str] = None) -> Any:
        """
        Read comparable value from devices[] entry.
        temp_hum dict → attribute temp/hum; actuators → bri/volume/state; scalars as-is.
        """
        ram_key = AutomationEngine._attr_ram_key(attribute)
        if isinstance(raw, dict):
            if ram_key is not None:
                return raw.get(ram_key)
            if "state" in raw:
                return raw.get("state")
            if "temp" in raw and attribute is None:
                return raw.get("temp")
            return raw.get("state", raw)
        return raw

    @staticmethod
    def _uses_rich_hub_numeric(attribute: Optional[str], op: str, threshold: Any) -> bool:
        """Rich actuator dict fields (volume, bri, shutter %) for HUB_STATE_CHANGED edge-cross."""
        if op not in (">", ">=", "<", "<=", "!=", "=="):
            return False
        if AutomationEngine._parse_compare_number(threshold) is None:
            return False
        if AutomationEngine._attr_ram_key(attribute) is not None:
            return True
        attr = str(attribute or "").strip().lower()
        return attr in ("position", "closed", "closed_pct", "open_pct")

    @staticmethod
    def _numeric_edge_raws_for_event(
        *,
        event_name: str,
        pl: dict,
        state: SystemState,
        cond_idx: int,
        t_attr: Optional[str],
        op: str,
        threshold: Any,
        new_state: Any,
    ) -> Tuple[Any, Any]:
        """Resolve old/new samples for B9A numeric edge-cross."""
        if event_name == "HUB_STATE_CHANGED":
            if AutomationEngine._is_shutter_position_numeric_compare(
                state, cond_idx, t_attr, op, threshold
            ):
                # Consecutive mesh reports — not optimistic RAM vs inbound (false reverse edge).
                old_raw = pl.get("old_value")
                if old_raw is None:
                    old_raw = pl.get("old_val", pl.get("old_state"))
                new_raw = pl.get("state", new_state)
                if new_raw is None:
                    new_raw = state.devices.get(cond_idx)
                return old_raw, new_raw
            if AutomationEngine._uses_rich_hub_numeric(t_attr, op, threshold):
                old_raw = pl.get("old_val", pl.get("old_state"))
                new_raw = state.devices.get(cond_idx)
                if new_raw is None:
                    new_raw = state.devices.get(str(cond_idx))
                return old_raw, new_raw
            old_raw = pl.get("old_state", pl.get("old_val"))
            new_raw = pl.get("state", new_state)
            if new_raw is None:
                new_raw = state.devices.get(cond_idx)
            return old_raw, new_raw
        if event_name == "TEMP_UPDATED":
            return {"temp": pl.get("old_value")}, state.devices.get(cond_idx)
        if event_name == "HUMIDITY_UPDATED":
            return {"hum": pl.get("old_value")}, state.devices.get(cond_idx)
        return pl.get("old_value"), state.devices.get(cond_idx)

    @staticmethod
    def _is_shutter_position_numeric_compare(
        state: SystemState,
        idx: Any,
        attribute: Optional[str],
        op: str,
        threshold: Any,
    ) -> bool:
        """True when edge-cross is shutter open-/closed-% (not volume/bri/temp)."""
        if not AutomationEngine._uses_rich_hub_numeric(attribute, op, threshold):
            return False
        if AutomationEngine._attr_ram_key(attribute) is not None:
            return False
        attr = str(attribute or "").strip().lower()
        if attr and attr not in ("position", "closed", "closed_pct", "open_pct"):
            return False
        meta = state.device_metadata.get(idx) or state.device_metadata.get(str(idx)) or {}
        return str(meta.get("type") or "").lower() in ("blinds", "shutter")

    @staticmethod
    def _shutter_position_zwave_telemetry(payload: Optional[dict]) -> bool:
        """Shutter % edge-cross uses sequential mesh reports, not optimistic commands."""
        return str((payload or {}).get("origin") or "").lower() == "zwave"

    @staticmethod
    def _hub_state_change_may_wake_compare(
        cond: Any,
        *,
        is_transition: bool,
        payload: Optional[dict],
    ) -> bool:
        from core.condition_tree import (
            condition_discrete_hub_wakes,
            condition_is_hub_level_numeric_compare,
            condition_is_shutter_position_numeric_compare,
        )

        if condition_is_shutter_position_numeric_compare(cond):
            return AutomationEngine._shutter_position_zwave_telemetry(payload)
        if condition_is_hub_level_numeric_compare(cond):
            return True
        return condition_discrete_hub_wakes(cond, payload)

    @staticmethod
    def _binary_device_state(raw: Any) -> str:
        """Normalize ON/OFF from a devices[] entry or flat scalar."""
        if isinstance(raw, dict):
            val = raw.get("state")
        else:
            val = raw
        return str(val).strip().upper() if val is not None else ""

    @staticmethod
    def _parse_compare_number(value: Any) -> Optional[float]:
        from logic.history_ids import parse_numeric_state
        return parse_numeric_state(value)

    @staticmethod
    def _compare_values(op: str, actual: Any, expected: Any) -> bool:
        """
        Apply compare op. Equality ops fall back to string match when not both numeric.
        Inequality ops require parseable numbers on both sides.
        """
        op_s = (op or "==").strip()
        if op_s not in ("==", "!=", ">", ">=", "<", "<="):
            op_s = "=="
        a_num = AutomationEngine._parse_compare_number(actual)
        e_num = AutomationEngine._parse_compare_number(expected)
        if op_s in (">", ">=", "<", "<="):
            if a_num is None or e_num is None:
                return False
            if op_s == ">":
                return a_num > e_num
            if op_s == ">=":
                return a_num >= e_num
            if op_s == "<":
                return a_num < e_num
            return a_num <= e_num
        # == / != : prefer numeric when both parse, else string (case-insensitive)
        if a_num is not None and e_num is not None:
            eq = a_num == e_num
        else:
            eq = str(actual).strip().upper() == str(expected).strip().upper()
        return eq if op_s == "==" else (not eq)

    @staticmethod
    def _condition_holds(
        condition: Any,
        state: SystemState,
        *,
        event: Optional[Event] = None,
        bus_token: Optional[str] = None,
        event_name: Optional[str] = None,
        event_idx: Any = None,
        new_state: Any = None,
        is_transition: bool = False,
        payload: Optional[dict] = None,
    ) -> bool:
        """Evaluate one leaf condition; True = pass. B19: event / ANY / numeric edge when event given."""
        from core.condition_tree import evaluate_condition_node, is_group_node

        if is_group_node(condition if isinstance(condition, dict) else condition):
            node = condition.model_dump(by_alias=True) if hasattr(condition, "model_dump") else condition
            return evaluate_condition_node(
                node,
                lambda leaf: AutomationEngine._condition_holds(
                    leaf,
                    state,
                    event=event,
                    bus_token=bus_token,
                    event_name=event_name,
                    event_idx=event_idx,
                    new_state=new_state,
                    is_transition=is_transition,
                    payload=payload,
                ),
            )
        if not hasattr(condition, "type") and isinstance(condition, dict):
            # Engine may receive plain dict leaves from expanded YAML.
            from core.config import ConditionConfig

            try:
                condition = ConditionConfig.model_validate(condition)
            except Exception:
                return False
        return AutomationEngine._condition_holds_leaf(
            condition,
            state,
            event=event,
            bus_token=bus_token,
            event_name=event_name,
            event_idx=event_idx,
            new_state=new_state,
            is_transition=is_transition,
            payload=payload,
        )

    @staticmethod
    def _condition_holds_leaf(
        condition: Any,
        state: SystemState,
        *,
        event: Optional[Event] = None,
        bus_token: Optional[str] = None,
        event_name: Optional[str] = None,
        event_idx: Any = None,
        new_state: Any = None,
        is_transition: bool = False,
        payload: Optional[dict] = None,
    ) -> bool:
        """Evaluate one leaf Compare (device / event / time)."""
        if condition.type == "time_of_day":
            is_dark = AutomationEngine._is_dark(state)
            if condition.condition_is == "dark":
                return is_dark
            if condition.condition_is == "light":
                return not is_dark
            return False
        if condition.type == "event":
            # B19 event Compare — holds when the current bus event matches.
            want = getattr(condition, "event", None)
            if not want or not bus_token:
                return False
            return to_bus_token(bus_token) == to_bus_token(str(want))
        if condition.type != "device_state":
            return True
        cond_idx = AutomationEngine.resolve_device_ref(condition, state)
        if cond_idx is None:
            return False
        is_val = condition.condition_is
        op = getattr(condition, "op", None) or "=="
        # B19: is ANY → true when this device is the waking device (any transition).
        if is_val is not None and str(is_val).upper() == "ANY":
            if event_idx is None or cond_idx != event_idx:
                return False
            if event_name == "DOOR_CHANGED":
                return True
            return bool(event_name == "HUB_STATE_CHANGED" and is_transition)
        # B9A/B19 numeric op: edge-cross when this device woke; else level check.
        if op in (">", ">=", "<", "<=", "!=", "==") and AutomationEngine._parse_compare_number(is_val) is not None:
            if event is not None and event_idx is not None and cond_idx == event_idx and event_name in (
                "HUB_STATE_CHANGED",
                "TEMP_UPDATED",
                "HUMIDITY_UPDATED",
                "POWER_UPDATED",
            ):
                pl = payload or {}
                t_attr = getattr(condition, "attribute", None)
                if (
                    event_name == "HUB_STATE_CHANGED"
                    and AutomationEngine._is_shutter_position_numeric_compare(
                        state, cond_idx, t_attr, op, is_val
                    )
                    and not AutomationEngine._shutter_position_zwave_telemetry(pl)
                ):
                    return False
                old_raw, new_raw = AutomationEngine._numeric_edge_raws_for_event(
                    event_name=event_name or "",
                    pl=pl,
                    state=state,
                    cond_idx=cond_idx,
                    t_attr=t_attr,
                    op=op,
                    threshold=is_val,
                    new_state=new_state,
                )
                if event_name == "TEMP_UPDATED" and t_attr is None:
                    t_attr = "temperature"
                elif event_name == "HUMIDITY_UPDATED" and t_attr is None:
                    t_attr = "humidity"
                return AutomationEngine._numeric_trigger_edge(
                    op=op,
                    attribute=t_attr,
                    threshold=is_val,
                    new_raw=new_raw,
                    old_raw=old_raw,
                )
        raw_state = state.devices.get(cond_idx)
        if raw_state is None:
            raw_state = state.devices.get(str(cond_idx))
        actual = AutomationEngine._extract_device_value(
            raw_state, getattr(condition, "attribute", None)
        )
        return AutomationEngine._compare_values(op, actual, is_val)

    @staticmethod
    def _branch_rule_wakes(
        rule: Any,
        *,
        bus_token: str,
        event_name: str,
        event_idx: Any,
        is_transition: bool,
        state: SystemState,
        payload: Optional[dict] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        B23: derived wake from If/Else-if branch condition trees.
        Returns (woke, reason, matched_event_uuid).
        """
        branches = getattr(rule, "branches", None) or []
        for br in branches:
            conds = getattr(br, "conditions", None) or []
            from core.condition_tree import branch_conditions_may_wake

            woke, reason, matched = branch_conditions_may_wake(
                conds,
                state=state,
                bus_token=bus_token,
                event_idx=event_idx,
                event_name=event_name,
                is_transition=is_transition,
                resolve_idx=lambda c: AutomationEngine.resolve_device_ref(c, state),
                payload=payload,
                to_bus_token=to_bus_token,
            )
            if woke:
                return True, reason, matched
        return False, "", None

    @staticmethod
    def _first_matching_branch(
        rule: Any,
        state: SystemState,
        *,
        event: Event,
        bus_token: str,
        event_name: str,
        event_idx: Any,
        new_state: Any,
        is_transition: bool,
        payload: dict,
    ) -> Tuple[Any, str]:
        """First-match If / Else-if. Returns (branch|None, id_suffix)."""
        elif_i = 0
        for br in getattr(rule, "branches", None) or []:
            when = getattr(br, "when", "") or ""
            # Bare else retired — skip if present in old in-memory/config shapes.
            if when == "else":
                continue
            if when == "if":
                suffix = "if"
            elif when == "else_if":
                suffix = f"elif{elif_i}"
                elif_i += 1
            else:
                continue
            ok = True
            conds = getattr(br, "conditions", None) or []
            if conds:
                from core.condition_tree import evaluate_condition_list

                ok = evaluate_condition_list(
                    conds,
                    lambda node: AutomationEngine._condition_holds(
                        node,
                        state,
                        event=event,
                        bus_token=bus_token,
                        event_name=event_name,
                        event_idx=event_idx,
                        new_state=new_state,
                        is_transition=is_transition,
                        payload=payload,
                    ),
                )
            if ok:
                return br, suffix
        return None, ""

    @staticmethod
    def _resolve_branch_executable_actions(
        br: Any,
        state: SystemState,
        *,
        event: Event,
        bus_token: str,
        event_name: str,
        event_idx: Any,
        new_state: Any,
        is_transition: bool,
        payload: dict,
    ) -> List[Any]:
        """
        B22: flatten branch ``then`` nesting to leaf ``actions`` (first-match per level).
        """
        then = getattr(br, "then", None)
        if then is not None:
            resolved: List[Any] = []
            for a in getattr(then, "leading_actions", None) or []:
                resolved.append(a)
            inner_branches = getattr(then, "branches", None) or []
            from types import SimpleNamespace

            if inner_branches:
                inner_rule = SimpleNamespace(branches=inner_branches)
                inner_br, _suffix = AutomationEngine._first_matching_branch(
                    inner_rule,
                    state,
                    event=event,
                    bus_token=bus_token,
                    event_name=event_name,
                    event_idx=event_idx,
                    new_state=new_state,
                    is_transition=is_transition,
                    payload=payload,
                )
                if inner_br is not None:
                    resolved.extend(
                        AutomationEngine._resolve_branch_executable_actions(
                            inner_br,
                            state,
                            event=event,
                            bus_token=bus_token,
                            event_name=event_name,
                            event_idx=event_idx,
                            new_state=new_state,
                            is_transition=is_transition,
                            payload=payload,
                        )
                    )
            for a in getattr(then, "trailing_actions", None) or []:
                resolved.append(a)
            return resolved
        return list(getattr(br, "actions", None) or [])

    @staticmethod
    def _numeric_trigger_edge(
        *,
        op: Optional[str],
        attribute: Optional[str],
        threshold: Any,
        new_raw: Any,
        old_raw: Any,
    ) -> bool:
        """True when compare becomes true on this edge (was false, now true)."""
        if not op or op == "==" and AutomationEngine._parse_compare_number(threshold) is None:
            # Non-numeric equality When still uses string edge elsewhere.
            return False
        new_v = AutomationEngine._extract_device_value(new_raw, attribute)
        old_v = AutomationEngine._extract_device_value(old_raw, attribute)
        now_ok = AutomationEngine._compare_values(op, new_v, threshold)
        if not now_ok:
            return False
        if old_raw is None and old_v is None:
            # First sample — treat becoming true as edge.
            return True
        was_ok = AutomationEngine._compare_values(op, old_v, threshold)
        return now_ok and not was_ok

    @staticmethod
    def evaluate(event: Event, state: SystemState) -> List[Event]:
        """
        Evaluate matching rules for ``event``.

        Re-entrancy (B10B): depth comes from ``payload._wanos_fire_depth`` when the
        event was produced by a fire-action (queued, not a nested call). Outer bus
        events default to depth 1. At depth >= 2, further event fire-actions are
        skipped (log once per attempt). Sibling fires at depth 2 remain OK.
        """
        payload = event.payload or {}
        stamped = payload.get("_wanos_fire_depth")
        prev = AutomationEngine._event_fire_depth
        if stamped is not None:
            try:
                AutomationEngine._event_fire_depth = int(stamped)
            except (TypeError, ValueError):
                AutomationEngine._event_fire_depth = 1
        else:
            AutomationEngine._event_fire_depth = 1
        try:
            return AutomationEngine._evaluate_body(event, state)
        finally:
            AutomationEngine._event_fire_depth = prev

    @staticmethod
    def _evaluate_body(event: Event, state: SystemState) -> List[Event]:
        bathroom_vent_idx = AutomationEngine.resolve_entity_id(
            state, AutomationEngine.ENTITY_BATHROOM_VENT)
        water_hot_idx = AutomationEngine.resolve_entity_id(
            state, AutomationEngine.ENTITY_WATER_HOT)

        payload = event.payload or {}
        config = AutomationEngine._get_config()

        follow_up_events: List[Event] = []
        # Bus token (UUID for catalog) vs legacy EventType key for hardcoded string compares.
        bus_token = to_bus_token(event.type)
        event_name = legacy_key_for_bus_token(bus_token)

        event_idx = payload.get("idx")
        try:
            if event_idx is not None:
                event_idx = int(event_idx)
        except (TypeError, ValueError):
            pass
        new_state = payload.get("state")
        if isinstance(new_state, dict):
            new_state = new_state.get("state")
        is_transition = payload.get("transitioned", False)

        # =========================================================================
        # 1. DYNAMIC YAML AUTOMATIONS (The Custom Rule Parser)
        # =========================================================================
        # This block parses the `automations:` list (from automations.auto.yaml).
        # - Triggers can be a single item or a List (List = OR logic. If any trigger matches, it fires).
        # - Actions are a List (List = AND logic. All actions execute sequentially).
        # - Origin force policy: RFX always; Sonos/Onkyo/Epson force OFF only (stale cache).
        # - Explicit "FORCE_" modifier still works for other origins (e.g. Z-Wave).
        # - Pure mirrors use explicit ON/OFF cases (SYNC / SYNCOPPOSITE retired).
        # =========================================================================

        # 🛡️ THE GENERIC BOOT GUARD 🛡️
        # Prevent "Boot Storms": We skip custom YAML rules if this is a boot initialization.
        # We do NOT return early so System Timers and shower vent watchdog can arm on boot!
        active_rules = [] if payload.get("is_initialization", False) else config.automations

        for rule in active_rules:
            # B10B: skip disabled rules (missing enabled → True).
            if getattr(rule, "enabled", True) is False:
                continue

            trigger_matched = False
            trigger_reason = ""
            matched_event_uuid: Optional[str] = None
            branch_mode = False

            # B19: Domoticz If/Do branches — derived wake + first-match.
            if getattr(rule, "branches", None):
                woke, trigger_reason, matched_event_uuid = AutomationEngine._branch_rule_wakes(
                    rule,
                    bus_token=bus_token,
                    event_name=event_name,
                    event_idx=event_idx,
                    is_transition=is_transition,
                    state=state,
                    payload=payload,
                )
                if not woke:
                    continue
                br, suffix = AutomationEngine._first_matching_branch(
                    rule,
                    state,
                    event=event,
                    bus_token=bus_token,
                    event_name=event_name,
                    event_idx=event_idx,
                    new_state=new_state,
                    is_transition=is_transition,
                    payload=payload,
                )
                if br is None:
                    automation_logger.debug(
                        f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} woke ({trigger_reason}) "
                        f"but no If/Else-if/Else matched."
                    )
                    continue
                br_conds = getattr(br, "conditions", None) or []
                from core.condition_tree import branch_has_flat_event_gate

                if branch_has_flat_event_gate(br_conds) and matched_event_uuid is None:
                    automation_logger.debug(
                        f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} flat event-gate branch "
                        f"woke ({trigger_reason}) without catalog event — skipped."
                    )
                    continue
                from types import SimpleNamespace
                base_id = getattr(rule, "id", None) or "-"
                resolved_actions = AutomationEngine._resolve_branch_executable_actions(
                    br,
                    state,
                    event=event,
                    bus_token=bus_token,
                    event_name=event_name,
                    event_idx=event_idx,
                    new_state=new_state,
                    is_transition=is_transition,
                    payload=payload,
                )
                if getattr(br, "then", None) is not None and not resolved_actions:
                    automation_logger.debug(
                        f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} branch {suffix} "
                        f"then chain had no matching inner branch."
                    )
                    continue
                rule = SimpleNamespace(
                    id=f"{base_id}#{suffix}",
                    name=getattr(rule, "name", None),
                    enabled=True,
                    trigger=None,
                    conditions=None,
                    actions=resolved_actions,
                    scene=bool(getattr(rule, "scene", False)),
                    require_confirmation=bool(getattr(rule, "require_confirmation", False)),
                    branches=None,
                )
                trigger_matched = True
                branch_mode = True
            else:
                # ⚡ Normalize trigger to a list so we can loop through it (Enabling OR logic)
                triggers = rule.trigger if isinstance(rule.trigger, list) else [rule.trigger]

                for t in triggers:
                    if t is None:
                        continue
                    trigger_idx = AutomationEngine.resolve_device_ref(t, state)
                    t_op = getattr(t, "op", None)
                    t_attr = getattr(t, "attribute", None)
                    # Trigger Type A: Device State Change (entity_id → idx)
                    if trigger_idx is not None and t.state:
                        # B9A numeric When — threshold-cross on sensor/host telemetry events.
                        if t_op and t_op in (">", ">=", "<", "<=", "!=", "=="):
                            if trigger_idx == event_idx and event_name in (
                                "HUB_STATE_CHANGED",
                                "TEMP_UPDATED",
                                "HUMIDITY_UPDATED",
                                "POWER_UPDATED",
                            ):
                                if (
                                    event_name == "HUB_STATE_CHANGED"
                                    and AutomationEngine._is_shutter_position_numeric_compare(
                                        state, trigger_idx, t_attr, t_op, t.state
                                    )
                                    and not AutomationEngine._shutter_position_zwave_telemetry(payload)
                                ):
                                    continue
                                old_raw, new_raw = AutomationEngine._numeric_edge_raws_for_event(
                                    event_name=event_name or "",
                                    pl=payload,
                                    state=state,
                                    cond_idx=trigger_idx,
                                    t_attr=t_attr,
                                    op=t_op,
                                    threshold=t.state,
                                    new_state=new_state,
                                )
                                if event_name == "TEMP_UPDATED" and t_attr is None:
                                    t_attr = "temperature"
                                elif event_name == "HUMIDITY_UPDATED" and t_attr is None:
                                    t_attr = "humidity"
                                if AutomationEngine._numeric_trigger_edge(
                                    op=t_op,
                                    attribute=t_attr,
                                    threshold=t.state,
                                    new_raw=new_raw,
                                    old_raw=old_raw,
                                ):
                                    trigger_matched = True
                                    trigger_reason = (
                                        f"{AutomationEngine.format_device_ref(state, event_idx)} "
                                        f"{t_op} {t.state} (edge)"
                                    )
                                    break
                        elif event_name == "HUB_STATE_CHANGED" and is_transition:
                            if trigger_idx == event_idx and AutomationEngine._states_match(
                                    t.state, new_state, state.device_metadata.get(trigger_idx, {})):
                                trigger_matched = True
                                trigger_reason = (
                                    f"{AutomationEngine.format_device_ref(state, event_idx)} -> {new_state}"
                                )
                                break
                        # ⚡ Support Native Door Telemetry: Map the semantic is_open boolean to standard ON/OFF string states
                        # Note: Hardware door events are inherently edge-triggered transitions, so is_transition is bypassed.
                        elif event_name == "DOOR_CHANGED":
                            is_open = payload.get("is_open")
                            mapped_state = "ON" if is_open else "OFF"
                            if trigger_idx == event_idx and AutomationEngine._states_match(
                                    t.state, mapped_state, state.device_metadata.get(trigger_idx, {})):
                                trigger_matched = True
                                trigger_reason = (
                                    f"Door {AutomationEngine.format_device_ref(state, event_idx)} -> {mapped_state}"
                                )
                                # Temporarily inject the mapped state into the local loop context
                                # so downstream Action resolving doesn't fail if it relies on 'new_state'
                                new_state = mapped_state
                                break

                    # Any transition — trigger has entity_id but no target state/op (v2 case "when transitioned").
                    elif trigger_idx is not None and t.state is None and not t_op:
                        if (
                            event_name == "HUB_STATE_CHANGED"
                            and is_transition
                            and trigger_idx == event_idx
                        ):
                            trigger_matched = True
                            trigger_reason = (
                                f"{AutomationEngine.format_device_ref(state, event_idx)} (transitioned)"
                            )
                            break

                    # Trigger Type B: Semantic / catalog event (UUID-on-bus after B10B)
                    elif t.event:
                        rule_event_str = t.event.value if hasattr(t.event, "value") else str(t.event)
                        # Compare bus tokens on both sides (legacy key ↔ UUID both normalize).
                        if to_bus_token(bus_token) == to_bus_token(rule_event_str):
                            trigger_matched = True
                            matched_event_uuid = to_bus_token(rule_event_str)
                            trigger_reason = f"Event [{matched_event_uuid}]"
                            break

            # --- TIER B: The Thought Process (DEBUG ONLY) ---
            if trigger_matched:
                automation_logger.debug(
                    f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} triggered by {trigger_reason}. "
                    f"Evaluating conditions...")

                conditions_met = True
                # B19 branch_mode: first-match already applied — skip flat conditions.
                if not branch_mode and rule.conditions:
                    for condition in rule.conditions:
                        if not AutomationEngine._condition_holds(
                            condition,
                            state,
                            event=event,
                            bus_token=bus_token,
                            event_name=event_name,
                            event_idx=event_idx,
                            new_state=new_state,
                            is_transition=is_transition,
                            payload=payload,
                        ):
                            conditions_met = False
                            if condition.type == "time_of_day":
                                automation_logger.debug(
                                    f"[X-RAY] -> ABORTED. Condition failed: time_of_day "
                                    f"requires '{condition.condition_is}'.")
                            elif condition.type == "device_state":
                                cond_idx = AutomationEngine.resolve_device_ref(condition, state)
                                automation_logger.debug(
                                    f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} -> "
                                    f"ABORTED. Condition failed: "
                                    f"{AutomationEngine.format_device_ref(state, cond_idx) if cond_idx is not None else condition.entity_id} "
                                    f"op={getattr(condition, 'op', None) or '=='} "
                                    f"attr={getattr(condition, 'attribute', None)} "
                                    f"requires '{condition.condition_is}'.")
                            else:
                                automation_logger.debug(
                                    f"[X-RAY] -> ABORTED. Unknown condition type '{condition.type}'.")
                            break

                # If all conditions pass, we calculate and dispatch the final actions
                if conditions_met:
                    trigger_label = trigger_reason
                    if matched_event_uuid:
                        trigger_label = legacy_key_for_bus_token(matched_event_uuid)
                    automation_logger.info(
                        f'[Automation] Rule "{AutomationEngine.format_rule_name(rule)}" '
                        f"fired (trigger: {trigger_label})"
                    )
                    automation_logger.debug(
                        f"[X-RAY] -> Conditions MET for {AutomationEngine.format_rule_ref(rule)}. Parsing actions..."
                    )

                    # B10B history: synthetic series keyed by event UUID when the trigger
                    # is a catalog event (no dependency on deprecated rule.scene).
                    if matched_event_uuid:
                        try:
                            from logic.history_ids import scene_history_idx
                            from core.events_store import find_event

                            if find_event(matched_event_uuid) is not None:
                                hm = getattr(AutomationEngine, "_history_manager", None)
                                if hm is not None:
                                    hm.log_event(
                                        scene_history_idx(matched_event_uuid), "ON", level=100.0
                                    )
                        except Exception:
                            pass

                    for action in (rule.actions or []):
                        # ⚡ Resolve modifiers
                        raw_action_state = action.state
                        is_force = False
                        if isinstance(raw_action_state, str) and raw_action_state.startswith("FORCE_"):
                            is_force = True
                            raw_action_state = raw_action_state.replace("FORCE_", "")

                        if action.state == "SYNC" or action.state == "SYNCOPPOSITE":
                            automation_logger.warning(
                                f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} action state "
                                f"{action.state} is retired — use explicit ON/OFF cases. Skipping action."
                            )
                            continue
                        target_action_state = raw_action_state

                        # ⚡ STRICT STATE FILTER: Prevent 'None' states from propagating to physical hardware.
                        # Drops ghost payloads (e.g., Hue brightness slides without binary power states)
                        # before they hit the execution blocks.
                        # We safely bypass this filter for Native Events and Hue Scenes which inherently do not require binary states.
                        is_pure_event: bool = getattr(action, "event", None) is not None
                        is_hue_scene: bool = getattr(action, "target", None) == "hue_scene"

                        if target_action_state is None and not is_pure_event and not is_hue_scene:
                            automation_logger.debug(
                                f"[X-RAY] -> Action SKIPPED: Target state resolved to None (Ghost Payload)."
                            )
                            continue

                        # --- Action Type A: Device Execution (entity_id → idx) ---
                        action_idx = AutomationEngine.resolve_device_ref(action, state)
                        if action_idx is not None and getattr(action, "target", None) != "hue_scene":
                            # ⚡ Extract state safely whether it's a flat string or a rich Hue dictionary
                            raw_target_state = state.devices.get(action_idx)
                            if raw_target_state is None:
                                raw_target_state = state.devices.get(str(action_idx))
                            current_target_state = raw_target_state.get("state") if isinstance(raw_target_state,
                                                                                               dict) else raw_target_state

                            meta = state.device_metadata.get(action_idx, {}) or {}
                            meta_origin: str = meta.get("origin", "") if isinstance(meta, dict) else ""

                            # Origin force policy (before NULL guard so unknown cache can still command):
                            # - RFX: always force (stateless 433 / boot seed lies)
                            # - Sonos / Onkyo / Epson: force OFF only (stale OFF while still on)
                            target_u = str(target_action_state).upper() if target_action_state is not None else ""
                            if meta_origin == "rfxcom":
                                is_force = True
                            elif meta_origin in ("sonos", "onkyo", "epson") and target_u == "OFF":
                                is_force = True

                            # ⚡ UNINITIALIZED STATE GUARD
                            # Skip unknown cache unless this action is forced (explicit FORCE_ or origin policy).
                            if current_target_state is None and not is_force:
                                automation_logger.debug(
                                    f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} -> "
                                    f"Action SKIPPED for "
                                    f"{AutomationEngine.format_device_ref(state, action_idx)}: "
                                    f"Current state is unknown (NULL).")
                                continue

                            # ⚡ RICH PAYLOAD EXTRACTION (Hue Presets & Direct Overrides)
                            bri = getattr(action, "bri", None)
                            xy = getattr(action, "xy", None)
                            preset_name = getattr(action, "preset", None)

                            # Load preset if specified
                            if preset_name and hasattr(config, "hue") and hasattr(config.hue, "presets"):
                                presets_col = config.hue.presets
                                # Safely extract from Pydantic dictionary or object
                                preset = presets_col.get(preset_name) if isinstance(presets_col, dict) else getattr(
                                    presets_col, preset_name, None)

                                if preset:
                                    # Support both dict and Pydantic model access for the payload claims
                                    bri = getattr(preset, "bri", bri) if hasattr(preset, "bri") else preset.get(
                                        "bri", bri)
                                    xy = getattr(preset, "xy", xy) if hasattr(preset, "xy") else preset.get("xy",
                                                                                                            xy)

                            # Extract Sonos rich parameters if provided in the YAML rule
                            volume = getattr(action, "volume", None)
                            station = getattr(action, "station", None)

                            is_rich_action = (
                                bri is not None or xy is not None
                                or volume is not None or station is not None
                            )

                            # Rich idempotency: only FORCE when power differs OR bri/xy/volume
                            # actually differ from the live snapshot. Blind force on any rich
                            # key re-triggers Sonos/Hue on every confirmation echo (e.g. Hue
                            # sync rule → Sonos forced again while already playing).
                            # `station` is not stored on device state; Sonos bridge already
                            # no-ops identical streams — do not force solely for station.
                            power_differs = (
                                current_target_state is None
                                or str(current_target_state).upper() != target_u
                            )
                            rich_differs = False
                            if is_rich_action:
                                if isinstance(raw_target_state, dict):
                                    if volume is not None:
                                        try:
                                            cur_vol = raw_target_state.get("volume")
                                            if cur_vol is None or int(cur_vol) != int(volume):
                                                rich_differs = True
                                        except (TypeError, ValueError):
                                            rich_differs = True
                                    if bri is not None:
                                        try:
                                            cur_bri = raw_target_state.get("bri")
                                            if cur_bri is None or int(cur_bri) != int(bri):
                                                rich_differs = True
                                        except (TypeError, ValueError):
                                            rich_differs = True
                                    if xy is not None:
                                        cur_xy = raw_target_state.get("xy")
                                        if list(cur_xy or []) != list(xy):
                                            rich_differs = True
                                elif not power_differs and (
                                    bri is not None or xy is not None or volume is not None
                                ):
                                    # Already at target power but no dict snapshot to compare —
                                    # allow one forced apply for bri/xy/volume. Station-only
                                    # has no comparable field; Sonos bridge no-ops same stream.
                                    rich_differs = True

                            # Rich same-power retune still needs force past the duplicate filter.
                            if rich_differs and not power_differs:
                                is_force = True

                            # STRING NORMALIZATION COMPARISON
                            # Coerced to uppercase strings to ensure integers (e.g., 100) and YAML strings (e.g., "100")
                            # or mixed-case status descriptors evaluate flawlessly, preventing duplicate command streams.
                            if power_differs or is_force or rich_differs:
                            # Use a distinct variable name to prevent shadowing the original event payload!
                            # Explicitly tags the origin as "AUTOMATION" for the IWHW Ledger
                                action_payload = {"idx": action_idx, "state": target_action_state,
                                                  "force": is_force, "origin": "AUTOMATION"}
                                if bri is not None:
                                    action_payload["bri"] = bri
                                if xy is not None:
                                    action_payload["xy"] = xy
                                if volume is not None:
                                    action_payload["volume"] = volume
                                if station is not None:
                                    action_payload["station"] = station

                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload=action_payload
                                ))

                                # --- TIER C: The Action Audit Trail (INFO) ---
                                final_state_str = f"{target_action_state} (FORCED)" if is_force else target_action_state
                                preset_str = f" [Rich Payload]" if is_rich_action else ""
                                automation_logger.info(
                                    f"[ACTION] {AutomationEngine.format_rule_name(rule)} -> "
                                    f"Set {AutomationEngine.format_device_ref(state, action_idx)} "
                                    f"to {final_state_str}{preset_str}")
                            else:
                                automation_logger.debug(
                                    f"[X-RAY] {AutomationEngine.format_rule_ref(rule)} -> "
                                    f"Target {AutomationEngine.format_device_ref(state, action_idx)} "
                                    f"is already {target_action_state}"
                                    f"{' (rich satisfied)' if is_rich_action else ''}. Ignoring.")

                        # --- Action Type B: Native Hue Scene Trigger ---
                        elif getattr(action, "target", None) == "hue_scene":
                            scene_name = getattr(action, "scene", None)
                            idx = AutomationEngine.resolve_device_ref(action, state)

                            # ⚡ 2-PART PAYLOAD: Requires both the string name AND the room IDX
                            if scene_name and idx is not None:
                                follow_up_events.append(Event(
                                    type=EventType.HUB_STATE_CHANGED,
                                    payload={"target": "hue_scene", "scene": scene_name, "idx": idx,
                                             "origin": "AUTOMATION"}
                                ))
                                automation_logger.info(
                                    f"[ACTION] {AutomationEngine.format_rule_name(rule)} -> "
                                    f"Dispatched Native Hue Scene [{scene_name}] on "
                                    f"{AutomationEngine.format_device_ref(state, idx)}")
                            else:
                                automation_logger.error(
                                    f"🔴 [AUTOMATION ERROR] {AutomationEngine.format_rule_ref(rule)} "
                                    f"failed: Missing 'scene' or device ref for hue_scene target.")

                        # --- Action Type C: Nested Event Chaining (UUID bus token) ---
                        elif getattr(action, "event", None):
                            # B10B re-entrancy: at depth >= 2, further event fires are no-op.
                            if AutomationEngine._event_fire_depth >= 2:
                                automation_logger.warning(
                                    f"[RE-ENTRANCY] Skipping nested fire-action event "
                                    f"'{action.event}' at depth "
                                    f"{AutomationEngine._event_fire_depth} "
                                    f"({AutomationEngine.format_rule_ref(rule)})."
                                )
                                continue

                            # Catalog keys → UUID; already-UUID / internals → pass-through.
                            # Do not require EventType enum membership (user events are UUIDs).
                            evt_type: Any = to_bus_token(action.event)

                            # ⚡ DYNAMIC PAYLOAD INJECTION
                            # Automatically map all provided YAML keys (idx, volume, station, etc.) into the event payload
                            action_payload = {}
                            if hasattr(action, "model_dump"):
                                action_payload = action.model_dump(exclude_none=True)
                                action_payload.pop("event",
                                                   None)  # Strip the event type itself out of the payload body

                            # Stamp depth+1 so the queued follow-up evaluates at depth 2
                            # (dispatch is async — call-stack depth alone cannot track this).
                            action_payload["_wanos_fire_depth"] = (
                                AutomationEngine._event_fire_depth + 1
                            )

                            follow_up_events.append(Event(
                                type=evt_type,
                                payload=action_payload
                            ))

                            payload_str = f" with payload: {action_payload}" if action_payload else ""
                            automation_logger.info(
                                f"[ACTION] {AutomationEngine.format_rule_name(rule)} -> "
                                f"Dispatched Internal Event [{evt_type}]{payload_str}")

        # =========================================================================
        # 2. SYSTEM SWEEPER: Time & Environment Audit (Option B Enforcer)
        # =========================================================================
        # When WanOS boots up, reloads its config, or recovers from a network outage,
        # it triggers a Sweeper. The sweeper looks at the clock and the live sensor data,
        # then explicitly commands the hardware to snap back to the mathematically correct state.
        # This prevents the house from staying "stuck" if an event fired while the hub was offline.
        # (Note: Environmental Blinds/Twilight are swept inside state_manager.py.)
        # =========================================================================
        if event_name == "SYSTEM_SWEEP_REQUESTED":
            recovered_timers: int = 0

            # --- Audit A: Auto-off Timers ---
            if hasattr(config, "auto_off_devices") and config.auto_off_devices.managed_auto_off:
                for light_eid in config.auto_off_devices.managed_auto_off:
                    light_idx = AutomationEngine.resolve_entity_id(state, light_eid)
                    if light_idx is None:
                        continue
                    current_state = state.devices.get(light_idx)

                    # ⚡ RICH PAYLOAD SUPPORT: Safely extract state from dictionary objects
                    extracted_state = current_state.get("state") if isinstance(current_state, dict) else current_state

                    if extracted_state == "ON":
                        timer_id = f"light_auto_off_{light_idx}"

                        # Secure parsing to detect JSON structured active_timers
                        timer_exists = AutomationEngine._timer_exists(state.system.active_timers, timer_id)

                        if not timer_exists:
                            meta = state.device_metadata.get(light_idx) or {}
                            dtype = meta.get("type") if isinstance(meta, dict) else None
                            origin = meta.get("origin") if isinstance(meta, dict) else None
                            delay_mins: int = resolve_auto_off_minutes(
                                eid=light_eid,
                                device_type=dtype,
                                auto_off_delays=config.auto_off_devices.auto_off_delays,
                                default_pertype=config.auto_off_devices.default_pertype_auto_off_minutes,
                                default_minutes=config.auto_off_devices.default_auto_off_minutes,
                                origin=str(origin) if origin else None,
                                product_type_overrides=getattr(config, "device_product_types", None) or {},
                            )
                            deadline: int = int(time.time()) + delay_mins * 60
                            semantic_name: str = device_name(state, light_idx, "Unknown")

                            # ⚡ Structured Payload for UI Timeline Processing
                            follow_up_events.append(Event(
                                type=EventType.TIMER_SCHEDULED,
                                payload={
                                    "timer_id": timer_id,
                                    "deadline": deadline,
                                    "event_type": EventType.LIGHT_TIMER_EXPIRED.value,
                                    "event_payload": {
                                        "idx": light_idx,
                                        "name": semantic_name,
                                        "type": str(meta.get("resolved_product_type") or "switch"),
                                        "target_state": "OFF",
                                        "origin": "TIMER"
                                    }
                                }
                            ))
                            automation_logger.info(
                                f"[System Sweeper] Recovered missing auto-off timer for "
                                f"{AutomationEngine.format_device_ref(state, light_idx)}. "
                                f"Turning OFF in {delay_mins} min.")
                            recovered_timers += 1

            # Feedback Alert for the Web UI
            if recovered_timers == 0:
                msg: str = "🟢 Sweeper complete: all synced."
            else:
                msg = f"🟢 Sweeper complete: Recovered {recovered_timers} timers."

            follow_up_events.append(Event(
                type=EventType.ALERT_INJECTED,
                payload={"msg_text": msg}
            ))

        # =========================================================================
        # 3. AUTO-OFF TIMERS (auto_off_devices)
        # =========================================================================
        # Prevents lights in transitive rooms (hallways, toilets, pantries) from being left on indefinitely.
        # - Only affects entity_ids explicitly listed in `managed_auto_off`.
        # - Delay = per-device override → type default → general default.
        # - Schedule only on OFF→ON for the managed device (ignore Hue/Sonos rich echoes while already ON).
        # =========================================================================
        if event_name == "HUB_STATE_CHANGED":
            idx = payload.get("idx")
            dev_ref = AutomationEngine.format_device_ref(state, idx)

            # Only track devices that are explicitly registered in the auto-off YAML config
            light_eid = AutomationEngine.entity_id_for(state, idx)
            if (light_eid is not None and hasattr(config, "auto_off_devices")
                    and light_eid in config.auto_off_devices.managed_auto_off):
                timer_id: str = f"light_auto_off_{idx}"

                # ⚡ Extract state safely whether it's a flat string or a rich Hue dictionary
                raw_state = state.devices.get(idx)
                current_state = raw_state.get("state") if isinstance(raw_state, dict) else raw_state

                # Normalize string to uppercase to catch mixed-case "On"/"Off" states
                safe_state = str(current_state).upper() if current_state else ""
                prior_raw = payload.get("old_val", payload.get("old_state"))
                was_on = AutomationEngine._binary_device_state(prior_raw) == "ON"

                if safe_state == "ON" and not was_on:
                    meta = state.device_metadata.get(idx) or {}
                    dtype = meta.get("type") if isinstance(meta, dict) else None
                    origin = meta.get("origin") if isinstance(meta, dict) else None
                    delay_mins: int = resolve_auto_off_minutes(
                        eid=light_eid,
                        device_type=dtype,
                        auto_off_delays=config.auto_off_devices.auto_off_delays,
                        default_pertype=config.auto_off_devices.default_pertype_auto_off_minutes,
                        default_minutes=config.auto_off_devices.default_auto_off_minutes,
                        origin=str(origin) if origin else None,
                        product_type_overrides=getattr(config, "device_product_types", None) or {},
                    )
                    deadline: int = int(time.time()) + delay_mins * 60

                    follow_up_events.append(Event(
                        type=EventType.TIMER_SCHEDULED,
                        payload={
                            "timer_id": timer_id,
                            "deadline": deadline,
                            "event_type": EventType.LIGHT_TIMER_EXPIRED.value,
                            "event_payload": {
                                "idx": idx,
                                "name": device_name(state, idx, "Unknown"),
                                "type": str(meta.get("resolved_product_type") or "switch"),
                                "target_state": "OFF",
                                "origin": "TIMER"
                            }
                        }
                    ))
                    automation_logger.info(
                        f"[Lighting Auto-Off] {dev_ref} turned ON. "
                        f"Scheduling OFF timer for {delay_mins} minutes (ID: {timer_id}).")

                elif safe_state == "OFF":
                    # Instantly cancel any pending countdowns for this light,
                    # but only if it's actually ticking (prevents phantom cancellations when the timer itself turned the light off)
                    timer_exists = AutomationEngine._timer_exists(state.system.active_timers, timer_id)

                    if timer_exists:
                        follow_up_events.append(Event(
                            type=EventType.TIMER_CANCELLED,
                            payload={"timer_id": timer_id}
                        ))
                        automation_logger.info(
                            f"[Lighting Auto-Off] {dev_ref} turned OFF. "
                            f"Cancelled pending auto-off timer.")

            # =========================================================================
            # 5. SHOWER VENTILATION WATCHDOG (Hot Water Overrun)
            # =========================================================================
            # Automatically activates the bathroom ventilator when a shower
            # is detected, filtering out transient spikes (hand washing) and extending
            # the runtime as a rolling debounced watchdog.
            # =========================================================================
            if event_name == "WATER_PULSE":
                idx = payload.get("idx")
                if idx == water_hot_idx and water_hot_idx is not None:
                    now_ts = time.time()
                    # Record current pulse timestamp
                    AutomationEngine._hot_water_pulses.append(now_ts)
                    # Evict pulse entries older than 10 seconds (Sliding Window filter)
                    AutomationEngine._hot_water_pulses = [
                        t for t in AutomationEngine._hot_water_pulses if now_ts - t <= 10.0
                    ]

                    # Enforce Hand-Washing Filter: Requires a minimum velocity of 5 pulses within 10 seconds
                    if len(AutomationEngine._hot_water_pulses) >= 5 and bathroom_vent_idx is not None:
                        current_vent_state = state.devices.get(bathroom_vent_idx, "OFF")
                        semantic_name = device_name(state, bathroom_vent_idx, "Unknown")

                        # Phase A: Force-engage the fan if it is currently offline
                        if current_vent_state != "ON":
                            follow_up_events.append(Event(
                                type=EventType.HUB_STATE_CHANGED,
                                payload = {"idx": bathroom_vent_idx, "state": "ON", "origin": "AUTOMATION"}
                            ))
                            automation_logger.info(
                                f"[Shower Automation] Hot water sustained flow verified "
                                f"({len(AutomationEngine._hot_water_pulses)} pulses/10s). "
                                f"Auto-engaging {AutomationEngine.format_device_ref(state, bathroom_vent_idx)}."
                            )

                        # Phase B: Manual Override Hijack & Rolling Overrun Extension
                        # Dynamically pushes the 5-minute safety lock deadline forward into the future.
                        # This establishes the rolling高度 debounce loop until the flow completely halts.
                        deadline = int(now_ts) + 300  # 5 minutes from the current pulse tick
                        follow_up_events.append(Event(
                            type=EventType.TIMER_SCHEDULED,
                            payload={
                                "timer_id": "bath1_vent_lock",
                                "deadline": deadline,
                                "event_type": "BATH1_VENT_LOCK_EXPIRED",
                                "event_payload": {
                                    "idx": bathroom_vent_idx,
                                    "name": semantic_name,
                                    "type": "switch",
                                    "target_state": "Climate Safe"
                                }
                            }
                        ))
                        # Downgrade rolling watchdog logs to DEBUG to protect the terminal from high-frequency pulse text noise
                        automation_logger.debug(
                            f"[X-RAY] Shower active. Extended ventilator tracking lock 'bath1_vent_lock' deadline to absolute UNIX: {deadline}."
                        )

        return follow_up_events