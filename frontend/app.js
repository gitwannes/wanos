// --- file: frontend/app.js ---

function wanosApp() {
    return {
        connected: false,

        state: {
            system: {
                version_major: "v0.0", // ⚡ Reactive placeholder container mapping
                version_full: "v0.0-build_unknown", // ⚡ Reactive placeholder container mapping
                wanos_mqtt_connected: false,
                domoticz_mqtt_connected: false,
                ip_address: "0.0.0.0",
                os_boot_unix: null,
                app_boot_unix: null,
                os_uptime_formatted: { duration: "00:00:00", boot: "--" },
                app_uptime_formatted: { duration: "00:00:00", boot: "--" },
                automations_enabled: true, // Master switch for the logic engine
                domoticz_integration_enabled: false, // ⚡ Switch to block/allow Domoticz messages
                owm_integration_enabled: false, // ⚡ Switch to block/allow OWM polling
                rfxcom_connected: false, // ⚡ Live USB mounting health status
                rfxcom_integration_enabled: false, // ⚡ Switch to block/allow native RFXCOM transmission/reception
                zwave_hardware_connected: false, // ⚡ Tracks physical USB stick presence
                zwave_mqtt_connected: false, // ⚡ Tracks Z-Wave JS UI engine health
                zwave_integration_enabled: false, // ⚡ Switch to block/allow Z-Wave processing
                epson_connected: false, // ⚡ Tracks physical TCP availability of the Epson Projector
                epson_integration_enabled: false, // ⚡ Master UI switch to block/allow Epson commands
                native_rfx_devices: [], // ⚡ Enables reactivity for the dynamic panel
                available_scenes: [], // ⚡ Holds dynamically extracted stateless automations
                hidden_explorer_idxs: [], // ⚡ Devices to hide from the Device Explorer
                hue_presets: {} // ⚡ Dynamically injected from config_hue.yaml
            },
            sensors: {
                outside_temp: null,
                outside_hum: null,
                sunrise_unix: null,
                sunset_unix: null,
                bathroom1_temp: null,
                bathroom1_hum: null,
                cinema_temp: null,
                cinema_hum: null,
                sauna_high_temp: null,
                sauna_high_hum: null,
                sauna_low_temp: null,
                sauna_low_hum: null,
                sauna_calc_temp: null,
                sauna_calc_hum: null,
                pc_power: null,
                pc_power_history: [],
                pc_aux_power: null,
                pc_aux_power_history: [],
                // Liters pre-rounded by the backend (1 decimal). No conversion needed here.
                water_cold_liters: 0.0,
                water_hot_liters: 0.0
            },
            sauna: {
                active: false,
                target_temp: null,
                max_temp: null,
                hold_mode: "autohold",
                modulation_pwm: 0,
                phases_pwm: [0, 0, 0],
                fireorder: "--",
                session_start_time: null,
                session_end_time: null,
                ventilation_state: "OFF",
                ventilation_deadline: null,
                light_color: "#FFD180",
                lcd_text: ""
            },
            ir: {
                active: false,
                modulation_pwm: 0,
                frequency: 0,
                session_start_time: null,
                session_end_time: null
            },
            metrics: {
                // Raw Wh tick counter kept in state for internal tracking.
                // Divide by 1000 at display time to show kWh.
                kwh_wh_ticks: 0,
                douche_active: false,
                douche_start_time: null,
                douche_duration_secs: 0,
                douche_water_liters: 0
            },
            hardware: {
                sht11_connected: false,
                sht11_enabled: false,
                gpio_input_connected: false,
                gpio_input_enabled: false,
                gpio_output_connected: false,
                gpio_output_enabled: false,
                simulations_enabled: false, // Master switch for the physics engine
                safety_pin_active: false, // Hardwired GPIO. Instantly verified locally, safe to default false.
                sensor_errors: []
            },
            // PESSIMISTIC UI ARCHITECTURE: All Domoticz-driven relays are initialized
            // strictly to `null`. This keeps the UI buttons disabled and grayed out
            // until the Python backend explicitly pushes their verified state.
            devices: {
                10001: "CLOSED", // Local GPIO (door_sauna)
                10002: "CLOSED", // Local GPIO (door_bathroom1)
                282: null, // buro
                283: null, // cinema_main
                40001: null, // cinema_schemer
                40002: null, // buro_schemer
                7312: null, // cinema_hue
                7561: null, // sauna_hue
                1500: null, // sauna_zoutlamp
                141: null, // bathroom1_main
                7555: null, // bathroom1_wastafel
                7558: null, // bathroom1_ventilator
                8577: null, // sauna_extrvent
                8567: null, // safety_ssr
                8: null, // pc
                9618: null, // pc_aux
                169: null // gang_boven
            },
            dashboard_map: {}, // ⚡ Store the backend mapping dictionary for labels only
            device_metadata: {}, // ⚡ The dynamic registry powering dashboard.html
            boot_seed: null
        },

        // Dedicated UI Toggle to lock/unlock manual manipulation of the physics simulator
        labControlsEnabled: false,

        // Tracks the execution state of the Sweeper
        sweepRunning: false,

        // Tracks the execution state of the configuration hot-reload loop
        configReloading: false,

        // ⚡ Light Control Modal State
        activeLightId: null,
        activeLightName: "",
        activeLightBri: 100,
        activeLightHex: "#FFD180",
        colorPicker: null, // ⚡ Holds the iro.js UI instance

        // ⚡ Dynamic Device Explorer (dashboard.html) UI States
        searchQuery: "",
        typeFilter: "ALL",   // "ALL", "SWITCH", "SCENE", "BLINDS", "SENSOR"
        statusFilter: "ALL", // "ALL", "ON", "OFF"
        sortMode: "NAME",    // "NAME", "STATUS"

        // ⚡ Reactive Time Heartbeat
        nowUnix: Math.floor(Date.now() / 1000),

        // ⚡ SSE Connection State
        eventSource: null,
        sseWatchdog: null,

        // ⏱️ Structured Chronological Timeline Getter
        get chronologicalTimeline() {
            if (!this.state.system.active_timers) return [];

            // Access this.nowUnix to ensure Alpine registers the dependency for periodic re-evaluations
            const now = this.nowUnix || Math.floor(Date.now() / 1000);

            let list = [];
            for (const itemStr of this.state.system.active_timers) {
                if (!itemStr) continue;
                let t;
                if (typeof itemStr === 'object') {
                    t = itemStr;
                } else {
                    try {
                        t = JSON.parse(itemStr);
                    } catch {
                        // Failsafe for generic string timers missing payload metadata
                        t = { timer_id: itemStr, deadline: 0, name: itemStr, type: "scene", target_state: "" };
                    }
                }
                list.push(t);
            }

            // Sort ascending by absolute deadline
            list.sort((a, b) => a.deadline - b.deadline);

            return list.map(t => {
                const d = new Date(t.deadline * 1000);
                const absTime = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

                const diff = t.deadline - now;
                let relTime = "";
                if (diff <= 0) relTime = "imminent";
                else if (diff < 60) relTime = `in ${diff} sec`;
                else {
                    const mins = Math.floor(diff / 60);
                    const hrs = Math.floor(mins / 60);
                    if (hrs > 0) relTime = `in ${hrs}h ${mins % 60}m`;
                    else relTime = `in ${mins} min`;
                }

                let actionText = "will trigger";
                if (t.target_state) {
                    if (t.type === "blinds") {
                        if (t.target_state === "100") actionText = "will CLOSE";
                        else if (t.target_state === "0") actionText = "will OPEN";
                        else actionText = `will change to ${t.target_state}%`;
                    } else if (t.type === "switch") {
                        actionText = `will turn ${t.target_state}`;
                    } else if (t.type === "scene") {
                        // ⚡ Detailed Scene Intention: Appends the specific scene name for timeline clarity
                        actionText = `will execute scene`;  //  "${t.name}"
                    } else {
                        actionText = `will -> ${t.target_state}`;
                    }
                }

                return {
                    ...t,
                    absTime: absTime,
                    relTime: relTime,
                    actionText: actionText
                };
            });
        },

        // 🔔 Intelligent Alert Routing Getters
        get criticalAlerts() {
            if (!this.state.system.system_alert_msgs) return [];
            return this.state.system.system_alert_msgs.filter(msg => msg.level === 'critical');
        },

        get nonCriticalAlerts() {
            if (!this.state.system.system_alert_msgs) return [];
            // Return sorted newest-first so the bell dropdown feels like a real notification feed
            return this.state.system.system_alert_msgs.filter(msg => msg.level !== 'critical').reverse();
        },

        get unreadAlertCount() {
            return this.nonCriticalAlerts.length;
        },

        // ⚡ Intelligently evaluates if all capable engines are currently running
        get allEnginesStarted() {
            const s = this.state.system;
            const h = this.state.hardware;

            if (!s.automations_enabled) return false;
            if (s.domoticz_mqtt_connected && !s.domoticz_integration_enabled) return false;
            if (s.hue_connected && !s.hue_integration_enabled) return false;
            if (s.epson_connected && !s.epson_integration_enabled) return false;
            if (s.rfxcom_connected && !s.rfxcom_integration_enabled) return false;
            if (s.zwave_hardware_connected && s.zwave_mqtt_connected && !s.zwave_integration_enabled) return false;
            if (s.owm_integration_enabled && !s.owm_integration_enabled) return false;
            if (h.gpio_input_connected && !h.gpio_input_enabled) return false;
            if (h.sht11_connected && !h.sht11_enabled) return false;
            if (h.gpio_output_connected && !h.gpio_output_enabled) return false;

            return true;
        },

        // ⚡ Dynamically compiles a list of disabled backend integrations
        get disabledIntegrationsText() {
            let disabled = [];
            if (!this.state.system.domoticz_integration_enabled) disabled.push("Domoticz");
            if (!this.state.system.automations_enabled) disabled.push("Automation");
            if (!this.state.system.hue_integration_enabled) disabled.push("Hue");
            if (!this.state.system.epson_integration_enabled) disabled.push("Epson projector");
            if (!this.state.system.rfxcom_integration_enabled) disabled.push("RFX");
            if (!this.state.system.zwave_integration_enabled) disabled.push("Z-Wave");
            if (!this.state.system.owm_integration_enabled) disabled.push("OpenWeatherMap");
            if (!this.state.hardware.gpio_input_enabled) disabled.push("GPIO inputs");
            if (!this.state.hardware.gpio_output_enabled) disabled.push("GPIO outputs");
            if (!this.state.hardware.sht11_enabled) disabled.push("temp/hum sensors");
            if (disabled.length === 0) return "";
            return "⚠️ OFFLINE: " + disabled.join(", ");
        },

        get unifiedDeviceList() {
            let list = [];

            // 1. Map actual devices from the backend metadata registry
            for (const [idxStr, meta] of Object.entries(this.state.device_metadata)) {

                // ⚡ INTEGRATION ORIGIN GUARD
                // Automatically drop devices from the UI if their parent integration is disabled.
                if (meta.origin === 'domoticz' && !this.state.system.domoticz_integration_enabled) continue;
                if (meta.origin === 'rfxcom' && !this.state.system.rfxcom_integration_enabled) continue;
                if (meta.origin === 'hue' && !this.state.system.hue_integration_enabled) continue;
                if (meta.origin === 'zwave' && !this.state.system.zwave_integration_enabled) continue;

                const idx = parseInt(idxStr, 10);

                // ⚡ CONFIG EXCLUSION GUARD
                // Automatically drop devices explicitly blacklisted in config.yaml
                if (this.state.system.hidden_explorer_idxs.includes(idx))
                    continue;

                const rawValue = this.state.devices[idx];
                let isOn = false;

                if (meta.type === 'blinds') {
                    // Shutters: > 0% = ON
                    isOn = parseInt(rawValue, 10) > 0;
                } else if (meta.type === 'switch' || meta.type === 'light') {
                    // ⚡ RICH PAYLOAD SUPPORT: Parse "ON" state whether it's a flat string or a dictionary object
                    isOn = (typeof rawValue === 'object' && rawValue !== null) ? rawValue.state === 'ON' : rawValue === 'ON';
                }

                list.push({
                    id: idx,
                    name: meta.name,
                    type: meta.type,
                    raw_value: rawValue,
                    is_on: isOn,
                    is_hue: meta.origin === 'hue'
                });
            }

            // 2. Map Stateless Scenes
            // ⚡ Only display scenes if both major action hubs (Domoticz & RFX) are online
            if (this.state.system.available_scenes &&
                this.state.system.domoticz_integration_enabled &&
                this.state.system.rfxcom_integration_enabled) {
                for (const scene of this.state.system.available_scenes) {
                    list.push({
                        id: scene.event,
                        name: scene.name,
                        type: 'scene',
                        raw_value: null,
                        is_on: null // Stateless element
                    });
                }
            }

            // 3. Apply Text Search
            if (this.searchQuery.trim() !== "") {
                const q = this.searchQuery.toLowerCase();
                list = list.filter(item => item.name.toLowerCase().includes(q));
            }

            // 4. Apply Type Filter
            if (this.typeFilter !== "ALL") {
                list = list.filter(item => {
                    // Isolates traditional non-Hue hardware relays, binary switches, and sockets
                    if (this.typeFilter === "SWITCH") return item.type === 'switch' && !item.is_hue;
                    // Isolates advanced local API Hue mesh channels, rooms, and zones (IDX >= 50000)
                    if (this.typeFilter === "HUE") return item.is_hue;
                    if (this.typeFilter === "SCENE") return item.type === 'scene';
                    if (this.typeFilter === "BLINDS") return item.type === 'blinds';
                    if (this.typeFilter === "SENSOR") return item.type === 'temp' || item.type === 'hum' || item.type === 'temp_hum' || item.type === 'power';
                    return true;
                });
            }

            // 5. Apply Status Filter (Hide sensors & scenes if ON/OFF is requested)
            if (this.statusFilter !== "ALL") {
                list = list.filter(item => {
                    if (item.type === 'temp' || item.type === 'hum' || item.type === 'temp_hum' || item.type === 'power' || item.type === 'scene') {
                        return false; // Safely drop elements that lack binary state
                    }
                    if (this.statusFilter === "ON") return item.is_on;
                    if (this.statusFilter === "OFF") return !item.is_on;
                    return true;
                });
            }

            // 6. Apply Nested Sort
            list.sort((a, b) => {
                if (this.sortMode === "STATUS") {
                    // 1 (ON) sorts before 0 (OFF) before -1 (Stateless)
                    const statusA = a.is_on === true ? 1 : (a.is_on === false ? 0 : -1);
                    const statusB = b.is_on === true ? 1 : (b.is_on === false ? 0 : -1);
                    if (statusA !== statusB) {
                        return statusB - statusA;
                    }
                } else if (this.sortMode === "NAME") {
                    // Sort primarily by Type (Groups items logically)
                    if (a.type !== b.type) {
                        return a.type.localeCompare(b.type);
                    }
                }
                // Universal Fallback: Alphabetical by Name
                return a.name.localeCompare(b.name);
            });

            return list;
        },

        // ⚡ IR Snapping Matrix (Values & Legacy Frequencies)
        // Solid State Relays (SSRs) must align with the 50Hz European AC grid (100 zero-crossings per second).
        // Standard PWM causes severe light flickering. This array maps specific power percentages to exact zero-crossing frequencies:
        // 0%   = 0Hz
        // 25%  = 25Hz (1 zero-crossing ON, 3 OFF)
        // 33%  = 33Hz (1 zero-crossing ON, 2 OFF)
        // 50%  = 50Hz (1 zero-crossing ON, 1 OFF)
        // 67%  = 33Hz (2 zero-crossings ON, 1 OFF)
        // 75%  = 25Hz (3 zero-crossings ON, 1 OFF)
        // 100% = 5Hz  (All ON - frequency technically irrelevant here, but 5Hz keeps lgpio stable)
        irStepIndex: 5, // Defaults to index 5 (75%)
        irStepValues: [0, 25, 33, 50, 67, 75, 100],
        irStepFreqs: [0, 25, 33, 50, 33, 25, 5],

        labSaunaHighTemp: null,
        labSaunaHighHum: null,
        labSaunaLowTemp: null,
        labSaunaLowHum: null,
        labBathroom1Temp: null,
        labBathroom1Hum: null,
        labCinemaTemp: null,
        labCinemaHum: null,
        labOutsideTemp: null,
        labOutsideHum: null,

        // Session Trackers cleanly split for multi-component use
        saunaElapsedText: "00:00:00",
        saunaRemainingText: "00:00:00",
        progressPercent: 0,

        irElapsedText: "00:00:00",
        irRemainingText: "00:00:00",

        ventRemainingText: "00:00:00",
        doucheElapsedText: "00:00:00",

        sunriseRelativeText: "",
        sunsetRelativeText: "",

        init() {
            console.log("🚀 WanOS Web Controller initializing...");

            // ⚡ URL Query Parameters Parser
            // Automatically extracts and seeds filters on page boot, stripping literal quotes if passed
            const urlParams = new URLSearchParams(window.location.search);

            if (urlParams.has('search')) {
                // Cleanly strips bounding single or double quotes from the string payload
                this.searchQuery = urlParams.get('search').replace(/^["']|["']$/g, '');
            }

            if (urlParams.has('state')) {
                const stateParam = urlParams.get('state').replace(/^["']|["']$/g, '').toUpperCase();
                // Map logical semantic device states directly back to binary dashboard filters
                if (stateParam === 'ON' || stateParam === 'CLOSED') {
                    this.statusFilter = 'ON';
                } else if (stateParam === 'OFF' || stateParam === 'OPEN') {
                    this.statusFilter = 'OFF';
                }
            }

            this.connectSSE();
            setInterval(this.ticker.bind(this), 1000);
        },

        async fetchFullSnapshot() {
            // Fetches the complete state from /api/state and replaces the local store.
            try {
                const res = await fetch("/api/state");
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const fullState = await res.json();
                this._applyFullSnapshot(fullState);
                console.log("✅ Full state snapshot loaded.");
            } catch (err) {
                console.error("⚠️ Failed to load full state snapshot:", err);
            }
        },

        _applyFullSnapshot(fullState) {
            // Defensive defaults for any fields that may be absent or improperly typed
            const p = fullState.sauna.phases_pwm;
            if (p && typeof p === 'object' && !Array.isArray(p) && 'U' in p && 'V' in p && 'W' in p) {
                for (const phase of ["U", "V", "W"]) {
                    let v = fullState.sauna.phases_pwm[phase];
                    fullState.sauna.phases_pwm[phase] = (v === null || v === undefined || isNaN(v)) ? 0 : v;
                }
            } else {
                fullState.sauna.phases_pwm = {"U": 0, "V": 0, "W": 0};
            }

            if (!fullState.hardware.sensor_errors) fullState.hardware.sensor_errors = [];
            fullState.sauna.modulation_pwm = fullState.sauna.modulation_pwm ?? 0;

            // Alpine Reactivity Preservation
            for (const domain of ["system", "sensors", "sauna", "ir", "metrics", "hardware", "device_metadata"]) {
                if (fullState[domain]) {
                    this.state[domain] = Object.assign({}, this.state[domain], fullState[domain]);
                }
            }

            if (fullState.dashboard_map) {
                this.state.dashboard_map = fullState.dashboard_map;
            }

            // ⚡ Natively merge the numeric IDXs directly without any string translation loops!
            if (fullState.devices) {
                this.state.devices = Object.assign({}, this.state.devices, fullState.devices);
            }

            if (fullState.boot_seed) {
                this.state.boot_seed = fullState.boot_seed;
            }

            this.syncIRStepIndex();

            if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                this.syncLabControls();
            }

            // ⚡ Instantly drop the loading screen so the user sees the populated data
            this.connected = true;
        },

        _applyDomainDelta(domain, data) {
            // 🛡️ Enforce immutability: Clone the incoming payload so we don't mutate the caller's parsed SSE object
            const payload = { ...data };

            // Merges a single changed domain subtree into the reactive store.
            if (domain === "sauna") {
                const p = payload.phases_pwm;
                if (p && typeof p === 'object' && !Array.isArray(p) && 'U' in p && 'V' in p && 'W' in p) {
                    // Deep clone the nested object to prevent mutating the inner array/object
                    payload.phases_pwm = { ...p };
                    for (const phase of ["U", "V", "W"]) {
                        let v = payload.phases_pwm[phase];
                        payload.phases_pwm[phase] = (v === null || v === undefined || isNaN(v)) ? 0 : v;
                    }
                } else {
                    payload.phases_pwm = {"U": 0, "V": 0, "W": 0};
                }
                payload.modulation_pwm = payload.modulation_pwm ?? 0;
            }
            if (domain === "hardware") {
                if (!payload.sensor_errors) payload.sensor_errors = [];
            }
            if (domain === "devices") {
                // Merge device keys individually natively!
                this.state.devices = Object.assign({}, this.state.devices, payload);
                if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                    this.syncLabControls();
                }
                return;
            }

            this.state[domain] = Object.assign({}, this.state[domain], payload);

            // ⚡ INTELLIGENT UI UNLOCKER: Watch for backend sweep or config completion dictionaries
            if (domain === "system" && payload.system_alert_msgs) {
                if (payload.system_alert_msgs.some(msg => msg.message && msg.message.includes("Sweeper complete"))) {
                    this.sweepRunning = false;
                }
                if (payload.system_alert_msgs.some(msg => msg.message && (msg.message.includes("Config reloaded") || msg.message.includes("Config reload failed")))) {
                    this.configReloading = false;
                }
            }

            // Re-sync components whenever their domain updates arrive
            if (domain === "ir") this.syncIRStepIndex();

            // Re-sync lab controls whenever sensors or sauna domain updates arrive
            if ((domain === "sensors" || domain === "sauna") &&
                (!document.activeElement || !document.activeElement.classList.contains('lab-slider'))) {
                this.syncLabControls();
            }
        },

        connectSSE() {
            // Fetch a full snapshot first, then open the delta stream.
            // This guarantees the store is coherent before any partial updates arrive.
            this.fetchFullSnapshot().then(() => {
                // 🛡️ Prevent memory/connection leaks if connectSSE is called multiple times
                if (this.eventSource) {
                    this.eventSource.close();
                }

                this.eventSource = new EventSource("/api/state/sse");

                // ⏱️ Sliding Watchdog Guardian Loop
                const resetWatchdog = () => {
                    if (this.sseWatchdog) clearTimeout(this.sseWatchdog);
                    this.sseWatchdog = setTimeout(() => {
                        console.warn("⚠️ Watchdog Timeout! No server signal detected for 10s. Forcing reconnect...");
                        this.connected = false;
                        if (this.eventSource) this.eventSource.close();
                        setTimeout(() => this.connectSSE(), 3000);
                    }, 10000); // 2x the 5-second backend ping interval
                };

                resetWatchdog();

                this.eventSource.onmessage = (event) => {
                    // This is where the data is received from the backend, main.py
                    try {
                        // Any incoming data frame proves the underlying pipeline is alive
                        resetWatchdog();
                        const msg = JSON.parse(event.data);

                        if (msg.domain === "ping") {
                            this.connected = true;
                            return;
                        }

                        this._applyDomainDelta(msg.domain, msg.data);
                        this.connected = true;
                    } catch (err) {
                        console.error("⚠️ Failed parsing SSE delta update:", err);
                    }
                };

                this.eventSource.onerror = (err) => {
                    if (this.sseWatchdog) clearTimeout(this.sseWatchdog);
                    this.connected = false;
                    console.error("❌ SSE stream broke. Re-linking context in 3s...");
                    if (this.eventSource) this.eventSource.close();
                    // On reconnect, fetch a fresh full snapshot before resuming deltas
                    setTimeout(() => this.connectSSE(), 3000);
                };
            });
        },

        ticker() {
            const now = Math.floor(Date.now() / 1000);
            this.nowUnix = now; // Binds local tick to reactive state engine

            // ⏱️ Dynamic Uptime Live Generators
            if (this.state.system.os_boot_unix) {
                this.state.system.os_uptime_formatted = this.formatExtendedUptime(this.state.system.os_boot_unix, now);
            }
            if (this.state.system.app_boot_unix) {
                this.state.system.app_uptime_formatted = this.formatExtendedUptime(this.state.system.app_boot_unix, now);
            }

            // Sauna Timeline Evaluation
            if (this.state.sauna.active && this.state.sauna.session_start_time && this.state.sauna.session_end_time) {
                const start = this.state.sauna.session_start_time;
                const end = this.state.sauna.session_end_time;

                if (end < 1000000000) {
                    // Timer not yet triggered: session_end_time holds raw duration seconds,
                    // not an absolute Unix timestamp. Display as countdown without progress bar.
                    this.saunaElapsedText = this.formatTime(Math.max(0, now - start));
                    this.saunaRemainingText = this.formatTime(end);
                    this.progressPercent = 0;
                } else {
                    // Timer triggered: session_end_time is an absolute Unix timestamp.
                    const elapsed = Math.max(0, now - start);
                    const remaining = Math.max(0, end - now);
                    const totalDuration = end - start;

                    this.saunaElapsedText = this.formatTime(elapsed);
                    this.saunaRemainingText = this.formatTime(remaining);
                    this.progressPercent = totalDuration > 0 ? Math.min(100, (elapsed / totalDuration) * 100) : 0;
                }
            } else {
                this.saunaElapsedText = "00:00:00";
                this.saunaRemainingText = "00:00:00";
                this.progressPercent = 0;
            }

            // IR Timeline Evaluation
            if (this.state.ir.active && this.state.ir.session_start_time && this.state.ir.session_end_time) {
                const irElapsed = Math.max(0, now - this.state.ir.session_start_time);
                const irRemain = Math.max(0, this.state.ir.session_end_time - now);
                this.irElapsedText = this.formatTime(irElapsed);
                this.irRemainingText = this.formatTime(irRemain);
            } else {
                this.irElapsedText = "00:00:00";
                this.irRemainingText = "00:00:00";
            }

            if (this.state.sauna.ventilation_state !== "OFF" && this.state.sauna.ventilation_deadline) {
                const vRemain = Math.max(0, this.state.sauna.ventilation_deadline - now);
                this.ventRemainingText = this.formatTime(vRemain);
            } else {
                this.ventRemainingText = "00:00:00";
            }

            if (this.state.metrics.douche_active && this.state.metrics.douche_start_time) {
                const dElapsed = Math.max(0, now - this.state.metrics.douche_start_time);
                this.doucheElapsedText = this.formatTime(dElapsed);
            } else if (this.state.metrics.douche_duration_secs > 0) {
                this.doucheElapsedText = this.formatTime(this.state.metrics.douche_duration_secs);
            } else {
                this.doucheElapsedText = "00:00:00";
            }

            // Sun Cycle Live Relative Trackers
            if (this.state.sensors.sunrise_unix) {
                this.sunriseRelativeText = this.getRelativeTime(this.state.sensors.sunrise_unix, now);
            } else {
                this.sunriseRelativeText = "";
            }

            if (this.state.sensors.sunset_unix) {
                this.sunsetRelativeText = this.getRelativeTime(this.state.sensors.sunset_unix, now);
            } else {
                this.sunsetRelativeText = "";
            }
        },

        formatTime(totalSeconds) {
            const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
            const s = (Math.floor(totalSeconds) % 60).toString().padStart(2, '0');
            return `${h}:${m}:${s}`;
        },

        formatExtendedUptime(bootUnix, now) {
            const totalSeconds = Math.max(0, now - bootUnix);

            // 1. Calculate duration component zero-padded to dd:HH:MM:ss
            const d = Math.floor(totalSeconds / 86400).toString().padStart(2, '0');
            const h = Math.floor((totalSeconds % 86400) / 3600).toString().padStart(2, '0');
            const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
            const s = (Math.floor(totalSeconds) % 60).toString().padStart(2, '0');
            const durationStr = `${d}d ${h}:${m}:${s}`;

            // 2. Parse absolute historical boot timestamp (YYYY-MM-DD HH:mm:ss)
            const dateObj = new Date(bootUnix * 1000);
            const year = dateObj.getFullYear();
            const month = (dateObj.getMonth() + 1).toString().padStart(2, '0');
            const date = dateObj.getDate().toString().padStart(2, '0');
            const hours = dateObj.getHours().toString().padStart(2, '0');
            const mins = dateObj.getMinutes().toString().padStart(2, '0');
            const secs = dateObj.getSeconds().toString().padStart(2, '0');
            const bootStr = `${year}-${month}-${date} ${hours}:${mins}:${secs}`;

            return { duration: durationStr, boot: bootStr };
        },

        getSparkline(data) {
            if (!data || data.length < 2) return "";

            const max = Math.max(...data);
            const min = Math.min(...data);
            const range = max - min;

            const width = 100;
            const height = 30;

            const points = data.map((val, i) => {
                const x = (i / (data.length - 1)) * width;
                let y;

                if (range === 0) {
                    y = val === 0 ? height : height / 2;
                } else {
                    y = height - ((val - min) / range) * height;
                }

                return `${x},${y}`;
            });
            return points.join(" ");
        },

        syncLabControls() {
            const sns = this.state.sensors;
            const seed = this.state.boot_seed;

            if (!seed) return;

            this.labSaunaHighTemp = sns.sauna_high_temp ?? seed.sauna_high_temp;
            this.labSaunaHighHum  = sns.sauna_high_hum  ?? seed.sauna_high_hum;
            this.labSaunaLowTemp  = sns.sauna_low_temp  ?? seed.sauna_low_temp;
            this.labSaunaLowHum   = sns.sauna_low_hum   ?? seed.sauna_low_hum;
            this.labBathroom1Temp = sns.bathroom1_temp  ?? seed.bathroom1_temp;
            this.labBathroom1Hum  = sns.bathroom1_hum   ?? seed.bathroom1_hum;
            this.labCinemaTemp    = sns.cinema_temp     ?? seed.cinema_temp;
            this.labCinemaHum     = sns.cinema_hum      ?? seed.cinema_hum;
            this.labOutsideTemp   = sns.outside_temp    ?? seed.outside_temp;
            this.labOutsideHum    = sns.outside_hum     ?? seed.outside_hum;
        },

        async publishEvent(eventType, payload = {}) {
            try {
                await fetch("/api/event", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ type: eventType, payload: payload })
                });
            } catch (error) {
                console.error(`💥 Event transmission collapsed [${eventType}]:`, error);
            }
        },

        // 🛡️ LEGACY API WRAPPER: Prevents breaking existing HTML files that still call dispatchEvent directly
        dispatchEvent(eventType, payload = {}) {
            console.warn("Deprecation notice: dispatchEvent shadows a native DOM API. It has been renamed to publishEvent. Please update your HTML templates.");
            return this.publishEvent(eventType, payload);
        },

        // 🔔 Alert UI Action Dispatchers
        dismissAlert(id) {
            this.publishEvent("ALERT_DISMISSED", { id: id });
        },

        clearNonCriticalAlerts() {
            this.publishEvent("ALERT_CLEAR_NON_CRITICAL");
        },

        injectLabMetric(eventType, idx, targetValue) {
            const payload = {
                idx: parseInt(idx, 10),
                value: eventType === "TEMP_UPDATED" ? parseFloat(targetValue) : parseInt(targetValue, 10),
                lab_override: true
            };
            this.publishEvent(eventType, payload);
        },

        toggleSauna() {
            if (this.state.sensors.sauna_calc_temp == null) {
                console.warn("UI locked: Cannot start Sauna without valid temperature data.");
                return;
            }
            const action = this.state.sauna.active ? "SAUNA_OFF" : "SAUNA_ON";
            this.publishEvent(action);
        },

        updateSaunaSetpoint() {
            this.publishEvent("SAUNA_SETPOINT_CHANGED", { target: parseFloat(this.state.sauna.target_temp) });
        },

        syncIRStepIndex() {
            const pwm = this.state.ir.modulation_pwm;
            const idx = this.irStepValues.indexOf(pwm);
            if (idx !== -1) this.irStepIndex = idx;
        },

        updateIRLocal() {
            // Instantly updates the UI badge number while dragging the slider
            this.state.ir.modulation_pwm = this.irStepValues[this.irStepIndex];
        },

        updateIRSetpoint() {
            // Fires the final selected value and required frequency to the backend
            const pwm = this.irStepValues[this.irStepIndex];
            const freq = this.irStepFreqs[this.irStepIndex];
            this.state.ir.modulation_pwm = pwm;
            this.publishEvent("IR_MODULATION_UPDATED", { pwm: pwm, freq: freq });
        },

        toggleSaunaHold() {
            this.publishEvent("SAUNA_HOLD_TOGGLED");
        },

        adjustSaunaTimer(minutesToAdd) {
            this.publishEvent("SAUNA_TIMER_ADJUSTED", { minutes: minutesToAdd });
        },

        toggleIR() {
            if (this.state.sensors.sauna_calc_temp == null) {
                console.warn("UI locked: Cannot start IR without valid temperature data.");
                return;
            }
            const action = this.state.ir.active ? "IR_OFF" : "IR_ON";
            this.publishEvent(action);
        },

        toggleSHT11() {
            const nextState = !this.state.hardware.sht11_enabled;
            this.publishEvent("SHT11_TOGGLED", { enabled: nextState });
        },

        toggleGPIOInput() {
            const nextState = !this.state.hardware.gpio_input_enabled;
            this.publishEvent("GPIO_INPUT_TOGGLED", { enabled: nextState });
        },

        toggleGPIOOutput() {
            const nextState = !this.state.hardware.gpio_output_enabled;
            this.publishEvent("GPIO_OUTPUT_TOGGLED", { enabled: nextState });
        },

        toggleAutomations() {
            const nextState = !this.state.system.automations_enabled;
            this.publishEvent("AUTOMATIONS_TOGGLED", { enabled: nextState });
        },

        toggleDomoticz() {
            const nextState = !this.state.system.domoticz_integration_enabled;
            this.publishEvent("DOMOTICZ_TOGGLED", { enabled: nextState });
        },

        toggleZwave() {
            const nextState = !this.state.system.zwave_integration_enabled;
            this.publishEvent("ZWAVE_TOGGLED", { enabled: nextState });
        },

        toggleRFXCOM() {
            const nextState = !this.state.system.rfxcom_integration_enabled;
            this.publishEvent("RFXCOM_TOGGLED", { enabled: nextState });
        },

        toggleOWM() {
            const nextState = !this.state.system.owm_integration_enabled;
            this.publishEvent("OWM_TOGGLED", { enabled: nextState });
        },

        toggleEpson() {
            const nextState = !this.state.system.epson_integration_enabled;
            this.publishEvent("EPSON_TOGGLED", { enabled: nextState });
        },

        toggleSimulations() {
            const nextState = !this.state.hardware.simulations_enabled;
            this.publishEvent("SIMULATIONS_TOGGLED", { enabled: nextState });
        },

        async enableAllIntegrations() {
            this.publishEvent("ALERT_INJECTED", { msg_text: "🚀 Initiating Master Start Sequence..." });

            // ⚡ NOTE ON AWAITS:
            // `await this.publishEvent` only waits for the HTTP 200 OK (the event being accepted into the queue).
            // It does NOT wait for the backend StateManager to actually process and propagate the state.
            // These awaits act as a network traffic pacer to prevent API DDoS, rather than strict logical sequence locks.

            // Phase 1: Arm the Brain (Automations)
            await this.publishEvent("AUTOMATIONS_TOGGLED", { enabled: true });

            // Phase 2: Power the Actuators (Hardware Bridges & Displays)
            await this.publishEvent("HUE_TOGGLED", { enabled: true });
            await this.publishEvent("EPSON_TOGGLED", { enabled: true });
            await this.publishEvent("RFXCOM_TOGGLED", { enabled: true });

            // Phase 3: Enable Domoticz (State Database Sync)
            await this.publishEvent("DOMOTICZ_TOGGLED", { enabled: true });

            // Phase 4: Enable Z-Wave
            await this.publishEvent("ZWAVE_TOGGLED", { enabled: true });

            // Phase 5: The Cloud (Low-priority polling)
            await this.publishEvent("OWM_TOGGLED", { enabled: true });

            // Phase 6: Arm Physical Inputs
            await this.publishEvent("GPIO_INPUT_TOGGLED", { enabled: true });
            if (this.state.hardware.sht11_connected) {
                await this.publishEvent("SHT11_TOGGLED", { enabled: true });
            }

            // Phase 7: Hardware Stabilization Wait (Give the SHT11 loop time to sample the room)
            this.publishEvent("ALERT_INJECTED", { msg_text: "⏳ Waiting 2 seconds for sensor bus stabilization..." });
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Phase 8: Arm High-Voltage Physical Outputs
            await this.publishEvent("GPIO_OUTPUT_TOGGLED", { enabled: true });

            // Phase 9: Ensure Time-Series & Auto-Timers are synchronized
            // (Reuses the dedicated sweep macro to enforce UI locks!)
            await this.requestSystemSweep();
        },

        injectLabDoorChange(idx, isOpen) {
            this.publishEvent("DOOR_CHANGED", { idx: parseInt(idx, 10), is_open: isOpen });
        },

        injectLabHubStateChange(idx, isOn) {
            // 🛡️ GHOST CLICK GUARD:
            if (this.state.devices[idx] === null) {
                console.warn(`[UI Guard] Blocked browser ghost click for IDX ${idx}. System still syncing.`);
                return;
            }

            const targetState = isOn ? "ON" : "OFF";
            const current = this.state.devices[idx];

            // ⚡ Extract state safely whether it's a flat string or a rich dictionary
            const currentState = (typeof current === 'object' && current !== null) ? current.state : current;

            if (currentState === targetState) {
                return;
            }

            this.publishEvent("HUB_STATE_CHANGED", { idx: parseInt(idx, 10), state: targetState });
        },

        // =========================================================================
        // 🎨 NATIVE LIGHTING CONTROL MATHEMATICS & DISPATCHERS
        // =========================================================================

        openLightModal(item) {
            this.activeLightId = item.id;
            this.activeLightName = item.name;

            // Load existing color from backend state, or default to Warm White
            if (typeof item.raw_value === 'object' && item.raw_value !== null) {
                this.activeLightBri = item.raw_value.bri !== undefined ? item.raw_value.bri : 100;
                this.activeLightHex = this.xyToHex(
                    item.raw_value.xy ? item.raw_value.xy[0] : undefined,
                    item.raw_value.xy ? item.raw_value.xy[1] : undefined,
                    this.activeLightBri
                );
            } else {
                this.activeLightBri = 100;
                this.activeLightHex = "#FFD180";
            }

            // ⚡ Initialize iro.js exactly once, then just update its color dynamically
            if (!this.colorPicker) {
                // Ensure the DOM element is visible before mounting
                setTimeout(() => {
                    this.colorPicker = new iro.ColorPicker("#color-picker-container", {
                        width: 220,
                        color: this.activeLightHex,
                        layout: [
                            { component: iro.ui.Wheel, options: {} }
                        ]
                    });

                    // Update Alpine state when user drags the wheel
                    this.colorPicker.on('color:change', (color) => {
                        this.activeLightHex = color.hexString;
                    });

                    // Send API call ONLY when the user stops dragging to prevent network spam
                    this.colorPicker.on('input:end', (color) => {
                        this.updateActiveLightState();
                    });
                }, 50); // Tiny delay ensures DaisyUI modal has rendered the div
            } else {
                // If it already exists, just snap the wheel to the correct color
                this.colorPicker.color.hexString = this.activeLightHex;
            }

            document.getElementById('light_control_modal').showModal();
        },

        applyPreset(preset) {
            this.activeLightBri = preset.bri;
            // The preset has xy coordinates. We need to convert xy back to hex for the UI wheel!
            this.activeLightHex = this.xyToHex(preset.xy[0], preset.xy[1], preset.bri);

            // Instantly snap the iro.js color wheel to the new preset color
            if (this.colorPicker) {
                this.colorPicker.color.hexString = this.activeLightHex;
            }

            // Dispatch the command to the physical bulb, but leave the modal open for tweaking!
            this.updateActiveLightState();
        },

        updateActiveLightState() {
            if (!this.activeLightId) return;
            const xy = this.hexToXY(this.activeLightHex);

            // Dispatch a rich dictionary. We pass force: true so the backend guarantees
            // transmission even if the bulb's power state is already "ON".
            this.publishEvent("HUB_STATE_CHANGED", {
                idx: parseInt(this.activeLightId, 10),
                state: "ON",
                bri: parseInt(this.activeLightBri, 10),
                xy: xy,
                force: true
            });
        },

        // 🧮 Converts CIE 1931 [x, y] color space to standard Hex string for the UI Color Wheel
        xyToHex(x, y, bri) {
            if (x === undefined || y === undefined) return "#FFD180";

            let z = 1.0 - x - y;
            let Y = (bri !== undefined ? bri : 100) / 100.0;
            let X = (Y / y) * x;
            let Z = (Y / y) * z;

            // Wide RGB D65 conversion matrix
            let r = X * 1.656492 - Y * 0.354851 - Z * 0.255038;
            let g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152;
            let b =  X * 0.051713 - Y * 0.121364 + Z * 1.011530;

            // Reverse gamma correction
            r = r <= 0.0031308 ? 12.92 * r : (1.0 + 0.055) * Math.pow(r, (1.0 / 2.4)) - 0.055;
            g = g <= 0.0031308 ? 12.92 * g : (1.0 + 0.055) * Math.pow(g, (1.0 / 2.4)) - 0.055;
            b = b <= 0.0031308 ? 12.92 * b : (1.0 + 0.055) * Math.pow(b, (1.0 / 2.4)) - 0.055;

            // Clamp and convert to Hex
            r = Math.max(0, Math.min(1, r));
            g = Math.max(0, Math.min(1, g));
            b = Math.max(0, Math.min(1, b));

            const toHex = (c) => Math.round(c * 255).toString(16).padStart(2, '0');
            return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
        },

        // 🧮 Converts standard Hex string from the UI Color Wheel to CIE 1931 [x, y] for the Hue API
        hexToXY(hex) {
            hex = hex.replace('#', '');
            let r = parseInt(hex.substring(0, 2), 16) / 255.0;
            let g = parseInt(hex.substring(2, 4), 16) / 255.0;
            let b = parseInt(hex.substring(4, 6), 16) / 255.0;

            // Apply gamma correction
            r = (r > 0.04045) ? Math.pow((r + 0.055) / 1.055, 2.4) : (r / 12.92);
            g = (g > 0.04045) ? Math.pow((g + 0.055) / 1.055, 2.4) : (g / 12.92);
            b = (b > 0.04045) ? Math.pow((b + 0.055) / 1.055, 2.4) : (b / 12.92);

            // Convert to XYZ color space
            let X = r * 0.664511 + g * 0.154324 + b * 0.162028;
            let Y = r * 0.283881 + g * 0.668433 + b * 0.047685;
            let Z = r * 0.000088 + g * 0.072310 + b * 0.986039;

            if ((X + Y + Z) === 0) return [0.3127, 0.3290]; // Failsafe to standard white

            // Calculate final CIE 1931 xy coordinates
            let x = X / (X + Y + Z);
            let y = Y / (X + Y + Z);

            return [parseFloat(x.toFixed(4)), parseFloat(y.toFixed(4))];
        },

        // 🛡️ PC Power Safety Interceptor
        handlePCToggleClick(event) {
            event.preventDefault(); // Universally stop the toggle from visually flipping
            document.getElementById('pc_power_modal').showModal(); // Open DaisyUI modal
        },

        // Executed only if the user confirms the action in the modal
        confirmPCPowerToggle() {
            document.getElementById('pc_power_modal').close();
            // 8 is the immutable IDX for the PC Power Relay
            const isCurrentlyOn = this.state.devices[8] === 'ON';
            this.injectLabHubStateChange(8, !isCurrentlyOn);
        },

        // 🛡️ Hardware Output Safety Interceptor
        handleOutputToggleClick(event) {
            event.preventDefault(); // Stop the toggle from visually flipping
            document.getElementById('hardware_output_modal').showModal();
        },

        // Executed only if the user confirms the bus switch
        confirmOutputModeToggle() {
            document.getElementById('hardware_output_modal').close();
            this.toggleGPIOOutput();
        },

        injectWaterPulse(fluidType) {
            // Injects 396 pulses = exactly 1 liter for lab testing
            this.publishEvent("WATER_PULSE", { fluid: fluidType, count: 396, lab_override: true });
        },

        formatUnixTime(unixTime) {
            if (!unixTime) return "--:--:--";
            const date = new Date(unixTime * 1000);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        },

        // Calculates countdown/countup string relative to current time
        getRelativeTime(targetUnix, nowUnix) {
            const diff = targetUnix - nowUnix;
            const absDiff = Math.abs(diff);
            const timeStr = this.formatTime(absDiff);

            if (diff > 0) {
                return `(in ${timeStr})`;
            } else {
                return `(${timeStr} ago)`;
            }
        },

        async reloadFrontend() {
            try {
                // 1. Force the browser network engine to silently download a fresh copy of app.js
                // This updates the internal cache behind the scenes.
                await fetch('app.js', { cache: 'reload' });
            } catch (err) {
                console.warn("⚠️ Cache bust fetch failed, proceeding with standard reload.");
            }

            // 2. Perform the standard reload. The browser will now load the freshly cached app.js!
            window.location.reload();
        },

        injectTestAlert() {
            const msg = `🧪 Simulated Error - Local Browser Injection`;
            this.publishEvent("ALERT_INJECTED", { msg_text: msg });
        },

        async requestSystemSweep() {
            if (this.sweepRunning) return;
            this.sweepRunning = true;

            this.publishEvent("ALERT_INJECTED", { msg_text: "🧹 System sweep running..." });

            await this.publishEvent("SYSTEM_SWEEP_REQUESTED");

            // 🛡️ EMERGENCY FAILSAFE ONLY
            // The button is normally unlocked instantly by the SSE stream interceptor above.
            // This timeout only exists to prevent a permanently frozen button
            // if the network cable is unplugged exactly while the sweep is calculating.
            setTimeout(() => {
                if (this.sweepRunning) {
                    this.sweepRunning = false;
                    console.warn("UI Guard: Sweeper lock released via timeout failsafe.");
                }
            }, 30 * 1000);
        },

        async requestConfigReload() {
            if (this.configReloading) return;
            this.configReloading = true;

            this.publishEvent("ALERT_INJECTED", { msg_text: "🔄 Reloading all config yaml configurations..." });

            await this.publishEvent("CONFIG_RELOAD_REQUESTED");

            setTimeout(() => {
                if (this.configReloading) {
                    this.configReloading = false;
                    console.warn("UI Guard: Config reload lock released via timeout failsafe.");
                }
            }, 10 * 1000);
        }
    };
}