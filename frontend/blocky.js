// --- file: frontend/blocky.js ---

const BLOCKY_BLOCK_TYPES = [
    "b_trigger_device", "b_trigger_event", "b_trigger_curated_event", "b_trigger_device_state",
    "b_then_do", "b_branch_on", "b_branch_off",
    "b_condition_device", "b_condition_time", "b_action_device", "b_action_event"
];

const BLOCKY_ACTION_STATES = [
    ["ON", "ON"], ["OFF", "OFF"], ["SYNC", "SYNC"], ["SYNCOPPOSITE", "SYNCOPPOSITE"],
    ["FORCE_ON", "FORCE_ON"], ["FORCE_OFF", "FORCE_OFF"], ["0", "0"], ["100", "100"]
];

/**
 * Defines every Blocky block on the given Blockly instance.
 * `providers` supplies the dynamic dropdown option callbacks: entity, family, event.
 * Kept top-level (outside the Alpine component) so it can be exercised by a harness.
 */
function defineBlockyBlocks(Blockly, providers) {
    const entityDd = providers.entity;
    const familyDd = providers.family;
    const eventDd = providers.event;

    BLOCKY_BLOCK_TYPES.forEach((t) => { delete Blockly.Blocks[t]; });

    Blockly.Blocks.b_trigger_device = {
        init() {
            this.appendDummyInput()
                .appendField("When device")
                .appendField(new Blockly.FieldDropdown(entityDd), "ENTITY")
                .appendField("(ON / OFF branches)");
            this.setColour(230);
        }
    };
    Blockly.Blocks.b_trigger_event = {
        init() {
            this.appendDummyInput()
                .appendField("When event")
                .appendField(new Blockly.FieldDropdown(familyDd), "FAMILY")
                .appendField("(paired ON / OFF)");
            this.setColour(210);
        }
    };
    Blockly.Blocks.b_trigger_curated_event = {
        init() {
            this.appendDummyInput()
                .appendField("When event")
                .appendField(new Blockly.FieldDropdown(eventDd), "EVENT");
            this.setColour(210);
        }
    };
    Blockly.Blocks.b_trigger_device_state = {
        init() {
            this.appendDummyInput()
                .appendField("When device")
                .appendField(new Blockly.FieldDropdown(entityDd), "ENTITY")
                .appendField("becomes")
                .appendField(new Blockly.FieldDropdown([["ON", "ON"], ["OFF", "OFF"]]), "STATE");
            this.setColour(230);
        }
    };

    // Each statement input sits alone on its row so the C-notch is a large, unambiguous
    // drop target. Typed checks keep conditions out of the actions slot and vice versa.
    const makeContainerBlock = (title, colour) => ({
        init() {
            this.appendDummyInput().appendField(title);
            this.appendDummyInput().appendField("conditions");
            this.appendStatementInput("CONDS").setCheck("Condition");
            this.appendDummyInput().appendField("actions");
            this.appendStatementInput("ACTIONS").setCheck("Action");
            this.setColour(colour);
            this.setInputsInline(false);
        }
    });
    Blockly.Blocks.b_branch_on = makeContainerBlock("ON branch", 120);
    Blockly.Blocks.b_branch_off = makeContainerBlock("OFF branch", 20);
    Blockly.Blocks.b_then_do = makeContainerBlock("Then", 160);

    Blockly.Blocks.b_condition_device = {
        init() {
            this.appendDummyInput()
                .appendField("if device")
                .appendField(new Blockly.FieldDropdown(entityDd), "ENTITY")
                .appendField("is")
                .appendField(new Blockly.FieldDropdown([["ON", "ON"], ["OFF", "OFF"]]), "STATE");
            this.setPreviousStatement(true, "Condition");
            this.setNextStatement(true, "Condition");
            this.setColour(60);
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
            this.appendDummyInput()
                .appendField("set device")
                .appendField(new Blockly.FieldDropdown(entityDd), "ENTITY")
                .appendField("to")
                .appendField(new Blockly.FieldDropdown(BLOCKY_ACTION_STATES), "STATE");
            this.setPreviousStatement(true, "Action");
            this.setNextStatement(true, "Action");
            this.setColour(290);
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

function blockyToolboxDefinition(presentTypes) {
    const present = presentTypes || new Set();
    const hasTrigger = ["b_trigger_device", "b_trigger_device_state", "b_trigger_event", "b_trigger_curated_event"]
        .some((t) => present.has(t));
    const deviceTriggers = hasTrigger ? [] : [
        { kind: "block", type: "b_trigger_device" },
        { kind: "block", type: "b_trigger_device_state" }
    ];
    const eventTriggers = hasTrigger ? [] : [
        { kind: "block", type: "b_trigger_event" },
        { kind: "block", type: "b_trigger_curated_event" }
    ];
    const branches = [];
    if (!present.has("b_branch_on")) branches.push({ kind: "block", type: "b_branch_on" });
    if (!present.has("b_branch_off")) branches.push({ kind: "block", type: "b_branch_off" });
    if (!present.has("b_then_do")) branches.push({ kind: "block", type: "b_then_do" });

    const contents = [];
    if (deviceTriggers.length) contents.push({ kind: "category", name: "Device", colour: "#5C81A6", contents: deviceTriggers });
    if (eventTriggers.length) contents.push({ kind: "category", name: "Event", colour: "#5C81A6", contents: eventTriggers });
    if (branches.length) contents.push({ kind: "category", name: "Branches", colour: "#5CA65C", contents: branches });
    contents.push({ kind: "category", name: "Conditions", colour: "#A6745C", contents: [
        { kind: "block", type: "b_condition_device" },
        { kind: "block", type: "b_condition_time" }
    ] });
    contents.push({ kind: "category", name: "Actions", colour: "#A65C81", contents: [
        { kind: "block", type: "b_action_device" },
        { kind: "block", type: "b_action_event" }
    ] });
    return { kind: "categoryToolbox", contents };
}

/**
 * Blockly workspace MUST stay outside Alpine's reactive proxy.
 * Storing WorkspaceSvg on Alpine `data` wraps it in a Proxy and breaks
 * drag, selection, and snapping (the minimal test page works because it
 * keeps a plain `const ws` reference — same pattern here).
 */
const BlockyRT = {
    ws: null,
    ready: false,
    schemaInjected: null,
    loading: false,
    enforcing: false,
    uniquenessScheduled: false,
    uniquenessTimer: null,
    pendingFieldEv: null,
    resizeObserver: null,
    app: null
};

function blockyWs() {
    return BlockyRT.ws;
}

function blockyFingerprint(block) {
    if (!block) return "";
    const t = block.type;
    if (t === "b_trigger_device" || t === "b_trigger_device_state"
        || t === "b_trigger_event" || t === "b_trigger_curated_event") return "trigger";
    if (t === "b_branch_on") return "branch:on";
    if (t === "b_branch_off") return "branch:off";
    if (t === "b_then_do") return "branch:then";
    try {
        if (t === "b_condition_device") {
            return `cond:device:${block.getFieldValue("ENTITY")}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_condition_time") return `cond:time:${block.getFieldValue("TOD")}`;
        if (t === "b_action_device") {
            return `act:device:${block.getFieldValue("ENTITY")}:${block.getFieldValue("STATE")}`;
        }
        if (t === "b_action_event") return `act:event:${block.getFieldValue("EVENT")}`;
    } catch (e) {
        return "";
    }
    return "";
}

function blockyRefreshToolbox() {
    const ws = blockyWs();
    if (!ws) return;
    const present = new Set(ws.getAllBlocks(false).map((b) => b.type));
    try { ws.updateToolbox(blockyToolboxDefinition(present)); } catch (e) { /* ignore */ }
}

function blockyIsRootType(type) {
    return type === "b_trigger_device"
        || type === "b_trigger_device_state"
        || type === "b_trigger_event"
        || type === "b_trigger_curated_event"
        || type === "b_branch_on"
        || type === "b_branch_off"
        || type === "b_then_do";
}

/** Condition/action blocks that are not snapped into a container (look nested but aren't). */
function blockyOrphanLeafBlocks(ws) {
    if (!ws) return [];
    return ws.getAllBlocks(false).filter((b) => {
        if (!b || blockyIsRootType(b.type)) return false;
        return !b.getParent();
    });
}

function blockyAssertNoOrphans(ws) {
    const orphans = blockyOrphanLeafBlocks(ws);
    if (!orphans.length) return;
    const labels = orphans.map((b) => {
        if (b.type === "b_condition_time") {
            return `if time is ${b.getFieldValue("TOD") || "?"}`;
        }
        if (b.type === "b_condition_device") {
            return `if device ${b.getFieldValue("ENTITY") || "?"} is ${b.getFieldValue("STATE") || "?"}`;
        }
        if (b.type === "b_action_device") {
            return `set device ${b.getFieldValue("ENTITY") || "?"}`;
        }
        if (b.type === "b_action_event") {
            return `fire event ${b.getFieldValue("EVENT") || "?"}`;
        }
        return b.type;
    });
    throw new Error(
        `Save blocked: ${orphans.length} block(s) are not snapped into conditions/actions — ` +
        `connect or delete: ${labels.join("; ")}`
    );
}

function blockyCancelUniqueness() {
    if (BlockyRT.uniquenessTimer) {
        clearTimeout(BlockyRT.uniquenessTimer);
        BlockyRT.uniquenessTimer = null;
    }
    BlockyRT.uniquenessScheduled = false;
    BlockyRT.pendingFieldEv = null;
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
        const seen = new Map();
        const toDispose = [];
        ws.getAllBlocks(false).forEach((b) => {
            const fp = blockyFingerprint(b);
            if (!fp) return;
            if (seen.has(fp)) toDispose.push(b);
            else seen.set(fp, b.id);
        });
        toDispose.forEach((b) => {
            try { b.dispose(false); changed = true; } catch (e) { /* ignore */ }
        });
    } finally {
        if (wasEnabled) Events.enable();
        if (!Events.isEnabled()) Events.enable();
        BlockyRT.enforcing = false;
        if (changed) blockyRefreshToolbox();
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
    if (isChange) BlockyRT.pendingFieldEv = ev;
    if (!isCreate && !isChange && !isMoveConnect && !isDelete) return;
    if (BlockyRT.uniquenessScheduled) return;
    BlockyRT.uniquenessScheduled = true;
    BlockyRT.uniquenessTimer = setTimeout(() => {
        BlockyRT.uniquenessTimer = null;
        BlockyRT.uniquenessScheduled = false;
        blockyEnforceUniqueness(isCreate || isDelete);
    }, 0);
}

function blockyMkBlock(type, fields, x, y) {
    const ws = blockyWs();
    const b = ws.newBlock(type);
    if (fields) {
        Object.keys(fields).forEach((name) => {
            try { b.setFieldValue(fields[name], name); } catch (e) { /* ignore */ }
        });
    }
    b.initSvg();
    if (b.queueRender) b.queueRender();
    else b.render();
    if (typeof x === "number" && typeof y === "number") b.moveBy(x, y);
    return b;
}

function blockyConnectChain(parentBlock, inputName, blocks) {
    if (!blocks || !blocks.length) return;
    const input = parentBlock.getInput(inputName);
    if (!input || !input.connection) return;
    let prevConn = input.connection;
    blocks.forEach((b) => {
        if (!b || !b.previousConnection) return;
        try {
            prevConn.connect(b.previousConnection);
            prevConn = b.nextConnection;
        } catch (e) { /* skip bad link */ }
    });
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
        branchedEditorMode: "blockly",
        flatEditorMode: "blockly",
        blocklyFullscreen: false,
        blocklySchemaVersion: 11,
        eventFamilies: ["blinds", "twilight_evening", "twilight_morning", "sauna", "ir", "cinema"],
        eventFamilyLabels: {
            blinds: "Blinds open/close (schedule event)",
            twilight_evening: "Twilight evening",
            twilight_morning: "Twilight morning",
            sauna: "Sauna",
            ir: "IR",
            cinema: "Cinema scene"
        },
        curatedEvents: [
            "BLINDS_OPEN_TRIGGER",
            "BLINDS_CLOSE_TRIGGER",
            "TWILIGHT_EVENING_ON_TRIGGER",
            "TWILIGHT_EVENING_OFF_TRIGGER",
            "TWILIGHT_MORNING_ON_TRIGGER",
            "TWILIGHT_MORNING_OFF_TRIGGER",
            "SAUNA_ON",
            "SAUNA_OFF",
            "IR_ON",
            "IR_OFF",
            "SCENE_CINEMA_ON",
            "SCENE_CINEMA_OFF",
            "SCENE_ALL_OFF",
            "SCENE_GOCOSY",
            "SCENE_GV_OFF",
            "SCENE_VERDIEP1_OFF",
            "SCENE_VERDIEP2_OFF"
        ],
        hardDenyPrefixes: [
            "switch.safety.",
            "switch.ssr.",
            "sensor.generic.host_",
            "sensor.temp_hum.host_",
            "sensor.generic.wanos_db_size"
        ],

        editor: {
            id: "",
            mode: "branched",
            name: "",
            scene: false,
            require_confirmation: false,
            triggerKind: "device",
            triggerEntityId: "",
            triggerEventFamily: "blinds",
            onEnabled: true,
            offEnabled: false,
            onConditions: [],
            onActions: [],
            offConditions: [],
            offActions: [],
            flatRuleJson: "{}"
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
            if (!this.selectedRule) return false;
            if (this.editor.mode === "branched") return this.branchedEditorMode === "blockly";
            if (this.editor.mode === "flat") return this.flatEditorMode === "blockly";
            return false;
        },

        ruleListKind(rule) {
            if (!rule || rule.isDraft) return "new";
            if (rule.mode === "branched") return "branched";
            if (rule.scene) return "dashboard";
            const t = this.normalizeFlatTrigger(rule.trigger);
            if (t && !t.multi && t.event) return "companion";
            return "flat";
        },

        ruleListBadgeClass(rule) {
            const k = this.ruleListKind(rule);
            if (k === "branched") return "badge-success";
            if (k === "dashboard") return "badge-secondary";
            if (k === "companion") return "badge-warning";
            if (k === "new") return "badge-ghost";
            return "badge-info";
        },

        deviceTypeLabel(type) {
            const t = String(type || "").toLowerCase();
            const map = {
                blinds: "blinds",
                switch: "switch",
                light: "light",
                hue: "light",
                speaker: "speaker",
                media_player: "speaker",
                scene: "scene",
                sensor: "sensor",
                temp: "sensor",
                hum: "sensor",
                temp_hum: "sensor",
                power: "sensor",
                energy: "sensor"
            };
            return map[t] || t || "device";
        },

        entityDisplayLabel(opt) {
            return `${opt.name} · ${this.deviceTypeLabel(opt.type)}`;
        },

        normalizeFlatTrigger(trigger) {
            if (!trigger) return null;
            if (Array.isArray(trigger)) {
                if (trigger.length === 1) return trigger[0];
                if (trigger.length === 0) return null;
                return { multi: true, triggers: trigger };
            }
            return trigger;
        },

        isFlatBlocklyCompatible(rule) {
            if (rule && rule.isDraft && this.editor.mode === "flat") return true;
            if (!rule || rule.on || rule.off) return false;
            const t = this.normalizeFlatTrigger(rule.trigger);
            if (!t) return false;
            if (t.multi) return false;
            if (t.event) return true;
            if (t.entity_id) return true;
            return false;
        },

        flatBlocklyBlockedReason(rule) {
            if (rule && rule.isDraft) return "";
            if (!rule || rule.on || rule.off) return "Branched rule — use branched Blockly.";
            const t = rule.trigger;
            if (Array.isArray(t) && t.length > 1) {
                return `Multiple triggers (${t.length}) — Blockly multi-trigger not yet supported.`;
            }
            if (!t) return "Missing trigger.";
            return "Complex flat rule — JSON only.";
        },

        eventFamilyLabel(fam) {
            return this.eventFamilyLabels[fam] || fam;
        },

        onBranchedEditorModeChanged() {
            if (this.editor.mode !== "branched") return;
            if (this.branchedEditorMode === "blockly") {
                this.scheduleBlocklyLoad();
            } else {
                this.blocklyFullscreen = false;
            }
        },

        onFlatEditorModeChanged() {
            if (this.editor.mode !== "flat") return;
            if (this.flatEditorMode === "blockly") {
                this.scheduleBlocklyLoad();
            } else {
                this.blocklyFullscreen = false;
            }
        },

        blocklyHostReady() {
            const host = document.getElementById("blocklyWorkspace");
            if (!host) return null;
            // Prefer offsetWidth: works even when Alpine parks the panel off-screen.
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
                if (ws.scrollbar && typeof ws.scrollbar.resize === "function") {
                    ws.scrollbar.resize();
                }
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
            return {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json"
            };
        },

        isAdminToken(token) {
            try {
                const payloadStr = atob(token.split(".")[1]);
                const payload = JSON.parse(payloadStr);
                return payload.role === "admin";
            } catch (e) {
                return false;
            }
        },

        isHardDeniedEntityId(eid) {
            if (!eid) return false;
            const v = String(eid);
            return this.hardDenyPrefixes.some((p) => v.startsWith(p));
        },

        collectEntityIdsFromRules(rules) {
            const out = new Set();
            const visit = (node) => {
                if (Array.isArray(node)) {
                    for (const it of node) visit(it);
                    return;
                }
                if (!node || typeof node !== "object") return;
                if (node.entity_id) out.add(String(node.entity_id));
                for (const val of Object.values(node)) visit(val);
            };
            visit(rules);
            return out;
        },

        rebuildEntityOptions(deviceMetadata, automations) {
            const usedEntityIds = this.collectEntityIdsFromRules(automations || []);
            const opts = [];
            for (const [idx, meta] of Object.entries(deviceMetadata || {})) {
                if (!meta || typeof meta !== "object") continue;
                const eid = meta.entity_id ? String(meta.entity_id) : "";
                if (!eid) continue;
                if (this.isHardDeniedEntityId(eid)) continue;
                const type = meta.type ? String(meta.type) : "unknown";
                // Synthetic dashboard scenes are not devices — exclude from device pickers.
                if (type === "scene") continue;
                const labelName = meta.name ? String(meta.name) : eid;
                const softHidden = Boolean(meta.hidden) && !usedEntityIds.has(eid);
                opts.push({
                    eid,
                    idx: Number(idx),
                    name: labelName,
                    label: labelName,
                    type,
                    softHidden
                });
            }
            opts.sort((a, b) => a.name.localeCompare(b.name));
            this.entityOptions = opts;
        },

        ensureTriggerEntitySelection() {
            if (this.editor.triggerKind !== "device") return;
            const all = this.entityOptions;
            const hasCurrent = all.some((o) => o.eid === this.editor.triggerEntityId);
            if (!hasCurrent) {
                const fallback = this.visibleEntityOptions[0] || all[0];
                this.editor.triggerEntityId = fallback ? fallback.eid : "";
            }
        },

        firstEntityId() {
            const first = this.visibleEntityOptions[0] || this.entityOptions[0];
            return first ? first.eid : "";
        },

        blankCondition() {
            return {
                type: "device_state",
                entity_id: this.firstEntityId(),
                is: "ON"
            };
        },

        blankAction(defaultState = "ON") {
            return {
                kind: "device", // device | event
                entity_id: this.firstEntityId(),
                state: defaultState,
                event: "",
                preset: "",
                bri: "",
                xy: "",
                volume: "",
                station: ""
            };
        },

        blankEditor() {
            return {
                id: "",
                mode: "branched",
                name: "",
                scene: false,
                require_confirmation: false,
                triggerKind: "device",
                triggerEntityId: this.firstEntityId(),
                triggerEventFamily: "blinds",
                onEnabled: true,
                offEnabled: false,
                onConditions: [],
                onActions: [this.blankAction("ON")],
                offConditions: [],
                offActions: [this.blankAction("OFF")],
                flatRuleJson: "{}",
                flatTriggerKind: "curated_event",
                flatTriggerEvent: "SCENE_CINEMA_ON",
                flatTriggerEntityId: this.firstEntityId(),
                flatTriggerState: "ON",
                flatConditions: [],
                flatActions: [this.blankAction("ON")]
            };
        },

        parseFlatRuleIntoEditor(editor, rule) {
            const t = this.normalizeFlatTrigger(rule.trigger);
            if (!t || t.multi) return;
            editor.flatConditions = ((rule.conditions || []).map((c) => this.normalizeCondition(c)));
            editor.flatActions = ((rule.actions || []).map((a) => this.normalizeAction(a)));
            if (editor.flatActions.length === 0) editor.flatActions.push(this.blankAction("ON"));

            if (t.event) {
                if (this.eventFamilies.includes(t.event)) {
                    editor.flatTriggerKind = "event_family";
                    editor.triggerEventFamily = t.event;
                } else {
                    editor.flatTriggerKind = "curated_event";
                    editor.flatTriggerEvent = t.event;
                }
            } else if (t.entity_id) {
                editor.flatTriggerKind = "device";
                editor.flatTriggerEntityId = t.entity_id;
                editor.flatTriggerState = t.state || "ON";
            }
        },

        normalizeCondition(c) {
            if (!c || typeof c !== "object") return this.blankCondition();
            // Backend historically dumped alias field as condition_is without by_alias=True.
            const isVal = c.is != null ? c.is : c.condition_is;
            if (c.type === "time_of_day") {
                return { type: "time_of_day", is: isVal || "dark" };
            }
            return {
                type: "device_state",
                entity_id: c.entity_id || this.firstEntityId(),
                is: isVal || "ON"
            };
        },

        normalizeAction(a) {
            if (!a || typeof a !== "object") return this.blankAction("ON");
            if (a.event) {
                return {
                    kind: "event",
                    event: a.event,
                    entity_id: "",
                    state: "",
                    preset: "",
                    bri: "",
                    xy: "",
                    volume: "",
                    station: ""
                };
            }
            return {
                kind: "device",
                entity_id: a.entity_id || this.firstEntityId(),
                state: a.state || "ON",
                event: "",
                preset: a.preset || "",
                bri: a.bri ?? "",
                xy: Array.isArray(a.xy) ? JSON.stringify(a.xy) : (a.xy || ""),
                volume: a.volume ?? "",
                station: a.station || ""
            };
        },

        addCondition(branchKey) {
            if (branchKey === "on") this.editor.onConditions.push(this.blankCondition());
            else this.editor.offConditions.push(this.blankCondition());
        },

        removeCondition(branchKey, idx) {
            if (branchKey === "on") this.editor.onConditions.splice(idx, 1);
            else this.editor.offConditions.splice(idx, 1);
        },

        addAction(branchKey, defaultState) {
            const a = this.blankAction(defaultState || "ON");
            if (branchKey === "on") this.editor.onActions.push(a);
            else this.editor.offActions.push(a);
        },

        removeAction(branchKey, idx) {
            if (branchKey === "on") this.editor.onActions.splice(idx, 1);
            else this.editor.offActions.splice(idx, 1);
        },

        actionKindChanged(action) {
            if (action.kind === "event") {
                action.entity_id = "";
                action.state = "";
                action.event = action.event || (this.curatedEvents[0] || "");
            } else {
                action.entity_id = action.entity_id || this.firstEntityId();
                action.state = action.state || "ON";
                action.event = "";
            }
        },

        conditionToPayload(c) {
            if (c.type === "time_of_day") {
                return { type: "time_of_day", is: c.is || "dark" };
            }
            if (!c.entity_id) throw new Error("Condition requires entity_id.");
            if (this.isHardDeniedEntityId(c.entity_id)) {
                throw new Error(`Blocked by policy: condition entity_id '${c.entity_id}' is not allowed.`);
            }
            return { type: "device_state", entity_id: c.entity_id, is: c.is || "ON" };
        },

        actionToPayload(a) {
            if (a.kind === "event") {
                if (!a.event || !String(a.event).trim()) throw new Error("Event action requires event key.");
                return { event: String(a.event).trim() };
            }
            if (!a.entity_id) throw new Error("Device action requires entity_id.");
            if (this.isHardDeniedEntityId(a.entity_id)) {
                throw new Error(`Blocked by policy: action entity_id '${a.entity_id}' is not allowed.`);
            }
            if (!a.state || !String(a.state).trim()) throw new Error("Device action requires state.");
            const out = { entity_id: a.entity_id, state: String(a.state).trim() };
            if (a.preset) out.preset = a.preset;
            if (a.station) out.station = a.station;
            if (a.bri !== "" && a.bri !== null && a.bri !== undefined) {
                const briNum = Number(a.bri);
                if (!Number.isNaN(briNum)) out.bri = briNum;
            }
            if (a.volume !== "" && a.volume !== null && a.volume !== undefined) {
                const volNum = Number(a.volume);
                if (!Number.isNaN(volNum)) out.volume = volNum;
            }
            if (a.xy && String(a.xy).trim()) {
                try {
                    const xy = JSON.parse(String(a.xy));
                    if (Array.isArray(xy)) out.xy = xy;
                } catch (e) {
                    throw new Error("Action xy must be JSON array (e.g. [0.5,0.5]).");
                }
            }
            return out;
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
                for (const [k, v] of Object.entries(node)) visit(v, path ? `${path}.${k}` : k);
            };
            visit(rulePayload, "rule");
            if (denied.length > 0) throw new Error(`Blocked by policy (hard deny): ${denied.join(", ")}`);
        },

        blocklyEntityDropdownOptions() {
            const opts = this.visibleEntityOptions.map((o) => [this.entityDisplayLabel(o), o.eid]);
            if (opts.length === 0) return [["(no entities)", ""]];
            return opts;
        },

        blocklyEventFamilyDropdownOptions() {
            return this.eventFamilies.map((f) => [this.eventFamilyLabel(f), f]);
        },

        blocklyEventDropdownOptions() {
            return this.curatedEvents.map((e) => [e, e]);
        },

        ensureBlocklyReady() {
            if (!window.Blockly) throw new Error("Blockly library not loaded.");
            BlockyRT.app = this;
            const host = this.blocklyHostReady();
            if (!host) return false;

            // Alpine x-if can recreate the host node; detect a dead injection.
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
                entity: () => (BlockyRT.app || this).blocklyEntityDropdownOptions(),
                family: () => (BlockyRT.app || this).blocklyEventFamilyDropdownOptions(),
                event: () => (BlockyRT.app || this).blocklyEventDropdownOptions()
            });

            // Same inject options as helpers/blockly_minimal_test.html
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

        destroyBlocklyWorkspace() {
            blockyDestroyWorkspace();
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
                    this.loadEditorIntoBlockly();
                    this.resizeBlockly();
                } catch (e) {
                    this.errorMessage = String(e && e.message ? e.message : e);
                }
            });
        },

        _conditionBlocksFromEditor(list) {
            const seen = new Set();
            const out = [];
            (list || []).forEach((c) => {
                let type; let fields; let fp;
                if (c.type === "time_of_day") {
                    type = "b_condition_time";
                    fields = { TOD: c.is || "dark" };
                    fp = `cond:time:${fields.TOD}`;
                } else {
                    type = "b_condition_device";
                    fields = { ENTITY: c.entity_id || this.firstEntityId(), STATE: c.is || "ON" };
                    fp = `cond:device:${fields.ENTITY}:${fields.STATE}`;
                }
                if (seen.has(fp)) return;
                seen.add(fp);
                out.push(blockyMkBlock(type, fields));
            });
            return out;
        },

        _actionBlocksFromEditor(list) {
            const seen = new Set();
            const out = [];
            (list || []).forEach((a) => {
                let type; let fields; let fp;
                if (a.kind === "event" || a.event) {
                    type = "b_action_event";
                    fields = { EVENT: a.event || this.curatedEvents[0] || "" };
                    fp = `act:event:${fields.EVENT}`;
                } else {
                    type = "b_action_device";
                    fields = { ENTITY: a.entity_id || this.firstEntityId(), STATE: a.state || "ON" };
                    fp = `act:device:${fields.ENTITY}:${fields.STATE}`;
                }
                if (seen.has(fp)) return;
                seen.add(fp);
                out.push(blockyMkBlock(type, fields));
            });
            return out;
        },

        /** Same lifecycle as minimal test seed(): disable events → clear → mk → resize → enable. */
        loadEditorIntoBlockly() {
            if (this.editor.mode === "flat") {
                this.loadFlatIntoBlockly();
                return;
            }
            if (!this.ensureBlocklyReady()) return;
            blockyCancelUniqueness();
            BlockyRT.loading = true;
            const Events = Blockly.Events;
            const wasEnabled = Events.isEnabled();
            try {
                Events.disable();
                const ws = blockyWs();
                ws.clear();

                if (this.editor.triggerKind === "event") {
                    blockyMkBlock("b_trigger_event", {
                        FAMILY: this.editor.triggerEventFamily || "blinds"
                    }, 16, 16);
                } else {
                    blockyMkBlock("b_trigger_device", {
                        ENTITY: this.editor.triggerEntityId || this.firstEntityId()
                    }, 16, 16);
                }

                if (this.editor.onEnabled) {
                    const onBlock = blockyMkBlock("b_branch_on", null, 16, 96);
                    blockyConnectChain(onBlock, "CONDS", this._conditionBlocksFromEditor(this.editor.onConditions));
                    blockyConnectChain(onBlock, "ACTIONS", this._actionBlocksFromEditor(this.editor.onActions));
                }

                if (this.editor.offEnabled) {
                    const offBlock = blockyMkBlock("b_branch_off", null, 400, 96);
                    blockyConnectChain(offBlock, "CONDS", this._conditionBlocksFromEditor(this.editor.offConditions));
                    blockyConnectChain(offBlock, "ACTIONS", this._actionBlocksFromEditor(this.editor.offActions));
                }

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

        loadFlatIntoBlockly() {
            if (!this.ensureBlocklyReady()) return;
            blockyCancelUniqueness();
            BlockyRT.loading = true;
            const Events = Blockly.Events;
            const wasEnabled = Events.isEnabled();
            try {
                Events.disable();
                const ws = blockyWs();
                ws.clear();

                if (this.editor.flatTriggerKind === "device") {
                    blockyMkBlock("b_trigger_device_state", {
                        ENTITY: this.editor.flatTriggerEntityId || this.firstEntityId(),
                        STATE: this.editor.flatTriggerState || "ON"
                    }, 16, 16);
                } else if (this.editor.flatTriggerKind === "event_family") {
                    blockyMkBlock("b_trigger_event", {
                        FAMILY: this.editor.triggerEventFamily || "blinds"
                    }, 16, 16);
                } else {
                    blockyMkBlock("b_trigger_curated_event", {
                        EVENT: this.editor.flatTriggerEvent || (this.curatedEvents[0] || "")
                    }, 16, 16);
                }

                const thenBlock = blockyMkBlock("b_then_do", null, 16, 96);
                blockyConnectChain(thenBlock, "CONDS", this._conditionBlocksFromEditor(this.editor.flatConditions));
                blockyConnectChain(thenBlock, "ACTIONS", this._actionBlocksFromEditor(this.editor.flatActions));

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

        _readStatementChain(startBlock, parserFn) {
            const out = [];
            let cur = startBlock;
            while (cur) {
                out.push(parserFn(cur));
                cur = cur.getNextBlock();
            }
            return out;
        },

        applyBlocklyToFlatEditor() {
            this.ensureBlocklyReady();
            const ws = blockyWs();
            if (!ws) throw new Error("Blockly workspace not ready.");
            blockyAssertNoOrphans(ws);
            const tops = ws.getTopBlocks(true);

            const trigCurated = tops.find((b) => b.type === "b_trigger_curated_event");
            const trigDeviceState = tops.find((b) => b.type === "b_trigger_device_state");
            const trigFamily = tops.find((b) => b.type === "b_trigger_event");
            if (!trigCurated && !trigDeviceState && !trigFamily) {
                throw new Error("Blockly requires one trigger block.");
            }
            const triggerCount = [trigCurated, trigDeviceState, trigFamily].filter(Boolean).length;
            if (triggerCount > 1) {
                throw new Error("Only one trigger allowed — remove the extra device or event block.");
            }

            if (trigDeviceState) {
                this.editor.flatTriggerKind = "device";
                this.editor.flatTriggerEntityId = trigDeviceState.getFieldValue("ENTITY");
                this.editor.flatTriggerState = trigDeviceState.getFieldValue("STATE");
            } else if (trigFamily) {
                this.editor.flatTriggerKind = "event_family";
                this.editor.triggerEventFamily = trigFamily.getFieldValue("FAMILY");
            } else {
                this.editor.flatTriggerKind = "curated_event";
                this.editor.flatTriggerEvent = trigCurated.getFieldValue("EVENT");
            }

            const thenBlock = tops.find((b) => b.type === "b_then_do");
            if (!thenBlock) throw new Error("Blockly flat rule requires a Then block.");

            const condStart = thenBlock.getInputTargetBlock("CONDS");
            const actStart = thenBlock.getInputTargetBlock("ACTIONS");
            this.editor.flatConditions = this._readStatementChain(condStart, (b) => {
                if (b.type === "b_condition_time") return { type: "time_of_day", is: b.getFieldValue("TOD") };
                return { type: "device_state", entity_id: b.getFieldValue("ENTITY"), is: b.getFieldValue("STATE") };
            });
            this.editor.flatActions = this._readStatementChain(actStart, (b) => {
                if (b.type === "b_action_event") return { kind: "event", event: b.getFieldValue("EVENT") };
                return { kind: "device", entity_id: b.getFieldValue("ENTITY"), state: b.getFieldValue("STATE"), preset: "", bri: "", xy: "", volume: "", station: "" };
            });

            this.infoMessage = "Applied Blockly workspace to flat rule data.";
        },

        applyBlocklyToEditor() {
            if (this.editor.mode === "flat") {
                this.applyBlocklyToFlatEditor();
                return;
            }
            this.ensureBlocklyReady();
            const ws = blockyWs();
            if (!ws) throw new Error("Blockly workspace not ready.");
            blockyAssertNoOrphans(ws);
            const tops = ws.getTopBlocks(true);

            const trigDevice = tops.find((b) => b.type === "b_trigger_device");
            const trigEvent = tops.find((b) => b.type === "b_trigger_event");
            if (!trigDevice && !trigEvent) {
                throw new Error("Blockly requires one trigger block (device or event).");
            }
            if (trigDevice && trigEvent) {
                throw new Error("Only one trigger allowed — remove the extra device or event block.");
            }

            if (trigEvent) {
                this.editor.triggerKind = "event";
                this.editor.triggerEventFamily = trigEvent.getFieldValue("FAMILY");
            } else {
                this.editor.triggerKind = "device";
                this.editor.triggerEntityId = trigDevice.getFieldValue("ENTITY");
            }

            const onBlock = tops.find((b) => b.type === "b_branch_on");
            const offBlock = tops.find((b) => b.type === "b_branch_off");
            this.editor.onEnabled = !!onBlock;
            this.editor.offEnabled = !!offBlock;

            if (onBlock) {
                const condStart = onBlock.getInputTargetBlock("CONDS");
                const actStart = onBlock.getInputTargetBlock("ACTIONS");
                this.editor.onConditions = this._readStatementChain(condStart, (b) => {
                    if (b.type === "b_condition_time") return { type: "time_of_day", is: b.getFieldValue("TOD") };
                    return { type: "device_state", entity_id: b.getFieldValue("ENTITY"), is: b.getFieldValue("STATE") };
                });
                this.editor.onActions = this._readStatementChain(actStart, (b) => {
                    if (b.type === "b_action_event") return { kind: "event", event: b.getFieldValue("EVENT") };
                    return { kind: "device", entity_id: b.getFieldValue("ENTITY"), state: b.getFieldValue("STATE"), preset: "", bri: "", xy: "", volume: "", station: "" };
                });
            } else {
                this.editor.onConditions = [];
                this.editor.onActions = [];
            }

            if (offBlock) {
                const condStart = offBlock.getInputTargetBlock("CONDS");
                const actStart = offBlock.getInputTargetBlock("ACTIONS");
                this.editor.offConditions = this._readStatementChain(condStart, (b) => {
                    if (b.type === "b_condition_time") return { type: "time_of_day", is: b.getFieldValue("TOD") };
                    return { type: "device_state", entity_id: b.getFieldValue("ENTITY"), is: b.getFieldValue("STATE") };
                });
                this.editor.offActions = this._readStatementChain(actStart, (b) => {
                    if (b.type === "b_action_event") return { kind: "event", event: b.getFieldValue("EVENT") };
                    return { kind: "device", entity_id: b.getFieldValue("ENTITY"), state: b.getFieldValue("STATE"), preset: "", bri: "", xy: "", volume: "", station: "" };
                });
            } else {
                this.editor.offConditions = [];
                this.editor.offActions = [];
            }

            this.infoMessage = "Applied Blockly workspace to form data.";
        },

        applyBlocklyToEditorQuiet() {
            const prev = this.infoMessage;
            if (this.editor.mode === "flat") {
                this.applyBlocklyToFlatEditor();
            } else {
                this.applyBlocklyToEditor();
            }
            this.infoMessage = prev;
        },

        buildPayloadFromEditor() {
            if (!this.editor.name || !this.editor.name.trim()) throw new Error("Rule name is required.");

            if (this.editor.mode === "branched") {
                if (!this.editor.onEnabled && !this.editor.offEnabled) {
                    throw new Error("At least one branch (ON/OFF) must be enabled.");
                }
                const payload = {
                    id: this.editor.id || undefined,
                    name: this.editor.name.trim(),
                    scene: !!this.editor.scene,
                    require_confirmation: !!this.editor.require_confirmation,
                    trigger: {}
                };

                if (this.editor.triggerKind === "device") {
                    if (!this.editor.triggerEntityId || !this.editor.triggerEntityId.trim()) {
                        throw new Error("Trigger entity_id is required for device trigger.");
                    }
                    if (this.isHardDeniedEntityId(this.editor.triggerEntityId.trim())) {
                        throw new Error(`Blocked by policy: '${this.editor.triggerEntityId.trim()}' cannot be used in automations.`);
                    }
                    payload.trigger = { entity_id: this.editor.triggerEntityId.trim() };
                } else {
                    if (!this.editor.triggerEventFamily) throw new Error("Event family is required.");
                    payload.trigger = { event: this.editor.triggerEventFamily };
                }

                if (this.editor.onEnabled) {
                    const actions = (this.editor.onActions || []).map((a) => this.actionToPayload(a));
                    if (actions.length === 0) throw new Error("ON branch must contain at least one action.");
                    payload.on = {
                        conditions: (this.editor.onConditions || []).map((c) => this.conditionToPayload(c)),
                        actions
                    };
                }

                if (this.editor.offEnabled) {
                    const actions = (this.editor.offActions || []).map((a) => this.actionToPayload(a));
                    if (actions.length === 0) throw new Error("OFF branch must contain at least one action.");
                    payload.off = {
                        conditions: (this.editor.offConditions || []).map((c) => this.conditionToPayload(c)),
                        actions
                    };
                }

                this.validateNoHardDeniedEntityIds(payload);
                return payload;
            }

            let flat;
            if (this.flatEditorMode === "blockly") {
                const payload = {
                    id: this.editor.id || undefined,
                    name: this.editor.name.trim(),
                    scene: !!this.editor.scene,
                    require_confirmation: !!this.editor.require_confirmation,
                    trigger: {},
                    actions: (this.editor.flatActions || []).map((a) => this.actionToPayload(a))
                };
                if (payload.actions.length === 0) throw new Error("Flat rule must contain at least one action.");

                if (this.editor.flatTriggerKind === "device") {
                    if (!this.editor.flatTriggerEntityId) throw new Error("Trigger device is required.");
                    payload.trigger = {
                        entity_id: this.editor.flatTriggerEntityId,
                        state: this.editor.flatTriggerState || "ON"
                    };
                } else if (this.editor.flatTriggerKind === "event_family") {
                    payload.trigger = { event: this.editor.triggerEventFamily };
                } else {
                    if (!this.editor.flatTriggerEvent) throw new Error("Trigger event is required.");
                    payload.trigger = { event: this.editor.flatTriggerEvent };
                }

                const conds = (this.editor.flatConditions || []).map((c) => this.conditionToPayload(c));
                if (conds.length > 0) payload.conditions = conds;

                this.validateNoHardDeniedEntityIds(payload);
                return payload;
            }

            try {
                flat = JSON.parse(this.editor.flatRuleJson || "{}");
            } catch (e) {
                throw new Error(`Flat rule JSON invalid (${e})`);
            }
            flat.id = this.editor.id || flat.id;
            flat.name = this.editor.name.trim();
            flat.scene = !!this.editor.scene;
            flat.require_confirmation = !!this.editor.require_confirmation;
            this.validateNoHardDeniedEntityIds(flat);
            return flat;
        },

        newRule() {
            this.selectedRule = { isDraft: true, mode: "branched" };
            this.editor = this.blankEditor();
            this.branchedEditorMode = "blockly";
            this.flatEditorMode = "blockly";
            this.errorMessage = "";
            this.infoMessage = "";
            this.ensureTriggerEntitySelection();
            this.scheduleBlocklyLoad();
        },

        selectRule(rule) {
            this.selectedRule = rule;
            this.errorMessage = "";
            this.infoMessage = "";

            const editor = this.blankEditor();
            editor.id = rule.id || "";
            editor.mode = rule.mode || "flat";
            editor.name = rule.name || "";
            editor.scene = !!rule.scene;
            editor.require_confirmation = !!rule.require_confirmation;

            if (editor.mode === "branched") {
                const t = rule.trigger || {};
                if (t.entity_id) {
                    editor.triggerKind = "device";
                    editor.triggerEntityId = t.entity_id;
                } else {
                    editor.triggerKind = "event";
                    editor.triggerEventFamily = t.event || "blinds";
                }
                editor.onEnabled = !!rule.on;
                editor.offEnabled = !!rule.off;
                editor.onConditions = ((rule.on && rule.on.conditions) || []).map((c) => this.normalizeCondition(c));
                editor.offConditions = ((rule.off && rule.off.conditions) || []).map((c) => this.normalizeCondition(c));
                editor.onActions = ((rule.on && rule.on.actions) || []).map((a) => this.normalizeAction(a));
                editor.offActions = ((rule.off && rule.off.actions) || []).map((a) => this.normalizeAction(a));
                if (editor.onEnabled && editor.onActions.length === 0) editor.onActions.push(this.blankAction("ON"));
                if (editor.offEnabled && editor.offActions.length === 0) editor.offActions.push(this.blankAction("OFF"));
            } else {
                if (this.isFlatBlocklyCompatible(rule)) {
                    this.flatEditorMode = "blockly";
                    this.parseFlatRuleIntoEditor(editor, rule);
                    editor.flatRuleJson = JSON.stringify(
                        {
                            id: rule.id,
                            name: rule.name,
                            scene: !!rule.scene,
                            require_confirmation: !!rule.require_confirmation,
                            trigger: rule.trigger,
                            conditions: rule.conditions || null,
                            actions: rule.actions || []
                        },
                        null,
                        2
                    );
                } else {
                    this.flatEditorMode = "json";
                    editor.flatRuleJson = JSON.stringify(
                        {
                            id: rule.id,
                            name: rule.name,
                            scene: !!rule.scene,
                            require_confirmation: !!rule.require_confirmation,
                            trigger: rule.trigger,
                            conditions: rule.conditions || null,
                            actions: rule.actions || []
                        },
                        null,
                        2
                    );
                }
            }
            this.editor = editor;
            this.ensureTriggerEntitySelection();
            if ((editor.mode === "branched" && this.branchedEditorMode === "blockly") ||
                (editor.mode === "flat" && this.flatEditorMode === "blockly")) {
                // Reuse the same workspace (minimal-test style): clear + reload, do not destroy.
                blockyCancelUniqueness();
                this.scheduleBlocklyLoad();
            }
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
                const rawRules = (rulesPayload.automations || []).filter((r) => r && typeof r === "object");
                this.automations = rawRules.map((r) => {
                    const mode = Object.prototype.hasOwnProperty.call(r, "on") || Object.prototype.hasOwnProperty.call(r, "off")
                        ? "branched"
                        : "flat";
                    return { ...r, mode };
                });

                this.rebuildEntityOptions(state.device_metadata || {}, this.automations);

                if (this.selectedRule && this.selectedRule.id) {
                    const fresh = this.automations.find((r) => r.id === this.selectedRule.id);
                    if (fresh) this.selectRule(fresh);
                }
                this.ensureTriggerEntitySelection();
                if (this.showBlocklyWorkspace) {
                    this.scheduleBlocklyLoad();
                }
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
                    headers: this.getAuthHeaders(),
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
                if (report.ok) {
                    this.registryCheckMessage =
                        warnN
                            ? `Admin Debug GREEN — entity_id / registry check passed (${warnN} non-blocking warning(s)).`
                            : "Admin Debug GREEN — entity_id / registry check passed (not a behavior smoke test).";
                } else {
                    this.registryCheckMessage =
                        `Admin Debug RED — ${errN} error(s), ${warnN} warning(s). Open Admin → Debug for the full report.`;
                }
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
                if ((this.editor.mode === "branched" && this.branchedEditorMode === "blockly") ||
                    (this.editor.mode === "flat" && this.flatEditorMode === "blockly")) {
                    this.applyBlocklyToEditorQuiet();
                }
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
                this.infoMessage = isUpdate ? "Automation updated (hot-reload queued)." : "Automation created (hot-reload queued).";
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

