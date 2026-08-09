// Auto-off timers admin page (auto_off_devices via /api/auto-off-timer).

function autoOffTimersApp() {
    const HARD_DENY = "switch.safety.safety_wisc_5v";
    const TYPE_KEYS = ["switch", "light", "speaker"];
    const ALLOWED = new Set(TYPE_KEYS);
    const DEVICE_DENY = new Set([
        HARD_DENY,
        "switch.ssr.safety_ssr_12v",
        "switch.cinema_projector",
    ]);

    return {
        typeKeys: TYPE_KEYS,
        rows: [],
        softHidden: new Set(),
        searchQuery: "",
        /** @type {"all"|"hidden"|"visible"} */
        viewMode: "visible",
        /** @type {"all"|"on"|"off"} — auto-off membership (checkbox), not lamp power */
        managedFilter: "all",
        /** @type {"name"|"type"|"effective"} */
        sortKey: "name",
        /** @type {"asc"|"desc"} */
        sortDir: "asc",
        saved: null,
        draft: {
            managed_auto_off: [],
            default_auto_off_minutes: 300,
            default_pertype_auto_off_minutes: {},
            auto_off_delays: {},
        },
        busy: false,
        errorMessage: "",
        infoMessage: "",
        // C2 leave-guard (Blocky-style Cancel / Discard / Save)
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
                };
                const managedSet = new Set(this.draft.managed_auto_off);
                const delays = this.draft.auto_off_delays;
                for (const row of this.rows) {
                    row.managed = managedSet.has(row.eid);
                    row.override = delays[row.eid] != null ? Number(delays[row.eid]) : null;
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
            const q = (this.searchQuery || "").trim().toLowerCase();
            if (q) {
                list = list.filter((r) =>
                    `${r.name || ""} ${r.typeLabel || ""} ${r.eid || ""}`.toLowerCase().includes(q)
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
                const av = String(key === "type" ? (a.typeLabel || "") : (a.name || ""));
                const bv = String(key === "type" ? (b.typeLabel || "") : (b.name || ""));
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

        typeLabel(type, origin, idx) {
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
                blinds: "Blinds",
                power: "Power",
                sensor: "Sensor",
            };
            return map[t] || t;
        },

        normType(type) {
            const t = String(type || "unknown").toLowerCase();
            if (t === "media_player") return "speaker";
            return t;
        },

        isEligible(eid, type) {
            if (!eid || DEVICE_DENY.has(eid)) return false;
            return ALLOWED.has(this.normType(type));
        },

        /** Stored per-device delay (explicit pin). */
        isExplicit(row) {
            return row.override != null && row.override !== "" && !Number.isNaN(Number(row.override));
        },

        /** Resolved minutes: per-device → type → general. */
        effectiveFor(row) {
            if (this.isExplicit(row)) {
                return Number(row.override);
            }
            const t = row.typeKey;
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

        toggleManaged(row, on) {
            row.managed = !!on;
            if (!on) {
                row.override = null;
            }
            this._syncDraftFromRows();
        },

        setEffective(row, raw) {
            const v = String(raw || "").trim();
            row.override = v === "" ? null : Number(v);
            this._syncDraftFromRows();
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
            return {
                managed_auto_off: [...(this.draft.managed_auto_off || [])].sort(),
                default_auto_off_minutes: Number(this.draft.default_auto_off_minutes),
                default_pertype_auto_off_minutes: Object.fromEntries(
                    Object.entries(pertype).sort(([a], [b]) => a.localeCompare(b))
                ),
                auto_off_delays: Object.fromEntries(
                    Object.entries(delays).sort(([a], [b]) => a.localeCompare(b))
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

                this.draft = {
                    managed_auto_off: [...managedSet].sort(),
                    default_auto_off_minutes: Number(cfg.default_auto_off_minutes) || 300,
                    default_pertype_auto_off_minutes: { ...(cfg.default_pertype_auto_off_minutes || {}) },
                    auto_off_delays: { ...delays },
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
                    if (!this.isEligible(eid, type)) continue;
                    const origin = m.origin ? String(m.origin) : "";
                    const typeKey = this.normType(type);
                    const ov = delays[eid];
                    rows.push({
                        eid,
                        name: m.name ? String(m.name) : eid,
                        type,
                        typeKey,
                        typeLabel: this.typeLabel(type, origin, idx),
                        softHidden: this.softHidden.has(eid),
                        managed: managedSet.has(eid),
                        override: ov != null ? Number(ov) : null,
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
                if (text.includes("Config reload failed")) return "fail";
                if (text.includes("Config reloaded")) return "ok";
            }
            return null;
        },

        _reloadAlertFingerprint(msgs) {
            if (!Array.isArray(msgs)) return "";
            const parts = [];
            for (const msg of msgs) {
                const text = msg && msg.message ? String(msg.message) : "";
                if (!text.includes("Config reloaded") && !text.includes("Config reload failed")) continue;
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
                };
                this.saved = this._payload();
                const managedSet = new Set(this.draft.managed_auto_off);
                const delays = this.draft.auto_off_delays;
                for (const row of this.rows) {
                    row.managed = managedSet.has(row.eid);
                    row.override = delays[row.eid] != null ? Number(delays[row.eid]) : null;
                }
                this.infoMessage = "Saved. Config reloading…";
                const reloadStatus = await this.waitForConfigReloadOk(baselineFp);
                if (reloadStatus === "ok") {
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
