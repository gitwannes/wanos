// Phase 6B: unified Blockly canvas for schema v2 (trigger + ordered cases).
// Contextual dropdowns: only show entries valid for the current trigger / device type.
// Phase 6C (TODO): rich action authoring UX — Hue preset, blinds open %, Sonos volume/station.

/** Keep in sync with core/schedule_events.SCHEDULE_WINDOW_EDGES (enter, exit). */
const BLOCKY_SCHEDULE_WINDOW_EDGES = {
    blinds: ["BLINDS_OPEN_TRIGGER", "BLINDS_CLOSE_TRIGGER"],
    twilight_evening: ["SUNSET_TRIGGER", "EVENING_OFF_TRIGGER"],
    twilight_morning: ["MORNING_ON_TRIGGER", "SUNRISE_TRIGGER"],
    sauna: ["SAUNA_ON", "SAUNA_OFF"],
    ir: ["IR_ON", "IR_OFF"],
    cinema: ["SCENE_CINEMA_ON", "SCENE_CINEMA_OFF"]
};

const BLOCKY_EDGE_SHORT = {
    BLINDS_OPEN_TRIGGER: "blinds open",
    BLINDS_CLOSE_TRIGGER: "blinds close",
    MORNING_ON_TRIGGER: "morning-on",
    SUNRISE_TRIGGER: "sunrise",
    SUNSET_TRIGGER: "sunset",
    EVENING_OFF_TRIGGER: "evening-off",
    SAUNA_ON: "sauna ON",
    SAUNA_OFF: "sauna OFF",
    IR_ON: "IR ON",
    IR_OFF: "IR OFF",
    SCENE_CINEMA_ON: "cinema ON",
    SCENE_CINEMA_OFF: "cinema OFF"
};

const BLOCKY_EDGE_STATES = [
    ["ON", "ON"], ["OFF", "OFF"]
];

const BLOCKY_ROOT_TRIGGERS = new Set([
    "b_trig_device", "b_trig_or", "b_trig_event", "b_trig_family"
]);

/** Sensor / temp-class — excluded from pickers (motion is separate: trigger OK, never action). */
const BLOCKY_SENSOR_LIKE_TYPES = new Set([
    "sensor", "temp_hum", "temp", "hum", "power", "energy", "fluid"
]);

/** Types that can appear as action targets. */
const BLOCKY_ACTUATOR_TYPES = new Set([
    "switch", "light", "blinds", "shutter", "speaker", "media_player"
]);

function blockyEdgeShort(ev) {
    return BLOCKY_EDGE_SHORT[ev] || String(ev || "").replace(/_TRIGGER$/i, "").replace(/_/g, " ").toLowerCase();
}

function blockyScheduleWindowHint(fam) {
    const edges = BLOCKY_SCHEDULE_WINDOW_EDGES[fam];
    if (!edges) return "";
    const a = blockyEdgeShort(edges[0]);
    const b = blockyEdgeShort(edges[1]);
    if (fam === "blinds") {
        return `Fires twice: ${a} (clamped), then ${b} (clamped). Not raw sunrise/sunset.`;
    }
    if (fam === "twilight_morning" || fam === "twilight_evening") {
        return `Fires twice: at ${a}, then at ${b}. Not blinds open/close.`;
    }
    return `Fires twice: ${a}, then ${b}.`;
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
    if (opt && opt.type) return String(opt.type).toLowerCase();
    const e = String(eid || "");
    if (e.startsWith("blinds.")) return "blinds";
    if (e.startsWith("hue.")) return "light";
    if (e.startsWith("media_player.")) return "speaker";
    if (e.startsWith("sensor.door.") || e.startsWith("door.")) return "door";
    if (e.includes("motion")) return "motion";
    if (e.startsWith("sensor.")) return "sensor";
    if (e.startsWith("switch.")) return "switch";
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
    if (blockyIsMotionEntity(opt)) {
        // Motion OK as When-device trigger (garage/toilet); not as condition for now.
        return role === "trigger";
    }
    return !blockyIsSensorLikeEntity(opt);
}

function blockyCaseMatchOptions(caseBlock) {
    let opts;
    try {
        const root = caseBlock.getRootBlock && caseBlock.getRootBlock();
        if (root && root.type === "b_trig_family") {
            const fam = root.getFieldValue("FAMILY");
            const edges = BLOCKY_SCHEDULE_WINDOW_EDGES[fam];
            if (edges) {
                opts = [
                    [`at start (${blockyEdgeShort(edges[0])})`, "ON"],
                    [`at end (${blockyEdgeShort(edges[1])})`, "OFF"]
                ];
            }
        } else if (root && root.type === "b_trig_device") {
            const type = blockyEntityTypeOf(root.getFieldValue("ENTITY"));
            if (type === "blinds" || type === "shutter") {
                opts = [
                    ["when OPEN", "OPEN"],
                    ["when CLOSED", "CLOSED"]
                ];
            } else {
                opts = [
                    ["when ON", "ON"],
                    ["when OFF", "OFF"]
                ];
            }
        } else if (root && root.type === "b_trig_or") {
            opts = [["(conditions only)", "NONE"]];
        } else if (root && root.type === "b_trig_event") {
            opts = [["(run if conditions)", "NONE"]];
        }
    } catch (e) { /* ignore */ }
    if (!opts) {
        opts = [
            ["when ON", "ON"],
            ["when OFF", "OFF"]
        ];
    }
    return opts;
}

function blockyEdgeStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    if (type === "blinds" || type === "shutter") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"]];
    }
    return BLOCKY_EDGE_STATES.slice();
}

/**
 * Action state entries by device type.
 * Phase 6C: add Hue preset / Sonos volume+station / blinds open-% authoring (not just 0/100).
 * No “(legacy)” — stale values are coerced away.
 */
function blockyActionStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    if (type === "blinds" || type === "shutter") {
        // Stored = closed % (0 open … 100 closed). Open-% picker is Phase 6C.
        return [
            ["0 — open", "0"],
            ["100 — closed", "100"]
        ];
    }
    if (type === "light" || type === "hue") {
        // Phase 6C: when ON, show preset dropdown from hue_presets.
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    if (type === "speaker" || type === "media_player") {
        // Phase 6C: when ON, show volume + station (Sonos) fields.
        return [["ON", "ON"], ["OFF", "OFF"]];
    }
    // switch (and unknown actuators)
    return [
        ["ON", "ON"], ["OFF", "OFF"],
        ["FORCE_ON", "FORCE_ON"], ["FORCE_OFF", "FORCE_OFF"]
    ];
}

