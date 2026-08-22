// --- file: frontend/blocky.js ---
// Phase B19: Domoticz If/Do + Else-if/Else (first-match); branches YAML; wake from Compares.
// Phase B4/H4: nested AND/OR/NOT Logic groups in Compare; OR-list migrator; legacy When/OR blocks removed.
// Discrete Compare labels: ordered AND — first wake (device or OR) → turns; later siblings → is.
// Duplicate fix: reshape b_condition_device on BLOCK_CREATE (init shaped the dropdown-default entity).
// Toolbox: Control · Logic (and/or) · Conditions · Actions; bare Else/NOT retired from toolbox.
// Device defaults: Hidden OFF → zwave.buro_licht ON; Hidden ON → door sauna opens / zwave.vent.sauna ON.
// Legacy Phase 6B: unified Blockly canvas for schema v2 (trigger + ordered cases) — retired.
// Contextual dropdowns: only show entries valid for the current trigger / device type.
// Phase 6C: rich action authoring — Hue preset XOR custom color (iro→bri/xy), blinds open %, Sonos/Onkyo volume, Sonos station.
// Phase B10A: editor trust — Hue picker-only / type-switch rebuild / no restore-modal;
//   toolbar Delete (no trashcan); Blockly Events disable/enable paired (v13 refcount); dirty from canvas.
// Phase B10B+D: events: catalog (UUID bus) — no family triggers / SCENE_* strings;
//   per-rule enabled; unique rule names; dashboard/confirm live on the event row.
// Phase B10E: Automations Library (UE/UR/SE/SR/D + C on UE), UE form (no Blockly),
//   SE catalog view-only, SR name = SE catalog name, When/Fire user vs system,
//   fire allowlist for unused system (Sauna/IR ON/OFF always).
// Phase B9A: sensor/host-gauge pickers (G2 — trigger+condition, never action);
//   sauna/IR status = condition-only; numeric compare on device conditions +
// Phase B10K: timings stopwatch (no auto-open); shutter OPEN/CLOSED (no FORCE/POS);
//   visible blinds→shutters; RFX ON/OFF no Hue color. G3: OWM poll 10′ (config).
// Phase B9C: temp_hum ATTR (temp+hum); shutters OPEN/CLOSED/open-% on When+if + Set open %;
//   audio ON/OFF/volume on When+if; open-% UI / closed-% YAML (B6C helpers);
//   open↔closed inequality flip on emit/load (`blockyInvertCompareOp`).

/** Min viewport width for History / Automation and the top-row join (tablets+). */
const WANOS_WIDE_MIN_PX = 768;

/** History & Automation: bounce phones to Device Explorer (also on shrink).
 *  Returns true when the viewport is too narrow (caller should abort init). */
function wanosRedirectIfNarrow() {
    const mq = window.matchMedia(`(min-width: ${WANOS_WIDE_MIN_PX}px)`);
    const bounce = () => {
        if (!mq.matches) window.location.replace("/deviceexplorer.html");
    };
    bounce();
    if (typeof mq.addEventListener === "function") mq.addEventListener("change", bounce);
    else if (typeof mq.addListener === "function") mq.addListener(bounce);
    return !mq.matches;
}

const BLOCKY_EDGE_STATES = [
    ["ON", "ON"], ["OFF", "OFF"]
];

/** B19: single If/Do control root (Else-if chain via next; bare Else retired). */
const BLOCKY_ROOT_TRIGGERS = new Set(["b_if_do"]);
/** @deprecated legacy — kept only so old workspaces dispose cleanly; not in toolbox. */
const BLOCKY_LEGACY_TRIGGERS = new Set([
    "b_trig_device", "b_trig_or", "b_trig_event", "b_trig_event_sys"
]);
/** Event-trigger roots (user or system) — same wire shape { event: uuid }. */
const BLOCKY_EVENT_TRIGGERS = new Set(["b_trig_event", "b_trig_event_sys"]);
/** Event OR-edge block types. */
const BLOCKY_EVENT_EDGES = new Set(["b_trig_event_edge", "b_trig_event_edge_sys"]);
/** Fire-event action block types. */
const BLOCKY_EVENT_ACTIONS = new Set(["b_action_event", "b_action_event_sys"]);
/** B19 control branch chain. */
const BLOCKY_CONTROL_BRANCH = new Set(["b_if_do", "b_else_if"]);
/** Retired bare Else — kept only so old canvases dispose; not in toolbox. */
const BLOCKY_LEGACY_ELSE = "b_else";
/** Event Compare block types. */
const BLOCKY_EVENT_COMPARES = new Set(["b_condition_event", "b_condition_event_sys"]);
/**
 * Sensor / temp-class — B9A (G2): allowed for trigger (When) + condition (if), never
 * action. Motion is handled separately (trigger only, never condition/action).
 */
const BLOCKY_SENSOR_LIKE_TYPES = new Set([
    "sensor", "temp_hum", "temp", "hum", "power", "energy", "fluid"
]);

/** Types that can appear as action targets. */
const BLOCKY_ACTUATOR_TYPES = new Set([
    "switch", "light", "blinds", "shutter", "speaker", "media_player"
]);

/**
 * B9A (G2): session-status sensors mirror sauna/IR ON/OFF but are condition (if)
 * only — never a When trigger, never an action. Discrete ON/OFF compare (not numeric).
 */
const BLOCKY_STATUS_CONDITION_ONLY = new Set([
    "sensor.generic.sauna_status", "sensor.generic.ir_status"
]);

/** B9A: host gauges published for dashboard/telemetry but hidden from every Blockly picker. */
const BLOCKY_HOST_GAUGE_HIDDEN = new Set([
    "sensor.generic.host_load_average_1m", "sensor.generic.host_load_average_5m"
]);

/** B9A: friendly Blockly labels for host/system gauges (overrides device_metadata name). */
const BLOCKY_HOST_GAUGE_LABELS = {
    "sensor.temp_hum.host_cpu_temperature": "Host CPU Temperature",
    "sensor.generic.host_cpu_usage": "Host CPU Usage",
    "sensor.generic.host_memory_free": "Host Memory Free",
    "sensor.generic.host_disk_free_root": "Host Disk Free (Root)",
    "sensor.generic.host_log2ram_free": "Host Log2Ram Free",
    "sensor.generic.host_load_average_15m": "Host average load %",
    "sensor.generic.wanos_db_size": "WanOS DB size",
    "sensor.generic.mains_voltage": "Mains voltage"
};

/**
 * B9A Silent-loss B+C — legal schema keys (must match core/config.py models).
 * UI-owned keys are re-emitted from Blockly; remaining legal keys ride as opaque
 * bags on the block (`_wanosOpaque`) and merge back on Save (C). Non-preservable
 * structure sets reasons that block Save (B).
 */
const BLOCKY_ACTION_LEGAL_KEYS = new Set([
    "entity_id", "state", "event", "target", "scene", "preset", "bri", "xy", "volume", "station"
]);
/** Keys Blockly authoring currently re-emits for actions (rest → opaque). */
const BLOCKY_ACTION_UI_KEYS = new Set([
    "entity_id", "state", "event", "preset", "bri", "xy", "volume", "station"
]);
const BLOCKY_CONDITION_LEGAL_KEYS = new Set([
    "type", "entity_id", "event", "is", "op", "attribute"
]);
const BLOCKY_CONDITION_UI_KEYS = new Set([
    "type", "entity_id", "event", "is", "op", "attribute"
]);
const BLOCKY_TRIGGER_LEGAL_KEYS = new Set([
    "entity_id", "state", "event", "op", "attribute"
]);
const BLOCKY_TRIGGER_UI_KEYS = new Set([
    "entity_id", "state", "event", "op", "attribute"
]);
const BLOCKY_SUPPORTED_CONDITION_TYPES = new Set(["device_state", "time_of_day", "event"]);

/** Deep-enough copy for opaque bag values (scalars / small arrays / plain objects). */
function blockyOpaqueClone(value) {
    if (Array.isArray(value)) return value.map(blockyOpaqueClone);
    if (value && typeof value === "object") {
        const out = {};
        Object.keys(value).forEach((k) => {
            out[k] = blockyOpaqueClone(value[k]);
        });
        return out;
    }
    return value;
}

/**
 * Collect legal keys present on source that Blockly UI does not own.
 * Illegal / unknown-to-schema keys are ignored (API `extra=forbid` would reject them).
 */
function blockyOpaqueFromSource(source, legalKeys, uiKeys) {
    const bag = {};
    if (!source || typeof source !== "object") return bag;
    Object.keys(source).forEach((k) => {
        if (!legalKeys.has(k) || uiKeys.has(k)) return;
        const v = source[k];
        if (v === undefined || v === null || v === "") return;
        bag[k] = blockyOpaqueClone(v);
    });
    return bag;
}

function blockyAttachOpaque(block, bag) {
    if (!block) return;
    if (bag && Object.keys(bag).length) block._wanosOpaque = bag;
    else delete block._wanosOpaque;
}

/** Merge opaque bag into an emitted object; UI-emitted keys win. */
function blockyMergeOpaque(out, block) {
    if (!out || !block || !block._wanosOpaque) return out;
    Object.keys(block._wanosOpaque).forEach((k) => {
        if (!(k in out)) out[k] = blockyOpaqueClone(block._wanosOpaque[k]);
    });
    return out;
}

/**
 * Tall FieldDropdown menus (entity/event) open upward near the top of the canvas
 * and get clipped. Cap menu height (scroll inside) and clamp to the page viewport.
 */
function blockyConfigureDropdownChrome(Blockly) {
    if (!Blockly) return;
    // Fraction of viewport height — Blockly scrolls the menu when content exceeds this.
    if (Blockly.FieldDropdown) {
        Blockly.FieldDropdown.MAX_MENU_HEIGHT_VH = 0.4;
    }
    // Position/size against the full page so the popup is not bound to the workspace box.
    if (Blockly.DropDownDiv && typeof Blockly.DropDownDiv.setBoundsElement === "function") {
        Blockly.DropDownDiv.setBoundsElement(document.body);
    }
}

/**
 * Catalog UUIDs seeded for bus/dashboard but excluded from Blockly event pickers.
 * Keep in sync with core.event_catalog.NON_PICKABLE_SYSTEM_UUIDS.
 * Prefer device Compares for telemetry; keep schedule + sauna/IR session SEs pickable.
 */
const BLOCKY_NON_PICKABLE_EVENT_IDS = new Set([
    "c3457c08-c26e-4ab7-8c32-76e0a746d6c3", // HUB_STATE_CHANGED
    "02d6b1d7-de0b-41f1-b89b-f371e2d35cea", // DOOR_CHANGED — use door device Compare
    "0b334052-620b-4379-89fb-8a548948873e", // TEMP_UPDATED
    "317b453b-18bb-4083-8b62-e14ba2bc4d26", // HUMIDITY_UPDATED
    "d6bebc9e-394e-4806-a007-4f863a7ccf5e", // POWER_UPDATED
    "0117e989-cf45-4359-98d3-9656284eb577", // SUNRISE_SUNSET_UPDATE — use schedule edges
    "b94ab2e2-a5d6-4651-9ff8-c832221c9169", // SAUNA_MODULATION_UPDATED
    "8bcbaacf-b072-422d-a270-b7810228684b", // IR_MODULATION_UPDATED
    "9fa21346-3952-4267-b2fd-c3362e520431", // SAUNA_SETPOINT_CHANGED
    "cef390eb-f9e0-4757-ae34-0e7918d49a9e", // WATER_PULSE
    "a1f2fe49-82db-4011-a9bb-c8afdbd46358", // KWH_PULSE
    "fff4c790-1b10-4084-a11f-4d7bf519ce40", // SENSOR_ERROR
    "718d81a1-c9bb-4f02-8b92-78de27c9aae9"  // SAUNA_HOLD
]);

/** Preferred new-block device refs (Hidden OFF vs soft-hidden catalog). */
const BLOCKY_DEFAULT_DEVICE_NORMAL = {
    condition: { entity_id: "zwave.buro_licht", state: "ON" },
    action: { entity_id: "zwave.buro_licht", state: "ON" }
};
const BLOCKY_DEFAULT_DEVICE_HIDDEN = {
    condition: { entity_id: "sensor.door.sauna_deur", state: "OPEN" },
    action: { entity_id: "zwave.vent.sauna", state: "ON" }
};

/**
 * Defaults for new device Compare / Set blocks — follows Automations Hidden toggle.
 * @param {"condition"|"action"} role
 * @returns {{ entity_id: string, state: string }}
 */
function blockyPreferredDeviceDefaults(role) {
    const hidden = !!(BlockyRT.app && BlockyRT.app.showHiddenEntities);
    const table = hidden ? BLOCKY_DEFAULT_DEVICE_HIDDEN : BLOCKY_DEFAULT_DEVICE_NORMAL;
    const row = table[role] || BLOCKY_DEFAULT_DEVICE_NORMAL.action;
    return { entity_id: row.entity_id, state: row.state };
}

/**
 * Apply preferred ENTITY + state on a freshly inited device block (toolbox / flyout).
 * Load/duplicate overwrite via setFieldValue after init — safe.
 * @param {Blockly.Block} block
 * @param {"condition"|"action"} role
 */
function blockyApplyPreferredDeviceDefaults(block, role) {
    if (!block || BlockyRT.loading) return;
    const pref = blockyPreferredDeviceDefaults(role);
    if (!pref.entity_id) return;
    try {
        blockySafeSetField(block, "ENTITY", pref.entity_id);
    } catch (e) { /* picker may not list eid yet */ }
    if (role === "condition") {
        blockyConditionUpdateShape(block, { forceState: pref.state });
    } else {
        blockyForceDropdownValue(block, "STATE", pref.state);
        blockyActionUpdateRichShape(block, { forceState: pref.state });
    }
}

/**
 * B10E: system UUIDs always fireable as actions even with no listening rule
 * (hardcoded Sauna/IR handlers). Keep in sync with core.event_catalog.FIRE_ALWAYS_SYSTEM_UUIDS.
 */
const BLOCKY_FIRE_ALWAYS_SYSTEM_IDS = new Set([
    "39120e7f-93e2-46ba-af70-9b6d7bf08df3", // SAUNA_ON
    "08b79199-86aa-4a1e-a29c-20ef2eb74e98", // SAUNA_OFF
    "056c3ade-659a-49e0-87f2-2c60e84ca792", // IR_ON
    "a97bba4d-78d3-4ce2-b134-fff36c2cd88c"  // IR_OFF
]);

/** localStorage key for Library sort mode (kind | name). */
const BLOCKY_LIBRARY_SORT_KEY = "blockyLibrarySortMode";

/** Resolve catalog event id → picker/UI label (wire still stores UUID). */
function blockyEventLabel(eventId) {
    const id = String(eventId || "");
    if (!id) return "(no event)";
    const rows = BlockyRT.catalogEvents || [];
    const hit = rows.find((r) => r && String(r.id) === id);
    // Catalog name only — library/dropdown badges already mark origin (no "system:" prefix).
    if (hit && hit.name) return String(hit.name);
    return id;
}

/** B10D / event-name spirit: trim + casefold for uniqueness compares. */
function blockyNormalizeNameKey(name) {
    return String(name || "").trim().toLowerCase();
}

function blockyEntityMeta(eid) {
    const app = BlockyRT.app;
    if (app && Array.isArray(app.entityOptions)) {
        return app.entityOptions.find((o) => o.eid === eid) || null;
    }
    return null;
}

function blockyEntityTypeOf(eid) {
    const opt = blockyEntityMeta(eid);
    const e = String(eid || "");
    const nativeType = opt && opt.type ? String(opt.type).toLowerCase() : "";
    // B10K / B9C: native blinds/sensors/speakers must win over rebuildEntityOptions'
    // missing-rpt fallback of "switch" (that fallback is for actuators only).
    if (nativeType === "blinds" || nativeType === "shutter") return nativeType;
    if (e.startsWith("blinds.")) return "blinds";
    if (nativeType === "temp_hum" || nativeType === "temp" || nativeType === "hum"
        || nativeType === "power" || nativeType === "energy" || nativeType === "fluid"
        || nativeType === "sensor" || nativeType === "motion" || nativeType === "door"
        || nativeType === "speaker" || nativeType === "media_player"
        || nativeType === "climate" || nativeType === "host") {
        return nativeType;
    }
    // Product light|switch only overrides switch-class actuators (Timers & types).
    if (opt && opt.resolvedProductType) {
        const rpt = String(opt.resolvedProductType).toLowerCase();
        if ((rpt === "light" || rpt === "switch")
            && (!nativeType || nativeType === "switch" || nativeType === "light"
                || nativeType === "unknown")) {
            return rpt;
        }
    }
    if (nativeType) return nativeType;
    if (e.startsWith("sensor.temp_hum.")) return "temp_hum";
    if (e.startsWith("hue.")) return "light";
    if (e.startsWith("media_player.")) return "speaker";
    if (e.startsWith("sensor.door.") || e.startsWith("door.")) return "door";
    if (e.includes("motion")) return "motion";
    if (e.startsWith("sensor.")) return "sensor";
    if (e.startsWith("switch.") || e.startsWith("zwave.") || e.startsWith("rfx.")) return "switch";
    return "";
}

function blockyEntityOriginOf(eid) {
    const opt = blockyEntityMeta(eid);
    return opt && opt.origin ? String(opt.origin).toLowerCase() : "";
}

function blockyIsMotionEntity(optOrEid) {
    const type = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.type : null)
        || blockyEntityTypeOf(typeof optOrEid === "string" ? optOrEid : (optOrEid && optOrEid.eid))
        || ""
    ).toLowerCase();
    if (type === "motion") return true;
    const eid = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.eid : optOrEid) || ""
    );
    const name = (optOrEid && typeof optOrEid === "object" ? optOrEid.name : "") || "";
    return /motion/i.test(eid) || /motion/i.test(name);
}

function blockyIsSensorLikeEntity(optOrEid, typeHint) {
    if (blockyIsMotionEntity(optOrEid)) return false; // motion ≠ temp/power class
    const type = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.type : typeHint)
        || blockyEntityTypeOf(typeof optOrEid === "string" ? optOrEid : (optOrEid && optOrEid.eid))
        || ""
    ).toLowerCase();
    if (BLOCKY_SENSOR_LIKE_TYPES.has(type)) return true;
    const eid = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.eid : optOrEid) || ""
    );
    if (eid.startsWith("sensor.door.")) return false;
    if (eid.startsWith("sensor.")) return true;
    return false;
}

function blockyIsActuatorEntity(optOrEid) {
    const type = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.type : null)
        || blockyEntityTypeOf(typeof optOrEid === "string" ? optOrEid : (optOrEid && optOrEid.eid))
        || ""
    ).toLowerCase();
    if (BLOCKY_ACTUATOR_TYPES.has(type)) return true;
    const eid = String(
        (optOrEid && typeof optOrEid === "object" ? optOrEid.eid : optOrEid) || ""
    );
    return (
        eid.startsWith("switch.")
        || eid.startsWith("zwave.")
        || eid.startsWith("rfx.")
        || eid.startsWith("hue.")
        || eid.startsWith("blinds.")
        || eid.startsWith("media_player.")
    );
}

function blockyEntityAllowedForRole(opt, role) {
    if (role === "action") {
        // Motion / sensors / doors cannot be actioned.
        return blockyIsActuatorEntity(opt) && !blockyIsMotionEntity(opt);
    }
    const eid = String((opt && typeof opt === "object" ? opt.eid : opt) || "");
    if (BLOCKY_STATUS_CONDITION_ONLY.has(eid)) {
        // Sauna/IR session status — condition (if) only; never a When trigger.
        return role === "condition";
    }
    if (blockyIsMotionEntity(opt)) {
        // B19: motion wakes via device Compare (If), same as other discrete devices.
        // Never an action target.
        return role === "trigger" || role === "condition";
    }
    // G2: sensor-like classes (temp/hum/power/energy/fluid/type:sensor) are now
    // legal for both trigger (When) and condition (if) — see blockyConditionIsNumeric.
    return role === "trigger" || role === "condition";
}

function blockyCaseMatchOptions(caseBlock) {
    let opts;
    try {
        const root = caseBlock.getRootBlock && caseBlock.getRootBlock();
        if (root && root.type === "b_trig_device") {
            const eid = root.getFieldValue("ENTITY");
            const type = blockyEntityTypeOf(eid);
            if (blockyTriggerHidesCaseMatch(root)) {
                // B9A/B9C: threshold or OPEN/CLOSED/volume mode lives on the When block.
                opts = [["(set on trigger)", "NONE"]];
            } else if (type === "blinds" || type === "shutter") {
                opts = [
                    ["when transitioned", "ANY"],
                    ["when OPEN", "OPEN"],
                    ["when CLOSED", "CLOSED"]
                ];
            } else {
                opts = [
                    ["when transitioned", "ANY"],
                    ["when ON", "ON"],
                    ["when OFF", "OFF"]
                ];
            }
        } else if (root && root.type === "b_trig_or") {
            // OR roots discriminate via conditions only (no to_state chrome).
            opts = [["(conditions only)", "NONE"]];
        } else if (root && BLOCKY_EVENT_TRIGGERS.has(root.type)) {
            // B10B/E: event cases keep conditions; empty = always. No ON/OFF "if" chrome.
            opts = [["(conditions only)", "NONE"]];
        }
    } catch (e) { /* ignore */ }
    if (!opts) {
        opts = [
            ["when transitioned", "ANY"],
            ["when ON", "ON"],
            ["when OFF", "OFF"]
        ];
    }
    return opts;
}

/** True when the case's root trigger is event-based (single event or OR of events). */
function blockyRootIsEventTrigger(root) {
    if (!root) return false;
    if (BLOCKY_EVENT_TRIGGERS.has(root.type)) return true;
    if (root.type !== "b_trig_or") return false;
    try {
        let e = root.getInputTargetBlock("EDGES");
        let hasEvent = false;
        let hasDevice = false;
        while (e) {
            if (BLOCKY_EVENT_EDGES.has(e.type)) hasEvent = true;
            if (e.type === "b_trig_device_edge") hasDevice = true;
            e = e.getNextBlock();
        }
        return hasEvent && !hasDevice;
    } catch (err) {
        return false;
    }
}

/**
 * B10B: hide useless "if"/MATCH chrome on event-triggered cases.
 * B9A: same for numeric device triggers — threshold lives on the trigger, not MATCH.
 * Keeps CONDS + ACTIONS; empty conditions = always run.
 */
function blockyCaseUpdateEventChrome(caseBlock) {
    if (!caseBlock || caseBlock.type !== "b_case") return;
    let root = null;
    try { root = caseBlock.getRootBlock && caseBlock.getRootBlock(); } catch (e) { /* ignore */ }
    // B9A sensors + B9C level (OPEN/CLOSED/PCT on When) — hide per-case MATCH.
    const hideChrome = blockyRootIsEventTrigger(root) || blockyTriggerHidesCaseMatch(root);
    const matchField = caseBlock.getField("MATCH");
    const ifLabel = caseBlock.getField("IF_LABEL");
    try {
        if (matchField && typeof matchField.setVisible === "function") {
            matchField.setVisible(!hideChrome);
        }
        if (ifLabel && typeof ifLabel.setVisible === "function") {
            ifLabel.setVisible(!hideChrome);
        }
        if (hideChrome && matchField) {
            matchField.setValue("NONE");
        }
        if (typeof caseBlock.render === "function") caseBlock.render();
    } catch (e) { /* ignore */ }
}

function blockyEdgeStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    if (type === "blinds" || type === "shutter") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"]];
    }
    return BLOCKY_EDGE_STATES.slice();
}

/**
 * Action state entries by device type / origin.
 * RFX / Sonos / Onkyo / Epson: no FORCE_* (engine always-forces RFX; OFF-only for the AV trio).
 * Shutters: OPEN/CLOSED (+ open % row when OPEN — B9C restores B6C).
 */
function blockyActionStateOptions(block) {
    const eid = block.getFieldValue("ENTITY");
    const type = blockyEntityTypeOf(eid);
    const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
    if (type === "blinds" || type === "shutter") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"]];
    }
    // RFX even when product type is light: ON/OFF only (engine always-force; no Hue color).
    if (origin === "rfxcom") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    if (type === "light" || type === "hue") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    if (type === "speaker" || type === "media_player") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    // Epson: always-forced at engine — no FORCE_* in the menu (RFX handled above).
    if (origin === "epson") {
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    // Z-Wave / generic switches — explicit FORCE remains available.
    return [
        ["ON", "ON"], ["OFF", "OFF"],
        ["FORCE_ON", "FORCE_ON"], ["FORCE_OFF", "FORCE_OFF"]
    ];
}

/**
 * Walk up from a Compare / Logic block to its If or Else-if control root.
 * @param {Blockly.Block|null|undefined} block
 * @returns {Blockly.Block|null}
 */
function blockyFindConditionBranchRoot(block) {
    let b = block || null;
    while (b) {
        if (b.type === "b_if_do" || b.type === "b_else_if") return b;
        if (typeof b.getSurroundParent === "function") {
            const sur = b.getSurroundParent();
            if (sur) {
                b = sur;
                continue;
            }
        }
        if (typeof b.getParent === "function") {
            b = b.getParent();
            continue;
        }
        break;
    }
    return null;
}

/**
 * True when a condition statement chain (and nested Logic groups) contains an event Compare.
 * @param {Blockly.Block|null|undefined} start
 * @returns {boolean}
 */
function blockyConditionTreeHasEvent(start) {
    let b = start || null;
    while (b) {
        if (BLOCKY_EVENT_COMPARES.has(b.type)) return true;
        if (b.type === "b_logic_and" || b.type === "b_logic_or") {
            if (blockyConditionTreeHasEvent(b.getInputTargetBlock("CHILDREN"))) return true;
        } else if (b.type === "b_logic_not") {
            if (blockyConditionTreeHasEvent(b.getInputTargetBlock("CHILD"))) return true;
        }
        b = typeof b.getNextBlock === "function" ? b.getNextBlock() : null;
    }
    return false;
}

/**
 * Call ``fn`` for every device Compare in a condition statement tree.
 * @param {Blockly.Block|null|undefined} start
 * @param {(b: Blockly.Block) => void} fn
 */
function blockyForEachConditionDeviceInTree(start, fn) {
    let b = start || null;
    while (b) {
        if (b.type === "b_condition_device") fn(b);
        else if (b.type === "b_logic_and" || b.type === "b_logic_or") {
            blockyForEachConditionDeviceInTree(b.getInputTargetBlock("CHILDREN"), fn);
        } else if (b.type === "b_logic_not") {
            blockyForEachConditionDeviceInTree(b.getInputTargetBlock("CHILD"), fn);
        }
        b = typeof b.getNextBlock === "function" ? b.getNextBlock() : null;
    }
}

function blockyResolveProductType(eid, origin, overrides) {
    const ov = overrides && overrides[eid];
    if (ov === "light" || ov === "switch") return ov;
    if (String(origin || "").toLowerCase() === "hue") return "light";
    return "switch";
}

/** Auto-off per-type tier key (mirrors lightingautooff.js). */
function blockyAutoOffTypeKey(eid, origin, deviceType, overrides) {
    const t = String(deviceType || "").toLowerCase();
    if (t === "speaker" || t === "media_player") return "speaker";
    if (t === "switch" || t === "light" || String(origin || "").toLowerCase() === "hue") {
        return blockyResolveProductType(eid, origin, overrides);
    }
    return t || "unknown";
}

/** True when live device status is omitted from the rule device table (motion only). */
function blockyDeviceTableSkipsStatus(meta) {
    if (!meta || typeof meta !== "object") return true;
    const type = String(meta.type || "").toLowerCase();
    const idxNum = Number(meta.idx);
    if (type === "motion" || (idxNum >= 75000 && idxNum < 76000)) return true;
    const name = String(meta.name || meta.label || "").toLowerCase();
    if (name.includes("motion") || name.includes("pir") || name.includes("beweging")) return true;
    return false;
}

/** True for blinds/shutter device types (rule device table status wording). */
function blockyIsShutterDeviceType(type) {
    const t = String(type || "").toLowerCase();
    return t === "blinds" || t === "shutter" || t === "shutters";
}

/** Format stored shutter closed-% / OPEN/CLOSED for the rule device table. */
function blockyFormatShutterTableStatus(raw) {
    const su = String(raw == null ? "" : raw).trim().toUpperCase();
    if (su === "OPEN" || su === "ON") return "Open";
    if (su === "CLOSED" || su === "OFF") return "Closed";
    const closedPct = parseInt(raw, 10);
    if (!Number.isFinite(closedPct)) return String(raw);
    if (closedPct <= 0) return "Open";
    if (closedPct >= 100) return "Closed";
    const openPct = blockyOpenPctFromStored(closedPct);
    return `${openPct} % Open`;
}

/** Format live hub state for the rule device table. */
function blockyFormatDeviceTableStatus(raw, meta) {
    if (raw === null || raw === undefined) return "SYNC…";
    if (raw === "DEAD") return "DEAD";
    const type = String((meta && meta.type) || "").toLowerCase();
    if (type === "door") return String(raw);
    if (blockyIsShutterDeviceType(type)) {
        return blockyFormatShutterTableStatus(raw);
    }
    if (typeof raw === "object" && raw !== null) {
        if (raw.temp !== undefined && raw.hum !== undefined) {
            return `${parseFloat(raw.temp).toFixed(1)} °C / ${raw.hum}%`;
        }
        if (raw.temp !== undefined) return `${parseFloat(raw.temp).toFixed(1)} °C`;
        if (raw.hum !== undefined) return `${raw.hum}%`;
        if (type === "speaker" || type === "media_player") {
            const st = raw.state != null ? String(raw.state) : "";
            if (st === "OFF" || raw.volume === null) return st || "OFF";
            if (raw.volume != null) return `${st || "ON"} · vol ${raw.volume}`;
            return st || "ON";
        }
        if (raw.state != null) return String(raw.state);
        const keys = Object.keys(raw);
        if (keys.length === 1 && typeof raw[keys[0]] !== "object") {
            return String(raw[keys[0]]);
        }
        return "—";
    }
    return String(raw);
}

