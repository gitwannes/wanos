// Timers & types admin page (auto_off_devices + device_product_types via /api/auto-off-timer).

function autoOffTimersApp() {
    const HARD_DENY = "switch.safety.safety_wisc_5v";
    const TYPE_KEYS = ["switch", "light", "speaker"];
    const PRODUCT_TYPES = ["light", "switch"];
    const ALLOWED = new Set(TYPE_KEYS);
    const DEVICE_DENY = new Set([
        HARD_DENY,
        "switch.ssr.safety_ssr_12v",
        "switch.epson",
        "switch.cinema_projector",
    ]);
    const VENT_WALL_SWITCH = "switch.vent.toilet_ventilatie";
    const INTRINSIC_TYPES = new Set([
        "blinds", "speaker", "media_player", "motion", "power", "energy", "fluid",
        "door", "temp_hum", "temp", "hum", "sensor", "scene", "unknown", "voltage", "shutter",
    ]);

    function isVentMotorEid(eid) {
        const e = String(eid || "").toLowerCase();
        if (e.startsWith("zwave.vent.")) return true;
        if (!e.startsWith("switch.vent.")) return false;
        return e !== VENT_WALL_SWITCH;
    }

    function isSsrOrSafety(eid) {
        const e = String(eid || "").toLowerCase();
        return e.startsWith("switch.ssr.") || e.startsWith("switch.safety.");
    }

    function isHuePhysical(eid) {
        return String(eid || "").toLowerCase().includes("hue_physical");
    }

    function resolveProductType(eid, origin, overrides) {
        if (String(origin || "").toLowerCase() === "hue") return "light";
        const ov = (overrides || {})[eid];
        if (ov === "light" || ov === "switch") return ov;
        return "switch";
    }

    function isProductTypeEditable(eid, origin, deviceType) {
        if (!eid || DEVICE_DENY.has(eid)) return false;
        if (String(origin || "").toLowerCase() === "hue") return false;
        if (isSsrOrSafety(eid) || isVentMotorEid(eid)) return false;
        if (eid === "switch.cinema_projector" || eid === "switch.epson") return false;
        if (isHuePhysical(eid) || eid === VENT_WALL_SWITCH) return true;
        const o = String(origin || "").toLowerCase();
        const t = String(deviceType || "").toLowerCase();
        if (o === "zwave" || o === "rfxcom") {
            if (t === "switch" || t === "light") return true;
        }
        const e = String(eid);
        if (e.startsWith("zwave.vent.")) return false;
        if (e.startsWith("zwave.") || e.startsWith("rfx.")) {
            return t === "switch" || t === "light" || !t;
        }
        if ((t === "switch" || t === "light") && e.startsWith("switch.")) {
            return !isSsrOrSafety(eid) && !isVentMotorEid(eid);
        }
        return false;
    }

    function isInventoryRow(eid, origin, deviceType) {
        if (!eid || DEVICE_DENY.has(eid)) return false;
        if (String(deviceType || "").toLowerCase() === "scene") return false;
        if (String(origin || "").toLowerCase() === "automation") return false;
        return true;
    }

    function readOnlyProductLabel(origin, deviceType, resolved) {
        const o = String(origin || "").toLowerCase();
        const t = String(deviceType || "").toLowerCase();
        if (o === "hue") return "light";
        if (t === "speaker" || t === "media_player") return "speaker";
        if (t === "blinds" || t === "shutter") return "shutter";
        if (t === "temp&hum") return "temp_hum";
        if (INTRINSIC_TYPES.has(t)) return t;
        // Fixed actuators that are still product-typed (vent motor, SSR, Epson, …)
        if (resolved === "light" || resolved === "switch") return resolved;
        return t || "switch";
    }

    /** Display value for the Type column (editable → light|switch; fixed → intrinsic kind). */
    function typeColumnValue(eid, origin, deviceType, editable, overrides) {
        const resolved = resolveProductType(eid, origin, overrides);
        if (editable) return resolved;
        return readOnlyProductLabel(origin, deviceType, resolved);
    }

    /** Auto-off per-type tier key: light | switch | speaker | … */
    function autoOffTypeKey(eid, origin, deviceType, overrides) {
        const t = String(deviceType || "").toLowerCase();
        if (t === "speaker" || t === "media_player") return "speaker";
        if (t === "switch" || t === "light" || String(origin || "").toLowerCase() === "hue") {
            return resolveProductType(eid, origin, overrides);
        }
        return t || "unknown";
    }

    return {
        typeKeys: TYPE_KEYS,
        productTypes: PRODUCT_TYPES,
        rows: [],
        softHidden: new Set(),
        searchQuery: "",
        /** @type {"all"|"hidden"|"visible"} */
        viewMode: "visible",
        /** @type {"all"|"on"|"off"} — auto-off membership (checkbox), not lamp power */
        managedFilter: "all",
        /** @type {"all"|"editable"|"fixed"} — product Type column editability */
        typeEditFilter: "all",
        /** @type {"name"|"provType"|"productType"|"effective"} */
        sortKey: "name",
        /** @type {"asc"|"desc"} */
        sortDir: "asc",
        saved: null,
        draft: {
            managed_auto_off: [],
            default_auto_off_minutes: 300,
            default_pertype_auto_off_minutes: {},
            auto_off_delays: {},
            device_product_types: {},
        },
        busy: false,
        errorMessage: "",
        infoMessage: "",
        pendingNav: null,

        logout() {
            localStorage.removeItem("wanos_jwt");
            window.location.href = "/login.html";
        },

        requestLeave(action) {
            if (!this.dirty) {
                this.runLeaveAction(action);
                return;
            }
            this.pendingNav = action;
            document.getElementById("unsaved_changes_modal")?.showModal();
        },

        runLeaveAction(action) {
            if (!action) return;
            if (action.type === "href" && action.url) window.location.href = action.url;
            else if (action.type === "logout") this.logout();
        },

        cancelUnsavedLeave() {
            this.pendingNav = null;
            document.getElementById("unsaved_changes_modal")?.close();
        },

        discardUnsavedLeave() {
            const action = this.pendingNav;
            this.pendingNav = null;
            if (this.saved) {
                this.draft = {
                    managed_auto_off: [...(this.saved.managed_auto_off || [])],
                    default_auto_off_minutes: this.saved.default_auto_off_minutes,
                    default_pertype_auto_off_minutes: {
                        ...(this.saved.default_pertype_auto_off_minutes || {}),
                    },
                    auto_off_delays: { ...(this.saved.auto_off_delays || {}) },
                    device_product_types: { ...(this.saved.device_product_types || {}) },
                };
                const managedSet = new Set(this.draft.managed_auto_off);
                const delays = this.draft.auto_off_delays;
                const overrides = this.draft.device_product_types || {};
                for (const row of this.rows) {
                    row.managed = managedSet.has(row.eid);
                    row.override = delays[row.eid] != null ? Number(delays[row.eid]) : null;
                    row.productTypeKey = autoOffTypeKey(
                        row.eid, row.origin, row.provType, overrides
                    );
                    row.productType = typeColumnValue(
                        row.eid, row.origin, row.provType, row.productEditable, overrides
                    );
                    this._refreshRowDirtyFlags(row);
                }
            }
            document.getElementById("unsaved_changes_modal")?.close();
            this.runLeaveAction(action);
        },

        async saveUnsavedLeave() {
            await this.save();
            if (this.errorMessage) return;
            const action = this.pendingNav;
            this.pendingNav = null;
            document.getElementById("unsaved_changes_modal")?.close();
            this.runLeaveAction(action);
        },

        navAway(ev, url) {
            if (!this.dirty) return;
            ev.preventDefault();
            this.requestLeave({ type: "href", url });
        },

        get managedCount() {
            return (this.draft.managed_auto_off || []).length;
        },

        get dirty() {
            if (!this.saved) return false;
            return JSON.stringify(this._payload()) !== JSON.stringify(this.saved);
        },

        /** True when general default minutes differ from last saved. */
        get generalDefaultUnsaved() {
            if (!this.saved) return false;
            return Number(this.draft.default_auto_off_minutes) !== Number(this.saved.default_auto_off_minutes);
        },

        /** True when this type-tier default differs from last saved (blank = inherit general). */
        isTypeDefaultUnsaved(t) {
            if (!this.saved || !t) return false;
            const draftMap = this.draft.default_pertype_auto_off_minutes || {};
            const savedMap = this.saved.default_pertype_auto_off_minutes || {};
            const dRaw = draftMap[t];
            const sRaw = savedMap[t];
            const dBlank = dRaw == null || dRaw === "";
            const sBlank = sRaw == null || sRaw === "";
            if (dBlank && sBlank) return false;
            if (dBlank !== sBlank) return true;
            return Number(dRaw) !== Number(sRaw);
        },

        get visibleRows() {
            let list = this.rows.slice();
            if (this.viewMode === "hidden") {
                list = list.filter((r) => r.softHidden);
            } else if (this.viewMode === "visible") {
                list = list.filter((r) => !r.softHidden);
            }
            if (this.managedFilter === "on") {
                list = list.filter((r) => r.managed);
            } else if (this.managedFilter === "off") {
                list = list.filter((r) => !r.managed);
            }
            if (this.typeEditFilter === "editable") {
                list = list.filter((r) => r.productEditable);
            } else if (this.typeEditFilter === "fixed") {
                list = list.filter((r) => !r.productEditable);
            }
            const q = (this.searchQuery || "").trim().toLowerCase();
            if (q) {
                list = list.filter((r) =>
                    `${r.name || ""} ${r.provTypeLabel || ""} ${r.productType || ""} ${r.eid || ""}`.toLowerCase().includes(q)
                );
            }
            const key = this.sortKey;
            const dir = this.sortDir === "asc" ? 1 : -1;
            list.sort((a, b) => {
                if (key === "effective") {
                    if (!!a.managed !== !!b.managed) return a.managed ? -1 : 1;
                    const av = this.effectiveFor(a);
                    const bv = this.effectiveFor(b);
                    if (av !== bv) return (av - bv) * dir;
                    return String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" });
                }
                let av;
                let bv;
                if (key === "provType") {
                    av = String(a.provTypeLabel || "");
                    bv = String(b.provTypeLabel || "");
                } else if (key === "productType") {
                    av = String(a.productType || "");
                    bv = String(b.productType || "");
                } else {
                    av = String(a.name || "");
                    bv = String(b.name || "");
                }
                return av.localeCompare(bv, undefined, { sensitivity: "base" }) * dir;
            });
            return list;
        },

        sortIndicator(key) {
            if (this.sortKey !== key) return "";
            return this.sortDir === "asc" ? " ▲" : " ▼";
        },

        toggleSort(key) {
            if (this.sortKey === key) {
                this.sortDir = this.sortDir === "asc" ? "desc" : "asc";
            } else {
                this.sortKey = key;
                this.sortDir = "asc";
            }
        },

        getAuthHeaders() {
            const token = localStorage.getItem("wanos_jwt") || "";
            return {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
            };
        },

        provTypeLabel(type, origin, idx) {
            const t = String(type || "unknown");
            const o = String(origin || "");
            if (t === "speaker" || t === "media_player") {
                if (o === "sonos" || (idx >= 60000 && idx < 61000)) return "Sonos";
                if (o === "onkyo" || (idx >= 61000 && idx < 62000)) return "Onkyo";
                return "Speaker";
            }
            const map = {
                light: "Light",
                switch: "Switch",
                blinds: "Shutter",
                shutter: "Shutter",
                power: "Power",
                sensor: "Sensor",
                door: "Door",
                fluid: "Fluid",
            };
            return map[t] || t;
        },

        normType(type) {
            const t = String(type || "unknown").toLowerCase();
            if (t === "media_player") return "speaker";
            if (t === "shutter") return "blinds";
            return t;
        },

        isAutoOffEligible(row) {
            if (!row || !row.eid || DEVICE_DENY.has(row.eid)) return false;
            return ALLOWED.has(row.productTypeKey);
        },

        isExplicit(row) {
            return row.override != null && row.override !== "" && !Number.isNaN(Number(row.override));
        },

        effectiveFor(row) {
            if (this.isExplicit(row)) {
                return Number(row.override);
            }
            const t = row.productTypeKey;
            const pt = this.draft.default_pertype_auto_off_minutes || {};
            if (t && pt[t] != null && pt[t] !== "") return Number(pt[t]);
            return Number(this.draft.default_auto_off_minutes) || 300;
        },

        setTypeDefault(t, raw) {
            const v = String(raw || "").trim();
            const next = { ...(this.draft.default_pertype_auto_off_minutes || {}) };
            if (!v) delete next[t];
            else next[t] = Number(v);
            this.draft.default_pertype_auto_off_minutes = next;
        },

        setProductType(row, raw) {
            if (!row || !row.productEditable) return;
            const val = String(raw || "").trim().toLowerCase();
            const next = { ...(this.draft.device_product_types || {}) };
            if (val === "light") {
                next[row.eid] = "light";
            } else {
                delete next[row.eid];
            }
            row.productType = val === "light" ? "light" : "switch";
            row.productTypeKey = row.productType;
            this.draft.device_product_types = next;
            this._refreshRowDirtyFlags(row);
        },

        /** Compare row draft fields to last saved payload; set Alpine-friendly boolean flags. */
        _refreshRowDirtyFlags(row) {
            if (!row) return;
            if (!this.saved) {
                row.managedUnsaved = false;
                row.typeUnsaved = false;
                row.effectiveUnsaved = false;
                return;
            }
            const wasManaged = (this.saved.managed_auto_off || []).includes(row.eid);
            row.managedUnsaved = !!row.managed !== wasManaged;

            if (row.productEditable) {
                const savedMap = this.saved.device_product_types || {};
                const savedType = savedMap[row.eid] === "light" ? "light" : "switch";
                const cur = String(row.productType || "switch").toLowerCase() === "light" ? "light" : "switch";
                row.typeUnsaved = cur !== savedType;
            } else {
                row.typeUnsaved = false;
            }

            const savedDelays = this.saved.auto_off_delays || {};
            const savedOv = savedDelays[row.eid];
            const savedExplicit = savedOv != null;
            const curExplicit = this.isExplicit(row);
            if (curExplicit !== savedExplicit) {
                row.effectiveUnsaved = true;
            } else if (!curExplicit) {
                row.effectiveUnsaved = false;
            } else {
                row.effectiveUnsaved = Number(row.override) !== Number(savedOv);
            }
        },

        toggleManaged(row, on) {
            if (!this.isAutoOffEligible(row)) return;
            row.managed = !!on;
            if (!on) {
                row.override = null;
            }
            this._syncDraftFromRows();
            this._refreshRowDirtyFlags(row);
        },

        setEffective(row, raw) {
            const v = String(raw || "").trim();
            row.override = v === "" ? null : Number(v);
            this._syncDraftFromRows();
            this._refreshRowDirtyFlags(row);
        },
        _syncDraftFromRows() {
            const managed = [];
            const delays = {};
            for (const row of this.rows) {
                if (!row.managed) continue;
                managed.push(row.eid);
                if (this.isExplicit(row)) {
                    delays[row.eid] = Number(row.override);
                }
            }
            managed.sort();
            this.draft.managed_auto_off = managed;
            this.draft.auto_off_delays = delays;
        },

        _payload() {
            const pertype = {};
            for (const [k, v] of Object.entries(this.draft.default_pertype_auto_off_minutes || {})) {
                if (v == null || v === "") continue;
                pertype[k] = Number(v);
            }
            const delays = {};
            for (const [k, v] of Object.entries(this.draft.auto_off_delays || {})) {
                delays[k] = Number(v);
            }
            const productTypes = {};
            for (const [k, v] of Object.entries(this.draft.device_product_types || {})) {
                if (v === "light") productTypes[k] = "light";
            }
            return {
                managed_auto_off: [...(this.draft.managed_auto_off || [])].sort(),
                default_auto_off_minutes: Number(this.draft.default_auto_off_minutes),
                default_pertype_auto_off_minutes: Object.fromEntries(
                    Object.entries(pertype).sort(([a], [b]) => a.localeCompare(b))
                ),
                auto_off_delays: Object.fromEntries(
                    Object.entries(delays).sort(([a], [b]) => a.localeCompare(b))
                ),
                device_product_types: Object.fromEntries(
                    Object.entries(productTypes).sort(([a], [b]) => a.localeCompare(b))
                ),
            };
        },

        init() {
            const token = localStorage.getItem("wanos_jwt") || "";
            if (!token) {
                window.location.href = "/login.html";
                return;
            }
            try {
                const payload = JSON.parse(atob(token.split(".")[1]));
                if (payload.role !== "admin") {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
            } catch (err) {
                window.location.href = "/login.html";
                return;
            }
            this.reload();
            this._onBeforeUnload = (e) => {
                if (!this.dirty) return;
                e.preventDefault();
                e.returnValue = "";
            };
            window.addEventListener("beforeunload", this._onBeforeUnload);
        },

        async reload() {
            this.errorMessage = "";
            try {
                const [stateRes, cfgRes, hideRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/auto-off-timer", { headers: this.getAuthHeaders() }),
                    fetch("/api/soft-hide", { headers: this.getAuthHeaders() }),
                ]);
                if (!stateRes.ok) throw new Error(`Failed /api/state (${stateRes.status})`);
                if (!cfgRes.ok) throw new Error(`Failed /api/auto-off-timer (${cfgRes.status})`);
                if (!hideRes.ok) throw new Error(`Failed /api/soft-hide (${hideRes.status})`);
                const state = await stateRes.json();
                const cfg = await cfgRes.json();
                const hideBody = await hideRes.json();
                this.softHidden = new Set((hideBody.entity_ids || []).map((e) => String(e)));

                const managedSet = new Set((cfg.managed_auto_off || []).map(String));
                const delays = cfg.auto_off_delays || {};
                const overrides = cfg.device_product_types || {};

                this.draft = {
                    managed_auto_off: [...managedSet].sort(),
                    default_auto_off_minutes: Number(cfg.default_auto_off_minutes) || 300,
                    default_pertype_auto_off_minutes: { ...(cfg.default_pertype_auto_off_minutes || {}) },
                    auto_off_delays: { ...delays },
                    device_product_types: { ...overrides },
                };
                this.saved = this._payload();

                const rows = [];
                const meta = state.device_metadata || {};
                for (const [idxStr, m] of Object.entries(meta)) {
                    if (!m || typeof m !== "object") continue;
                    const eid = m.entity_id ? String(m.entity_id) : "";
                    if (!eid) continue;
                    const idx = Number(idxStr);
                    if (idx === 90001 || idx === 71040) continue;
                    const type = m.type ? String(m.type) : "unknown";
                    const origin = m.origin ? String(m.origin) : "";
                    if (!isInventoryRow(eid, origin, type)) continue;
                    const editable = isProductTypeEditable(eid, origin, type);
                    const displayProduct = typeColumnValue(
                        eid, origin, type, editable, overrides
                    );
                    const ov = delays[eid];
                    rows.push({
                        eid,
                        name: m.name ? String(m.name) : eid,
                        provType: type,
                        provTypeLabel: this.provTypeLabel(type, origin, idx),
                        productType: displayProduct,
                        productTypeKey: autoOffTypeKey(eid, origin, type, overrides),
                        productEditable: editable,
                        origin,
                        softHidden: this.softHidden.has(eid),
                        managed: managedSet.has(eid),
                        override: ov != null ? Number(ov) : null,
                        managedUnsaved: false,
                        typeUnsaved: false,
                        effectiveUnsaved: false,
                    });
                }
                this.rows = rows;
                this.connected = true;
            } catch (e) {
                this.errorMessage = String(e.message || e);
            }
        },

        _alertSaysReloadDone(msgs) {
            if (!Array.isArray(msgs)) return null;
            for (const msg of msgs) {
                const text = msg && msg.message ? String(msg.message) : "";
                if (window.WanOSReloadAlerts) {
                    if (window.WanOSReloadAlerts.isFailed(text)) return "fail";
                    if (window.WanOSReloadAlerts.COMPLETE.includes(text)) return "ok";
                } else {
                    if (text.includes("Config reload failed")) return "fail";
                    if (text.includes("Config reloaded") || text.includes("reloaded.")) return "ok";
                }
            }
            return null;
        },

        _reloadAlertFingerprint(msgs) {
            if (!Array.isArray(msgs)) return "";
            const parts = [];
            for (const msg of msgs) {
                const text = msg && msg.message ? String(msg.message) : "";
                const isReload = window.WanOSReloadAlerts
                    ? (window.WanOSReloadAlerts.COMPLETE.includes(text)
                        || window.WanOSReloadAlerts.isFailed(text)
                        || window.WanOSReloadAlerts.IN_PROGRESS.includes(text))
                    : (text.includes("Config reloaded") || text.includes("Config reload failed")
                        || text.includes("Reloading"));
                if (!isReload) continue;
                parts.push(`${text}|${msg.count || 1}|${msg.timestamp || ""}`);
            }
            return parts.join(";");
        },

        async waitForConfigReloadOk(baselineFp) {
            const deadline = Date.now() + 15000;
            const base = baselineFp || "";
            while (Date.now() < deadline) {
                await new Promise((r) => setTimeout(r, 400));
                try {
                    const res = await fetch("/api/state", { headers: this.getAuthHeaders() });
                    if (!res.ok) continue;
                    const st = await res.json();
                    const msgs = (st.system && st.system.system_alert_msgs) || [];
                    const fp = this._reloadAlertFingerprint(msgs);
                    if (!fp || fp === base) continue;
                    return this._alertSaysReloadDone(msgs) || "ok";
                } catch (e) { /* keep polling */ }
            }
            return "timeout";
        },

        async save() {
            this.busy = true;
            this.errorMessage = "";
            this.infoMessage = "Saving…";
            this._syncDraftFromRows();
            let baselineFp = "";
            try {
                const snap = await fetch("/api/state", { headers: this.getAuthHeaders() });
                if (snap.ok) {
                    const st = await snap.json();
                    baselineFp = this._reloadAlertFingerprint((st.system && st.system.system_alert_msgs) || []);
                }
            } catch (e) { /* ignore */ }
            try {
                const payload = this._payload();
                const res = await fetch("/api/auto-off-timer", {
                    method: "PUT",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify(payload),
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `Save failed (${res.status})`);
                this.draft = {
                    managed_auto_off: body.managed_auto_off || payload.managed_auto_off,
                    default_auto_off_minutes: body.default_auto_off_minutes ?? payload.default_auto_off_minutes,
                    default_pertype_auto_off_minutes: body.default_pertype_auto_off_minutes || {},
                    auto_off_delays: body.auto_off_delays || {},
                    device_product_types: body.device_product_types || payload.device_product_types || {},
                };
                this.saved = this._payload();
                const managedSet = new Set(this.draft.managed_auto_off);
                const delays = this.draft.auto_off_delays;
                const overrides = this.draft.device_product_types || {};
                for (const row of this.rows) {
                    row.managed = managedSet.has(row.eid);
                    row.override = delays[row.eid] != null ? Number(delays[row.eid]) : null;
                    row.productTypeKey = autoOffTypeKey(
                        row.eid, row.origin, row.provType, overrides
                    );
                    row.productType = typeColumnValue(
                        row.eid, row.origin, row.provType, row.productEditable, overrides
                    );
                    row.managedUnsaved = false;
                    row.typeUnsaved = false;
                    row.effectiveUnsaved = false;
                }
                this.infoMessage = "Saved. Config reloading…";
                const reloadStatus = await this.waitForConfigReloadOk(baselineFp);
                if (reloadStatus === "ok") {
                    this.infoMessage = "Config reload OK";
                    await this.reload();
                    this.infoMessage = "Config reload OK";
                } else if (reloadStatus === "fail") {
                    this.errorMessage = "Config reload failed";
                    this.infoMessage = "";
                } else {
                    this.infoMessage = "Saved (reload status not confirmed — refresh if timers look stale)";
                }
            } catch (e) {
                this.errorMessage = String(e.message || e);
                this.infoMessage = "";
            } finally {
                this.busy = false;
            }
        },
    };
}