function blockyConditionStateOptions(block) {
    const type = blockyEntityTypeOf(block.getFieldValue("ENTITY"));
    if (type === "blinds" || type === "shutter") {
        return [["Open", "0"], ["Closed", "100"]];
    }
    if (type === "door") {
        return [["OPEN", "OPEN"], ["CLOSED", "CLOSED"]];
    }
    return [["ON", "ON"], ["OFF", "OFF"]];
}

function blockyCoerceFieldToOptions(block, fieldName, optionsFn) {
    try {
        const f = block.getField(fieldName);
        if (!f) return;
        const opts = optionsFn(block);
        const v = f.getValue();
        if (!opts.some((o) => o[1] === v)) {
            f.setValue(opts[0][1]);
        }
    } catch (e) { /* ignore */ }
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
        }
        cur = cur.getNextBlock ? cur.getNextBlock() : null;
    }
}

function defineBlockyBlocks(Blockly, providers) {
    const entityTriggerDd = providers.entityTrigger || providers.entity;
    const entityConditionDd = providers.entityCondition || providers.entity;
    const entityActionDd = providers.entityAction || providers.entity;
    const familyDd = providers.family;
    const eventDd = providers.event;

    Object.keys(Blockly.Blocks).forEach((t) => {
        if (t.startsWith("b_")) delete Blockly.Blocks[t];
    });

    Blockly.Blocks.b_trig_device = {
        init() {
            this.appendDummyInput()
                .appendField("When device")
                .appendField(new Blockly.FieldDropdown(entityTriggerDd), "ENTITY")
                .appendField("(use cases for ON/OFF)");
            this.setNextStatement(true, "Case");
            this.setColour(230);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move"
                || (ev.type === "change" && ev.name === "ENTITY"))) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_device_edge = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("When device")
                .appendField(new Blockly.FieldDropdown(entityTriggerDd), "ENTITY")
                .appendField("becomes")
                .appendField(new Blockly.FieldDropdown(() => blockyEdgeStateOptions(block)), "STATE");
            this.setPreviousStatement(true, "TrigEdge");
            this.setNextStatement(true, "TrigEdge");
            this.setColour(230);
            this.setTooltip("OR-list edge only — put inside “When any of”. For a single device use “When device” + cases.");
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && ev.type === "change" && ev.name === "ENTITY") {
                blockyCoerceFieldToOptions(this, "STATE", blockyEdgeStateOptions);
            }
        }
    };
    Blockly.Blocks.b_trig_event_edge = {
        init() {
            this.appendDummyInput()
                .appendField("When event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setPreviousStatement(true, "TrigEdge");
            this.setNextStatement(true, "TrigEdge");
            this.setColour(210);
            this.setTooltip("OR-list edge only — put inside “When any of”.");
        }
    };
    Blockly.Blocks.b_trig_or = {
        init() {
            this.appendDummyInput().appendField("When any of");
            this.appendStatementInput("EDGES").setCheck("TrigEdge");
            this.setNextStatement(true, "Case");
            this.setColour(220);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move")) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_event = {
        init() {
            this.appendDummyInput()
                .appendField("When event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setNextStatement(true, "Case");
            this.setColour(210);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "create" || ev.type === "move")) {
                blockyRefreshCaseMatchLabels(this.getNextBlock());
            }
        }
    };
    Blockly.Blocks.b_trig_family = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("When schedule (start→end)")
                .appendField(new Blockly.FieldDropdown(familyDd, (newVal) => {
                    block.updateScheduleHint_(newVal);
                    blockyRefreshCaseMatchLabels(block.getNextBlock());
                    return newVal;
                }), "FAMILY");
            this.appendDummyInput("HINT")
                .appendField(new Blockly.FieldLabel(""), "HINT");
            this.setNextStatement(true, "Case");
            this.setColour(210);
        },
        updateScheduleHint_(fam) {
            const hint = this.getField("HINT");
            if (!hint) return;
            hint.setValue(blockyScheduleWindowHint(fam || this.getFieldValue("FAMILY")));
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            // Keep hint + case labels in sync after load / move
            if (!ev || ev.type === "create" || ev.type === "move" || ev.type === "change") {
                this.updateScheduleHint_(this.getFieldValue("FAMILY"));
                if (ev && ev.type === "change" && ev.name === "FAMILY") {
                    blockyRefreshCaseMatchLabels(this.getNextBlock());
                }
            }
        }
    };

    Blockly.Blocks.b_case = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("if")
                .appendField(new Blockly.FieldDropdown(() => blockyCaseMatchOptions(block)), "MATCH");
            this.appendDummyInput().appendField("conditions");
            this.appendStatementInput("CONDS").setCheck("Condition");
            this.appendDummyInput().appendField("actions");
            this.appendStatementInput("ACTIONS").setCheck("Action");
            this.setPreviousStatement(true, "Case");
            this.setNextStatement(true, "Case");
            this.setColour(120);
            this.setInputsInline(false);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && (ev.type === "move" || ev.type === "create")) {
                blockyCoerceFieldToOptions(this, "MATCH", blockyCaseMatchOptions);
                const f = this.getField("MATCH");
                if (f) {
                    try {
                        const v = f.getValue();
                        f.setValue(v);
                        if (typeof f.forceRerender === "function") f.forceRerender();
                    } catch (e) { /* ignore */ }
                }
            }
        }
    };

    Blockly.Blocks.b_condition_device = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("if device")
                .appendField(new Blockly.FieldDropdown(entityConditionDd), "ENTITY")
                .appendField("is")
                .appendField(new Blockly.FieldDropdown(() => blockyConditionStateOptions(block)), "STATE");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && ev.type === "change" && ev.name === "ENTITY") {
                blockyCoerceFieldToOptions(this, "STATE", blockyConditionStateOptions);
            }
        }
    };
    Blockly.Blocks.b_condition_time = {
        init() {
            this.appendDummyInput()
                .appendField("if time is")
                .appendField(new Blockly.FieldDropdown([["dark", "dark"], ["light", "light"]]), "TOD");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
        }
    };
    Blockly.Blocks.b_action_device = {
        init() {
            const block = this;
            this.appendDummyInput()
                .appendField("set device")
                .appendField(new Blockly.FieldDropdown(entityActionDd), "ENTITY")
                .appendField("to")
                .appendField(new Blockly.FieldDropdown(() => blockyActionStateOptions(block)), "STATE");
            // Phase 6C: append preset / volume / station / open-% fields when entity type warrants it.
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
        },
        onchange(ev) {
            if (!this.workspace || this.isInFlyout) return;
            if (ev && ev.type === "change" && ev.name === "ENTITY") {
                blockyCoerceFieldToOptions(this, "STATE", blockyActionStateOptions);
            }
        }
    };
    Blockly.Blocks.b_action_event = {
        init() {
            this.appendDummyInput()
                .appendField("fire event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
        }
    };
}