/**
 * Flat sibling chain under one AND list (IF stack or Logic AND CHILDREN).
 * @param {Blockly.Block|null|undefined} start
 * @returns {Blockly.Block[]}
 */
function blockyFlatAndNodesFromStart(start) {
    const out = [];
    let b = start || null;
    while (b) {
        out.push(b);
        b = typeof b.getNextBlock === "function" ? b.getNextBlock() : null;
    }
    return out;
}

/**
 * B23: one OR arm → child list for implicit/explicit AND.
 * @param {Blockly.Block|null|undefined} arm
 * @returns {Blockly.Block[]}
 */
function blockyNormalizeAndArmChildren(arm) {
    if (!arm) return [];
    if (arm.type === "b_logic_and") {
        return blockyFlatAndNodesFromStart(arm.getInputTargetBlock("CHILDREN"));
    }
    return [arm];
}

/**
 * B23: top-level IF chain has an event Compare and no Logic groups (event-only wake branch).
 * @param {Blockly.Block|null|undefined} start
 * @returns {boolean}
 */
function blockyBranchHasFlatEventGate(start) {
    let b = start || null;
    while (b) {
        if (b.type === "b_logic_and" || b.type === "b_logic_or" || b.type === "b_logic_not") {
            return false;
        }
        if (BLOCKY_EVENT_COMPARES.has(b.type)) return true;
        b = typeof b.getNextBlock === "function" ? b.getNextBlock() : null;
    }
    return false;
}

/**
 * B23: device Compare blocks that may wake within one AND list (mirrors core/condition_tree.py).
 * @param {Blockly.Block[]} nodes
 * @returns {Blockly.Block[]}
 */
function blockyWakeDeviceBlocksInAndList(nodes) {
    const wakes = [];
    let seenFirstDevice = false;
    for (const node of nodes || []) {
        if (!node) continue;
        const t = node.type;
        if (BLOCKY_EVENT_COMPARES.has(t) || t === "b_condition_time") continue;
        if (t === "b_condition_device") {
            if (!seenFirstDevice) {
                wakes.push(node);
                seenFirstDevice = true;
            }
            continue;
        }
        if (t === "b_logic_not") continue;
        if (t === "b_logic_or") {
            let arm = node.getInputTargetBlock("CHILDREN");
            while (arm) {
                wakes.push(...blockyWakeDeviceBlocksInAndList(blockyNormalizeAndArmChildren(arm)));
                arm = arm.getNextBlock();
            }
        } else if (t === "b_logic_and") {
            wakes.push(...blockyWakeDeviceBlocksInAndList(blockyNormalizeAndArmChildren(node)));
        }
    }
    return wakes;
}

/**
 * B23: all device Compare blocks that may wake in one If/Else-if branch.
 * @param {Blockly.Block|null|undefined} ifStart
 * @returns {Blockly.Block[]}
 */
function blockyCollectWakeDeviceBlocks(ifStart) {
    return blockyWakeDeviceBlocksInAndList(blockyFlatAndNodesFromStart(ifStart));
}

/**
 * True when ``target`` is this node or nested under a Logic group.
 * @param {Blockly.Block|null|undefined} node
 * @param {Blockly.Block|null|undefined} targetBlock
 * @returns {boolean}
 */
function blockyBlockContainsDeviceCompare(node, targetBlock) {
    if (!node || !targetBlock) return false;
    if (node.type === "b_condition_device") return node.id === targetBlock.id;
    if (node.type === "b_logic_not") {
        return blockyBlockContainsDeviceCompare(node.getInputTargetBlock("CHILD"), targetBlock);
    }
    if (node.type === "b_logic_or" || node.type === "b_logic_and") {
        let arm = node.getInputTargetBlock("CHILDREN");
        while (arm) {
            if (arm.type === "b_logic_and") {
                let c = arm.getInputTargetBlock("CHILDREN");
                while (c) {
                    if (blockyBlockContainsDeviceCompare(c, targetBlock)) return true;
                    c = c.getNextBlock();
                }
            } else if (blockyBlockContainsDeviceCompare(arm, targetBlock)) {
                return true;
            }
            arm = arm.getNextBlock();
        }
    }
    return false;
}

/**
 * AND sibling list that owns ``targetBlock`` (explicit AND CHILDREN or flat If chain).
 * @param {Blockly.Block} targetBlock
 * @returns {Blockly.Block|null|undefined}
 */
function blockyAndListHeadForBlock(targetBlock) {
    let innermostAndChildren = null;
    let p = targetBlock;
    while (p) {
        const parent = typeof p.getParent === "function" ? p.getParent() : null;
        if (!parent) break;
        if (parent.type === "b_logic_and") {
            innermostAndChildren = parent.getInputTargetBlock("CHILDREN");
        }
        if (parent.type === "b_if_do" || parent.type === "b_else_if") {
            if (innermostAndChildren) return innermostAndChildren;
            return parent.getInputTargetBlock("IF");
        }
        p = parent;
    }
    return null;
}

/**
 * Ordered AND gate wording: first wake segment → turns/opens; later siblings + nested OR → is/is open.
 * @param {Blockly.Block|null|undefined} andListHead
 * @param {Blockly.Block} targetBlock
 * @returns {boolean}
 */
function blockyDeviceCompareIsLevelGateInAndList(andListHead, targetBlock) {
    const nodes = blockyFlatAndNodesFromStart(andListHead);
    let pastFirstWake = false;

    for (const node of nodes) {
        if (!node) continue;
        if (BLOCKY_EVENT_COMPARES.has(node.type) || node.type === "b_condition_time") {
            continue;
        }

        if (pastFirstWake) {
            if (blockyBlockContainsDeviceCompare(node, targetBlock)) return true;
            continue;
        }

        if (node.type === "b_condition_device") {
            if (node.id === targetBlock.id) return false;
            pastFirstWake = true;
            continue;
        }
        if (node.type === "b_logic_or") {
            if (blockyBlockContainsDeviceCompare(node, targetBlock)) return false;
            pastFirstWake = true;
            continue;
        }
        if (node.type === "b_logic_and") {
            if (blockyBlockContainsDeviceCompare(node, targetBlock)) {
                return blockyDeviceCompareIsLevelGateInAndList(
                    node.getInputTargetBlock("CHILDREN"),
                    targetBlock
                );
            }
            pastFirstWake = true;
            continue;
        }
    }
    return false;
}

/**
 * Device Compare uses level gate wording ("is ON") when it does not wake the branch.
 * B23+: ordered AND — first device or first OR-of-wakes → turns; all later siblings → is.
 * Flat event branches gate all devices; top-level OR-of-AND arms unchanged.
 * @param {Blockly.Block|null|undefined} block
 * @returns {boolean}
 */
function blockyConditionUsesLevelGateWording(block) {
    if (!block || block.isInFlyout || block.type !== "b_condition_device") return false;
    const root = blockyFindConditionBranchRoot(block);
    if (!root) return false;
    const ifStart = root.getInputTargetBlock("IF");
    if (blockyBranchHasFlatEventGate(ifStart)) return true;
    const andHead = blockyAndListHeadForBlock(block);
    if (!andHead) return false;
    return blockyDeviceCompareIsLevelGateInAndList(andHead, block);
}

/**
 * Rebuild discrete / level Compare chrome for every device Compare under all If/Else-if.
 * Used when event Compares are added/removed so "turns" ↔ "is" labels stay honest.
 */
function blockyRefreshAllConditionGateWording() {
    const ws = blockyWs();
    if (!ws) return;
    const blocks = typeof ws.getAllBlocks === "function" ? ws.getAllBlocks(false) : [];
    blocks.forEach((b) => {
        if (b.type !== "b_if_do" && b.type !== "b_else_if") return;
        blockyForEachConditionDeviceInTree(b.getInputTargetBlock("IF"), (d) => {
            blockyConditionUpdateShape(d);
        });
    });
}

/** Schedule a single gate-wording pass after create/delete/move settles. */
function blockyScheduleConditionGateWordingRefresh() {
    if (BlockyRT.gateWordingTimer) return;
    BlockyRT.gateWordingTimer = setTimeout(() => {
        BlockyRT.gateWordingTimer = null;
        blockyRefreshAllConditionGateWording();
    }, 0);
}

/**
 * Discrete STATE dropdown labels — "turns ON" when device-only wake; "is ON" when
 * the branch also has an event Compare (level gate after event wake).
 * @param {Blockly.Block} block
 * @returns {string[][]}
 */
function blockyConditionStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    const levelGate = blockyConditionUsesLevelGateWording(block);
    if (type === "blinds" || type === "shutter") {
        // Level profile normally owns shutters; keep opens/closes + changes state if discrete shape used.
        return levelGate
            ? [["is open", "0"], ["is closed", "100"], ["changes state", "ANY"]]
            : [["opens", "0"], ["closes", "100"], ["changes state", "ANY"]];
    }
    if (type === "door") {
        return levelGate
            ? [["is OPEN", "OPEN"], ["is CLOSED", "CLOSED"], ["changes state", "ANY"]]
            : [["opens", "OPEN"], ["closes", "CLOSED"], ["changes state", "ANY"]];
    }
    // Lights / switches / status.
    return levelGate
        ? [["is ON", "ON"], ["is OFF", "OFF"], ["changes state", "ANY"]]
        : [["turns ON", "ON"], ["turns OFF", "OFF"], ["changes state", "ANY"]];
}

/**
 * Level-profile MODE labels with the same turns/is context as discrete STATE.
 * @param {Blockly.Block} block
 * @param {{ modes?: string[][] }} profile
 * @returns {string[][]}
 */
function blockyConditionLevelModeOptions(block, profile) {
    const modes = (profile && profile.modes) || [];
    if (!blockyConditionUsesLevelGateWording(block)) return modes.slice();
    return modes.map((row) => {
        const label = row[0];
        const value = row[1];
        if (value === "ON") return ["is ON", value];
        if (value === "OFF") return ["is OFF", value];
        if (value === "OPEN") return ["is open", value];
        if (value === "CLOSED") return ["is closed", value];
        return [label, value];
    });
}

/** Compare op menu shared by numeric conditions and numeric device triggers. */
const BLOCKY_COMPARE_OPS = [
    ["==", "=="], ["!=", "!="], [">", ">"], [">=", ">="], ["<", "<"], ["<=", "<="]
];

/**
 * Human-readable label for a numeric operator used in condition blocks.
 * Describes the crossing direction to the author.
 * @param {string} op
 * @returns {string}
 */
function blockyOpCrossesLabel(op) {
    switch (op) {
        case ">":  return "crosses above";
        case ">=": return "reaches";
        case "<":  return "crosses below";
        case "<=": return "falls to";
        case "==": return "equals";
        case "!=": return "is not";
        default:   return "crosses above";
    }
}

/**
 * Compare UX profile for if-device conditions and When device triggers.
 * kind:
 *   sensor  — numeric OP/VALUE (+ optional temp/hum ATTR)
 *   level   — OPEN/CLOSED or ON/OFF plus optional PCT compare (shutters / audio)
 *   discrete — plain STATE dropdown (switches, lights, doors, …)
 */
function blockyConditionCompareProfile(eid) {
    const id = String(eid || "");
    if (BLOCKY_STATUS_CONDITION_ONLY.has(id)) return { kind: "discrete" };
    const type = blockyEntityTypeOf(id);
    if (type === "door" || blockyIsMotionEntity(id)) return { kind: "discrete" };

    // B9C: shutters — opens | closes | changes state | open % compare (UI open %, YAML closed %).
    if (type === "blinds" || type === "shutter") {
        return {
            kind: "level",
            modes: [
                ["opens", "OPEN"],
                ["closes", "CLOSED"],
                ["changes state", "ANY"],
                ["open %", "PCT"]
            ],
            attribute: "position",
            valueUi: "open_pct",
            unit: "% open",
            min: 0,
            max: 100
        };
    }
    // B9C: Sonos / Onkyo — turns ON | turns OFF | changes state | volume compare (0…max_volume).
    if (type === "speaker" || type === "media_player") {
        return {
            kind: "level",
            modes: [
                ["turns ON", "ON"],
                ["turns OFF", "OFF"],
                ["changes state", "ANY"],
                ["volume", "PCT"]
            ],
            attribute: "volume",
            valueUi: "raw",
            unit: "",
            min: 0,
            maxFromMeta: true
        };
    }
    if (type === "light" || type === "hue") return { kind: "discrete" };

    // Dual temp/hum — channel ATTR (host CPU temp-only stays °C-only).
    if (type === "temp_hum" || id.startsWith("sensor.temp_hum.")) {
        if (id.includes("host_cpu_temperature")) {
            return { kind: "sensor" };
        }
        return {
            kind: "sensor",
            attrs: ["temperature", "humidity"],
            attrLabels: [["temperature °C", "temperature"], ["humidity %", "humidity"]]
        };
    }
    if (blockyIsSensorLikeEntity(id, type)) return { kind: "sensor" };
    return { kind: "discrete" };
}

/** Unit suffix shown after numeric threshold (conditions + When). */
function blockySensorUnitLabel(eid, attr) {
    const id = String(eid || "");
    const type = blockyEntityTypeOf(id);
    const a = String(attr || "").toLowerCase();
    if (type === "temp_hum" || id.startsWith("sensor.temp_hum.")) {
        if (a === "humidity" || a === "hum") return "%";
        return "°C";
    }
    if (type === "hum" || a === "humidity") return "%";
    if (type === "temp" || a === "temperature" || a === "temp") return "°C";
    if (type === "power") return "W";
    if (type === "energy") return "kWh";
    if (id.includes("mains_voltage")) return "V";
    if (id.includes("host_cpu_usage") || id.includes("host_load_average")) return "%";
    if (id.includes("host_memory_free") || id.includes("host_log2ram_free")
        || id.includes("host_disk_free") || id.includes("wanos_db_size")) {
        return "MB";
    }
    return "";
}

/** Max for level PCT FieldNumber (volume from entity meta). */
function blockyLevelValueMax(eid, profile) {
    if (profile && profile.maxFromMeta) return blockyEntityMaxVolume(eid);
    if (profile && profile.max != null) return Number(profile.max);
    return 100;
}

/**
 * Numeric When / if — sensors always; level blocks only in PCT mode.
 * @param {string} eid
 * @param {object} [block] trigger or condition block (needed for level MODE)
 */
function blockyTriggerIsNumeric(eid, block) {
    const profile = blockyConditionCompareProfile(eid);
    if (profile.kind === "sensor") return true;
    if (profile.kind === "level" && block) {
        return block.getFieldValue("MODE") === "PCT";
    }
    return false;
}

/** True when case MATCH chrome should hide (threshold / mode lives on When). */
function blockyTriggerHidesCaseMatch(root) {
    if (!root || root.type !== "b_trig_device") return false;
    const profile = blockyConditionCompareProfile(root.getFieldValue("ENTITY"));
    return profile.kind === "sensor" || profile.kind === "level";
}

/** True when the condition block emits op/value (sensor gauges or level PCT). */
function blockyConditionIsNumericCompare(block) {
    if (!block) return false;
    const eid = block.getFieldValue("ENTITY");
    const profile = blockyConditionCompareProfile(eid);
    if (profile.kind === "sensor") return true;
    if (profile.kind === "level") return block.getFieldValue("MODE") === "PCT";
    return false;
}

function blockyConditionIsNumeric(eid, block) {
    if (block) return blockyConditionIsNumericCompare(block);
    return blockyConditionCompareProfile(eid).kind === "sensor";
}

/**
 * Rebuild the dynamic "is …" row on b_condition_device:
 * motion → fixed "motion" label (wake on detect; YAML is: ON);
 * sensors → temp/hum ATTR + OP + VALUE + unit;
 * level → MODE (OPEN/CLOSED/ON/OFF/PCT) + optional OP/VALUE;
 * discrete → STATE dropdown.
 */
function blockyConditionUpdateShape(block, opts) {
    if (!block || !window.Blockly || block._condUpdating) return;
    opts = opts || {};
    block._condUpdating = true;
    const Events = Blockly.Events;
    Events.disable();
    try {
        const eid = block.getFieldValue("ENTITY");
        const profile = blockyConditionCompareProfile(eid);

        const snap = {};
        ["STATE", "MODE", "OP", "ATTR", "VALUE"].forEach((n) => {
            try {
                const f = block.getField(n);
                if (f) snap[n] = f.getValue();
            } catch (e) { /* ignore */ }
        });

        blockyRemoveInput(block, "COMPARE");

        // Motion sensors only wake on detect — no ON/OFF/transitioned picker.
        if (blockyIsMotionEntity(eid)) {
            block.appendDummyInput("COMPARE").appendField("motion");
            return;
        }

        if (profile.kind === "sensor") {
            // Numeric sensor: show crossing direction label that updates with the op dropdown.
            let op = opts.forceOp != null ? opts.forceOp : snap.OP;
            if (!BLOCKY_COMPARE_OPS.some((o) => o[1] === op)) op = "==";
            const input = block.appendDummyInput("COMPARE")
                .appendField(blockyOpCrossesLabel(op), "CROSSES_LABEL");
            let attr = null;
            if (profile.attrs) {
                const labels = profile.attrLabels || profile.attrs.map((a) => [a, a]);
                attr = opts.forceAttr != null ? opts.forceAttr : snap.ATTR;
                if (!profile.attrs.some((a) => a === attr)) attr = profile.attrs[0];
                input.appendField(new Blockly.FieldDropdown(labels), "ATTR");
                blockySafeSetField(block, "ATTR", attr);
            }
            input.appendField(new Blockly.FieldDropdown(BLOCKY_COMPARE_OPS), "OP");
            const rawVal = opts.forceValue != null ? opts.forceValue : snap.VALUE;
            const numVal = Number(rawVal);
            input.appendField(new Blockly.FieldNumber(Number.isFinite(numVal) ? numVal : 0), "VALUE");
            const unitAttr = profile.attrs
                ? (block.getFieldValue("ATTR") || attr || opts.forceAttr || snap.ATTR)
                : null;
            const unit = blockySensorUnitLabel(eid, unitAttr);
            if (unit) input.appendField(unit);
            blockySafeSetField(block, "OP", op);
            return;
        }

        if (profile.kind === "level") {
            // level: MODE labels are turns/opens alone, or is ON / is open when event gate.
            // PCT mode: op dropdown (crosses via separate OP field).
            const input = block.appendDummyInput("COMPARE");
            let mode = opts.forceMode != null ? opts.forceMode : snap.MODE;
            if (!profile.modes.some((m) => m[1] === mode)) {
                mode = profile.modes[0][1];
            }
            input.appendField(
                new Blockly.FieldDropdown(() => blockyConditionLevelModeOptions(block, profile)),
                "MODE"
            );
            blockySafeSetField(block, "MODE", mode);
            if (mode === "PCT") {
                let op = opts.forceOp != null ? opts.forceOp : snap.OP;
                if (!BLOCKY_COMPARE_OPS.some((o) => o[1] === op)) op = ">";
                input.appendField(new Blockly.FieldDropdown(BLOCKY_COMPARE_OPS), "OP");
                const maxV = blockyLevelValueMax(eid, profile);
                const rawVal = opts.forceValue != null ? opts.forceValue : snap.VALUE;
                const numVal = Number(rawVal);
                const clamped = Number.isFinite(numVal)
                    ? Math.min(maxV, Math.max(profile.min || 0, numVal))
                    : 0;
                input.appendField(new Blockly.FieldNumber(clamped, profile.min || 0, maxV, 1), "VALUE");
                if (profile.unit) input.appendField(profile.unit);
                blockySafeSetField(block, "OP", op);
            }
            return;
        }

        // Discrete: turns ON / is ON (context) — see blockyConditionStateOptions.
        block.appendDummyInput("COMPARE")
            .appendField(new Blockly.FieldDropdown(() => blockyConditionStateOptions(block)), "STATE");
        const st = opts.forceState != null ? opts.forceState : snap.STATE;
        if (st) blockySafeSetField(block, "STATE", st);
    } finally {
        Events.enable();
        block._condUpdating = false;
        try {
            if (block.rendered && typeof block.render === "function") block.render();
        } catch (e) { /* ignore */ }
    }
}

/** Apply a loaded condition's op/attribute/is onto a freshly-shaped b_condition_device. */
function blockyApplyConditionRich(block, cond) {
    if (!block || !cond) return;
    const eid = cond.entity_id || block.getFieldValue("ENTITY");
    blockyAttachOpaque(
        block,
        blockyOpaqueFromSource(cond, BLOCKY_CONDITION_LEGAL_KEYS, BLOCKY_CONDITION_UI_KEYS)
    );
    const profile = blockyConditionCompareProfile(eid);

    // Motion: fixed chrome only (ignore stored is; always ON on emit).
    if (blockyIsMotionEntity(eid)) {
        blockyConditionUpdateShape(block);
        return;
    }

    if (profile.kind === "sensor") {
        blockyConditionUpdateShape(block, {
            forceOp: cond.op || "==",
            forceAttr: cond.attribute || (profile.attrs ? profile.attrs[0] : null),
            forceValue: cond.is != null ? cond.is : 0
        });
        return;
    }

    if (profile.kind === "level") {
        // Any edge (ON↔OFF / OPEN↔CLOSED) — same YAML is: ANY as discrete wake.
        if (String(cond.is || "").toUpperCase() === "ANY") {
            blockyConditionUpdateShape(block, { forceMode: "ANY" });
            return;
        }
        const attr = String(cond.attribute || "").toLowerCase();
        const n = Number(cond.is);
        const wantPct = attr === profile.attribute
            || (cond.op && cond.op !== "==")
            || (profile.valueUi === "open_pct" && Number.isFinite(n) && n !== 0 && n !== 100
                && String(cond.is).toUpperCase() !== "OPEN"
                && String(cond.is).toUpperCase() !== "CLOSED");
        if (wantPct) {
            let uiVal = cond.is != null ? cond.is : 0;
            let uiOp = cond.op || "==";
            if (profile.valueUi === "open_pct") {
                uiVal = blockyOpenPctFromStored(cond.is);
                uiOp = blockyInvertCompareOp(uiOp);
            }
            blockyConditionUpdateShape(block, {
                forceMode: "PCT",
                forceOp: uiOp,
                forceValue: uiVal
            });
            return;
        }
        let mode;
        if (profile.valueUi === "open_pct") {
            mode = blockyBlindsUiStateFromStored(cond.is) === "CLOSED" ? "CLOSED" : "OPEN";
        } else {
            mode = String(cond.is || "ON").toUpperCase() === "OFF" ? "OFF" : "ON";
        }
        blockyConditionUpdateShape(block, { forceMode: mode });
        return;
    }

    const type = blockyEntityTypeOf(eid);
    let forceSt = cond.is || "ON";
    if (String(forceSt).toUpperCase() === "ANY") {
        forceSt = "ANY";
    } else if (type === "blinds" || type === "shutter") {
        forceSt = blockyBlindsUiStateFromStored(cond.is) === "CLOSED" ? "100" : "0";
    }
    blockyConditionUpdateShape(block, { forceState: forceSt });
}

/**
 * B9A/B9C: When device chrome — sensors (ATTR/OP/VALUE); level (MODE + optional PCT);
 * discrete actuators keep the case-MATCH note.
 */
function blockyTriggerUpdateShape(block, opts) {
    if (!block || !window.Blockly || block._trigUpdating) return;
    opts = opts || {};
    block._trigUpdating = true;
    const Events = Blockly.Events;
    Events.disable();
    try {
        const eid = block.getFieldValue("ENTITY");
        const profile = blockyConditionCompareProfile(eid);

        const snap = {};
        ["MODE", "OP", "ATTR", "VALUE"].forEach((n) => {
            try {
                const f = block.getField(n);
                if (f) snap[n] = f.getValue();
            } catch (e) { /* ignore */ }
        });

        blockyRemoveInput(block, "COMPARE");

        if (profile.kind === "sensor") {
            const input = block.appendDummyInput("COMPARE");
            let attr = null;
            if (profile.attrs) {
                const labels = profile.attrLabels || profile.attrs.map((a) => [a, a]);
                attr = opts.forceAttr != null ? opts.forceAttr : snap.ATTR;
                if (!profile.attrs.some((a) => a === attr)) attr = profile.attrs[0];
                input.appendField(new Blockly.FieldDropdown(labels), "ATTR");
                blockySafeSetField(block, "ATTR", attr);
            }
            let op = opts.forceOp != null ? opts.forceOp : snap.OP;
            if (!BLOCKY_COMPARE_OPS.some((o) => o[1] === op)) op = ">=";
            input.appendField(new Blockly.FieldDropdown(BLOCKY_COMPARE_OPS), "OP");
            const rawVal = opts.forceValue != null ? opts.forceValue : snap.VALUE;
            const numVal = Number(rawVal);
            input.appendField(new Blockly.FieldNumber(Number.isFinite(numVal) ? numVal : 0), "VALUE");
            const unitAttr = profile.attrs
                ? (block.getFieldValue("ATTR") || attr || opts.forceAttr || snap.ATTR)
                : null;
            const unit = blockySensorUnitLabel(eid, unitAttr);
            if (unit) input.appendField(unit);
            blockySafeSetField(block, "OP", op);
        } else if (profile.kind === "level") {
            const input = block.appendDummyInput("COMPARE");
            let mode = opts.forceMode != null ? opts.forceMode : snap.MODE;
            if (!profile.modes.some((m) => m[1] === mode)) {
                mode = profile.modes[0][1];
            }
            input.appendField(new Blockly.FieldDropdown(profile.modes), "MODE");
            blockySafeSetField(block, "MODE", mode);
            if (mode === "PCT") {
                let op = opts.forceOp != null ? opts.forceOp : snap.OP;
                if (!BLOCKY_COMPARE_OPS.some((o) => o[1] === op)) op = ">";
                input.appendField(new Blockly.FieldDropdown(BLOCKY_COMPARE_OPS), "OP");
                const maxV = blockyLevelValueMax(eid, profile);
                const rawVal = opts.forceValue != null ? opts.forceValue : snap.VALUE;
                const numVal = Number(rawVal);
                const clamped = Number.isFinite(numVal)
                    ? Math.min(maxV, Math.max(profile.min || 0, numVal))
                    : 0;
                input.appendField(new Blockly.FieldNumber(clamped, profile.min || 0, maxV, 1), "VALUE");
                if (profile.unit) input.appendField(profile.unit);
                blockySafeSetField(block, "OP", op);
            }
        } else {
            block.appendDummyInput("COMPARE").appendField("(pick case: ON / OFF / transitioned)");
        }
    } finally {
        Events.enable();
        block._trigUpdating = false;
        try {
            if (block.rendered && typeof block.render === "function") block.render();
        } catch (e) { /* ignore */ }
        // Level / sensor When owns MATCH — refresh case chrome after MODE rebuild.
        try {
            blockyRefreshCaseMatchLabels(block.getNextBlock && block.getNextBlock());
        } catch (e) { /* ignore */ }
    }
}

/** Stored blinds state = closed % (0 open … 100 closed). UI = open %. */
function blockyOpenPctFromStored(stored) {
    const n = Number(stored);
    if (!Number.isFinite(n)) return 100;
    return Math.max(0, Math.min(100, 100 - n));
}

function blockyStoredFromOpenPct(openPct) {
    const n = Number(openPct);
    if (!Number.isFinite(n)) return "0";
    return String(Math.max(0, Math.min(100, Math.round(100 - n))));
}

/**
 * B9C: open % and closed % move in opposite directions — flip inequality ops
 * when converting UI open-% ↔ YAML closed-% (`==` / `!=` unchanged).
 * @param {string|null|undefined} op
 * @returns {string}
 */
function blockyInvertCompareOp(op) {
    const o = String(op || "==").trim();
    if (o === ">") return "<";
    if (o === "<") return ">";
    if (o === ">=") return "<=";
    if (o === "<=") return ">=";
    return o;
}

/** Map stored shutter closed-% / OPEN/CLOSED / ON/OFF leftovers → Blockly Set STATE.
 * Mid-% → OPEN (open % field holds the intermediate). */
function blockyBlindsUiStateFromStored(stored) {
    const su = String(stored == null ? "" : stored).trim().toUpperCase();
    if (su === "CLOSED" || su === "OFF") return "CLOSED";
    if (su === "OPEN" || su === "ON") return "OPEN";
    const n = Number(stored);
    if (n === 100) return "CLOSED";
    return "OPEN";
}

function blockyHuePresetsMap() {
    const app = BlockyRT.app;
    if (app && app.huePresets && typeof app.huePresets === "object") return app.huePresets;
    if (app && app.state && app.state.system && app.state.system.hue_presets) {
        return app.state.system.hue_presets;
    }
    return {};
}

function blockySonosStationsMap() {
    const app = BlockyRT.app;
    if (app && app.sonosStations && typeof app.sonosStations === "object") return app.sonosStations;
    if (app && app.state && app.state.system && app.state.system.sonos_stations) {
        return app.state.system.sonos_stations;
    }
    return {};
}

function blockyHuePresetOptions(stickyKey) {
    const presets = blockyHuePresetsMap();
    const keys = Object.keys(presets);
    const opts = [];
    const seen = new Set();
    keys.forEach((k) => {
        const p = presets[k];
        const label = (p && p.name) ? String(p.name) : k;
        opts.push([label, k]);
        seen.add(k);
    });
    blockyStickyRichKeys("preset", stickyKey).forEach((k) => {
        if (!seen.has(k)) {
            const label = keys.length ? `${k} · (missing)` : k;
            opts.push([label, k]);
            seen.add(k);
        }
    });
    // Never offer empty "(none)" — preset mode always needs a real key.
    return opts.length ? opts : [["(no presets in config)", ""]];
}

