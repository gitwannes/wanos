// --- file: frontend/blocky.js ---

function blockyApp() {
    return {
        connected: false,
        busy: false,
        errorMessage: "",
        infoMessage: "",
        filterText: "",
        automations: [],
        selectedRule: null,
        entityOptions: [],
        showHiddenEntities: false,
        eventFamilies: ["blinds", "twilight_evening", "twilight_morning", "sauna", "ir", "cinema"],
        eventFamilyLabels: {
            blinds: "Blinds (open/close)",
            twilight_evening: "Twilight evening (ON/OFF)",
            twilight_morning: "Twilight morning (ON/OFF)",
            sauna: "Sauna (ON/OFF)",
            ir: "IR (ON/OFF)",
            cinema: "Cinema scene (ON/OFF)"
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

        eventFamilyLabel(fam) {
            return this.eventFamilyLabels[fam] || fam;
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
                const labelName = meta.name ? String(meta.name) : eid;
                const type = meta.type ? String(meta.type) : "unknown";
                const softHidden = Boolean(meta.hidden) && !usedEntityIds.has(eid);
                opts.push({
                    eid,
                    idx: Number(idx),
                    label: `${labelName} (${eid})`,
                    type,
                    softHidden
                });
            }
            opts.sort((a, b) => a.label.localeCompare(b.label));
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
                flatRuleJson: "{}"
            };
        },

        normalizeCondition(c) {
            if (!c || typeof c !== "object") return this.blankCondition();
            if (c.type === "time_of_day") {
                return { type: "time_of_day", is: c.is || "dark" };
            }
            return {
                type: "device_state",
                entity_id: c.entity_id || this.firstEntityId(),
                is: c.is || "ON"
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
            this.selectedRule = null;
            this.editor = this.blankEditor();
            this.errorMessage = "";
            this.infoMessage = "";
            this.ensureTriggerEntitySelection();
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
            this.editor = editor;
            this.ensureTriggerEntitySelection();
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
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async saveRule() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
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
                this.infoMessage = isUpdate ? "Automation updated." : "Automation created.";
                await this.refreshAll();
                const rid = (body.automation && body.automation.id) || payload.id;
                if (rid) {
                    const fresh = this.automations.find((r) => r.id === rid);
                    if (fresh) this.selectRule(fresh);
                }
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
            try {
                const res = await fetch("/api/automations", {
                    method: "DELETE",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ id: this.editor.id })
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `DELETE failed (${res.status})`);
                this.infoMessage = "Automation deleted.";
                await this.refreshAll();
                this.newRule();
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        async init() {
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

