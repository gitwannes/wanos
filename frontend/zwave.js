// --- file: frontend/zwave.js ---

function zwaveApp() {
    return {
        connected: false,
        isAdmin: true,
        reloadSuppressOverlay: false,
        _sseOfflineDebounce: null,
        eventSource: null,
        usbPath: "",
        errorMessage: "",
        infoMessage: "",
        deviceList: [],
        configReloading: false,
        searchQuery: "",
        typeFilter: "ALL",
        sortMode: "NODE", // "NODE", "IDX", "NAME", "TYPE", "PATH"
        sortDir: "asc",
        savedFingerprint: "",
        /** @type {Record<string, {selected: boolean, name: string, type: string, comment_str: string}>} */
        savedSnapshot: {},
        _baselinePending: false,
        // C2 leave-guard (Blocky-style Cancel / Discard / Save)
        pendingNav: null,
        /** Set true after user confirms Discard/Save leave so beforeunload does not double-prompt. */
        _allowNavigation: false,

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

        async discardUnsavedLeave() {
            const action = this.pendingNav;
            this.pendingNav = null;
            document.getElementById("unsaved_changes_modal")?.close();
            // Force map rebuild: processBackendState otherwise skips zwave_mapped while
            // _initialMapDone (intent-preservation), leaving dirty=true → browser Leave site? dialog.
            try {
                const token = localStorage.getItem("wanos_jwt") || "";
                const res = await fetch("/api/state", {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (res.ok) {
                    const data = await res.json();
                    this._initialMapDone = false;
                    this.processBackendState(data);
                }
            } catch (e) {
                console.error("discard reload failed", e);
            }
            // User already confirmed discard — never show a second native prompt.
            this._allowNavigation = true;
            this.runLeaveAction(action);
        },

        async saveUnsavedLeave() {
            await this.saveAndReloadConfig();
            if (this.errorMessage) return;
            const action = this.pendingNav;
            this.pendingNav = null;
            document.getElementById("unsaved_changes_modal")?.close();
            this._allowNavigation = true;
            this.runLeaveAction(action);
        },
        navAway(ev, url) {
            if (!this.dirty) return;
            ev.preventDefault();
            this.requestLeave({ type: "href", url });
        },

        _mapFingerprint() {
            const rows = this.deviceList
                .filter((i) => i.selected)
                .map((i) => [
                    i.idx,
                    i.path,
                    i.type,
                    (i.name || "").trim(),
                    (i.comment_str || "").toString().trim(),
                ].join("\t"))
                .sort();
            return rows.join("\n") + `\nusb:${this.usbPath || ""}`;
        },

        get dirty() {
            if (!this.savedFingerprint) return false;
            return this._mapFingerprint() !== this.savedFingerprint;
        },

        _captureSavedSnapshot() {
            const snap = {};
            for (const i of this.deviceList) {
                snap[i.path] = {
                    selected: !!i.selected,
                    name: String(i.name || "").trim(),
                    type: String(i.type || ""),
                    comment_str: String(i.comment_str || "").trim(),
                };
            }
            this.savedSnapshot = snap;
        },

        /** True when this row differs from last saved map (add/remove/name/type/comment). */
        isRowDirty(item) {
            if (!item || !item.path) return false;
            if (!this.savedFingerprint) return false;
            const base = this.savedSnapshot[item.path];
            const selected = !!item.selected;
            const name = String(item.name || "").trim();
            const type = String(item.type || "");
            const comment = String(item.comment_str || "").trim();
            if (!base) {
                // New inbox row since baseline — dirty only once selected (add).
                return selected;
            }
            if (selected !== base.selected) return true;
            if (!selected) return false;
            return name !== base.name || type !== base.type || comment !== base.comment_str;
        },

        isNameDirty(item) {
            if (!this.isRowDirty(item) || !item) return false;
            const base = this.savedSnapshot[item.path];
            if (!base) return !!item.selected;
            return String(item.name || "").trim() !== base.name;
        },

        isAddDirty(item) {
            if (!item) return false;
            const base = this.savedSnapshot[item.path];
            const selected = !!item.selected;
            if (!base) return selected;
            return selected !== base.selected;
        },

        isTypeDirty(item) {
            if (!item || item.is_mapped) return false;
            const base = this.savedSnapshot[item.path];
            if (!base) return !!item.selected;
            if (!item.selected && !base.selected) return false;
            return String(item.type || "") !== base.type;
        },

        isCommentDirty(item) {
            if (!item || !item.selected) return false;
            const base = this.savedSnapshot[item.path];
            if (!base) return !!String(item.comment_str || "").trim();
            return String(item.comment_str || "").trim() !== base.comment_str;
        },

        sortIndicator(mode) {
            if (this.sortMode !== mode) return "";
            return this.sortDir === "asc" ? " ▲" : " ▼";
        },

        toggleSort(mode) {
            if (this.sortMode === mode) {
                this.sortDir = this.sortDir === "asc" ? "desc" : "asc";
            } else {
                this.sortMode = mode;
                this.sortDir = "asc";
            }
        },

        resolvedProductType(item) {
            // Mapped binary (71–72x): always show product type; never blank.
            if (!item || item.idx == null) return "switch";
            const meta = (this._lastMeta || {})[item.idx] || (this._lastMeta || {})[String(item.idx)];
            if (meta && meta.resolved_product_type) return String(meta.resolved_product_type);
            if (item.product_type) return String(item.product_type);
            return "switch";
        },

        mappedTypeLabel(item) {
            if (!item) return "";
            if (this.isBinaryIdx(item.idx)) return this.resolvedProductType(item);
            return item.type || "";
        },

        isBinaryIdx(idx) {
            const i = Number(idx);
            return Number.isFinite(i) && i >= 71000 && i < 73000;
        },

        // ⚡ Reactive filtering pipeline
        get visibleDeviceList() {
            const shutterNodes = new Set(this.deviceList.filter(i => i.type === 'shutter').map(i => i.node));
            const switchNodes = new Set(this.deviceList.filter(i => i.type === 'switch').map(i => i.node));
            const dir = this.sortDir === "asc" ? 1 : -1;

            return this.deviceList.filter(item => {
                // Rule 1: Drop dead probes
                if (item.value === -999.9 || item.value === "-999.9") return false;
                // Rule 2: Suppress aux endpoints on unmapped shutters
                if (shutterNodes.has(item.node) && (item.type === 'switch' || item.type === 'power') && !item.is_mapped) return false;
                // Rule 3: Suppress raw binary endpoints on standard switches
                if (switchNodes.has(item.node) && item.type === 'motion' && !item.is_mapped) return false;

                // User Filters
                if (this.typeFilter !== "ALL" && item.type !== this.typeFilter) return false;
                if (this.searchQuery.trim() !== "") {
                    const q = this.searchQuery.toLowerCase();
                    // Track matches on the absolute index string representation if populated
                    const matchesIdx = item.idx !== null && String(item.idx).includes(q);

                    if (!item.name.toLowerCase().includes(q) && !item.path.toLowerCase().includes(q) && !matchesIdx) return false;
                }

                return true;
            }).sort((a, b) => {
                if (this.sortMode === "IDX") {
                    const idxA = a.idx !== null ? a.idx : Number.MAX_SAFE_INTEGER;
                    const idxB = b.idx !== null ? b.idx : Number.MAX_SAFE_INTEGER;
                    if (idxA !== idxB) return (idxA - idxB) * dir;
                } else if (this.sortMode === "NAME") {
                    const cmp = a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
                    if (cmp !== 0) return cmp * dir;
                } else if (this.sortMode === "TYPE") {
                    const cmp = String(a.type || "").localeCompare(String(b.type || ""), undefined, { sensitivity: "base" });
                    if (cmp !== 0) return cmp * dir;
                } else if (this.sortMode === "PATH") {
                    const cmp = String(a.path || "").localeCompare(String(b.path || ""), undefined, { sensitivity: "base" });
                    if (cmp !== 0) return cmp * dir;
                }

                // Default / Fallback: Sort by Node Number, then Type, then Path
                const nodeA = parseInt(a.node, 10) || 0;
                const nodeB = parseInt(b.node, 10) || 0;
                if (nodeA !== nodeB) return (nodeA - nodeB) * (this.sortMode === "NODE" ? dir : 1);
                if (a.type !== b.type) return a.type.localeCompare(b.type);
                return a.path.localeCompare(b.path);
            });
        },

        init() {
            // Load persistent credential mapping from localStorage
            const token = localStorage.getItem("wanos_jwt") || "";
            if (!token) {
                window.location.href = '/login.html';
                return;
            }

            // ⚡ Admin Gatekeeper: Decode JWT locally to ensure authorization
            try {
                const payloadStr = atob(token.split('.')[1]);
                const payload = JSON.parse(payloadStr);
                if (payload.role !== "admin") {
                    console.warn("Unauthorized access attempt. Redirecting to device explorer.");
                    window.location.href = '/deviceexplorer.html';
                    return;
                }
            } catch (err) {
                window.location.href = '/login.html';
                return;
            }

            // Initial cache state fetch
            fetch("/api/state", {
                headers: { "Authorization": `Bearer ${token}` }
            }).then(res => res.json()).then(data => {
                this.processBackendState(data);
                this.connectSSE(token);
            }).catch(err => console.error("Failed to fetch state:", err));

            this._onBeforeUnload = (e) => {
                if (this._allowNavigation) return;
                if (!this.dirty) return;
                e.preventDefault();
                e.returnValue = "";
            };
            window.addEventListener("beforeunload", this._onBeforeUnload);
        },

        connectSSE(token) {
            this.eventSource = new EventSource(`/api/state/sse?jwt=${token}`);

            const scheduleOffline = () => {
                if (this._sseOfflineDebounce) clearTimeout(this._sseOfflineDebounce);
                this._sseOfflineDebounce = setTimeout(() => {
                    this._sseOfflineDebounce = null;
                    this.connected = false;
                }, 3000);
            };
            const markAlive = () => {
                if (this._sseOfflineDebounce) {
                    clearTimeout(this._sseOfflineDebounce);
                    this._sseOfflineDebounce = null;
                }
                this.connected = true;
            };

            this.eventSource.onmessage = (e) => {
                const msg = JSON.parse(e.data);

                if (msg.domain === "ping") {
                    markAlive();
                    return;
                }

                if (msg.domain === "system") {
                    this.processBackendState({ system: msg.data });
                    if (msg.data && msg.data.system_alert_msgs && window.WanOSReloadAlerts) {
                        this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(
                            msg.data.system_alert_msgs
                        );
                    }
                } else if (msg.domain === "devices") {
                    // Update values for configured nodes running live
                    for (const [idxStr, val] of Object.entries(msg.data)) {
                        const targetIdx = parseInt(idxStr, 10);
                        const item = this.deviceList.find(i => i.idx === targetIdx);
                        if (item) {
                            item.value = this.flattenNestedObject(val);
                        }
                    }
                }
                markAlive();
            };
            this.eventSource.onerror = () => {
                if (this.eventSource) this.eventSource.close();
                scheduleOffline();
                setTimeout(() => this.connectSSE(token), 3000);
            };
        },

        flattenNestedObject(val) {
            // Evaluates and extracts the raw value and maps it to a standard unit
            if (typeof val === 'object' && val !== null) {
                // E.g. {"Air temperature": 26.5} -> "26.5 °C"
                const keys = Object.keys(val);
                if (keys.length > 0 && typeof val[keys[0]] !== 'object') {
                    let k = keys[0].toLowerCase();
                    let unit = "";

                    if (k.includes('temp') || k.includes('air')) unit = '°C';
                    else if (k.includes('hum')) unit = '%';
                    else if (k.includes('lux') || k.includes('illuminance')) unit = 'Lux';
                    else if (k.includes('pow') || k.includes('watt') || k.includes('meter')) unit = 'W';
                    else if (k.includes('volt')) unit = 'V';
                    else if (k.includes('amp') || k.includes('current')) unit = 'A';

                    return unit ? `${val[keys[0]]} ${unit}` : `${val[keys[0]]} ${keys[0]}`;
                }
                return JSON.stringify(val);
            }
            return val;
        },

        processBackendState(fullState) {
            if (!fullState.system) return;
            let listModified = false;
            this._lastMeta = fullState.device_metadata || {};

            if (fullState.system.zwave_usb_path) {
                this.usbPath = fullState.system.zwave_usb_path;
            }

            // 1. Unpack Mapped System Configuration
            if (fullState.system.zwave_mapped) {
                // ⚡ INTENT PRESERVATION GUARD
                // Only reconstruct the configuration matrix on initial boot or during an explicit config reload.
                // This prevents continuous background SSE ticks (like telemetry or uptime) from ruthlessly overwriting
                // checkboxes and text fields while the user is actively making configuration changes!
                if (!this._initialMapDone || this.configReloading) {

                    // ⚡ PURGE LOCAL UI CACHE
                    for (const item of this.deviceList) {
                        if (item.is_mapped) {
                            item.is_mapped = false;
                            item.selected = false;
                            item.idx = null;
                            item.original_idx = null;
                        }
                    }

                    for (const [idxStr, rawStr] of Object.entries(fullState.system.zwave_mapped)) {
                        const idx = parseInt(idxStr, 10);
                        let path = rawStr;
                        let name = `Node ${rawStr.split('/')[0]}`;
                        let commentStr = "";

                        if (rawStr.includes('|')) {
                            const parts = rawStr.split('|');
                            path = parts[0].trim();
                            name = parts[1] ? parts[1].trim() : name;
                            commentStr = parts[2] ? parts[2].trim() : "";
                        }

                        const safeNode = path.split('/')[0];
                        if (safeNode === "1") continue;

                        const existing = this.deviceList.find(i => i.path === path);
                        const metaRow = (fullState.device_metadata && fullState.device_metadata[idx])
                            || (fullState.device_metadata && fullState.device_metadata[String(idx)]);
                        const productType = (metaRow && metaRow.resolved_product_type)
                            || ((idx >= 71000 && idx < 73000) ? "switch" : null);
                        if (existing) {
                            existing.is_mapped = true;
                            existing.idx = idx;
                            existing.name = name;
                            existing.comment_str = commentStr;
                            existing.original_idx = idx;
                            existing.entity_id = metaRow ? metaRow.entity_id : null;
                            if (productType) existing.product_type = productType;
                            // We can safely restore the auto-select because this block ONLY runs on fresh boots or manual reloads.
                            existing.selected = true;
                        } else {
                            let type = "switch";
                            if (idx >= 71000 && idx < 73000) type = "switch";
                            else if (idx >= 73000 && idx < 74000) type = "shutter";
                            else if (idx >= 74000 && idx < 75000) type = "power";
                            else if (idx >= 75000 && idx < 76000) type = "motion";
                            else if (idx >= 76000 && idx < 77000) type = "temp&hum";

                            this.deviceList.push({
                                path: path,
                                node: safeNode,
                                value: "Mapped",
                                selected: true,
                                is_mapped: true,
                                type: type,
                                product_type: productType || undefined,
                                idx: idx,
                                name: name,
                                comment_str: commentStr,
                                original_idx: idx,
                                entity_id: metaRow ? metaRow.entity_id : null,
                            });
                            listModified = true;
                        }
                    }
                    this._initialMapDone = true;
                    this._baselinePending = true;
                }
            }

            // 2. Unpack Transient Discovery Data Elements
            if (fullState.system.zwave_inbox) {
                for (const [path, data] of Object.entries(fullState.system.zwave_inbox)) {
                    const safeNode = data.node || data.node_name || path.split('/')[0];

                    if (safeNode === "1" || path.includes("duration") || path.includes("targetValue")) continue;
                    // Bypass the generic CC 50 suppression rule specifically for the line voltage sensor token path
                    if (path.includes("/50/") && path.includes("/value/") && !path.includes("66561")) continue;

                    const existing = this.deviceList.find(i => i.path === path);
                    if (existing) {
                        existing.value = this.flattenNestedObject(data.value);
                    } else {
                        let staticType = "switch";
                        const cc = data.command_class;
                        const lowerPath = path.toLowerCase();

                        if (cc === "37") {
                            // D1: binary inbox default → switch (unified 71–72x pool)
                            staticType = "switch";
                        }
                        else if (cc === "38") staticType = "shutter";
                        else if (cc === "48") staticType = "motion";
                        else if (cc === "49") {
                            if (lowerPath.includes("power")) staticType = "power";
                            else if (lowerPath.includes("temp") || lowerPath.includes("humid") || lowerPath.includes("air")) staticType = "temp&hum";
                            else staticType = "sensor";
                        }
                        // Default CC 50 entries to power endpoints, unless they contain the line voltage signature
                        else if (cc === "50") {
                            staticType = path.includes("66561") ? "sensor" : "power";
                        }

                        this.deviceList.push({
                            path: path,
                            node: safeNode,
                            value: this.flattenNestedObject(data.value),
                            selected: false,
                            is_mapped: false,
                            type: staticType,
                            idx: null,
                            name: "",
                            comment_str: "",
                            original_idx: null,
                        });
                        listModified = true;
                    }
                }
            }

            if (listModified) {
                this.recalculateIDXs();
            }
            if (this._baselinePending) {
                this.savedFingerprint = this._mapFingerprint();
                this._captureSavedSnapshot();
                this._baselinePending = false;
            }

            // 3. Clear reloading spinner if a fresh snapshot indicates reload is complete
            if (this.configReloading && fullState.system.system_alert_msgs) {
                const done = (msg) => {
                    const text = msg && msg.message ? String(msg.message) : "";
                    if (window.WanOSReloadAlerts) {
                        return window.WanOSReloadAlerts.COMPLETE.includes(text)
                            || window.WanOSReloadAlerts.isFailed(text);
                    }
                    return text.includes("Config reloaded");
                };
                if (fullState.system.system_alert_msgs.some(done)) {
                    this.configReloading = false;
                }
            }
            if (fullState.system.system_alert_msgs && window.WanOSReloadAlerts) {
                this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(
                    fullState.system.system_alert_msgs
                );
            }
        },

        recalculateIDXs() {
            let reservedIdxs = new Set();

            for (const item of this.deviceList) {
                if (item.selected && item.is_mapped && item.original_idx !== null) {
                    item.idx = item.original_idx;
                    reservedIdxs.add(item.idx);
                }
            }

            for (const item of this.deviceList) {
                if (!item.selected) {
                    item.idx = null;
                    continue;
                }

                if (!item.is_mapped) {
                    let basePrefix = 71;
                    const provType = item.type === "light" ? "switch" : item.type;
                    if (provType === 'shutter') basePrefix = 73;
                    else if (provType === 'power') basePrefix = 74;
                    else if (provType === 'motion') basePrefix = 75;
                    else if (provType === 'temp&hum' || provType === 'sensor') basePrefix = 76;

                    const blockIdxs = Array.from(reservedIdxs).filter(id => Math.floor(id / 1000) === basePrefix);

                    let nextIdx = basePrefix * 1000 + 1;
                    if (blockIdxs.length > 0) {
                        nextIdx = Math.max(...blockIdxs) + 1;
                    }

                    item.idx = nextIdx;
                    reservedIdxs.add(nextIdx);
                }
            }
        },

        async saveAndReloadConfig() {
            this.errorMessage = "";
            this.infoMessage = "";
            let finalMap = [];

            for (const item of this.deviceList) {
                if (item.selected) {
                    if (item.name.trim() === "") {
                        this.errorMessage = `Validation Failed: Please provide a name for Node ${item.node} (${item.type})`;
                        return;
                    }

                    let extraStr = "";
                    if (item.comment_str && item.comment_str.toString().trim() !== "") {
                        extraStr = ` | ${item.comment_str.toString().trim()}`;
                    }

                    finalMap.push({ idx: item.idx, line: `    ${item.idx}: "${item.path} | ${item.name.trim()}${extraStr}"` });
                }
            }

            if (finalMap.length === 0) {
                this.errorMessage = "You must select at least one active endpoint to compile configuration matrices.";
                return;
            }

            let yamlLines = [];
            yamlLines.push(``);
            yamlLines.push(`  # ==============================================================================`);
            yamlLines.push(`  # config_zwave.auto.yaml`);
            yamlLines.push(``);
            yamlLines.push(`  # This file should NOT be edit manually: consult zwaveconfig.html.`);
            yamlLines.push(``);
            yamlLines.push(`  # Z-Wave JS UI: http://10.32.251.30:8091`);
            yamlLines.push(`  # ==============================================================================`);
            yamlLines.push(``);
            yamlLines.push(`zwave:`);
            yamlLines.push(`  # The physical hardware path used by WanOS to verify the stick is plugged in`);
            yamlLines.push(`  usb_path: "${this.usbPath}"`);
            yamlLines.push(``);

            yamlLines.push(`  device_map:`);
            yamlLines.push(`    # 71000: light`);
            yamlLines.push(`    # 72000: switch`);
            yamlLines.push(`    # 73000: shutter`);
            yamlLines.push(`    # 74000: power`);
            yamlLines.push(`    # 75000: motion`);
            yamlLines.push(`    # 76000: temp&hum`);

            finalMap.sort((a, b) => a.idx - b.idx);

            let lastBlock = null;
            for (const entry of finalMap) {
                let currentBlock = Math.floor(entry.idx / 1000);
                if (lastBlock !== null && currentBlock !== lastBlock) {
                    yamlLines.push(``);
                }
                yamlLines.push(entry.line);
                lastBlock = currentBlock;
            }

            const finalYamlString = yamlLines.join('\n');

            this.configReloading = true;
            try {
                const token = localStorage.getItem("wanos_jwt") || "";
                const res = await fetch("/api/config/zwave", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify({ yaml_content: finalYamlString })
                });

                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP Error ${res.status}`);
                }

                this.infoMessage = "Saved. Config reloading…";
                const reloadRes = await fetch("/api/event", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify({ type: "CONFIG_RELOAD_REQUESTED", payload: { source: "api" } })
                });
                if (!reloadRes.ok) throw new Error("Failed to trigger reload signal to backend.");

                this.infoMessage = "Config reload requested";
                this.savedFingerprint = this._mapFingerprint();
                this._captureSavedSnapshot();
                setTimeout(() => {
                    if (this.configReloading) this.configReloading = false;
                }, 10000);
            } catch (err) {
                this.configReloading = false;
                this.errorMessage = "Failed to save configuration: " + err.message;
                this.infoMessage = "";
            }
        }
    };
}