/** Station keys from config + sticky (open rule / pending load) so setValue cannot be rejected. */
function blockySonosStationOptions(stickyKey) {
    const stations = blockySonosStationsMap();
    const known = Object.keys(stations);
    const opts = [["(none)", ""]];
    const seen = new Set([""]);
    known.forEach((k) => {
        opts.push([k, k]);
        seen.add(k);
    });
    blockyStickyRichKeys("station", stickyKey).forEach((k) => {
        if (!seen.has(k)) {
            const label = known.length ? `${k} · (missing from config)` : k;
            opts.push([label, k]);
            seen.add(k);
        }
    });
    return opts;
}

/** Collect preset/station keys from open ruleJson, pending apply, and workspace fields. */
function blockyStickyRichKeys(kind, stickyKey) {
    const out = new Set();
    if (stickyKey) out.add(String(stickyKey));
    const app = BlockyRT.app;
    if (app && app._pendingRichSticky && app._pendingRichSticky[kind]) {
        app._pendingRichSticky[kind].forEach((k) => out.add(String(k)));
    }
    try {
        const rule = JSON.parse((app && app.editor && app.editor.ruleJson) || "{}");
        (rule.cases || []).forEach((c) => {
            (c.actions || []).forEach((a) => {
                if (kind === "station" && a.station) out.add(String(a.station));
                if (kind === "preset" && a.preset) out.add(String(a.preset));
            });
        });
    } catch (e) { /* ignore */ }
    try {
        const ws = blockyWs();
        const field = kind === "station" ? "STATION" : "PRESET";
        if (ws) {
            ws.getAllBlocks(false).forEach((b) => {
                if (b.type !== "b_action_device" || !b.getField(field)) return;
                const v = b.getFieldValue(field);
                if (v) out.add(String(v));
            });
        }
    } catch (e) { /* ignore */ }
    return [...out].filter(Boolean);
}

function blockyEntityMaxVolume(eid) {
    const opt = blockyEntityMeta(eid);
    if (opt && opt.max_volume != null) {
        const n = Number(opt.max_volume);
        if (Number.isFinite(n) && n > 0) return n;
    }
    const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
    if (origin === "onkyo") return 60;
    if (origin === "sonos") return 70;
    return 100;
}

function blockySafeSetField(block, name, value) {
    if (!block || value == null) return;
    try {
        const f = block.getField(name);
        if (!f) return;
        f.setValue(value);
    } catch (e) { /* ignore */ }
}

/** CIE xy + bri → hex (same math as Device Explorer). */
function blockyXyToHex(x, y, bri) {
    if (x === undefined || y === undefined || x == null || y == null) return "#FFD180";
    let z = 1.0 - x - y;
    const Y = (bri !== undefined && bri != null ? bri : 100) / 100.0;
    if (!y) return "#FFD180";
    const X = (Y / y) * x;
    const Z = (Y / y) * z;
    let r = X * 1.656492 - Y * 0.354851 - Z * 0.255038;
    let g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152;
    let b = X * 0.051713 - Y * 0.121364 + Z * 1.011530;
    r = r <= 0.0031308 ? 12.92 * r : (1.0 + 0.055) * Math.pow(r, (1.0 / 2.4)) - 0.055;
    g = g <= 0.0031308 ? 12.92 * g : (1.0 + 0.055) * Math.pow(g, (1.0 / 2.4)) - 0.055;
    b = b <= 0.0031308 ? 12.92 * b : (1.0 + 0.055) * Math.pow(b, (1.0 / 2.4)) - 0.055;
    r = Math.max(0, Math.min(1, r));
    g = Math.max(0, Math.min(1, g));
    b = Math.max(0, Math.min(1, b));
    const toHex = (c) => Math.round(c * 255).toString(16).padStart(2, "0");
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase();
}

/** Hex → CIE xy (same math as Device Explorer). */
function blockyHexToXy(hex) {
    let h = String(hex || "").replace("#", "");
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    if (h.length !== 6) return [0.4575, 0.4099];
    let r = parseInt(h.slice(0, 2), 16) / 255;
    let g = parseInt(h.slice(2, 4), 16) / 255;
    let b = parseInt(h.slice(4, 6), 16) / 255;
    r = r > 0.04045 ? Math.pow((r + 0.055) / 1.055, 2.4) : r / 12.92;
    g = g > 0.04045 ? Math.pow((g + 0.055) / 1.055, 2.4) : g / 12.92;
    b = b > 0.04045 ? Math.pow((b + 0.055) / 1.055, 2.4) : b / 12.92;
    const X = r * 0.664511 + g * 0.154324 + b * 0.162028;
    const Y = r * 0.283881 + g * 0.668433 + b * 0.047685;
    const Z = r * 0.000088 + g * 0.072310 + b * 0.986039;
    const sum = X + Y + Z;
    if (sum <= 0) return [0.4575, 0.4099];
    return [X / sum, Y / sum];
}

function blockyCloseHueColorModal() {
    // Drop any queued reopen from HUE_MODE validators.
    if (BlockyRT.pendingRichOpts) BlockyRT.pendingRichOpts.openWheel = false;
    const app = BlockyRT.app;
    if (app) app.blockyColorTargetId = null;
    const dlg = document.getElementById("blocky_hue_color_modal");
    if (dlg && typeof dlg.close === "function") {
        try { dlg.close(); } catch (e) { /* ignore */ }
    }
}

function blockyOpenHueColorModal(block) {
    const app = BlockyRT.app;
    if (!app || !block || block._hueSuppressWheel || block._richUpdating) return;
    if (BlockyRT.loading || BlockyRT.suppressHueWheel) return;
    app.blockyColorTargetId = block.id;
    app.blockyColorBri = block._hueBri != null ? Number(block._hueBri) : 100;
    app.blockyColorHex = block._hueHex || "#FFD180";
    const dlg = document.getElementById("blocky_hue_color_modal");
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    queueMicrotask(() => {
        if (!window.iro || !dlg.open) return;
        const host = document.getElementById("blocky-color-picker-container");
        if (!host) return;
        if (!BlockyRT.colorPicker) {
            host.innerHTML = "";
            BlockyRT.colorPicker = new iro.ColorPicker(host, {
                width: 220,
                color: app.blockyColorHex,
                layout: [{ component: iro.ui.Wheel, options: {} }]
            });
            BlockyRT.colorPicker.on("color:change", (color) => {
                if (BlockyRT.app) BlockyRT.app.blockyColorHex = color.hexString;
            });
        } else {
            try { BlockyRT.colorPicker.color.hexString = app.blockyColorHex; } catch (e) { /* ignore */ }
        }
    });
}

function blockyApplyHueColorModal() {
    const app = BlockyRT.app;
    const ws = blockyWs();
    if (!app || !ws || !app.blockyColorTargetId) {
        blockyCloseHueColorModal();
        return;
    }
    const block = ws.getBlockById(app.blockyColorTargetId);
    if (!block) {
        blockyCloseHueColorModal();
        return;
    }
    const bri = Math.max(1, Math.min(100, Number(app.blockyColorBri) || 100));
    const hex = String(app.blockyColorHex || "#FFD180");
    const xy = blockyHexToXy(hex);
    block._hueBri = bri;
    block._hueXy = xy;
    block._hueHex = hex.toUpperCase();
    // Prevent HUE_MODE validators from reopening the wheel while we sync shape.
    block._hueSuppressWheel = true;
    try {
        blockyActionUpdateRichShape(block, { forceState: "ON", forceHueMode: "CUSTOM" });
        blockyPaintHueSwatch(block);
    } finally {
        block._hueSuppressWheel = false;
    }
    if (typeof app.markEditorDirty === "function") app.markEditorDirty();
    blockyCloseHueColorModal();
}

function blockyPaintHueSwatch(block) {
    const f = block && block.getField("COLOR_SWATCH");
    if (!f) return;
    const hex = block._hueHex || "#FFD180";
    try {
        const el = (typeof f.getTextElement === "function" ? f.getTextElement() : null)
            || f.textElement_;
        if (el) el.style.fill = hex;
    } catch (e) { /* ignore */ }
}

function blockyClearActionRichSticky(block) {
    if (!block) return;
    delete block._hueBri;
    delete block._hueXy;
    delete block._hueHex;
    delete block._pendingPreset;
    delete block._pendingStation;
    blockyRemoveInput(block, "RICH_BLINDS");
    blockyRemoveInput(block, "RICH_HUE_MODE");
    blockyRemoveInput(block, "RICH_HUE_PRESET");
    blockyRemoveInput(block, "RICH_HUE_CUSTOM");
    blockyRemoveInput(block, "RICH_AUDIO");
}

/** Remove a named dummy input if present (never throws). */
function blockyRemoveInput(block, name) {
    if (!block || !block.getInput(name)) return;
    try { block.removeInput(name); } catch (e) { /* ignore */ }
}

/**
 * Queue rich-shape sync after the current field commit finishes.
 * Independent of uniqueness timer so load/cancel cannot drop UI updates.
 */
function blockyQueueRichShape(block, opts) {
    if (!block || block.isInFlyout) return;
    opts = opts || {};
    BlockyRT.pendingRichOpts = Object.assign({}, BlockyRT.pendingRichOpts || {}, opts, {
        blockId: block.id
    });
    if (BlockyRT.richTimer) clearTimeout(BlockyRT.richTimer);
    BlockyRT.richTimer = setTimeout(() => {
        BlockyRT.richTimer = null;
        const pending = BlockyRT.pendingRichOpts;
        BlockyRT.pendingRichOpts = null;
        if (!pending || !pending.blockId) return;
        const ws = blockyWs();
        const blk = ws && ws.getBlockById(pending.blockId);
        if (!blk || blk.type !== "b_action_device") return;
        const openWheel = !!pending.openWheel;
        delete pending.openWheel;
        delete pending.blockId;
        blockyActionUpdateRichShape(blk, pending);
        if (openWheel && !BlockyRT.loading && !BlockyRT.suppressHueWheel) {
            blockyOpenHueColorModal(blk);
        }
    }, 0);
}

function blockyRemoveHueSwatchField(block) {
    if (!block || !block.getField("COLOR_SWATCH")) return;
    const input = block.getInput("RICH_HUE_MODE");
    if (!input) return;
    try { input.removeField("COLOR_SWATCH"); } catch (e) { /* ignore */ }
}

function blockyEnsureHueSwatchField(block) {
    if (!block || block.getField("COLOR_SWATCH")) return;
    const input = block.getInput("RICH_HUE_MODE");
    if (!input) return;
    try {
        input.appendField(new Blockly.FieldLabel("⬤"), "COLOR_SWATCH");
    } catch (e) { /* ignore */ }
}

/** Ensure Hue mode dropdown exists once — never dispose it while light is ON. */
function blockyEnsureHueModeInput(block) {
    if (block.getInput("RICH_HUE_MODE")) return;
    const modeOpts = [
        ["named preset", "PRESET"],
        ["custom color", "CUSTOM"],
        ["(no color)", "NONE"]
    ];
    block.appendDummyInput("RICH_HUE_MODE")
        .appendField("color")
        .appendField(new Blockly.FieldDropdown(modeOpts, (newMode) => {
            if (block._richUpdating || block._hueSuppressWheel || BlockyRT.loading || BlockyRT.suppressHueWheel) {
                return newMode;
            }
            // Validator runs before value commits — schedule shape after.
            if (newMode === "CUSTOM") {
                blockyQueueRichShape(block, {
                    forceState: "ON",
                    forceHueMode: "CUSTOM",
                    openWheel: true
                });
            } else {
                if (newMode !== "PRESET") block._pendingPreset = null;
                blockyQueueRichShape(block, {
                    forceState: "ON",
                    forceHueMode: newMode
                });
            }
            return newMode;
        }), "HUE_MODE");
}

/**
 * Sync optional rich inputs on b_action_device from entity type + STATE.
 * Critical: never dispose HUE_MODE / STATE while that field is being edited —
 * only add/remove sibling rows (preset / custom / audio / blinds).
 * opts.forceState / opts.forceHueMode: caller-supplied values (validators / events).
 */
function blockyActionUpdateRichShape(block, opts) {
    if (!block || !window.Blockly || block._richUpdating) return;
    opts = opts || {};
    block._richUpdating = true;
    const Events = Blockly.Events;
    // Blockly 13 refcounts disable/enable — always pair 1:1 (never gate enable on wasEnabled).
    Events.disable();
    try {
        const eid = block.getFieldValue("ENTITY");
        const type = blockyEntityTypeOf(eid);
        const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
        const state = String(
            opts.forceState != null ? opts.forceState : (block.getFieldValue("STATE") || "")
        );

        const snap = {};
        ["OPEN_PCT", "HUE_MODE", "PRESET", "VOLUME", "STATION"].forEach((n) => {
            try {
                const f = block.getField(n);
                if (f) snap[n] = f.getValue();
            } catch (e) { /* ignore */ }
        });

        const wantBlinds = type === "blinds" || type === "shutter";
        const wantHue = (type === "light" || type === "hue") && origin !== "rfxcom" && state === "ON";
        const wantAudio = (type === "speaker" || type === "media_player") && state === "ON";

        if (!wantBlinds) blockyRemoveInput(block, "RICH_BLINDS");
        if (!wantHue) {
            blockyRemoveInput(block, "RICH_HUE_MODE");
            blockyRemoveInput(block, "RICH_HUE_PRESET");
            blockyRemoveInput(block, "RICH_HUE_CUSTOM");
        }
        if (!wantAudio) blockyRemoveInput(block, "RICH_AUDIO");

        if (wantBlinds) {
            let st = state;
            if (st !== "OPEN" && st !== "CLOSED") {
                st = blockyBlindsUiStateFromStored(st);
                if (st !== "OPEN" && st !== "CLOSED") st = "OPEN";
                blockyForceDropdownValue(block, "STATE", st);
            }
            // B9C: restore B6C open-% row when OPEN (CLOSED = fully closed, no field).
            if (st === "OPEN") {
                const rawPct = opts.forceOpenPct != null ? opts.forceOpenPct : snap.OPEN_PCT;
                const n = Number(rawPct);
                const openPct = Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : 100;
                if (!block.getInput("RICH_BLINDS")) {
                    block.appendDummyInput("RICH_BLINDS")
                        .appendField("open %")
                        .appendField(new Blockly.FieldNumber(openPct, 0, 100, 1), "OPEN_PCT");
                }
                blockySafeSetField(block, "OPEN_PCT", openPct);
            } else {
                blockyRemoveInput(block, "RICH_BLINDS");
            }
            return;
        }

        if (wantHue) {
            blockyEnsureHueModeInput(block);

            let mode = opts.forceHueMode != null ? opts.forceHueMode : snap.HUE_MODE;
            // Prefer sticky/pending rich over a bare NONE left by an earlier shape rebuild
            // (e.g. coerce before apply, or ENTITY microtask). Do not override an
            // already-committed PRESET/CUSTOM — only upgrade from NONE/invalid.
            if (opts.forceHueMode == null) {
                if (mode !== "PRESET" && mode !== "CUSTOM") {
                    if (block._pendingPreset || snap.PRESET) mode = "PRESET";
                    else if (block._hueBri != null || block._hueXy) mode = "CUSTOM";
                    else mode = "NONE";
                }
            }
            if (mode === "CUSTOM" || mode === "NONE") block._pendingPreset = null;

            // Keep HUE_MODE field — only set its value (do not recreate).
            blockySafeSetField(block, "HUE_MODE", mode);

            if (mode === "PRESET") {
                blockyRemoveInput(block, "RICH_HUE_CUSTOM");
                blockyRemoveHueSwatchField(block);
                const presetOpts = blockyHuePresetOptions(
                    snap.PRESET || block._pendingPreset || ""
                );
                let stickyPreset = snap.PRESET || block._pendingPreset || "";
                if (!stickyPreset || !presetOpts.some((o) => o[1] === stickyPreset)) {
                    stickyPreset = presetOpts[0] ? presetOpts[0][1] : "";
                }
                if (!block.getInput("RICH_HUE_PRESET")) {
                    block.appendDummyInput("RICH_HUE_PRESET")
                        .appendField("preset")
                        .appendField(new Blockly.FieldDropdown(
                            () => blockyHuePresetOptions(
                                block.getFieldValue("PRESET") || block._pendingPreset || stickyPreset
                            )
                        ), "PRESET");
                }
                if (stickyPreset) blockySafeSetField(block, "PRESET", stickyPreset);
            } else if (mode === "CUSTOM") {
                blockyRemoveInput(block, "RICH_HUE_PRESET");
                // Drop legacy third-row "edit color…" chrome (re-select custom opens wheel).
                blockyRemoveInput(block, "RICH_HUE_CUSTOM");
                if (block._hueBri == null) block._hueBri = 100;
                if (!block._hueXy) block._hueXy = [0.4575, 0.4099];
                if (!block._hueHex) {
                    block._hueHex = blockyXyToHex(block._hueXy[0], block._hueXy[1], block._hueBri);
                }
                // Swatch on the same row as color / custom color.
                blockyEnsureHueSwatchField(block);
                blockyPaintHueSwatch(block);
            } else {
                blockyRemoveInput(block, "RICH_HUE_PRESET");
                blockyRemoveInput(block, "RICH_HUE_CUSTOM");
                blockyRemoveHueSwatchField(block);
                // Drop sticky custom so a later bare rebuild does not bounce back to CUSTOM.
                delete block._hueBri;
                delete block._hueXy;
                delete block._hueHex;
            }
            return;
        }

        if (wantAudio) {
            const maxVol = blockyEntityMaxVolume(eid);
            const vol = snap.VOLUME != null && snap.VOLUME !== "" ? Number(snap.VOLUME) : 0;
            const needStation = origin === "sonos";
            const hasAudio = !!block.getInput("RICH_AUDIO");
            const hasStation = !!block.getField("STATION");
            if (!hasAudio || (!!hasStation) !== needStation) {
                blockyRemoveInput(block, "RICH_AUDIO");
                const input = block.appendDummyInput("RICH_AUDIO")
                    .appendField("volume")
                    .appendField(new Blockly.FieldNumber(
                        Number.isFinite(vol) ? Math.min(maxVol, Math.max(0, vol)) : 0,
                        0, maxVol, 1
                    ), "VOLUME");
                if (needStation) {
                    const stickyStation = snap.STATION || block._pendingStation || "";
                    input.appendField("station")
                        .appendField(new Blockly.FieldDropdown(
                            () => blockySonosStationOptions(
                                block.getFieldValue("STATION") || block._pendingStation || stickyStation
                            )
                        ), "STATION");
                    if (stickyStation) blockySafeSetField(block, "STATION", stickyStation);
                    else if (snap.STATION) blockySafeSetField(block, "STATION", snap.STATION);
                }
            } else if (snap.VOLUME != null) {
                blockySafeSetField(block, "VOLUME", snap.VOLUME);
            }
        }
    } finally {
        Events.enable();
        block._richUpdating = false;
        try {
            if (block.rendered && typeof block.render === "function") block.render();
        } catch (e) { /* ignore */ }
        blockyPaintHueSwatch(block);
    }
}

/** Apply YAML/JSON action rich keys onto a block after shape is built (per-action, not by entity). */
function blockyApplyActionRich(block, action) {
    if (!block || !action) return;
    const eid = action.entity_id || block.getFieldValue("ENTITY");
    const type = blockyEntityTypeOf(eid);
    const origin = String(blockyEntityOriginOf(eid) || "").toLowerCase();
    // B9A B+C: stash legal keys Blockly does not author (e.g. target/scene).
    blockyAttachOpaque(
        block,
        blockyOpaqueFromSource(action, BLOCKY_ACTION_LEGAL_KEYS, BLOCKY_ACTION_UI_KEYS)
    );

    // Seed sticky keys before shape build so FieldDropdown accepts setValue.
    if (action.station) block._pendingStation = String(action.station);
    if (action.preset) block._pendingPreset = String(action.preset);

    if (type === "blinds" || type === "shutter") {
        const stored = action.state;
        const n = Number(stored);
        const ui = blockyBlindsUiStateFromStored(stored);
        blockyForceDropdownValue(block, "STATE", ui);
        const forceOpenPct = (ui === "OPEN")
            ? (Number.isFinite(n) ? blockyOpenPctFromStored(n) : 100)
            : undefined;
        blockyActionUpdateRichShape(block, { forceState: ui, forceOpenPct });
        return;
    }

    if ((type === "light" || type === "hue") && origin !== "rfxcom"
        && String(action.state || "").toUpperCase() === "ON") {
        if (action.preset) {
            // forceHueMode — do not let a prior NONE snap wipe _pendingPreset.
            blockyActionUpdateRichShape(block, { forceHueMode: "PRESET" });
            blockySafeSetField(block, "PRESET", action.preset);
        } else if (action.bri != null || action.xy != null) {
            if (action.bri != null) block._hueBri = Number(action.bri);
            if (Array.isArray(action.xy) && action.xy.length >= 2) {
                block._hueXy = [Number(action.xy[0]), Number(action.xy[1])];
            }
            block._hueHex = blockyXyToHex(
                (block._hueXy && block._hueXy[0]) || 0.4575,
                (block._hueXy && block._hueXy[1]) || 0.4099,
                block._hueBri != null ? block._hueBri : 100
            );
            blockyActionUpdateRichShape(block, { forceHueMode: "CUSTOM" });
        } else {
            blockyActionUpdateRichShape(block, { forceHueMode: "NONE" });
        }
        delete block._pendingPreset;
        return;
    }

    if ((type === "speaker" || type === "media_player") && String(action.state || "").toUpperCase() === "ON") {
        blockyActionUpdateRichShape(block);
        if (action.volume != null) blockySafeSetField(block, "VOLUME", Number(action.volume));
        if (action.station) blockySafeSetField(block, "STATION", action.station);
        delete block._pendingStation;
        return;
    }

    blockyActionUpdateRichShape(block);
    delete block._pendingStation;
    delete block._pendingPreset;
}

function blockyReadActionRich(block) {
    const entity = block.getFieldValue("ENTITY");
    const type = blockyEntityTypeOf(entity);
    const origin = String(blockyEntityOriginOf(entity) || "").toLowerCase();
    const out = { entity_id: entity, state: block.getFieldValue("STATE") };

    if (type === "blinds" || type === "shutter") {
        const ui = block.getFieldValue("STATE");
        if (ui === "CLOSED") {
            out.state = "100";
        } else {
            const pct = block.getFieldValue("OPEN_PCT");
            out.state = blockyStoredFromOpenPct(pct != null && pct !== "" ? pct : 100);
        }
        return blockyMergeOpaque(out, block);
    }

    if ((type === "light" || type === "hue") && origin !== "rfxcom" && out.state === "ON") {
        const mode = block.getFieldValue("HUE_MODE") || "NONE";
        if (mode === "PRESET") {
            const preset = block.getFieldValue("PRESET");
            if (preset) out.preset = preset;
        } else if (mode === "CUSTOM") {
            const bri = block._hueBri;
            const xy = block._hueXy;
            if (bri != null && !Number.isNaN(Number(bri))) out.bri = Number(bri);
            if (Array.isArray(xy) && xy.length >= 2) {
                const x = Number(xy[0]);
                const y = Number(xy[1]);
                if (!Number.isNaN(x) && !Number.isNaN(y)) out.xy = [x, y];
            }
        }
        return blockyMergeOpaque(out, block);
    }

    if ((type === "speaker" || type === "media_player") && out.state === "ON") {
        const vol = block.getFieldValue("VOLUME");
        if (vol !== "" && vol != null) {
            const n = Number(vol);
            if (!Number.isNaN(n)) out.volume = n;
        }
        if (origin === "sonos") {
            const station = block.getFieldValue("STATION");
            if (station) out.station = station;
        }
        return blockyMergeOpaque(out, block);
    }

    return blockyMergeOpaque(out, block);
}

function blockyCoerceFieldToOptions(block, fieldName, optionsFn) {
    try {
        const f = block.getField(fieldName);
        if (!f) return;
        // Refresh dynamic menu before setValue — stale cache rejects valid new values
        // (e.g. light ON/OFF cache rejecting blinds OPEN).
        try { f.getOptions(false); } catch (e) { /* ignore */ }
        const opts = optionsFn(block);
        if (!opts || !opts.length) return;
        let v = f.getValue();
        // Legacy FORCE_* on always-forced origins → plain ON/OFF before menu coerce.
        if (fieldName === "STATE" && typeof v === "string" && v.startsWith("FORCE_")) {
            const stripped = v.slice("FORCE_".length);
            if (opts.some((o) => o[1] === stripped)) {
                f.setValue(stripped);
                if (typeof f.forceRerender === "function") f.forceRerender();
                return;
            }
        }
        // Shutters may still hold closed-% ("100"), ON/OFF leftovers, or MATCH ON after mkBlock.
        if ((fieldName === "STATE" || fieldName === "MATCH") && !opts.some((o) => o[1] === v)) {
            const et = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
            if (et === "blinds" || et === "shutter" || fieldName === "MATCH") {
                const mapped = blockyBlindsUiStateFromStored(v);
                const candidates = [mapped, mapped === "CLOSED" ? "100" : "0"];
                for (let i = 0; i < candidates.length; i += 1) {
                    if (opts.some((o) => o[1] === candidates[i])) {
                        f.setValue(candidates[i]);
                        if (typeof f.forceRerender === "function") f.forceRerender();
                        return;
                    }
                }
            }
        }
        if (!opts.some((o) => o[1] === v)) {
            f.setValue(opts[0][1]);
        }
        if (typeof f.forceRerender === "function") f.forceRerender();
    } catch (e) { /* ignore */ }
}

/** Set a dynamic dropdown value after refreshing its option list. */
function blockyForceDropdownValue(block, fieldName, value) {
    if (!block || value == null || value === "") return;
    const f = block.getField(fieldName);
    if (!f) return;
    try { f.getOptions(false); } catch (e) { /* ignore */ }
    try { f.setValue(String(value)); } catch (e) { /* ignore */ }
    if (typeof f.forceRerender === "function") f.forceRerender();
}

function blockyRefreshCaseMatchLabels(fromBlock) {
    let cur = fromBlock;
    while (cur) {
        if (cur.type === "b_case") {
            const f = cur.getField("MATCH");
            if (f) {
                try {
                    const opts = blockyCaseMatchOptions(cur);
                    const v = f.getValue();
                    f.getOptions(false);
                    if (!opts.some((o) => o[1] === v)) {
                        f.setValue(opts[0][1]);
                    } else {
                        f.setValue(v);
                    }
                    if (typeof f.forceRerender === "function") f.forceRerender();
                } catch (e) { /* ignore */ }
            }
            blockyCaseUpdateEventChrome(cur);
        }
        cur = cur.getNextBlock ? cur.getNextBlock() : null;
    }
}

