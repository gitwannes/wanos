// --- file: frontend/app.js ---

// ECharts instances MUST live outside the Alpine component data. Alpine deep-wraps
// everything reachable from `this` in reactive Proxies; a proxied ECharts instance
// corrupts ECharts' internal identity checks and resize()/setOption() then throw
// ("Cannot read properties of undefined"), silently aborting the rest of the render.
const wanosHistoryCharts = { day: null, month: null, year: null };
const wanosActuatorCharts = { day: null, month: null, year: null };

function wanosApp() {
    return {
        connected: false,
        isAdmin: false,
        showHiddenNodes: false,

        state: {
            system: {
                version_major: "v0.0", // ⚡ Reactive placeholder container mapping
                version_full: "v0.0-build_unknown", // ⚡ Reactive placeholder container mapping
                wanos_mqtt_connected: false,
                ip_address: "0.0.0.0",
                os_boot_unix: null,
                app_boot_unix: null,
                os_uptime_formatted: { duration: "00:00:00", boot: "--" },
                app_uptime_formatted: { duration: "00:00:00", boot: "--" },
                automations_enabled: true, // Master switch for the logic engine
                owm_integration_enabled: false, // ⚡ Switch to block/allow OWM polling
                rfxcom_connected: false, // ⚡ Live USB mounting health status
                rfxcom_integration_enabled: false, // ⚡ Switch to block/allow native RFXCOM transmission/reception
                zwave_hardware_connected: false, // ⚡ Tracks physical USB stick presence
                zwave_web_alive: false, // ⚡ Tracks Z-Wave JS UI Web Panel health
                zwave_data_alive: false, // ⚡ Tracks Z-Wave JS UI MQTT data stream
                zwave_integration_enabled: false, // ⚡ Switch to block/allow Z-Wave processing
                epson_connected: false, // ⚡ Tracks physical TCP availability of the Epson Projector
                epson_integration_enabled: false, // ⚡ Master UI switch to block/allow Epson commands
                sonos_connected: false, // ⚡ Tracks physical availability of Sonos network
                sonos_integration_enabled: false, // ⚡ Master UI switch to block/allow Sonos commands
                onkyo_connected: false, // ⚡ Tracks physical TCP availability of Onkyo Receivers
                onkyo_integration_enabled: false, // ⚡ Master UI switch to block/allow Onkyo Receivers
                native_rfx_devices: [], // ⚡ Enables reactivity for the dynamic panel
                available_scenes: [], // ⚡ Holds dynamically extracted stateless automations
                hidden_explorer_idxs: [], // ⚡ Devices to hide from the Device Explorer
                hue_presets: {} // ⚡ Dynamically injected from config_hue.yaml
            },
            sensors: {
                sunrise_unix: null,
                sunset_unix: null,
                sauna_calc_temp: null,
                sauna_calc_hum: null,
                sensor_history: {} // ⚡ Universal dynamic history tracking
            },
            sauna: {
                active: false,
                target_temp: null,
                min_temp: null,
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
                douche_active: false,
                douche_start_time: null,
                douche_duration_secs: 0,
                douche_water_liters: 0,
                motion_triggers: {}, // ⚡ Ephemeral diagnostic tally
                p_leak_baseline_watts: 0.0,
                p_elements_real_watts: 0.0,
                r_th_insulation_coefficient: null,
                extracted_p_u: 3500.0,
                extracted_p_v: 3500.0,
                extracted_p_w: 2000.0,
                running_energy_real_wh: 0.0,
                running_energy_calc_wh: 0.0,
                total_energy_real_wh: 0.0,
                last_sauna_session: null,
                last_ir_session: null
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
            // PESSIMISTIC UI ARCHITECTURE: All devices are initialized empty.
            // The Frontend remains completely agnostic until the Python backend
            // explicitly pushes the RAM dictionary over the boot sync.
            // ⚡ DYNAMIC REGISTRY: Devices are dynamically injected by the backend.
            devices: {},
            device_metadata: {}, // ⚡ The dynamic registry powering deviceexplorer.html
            boot_seed: null
        },

        // Dedicated UI Toggle to lock/unlock manual manipulation of the physics simulator
        // ⚡ Reads the previous layout state from the browser's local storage immediately on boot
        labControlsEnabled: localStorage.getItem('wanos_lab_open') === 'true',

        // Tracks the execution state of the Sweeper
        sweepRunning: false,

        // Tracks Admin Debug "Entity Registry Check"
        entityRegistryChecking: false,
        entityRegistryReportText: "",
        entityRegistryReportOk: null,

        // Tracks Admin System Commands "Entity ID List" download
        entityIdListDownloading: false,

        // Tracks the execution state of the configuration hot-reload loop
        configReloading: false,

        // ⚡ Optimistic UI Locks (Anti-Rubberbanding)
        // Tracks timestamp of last user action per IDX: { idx: expiration_timestamp }
        uiLocks: {},

        // ⚡ Light Control Modal State
        activeLightId: null,
        activeLightName: "",
        activeLightBri: 100,
        activeLightHex: "#FFD180",
        colorPicker: null, // ⚡ Holds the iro.js UI instance
        // ⚡ Scene Confirmation Modal State
        activeSceneId: null,
        activeSceneName: "",

        // ⚡ Dynamic Device Explorer (deviceexplorer.html) UI States
        searchQuery: "",
        typeFilter: "ALL",   // "ALL", "SWITCH", "SCENE", "BLINDS", "SENSOR"
        statusFilter: "ALL", // "ALL", "ON", "OFF"
        sortMode: "NAME",    // "NAME", "STATUS"
        explorerMode: "control", // "control" | "history" — always land on control

        // ⚡ View Presets State
        presets: [null, null, null, null, null], // Array of 5 slots to hold view filter dictionaries
        activePresetSlot: null, // Tracks which slot is currently being saved
        toastMessage: "", // Ephemeral UI feedback message

        // ⚡ Sensor History / Explorer History mode
        historyTab: "sessions",
        historySensors: [],
        utilitySummaries: {},
        selectedHistoryIdx: null,
        selectedSensorIdx: null,
        selectedSensorKind: null, // 'utility' | 'climate' | 'actuator'
        selectedSensorName: "",
        historySummary: null,
        historyLoading: false,
        historyDayTitle: "Usage last 24 hours",
        historyMonthTitle: "Usage last month",
        historyYearTitle: "Usage last year",
        _historyRefreshTimer: null,
        historyChartHasData: { day: false, month: false, year: false },
        // Flat flags for Alpine x-if (more reliable than nested object keys)
        historyHasDay: false,
        historyHasMonth: false,
        historyHasYear: false,
        actuatorHasDay: false,
        actuatorHasMonth: false,
        actuatorHasYear: false,
        actuatorChartHasData: { day: false, month: false, year: false },
        actuatorList: [],
        actuatorFavorites: [],
        actuatorFavoritesOnly: false,
        actuatorSearchQuery: "",
        selectedActuatorIdx: null,
        selectedActuatorName: "",
        actuatorLoading: false,
        sessionHistoryType: "sauna",
        sessionHistoryRows: [],
        sessionHistoryTotal: 0,
        sessionHistoryOffset: 0,
        toastTimeout: null,

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

        // ⚡ Dynamically extracts all configured Sonos speakers for the diagnostic modal
        get sonosDevices() {
            let list = [];
            for (const [idxStr, meta] of Object.entries(this.state.device_metadata)) {
                if (!meta) continue;
                if (meta.origin === 'sonos') {
                    const idx = parseInt(idxStr, 10);
                    const rawValue = this.state.devices[idx];
                    // Map DEAD explicitly to OFFLINE for clearer diagnostics
                    const displayState = rawValue === 'DEAD' ? 'OFFLINE' : (rawValue === null ? 'SYNCING' : 'ONLINE');
                    list.push({
                        id: idx,
                        name: meta.name,
                        state: displayState
                    });
                }
            }
            return list.sort((a, b) => a.name.localeCompare(b.name));
        },

        get onkyoDevices() {
            let list = [];
            for (const [idxStr, meta] of Object.entries(this.state.device_metadata)) {
                if (!meta) continue;
                if (meta.origin === 'onkyo') {
                    const idx = parseInt(idxStr, 10);
                    const rawValue = this.state.devices[idx];
                    const displayState = rawValue === 'DEAD' ? 'OFFLINE' : (rawValue === null ? 'SYNCING' : 'ONLINE');
                    list.push({
                        id: idx,
                        name: meta.name,
                        state: displayState
                    });
                }
            }
            return list.sort((a, b) => a.name.localeCompare(b.name));
        },

        // ⚡ New dedicated property to easily expose the simulation state to any HTML view
        get ssrSimulationText() {
            return this.state.devices[71036] !== 'ON' ? 'SIMULATION MODE (5V RELAY OFF)' : '';
        },

        // ⚡ Dynamically compiles a list of disabled backend integrations
        get disabledIntegrationsText() {
            let disabled = [];
            if (!this.state.system.automations_enabled) disabled.push("Automation");
            if (!this.state.system.hue_integration_enabled) disabled.push("Hue");
            if (!this.state.system.epson_integration_enabled) disabled.push("Epson projector");
            if (!this.state.system.rfxcom_integration_enabled) disabled.push("RFX");
            if (!this.state.system.zwave_integration_enabled) disabled.push("Z-Wave");
            if (!this.state.system.owm_integration_enabled) disabled.push("OpenWeatherMap");
            if (!this.state.system.sonos_integration_enabled) disabled.push("Sonos");
            if (!this.state.system.onkyo_integration_enabled) disabled.push("Onkyo");
            if (!this.state.hardware.gpio_input_enabled) disabled.push("GPIO inputs");
            if (!this.state.hardware.gpio_output_enabled) disabled.push("GPIO outputs");
            if (!this.state.hardware.sht11_enabled) disabled.push("temp/hum sensors");

            // ⚡ Automatically warn the user through the universal banner if they are in SSR Simulation mode
            if (this.state.devices[71036] !== 'ON') disabled.push("SSR Power (SIMULATION MODE)");

            if (disabled.length === 0) return "";
            return "⚠️ OFFLINE: " + disabled.join(", ");
        },

        get unifiedDeviceList() {
            let list = [];

            // 1. Map actual devices from the backend metadata registry
            for (const [idxStr, meta] of Object.entries(this.state.device_metadata)) {
                if (!meta) continue;

                // ⚡ INTEGRATION ORIGIN GUARD
                // Automatically drop devices from the UI if their parent integration is disabled.
                if (meta.origin === 'rfxcom' && !this.state.system.rfxcom_integration_enabled) continue;
                if (meta.origin === 'hue' && !this.state.system.hue_integration_enabled) continue;
                if (meta.origin === 'zwave' && !this.state.system.zwave_integration_enabled) continue;
                if (meta.origin === 'sonos' && !this.state.system.sonos_integration_enabled) continue;
                if (meta.origin === 'onkyo' && !this.state.system.onkyo_integration_enabled) continue;

                // Native Physical & Cloud Integrations
                if (meta.origin === 'gpio_input' && !this.state.hardware.gpio_input_enabled) continue;
                if (meta.origin === 'sht11' && !this.state.hardware.sht11_enabled) continue;
                if (meta.origin === 'owm' && !this.state.system.owm_integration_enabled) continue;
                // Scene rows are rendered from available_scenes below; skip synthetic scene metadata here to avoid duplicates.
                if (meta.type === 'scene') continue;

                const idx = parseInt(idxStr, 10);
                // Internal virtual lock flags should never be visible in Explorer (user or admin).
                if (idx === 90001) continue;

                // Hidden = meta.hidden or idx in system.hidden_explorer_idxs
                // (from automations.auto.yaml deviceexplorer_exclude + Z-Wave hidden_nodes)
                const hiddenIdxs = this.state.system.hidden_explorer_idxs || [];
                const isHiddenDevice = meta.hidden === true
                    || hiddenIdxs.includes(idx) || hiddenIdxs.includes(Number(idxStr));

                if (this.showHiddenNodes) {
                    // Exclusive View: ONLY show hidden devices
                    if (!isHiddenDevice) continue;
                } else {
                    // Normal View: Drop hidden devices
                    if (isHiddenDevice) continue;
                }

                const rawValue = this.state.devices[idx];
                let isOn = false;

                const isDead = rawValue === 'DEAD';

                if (!isDead) {
                    if (meta.type === 'blinds') {
                        // Shutters: > 0% = ON
                        isOn = parseInt(rawValue, 10) > 0;
                    } else if (meta.type === 'switch' || meta.type === 'light' || meta.type === 'speaker' || meta.type === 'sensor' || meta.type === 'power' || meta.type === 'energy') {
                        // ⚡ ANALOG vs BINARY DISTINCTION
                        // Ensure power (W) and energy (kWh) natively map to analog UI elements rather than binary switches
                        if ((meta.type === 'sensor' || meta.type === 'power' || meta.type === 'energy') && rawValue !== 'ON' && rawValue !== 'OFF' && rawValue !== null) {
                            isOn = null; // Explicitly mark analog strings (e.g., "55 Lux", "150 W") as having no binary state
                        } else {
                            // ⚡ RICH PAYLOAD SUPPORT: Parse "ON" state whether it's a flat string or a dictionary object
                            isOn = (typeof rawValue === 'object' && rawValue !== null) ? rawValue.state === 'ON' : rawValue === 'ON';
                        }
                    }
                }

                // ⚡ STATE INVALIDATION GUARD: Check if the entire node or specifically its volume is still booting
                let isSyncing = (rawValue === null);

                // ⚡ Format Display Text
                let displayText = rawValue;
                if (isDead) {
                    displayText = "DEAD";
                } else if (isSyncing) {
                    displayText = "SYNC...";
                } else if (idxStr.startsWith('75')) {
                    // ⚡ MOTION SENSOR DIAGNOSTIC LEDGER (Admin Only)
                    // Ignore raw binary states. Pull the ephemeral trigger tally directly from the metrics ledger.
                    const tally = this.state.metrics.motion_triggers?.[idx] || 0;
                    displayText = `${tally}x`;
                } else if (typeof rawValue === 'object' && rawValue !== null) {
                    if (meta.type === 'speaker') {
                        // ⚡ EXPLICIT SYNC CHECK: If the volume key is explicitly null, the hardware is answering the power command but volume is still fetching
                        if (rawValue.volume === null) {
                            isSyncing = true;
                            displayText = "SYNC...";
                        }
                        // ⚡ Smart Badge Text: Display 'OFF' if the power state is down,
                        // otherwise show the raw hardware integer without the % symbol.
                        else if (!isOn) {
                            displayText = "OFF";
                        } else {
                            const vol = rawValue.volume !== undefined ? rawValue.volume : 0;
                            displayText = `${vol}`;
                        }
                    } else if (meta.type === 'sensor' || meta.type === 'temp' || meta.type === 'hum' || meta.type === 'temp_hum' || meta.type === 'power' || meta.type === 'energy') {
                        if (rawValue.temp !== undefined && rawValue.hum !== undefined) {
                            displayText = `${parseFloat(rawValue.temp).toFixed(1)} °C / ${rawValue.hum} %`;
                        } else if (rawValue.temp !== undefined) {
                            displayText = `${parseFloat(rawValue.temp).toFixed(1)} °C`;
                        } else if (rawValue.hum !== undefined) {
                            displayText = `${rawValue.hum} %`;
                        } else if (rawValue.state !== undefined) {
                            displayText = rawValue.state;
                        } else {
                            const keys = Object.keys(rawValue);
                            if (keys.length > 0 && typeof rawValue[keys[0]] !== 'object') {
                                let k = keys[0].toLowerCase();
                                let unit = "";
                                if (k.includes('temp') || k.includes('air')) unit = '°C';
                                else if (k.includes('hum')) unit = '%';
                                else if (k.includes('lux') || k.includes('illuminance')) unit = 'Lux';
                                else if (k.includes('pow') || k.includes('watt') || k.includes('meter')) unit = 'W';
                                else if (k.includes('volt')) unit = 'V';
                                else if (k.includes('amp') || k.includes('current')) unit = 'A';
                                else if (k.includes('water') || k.includes('liter') || k.includes('volume')) unit = 'l';
                                else if (k.includes('kwh') || k.includes('energy')) unit = 'kWh';

                                displayText = unit ? `${rawValue[keys[0]]} ${unit}` : `${rawValue[keys[0]]} ${keys[0]}`;
                            } else {
                                displayText = JSON.stringify(rawValue);
                            }
                        }
                    } else if (rawValue.state !== undefined) {
                        displayText = rawValue.state;
                    } else {
                        displayText = JSON.stringify(rawValue);
                    }
                } else if (typeof rawValue === 'number' || (!isNaN(parseFloat(rawValue)) && isFinite(rawValue))) {
                    // ⚡ NATIVE FLOAT/INT FORMATTING
                    // Assign units to raw numbers based on strict metadata type first, then fallback to semantic names
                    const n = meta.name.toLowerCase();

                    if (meta.type === 'energy' || n.includes('kwh') || n.includes('energy')) {
                        // ⚡ Smart Scaling: Physical GPIO pulses (Wh) require division. Z-Wave and similar integrations are natively pre-scaled.
                        if (meta.origin === 'gpio_input') {
                            displayText = `${(parseFloat(rawValue) / 1000).toFixed(3)} kWh`;
                        } else {
                            displayText = `${parseFloat(rawValue).toFixed(3)} kWh`;
                        }
                    }
                    else if (meta.type === 'power' || n.includes('power') || n.includes('watt')) displayText = `${rawValue} W`;
                    else if (meta.type === 'fluid' || n.includes('water') || n.includes('liter')) displayText = `${parseFloat(rawValue).toFixed(1)} l`;
                    else if (n.includes('temp')) displayText = `${rawValue} °C`;
                    else if (n.includes('hum')) displayText = `${rawValue} %`;
                    else if (n.includes('lux')) displayText = `${rawValue} Lux`;
                }

                let uiVolume = undefined;
                if (meta.type === 'speaker' && !isDead && typeof rawValue === 'object' && rawValue !== null && rawValue.volume !== undefined) {
                    // ⚡ Direct mapping to hardware integers. Logarithmic taper removed.
                    uiVolume = rawValue.volume;
                }

                // ⏱️ CLIENT-SIDE COUNTDOWN MODELER
                // Iterates over active timers to compute any matching absolute auto-off deadlines
                let autoOffCountdown = null;
                if (this.state.system.active_timers) {
                    const targetTimerId = `light_auto_off_${idx}`;
                    for (const itemStr of this.state.system.active_timers) {
                        if (!itemStr) continue;
                        let t = typeof itemStr === 'object' ? itemStr : null;
                        if (!t) {
                            try { t = JSON.parse(itemStr); } catch (e) {}
                        }
                        if (t && t.timer_id === targetTimerId) {
                            const diff = t.deadline - this.nowUnix;
                            if (diff > 0) {
                                const hrs = Math.floor(diff / 3600);
                                const mins = Math.floor((diff % 3600) / 60);
                                const secs = diff % 60;

                                // Dynamically drop format components based on remaining duration thresholds
                                if (hrs > 0) {
                                    autoOffCountdown = `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                                } else if (mins > 0) {
                                    autoOffCountdown = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                                } else {
                                    autoOffCountdown = `${secs.toString().padStart(2, '0')}`;
                                }
                            }
                            break;
                        }
                    }
                }

                list.push({
                    id: idx,
                    name: meta.name,
                    type: meta.type,
                    origin: meta.origin, // dynamically label Sonos vs Onkyo
                    max_volume: meta.max_volume !== undefined ? meta.max_volume : 100, // ⚡ Natively extract max_volume to avoid Alpine HTML evaluation race conditions
                    raw_value: rawValue === 0 ? "0" : rawValue,
                    display_text: displayText,
                    ui_volume: uiVolume, // direct hardware integer slider UI
                    is_on: isOn,
                    is_syncing: isSyncing, // ⚡ Exposed explicitly to lock UI elements during hardware handshakes
                    is_hue: meta.origin === 'hue',
                    is_dead: isDead,
                    auto_off_countdown: autoOffCountdown // ⚡ Injected for role-restricted layout timer badges
                });
            }

            // 2. Map Stateless Scenes
            // ⚡ Display scenes as long as the Automation Engine is alive to process them
            // ⚡ Admin Guard: Hide stateless software scenes from the diagnostic "Hidden Nodes" view
            if (!this.showHiddenNodes && this.state.system.available_scenes && this.state.system.automations_enabled) {
                for (const scene of this.state.system.available_scenes) {
                    list.push({
                        id: scene.event,
                        name: scene.name,
                        type: 'scene',
                        raw_value: null,
                        is_on: null, // Stateless element
                        require_confirmation: scene.require_confirmation === true // Mapped from backend config
                    });
                }
            }

            // 2b. Favorites (shared localStorage with Sensor History)
            if (this.actuatorFavoritesOnly) {
                list = list.filter(item => {
                    if (this.actuatorFavorites.includes(Number(item.id))) return true;
                    // Water pair: keep cold primary if either fluid is favorited
                    const cap = this.historyCapabilityByIdx[Number(item.id)];
                    if (cap && cap.kind === "water" && Array.isArray(cap.pairIdxs)) {
                        return cap.pairIdxs.some(i => this.actuatorFavorites.includes(Number(i)));
                    }
                    return false;
                });
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
                    if (this.typeFilter === "SPEAKER") return item.type === 'speaker';
                    if (this.typeFilter === "SCENE") return item.type === 'scene';
                    if (this.typeFilter === "BLINDS") return item.type === 'blinds';
                    if (this.typeFilter === "SENSOR") return item.type === 'temp' || item.type === 'hum' || item.type === 'temp_hum' || item.type === 'power' || item.type === 'energy' || item.type === 'sensor';
                    return true;
                });
            }

            // 5. Apply Status Filter (Hide sensors, scenes & shutters if ON/OFF is requested)
            if (this.statusFilter !== "ALL") {
                list = list.filter(item => {
                    // Instantly drop legacy analog sensors, scenes, and shutters
                    // (shutters only appear when status filter is ALL)
                    if (item.type === 'temp' || item.type === 'hum' || item.type === 'temp_hum' || item.type === 'power' || item.type === 'energy' || item.type === 'scene' || item.type === 'blinds') {
                        return false;
                    }

                    // ⚡ Analog String Filter: Safely drop environmental strings (like Lux/Temp) when filtering by binary states
                    if (item.is_on === null) {
                        return false;
                    }

                    if (this.statusFilter === "ON") return item.is_on === true;
                    if (this.statusFilter === "OFF") return item.is_on === false;
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
                } else if (this.sortMode === "TYPE") {
                    // Sort primarily by Type (Groups items logically)
                    if (a.type !== b.type) {
                        return a.type.localeCompare(b.type);
                    }
                }
                // Universal Fallback: Alphabetical by Name (Used purely for "NAME", or as secondary for "STATUS"/"TYPE")
                return a.name.localeCompare(b.name);
            });

            return list;
        },

        /** idx → { category, name } for devices that have a history backend series. */
        get historyCapabilityByIdx() {
            const map = {};
            for (const s of (this.historySensors || [])) {
                let category = "utility";
                if (s.kind === "climate") category = "climate";
                else if (s.kind === "host") category = "host";
                const entry = {
                    category,
                    name: s.label || `IDX ${s.idx}`,
                    kind: s.kind,
                    primaryIdx: Number(s.idx),
                };
                if (s.kind === "water") {
                    entry.name = s.label || "Water";
                    entry.coldIdx = Number(s.cold_idx ?? s.idx);
                    entry.hotIdx = Number(s.hot_idx ?? 11003);
                    entry.pairIdxs = (s.pair_idxs || [entry.coldIdx, entry.hotIdx]).map(Number);
                    entry.primaryIdx = entry.coldIdx;
                    for (const pid of entry.pairIdxs) {
                        map[pid] = { ...entry };
                    }
                    continue;
                }
                map[Number(s.idx)] = entry;
            }
            for (const a of (this.actuatorList || [])) {
                map[Number(a.idx)] = {
                    category: "actuator",
                    name: a.name || `IDX ${a.idx}`,
                    kind: "actuator",
                    primaryIdx: Number(a.idx),
                };
            }
            return map;
        },

        deviceHasHistory(idx) {
            return this.historyCapabilityByIdx[Number(idx)] != null;
        },

        /** Control list as-is; History mode applies hybrid C + water pair merge. */
        get explorerDisplayList() {
            const base = this.unifiedDeviceList;
            if (this.explorerMode !== "history") return base;
            const withHist = base.filter(item => this.deviceHasHistory(item.id));
            // Drop secondary fluid row (hot) when cold/hot are merged into one Water detail.
            const hotSecondary = new Set();
            for (const item of withHist) {
                const cap = this.historyCapabilityByIdx[Number(item.id)];
                if (cap && cap.kind === "water" && cap.hotIdx != null && Number(item.id) === Number(cap.hotIdx)
                    && Number(cap.hotIdx) !== Number(cap.primaryIdx)) {
                    hotSecondary.add(Number(item.id));
                }
            }
            return withHist
                .filter(item => !hotSecondary.has(Number(item.id)))
                .map(item => {
                    const cap = this.historyCapabilityByIdx[Number(item.id)];
                    if (!cap || cap.kind !== "water") return item;
                    return {
                        ...item,
                        name: cap.name || "Water",
                        display_text: this._waterPairLiveStatus(cap),
                    };
                });
        },

        _waterPairLiveStatus(cap) {
            const fmt = (idx) => {
                const raw = this.state.devices?.[idx];
                if (raw == null) return "—";
                const L = Number(raw);
                return Number.isFinite(L) ? L.toFixed(1) + " l" : "—";
            };
            if (!cap) return "—";
            return "C " + fmt(cap.coldIdx) + " · H " + fmt(cap.hotIdx);
        },

        _waterLitersText(idx) {
            const raw = this.state.devices?.[idx];
            if (raw == null) return "—";
            const L = Number(raw);
            return Number.isFinite(L) ? L.toFixed(1) + " l" : "—";
        },

        isWaterHistoryItem(item) {
            if (!item) return false;
            const cap = this.historyCapabilityByIdx[Number(item.id)];
            return !!(cap && cap.kind === "water");
        },

        historyRowSubtitle(item) {
            if (!item) return "";
            if (this.isWaterHistoryItem(item)) return "fluid";
            return item.id + " · " + (item.type || "");
        },

        isColdWaterItem(item) {
            if (!item) return false;
            const id = Number(item.id);
            const cap = this.historyCapabilityByIdx[id];
            if (cap && cap.kind === "water" && cap.coldIdx != null) return id === Number(cap.coldIdx);
            const n = String(item.name || "").toLowerCase();
            return item.type === "fluid" && (n.includes("koud") || n.includes("cold"));
        },

        isHotWaterItem(item) {
            if (!item) return false;
            const id = Number(item.id);
            const cap = this.historyCapabilityByIdx[id];
            if (cap && cap.kind === "water" && cap.hotIdx != null) return id === Number(cap.hotIdx);
            const n = String(item.name || "").toLowerCase();
            return item.type === "fluid" && (n.includes("warm") || n.includes("hot"));
        },

        /** Admin-only hint: how many Control-visible rows were dropped by hybrid C. */
        get historyWithoutSeriesCount() {
            return (this.unifiedDeviceList || []).filter(item => !this.deviceHasHistory(item.id)).length;
        },

        // ⏱️ Mathematical duration translator for history tallies
        getDurationString(unixTimestamp) {
            if (!unixTimestamp) return "--";
            const diff = Math.floor(Date.now() / 1000) - unixTimestamp;
            if (diff < 60) return `${diff}s ago`;
            const mins = Math.floor(diff / 60);
            if (mins < 60) return `${mins}m ago`;
            const hrs = Math.floor(mins / 60);
            if (hrs < 24) return `${hrs}h ${mins % 60}m ago`;
            const days = Math.floor(hrs / 24);
            return `${days}d ${hrs % 24}h ago`;
        },

        getAuthHeaders() {
            // Retrieve persistent token from localStorage
            const token = localStorage.getItem("wanos_jwt");
            return {
                "Content-Type": "application/json",
                "Authorization": token ? `Bearer ${token}` : ""
            };
        },

        // ⚡ UNIVERSAL DEVICE ONLINE DECIPHER
        // Dynamically checks if a device's parent integration is currently running.
        isDeviceOnline(idx) {
            const meta = this.state.device_metadata[idx];
            if (!meta) return false;
            if (meta.origin === 'zwave') return this.state.system.zwave_integration_enabled;
            if (meta.origin === 'hue') return this.state.system.hue_integration_enabled;
            if (meta.origin === 'epson') return this.state.system.epson_integration_enabled;
            if (meta.origin === 'sonos') return this.state.system.sonos_integration_enabled;
            if (meta.origin === 'onkyo') return this.state.system.onkyo_integration_enabled;
            if (meta.origin === 'gpio_input') return this.state.hardware.gpio_input_enabled;
            if (meta.origin === 'sht11') return this.state.hardware.sht11_enabled;
            return true; // Fallback for local macros/scenes
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

            // ⚡ RESTORE VIEW PRESETS
            // Loads saved filter/sort configurations from the browser's persistent local storage
            try {
                const savedPresets = localStorage.getItem('wanos_view_presets');
                if (savedPresets) {
                    const parsed = JSON.parse(savedPresets);
                    if (Array.isArray(parsed)) {
                        // Safe migration: Pads existing 4-slot arrays to 5 slots, or truncates if somehow longer
                        this.presets = [...parsed, null, null, null, null, null].slice(0, 5);
                    }
                }
            } catch (err) {
                console.warn("⚠️ Failed to parse view presets from localStorage. Reverting to default array.");
            }

            // Shared favorites (Device Explorer + Sensor History)
            try {
                const fav = JSON.parse(localStorage.getItem("wanos_history_favorites") || "[]");
                this.actuatorFavorites = Array.isArray(fav) ? fav.map(Number) : [];
            } catch (e) {
                this.actuatorFavorites = [];
            }

            // ⚡ VISUAL STATE PERSISTENCE
            // Automatically saves the lab panel toggle state to the browser whenever you click it
            this.$watch('labControlsEnabled', value => {
                localStorage.setItem('wanos_lab_open', value);
            });

            // Admin Gatekeeper & Strict Page Bouncer
            const token = localStorage.getItem("wanos_jwt") || "";
            if (token) {
                try {
                    const payloadStr = atob(token.split('.')[1]);
                    const payload = JSON.parse(payloadStr);

                    if (payload.role === "admin") {
                        this.isAdmin = true;
                    } else if (payload.role === "user" && window.location.pathname.includes("admin.html")) {
                        // ⚡ THE BOUNCER: user role cannot open admin.html (History/sessions are allowed)
                        console.warn("Unauthorized access attempt. Redirecting...");
                        window.location.href = "/deviceexplorer.html";
                        return;
                    }
                } catch (err) {
                    localStorage.removeItem("wanos_jwt");
                }
            } else if (!window.location.pathname.includes("login.html")) {
                // Failsafe: Evict completely unauthenticated users who bypass the root routing
                window.location.href = "/login.html";
                return;
            }

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

            // ⚡ RESTORE FILTERS FROM SESSION
            // Seamlessly maintains active filter contexts when moving between the Explorer and Insights pages
            const savedFilters = sessionStorage.getItem('wanos_active_filters');
            if (savedFilters) {
                try {
                    const parsed = JSON.parse(savedFilters);
                    this.searchQuery = parsed.searchQuery !== undefined ? parsed.searchQuery : "";
                    this.typeFilter = parsed.typeFilter || "ALL";
                    this.statusFilter = parsed.statusFilter || "ALL";
                    this.sortMode = parsed.sortMode || "NAME";
                } catch (e) {}
            }

            // Bind watchers to actively save filters as the user navigates
            this.$watch('searchQuery', () => this.saveFilters());
            this.$watch('typeFilter', () => this.saveFilters());
            this.$watch('statusFilter', () => this.saveFilters());
            this.$watch('sortMode', () => this.saveFilters());

            this.connectSSE();
            setInterval(this.ticker.bind(this), 1000);
        },

        // Helper to push current layout filters to sessionStorage
        saveFilters() {
            sessionStorage.setItem('wanos_active_filters', JSON.stringify({
                searchQuery: this.searchQuery,
                typeFilter: this.typeFilter,
                statusFilter: this.statusFilter,
                sortMode: this.sortMode
            }));
        },

        async fetchFullSnapshot() {
            try {
                // Attach the authorization headers to the request
                const res = await fetch("/api/state", { headers: this.getAuthHeaders() });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = '/login.html';
                    return;
                }
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

            // ⚡ RESTORE LAB UI STATE
            // If the user refreshes the page while the backend physics engine is still running,
            // automatically snap the Lab Controls panel open so it isn't hidden in the dark.
            if (this.state.hardware && this.state.hardware.simulations_enabled) {
                this.labControlsEnabled = true;
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
                // ⚡ OPTIMISTIC UI LOCK GUARD (Anti-Rubberbanding)
                // Filter out incoming telemetry for sliders we recently touched to prevent snapping
                const filteredPayload = {};
                const now = Date.now();

                for (const [idx, val] of Object.entries(payload)) {
                    if (this.uiLocks[idx] && now < this.uiLocks[idx]) {
                        // ⚡ Calculate remaining lock time for the console log
                        const remaining = Math.round((this.uiLocks[idx] - now) / 1000);
                        console.info(`[UI Guard] Event ignored for IDX ${idx}: locked for ${remaining} more seconds to prevent rubberbanding.`);
                        continue;
                    }
                    filteredPayload[idx] = val;
                }

                // Merge device keys individually natively!
                this.state.devices = Object.assign({}, this.state.devices, filteredPayload);
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
                if (this.eventSource) {
                    this.eventSource.close();
                }

                // Native EventSource doesn't support custom headers, so we pass the token in the URL
                const token = localStorage.getItem("wanos_jwt") || "";
                this.eventSource = new EventSource(`/api/state/sse?jwt=${token}`);

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

        syncLabControls() {
            const devs = this.state.devices;
            const seed = this.state.boot_seed;

            if (!seed) return;

            // ⚡ DYNAMIC LAB SEEDING:
            // Safely parses the boot_seed dictionary by integer IDX.
            // If real hardware is online, `devs[idx].temp` exists and overrides the seed.
            // If hardware is offline, `devs[idx]` is null, falling back to the seed.
            this.labSaunaHighTemp = (devs[20001] && devs[20001].temp) ?? (seed['20001'] ? seed['20001'].temp : 21.0);
            this.labSaunaHighHum  = (devs[20001] && devs[20001].hum)  ?? (seed['20001'] ? seed['20001'].hum : 45);
            this.labSaunaLowTemp  = (devs[20002] && devs[20002].temp) ?? (seed['20002'] ? seed['20002'].temp : 20.0);
            this.labSaunaLowHum   = (devs[20002] && devs[20002].hum)  ?? (seed['20002'] ? seed['20002'].hum : 48);
            this.labBathroom1Temp = (devs[20004] && devs[20004].temp) ?? (seed['20004'] ? seed['20004'].temp : 20.0);
            this.labBathroom1Hum  = (devs[20004] && devs[20004].hum)  ?? (seed['20004'] ? seed['20004'].hum : 45);
            this.labCinemaTemp    = (devs[20003] && devs[20003].temp) ?? (seed['20003'] ? seed['20003'].temp : 20.0);
            this.labCinemaHum     = (devs[20003] && devs[20003].hum)  ?? (seed['20003'] ? seed['20003'].hum : 45);
            this.labOutsideTemp   = (devs[30001] && devs[30001].temp) ?? (seed['30001'] ? seed['30001'].temp : 15.0);
            this.labOutsideHum    = (devs[30001] && devs[30001].hum)  ?? (seed['30001'] ? seed['30001'].hum : 60);
        },

        async publishEvent(eventType, payload = {}) {
            // Automatically inject the MANUAL origin for all UI-driven interactions
            if (typeof payload === 'object' && payload !== null && !payload.origin) {
                payload.origin = "MANUAL";
            }

            try {
                const res = await fetch("/api/event", {
                    method: "POST",
                    headers: this.getAuthHeaders(), // Inject headers here
                    body: JSON.stringify({ type: eventType, payload: payload })
                });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = '/login.html';
                    return;
                }
            } catch (error) {
                console.error(`💥 Event transmission collapsed [${eventType}]:`, error);
            }
        },

        async initDeviceExplorerPage() {
            if (!window.location.pathname.includes("deviceexplorer.html")) return;
            await this.$nextTick();
            window.addEventListener("resize", () => {
                Object.values(wanosHistoryCharts || {}).forEach(c => c && c.resize());
                Object.values(wanosActuatorCharts || {}).forEach(c => c && c.resize());
            });
            // Preload capability maps so History mode can filter immediately
            try {
                await Promise.all([this.loadHistorySensors(), this.loadActuatorOverview()]);
            } catch (e) {
                console.warn("History capability preload failed", e);
            }
        },

        async initSensorHistoryPage() {
            if (!window.location.pathname.includes("sensorhistory.html")) return;
            await this.$nextTick();
            this.historyTab = "sessions";
            await this.loadSessionHistory();

            if (this._historyRefreshTimer) {
                clearInterval(this._historyRefreshTimer);
            }
            this._historyRefreshTimer = setInterval(() => {
                if (document.visibilityState !== "visible") return;
                this.loadSessionHistory();
            }, 60_000);
        },

        async setExplorerMode(mode) {
            if (mode !== "control" && mode !== "history") return;
            if (this.explorerMode === mode) return;
            this.explorerMode = mode;

            if (mode === "history") {
                await this.ensureExplorerHistoryData();
                const id = this.selectedSensorIdx;
                if (id != null) {
                    const still = (this.explorerDisplayList || []).some(i => Number(i.id) === Number(id));
                    if (still) {
                        await this.$nextTick();
                        await this.reloadSelectedSensorDetail();
                    } else {
                        this.closeHistoryDetail();
                    }
                }
                this._startExplorerHistoryRefresh();
            } else {
                this._stopExplorerHistoryRefresh();
                // Keep selection ids for when user returns to History; hide charts in Control UI.
                this._disposeHistoryCharts();
                this._disposeActuatorCharts();
            }
        },

        async ensureExplorerHistoryData() {
            await Promise.all([this.loadHistorySensors(), this.loadActuatorOverview()]);
        },

        _startExplorerHistoryRefresh() {
            this._stopExplorerHistoryRefresh();
            this._historyRefreshTimer = setInterval(() => {
                if (document.visibilityState !== "visible") return;
                if (this.explorerMode !== "history") return;
                this.refreshExplorerHistory();
            }, 60_000);
        },

        _stopExplorerHistoryRefresh() {
            if (this._historyRefreshTimer) {
                clearInterval(this._historyRefreshTimer);
                this._historyRefreshTimer = null;
            }
        },

        async refreshExplorerHistory() {
            await this.ensureExplorerHistoryData();
            if (this.selectedSensorIdx != null && this.selectedSensorKind) {
                const still = (this.explorerDisplayList || []).some(
                    i => Number(i.id) === Number(this.selectedSensorIdx)
                );
                if (still) await this.reloadSelectedSensorDetail();
                else this.closeHistoryDetail();
            }
        },

        async selectExplorerHistoryItem(item) {
            if (!item || this.explorerMode !== "history") return;
            const cap = this.historyCapabilityByIdx[Number(item.id)];
            if (!cap) return;
            const idx = cap.primaryIdx != null ? cap.primaryIdx : item.id;
            await this.selectHistoryRow({
                idx,
                name: cap.name || item.name,
                category: cap.category,
                type: item.type,
            });
        },

        _isHistoryRowHidden(idx, explicitHidden) {
            const idxStr = String(idx);
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            const hiddenIdxs = this.state.system.hidden_explorer_idxs || [];
            return explicitHidden === true || meta.hidden === true
                || hiddenIdxs.includes(idx) || hiddenIdxs.includes(Number(idx));
        },

        /** Display label for History type chips (Device Explorer keeps raw `type`). */
        historyTypeLabel(type) {
            if (type === "light") return "Hue light";
            return type || "";
        },

        /**
         * Icon emoji matching Device Explorer name/type heuristics.
         * Use mobile-safe emoji (avoid U+23FB POWER which often renders blank on phones).
         */
        historyRowIcon(row) {
            if (!row) return "";
            const meta = (this.state.device_metadata && this.state.device_metadata[row.idx]) || {};
            const name = String(row.name || meta.name || "").toLowerCase();
            const type = String(row.type || meta.type || "").toLowerCase();
            const origin = String(meta.origin || row.origin || "").toLowerCase();

            if (type === "speaker") return origin === "onkyo" ? "📻" : "🔊";
            if (type === "scene") return "✨";
            if (type === "blinds") return "↕️";
            if (name.includes("water") || name.includes("liter") || type === "water") return "💧";
            if (type === "temp_hum" || type === "climate") return "🌡️💧";
            if (type === "temp" || (type === "sensor" && name.includes("temp")) || (type === "host" && name.includes("temp"))) return "🌡️";
            if (type === "hum") return "💧";
            if (type === "energy") return "🔌";
            if (type === "power") return "⚡";
            if (type === "sensor" && name.includes("volt")) return "⚡";
            if ((type === "sensor" || type === "generic") && name.includes("motion")) return "🏃";
            if (type === "light") return "💡";
            if ((name.includes("cinema") || name.includes("epson") || name.includes("projector"))
                && type !== "blinds" && type !== "speaker" && type !== "scene"
                && type !== "temp_hum" && type !== "temp"
                && !(type === "sensor" && (name.includes("temp") || name.includes("volt") || name.includes("motion")))) {
                return "🎬";
            }
            if ((name.includes("sauna") || name.includes("zoutlamp"))
                && type !== "blinds" && type !== "speaker" && type !== "scene"
                && type !== "temp_hum" && type !== "temp" && type !== "power" && type !== "energy"
                && !name.includes("cinema")
                && !(type === "sensor" && (name.includes("temp") || name.includes("volt") || name.includes("motion")))) {
                return "♨️";
            }
            if ((name.includes(" ir ") || name.startsWith("ir ") || name === "ir" || name.includes("infrarood"))
                && type !== "blinds" && type !== "speaker" && type !== "scene"
                && type !== "temp_hum" && type !== "temp" && type !== "power" && type !== "energy"
                && !name.includes("sauna")
                && !(type === "sensor" && (name.includes("temp") || name.includes("volt") || name.includes("motion")))) {
                return "🟥";
            }
            if (type === "host") return "🖥️";
            if (type === "switch") return "💡";
            return "";
        },

        /** Explorer-facing icon for a unified list item (same heuristics as History). */
        explorerItemIcon(item) {
            if (!item) return "";
            return this.historyRowIcon({
                idx: item.id,
                name: item.name,
                type: item.type,
                origin: item.origin,
            });
        },

        /**
         * History-mode trailing value: same semantics as Control, richer for audio/blinds.
         * Speakers → "ON, vol N" / "OFF"; blinds → Open / Closed / Open X%.
         */
        explorerHistoryValueText(item) {
            if (!item) return "—";
            if (item.is_dead) return "DEAD";
            if (item.raw_value === null || item.raw_value === undefined) return "SYNC...";

            if (item.type === "speaker") {
                const raw = item.raw_value;
                const on = item.is_on === true;
                let vol = null;
                if (typeof raw === "object" && raw !== null && raw.volume != null) {
                    vol = raw.volume;
                } else if (item.ui_volume != null) {
                    vol = item.ui_volume;
                }
                if (!on) return "OFF";
                if (vol == null) return "ON";
                return "ON, vol " + vol;
            }

            if (item.type === "blinds") {
                const level = parseInt(item.raw_value, 10);
                if (!Number.isFinite(level)) return String(item.display_text || "—");
                if (level <= 0) return "Open";
                if (level >= 100) return "Closed";
                const openPct = Math.max(0, Math.min(100, 100 - level));
                return "Open " + openPct + "%";
            }

            return item.display_text != null ? String(item.display_text) : "—";
        },

        /** Match Control-mode value colors in History mode. */
        explorerHistoryValueClass(item) {
            if (!item) return "text-base-content/80";
            if (item.is_dead) return "text-error";
            if (item.type === "temp" || item.type === "temp_hum") return "text-orange-400";
            if (item.type === "hum") return "text-info";
            if (item.type === "energy") return "text-success";
            if (item.type === "power") return "text-warning";
            if (item.type === "sensor") {
                const name = String(item.name || "").toLowerCase();
                if (name.includes("temp")) return "text-orange-400";
                if (name.includes("volt")) return "text-info";
                if (item.is_on === true) return "text-error animate-pulse";
                if (item.is_on === false) return "text-base-500";
                return "text-success";
            }
            if (item.type === "speaker") {
                return item.is_on ? "text-warning" : "text-base-content/70";
            }
            if (item.type === "blinds") return "text-info";
            if (item.type === "switch" || item.type === "light") {
                return item.is_on ? "text-warning" : "text-base-500";
            }
            return "text-base-content/80";
        },

        /** Hardware / configured level ceiling (Onkyo uses max_volume). */
        _actuatorLevelDeviceMax(idx) {
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            const maxVol = meta.max_volume != null ? Number(meta.max_volume) : null;
            if (Number.isFinite(maxVol) && maxVol > 0) return maxVol;
            if (meta.origin === "onkyo") return 60;
            return 100;
        },

        _isAudioActuator(idx) {
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            return meta.type === "speaker"
                || meta.origin === "sonos"
                || meta.origin === "onkyo";
        },

        /** Peak numeric value across one or more series payloads. */
        _seriesPeak(...seriesList) {
            let peak = null;
            for (const points of seriesList) {
                for (const p of points || []) {
                    if (p == null || p.v == null) continue;
                    const n = Number(p.v);
                    if (!Number.isFinite(n)) continue;
                    if (peak == null || n > peak) peak = n;
                }
            }
            return peak;
        },

        /**
         * Level Y-axis max for one chart window.
         * Audio: min(device max_volume, visible peak rounded up to nearest 10).
         * Other actuators: fixed device ceiling (0–100 / max_volume).
         */
        _actuatorLevelAxisMax(idx, ...seriesForWindow) {
            const deviceMax = this._actuatorLevelDeviceMax(idx);
            if (!this._isAudioActuator(idx)) return deviceMax;
            const peak = this._seriesPeak(...seriesForWindow);
            if (peak == null || peak <= 0) return Math.min(deviceMax, 10);
            const rounded = Math.ceil(peak / 10) * 10;
            return Math.min(deviceMax, Math.max(rounded, 10));
        },

        _utilityLiveStatus(s) {
            const raw = this.state.devices?.[s.idx];
            if (raw == null) return "—";
            if (s.kind === "energy") {
                const kwh = Number(raw) / 1000;
                return Number.isFinite(kwh) ? kwh.toFixed(2) + " kWh" : String(raw);
            }
            if (s.kind === "water") {
                const L = Number(raw);
                return Number.isFinite(L) ? L.toFixed(1) + " l" : String(raw);
            }
            if (s.kind === "power") {
                const w = Number(raw);
                return Number.isFinite(w) ? w.toFixed(1) + " W" : String(raw);
            }
            return String(raw);
        },

        get filteredHistoryRows() {
            const daysInMonth = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate();
            const rows = [];

            for (const s of (this.historySensors || [])) {
                if (s.kind === "climate") {
                    rows.push({
                        idx: s.idx,
                        name: s.label || `IDX ${s.idx}`,
                        type: "temp_hum",
                        category: "climate",
                        status: this._climateLiveStatus(s),
                        last_changed: null,
                        today_display: "—",
                        avg_display: "—",
                        hidden: s.hidden === true,
                        has_humidity: s.has_humidity !== false,
                    });
                    continue;
                }
                if (s.kind === "host") {
                    rows.push({
                        idx: s.idx,
                        name: s.label || `IDX ${s.idx}`,
                        type: "host",
                        category: "host",
                        status: this._hostLiveStatus(s),
                        last_changed: null,
                        today_display: "—",
                        avg_display: "—",
                        hidden: s.hidden === true,
                    });
                    continue;
                }
                const sum = this.utilitySummaries[s.idx];
                const todayVal = sum ? this.formatHistoryValue(sum.today, sum.display_unit) : "—";
                const avgVal = sum
                    ? this.formatHistoryValue((sum.month || 0) / daysInMonth, sum.display_unit)
                    : "—";
                let status = this._utilityLiveStatus(s);
                if (s.kind === "water") {
                    status = this._waterPairLiveStatus({
                        coldIdx: Number(s.cold_idx ?? s.idx),
                        hotIdx: Number(s.hot_idx ?? 11003),
                    });
                }
                rows.push({
                    idx: s.idx,
                    name: s.label || `IDX ${s.idx}`,
                    type: s.kind || "utility",
                    category: "utility",
                    status,
                    last_changed: null,
                    today_display: todayVal,
                    avg_display: avgVal,
                    hidden: false,
                });
            }

            for (const a of (this.actuatorList || [])) {
                rows.push({
                    idx: a.idx,
                    name: a.name,
                    type: a.type || "switch",
                    category: "actuator",
                    status: a.status,
                    last_changed: a.last_changed,
                    today_display: String(a.today_count ?? 0),
                    avg_display: String(a.daily_avg ?? 0),
                    hidden: a.hidden === true,
                });
            }

            let list = rows.filter(r => {
                // Utility meters always listed in normal view (even if Explorer-excluded)
                if (r.category === "utility") {
                    return !this.showHiddenNodes;
                }
                const isHidden = this._isHistoryRowHidden(r.idx, r.hidden);
                return this.showHiddenNodes ? isHidden : !isHidden;
            });
            if (this.actuatorFavoritesOnly) {
                list = list.filter(r => this.actuatorFavorites.includes(Number(r.idx)));
            }

            // Shared type filter with Device Explorer
            if (this.typeFilter !== "ALL") {
                list = list.filter(r => {
                    const meta = (this.state.device_metadata && this.state.device_metadata[r.idx]) || {};
                    const isHue = meta.origin === "hue" || r.type === "light";
                    if (this.typeFilter === "SWITCH") return r.type === "switch" && !isHue;
                    if (this.typeFilter === "HUE") return isHue;
                    if (this.typeFilter === "SPEAKER") return r.type === "speaker";
                    if (this.typeFilter === "SCENE") return r.type === "scene";
                    if (this.typeFilter === "BLINDS") return r.type === "blinds";
                    if (this.typeFilter === "SENSOR") {
                        return ["temp", "hum", "temp_hum", "power", "energy", "sensor", "host", "climate", "water"]
                            .includes(r.type) || r.category === "utility" || r.category === "climate" || r.category === "host";
                    }
                    return true;
                });
            }

            // Shared status filter (binary actuators only; drop sensors/scenes/blinds like Explorer)
            if (this.statusFilter !== "ALL") {
                list = list.filter(r => {
                    if (r.category !== "actuator") return false;
                    if (["temp", "hum", "temp_hum", "power", "energy", "scene", "blinds", "host", "climate"].includes(r.type)) {
                        return false;
                    }
                    const st = String(r.status || "").toUpperCase();
                    const isOn = st === "ON" || st === "CLOSED" || st === "HIT";
                    const isOff = st === "OFF" || st === "OPEN";
                    if (this.statusFilter === "ON") return isOn;
                    if (this.statusFilter === "OFF") return isOff;
                    return false;
                });
            }

            const q = (this.actuatorSearchQuery || this.searchQuery || "").trim().toLowerCase();
            if (q) {
                list = list.filter(r => {
                    const typeLabel = this.historyTypeLabel(r.type) || "";
                    const hay = `${r.idx} ${r.name || ""} ${r.type || ""} ${typeLabel} ${r.status || ""} ${r.category}`.toLowerCase();
                    return hay.includes(q);
                });
            }
            list.sort((a, b) => {
                if (this.sortMode === "STATUS") {
                    const statusA = String(a.status || "");
                    const statusB = String(b.status || "");
                    if (statusA !== statusB) return statusA.localeCompare(statusB);
                } else if (this.sortMode === "TYPE") {
                    if (a.type !== b.type) return String(a.type).localeCompare(String(b.type));
                }
                return String(a.name).localeCompare(String(b.name)) || (a.idx - b.idx);
            });
            return list;
        },

        _hostLiveStatus(s) {
            const raw = this.state.devices?.[s.idx];
            if (raw == null) return "—";
            return String(raw);
        },

        _climateLiveStatus(s) {
            const raw = this.state.devices?.[s.idx];
            if (raw && typeof raw === "object") {
                const t = raw.temp != null ? Number(raw.temp).toFixed(1) + "°C" : null;
                const h = raw.hum != null ? Number(raw.hum).toFixed(0) + "%" : null;
                if (t && h) return t + " / " + h;
                if (t) return t;
                if (h) return h;
            }
            if (Number(s.idx) === 20101) {
                const t = this.state.sensors?.sauna_calc_temp;
                const h = this.state.sensors?.sauna_calc_hum;
                if (t != null && h != null) return Number(t).toFixed(1) + "°C / " + Number(h).toFixed(0) + "%";
                if (t != null) return Number(t).toFixed(1) + "°C";
            }
            return "—";
        },

        async refreshSensorHistoryList() {
            await Promise.all([this.loadHistorySensors(), this.loadActuatorOverview()]);
            const headers = this.getAuthHeaders();
            const sums = {};
            await Promise.all((this.historySensors || []).filter(s => s.kind !== "climate" && s.kind !== "host").map(async s => {
                try {
                    const res = await fetch(`/api/history/${s.idx}/summary`, { headers });
                    if (res.ok) sums[s.idx] = await res.json();
                } catch (e) { /* ignore */ }
            }));
            this.utilitySummaries = sums;
            if (this.selectedSensorIdx != null && this.selectedSensorKind) {
                await this.reloadSelectedSensorDetail();
            }
        },

        async selectHistoryRow(row) {
            const id = Number(row.idx);
            const kind = row.category;
            if (Number(this.selectedSensorIdx) === id && this.selectedSensorKind === kind) {
                this.closeHistoryDetail();
                return;
            }
            this._disposeHistoryCharts();
            this._disposeActuatorCharts();
            this.selectedSensorIdx = id;
            this.selectedSensorKind = kind;
            this.selectedSensorName = row.name || String(id);
            this.selectedHistoryIdx = (kind === "utility" || kind === "climate" || kind === "host") ? id : null;
            this.selectedActuatorIdx = kind === "actuator" ? id : null;
            this.selectedActuatorName = kind === "actuator" ? row.name : "";
            await this.$nextTick();
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            await this.reloadSelectedSensorDetail();
            const anchor = kind === "actuator"
                ? document.getElementById("chart-act-day")
                : document.getElementById("chart-day");
            anchor?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        },

        async reloadSelectedSensorDetail() {
            if ((this.selectedSensorKind === "utility" || this.selectedSensorKind === "climate"
                    || this.selectedSensorKind === "host")
                && this.selectedSensorIdx != null) {
                this.selectedHistoryIdx = this.selectedSensorIdx;
                await this.reloadHistoryCharts();
                Object.values(wanosHistoryCharts).forEach(c => c && c.resize());
            } else if (this.selectedSensorKind === "actuator" && this.selectedSensorIdx != null) {
                this.selectedActuatorIdx = this.selectedSensorIdx;
                await this.reloadActuatorCharts();
                Object.values(wanosActuatorCharts).forEach(c => c && c.resize());
            }
        },

        closeHistoryDetail() {
            this._disposeHistoryCharts();
            this._disposeActuatorCharts();
            this.selectedSensorIdx = null;
            this.selectedSensorKind = null;
            this.selectedSensorName = "";
            this.selectedHistoryIdx = null;
            this.selectedActuatorIdx = null;
            this.selectedActuatorName = "";
            this.historySummary = null;
            this.historyChartHasData.day = false;
            this.historyChartHasData.month = false;
            this.historyChartHasData.year = false;
            this.actuatorChartHasData.day = false;
            this.actuatorChartHasData.month = false;
            this.actuatorChartHasData.year = false;
            this._syncHistoryHasFlags();
            this._syncActuatorHasFlags();
        },

        _disposeHistoryCharts() {
            Object.keys(wanosHistoryCharts || {}).forEach(k => {
                try { wanosHistoryCharts[k]?.dispose(); } catch (e) { /* ignore */ }
                wanosHistoryCharts[k] = null;
            });
        },

        isActuatorFavorite(idx) {
            const id = Number(idx);
            const cap = this.historyCapabilityByIdx[id];
            if (cap && cap.kind === "water" && Array.isArray(cap.pairIdxs)) {
                return cap.pairIdxs.some(i => this.actuatorFavorites.includes(Number(i)));
            }
            return this.actuatorFavorites.includes(id);
        },

        toggleActuatorFavorite(idx) {
            const cap = this.historyCapabilityByIdx[Number(idx)];
            const ids = (cap && cap.kind === "water" && Array.isArray(cap.pairIdxs))
                ? cap.pairIdxs.map(Number)
                : [Number(idx)];
            const on = ids.some(i => this.actuatorFavorites.includes(i));
            if (on) {
                this.actuatorFavorites = this.actuatorFavorites.filter(x => !ids.includes(Number(x)));
            } else {
                this.actuatorFavorites = [...new Set([...this.actuatorFavorites, ...ids])];
            }
            localStorage.setItem("wanos_history_favorites", JSON.stringify(this.actuatorFavorites));
        },

        async loadActuatorOverview() {
            this.actuatorLoading = true;
            try {
                const res = await fetch("/api/history/actuators", { headers: this.getAuthHeaders() });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
                const data = await res.json();
                this.actuatorList = data.actuators || [];
            } catch (e) {
                console.error("Failed to load actuators", e);
            } finally {
                this.actuatorLoading = false;
            }
        },

        async selectActuator(idx) {
            const row = (this.filteredHistoryRows || []).find(
                r => r.category === "actuator" && Number(r.idx) === Number(idx)
            ) || { idx, category: "actuator", name: String(idx) };
            await this.selectHistoryRow(row);
        },

        closeActuatorDetail() {
            this.closeHistoryDetail();
        },

        _disposeActuatorCharts() {
            Object.keys(wanosActuatorCharts || {}).forEach(k => {
                try {
                    wanosActuatorCharts[k]?.dispose();
                } catch (e) { /* ignore */ }
                wanosActuatorCharts[k] = null;
            });
        },

        _ensureActuatorChart(key, elId) {
            if (typeof echarts === "undefined") return null;
            const el = document.getElementById(elId);
            if (!el) return null;
            if (wanosActuatorCharts[key]) {
                try {
                    wanosActuatorCharts[key].resize();
                } catch (e) { /* ignore */ }
                return wanosActuatorCharts[key];
            }
            wanosActuatorCharts[key] = echarts.init(el, "dark");
            return wanosActuatorCharts[key];
        },

        renderActuatorCharts(dayData, monthData, yearData) {
            const dayOk = this._historyPayloadHasData(dayData);
            const monthOk = this._historyPayloadHasData(monthData);
            const yearOk = this._historyPayloadHasData(yearData);

            this.actuatorChartHasData.day = false;
            this.actuatorChartHasData.month = false;
            this.actuatorChartHasData.year = false;
            this._syncActuatorHasFlags();
            this._disposeActuatorCharts();

            const idx = dayData?.idx ?? monthData?.idx ?? yearData?.idx ?? this.selectedActuatorIdx;
            const dayLevelMax = this._actuatorLevelAxisMax(idx, dayData?.series?.level);
            const monthLevelMax = this._actuatorLevelAxisMax(
                idx, monthData?.series?.level_min, monthData?.series?.level_max
            );
            const yearLevelMax = this._actuatorLevelAxisMax(
                idx, yearData?.series?.level_min, yearData?.series?.level_max
            );

            const draw = () => {
                const dayChart = dayOk ? this._ensureActuatorChart("day", "chart-act-day") : null;
                const monthChart = monthOk ? this._ensureActuatorChart("month", "chart-act-month") : null;
                const yearChart = yearOk ? this._ensureActuatorChart("year", "chart-act-year") : null;

                this.actuatorChartHasData.day = !!(dayOk && dayChart);
                this.actuatorChartHasData.month = !!(monthOk && monthChart);
                this.actuatorChartHasData.year = !!(yearOk && yearChart);
                this._syncActuatorHasFlags();

                if (dayChart && this.actuatorChartHasData.day) {
                    const opt = this._baseChartOption("Level (0–" + dayLevelMax + ")");
                    opt.yAxis.min = 0;
                    opt.yAxis.max = dayLevelMax;
                    opt.series = [{
                        name: "Level",
                        type: "line",
                        step: "end",
                        showSymbol: true,
                        symbolSize: 6,
                        data: this._pointsToSeries(dayData?.series?.level),
                        lineStyle: { color: "#2dd4bf", width: 2 },
                        connectNulls: false
                    }];
                    this._applyTimeWindow(opt, 24 * 60 * 60 * 1000);
                    dayChart.setOption(opt, true);
                    dayChart.resize();
                }

                if (monthChart && this.actuatorChartHasData.month) {
                    this._renderActuatorPeriodChart(monthChart, monthData, "month", monthLevelMax);
                }

                if (yearChart && this.actuatorChartHasData.year) {
                    this._renderActuatorPeriodChart(yearChart, yearData, "year", yearLevelMax);
                }
            };

            this.$nextTick(() => {
                this.actuatorChartHasData.day = dayOk;
                this.actuatorChartHasData.month = monthOk;
                this.actuatorChartHasData.year = yearOk;
                this._syncActuatorHasFlags();
                this.$nextTick(() => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(draw);
                    });
                });
            });
        },

        async reloadActuatorCharts() {
            if (!this.selectedActuatorIdx) return;
            this.actuatorLoading = true;
            try {
                const idx = this.selectedActuatorIdx;
                const headers = this.getAuthHeaders();
                const [dayRes, monthRes, yearRes] = await Promise.all([
                    fetch(`/api/history/actuators/${idx}?range=day`, { headers }),
                    fetch(`/api/history/actuators/${idx}?range=month`, { headers }),
                    fetch(`/api/history/actuators/${idx}?range=year`, { headers })
                ]);
                if ([dayRes, monthRes, yearRes].some(r => r.status === 401 || r.status === 403)) {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
                const dayData = await dayRes.json();
                const monthData = await monthRes.json();
                const yearData = await yearRes.json();
                this.selectedActuatorName = dayData.name || this.selectedActuatorName;
                await this.$nextTick();
                this.renderActuatorCharts(dayData, monthData, yearData);
            } catch (e) {
                console.error("Failed to reload actuator charts", e);
            } finally {
                this.actuatorLoading = false;
            }
        },

        async loadHistorySensors() {
            try {
                const res = await fetch("/api/history/sensors", { headers: this.getAuthHeaders() });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
                const data = await res.json();
                this.historySensors = data.sensors || [];
            } catch (e) {
                console.error("Failed to load history sensors", e);
            }
        },

        formatHistoryValue(val, unit) {
            if (val == null || Number.isNaN(Number(val))) return "—";
            const n = Number(val);
            if (unit === "kWh") return n.toFixed(2) + " kWh";
            if (unit === "L" || unit === "l") return n.toFixed(1) + " l";
            return n.toFixed(1) + (unit ? " " + unit : "");
        },

        formatSessionTs(ts) {
            if (!ts) return "—";
            try {
                return new Date(ts * 1000).toLocaleString("nl-BE", { timeZone: "Europe/Brussels" });
            } catch (e) {
                return String(ts);
            }
        },

        formatSessionRuntime(secs) {
            if (secs == null) return "—";
            const m = Math.floor(Number(secs) / 60);
            const s = Number(secs) % 60;
            return m + "m " + s + "s";
        },

        _ensureHistoryChart(key, elId) {
            if (typeof echarts === "undefined") return null;
            const el = document.getElementById(elId);
            if (!el) return null;
            if (wanosHistoryCharts[key]) {
                try { wanosHistoryCharts[key].resize(); } catch (e) { /* ignore */ }
                return wanosHistoryCharts[key];
            }
            wanosHistoryCharts[key] = echarts.init(el, "dark");
            return wanosHistoryCharts[key];
        },

        _normalizeTsMs(t) {
            const n = Number(t);
            if (!Number.isFinite(n) || n <= 0) return null;
            // Backend sends ms; tolerate accidental unix-seconds.
            return n < 1e12 ? n * 1000 : n;
        },

        _pointsToSeries(points) {
            return (points || []).map(p => {
                const t = this._normalizeTsMs(p && p.t);
                return [t, (p == null || p.v == null) ? null : p.v];
            }).filter(row => row[0] != null);
        },

        _seriesHasPoints(points) {
            return (points || []).some(p => p != null && p.v != null && !Number.isNaN(Number(p.v)));
        },

        _seriesDrawable(points) {
            return this._pointsToSeries(points).some(row => row[1] != null && !Number.isNaN(Number(row[1])));
        },

        _historyPayloadHasData(data) {
            const s = data && data.series;
            if (!s || typeof s !== "object") return false;
            return Object.values(s).some(arr => this._seriesHasPoints(arr));
        },

        _climateRangeHasData(data, rangeName) {
            const s = data && data.series;
            if (!s) return false;
            if (rangeName === "day") {
                return this._seriesDrawable(s.temp) || this._seriesDrawable(s.hum);
            }
            return this._seriesDrawable(s.temp_min) || this._seriesDrawable(s.temp_max)
                || this._seriesDrawable(s.hum_min) || this._seriesDrawable(s.hum_max);
        },

        _syncHistoryHasFlags() {
            this.historyHasDay = !!this.historyChartHasData.day;
            this.historyHasMonth = !!this.historyChartHasData.month;
            this.historyHasYear = !!this.historyChartHasData.year;
        },

        _syncActuatorHasFlags() {
            this.actuatorHasDay = !!this.actuatorChartHasData.day;
            this.actuatorHasMonth = !!this.actuatorChartHasData.month;
            this.actuatorHasYear = !!this.actuatorChartHasData.year;
        },

        /**
         * Force the titled window (last 24h / month / year). Sparse event series otherwise
         * collapse the time axis; reused chart instances also keep a tiny dataZoom from before.
         * Use percent zoom (0–100) against explicit axis min/max — more reliable than startValue
         * when series only cover a thin slice of the window.
         */
        _applyTimeWindow(opt, windowMs) {
            if (!opt || !opt.xAxis || !windowMs) return;
            const end = Date.now();
            const start = end - windowMs;
            opt.xAxis.min = start;
            opt.xAxis.max = end;
            opt.xAxis.scale = true;
            opt.dataZoom = [
                { type: "inside", start: 0, end: 100, filterMode: "none", minValueSpan: Math.min(windowMs, 60 * 60 * 1000) },
                { type: "slider", height: 18, bottom: 28, start: 0, end: 100, filterMode: "none", minValueSpan: Math.min(windowMs, 60 * 60 * 1000) },
            ];
        },

        _baseChartOption(yName) {
            return {
                backgroundColor: "transparent",
                tooltip: { trigger: "axis" },
                legend: { bottom: 0, textStyle: { color: "#9ca3af" } },
                grid: { left: 48, right: 24, top: 24, bottom: 56 },
                xAxis: {
                    type: "time",
                    axisLabel: { color: "#9ca3af", hideOverlap: true },
                    splitLine: { show: false }
                },
                yAxis: {
                    type: "value",
                    name: yName,
                    nameTextStyle: { color: "#9ca3af" },
                    axisLabel: { color: "#9ca3af" },
                    splitLine: { lineStyle: { color: "#374151" } }
                },
                dataZoom: [
                    { type: "inside", filterMode: "none" },
                    { type: "slider", height: 18, bottom: 28, filterMode: "none" },
                ]
            };
        },

        renderHistoryCharts(dayData, monthData, yearData) {
            const kind = dayData?.kind || monthData?.kind || "power";
            const isWater = kind === "water";
            const isClimate = kind === "climate";
            const isHost = kind === "host";
            const hostUnit = dayData?.unit || monthData?.unit || "";

            this.historyDayTitle = isClimate
                ? "Temperature / humidity last 24 hours"
                : (isHost ? `Value last 24 hours (${hostUnit})`
                    : (isWater ? "Cold / hot water last 24 hours" : "Usage last 24 hours"));
            this.historyMonthTitle = isClimate
                ? "Temperature / humidity last month"
                : (isHost ? `Min / max last month (${hostUnit})`
                    : (isWater ? "Cold / hot water last month" : "Usage last month"));
            this.historyYearTitle = isClimate
                ? "Temperature / humidity last year (weekly)"
                : (isHost ? `Min / max last year (${hostUnit})`
                    : (isWater ? "Cold / hot water last year" : "Usage last year"));

            // Phase 1: unmount all chart sections so empty titles cannot linger.
            this.historyChartHasData.day = false;
            this.historyChartHasData.month = false;
            this.historyChartHasData.year = false;
            this._syncHistoryHasFlags();
            this._disposeHistoryCharts();

            const dayOk = isClimate
                ? this._climateRangeHasData(dayData, "day")
                : this._historyPayloadHasData(dayData);
            const monthOk = isClimate
                ? this._climateRangeHasData(monthData, "month")
                : this._historyPayloadHasData(monthData);
            const yearOk = isClimate
                ? this._climateRangeHasData(yearData, "year")
                : this._historyPayloadHasData(yearData);

            const draw = () => {
                const dayChart = dayOk ? this._ensureHistoryChart("day", "chart-day") : null;
                const monthChart = monthOk ? this._ensureHistoryChart("month", "chart-month") : null;
                const yearChart = yearOk ? this._ensureHistoryChart("year", "chart-year") : null;

                // Only keep sections whose containers actually mounted + have drawable series.
                this.historyChartHasData.day = !!(dayOk && dayChart);
                this.historyChartHasData.month = !!(monthOk && monthChart);
                this.historyChartHasData.year = !!(yearOk && yearChart);
                this._syncHistoryHasFlags();

                if (isClimate) {
                    const showHum = dayData?.has_humidity !== false
                        || this._seriesDrawable(dayData?.series?.hum)
                        || this._seriesDrawable(monthData?.series?.hum_min)
                        || this._seriesDrawable(monthData?.series?.hum_max);
                    this._renderClimateCharts(
                        this.historyChartHasData.day ? dayChart : null,
                        this.historyChartHasData.month ? monthChart : null,
                        this.historyChartHasData.year ? yearChart : null,
                        dayData, monthData, yearData, showHum
                    );
                    // Drop any range that rendered with no drawable points
                    if (this.historyChartHasData.month && !this._climateRangeHasData(monthData, "month")) {
                        this.historyChartHasData.month = false;
                    }
                    if (this.historyChartHasData.year && !this._climateRangeHasData(yearData, "year")) {
                        this.historyChartHasData.year = false;
                    }
                    this._syncHistoryHasFlags();
                    return;
                }

                const yLabel = isWater ? "liters" : (isHost ? (hostUnit || "Value") : "Usage (Watt)");
                const seriesName = isHost ? "Value" : "Usage";

                if (dayChart && this.historyChartHasData.day) {
                    if (isWater) {
                        this._renderWaterChart(dayChart, dayData, "day");
                    } else {
                        const opt = this._baseChartOption(yLabel);
                        opt.series = [{
                            name: seriesName,
                            type: "line",
                            showSymbol: false,
                            data: this._pointsToSeries(dayData?.series?.usage),
                            lineStyle: { color: "#2dd4bf", width: 2 },
                            areaStyle: { color: "rgba(45,212,191,0.08)" },
                            connectNulls: false
                        }];
                        this._applyTimeWindow(opt, 24 * 60 * 60 * 1000);
                        dayChart.setOption(opt, true);
                        dayChart.resize();
                    }
                }

                if (monthChart && this.historyChartHasData.month) {
                    if (isWater) {
                        this._renderWaterChart(monthChart, monthData, "month");
                    } else {
                        const opt = this._baseChartOption(yLabel);
                        opt.series = [
                            {
                                name: seriesName + " min",
                                type: "line",
                                showSymbol: false,
                                data: this._pointsToSeries(monthData?.series?.usage_min),
                                lineStyle: { color: "#2dd4bf" },
                                connectNulls: false
                            },
                            {
                                name: seriesName + " max",
                                type: "line",
                                showSymbol: false,
                                data: this._pointsToSeries(monthData?.series?.usage_max),
                                lineStyle: { color: "#a3e635" },
                                connectNulls: false
                            }
                        ];
                        this._applyTimeWindow(opt, 31 * 24 * 60 * 60 * 1000);
                        monthChart.setOption(opt, true);
                        monthChart.resize();
                    }
                }

                if (yearChart && this.historyChartHasData.year) {
                    if (isWater) {
                        this._renderWaterChart(yearChart, yearData, "year");
                    } else {
                        const opt = this._baseChartOption(yLabel);
                        opt.series = [
                            {
                                name: seriesName + " min",
                                type: "line",
                                showSymbol: false,
                                data: this._pointsToSeries(yearData?.series?.usage_min),
                                lineStyle: { color: "#2dd4bf" },
                                connectNulls: false
                            },
                            {
                                name: seriesName + " max",
                                type: "line",
                                showSymbol: false,
                                data: this._pointsToSeries(yearData?.series?.usage_max),
                                lineStyle: { color: "#a3e635" },
                                connectNulls: false
                            }
                        ];
                        this._applyTimeWindow(opt, 366 * 24 * 60 * 60 * 1000);
                        yearChart.setOption(opt, true);
                        yearChart.resize();
                    }
                }
            };

            // Phase 2: mount only ranges that have data, then init charts.
            this.$nextTick(() => {
                this.historyChartHasData.day = dayOk;
                this.historyChartHasData.month = monthOk;
                this.historyChartHasData.year = yearOk;
                this._syncHistoryHasFlags();
                this.$nextTick(() => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(draw);
                    });
                });
            });
        },

        /** Format one history bucket timestamp for category-axis labels. */
        _historyBucketLabel(tsMs, range) {
            const t = this._normalizeTsMs(tsMs);
            if (t == null) return "";
            const d = new Date(t);
            const tz = "Europe/Brussels";
            if (range === "day") {
                return d.toLocaleTimeString("nl-BE", { hour: "2-digit", minute: "2-digit", timeZone: tz });
            }
            if (range === "month") {
                return d.toLocaleDateString("nl-BE", { day: "numeric", month: "short", timeZone: tz });
            }
            return d.toLocaleDateString("nl-BE", { month: "short", year: "numeric", timeZone: tz });
        },

        _buildActuatorPeriodPayload(data) {
            const map = new Map();
            const add = (points, field) => {
                for (const p of points || []) {
                    const t = this._normalizeTsMs(p && p.t);
                    if (t == null) continue;
                    if (!map.has(t)) map.set(t, { t, events: 0, lmin: null, lmax: null });
                    const row = map.get(t);
                    if (field === "events") row.events = Number(p.v) || 0;
                    else if (field === "lmin") row.lmin = p.v == null ? null : Number(p.v);
                    else if (field === "lmax") row.lmax = p.v == null ? null : Number(p.v);
                }
            };
            add(data?.series?.event_count, "events");
            add(data?.series?.level_min, "lmin");
            add(data?.series?.level_max, "lmax");
            return [...map.values()].sort((a, b) => a.t - b.t);
        },

        /**
         * Actuator month/year: category axis so event bars don't stretch across the window.
         */
        _renderActuatorPeriodChart(chart, data, range, levelMax) {
            if (!chart) return;
            const rows = this._buildActuatorPeriodPayload(data);
            if (!rows.length) return;
            const labels = rows.map(r => this._historyBucketLabel(r.t, range));
            const opt = {
                backgroundColor: "transparent",
                tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
                legend: {
                    top: 4,
                    left: "center",
                    itemGap: 10,
                    textStyle: { color: "#9ca3af", fontSize: 10 }
                },
                grid: { left: 48, right: 48, top: 36, bottom: labels.length > 8 ? 72 : 56 },
                xAxis: {
                    type: "category",
                    data: labels,
                    axisLabel: {
                        color: "#9ca3af",
                        hideOverlap: true,
                        rotate: labels.length > 6 ? 35 : 0,
                        fontSize: 10
                    },
                    axisTick: { alignWithLabel: true },
                    splitLine: { show: false }
                },
                yAxis: [
                    {
                        type: "value",
                        name: "Level",
                        min: 0,
                        max: levelMax,
                        nameTextStyle: { color: "#9ca3af" },
                        axisLabel: { color: "#9ca3af" },
                        splitLine: { lineStyle: { color: "#374151" } }
                    },
                    {
                        type: "value",
                        name: "Events",
                        nameTextStyle: { color: "#9ca3af" },
                        axisLabel: { color: "#9ca3af" },
                        splitLine: { show: false }
                    }
                ],
                series: [
                    {
                        name: "Events",
                        type: "bar",
                        yAxisIndex: 1,
                        barMaxWidth: 40,
                        data: rows.map(r => r.events),
                        itemStyle: { color: "#64748b" }
                    },
                    {
                        name: "Level min",
                        type: "line",
                        yAxisIndex: 0,
                        step: "end",
                        showSymbol: true,
                        symbolSize: 5,
                        data: rows.map(r => r.lmin),
                        lineStyle: { color: "#2dd4bf" },
                        connectNulls: false
                    },
                    {
                        name: "Level max",
                        type: "line",
                        yAxisIndex: 0,
                        step: "end",
                        showSymbol: true,
                        symbolSize: 5,
                        data: rows.map(r => r.lmax),
                        lineStyle: { color: "#a3e635" },
                        connectNulls: false
                    }
                ]
            };
            chart.setOption(opt, true);
            chart.resize();
        },

        _buildWaterChartPayload(data, range) {
            const cold = data?.series?.cold || [];
            const hot = data?.series?.hot || [];
            const labels = [];
            const coldVals = [];
            const hotVals = [];
            const n = Math.max(cold.length, hot.length);
            for (let i = 0; i < n; i++) {
                const cp = cold[i];
                const hp = hot[i];
                const ts = (cp && cp.t != null) ? cp.t : (hp && hp.t);
                if (ts == null) continue;
                labels.push(this._historyBucketLabel(ts, range));
                coldVals.push(cp != null && cp.v != null ? Number(cp.v) : 0);
                hotVals.push(hp != null && hp.v != null ? Number(hp.v) : 0);
            }
            return { labels, coldVals, hotVals };
        },

        /**
         * Water consumption: category axis (one slot per hour/day/month bucket).
         * Time axis + bar charts mis-render sparse buckets as solid slabs.
         */
        _renderWaterChart(chart, data, range) {
            if (!chart) return;
            const { labels, coldVals, hotVals } = this._buildWaterChartPayload(data, range);
            if (!labels.length) return;

            const opt = {
                backgroundColor: "transparent",
                tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
                legend: { bottom: 0, textStyle: { color: "#9ca3af" } },
                grid: { left: 48, right: 24, top: 24, bottom: labels.length > 10 ? 72 : 56 },
                xAxis: {
                    type: "category",
                    data: labels,
                    axisLabel: {
                        color: "#9ca3af",
                        hideOverlap: true,
                        rotate: labels.length > 8 ? 35 : 0,
                        fontSize: 10
                    },
                    axisTick: { alignWithLabel: true },
                    splitLine: { show: false }
                },
                yAxis: {
                    type: "value",
                    name: "liters",
                    min: 0,
                    nameTextStyle: { color: "#9ca3af" },
                    axisLabel: { color: "#9ca3af" },
                    splitLine: { lineStyle: { color: "#374151" } }
                },
                series: [
                    {
                        name: "Cold",
                        type: "bar",
                        stack: "water",
                        barMaxWidth: 40,
                        data: coldVals,
                        itemStyle: { color: "#38bdf8" }
                    },
                    {
                        name: "Hot",
                        type: "bar",
                        stack: "water",
                        barMaxWidth: 40,
                        data: hotVals,
                        itemStyle: { color: "#f87171" }
                    }
                ]
            };
            chart.setOption(opt, true);
            chart.resize();
        },

        _climateDualAxisOption(seriesCount) {
            const many = (seriesCount || 0) > 2;
            const opt = this._baseChartOption("°C");
            opt.legend = many
                ? { top: 4, left: "center", itemGap: 10, textStyle: { color: "#9ca3af", fontSize: 10 } }
                : { bottom: 4, left: "center", textStyle: { color: "#9ca3af", fontSize: 10 } };
            opt.grid = many
                ? { left: 48, right: 48, top: 40, bottom: 52 }
                : { left: 48, right: 48, top: 24, bottom: 64 };
            opt.yAxis = [
                {
                    type: "value",
                    name: "°C",
                    nameTextStyle: { color: "#eab308" },
                    axisLabel: { color: "#eab308" },
                    splitLine: { lineStyle: { color: "#374151" } }
                },
                {
                    type: "value",
                    name: "%",
                    nameTextStyle: { color: "#22c55e" },
                    axisLabel: { color: "#22c55e" },
                    splitLine: { show: false }
                }
            ];
            return opt;
        },

        _applyClimateTimeWindow(opt, windowMs) {
            if (!opt || !opt.xAxis || !windowMs) return;
            const end = Date.now();
            const start = end - windowMs;
            opt.xAxis.min = start;
            opt.xAxis.max = end;
            opt.xAxis.scale = true;
            const many = (opt.series || []).length > 2;
            const sliderBottom = many ? 6 : 22;
            opt.dataZoom = [
                { type: "inside", start: 0, end: 100, filterMode: "none", minValueSpan: Math.min(windowMs, 60 * 60 * 1000) },
                { type: "slider", height: 14, bottom: sliderBottom, start: 0, end: 100, filterMode: "none", minValueSpan: Math.min(windowMs, 60 * 60 * 1000) },
            ];
        },

        _renderClimateCharts(dayChart, monthChart, yearChart, dayData, monthData, yearData, showHum) {
            if (dayChart) {
                const series = [{
                    name: "Temperature",
                    type: "line",
                    step: "end",
                    showSymbol: false,
                    yAxisIndex: 0,
                    data: this._pointsToSeries(dayData?.series?.temp),
                    lineStyle: { color: "#eab308", width: 2 },
                    connectNulls: false
                }];
                if (showHum) {
                    series.push({
                        name: "Humidity",
                        type: "line",
                        step: "end",
                        showSymbol: false,
                        yAxisIndex: 1,
                        data: this._pointsToSeries(dayData?.series?.hum),
                        lineStyle: { color: "#22c55e", width: 2 },
                        connectNulls: false
                    });
                }
                const opt = this._climateDualAxisOption(series.length);
                opt.series = series;
                this._applyClimateTimeWindow(opt, 24 * 60 * 60 * 1000);
                dayChart.setOption(opt, true);
                dayChart.resize();
            }

            if (monthChart) {
                const series = [
                    {
                        name: "Temp min",
                        type: "line",
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._pointsToSeries(monthData?.series?.temp_min),
                        lineStyle: { color: "#eab308", width: 1.5, type: "dashed" },
                        connectNulls: false
                    },
                    {
                        name: "Temp max",
                        type: "line",
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._pointsToSeries(monthData?.series?.temp_max),
                        lineStyle: { color: "#eab308", width: 2 },
                        connectNulls: false
                    }
                ];
                if (showHum) {
                    series.push(
                        {
                            name: "Hum min",
                            type: "line",
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(monthData?.series?.hum_min),
                            lineStyle: { color: "#22c55e", width: 1.5, type: "dashed" },
                            connectNulls: false
                        },
                        {
                            name: "Hum max",
                            type: "line",
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(monthData?.series?.hum_max),
                            lineStyle: { color: "#22c55e", width: 2 },
                            connectNulls: false
                        }
                    );
                }
                const opt = this._climateDualAxisOption(series.length);
                opt.series = series;
                this._applyClimateTimeWindow(opt, 31 * 24 * 60 * 60 * 1000);
                monthChart.setOption(opt, true);
                monthChart.resize();
            }

            if (yearChart) {
                const series = [
                    {
                        name: "Temp min",
                        type: "line",
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._pointsToSeries(yearData?.series?.temp_min),
                        lineStyle: { color: "#eab308", width: 1.5, type: "dashed" },
                        connectNulls: false
                    },
                    {
                        name: "Temp max",
                        type: "line",
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._pointsToSeries(yearData?.series?.temp_max),
                        lineStyle: { color: "#eab308", width: 2 },
                        connectNulls: false
                    }
                ];
                if (showHum) {
                    series.push(
                        {
                            name: "Hum min",
                            type: "line",
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(yearData?.series?.hum_min),
                            lineStyle: { color: "#22c55e", width: 1.5, type: "dashed" },
                            connectNulls: false
                        },
                        {
                            name: "Hum max",
                            type: "line",
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(yearData?.series?.hum_max),
                            lineStyle: { color: "#22c55e", width: 2 },
                            connectNulls: false
                        }
                    );
                }
                const opt = this._climateDualAxisOption(series.length);
                opt.series = series;
                this._applyClimateTimeWindow(opt, 366 * 24 * 60 * 60 * 1000);
                yearChart.setOption(opt, true);
                yearChart.resize();
            }
        },

        async reloadHistoryCharts() {
            if (!this.selectedHistoryIdx) return;
            this.historyLoading = true;
            try {
                const idx = this.selectedHistoryIdx;
                const headers = this.getAuthHeaders();
                const isClimate = this.selectedSensorKind === "climate";
                const isHost = this.selectedSensorKind === "host";
                const fetches = [
                    fetch(`/api/history/${idx}?range=day`, { headers }),
                    fetch(`/api/history/${idx}?range=month`, { headers }),
                    fetch(`/api/history/${idx}?range=year`, { headers })
                ];
                if (!isClimate && !isHost) {
                    fetches.unshift(fetch(`/api/history/${idx}/summary`, { headers }));
                }
                const results = await Promise.all(fetches);
                if (results.some(r => r.status === 401 || r.status === 403)) {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
                let dayData, monthData, yearData;
                if (isClimate || isHost) {
                    this.historySummary = null;
                    dayData = await results[0].json();
                    monthData = await results[1].json();
                    yearData = await results[2].json();
                } else {
                    this.historySummary = await results[0].json();
                    dayData = await results[1].json();
                    monthData = await results[2].json();
                    yearData = await results[3].json();
                }
                await this.$nextTick();
                this.renderHistoryCharts(dayData, monthData, yearData);
            } catch (e) {
                console.error("Failed to reload history charts", e);
            } finally {
                this.historyLoading = false;
            }
        },

        async loadSessionHistory() {
            try {
                const res = await fetch(
                    `/api/history/sessions?type=${this.sessionHistoryType}&limit=50&offset=${this.sessionHistoryOffset}`,
                    { headers: this.getAuthHeaders() }
                );
                if (res.status === 401 || res.status === 403) {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
                const data = await res.json();
                this.sessionHistoryRows = data.sessions || [];
                this.sessionHistoryTotal = data.total || 0;
            } catch (e) {
                console.error("Failed to load session history", e);
            }
        },

        async logout() {
            await fetch("/api/auth/logout", { method: "POST", headers: this.getAuthHeaders() });
            // Erase persistent credentials from storage
            localStorage.removeItem("wanos_jwt");
            window.location.href = "/login.html";
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

        toggleSonos() {
            const nextState = !this.state.system.sonos_integration_enabled;
            this.publishEvent("SONOS_TOGGLED", { enabled: nextState });
        },

        toggleOnkyo() {
            const nextState = !this.state.system.onkyo_integration_enabled;
            this.publishEvent("ONKYO_TOGGLED", { enabled: nextState });
        },

        toggleSimulations() {
            const nextState = !this.state.hardware.simulations_enabled;
            this.publishEvent("SIMULATIONS_TOGGLED", { enabled: nextState });

            // ⚡ VIRTUAL SENSOR BOOT-STRAP
            // When spinning up the physics engine, instantly push the initial lab slider
            // states so the backend has a baseline temperature to satisfy the PID controller
            // and unlock the sauna UI automatically.
            if (nextState) {
                setTimeout(() => {
                    this.injectLabMetric("TEMP_UPDATED", 20001, this.labSaunaHighTemp || 21.0);
                    this.injectLabMetric("HUMIDITY_UPDATED", 20001, this.labSaunaHighHum || 45);
                    this.injectLabMetric("TEMP_UPDATED", 20002, this.labSaunaLowTemp || 20.0);
                    this.injectLabMetric("HUMIDITY_UPDATED", 20002, this.labSaunaLowHum || 48);
                }, 250); // Tiny delay to ensure the backend processed the SIMULATIONS_TOGGLED event first
            }
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

        toggleSpeakerPower(idx, isOn) {
            // 🛡️ GHOST CLICK GUARD:
            if (this.state.devices[idx] === null) return;

            const targetState = isOn ? "ON" : "OFF";
            let current = this.state.devices[idx] || { state: 'OFF' };
            if (typeof current !== 'object') current = { state: current };

            if (current.state === targetState) return;

            current.state = targetState;

            // ⚡ CONTEXTUAL CACHE INVALIDATION:
            // Only wipe the volume cache when turning ON (so we can fetch the boot volume).
            // When turning OFF, the volume is irrelevant, and keeping the cached value avoids the "SYNC..." text.
            if (targetState === "ON") {
                current.volume = null;
            }

            this.state.devices[idx] = current;

            // ⚡ LOCK REMOVAL: Do NOT apply uiLocks here. We want the blazing fast 0.2s network
            // reply to be accepted instantly by the frontend. The slider is already visually protected
            // by the HTML :disabled="item.is_syncing" attribute during boot!

            this.publishEvent("HUB_STATE_CHANGED", { idx: parseInt(idx, 10), state: targetState });
        },

        handleShutterNameClick(item) {
            // ⚡ MOBILE UX: Force the browser to drop focus so the color doesn't "stick" after tapping
            if (document.activeElement) {
                document.activeElement.blur();
            }

            if (item.type !== 'blinds' || item.is_dead || item.raw_value === null) return;
            // ⚡ Binary Toggle Logic: If > 0, assume user wants it OPEN (0). Else CLOSED (100).
            const targetState = item.raw_value > 0 ? 0 : 100;
            this.setShutterState(item.id, targetState);
        },

        handleSpeakerNameClick(item) {
            // ⚡ MOBILE UX: Force the browser to drop focus so the color doesn't "stick" after tapping
            if (document.activeElement) {
                document.activeElement.blur();
            }

            if (item.type !== 'speaker' || item.is_dead || item.raw_value === null) return;
            // Toggle the target playback state smoothly on smartphone row touches using the dedicated invalidator
            this.toggleSpeakerPower(item.id, !item.is_on);
        },

        // ⚡ Smart Protocol-Aware UI Lock TTL Calculator
        getUiLockTime(deviceType, isDragging = false) {
            if (deviceType === 'blinds') {
                // Mechanical mesh blinds take time to physically roll and report back
                const lockTime = 7; // seconds
                return (this.state.system.shutter_rubberbanding || lockTime) * 1000;
            }
            if (deviceType === 'speaker') {
                // Speakers run on instant local TCP/API.
                // Give a short lock while dragging to prevent fighting the finger,
                // but drop the lock to 0ms instantly upon release!
                return isDragging ? 2000 : 0;
            }
            // Default fallback
            return 1000;
        },

        setShutterState(idx, targetState) {
            // Set Optimistic UI Lock expiration to ignore incoming Z-Wave state updates
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('blinds', false);

            // ⚡ Instantly mutate local state so OPEN/CLOSED text clicks don't flicker
            this.state.devices[idx] = targetState;

            // Dispatch command to backend
            this.publishEvent("HUB_STATE_CHANGED", { idx: parseInt(idx, 10), state: targetState });
        },

        setSpeakerVolume(idx, uiVol) {
            // ⚡ CLEAR THE LOCK: The user released the slider.
            // We instantly lift the block so the 0.2s network reply from the receiver is accepted!
            this.uiLocks[idx] = 0;

            let current = this.state.devices[idx] || { state: 'ON' };
            if (typeof current !== 'object') current = { state: current };

            // ⚡ Use pure hardware value directly without logarithmic translation
            const rawVol = parseInt(uiVol, 10);
            current.volume = rawVol;
            this.state.devices[idx] = current;

            // ⚡ DYNAMIC ROUTING: Dispatch to the correct integration based on the origin
            const meta = this.state.device_metadata[idx];
            if (meta && meta.origin === 'onkyo') {
                // ⚡ Optimistic UI Lock: Instantly force the "SYNC..." state in Alpine to disable the slider
                // until the physical receiver answers back with the true volume value.
                this.state.devices[idx] = null;
                this.publishEvent("HUB_STATE_CHANGED", { idx: parseInt(idx, 10), volume: rawVol });
            } else {
                this.publishEvent("SONOS_COMMAND", { idx: parseInt(idx, 10), volume: rawVol });
            }
        },

        updateSpeakerOptimistic(idx, uiVol) {
            // ⚡ SHORT LOCK: Keep a 2-second lock while actively dragging so network
            // echoes don't rip the slider out from under the user's finger.
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('speaker', true);

            let current = this.state.devices[idx] || { state: 'ON' };
            if (typeof current !== 'object') current = { state: current };

            // ⚡ Optimistically update the real volume directly without logarithmic translation
            const rawVol = parseInt(uiVol, 10);
            current.volume = rawVol;
            this.state.devices[idx] = current;
        },

        updateShutterOptimistic(idx, val) {
            const numVal = parseInt(val, 10);
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('blinds', true);

            // ⚡ Immediately update the reactive dictionary so the slider and % text move live with the mouse pointer
            this.state.devices[idx] = numVal;
        },

        // =========================================================================
        // 🎨 NATIVE LIGHTING CONTROL MATHEMATICS & DISPATCHERS
        // =========================================================================

        openSceneModal(item) {
            this.activeSceneId = item.id;
            this.activeSceneName = item.name;
            document.getElementById('scene_confirm_modal').showModal();
        },

        confirmSceneExecution() {
            if (this.activeSceneId) {
                this.dispatchEvent(this.activeSceneId);
            }
            document.getElementById('scene_confirm_modal').close();
        },

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
            const isCurrentlyOn = this.state.devices[72001] === 'ON';
            this.injectLabHubStateChange(72001, !isCurrentlyOn);
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
            // ⚡ DYNAMIC ROUTING: Resolves the semantic fluid type to its strict hardware IDX
            const targetIdx = fluidType === 'cold' ? 11002 : 11003;
            this.publishEvent("WATER_PULSE", { idx: targetIdx, count: 396, lab_override: true });
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

        formatEntityRegistryReport(report) {
            // Prefer server-rendered text (shared with CLI) so copy stays aligned.
            if (report.report_text) return report.report_text;

            const lines = [];
            const stats = report.stats || {};
            const warnings = report.warnings || [];
            const errors = report.errors || [];
            const live = Object.prototype.hasOwnProperty.call(stats, "live_metadata_with_entity_id")
                || Object.prototype.hasOwnProperty.call(stats, "live_metadata_missing_entity_id");

            lines.push("ENTITY REGISTRY / CUTOVER CHECK");
            lines.push("========================================");
            lines.push("");
            lines.push("How to read this report");
            lines.push("- GREEN (ok=true, no ERRORS): safe to proceed toward Phase 4");
            lines.push("  (entity_id-only engine). Smoke-test after deploy anyway.");
            lines.push("- RED (any ERRORS): do NOT enable entity_id-only / Phase 4 until fixed.");
            lines.push("- WARNINGS: non-blocking. Mostly leftover bare idxs in Python");
            lines.push("  (host metrics, sauna, simulator). Clear later; not a cutover blocker.");
            if (live) {
                lines.push("- This run included live device_metadata (Admin API / running WanOS).");
            } else {
                lines.push("- No live device_metadata in this run (typical for CLI offline).");
            }
            lines.push("");
            lines.push("STATS");
            lines.push("----------------------------------------");
            lines.push(JSON.stringify(stats, null, 2));
            if (warnings.length) {
                lines.push("");
                lines.push(`WARNINGS (${warnings.length}) - non-blocking follow-up`);
                warnings.forEach((w) => lines.push(`  - ${w}`));
            }
            if (errors.length) {
                lines.push("");
                lines.push(`ERRORS (${errors.length}) - BLOCKING`);
                errors.forEach((e) => lines.push(`  - ${e}`));
                lines.push("");
                lines.push("RESULT: RED - do not cut over until fixed.");
            } else {
                lines.push("");
                lines.push("RESULT: GREEN - entity_id cutover checks passed.");
                if (warnings.length) {
                    lines.push(`(${warnings.length} warning(s) are non-blocking; clear Python magic idxs in a follow-up.)`);
                }
            }
            return lines.join("\n");
        },

        async runEntityRegistryCheck() {
            if (this.entityRegistryChecking) return;
            this.entityRegistryChecking = true;
            try {
                const res = await fetch("/api/debug/entity-registry-check", {
                    headers: this.getAuthHeaders(),
                });
                const report = await res.json();
                if (!res.ok) {
                    this.entityRegistryReportOk = false;
                    this.entityRegistryReportText = `Entity check failed: ${report.error || res.status}`;
                    document.getElementById("entity_registry_check_modal")?.showModal();
                    this.publishEvent("ALERT_INJECTED", {
                        msg_text: `Entity check failed: ${report.error || res.status}`,
                    });
                    return;
                }
                this.entityRegistryReportOk = !!report.ok;
                this.entityRegistryReportText = this.formatEntityRegistryReport(report);
                document.getElementById("entity_registry_check_modal")?.showModal();

                const errN = (report.errors || []).length;
                const warnN = (report.warnings || []).length;
                const stats = report.stats || {};
                if (report.ok) {
                    this.publishEvent("ALERT_INJECTED", {
                        msg_text: `Entity check GREEN — ${stats.automation_entity_ids || 0} automation ids, ${stats.registry_active || 0} registry rows (${warnN} warnings)`,
                    });
                } else {
                    this.publishEvent("ALERT_INJECTED", {
                        msg_text: `Entity check RED — ${errN} error(s), ${warnN} warning(s)`,
                    });
                }
            } catch (err) {
                this.entityRegistryReportOk = false;
                this.entityRegistryReportText = `Entity check request failed: ${err}`;
                document.getElementById("entity_registry_check_modal")?.showModal();
                this.publishEvent("ALERT_INJECTED", {
                    msg_text: `Entity check request failed: ${err}`,
                });
            } finally {
                this.entityRegistryChecking = false;
            }
        },

        async downloadEntityIdList() {
            if (this.entityIdListDownloading) return;
            this.entityIdListDownloading = true;
            try {
                const res = await fetch("/api/admin/entity-id-list", {
                    headers: this.getAuthHeaders(),
                });
                if (!res.ok) {
                    let errMsg = `HTTP ${res.status}`;
                    try {
                        const body = await res.json();
                        errMsg = body.error || errMsg;
                    } catch (_) { /* response may be plain text */ }
                    this.publishEvent("ALERT_INJECTED", {
                        msg_text: `Entity ID list download failed: ${errMsg}`,
                    });
                    return;
                }
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "entity_id-list.txt";
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
                this.publishEvent("ALERT_INJECTED", {
                    msg_text: "Downloaded entity_id-list.txt",
                });
            } catch (err) {
                this.publishEvent("ALERT_INJECTED", {
                    msg_text: `Entity ID list download failed: ${err}`,
                });
            } finally {
                this.entityIdListDownloading = false;
            }
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
        },

        // =========================================================================
        // 🗂️ PRESET FILTER MANAGEMENT
        // =========================================================================

        // Determines if the current view state differs from the system defaults
        isFilterActive() {
            return this.searchQuery.trim() !== ""
                || this.typeFilter !== "ALL"
                || this.statusFilter !== "ALL"
                || this.sortMode !== "NAME"
                || this.actuatorFavoritesOnly === true;
        },

        // Rapidly clears all UI filters and sort modes back to their base defaults
        clearAllFilters() {
            this.searchQuery = "";
            this.actuatorSearchQuery = "";
            this.typeFilter = "ALL";
            this.statusFilter = "ALL";
            this.sortMode = "NAME";
            this.actuatorFavoritesOnly = false;
        },

        // Router for when a user clicks one of the 1-4 preset circles
        handlePresetClick(index) {
            if (this.presets[index] !== null) {
                // APPLY PRESET: Slot is filled, instantly map the saved payload to the reactive filters
                const p = this.presets[index];
                this.searchQuery = p.searchQuery || "";
                this.typeFilter = p.typeFilter || "ALL";
                this.statusFilter = p.statusFilter || "ALL";
                this.sortMode = p.sortMode || "NAME";
                this.actuatorFavoritesOnly = p.favoritesOnly === true;
            } else {
                // SAVE PRESET: Slot is empty, verify if there is actually a modified view to save
                if (!this.isFilterActive()) {
                    this.showToast("Kan filter niet bewaren: er is geen filter of sortering.");
                } else {
                    this.activePresetSlot = index;
                    document.getElementById('preset_save_modal').showModal();
                }
            }
        },

        // Invoked via the modal to permanently commit the current view state to the active slot
        confirmSavePreset() {
            if (this.activePresetSlot !== null) {
                const payload = {
                    searchQuery: this.searchQuery,
                    typeFilter: this.typeFilter,
                    statusFilter: this.statusFilter,
                    sortMode: this.sortMode,
                    favoritesOnly: this.actuatorFavoritesOnly === true,
                };
                this.presets[this.activePresetSlot] = payload;
                localStorage.setItem('wanos_view_presets', JSON.stringify(this.presets));
                this.activePresetSlot = null; // Release the lock
                document.getElementById('preset_save_modal').close();
            }
        },

        // Clears a specific slot and flushes the deletion to persistent storage
        removePreset(index) {
            this.presets[index] = null;
            localStorage.setItem('wanos_view_presets', JSON.stringify(this.presets));
        },

        // Compiles a human-readable summary of the payload for the edit menu
        getPresetSummary(index) {
            const p = this.presets[index];
            if (!p) return "Empty";

            let parts = [];
            if (p.searchQuery) parts.push(`"${p.searchQuery}"`);
            if (p.typeFilter !== "ALL") parts.push(p.typeFilter);
            if (p.statusFilter !== "ALL") parts.push(p.statusFilter);
            if (p.favoritesOnly) parts.push("Favorites");

            if (p.sortMode === "STATUS") parts.push("Sort: Status");
            else if (p.sortMode === "TYPE") parts.push("Sort: Type, Name");
            else if (p.sortMode === "NAME") parts.push("Sort: Name");

            // Fallback for edge cases, though isFilterActive normally guards against saving empty states
            return parts.length > 0 ? parts.join(" • ") : "Default View";
        },

        // Simple ephemeral UI feedback manager
        showToast(msg) {
            this.toastMessage = msg;
            if (this.toastTimeout) clearTimeout(this.toastTimeout);
            this.toastTimeout = setTimeout(() => { this.toastMessage = ""; }, 3000);
        }
    };
}

// =========================================================================
// 🔐 AUTHENTICATION & LOGIN UI LOGIC
// =========================================================================
function loginApp() {
    return {
        pin: "",
        errorMsg: "",
        loading: true,

        async init() {
            // ⚡ ROLE-AWARE SESSION AUTO-RESTORE:
            // Inspects localStorage for existing authorization signatures before rendering the keypad.
            // This guarantees standard user roles are never accidentally misrouted to administrative pages.
            const persistentToken = localStorage.getItem("wanos_jwt");
            if (persistentToken) {
                try {
                    const claimsPayload = JSON.parse(atob(persistentToken.split('.')[1]));
                    const currentUnixTimestamp = Math.floor(Date.now() / 1000);

                    // Validate session expiration timeline parameters before allowing a bypass redirect
                    if (claimsPayload.exp && currentUnixTimestamp < claimsPayload.exp) {
                        if (claimsPayload.role === "admin") {
                            window.location.href = "/admin.html";
                            return;
                        } else if (claimsPayload.role === "user") {
                            window.location.href = "/deviceexplorer.html";
                            return;
                        } else if (claimsPayload.role === "kiosk") {
                            window.location.href = "/kiosk.html";
                            return;
                        }
                    } else {
                        localStorage.removeItem("wanos_jwt"); // Session expired clean-up
                    }
                } catch (authError) {
                    localStorage.removeItem("wanos_jwt"); // Evict malformed context tokens
                }
            }

            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token');

            // Invisible Token Bypass Execution (For Kiosks / Magic Links)
            if (token) {
                await this.submitAuth({ token: token });
            } else {
                this.loading = false;
            }
        },

        addNumber(n) {
            if (this.pin.length < 4) {
                this.pin += n;
                this.errorMsg = "";
                // Auto-submit when exactly 4 digits are entered
                if (this.pin.length === 4) {
                    this.submit();
                }
            }
        },

        clear() {
            this.pin = "";
            this.errorMsg = "";
        },

        deletePin() {
            if (this.pin.length > 0) {
                this.pin = this.pin.slice(0, -1);
                this.errorMsg = "";
            }
        },

        handleKeydown(e) {
            if (this.loading) return;

            // Capture numeric keys (0-9)
            if (e.key >= '0' && e.key <= '9') {
                this.addNumber(e.key);
            }
            // Capture Backspace to delete a single digit
            else if (e.key === 'Backspace') {
                this.deletePin();
            }
            // Capture 'C' or 'Escape' to clear the entire pad
            else if (e.key.toLowerCase() === 'c' || e.key === 'Escape') {
                this.clear();
            }
            // Capture Enter to submit
            else if (e.key === 'Enter') {
                if (this.pin.length === 4) {
                    this.submit();
                }
            }
        },

        submit() {
            if (this.pin.length > 0) {
                this.loading = true;
                this.errorMsg = "";
                this.submitAuth({ pin: this.pin });
            }
        },

        async submitAuth(payload) {
            try {
                const res = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();

                if (res.status === 200) {
                    // PERSISTENT AUTHENTICATION: Save the token to survive tab closure and browser reboots
                    localStorage.setItem("wanos_jwt", data.token);
                    window.location.href = data.redirect;
                } else {
                    this.pin = "";
                    this.errorMsg = data.detail || data.error || "Authentication failed.";
                    this.loading = false;
                }
            } catch (error) {
                this.errorMsg = "Server offline or unreachable.";
                this.loading = false;
                this.pin = "";
            }
        }
    }
}