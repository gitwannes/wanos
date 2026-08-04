// --- file: frontend/zwave.js ---

function zwaveApp() {
    return {
        connected: false,
        eventSource: null,
        usbPath: "",
        errorMessage: "",
        deviceList: [],
        configReloading: false,
        searchQuery: "",
        typeFilter: "ALL",
        sortMode: "NODE", // "NODE", "IDX", "NAME"

        // ⚡ Reactive filtering pipeline
        get visibleDeviceList() {
            const shutterNodes = new Set(this.deviceList.filter(i => i.type === 'shutter').map(i => i.node));
            const switchNodes = new Set(this.deviceList.filter(i => i.type === 'switch').map(i => i.node));

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
                // ⚡ Reactive Sorting Logic
                if (this.sortMode === "IDX") {
                    const idxA = a.idx !== null ? a.idx : Number.MAX_SAFE_INTEGER;
                    const idxB = b.idx !== null ? b.idx : Number.MAX_SAFE_INTEGER;
                    if (idxA !== idxB) return idxA - idxB;
                } else if (this.sortMode === "NAME") {
                    return a.name.localeCompare(b.name);
                }

                // Default / Fallback: Sort by Node Number, then Type, then Path
                const nodeA = parseInt(a.node, 10) || 0;
                const nodeB = parseInt(b.node, 10) || 0;
                if (nodeA !== nodeB) return nodeA - nodeB;
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
        },

        connectSSE(token) {
            this.eventSource = new EventSource(`/api/state/sse?jwt=${token}`);
            this.eventSource.onmessage = (e) => {
                const msg = JSON.parse(e.data);

                if (msg.domain === "ping") {
                    this.connected = true;
                    return;
                }

                if (msg.domain === "system") {
                    this.processBackendState({ system: msg.data });
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
                this.connected = true;
            };
            this.eventSource.onerror = () => {
                this.connected = false;
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
                        if (existing) {
                            existing.is_mapped = true;
                            existing.idx = idx;
                            existing.name = name;
                            existing.comment_str = commentStr;
                            existing.original_idx = idx;
                            existing.entity_id = (fullState.device_metadata && fullState.device_metadata[idx]
                                ? fullState.device_metadata[idx].entity_id : null);
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
                                idx: idx,
                                name: name,
                                comment_str: commentStr,
                                original_idx: idx,
                                entity_id: (fullState.device_metadata && fullState.device_metadata[idx]
                                    ? fullState.device_metadata[idx].entity_id : null),
                                is_hidden: fullState.system.hidden_explorer_idxs.includes(idx)
                            });
                            listModified = true;
                        }
                    }
                    this._initialMapDone = true;
                }
            }

            // 2. Unpack Transient Discovery Data Elements
            if (fullState.system.zwave_inbox) {
                // ⚡ SMART DEFAULT HELPER: Scan inbox first to identify which physical nodes have Power telemetry
                const nodesWithPower = new Set();
                for (const [path, data] of Object.entries(fullState.system.zwave_inbox)) {
                    const sn = data.node || data.node_name || path.split('/')[0];
                    const cc = data.command_class;
                    const lp = path.toLowerCase();
                    if (cc === "50" || (cc === "49" && lp.includes("power"))) {
                        nodesWithPower.add(sn);
                    }
                }

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

                        if (cc === "37" || cc === "25") {
                            // ⚡ SMART DEFAULT: If a relay node also has power telemetry, guess Switch (72xxx), else Light (71xxx)
                            staticType = nodesWithPower.has(safeNode) ? "switch" : "light";
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
                            is_hidden: false
                        });
                        listModified = true;
                    }
                }
            }

            if (listModified) {
                this.recalculateIDXs();
            }

            // 3. Clear reloading spinner if a fresh snapshot indicates reload is complete
            if (this.configReloading && fullState.system.system_alert_msgs) {
                if (fullState.system.system_alert_msgs.some(msg => msg.message && msg.message.includes("Config reloaded"))) {
                    this.configReloading = false;
                }
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
                    if (item.type === 'shutter') basePrefix = 73;
                    else if (item.type === 'power') basePrefix = 74;
                    else if (item.type === 'motion') basePrefix = 75;
                    else if (item.type === 'temp&hum' || item.type === 'sensor') basePrefix = 76;

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

        async requestConfigReload() {
            if (this.configReloading) return;
            this.configReloading = true;
            this.errorMessage = "";

            try {
                // Fetch credentials from persistent browser space
                const token = localStorage.getItem("wanos_jwt") || "";
                const res = await fetch("/api/event", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify({ type: "CONFIG_RELOAD_REQUESTED", payload: {} })
                });

                if (!res.ok) throw new Error("Failed to trigger reload signal to backend.");

                // Failsafe timeout in case the SSE response doesn't clear the lock
                setTimeout(() => {
                    if (this.configReloading) this.configReloading = false;
                }, 10000);
            } catch (err) {
                this.configReloading = false;
                this.errorMessage = "Failed to reload: " + err.message;
            }
        },

        async injectAndDownloadYAML() {
            this.errorMessage = "";
            let finalMap = [];
            let hiddenNodes = [];

            for (const item of this.deviceList) {
                if (item.selected) {
                    if (item.is_hidden && item.idx !== null) {
                        const eid = item.entity_id
                            || (this._lastMeta && this._lastMeta[item.idx] && this._lastMeta[item.idx].entity_id);
                        if (eid) {
                            hiddenNodes.push(eid);
                        }
                    }

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

            if (hiddenNodes.length > 0) {
                yamlLines.push(`  hidden_nodes: [${hiddenNodes.join(', ')}]`);
                yamlLines.push(``);
            }

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

            try {
                // 1. Inject Config into the Backend Directory
                // Pull credentials from persistent container
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
                    const errorData = await res.json();
                    throw new Error(errorData.error || `HTTP Error ${res.status}`);
                }

                // 2. Provide Local Download Fallback
                const blob = new Blob([finalYamlString], { type: "text/yaml" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "config_zwave.auto.yaml.txt";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                // Alert the user and suggest an automatic configuration reload
                this.errorMessage = "";
                setTimeout(() => {
                    this.requestConfigReload();
                }, 1000);

            } catch (err) {
                this.errorMessage = "Failed to inject configuration to server: " + err.message;
            }
        }
    };
}