function blockyToolboxDefinition(_presentTypes) {
    // Always offer triggers so operators can swap device ↔ event ↔ schedule (start→end).
    // Uniqueness keeps a single root and adopts the case chain onto the new trigger.
    const contents = [
        {
            kind: "category",
            name: "Trigger",
            colour: "#5C81A6",
            contents: [
                { kind: "block", type: "b_trig_device" },
                { kind: "block", type: "b_trig_or" },
                { kind: "block", type: "b_trig_event" },
                { kind: "block", type: "b_trig_family" }
            ]
        }
    ];
    // OR edges only snap inside “When any of” — hide the category otherwise.
    let showOrEdges = false;
    try {
        const ws = blockyWs();
        if (ws) {
            const roots = ws.getTopBlocks(false).filter((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
            showOrEdges = roots.some((b) => b.type === "b_trig_or");
        }
    } catch (e) { /* ignore */ }
    if (showOrEdges) {
        contents.push({
            kind: "category",
            name: "OR edges",
            colour: "#6B8CAE",
            contents: [
                { kind: "block", type: "b_trig_device_edge" },
                { kind: "block", type: "b_trig_event_edge" }
            ]
        });
    }
    contents.push(
        {
            kind: "category",
            name: "Cases",
            colour: "#5CA65C",
            contents: [{ kind: "block", type: "b_case" }]
        },
        {
            kind: "category",
            name: "Conditions",
            colour: "#A6745C",
            contents: [
                { kind: "block", type: "b_condition_device" },
                { kind: "block", type: "b_condition_time" }
            ]
        },
        {
            kind: "category",
            name: "Actions",
            colour: "#A65C81",
            contents: [
                { kind: "block", type: "b_action_device" },
                { kind: "block", type: "b_action_event" }
            ]
        }
    );
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
    app: null,
    richByEntity: {}
};

function blockyWs() {
    return BlockyRT.ws;
}

function blockyFingerprint(block) {
    if (!block) return "";
    const t = block.type;
    if (BLOCKY_ROOT_TRIGGERS.has(t)) return "trigger";
    try {
        if (t === "b_condition_device") {
            return `cond:device:${block.getFieldValue("ENTITY")}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_condition_time") return `cond:time:${block.getFieldValue("TOD")}`;
        if (t === "b_action_device") {
            return `act:device:${block.getFieldValue("ENTITY")}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_action_event") return `act:event:${block.getFieldValue("EVENT")}`;
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
}

function blockyMoveCaseChain(fromRoot, toRoot) {
    if (!fromRoot || !toRoot || fromRoot === toRoot) return;
    const firstCase = fromRoot.getNextBlock();
    if (!firstCase || firstCase.type !== "b_case") return;
    try {
        if (fromRoot.nextConnection && fromRoot.nextConnection.isConnected()) {
            fromRoot.nextConnection.disconnect();
        }
        if (toRoot.nextConnection && toRoot.nextConnection.isConnected()) {
            const existing = toRoot.getNextBlock();
            if (existing) {
                try { existing.dispose(false); } catch (e) { /* ignore */ }
            }
        }
        if (toRoot.nextConnection && firstCase.previousConnection) {
            toRoot.nextConnection.connect(firstCase.previousConnection);
        }
    } catch (e) { /* ignore */ }
}

function blockyEnforceUniqueness(forceToolbox) {
    const ws = blockyWs();
    if (BlockyRT.loading || BlockyRT.enforcing || !ws || !window.Blockly) return;
    BlockyRT.enforcing = true;
    const Events = Blockly.Events;
    const wasEnabled = Events.isEnabled();
    const fieldEv = BlockyRT.pendingFieldEv;
    BlockyRT.pendingFieldEv = null;
    let changed = !!forceToolbox;
    try {
        Events.disable();
        if (fieldEv && fieldEv.element === "field" && fieldEv.blockId) {
            const blk = ws.getBlockById(fieldEv.blockId);
            if (blk) {
                const fp = blockyFingerprint(blk);
                const other = fp && ws.getAllBlocks(false).find(
                    (b) => b.id !== blk.id && blockyFingerprint(b) === fp
                );
                if (other) {
                    try { blk.setFieldValue(fieldEv.oldValue, fieldEv.name); } catch (e) { /* ignore */ }
                    changed = true;
                }
            }
        }
        // Only one root trigger — keep the newly dragged one; move cases across
        const roots = ws.getTopBlocks(false).filter((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
        if (roots.length > 1) {
            let keep = roots[roots.length - 1];
            const preferId = BlockyRT.pendingCreateRootId;
            if (preferId) {
                const preferred = roots.find((b) => b.id === preferId);
                if (preferred) keep = preferred;
            }
            roots.forEach((b) => {
                if (b.id === keep.id) return;
                blockyMoveCaseChain(b, keep);
                try { b.dispose(false); changed = true; } catch (e) { /* ignore */ }
            });
            blockyRefreshCaseMatchLabels(keep.getNextBlock());
        }
        BlockyRT.pendingCreateRootId = null;
        const seen = new Map();
        const toDispose = [];
        ws.getAllBlocks(false).forEach((b) => {
            const fp = blockyFingerprint(b);
            if (!fp || fp === "trigger") return;
            const parent = b.getParent();
            const scope = parent ? parent.id : "top";
            const key = `${scope}::${fp}`;
            if (seen.has(key)) toDispose.push(b);
            else seen.set(key, b.id);
        });
        toDispose.forEach((b) => {
            try { b.dispose(false); changed = true; } catch (e) { /* ignore */ }
        });
    } finally {
        if (wasEnabled) Events.enable();
        if (!Events.isEnabled()) Events.enable();
        BlockyRT.enforcing = false;
        // Always refresh — OR-edges category depends on whether root is “When any of”.
        blockyRefreshToolbox();
    }
}

function blockyOnChange(ev) {
    if (BlockyRT.loading || !blockyWs() || !ev || ev.isUiEvent) return;
    const Events = Blockly.Events;
    const t = ev.type;
    const isCreate = t === Events.BLOCK_CREATE || t === "create";
    const isChange = (t === Events.BLOCK_CHANGE || t === "change") && ev.element === "field";
    const isMoveConnect = (t === Events.BLOCK_MOVE || t === "move") && !!ev.newParentId;
    const isDelete = t === Events.BLOCK_DELETE || t === "delete";
    if (!isCreate && !isChange && !isMoveConnect && !isDelete) return;
    if (isCreate) {
        const ws = blockyWs();
        const ids = ev.ids || (ev.blockId ? [ev.blockId] : []);
        ids.forEach((id) => {
            const b = ws && ws.getBlockById(id);
            if (b && BLOCKY_ROOT_TRIGGERS.has(b.type)) {
                BlockyRT.pendingCreateRootId = b.id;
            }
        });
    }
    if (isChange) BlockyRT.pendingFieldEv = ev;
    if (BlockyRT.uniquenessScheduled) return;
    BlockyRT.uniquenessScheduled = true;
    BlockyRT.uniquenessTimer = setTimeout(() => {
        BlockyRT.uniquenessScheduled = false;
        BlockyRT.uniquenessTimer = null;
        blockyEnforceUniqueness(false);
        if (BlockyRT.app) {
            BlockyRT.app.blocklyUiTick = (BlockyRT.app.blocklyUiTick || 0) + 1;
            if (!BlockyRT.app.canShowOnDashboard) {
                BlockyRT.app.editor.scene = false;
                BlockyRT.app.editor.require_confirmation = false;
            }
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
        if (BLOCKY_ROOT_TRIGGERS.has(b.type)) return false;
        if (b.type === "b_case") {
            const prev = b.previousConnection;
            return !b.getParent() && !(prev && prev.isConnected());
        }
        // trig edges may be inside OR
        if (b.type === "b_trig_device_edge" || b.type === "b_trig_event_edge") {
            const p = b.getParent();
            if (p && p.type === "b_trig_or") return false;
            return true; // must live inside “When any of”
        }
        if (b.type === "b_condition_device" || b.type === "b_condition_time"
            || b.type === "b_action_device" || b.type === "b_action_event") {
            return !b.getParent();
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

function blockyApp() {
    return {
        connected: false,
        busy: false,
        errorMessage: "",
        infoMessage: "",
        registryCheckMessage: "",
        registryCheckOk: null,
        filterText: "",
        automations: [],
        selectedRule: null,
        entityOptions: [],
        showHiddenEntities: false,
        editorMode: "blockly",
        blocklyFullscreen: false,
            blocklySchemaVersion: 30,
        blocklyUiTick: 0,
        eventFamilies: ["blinds", "twilight_evening", "twilight_morning", "sauna", "ir", "cinema"],
        eventFamilyLabels: {
            blinds: "Blinds",
            twilight_evening: "Twilight evening",
            twilight_morning: "Twilight morning",
            sauna: "Sauna",
            ir: "IR",
            cinema: "Cinema"
        },
        curatedEvents: [
            "BLINDS_OPEN_TRIGGER", "BLINDS_CLOSE_TRIGGER",
            "MORNING_ON_TRIGGER", "SUNRISE_TRIGGER",
            "SUNSET_TRIGGER", "EVENING_OFF_TRIGGER",
            "SAUNA_ON", "SAUNA_OFF", "IR_ON", "IR_OFF",
            "SCENE_CINEMA_ON", "SCENE_CINEMA_OFF", "SCENE_ALL_OFF", "SCENE_GOCOSY",
            "SCENE_GV_OFF", "SCENE_VERDIEP1_OFF", "SCENE_VERDIEP2_OFF"
        ],
        hardDenyPrefixes: [
            "switch.safety.", "switch.ssr.",
            "sensor.generic.host_", "sensor.temp_hum.host_", "sensor.generic.wanos_db_size"
        ],
        editor: {
            id: "",
            name: "",
            scene: false,
            require_confirmation: false,
            ruleJson: "{}"
        },

        get filteredRules() {
            const q = this.filterText.trim().toLowerCase();
            if (!q) return this.automations;
            return this.automations.filter((r) => {
                const name = (r.name || "").toLowerCase();
                const id = String(r.id || "").toLowerCase();
                return name.includes(q) || id.includes(q);
            });
        },

        get visibleEntityOptions() {
            return this.entityOptions.filter((opt) => this.showHiddenEntities || !opt.softHidden);
        },

        get showBlocklyWorkspace() {
            return !!(this.selectedRule && this.editorMode === "blockly");
        },

        /** Dashboard scenes need an event trigger (device rules cannot appear as buttons). */
        triggerAllowsDashboard(trigger) {
            if (!trigger) return false;
            if (Array.isArray(trigger)) {
                if (!trigger.length) return false;
                return trigger.every((t) => t && t.event && !t.entity_id);
            }
            return !!(trigger.event && !trigger.entity_id);
        },

        get canShowOnDashboard() {
            void this.blocklyUiTick;
            if (this.editorMode === "blockly" && blockyWs()) {
                try {
                    const root = blockyWs().getTopBlocks(false).find((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
                    if (root) {
                        if (root.type === "b_trig_event" || root.type === "b_trig_family") return true;
                        if (root.type === "b_trig_or") {
                            let e = root.getInputTargetBlock("EDGES");
                            let hasEvent = false;
                            let hasDevice = false;
                            while (e) {
                                if (e.type === "b_trig_event_edge") hasEvent = true;
                                if (e.type === "b_trig_device_edge") hasDevice = true;
                                e = e.getNextBlock();
                            }
                            return hasEvent && !hasDevice;
                        }
                        return false;
                    }
                } catch (e) { /* ignore */ }
            }
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                return this.triggerAllowsDashboard(rule.trigger);
            } catch (e) {
                return false;
            }
        },

        ruleListKind(rule) {
            if (!rule || rule.isDraft) return "new";
            if (rule.scene) return "dashboard";
            const cases = rule.cases || [];
            if (cases.length >= 2) return "multi-case";
            let t = rule.trigger;
            // Singleton list is not a real OR (legacy YAML style)
            if (Array.isArray(t) && t.length === 1) t = t[0];
            if (Array.isArray(t)) return "or-trigger";
            if (t && t.event && this.eventFamilies.includes(t.event)) return "window";
            if (t && t.event) return "event";
            if (cases.some((c) => c && (c.to_state === "ON" || c.to_state === "OFF"))) return "edged";
            if (t && (t.state === "ON" || t.state === "OFF")) return "edged";
            return "rule";
        },

        ruleListBadgeClass(rule) {
            const k = this.ruleListKind(rule);
            if (k === "dashboard") return "badge-secondary";
            if (k === "multi-case" || k === "window" || k === "edged") return "badge-success";
            if (k === "or-trigger") return "badge-accent";
            if (k === "event") return "badge-warning";
            if (k === "new") return "badge-ghost";
            return "badge-info";
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
                blinds: "blinds", switch: "switch", light: "light", hue: "light",
                scene: "scene", motion: "motion"
            };
            return map[t] || t || "device";
        },

        entityDisplayLabel(opt) {
            if (opt && opt.typeLabel) return `${opt.name} · ${opt.typeLabel}`;
            return `${opt.name} · ${this.deviceTypeLabel(opt.type, opt.origin, opt.idx)}`;
        },

        eventFamilyLabel(fam) {
            return this.eventFamilyLabels[fam] || fam;
        },

        onEditorModeChanged() {
            this.blocklyFullscreen = false;
            if (this.editorMode === "json") {
                try {
                    if (blockyWs()) this.applyBlocklyToV2();
                } catch (e) { /* keep existing ruleJson if canvas incomplete */ }
                return;
            }
            this.scheduleBlocklyLoad();
        },

        blocklyHostReady() {
            const host = document.getElementById("blocklyWorkspace");
            if (!host) return null;
            if ((host.offsetWidth || 0) < 50 || (host.offsetHeight || 0) < 50) return null;
            return host;
        },

        resizeBlockly() {
            const ws = blockyWs();
            if (!ws || !window.Blockly) return;
            const host = this.blocklyHostReady();
            if (!host) return;
            try {
                const inj = host.querySelector(".injectionDiv");
                if (inj) {
                    inj.style.position = "absolute";
                    inj.style.left = "0";
                    inj.style.top = "0";
                    inj.style.right = "0";
                    inj.style.bottom = "0";
                    inj.style.width = "100%";
                    inj.style.height = "100%";
                }
                Blockly.svgResize(ws);
                if (ws.scrollbar && typeof ws.scrollbar.resize === "function") ws.scrollbar.resize();
            } catch (e) { /* ignore */ }
        },

        observeBlocklyHost(host) {
            if (BlockyRT.resizeObserver) BlockyRT.resizeObserver.disconnect();
            if (typeof ResizeObserver !== "undefined") {
                BlockyRT.resizeObserver = new ResizeObserver(() => this.resizeBlockly());
                BlockyRT.resizeObserver.observe(host);
            }
            if (!BlockyRT.windowResize) {
                BlockyRT.windowResize = () => this.resizeBlockly();
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
            requestAnimationFrame(() => requestAnimationFrame(() => this.resizeBlockly()));
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

        isHardDeniedEntityId(eid) {
            if (!eid) return false;
            const v = String(eid);
            return this.hardDenyPrefixes.some((p) => v.startsWith(p));
        },

        rebuildEntityOptions(deviceMetadata, _automations) {
            const opts = [];
            for (const [idx, meta] of Object.entries(deviceMetadata || {})) {
                if (!meta || typeof meta !== "object") continue;
                const eid = meta.entity_id ? String(meta.entity_id) : "";
                if (!eid || this.isHardDeniedEntityId(eid)) continue;
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
                    typeLabel,
                    // Honor Explorer soft-hide; do not auto-unhide just because another rule references it.
                    // Open-rule eids are re-added in blocklyEntityDropdownOptions for round-trip.
                    softHidden: Boolean(meta.hidden)
                });
            }
            opts.sort((a, b) => a.name.localeCompare(b.name));
            this.entityOptions = opts;
        },

        firstEntityId(role = "trigger") {
            const opts = this.blocklyEntityDropdownOptions({ role });
            const first = opts.find((o) => o[1]);
            return first ? first[1] : "";
        },

        /**
         * role: "trigger" | "condition" | "action"
         * Sensors/temp excluded; motion OK as trigger only; actions = actuators only.
         * Round-trip guarantee is role-scoped — action eids must not leak into When-device.
         */
        blocklyEntityDropdownOptions(optsIn) {
            const role = (optsIn && optsIn.role) || "action";
            const base = this.visibleEntityOptions.filter((o) => blockyEntityAllowedForRole(o, role));
            const opts = base.map((o) => [this.entityDisplayLabel(o), o.eid]);
            const seen = new Set(opts.map((o) => o[1]));
            const add = (eid) => {
                if (!eid || seen.has(eid) || this.isHardDeniedEntityId(eid)) return;
                // Always include open-rule eids for this role (soft-hidden / motion / etc.)
                // so Blockly setFieldValue does not fall back to the first catalog entry.
                seen.add(eid);
                const meta = (this.entityOptions || []).find((o) => o.eid === eid);
                if (meta) {
                    opts.push([this.entityDisplayLabel(meta), eid]);
                } else {
                    opts.push([`${eid} · (missing metadata)`, eid]);
                }
            };
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                this._ruleEntityIdsForRole(rule, role).forEach(add);
            } catch (e) { /* ignore */ }
            return opts.length ? opts : [["(no entities)", ""]];
        },

        /** Only eids that belong in this picker role (prevents action→trigger leak). */
        _ruleEntityIdsForRole(rule, role) {
            const out = [];
            const push = (eid) => {
                if (eid) out.push(String(eid));
            };
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

        blocklyEventDropdownOptions() {
            const opts = this.curatedEvents.map((e) => [e, e]);
            const seen = new Set(this.curatedEvents);
            try {
                const rule = JSON.parse(this.editor.ruleJson || "{}");
                const addEv = (ev) => {
                    if (!ev || seen.has(ev)) return;
                    seen.add(ev);
                    opts.push([ev, ev]);
                };
                const t = rule.trigger;
                if (Array.isArray(t)) t.forEach((x) => x && addEv(x.event));
                else if (t) addEv(t.event);
            } catch (e) { /* ignore */ }
            return opts;
        },

        blocklyEventFamilyDropdownOptions() {
            return this.eventFamilies.map((f) => [this.eventFamilyLabel(f), f]);
        },

        /** Unwrap singleton trigger lists (legacy YAML often uses a 1-item list). */
        _canonicalTrigger(trigger) {
            if (Array.isArray(trigger) && trigger.length === 1) {
                return trigger[0];
            }
            return trigger;
        },

        _mkTriggerRoot(trigger, cases) {
            const t = this._canonicalTrigger(trigger);

            if (Array.isArray(t) && t.length) {
                const allDevices = t.every((x) => x && x.entity_id);
                const allEvents = t.every((x) => x && x.event && !x.entity_id);
                if (allEvents) {
                    // Multi-event OR: use event-edge blocks inside OR
                    const root = blockyMkBlock("b_trig_or", null, 16, 16);
                    const edges = t.map((edge) => blockyMkBlock("b_trig_event_edge", {
                        EVENT: edge.event
                    }));
                    blockyConnectChain(root, "EDGES", edges);
                    return root;
                }
                if (!allDevices) {
                    const first = t[0] || {};
                    if (first.event || first.entity_id) {
                        return this._mkTriggerRoot(first, cases);
                    }
                    return blockyMkBlock("b_trig_device", { ENTITY: this.firstEntityId() }, 16, 16);
                }
                const root = blockyMkBlock("b_trig_or", null, 16, 16);
                const edges = t.map((edge) => blockyMkBlock("b_trig_device_edge", {
                    ENTITY: edge.entity_id || this.firstEntityId(),
                    STATE: edge.state || "ON"
                }));
                blockyConnectChain(root, "EDGES", edges);
                return root;
            }

            if (t && t.entity_id && (t.state === "ON" || t.state === "OFF")) {
                // Legacy edge-on-trigger → device wake; put edge into cases
                if (!cases.length) {
                    cases.push({ to_state: t.state, actions: [] });
                } else if (cases.length === 1 && !cases[0].to_state) {
                    cases[0].to_state = t.state;
                }
                return blockyMkBlock("b_trig_device", {
                    ENTITY: t.entity_id
                }, 16, 16);
            }
            if (t && t.entity_id) {
                return blockyMkBlock("b_trig_device", {
                    ENTITY: t.entity_id
                }, 16, 16);
            }
            if (t && t.event && this.eventFamilies.includes(t.event)) {
                return blockyMkBlock("b_trig_family", { FAMILY: t.event }, 16, 16);
            }
            if (t && t.event) {
                return blockyMkBlock("b_trig_event", { EVENT: t.event }, 16, 16);
            }
            return blockyMkBlock("b_trig_device", {
                ENTITY: this.firstEntityId()
            }, 16, 16);
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
                family: () => (BlockyRT.app || this).blocklyEventFamilyDropdownOptions(),
                event: () => (BlockyRT.app || this).blocklyEventDropdownOptions()
            });
            BlockyRT.ws = Blockly.inject(host, {
                toolbox: blockyToolboxDefinition(new Set()),
                trashcan: true,
                scrollbars: true,
                move: { scrollbars: true, drag: true, wheel: true },
                zoom: { controls: true, wheel: false, startScale: 1.0 }
            });
            BlockyRT.ws.addChangeListener(blockyOnChange);
            BlockyRT.ready = true;
            BlockyRT.schemaInjected = this.blocklySchemaVersion;
            this.observeBlocklyHost(host);
            Blockly.svgResize(BlockyRT.ws);
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
            return (list || []).map((c) => {
                if (c.type === "time_of_day") {
                    return blockyMkBlock("b_condition_time", { TOD: c.is || "dark" });
                }
                return blockyMkBlock("b_condition_device", {
                    ENTITY: c.entity_id || this.firstEntityId("condition"),
                    STATE: c.is || "ON"
                });
            });
        },

        _actionBlocks(list) {
            return (list || []).map((a) => {
                if (a.event && !a.entity_id) {
                    return blockyMkBlock("b_action_event", { EVENT: a.event });
                }
                if (a.entity_id) {
                    // Phase 6C: move rich fields onto the action block (keyed by entity alone can collide).
                    BlockyRT.richByEntity[a.entity_id] = {
                        preset: a.preset || "",
                        bri: a.bri ?? "",
                        xy: Array.isArray(a.xy) ? JSON.stringify(a.xy) : (a.xy || ""),
                        volume: a.volume ?? "",
                        station: a.station || ""
                    };
                }
                return blockyMkBlock("b_action_device", {
                    ENTITY: a.entity_id || this.firstEntityId("action"),
                    STATE: a.state || "ON"
                });
            });
        },

        _caseBlocks(cases) {
            return (cases || []).map((c) => {
                const match = (
                    c.to_state === "ON" || c.to_state === "OFF"
                    || c.to_state === "OPEN" || c.to_state === "CLOSED"
                ) ? c.to_state : "NONE";
                const blk = blockyMkBlock("b_case", { MATCH: match });
                blockyConnectChain(blk, "CONDS", this._conditionBlocks(c.conditions));
                blockyConnectChain(blk, "ACTIONS", this._actionBlocks(c.actions));
                return blk;
            });
        },

        loadV2IntoBlockly() {
            if (!this.ensureBlocklyReady()) return;
            blockyCancelUniqueness();
            BlockyRT.loading = true;
            BlockyRT.richByEntity = {};
            const Events = Blockly.Events;
            const wasEnabled = Events.isEnabled();
            try {
                Events.disable();
                const ws = blockyWs();
                ws.clear();

                let rule;
                try {
                    rule = JSON.parse(this.editor.ruleJson || "{}");
                } catch (e) {
                    rule = { cases: [], trigger: {} };
                }
                const cases = rule.cases || [];
                const root = this._mkTriggerRoot(rule.trigger, cases);

                const caseBlocks = this._caseBlocks(cases.length ? cases : [{ actions: [] }]);
                if (root && caseBlocks.length) {
                    if (root.nextConnection && caseBlocks[0].previousConnection) {
                        try {
                            root.nextConnection.connect(caseBlocks[0].previousConnection);
                        } catch (e) { /* ignore */ }
                        blockyConnectNext(caseBlocks[0], caseBlocks.slice(1));
                    }
                }

                if (root && root.type === "b_trig_family" && typeof root.updateScheduleHint_ === "function") {
                    root.updateScheduleHint_(root.getFieldValue("FAMILY"));
                    blockyRefreshCaseMatchLabels(root.getNextBlock());
                } else if (root) {
                    blockyRefreshCaseMatchLabels(root.getNextBlock());
                }

                // Coerce action/condition STATE to type-valid options after load.
                ws.getAllBlocks(false).forEach((b) => {
                    if (b.type === "b_action_device") {
                        blockyCoerceFieldToOptions(b, "STATE", blockyActionStateOptions);
                    } else if (b.type === "b_condition_device") {
                        blockyCoerceFieldToOptions(b, "STATE", blockyConditionStateOptions);
                    } else if (b.type === "b_case") {
                        blockyCoerceFieldToOptions(b, "MATCH", blockyCaseMatchOptions);
                    }
                });

                if (ws.render) ws.render();
                this.resizeBlockly();
                this.scrollBlocklyToTopLeft();
                blockyRefreshToolbox();
                requestAnimationFrame(() => {
                    this.resizeBlockly();
                    requestAnimationFrame(() => this.resizeBlockly());
                });
            } finally {
                if (wasEnabled) Events.enable();
                if (!Events.isEnabled()) Events.enable();
                BlockyRT.loading = false;
            }
        },

        _readConditions(start) {
            return blockyReadChain(start, (b) => {
                if (b.type === "b_condition_time") return { type: "time_of_day", is: b.getFieldValue("TOD") };
                return {
                    type: "device_state",
                    entity_id: b.getFieldValue("ENTITY"),
                    is: b.getFieldValue("STATE")
                };
            });
        },

        _readActions(start) {
            return blockyReadChain(start, (b) => {
                if (b.type === "b_action_event") return { event: b.getFieldValue("EVENT") };
                const entity = b.getFieldValue("ENTITY");
                const rich = BlockyRT.richByEntity[entity] || {};
                const out = {
                    entity_id: entity,
                    state: b.getFieldValue("STATE")
                };
                if (rich.preset) out.preset = rich.preset;
                if (rich.station) out.station = rich.station;
                if (rich.bri !== "" && rich.bri != null) {
                    const n = Number(rich.bri);
                    if (!Number.isNaN(n)) out.bri = n;
                }
                if (rich.volume !== "" && rich.volume != null) {
                    const n = Number(rich.volume);
                    if (!Number.isNaN(n)) out.volume = n;
                }
                if (rich.xy) {
                    try {
                        const xy = JSON.parse(String(rich.xy));
                        if (Array.isArray(xy)) out.xy = xy;
                    } catch (e) { /* ignore */ }
                }
                return out;
            });
        },

        applyBlocklyToV2() {
            this.ensureBlocklyReady();
            const ws = blockyWs();
            if (!ws) throw new Error("Blockly workspace not ready.");
            blockyAssertNoOrphans(ws);
            const tops = ws.getTopBlocks(true);
            const root = tops.find((b) => BLOCKY_ROOT_TRIGGERS.has(b.type));
            if (!root) throw new Error("Blockly requires one trigger block.");

            let trigger;
            let caseStart = root.getNextBlock();

            if (root.type === "b_trig_or") {
                const edges = [];
                let e = root.getInputTargetBlock("EDGES");
                while (e) {
                    if (e.type === "b_trig_device_edge") {
                        edges.push({
                            entity_id: e.getFieldValue("ENTITY"),
                            state: e.getFieldValue("STATE")
                        });
                    } else if (e.type === "b_trig_event_edge") {
                        edges.push({ event: e.getFieldValue("EVENT") });
                    } else {
                        throw new Error("OR trigger only accepts device or event edges.");
                    }
                    e = e.getNextBlock();
                }
                if (!edges.length) throw new Error("OR trigger needs at least one edge.");
                trigger = edges.length === 1 ? edges[0] : edges;
            } else if (root.type === "b_trig_device") {
                trigger = { entity_id: root.getFieldValue("ENTITY") };
            } else if (root.type === "b_trig_family") {
                trigger = { event: root.getFieldValue("FAMILY") };
            } else if (root.type === "b_trig_event") {
                trigger = { event: root.getFieldValue("EVENT") };
            } else {
                throw new Error("Unsupported trigger block. Use When device / event / schedule (start→end) / When any of.");
            }

            const cases = [];
            let cur = caseStart;
            // Event / OR: MATCH is conditions-gate only — never persist to_state from a stale ON/OFF.
            const matchWritesToState = root.type === "b_trig_device" || root.type === "b_trig_family";
            while (cur && cur.type === "b_case") {
                const match = cur.getFieldValue("MATCH");
                const conds = this._readConditions(cur.getInputTargetBlock("CONDS"));
                const acts = this._readActions(cur.getInputTargetBlock("ACTIONS"));
                if (!acts.length) throw new Error("Each case needs at least one action.");
                const c = { actions: acts };
                if (matchWritesToState && (match === "ON" || match === "OFF"
                    || match === "OPEN" || match === "CLOSED")) {
                    c.to_state = match;
                }
                if (conds.length) c.conditions = conds;
                cases.push(c);
                cur = cur.getNextBlock();
            }

            if (!cases.length) throw new Error("Add at least one case with actions.");

            const sceneOk = this.triggerAllowsDashboard(trigger);
            if (!sceneOk) {
                this.editor.scene = false;
                this.editor.require_confirmation = false;
            }
            const payload = {
                id: this.editor.id || undefined,
                name: (this.editor.name || "").trim(),
                scene: sceneOk && !!this.editor.scene,
                require_confirmation: sceneOk && !!this.editor.require_confirmation,
                trigger,
                cases
            };
            if (!payload.name) throw new Error("Rule name is required.");
            this.validateNoHardDeniedEntityIds(payload);
            this.editor.ruleJson = JSON.stringify(payload, null, 2);
            return payload;
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

        buildPayloadFromEditor() {
            if (this.editorMode === "blockly") {
                return this.applyBlocklyToV2();
            }
            let rule;
            try {
                rule = JSON.parse(this.editor.ruleJson || "{}");
            } catch (e) {
                throw new Error(`Rule JSON invalid (${e})`);
            }
            rule.id = this.editor.id || rule.id;
            rule.name = (this.editor.name || "").trim();
            const sceneOk = this.triggerAllowsDashboard(rule.trigger);
            rule.scene = sceneOk && !!this.editor.scene;
            rule.require_confirmation = sceneOk && !!this.editor.require_confirmation;
            if (!sceneOk) {
                this.editor.scene = false;
                this.editor.require_confirmation = false;
            }
            if (!rule.name) throw new Error("Rule name is required.");
            if (!Array.isArray(rule.cases) || !rule.cases.length) {
                throw new Error("v2 rule requires cases[].");
            }
            this.validateNoHardDeniedEntityIds(rule);
            return rule;
        },

        blankEditor() {
            return {
                id: "",
                name: "",
                scene: false,
                require_confirmation: false,
                ruleJson: JSON.stringify({
                    trigger: { entity_id: this.firstEntityId("trigger") },
                    cases: [{ to_state: "ON", actions: [{ entity_id: this.firstEntityId("action"), state: "ON" }] }]
                }, null, 2)
            };
        },

        newRule() {
            this.selectedRule = { isDraft: true };
            this.editor = this.blankEditor();
            this.editorMode = "blockly";
            this.errorMessage = "";
            this.infoMessage = "";
            this.scheduleBlocklyLoad();
        },

        selectRule(rule) {
            this.selectedRule = rule;
            this.errorMessage = "";
            this.infoMessage = "";
            const sceneOk = this.triggerAllowsDashboard(rule.trigger);
            this.editor = {
                id: rule.id || "",
                name: rule.name || "",
                scene: sceneOk && !!rule.scene,
                require_confirmation: sceneOk && !!rule.require_confirmation,
                ruleJson: JSON.stringify({
                    id: rule.id,
                    name: rule.name,
                    scene: sceneOk && !!rule.scene,
                    require_confirmation: sceneOk && !!rule.require_confirmation,
                    trigger: rule.trigger,
                    cases: rule.cases || []
                }, null, 2)
            };
            this.editorMode = "blockly";
            this.blocklyUiTick = (this.blocklyUiTick || 0) + 1;
            blockyCancelUniqueness();
            this.scheduleBlocklyLoad();
        },

        async refreshAll() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            try {
                const [stateRes, rulesRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/automations", { headers: this.getAuthHeaders() })
                ]);
                if (!stateRes.ok) throw new Error(`Failed /api/state (${stateRes.status})`);
                if (!rulesRes.ok) throw new Error(`Failed /api/automations (${rulesRes.status})`);
                const state = await stateRes.json();
                const rulesPayload = await rulesRes.json();
                this.automations = (rulesPayload.automations || []).filter((r) => r && typeof r === "object");
                this.rebuildEntityOptions(state.device_metadata || {}, this.automations);
                if (this.selectedRule && this.selectedRule.id) {
                    const fresh = this.automations.find((r) => r.id === this.selectedRule.id);
                    if (fresh) this.selectRule(fresh);
                }
                if (this.showBlocklyWorkspace) this.scheduleBlocklyLoad();
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async runPostWriteRegistryCheck() {
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const res = await fetch("/api/debug/entity-registry-check", {
                    headers: this.getAuthHeaders()
                });
                const report = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.registryCheckOk = false;
                    this.registryCheckMessage =
                        `Admin Debug check failed: ${report.error || res.status}. Open Admin → Debug.`;
                    return;
                }
                const errN = (report.errors || []).length;
                const warnN = (report.warnings || []).length;
                this.registryCheckOk = !!report.ok;
                this.registryCheckMessage = report.ok
                    ? (warnN
                        ? `Admin Debug GREEN — entity_id / registry check passed (${warnN} non-blocking warning(s)).`
                        : "Admin Debug GREEN — entity_id / registry check passed (not a behavior smoke test).")
                    : `Admin Debug RED — ${errN} error(s), ${warnN} warning(s). Open Admin → Debug for the full report.`;
            } catch (e) {
                this.registryCheckOk = false;
                this.registryCheckMessage = `Admin Debug check request failed: ${e}. Open Admin → Debug.`;
            }
        },

        async saveRule() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            this.registryCheckMessage = "";
            this.registryCheckOk = null;
            try {
                const payload = this.buildPayloadFromEditor();
                const isUpdate = !!payload.id && this.automations.some((r) => r.id === payload.id);
                const method = isUpdate ? "PUT" : "POST";
                const res = await fetch("/api/automations", {
                    method,
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `${method} failed (${res.status})`);
                this.infoMessage = isUpdate
                    ? "Automation updated (hot-reload queued)."
                    : "Automation created (hot-reload queued).";
                await this.refreshAll();
                const rid = (body.automation && body.automation.id) || payload.id;
                if (rid) {
                    const fresh = this.automations.find((r) => r.id === rid);
                    if (fresh) this.selectRule(fresh);
                }
                await this.runPostWriteRegistryCheck();
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async deleteRule() {
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
                this.infoMessage = "Automation deleted (hot-reload queued).";
                await this.refreshAll();
                this.newRule();
                await this.runPostWriteRegistryCheck();
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async init() {
            BlockyRT.app = this;
            const token = localStorage.getItem("wanos_jwt") || "";
            if (!token) {
                window.location.href = "/login.html";
                return;
            }
            if (!this.isAdminToken(token)) {
                window.location.href = "/deviceexplorer.html";
                return;
            }
            await this.refreshAll();
            this.connected = true;
        }
    };
}