function defineBlockyBlocks(Blockly, providers) {
    const entityTriggerDd = providers.entityTrigger || providers.entity;
    const entityConditionDd = providers.entityCondition || providers.entity;
    const entityActionDd = providers.entityAction || providers.entity;
    // B10E: separate dropdown providers for user vs system (trigger vs fire filters).
    const eventUserTrigDd = providers.eventUserTrigger || providers.event;
    const eventSysTrigDd = providers.eventSystemTrigger || providers.event;
    const eventUserFireDd = providers.eventUserFire || providers.event;
    const eventSysFireDd = providers.eventSystemFire || providers.event;

    Object.keys(Blockly.Blocks).forEach((t) => {
        if (t.startsWith("b_")) delete Blockly.Blocks[t];
    });

    // Legacy When/case / OR-list blocks removed (B4/H4). Old block types → silent-loss on Save.

    // --- B19 Domoticz If/Do + Else-if + Else (first-match; gear = next-chain) ---
    Blockly.Blocks.b_if_do = {
        init() {
            // No title row — If / Do statement labels are enough.
            this.appendStatementInput("IF").setCheck("Condition").appendField("If");
            this.appendStatementInput("DO").setCheck("Action").appendField("Do");
            this.setNextStatement(true, "BranchCont");
            this.setColour(120);
            this.setTooltip("If/Do — first branch. Chain Else-if below. First match wins.");
        }
    };
    Blockly.Blocks.b_else_if = {
        init() {
            this.appendDummyInput().appendField("Else-if");
            // No second "If" label — Else-if title already names the branch.
            this.appendStatementInput("IF").setCheck("Condition");
            this.appendStatementInput("DO").setCheck("Action").appendField("Do");
            this.setPreviousStatement(true, "BranchCont");
            this.setNextStatement(true, "BranchCont");
            this.setColour(120);
            this.setTooltip("Else-if branch (first match wins — complementary Compare required).");
        }
    };
    // Bare Else retired (2026-08-21): use Else-if with an explicit complementary Compare.
    // Definition kept so a stale workspace can dispose; not in the toolbox.
    Blockly.Blocks.b_else = {
        init() {
            this.appendDummyInput().appendField("Else (retired)");
            this.appendStatementInput("DO").setCheck("Action").appendField("Do");
            this.setPreviousStatement(true, "BranchCont");
            this.setColour(120);
            this.setTooltip("Retired — replace with Else-if + complementary Compare (no bare Else).");
        }
    };

    // B4/H4 Domoticz Logic — nested AND / OR / NOT inside If Compare sockets.
    Blockly.Blocks.b_logic_and = {
        init() {
            this.appendDummyInput().appendField("and");
            this.appendStatementInput("CHILDREN").setCheck("Condition");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(210);
            this.setTooltip("All nested Compares must be true (Domoticz Logic).");
        }
    };
    Blockly.Blocks.b_logic_or = {
        init() {
            this.appendDummyInput().appendField("or");
            this.appendStatementInput("CHILDREN").setCheck("Condition");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(210);
            this.setTooltip("Any nested Compare may be true (Domoticz Logic).");
        }
    };
    Blockly.Blocks.b_logic_not = {
        init() {
            this.appendDummyInput().appendField("not (retired)");
            this.appendStatementInput("CHILD").setCheck("Condition");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(210);
            this.setTooltip("Retired — not in toolbox; delete if present on an old canvas.");
        }
    };

    Blockly.Blocks.b_condition_device = {
        init() {
            this.appendDummyInput("MAIN")
                .appendField(new Blockly.FieldDropdown(entityConditionDd), "ENTITY");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
            blockyConditionUpdateShape(this);
            blockyApplyPreferredDeviceDefaults(this, "condition");
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && ev.type === "change"
                && (ev.name === "ENTITY" || ev.name === "ATTR" || ev.name === "MODE")
                && !BlockyRT.loading) {
                blockyConditionUpdateShape(this);
            }
        }
    };
    Blockly.Blocks.b_condition_time = {
        init() {
            this.appendDummyInput()
                .appendField("time is")
                .appendField(new Blockly.FieldDropdown([["dark", "dark"], ["light", "light"]]), "TOD");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
        }
    };
    Blockly.Blocks.b_condition_event = {
        init() {
            this.appendDummyInput()
                .appendField("user event")
                .appendField(new Blockly.FieldDropdown(eventUserTrigDd), "EVENT");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
            this.setTooltip("Wake + match when this user catalog event is on the bus.");
        }
    };
    Blockly.Blocks.b_condition_event_sys = {
        init() {
            this.appendDummyInput()
                .appendField("system event")
                .appendField(new Blockly.FieldDropdown(eventSysTrigDd), "EVENT");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
            this.setTooltip("Wake + match when this system catalog event is on the bus.");
        }
    };
    Blockly.Blocks.b_action_device = {
        init() {
            const block = this;
            this.appendDummyInput("MAIN")
                .appendField("Set")
                .appendField(new Blockly.FieldDropdown(entityActionDd, (newEid) => {
                    // Validator runs before commit — ENTITY field still holds previous id.
                    const prevEid = block.getFieldValue("ENTITY");
                    const prevType = blockyEntityTypeOf(prevEid);
                    const nextType = blockyEntityTypeOf(newEid);
                    queueMicrotask(() => {
                        // Load path applies rich itself — do not clear sticky after mkBlock setField.
                        if (BlockyRT.loading) return;
                        let forceSt = null;
                        if (prevEid && prevType !== nextType) {
                            blockyClearActionRichSticky(block);
                            if (nextType === "blinds" || nextType === "shutter") forceSt = "OPEN";
                            else if (nextType === "light" || nextType === "hue") forceSt = "ON";
                        }
                        if (forceSt) {
                            blockyForceDropdownValue(block, "STATE", forceSt);
                        }
                        // Always coerce so invalid leftovers (ON on blinds) snap to OPEN/etc.
                        blockyCoerceFieldToOptions(block, "STATE", blockyActionStateOptions);
                        if (forceSt && block.getFieldValue("STATE") !== forceSt) {
                            blockyForceDropdownValue(block, "STATE", forceSt);
                        }
                        const st = block.getFieldValue("STATE") || forceSt;
                        blockyQueueRichShape(block, { forceState: st });
                        if (BlockyRT.app) BlockyRT.app.markEditorDirty();
                    });
                    return newEid;
                }), "ENTITY")
                .appendField("to")
                .appendField(new Blockly.FieldDropdown(
                    () => blockyActionStateOptions(block),
                    (newState) => {
                        if (!BlockyRT.loading) {
                            blockyQueueRichShape(block, { forceState: newState });
                        }
                        return newState;
                    }
                ), "STATE");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
            blockyActionUpdateRichShape(this);
            blockyApplyPreferredDeviceDefaults(this, "action");
        },
        // Shape updates come from field validators + blockyQueueRichShape (not onchange).
        onchange() { /* intentional no-op */ }
    };
    Blockly.Blocks.b_action_event = {
        init() {
            this.appendDummyInput()
                .appendField("Fire user event")
                .appendField(new Blockly.FieldDropdown(eventUserFireDd), "EVENT");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
            this.setTooltip("Emit user catalog event UUID on the bus (no explorer confirm on fire-action).");
        }
    };
    Blockly.Blocks.b_action_event_sys = {
        init() {
            this.appendDummyInput()
                .appendField("Fire system event")
                .appendField(new Blockly.FieldDropdown(eventSysFireDd), "EVENT");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
            this.setTooltip(
                "Emit system catalog event. Unused system events are excluded except Sauna/IR ON/OFF."
            );
        }
    };
}

function blockyToolboxDefinition(_presentTypes) {
    // Control · Logic · Conditions · Actions (Time drawer folded into Conditions).
    const contents = [
        {
            kind: "category",
            name: "Control",
            colour: "#5CA65C",
            contents: [
                { kind: "block", type: "b_if_do" },
                { kind: "block", type: "b_else_if" }
            ]
        },
        {
            kind: "category",
            name: "Logic",
            colour: "#A6745C",
            contents: [
                { kind: "block", type: "b_logic_and" },
                { kind: "block", type: "b_logic_or" }
            ]
        },
        {
            kind: "category",
            name: "Conditions",
            colour: "#5C81A6",
            contents: [
                { kind: "block", type: "b_condition_device" },
                { kind: "block", type: "b_condition_time" },
                { kind: "block", type: "b_condition_event" },
                { kind: "block", type: "b_condition_event_sys" }
            ]
        },
        {
            kind: "category",
            name: "Actions",
            colour: "#A65C81",
            contents: [
                { kind: "block", type: "b_action_device" },
                { kind: "block", type: "b_action_event" },
                { kind: "block", type: "b_action_event_sys" }
            ]
        }
    ];
    return { kind: "categoryToolbox", contents };
}

const BlockyRT = {
    ws: null,
    ready: false,
    schemaInjected: null,
    loading: false,
    enforcing: false,
    uniquenessScheduled: false,
    uniquenessTimer: null,
    pendingFieldEv: null,
    pendingCreateRootId: null,
    resizeObserver: null,
    windowResize: null,
    /** rAF id for debounced workspace resize (grey scrollbar guard). */
    resizeRaf: null,
    /** Late setTimeout pass after flex/CSS settle. */
    resizeTimer: null,
    /** rAF id for post-edit scrollbar show/hide sync. */
    scrollSyncRaf: null,
    app: null,
    colorPicker: null,
    pendingRichOpts: null,
    richTimer: null,
    suppressHueWheel: false,
    /** Full GET /api/events rows (system + user). Pickers filter from this. */
    catalogEvents: []
};

/**
 * Strip Tailwind-ish max-size on Blockly SVGs (skews metrics → ghost scrollbars).
 */
function blockyClearSvgMetricSkews(host) {
    if (!host) return;
    host.querySelectorAll("svg").forEach((svg) => {
        svg.style.maxWidth = "none";
        svg.style.maxHeight = "none";
    });
}

/**
 * Paired h+v scrollbars never auto-hide in Blockly when content fits — the
 * background track stays as a grey bar. Hide each axis when not needed.
 * (Scrollbar.setVisible throws on paired bars; use setVisibleInternal.)
 */
function blockySyncScrollbarVisibility(ws) {
    const pair = ws && ws.scrollbar;
    if (!pair) return;
    let m;
    try {
        m = ws.getMetrics();
    } catch (e) {
        return;
    }
    if (!m) return;
    // Slack for float rounding so a 1px overflow does not keep a dead track.
    const slack = 2;
    const needH = (m.scrollWidth || m.contentWidth || 0) > (m.viewWidth || 0) + slack;
    const needV = (m.scrollHeight || m.contentHeight || 0) > (m.viewHeight || 0) + slack;
    const h = pair.hScroll;
    const v = pair.vScroll;
    try {
        if (h && typeof h.setVisibleInternal === "function") h.setVisibleInternal(needH);
        if (v && typeof v.setVisibleInternal === "function") v.setVisibleInternal(needV);
        // Corner square between bars — hide when either axis is off.
        if (pair.corner_) {
            pair.corner_.setAttribute("display", needH && needV ? "block" : "none");
        }
    } catch (e) { /* ignore */ }
}

/** Immediate resize + scrollbar sync (host must be laid out and ≥50px). */
function blockyApplyWorkspaceResize() {
    const ws = BlockyRT.ws;
    if (!ws || !window.Blockly) return;
    const host = document.getElementById("blocklyWorkspace");
    if (!host) return;
    if ((host.offsetWidth || 0) < 50 || (host.offsetHeight || 0) < 50) return;
    try {
        const inj = host.querySelector(".injectionDiv");
        if (inj) {
            inj.style.position = "absolute";
            inj.style.left = "0";
            inj.style.top = "0";
            inj.style.right = "0";
            inj.style.bottom = "0";
            // Do not force width/height % — that parks scrollbars over the canvas.
            inj.style.removeProperty("width");
            inj.style.removeProperty("height");
        }
        blockyClearSvgMetricSkews(host);
        Blockly.svgResize(ws);
        if (ws.scrollbar && typeof ws.scrollbar.resize === "function") ws.scrollbar.resize();
        blockySyncScrollbarVisibility(ws);
    } catch (e) { /* ignore */ }
}

/**
 * Debounced resize: double-rAF for Alpine/flex settle, then a short late pass.
 * Single entry point so FS alerts / park / window resize do not thrash metrics.
 */
function blockyScheduleWorkspaceResize() {
    if (BlockyRT.resizeRaf) {
        cancelAnimationFrame(BlockyRT.resizeRaf);
        BlockyRT.resizeRaf = null;
    }
    if (BlockyRT.resizeTimer) {
        clearTimeout(BlockyRT.resizeTimer);
        BlockyRT.resizeTimer = null;
    }
    BlockyRT.resizeRaf = requestAnimationFrame(() => {
        BlockyRT.resizeRaf = requestAnimationFrame(() => {
            BlockyRT.resizeRaf = null;
            blockyApplyWorkspaceResize();
            BlockyRT.resizeTimer = setTimeout(() => {
                BlockyRT.resizeTimer = null;
                blockyApplyWorkspaceResize();
            }, 50);
        });
    });
}

/** Light pass after blocks move/grow — re-show bars we hid when content now overflows. */
function blockyScheduleScrollbarSync() {
    if (BlockyRT.scrollSyncRaf) cancelAnimationFrame(BlockyRT.scrollSyncRaf);
    BlockyRT.scrollSyncRaf = requestAnimationFrame(() => {
        BlockyRT.scrollSyncRaf = null;
        const ws = BlockyRT.ws;
        if (!ws) return;
        try {
            if (ws.scrollbar && typeof ws.scrollbar.resize === "function") ws.scrollbar.resize();
            blockySyncScrollbarVisibility(ws);
        } catch (e) { /* ignore */ }
    });
}

function blockyWs() {
    return BlockyRT.ws;
}

