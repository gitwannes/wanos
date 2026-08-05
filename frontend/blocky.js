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
        entityIds: [],
        eventFamilies: ["blinds", "twilight_evening", "twilight_morning", "sauna", "ir", "cinema"],

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
            onConditionsJson: "[]",
            onActionsJson: "[]",
            offConditionsJson: "[]",
            offActionsJson: "[]",
            flatRuleJson: "{}"
        },

        get filteredRules() {
            const q = this.filterText.trim().toLowerCase();
            if (!q) return this.automations;
            return this.automations.filter(r => {
                const name = (r.name || "").toLowerCase();
                const id = String(r.id || "").toLowerCase();
                return name.includes(q) || id.includes(q);
            });
        },

        getAuthHeaders() {
            const token = localStorage.getItem("wanos_jwt") || "";
            return {
                "Authorization": `Bearer ${token}`,
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
                const metadata = state.device_metadata || {};
                this.entityIds = Object.values(metadata)
                    .map(m => m && m.entity_id ? String(m.entity_id) : "")
                    .filter(Boolean)
                    .sort();

                const rawRules = (rulesPayload.automations || []).filter(r => r && typeof r === "object");
                this.automations = rawRules.map(r => {
                    const mode = (Object.prototype.hasOwnProperty.call(r, "on") || Object.prototype.hasOwnProperty.call(r, "off"))
                        ? "branched"
                        : "flat";
                    return { ...r, mode };
                });

                if (this.selectedRule && this.selectedRule.id) {
                    const fresh = this.automations.find(r => r.id === this.selectedRule.id);
                    if (fresh) this.selectRule(fresh);
                }
            } catch (e) {
                this.errorMessage = String(e);
            } finally {
                this.busy = false;
            }
        },

        blankEditor() {
            return {
                id: "",
                mode: "branched",
                name: "",
                scene: false,
                require_confirmation: false,
                triggerKind: "device",
                triggerEntityId: this.entityIds.length > 0 ? this.entityIds[0] : "",
                triggerEventFamily: "blinds",
                onEnabled: true,
                offEnabled: false,
                onConditionsJson: "[]",
                onActionsJson: "[\n  {\n    \"entity_id\": \"\",\n    \"state\": \"ON\"\n  }\n]",
                offConditionsJson: "[]",
                offActionsJson: "[\n  {\n    \"entity_id\": \"\",\n    \"state\": \"OFF\"\n  }\n]",
                flatRuleJson: "{}"
            };
        },

        newRule() {
            this.selectedRule = null;
            this.editor = this.blankEditor();
            this.errorMessage = "";
            this.infoMessage = "";
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
                editor.onConditionsJson = JSON.stringify((rule.on && rule.on.conditions) || [], null, 2);
                editor.onActionsJson = JSON.stringify((rule.on && rule.on.actions) || [], null, 2);
                editor.offConditionsJson = JSON.stringify((rule.off && rule.off.conditions) || [], null, 2);
                editor.offActionsJson = JSON.stringify((rule.off && rule.off.actions) || [], null, 2);
            } else {
                editor.flatRuleJson = JSON.stringify({
                    id: rule.id,
                    name: rule.name,
                    scene: !!rule.scene,
                    require_confirmation: !!rule.require_confirmation,
                    trigger: rule.trigger,
                    conditions: rule.conditions || null,
                    actions: rule.actions || []
                }, null, 2);
            }

            this.editor = editor;
        },

        parseJsonArray(label, text) {
            let val;
            try {
                val = JSON.parse(text || "[]");
            } catch (e) {
                throw new Error(`${label}: invalid JSON (${e})`);
            }
            if (!Array.isArray(val)) {
                throw new Error(`${label}: expected JSON array`);
            }
            return val;
        },

        buildPayloadFromEditor() {
            if (!this.editor.name || !this.editor.name.trim()) {
                throw new Error("Rule name is required.");
            }
            if (this.editor.mode === "branched") {
                if (!this.editor.onEnabled && !this.editor.offEnabled) {
                    throw new Error("At least one branch (ON/OFF) must be enabled.");
                }
                const payload = {
                    id: this.editor.id || undefined,
                    name: this.editor.name.trim(),
                    scene: !!this.editor.scene,
                    require_confirmation: !!this.editor.require_confirmation,
                    trigger: {},
                };

                if (this.editor.triggerKind === "device") {
                    if (!this.editor.triggerEntityId || !this.editor.triggerEntityId.trim()) {
                        throw new Error("Trigger entity_id is required for device trigger.");
                    }
                    payload.trigger = { entity_id: this.editor.triggerEntityId.trim() };
                } else {
                    if (!this.editor.triggerEventFamily) throw new Error("Event family is required.");
                    payload.trigger = { event: this.editor.triggerEventFamily };
                }

                if (this.editor.onEnabled) {
                    payload.on = {
                        conditions: this.parseJsonArray("ON conditions", this.editor.onConditionsJson),
                        actions: this.parseJsonArray("ON actions", this.editor.onActionsJson)
                    };
                }
                if (this.editor.offEnabled) {
                    payload.off = {
                        conditions: this.parseJsonArray("OFF conditions", this.editor.offConditionsJson),
                        actions: this.parseJsonArray("OFF actions", this.editor.offActionsJson)
                    };
                }
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
            return flat;
        },

        async saveRule() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "";
            try {
                const payload = this.buildPayloadFromEditor();
                const isUpdate = !!payload.id && this.automations.some(r => r.id === payload.id);
                const method = isUpdate ? "PUT" : "POST";
                const res = await fetch("/api/automations", {
                    method,
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload)
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) {
                    throw new Error(body.error || `${method} failed (${res.status})`);
                }
                this.infoMessage = isUpdate ? "Automation updated." : "Automation created.";
                await this.refreshAll();
                const rid = (body.automation && body.automation.id) || payload.id;
                if (rid) {
                    const fresh = this.automations.find(r => r.id === rid);
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
        }
    };
}

