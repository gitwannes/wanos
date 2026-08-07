// Explorer soft-hide admin page (deviceexplorer_hide via /api/soft-hide).

function hiddenDevicesApp() {
    const HARD_DENY = "switch.safety.safety_wisc_5v";

    return {
        rows: [],
        searchQuery: "",
        /** @type {"all"|"hidden"|"visible"} */
        viewMode: "all",
        /** @type {"name"|"type"} */
        sortKey: "name",
        /** @type {"asc"|"desc"} */
        sortDir: "asc",
        savedHidden: new Set(),
        draftHidden: new Set(),
        busy: false,
        connected: false,
        isAdmin: true,
        errorMessage: "",
        infoMessage: "",

        logout() {
            localStorage.removeItem("wanos_jwt");
            window.location.href = "/login.html";
        },

        get dirty() {
            if (this.savedHidden.size !== this.draftHidden.size) return true;
            for (const e of this.draftHidden) {
                if (!this.savedHidden.has(e)) return true;
            }
            return false;
        },

        get selectedCount() {
            return this.draftHidden.size;
        },

        get visibleRows() {
            let list = this.rows.slice();
            if (this.viewMode === "hidden") {
                list = list.filter((r) => r.hidden);
            } else if (this.viewMode === "visible") {
                list = list.filter((r) => !r.hidden);
            }
            const q = (this.searchQuery || "").trim();
            if (q) {
                const parsed = this._parseTextQuery(q);
                list = list.filter((r) =>
                    this._matchesTextQuery(`${r.name || ""} ${r.typeLabel || ""}`, parsed)
                );
            }
            const key = this.sortKey;
            const dir = this.sortDir === "asc" ? 1 : -1;
            list.sort((a, b) => {
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
                shutter: "Blinds",
                power: "Power",
                motion: "Motion",
                temp_hum: "Temp/Hum",
                "temp&hum": "Temp/Hum",
                door: "Door",
                sensor: "Sensor",
                fluid: "Fluid",
                energy: "Energy",
            };
            return map[t] || t;
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
        },

        async reload() {
            this.errorMessage = "";
            try {
                const [stateRes, hideRes] = await Promise.all([
                    fetch("/api/state", { headers: this.getAuthHeaders() }),
                    fetch("/api/soft-hide", { headers: this.getAuthHeaders() }),
                ]);
                if (!stateRes.ok) throw new Error(`Failed /api/state (${stateRes.status})`);
                if (!hideRes.ok) throw new Error(`Failed /api/soft-hide (${hideRes.status})`);
                const state = await stateRes.json();
                const hideBody = await hideRes.json();
                const hidden = new Set((hideBody.entity_ids || []).map((e) => String(e)));
                this.savedHidden = new Set(hidden);
                this.draftHidden = new Set(hidden);

                const rows = [];
                const meta = state.device_metadata || {};
                for (const [idxStr, m] of Object.entries(meta)) {
                    if (!m || typeof m !== "object") continue;
                    const eid = m.entity_id ? String(m.entity_id) : "";
                    if (!eid || eid === HARD_DENY) continue;
                    const idx = Number(idxStr);
                    if (idx === 90001 || idx === 71040) continue;
                    if (m.type === "scene") continue;
                    const name = m.name ? String(m.name) : eid;
                    const type = m.type ? String(m.type) : "unknown";
                    const origin = m.origin ? String(m.origin) : "";
                    rows.push({
                        eid,
                        name,
                        type,
                        typeLabel: this.typeLabel(type, origin, idx),
                        hidden: this.draftHidden.has(eid),
                    });
                }
                this.rows = rows;
                this.connected = true;
            } catch (e) {
                this.connected = false;
                this.errorMessage = String(e.message || e);
            }
        },

        toggle(row, checked) {
            row.hidden = checked;
            if (checked) this.draftHidden.add(row.eid);
            else this.draftHidden.delete(row.eid);
            this.draftHidden = new Set(this.draftHidden);
        },

        selectAllVisible() {
            for (const row of this.visibleRows) {
                row.hidden = true;
                this.draftHidden.add(row.eid);
            }
            this.draftHidden = new Set(this.draftHidden);
        },

        deselectAllVisible() {
            for (const row of this.visibleRows) {
                row.hidden = false;
                this.draftHidden.delete(row.eid);
            }
            this.draftHidden = new Set(this.draftHidden);
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

        /** Fingerprint Config reload alerts (dedupe bumps count/timestamp in place). */
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
            let baselineFp = "";
            try {
                const snap = await fetch("/api/state", { headers: this.getAuthHeaders() });
                if (snap.ok) {
                    const st = await snap.json();
                    baselineFp = this._reloadAlertFingerprint((st.system && st.system.system_alert_msgs) || []);
                }
            } catch (e) { /* ignore */ }
            try {
                const entity_ids = Array.from(this.draftHidden).sort();
                const res = await fetch("/api/soft-hide", {
                    method: "PUT",
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ entity_ids }),
                });
                const body = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(body.error || `Save failed (${res.status})`);
                this.savedHidden = new Set(body.entity_ids || entity_ids);
                this.draftHidden = new Set(this.savedHidden);
                for (const row of this.rows) {
                    row.hidden = this.draftHidden.has(row.eid);
                }
                this.infoMessage = "Saved. Config reloading…";
                const reloadStatus = await this.waitForConfigReloadOk(baselineFp);
                if (reloadStatus === "ok") {
                    this.infoMessage = "Config reload OK";
                } else if (reloadStatus === "fail") {
                    this.errorMessage = "Config reload failed";
                    this.infoMessage = "";
                } else {
                    this.infoMessage = "Saved (reload status not confirmed — refresh if Explorer looks stale)";
                }
            } catch (e) {
                this.errorMessage = String(e.message || e);
                this.infoMessage = "";
            } finally {
                this.busy = false;
            }
        },

        _parseTextQuery(raw) {
            const includes = [];
            const excludes = [];
            for (const tok of String(raw).trim().split(/\s+/).filter(Boolean)) {
                if (tok.startsWith("-") && tok.length > 1) excludes.push(tok.slice(1).toLowerCase());
                else includes.push(tok.toLowerCase());
            }
            return { includes, excludes };
        },

        _matchesTextQuery(haystack, parsed) {
            const h = String(haystack || "").toLowerCase();
            for (const ex of parsed.excludes) {
                if (h.includes(ex)) return false;
            }
            for (const inc of parsed.includes) {
                if (!h.includes(inc)) return false;
            }
            return true;
        },
    };
}