function blockyFingerprint(block) {
    if (!block) return "";
    const t = block.type;
    if (BLOCKY_ROOT_TRIGGERS.has(t) || t === "b_else_if" || t === BLOCKY_LEGACY_ELSE) return "control";
    try {
        if (BLOCKY_EVENT_COMPARES.has(t)) {
            return `cond:event:${block.getFieldValue("EVENT") || ""}`;
        }
        if (t === "b_condition_device") {
            const eid = block.getFieldValue("ENTITY");
            if (blockyIsMotionEntity(eid)) {
                return `cond:device:${eid}:motion`;
            }
            const profile = blockyConditionCompareProfile(eid);
            if (profile.kind === "level") {
                const mode = block.getFieldValue("MODE") || "";
                if (mode === "PCT") {
                    return `cond:device:${eid}:${profile.attribute || "pct"}`
                        + `:${block.getFieldValue("OP")}:${block.getFieldValue("VALUE")}`;
                }
                return `cond:device:${eid}:${mode}`;
            }
            if (blockyConditionIsNumericCompare(block)) {
                let attrPart = "";
                try {
                    if (profile.attrs) attrPart = String(block.getFieldValue("ATTR") || "");
                } catch (e) { /* ignore */ }
                return `cond:device:${eid}:${attrPart}`
                    + `:${block.getFieldValue("OP")}:${block.getFieldValue("VALUE")}`;
            }
            return `cond:device:${eid}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_condition_time") return `cond:time:${block.getFieldValue("TOD")}`;
        if (t === "b_action_device") {
            const eid = block.getFieldValue("ENTITY");
            const type = blockyEntityTypeOf(eid);
            if (type === "blinds" || type === "shutter") {
                const ui = block.getFieldValue("STATE");
                let pct = "";
                try { pct = String(block.getFieldValue("OPEN_PCT") || ""); } catch (e) { /* ignore */ }
                return `act:device:${eid}:${ui || "OPEN"}:${pct}`;
            }
            return `act:device:${eid}:${block.getFieldValue("STATE")}`;
        }
        if (BLOCKY_EVENT_ACTIONS.has(t)) return `act:event:${block.getFieldValue("EVENT")}`;
        // Cases and OR edges are allowed as multiples — no fingerprint
    } catch (e) { /* ignore */ }
    return "";
}

function blockyRefreshToolbox() {
    const ws = blockyWs();
    if (!ws) return;
    const present = new Set(ws.getAllBlocks(false).map((b) => b.type));
    try { ws.updateToolbox(blockyToolboxDefinition(present)); } catch (e) { /* ignore */ }
}

function blockyCancelUniqueness() {
    if (BlockyRT.uniquenessTimer) {
        clearTimeout(BlockyRT.uniquenessTimer);
        BlockyRT.uniquenessTimer = null;
    }
    BlockyRT.uniquenessScheduled = false;
    BlockyRT.pendingFieldEv = null;
    BlockyRT.pendingCreateRootId = null;
    // Do not clear richTimer / pendingRichOpts — field validators own that path.
}

function blockyBlockCaseScope(b) {
    let p = b;
    while (p) {
        if (p.type === "b_case") return p.id;
        try { p = p.getParent(); } catch (e) { break; }
    }
    return "top";
}

function blockyEnforceUniqueness(forceToolbox) {
    const ws = blockyWs();
    if (BlockyRT.loading || BlockyRT.enforcing || !ws || !window.Blockly) return;
    // Rich-shape mutate + uniqueness both use timeout 0 — never dispose mid-reshape
    // (dispose without heal was leaving “not snapped” orphans on Save).
    if (BlockyRT.richTimer || BlockyRT.pendingRichOpts) {
        if (!BlockyRT.uniquenessScheduled) {
            BlockyRT.uniquenessScheduled = true;
            BlockyRT.uniquenessTimer = setTimeout(() => {
                BlockyRT.uniquenessScheduled = false;
                BlockyRT.uniquenessTimer = null;
                blockyEnforceUniqueness(forceToolbox);
            }, 0);
        }
        return;
    }
    BlockyRT.enforcing = true;
    const Events = Blockly.Events;
    const fieldEv = BlockyRT.pendingFieldEv;
    BlockyRT.pendingFieldEv = null;
    let changed = !!forceToolbox;
    Events.disable();
    try {
        if (fieldEv && fieldEv.element === "field" && fieldEv.blockId) {
            const blk = ws.getBlockById(fieldEv.blockId);
            if (blk) {
                const fp = blockyFingerprint(blk);
                // Scope by case — ON-case Sonos OFF must not collide with OFF-case Sonos OFF.
                const scope = blockyBlockCaseScope(blk);
                const other = fp && ws.getAllBlocks(false).find((b) => (
                    b.id !== blk.id
                    && !b.isInsertionMarker
                    && blockyFingerprint(b) === fp
                    && blockyBlockCaseScope(b) === scope
                ));
                if (other) {
                    try { blk.setFieldValue(fieldEv.oldValue, fieldEv.name); } catch (e) { /* ignore */ }
                    if (blk.type === "b_action_device"
                        && (fieldEv.name === "STATE" || fieldEv.name === "ENTITY" || fieldEv.name === "HUE_MODE")) {
                        blockyActionUpdateRichShape(blk);
                    } else if (blk.type === "b_condition_device" && fieldEv.name === "ENTITY") {
                        blockyConditionUpdateShape(blk);
                    }
                    changed = true;
                }
            }
        }
        // Only one If/Do root — keep the existing rule; reject extras.
        const roots = ws.getTopBlocks(false).filter((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
        if (roots.length > 1) {
            const newId = BlockyRT.pendingCreateRootId;
            let keep = roots.find((b) => !newId || b.id !== newId) || roots[0];
            let rejected = false;
            roots.forEach((b) => {
                if (b.id === keep.id) return;
                // healStack true — keep Else-if chain attached to the surviving If/Do.
                try { b.dispose(true); changed = true; rejected = true; } catch (e) { /* ignore */ }
            });
            blockyRefreshCaseMatchLabels(keep.getNextBlock());
            if (rejected && BlockyRT.app) {
                BlockyRT.app.infoMessage =
                    "Only one If/Do per rule — use Else-if on the chain (gear-style next blocks).";
            }
        }
        BlockyRT.pendingCreateRootId = null;
        const seen = new Map();
        const toDispose = [];
        ws.getAllBlocks(false).forEach((b) => {
            if (b.isInsertionMarker) return;
            const fp = blockyFingerprint(b);
            if (!fp || fp === "trigger" || fp === "control") return;
            // Immediate parent scope: allows same device twice in one branch (per-action rich).
            const parent = b.getParent();
            const scope = parent ? parent.id : "top";
            const key = `${scope}::${fp}`;
            if (seen.has(key)) toDispose.push(b);
            else seen.set(key, b.id);
        });
        toDispose.forEach((b) => {
            // healStack true — do not leave the next action as a floating orphan.
            try { b.dispose(true); changed = true; } catch (e) { /* ignore */ }
        });
    } finally {
        Events.enable();
        BlockyRT.enforcing = false;
        // Always refresh toolbox after uniqueness.
        blockyRefreshToolbox();
    }
}

function blockyOnChange(ev) {
    if (!blockyWs() || !ev) return;
    // Selection / UI — refresh Delete button enabled state.
    if (ev.isUiEvent) {
        if (BlockyRT.app) {
            // Blockly Selected: newElementId is the block id (or null when cleared).
            const selType = Blockly.Events && Blockly.Events.SELECTED;
            if (ev.type === selType || ev.type === "selected" || ev.element === "selected") {
                const nid = ev.newElementId != null ? ev.newElementId : ev.newValue;
                BlockyRT.app._blocklySelectedId = nid || null;
            } else if (typeof BlockyRT.app._captureSelectedBlock === "function") {
                BlockyRT.app._captureSelectedBlock();
            }
            BlockyRT.app.blocklyUiTick = (BlockyRT.app.blocklyUiTick || 0) + 1;
        }
        return;
    }
    if (BlockyRT.loading) return;
    const Events = Blockly.Events;
    const t = ev.type;
    const isCreate = t === Events.BLOCK_CREATE || t === "create";
    const isChange = (t === Events.BLOCK_CHANGE || t === "change") && ev.element === "field";
    // Connect or disconnect (not free XY nudges — those are not in saved JSON).
    const isMoveRelink = (t === Events.BLOCK_MOVE || t === "move") && (!!ev.newParentId || !!ev.oldParentId);
    const isDelete = t === Events.BLOCK_DELETE || t === "delete";
    const isMoveAny = t === Events.BLOCK_MOVE || t === "move";
    if (!isCreate && !isChange && !isMoveRelink && !isDelete) {
        // Free XY drag still changes content bounds — keep scrollbar visibility honest.
        if (isMoveAny) blockyScheduleScrollbarSync();
        return;
    }

    // Mark dirty immediately. The uniqueness timer below can be cancelled (e.g. by
    // loadV2IntoBlockly → blockyCancelUniqueness) and must not be the only dirty path.
    if (BlockyRT.app) BlockyRT.app.markEditorDirty();
    blockyScheduleScrollbarSync();

    if (isCreate) {
        const ws = blockyWs();
        const ids = ev.ids || (ev.blockId ? [ev.blockId] : []);
        let needGateWording = false;
        ids.forEach((id) => {
            const b = ws && ws.getBlockById(id);
            if (!b) return;
            if (BLOCKY_ROOT_TRIGGERS.has(b.type)) {
                BlockyRT.pendingCreateRootId = b.id;
            }
            // Duplicate/paste: init() shaped COMPARE for the dropdown-default ENTITY;
            // Blockly then restores the copied ENTITY without a field-change reshape.
            if (b.type === "b_condition_device") {
                blockyConditionUpdateShape(b);
                needGateWording = true;
            } else if (
                BLOCKY_EVENT_COMPARES.has(b.type)
                || b.type === "b_logic_and"
                || b.type === "b_logic_or"
                || b.type === "b_logic_not"
            ) {
                needGateWording = true;
            }
        });
        if (needGateWording) blockyScheduleConditionGateWordingRefresh();
    }
    if (isDelete || isMoveRelink) {
        // Event Compare added/removed/moved → refresh turns ↔ is on sibling device Compares.
        blockyScheduleConditionGateWordingRefresh();
    }
    let touchedActionId = null;
    if (isChange) {
        BlockyRT.pendingFieldEv = ev;
        // When OP changes on a sensor condition, update the crosses/equals/… label live.
        if (ev.blockId && ev.name === "OP") {
            const ws = blockyWs();
            const blk = ws && ws.getBlockById(ev.blockId);
            if (blk && blk.type === "b_condition_device") {
                const profile = blockyConditionCompareProfile(blk.getFieldValue("ENTITY"));
                if (profile.kind === "sensor") {
                    try {
                        const lf = blk.getField("CROSSES_LABEL");
                        if (lf) lf.setValue(blockyOpCrossesLabel(ev.newValue));
                    } catch (e) { /* ignore */ }
                }
            }
        }
        // Backup path: field validators usually queue rich shape; this covers setFieldValue.
        if (ev.blockId && (ev.name === "STATE" || ev.name === "ENTITY" || ev.name === "HUE_MODE")) {
            const ws = blockyWs();
            const blk = ws && ws.getBlockById(ev.blockId);
            if (blk && blk.type === "b_action_device") {
                touchedActionId = blk.id;
                const opts = {};
                if (ev.name === "STATE") opts.forceState = ev.newValue;
                if (ev.name === "HUE_MODE") {
                    opts.forceHueMode = ev.newValue;
                    opts.forceState = "ON";
                    if (ev.newValue === "CUSTOM" && !BlockyRT.suppressHueWheel) opts.openWheel = true;
                }
                blockyQueueRichShape(blk, opts);
            }
        }
    }
    if (BlockyRT.uniquenessScheduled) return;
    BlockyRT.uniquenessScheduled = true;
    BlockyRT.uniquenessTimer = setTimeout(() => {
        BlockyRT.uniquenessScheduled = false;
        BlockyRT.uniquenessTimer = null;
        blockyEnforceUniqueness(false);
        // After uniqueness may revert STATE — re-sync from live fields (skip if a
        // richer queued update with force* / openWheel is already pending).
        if (touchedActionId && !BlockyRT.pendingRichOpts) {
            const ws = blockyWs();
            const blk = ws && ws.getBlockById(touchedActionId);
            if (blk && blk.type === "b_action_device") {
                blockyActionUpdateRichShape(blk);
            }
        }
        if (BlockyRT.app) {
            BlockyRT.app.blocklyUiTick = (BlockyRT.app.blocklyUiTick || 0) + 1;
        }
    }, 0);
}

function blockyMkBlock(type, fields, x, y) {
    const ws = blockyWs();
    const b = ws.newBlock(type);
    if (fields) {
        Object.entries(fields).forEach(([k, v]) => {
            if (v == null || v === "") return;
            try {
                b.setFieldValue(String(v), k);
            } catch (e) {
                // Usually means eid missing from dropdown — open-rule inject should prevent this.
                console.warn(`Blocky: could not set ${type}.${k}=${v}`, e);
            }
        });
    }
    if (typeof x === "number" && typeof y === "number") b.moveBy(x, y);
    if (b.initSvg) b.initSvg();
    b.render();
    return b;
}

function blockyConnectChain(parent, inputName, blocks) {
    const input = parent.getInput(inputName);
    if (!input || !input.connection) return;
    let prevConn = input.connection;
    blocks.forEach((b) => {
        if (!b || !b.previousConnection) return;
        try {
            prevConn.connect(b.previousConnection);
            prevConn = b.nextConnection;
        } catch (e) { /* skip */ }
    });
}

function blockyConnectNext(start, blocks) {
    let prev = start;
    blocks.forEach((b) => {
        if (!prev || !b || !prev.nextConnection || !b.previousConnection) return;
        try {
            prev.nextConnection.connect(b.previousConnection);
            prev = b;
        } catch (e) { /* skip */ }
    });
    return prev;
}

function blockyDestroyWorkspace() {
    blockyCancelUniqueness();
    if (BlockyRT.richTimer) {
        clearTimeout(BlockyRT.richTimer);
        BlockyRT.richTimer = null;
    }
    BlockyRT.pendingRichOpts = null;
    if (BlockyRT.resizeRaf) {
        cancelAnimationFrame(BlockyRT.resizeRaf);
        BlockyRT.resizeRaf = null;
    }
    if (BlockyRT.resizeTimer) {
        clearTimeout(BlockyRT.resizeTimer);
        BlockyRT.resizeTimer = null;
    }
    if (BlockyRT.scrollSyncRaf) {
        cancelAnimationFrame(BlockyRT.scrollSyncRaf);
        BlockyRT.scrollSyncRaf = null;
    }
    if (BlockyRT.resizeObserver) {
        try { BlockyRT.resizeObserver.disconnect(); } catch (e) { /* ignore */ }
        BlockyRT.resizeObserver = null;
    }
    if (BlockyRT.ws) {
        try { BlockyRT.ws.dispose(); } catch (e) { /* ignore */ }
    }
    BlockyRT.ws = null;
    BlockyRT.ready = false;
    BlockyRT.schemaInjected = null;
    const host = document.getElementById("blocklyWorkspace");
    if (host) host.innerHTML = "";
}

function blockyOrphanLeaves(ws) {
    return ws.getAllBlocks(false).filter((b) => {
        if (!b) return false;
        if (b.isInsertionMarker) return false;
        if (typeof b.isDeadOrDying === "function" && b.isDeadOrDying()) return false;
        if (b.type === "b_if_do") return false;
        if (b.type === "b_else_if") {
            const prev = b.previousConnection;
            return !(prev && prev.isConnected());
        }
        // Bare Else / NOT retired — always treat as orphan until the author deletes them.
        if (b.type === BLOCKY_LEGACY_ELSE || b.type === "b_logic_not") return true;
        if (b.type === "b_condition_device" || b.type === "b_condition_time"
            || BLOCKY_EVENT_COMPARES.has(b.type)
            || b.type === "b_action_device" || BLOCKY_EVENT_ACTIONS.has(b.type)) {
            const prev = b.previousConnection;
            return !(prev && prev.isConnected());
        }
        // Legacy blocks (if any left on canvas) count as orphans — must delete.
        if (BLOCKY_LEGACY_TRIGGERS.has(b.type) || b.type === "b_case"
            || b.type === "b_trig_device_edge" || BLOCKY_EVENT_EDGES.has(b.type)) {
            return true;
        }
        return false;
    });
}

function blockyAssertNoOrphans(ws) {
    const orphans = blockyOrphanLeaves(ws);
    if (!orphans.length) return;
    throw new Error(
        `Save blocked: ${orphans.length} block(s) not snapped into place — connect or delete them.`
    );
}

function blockyReadChain(start, fn) {
    const out = [];
    let cur = start;
    while (cur) {
        out.push(fn(cur));
        cur = cur.getNextBlock();
    }
    return out;
}

/** B4/H4: walk nested condition trees (branch top-level or Logic group children). */
function blockyForEachConditionLeaf(conds, fn) {
    (conds || []).forEach((c) => {
        if (!c || typeof c !== "object") return;
        if ((c.op === "and" || c.op === "or" || c.op === "not") && Array.isArray(c.children)) {
            blockyForEachConditionLeaf(c.children, fn);
        } else if (c.type) {
            fn(c);
        }
    });
}

/** Count leaf Compare rows (ignores Logic group wrappers). */
function blockyCountLeafCompares(conds) {
    let n = 0;
    blockyForEachConditionLeaf(conds, () => { n += 1; });
    return n;
}

function blockyOrListWakeConditions(trigger) {
    const edges = (trigger || []).filter((x) => x && x.entity_id);
    const unique = [...new Set(edges.map((x) => String(x.entity_id)))];
    if (unique.length === 1) {
        return [{ type: "device_state", entity_id: unique[0], is: "ANY" }];
    }
    const children = edges.map((edge) => {
        const eid = String(edge.entity_id);
        const raw = edge.state;
        if (raw == null || raw === "") {
            return { type: "device_state", entity_id: eid, is: "ANY" };
        }
        const st = String(raw).toUpperCase();
        const isVal = (st === "ON" || st === "OFF" || st === "OPEN" || st === "CLOSED")
            ? st : String(raw);
        return { type: "device_state", entity_id: eid, is: isVal };
    });
    if (children.length <= 1) return children;
    return [{ op: "or", children }];
}

/** Read one leaf or Logic group block → YAML condition expr. */
function blockyReadConditionExpr(block, readLeafFn) {
    if (!block) return null;
    if (block.type === "b_logic_and" || block.type === "b_logic_or") {
        const op = block.type === "b_logic_and" ? "and" : "or";
        const children = blockyReadChain(block.getInputTargetBlock("CHILDREN"), (b) =>
            blockyReadConditionExpr(b, readLeafFn)).filter(Boolean);
        return children.length ? { op, children } : null;
    }
    if (block.type === "b_logic_not") {
        const inner = blockyReadConditionExpr(block.getInputTargetBlock("CHILD"), readLeafFn);
        return inner ? { op: "not", children: [inner] } : null;
    }
    return readLeafFn(block);
}

/** Build one Blockly block from a YAML condition leaf or Logic group. */
function blockyConditionBlockFromExpr(c, applyRichFn) {
    if (!c || typeof c !== "object") return null;
    if ((c.op === "and" || c.op === "or" || c.op === "not") && Array.isArray(c.children)) {
        if (c.op === "not") {
            const blk = blockyMkBlock("b_logic_not");
            const child = blockyConditionBlockFromExpr(c.children[0], applyRichFn);
            if (child) blockyConnectChain(blk, "CHILD", [child]);
            return blk;
        }
        const blk = blockyMkBlock(c.op === "and" ? "b_logic_and" : "b_logic_or");
        const kids = (c.children || []).map((x) => blockyConditionBlockFromExpr(x, applyRichFn)).filter(Boolean);
        blockyConnectChain(blk, "CHILDREN", kids);
        return blk;
    }
    if (c.type === "time_of_day") {
        return blockyMkBlock("b_condition_time", { TOD: c.is || "dark" });
    }
    if (c.type === "event") {
        const eid = String(c.event || "");
        let origin = "user";
        try {
            if (BlockyRT.app && typeof BlockyRT.app._eventOrigin === "function") {
                origin = BlockyRT.app._eventOrigin(eid);
            }
        } catch (e) { /* ignore */ }
        const type = origin === "system" ? "b_condition_event_sys" : "b_condition_event";
        return blockyMkBlock(type, { EVENT: eid });
    }
    if (c.type === "device_state") {
        const blk = blockyMkBlock("b_condition_device", { ENTITY: c.entity_id });
        if (typeof applyRichFn === "function") applyRichFn(blk, c);
        else blockyApplyConditionRich(blk, c);
        return blk;
    }
    return null;
}

/**
 * Project legacy v2 trigger+cases → B19 branches for canvas load (cutover window).
 * Mirrors core/automations_schema_b19.convert_v2_rule_to_branches (simplified).
 */
function blockyProjectLegacyToBranches(rule) {
    if (rule && Array.isArray(rule.branches)) return rule;
    const cases = (rule && rule.cases) || [];
    const rawTrig = (rule && rule.trigger) || {};
    let trig = rawTrig;
    if (Array.isArray(trig) && trig.length === 1) trig = trig[0];
    const branches = [];
    let wakeCommon = [];
    if (Array.isArray(rawTrig) && rawTrig.length >= 2) {
        wakeCommon = blockyOrListWakeConditions(rawTrig);
    } else if (trig && trig.event) {
        wakeCommon.push({ type: "event", event: String(trig.event) });
    }
    const deviceEid = (trig && trig.entity_id) ? String(trig.entity_id) : "";
    const numericTrig = !!(trig && trig.op);
    if (numericTrig && deviceEid) {
        const c = {
            type: "device_state",
            entity_id: deviceEid,
            op: String(trig.op),
            is: trig.state
        };
        if (trig.attribute) c.attribute = trig.attribute;
        wakeCommon.push(c);
    }
    const orDeviceEid = (Array.isArray(rawTrig) && rawTrig.length >= 2)
        ? ([...new Set(rawTrig.filter((x) => x && x.entity_id).map((x) => String(x.entity_id)))].length === 1
            ? String(rawTrig.find((x) => x && x.entity_id).entity_id) : "")
        : deviceEid;
    const wakeHasAny = wakeCommon.some((c) => c.type === "device_state" && c.is === "ANY");
    const list = cases.length ? cases : [{ actions: [] }];
    list.forEach((c, i) => {
        const when = i === 0 ? "if" : "else_if";
        const conds = wakeCommon.map((x) => Object.assign({}, x));
        if (orDeviceEid && !numericTrig && !Array.isArray(rawTrig)) {
            const ts = c.to_state;
            if (ts == null || ts === "") {
                if (!wakeHasAny) {
                    conds.push({ type: "device_state", entity_id: orDeviceEid, is: "ANY" });
                }
            } else {
                conds.push({
                    type: "device_state",
                    entity_id: orDeviceEid,
                    is: String(ts).toUpperCase()
                });
            }
        }
        (c.conditions || []).forEach((cc) => conds.push(Object.assign({}, cc)));
        branches.push({
            when,
            conditions: conds,
            actions: (c.actions || []).map((a) => Object.assign({}, a))
        });
    });
    return {
        id: rule.id,
        name: rule.name,
        enabled: rule.enabled !== false,
        branches
    };
}

/** Build condition blocks from B19 condition dicts (flat AND + nested Logic groups). */
function blockyConditionBlocksFromList(conds) {
    return (conds || []).map((c) => blockyConditionBlockFromExpr(c)).filter(Boolean);
}

function blockyApp() {
    return {
        connected: false,
        /** B10G: yellow checklist overlay during cold init only. */
        editorLoading: true,
        reloadSuppressOverlay: false,
        loadTimingsModalOpen: false,
        /** Frozen copy for the admin modal — taken once at end of cold load. */
        coldLoadTimingsSnapshot: null,
        /** JS wall clock for full cold refreshAll() (first fetch → snapshot). */
        coldLoadTotalMs: null,
        /** B10H: nav → library visible (overlay clear); empty canvas OK. */
        coldTimeToInteractiveMs: null,
        /** init() entry → refreshAll() start (Alpine setup before first fetch). */
        coldLoadInitDelayMs: null,
        /** navigation start → init() entry (script load / parse before Alpine runs). */
        coldLoadNavToInitMs: null,
        loadChecklist: [
            { key: "state", label: "Device state", api: "GET /api/state", done: false, ms: null },
            { key: "automations", label: "Automations", api: "GET /api/automations", done: false, ms: null },
            { key: "events", label: "Events", api: "GET /api/events", done: false, ms: null },
            { key: "library", label: "Building library", api: "Building library", done: false, ms: null },
            { key: "fire", label: "Schedule status", api: "GET /api/automations/fire-status", done: false, ms: null }
        ],
        _heartbeatTimer: null,
        /** B10H: in-flight guard — concurrent cold/warm refresh shares one promise. */
        _refreshAllInFlight: null,
        busy: false,
        /** B10F: rule-save lock — busy overlay or failed (retry/dismiss). */
        ruleSaveBusy: false,
        ruleSaveFailed: false,
        /** Page lock during manual Refresh (same overlay chrome as rule save). */
        refreshBusy: false,
        isAdmin: false,
        errorMessage: "",
        /** B9A silent-loss B: non-preservable drops detected on last canvas load. */
        silentLossReasons: [],
        infoMessage: "",
        registryCheckMessage: "",
        registryCheckOk: null,
        filterText: "",
        /** Exclusive: true ⇒ only disabled rows; false ⇒ only enabled (default).
         * Applies to UE/UR/SR/D only — SE is never disabled and ignores this toggle. */
        showDisabledOnly: false,
        /** Kind checkboxes — B10F: UE & SE default OFF; UR/SR/D default ON. */
        libraryKindFilter: { ue: false, ur: true, se: false, sr: true, d: true },
        /** 'kind' = UE→UR→SE→SR→D then name; 'name' = name only. Persisted in localStorage. */
        librarySortMode: (typeof localStorage !== "undefined"
            && localStorage.getItem(BLOCKY_LIBRARY_SORT_KEY) === "name") ? "name" : "kind",
        automations: [],
        selectedRule: null,
        entityOptions: [],
        huePresets: {},
        sonosStations: {},
        blockyColorTargetId: null,
        blockyColorBri: 100,
        blockyColorHex: "#FFD180",
        showHiddenEntities: false,
        editorDirty: false,
        suppressDirtyUntil: 0,
        pendingNav: null,
        blocklyFullscreen: false,
        // Bump when block definitions change (B10E: user/system When+Fire twins).
        blocklySchemaVersion: 58,
        /** B23: server pending activation queue from GET /api/state. */
        rulesActivationPending: {
            count: 0,
            rule_ids: [],
            event_ids: [],
            needs_automations: false,
            needs_events: false
        },
        activateBusy: false,
        /** Session cache — auto-off from GET /api/state (fallback: GET /api/auto-off-timer). */
        autoOffConfig: null,
        _autoOffFetchInFlight: null,
        /** Set after a failed fetch so the table stops spinning. */
        _autoOffLoadFailed: false,
        /** entity_id → display label; rebuilt when auto-off config loads. */
        autoOffByEid: {},
        /** Live device values keyed by registry idx (from GET /api/state). */
        liveDevices: {},
        blocklyUiTick: 0,
        hardDenyEntityIds: ["switch.safety.safety_wisc_5v"],
        /**
         * B10E Library rows: UE (user events) + UR/SR/D rules + SE (all pickable
         * system catalog events, view-only). No in-memory shells — create SR via New rule.
         */
        libraryRows: [],
        /** @deprecated kept as empty alias; rebuildLibraryRows is authoritative. */
        orphanEventRows: [],
        /** Delete-blocked modal copy when DELETE /api/events returns 409. */
        eventDeleteBlockedMessage: "",
        /**
         * Disable-blocked inline usages: rule names that listen and/or fire the event.
         */
        fireRefRuleNames: [],
        /** B10F: GET /api/automations/fire-status entries keyed by event_uuid. */
        fireStatusByUuid: {},
        /** Display line above Full screen (Will fire / Has fired / Doesn't fire). */
        fireStatusLine: "",
        editor: {
            id: "",
            name: "",
            // B10B: per-rule enable (engine skips when false). Default true.
            enabled: true,
            ruleJson: "{}",
            // UE-form fields (user event — Appear on explorer / confirm / enabled).
            eventShowOnDashboard: false,
            eventRequireConfirmation: false,
            eventEnabled: true
        },

        /**
         * Left Library = UE + UR + SE + SR + D, filtered by text / kind / Show disabled/unused XOR.
         * UE/UR/SR/D: OFF = enabled only; ON = disabled only.
         * SE: OFF = used only (has listening SR); ON = unused only (no listening SR).
         */
        get filteredLibrary() {
            const q = this.filterText.trim().toLowerCase();
            const kinds = this.libraryKindFilter || {};
            const showDis = !!this.showDisabledOnly;
            // Companion SR presence — SE used/unused XOR.
            const seListeners = this._systemEventsWithListeners();
            const rows = (this.libraryRows || []).filter((r) => {
                if (!r) return false;
                const k = this.libraryKind(r);
                if (k && kinds[k] === false) return false;
                if (k === "se") {
                    // Exclusive: used view XOR unused view (SE never "disabled").
                    const sid = String(r.id || "");
                    const unused = !seListeners.has(sid);
                    if (showDis ? !unused : unused) return false;
                } else {
                    const isDis = this.libraryRowIsDisabled(r);
                    // Exclusive: enabled view XOR disabled view (UE/UR/SR/D).
                    if (showDis ? !isDis : isDis) return false;
                }
                if (!q) return true;
                const label = this.libraryRowLabel(r).toLowerCase();
                const id = String(r.id || r.systemEventId || "").toLowerCase();
                return label.includes(q) || id.includes(q);
            });
            return this._sortLibraryRows(rows);
        },

        /** Exclusive like Device Explorer: ON = only soft-hidden; OFF = only non-hidden. */
        get visibleEntityOptions() {
            return this.entityOptions.filter((opt) =>
                this.showHiddenEntities ? opt.softHidden : !opt.softHidden
            );
        },

        /** B23: pending activation count from server state. */
        get rulesPendingCount() {
            const p = this.rulesActivationPending || {};
            return Number(p.count) || 0;
        },

        get rulesPendingBannerText() {
            const n = this.rulesPendingCount;
            const noun = n === 1 ? "rule" : "rules";
            return `${n} ${noun} saved — not active until you Activate changed rules.`;
        },

        get showActivatePendingButton() {
            return this.rulesPendingCount > 0 && this.isAdmin && !this.editorLoading;
        },

        /** Collect entity_ids used in the open rule for the read-only device table. */
        _collectRuleDeviceRoles() {
            const roles = new Map();
            const mark = (eid, role) => {
                if (!eid) return;
                const k = String(eid);
                if (!roles.has(k)) roles.set(k, { condition: false, action: false });
                roles.get(k)[role] = true;
            };
            const fromRuleJson = () => {
                try {
                    const rule = JSON.parse(this.editor.ruleJson || "{}");
                    if (Array.isArray(rule.branches)) {
                        rule.branches.forEach((br) => {
                            blockyForEachConditionLeaf((br && br.conditions) || [], (c) => {
                                if (c && c.type === "device_state" && c.entity_id) mark(c.entity_id, "condition");
                            });
                            (br.actions || []).forEach((a) => {
                                if (a && a.entity_id) mark(a.entity_id, "action");
                            });
                        });
                    }
                } catch (e) { /* ignore */ }
            };
            // Saved selection: ruleJson updates synchronously in _doSelectRule.
            // Workspace lags until loadV2IntoBlockly (~seconds) — do not read stale blocks.
            const ws = blockyWs();
            if (this.editorDirty && ws && !BlockyRT.loading && this.showBlocklyWorkspace) {
                ws.getAllBlocks(false).forEach((b) => {
                    if (b.isInFlyout) return;
                    if (b.type === "b_condition_device") mark(b.getFieldValue("ENTITY"), "condition");
                    if (b.type === "b_action_device") mark(b.getFieldValue("ENTITY"), "action");
                });
            }
            if (roles.size === 0) {
                fromRuleJson();
            } else if (!this.editorDirty) {
                // Clean selection — ruleJson is authoritative even if workspace not cleared yet.
                roles.clear();
                fromRuleJson();
            }
            return roles;
        },

        _autoOffLabelForEid(eid, meta) {
            if (!this.autoOffConfig) {
                if (this._autoOffFetchInFlight) return "loading…";
                if (!this._autoOffLoadFailed) {
                    void this._kickAutoOffConfigLoad();
                    return "loading…";
                }
                return "unavailable";
            }
            const key = String(eid || "");
            if (this.autoOffByEid && Object.prototype.hasOwnProperty.call(this.autoOffByEid, key)) {
                return this.autoOffByEid[key];
            }
            return this._computeAutoOffLabel(key, meta);
        },

        _applyAutoOffConfigPayload(raw) {
            if (!raw || typeof raw !== "object") {
                this.autoOffConfig = null;
                return;
            }
            // Defensive: accept flat payload or legacy wrapper shape.
            if (raw.auto_off_devices && typeof raw.auto_off_devices === "object") {
                this.autoOffConfig = Object.assign({}, raw.auto_off_devices, {
                    device_product_types: raw.device_product_types || raw.auto_off_devices.device_product_types || {}
                });
            } else {
                this.autoOffConfig = raw;
            }
            this._autoOffLoadFailed = false;
            this._rebuildAutoOffIndex();
        },

        /** B23: primary auto-off source — bundled in GET /api/state (no extra round-trip). */
        _applyAutoOffFromState(system) {
            const sys = system && typeof system === "object" ? system : {};
            const raw = sys.auto_off_timer;
            if (!raw || typeof raw !== "object" || !Object.keys(raw).length) return false;
            this._applyAutoOffConfigPayload(raw);
            return !!this.autoOffConfig;
        },

        _kickAutoOffConfigLoad() {
            if (this.autoOffConfig || this._autoOffFetchInFlight) return this._autoOffFetchInFlight;
            this._autoOffFetchInFlight = this.ensureAutoOffConfig()
                .finally(() => {
                    this._autoOffFetchInFlight = null;
                    this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                });
            return this._autoOffFetchInFlight;
        },

        _computeAutoOffLabel(eid, meta) {
            const cfg = this.autoOffConfig;
            if (!cfg) return "unavailable";
            const managed = new Set((cfg.managed_auto_off || []).map(String));
            if (!managed.has(String(eid))) return "-";
            const delays = cfg.auto_off_delays || {};
            const eidStr = String(eid);
            if (delays[eidStr] != null && delays[eidStr] !== "") {
                return `${Number(delays[eidStr])} min`;
            }
            const overrides = cfg.device_product_types || {};
            const typeKey = blockyAutoOffTypeKey(
                eidStr,
                meta && meta.origin,
                meta && meta.type,
                overrides
            );
            const pt = cfg.default_pertype_auto_off_minutes || {};
            if (typeKey && pt[typeKey] != null && pt[typeKey] !== "") {
                return `${Number(pt[typeKey])} min (${typeKey})`;
            }
            const gen = Number(cfg.default_auto_off_minutes);
            return Number.isFinite(gen) && gen > 0 ? `${gen} min (default)` : "managed";
        },

        _rebuildAutoOffIndex() {
            const cfg = this.autoOffConfig;
            const out = {};
            if (!cfg) {
                this.autoOffByEid = out;
                return;
            }
            const managed = (cfg.managed_auto_off || []).map(String);
            for (const eid of managed) {
                const meta = (this.entityOptions || []).find((o) => o.eid === eid);
                out[eid] = this._computeAutoOffLabel(eid, meta);
            }
            this.autoOffByEid = out;
        },

        _liveDeviceRaw(meta) {
            if (!meta || meta.idx == null) return undefined;
            const idx = meta.idx;
            const live = this.liveDevices || {};
            if (live[idx] !== undefined) return live[idx];
            if (live[String(idx)] !== undefined) return live[String(idx)];
            return undefined;
        },

        /** B23: read-only device summary for the open rule (below hidden-devices toggle). */
        get ruleDeviceTableRows() {
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return [];
            }
            // Reactive deps: auto-off cache + live device snapshot.
            void this.autoOffConfig;
            void this.autoOffByEid;
            void this._autoOffLoadFailed;
            void this.liveDevices;
            void this.blocklyUiTick;
            void (this.selectedRule && this.selectedRule.id);
            void (this.editor && this.editor.ruleJson);
            const roles = this._collectRuleDeviceRoles();
            const rows = [];
            for (const [eid, r] of roles.entries()) {
                const meta = (this.entityOptions || []).find((o) => o.eid === eid);
                let roleLabel = "action";
                if (r.condition && r.action) roleLabel = "both";
                else if (r.condition) roleLabel = "condition";
                const raw = this._liveDeviceRaw(meta);
                const status = meta && !blockyDeviceTableSkipsStatus(meta)
                    ? blockyFormatDeviceTableStatus(raw, meta)
                    : "—";
                rows.push({
                    eid,
                    name: meta ? meta.name : eid,
                    role: roleLabel,
                    type: meta ? (meta.typeLabel || meta.type || "—") : "—",
                    status,
                    autoOff: this._autoOffLabelForEid(eid, meta),
                    origin: meta && meta.origin ? meta.origin : "—",
                    hidden: meta && meta.softHidden ? "Yes" : "No"
                });
            }
            rows.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
            return rows;
        },

        libraryRowIsPending(row) {
            if (!row) return false;
            const p = this.rulesActivationPending || {};
            const ruleIds = (p.rule_ids || []).map(String);
            const eventIds = (p.event_ids || []).map(String);
            if (row.isEventRow) return eventIds.includes(String(row.id || ""));
            if (row.isSystemEventRow) return false;
            return ruleIds.includes(String(row.id || ""));
        },

        get showBlocklyWorkspace() {
            // UE / SE catalog rows have no Blockly canvas. B9A: Blockly is the only
            // rule editor, so any other selected rule always shows the canvas.
            if (this.selectedRule && (this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow)) {
                return false;
            }
            return !!this.selectedRule;
        },

        /** B10F: all Automations UI locked during rule save, refresh, activation, or until retry/dismiss. */
        get uiLocked() {
            return !!(this.ruleSaveBusy || this.ruleSaveFailed || this.refreshBusy || this.activateBusy);
        },

        /** True when the editor row is a saved UR or SR (event-triggered rule). */
        get showExecuteRuleButton() {
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return false;
            }
            const kind = this.libraryKind(this.selectedRule);
            return kind === "ur" || kind === "sr";
        },

        /** Saved trigger event UUID for manual Execute (UR/SR only). */
        _executeTriggerEventId() {
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return "";
            }
            const rid = this.editor.id || this.selectedRule.id;
            const saved = rid
                ? (this.automations || []).find((r) => r && String(r.id) === String(rid))
                : null;
            if (saved) return this._primaryEventIdFromRule(saved);
            try {
                return this._primaryEventIdFromRule(JSON.parse(this.editor.ruleJson || "{}"));
            } catch (e) {
                return "";
            }
        },

        /** Manual test fire — saved UR/SR only (same bus path as Explorer scene buttons). */
        get canExecuteSelectedRule() {
            if (this.uiLocked || this.busy) return false;
            if (!this.showExecuteRuleButton) return false;
            if (this.selectedRule.isDraft || !this.editor.id) return false;
            if (this.editor.enabled === false) return false;
            if (this.editorDirty) return false;
            return !!this._executeTriggerEventId();
        },

        /** Tooltip when Execute is visible but disabled. */
        get executeRuleTitle() {
            if (!this.showExecuteRuleButton) return "";
            if (this.selectedRule && this.selectedRule.isDraft) return "Save the rule first";
            if (!this.editor.id) return "Save the rule first";
            if (this.editor.enabled === false) return "Enable the rule first";
            if (this.editorDirty) return "Save changes first";
            if (!this._executeTriggerEventId()) return "Rule has no event trigger";
            return "Fire this rule's trigger event (manual test)";
        },

        /** True when open UE already has a listening UR. */
        get selectedUeHasListeningUr() {
            if (!this.selectedRule || !this.selectedRule.isEventRow) return false;
            const eid = String(this.selectedRule.id || this.editor.id || "");
            if (!eid) return false;
            return this._triggerRefNamesForEvent(eid).length > 0;
        },

        /** Event id for disable locks / Show usages (UE form id, or UR rule's user-event trigger). */
        get usagesEventId() {
            if (this.selectedRule && this.selectedRule.isEventRow) {
                return String(this.editor.id || this.selectedRule.id || "");
            }
            if (this.selectedRule && this.selectedRule.isSystemEventRow) {
                return String(this.selectedRule.id || this.editor.id || "");
            }
            let rule = this.selectedRule;
            if (!rule || (!rule.branches && !rule.trigger)) {
                try { rule = JSON.parse(this.editor.ruleJson || "{}"); }
                catch (e) { rule = null; }
            }
            const evId = this._primaryEventIdFromRule(rule);
            if (!evId) return "";
            if (this._eventOrigin(evId) === "user") return evId;
            return "";
        },

        /**
         * True when current UE cannot be disabled: any rule *listens* (trigger)
         * OR *fires* it. Both directions block — see `_usageRuleNamesForEvent`.
         */
        get eventDisableBlocked() {
            const id = this.usagesEventId;
            if (!id || !(this.selectedRule && this.selectedRule.isEventRow)) return false;
            return this._usageRuleNamesForEvent(id).length > 0;
        },

        /** True when current UR cannot be disabled (its trigger UE is fire-referenced). */
        get ruleDisableBlocked() {
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return false;
            }
            if (this.libraryKind(this.selectedRule) !== "ur") return false;
            const id = this.usagesEventId;
            if (!id) return false;
            return this._fireRefNamesForEvent(id).length > 0;
        },

        /** Listening SR name for the open SE catalog row (if any). */
        get selectedSeListenerName() {
            if (!this.selectedRule || !this.selectedRule.isSystemEventRow) return "";
            const eid = String(this.selectedRule.id || "");
            if (!eid) return "";
            for (const rule of this.automations || []) {
                if (!rule) continue;
                if (this._primaryEventIdFromRule(rule) === eid) {
                    return String(rule.listName || rule.name || rule.id || "");
                }
            }
            return "";
        },

        toggleLibrarySortMode() {
            this.librarySortMode = this.librarySortMode === "name" ? "kind" : "name";
            try { localStorage.setItem(BLOCKY_LIBRARY_SORT_KEY, this.librarySortMode); }
            catch (e) { /* ignore */ }
        },

        libraryRowKey(row) {
            if (!row) return "nil";
            if (row.isSystemEventRow) return `se:${row.id}`;
            if (row.isEventRow) return `ue:${row.id || "draft"}`;
            return `rule:${row.id || row.name || "x"}`;
        },

        libraryRowLabel(row) {
            if (!row) return "(unnamed)";
            if (row.listName) return row.listName;
            const base = row.name || "(unnamed)";
            if (row.isEventRow || row.isSystemEventRow || row.isDraft) return base;
            const wake = this._wakeSummaryFromRule(row);
            return wake ? `${base} · ${wake}` : base;
        },

        /** Disabled for exclusive Show disabled/unused filter (UE/UR/SR/D). SE uses unused XOR separately. */
        libraryRowIsDisabled(row) {
            if (!row) return false;
            if (row.isSystemEventRow || this.libraryKind(row) === "se") return false;
            if (row.isEventRow) return row.enabled === false;
            return row.enabled === false;
        },

        /**
         * B10E libraryKind: ue | ur | se | sr | d.
         * UE = user event catalog; UR = user-event rule; SE = system event catalog;
         * SR = system-event rule; D = device-triggered rule.
         */
        libraryKind(rule) {
            if (!rule) return null;
            if (rule.isDraft && !rule.isEventRow && !rule.isSystemEventRow) return null;
            if (rule.libraryKind) return rule.libraryKind;
            if (rule.isEventRow) return "ue";
            if (rule.isSystemEventRow) return "se";
            const evId = this._primaryEventIdFromRule(rule);
            if (evId) {
                if (this._eventOrigin(evId) === "system") return "sr";
                return "ur";
            }
            return "d";
        },

        libraryRowButtonClass(row) {
            const selected = this._isSelectedLibraryRow(row);
            const parts = ["w-full", "btn", "btn-sm", "justify-start", "text-left", "normal-case", "gap-1.5", "px-2"];
            if (selected) parts.push("btn-warning");
            else if (!(this.selectedRule && this.selectedRule.isDraft && !this.selectedRule.isEventRow
                && !this.selectedRule.isSystemEventRow)) {
                parts.push("btn-ghost");
            }
            if (this.libraryRowIsDisabled(row)) parts.push("opacity-40");
            return parts.join(" ");
        },

        _isSelectedLibraryRow(row) {
            const sel = this.selectedRule;
            if (!sel || !row) return false;
            if (sel.isSystemEventRow && row.isSystemEventRow) {
                return String(sel.id) === String(row.id);
            }
            if (sel.isEventRow && row.isEventRow) {
                if (sel.isDraft && row.isDraft) return true;
                return !!sel.id && sel.id === row.id;
            }
            if (sel.isDraft && !sel.isEventRow) return false;
            if (sel.isSystemEventRow || row.isSystemEventRow || sel.isEventRow || row.isEventRow) {
                return false;
            }
            return !!sel.id && sel.id === row.id;
        },

        _sortLibraryRows(rows) {
            const kindRank = { ue: 0, ur: 1, se: 2, sr: 3, d: 4 };
            const mode = this.librarySortMode;
            const nameKey = (r) => String(this.libraryRowLabel(r) || "").toLowerCase();
            return rows.slice().sort((a, b) => {
                if (mode !== "name") {
                    const ka = kindRank[this.libraryKind(a)] ?? 9;
                    const kb = kindRank[this.libraryKind(b)] ?? 9;
                    if (ka !== kb) return ka - kb;
                }
                return nameKey(a).localeCompare(nameKey(b), undefined, { sensitivity: "base" });
            });
        },

        _primaryTriggerEventId(triggerOrRule) {
            // B19: full rule with branches — first event Compare.
            if (triggerOrRule && Array.isArray(triggerOrRule.branches)) {
                for (const br of triggerOrRule.branches) {
                    let found = "";
                    blockyForEachConditionLeaf((br && br.conditions) || [], (c) => {
                        if (!found && c.type === "event" && c.event) found = String(c.event);
                    });
                    if (found) return found;
                }
                return "";
            }
            let t = triggerOrRule;
            if (Array.isArray(t) && t.length === 1) t = t[0];
            if (Array.isArray(t)) {
                const first = (t || []).find((x) => x && x.event && !x.entity_id);
                return first ? String(first.event) : "";
            }
            if (t && t.event && !t.entity_id) return String(t.event);
            return "";
        },

        /** Wake event id from a stored automation row (branches or legacy trigger). */
        _primaryEventIdFromRule(rule) {
            if (!rule || typeof rule !== "object") return "";
            if (Array.isArray(rule.branches)) return this._primaryTriggerEventId(rule);
            return this._primaryTriggerEventId(rule.trigger);
        },

        /** Read-only Library wake summary from Compares (B19). */
        _wakeSummaryFromRule(rule) {
            if (!rule || typeof rule !== "object") return "";
            const parts = [];
            const seen = new Set();
            const push = (s) => {
                const k = String(s || "");
                if (!k || seen.has(k)) return;
                seen.add(k);
                parts.push(k);
            };
            if (Array.isArray(rule.branches)) {
                for (const br of rule.branches) {
                    for (const c of (br && br.conditions) || []) {
                        if (!c) continue;
                        if (c.type === "device_state" && c.entity_id) push(c.entity_id);
                        if (c.type === "event" && c.event) {
                            push(this._catalogEventName(c.event) || c.event);
                        }
                    }
                }
            } else if (rule.trigger) {
                const t = Array.isArray(rule.trigger) ? rule.trigger : [rule.trigger];
                t.forEach((x) => {
                    if (x && x.entity_id) push(x.entity_id);
                    if (x && x.event) push(this._catalogEventName(x.event) || x.event);
                });
            }
            return parts.join(", ");
        },

        /** Catalog origin for an event UUID (`user` | `system` | ""). */
        _eventOrigin(eventId) {
            const id = String(eventId || "");
            if (!id) return "";
            const row = (BlockyRT.catalogEvents || []).find((r) => r && String(r.id) === id);
            return row ? String(row.origin || "user") : "";
        },

        /** Catalog display name for an event UUID (empty if unknown). */
        _catalogEventName(eventId) {
            const id = String(eventId || "");
            if (!id) return "";
            const row = (BlockyRT.catalogEvents || []).find((r) => r && String(r.id) === id);
            return row && row.name ? String(row.name) : "";
        },

        /**
         * SR invariant (FE): force payload.name = companion SE catalog name.
         * Backend also overwrites on POST/PUT so YAML cannot drift.
         */
        _bindSrNameToSeCatalog(payload) {
            if (!payload || typeof payload !== "object") return payload;
            const evId = this._primaryEventIdFromRule(payload);
            if (!evId || this._eventOrigin(evId) !== "system") return payload;
            const catName = this._catalogEventName(evId);
            if (catName) {
                payload.name = catName;
                this.editor.name = catName;
            }
            return payload;
        },

        /**
         * Display name for a rule in usages / blocked-delete messages.
         * SR: companion SE catalog name (never drifted YAML free-text).
         * UR: rule.name / listName.
         */
        _ruleDisplayName(rule) {
            if (!rule) return "(unnamed)";
            const evId = this._primaryEventIdFromRule(rule);
            if (evId && this._eventOrigin(evId) === "system") {
                return (
                    this._catalogEventName(evId)
                    || rule.listName
                    || rule.name
                    || rule.id
                    || "(unnamed)"
                );
            }
            return String(rule.listName || rule.name || rule.id || "(unnamed)");
        },

        /** Rule names whose trigger listens to this event id (When user/system event). */
        _triggerRefNamesForEvent(eventId) {
            const id = String(eventId || "");
            if (!id) return [];
            const names = [];
            for (const rule of this.automations || []) {
                if (!rule) continue;
                if (this._primaryEventIdFromRule(rule) === id) {
                    names.push(this._ruleDisplayName(rule));
                }
            }
            return names;
        },

        /** Rule names that fire this event as an action (Fire user/system event). */
        _fireRefNamesForEvent(eventId) {
            const id = String(eventId || "");
            if (!id) return [];
            const names = [];
            for (const rule of this.automations || []) {
                if (!rule) continue;
                let hit = false;
                for (const c of rule.cases || []) {
                    for (const a of c.actions || []) {
                        if (a && a.event && !a.entity_id && String(a.event) === id) {
                            hit = true;
                            break;
                        }
                    }
                    if (hit) break;
                }
                if (hit) names.push(this._ruleDisplayName(rule));
            }
            return names;
        },

        /**
         * Unique rule names that listen to OR fire this event.
         * Disable of an E is blocked when either side is non-empty: a listening U
         * must not keep a disabled catalog target, and Fire-user-event actions must
         * not target a disabled E (same product rule as backend `rule_refs_to_event`).
         */
        _usageRuleNamesForEvent(eventId) {
            const id = String(eventId || "");
            if (!id) return [];
            const seen = new Set();
            const out = [];
            for (const nm of [
                ...this._triggerRefNamesForEvent(id),
                ...this._fireRefNamesForEvent(id)
            ]) {
                if (seen.has(nm)) continue;
                seen.add(nm);
                out.push(nm);
            }
            return out;
        },

        /** Set of system event UUIDs that already have a listening rule. */
        _systemEventsWithListeners() {
            const out = new Set();
            for (const rule of this.automations || []) {
                if (!rule) continue;
                const evId = this._primaryEventIdFromRule(rule);
                if (evId && this._eventOrigin(evId) === "system") out.add(evId);
            }
            return out;
        },

        onExplorerFlagChanged() {
            // Invariant: explorer OFF while confirm ON → force confirm OFF.
            if (!this.editor.eventShowOnDashboard && this.editor.eventRequireConfirmation) {
                this.editor.eventRequireConfirmation = false;
            }
            this.markEditorDirty();
        },

        showEventUsagesModal() {
            const id = this.usagesEventId;
            // UE form: listeners + fire-refs. UR disable-blocked: fire-refs of trigger only.
            if (this.selectedRule && this.selectedRule.isEventRow) {
                this.fireRefRuleNames = this._usageRuleNamesForEvent(id);
            } else {
                this.fireRefRuleNames = this._fireRefNamesForEvent(id);
            }
            const dlg = document.getElementById("event_usages_modal");
            if (dlg) dlg.showModal();
        },

        closeEventUsagesModal() {
            document.getElementById("event_usages_modal")?.close();
        },

        deviceTypeLabel(type, origin, idx) {
            const t = String(type || "").toLowerCase();
            let o = String(origin || "").toLowerCase();
            if ((t === "speaker" || t === "media_player") && !o) {
                const n = Number(idx);
                if (n >= 60000 && n < 61000) o = "sonos";
                else if (n >= 61000 && n < 62000) o = "onkyo";
            }
            if (t === "speaker" || t === "media_player") {
                if (o === "onkyo") return "Onkyo";
                if (o === "sonos") return "Sonos";
                return "speaker";
            }
            const map = {
                blinds: "shutters", shutter: "shutters", switch: "switch", light: "light", hue: "light",
                motion: "motion"
            };
            return map[t] || t || "device";
        },

        entityDisplayLabel(opt) {
            // B9A: host/system gauges get a friendly override name over the raw device name.
            const name = (opt && BLOCKY_HOST_GAUGE_LABELS[opt.eid]) || (opt && opt.name);
            if (opt && opt.typeLabel) return `${name} · ${opt.typeLabel}`;
            return `${name} · ${this.deviceTypeLabel(opt.type, opt.origin, opt.idx)}`;
        },

        /** Alpine-friendly wrapper for catalog UUID → name. */
        eventLabel(eventId) {
            return blockyEventLabel(eventId);
        },

        markEditorDirty() {
            if (BlockyRT.loading || Date.now() < (this.suppressDirtyUntil || 0)) return;
            if (!this.selectedRule) return;
            this.editorDirty = true;
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
        },

        get hasBlocklySelection() {
            void this.blocklyUiTick;
            const ws = blockyWs();
            if (!ws) return false;
            if (this._blocklySelectedId && ws.getBlockById(this._blocklySelectedId)) return true;
            return !!this._captureSelectedBlock();
        },

        _captureSelectedBlock() {
            if (!window.Blockly || !blockyWs()) return null;
            let sel = null;
            try {
                if (typeof Blockly.getSelected === "function") sel = Blockly.getSelected();
                else if (Blockly.common && typeof Blockly.common.getSelected === "function") {
                    sel = Blockly.common.getSelected();
                }
            } catch (e) { /* ignore */ }
            if (!sel || sel.isInFlyout || sel.workspace !== blockyWs()) return null;
            this._blocklySelectedId = sel.id;
            return sel;
        },

        /** mousedown.prevent on Delete — capture id before Blockly clears selection on button focus. */
        onDeletePointerDown(ev) {
            if (ev) ev.preventDefault();
            this._captureSelectedBlock();
            this._deleteTargetId = this._blocklySelectedId || null;
        },

        deleteSelectedBlock() {
            const ws = blockyWs();
            if (!ws) return;
            const id = this._deleteTargetId || this._blocklySelectedId;
            this._deleteTargetId = null;
            let sel = id ? ws.getBlockById(id) : null;
            if (!sel) sel = this._captureSelectedBlock();
            if (!sel || sel.isInFlyout) return;
            try {
                sel.dispose(true);
            } catch (e) {
                try { sel.dispose(false); } catch (e2) { /* ignore */ }
            }
            this._blocklySelectedId = null;
            this.markEditorDirty();
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
        },

        applyBlockyHueColor() {
            blockyApplyHueColorModal();
        },

        closeBlockyHueColor() {
            blockyCloseHueColorModal();
        },

        markEditorClean() {
            this.editorDirty = false;
            this.suppressDirtyUntil = Date.now() + 400;
        },

        requestLeave(action) {
            if (!this.editorDirty) {
                this._finishLeave(action);
                return;
            }
            this.pendingNav = action;
            const dlg = document.getElementById("unsaved_rule_modal");
            if (dlg) dlg.showModal();
        },

        _finishLeave(action) {
            const leavingPage = !!(action && (action.type === "href" || action.type === "logout"));
            if (leavingPage && this.rulesPendingCount > 0) {
                this.pendingNav = action;
                document.getElementById("pending_activation_modal")?.showModal();
                return;
            }
            this.pendingNav = null;
            this.runLeaveAction(action);
        },

        runLeaveAction(action) {
            if (!action) return;
            if (action.type === "select") this._doSelectRule(action.rule);
            else if (action.type === "new") this._doNewRule();
            else if (action.type === "newUserEvent") this._doNewUserEvent();
            else if (action.type === "newFromSe") this._doNewRuleFromEvent(action.eventId, "system");
            else if (action.type === "newFromUe") this._doNewRuleFromEvent(action.eventId, "user");
            else if (action.type === "href" && action.url) window.location.href = action.url;
            else if (action.type === "reload") this.loadV2IntoBlockly();
            else if (action.type === "logout") this.logout();
        },

        cancelUnsavedLeave() {
            this.pendingNav = null;
            document.getElementById("unsaved_rule_modal")?.close();
        },

        discardUnsavedLeave() {
            const action = this.pendingNav;
            this.pendingNav = null;
            this.markEditorClean();
            document.getElementById("unsaved_rule_modal")?.close();
            this._finishLeave(action);
        },

        async saveUnsavedLeave() {
            await this.saveRule();
            if (this.errorMessage) return;
            const action = this.pendingNav;
            document.getElementById("unsaved_rule_modal")?.close();
            this._finishLeave(action);
        },

        continueEditingLeave() {
            this.pendingNav = null;
            document.getElementById("pending_activation_modal")?.close();
        },

        async activateNowLeave() {
            document.getElementById("pending_activation_modal")?.close();
            const ok = await this.activatePendingRules();
            if (!ok) return;
            const action = this.pendingNav;
            this.pendingNav = null;
            this.runLeaveAction(action);
        },

        _applyRulesActivationPending(raw) {
            const p = raw && typeof raw === "object" ? raw : {};
            this.rulesActivationPending = {
                count: Number(p.count) || 0,
                rule_ids: Array.isArray(p.rule_ids) ? p.rule_ids.map(String) : [],
                event_ids: Array.isArray(p.event_ids) ? p.event_ids.map(String) : [],
                needs_automations: !!p.needs_automations,
                needs_events: !!p.needs_events
            };
        },

        async ensureAutoOffConfig() {
            if (this.autoOffConfig) return this.autoOffConfig;
            this._autoOffLoadFailed = false;
            try {
                const stateRes = await fetch("/api/state", { headers: this.getAuthHeaders() });
                if (stateRes.ok) {
                    const state = await stateRes.json();
                    if (this._applyAutoOffFromState(state.system)) {
                        return this.autoOffConfig;
                    }
                }
                const res = await fetch("/api/auto-off-timer", { headers: this.getAuthHeaders() });
                if (!res.ok) throw new Error(`Failed /api/auto-off-timer (${res.status})`);
                this._applyAutoOffConfigPayload(await res.json());
            } catch (e) {
                this.autoOffConfig = null;
                this.autoOffByEid = {};
                this._autoOffLoadFailed = true;
            }
            return this.autoOffConfig;
        },

        _reloadAlertSaysActivationFailed(msgs) {
            if (!Array.isArray(msgs)) return "";
            for (const msg of msgs) {
                const text = msg && msg.message ? String(msg.message) : "";
                if (window.WanOSReloadAlerts && window.WanOSReloadAlerts.isFailed(text)) {
                    if (text.startsWith("Rule activation failed:")) return text.replace(/^Rule activation failed:\s*/, "");
                    if (text.startsWith("Events catalog reload failed:")) return text.replace(/^Events catalog reload failed:\s*/, "");
                }
            }
            return "";
        },

        async _waitForPendingActivationClear() {
            const deadline = Date.now() + 120000;
            while (Date.now() < deadline) {
                await new Promise((r) => setTimeout(r, 400));
                try {
                    const res = await fetch("/api/state", { headers: this.getAuthHeaders() });
                    if (!res.ok) continue;
                    const state = await res.json();
                    const sys = (state && state.system) || {};
                    this._applyRulesActivationPending(sys.rules_activation_pending);
                    if (window.WanOSReloadAlerts) {
                        this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(
                            sys.system_alert_msgs || []
                        );
                    }
                    const failReason = this._reloadAlertSaysActivationFailed(sys.system_alert_msgs);
                    if (failReason) throw new Error(failReason);
                    if (this.rulesPendingCount <= 0) return true;
                } catch (e) {
                    if (e && e.message) throw e;
                }
            }
            throw new Error("Timed out waiting for activation");
        },

        async activatePendingRules() {
            if (this.activateBusy || this.rulesPendingCount <= 0) return false;
            this.activateBusy = true;
            this.errorMessage = "";
            try {
                const res = await fetch("/api/automations/activate", {
                    method: "POST",
                    headers: this.getAuthHeaders()
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `Activate failed (${res.status})`);
                if (body.rules_activation_pending) {
                    this._applyRulesActivationPending(body.rules_activation_pending);
                }
                await this._waitForPendingActivationClear();
                await this._refreshAfterActivation();
                this.infoMessage = "Changed rules are now active.";
                return true;
            } catch (e) {
                this.errorMessage = `Activation failed: ${e.message || e}. Changes are still saved but not active. Try again.`;
                return false;
            } finally {
                this.activateBusy = false;
            }
        },

        /** Patch lists after activation — no full cold refresh overlay. */
        async _refreshAfterActivation() {
            try {
                const [stateRes, rulesRes, eventsRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/automations", { headers: this.getAuthHeaders() }),
                    fetch("/api/events", { headers: this.getAuthHeaders() })
                ]);
                if (stateRes.ok) {
                    const state = await stateRes.json();
                    this._applyRulesActivationPending((state.system || {}).rules_activation_pending);
                    this.liveDevices = state.devices || {};
                    this.rebuildEntityOptions(state.device_metadata || {}, this.automations);
                }
                if (rulesRes.ok) {
                    const rulesPayload = await rulesRes.json();
                    this.automations = (rulesPayload.automations || []).filter((r) => r && typeof r === "object");
                }
                if (eventsRes.ok) {
                    const eventsPayload = await eventsRes.json();
                    BlockyRT.catalogEvents = Array.isArray(eventsPayload.events) ? eventsPayload.events : [];
                }
                this.rebuildLibraryRows();
                await this.fetchFireStatus();
            } catch (e) { /* non-fatal */ }
        },

        /** Fast path after user-event save/delete. */
        async _refreshAfterEventSave(savedEvent) {
            if (savedEvent && savedEvent.id) {
                const id = String(savedEvent.id);
                const ix = (BlockyRT.catalogEvents || []).findIndex((r) => r && String(r.id) === id);
                if (ix >= 0) BlockyRT.catalogEvents[ix] = savedEvent;
                else BlockyRT.catalogEvents.push(savedEvent);
            }
            try {
                const [stateRes, eventsRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/events", { headers: this.getAuthHeaders() })
                ]);
                if (eventsRes.ok) {
                    const eventsPayload = await eventsRes.json();
                    BlockyRT.catalogEvents = Array.isArray(eventsPayload.events) ? eventsPayload.events : [];
                }
                if (stateRes.ok) {
                    const state = await stateRes.json();
                    this._applyRulesActivationPending((state.system || {}).rules_activation_pending);
                    this.liveDevices = state.devices || {};
                }
                this.rebuildLibraryRows();
            } catch (e) { /* ignore */ }
        },

        /** Fast path after rule save/delete — YAML written, engine not reloaded yet. */
        async _refreshAfterRuleSave(savedRow) {
            if (savedRow && savedRow.id) {
                const id = String(savedRow.id);
                const ix = this.automations.findIndex((r) => r && String(r.id) === id);
                if (ix >= 0) this.automations[ix] = savedRow;
                else this.automations.push(savedRow);
            }
            this.rebuildLibraryRows();
            try {
                const res = await fetch("/api/state", { headers: this.getAuthHeaders() });
                if (!res.ok) return;
                const state = await res.json();
                this._applyRulesActivationPending((state.system || {}).rules_activation_pending);
                this.liveDevices = state.devices || {};
                this.rebuildEntityOptions(state.device_metadata || {}, this.automations);
            } catch (e) { /* ignore */ }
            if (this.autoOffConfig) {
                this._rebuildAutoOffIndex();
            }
        },

        navAway(ev, url) {
            if (!this.editorDirty && this.rulesPendingCount <= 0) return;
            ev.preventDefault();
            this.requestLeave({ type: "href", url });
        },

        blocklyHostReady() {
            const host = document.getElementById("blocklyWorkspace");
            if (!host) return null;
            if ((host.offsetWidth || 0) < 50 || (host.offsetHeight || 0) < 50) return null;
            return host;
        },

        resizeBlockly() {
            // Debounced settle path — see blockyScheduleWorkspaceResize.
            blockyScheduleWorkspaceResize();
        },

        observeBlocklyHost(host) {
            if (BlockyRT.resizeObserver) BlockyRT.resizeObserver.disconnect();
            if (typeof ResizeObserver !== "undefined") {
                BlockyRT.resizeObserver = new ResizeObserver(() => blockyScheduleWorkspaceResize());
                BlockyRT.resizeObserver.observe(host);
            }
            if (!BlockyRT.windowResize) {
                BlockyRT.windowResize = () => blockyScheduleWorkspaceResize();
                window.addEventListener("resize", BlockyRT.windowResize);
            }
        },

        scrollBlocklyToTopLeft() {
            const ws = blockyWs();
            if (!ws) return;
            try {
                const m = ws.getMetrics();
                if (m) ws.scroll(-m.contentLeft + 16, -m.contentTop + 16);
            } catch (e) { /* ignore */ }
        },

        toggleBlocklyFullscreen() {
            this.blocklyFullscreen = !this.blocklyFullscreen;
            blockyScheduleWorkspaceResize();
        },

        getAuthHeaders() {
            const token = localStorage.getItem("wanos_jwt") || "";
            return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
        },

        isAdminToken(token) {
            try {
                return JSON.parse(atob(token.split(".")[1])).role === "admin";
            } catch (e) {
                return false;
            }
        },

        async logout() {
            try {
                await fetch("/api/auth/logout", { method: "POST", headers: this.getAuthHeaders() });
            } catch (e) { /* ignore */ }
            localStorage.removeItem("wanos_jwt");
            window.location.href = "/login.html";
        },

        isHardDeniedEntityId(eid) {
            if (!eid) return false;
            const v = String(eid);
            return (this.hardDenyEntityIds || []).includes(v);
        },

        rebuildEntityOptions(deviceMetadata, _automations) {
            const opts = [];
            for (const [idx, meta] of Object.entries(deviceMetadata || {})) {
                if (!meta || typeof meta !== "object") continue;
                const eid = meta.entity_id ? String(meta.entity_id) : "";
                if (!eid || this.isHardDeniedEntityId(eid)) continue;
                // B9A (G2): 1m/5m load gauges stay published but never enter the Blockly
                // catalog. Already-open rules keep them via sticky (_stickyEntityIdsForRole).
                if (BLOCKY_HOST_GAUGE_HIDDEN.has(eid)) continue;
                const type = meta.type ? String(meta.type) : "unknown";
                if (type === "scene") continue;
                const labelName = meta.name ? String(meta.name) : eid;
                let origin = meta.origin ? String(meta.origin) : "";
                const idxNum = Number(idx);
                if ((type === "speaker" || type === "media_player") && !origin) {
                    if (idxNum >= 60000 && idxNum < 61000) origin = "sonos";
                    else if (idxNum >= 61000 && idxNum < 62000) origin = "onkyo";
                }
                const typeLabel = this.deviceTypeLabel(type, origin, idxNum);
                opts.push({
                    eid,
                    idx: idxNum,
                    name: labelName,
                    label: labelName,
                    type,
                    origin,
                    resolvedProductType: meta.resolved_product_type
                        || (origin === "hue" ? "light"
                            : (type === "switch" || type === "light" ? "switch" : null)),
                    typeLabel,
                    max_volume: meta.max_volume != null ? Number(meta.max_volume) : null,
                    // Honor Explorer soft-hide; exclusive Hidden toggle filters via visibleEntityOptions.
                    // Currently selected eids stay sticky in blocklyEntityDropdownOptions until cleared.
                    softHidden: Boolean(meta.hidden)
                });
            }
            opts.sort((a, b) => a.name.localeCompare(b.name));
            this.entityOptions = opts;
        },

        firstEntityId(role = "trigger", preferTypes = null) {
            const pickerRole = role === "trigger" ? "condition" : role;
            const opts = this.blocklyEntityDropdownOptions({ role: pickerRole });
            const prefRole = role === "action" ? "action" : "condition";
            const pref = blockyPreferredDeviceDefaults(prefRole);
            if (pref.entity_id && opts.some((o) => o[1] === pref.entity_id)) {
                return pref.entity_id;
            }
            const types = preferTypes
                ? (Array.isArray(preferTypes) ? preferTypes : [preferTypes])
                : null;
            if (types && types.length) {
                const hit = opts.find((o) => {
                    if (!o[1]) return false;
                    const t = blockyEntityTypeOf(o[1]);
                    return types.includes(t);
                });
                if (hit) return hit[1];
            }
            const first = opts.find((o) => o[1]);
            return first ? first[1] : "";
        },

        /** Prefer two different lights for new-rule trigger + action defaults. */
        defaultLightPair() {
            const trigOpts = this.blocklyEntityDropdownOptions({ role: "trigger" })
                .filter((o) => o[1] && (blockyEntityTypeOf(o[1]) === "light" || blockyEntityTypeOf(o[1]) === "hue"))
                .map((o) => o[1]);
            const actOpts = this.blocklyEntityDropdownOptions({ role: "action" })
                .filter((o) => o[1] && (blockyEntityTypeOf(o[1]) === "light" || blockyEntityTypeOf(o[1]) === "hue"))
                .map((o) => o[1]);
            const triggerEid = trigOpts[0]
                || this.firstEntityId("trigger", ["light", "hue"])
                || this.firstEntityId("trigger");
            const actionEid = actOpts.find((e) => e !== triggerEid)
                || actOpts[0]
                || this.firstEntityId("action", ["light", "hue"])
                || this.firstEntityId("action");
            return { triggerEid, actionEid };
        },

        /**
         * role: "trigger" | "condition" | "action"
         * Motion OK as trigger or condition (B19 Compare wake); actions = actuators only.
         * Sticky: eids still selected for this role stay in the menu on the wrong Hidden
         * side (can clear, cannot re-pick once gone). Hard deny never sticky.
         * HIDDEN is exclusive (ON = soft-hidden catalog; OFF = non-hidden) + sticky current.
         */
        blocklyEntityDropdownOptions(optsIn) {
            const role = (optsIn && optsIn.role) || "action";
            const base = this.visibleEntityOptions.filter((o) => blockyEntityAllowedForRole(o, role));
            const opts = base.map((o) => [this.entityDisplayLabel(o), o.eid]);
            const seen = new Set(opts.map((o) => o[1]));
            const add = (eid) => {
                if (!eid || seen.has(eid) || this.isHardDeniedEntityId(eid)) return;
                // Keep currently selected eids in the menu (wrong Hidden side / missing meta)
                // so Blockly does not snap the field to the first catalog entry.
                seen.add(eid);
                const meta = (this.entityOptions || []).find((o) => o.eid === eid);
                if (meta) {
                    opts.push([this.entityDisplayLabel(meta), eid]);
                } else {
                    opts.push([`${eid} · (missing metadata)`, eid]);
                }
            };
            this._stickyEntityIdsForRole(role).forEach(add);
            return opts.length ? opts : [["(no entities)", ""]];
        },

        /**
         * Live workspace wins once load is finished (deselection drops sticky).
         * During load, always use full open-rule eids — a partial workspace list
         * (blocks created one-by-one) would omit later action eids and FieldDropdown
         * would snap them to options[0] (seen as identical wrong labels when HIDDEN ON).
         * Role-scoped — action sticky does not leak into When-device.
         */
        _stickyEntityIdsForRole(role) {
            let ruleIds = [];
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                ruleIds = this._ruleEntityIdsForRole(rule, role);
            } catch (e) { /* ignore */ }
            // Load path: ruleJson is complete; workspace is still being filled.
            if (BlockyRT.loading) return ruleIds;
            const fromWs = this._workspaceEntityIdsForRole(role);
            if (fromWs === null) return ruleIds;
            if (fromWs.length > 0) return fromWs;
            return ruleIds;
        },

        /** null = workspace not ready (caller falls back to ruleJson). */
        _workspaceEntityIdsForRole(role) {
            const ws = blockyWs();
            if (!ws) return null;
            const out = [];
            const push = (eid) => {
                if (eid) out.push(String(eid));
            };
            const blocks = ws.getAllBlocks(false);
            for (const b of blocks) {
                if (b.isInFlyout) continue;
                const t = b.type;
                if (role === "trigger") {
                    if (t === "b_trig_device" || t === "b_trig_device_edge") {
                        push(b.getFieldValue("ENTITY"));
                    }
                } else if (role === "condition") {
                    if (t === "b_condition_device") push(b.getFieldValue("ENTITY"));
                } else if (role === "action") {
                    if (t === "b_action_device") push(b.getFieldValue("ENTITY"));
                }
            }
            return out;
        },

        /** Only eids that belong in this picker role (prevents action→trigger leak). */
        _ruleEntityIdsForRole(rule, role) {
            const out = [];
            const push = (eid) => {
                if (eid) out.push(String(eid));
            };
            // B19: sticky from branches. Legacy: trigger + cases.
            if (Array.isArray(rule.branches)) {
                if (role === "trigger") {
                    // No authoring trigger; wake devices live as condition Compares.
                    return out;
                }
                rule.branches.forEach((br) => {
                    if (!br) return;
                    if (role === "condition") {
                        blockyForEachConditionLeaf(br.conditions, (cond) => {
                            if (cond && cond.type !== "event" && cond.type !== "time_of_day") {
                                push(cond.entity_id);
                            }
                        });
                    } else if (role === "action") {
                        (br.actions || []).forEach((a) => {
                            if (a && a.entity_id) push(a.entity_id);
                        });
                    }
                });
                return out;
            }
            if (role === "trigger") {
                const t = rule.trigger;
                if (Array.isArray(t)) t.forEach((x) => x && push(x.entity_id));
                else if (t) push(t.entity_id);
                return out;
            }
            const cases = rule.cases || [];
            if (role === "condition") {
                cases.forEach((c) => (c.conditions || []).forEach((cond) => push(cond && cond.entity_id)));
                return out;
            }
            cases.forEach((c) => (c.actions || []).forEach((a) => push(a && a.entity_id)));
            return out;
        },

        /**
         * B10E event pickers — filter by origin (user|system) and role (trigger|fire).
         * Trigger system: unused SEs only (sticky keeps current when editing SR).
         * Fire system: listeners OR FIRE_ALWAYS only.
         * Sticky: events already on the open rule stay listed (round-trip safe).
         */
        blocklyEventDropdownOptions(optsIn) {
            const originWant = (optsIn && optsIn.origin) || "";
            const role = (optsIn && optsIn.role) || "trigger";
            const catalog = BlockyRT.catalogEvents || [];
            const listeners = this._systemEventsWithListeners();
            let pickable = catalog.filter((r) => {
                if (!r || !r.id) return false;
                if (BLOCKY_NON_PICKABLE_EVENT_IDS.has(String(r.id))) return false;
                const origin = String(r.origin || "user");
                if (originWant && origin !== originWant) return false;
                if (origin === "system") {
                    const id = String(r.id);
                    if (role === "fire") {
                        // Unused system not fireable except Sauna/IR ON/OFF always.
                        return BLOCKY_FIRE_ALWAYS_SYSTEM_IDS.has(id) || listeners.has(id);
                    }
                    // New SR: only unused SEs; editing keeps current via sticky below.
                    return !listeners.has(id);
                }
                // User: enabled only (disabled stay sticky if already on rule).
                return r.enabled !== false;
            });
            const nameKey = (r) => String(r.name || r.id || "");
            pickable.sort((a, b) => nameKey(a).localeCompare(nameKey(b), undefined, { sensitivity: "base" }));
            const opts = pickable.map((r) => [blockyEventLabel(r.id), String(r.id)]);
            const seen = new Set(opts.map((o) => o[1]));
            const addSticky = (evId) => {
                const id = String(evId || "");
                if (!id || seen.has(id)) return;
                // Sticky must still match origin filter when set.
                if (originWant) {
                    const o = this._eventOrigin(id);
                    if (o && o !== originWant) return;
                }
                seen.add(id);
                opts.push([blockyEventLabel(id), id]);
            };
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                // B19: sticky from branches (event Compare / Fire). Legacy: trigger + cases.
                if (Array.isArray(rule.branches)) {
                    rule.branches.forEach((br) => {
                        if (!br) return;
                        if (role === "trigger") {
                            blockyForEachConditionLeaf(br.conditions, (c) => {
                                if (c && c.type === "event" && c.event) addSticky(c.event);
                            });
                        } else {
                            (br.actions || []).forEach((a) => {
                                if (a && a.event && !a.entity_id) addSticky(a.event);
                            });
                        }
                    });
                } else {
                    const t = rule.trigger;
                    if (role === "trigger") {
                        if (Array.isArray(t)) t.forEach((x) => x && addSticky(x.event));
                        else if (t) addSticky(t.event);
                    } else {
                        (rule.cases || []).forEach((c) => {
                            (c.actions || []).forEach((a) => {
                                if (a && a.event && !a.entity_id) addSticky(a.event);
                            });
                        });
                    }
                }
            } catch (e) { /* ignore */ }
            // Also sticky live canvas picks during edit.
            try {
                const ws = blockyWs();
                if (ws && !BlockyRT.loading) {
                    ws.getAllBlocks(false).forEach((b) => {
                        if (b.isInFlyout) return;
                        if (role === "trigger") {
                            // B19 wake = event Compare; keep legacy When/OR-edge sticky too.
                            if (BLOCKY_EVENT_TRIGGERS.has(b.type)
                                || BLOCKY_EVENT_EDGES.has(b.type)
                                || BLOCKY_EVENT_COMPARES.has(b.type)) {
                                addSticky(b.getFieldValue("EVENT"));
                            }
                        } else if (BLOCKY_EVENT_ACTIONS.has(b.type)) {
                            addSticky(b.getFieldValue("EVENT"));
                        }
                    });
                }
            } catch (e) { /* ignore */ }
            return opts.length ? opts : [["(no events)", ""]];
        },

        ensureBlocklyReady() {
            if (!window.Blockly) throw new Error("Blockly library not loaded.");
            BlockyRT.app = this;
            const host = this.blocklyHostReady();
            if (!host) return false;
            if (BlockyRT.ready && BlockyRT.ws && !host.querySelector(".injectionDiv")) {
                BlockyRT.ws = null;
                BlockyRT.ready = false;
                BlockyRT.schemaInjected = null;
            }
            if (BlockyRT.ready && BlockyRT.ws && BlockyRT.schemaInjected === this.blocklySchemaVersion) {
                this.resizeBlockly();
                return true;
            }
            if (BlockyRT.ready) blockyDestroyWorkspace();
            defineBlockyBlocks(Blockly, {
                entityTrigger: () => (BlockyRT.app || this).blocklyEntityDropdownOptions({ role: "trigger" }),
                entityCondition: () => (BlockyRT.app || this).blocklyEntityDropdownOptions({ role: "condition" }),
                entityAction: () => (BlockyRT.app || this).blocklyEntityDropdownOptions({ role: "action" }),
                eventUserTrigger: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "user", role: "trigger"
                }),
                eventSystemTrigger: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "system", role: "trigger"
                }),
                eventUserFire: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "user", role: "fire"
                }),
                eventSystemFire: () => (BlockyRT.app || this).blocklyEventDropdownOptions({
                    origin: "system", role: "fire"
                })
            });
            BlockyRT.ws = Blockly.inject(host, {
                toolbox: blockyToolboxDefinition(new Set()),
                trashcan: false,
                scrollbars: true,
                move: { scrollbars: true, drag: true, wheel: true },
                zoom: { controls: true, wheel: false, startScale: 1.0 }
            });
            // After inject: dropdown chrome needs DropDownDiv on the page.
            blockyConfigureDropdownChrome(Blockly);
            BlockyRT.ws.addChangeListener(blockyOnChange);
            BlockyRT.ready = true;
            BlockyRT.schemaInjected = this.blocklySchemaVersion;
            this.observeBlocklyHost(host);
            blockyScheduleWorkspaceResize();
            return true;
        },

        scheduleBlocklyLoad(attempt = 0) {
            if (!this.selectedRule || !this.showBlocklyWorkspace) return;
            requestAnimationFrame(() => {
                if (!this.selectedRule || !this.showBlocklyWorkspace) return;
                if (!this.blocklyHostReady()) {
                    if (attempt < 40) this.scheduleBlocklyLoad(attempt + 1);
                    return;
                }
                try {
                    if (!this.ensureBlocklyReady()) {
                        if (attempt < 40) this.scheduleBlocklyLoad(attempt + 1);
                        return;
                    }
                    this.loadV2IntoBlockly();
                    this.resizeBlockly();
                } catch (e) {
                    this.errorMessage = String(e && e.message ? e.message : e);
                }
            });
        },

        _conditionBlocks(list) {
            return (list || []).map((c, idx) => {
                if (!c || typeof c !== "object") {
                    this._noteSilentLoss(`Condition #${idx + 1}: empty/invalid — cannot load safely`);
                    return blockyMkBlock("b_condition_time", { TOD: "dark" });
                }
                if (c.type === "time_of_day") {
                    const blk = blockyMkBlock("b_condition_time", { TOD: c.is || "dark" });
                    blockyAttachOpaque(
                        blk,
                        blockyOpaqueFromSource(c, BLOCKY_CONDITION_LEGAL_KEYS, BLOCKY_CONDITION_UI_KEYS)
                    );
                    return blk;
                }
                if (c.type && !BLOCKY_SUPPORTED_CONDITION_TYPES.has(c.type)) {
                    this._noteSilentLoss(
                        `Condition type "${c.type}" has no Blockly block — Save blocked (silent-loss B)`
                    );
                }
                if (c.type === "device_state" || c.entity_id) {
                    const eid = c.entity_id || this.firstEntityId("condition");
                    const blk = blockyMkBlock("b_condition_device", { ENTITY: eid });
                    blockyApplyConditionRich(blk, c);
                    return blk;
                }
                this._noteSilentLoss(
                    `Condition #${idx + 1}: unsupported shape — Save blocked (silent-loss B)`
                );
                return blockyMkBlock("b_condition_time", { TOD: "dark" });
            });
        },

        _actionBlocks(list) {
            return (list || []).map((a, idx) => {
                if (!a || typeof a !== "object") {
                    this._noteSilentLoss(`Action #${idx + 1}: empty/invalid — cannot load safely`);
                    return blockyMkBlock("b_action_device", {
                        ENTITY: this.firstEntityId("action"),
                        STATE: "ON"
                    });
                }
                if (a.event && !a.entity_id) {
                    const origin = this._eventOrigin(a.event);
                    const type = origin === "system" ? "b_action_event_sys" : "b_action_event";
                    const blk = blockyMkBlock(type, { EVENT: a.event });
                    blockyAttachOpaque(
                        blk,
                        blockyOpaqueFromSource(a, BLOCKY_ACTION_LEGAL_KEYS, BLOCKY_ACTION_UI_KEYS)
                    );
                    return blk;
                }
                if (a.entity_id) {
                    const type = blockyEntityTypeOf(a.entity_id);
                    const isBlinds = type === "blinds" || type === "shutter";
                    const blk = blockyMkBlock("b_action_device", {
                        ENTITY: a.entity_id || this.firstEntityId("action"),
                        STATE: isBlinds ? blockyBlindsUiStateFromStored(a.state) : (a.state || "ON")
                    });
                    blockyApplyActionRich(blk, a);
                    return blk;
                }
                // Neither entity nor event — cannot attach a faithful block (e.g. scene-only).
                this._noteSilentLoss(
                    `Action #${idx + 1}: no entity_id/event — Save blocked (silent-loss B)`
                );
                return blockyMkBlock("b_action_device", {
                    ENTITY: this.firstEntityId("action"),
                    STATE: "ON"
                });
            });
        },

        loadV2IntoBlockly() {
            if (!this.ensureBlocklyReady()) return;
            blockyCancelUniqueness();
            BlockyRT.loading = true;
            BlockyRT.suppressHueWheel = true;
            this.silentLossReasons = [];
            const Events = Blockly.Events;
            Events.disable();
            try {
                const ws = blockyWs();
                ws.clear();

                let rule;
                try {
                    rule = JSON.parse(this.editor.ruleJson || "{}");
                } catch (e) {
                    rule = { branches: [{ when: "if", conditions: [], actions: [] }] };
                    this._noteSilentLoss("Rule JSON could not be parsed — Save blocked");
                }
                rule = blockyProjectLegacyToBranches(rule);
                const branches = rule.branches || [];
                if (!branches.length) {
                    branches.push({ when: "if", conditions: [], actions: [] });
                }

                let prev = null;
                branches.forEach((br, bi) => {
                    const when = br.when || (bi === 0 ? "if" : "else_if");
                    if (when === "else") {
                        this._noteSilentLoss(
                            `Branch #${bi + 1}: bare Else is retired — re-author as Else-if`
                        );
                        return;
                    }
                    const type = when === "if" ? "b_if_do" : "b_else_if";
                    const blk = blockyMkBlock(type, null, bi === 0 ? 16 : undefined, bi === 0 ? 16 : undefined);
                    blockyConnectChain(blk, "IF", blockyConditionBlocksFromList(br.conditions || []));
                    blockyConnectChain(blk, "DO", this._actionBlocks(br.actions || []));
                    if (prev && prev.nextConnection && blk.previousConnection) {
                        try { prev.nextConnection.connect(blk.previousConnection); } catch (e) { /* ignore */ }
                    }
                    prev = blk;
                });

                ws.getAllBlocks(false).forEach((b) => {
                    if (b.type === "b_action_device") {
                        blockyCoerceFieldToOptions(b, "STATE", blockyActionStateOptions);
                        blockyActionUpdateRichShape(b);
                    }
                });
                // IF trees are connected: reshape device Compares (turns vs is; duplicate-safe chrome).
                blockyRefreshAllConditionGateWording();
                ws.getAllBlocks(false).forEach((b) => {
                    if (b.type === "b_condition_device") {
                        blockyCoerceFieldToOptions(b, "STATE", blockyConditionStateOptions);
                    }
                });

                let node = ws.getTopBlocks(true).find((b) => b.type === "b_if_do");
                let bi = 0;
                while (node && BLOCKY_CONTROL_BRANCH.has(node.type)) {
                    const br = branches[bi] || {};
                    const acts = br.actions || [];
                    let ab = node.getInputTargetBlock("DO");
                    let ai = 0;
                    while (ab) {
                        if (ab.type === "b_action_device") {
                            if (acts[ai] && acts[ai].entity_id) {
                                blockySafeSetField(ab, "ENTITY", acts[ai].entity_id);
                                blockyApplyActionRich(ab, acts[ai]);
                            }
                            ai += 1;
                        } else if (BLOCKY_EVENT_ACTIONS.has(ab.type)) {
                            ai += 1;
                        }
                        ab = ab.getNextBlock();
                    }
                    bi += 1;
                    node = node.getNextBlock();
                }

                if (BlockyRT.richTimer) {
                    clearTimeout(BlockyRT.richTimer);
                    BlockyRT.richTimer = null;
                }
                BlockyRT.pendingRichOpts = null;
                blockyCancelUniqueness();

                if (ws.render) ws.render();
                this.resizeBlockly();
                this.scrollBlocklyToTopLeft();
                blockyRefreshToolbox();
                if (this.silentLossReasons.length) {
                    this.errorMessage = "Silent-loss: Save blocked — "
                        + this.silentLossReasons.join("; ");
                }
                requestAnimationFrame(() => {
                    this.resizeBlockly();
                    requestAnimationFrame(() => this.resizeBlockly());
                });
            } finally {
                Events.enable();
                if (this._markDirtyAfterBlocklyLoad) {
                    this._markDirtyAfterBlocklyLoad = false;
                    this.editorDirty = true;
                    this.suppressDirtyUntil = 0;
                    this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                } else {
                    this.markEditorClean();
                }
                queueMicrotask(() => {
                    BlockyRT.loading = false;
                    BlockyRT.suppressHueWheel = false;
                });
            }
        },

        _readConditions(start) {
            const readLeaf = (b) => {
                if (b.type === "b_condition_time") {
                    return blockyMergeOpaque(
                        { type: "time_of_day", is: b.getFieldValue("TOD") },
                        b
                    );
                }
                if (BLOCKY_EVENT_COMPARES.has(b.type)) {
                    return blockyMergeOpaque(
                        { type: "event", event: b.getFieldValue("EVENT") },
                        b
                    );
                }
                const eid = b.getFieldValue("ENTITY");
                const out = { type: "device_state", entity_id: eid };
                const profile = blockyConditionCompareProfile(eid);
                if (profile.kind === "level") {
                    const mode = b.getFieldValue("MODE") || profile.modes[0][1];
                    if (mode === "ANY") {
                        out.is = "ANY";
                    } else if (mode === "PCT") {
                        out.op = b.getFieldValue("OP") || "==";
                        out.attribute = profile.attribute;
                        let v = b.getFieldValue("VALUE");
                        if (profile.valueUi === "open_pct") {
                            out.op = blockyInvertCompareOp(out.op);
                            v = blockyStoredFromOpenPct(v);
                        }
                        out.is = String(v);
                    } else if (profile.valueUi === "open_pct") {
                        out.is = mode === "CLOSED" ? "100" : "0";
                    } else {
                        out.is = mode;
                    }
                } else if (blockyConditionIsNumericCompare(b)) {
                    out.op = b.getFieldValue("OP") || "==";
                    if (profile.attrs) {
                        const attr = b.getFieldValue("ATTR");
                        if (attr) out.attribute = attr;
                    }
                    out.is = String(b.getFieldValue("VALUE"));
                } else if (blockyIsMotionEntity(eid)) {
                    out.is = "ON";
                } else {
                    out.is = b.getFieldValue("STATE");
                }
                return blockyMergeOpaque(out, b);
            };
            return blockyReadChain(start, (b) => blockyReadConditionExpr(b, readLeaf)).filter(Boolean);
        },

        _readActions(start) {
            return blockyReadChain(start, (b) => {
                if (BLOCKY_EVENT_ACTIONS.has(b.type)) {
                    return blockyMergeOpaque({ event: b.getFieldValue("EVENT") }, b);
                }
                return blockyReadActionRich(b);
            });
        },

        applyBlocklyToV2() {
            this.ensureBlocklyReady();
            this.assertSilentLossClear();
            const ws = blockyWs();
            if (!ws) throw new Error("Blockly workspace not ready.");
            blockyAssertNoOrphans(ws);
            const tops = ws.getTopBlocks(true);
            const root = tops.find((b) => b.type === "b_if_do");
            if (!root) throw new Error("Blockly requires one If/Do block.");
            if (tops.filter((b) => b.type === "b_if_do").length > 1) {
                throw new Error("Only one If/Do root allowed — use Else-if on the chain.");
            }

            const branches = [];
            let cur = root;
            let i = 0;
            while (cur) {
                if (cur.type === "b_if_do" || cur.type === "b_else_if") {
                    const when = cur.type === "b_if_do" ? "if" : "else_if";
                    const conds = this._readConditions(cur.getInputTargetBlock("IF"));
                    const acts = this._readActions(cur.getInputTargetBlock("DO"));
                    if (!conds.length) {
                        // Invalid for enable — still allow serialize while disabled.
                    }
                    branches.push({ when, conditions: conds, actions: acts });
                } else if (cur.type === BLOCKY_LEGACY_ELSE) {
                    throw new Error(
                        "Bare Else is retired — use Else-if with an explicit complementary Compare."
                    );
                } else {
                    throw new Error("Unexpected block on control chain: " + cur.type);
                }
                cur = cur.getNextBlock();
                i += 1;
                if (i > 64) throw new Error("Branch chain too long.");
            }
            if (!branches.length || branches[0].when !== "if") {
                throw new Error("First branch must be If/Do.");
            }

            const payload = {
                id: this.editor.id || undefined,
                name: (this.editor.name || "").trim(),
                enabled: this.editor.enabled !== false,
                branches
            };
            this._bindSrNameToSeCatalog(payload);
            if (!payload.name) throw new Error("Rule name is required.");
            this.validateNoHardDeniedEntityIds(payload);
            // B19 enable gate (mirrors backend).
            const enableErr = this._validateBranchesForEnable(payload);
            if (payload.enabled !== false && enableErr) {
                throw new Error(enableErr);
            }
            this.editor.ruleJson = JSON.stringify(payload, null, 2);
            return payload;
        },

        _validateBranchesForEnable(payload) {
            const branches = payload.branches || [];
            if (!branches.length) return "Automation must contain at least one branch.";
            if (branches[0].when !== "if") return "First branch must be If.";
            for (let i = 0; i < branches.length; i += 1) {
                const br = branches[i];
                if ((br.when === "if" || br.when === "else_if")
                    && blockyCountLeafCompares(br.conditions) < 1) {
                    return "Each If / Else-if needs at least one condition (or disable the rule).";
                }
            }
            return null;
        },

        validateNoHardDeniedEntityIds(rulePayload) {
            const denied = [];
            const visit = (node, path) => {
                if (Array.isArray(node)) {
                    node.forEach((it, i) => visit(it, `${path}[${i}]`));
                    return;
                }
                if (!node || typeof node !== "object") return;
                if (node.entity_id && this.isHardDeniedEntityId(node.entity_id)) {
                    denied.push(`${path}.entity_id=${node.entity_id}`);
                }
                Object.entries(node).forEach(([k, v]) => visit(v, path ? `${path}.${k}` : k));
            };
            visit(rulePayload, "rule");
            if (denied.length) throw new Error(`Blocked by policy (hard deny): ${denied.join(", ")}`);
        },

        /** B9A silent-loss B: record a non-preservable drop detected during canvas load. */
        _noteSilentLoss(reason) {
            const msg = String(reason || "unknown silent-loss");
            if (!this.silentLossReasons) this.silentLossReasons = [];
            if (!this.silentLossReasons.includes(msg)) this.silentLossReasons.push(msg);
        },

        /** B9A silent-loss B: refuse Save when load flagged a non-preservable drop. */
        assertSilentLossClear() {
            const reasons = this.silentLossReasons || [];
            if (!reasons.length) return;
            throw new Error(
                "Save blocked (silent-loss B): rule cannot round-trip safely — "
                + reasons.join("; ")
            );
        },

        /** B9A: Blockly is the only rule editor — payload always comes off the canvas. */
        buildPayloadFromEditor() {
            return this.applyBlocklyToV2();
        },

        /** B10D: block Save when another rule has the same trim+casefold name. */
        assertUniqueRuleName(name, excludeId) {
            const needle = blockyNormalizeNameKey(name);
            if (!needle) throw new Error("Rule name is required.");
            for (const r of this.automations || []) {
                if (!r || r.isEventRow) continue;
                const rid = String(r.id || "");
                if (excludeId && rid === String(excludeId)) continue;
                if (blockyNormalizeNameKey(r.name) === needle) {
                    throw new Error(
                        `Another automation already uses the name "${(r.name || "").trim()}" `
                        + `(case-insensitive). Choose a unique name.`
                    );
                }
            }
        },

        blankEditor() {
            // B19: New rule = empty If/Do, disabled until Compares added.
            return {
                id: "",
                name: "",
                enabled: false,
                ruleJson: JSON.stringify({
                    enabled: false,
                    branches: [{ when: "if", conditions: [], actions: [] }]
                }, null, 2),
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
        },

        /**
         * B10F/B19: draft New rule with event Compare preselected (no POST until Save).
         */
        blankEditorForEvent(eventId, origin) {
            const eid = String(eventId || "");
            let name = "";
            if (origin === "system") {
                name = this._catalogEventName(eid)
                    || (() => {
                        const se = (this.libraryRows || []).find(
                            (r) => r && r.isSystemEventRow && String(r.id) === eid
                        );
                        return se ? String(se.name || se.listName || "") : "";
                    })();
            }
            return {
                id: "",
                name,
                enabled: false,
                ruleJson: JSON.stringify({
                    enabled: false,
                    branches: [{
                        when: "if",
                        conditions: [{ type: "event", event: eid }],
                        actions: []
                    }]
                }, null, 2),
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
        },

        newRule() {
            this.requestLeave({ type: "new" });
        },

        newUserEvent() {
            this.requestLeave({ type: "newUserEvent" });
        },

        _doNewRule() {
            this.markEditorClean();
            this.selectedRule = { isDraft: true };
            this.editor = this.blankEditor();
            this.errorMessage = "";
            this.infoMessage = "";
            this.fireStatusLine = "";
            this.scheduleBlocklyLoad();
        },

        /** B10F: draft New rule with When event preselected (SE→SR or UE→UR). */
        _doNewRuleFromEvent(eventId, origin) {
            this.markEditorClean();
            this.selectedRule = { isDraft: true };
            this.editor = this.blankEditorForEvent(eventId, origin);
            this.errorMessage = "";
            this.infoMessage = "";
            this.fireStatusLine = "";
            // Prefill is already a change — keep dirty through Blockly load (B10F items 6/9).
            this.editorDirty = true;
            this._markDirtyAfterBlocklyLoad = true;
            this.scheduleBlocklyLoad();
        },

        /** B10F: unused SE → open New rule with When system event preselected (draft). */
        createSystemRuleForSelectedSe() {
            if (this.uiLocked) return;
            if (!this.selectedRule || !this.selectedRule.isSystemEventRow) return;
            if (this.selectedSeListenerName) return;
            const eid = String(this.selectedRule.id || "");
            if (!eid) return;
            this.requestLeave({ type: "newFromSe", eventId: eid });
        },

        /** B10F: unused UE → open New rule with When user event preselected (draft). */
        createUserRuleForSelectedUe() {
            if (this.uiLocked) return;
            if (!this.selectedRule || !this.selectedRule.isEventRow) return;
            if (this.selectedUeHasListeningUr) return;
            const eid = String(this.selectedRule.id || this.editor.id || "");
            if (!eid) return;
            this.requestLeave({ type: "newFromUe", eventId: eid });
        },

        /** B10E: draft UE form — Save → POST /api/events only (no Blockly / no rule). */
        _doNewUserEvent() {
            this.markEditorClean();
            this.selectedRule = { isDraft: true, isEventRow: true, libraryKind: "ue" };
            this.editor = {
                id: "",
                name: "",
                enabled: true,
                ruleJson: "{}",
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
            this.errorMessage = "";
            this.infoMessage = "";
            this.fireRefRuleNames = [];
        },

        selectRule(rule) {
            if (!rule) return;
            if (this._isSelectedLibraryRow(rule) && !(rule.isDraft)) return;
            this.requestLeave({ type: "select", rule });
        },

        _doSelectRule(rule) {
            this.markEditorClean();
            this.selectedRule = rule;
            this.errorMessage = "";
            this.infoMessage = "";
            this.eventDeleteBlockedMessage = "";
            this.fireRefRuleNames = [];

            // UE row — catalog form only (no Blockly).
            if (rule && rule.isEventRow) {
                this.editor = {
                    id: rule.id || "",
                    name: rule.name || "",
                    enabled: true,
                    ruleJson: "{}",
                    eventShowOnDashboard: !!rule.show_on_dashboard,
                    eventRequireConfirmation: !!rule.require_confirmation,
                    eventEnabled: rule.enabled !== false
                };
                // Prefill usages for disable-blocked + Show usages (listeners OR fire-refs).
                this.fireRefRuleNames = this._usageRuleNamesForEvent(rule.id);
                this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                return;
            }

            // SE row — system catalog view-only (immutable; create SR via New rule / Create button).
            if (rule && rule.isSystemEventRow) {
                this.editor = {
                    id: rule.id || "",
                    name: rule.name || "",
                    enabled: true,
                    ruleJson: "{}",
                    eventShowOnDashboard: false,
                    eventRequireConfirmation: false,
                    eventEnabled: true
                };
                this.fireStatusLine = "";
                this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
                return;
            }

            // SR: show SE catalog name in the locked name field (even if YAML drifted).
            const kind = this.libraryKind(rule);
            let displayName = rule.name || "";
            if (kind === "sr") {
                displayName = rule.listName
                    || this._catalogEventName(this._primaryEventIdFromRule(rule))
                    || displayName;
            }

            // B19: prefer branches; keep trigger+cases only for unmigrated legacy rows.
            const ruleBody = Array.isArray(rule.branches)
                ? {
                    id: rule.id,
                    name: displayName,
                    enabled: rule.enabled !== false,
                    branches: rule.branches
                }
                : {
                    id: rule.id,
                    name: displayName,
                    enabled: rule.enabled !== false,
                    trigger: rule.trigger,
                    cases: rule.cases || []
                };
            this.editor = {
                id: rule.id || "",
                name: displayName,
                enabled: rule.enabled !== false,
                ruleJson: JSON.stringify(ruleBody, null, 2),
                eventShowOnDashboard: false,
                eventRequireConfirmation: false,
                eventEnabled: true
            };
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
            // Prefill usages for UR whose trigger event is fire-referenced.
            if (kind === "ur") {
                const evId = this._primaryEventIdFromRule(rule);
                this.fireRefRuleNames = this._fireRefNamesForEvent(evId);
            }
            this.refreshFireStatusLine();
            blockyCancelUniqueness();
            void this.ensureAutoOffConfig().then(() => {
                this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
            });
            this.scheduleBlocklyLoad();
        },

        /**
         * Rebuild Library rows: all user events (UE) + rules (UR/SR/D) + all pickable
         * system catalog events (SE, view-only). Unused SE = no listening SR (not disabled).
         */
        rebuildLibraryRows() {
            const catalog = BlockyRT.catalogEvents || [];
            const rules = this.automations || [];
            const rows = [];

            // UE: every user catalog event (including those with listening UR rules).
            for (const r of catalog) {
                if (!r || String(r.origin || "user") !== "user") continue;
                rows.push({
                    id: String(r.id),
                    name: String(r.name || r.id),
                    listName: String(r.name || r.id),
                    origin: "user",
                    show_on_dashboard: !!r.show_on_dashboard,
                    require_confirmation: !!r.require_confirmation,
                    enabled: r.enabled !== false,
                    isEventRow: true,
                    libraryKind: "ue"
                });
            }

            // UR / SR / D from real automation rules.
            for (const rule of rules) {
                if (!rule || typeof rule !== "object") continue;
                const kind = (() => {
                    const evId = this._primaryEventIdFromRule(rule);
                    if (evId) {
                        return this._eventOrigin(evId) === "system" ? "sr" : "ur";
                    }
                    return "d";
                })();
                if (kind === "sr") {
                    const evId = this._primaryEventIdFromRule(rule);
                    const cat = catalog.find((r) => r && String(r.id) === evId);
                    // List label = SE catalog name (SR name always equals SE).
                    const catName = cat ? String(cat.name || evId) : evId;
                    rows.push(Object.assign({}, rule, {
                        libraryKind: "sr",
                        listName: catName,
                        systemEventId: evId
                    }));
                } else {
                    rows.push(Object.assign({}, rule, {
                        libraryKind: kind,
                        listName: String(rule.name || "(unnamed)")
                    }));
                }
            }

            // SE: all pickable system catalog events (view-only; not editable shells).
            for (const r of catalog) {
                if (!r || String(r.origin) !== "system") continue;
                const id = String(r.id);
                if (BLOCKY_NON_PICKABLE_EVENT_IDS.has(id)) continue;
                const catName = String(r.name || id);
                rows.push({
                    isSystemEventRow: true,
                    id,
                    name: catName,
                    listName: catName,
                    origin: "system",
                    enabled: true,
                    libraryKind: "se"
                });
            }

            this.libraryRows = rows;
            // Keep deprecated alias empty so stale UI never mixes orphan list.
            this.orphanEventRows = [];
        },

        /** @deprecated — use rebuildLibraryRows (B10E). */
        rebuildOrphanEventRows() {
            this.rebuildLibraryRows();
        },

        /** Fire the saved UR/SR trigger event on the bus (Explorer-equivalent manual test). */
        async executeSelectedRule() {
            if (!this.canExecuteSelectedRule) return;
            const evId = this._executeTriggerEventId();
            if (!evId) return;
            const evName = this._catalogEventName(evId) || evId;
            const row = (BlockyRT.catalogEvents || []).find((r) => r && String(r.id) === String(evId));
            if (row && row.require_confirmation) {
                if (!confirm(`Fire "${evName}"?`)) return;
            }
            this.busy = true;
            if (!this.ruleSaveFailed) {
                this.errorMessage = "";
            }
            try {
                const res = await fetch("/api/event", {
                    method: "POST",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ type: evId, payload: { origin: "MANUAL" } })
                });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = "/login.html";
                    return;
                }
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `Execute failed (${res.status})`);
                this.infoMessage = `Fired "${evName}" (manual test).`;
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async refreshAll() {
            if (this._refreshAllInFlight) {
                return this._refreshAllInFlight;
            }
            this._refreshAllInFlight = this._refreshAllOnce();
            try {
                return await this._refreshAllInFlight;
            } finally {
                this._refreshAllInFlight = null;
            }
        },

        async _refreshAllOnce() {
            // Nested inside rule save — ruleSaveBusy already owns the overlay + lock.
            const nestedInRuleSave = !!this.ruleSaveBusy;
            const coldLoad = !!this.editorLoading;
            if (!nestedInRuleSave && !coldLoad) {
                this.refreshBusy = true;
            }
            this.busy = true;
            // Keep save-failure message visible while ruleSaveFailed (B10F).
            if (!this.ruleSaveFailed) {
                this.errorMessage = "";
                this.infoMessage = "";
            }
            if (coldLoad) {
                this.coldLoadTimingsSnapshot = null;
                this.coldLoadTotalMs = null;
                this.coldTimeToInteractiveMs = null;
                this.coldLoadInitDelayMs = null;
                this.coldLoadNavToInitMs = null;
                this.infoMessage = "";
                this.errorMessage = "";
                this.registryCheckMessage = "";
                this.registryCheckOk = null;
                this._coldLoadFetchOffsets = {};
                for (const row of this.loadChecklist) {
                    row.done = false;
                    row.ms = null;
                    row.wallMs = null;
                    row.timing = null;
                    row.timingCaptured = false;
                }
            }
            const coldLoadWallStart = coldLoad ? performance.now() : null;
            if (coldLoad && this._coldLoadInitWallStart != null) {
                this.coldLoadInitDelayMs = Math.max(
                    0,
                    Math.round(coldLoadWallStart - this._coldLoadInitWallStart)
                );
            }
            const wrapFetch = (key, fetchPromise) => {
                const markName = `wanos-load-${key}`;
                if (coldLoad && coldLoadWallStart != null) {
                    this._coldLoadFetchOffsets[key] = Math.max(
                        0,
                        Math.round(performance.now() - coldLoadWallStart)
                    );
                }
                performance.mark(markName);
                const start = performance.now();
                return fetchPromise.then((res) => {
                    if (coldLoad) this._markLoadChecklistDone(key, start);
                    return res;
                });
            };
            try {
                const fetches = [
                    wrapFetch("state", fetch("/api/state", { headers: this.getAuthHeaders() })),
                    wrapFetch("automations", fetch("/api/automations", { headers: this.getAuthHeaders() })),
                    wrapFetch("events", fetch("/api/events", { headers: this.getAuthHeaders() }))
                ];
                const results = await Promise.all(fetches);
                const stateRes = results[0];
                const rulesRes = results[1];
                const eventsRes = results[2];
                if (!stateRes.ok) throw new Error(`Failed /api/state (${stateRes.status})`);
                if (!rulesRes.ok) throw new Error(`Failed /api/automations (${rulesRes.status})`);
                if (!eventsRes.ok) throw new Error(`Failed /api/events (${eventsRes.status})`);
                const [state, rulesPayload, eventsPayload] = await Promise.all([
                    stateRes.json(),
                    rulesRes.json(),
                    eventsRes.json()
                ]);
                if (coldLoad) {
                    this._captureLoadRowTiming("state", "/api/state", "wanos-load-state");
                    this._captureLoadRowTiming("automations", "/api/automations", "wanos-load-automations");
                    this._captureLoadRowTiming("events", "/api/events", "wanos-load-events");
                }
                if (coldLoad && window.WanOSReloadAlerts && state.system) {
                    this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(
                        state.system.system_alert_msgs || []
                    );
                }
                const libStart = performance.now();
                this.automations = (rulesPayload.automations || []).filter((r) => r && typeof r === "object");
                BlockyRT.catalogEvents = Array.isArray(eventsPayload.events) ? eventsPayload.events : [];
                this.rebuildLibraryRows();
                this.rebuildEntityOptions(state.device_metadata || {}, this.automations);
                this.liveDevices = state.devices || {};
                this._applyAutoOffFromState(state.system);
                const sys = (state && state.system) || {};
                this._applyRulesActivationPending(sys.rules_activation_pending);
                this.huePresets = (sys.hue_presets && typeof sys.hue_presets === "object")
                    ? sys.hue_presets : {};
                this.sonosStations = (sys.sonos_stations && typeof sys.sonos_stations === "object")
                    ? sys.sonos_stations : {};
                if (coldLoad) this._markLoadChecklistDone("library", libStart);
                if (this.selectedRule && !this.editorDirty) {
                    if (this.selectedRule.isEventRow) {
                        const sid = String(this.selectedRule.id || this.editor.id || "");
                        const freshEv = (this.libraryRows || []).find(
                            (e) => e.isEventRow && String(e.id) === sid
                        );
                        if (freshEv) {
                            this._doSelectRule(Object.assign({}, freshEv, { isEventRow: true }));
                        } else if (!this.selectedRule.isDraft) {
                            this.selectedRule = null;
                        }
                    } else if (this.selectedRule.isSystemEventRow) {
                        const sid = String(this.selectedRule.id || this.editor.id || "");
                        const freshSe = (this.libraryRows || []).find(
                            (e) => e.isSystemEventRow && String(e.id) === sid
                        );
                        if (freshSe) this._doSelectRule(freshSe);
                        else this.selectedRule = null;
                    } else if (this.selectedRule.id) {
                        const fresh = this.automations.find((r) => r.id === this.selectedRule.id);
                        if (fresh) this._doSelectRule(fresh);
                    }
                }
                if (!coldLoad && this.showBlocklyWorkspace && !this.editorDirty) {
                    this.scheduleBlocklyLoad();
                }
                if (coldLoad) {
                    if (!this.autoOffConfig) {
                        await this.ensureAutoOffConfig();
                    }
                    this.coldTimeToInteractiveMs = Math.round(performance.now());
                    this.connected = true;
                    this.editorLoading = false;
                    this._snapshotColdLoadTimings();
                    this._logColdLoadTimings();
                    this._deferColdFireStatus(coldLoadWallStart);
                    return true;
                }
                const fireStart = performance.now();
                await this.fetchFireStatus();
                this.connected = true;
                return true;
            } catch (e) {
                if (!this.ruleSaveFailed) this.errorMessage = String(e);
                this.connected = false;
                return false;
            } finally {
                this.busy = false;
                if (!nestedInRuleSave && !coldLoad) {
                    this.refreshBusy = false;
                }
            }
        },

        /** B10H: fire-status after cold overlay clears — updates checklist + refreshAll total. */
        _deferColdFireStatus(coldLoadWallStart) {
            if (coldLoadWallStart != null) {
                this._coldLoadFetchOffsets.fire = Math.max(
                    0,
                    Math.round(performance.now() - coldLoadWallStart)
                );
            }
            performance.mark("wanos-load-fire");
            const fireStart = performance.now();
            void (async () => {
                try {
                    await this.fetchFireStatus();
                    this._markLoadChecklistDone("fire", fireStart);
                    this._captureLoadRowTiming("fire", "/api/automations/fire-status", "wanos-load-fire");
                    if (coldLoadWallStart != null) {
                        this.coldLoadTotalMs = Math.max(
                            0,
                            Math.round(performance.now() - coldLoadWallStart)
                        );
                    }
                    this._snapshotColdLoadTimings();
                    this._logColdLoadTimings();
                } catch (e) {
                    /* optional — status line only */
                }
            })();
        },

        _markLoadChecklistDone(key, startMs) {
            const row = this.loadChecklist.find((r) => r.key === key);
            if (row && !row.done) {
                row.done = true;
                const wallMs = Math.max(0, Math.round(performance.now() - startMs));
                row.wallMs = wallMs;
                row.ms = wallMs;
            }
        },

        /** Match the PerformanceResourceTiming row for one cold-load fetch (mark → resource). */
        _readFetchResourceTiming(pathname, markName, jsBeforeFetchMs) {
            const markEntries = markName ? performance.getEntriesByName(markName, "mark") : [];
            const markStart = markEntries.length ? markEntries[markEntries.length - 1].startTime : null;
            const candidates = performance.getEntriesByType("resource").filter((entry) => {
                try {
                    return new URL(entry.name).pathname === pathname;
                } catch (e) {
                    return false;
                }
            });
            let entry = null;
            if (markStart != null) {
                const afterMark = candidates
                    .filter((e) => e.startTime >= markStart - 1)
                    .sort((a, b) => a.startTime - b.startTime);
                entry = afterMark.length ? afterMark[0] : null;
            }
            if (!entry && candidates.length) entry = candidates[candidates.length - 1];
            if (!entry || entry.responseEnd <= 0) return null;

            const download = Math.max(0, entry.responseEnd - entry.responseStart);
            const resourceTotal = Math.max(0, entry.duration || (entry.responseEnd - entry.startTime));
            const wireTtfb = entry.requestStart > 0
                ? Math.max(0, entry.responseStart - entry.requestStart)
                : null;
            const fetchToFirstByte = entry.fetchStart > 0 && entry.responseStart > 0
                ? Math.max(0, entry.responseStart - entry.fetchStart)
                : null;
            const navToFirstByte = entry.responseStart > 0
                ? Math.max(0, entry.responseStart)
                : null;
            const queueBeforeSend = entry.requestStart > 0 && entry.fetchStart > 0
                ? Math.max(0, entry.requestStart - entry.fetchStart)
                : null;

            return {
                resourceTotal: Math.round(resourceTotal),
                download: Math.round(download),
                wireTtfb: wireTtfb != null ? Math.round(wireTtfb) : null,
                fetchToFirstByte: fetchToFirstByte != null ? Math.round(fetchToFirstByte) : null,
                navToFirstByte: navToFirstByte != null ? Math.round(navToFirstByte) : null,
                queueBeforeSend: queueBeforeSend != null ? Math.round(queueBeforeSend) : null,
                jsBeforeFetch: jsBeforeFetchMs != null ? Math.round(jsBeforeFetchMs) : null,
                requestStartMissing: entry.requestStart <= 0
            };
        },

        /** Immutable capture — never re-read (Resource Timing entries can grow after the fact). */
        _captureLoadRowTiming(key, pathname, markName) {
            const row = this.loadChecklist.find((r) => r.key === key);
            if (!row || row.timingCaptured) return;
            const jsBeforeFetch = (this._coldLoadFetchOffsets || {})[key];
            const timing = this._readFetchResourceTiming(pathname, markName, jsBeforeFetch);
            if (!timing) return;
            row.timing = {
                resourceTotal: timing.resourceTotal,
                download: timing.download,
                wireTtfb: timing.wireTtfb,
                fetchToFirstByte: timing.fetchToFirstByte,
                navToFirstByte: timing.navToFirstByte,
                queueBeforeSend: timing.queueBeforeSend,
                jsBeforeFetch: timing.jsBeforeFetch,
                requestStartMissing: !!timing.requestStartMissing
            };
            row.timingCaptured = true;
            row.ms = timing.resourceTotal;
        },

        _cloneLoadTiming(timing) {
            if (!timing) return null;
            return {
                resourceTotal: timing.resourceTotal,
                download: timing.download,
                wireTtfb: timing.wireTtfb,
                fetchToFirstByte: timing.fetchToFirstByte,
                navToFirstByte: timing.navToFirstByte,
                queueBeforeSend: timing.queueBeforeSend,
                jsBeforeFetch: timing.jsBeforeFetch,
                requestStartMissing: !!timing.requestStartMissing
            };
        },

        /** Deep-freeze checklist rows for the admin modal (before heartbeat adds /api/state). */
        _snapshotColdLoadTimings() {
            this.coldLoadTimingsSnapshot = this.loadChecklist.map((row) => ({
                key: row.key,
                label: row.label,
                api: row.api,
                done: !!row.done,
                ms: row.ms,
                wallMs: row.wallMs,
                timing: this._cloneLoadTiming(row.timing)
            }));
        },

        _logColdLoadTimings() {
            const rows = this.coldLoadTimingsSnapshot || this.loadChecklist;
            const lines = rows.map((r) => {
                const base = `${this.loadChecklistLabel(r)} (${r.api}): ${this.loadChecklistTimingMs(r)}`;
                const detail = this.loadChecklistTimingDetail(r);
                return detail ? `${base} — ${detail}` : base;
            });
            const footer = [];
            if (this.coldLoadInitDelayMs != null) {
                footer.push(`Init→refreshAll: ${this.coldLoadInitDelayMs} ms`);
            }
            if (this.coldLoadNavToInitMs != null) {
                footer.push(`nav→init: ${this.coldLoadNavToInitMs} ms`);
            }
            if (this.coldLoadTotalMs != null) {
                footer.push(`refreshAll total: ${this.coldLoadTotalMs} ms`);
            }
            if (this.coldTimeToInteractiveMs != null) {
                footer.push(`time-to-interactive: ${this.coldTimeToInteractiveMs} ms`);
            }
            if (this.coldLoadNavToInitMs != null && this.coldLoadTotalMs != null) {
                const initDelay = this.coldLoadInitDelayMs || 0;
                footer.push(`Cold open (nav→done): ${this.coldLoadNavToInitMs + initDelay + this.coldLoadTotalMs} ms`);
            }
            console.info("[B10G load timings]\n" + lines.join("\n")
                + (footer.length ? `\n${footer.join(" · ")}` : ""));
        },

        /** B10G: checklist/modal row label. */
        loadChecklistLabel(row) {
            return row && row.label ? row.label : "";
        },

        /** Primary ms column — Resource Timing resource duration when available. */
        loadChecklistTimingMs(row) {
            if (!row || row.ms == null) return "—";
            return `${row.ms} ms`;
        },

        /** wire TTFB / fetch→byte / nav→byte / queue / dl / before fetch (+ JS wall when divergent). */
        loadChecklistTimingDetail(row) {
            if (!row || !row.timing) return "";
            const t = row.timing;
            const parts = [];
            parts.push(t.wireTtfb != null ? `wire TTFB ${t.wireTtfb}` : "wire TTFB —");
            if (t.fetchToFirstByte != null) parts.push(`fetch→byte ${t.fetchToFirstByte}`);
            if (t.navToFirstByte != null) parts.push(`nav→byte ${t.navToFirstByte}`);
            if (t.queueBeforeSend != null) parts.push(`queue ${t.queueBeforeSend}`);
            parts.push(`dl ${t.download}`);
            if (t.jsBeforeFetch != null) parts.push(`before fetch ${t.jsBeforeFetch}`);
            if (t.requestStartMissing) parts.push("requestStart hidden");
            let detail = parts.join(" · ");
            if (row.wallMs != null && t.resourceTotal != null && row.wallMs > t.resourceTotal + 50) {
                detail += ` · JS wall ${row.wallMs} ms`;
            }
            return detail;
        },

        /** Footer summary for the admin timings modal. */
        coldLoadTimingSummary() {
            const parts = [];
            if (this.coldLoadNavToInitMs != null) {
                parts.push(`nav→init: ${this.coldLoadNavToInitMs} ms`);
            }
            if (this.coldLoadInitDelayMs != null) {
                parts.push(`Init→refreshAll: ${this.coldLoadInitDelayMs} ms`);
            }
            if (this.coldTimeToInteractiveMs != null) {
                parts.push(`time-to-interactive: ${this.coldTimeToInteractiveMs} ms`);
            }
            if (this.coldLoadTotalMs != null) {
                parts.push(`refreshAll total: ${this.coldLoadTotalMs} ms`);
            }
            if (this.coldTimeToInteractiveMs != null) {
                parts.push(`Cold open (nav→interactive): ${this.coldTimeToInteractiveMs} ms`);
            } else if (this.coldLoadNavToInitMs != null && this.coldLoadTotalMs != null) {
                const initDelay = this.coldLoadInitDelayMs || 0;
                parts.push(`Cold open (nav→done): ${this.coldLoadNavToInitMs + initDelay + this.coldLoadTotalMs} ms`);
            }
            return parts.join(" · ");
        },

        _startRestHeartbeat() {
            if (this._heartbeatTimer) clearInterval(this._heartbeatTimer);
            const tick = async () => {
                if (document.hidden || this.editorLoading) return;
                try {
                    const res = await fetch("/api/state", { headers: this.getAuthHeaders() });
                    if (!res.ok) {
                        this.connected = false;
                        return;
                    }
                    const st = await res.json();
                    if (window.WanOSReloadAlerts && st.system) {
                        this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(
                            st.system.system_alert_msgs || []
                        );
                        this._applyRulesActivationPending(st.system.rules_activation_pending);
                    }
                    this.liveDevices = st.devices || {};
                    this.connected = true;
                } catch (e) {
                    this.connected = false;
                }
            };
            tick();
            this._heartbeatTimer = setInterval(tick, 10000);
        },

        _stopRestHeartbeat() {
            if (this._heartbeatTimer) {
                clearInterval(this._heartbeatTimer);
                this._heartbeatTimer = null;
            }
        },

        _openLoadTimingsModal() {
            const dlg = document.getElementById("blocky_load_timings_modal");
            if (dlg && typeof dlg.showModal === "function") dlg.showModal();
            this.loadTimingsModalOpen = true;
        },

        /** B10K: stopwatch — only after a successful cold-load snapshot. */
        openLoadTimingsModal() {
            if (this.editorLoading || !this.coldLoadTimingsSnapshot) return;
            this._openLoadTimingsModal();
        },

        async runPostWriteRegistryCheck(opts = {}) {
            const okMsg = opts.okMsg || "Rule saved";
            const failMsg = opts.failMsg || "Saved, but registry check failed — open Admin → Debug.";
            const verifyFailMsg = opts.verifyFailMsg || "Saved, but could not verify — open Admin → Debug.";
            // Post-save registry check — GREEN expected after B4/H4 OR-list cutover.
            const savedName = String(opts.savedRuleName || "").trim();
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const res = await fetch("/api/debug/entity-registry-check", {
                    headers: this.getAuthHeaders()
                });
                const report = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.registryCheckOk = false;
                    this.registryCheckMessage = verifyFailMsg;
                    return;
                }
                const errors = Array.isArray(report.errors) ? report.errors.map(String) : [];
                const warnN = (report.warnings || []).length;
                if (report.ok) {
                    this.registryCheckOk = true;
                    this.registryCheckMessage = warnN
                        ? `${okMsg} (warnings in Admin → Debug).`
                        : okMsg;
                    return;
                }
                const legacyRe = /^B19 legacy trigger\/cases still present:/;
                const onlyAcceptedLegacy = errors.length > 0
                    && errors.every((e) => legacyRe.test(e));
                const savedFlaggedLegacy = !!(savedName && errors.some((e) =>
                    legacyRe.test(e) && e.indexOf(savedName) !== -1
                ));
                if (onlyAcceptedLegacy && !savedFlaggedLegacy) {
                    this.registryCheckOk = true;
                    this.registryCheckMessage = `${okMsg} `
                        + `(Admin Debug still RED until H4 — ${errors.length} leftover OR rule`
                        + `${errors.length === 1 ? "" : "s"}).`;
                    return;
                }
                this.registryCheckOk = false;
                this.registryCheckMessage = failMsg;
            } catch (e) {
                this.registryCheckOk = false;
                this.registryCheckMessage = verifyFailMsg;
            }
        },

        /**
         * PUT /api/events for the open UE-form row (name / explorer / confirm / enabled).
         * Confirm is coerced off when Appear on explorer is off.
         */
        async persistUserEventFromEditor(eventId, opts = {}) {
            const id = String(eventId || "");
            if (!id) return null;
            const show = !!this.editor.eventShowOnDashboard;
            const body = {
                id,
                name: String(opts.name || this.editor.name || "").trim(),
                show_on_dashboard: show,
                require_confirmation: show && !!this.editor.eventRequireConfirmation,
                enabled: this.editor.eventEnabled !== false
            };
            if (!body.name) throw new Error("Event name is required.");
            if (body.enabled === false && this._usageRuleNamesForEvent(id).length) {
                throw new Error(
                    "Cannot disable this event — rules still listen to or fire it. See Show usages."
                );
            }
            const res = await fetch("/api/events", {
                method: "PUT",
                headers: this.getAuthHeaders(),
                body: JSON.stringify(body)
            });
            const resp = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(resp.error || `PUT /api/events failed (${res.status})`);
            return resp.event || body;
        },

        /** POST a new user event from E form (editor.name). */
        async createUserEventFromEditor() {
            const name = String(this.editor.name || "").trim();
            if (!name) throw new Error("New user event requires a name.");
            const show = !!this.editor.eventShowOnDashboard;
            const body = {
                name,
                show_on_dashboard: show,
                require_confirmation: show && !!this.editor.eventRequireConfirmation,
                enabled: this.editor.eventEnabled !== false
            };
            const res = await fetch("/api/events", {
                method: "POST",
                headers: this.getAuthHeaders(),
                body: JSON.stringify(body)
            });
            const resp = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(resp.error || `POST /api/events failed (${res.status})`);
            return resp.event;
        },

        /**
         * B10E: one listening rule max per system event UUID.
         * Throws if save would create a second listener.
         */
        assertOneSystemListener(payload) {
            const evId = this._primaryEventIdFromRule(payload);
            if (!evId || this._eventOrigin(evId) !== "system") return;
            const excludeId = payload && payload.id ? String(payload.id) : "";
            for (const r of this.automations || []) {
                if (!r) continue;
                if (excludeId && String(r.id) === excludeId) continue;
                if (this._primaryEventIdFromRule(r) === evId) {
                    const nm = (r.name || r.id || "").trim();
                    throw new Error(
                        `Only one rule may listen to this system event`
                        + (nm ? ` (already: "${nm}")` : "")
                        + ". Edit the existing SR row instead."
                    );
                }
            }
        },

        async saveRule() {
            // SE catalog: immutable — no Save that edits the system event.
            if (this.selectedRule && this.selectedRule.isSystemEventRow) {
                this.errorMessage = "System events are catalog-only (view-only). "
                    + "Create a system rule via New rule → When system event.";
                return;
            }

            // UE row (user event): POST create or PUT update — no automation rule.
            if (this.selectedRule && this.selectedRule.isEventRow) {
                this.busy = true;
                this.errorMessage = "";
                this.infoMessage = "";
                try {
                    const isDraft = !!this.selectedRule.isDraft || !this.editor.id;
                    if (isDraft) {
                        const created = await this.createUserEventFromEditor();
                        this.infoMessage = "Event saved. Activate changed rules to apply.";
                        this.markEditorClean();
                        await this._refreshAfterEventSave(created);
                        if (created && created.id) {
                            const row = (this.libraryRows || []).find(
                                (e) => e.isEventRow && String(e.id) === String(created.id)
                            );
                            if (row) this._doSelectRule(row);
                        }
                    } else {
                        // Coerce confirm when explorer off before PUT
                        if (!this.editor.eventShowOnDashboard) {
                            this.editor.eventRequireConfirmation = false;
                        }
                        if (this.editor.eventEnabled === false
                            && this._usageRuleNamesForEvent(this.editor.id).length) {
                            throw new Error(
                                "Cannot disable this event — rules still listen to or fire it. See usages listed below."
                            );
                        }
                        await this.persistUserEventFromEditor(this.editor.id, { name: this.editor.name });
                        this.infoMessage = "Event saved. Activate changed rules to apply.";
                        this.markEditorClean();
                        await this._refreshAfterEventSave({ id: this.editor.id, name: this.editor.name });
                    }
                } catch (e) {
                    this.errorMessage = String(e);
                } finally {
                    this.busy = false;
                }
                return;
            }

            this.busy = true;
            this.ruleSaveBusy = true;
            this.ruleSaveFailed = false;
            this.errorMessage = "";
            this.infoMessage = "";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                if (this.ruleDisableBlocked && this.editor.enabled === false) {
                    throw new Error(
                        "Cannot disable this rule — its user event is fired by other rules. See usages listed below."
                    );
                }
                const payload = this.buildPayloadFromEditor();
                this.assertUniqueRuleName(payload.name, payload.id);
                this.assertOneSystemListener(payload);

                const isUpdate = !!payload.id && this.automations.some((r) => r.id === payload.id);
                const method = isUpdate ? "PUT" : "POST";
                const res = await fetch("/api/automations", {
                    method,
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `${method} failed (${res.status})`);
                if (body.rules_activation_pending) {
                    this._applyRulesActivationPending(body.rules_activation_pending);
                }
                const savedDisabled = payload.enabled === false;
                this.infoMessage = savedDisabled
                    ? "Rule saved."
                    : (this.rulesPendingCount > 0
                        ? "Rule saved. Activate changed rules to apply."
                        : "Rule saved.");
                this.markEditorClean();
                this.ruleSaveBusy = false;
                await this._refreshAfterRuleSave(body.automation || payload);
                const savedId = (body.automation && body.automation.id) || payload.id;
                if (savedId) {
                    const fresh = (this.libraryRows || []).find((r) =>
                        r && !r.isEventRow && !r.isSystemEventRow && r.id === savedId
                    ) || this.automations.find((r) => r.id === savedId);
                    if (fresh) this._doSelectRule(fresh);
                }
                void this.runPostWriteRegistryCheck({
                    okMsg: isUpdate ? "Rule updated" : "Rule created",
                    failMsg: "Saved, but registry check failed — open Admin → Debug.",
                    savedRuleName: (body.automation && body.automation.name) || payload.name || ""
                });
                this.ruleSaveFailed = false;
            } catch (e) {
                this.errorMessage = String(e);
                this.ruleSaveBusy = false;
                this.ruleSaveFailed = true;
            } finally {
                this.busy = false;
            }
        },

        /** B10F: re-attempt the failed rule save. */
        async retryRuleSave() {
            if (!this.ruleSaveFailed) return;
            this.ruleSaveFailed = false;
            await this.saveRule();
        },

        /** B10F: unlock UI after failed rule save; keep editor edits. */
        dismissRuleSaveFailure() {
            this.ruleSaveFailed = false;
            this.ruleSaveBusy = false;
            this.busy = false;
        },

        /**
         * B10F: ↑/↓ changes selection in the currently filtered Library list (no wrap).
         * Bound only on the Library list (not also on main — that double-fired via bubble).
         */
        onLibraryKeydown(ev) {
            if (this.uiLocked) return;
            if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
            const rows = this.filteredLibrary || [];
            if (!rows.length) return;
            // Ignore when typing in inputs (except the library list container itself).
            const tag = (ev.target && ev.target.tagName) || "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
            ev.preventDefault();
            ev.stopPropagation();
            let idx = -1;
            if (this.selectedRule) {
                const key = this.libraryRowKey(this.selectedRule);
                idx = rows.findIndex((r) => this.libraryRowKey(r) === key);
            }
            if (ev.key === "ArrowDown") {
                if (idx < 0) idx = 0;
                else if (idx < rows.length - 1) idx += 1;
                // else stop at end (no wrap)
            } else {
                if (idx < 0) idx = 0;
                else if (idx > 0) idx -= 1;
                // else stop at start (no wrap)
            }
            const next = rows[idx];
            if (!next) return;
            this.selectRule(next);
            // Keep the selected row visible inside the overflow list.
            const scrollKey = this.libraryRowKey(next);
            this.$nextTick(() => {
                const el = document.querySelector(
                    `[data-library-row-key="${CSS.escape(scrollKey)}"]`
                );
                if (el && typeof el.scrollIntoView === "function") {
                    el.scrollIntoView({ block: "nearest", inline: "nearest" });
                }
            });
        },

        /** Fetch fire-status map; refresh line for the open SR. */
        async fetchFireStatus() {
            try {
                const res = await fetch("/api/automations/fire-status", {
                    headers: this.getAuthHeaders()
                });
                if (!res.ok) return;
                const body = await res.json().catch(() => ({}));
                const map = {};
                for (const e of (body.entries || [])) {
                    if (e && e.event_uuid) map[String(e.event_uuid)] = e;
                }
                this.fireStatusByUuid = map;
                this.refreshFireStatusLine();
            } catch (e) {
                /* ignore — status line optional */
            }
        },

        /** B10F: status copy right above Full screen for in-scope SR When triggers. */
        refreshFireStatusLine() {
            this.fireStatusLine = "";
            if (!this.selectedRule || this.selectedRule.isEventRow || this.selectedRule.isSystemEventRow) {
                return;
            }
            let rule = this.selectedRule;
            if (!rule || (!rule.branches && !rule.trigger)) {
                try { rule = JSON.parse(this.editor.ruleJson || "{}"); }
                catch (e) { rule = null; }
            }
            const evId = this._primaryEventIdFromRule(rule);
            if (!evId || this._eventOrigin(evId) !== "system") return;
            const entry = this.fireStatusByUuid[String(evId)];
            if (!entry) return;
            const st = entry.state;
            if (st === "not_armed") return;
            if (st === "doesnt_fire_today") {
                this.fireStatusLine = "Doesn't fire today";
                return;
            }
            const hhmm = entry.at_hhmm || "";
            if (st === "will_fire" && hhmm) {
                this.fireStatusLine = `Will fire at ${hhmm}`;
                return;
            }
            if (st === "has_fired" && hhmm) {
                this.fireStatusLine = `Has fired at ${hhmm}`;
            }
        },

        async deleteRule() {
            // UE delete — DELETE /api/events with confirm; 409 → modal.
            if (this.selectedRule && this.selectedRule.isEventRow) {
                await this.deleteSelectedEvent();
                return;
            }
            if (this.selectedRule && this.selectedRule.isSystemEventRow) {
                this.errorMessage = "System events cannot be deleted (catalog seeds).";
                return;
            }
            if (!this.editor.id) {
                this.errorMessage = "No rule id to delete.";
                return;
            }
            if (!confirm(`Delete automation '${this.editor.name}'?`)) return;
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const res = await fetch("/api/automations", {
                    method: "DELETE",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ id: this.editor.id })
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `DELETE failed (${res.status})`);
                if (body.rules_activation_pending) {
                    this._applyRulesActivationPending(body.rules_activation_pending);
                }
                const wasDisabled = this.editor.enabled === false;
                this.infoMessage = wasDisabled
                    ? "Rule deleted."
                    : (this.rulesPendingCount > 0
                        ? "Rule deleted. Activate changed rules to apply."
                        : "Rule deleted.");
                this.markEditorClean();
                this.automations = (this.automations || []).filter((r) => r && String(r.id) !== String(this.editor.id));
                await this._refreshAfterRuleSave(null);
                this._doNewRule();
                await this.runPostWriteRegistryCheck({
                    okMsg: "Rule deleted",
                    failMsg: "Deleted, but registry check failed — open Admin → Debug.",
                    verifyFailMsg: "Deleted, but could not verify — open Admin → Debug."
                });
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        /** Delete unused user event (orphan row). API guards block in-use / dashboard / system. */
        async deleteSelectedEvent() {
            const id = this.editor.id;
            if (!id) {
                this.errorMessage = "No event id to delete.";
                return;
            }
            if (!confirm(`Delete user event '${this.editor.name || id}'? This cannot be undone.`)) return;
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            this.eventDeleteBlockedMessage = "";
            try {
                const res = await fetch("/api/events", {
                    method: "DELETE",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ id })
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const msg = body.error || `DELETE /api/events failed (${res.status})`;
                    if (res.status === 409 || res.status === 400) {
                        this.eventDeleteBlockedMessage = msg;
                        const dlg = document.getElementById("event_delete_blocked_modal");
                        if (dlg) dlg.showModal();
                        else this.errorMessage = msg;
                        return;
                    }
                    throw new Error(msg);
                }
                if (body.rules_activation_pending) {
                    this._applyRulesActivationPending(body.rules_activation_pending);
                }
                this.infoMessage = "Event deleted. Activate changed rules to apply.";
                this.markEditorClean();
                BlockyRT.catalogEvents = (BlockyRT.catalogEvents || []).filter(
                    (r) => r && String(r.id) !== String(id)
                );
                await this._refreshAfterEventSave(null);
                this.selectedRule = null;
                this.editor = {
                    id: "",
                    name: "",
                    enabled: true,
                    ruleJson: "{}",
                    eventShowOnDashboard: false,
                    eventRequireConfirmation: false,
                    eventEnabled: true
                };
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        closeEventDeleteBlockedModal() {
            this.eventDeleteBlockedMessage = "";
            document.getElementById("event_delete_blocked_modal")?.close();
        },

        async init() {
            this.coldLoadNavToInitMs = Math.round(performance.now());
            BlockyRT.app = this;
            if (wanosRedirectIfNarrow()) return;
            const token = localStorage.getItem("wanos_jwt") || "";
            if (!token) {
                window.location.href = "/login.html";
                return;
            }
            if (!this.isAdminToken(token)) {
                window.location.href = "/deviceexplorer.html";
                return;
            }
            this.isAdmin = true;
            this._onBeforeUnload = (e) => {
                if (!this.editorDirty) return;
                e.preventDefault();
                e.returnValue = "";
            };
            window.addEventListener("beforeunload", this._onBeforeUnload);
            this.$watch("editor.name", () => this.markEditorDirty());
            this.$watch("editor.enabled", () => this.markEditorDirty());
            this.$watch("editor.eventShowOnDashboard", () => this.markEditorDirty());
            this.$watch("editor.eventRequireConfirmation", () => this.markEditorDirty());
            this.$watch("editor.eventEnabled", () => this.markEditorDirty());
            this.$watch("editor.ruleJson", () => this.markEditorDirty());
            this._coldLoadInitWallStart = performance.now();
            this.editorLoading = true;
            const ok = await this.refreshAll();
            if (this.editorLoading) {
                if (ok) this.connected = true;
                this.editorLoading = false;
            }
            if (ok) {
                this.connected = true;
                this._startRestHeartbeat();
                if (this.showBlocklyWorkspace && !this.editorDirty) {
                    this.scheduleBlocklyLoad();
                }
            } else {
                this.connected = false;
            }
        }
    };
}
