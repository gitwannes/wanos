// --- file: frontend/app.js ---

// ECharts instances MUST live outside the Alpine component data. Alpine deep-wraps
// everything reachable from `this` in reactive Proxies; a proxied ECharts instance
// corrupts ECharts' internal identity checks and resize()/setOption() then throw
// ("Cannot read properties of undefined"), silently aborting the rest of the render.
const wanosHistoryCharts = { day: null, month: null, year: null };
const wanosActuatorCharts = { day: null, month: null, year: null };
/** C24: temp/hum day fullscreen overlay chart (outside Alpine reactive data). */
let wanosClimateFsChart = null;

/**
 * C19: stored ECharts instance is unusable for `el` (missing, disposed, or bound
 * to a previous Alpine node after x-if / x-for remount).
 * @param {Object|null|undefined} inst
 * @param {HTMLElement|null} el
 * @returns {boolean}
 */
function wanosChartInstanceStale(inst, el) {
    if (!inst || !el) return true;
    try {
        if (typeof inst.isDisposed === "function" && inst.isDisposed()) return true;
        return inst.getDom() !== el;
    } catch (e) {
        return true;
    }
}

/**
 * C19: drop a stale instance so the next ensure can init on the live node.
 * @param {{ day: Object|null, month: Object|null, year: Object|null }} store
 * @param {"day"|"month"|"year"} key
 * @param {HTMLElement} el
 * @returns {void}
 */
function wanosDisposeStaleChart(store, key, el) {
    const inst = store[key];
    if (!inst || !wanosChartInstanceStale(inst, el)) return;
    try { inst.dispose(); } catch (e) { /* ignore */ }
    store[key] = null;
}

/**
 * C19: resize only instances still attached to the document.
 * @param {{ day: Object|null, month: Object|null, year: Object|null }} store
 * @returns {void}
 */
function wanosResizeConnectedCharts(store) {
    Object.values(store || {}).forEach((c) => {
        if (!c) return;
        try {
            const el = typeof c.getDom === "function" ? c.getDom() : null;
            if (el && el.isConnected) c.resize();
        } catch (e) { /* ignore */ }
    });
}

/** Min viewport width for History / Automation and the top-row join (tablets+). */
const WANOS_WIDE_MIN_PX = 768;

/** History & Automation: bounce phones to Device Explorer (also on shrink).
 *  Returns true when the viewport is too narrow (caller should abort init). */
function wanosRedirectIfNarrow() {
    const mq = window.matchMedia(`(min-width: ${WANOS_WIDE_MIN_PX}px)`);
    const bounce = () => {
        if (!mq.matches) window.location.replace("/deviceexplorer.html");
    };
    bounce();
    if (typeof mq.addEventListener === "function") mq.addEventListener("change", bounce);
    else if (typeof mq.addListener === "function") mq.addListener(bounce);
    return !mq.matches;
}

function wanosApp() {
    return {
        connected: false,
        isAdmin: false,
        /** B10G: hide shared NOT CONNECTED overlay during backend config reload alerts. */
        reloadSuppressOverlay: false,
        /** B10G: debounce SSE onerror → offline (ms). */
        _sseOfflineDebounce: null,
        /** B10H: dedupe concurrent connectSSE / reconnect attempts. */
        _sseConnectInFlight: null,
        /** B10H: SSE reconnect in flight — keep overlay hidden when REST snapshot is still fresh. */
        _sseReconnecting: false,
        /** B10H: ms since epoch when fetchFullSnapshot last succeeded. */
        _lastSnapshotAt: 0,
        /** B10H: skip REST on SSE reconnect when snapshot is newer than this (ms). */
        _SNAPSHOT_REUSE_MS: 30000,
        /** B10H: only show NOT CONNECTED on SSE loss when snapshot is older than this (ms). */
        _SNAPSHOT_STALE_MS: 60000,
        /** C37: abort hung /api/state on resume (ms). */
        _SNAPSHOT_FETCH_TIMEOUT_MS: 20000,
        /** C37: ignore duplicate resume events within this window (ms). */
        _RESUME_RECONNECT_MIN_MS: 1500,
        /** C37: skip force-reconnect after short backgrounding unless frozen thaw (ms). */
        _RESUME_HIDDEN_FORCE_MS: 5000,
        /** C37: generation token so superseded connectSSE work does not reopen a zombie stream. */
        _sseGeneration: 0,
        /** C37: AbortController for in-flight snapshot fetch. */
        _snapshotAbort: null,
        /** C37: ms since epoch when init finished wiring SSE. */
        _pageReadyAt: 0,
        /** C37: ms since epoch when document became hidden (0 = unknown). */
        _pageHiddenAt: 0,
        /** C37: ms since epoch of last forced resume reconnect. */
        _lastResumeReconnectAt: 0,
        showHiddenNodes: false,

        /**
         * B10L: second line under Re-connecting copy (honest milestones; no fake %).
         * Overlay is hidden when connected — these strings apply while !connected.
         */
        get offlineStatusLine() {
            if (this._sseReconnecting) return "Live stream reconnecting...";
            if (this._lastSnapshotAt > 0) return "Waiting for live stream...";
            return "Waiting for snapshot...";
        },

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
                lg_connected: false, // ⚡ LG bridge healthy (not TV power) — G16
                lg_integration_enabled: false, // ⚡ Master UI switch for LG webOS — G16
                sonos_connected: false, // ⚡ Tracks physical availability of Sonos network
                sonos_integration_enabled: false, // ⚡ Master UI switch to block/allow Sonos commands
                onkyo_connected: false, // ⚡ Tracks physical TCP availability of Onkyo Receivers
                onkyo_integration_enabled: false, // ⚡ Master UI switch to block/allow Onkyo Receivers
                lcd_integration_enabled: false, // ⚡ Master UI switch to block/allow LCD MQTT publishes
                native_rfx_devices: [], // ⚡ Enables reactivity for the dynamic panel
                dashboard_events: [], // ⚡ B10B: Explorer buttons from events: catalog ({id, name, require_confirmation})
                hidden_explorer_idxs: [], // ⚡ Devices to hide from the Device Explorer
                hue_presets: {}, // From config_hue_presets.auto.yaml (Pi) via load_config / SSE
                sonos_stations: {}, // ⚡ TuneIn station key → URI from config.yaml (Blocky 6C)
                lg_apps: {} // ⚡ G16 Blockly catalog key → label
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
                phases_pwm: {"U": 0, "V": 0, "W": 0},
                fireorder: "--",
                session_start_time: null,
                session_end_time: null,
                ventilation_state: "OFF",
                ventilation_deadline: null,
                light_color: "#FFD180",
                lcd_line1: "",
                lcd_line2: "",
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
                p_elements_calc_watts: 0.0,
                r_th_insulation_coefficient: null,
                extracted_p_u: 3500.0,
                extracted_p_v: 3500.0,
                extracted_p_w: 2000.0,
                running_energy_real_wh: 0.0,
                running_energy_calc_wh: 0.0,
                total_energy_real_wh: 0.0,
                meter_total_kwh: 0.0,
                water_cold_today_l: 0.0,
                water_hot_today_l: 0.0,
                last_sauna_session: null,
                last_ir_session: null,
                session_count_sauna: 0,
                session_count_ir: 0
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
        // Active blinds slider drag (Device Explorer). Keeps the row in ON/OFF mid-travel
        // filters until commit so @change is not lost when optimistic value hits 0/100.
        shutterDragIdx: null,
        // C12: position at drag start for proportional ui-lock
        shutterDragFrom: null,

        // ⚡ Light Control Modal State
        activeLightId: null,
        activeLightName: "",
        activeLightBri: 100,
        activeLightHex: "#FFD180",
        colorPicker: null, // ⚡ Holds the iro.js UI instance
        // B9A: Hue colour-preset CRUD (config_hue_presets.auto.yaml) in Explorer Edit mode
        huePresetEditMode: false,
        huePresetUsages: {},
        /** Last preset chip clicked; used with xy+bri match for Save-current gating. */
        activeHuePresetKey: null,
        /** True only after user tweaks wheel/brightness since selecting/saving a preset. */
        huePresetDirtySinceSelect: false,
        /** Suppress preset-key clear while iro snaps to a preset colour programmatically. */
        _huePresetApplyGuard: false,
        /** DaisyUI modals for preset save/rename/delete (replaces window.prompt/confirm). */
        huePresetNameModalTitle: "",
        huePresetNameInput: "",
        huePresetNameModalMode: null,
        huePresetNameModalKey: null,
        huePresetDeleteKey: null,
        huePresetDeleteDisplayName: "",
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
        appliedPresetIndex: null, // Last applied view-preset slot (UI caption / highlight)
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
        historyDayTitle: "Usage day window",
        historyDaySubtitle: "",
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
        // C10: actuator History chart section titles (binary / hits / level)
        actuatorDayTitle: "Level day window",
        actuatorDaySubtitle: "",
        actuatorMonthTitle: "Last month (counts + level)",
        actuatorYearTitle: "Last year (counts + level)",
        actuatorChartHasData: { day: false, month: false, year: false },
        // C16: last day payload retention (from API) for sliding window
        historyDayRetentionDays: 7,
        // C24/C25: temp/hum day fullscreen overlay
        climateFsOpen: false,
        climateFsShow: { temp: true, hum: true, dew: true, ah: false, ci: true, dewLikelihood: true },
        climateFsCiHelpOpen: false,
        // C25: Compare with peer climate (null / "" = none)
        climateFsCompareIdx: "",
        climateFsPeerShow: { temp: true, hum: true, dew: true },
        climateFsPeerDayData: null,
        climateFsPeerName: "",
        climateFsSmooth: true,
        historyDayClimateData: null,
        actuatorList: [],
        actuatorFavorites: [],
        actuatorFavoritesOnly: false,
        // C1: Edit/Done favorites — row checkboxes only while true; idle shows no indicators
        favoritesEditMode: false,
        actuatorSearchQuery: "",
        selectedActuatorIdx: null,
        selectedActuatorName: "",
        actuatorLoading: false,
        sessionHistoryType: "sauna",
        sessionHistoryRows: [],
        sessionHistoryTotal: 0,
        sessionHistoryOffset: 0,
        elementPowerMeta: {
            w_u: 3500, w_v: 3500, w_w: 2000, w_ir: 525,
            updated_at: null,
            learn_count_sauna: 0, learn_count_ir: 0,
            last_learn_sauna_status: null, last_learn_sauna_detail: null, last_learn_sauna_at: null,
            last_learn_ir_status: null, last_learn_ir_measured_w: null, last_learn_ir_at: null,
            session_count_sauna: 0, session_count_ir: 0,
        },
        sessionAuditPopoverId: null,
        sessionAuditPopoverRow: null,
        sessionAuditPopoverStyle: "",
        sessionAuditPopoverPinned: false,
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

            // C10: drop past/done timers (deadline reached) — do not show stale "imminent"
            list = list.filter(t => {
                const dl = Number(t && t.deadline);
                return Number.isFinite(dl) && dl > now;
            });

            // Sort ascending by absolute deadline
            list.sort((a, b) => a.deadline - b.deadline);

            return list.map(t => {
                const d = new Date(t.deadline * 1000);
                const absTime = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });

                const diff = t.deadline - now;
                let relTime = "";
                if (diff < 60) relTime = `in ${diff} sec`;
                else {
                    const mins = Math.floor(diff / 60);
                    const hrs = Math.floor(mins / 60);
                    if (hrs > 0) relTime = `in ${hrs}h ${mins % 60}m`;
                    else relTime = `in ${mins} min`;
                }

                return {
                    ...t,
                    absTime: absTime,
                    relTime: relTime,
                    displayLabel: this.formatPlannedTimelineLabel(t),
                };
            });
        },

        /** Admin Planned Automations row label (C2 / env schedule catalog names). */
        formatPlannedTimelineLabel(t) {
            const eventLabels = {
                BLINDS_OPEN_TRIGGER: "Shutters open",
                BLINDS_CLOSE_TRIGGER: "Shutters close",
                MORNING_ON_TRIGGER: "Morning lights on",
                SUNRISE_TRIGGER: "Morning lights off",
                SUNSET_TRIGGER: "Evening lights on",
                EVENING_OFF_TRIGGER: "Evening lights off",
                SAUNA_ON: "Sauna ON",
                SAUNA_OFF: "Sauna OFF",
                IR_ON: "IR ON",
                IR_OFF: "IR OFF",
            };
            const timerLabels = {
                env_blinds_open: "Shutters open",
                env_blinds_close: "Shutters close",
                env_twi_morn_on: "Morning lights on",
                env_twi_morn_off: "Morning lights off",
                env_twi_eve_on: "Evening lights on",
                env_twi_eve_off: "Evening lights off",
            };

            if (t.type === "scene") {
                let name = String(t.name || "").trim();
                if (!name || name === "System Macro") {
                    name = eventLabels[t.event_type]
                        || timerLabels[t.timer_id]
                        || String(t.event_type || t.timer_id || "Unknown");
                }
                return `Scene: ${name}`;
            }
            if (t.type === "blinds") {
                const dev = String(t.name || "Blinds").trim();
                if (t.target_state === "100") return `${dev} → close`;
                if (t.target_state === "0") return `${dev} → open`;
                return `${dev} → ${t.target_state}%`;
            }
            if (t.type === "switch" || t.type === "light") {
                const dev = String(t.name || "Device").trim();
                return `${dev} → ${t.target_state || "?"}`;
            }
            if (t.target_state) {
                return `${t.name || t.timer_id || "Timer"} → ${t.target_state}`;
            }
            return String(t.name || t.timer_id || "Scheduled");
        },

        // C2: independent dismiss per surface (banner vs bell); not synced to server removal
        bannerDismissedAlertIds: [],
        bellDismissedAlertIds: [],

        // 🔔 Intelligent Alert Routing Getters
        // Banner = critical only. Bell = critical + error/warning/success/info (connection
        // transitions use error/success so they never hit the red banner).
        get criticalAlerts() {
            if (!this.state.system.system_alert_msgs) return [];
            const dismissed = new Set(this.bannerDismissedAlertIds || []);
            return this.state.system.system_alert_msgs.filter(
                msg => msg.level === 'critical' && !dismissed.has(msg.id)
            );
        },

        /** Criticals for the Admin bell only (banner dismiss does not hide these). */
        get bellCriticalAlerts() {
            if (!this.state.system.system_alert_msgs) return [];
            const dismissed = new Set(this.bellDismissedAlertIds || []);
            return this.state.system.system_alert_msgs.filter(
                msg => msg.level === 'critical' && !dismissed.has(msg.id)
            );
        },

        get nonCriticalAlerts() {
            if (!this.state.system.system_alert_msgs) return [];
            const dismissed = new Set(this.bellDismissedAlertIds || []);
            // Newest-first; skip ids dismissed from the bell surface
            return this.state.system.system_alert_msgs
                .filter(msg => msg.level !== 'critical' && !dismissed.has(msg.id))
                .reverse();
        },

        /** Bell feed = criticals + non-criticals (error/warning/success/info). */
        get bellAlerts() {
            const crit = this.bellCriticalAlerts.slice().reverse();
            return crit.concat(this.nonCriticalAlerts);
        },

        get unreadAlertCount() {
            return this.bellAlerts.length;
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
            if (!this.state.system.lg_integration_enabled) disabled.push("LG TV");
            if (!this.state.system.rfxcom_integration_enabled) disabled.push("RFX");
            if (!this.state.system.zwave_integration_enabled) disabled.push("Z-Wave");
            if (!this.state.system.owm_integration_enabled) disabled.push("OpenWeatherMap");
            if (!this.state.system.sonos_integration_enabled) disabled.push("Sonos");
            if (!this.state.system.onkyo_integration_enabled) disabled.push("Onkyo");
            if (!this.state.system.lcd_integration_enabled) disabled.push("LCD screens");
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
                if (meta.origin === 'epson' && !this.state.system.epson_integration_enabled) continue;
                if (meta.origin === 'lg' && !this.state.system.lg_integration_enabled) continue;

                // Native Physical & Cloud Integrations
                if (meta.origin === 'gpio_input' && !this.state.hardware.gpio_input_enabled) continue;
                if (meta.origin === 'sht11' && !this.state.hardware.sht11_enabled) continue;
                if (meta.origin === 'owm' && !this.state.system.owm_integration_enabled) continue;
                // Dashboard event rows are rendered from dashboard_events below; skip synthetic scene metadata here to avoid duplicates.
                if (meta.type === 'scene') continue;

                const idx = parseInt(idxStr, 10);
                // Internal virtual lock flags should never be visible in Explorer (user or admin).
                if (idx === 90001) continue;
                // Hard-deny (Pi power) — never visible, even with Hidden toggle.
                if (idx === 71040 || meta.entity_id === "switch.safety.safety_wisc_5v") continue;

                // Hidden = meta.hidden or idx in system.hidden_explorer_idxs
                // (from automations.auto.yaml deviceexplorer_hide)
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

                const rawValue = this.state.devices[idx]
                    ?? this.state.devices[idxStr]
                    ?? this.state.devices[String(idx)];
                let isOn = false;

                const isDead = rawValue === 'DEAD';

                if (!isDead) {
                    if (meta.type === 'blinds') {
                        // Shutters: > 0% = ON
                        isOn = parseInt(rawValue, 10) > 0;
                    } else if (meta.type === 'door') {
                        // OPEN = active / ajar (matches History status emphasis)
                        isOn = rawValue === 'OPEN';
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
                    } else if (meta.type === 'light') {
                        displayText = (rawValue.state === 'ON' || rawValue.state === 'OFF')
                            ? rawValue.state
                            : (isOn ? 'ON' : 'OFF');
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

                // ⏱️ CLIENT-SIDE COUNTDOWN MODELER (C21: only while device is ON)
                // Iterates over active timers to compute any matching absolute auto-off deadlines
                let autoOffCountdown = null;
                if (isOn === true && this.state.system.active_timers) {
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
                    // Product type only for binary actuators / Hue; do not default sensors→switch.
                    resolved_product_type: (() => {
                        if (meta.resolved_product_type) return meta.resolved_product_type;
                        if (meta.origin === "hue") return "light";
                        const t = String(meta.type || "").toLowerCase();
                        if (t === "switch" || t === "light") return "switch";
                        return null;
                    })(),
                    // Same as Onkyo: config max_volume on meta; fallback by origin if meta missing.
                    max_volume: (() => {
                        if (meta.max_volume !== undefined && meta.max_volume !== null) return meta.max_volume;
                        if (meta.origin === "onkyo") return 60;
                        if (meta.origin === "sonos") return 70;
                        return 100;
                    })(),
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

            // 2. Map dashboard events (B10B: UUID id on the bus)
            // ⚡ Display as long as the Automation Engine is alive to process them
            // ⚡ Admin Guard: Hide from the diagnostic "Hidden Nodes" view
            if (!this.showHiddenNodes && this.state.system.dashboard_events && this.state.system.automations_enabled) {
                for (const ev of this.state.system.dashboard_events) {
                    list.push({
                        id: ev.id, // event UUID — dispatchEvent / publishEvent uses this as type
                        name: ev.name,
                        type: 'scene',
                        raw_value: null,
                        is_on: null, // Stateless element
                        require_confirmation: ev.require_confirmation === true
                    });
                }
            }

            // 2b. Favorites (shared localStorage with Sensor History)
            if (this.actuatorFavoritesOnly) {
                list = list.filter(item => {
                    if (this.actuatorFavorites.includes(this._favoriteIdKey(item.id))) return true;
                    // Water pair: keep cold primary if either fluid is favorited
                    const cap = this.historyCapabilityByIdx[Number(item.id)];
                    if (cap && cap.kind === "water" && Array.isArray(cap.pairIdxs)) {
                        return cap.pairIdxs.some(i => this.actuatorFavorites.includes(this._favoriteIdKey(i)));
                    }
                    return false;
                });
            }

            // 3. Apply Text Search (multi-term AND + `-exclude`, case-insensitive)
            // History applies an enriched query in explorerDisplayList (includes "(no history)").
            // C10: keep blinds row visible while dragging when search matched state text (e.g. "60").
            if (this.explorerMode !== "history" && this.searchQuery.trim() !== "") {
                const parsed = this._parseTextQuery(this.searchQuery);
                if (parsed) {
                    list = list.filter(item => {
                        if (this.shutterDragIdx != null && Number(this.shutterDragIdx) === Number(item.id)) {
                            return true;
                        }
                        return this._matchesTextQuery(this._explorerSearchHaystack(item), parsed);
                    });
                }
            }

            // 4. Apply Type Filter
            if (this.typeFilter !== "ALL") {
                list = list.filter(item => {
                    const t = String(item.type || "").toLowerCase();
                    const isBinaryActuator = t === "switch" || t === "light";
                    const rpt = item.resolved_product_type
                        || (item.is_hue ? "light" : (isBinaryActuator ? "switch" : null));
                    // Product SWITCH/LIGHT: binary actuators only (not sensors/scenes/doors/…).
                    if (this.typeFilter === "SWITCH") {
                        return isBinaryActuator && !item.is_hue && rpt === "switch";
                    }
                    if (this.typeFilter === "LIGHT") {
                        return isBinaryActuator && !item.is_hue && rpt === "light";
                    }
                    if (this.typeFilter === "HUE") return item.is_hue;
                    if (this.typeFilter === "SPEAKER") return t === "speaker";
                    if (this.typeFilter === "SCENE") return t === "scene";
                    if (this.typeFilter === "SHUTTER" || this.typeFilter === "BLINDS") return t === "blinds";
                    if (this.typeFilter === "SENSOR") {
                        return t === "temp" || t === "hum" || t === "temp_hum"
                            || t === "power" || t === "energy" || t === "sensor"
                            || t === "door" || t === "fluid" || t === "motion";
                    }
                    return true;
                });
            }

            // 5. Apply Status Filter (ON/OFF)
            // Sensors/scenes stay hidden. Blinds: only mid-travel (not fully open 0, not fully closed 100)
            // appear — and in both ON and OFF filters.
            if (this.statusFilter !== "ALL") {
                list = list.filter(item => {
                    if (item.type === 'temp' || item.type === 'hum' || item.type === 'temp_hum'
                        || item.type === 'power' || item.type === 'energy' || item.type === 'scene') {
                        return false;
                    }
                    if (item.type === 'blinds') {
                        return this._blindsVisibleInStatusFilter(item.id, item.raw_value);
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
                // C10: scene synthetic idxs are not History list rows
                if ((a.type || "") === "scene") continue;
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

        /** Control vs History: one list source for the shared row UI. */
        get explorerActiveList() {
            return this.explorerMode === "history" ? this.explorerDisplayList : this.unifiedDeviceList;
        },

        /** Control list as-is; History = same inventory + water pair merge (no series filter). */
        get explorerDisplayList() {
            const base = this.unifiedDeviceList;
            if (this.explorerMode !== "history") return base;
            // Drop secondary fluid row (hot) when cold/hot are merged into one Water detail.
            const hotSecondary = new Set();
            for (const item of base) {
                const cap = this.historyCapabilityByIdx[Number(item.id)];
                if (cap && cap.kind === "water" && cap.hotIdx != null && Number(item.id) === Number(cap.hotIdx)
                    && Number(cap.hotIdx) !== Number(cap.primaryIdx)) {
                    hotSecondary.add(Number(item.id));
                }
            }
            let list = base
                // C10: omit all catalog-event / scene rows from History (UE + SE); Control unchanged
                .filter(item => item.type !== "scene" && !hotSecondary.has(Number(item.id)))
                .map(item => {
                    const cap = this.historyCapabilityByIdx[Number(item.id)];
                    if (!cap || cap.kind !== "water") return item;
                    return {
                        ...item,
                        name: cap.name || "Water",
                        display_text: this._waterPairLiveStatus(cap),
                    };
                });

            // History search: name + live values + "(no history)" so `-history` / `24` / `ON` work.
            const parsed = this._parseTextQuery(this.searchQuery);
            if (parsed) {
                list = list.filter(item => {
                    const marker = this.deviceHasHistory(item.id) ? "" : "(no history)";
                    return this._matchesTextQuery(this._explorerSearchHaystack(item, marker), parsed);
                });
            }
            return list;
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
            return item.type || "";
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

        /**
         * Multi-term search: space-separated tokens, AND includes, `-token` excludes.
         * Case-insensitive. Example: "hue slpk -wannes"
         */
        _parseTextQuery(query) {
            const raw = String(query || "").trim();
            if (!raw) return null;
            const include = [];
            const exclude = [];
            for (const tok of raw.split(/\s+/)) {
                if (!tok) continue;
                // Exclude only "-word" (dash + letter/digit). "---" / "--" are literal includes.
                if (/^-[a-zA-Z0-9]/.test(tok)) {
                    exclude.push(tok.slice(1).toLowerCase());
                } else {
                    include.push(tok.toLowerCase());
                }
            }
            if (!include.length && !exclude.length) return null;
            return { include, exclude };
        },

        _matchesTextQuery(haystack, query) {
            const parsed = (query && typeof query === "object" && Array.isArray(query.include))
                ? query
                : this._parseTextQuery(query);
            if (!parsed) return true;
            const hay = String(haystack || "").toLowerCase();
            for (const t of parsed.include) {
                if (!hay.includes(t)) return false;
            }
            for (const t of parsed.exclude) {
                if (hay.includes(t)) return false;
            }
            return true;
        },

        /** Name + live value/status for explorer search (temp/hum figures, ON/OFF/OPEN/CLOSED, …). */
        _explorerSearchHaystack(item, extra = "") {
            if (!item) return String(extra || "");
            const parts = [item.name, item.display_text, extra];
            const raw = item.raw_value;
            if (raw != null && raw !== "DEAD") {
                if (typeof raw === "object") {
                    if (raw.temp != null) parts.push(String(raw.temp));
                    if (raw.hum != null) parts.push(String(raw.hum));
                    if (raw.state != null) parts.push(String(raw.state));
                    if (raw.volume != null) parts.push(String(raw.volume));
                } else {
                    parts.push(String(raw));
                }
            }
            if (item.is_on === true) parts.push("ON");
            else if (item.is_on === false) parts.push("OFF");
            if (item.type === "blinds") {
                const n = parseInt(raw, 10);
                if (n === 0) parts.push("OPEN");
                else if (n === 100) parts.push("CLOSED");
            }
            return parts.filter(p => p != null && p !== "").join(" ");
        },

        /**
         * Blinds closed-% (0 open … 100 closed). Mid-travel only — used by ON/OFF status filters
         * so partially open blinds show under both filters; endpoints stay on ALL / BLINDS.
         */
        _blindsIsPartialPosition(raw) {
            if (raw == null || raw === "DEAD" || raw === "Sync...") return false;
            const n = parseInt(raw, 10);
            return Number.isFinite(n) && n > 0 && n < 100;
        },

        /** Mid-travel OR currently dragging this shutter (avoid filter eviction before commit). */
        _blindsVisibleInStatusFilter(idx, raw) {
            if (this.shutterDragIdx != null && Number(this.shutterDragIdx) === Number(idx)) {
                return true;
            }
            return this._blindsIsPartialPosition(raw);
        },

        /** History/actuator overview status: OPEN | CLOSED | "N%". */
        _blindsIsPartialFromStatus(status) {
            const st = String(status || "").trim().toUpperCase();
            if (!st || st === "OPEN" || st === "CLOSED" || st === "—") return false;
            const m = st.match(/^(\d+)\s*%$/);
            if (!m) return false;
            const n = parseInt(m[1], 10);
            return Number.isFinite(n) && n > 0 && n < 100;
        },

        // ⚡ UNIVERSAL DEVICE ONLINE DECIPHER
        // Dynamically checks if a device's parent integration is currently running.
        isDeviceOnline(idx) {
            const meta = this.state.device_metadata[idx];
            if (!meta) return false;
            if (meta.origin === 'zwave') return this.state.system.zwave_integration_enabled;
            if (meta.origin === 'hue') return this.state.system.hue_integration_enabled;
            if (meta.origin === 'epson') return this.state.system.epson_integration_enabled;
            if (meta.origin === 'lg') return this.state.system.lg_integration_enabled;
            if (meta.origin === 'sonos') return this.state.system.sonos_integration_enabled;
            if (meta.origin === 'onkyo') return this.state.system.onkyo_integration_enabled;
            if (meta.origin === 'gpio_input') return this.state.hardware.gpio_input_enabled;
            if (meta.origin === 'sht11') return this.state.hardware.sht11_enabled;
            return true; // Fallback for local macros/scenes
        },

        // IR Snapping Matrix (duty % + PWM freq for zero-crossing SSRs).
        // net = 50 Hz => 100 zero-crossings / s = 10 ms between crossings.
        // 100% = DC 100%, freq 5 Hz (freq irrelevant): all on
        //  75% = DC  75%, freq 25 Hz: 3 zc on, 1 zc off
        //  67% = DC  67%, freq 33 Hz: 2 zc on, 1 zc off
        //  50% = DC  50%, freq 50 Hz: 1 zc on, 1 zc off
        //  33% = DC  33%, freq 33 Hz: 1 zc on, 2 zc off
        //  25% = DC  25%, freq 25 Hz: 1 zc on, 3 zc off
        //  0%  = 0 Hz
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
        sunriseDisplayText: "",
        sunsetDisplayText: "",
        /** C25 Admin Outside weather: last OWM poll HH:MM + relative (ticker-driven). */
        owmLastPollDisplayText: "",
        /** Admin GPIO output arm ladder label (ticker-driven so WAIT TEMP -> READY updates). */
        gpioOutputArmStatusText: "OFFLINE",
        gpioOutputArmStatusClassName: "text-gray-500",

        sunCyclePopoverOpen: false,

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

            // Shared favorites (Device Explorer + Sensor History).
            // C12: keep scene UUID strings; numeric idxs as numbers (Number(uuid) was NaN → all scenes).
            try {
                const fav = JSON.parse(localStorage.getItem("wanos_history_favorites") || "[]");
                this.actuatorFavorites = Array.isArray(fav)
                    ? fav.map((x) => this._favoriteIdKey(x)).filter((x) => x != null)
                    : [];
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
                    } else if (payload.role === "user" && (
                        window.location.pathname.includes("admin.html") ||
                        window.location.pathname.includes("sensorhistory.html")
                    )) {
                        // ⚡ THE BOUNCER: user role cannot open Admin or Session History
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
            // C37: Android PWA warm resume — force SSE heal (timers/EventSource freeze otherwise).
            this._bindPageResumeHandlers();
            this._pageReadyAt = Date.now();

            if (this.isAdmin && window.location.pathname.includes("admin.html")) {
                this.loadElementPower();
                // C35: refresh learn counts when a session row lands in metrics (SSE).
                this.$watch(
                    () => {
                        const m = this.state.metrics || {};
                        const ir = m.last_ir_session;
                        const sauna = m.last_sauna_session;
                        return [
                            ir && ir.session_id,
                            ir && ir.start_timestamp,
                            sauna && sauna.session_id,
                            sauna && sauna.start_timestamp,
                            m.session_count_ir,
                            m.session_count_sauna,
                        ].join("|");
                    },
                    () => { this.loadElementPower(); }
                );
            }
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

        /**
         * C7: re-apply filters from sessionStorage and force select↔model sync
         * (SSE reconnect / snapshot can leave selects looking inactive).
         */
        _reapplyActiveFiltersFromSession() {
            const savedFilters = sessionStorage.getItem('wanos_active_filters');
            if (!savedFilters) return;
            let parsed;
            try {
                parsed = JSON.parse(savedFilters);
            } catch (e) {
                return;
            }
            const nextSearch = parsed.searchQuery !== undefined ? parsed.searchQuery : "";
            const nextType = parsed.typeFilter || "ALL";
            const nextStatus = parsed.statusFilter || "ALL";
            const nextSort = parsed.sortMode || "NAME";
            // Persist desired filters first so watchers during the bump cannot clobber session
            sessionStorage.setItem('wanos_active_filters', JSON.stringify({
                searchQuery: nextSearch,
                typeFilter: nextType,
                statusFilter: nextStatus,
                sortMode: nextSort
            }));
            // Force Alpine + native <select> refresh even when values are unchanged
            this.searchQuery = nextSearch === "" ? "\u200b" : "";
            this.typeFilter = nextType === "ALL" ? "SWITCH" : "ALL";
            this.statusFilter = nextStatus === "ALL" ? "ON" : "ALL";
            this.sortMode = nextSort === "NAME" ? "TYPE" : "NAME";
            this.$nextTick(() => {
                this.searchQuery = nextSearch;
                this.typeFilter = nextType;
                this.statusFilter = nextStatus;
                this.sortMode = nextSort;
                this.saveFilters();
            });
        },

        async fetchFullSnapshot() {
            // C37: abort any prior hung snapshot (common on Android resume before radio is ready).
            if (this._snapshotAbort) {
                try { this._snapshotAbort.abort(); } catch (e) { /* ignore */ }
            }
            this._snapshotAbort = new AbortController();
            const ac = this._snapshotAbort;
            const timeoutId = setTimeout(() => {
                try { ac.abort(); } catch (e) { /* ignore */ }
            }, this._SNAPSHOT_FETCH_TIMEOUT_MS);
            try {
                // Attach the authorization headers to the request
                const res = await fetch("/api/state", {
                    headers: this.getAuthHeaders(),
                    signal: ac.signal
                });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = '/login.html';
                    return false;
                }
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const fullState = await res.json();
                this._applyFullSnapshot(fullState);
                // C7: restore Control/History filter chrome after every snapshot (incl. SSE reconnect)
                this._reapplyActiveFiltersFromSession();
                console.log("✅ Full state snapshot loaded.");
                return true;
            } catch (err) {
                if (err && err.name === "AbortError") {
                    // C37: timeout or supersede — caller owns connected / overlay state.
                    console.warn("⚠️ Full state snapshot aborted (timeout or supersede).");
                    return false;
                }
                console.error("⚠️ Failed to load full state snapshot:", err);
                this._lastSnapshotAt = 0;
                this.connected = false;
                return false;
            } finally {
                clearTimeout(timeoutId);
                if (this._snapshotAbort === ac) this._snapshotAbort = null;
            }
        },

        /**
         * C37: wire Page Lifecycle hooks so Android PWA warm resume heals SSE.
         * Frozen thaw may fire `resume` without `visibilitychange` (Chrome Android).
         */
        _bindPageResumeHandlers() {
            document.addEventListener("visibilitychange", () => {
                if (document.visibilityState === "hidden") {
                    this._pageHiddenAt = Date.now();
                    return;
                }
                this._onPageResume({ fromFreeze: false });
            });
            // Page Lifecycle API — frozen → active (may omit visibilitychange).
            document.addEventListener("resume", () => {
                this._onPageResume({ fromFreeze: true });
            });
            window.addEventListener("pageshow", (ev) => {
                if (ev.persisted) this._onPageResume({ fromFreeze: true });
            });
        },

        /**
         * C37: decide whether to force-close EventSource and reconnect after foregrounding.
         * @param {{ fromFreeze: boolean }} opts
         */
        _onPageResume(opts) {
            const fromFreeze = !!(opts && opts.fromFreeze);
            if (document.visibilityState === "hidden") return;
            if (!this._pageReadyAt || (Date.now() - this._pageReadyAt) < 2000) return;

            const hiddenFor = this._pageHiddenAt ? (Date.now() - this._pageHiddenAt) : 0;
            // Brief app switches: keep stream; frozen thaw / long background: force heal.
            if (!fromFreeze && hiddenFor > 0 && hiddenFor < this._RESUME_HIDDEN_FORCE_MS) {
                return;
            }

            const now = Date.now();
            if (this._lastResumeReconnectAt
                && (now - this._lastResumeReconnectAt) < this._RESUME_RECONNECT_MIN_MS) {
                return;
            }
            this._lastResumeReconnectAt = now;
            this._pageHiddenAt = 0;
            this._forceSseReconnect(fromFreeze ? "freeze-resume" : "visibility-resume");
        },

        /**
         * C37: tear down zombie EventSource / hung snapshot and start a fresh connect.
         * Does not trust readyState === OPEN after mobile suspension.
         * @param {string} reason
         * @returns {Promise<void>}
         */
        _forceSseReconnect(reason) {
            console.info("[C37] Forcing SSE reconnect:", reason);
            this._sseGeneration += 1;
            const gen = this._sseGeneration;

            if (this.sseWatchdog) {
                clearTimeout(this.sseWatchdog);
                this.sseWatchdog = null;
            }
            this._cancelSseOfflineDebounce();
            if (this._snapshotAbort) {
                try { this._snapshotAbort.abort(); } catch (e) { /* ignore */ }
                this._snapshotAbort = null;
            }
            if (this.eventSource) {
                try { this.eventSource.close(); } catch (e) { /* ignore */ }
                this.eventSource = null;
            }
            // Drop hung in-flight tracking so a new connect can start.
            this._sseConnectInFlight = null;

            const snapshotAge = this._lastSnapshotAt ? Date.now() - this._lastSnapshotAt : Infinity;
            this._sseReconnecting = true;
            // Long-background: show NOT CONNECTED immediately (do not wait for 3s debounce).
            if (snapshotAge >= this._SNAPSHOT_STALE_MS) {
                this.connected = false;
            }

            const run = this._connectSSEOnce(gen).catch((err) => {
                console.error("[C37] Resume reconnect failed:", err);
                if (gen === this._sseGeneration) {
                    this._sseReconnecting = false;
                    this.connected = false;
                }
            });
            this._sseConnectInFlight = run;
            return run.finally(() => {
                if (this._sseConnectInFlight === run) this._sseConnectInFlight = null;
            });
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

            if (fullState.devices) {
                this._mergeDevicesIntoState(fullState.devices);
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
            this._lastSnapshotAt = Date.now();
            this.connected = true;
            if (fullState.system && fullState.system.system_alert_msgs && window.WanOSReloadAlerts) {
                this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(
                    fullState.system.system_alert_msgs
                );
            }
        },

        _syncReloadSuppressFromAlerts(msgs) {
            if (!window.WanOSReloadAlerts || !Array.isArray(msgs)) return;
            this.reloadSuppressOverlay = window.WanOSReloadAlerts.computeSuppressOverlay(msgs);
        },

        _scheduleSseOfflineDebounce() {
            const snapshotAge = this._lastSnapshotAt ? Date.now() - this._lastSnapshotAt : Infinity;
            // Fresh REST snapshot: reconnect quietly — do not flash NOT CONNECTED (B10H).
            if (snapshotAge < this._SNAPSHOT_STALE_MS) {
                this._cancelSseOfflineDebounce();
                this._sseReconnecting = true;
                return;
            }
            if (this._sseOfflineDebounce) clearTimeout(this._sseOfflineDebounce);
            this._sseOfflineDebounce = setTimeout(() => {
                this._sseOfflineDebounce = null;
                this._sseReconnecting = false;
                this.connected = false;
            }, 3000);
        },

        _cancelSseOfflineDebounce() {
            if (this._sseOfflineDebounce) {
                clearTimeout(this._sseOfflineDebounce);
                this._sseOfflineDebounce = null;
            }
        },

        _markSseAlive() {
            this._cancelSseOfflineDebounce();
            this._sseReconnecting = false;
            this.connected = true;
        },

        /**
         * Merge device idx keys as both string and number so Control `item.is_on`
         * (numeric lookup) sees SSE JSON string keys.
         * @param {Object<string, *>} incoming
         */
        _mergeDevicesIntoState(incoming) {
            const next = Object.assign({}, this.state.devices);
            for (const [key, val] of Object.entries(incoming || {})) {
                next[key] = val;
                const n = Number(key);
                if (!Number.isNaN(n)) next[n] = val;
            }
            this.state.devices = next;
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
            if (domain === "c18_commit") {
                // C18: apply/revert RAM for Control rows; bypass uiLocks (clicked optimistic snap-back).
                for (const idx of Object.keys(payload)) {
                    delete this.uiLocks[idx];
                    const n = Number(idx);
                    if (!Number.isNaN(n)) delete this.uiLocks[n];
                }
                this._mergeDevicesIntoState(payload);
                if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                    this.syncLabControls();
                }
                return;
            }
            if (domain === "devices") {
                // ⚡ OPTIMISTIC UI LOCK GUARD (Anti-Rubberbanding)
                // Filter out incoming telemetry for sliders we recently touched to prevent snapping
                const filteredPayload = {};
                const now = Date.now();

                for (const [idx, val] of Object.entries(payload)) {
                    const n = Number(idx);
                    const locked = (this.uiLocks[idx] && now < this.uiLocks[idx])
                        || (!Number.isNaN(n) && this.uiLocks[n] && now < this.uiLocks[n]);
                    if (locked) {
                        const until = this.uiLocks[idx] || this.uiLocks[n];
                        const remaining = Math.round((until - now) / 1000);
                        console.info(`[UI Guard] Event ignored for IDX ${idx}: locked for ${remaining} more seconds to prevent rubberbanding.`);
                        continue;
                    }
                    filteredPayload[idx] = val;
                }

                this._mergeDevicesIntoState(filteredPayload);
                if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                    this.syncLabControls();
                }
                return;
            }

            this.state[domain] = Object.assign({}, this.state[domain], payload);

            // ⚡ INTELLIGENT UI UNLOCKER: Watch for backend sweep or config completion dictionaries
            if (domain === "system" && payload.system_alert_msgs) {
                this._syncReloadSuppressFromAlerts(payload.system_alert_msgs);
                if (payload.system_alert_msgs.some(msg => msg.message && msg.message.includes("Sweeper complete"))) {
                    this.sweepRunning = false;
                }
                const reloadDone = (msg) => {
                    const text = msg && msg.message ? String(msg.message) : "";
                    if (window.WanOSReloadAlerts) {
                        return window.WanOSReloadAlerts.COMPLETE.includes(text)
                            || window.WanOSReloadAlerts.isFailed(text);
                    }
                    return text.includes("Config reloaded") || text.includes("Config reload failed");
                };
                if (payload.system_alert_msgs.some(reloadDone)) {
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
            if (this._sseConnectInFlight) {
                return this._sseConnectInFlight;
            }
            if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
                return Promise.resolve();
            }
            const gen = this._sseGeneration;
            const run = this._connectSSEOnce(gen);
            this._sseConnectInFlight = run;
            return run.finally(() => {
                if (this._sseConnectInFlight === run) this._sseConnectInFlight = null;
            });
        },

        /**
         * Open REST snapshot (unless fresh) + EventSource.
         * @param {number} [generation] C37: skip open if a newer force-reconnect superseded this run
         * @returns {Promise<void>}
         */
        _connectSSEOnce(generation) {
            const gen = generation != null ? generation : this._sseGeneration;
            const snapshotAge = this._lastSnapshotAt ? Date.now() - this._lastSnapshotAt : Infinity;
            const reuseSnapshot = this._lastSnapshotAt > 0 && snapshotAge < this._SNAPSHOT_REUSE_MS;

            const openEventStream = () => {
                // C37: abandoned after a newer force-reconnect
                if (gen !== this._sseGeneration) return;

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
                        if (gen !== this._sseGeneration) return;
                        console.warn("⚠️ Watchdog Timeout! No server signal detected for 10s. Forcing reconnect...");
                        this._scheduleSseOfflineDebounce();
                        if (this.eventSource) this.eventSource.close();
                        setTimeout(() => this.connectSSE(), 3000);
                    }, 10000); // 2x the 5-second backend ping interval
                };

                resetWatchdog();

                this.eventSource.onopen = () => {
                    if (gen !== this._sseGeneration) return;
                    this._sseReconnecting = false;
                    this._markSseAlive();
                };

                this.eventSource.onmessage = (event) => {
                    if (gen !== this._sseGeneration) return;
                    // This is where the data is received from the backend, main.py
                    try {
                        // Any incoming data frame proves the underlying pipeline is alive
                        resetWatchdog();
                        const msg = JSON.parse(event.data);

                        if (msg.domain === "ping") {
                            this._markSseAlive();
                            return;
                        }

                        this._applyDomainDelta(msg.domain, msg.data);
                        this._markSseAlive();
                    } catch (err) {
                        console.error("⚠️ Failed parsing SSE delta update:", err);
                    }
                };

                this.eventSource.onerror = (err) => {
                    if (gen !== this._sseGeneration) return;
                    if (this.sseWatchdog) clearTimeout(this.sseWatchdog);
                    console.error("❌ SSE stream broke. Re-linking context in 3s...");
                    if (this.eventSource) this.eventSource.close();
                    this._scheduleSseOfflineDebounce();
                    // On reconnect, reuse recent REST snapshot when possible (B10H).
                    setTimeout(() => this.connectSSE(), 3000);
                };
            };

            if (reuseSnapshot) {
                this._sseReconnecting = true;
                return Promise.resolve().then(openEventStream);
            }

            if (this._lastSnapshotAt > 0) {
                this._sseReconnecting = true;
            }

            return this.fetchFullSnapshot().then((ok) => {
                if (gen !== this._sseGeneration) return;
                if (!ok) {
                    this._sseReconnecting = false;
                    this.connected = false;
                    throw new Error("Full state snapshot failed");
                }
                openEventStream();
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

            // Sun Cycle Live Relative Trackers (C27: Admin + Explorer ℹ popover)
            if (this.state.sensors.sunrise_unix) {
                this.sunriseRelativeText = this.getRelativeTime(this.state.sensors.sunrise_unix, now);
                this.sunriseDisplayText = this.formatSunDiagnosticLine(
                    this.state.sensors.sunrise_unix, now
                );
            } else {
                this.sunriseRelativeText = "";
                this.sunriseDisplayText = "";
            }

            if (this.state.sensors.sunset_unix) {
                this.sunsetRelativeText = this.getRelativeTime(this.state.sensors.sunset_unix, now);
                this.sunsetDisplayText = this.formatSunDiagnosticLine(
                    this.state.sensors.sunset_unix, now
                );
            } else {
                this.sunsetRelativeText = "";
                this.sunsetDisplayText = "";
            }

            // Last OWM poll relative age (same 1 Hz path as sun cycle — not a getter).
            const pollTs = this.state.sensors && this.state.sensors.owm_last_poll_unix;
            if (pollTs) {
                this.owmLastPollDisplayText = this.formatSunDiagnosticLine(pollTs, now);
            } else {
                this.owmLastPollDisplayText = "";
            }

            // GPIO output arm ladder — refresh every tick so WAIT TEMP -> READY
            // after first SHT11 composite without requiring a page reload.
            this.gpioOutputArmStatusText = this.gpioOutputArmStatus();
            this.gpioOutputArmStatusClassName = this.gpioOutputArmStatusClass();
        },

        formatTime(totalSeconds) {
            const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
            const s = (Math.floor(totalSeconds) % 60).toString().padStart(2, '0');
            return `${h}:${m}:${s}`;
        },

        /** LCD integration master switch (Admin); gates MQTT to LCD Pi agent. */
        lcdIntegrationEnabled() {
            return Boolean(this.state.system && this.state.system.lcd_integration_enabled);
        },

        /** True when MQTT/WISC screen1 has any non-blank line (else show standby). */
        lcdScreen1HasContent() {
            if (!this.lcdIntegrationEnabled()) {
                return false;
            }
            const l1 = (this.state.sauna && this.state.sauna.lcd_line1) ? String(this.state.sauna.lcd_line1) : '';
            const l2 = (this.state.sauna && this.state.sauna.lcd_line2) ? String(this.state.sauna.lcd_line2) : '';
            return l1.trim().length > 0 || l2.trim().length > 0;
        },

        /**
         * Map one MQTT LCD line to display glyphs, cell-by-cell (§X = 1 cell).
         * Must NOT trim — leading/trailing spaces are how the composer centers text.
         */
        lcdPrettyLine(raw) {
            const s = String(raw == null ? '' : raw);
            let out = '';
            for (let i = 0; i < s.length; ) {
                if (s[i] === '§' && i + 1 < s.length && s[i + 1] >= '0' && s[i + 1] <= '9') {
                    const slot = s[i + 1];
                    if (slot === '0') out += '♥';
                    else if (slot === '1') out += '°';
                    // other custom slots: omit glyph but still consume one cell via skip
                    i += 2;
                    continue;
                }
                out += s[i];
                i += 1;
            }
            return out;
        },

        /**
         * Exact 16x2 LCD text for the WISC panel (single pre; spaces preserved).
         * Pads/truncates each row to 16 cells so centered lines match the physical LCD.
         */
        lcdScreen1Display() {
            if (!this.lcdIntegrationEnabled()) {
                return 'no LCD text:\nintegration off';
            }
            if (!this.lcdScreen1HasContent()) {
                return 'WanOS Wisc standby';
            }
            const l1 = this.lcdPad16(this.lcdPrettyLine(this.state.sauna.lcd_line1));
            const l2 = this.lcdPad16(this.lcdPrettyLine(this.state.sauna.lcd_line2));
            return l1 + '\n' + l2;
        },

        /** Force exactly 16 display columns (never trim — pad/slice only). */
        lcdPad16(s) {
            const t = String(s == null ? '' : s);
            if (t.length >= 16) return t.slice(0, 16);
            return t + ' '.repeat(16 - t.length);
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
                wanosResizeConnectedCharts(wanosHistoryCharts);
                wanosResizeConnectedCharts(wanosActuatorCharts);
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
            if (wanosRedirectIfNarrow()) return;
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
            // C19: let Alpine morph the History list before we touch ECharts
            // (x-for may replace #chart-day while the old instance is still stored).
            await this.$nextTick();
            if (this.selectedSensorIdx != null && this.selectedSensorKind) {
                const still = (this.explorerDisplayList || []).some(
                    i => Number(i.id) === Number(this.selectedSensorIdx)
                );
                // Soft update: keep ECharts instances mounted (no dispose / x-if flicker)
                if (still) await this.reloadSelectedSensorDetail({ soft: true });
                else this.closeHistoryDetail();
            }
        },

        async selectExplorerHistoryItem(item) {
            if (!item || this.explorerMode !== "history") return;
            // No series → no-op (UI shows red "(no history)" on the name).
            if (!this.deviceHasHistory(item.id)) return;
            const cap = this.historyCapabilityByIdx[Number(item.id)];
            if (!cap) return;

            // Already open for this row (or its water primary) → collapse.
            if (this.isExplorerHistoryRowSelected(item)) {
                this.closeHistoryDetail();
                return;
            }
            const primary = Number(cap.primaryIdx != null ? cap.primaryIdx : item.id);
            await this.selectHistoryRow({
                idx: primary,
                name: cap.name || item.name,
                category: cap.category,
                type: item.type,
                scrollIdx: item.id,
            });
        },

        /** True when History detail is open for this list row (handles water primaryIdx remap). */
        isExplorerHistoryRowSelected(item) {
            if (!item || this.selectedSensorIdx == null) return false;
            const selected = Number(this.selectedSensorIdx);
            const id = Number(item.id);
            if (selected === id) return true;
            const cap = this.historyCapabilityByIdx[id];
            if (!cap) return false;
            const primary = Number(cap.primaryIdx != null ? cap.primaryIdx : id);
            return selected === primary
                && (this.selectedSensorKind == null || this.selectedSensorKind === cap.category);
        },

        _isHistoryRowHidden(idx, explicitHidden) {
            const idxStr = String(idx);
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            const hiddenIdxs = this.state.system.hidden_explorer_idxs || [];
            return explicitHidden === true || meta.hidden === true
                || hiddenIdxs.includes(idx) || hiddenIdxs.includes(Number(idx));
        },

        /** Hue color-dot CSS for the shared Explorer leading slot. */
        explorerHueSwatchStyle(item) {
            if (!item || !item.is_on) return "background-color: #333; opacity: 0.5;";
            const raw = item.raw_value;
            const hex = (typeof raw === "object" && raw && raw.xy)
                ? this.xyToHex(raw.xy[0], raw.xy[1], raw.bri)
                : "#FFD180";
            return `background-color: ${hex}; box-shadow: 0 0 10px ${hex};`;
        },

        /** Display label for History type chips. */
        historyTypeLabel(type, origin) {
            const t = String(type || "");
            const o = String(origin || "").toLowerCase();
            if (t === "light") return o === "hue" ? "Hue light" : "light";
            if (t === "blinds") return "shutter";
            return t || "";
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
            if (type === "door") return "🚪";
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
                && type !== "blinds" && type !== "speaker" && type !== "scene" && type !== "door"
                && type !== "temp_hum" && type !== "temp"
                && !(type === "sensor" && (name.includes("temp") || name.includes("volt") || name.includes("motion")))) {
                return "🎬";
            }
            if ((name.includes("sauna") || name.includes("zoutlamp"))
                && type !== "blinds" && type !== "speaker" && type !== "scene" && type !== "door"
                && type !== "temp_hum" && type !== "temp" && type !== "power" && type !== "energy"
                && !name.includes("cinema")
                && !(type === "sensor" && (name.includes("temp") || name.includes("volt") || name.includes("motion")))) {
                return "♨️";
            }
            if ((name.includes(" ir ") || name.startsWith("ir ") || name === "ir" || name.includes("infrarood"))
                && type !== "blinds" && type !== "speaker" && type !== "scene" && type !== "door"
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
            // Scenes are stateless triggers — no live value in History.
            if (item.type === "scene") return "";
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

            if (item.type === "door") {
                const st = String(item.raw_value || item.display_text || "").toUpperCase();
                if (st === "OPEN" || st === "CLOSED") return st;
                return item.display_text != null ? String(item.display_text) : "—";
            }

            if (item.type === "switch" || item.type === "light" || item.is_hue) {
                const raw = item.raw_value;
                if (typeof raw === "object" && raw !== null && (raw.state === "ON" || raw.state === "OFF")) {
                    return raw.state;
                }
                if (raw === "ON" || raw === "OFF") return raw;
                return item.is_on ? "ON" : "OFF";
            }

            const dt = item.display_text;
            if (dt != null && typeof dt === "object") {
                if (dt.state === "ON" || dt.state === "OFF") return dt.state;
                return "—";
            }
            return dt != null ? String(dt) : "—";
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
            if (item.type === "door") {
                return item.is_on ? "text-error animate-pulse" : "text-base-500";
            }
            if (item.type === "switch" || item.type === "light" || item.is_hue) {
                return item.is_on ? "text-warning" : "text-base-500";
            }
            return "text-base-content/80";
        },

        /**
         * C10: pin ECharts legend/tooltip color to lineStyle (avoids palette swap vs drawn line).
         */
        _pinSeriesLegendColors(seriesList) {
            for (const s of seriesList || []) {
                if (!s) continue;
                const c = (s.lineStyle && s.lineStyle.color)
                    || (s.itemStyle && s.itemStyle.color)
                    || s.color;
                if (!c) continue;
                s.color = c;
                s.itemStyle = Object.assign({}, s.itemStyle || {}, { color: c });
            }
            return seriesList;
        },

        /**
         * C10/C12: History actuator chart family for one idx.
         * @returns {"hits"|"binary"|"audio"|"level"}
         */
        _actuatorChartKind(idx) {
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            const type = String(meta.type || "").toLowerCase();
            const origin = String(meta.origin || "").toLowerCase();

            // Motion = impulse hits (not ON/OFF, not continuous Level)
            if (type === "motion") return "hits";

            // C12 follow-up: Hue + audio month/year = duration ON (no events, no level min/max)
            if (origin === "hue") return "audio";
            if (type === "speaker" || origin === "sonos" || origin === "onkyo") return "audio";
            // Blinds keep Level min/max + Events on month/year
            if (type === "blinds") return "level";

            // Binary ON/OFF: door, switch, non-Hue light, Epson, etc.
            return "binary";
        },

        /** Y-axis label formatter: blank at 0, "hit" at ceiling (motion day). */
        _hitAxisLabelFormatter(ceiling) {
            const top = Number(ceiling) > 0 ? Number(ceiling) : 100;
            return (v) => {
                const n = Number(v);
                if (!Number.isFinite(n)) return "";
                if (n <= 0) return "";
                if (n >= top) return "hit";
                return "";
            };
        },

        /** Y-axis label formatter: OFF at 0, ON at ceiling (binary day/period). */
        _binaryAxisLabelFormatter(ceiling) {
            const top = Number(ceiling) > 0 ? Number(ceiling) : 100;
            return (v) => {
                const n = Number(v);
                if (!Number.isFinite(n)) return "";
                if (n <= 0) return "OFF";
                if (n >= top) return "ON";
                return "";
            };
        },

        _syncActuatorChartTitles(kind) {
            // C16: day title — default viewport 24 h; zoom-out up to hires_days buffer
            if (kind === "hits") {
                this.actuatorDayTitle = "Hits day window";
                this.actuatorMonthTitle = "Hits last month";
                this.actuatorYearTitle = "Hits last year";
            } else if (kind === "binary" || kind === "audio") {
                this.actuatorDayTitle = kind === "binary" ? "ON / OFF day window" : "Level day window";
                this.actuatorMonthTitle = "Last month (duration ON)";
                this.actuatorYearTitle = "Last year (duration ON)";
            } else {
                this.actuatorDayTitle = "Level day window";
                this.actuatorMonthTitle = "Last month (counts + level)";
                this.actuatorYearTitle = "Last year (counts + level)";
            }
        },

        /** C24/C25: fixed line colors for fullscreen overlay series (each distinct). */
        _climateFsSeriesColor(key) {
            const map = {
                temp: "#eab308",
                hum: "#22c55e",
                dew: "#38bdf8",
                ah: "#a855f7",
                ci: "#f472b6",
                dewLikelihood: "#c026d3",
                peerTemp: "#f97316",
                peerHum: "#4ade80",
                peerDew: "#67e8f9",
            };
            return map[key] || "#9ca3af";
        },

        /** C25: day payload carries OWM dew-likelihood history. */
        get climateFsHasDewLikelihood() {
            const d = this.historyDayClimateData;
            if (!d) return false;
            if (d.has_dew_likelihood === true) return true;
            return this._seriesDrawable(d.series && d.series.dew_likelihood);
        },

        /** C25: other temp / temp_hum climate sensors for Compare with (full catalog, not Explorer filters). */
        _climateComparePeerCatalog() {
            const cur = Number(this.selectedSensorIdx);
            const out = [];
            for (const s of (this.historySensors || [])) {
                if (s.kind !== "climate") continue;
                const idx = Number(s.idx);
                if (!Number.isFinite(idx) || idx === cur) continue;
                out.push({
                    idx,
                    name: s.label || `IDX ${idx}`,
                    has_humidity: s.has_humidity !== false,
                });
            }
            out.sort((a, b) => String(a.name).localeCompare(String(b.name)));
            return out;
        },

        get climateFsComparePeers() {
            return this._climateComparePeerCatalog();
        },

        /** Plain-language help for apparent humidity (comfort index). */
        get climateFsCiHelpText() {
            return "Feels-like humidity is a comfort index (0–100%). It combines dew point and air temperature "
                + "to show how humid the air feels — not a separate sensor reading. "
                + "Higher values mean sweat evaporates less easily and the air feels stickier. "
                + "Tooltip on the chart also shows the comfort band (dry → tropical).";
        },

        /** Display name for CI series (checkbox, chart, tooltip, CSV). */
        get climateFsCiSeriesName() {
            return "Feels-like humidity";
        },

        /** True when the overlay viewport is phone-narrow (portrait or small width). */
        _climateFsIsCompactWidth() {
            try {
                return window.matchMedia("(max-width: 640px)").matches;
            } catch (e) {
                return false;
            }
        },

        /** Short landscape (phone rotated) — chrome must stay compact so the chart fits. */
        _climateFsIsShortLandscape() {
            try {
                return window.matchMedia("(max-height: 480px)").matches;
            } catch (e) {
                return false;
            }
        },

        _bindClimateFsResize() {
            if (this._climateFsResizeBound) return;
            this._climateFsOnResize = () => {
                if (!this.climateFsOpen) return;
                if (wanosClimateFsChart) {
                    try { wanosClimateFsChart.resize(); } catch (e) { /* ignore */ }
                }
                this._renderClimateFullscreenChart({ soft: true });
            };
            window.addEventListener("resize", this._climateFsOnResize);
            window.addEventListener("orientationchange", this._climateFsOnResize);
            this._climateFsResizeBound = true;
        },

        _unbindClimateFsResize() {
            if (!this._climateFsResizeBound) return;
            window.removeEventListener("resize", this._climateFsOnResize);
            window.removeEventListener("orientationchange", this._climateFsOnResize);
            this._climateFsOnResize = null;
            this._climateFsResizeBound = false;
        },

        /** Fullscreen overlay title including max retention days from API. */
        get climateFsOverlayTitle() {
            const name = this.selectedSensorName || "Climate";
            const days = this.historyDayRetentionDays || 7;
            return `${name} — day window (up to ${days} d)`;
        },

        /** Hardware / configured level ceiling (Sonos + Onkyo: meta.max_volume). */
        _actuatorLevelDeviceMax(idx) {
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            const maxVol = meta.max_volume != null ? Number(meta.max_volume) : null;
            if (Number.isFinite(maxVol) && maxVol > 0) return maxVol;
            if (meta.origin === "onkyo") return 60;
            if (meta.origin === "sonos") return 70;
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
                // C10: History omits all type===scene (catalog event synthetic idxs)
                if ((a.type || "") === "scene") continue;
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
                list = list.filter(r => this.actuatorFavorites.includes(this._favoriteIdKey(r.idx)));
            }

            // Shared type filter with Device Explorer
            if (this.typeFilter !== "ALL") {
                list = list.filter(r => {
                    const meta = (this.state.device_metadata && this.state.device_metadata[r.idx]) || {};
                    const isHue = meta.origin === "hue";
                    const t = String(r.type || meta.type || "").toLowerCase();
                    const isBinaryActuator = t === "switch" || t === "light";
                    const rpt = meta.resolved_product_type
                        || (isHue ? "light" : (isBinaryActuator ? "switch" : null));
                    if (this.typeFilter === "SWITCH") {
                        return isBinaryActuator && !isHue && rpt === "switch";
                    }
                    if (this.typeFilter === "LIGHT") {
                        return isBinaryActuator && !isHue && rpt === "light";
                    }
                    if (this.typeFilter === "HUE") return isHue;
                    if (this.typeFilter === "SPEAKER") return t === "speaker" || r.type === "speaker";
                    if (this.typeFilter === "SCENE") return t === "scene" || r.type === "scene";
                    if (this.typeFilter === "SHUTTER" || this.typeFilter === "BLINDS") {
                        return t === "blinds" || r.type === "blinds";
                    }
                    if (this.typeFilter === "SENSOR") {
                        return ["temp", "hum", "temp_hum", "power", "energy", "sensor", "host", "climate", "water", "door", "fluid", "motion"]
                            .includes(t) || r.category === "utility" || r.category === "climate" || r.category === "host";
                    }
                    return true;
                });
            }

            // Shared status filter: binary actuators + mid-travel blinds (both ON and OFF)
            if (this.statusFilter !== "ALL") {
                list = list.filter(r => {
                    if (r.category !== "actuator") return false;
                    if (["temp", "hum", "temp_hum", "power", "energy", "scene", "host", "climate"].includes(r.type)) {
                        return false;
                    }
                    if (r.type === "blinds") {
                        return this._blindsIsPartialFromStatus(r.status);
                    }
                    const st = String(r.status || "").toUpperCase();
                    const isOn = st === "ON" || st === "CLOSED" || st === "HIT";
                    const isOff = st === "OFF" || st === "OPEN";
                    if (this.statusFilter === "ON") return isOn;
                    if (this.statusFilter === "OFF") return isOff;
                    return false;
                });
            }

            const parsed = this._parseTextQuery(this.actuatorSearchQuery || this.searchQuery || "");
            if (parsed) {
                list = list.filter(r => {
                    const meta = (this.state.device_metadata && this.state.device_metadata[r.idx]) || {};
                    const typeLabel = this.historyTypeLabel(r.type, meta.origin) || "";
                    const hay = `${r.idx} ${r.name || ""} ${r.type || ""} ${typeLabel} ${r.status || ""} ${r.category}`;
                    return this._matchesTextQuery(hay, parsed);
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
            // Generation token: ignore stale async completions after a newer click/close.
            const gen = (this._historySelectGen = (this._historySelectGen || 0) + 1);
            this._disposeHistoryCharts();
            this._disposeActuatorCharts();
            this.selectedSensorIdx = id;
            this.selectedSensorKind = kind;
            this.selectedSensorName = row.name || String(id);
            this.selectedHistoryIdx = (kind === "utility" || kind === "climate" || kind === "host") ? id : null;
            this.selectedActuatorIdx = kind === "actuator" ? id : null;
            this.selectedActuatorName = kind === "actuator" ? row.name : "";
            await this.$nextTick();
            if (gen !== this._historySelectGen) return;
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            if (gen !== this._historySelectGen) return;
            const scrollIdx = row.scrollIdx != null ? row.scrollIdx : id;
            this._scrollExplorerRowToTop(scrollIdx);
            await this.reloadSelectedSensorDetail();
            if (gen !== this._historySelectGen) return;
        },

        /** Pin the clicked history name row under the sticky filter bar. */
        _scrollExplorerRowToTop(idx) {
            const row = document.getElementById(`explorer-row-${idx}`);
            if (!row) return;
            const sticky = document.querySelector("[data-explorer-sticky-filters]");
            const margin = (sticky ? sticky.getBoundingClientRect().height : 0) + 8;
            const top = row.getBoundingClientRect().top + window.pageYOffset - margin;
            window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
        },

        async reloadSelectedSensorDetail(opts = {}) {
            const soft = !!opts.soft;
            if ((this.selectedSensorKind === "utility" || this.selectedSensorKind === "climate"
                    || this.selectedSensorKind === "host")
                && this.selectedSensorIdx != null) {
                this.selectedHistoryIdx = this.selectedSensorIdx;
                await this.reloadHistoryCharts({ soft });
                // C6: one resize pass after soft/hard draw (soft helper skips per-chart resize)
                // C19: skip detached instances (Alpine remount left the old canvas off-document)
                wanosResizeConnectedCharts(wanosHistoryCharts);
            } else if (this.selectedSensorKind === "actuator" && this.selectedSensorIdx != null) {
                this.selectedActuatorIdx = this.selectedSensorIdx;
                await this.reloadActuatorCharts({ soft });
                wanosResizeConnectedCharts(wanosActuatorCharts);
            }
        },

        closeHistoryDetail() {
            this._historySelectGen = (this._historySelectGen || 0) + 1;
            this.closeClimateFullscreen();
            this._disposeHistoryCharts();
            this._disposeActuatorCharts();
            this.selectedSensorIdx = null;
            this.selectedSensorKind = null;
            this.selectedSensorName = "";
            this.selectedHistoryIdx = null;
            this.selectedActuatorIdx = null;
            this.selectedActuatorName = "";
            this.historySummary = null;
            this.historyDayClimateData = null;
            this.historyDaySubtitle = "";
            this.actuatorDaySubtitle = "";
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

        /**
         * C12: favorite key — numeric idx as Number; scene UUID (non-numeric) as string.
         * @param {*} id
         * @returns {number|string|null}
         */
        _favoriteIdKey(id) {
            if (id == null || id === "") return null;
            if (typeof id === "string" && !/^\d+$/.test(id.trim())) return id;
            const n = Number(id);
            if (Number.isFinite(n)) return n;
            return String(id);
        },

        isActuatorFavorite(idx) {
            const key = this._favoriteIdKey(idx);
            if (key == null) return false;
            const cap = this.historyCapabilityByIdx[Number(idx)];
            if (cap && cap.kind === "water" && Array.isArray(cap.pairIdxs)) {
                return cap.pairIdxs.some(i => this.actuatorFavorites.includes(this._favoriteIdKey(i)));
            }
            return this.actuatorFavorites.includes(key);
        },

        /** C1: enter/exit Edit favorites mode (Done = idle, no row checkboxes). */
        toggleFavoritesEditMode() {
            this.favoritesEditMode = !this.favoritesEditMode;
        },

        /**
         * C1: when the last favorite is removed, clear favorites-only filter and hide its toggle.
         * Call after any mutation of actuatorFavorites.
         */
        _syncFavoritesFilterAfterChange() {
            if (this.actuatorFavorites.length === 0) {
                this.actuatorFavoritesOnly = false;
            }
        },

        toggleActuatorFavorite(idx) {
            const cap = this.historyCapabilityByIdx[Number(idx)];
            const ids = (cap && cap.kind === "water" && Array.isArray(cap.pairIdxs))
                ? cap.pairIdxs.map((i) => this._favoriteIdKey(i)).filter((x) => x != null)
                : [this._favoriteIdKey(idx)].filter((x) => x != null);
            if (!ids.length) return;
            const on = ids.some(i => this.actuatorFavorites.includes(i));
            if (on) {
                this.actuatorFavorites = this.actuatorFavorites.filter(x => !ids.includes(x));
            } else {
                this.actuatorFavorites = [...new Set([...this.actuatorFavorites, ...ids])];
            }
            localStorage.setItem("wanos_history_favorites", JSON.stringify(this.actuatorFavorites));
            this._syncFavoritesFilterAfterChange();
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

        _ensureActuatorChart(key, elId, { soft = false } = {}) {
            if (typeof echarts === "undefined") return null;
            const el = document.getElementById(elId);
            if (!el) return null;
            // C19 cause 2: Alpine may have replaced this node; do not setOption on a detached canvas
            wanosDisposeStaleChart(wanosActuatorCharts, key, el);
            if (wanosActuatorCharts[key]) {
                // C6: soft path defers resize to a single pass after draw
                if (!soft) {
                    try {
                        wanosActuatorCharts[key].resize();
                    } catch (e) { /* ignore */ }
                }
                return wanosActuatorCharts[key];
            }
            wanosActuatorCharts[key] = echarts.init(el, "dark");
            return wanosActuatorCharts[key];
        },

        _captureChartDataZoom(chart) {
            if (!chart) return null;
            try {
                const opt = chart.getOption();
                const list = opt && opt.dataZoom;
                if (!Array.isArray(list) || !list.length) return null;
                const dz = list.find((z) => z && (z.start != null || z.end != null
                    || z.startValue != null || z.endValue != null)) || list[0];
                if (!dz) return null;
                return {
                    start: dz.start != null ? Number(dz.start) : 0,
                    end: dz.end != null ? Number(dz.end) : 100,
                    startValue: dz.startValue != null ? Number(dz.startValue) : null,
                    endValue: dz.endValue != null ? Number(dz.endValue) : null,
                };
            } catch (e) {
                return null;
            }
        },

        /**
         * C16: capture day sliding window for soft refresh (absolute ms + live pin).
         * @param {Object|null} chart
         * @returns {{ startValue: number, endValue: number, span: number, live: boolean }|null}
         */
        _captureSlidingDayZoom(chart) {
            const raw = this._captureChartDataZoom(chart);
            if (!raw) return null;
            const now = Date.now();
            let startValue = raw.startValue;
            let endValue = raw.endValue;
            // Percent-only fallback against current axis extent
            if ((startValue == null || endValue == null) && chart) {
                try {
                    const opt = chart.getOption();
                    const xa = Array.isArray(opt.xAxis) ? opt.xAxis[0] : opt.xAxis;
                    const amin = xa && xa.min != null ? Number(xa.min) : null;
                    const amax = xa && xa.max != null ? Number(xa.max) : null;
                    if (amin != null && amax != null && Number.isFinite(raw.start) && Number.isFinite(raw.end)) {
                        const span = amax - amin;
                        startValue = amin + (span * raw.start) / 100;
                        endValue = amin + (span * raw.end) / 100;
                    }
                } catch (e) { /* ignore */ }
            }
            if (startValue == null || endValue == null) return null;
            if (!Number.isFinite(startValue) || !Number.isFinite(endValue) || endValue <= startValue) return null;
            const liveSlackMs = 3 * 60 * 1000;
            const live = (now - endValue) <= liveSlackMs;
            return {
                startValue,
                endValue,
                span: endValue - startValue,
                live,
            };
        },

        /** C16: retention days from day API payload (default 7). */
        _retentionDaysFromPayload(data) {
            const n = data && data.retention_days != null ? Number(data.retention_days) : NaN;
            return Number.isFinite(n) && n > 0 ? n : 7;
        },

        /**
         * C16: format from/to subtitle when day viewport is not live-pinned to now.
         * @param {number} startMs
         * @param {number} endMs
         * @param {boolean} live
         * @returns {string}
         */
        _formatDayWindowSubtitle(startMs, endMs, live) {
            if (live) return "";
            const tz = "Europe/Brussels";
            const fmt = (ms) => {
                const d = new Date(ms);
                return d.toLocaleString("en-GB", {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: tz,
                });
            };
            return `${fmt(startMs)} → ${fmt(endMs)}`;
        },

        /**
         * C16: keep historyDaySubtitle / actuatorDaySubtitle in sync with dataZoom.
         * @param {Object} chart
         * @param {"historyDaySubtitle"|"actuatorDaySubtitle"} prop
         */
        _bindDayWindowSubtitle(chart, prop) {
            if (!chart || !prop) return;
            const key = "_wanosDaySubtitleHandler";
            if (chart[key]) {
                try { chart.off("datazoom", chart[key]); } catch (e) { /* ignore */ }
            }
            const handler = () => {
                const cap = this._captureSlidingDayZoom(chart);
                if (!cap) {
                    this[prop] = "";
                    return;
                }
                this[prop] = this._formatDayWindowSubtitle(cap.startValue, cap.endValue, cap.live);
            };
            chart[key] = handler;
            chart.on("datazoom", handler);
            handler();
        },

        /**
         * C16: x-axis = full hires buffer; default viewport 24 h; zoom-out to full retention; zoom-in to ~1 h.
         * @param {Object} opt
         * @param {number} retentionDays
         * @param {{ startValue?: number, endValue?: number, span?: number, live?: boolean }|null} saved
         * @param {{ sliderBottom?: number }=} ui
         */
        _applySlidingDayTimeWindow(opt, retentionDays, saved, ui = {}) {
            if (!opt || !opt.xAxis) return;
            const defaultSpanMs = 24 * 60 * 60 * 1000;
            const minSpanMs = 60 * 60 * 1000;
            const days = Number.isFinite(retentionDays) && retentionDays > 0 ? retentionDays : 7;
            const maxSpanMs = days * 86400 * 1000;
            const end = Date.now();
            const start = end - maxSpanMs;
            opt.xAxis.min = start;
            opt.xAxis.max = end;
            opt.xAxis.scale = true;

            let viewStart = end - defaultSpanMs;
            let viewEnd = end;
            if (saved && Number.isFinite(saved.span) && saved.span > 0) {
                const span = Math.min(maxSpanMs, Math.max(minSpanMs, saved.span));
                if (saved.live) {
                    viewEnd = end;
                    viewStart = viewEnd - span;
                } else if (Number.isFinite(saved.startValue) && Number.isFinite(saved.endValue)) {
                    viewStart = saved.startValue;
                    viewEnd = saved.endValue;
                    const curSpan = viewEnd - viewStart;
                    if (curSpan > maxSpanMs) {
                        viewStart = viewEnd - maxSpanMs;
                    } else if (curSpan < minSpanMs) {
                        viewStart = viewEnd - minSpanMs;
                    }
                }
            }
            if (viewStart < start) {
                const shift = start - viewStart;
                viewStart += shift;
                viewEnd += shift;
            }
            if (viewEnd > end) {
                const shift = viewEnd - end;
                viewStart -= shift;
                viewEnd -= shift;
            }
            if (viewStart < start) viewStart = start;
            if (viewEnd > end) viewEnd = end;

            const sliderBottom = ui.sliderBottom != null ? ui.sliderBottom : 28;
            opt.dataZoom = [
                {
                    type: "inside",
                    startValue: viewStart,
                    endValue: viewEnd,
                    filterMode: "none",
                    minValueSpan: minSpanMs,
                    maxValueSpan: maxSpanMs,
                },
                {
                    type: "slider",
                    height: ui.sliderHeight != null ? ui.sliderHeight : 18,
                    bottom: sliderBottom,
                    startValue: viewStart,
                    endValue: viewEnd,
                    filterMode: "none",
                    minValueSpan: minSpanMs,
                    maxValueSpan: maxSpanMs,
                },
            ];
        },

        /**
         * C16 water day: category bars over hires_days hours; default last 24 h; zoom-out to full buffer.
         * @param {Object} opt
         * @param {number} categoryCount
         * @param {{ start?: number, end?: number, live?: boolean }|null} saved
         */
        _applyWaterDaySlidingZoom(opt, categoryCount, saved) {
            if (!opt || categoryCount <= 0) return;
            const defaultVisible = Math.min(24, categoryCount);
            const minSpan = 1;
            const maxSpan = categoryCount;
            const n = categoryCount;
            let startIdx = Math.max(0, n - defaultVisible);
            let endIdx = n - 1;
            if (saved && Number.isFinite(saved.start) && Number.isFinite(saved.end) && n > 0) {
                startIdx = Math.round((saved.start / 100) * (n - 1));
                endIdx = Math.round((saved.end / 100) * (n - 1));
                if (saved.live) {
                    endIdx = n - 1;
                    const visible = Math.max(minSpan, endIdx - startIdx + 1);
                    startIdx = Math.max(0, endIdx - visible + 1);
                }
            }
            if (endIdx - startIdx + 1 > maxSpan) startIdx = endIdx - maxSpan + 1;
            if (endIdx - startIdx + 1 < minSpan) startIdx = Math.max(0, endIdx - minSpan + 1);
            if (startIdx < 0) startIdx = 0;
            if (endIdx > n - 1) endIdx = n - 1;
            const startPct = n <= 1 ? 0 : (startIdx / (n - 1)) * 100;
            const endPct = n <= 1 ? 100 : (endIdx / (n - 1)) * 100;
            opt.dataZoom = [
                {
                    type: "inside",
                    start: startPct,
                    end: endPct,
                    filterMode: "none",
                    minValueSpan: minSpan,
                    maxValueSpan: maxSpan,
                },
                {
                    type: "slider",
                    height: 18,
                    bottom: 28,
                    start: startPct,
                    end: endPct,
                    filterMode: "none",
                    minValueSpan: minSpan,
                    maxValueSpan: maxSpan,
                },
            ];
        },

        /** Re-apply saved percent zoom onto a freshly built option (soft refresh). */
        _applySavedDataZoomToOpt(opt, saved) {
            if (!opt || !saved || !Array.isArray(opt.dataZoom)) return;
            for (const z of opt.dataZoom) {
                if (!z) continue;
                if (saved.start != null) z.start = saved.start;
                if (saved.end != null) z.end = saved.end;
            }
        },

        /**
         * C19: stable series ids so replaceMerge matches by id (not a shifting index).
         * @param {Object} opt
         * @returns {void}
         */
        _pinSoftSeriesIds(opt) {
            if (!opt || !Array.isArray(opt.series)) return;
            opt.series.forEach((s, i) => {
                if (!s) return;
                if (s.id == null) s.id = String(s.name || ("s" + i));
            });
        },

        /**
         * C19 cause 1: true when the option had drawable series but the instance has none after merge.
         * @param {Object} chart
         * @param {Object} opt
         * @returns {boolean}
         */
        _historySoftOptionDroppedSeries(chart, opt) {
            const incomingHas = (opt.series || []).some(
                (s) => s && Array.isArray(s.data) && s.data.length > 0
            );
            if (!incomingHas) return false;
            try {
                const got = chart.getOption();
                const series = (got && got.series) || [];
                return !series.some((s) => s && Array.isArray(s.data) && s.data.length > 0);
            } catch (e) {
                return false;
            }
        },

        /**
         * setOption + optional resize. Soft refresh: merge (no wipe), no animation, no resize here.
         * Hard open/switch: notMerge wipe + resize (unchanged).
         */
        _setHistoryChartOption(chart, opt, savedZoom, { soft = false, replaceYAxis = false } = {}) {
            if (!chart || !opt) return;
            if (savedZoom) this._applySavedDataZoomToOpt(opt, savedZoom);
            if (soft) {
                opt.animation = false;
                opt.animationDurationUpdate = 0;
                this._pinSoftSeriesIds(opt);
                let el = null;
                try { el = chart.getDom(); } catch (e) { el = null; }
                // Cause 2: never paint onto a detached canvas (ensure should have rebound)
                if (!el || !el.isConnected) return;
                // Cause 1: replace series + dataZoom together so a merged stale zoom cannot
                // collapse the window to empty. Saved zoom is already copied onto `opt`.
                // C12 duration charts: also replace yAxis (tick interval must not stick from prior paint).
                const replaceMerge = replaceYAxis
                    ? ["series", "dataZoom", "yAxis"]
                    : ["series", "dataZoom"];
                chart.setOption(opt, { notMerge: false, replaceMerge });
                if (this._historySoftOptionDroppedSeries(chart, opt)) {
                    chart.setOption(opt, true);
                }
            } else {
                chart.setOption(opt, true);
                chart.resize();
            }
        },

        renderActuatorCharts(dayData, monthData, yearData, { soft = false } = {}) {
            const dayOk = this._historyPayloadHasData(dayData);
            const monthOk = this._historyPayloadHasData(monthData);
            const yearOk = this._historyPayloadHasData(yearData);

            const zoomByKey = soft
                ? {
                    day: this._captureSlidingDayZoom(wanosActuatorCharts.day),
                    month: this._captureChartDataZoom(wanosActuatorCharts.month),
                    year: this._captureChartDataZoom(wanosActuatorCharts.year),
                }
                : {};
            if (!soft) {
                this.actuatorDaySubtitle = "";
            }

            if (!soft) {
                this.actuatorChartHasData.day = false;
                this.actuatorChartHasData.month = false;
                this.actuatorChartHasData.year = false;
                this._syncActuatorHasFlags();
                this._disposeActuatorCharts();
            }

            const idx = dayData?.idx ?? monthData?.idx ?? yearData?.idx ?? this.selectedActuatorIdx;
            const chartKind = this._actuatorChartKind(idx);
            this._syncActuatorChartTitles(chartKind);
            const dayRetention = this._retentionDaysFromPayload(dayData);
            const dayLevelMax = this._actuatorLevelAxisMax(idx, dayData?.series?.level);
            const monthLevelMax = this._actuatorLevelAxisMax(
                idx, monthData?.series?.level_min, monthData?.series?.level_max
            );
            const yearLevelMax = this._actuatorLevelAxisMax(
                idx, yearData?.series?.level_min, yearData?.series?.level_max
            );

            const draw = () => {
                if (soft) {
                    if (!dayOk && wanosActuatorCharts.day) {
                        try { wanosActuatorCharts.day.dispose(); } catch (e) { /* ignore */ }
                        wanosActuatorCharts.day = null;
                    }
                    if (!monthOk && wanosActuatorCharts.month) {
                        try { wanosActuatorCharts.month.dispose(); } catch (e) { /* ignore */ }
                        wanosActuatorCharts.month = null;
                    }
                    if (!yearOk && wanosActuatorCharts.year) {
                        try { wanosActuatorCharts.year.dispose(); } catch (e) { /* ignore */ }
                        wanosActuatorCharts.year = null;
                    }
                }

                const dayChart = dayOk ? this._ensureActuatorChart("day", "chart-act-day", { soft }) : null;
                const monthChart = monthOk ? this._ensureActuatorChart("month", "chart-act-month", { soft }) : null;
                const yearChart = yearOk ? this._ensureActuatorChart("year", "chart-act-year", { soft }) : null;

                this.actuatorChartHasData.day = !!(dayOk && dayChart);
                this.actuatorChartHasData.month = !!(monthOk && monthChart);
                this.actuatorChartHasData.year = !!(yearOk && yearChart);
                this._syncActuatorHasFlags();

                if (dayChart && this.actuatorChartHasData.day) {
                    if (chartKind === "hits") {
                        // C10 motion day: impulse spikes; Y blank / "hit" (no Level, no 0/100)
                        const opt = this._baseChartOption("");
                        opt.yAxis.min = 0;
                        opt.yAxis.max = dayLevelMax;
                        opt.yAxis.interval = dayLevelMax;
                        opt.yAxis.name = "";
                        opt.yAxis.axisLabel = {
                            color: "#9ca3af",
                            formatter: this._hitAxisLabelFormatter(dayLevelMax)
                        };
                        opt.legend = { show: false };
                        opt.series = [{
                            name: "hit",
                            type: "line",
                            step: "end",
                            showSymbol: true,
                            symbolSize: 6,
                            data: this._pointsToSeries(dayData?.series?.level),
                            color: "#2dd4bf",
                            itemStyle: { color: "#2dd4bf" },
                            lineStyle: { color: "#2dd4bf", width: 2 },
                            connectNulls: false
                        }];
                        this._applySlidingDayTimeWindow(opt, dayRetention, zoomByKey.day);
                        this._setHistoryChartOption(dayChart, opt, null, { soft });
                        this._bindDayWindowSubtitle(dayChart, "actuatorDaySubtitle");
                    } else if (chartKind === "binary") {
                        // C10 binary day: ON/OFF Y labels (not numeric Level)
                        const opt = this._baseChartOption("");
                        opt.yAxis.min = 0;
                        opt.yAxis.max = dayLevelMax;
                        opt.yAxis.interval = dayLevelMax;
                        opt.yAxis.name = "";
                        opt.yAxis.axisLabel = {
                            color: "#9ca3af",
                            formatter: this._binaryAxisLabelFormatter(dayLevelMax)
                        };
                        opt.legend = { show: false };
                        opt.series = [{
                            name: "State",
                            type: "line",
                            step: "end",
                            showSymbol: true,
                            symbolSize: 6,
                            data: this._pointsToSeries(dayData?.series?.level),
                            color: "#2dd4bf",
                            itemStyle: { color: "#2dd4bf" },
                            lineStyle: { color: "#2dd4bf", width: 2 },
                            connectNulls: false
                        }];
                        this._applySlidingDayTimeWindow(opt, dayRetention, zoomByKey.day);
                        this._setHistoryChartOption(dayChart, opt, null, { soft });
                        this._bindDayWindowSubtitle(dayChart, "actuatorDaySubtitle");
                    } else {
                        const opt = this._baseChartOption("Level");
                        opt.yAxis.min = 0;
                        opt.series = [{
                            name: "Level",
                            type: "line",
                            step: "end",
                            showSymbol: true,
                            symbolSize: 6,
                            data: this._pointsToSeries(dayData?.series?.level),
                            color: "#2dd4bf",
                            itemStyle: { color: "#2dd4bf" },
                            lineStyle: { color: "#2dd4bf", width: 2 },
                            connectNulls: false
                        }];
                        this._applySlidingDayTimeWindow(opt, dayRetention, zoomByKey.day);
                        this._setHistoryChartOption(dayChart, opt, null, { soft });
                        this._bindDayWindowSubtitle(dayChart, "actuatorDaySubtitle");
                        this._bindHistoryYSnap(dayChart, [{ axisIndex: 0, step: 10 }]);
                    }
                }

                if (monthChart && this.actuatorChartHasData.month) {
                    this._renderActuatorPeriodChart(monthChart, monthData, "month", monthLevelMax, {
                        soft, savedZoom: zoomByKey.month, chartKind
                    });
                }

                if (yearChart && this.actuatorChartHasData.year) {
                    this._renderActuatorPeriodChart(yearChart, yearData, "year", yearLevelMax, {
                        soft, savedZoom: zoomByKey.year, chartKind
                    });
                }
            };

            this.actuatorChartHasData.day = dayOk;
            this.actuatorChartHasData.month = monthOk;
            this.actuatorChartHasData.year = yearOk;
            this._syncActuatorHasFlags();

            if (soft) {
                // C19: always wait one Alpine tick so x-if remounts finish before ensure/setOption
                this.$nextTick(() => requestAnimationFrame(draw));
                return;
            }

            this.$nextTick(() => {
                this.$nextTick(() => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(draw);
                    });
                });
            });
        },

        async reloadActuatorCharts(opts = {}) {
            if (!this.selectedActuatorIdx) return;
            const soft = !!opts.soft;
            if (!soft) this.actuatorLoading = true;
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
                if (!soft) await this.$nextTick();
                this.renderActuatorCharts(dayData, monthData, yearData, { soft });
            } catch (e) {
                console.error("Failed to reload actuator charts", e);
            } finally {
                if (!soft) this.actuatorLoading = false;
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

        /** Calendar day in Europe/Brussels as YYYY-MM-DD (for relative day math). */
        _brusselsDateKey(d) {
            return new Intl.DateTimeFormat("en-CA", {
                timeZone: "Europe/Brussels",
                year: "numeric",
                month: "2-digit",
                day: "2-digit",
            }).format(d);
        },

        /** Whole days between two YYYY-MM-DD keys (b - a). */
        _daysBetweenDateKeys(aKey, bKey) {
            const [ay, am, ad] = aKey.split("-").map(Number);
            const [by, bm, bd] = bKey.split("-").map(Number);
            const aUtc = Date.UTC(ay, am - 1, ad);
            const bUtc = Date.UTC(by, bm - 1, bd);
            return Math.round((bUtc - aUtc) / 86400000);
        },

        /**
         * Session start display: vandaag/gisteren/eergisteren + ochtend/middag/namiddag/avond,
         * or "2 sep" / "2 sep 2025" + HH:MM for older sessions (Europe/Brussels).
         */
        formatSessionWhenSmart(ts) {
            if (!ts) return "—";
            const d = new Date(Number(ts) * 1000);
            if (Number.isNaN(d.getTime())) return "—";

            const now = new Date();
            const dKey = this._brusselsDateKey(d);
            const todayKey = this._brusselsDateKey(now);
            const daysAgo = this._daysBetweenDateKeys(dKey, todayKey);

            let dayPart;
            let recent = false;
            if (daysAgo === 0) {
                dayPart = "vandaag";
                recent = true;
            } else if (daysAgo === 1) {
                dayPart = "gisteren";
                recent = true;
            } else if (daysAgo === 2) {
                dayPart = "eergisteren";
                recent = true;
            } else {
                const dYear = parseInt(dKey.slice(0, 4), 10);
                const tYear = parseInt(todayKey.slice(0, 4), 10);
                const md = new Intl.DateTimeFormat("nl-BE", {
                    timeZone: "Europe/Brussels",
                    day: "numeric",
                    month: "short",
                }).format(d).replace(/\./g, "");
                dayPart = dYear !== tYear ? `${md} ${dYear}` : md;
            }

            let timePart;
            if (recent) {
                const hour = parseInt(
                    new Intl.DateTimeFormat("en-GB", {
                        timeZone: "Europe/Brussels",
                        hour: "numeric",
                        hour12: false,
                    }).format(d),
                    10
                );
                if (hour < 12) timePart = "ochtend";
                else if (hour < 14) timePart = "middag";
                else if (hour < 19) timePart = "namiddag";
                else timePart = "avond";
            } else {
                timePart = new Intl.DateTimeFormat("en-GB", {
                    timeZone: "Europe/Brussels",
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false,
                }).format(d);
            }
            return dayPart + ", " + timePart;
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
            const total = Math.max(0, Math.floor(Number(secs)));
            if (!Number.isFinite(total)) return "—";
            const h = Math.floor(total / 3600).toString().padStart(2, "0");
            const m = Math.floor((total % 3600) / 60).toString().padStart(2, "0");
            const s = (total % 60).toString().padStart(2, "0");
            return h + ":" + m + ":" + s;
        },

        /** Session list: single value when start/end differ insignificantly (IR temp/hum). */
        formatSessionClimateRange(start, end, unit = "°C") {
            if (start == null && end == null) return "—";
            const s = start != null ? Number(start) : null;
            const e = end != null ? Number(end) : null;
            const isTemp = unit === "°C";
            const threshold = isTemp ? 0.2 : 2;
            const decimals = isTemp ? 1 : 0;
            const suffix = isTemp ? "°C" : "%";
            if (s == null && e != null) return e.toFixed(decimals) + suffix;
            if (s != null && e == null) return s.toFixed(decimals) + suffix;
            if (s == null || e == null) return "—";
            if (Math.abs(e - s) <= threshold) return s.toFixed(decimals) + suffix;
            return s.toFixed(decimals) + " → " + e.toFixed(decimals) + suffix;
        },

        /** Session list: average real power from stored energy and runtime (display-time). */
        formatSessionAvgRealW(energyWh, runtimeSecs) {
            if (energyWh == null || runtimeSecs == null) return "—";
            const wh = Number(energyWh);
            const secs = Number(runtimeSecs);
            if (!Number.isFinite(wh) || !Number.isFinite(secs) || secs <= 0) return "—";
            const watts = (wh * 3600) / secs;
            return watts.toFixed(0) + " W";
        },

        formatSessionEnergy(energyWh, sessionType) {
            if (energyWh == null) return "—";
            const wh = Number(energyWh);
            if (!Number.isFinite(wh)) return "—";
            if (sessionType === "ir") {
                return wh.toFixed(0) + " Wh";
            }
            return (wh / 1000).toFixed(2) + " kWh";
        },

        formatAuditW(val) {
            if (val == null || !Number.isFinite(Number(val))) return "—";
            return Number(val).toFixed(0) + " W";
        },

        formatElementLastSession(kind) {
            const row = kind === "ir"
                ? (this.state.metrics.last_ir_session || null)
                : (this.state.metrics.last_sauna_session || null);
            const label = kind === "ir" ? "IR" : "Sauna";
            if (!row || row.start_timestamp == null) {
                return label + " last session: —";
            }
            const runtime = this.formatSessionRuntime(row.total_runtime_secs);
            const energy = this.formatSessionEnergy(row.energy_real_wh, kind);
            const avgW = this.formatSessionAvgRealW(row.energy_real_wh, row.total_runtime_secs);
            const when = this.formatSessionWhenSmart(row.start_timestamp);
            return label + " last session: " + energy + " · " + avgW + " · " + runtime + " · " + when;
        },

        formatElementLastLearn(kind) {
            const m = this.elementPowerMeta || {};
            if (kind === "ir") {
                const st = m.last_learn_ir_status;
                if (!st) return "IR last: —";
                const meas = m.last_learn_ir_measured_w != null
                    ? Number(m.last_learn_ir_measured_w).toFixed(0) + " W"
                    : "—";
                const when = m.last_learn_ir_at ? " @ " + this.formatUnixTime(m.last_learn_ir_at) : "";
                return "IR last: " + st + " · meas " + meas + when;
            }
            const st = m.last_learn_sauna_status;
            if (!st) return "Sauna last: —";
            const detail = m.last_learn_sauna_detail || "—";
            const when = m.last_learn_sauna_at ? " @ " + this.formatUnixTime(m.last_learn_sauna_at) : "";
            return "Sauna last: " + st + " · " + detail + when;
        },

        formatLiveEstimatedPhaseW() {
            const pwm = (this.state && this.state.sauna && this.state.sauna.phases_pwm) || {};
            const m = this.elementPowerMeta || {};
            const u = (Number(m.w_u) || Number(this.state.metrics.extracted_p_u) || 0) * (Number(pwm.U) || 0) / 100;
            const v = (Number(m.w_v) || Number(this.state.metrics.extracted_p_v) || 0) * (Number(pwm.V) || 0) / 100;
            const w = (Number(m.w_w) || Number(this.state.metrics.extracted_p_w) || 0) * (Number(pwm.W) || 0) / 100;
            return u.toFixed(0) + " / " + v.toFixed(0) + " / " + w.toFixed(0) + " W";
        },

        formatWiscLiveEnergy() {
            const wh = Number(this.state.metrics.running_energy_real_wh) || 0;
            if (this.state.ir && this.state.ir.active && !(this.state.sauna && this.state.sauna.active)) {
                return wh.toFixed(0) + " Wh";
            }
            return (wh / 1000).toFixed(3) + " kWh";
        },

        formatAdminLiveEnergy() {
            const realWh = Number(this.state.metrics.running_energy_real_wh) || 0;
            const calcWh = Number(this.state.metrics.running_energy_calc_wh) || 0;
            const irOnly = this.state.ir && this.state.ir.active
                && !(this.state.sauna && this.state.sauna.active);
            if (irOnly) {
                return realWh.toFixed(0) + " / " + calcWh.toFixed(0) + " Wh";
            }
            return (realWh / 1000).toFixed(3) + " / " + (calcWh / 1000).toFixed(3) + " kWh";
        },

        /** Admin Site health: Rth as 0.00 °C/kW (stored as °C/W; display x1000). */
        formatRthInsulation() {
            const raw = this.state && this.state.metrics
                ? this.state.metrics.r_th_insulation_coefficient
                : null;
            if (raw === null || raw === undefined) return "N/A";
            const n = Number(raw);
            if (!Number.isFinite(n)) return "N/A";
            return (n * 1000).toFixed(2) + " °C/kW";
        },

        formatWiscLastSessionOneLiner(kind) {
            const row = kind === "ir"
                ? (this.state.metrics.last_ir_session || null)
                : (this.state.metrics.last_sauna_session || null);
            if (!row) return "";
            const label = kind === "ir" ? "IR" : "Sauna";
            const when = row.start_timestamp != null
                ? this.formatSessionWhenSmart(row.start_timestamp)
                : "—";
            return label + ": " + when;
        },

        /** Admin GPIO output arm status (why toggle may be blocked). */
        gpioOutputArmStatus() {
            const h = this.state.hardware || {};
            if (!h.gpio_output_connected) return "OFFLINE";
            if (!h.gpio_input_enabled) return "NEED INPUTS";
            if (!h.sht11_enabled) return "NEED SHT11";
            if (this.state.sensors.sauna_calc_temp == null) return "WAIT TEMP";
            if (!h.gpio_output_enabled) return "READY";
            return "ARMED";
        },

        gpioOutputArmStatusClass() {
            const s = this.gpioOutputArmStatus();
            if (s === "OFFLINE") return "text-gray-500";
            if (s === "ARMED") return "text-error animate-pulse";
            if (s === "READY") return "text-success";
            return "text-warning";
        },

        sessionAuditLines(row, sessionType) {
            if (!row) return [];
            if (sessionType === "ir") {
                return [
                    { label: "IR", baseline: row.audit_baseline_w_ir, measured: row.audit_measured_w_ir, newVal: row.audit_new_w_ir },
                ];
            }
            return [
                { label: "U", baseline: row.audit_baseline_w_u, measured: row.audit_measured_w_u, newVal: row.audit_new_w_u },
                { label: "V", baseline: row.audit_baseline_w_v, measured: row.audit_measured_w_v, newVal: row.audit_new_w_v },
                { label: "W", baseline: row.audit_baseline_w_w, measured: row.audit_measured_w_w, newVal: row.audit_new_w_w },
            ];
        },

        _sessionAuditAnchorStyle(anchorEl) {
            if (!anchorEl || typeof anchorEl.getBoundingClientRect !== "function") {
                return "top: 1rem; left: 1rem;";
            }
            const rect = anchorEl.getBoundingClientRect();
            const tipW = 224;
            const tipH = 120;
            let left = rect.right - tipW;
            let top = rect.bottom + 6;
            if (left < 8) left = 8;
            if (left + tipW > window.innerWidth - 8) left = window.innerWidth - tipW - 8;
            if (top + tipH > window.innerHeight - 8) top = Math.max(8, rect.top - tipH - 6);
            return `top: ${Math.round(top)}px; left: ${Math.round(left)}px;`;
        },

        openSessionAuditHover(event, row) {
            if (!row || this.sessionAuditPopoverPinned) return;
            // Prefer the row's i button as anchor when hovering the line on PC.
            const btn = event && event.currentTarget
                ? event.currentTarget.querySelector("button")
                : null;
            this.sessionAuditPopoverId = row.session_id;
            this.sessionAuditPopoverRow = row;
            this.sessionAuditPopoverStyle = this._sessionAuditAnchorStyle(btn || (event && event.currentTarget));
        },

        closeSessionAuditHover() {
            if (this.sessionAuditPopoverPinned) return;
            this.sessionAuditPopoverId = null;
            this.sessionAuditPopoverRow = null;
            this.sessionAuditPopoverStyle = "";
        },

        toggleSessionAuditPopover(event, row) {
            if (!row) return;
            const id = row.session_id;
            if (this.sessionAuditPopoverPinned && this.sessionAuditPopoverId === id) {
                this.dismissSessionAuditPopover();
                return;
            }
            const anchor = event && event.currentTarget ? event.currentTarget : null;
            this.sessionAuditPopoverId = id;
            this.sessionAuditPopoverRow = row;
            this.sessionAuditPopoverStyle = this._sessionAuditAnchorStyle(anchor);
            // Defer pin so the opening click is not treated as click.outside.
            this.$nextTick(() => {
                this.sessionAuditPopoverPinned = true;
            });
        },

        dismissSessionAuditPopover() {
            this.sessionAuditPopoverPinned = false;
            this.sessionAuditPopoverId = null;
            this.sessionAuditPopoverRow = null;
            this.sessionAuditPopoverStyle = "";
        },

        async loadElementPower() {
            try {
                const res = await fetch("/api/admin/analytics/element-power", {
                    headers: this.getAuthHeaders(),
                });
                if (!res.ok) return;
                const data = await res.json();
                this.elementPowerMeta = {
                    w_u: Number(data.w_u) || 3500,
                    w_v: Number(data.w_v) || 3500,
                    w_w: Number(data.w_w) || 2000,
                    w_ir: Number(data.w_ir) || 525,
                    updated_at: data.updated_at != null ? Number(data.updated_at) : null,
                    learn_count_sauna: Number(data.learn_count_sauna) || 0,
                    learn_count_ir: Number(data.learn_count_ir) || 0,
                    last_learn_sauna_status: data.last_learn_sauna_status || null,
                    last_learn_sauna_detail: data.last_learn_sauna_detail || null,
                    last_learn_sauna_at: data.last_learn_sauna_at != null
                        ? Number(data.last_learn_sauna_at) : null,
                    last_learn_ir_status: data.last_learn_ir_status || null,
                    last_learn_ir_measured_w: data.last_learn_ir_measured_w != null
                        ? Number(data.last_learn_ir_measured_w) : null,
                    last_learn_ir_at: data.last_learn_ir_at != null
                        ? Number(data.last_learn_ir_at) : null,
                    session_count_sauna: Number(data.session_count_sauna) || 0,
                    session_count_ir: Number(data.session_count_ir) || 0,
                };
            } catch (e) {
                console.error("Failed to load element power", e);
            }
        },

        async deleteSessionRow(sessionId) {
            const label = this.sessionHistoryType === "ir" ? "IR" : "Sauna";
            if (!window.confirm(`Delete ${label} session #${sessionId}? This cannot be undone.`)) {
                return;
            }
            try {
                const res = await fetch(
                    `/api/history/sessions/${this.sessionHistoryType}/${sessionId}`,
                    { method: "DELETE", headers: this.getAuthHeaders() }
                );
                const data = await res.json();
                if (!res.ok) {
                    this.showToast(data.error || "Delete failed");
                    return;
                }
                await this.loadSessionHistory();
            } catch (e) {
                console.error("Failed to delete session", e);
                this.showToast("Delete failed");
            }
        },

        _ensureHistoryChart(key, elId, { soft = false } = {}) {
            if (typeof echarts === "undefined") return null;
            const el = document.getElementById(elId);
            if (!el) return null;
            // C19 cause 2: Alpine may have replaced this node; do not setOption on a detached canvas
            wanosDisposeStaleChart(wanosHistoryCharts, key, el);
            if (wanosHistoryCharts[key]) {
                // C6: soft path defers resize to a single pass after draw
                if (!soft) {
                    try { wanosHistoryCharts[key].resize(); } catch (e) { /* ignore */ }
                }
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

        /**
         * Gap break threshold (ms): 3 × expected sample cadence from day API.
         * Prefer climate_sample_interval_secs (OWM poll vs SHT11 max-interval);
         * fall back to climate_max_interval_secs (default 300 s → 15 min break).
         * Intent: keep the line across 1–2 missed samples; break only when more
         * than two expected samples are missing (Δt > 3× period).
         * @param {Object|null|undefined} dayData
         * @returns {number}
         */
        _climateSampleGapBreakMs(dayData) {
            let secs = null;
            if (dayData && dayData.climate_sample_interval_secs != null) {
                secs = Number(dayData.climate_sample_interval_secs);
            } else if (dayData && dayData.climate_max_interval_secs != null) {
                secs = Number(dayData.climate_max_interval_secs);
            }
            const base = Number.isFinite(secs) && secs > 0 ? secs : 300;
            return base * 3 * 1000;
        },

        /**
         * Insert a null point between consecutive valued samples when Δt > gapBreakMs.
         * ECharts connectNulls:false then leaves a visible gap (no implied readings).
         * @param {Array} series  rows [t, v, ...extra]
         * @param {number} gapBreakMs
         * @returns {Array}
         */
        _breakLineOnSampleGap(series, gapBreakMs) {
            if (!Array.isArray(series) || !series.length) return series || [];
            const maxGap = Number(gapBreakMs);
            if (!Number.isFinite(maxGap) || maxGap <= 0) return series;
            const out = [];
            let prevValuedT = null;
            for (const row of series) {
                if (!row || row[0] == null) continue;
                const t = Number(row[0]);
                if (!Number.isFinite(t)) continue;
                const v = row[1];
                const hasVal = v != null && Number.isFinite(Number(v));
                if (hasVal && prevValuedT != null && (t - prevValuedT) > maxGap) {
                    // Null sentinel just after last valued sample — breaks the polyline
                    const nullRow = row.slice();
                    nullRow[0] = prevValuedT + 1;
                    for (let i = 1; i < nullRow.length; i++) nullRow[i] = null;
                    out.push(nullRow);
                }
                out.push(row);
                if (hasVal) prevValuedT = t;
            }
            return out;
        },

        /**
         * Drop max-interval heartbeats that repeat the same value (climate deadband hold).
         * Keeps change points and extends the last plateau timestamp so ECharts smooth
         * curves between real changes instead of stair-stepping on duplicate samples.
         * @param {Array} series  rows [t, v, ...extra]
         * @param {number=} epsilon
         * @returns {Array}
         */
        _thinClimatePlateauSamples(series, epsilon = 0.001) {
            if (!Array.isArray(series) || !series.length) return series || [];
            const out = [];
            for (let i = 0; i < series.length; i++) {
                const row = series[i];
                if (!row || row[0] == null) continue;
                const v = row[1];
                const hasVal = v != null && Number.isFinite(Number(v));
                if (!hasVal) {
                    out.push(row);
                    continue;
                }
                const n = Number(v);
                const isLast = i === series.length - 1;
                if (!out.length) {
                    out.push(row.slice());
                    continue;
                }
                const last = out[out.length - 1];
                const lastV = last[1];
                const lastN = lastV != null && Number.isFinite(Number(lastV)) ? Number(lastV) : null;
                const same = lastN != null && Math.abs(lastN - n) <= epsilon;
                if (!same) {
                    out.push(row.slice());
                } else if (isLast) {
                    last[0] = row[0];
                }
            }
            return out.length ? out : (series || []);
        },

        /** Day climate line: gap-break then thin duplicate hold samples. */
        _climateDayLineRows(rows, gapMs) {
            return this._thinClimatePlateauSamples(this._breakLineOnSampleGap(rows, gapMs));
        },

        /** Day climate line from API points. */
        _climateDayLineData(points, gapMs) {
            return this._climateDayLineRows(this._pointsToSeries(points), gapMs);
        },

        /** Fullscreen day line — gap-break; optional plateau thin per climateFsSmooth. */
        _climateFsLineRows(rows, gapMs) {
            const base = this._breakLineOnSampleGap(rows, gapMs);
            return this.climateFsSmooth ? this._thinClimatePlateauSamples(base) : base;
        },

        /** Fullscreen day line from API points. */
        _climateFsLineData(points, gapMs) {
            return this._climateFsLineRows(this._pointsToSeries(points), gapMs);
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
         * Force the titled window (month / year). Sparse event series otherwise
         * collapse the time axis; reused chart instances also keep a tiny dataZoom from before.
         * Use percent zoom (0–100) against explicit axis min/max — more reliable than startValue
         * when series only cover a thin slice of the window.
         * C16 day charts use `_applySlidingDayTimeWindow` instead.
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
                // C7: line color swatch only (no legend marker dots)
                legend: {
                    bottom: 0,
                    icon: "rect",
                    itemWidth: 12,
                    itemHeight: 3,
                    textStyle: { color: "#9ca3af" }
                },
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

        // ---------------------------------------------------------------------
        // C5 — dew point (Sonntag Magnus) + Y-axis snap from dataZoom window
        // ---------------------------------------------------------------------

        /**
         * Sonntag Magnus dew point (°C). T in °C, RH 0–100.
         * Returns null when RH is missing/invalid (caller hides dew series).
         * Value rounded to 1 decimal (chart / tooltip display).
         */
        _dewPointC(tempC, rhPct) {
            const T = Number(tempC);
            const RH = Number(rhPct);
            if (!Number.isFinite(T) || !Number.isFinite(RH) || RH <= 0 || RH > 100) return null;
            const b = 17.62;
            const c = 243.12;
            const gamma = Math.log(RH / 100) + (b * T) / (c + T);
            if (!Number.isFinite(gamma) || Math.abs(b - gamma) < 1e-12) return null;
            const tdp = (c * gamma) / (b - gamma);
            if (!Number.isFinite(tdp)) return null;
            return Math.round(tdp * 10) / 10;
        },

        /** Build [t_ms, dew°C] series by pairing temp/hum samples on the same timestamp. */
        _dewSeriesFromTempHum(tempPoints, humPoints) {
            const humByT = new Map();
            for (const p of humPoints || []) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                humByT.set(t, Number(p.v));
            }
            const out = [];
            for (const p of tempPoints || []) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                const dp = this._dewPointC(p.v, humByT.get(t));
                if (dp == null) continue;
                out.push([t, dp]);
            }
            return out;
        },

        // ---------------------------------------------------------------------
        // C24 — temp/hum day fullscreen overlay (AH / CI / CSV)
        // ---------------------------------------------------------------------

        /**
         * Absolute humidity g/m³ from T (°C) and Td (°C). Null when inputs invalid.
         * @param {number} tempC
         * @param {number} dewC
         * @returns {number|null}
         */
        _absoluteHumidityGm3(tempC, dewC) {
            const T = Number(tempC);
            const Td = Number(dewC);
            if (!Number.isFinite(T) || !Number.isFinite(Td)) return null;
            const e = 6.112 * Math.exp((17.67 * Td) / (Td + 243.5));
            if (!Number.isFinite(e)) return null;
            const ah = (216.7 * e) / (T + 273.15);
            if (!Number.isFinite(ah)) return null;
            return Math.round(ah * 100) / 100;
        },

        /**
         * Feels-like humidity / comfort index % (C24 lock 2026-08-17).
         * @param {number} tempC
         * @param {number} dewC
         * @returns {number|null}
         */
        _apparentHumidityPct(tempC, dewC) {
            const T = Number(tempC);
            const Td = Number(dewC);
            if (!Number.isFinite(T) || !Number.isFinite(Td)) return null;
            let ciBase = 4.5 * Td - 30;
            if (ciBase < 0) ciBase = 0;
            if (ciBase > 100) ciBase = 100;
            const tc = 0.8 * (T - 20);
            let ci = ciBase + tc;
            if (ci < 0) ci = 0;
            if (ci > 100) ci = 100;
            return Math.round(ci * 10) / 10;
        },

        /** Comfort category label from dew point (°C) — English (UI / tooltip). */
        _comfortCategoryFromTd(dewC) {
            const Td = Number(dewC);
            if (!Number.isFinite(Td)) return "";
            if (Td < 10) return "Dry";
            if (Td < 15) return "Comfortable";
            if (Td < 18) return "Moderately humid";
            if (Td < 21) return "Humid";
            if (Td < 24) return "Very humid";
            return "Tropically humid";
        },

        /** CI line color from Td band (C24 comfort table). */
        _comfortColorFromTd(dewC) {
            const Td = Number(dewC);
            if (!Number.isFinite(Td)) return "#22c55e";
            if (Td < 10) return "#7dd3fc";
            if (Td < 15) return "#22c55e";
            if (Td < 18) return "#a3e635";
            if (Td < 21) return "#fb923c";
            if (Td < 24) return "#ef4444";
            return "#991b1b";
        },

        /** True when day climate chart has humidity (fullscreen button gate). */
        get climateFullscreenAvailable() {
            if (this.selectedSensorKind !== "climate" || !this.historyHasDay) return false;
            const d = this.historyDayClimateData;
            if (!d) return false;
            return d.has_humidity !== false && this._seriesDrawable(d.series && d.series.hum);
        },

        openClimateFullscreen() {
            if (!this.climateFullscreenAvailable) return;
            this.climateFsOpen = true;
            this._bindClimateFsResize();
            // Compare dropdown uses historySensors, not the filtered Explorer list.
            if (!(this.historySensors || []).some((s) => s.kind === "climate")) {
                void this.loadHistorySensors();
            }
            this.$nextTick(() => {
                requestAnimationFrame(() => this._renderClimateFullscreenChart({ soft: false }));
            });
        },

        closeClimateFullscreen() {
            this.climateFsOpen = false;
            this.climateFsCiHelpOpen = false;
            this.climateFsCompareIdx = "";
            this.climateFsPeerDayData = null;
            this.climateFsPeerName = "";
            this._unbindClimateFsResize();
            if (wanosClimateFsChart) {
                try { wanosClimateFsChart.dispose(); } catch (e) { /* ignore */ }
                wanosClimateFsChart = null;
            }
        },

        /**
         * C24/C25: series checkbox change — keep at least one series on (primary + peer rows).
         * @param {string} key
         * @param {"primary"|"peer"=} row
         */
        onClimateFsToggle(key, row) {
            const which = row === "peer" ? "peer" : "primary";
            const show = which === "peer" ? this.climateFsPeerShow : this.climateFsShow;
            if (!show) return;
            const keys = which === "peer"
                ? ["temp", "hum", "dew"]
                : ["temp", "hum", "dew", "ah", "ci", "dewLikelihood"];
            const active = keys.filter((k) => !!show[k]);
            if (active.length === 0 && key && keys.includes(key)) {
                show[key] = true;
                return;
            }
            if (!this.climateFsOpen) return;
            this.$nextTick(() => this._renderClimateFullscreenChart({ soft: true }));
        },

        /** Fullscreen overlay — smooth lines toggle (plateau thin + ECharts curve). */
        onClimateFsSmoothChange() {
            if (!this.climateFsOpen) return;
            this.$nextTick(() => this._renderClimateFullscreenChart({ soft: true }));
        },

        /**
         * C25: Compare with dropdown — (none) clears peer; peer select unchecks specials.
         * @param {string|number|Event=} rawOrEvent — option value, or change event from select
         */
        async onClimateFsCompareChange(rawOrEvent) {
            let raw = this.climateFsCompareIdx;
            if (rawOrEvent != null && typeof rawOrEvent === "object" && rawOrEvent.target) {
                raw = rawOrEvent.target.value;
            } else if (rawOrEvent !== undefined && rawOrEvent !== null) {
                raw = rawOrEvent;
            }
            if (raw === "" || raw == null) {
                this.climateFsPeerDayData = null;
                this.climateFsPeerName = "";
                if (this.climateFsOpen) {
                    this.$nextTick(() => this._renderClimateFullscreenChart({ soft: true }));
                }
                return;
            }
            const idx = Number(raw);
            if (!Number.isFinite(idx)) return;
            const peerMeta = this._climateComparePeerCatalog().find((p) => Number(p.idx) === idx);
            this.climateFsPeerName = peerMeta ? peerMeta.name : `IDX ${idx}`;
            // Uncheck specials on primary (leave as-is if operator re-checks later)
            if (this.climateFsShow) {
                this.climateFsShow.ah = false;
                this.climateFsShow.ci = false;
                this.climateFsShow.dewLikelihood = false;
            }
            const hasHum = peerMeta ? peerMeta.has_humidity !== false : true;
            this.climateFsPeerShow = {
                temp: true,
                hum: !!hasHum,
                dew: !!hasHum,
            };
            try {
                const headers = this.getAuthHeaders();
                const res = await fetch(`/api/history/${idx}?range=day`, { headers });
                if (res.status === 401 || res.status === 403) {
                    window.location.href = "/deviceexplorer.html";
                    return;
                }
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                this.climateFsPeerDayData = await res.json();
            } catch (e) {
                console.error("[C25] compare peer history failed", e);
                this.climateFsPeerDayData = null;
            }
            if (this.climateFsOpen) {
                this.$nextTick(() => this._renderClimateFullscreenChart({ soft: true }));
            }
        },

        /**
         * Build aligned T/RH/Td/AH/CI/dewLikelihood rows for overlay + CSV.
         * @param {Object} dayData
         * @returns {Array<{ t: number, temp: number|null, hum: number|null, dew: number|null, ah: number|null, ci: number|null, dewLikelihood: number|null }>}
         */
        _climateDayDerivedRows(dayData) {
            const tempPts = (dayData && dayData.series && dayData.series.temp) || [];
            const humPts = (dayData && dayData.series && dayData.series.hum) || [];
            const dewLikPts = (dayData && dayData.series && dayData.series.dew_likelihood) || [];
            const humByT = new Map();
            for (const p of humPts) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                humByT.set(t, Number(p.v));
            }
            const dewLikByT = new Map();
            for (const p of dewLikPts) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                dewLikByT.set(t, Number(p.v));
            }
            const rows = [];
            const seen = new Set();
            for (const p of tempPts) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null) continue;
                seen.add(t);
                const temp = p.v == null ? null : Number(p.v);
                const hum = humByT.has(t) ? humByT.get(t) : null;
                let dew = null;
                let ah = null;
                let ci = null;
                if (temp != null && Number.isFinite(temp) && hum != null) {
                    dew = this._dewPointC(temp, hum);
                    if (dew != null) {
                        ah = this._absoluteHumidityGm3(temp, dew);
                        ci = this._apparentHumidityPct(temp, dew);
                    }
                }
                const dewLikelihood = dewLikByT.has(t) ? dewLikByT.get(t) : null;
                rows.push({
                    t,
                    temp: Number.isFinite(temp) ? temp : null,
                    hum,
                    dew,
                    ah,
                    ci,
                    dewLikelihood: Number.isFinite(dewLikelihood) ? dewLikelihood : null,
                });
            }
            // Humidity-only timestamps (rare): still plot RH
            for (const p of humPts) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                if (seen.has(t)) continue;
                seen.add(t);
                rows.push({
                    t,
                    temp: null,
                    hum: Number(p.v),
                    dew: null,
                    ah: null,
                    ci: null,
                    dewLikelihood: dewLikByT.has(t) ? dewLikByT.get(t) : null,
                });
            }
            // Dew-likelihood-only samples (every OWM poll even when T/RH skipped)
            for (const p of dewLikPts) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                if (seen.has(t)) continue;
                rows.push({
                    t,
                    temp: null,
                    hum: null,
                    dew: null,
                    ah: null,
                    ci: null,
                    dewLikelihood: Number(p.v),
                });
            }
            rows.sort((a, b) => a.t - b.t);
            return rows;
        },
        _ensureClimateFsChart() {
            if (typeof echarts === "undefined") return null;
            const el = document.getElementById("chart-climate-fs");
            if (!el) return null;
            if (wanosClimateFsChart) {
                try {
                    if (wanosClimateFsChart.getDom() === el && !wanosClimateFsChart.isDisposed()) {
                        return wanosClimateFsChart;
                    }
                    wanosClimateFsChart.dispose();
                } catch (e) { /* ignore */ }
                wanosClimateFsChart = null;
            }
            wanosClimateFsChart = echarts.init(el, "dark");
            return wanosClimateFsChart;
        },

        /**
         * C24 overlay chart: five optional series, three y-axes, inherit day pan.
         * @param {{ soft?: boolean }=} opts
         */
        _renderClimateFullscreenChart(opts = {}) {
            const soft = !!opts.soft;
            const dayData = this.historyDayClimateData;
            const chart = this._ensureClimateFsChart();
            if (!chart || !dayData) return;

            const show = this.climateFsShow || {};
            const rows = this._climateDayDerivedRows(dayData);
            const tempPts = dayData.series && dayData.series.temp;
            const humPts = dayData.series && dayData.series.hum;
            const gapMs = this._climateSampleGapBreakMs(dayData);
            const lineSmooth = !!this.climateFsSmooth;

            const series = [];
            if (show.temp) {
                const frostSplit = this._tempSeriesWithFrost(tempPts, humPts);
                const warmData = this._climateFsLineRows(frostSplit.warm, gapMs);
                const frostData = this._climateFsLineRows(frostSplit.frost, gapMs);
                const hasFrost = (frostData || []).some((row) => row && row[1] != null);
                series.push({
                    id: "fs-temp-warm",
                    name: "Temperature",
                    type: "line",
                    smooth: lineSmooth,
                    showSymbol: false,
                    yAxisIndex: 0,
                    data: warmData,
                    lineStyle: { color: "#eab308", width: 2 },
                    itemStyle: { color: "#eab308" },
                    connectNulls: false,
                });
                if (hasFrost) {
                    series.push({
                        id: "fs-temp-frost",
                        name: "Temperature",
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: frostData,
                        lineStyle: { color: "#ef4444", width: 4 },
                        itemStyle: { color: "#ef4444" },
                        connectNulls: false,
                    });
                }
            }
            if (show.hum) {
                const humColor = this._climateFsSeriesColor("hum");
                series.push({
                    id: "fs-hum",
                    name: "Humidity",
                    type: "line",
                    smooth: lineSmooth,
                    showSymbol: false,
                    yAxisIndex: 1,
                    data: this._climateFsLineData(humPts, gapMs),
                    lineStyle: { color: humColor, width: 2 },
                    itemStyle: { color: humColor },
                    connectNulls: false,
                });
            }
            if (show.dew) {
                const dew = this._climateFsLineRows(
                    this._dewSeriesFromTempHum(tempPts, humPts), gapMs
                );
                if (dew.length) {
                    const dewColor = this._climateFsSeriesColor("dew");
                    series.push({
                        id: "fs-dew",
                        name: "Dew point",
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: dew,
                        lineStyle: { color: dewColor, width: 1.5, type: "dashed" },
                        itemStyle: { color: dewColor },
                        connectNulls: false,
                    });
                }
            }
            if (show.ah) {
                const ahColor = this._climateFsSeriesColor("ah");
                // Omit unpaired / missing AH (same as dew / Feels-like) — do not insert nulls
                // that only fragment this series while T/RH still plot.
                const ahData = this._climateFsLineRows(
                    rows.filter((r) => r.ah != null).map((r) => [r.t, r.ah]),
                    gapMs
                );
                series.push({
                    id: "fs-ah",
                    name: "Absolute humidity",
                    type: "line",
                    smooth: lineSmooth,
                    showSymbol: false,
                    yAxisIndex: 2,
                    data: ahData,
                    lineStyle: { color: ahColor, width: 2 },
                    itemStyle: { color: ahColor },
                    connectNulls: false,
                });
            }
            if (show.ci) {
                const ciColor = this._climateFsSeriesColor("ci");
                const ciName = this.climateFsCiSeriesName;
                const ciData = this._climateFsLineRows(
                    rows
                        .filter((r) => r.ci != null && r.dew != null)
                        .map((r) => [r.t, r.ci, r.dew]),
                    gapMs
                );
                series.push({
                    id: "fs-ci",
                    name: ciName,
                    type: "line",
                    smooth: lineSmooth,
                    showSymbol: false,
                    yAxisIndex: 1,
                    data: ciData,
                    lineStyle: { color: ciColor, width: 2 },
                    itemStyle: { color: ciColor },
                    connectNulls: false,
                });
            }
            // C25: Dew likelihood % (OWM outside only — series present on day payload)
            if (show.dewLikelihood && this.climateFsHasDewLikelihood) {
                const dlColor = this._climateFsSeriesColor("dewLikelihood");
                const dlData = this._climateFsLineRows(
                    rows
                        .filter((r) => r.dewLikelihood != null)
                        .map((r) => [r.t, r.dewLikelihood]),
                    gapMs
                );
                series.push({
                    id: "fs-dew-likelihood",
                    name: "Dew likelihood %",
                    type: "line",
                    smooth: lineSmooth,
                    showSymbol: false,
                    yAxisIndex: 1,
                    data: dlData,
                    lineStyle: { color: dlColor, width: 2 },
                    itemStyle: { color: dlColor },
                    connectNulls: false,
                });
            }

            // C25: peer climate series (synced window)
            const peer = this.climateFsPeerDayData;
            const peerShow = this.climateFsPeerShow || {};
            const peerLabel = this.climateFsPeerName || "Peer";
            if (peer && peer.series) {
                const pTemp = peer.series.temp;
                const pHum = peer.series.hum;
                const pGap = this._climateSampleGapBreakMs(peer);
                if (peerShow.temp && this._seriesDrawable(pTemp)) {
                    const c = this._climateFsSeriesColor("peerTemp");
                    series.push({
                        id: "fs-peer-temp",
                        name: `${peerLabel} Temperature`,
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._climateFsLineData(pTemp, pGap),
                        lineStyle: { color: c, width: 2, type: "dashed" },
                        itemStyle: { color: c },
                        connectNulls: false,
                    });
                }
                if (peerShow.hum && this._seriesDrawable(pHum)) {
                    const c = this._climateFsSeriesColor("peerHum");
                    series.push({
                        id: "fs-peer-hum",
                        name: `${peerLabel} Humidity`,
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 1,
                        data: this._climateFsLineData(pHum, pGap),
                        lineStyle: { color: c, width: 2, type: "dashed" },
                        itemStyle: { color: c },
                        connectNulls: false,
                    });
                }
                if (peerShow.dew && this._seriesDrawable(pTemp) && this._seriesDrawable(pHum)) {
                    const dew = this._climateFsLineRows(
                        this._dewSeriesFromTempHum(pTemp, pHum), pGap
                    );
                    if (dew.length) {
                        const c = this._climateFsSeriesColor("peerDew");
                        series.push({
                            id: "fs-peer-dew",
                            name: `${peerLabel} Dew point`,
                            type: "line",
                            smooth: lineSmooth,
                            showSymbol: false,
                            yAxisIndex: 0,
                            data: dew,
                            lineStyle: { color: c, width: 1.5, type: "dashed" },
                            itemStyle: { color: c },
                            connectNulls: false,
                        });
                    }
                }
            }

            const showLeft = !!(show.temp || show.dew
                || (peer && peerShow.temp) || (peer && peerShow.dew));
            const showRight = !!(show.hum || show.ci || show.dewLikelihood
                || (peer && peerShow.hum));
            const showAh = !!show.ah;
            const compact = this._climateFsIsCompactWidth();
            const shortLand = this._climateFsIsShortLandscape();
            const labelFs = compact || shortLand ? 9 : 11;
            // Units live on legend checkboxes; hide axis name titles on narrow phones to reclaim width
            const showAxisNames = !compact;
            const rightAxes = (showRight ? 1 : 0) + (showAh ? 1 : 0);
            const leftGrid = compact ? (showLeft ? 32 : 12) : (showLeft ? 48 : 24);
            const rightPerAxis = compact ? 28 : 40;
            const rightGrid = rightAxes > 0 ? rightAxes * rightPerAxis + (compact ? 4 : 8) : (compact ? 12 : 24);
            const bottomGrid = shortLand ? 48 : (compact ? 56 : 72);
            const topGrid = shortLand ? 8 : 16;
            const ciName = this.climateFsCiSeriesName;

            const opt = {
                backgroundColor: "transparent",
                animation: soft ? false : true,
                legend: { show: false },
                tooltip: {
                    trigger: "axis",
                    formatter: (params) => {
                        if (!Array.isArray(params) || !params.length) return "";
                        const t = params[0].axisValue;
                        const head = new Date(t).toLocaleString("en-GB", {
                            timeZone: "Europe/Brussels",
                        });
                        const lines = [head];
                        for (const p of params) {
                            if (p == null || p.data == null) continue;
                            const val = Array.isArray(p.data) ? p.data[1] : p.value;
                            if (val == null || !Number.isFinite(Number(val))) continue;
                            if (p.seriesName === ciName && Array.isArray(p.data) && p.data[2] != null) {
                                const cat = this._comfortCategoryFromTd(p.data[2]);
                                const pct = Math.round(Number(val));
                                lines.push(`${p.marker}${p.seriesName}: ${cat} — ${pct}%`);
                            } else {
                                const unit = p.seriesName === "Absolute humidity" ? " g/m³"
                                    : (p.seriesName === "Humidity"
                                        || p.seriesName === ciName
                                        || p.seriesName === "Dew likelihood %"
                                        || String(p.seriesName || "").endsWith(" Humidity")) ? " %"
                                        : " °C";
                                const n = Number(val);
                                const shown = (p.seriesName === ciName || p.seriesName === "Dew likelihood %")
                                    ? String(Math.round(n))
                                    : String(n);
                                lines.push(`${p.marker}${p.seriesName}: ${shown}${unit}`);
                            }
                        }
                        return lines.join("<br/>");
                    },
                },
                grid: { left: leftGrid, right: rightGrid, top: topGrid, bottom: bottomGrid },
                xAxis: {
                    type: "time",
                    axisLabel: { color: "#9ca3af", hideOverlap: true, fontSize: labelFs },
                    splitLine: { show: false },
                },
                yAxis: [
                    {
                        type: "value",
                        name: showAxisNames && showLeft ? "°C" : "",
                        show: showLeft,
                        nameTextStyle: { color: "#eab308", fontSize: labelFs },
                        axisLabel: { color: "#eab308", fontSize: labelFs, margin: compact ? 4 : 8 },
                        splitLine: { lineStyle: { color: "#374151" } },
                    },
                    {
                        type: "value",
                        name: showAxisNames && showRight ? "%" : "",
                        show: showRight,
                        position: "right",
                        offset: 0,
                        nameTextStyle: { color: "#9ca3af", fontSize: labelFs },
                        axisLabel: { color: "#9ca3af", fontSize: labelFs, margin: compact ? 4 : 8 },
                        splitLine: { show: false },
                    },
                    {
                        type: "value",
                        name: showAxisNames && showAh ? "g/m³" : "",
                        show: showAh,
                        position: "right",
                        offset: showRight ? (compact ? 28 : 44) : 0,
                        nameTextStyle: { color: this._climateFsSeriesColor("ah"), fontSize: labelFs },
                        axisLabel: {
                            color: this._climateFsSeriesColor("ah"),
                            fontSize: labelFs,
                            margin: compact ? 4 : 8,
                        },
                        splitLine: { show: false },
                    },
                ],
                series,
            };

            // Inherit inline day pan when hard-open; soft refresh keeps overlay zoom / live pin
            let saved = null;
            if (soft && wanosClimateFsChart) {
                saved = this._captureSlidingDayZoom(chart);
            } else {
                saved = this._captureSlidingDayZoom(wanosHistoryCharts.day);
            }
            this._applySlidingDayTimeWindow(
                opt,
                this._retentionDaysFromPayload(dayData),
                saved,
                { sliderBottom: shortLand ? 4 : 28, sliderHeight: shortLand ? 14 : 18 }
            );

            this._pinSoftSeriesIds(opt);
            if (soft) {
                chart.setOption(opt, { notMerge: false, replaceMerge: ["series", "dataZoom", "yAxis"] });
            } else {
                chart.setOption(opt, true);
                chart.resize();
            }
            this._bindHistoryYSnap(chart, [
                { axisIndex: 0, step: 5 },
                { axisIndex: 1, step: 10 },
                { axisIndex: 2, step: 1 },
            ].filter((a) => {
                if (a.axisIndex === 0) return showLeft;
                if (a.axisIndex === 1) return showRight;
                return showAh;
            }));
            this._bindDayWindowSubtitle(chart, "historyDaySubtitle");
        },

        /** C24/C25: CSV export of full hires_days buffer (+ peer columns when comparing). */
        exportClimateFullscreenCsv() {
            const dayData = this.historyDayClimateData;
            if (!dayData) return;
            const rows = this._climateDayDerivedRows(dayData);
            const peer = this.climateFsPeerDayData;
            const peerLabel = this.climateFsPeerName || "peer";
            const peerRows = peer ? this._climateDayDerivedRows(peer) : [];
            const peerByT = new Map();
            for (const r of peerRows) peerByT.set(r.t, r);
            const esc = (v) => {
                if (v == null || v === "") return "";
                const s = String(v);
                return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
            };
            const headers = [
                "timestamp_iso",
                "temperature_c",
                "humidity_pct",
                "dew_point_c",
                "absolute_humidity_gm3",
                "feels_like_humidity_pct",
                "dew_likelihood_pct",
            ];
            if (peer) {
                const slug = String(peerLabel).replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_|_$/g, "");
                headers.push(
                    `${slug}_temperature_c`,
                    `${slug}_humidity_pct`,
                    `${slug}_dew_point_c`,
                );
            }
            const lines = [headers.join(",")];
            const allTs = new Set(rows.map((r) => r.t));
            for (const r of peerRows) allTs.add(r.t);
            const sortedTs = Array.from(allTs).sort((a, b) => a - b);
            const primaryByT = new Map(rows.map((r) => [r.t, r]));
            for (const t of sortedTs) {
                const r = primaryByT.get(t) || {
                    temp: null, hum: null, dew: null, ah: null, ci: null, dewLikelihood: null,
                };
                const pr = peerByT.get(t);
                const iso = new Date(t).toISOString();
                const cols = [
                    esc(iso),
                    esc(r.temp),
                    esc(r.hum),
                    esc(r.dew),
                    esc(r.ah),
                    esc(r.ci != null ? Math.round(Number(r.ci)) : ""),
                    esc(r.dewLikelihood != null ? Math.round(Number(r.dewLikelihood)) : ""),
                ];
                if (peer) {
                    cols.push(
                        esc(pr ? pr.temp : ""),
                        esc(pr ? pr.hum : ""),
                        esc(pr ? pr.dew : ""),
                    );
                }
                lines.push(cols.join(","));
            }
            const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            const days = this._retentionDaysFromPayload(dayData);
            const idx = dayData.idx != null ? dayData.idx : "climate";
            a.href = url;
            a.download = `wanos-climate-${idx}-${days}d.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },
        /**
         * C12: split day temp into warm vs frost (temp < dew) segments for dual line styling.
         * Boundary points are duplicated so ECharts keeps continuous segments.
         * @returns {{ warm: Array, frost: Array }}
         */
        _tempSeriesWithFrost(tempPoints, humPoints) {
            const humByT = new Map();
            for (const p of humPoints || []) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                humByT.set(t, Number(p.v));
            }
            const warm = [];
            const frost = [];
            let prevFrost = null;
            for (const p of tempPoints || []) {
                const t = this._normalizeTsMs(p && p.t);
                if (t == null || p.v == null) continue;
                const v = Number(p.v);
                if (!Number.isFinite(v)) continue;
                const dp = this._dewPointC(v, humByT.get(t));
                const isFrost = dp != null && v < dp;
                if (prevFrost === true && !isFrost) {
                    frost.push([t, v]);
                    warm.push([t, v]);
                } else if (prevFrost === false && isFrost) {
                    warm.push([t, v]);
                    frost.push([t, v]);
                } else if (isFrost) {
                    frost.push([t, v]);
                    warm.push([t, null]);
                } else {
                    warm.push([t, v]);
                    frost.push([t, null]);
                }
                prevFrost = isFrost;
            }
            return { warm, frost };
        },

        _snapBounds(minV, maxV, step) {
            const s = Number(step) || 1;
            let lo = Math.floor(minV / s) * s;
            let hi = Math.ceil(maxV / s) * s;
            if (lo === hi) {
                lo -= s;
                hi += s;
            }
            return { min: lo, max: hi };
        },

        /**
         * C5 locked snap steps by unit.
         * @param {string} unit
         * @param {"day"|"month"|"year"} [range]
         * @returns {number|null}
         */
        _ySnapStepForUnit(unit, range) {
            const u = String(unit || "").trim();
            if (u === "°C" || u === "C") return 5;
            if (u === "%") return 10;
            if (u === "W") return 10;
            if (u === "L" || u === "l") return range === "day" ? 10 : 50;
            if (u === "V") return 5;
            if (u === "MB" || u === "MiB") return 50;
            return null;
        },

        /**
         * Snap Y axes from series values inside the current dataZoom window.
         * @param {*} chart
         * @param {{ axisIndex: number, step: number, seriesIndexes?: number[] }[]} snapAxes
         */
        _applyVisibleYSnap(chart, snapAxes) {
            if (!chart || !snapAxes || !snapAxes.length) return;
            const opt = chart.getOption();
            if (!opt || !opt.series) return;

            const xRaw = Array.isArray(opt.xAxis) ? opt.xAxis[0] : opt.xAxis;
            const baseMin = xRaw && xRaw.min != null ? Number(xRaw.min) : null;
            const baseMax = xRaw && xRaw.max != null ? Number(xRaw.max) : null;
            let xMin = baseMin;
            let xMax = baseMax;
            const dzList = opt.dataZoom || [];
            const dz = dzList.find((z) => z && (z.start != null || z.end != null)) || dzList[0];
            if (
                dz
                && baseMin != null
                && baseMax != null
                && Number.isFinite(baseMin)
                && Number.isFinite(baseMax)
            ) {
                const startPct = dz.start != null ? Number(dz.start) : 0;
                const endPct = dz.end != null ? Number(dz.end) : 100;
                const span = baseMax - baseMin;
                xMin = baseMin + (span * startPct) / 100;
                xMax = baseMin + (span * endPct) / 100;
            }

            const series = opt.series || [];
            const yPatch = {};
            for (const ax of snapAxes) {
                const step = Number(ax.step);
                if (!step || !Number.isFinite(step)) continue;
                const idxs = ax.seriesIndexes != null
                    ? ax.seriesIndexes
                    : series.map((_, i) => i).filter((i) => {
                        const s = series[i];
                        const yi = s && s.yAxisIndex != null ? Number(s.yAxisIndex) : 0;
                        return yi === ax.axisIndex;
                    });
                let minV = Infinity;
                let maxV = -Infinity;
                for (const si of idxs) {
                    const s = series[si];
                    if (!s || !Array.isArray(s.data)) continue;
                    for (const row of s.data) {
                        if (!Array.isArray(row) || row.length < 2) continue;
                        const t = Number(row[0]);
                        const v = row[1];
                        if (v == null || !Number.isFinite(Number(v))) continue;
                        if (xMin != null && xMax != null && Number.isFinite(t)) {
                            if (t < xMin || t > xMax) continue;
                        }
                        const n = Number(v);
                        if (n < minV) minV = n;
                        if (n > maxV) maxV = n;
                    }
                }
                if (!Number.isFinite(minV) || !Number.isFinite(maxV)) continue;
                const bounds = this._snapBounds(minV, maxV, step);
                yPatch[ax.axisIndex] = {
                    min: bounds.min,
                    max: bounds.max,
                    interval: step,
                };
            }

            const yAxes = Array.isArray(opt.yAxis) ? opt.yAxis : (opt.yAxis ? [opt.yAxis] : []);
            if (!yAxes.length) return;
            const yAxisOpt = yAxes.map((_, i) => (yPatch[i] ? {
                min: yPatch[i].min,
                max: yPatch[i].max,
                interval: yPatch[i].interval,
            } : {}));
            if (!Object.keys(yPatch).length) return;
            chart.setOption({ yAxis: yAxisOpt }, false);
        },

        /** Bind dataZoom → Y snap; re-apply immediately for the initial window. */
        _bindHistoryYSnap(chart, snapAxes) {
            if (!chart || !snapAxes || !snapAxes.length) return;
            const key = "_wanosYSnapHandler";
            if (chart[key]) {
                try { chart.off("datazoom", chart[key]); } catch (e) { /* ignore */ }
            }
            const handler = () => this._applyVisibleYSnap(chart, snapAxes);
            chart[key] = handler;
            chart.on("datazoom", handler);
            handler();
        },

        /** C5: true when Explorer History detail chart is open (landscape filter compact gate). */
        get historyChartOpen() {
            return this.explorerMode === "history" && this.selectedSensorIdx != null;
        },

        renderHistoryCharts(dayData, monthData, yearData, { soft = false } = {}) {
            const kind = dayData?.kind || monthData?.kind || "power";
            const isWater = kind === "water";
            const isClimate = kind === "climate";
            const isHost = kind === "host";
            const hostUnit = dayData?.unit || monthData?.unit || "";

            this.historyDayTitle = isClimate
                ? "Temperature / humidity day window"
                : (isHost ? `Value day window (${hostUnit})`
                    : (isWater ? "Cold / hot water day window" : "Usage day window"));
            this.historyMonthTitle = isClimate
                ? "Temperature / humidity last month"
                : (isHost ? `Min / max last month (${hostUnit})`
                    : (isWater ? "Cold / hot water last month" : "Usage last month"));
            this.historyYearTitle = isClimate
                ? "Temperature / humidity last year (weekly)"
                : (isHost ? `Min / max last year (${hostUnit})`
                    : (isWater ? "Cold / hot water last year" : "Usage last year"));

            this.historyDayRetentionDays = this._retentionDaysFromPayload(dayData);
            if (isClimate) {
                this.historyDayClimateData = dayData;
            }

            const zoomByKey = soft
                ? {
                    day: isWater
                        ? this._captureChartDataZoom(wanosHistoryCharts.day)
                        : this._captureSlidingDayZoom(wanosHistoryCharts.day),
                    month: this._captureChartDataZoom(wanosHistoryCharts.month),
                    year: this._captureChartDataZoom(wanosHistoryCharts.year),
                }
                : {};
            if (!soft) {
                this.historyDaySubtitle = "";
            }

            // Hard open/switch: unmount so empty titles cannot linger.
            // Soft auto-refresh: keep DOM + ECharts instances (avoids flicker).
            if (!soft) {
                this.historyChartHasData.day = false;
                this.historyChartHasData.month = false;
                this.historyChartHasData.year = false;
                this._syncHistoryHasFlags();
                this._disposeHistoryCharts();
            }

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
                if (soft) {
                    if (!dayOk && wanosHistoryCharts.day) {
                        try { wanosHistoryCharts.day.dispose(); } catch (e) { /* ignore */ }
                        wanosHistoryCharts.day = null;
                    }
                    if (!monthOk && wanosHistoryCharts.month) {
                        try { wanosHistoryCharts.month.dispose(); } catch (e) { /* ignore */ }
                        wanosHistoryCharts.month = null;
                    }
                    if (!yearOk && wanosHistoryCharts.year) {
                        try { wanosHistoryCharts.year.dispose(); } catch (e) { /* ignore */ }
                        wanosHistoryCharts.year = null;
                    }
                }

                const dayChart = dayOk ? this._ensureHistoryChart("day", "chart-day", { soft }) : null;
                const monthChart = monthOk ? this._ensureHistoryChart("month", "chart-month", { soft }) : null;
                const yearChart = yearOk ? this._ensureHistoryChart("year", "chart-year", { soft }) : null;

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
                        dayData, monthData, yearData, showHum, zoomByKey, { soft }
                    );
                    // Drop any range that rendered with no drawable points
                    if (this.historyChartHasData.month && !this._climateRangeHasData(monthData, "month")) {
                        this.historyChartHasData.month = false;
                    }
                    if (this.historyChartHasData.year && !this._climateRangeHasData(yearData, "year")) {
                        this.historyChartHasData.year = false;
                    }
                    this._syncHistoryHasFlags();
                    if (this.climateFsOpen) {
                        // Soft-refresh peer day buffer when comparing (keep checkbox state).
                        // renderHistoryCharts is sync — use then/finally, not await.
                        const redrawFs = () => this._renderClimateFullscreenChart({ soft: true });
                        if (this.climateFsCompareIdx !== "" && this.climateFsCompareIdx != null) {
                            const pIdx = Number(this.climateFsCompareIdx);
                            if (Number.isFinite(pIdx)) {
                                const headers = this.getAuthHeaders();
                                fetch(`/api/history/${pIdx}?range=day`, { headers })
                                    .then((pr) => {
                                        if (pr.status === 401 || pr.status === 403) {
                                            window.location.href = "/deviceexplorer.html";
                                            return null;
                                        }
                                        return pr.ok ? pr.json() : null;
                                    })
                                    .then((data) => {
                                        if (data) this.climateFsPeerDayData = data;
                                    })
                                    .catch(() => { /* keep last peer buffer */ })
                                    .finally(redrawFs);
                                return;
                            }
                        }
                        redrawFs();
                    }
                    return;
                }

                const yLabel = isWater ? "liters" : (isHost ? (hostUnit || "Value") : "Usage (Watt)");
                const seriesName = isHost ? "Value" : "Usage";
                const snapUnit = isWater ? "L" : (isHost ? hostUnit : "W");

                if (dayChart && this.historyChartHasData.day) {
                    if (isWater) {
                        this._renderWaterChart(dayChart, dayData, "day", {
                            soft,
                            savedZoom: zoomByKey.day,
                        });
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
                        this._applySlidingDayTimeWindow(
                            opt, this.historyDayRetentionDays, zoomByKey.day
                        );
                        this._setHistoryChartOption(dayChart, opt, null, { soft });
                        this._bindDayWindowSubtitle(dayChart, "historyDaySubtitle");
                        const step = this._ySnapStepForUnit(snapUnit, "day");
                        if (step) this._bindHistoryYSnap(dayChart, [{ axisIndex: 0, step }]);
                    }
                }

                if (monthChart && this.historyChartHasData.month) {
                    if (isWater) {
                        this._renderWaterChart(monthChart, monthData, "month", { soft });
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
                        this._setHistoryChartOption(monthChart, opt, zoomByKey.month, { soft });
                        const step = this._ySnapStepForUnit(snapUnit, "month");
                        if (step) this._bindHistoryYSnap(monthChart, [{ axisIndex: 0, step }]);
                    }
                }

                if (yearChart && this.historyChartHasData.year) {
                    if (isWater) {
                        this._renderWaterChart(yearChart, yearData, "year", { soft });
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
                        this._setHistoryChartOption(yearChart, opt, zoomByKey.year, { soft });
                        const step = this._ySnapStepForUnit(snapUnit, "year");
                        if (step) this._bindHistoryYSnap(yearChart, [{ axisIndex: 0, step }]);
                    }
                }
            };

            this.historyChartHasData.day = dayOk;
            this.historyChartHasData.month = monthOk;
            this.historyChartHasData.year = yearOk;
            this._syncHistoryHasFlags();

            if (soft) {
                // C19: always wait one Alpine tick so x-if remounts finish before ensure/setOption
                this.$nextTick(() => requestAnimationFrame(draw));
                return;
            }

            // Phase 2: mount only ranges that have data, then init charts.
            this.$nextTick(() => {
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
                // C16: water day buffer spans hires_days — include day when not today
                return d.toLocaleString("nl-BE", {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: tz,
                });
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
                    if (!map.has(t)) map.set(t, { t, events: 0, lmin: null, lmax: null, duration: null });
                    const row = map.get(t);
                    if (field === "events") row.events = Number(p.v) || 0;
                    else if (field === "lmin") row.lmin = p.v == null ? null : Number(p.v);
                    else if (field === "lmax") row.lmax = p.v == null ? null : Number(p.v);
                    else if (field === "duration") row.duration = p.v == null ? null : Number(p.v);
                }
            };
            add(data?.series?.event_count, "events");
            add(data?.series?.level_min, "lmin");
            add(data?.series?.level_max, "lmax");
            // C12: binary month minutes_on / year hours_on
            add(data?.series?.minutes_on || data?.series?.hours_on, "duration");
            return [...map.values()].sort((a, b) => a.t - b.t);
        },

        /**
         * C12: duration ON Y-axis for month/year (binary / Hue / audio).
         * Bounds: month snap ±10 min; year snap ±1 h. Interval aims for ~5 ticks
         * so labels stay readable (not every integer).
         * @param {number[]} vals
         * @param {"month"|"year"} range
         * @returns {{ min: number, max: number, interval: number }}
         */
        _durationOnAxisBounds(vals, range) {
            const nums = (vals || []).map(Number).filter((n) => Number.isFinite(n));
            const emptyMax = range === "year" ? 1 : 10;
            if (!nums.length) {
                return { min: 0, max: emptyMax, interval: emptyMax };
            }
            const dataMin = Math.min(...nums);
            const dataMax = Math.max(...nums);

            if (range === "year") {
                let min = Math.max(0, Math.floor(dataMin));
                let max = Math.max(min + 1, Math.ceil(dataMax));
                const span = max - min;
                // Prefer ~5 ticks: 1, 2, 5, 10, 20…
                let interval = 1;
                if (span > 6) interval = 2;
                if (span > 12) interval = 5;
                if (span > 30) interval = 10;
                if (span > 60) interval = 20;
                if (span > 120) interval = Math.ceil(span / 5);
                // Align max to interval so ticks land cleanly
                max = min + Math.ceil((max - min) / interval) * interval;
                return { min, max, interval };
            }

            // month — minutes, snap bounds to 10
            let min = Math.max(0, Math.floor(dataMin / 10) * 10);
            let max = Math.max(min + 10, Math.ceil(dataMax / 10) * 10);
            const span = max - min;
            let interval = 10;
            if (span > 50) interval = 20;
            if (span > 100) interval = 50;
            if (span > 250) interval = 100;
            if (span > 500) interval = Math.ceil(span / 5 / 10) * 10;
            max = min + Math.ceil((max - min) / interval) * interval;
            return { min, max, interval };
        },

        /**
         * Actuator month/year: category axis so event bars don't stretch across the window.
         * C10/C12: hits; binary+Hue+audio = duration ON; blinds level = min/max + Events.
         */
        _renderActuatorPeriodChart(chart, data, range, levelMax, { soft = false, savedZoom = null, chartKind = "level" } = {}) {
            if (!chart) return;
            const rows = this._buildActuatorPeriodPayload(data);
            if (!rows.length) return;
            const labels = rows.map(r => this._historyBucketLabel(r.t, range));
            const hitVals = rows.map(r => r.events);

            if (chartKind === "hits") {
                // C10 motion month/year: # hits per bucket only (not binary, no Level min/max)
                const peak = Math.max(0, ...hitVals.map(Number));
                const opt = {
                    backgroundColor: "transparent",
                    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
                    legend: { show: false },
                    grid: { left: 48, right: 24, top: 24, bottom: labels.length > 8 ? 72 : 56 },
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
                    yAxis: {
                        type: "value",
                        name: "Hits",
                        min: 0,
                        minInterval: 1,
                        nameTextStyle: { color: "#9ca3af" },
                        axisLabel: { color: "#9ca3af", hideOverlap: true },
                        splitLine: { lineStyle: { color: "#374151" } }
                    },
                    series: [{
                        name: "Hits",
                        type: "bar",
                        barMaxWidth: 40,
                        data: hitVals,
                        itemStyle: { color: "#64748b" }
                    }]
                };
                if (peak > 0) opt.yAxis.max = Math.ceil(peak);
                this._setHistoryChartOption(chart, opt, savedZoom, { soft, replaceYAxis: true });
                return;
            }

            // C12: binary + Hue + audio month/year → duration ON (minutes / hours)
            if (chartKind === "binary" || chartKind === "audio") {
                const durVals = rows.map(r => (r.duration == null ? 0 : Number(r.duration)));
                const yName = range === "year" ? "hours" : "minutes";
                const bounds = this._durationOnAxisBounds(durVals, range);
                const opt = {
                    backgroundColor: "transparent",
                    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
                    legend: { show: false },
                    grid: { left: 56, right: 24, top: 24, bottom: labels.length > 8 ? 72 : 56 },
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
                    yAxis: {
                        type: "value",
                        name: yName,
                        min: bounds.min,
                        max: bounds.max,
                        interval: bounds.interval,
                        minInterval: bounds.interval,
                        splitNumber: Math.max(2, Math.round((bounds.max - bounds.min) / bounds.interval)),
                        nameTextStyle: { color: "#9ca3af" },
                        axisLabel: {
                            color: "#9ca3af",
                            hideOverlap: true,
                            // Year can be integer hours; month whole minutes
                            formatter: (v) => {
                                const n = Number(v);
                                if (!Number.isFinite(n)) return "";
                                return range === "year" ? String(Math.round(n)) : String(Math.round(n));
                            }
                        },
                        splitLine: { lineStyle: { color: "#374151" } }
                    },
                    series: [{
                        name: "duration ON",
                        type: "bar",
                        barMaxWidth: 40,
                        data: durVals,
                        itemStyle: { color: "#2dd4bf" }
                    }]
                };
                this._setHistoryChartOption(chart, opt, savedZoom, { soft, replaceYAxis: true });
                return;
            }

            // Blinds / remaining level: Events + Level min/max
            const stateYName = "Level";
            const stateMinName = "Level min";
            const stateMaxName = "Level max";
            const stateAxisLabel = { color: "#9ca3af" };

            const opt = {
                backgroundColor: "transparent",
                tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
                legend: {
                    top: 4,
                    left: "center",
                    itemGap: 10,
                    // C7: line swatch, no marker dots
                    icon: "rect",
                    itemWidth: 12,
                    itemHeight: 3,
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
                        name: stateYName,
                        min: 0,
                        max: levelMax,
                        nameTextStyle: { color: "#9ca3af" },
                        axisLabel: stateAxisLabel,
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
                        data: hitVals,
                        itemStyle: { color: "#64748b" }
                    },
                    {
                        name: stateMinName,
                        type: "line",
                        yAxisIndex: 0,
                        step: "end",
                        showSymbol: true,
                        symbolSize: 5,
                        data: rows.map(r => r.lmin),
                        color: "#2dd4bf",
                        itemStyle: { color: "#2dd4bf" },
                        lineStyle: { color: "#2dd4bf" },
                        connectNulls: false
                    },
                    {
                        name: stateMaxName,
                        type: "line",
                        yAxisIndex: 0,
                        step: "end",
                        showSymbol: true,
                        symbolSize: 5,
                        data: rows.map(r => r.lmax),
                        color: "#a3e635",
                        itemStyle: { color: "#a3e635" },
                        lineStyle: { color: "#a3e635" },
                        connectNulls: false
                    }
                ]
            };
            this._setHistoryChartOption(chart, opt, savedZoom, { soft });
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
         * C16 day: pan over hires_days hours with max 24 h viewport.
         */
        _renderWaterChart(chart, data, range, { soft = false, savedZoom = null } = {}) {
            if (!chart) return;
            const { labels, coldVals, hotVals } = this._buildWaterChartPayload(data, range);
            if (!labels.length) return;

            const opt = {
                backgroundColor: "transparent",
                tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
                // C7: line/bar swatch without marker dots
                legend: {
                    bottom: 0,
                    icon: "rect",
                    itemWidth: 12,
                    itemHeight: 3,
                    textStyle: { color: "#9ca3af" }
                },
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
            if (range === "day") {
                // Soft refresh: treat end≈100% as live pin to newest hours
                let waterSaved = savedZoom;
                if (waterSaved && waterSaved.end != null && Number(waterSaved.end) >= 98) {
                    waterSaved = Object.assign({}, waterSaved, { live: true });
                }
                this._applyWaterDaySlidingZoom(opt, labels.length, waterSaved);
                opt.grid = { left: 48, right: 24, top: 24, bottom: 72 };
            }
            // C5: snap liters axis
            const step = this._ySnapStepForUnit("L", range);
            if (step) {
                const peak = Math.max(0, ...coldVals.map(Number), ...hotVals.map(Number));
                const bounds = this._snapBounds(0, peak, step);
                opt.yAxis.max = bounds.max;
                opt.yAxis.interval = step;
            }
            this._setHistoryChartOption(chart, opt, null, { soft });
            if (range === "day") {
                this._bindWaterDaySubtitle(chart, labels);
                if (step) this._bindHistoryYSnap(chart, [{ axisIndex: 0, step }]);
            }
        },

        /**
         * C16: from/to subtitle for water day category zoom (hour labels).
         * @param {Object} chart
         * @param {string[]} labels
         */
        _bindWaterDaySubtitle(chart, labels) {
            if (!chart || !labels || !labels.length) return;
            const key = "_wanosWaterSubtitleHandler";
            if (chart[key]) {
                try { chart.off("datazoom", chart[key]); } catch (e) { /* ignore */ }
            }
            const handler = () => {
                const raw = this._captureChartDataZoom(chart);
                if (!raw || labels.length <= 0) {
                    this.historyDaySubtitle = "";
                    return;
                }
                const n = labels.length;
                const startIdx = Math.round((Number(raw.start) / 100) * (n - 1));
                const endIdx = Math.round((Number(raw.end) / 100) * (n - 1));
                const live = Number(raw.end) >= 98;
                if (live) {
                    this.historyDaySubtitle = "";
                    return;
                }
                const a = labels[Math.max(0, Math.min(n - 1, startIdx))] || "";
                const b = labels[Math.max(0, Math.min(n - 1, endIdx))] || "";
                this.historyDaySubtitle = a && b ? `${a} → ${b}` : "";
            };
            chart[key] = handler;
            chart.on("datazoom", handler);
            handler();
        },

        _climateDualAxisOption(seriesCount) {
            const many = (seriesCount || 0) > 2;
            const opt = this._baseChartOption("°C");
            opt.legend = many
                ? {
                    top: 4, left: "center", itemGap: 10,
                    icon: "rect", itemWidth: 12, itemHeight: 3,
                    textStyle: { color: "#9ca3af", fontSize: 10 }
                }
                : {
                    bottom: 4, left: "center",
                    icon: "rect", itemWidth: 12, itemHeight: 3,
                    textStyle: { color: "#9ca3af", fontSize: 10 }
                };
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

        _renderClimateCharts(dayChart, monthChart, yearChart, dayData, monthData, yearData, showHum, zoomByKey = {}, { soft = false } = {}) {
            const lineSmooth = true;
            const climateSnap = (hasHum) => {
                const axes = [{ axisIndex: 0, step: 5 }];
                if (hasHum) axes.push({ axisIndex: 1, step: 10 });
                return axes;
            };

            if (dayChart) {
                // C5: day climate — smooth curves (no step stairs)
                // C12: frost when temp < dew — red + thicker (width 4); RH/dew unchanged
                // Gap break: only when >3× sample interval (more than 2 missed samples)
                const gapMs = this._climateSampleGapBreakMs(dayData);
                const tempPts = dayData?.series?.temp;
                const humPts = showHum ? dayData?.series?.hum : null;
                const frostSplit = showHum
                    ? this._tempSeriesWithFrost(tempPts, humPts)
                    : { warm: this._pointsToSeries(tempPts), frost: [] };
                const warmData = this._climateDayLineRows(frostSplit.warm, gapMs);
                const frostData = this._climateDayLineRows(frostSplit.frost, gapMs);
                const hasFrost = (frostData || []).some(row => row && row[1] != null);
                const series = [{
                    name: "Temperature",
                    type: "line",
                    smooth: lineSmooth,
                    showSymbol: false,
                    yAxisIndex: 0,
                    data: warmData,
                    lineStyle: { color: "#eab308", width: 2 },
                    itemStyle: { color: "#eab308" },
                    connectNulls: false
                }];
                if (hasFrost) {
                    series.push({
                        name: "Temperature",
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: frostData,
                        lineStyle: { color: "#ef4444", width: 4 },
                        itemStyle: { color: "#ef4444" },
                        connectNulls: false,
                        // Keep single Temperature legend entry (shared name)
                        legendHoverLink: true
                    });
                }
                if (showHum) {
                    series.push({
                        name: "Humidity",
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 1,
                        data: this._climateDayLineData(humPts, gapMs),
                        lineStyle: { color: "#22c55e", width: 2 },
                        connectNulls: false
                    });
                    // C5: dew only when humidity present (Sonntag Magnus)
                    const dew = this._climateDayLineRows(
                        this._dewSeriesFromTempHum(tempPts, humPts), gapMs
                    );
                    if (dew.length) {
                        series.push({
                            name: "Dew point",
                            type: "line",
                            smooth: lineSmooth,
                            showSymbol: false,
                            yAxisIndex: 0,
                            data: dew,
                            lineStyle: { color: "#38bdf8", width: 1.5, type: "dashed" },
                            connectNulls: false
                        });
                    }
                }
                const opt = this._climateDualAxisOption(series.length);
                // C10: legend/tooltip color must match drawn line (not ECharts default palette)
                opt.series = this._pinSeriesLegendColors(series);
                // Dedupe Temperature in legend when frost segment is present
                if (hasFrost) {
                    const legendNames = [];
                    for (const s of series) {
                        if (s.name === "Temperature" && legendNames.includes("Temperature")) continue;
                        legendNames.push(s.name);
                    }
                    opt.legend = Object.assign({}, opt.legend, { data: legendNames });
                }
                const many = (opt.series || []).length > 2;
                this._applySlidingDayTimeWindow(
                    opt,
                    this._retentionDaysFromPayload(dayData),
                    zoomByKey.day,
                    { sliderBottom: many ? 6 : 22, sliderHeight: 14 }
                );
                this._setHistoryChartOption(dayChart, opt, null, { soft });
                this._bindDayWindowSubtitle(dayChart, "historyDaySubtitle");
                this._bindHistoryYSnap(dayChart, climateSnap(showHum));
            }

            if (monthChart) {
                const series = [
                    {
                        name: "Temp min",
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._pointsToSeries(monthData?.series?.temp_min),
                        lineStyle: { color: "#eab308", width: 1.5, type: "dashed" },
                        connectNulls: false
                    },
                    {
                        name: "Temp max",
                        type: "line",
                        smooth: lineSmooth,
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
                            smooth: lineSmooth,
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(monthData?.series?.hum_min),
                            lineStyle: { color: "#22c55e", width: 1.5, type: "dashed" },
                            connectNulls: false
                        },
                        {
                            name: "Hum max",
                            type: "line",
                            smooth: lineSmooth,
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(monthData?.series?.hum_max),
                            lineStyle: { color: "#22c55e", width: 2 },
                            connectNulls: false
                        }
                    );
                    // C12: no dew series on month charts (day only)
                }
                const opt = this._climateDualAxisOption(series.length);
                opt.series = this._pinSeriesLegendColors(series);
                this._applyClimateTimeWindow(opt, 31 * 24 * 60 * 60 * 1000);
                this._setHistoryChartOption(monthChart, opt, zoomByKey.month, { soft });
                this._bindHistoryYSnap(monthChart, climateSnap(showHum));
            }

            if (yearChart) {
                const series = [
                    {
                        name: "Temp min",
                        type: "line",
                        smooth: lineSmooth,
                        showSymbol: false,
                        yAxisIndex: 0,
                        data: this._pointsToSeries(yearData?.series?.temp_min),
                        lineStyle: { color: "#eab308", width: 1.5, type: "dashed" },
                        connectNulls: false
                    },
                    {
                        name: "Temp max",
                        type: "line",
                        smooth: lineSmooth,
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
                            smooth: lineSmooth,
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(yearData?.series?.hum_min),
                            lineStyle: { color: "#22c55e", width: 1.5, type: "dashed" },
                            connectNulls: false
                        },
                        {
                            name: "Hum max",
                            type: "line",
                            smooth: lineSmooth,
                            showSymbol: false,
                            yAxisIndex: 1,
                            data: this._pointsToSeries(yearData?.series?.hum_max),
                            lineStyle: { color: "#22c55e", width: 2 },
                            connectNulls: false
                        }
                    );
                    // C12: no dew series on year charts (day only)
                }
                const opt = this._climateDualAxisOption(series.length);
                opt.series = this._pinSeriesLegendColors(series);
                this._applyClimateTimeWindow(opt, 366 * 24 * 60 * 60 * 1000);
                this._setHistoryChartOption(yearChart, opt, zoomByKey.year, { soft });
                this._bindHistoryYSnap(yearChart, climateSnap(showHum));
            }
        },

        async reloadHistoryCharts(opts = {}) {
            if (!this.selectedHistoryIdx) return;
            const soft = !!opts.soft;
            if (!soft) this.historyLoading = true;
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
                if (!soft) await this.$nextTick();
                this.renderHistoryCharts(dayData, monthData, yearData, { soft });
            } catch (e) {
                console.error("Failed to reload history charts", e);
            } finally {
                if (!soft) this.historyLoading = false;
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
                this.dismissSessionAuditPopover();
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

        // 🔔 Alert UI Action Dispatchers (C2: banner vs bell dismiss are independent)
        // C8: fire-and-forget ALERT_UI_DISMISSED log only (does not remove alert from server state)
        _logAlertUiDismiss(surface, id) {
            const msg = (this.state.system.system_alert_msgs || []).find(m => m.id === id);
            const level = (msg && msg.level) ? msg.level : "info";
            const text = (msg && msg.message) ? String(msg.message) : "";
            // C12: prefer produced_at (YYYY-MM-DD HH:MM:SS, matches loguru); fallback UI timestamp
            const producedAt = (msg && (msg.produced_at || msg.timestamp))
                ? String(msg.produced_at || msg.timestamp)
                : "";
            this.publishEvent("ALERT_UI_DISMISSED", {
                surface: surface,
                level: level,
                message: text,
                produced_at: producedAt,
            }).catch(() => { /* log failure must not undo UI dismiss */ });
        },

        dismissBannerAlert(id) {
            if (!this.bannerDismissedAlertIds.includes(id)) {
                this.bannerDismissedAlertIds = [...this.bannerDismissedAlertIds, id];
            }
            this._logAlertUiDismiss("banner", id);
        },

        dismissBellAlert(id) {
            if (!this.bellDismissedAlertIds.includes(id)) {
                this.bellDismissedAlertIds = [...this.bellDismissedAlertIds, id];
            }
            this._logAlertUiDismiss("bell", id);
            // Non-criticals: also clear on server so other Admin views stay consistent
            const msg = (this.state.system.system_alert_msgs || []).find(m => m.id === id);
            if (msg && msg.level !== "critical") {
                this.publishEvent("ALERT_DISMISSED", { id: id });
            }
        },

        /** @deprecated Prefer dismissBannerAlert / dismissBellAlert (C2 dual dismiss). */
        dismissAlert(id) {
            this.dismissBellAlert(id);
        },

        clearNonCriticalAlerts() {
            // C20: Clear All = dismiss every visible bell row (same as each X)
            const rows = this.bellAlerts || [];
            for (const msg of rows) {
                if (msg && msg.id != null) {
                    this.dismissBellAlert(msg.id);
                }
            }
        },

        async requestWanosRestart() {
            const dlg = document.getElementById("wanos_restart_modal");
            if (dlg) dlg.showModal();
        },

        cancelWanosRestart() {
            document.getElementById("wanos_restart_modal")?.close();
        },

        async confirmWanosRestart() {
            document.getElementById("wanos_restart_modal")?.close();
            try {
                const res = await fetch("/api/admin/restart", {
                    method: "POST",
                    headers: this.getAuthHeaders(),
                });
                if (res.status === 202) {
                    this.showToast("WanOS service restarting… reconnecting shortly");
                    return;
                }
                const body = await res.json().catch(() => ({}));
                this.showToast(body.error || `Restart failed (${res.status})`);
            } catch (e) {
                this.showToast(String(e.message || e || "Restart failed"));
            }
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

        adjustIrTimer(minutesToAdd) {
            this.publishEvent("IR_TIMER_ADJUSTED", { minutes: minutesToAdd });
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

        toggleLg() {
            const nextState = !this.state.system.lg_integration_enabled;
            this.publishEvent("LG_TOGGLED", { enabled: nextState });
        },

        toggleSonos() {
            const nextState = !this.state.system.sonos_integration_enabled;
            this.publishEvent("SONOS_TOGGLED", { enabled: nextState });
        },

        toggleOnkyo() {
            const nextState = !this.state.system.onkyo_integration_enabled;
            this.publishEvent("ONKYO_TOGGLED", { enabled: nextState });
        },

        toggleLcd() {
            const nextState = !this.state.system.lcd_integration_enabled;
            this.publishEvent("LCD_TOGGLED", { enabled: nextState });
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

            // Optimistic UI: keep toggle/checkbox in sync with the click immediately.
            // Without this, :checked="item.is_on" rebinds from still-old state → OFF→ON flicker,
            // and repeated clicks enqueue more OFF/ON commands while SSE lags (RFX / Z-Wave / Hue).
            let nextVal;
            if (typeof current === 'object' && current !== null) {
                nextVal = Object.assign({}, current, { state: targetState });
            } else {
                nextVal = targetState;
            }
            this.state.devices[idx] = nextVal;

            // Ignore stale bridge echoes until the command settles (same anti-rubberband as shutters).
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('switch', false);

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
        // C12 blinds: proportional to travel Δ% × travel_time × 1.10 (mirrors hub_handlers).
        getUiLockTime(deviceType, isDragging = false, opts = {}) {
            if (deviceType === 'blinds') {
                const fromPos = opts.fromPos;
                const toPos = opts.toPos;
                const base = this._blindsTravelSecs(opts.entityId);
                if (fromPos != null && toPos != null
                    && Number.isFinite(Number(fromPos)) && Number.isFinite(Number(toPos))) {
                    const delta = Math.abs(Number(fromPos) - Number(toPos));
                    const secs = Math.max(1, Math.round((delta / 100.0) * base * 1.10));
                    return secs * 1000;
                }
                // Unknown span (e.g. mid-drag start): conservative full-travel lock
                return Math.max(1, Math.round(base * 1.10)) * 1000;
            }
            if (deviceType === 'speaker') {
                // Speakers run on instant local TCP/API.
                // Give a short lock while dragging to prevent fighting the finger,
                // but drop the lock to 0ms instantly upon release!
                return isDragging ? 2000 : 0;
            }
            // Binary switch/light toggles (RFX / Z-Wave / Hue): cover bridge round-trip
            // so a stale ON echo cannot snap the Explorer toggle back after optimistic OFF.
            if (deviceType === 'switch' || deviceType === 'light') {
                return 2000;
            }
            // Default fallback
            return 1000;
        },

        /** C12: per-blind travel seconds from system state (config.blinds). */
        _blindsTravelSecs(entityId) {
            const sys = this.state.system || {};
            const map = sys.blinds_travel_times || {};
            const defRaw = Number(sys.blinds_default_travel_time_secs);
            const def = (Number.isFinite(defRaw) && defRaw > 0) ? defRaw : 35;
            if (entityId != null && map[entityId] != null) {
                const n = Number(map[entityId]);
                if (Number.isFinite(n) && n > 0) return n;
            }
            return def;
        },

        setShutterState(idx, targetState) {
            if (this.shutterDragIdx != null && Number(this.shutterDragIdx) === Number(idx)) {
                this.shutterDragIdx = null;
            }

            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            const cur = this.state.devices[idx];
            const fromPos = (this.shutterDragFrom != null)
                ? this.shutterDragFrom
                : (typeof cur === "number" ? cur : (cur != null ? Number(cur) : 0));
            this.shutterDragFrom = null;

            // Set Optimistic UI Lock expiration to ignore incoming Z-Wave state updates
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('blinds', false, {
                fromPos,
                toPos: targetState,
                entityId: meta.entity_id,
            });

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

            // Pure hardware integer; clamp to device max_volume (Sonos + Onkyo).
            const meta = this.state.device_metadata[idx] || {};
            const deviceMax = this._actuatorLevelDeviceMax(idx);
            const rawVol = Math.max(0, Math.min(deviceMax, parseInt(uiVol, 10)));
            current.volume = rawVol;
            this.state.devices[idx] = current;

            // ⚡ DYNAMIC ROUTING: volume via HUB_STATE_CHANGED so automations see the edge (B19; mirror Onkyo).
            if (meta && meta.origin === 'onkyo') {
                // ⚡ Optimistic UI Lock: Instantly force the "SYNC..." state in Alpine to disable the slider
                // until the physical receiver answers back with the true volume value.
                this.state.devices[idx] = null;
            }
            this.publishEvent("HUB_STATE_CHANGED", { idx: parseInt(idx, 10), volume: rawVol });
        },

        updateSpeakerOptimistic(idx, uiVol) {
            // ⚡ SHORT LOCK: Keep a 2-second lock while actively dragging so network
            // echoes don't rip the slider out from under the user's finger.
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('speaker', true);

            let current = this.state.devices[idx] || { state: 'ON' };
            if (typeof current !== 'object') current = { state: current };

            const deviceMax = this._actuatorLevelDeviceMax(idx);
            const rawVol = Math.max(0, Math.min(deviceMax, parseInt(uiVol, 10)));
            current.volume = rawVol;
            this.state.devices[idx] = current;
        },

        updateShutterOptimistic(idx, val) {
            const numVal = parseInt(val, 10);
            const meta = (this.state.device_metadata && this.state.device_metadata[idx]) || {};
            // C12: remember drag start so lock Δ matches hub proportional debounce
            if (this.shutterDragIdx == null || Number(this.shutterDragIdx) !== Number(idx)) {
                const cur = this.state.devices[idx];
                this.shutterDragFrom = typeof cur === "number" ? cur : (cur != null ? Number(cur) : 0);
            }
            this.shutterDragIdx = parseInt(idx, 10);
            this.uiLocks[idx] = Date.now() + this.getUiLockTime('blinds', true, {
                fromPos: this.shutterDragFrom,
                toPos: numVal,
                entityId: meta.entity_id,
            });

            // ⚡ Immediately update the reactive dictionary so the slider and % text move live with the mouse pointer
            this.state.devices[idx] = numVal;
        },

        /** Commit after drag; safe if @change was skipped because the row left the filter. */
        commitShutterDrag(idx, val, verified) {
            if (!verified) return;
            if (this.shutterDragIdx == null || Number(this.shutterDragIdx) !== Number(idx)) return;
            this.setShutterState(idx, parseInt(val, 10));
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
            this.activeHuePresetKey = null;
            this.huePresetDirtySinceSelect = false;
            this.huePresetEditMode = false;

            // Load existing color from backend state, or default to Warm White
            // C12: bri display/slider integer 1–100 (ON never 0)
            if (typeof item.raw_value === 'object' && item.raw_value !== null) {
                this.activeLightBri = this._clampHueBri(item.raw_value.bri);
                this.activeLightHex = this.xyToWheelHex(
                    item.raw_value.xy ? item.raw_value.xy[0] : undefined,
                    item.raw_value.xy ? item.raw_value.xy[1] : undefined
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

                    // Update Alpine state from wheel changes.
                    this.colorPicker.on('color:change', (color) => {
                        if (this.huePresetEditMode) return;
                        this.activeLightHex = color.hexString;
                    });

                    // User drag starts → this is no longer "exactly the selected preset".
                    this.colorPicker.on('input:start', () => {
                        if (this.huePresetEditMode) return;
                        if (!this._huePresetApplyGuard && this.activeHuePresetKey) {
                            this.huePresetDirtySinceSelect = true;
                        }
                    });

                    // Send API call ONLY when the user stops dragging to prevent network spam
                    this.colorPicker.on('input:end', (color) => {
                        if (this.huePresetEditMode) return;
                        this.updateActiveLightState();
                    });
                }, 50); // Tiny delay ensures DaisyUI modal has rendered the div
            } else {
                // If it already exists, just snap the wheel to the correct color
                this.colorPicker.color.hexString = this.activeLightHex;
            }

            document.getElementById('light_control_modal').showModal();
            if (this.isAdmin) {
                this.refreshHuePresetsCatalog();
            }
        },

        applyPreset(preset, key) {
            if (!preset) return;
            const prevHex = String(this.activeLightHex || "");
            const prevBri = parseInt(this.activeLightBri, 10);

            this.activeHuePresetKey = key;
            this.huePresetDirtySinceSelect = false;
            this.activeLightBri = this._clampHueBri(preset.bri);
            // For rgb-backed presets keep exact wheel color; fallback to xy.
            const nextHex = preset.rgb
                ? String(preset.rgb)
                : this.xyToWheelHex(preset.xy[0], preset.xy[1]);
            this.activeLightHex = nextHex;

            const shouldSkipWheelSnap =
                String(prevHex).trim().toUpperCase() === String(nextHex || "").trim().toUpperCase()
                && parseInt(prevBri, 10) === parseInt(this.activeLightBri, 10);

            // Instantly snap the iro.js color wheel to the new preset color.
            this._huePresetApplyGuard = true;
            if (this.colorPicker && !shouldSkipWheelSnap) {
                this.colorPicker.color.hexString = this.activeLightHex;
            }
            setTimeout(() => {
                this._huePresetApplyGuard = false;
            }, 80);

            // Dispatch the command to the physical bulb, but leave the modal open for tweaking!
            this.updateActiveLightState();
        },

        /** B9A: refresh preset chips + usage map (immediate UI; does not wait for SSE reload). */
        async refreshHuePresetsCatalog() {
            try {
                const res = await fetch("/api/hue-presets", { headers: this.getAuthHeaders() });
                if (!res.ok) return;
                const data = await res.json();
                // Replace wholesale so Alpine x-for picks up add/rename/delete immediately.
                this.state.system = {
                    ...this.state.system,
                    hue_presets: { ...(data.presets || {}) }
                };
                this.huePresetUsages = data.usages || {};
            } catch (e) { /* ignore */ }
        },

        _applyHuePresetCatalogPatch(key, preset) {
            if (!key) return;
            const next = { ...(this.state.system.hue_presets || {}) };
            if (preset) {
                next[key] = preset;
            } else {
                delete next[key];
            }
            this.state.system = {
                ...this.state.system,
                hue_presets: next
            };
        },

        _huePresetDisplayNameTaken(name, excludeKey) {
            const target = String(name || "").trim().toLowerCase();
            if (!target) return false;
            const presets = this.state.system.hue_presets || {};
            return Object.entries(presets).some(([key, preset]) => {
                if (excludeKey && key === excludeKey) return false;
                const label = String((preset && preset.name) || key).trim().toLowerCase();
                return label === target;
            });
        },

        /** True when wheel xy + brightness slider match the last clicked preset chip. */
        hueCurrentMatchesActivePreset() {
            return !!this.activeHuePresetKey && !this.huePresetDirtySinceSelect;
        },

        onHueBrightnessInput() {
            if (this.huePresetEditMode) return;
            // C12: keep display + outbound bri as integer 1–100
            this.activeLightBri = this._clampHueBri(this.activeLightBri);
            if (!this._huePresetApplyGuard && this.activeHuePresetKey) {
                this.huePresetDirtySinceSelect = true;
            }
            this.updateActiveLightState();
        },

        /**
         * C12: Hue brightness for Explorer modal — integer only, range 1–100 (ON never 0).
         * @param {*} raw
         * @returns {number}
         */
        _clampHueBri(raw) {
            const n = Math.round(Number(raw));
            if (!Number.isFinite(n)) return 100;
            return Math.max(1, Math.min(100, n));
        },

        openHuePresetSaveModal() {
            // B10M: allow same colour/bri as an existing preset (unique display name required)
            this.huePresetNameModalMode = "save";
            this.huePresetNameModalKey = null;
            this.huePresetNameModalTitle = "Save colour preset";
            this.huePresetNameInput = "";
            document.getElementById("hue_preset_name_modal")?.showModal();
        },

        openHuePresetRenameModal(key, preset) {
            this.huePresetNameModalMode = "rename";
            this.huePresetNameModalKey = key;
            this.huePresetNameModalTitle = "Rename preset";
            this.huePresetNameInput = (preset && preset.name) || key;
            document.getElementById("hue_preset_name_modal")?.showModal();
        },

        cancelHuePresetNameModal() {
            document.getElementById("hue_preset_name_modal")?.close();
            this.huePresetNameModalMode = null;
            this.huePresetNameModalKey = null;
            this.huePresetNameInput = "";
        },

        async confirmHuePresetNameModal() {
            const trimmed = String(this.huePresetNameInput || "").trim();
            if (!trimmed) return;
            const mode = this.huePresetNameModalMode;
            const key = this.huePresetNameModalKey;
            this.cancelHuePresetNameModal();
            if (mode === "save") {
                await this.saveCurrentAsHuePreset(trimmed);
            } else if (mode === "rename" && key) {
                await this.renameHuePreset(key, trimmed);
            }
        },

        openHuePresetDeleteModal(key, preset) {
            const usages = (this.huePresetUsages && this.huePresetUsages[key]) || [];
            if (usages.length) {
                this.showToast(`Cannot delete — in use by: ${usages.join(", ")}`);
                return;
            }
            this.huePresetDeleteKey = key;
            this.huePresetDeleteDisplayName = (preset && preset.name) || key;
            document.getElementById("hue_preset_delete_modal")?.showModal();
        },

        cancelHuePresetDeleteModal() {
            document.getElementById("hue_preset_delete_modal")?.close();
            this.huePresetDeleteKey = null;
            this.huePresetDeleteDisplayName = "";
        },

        async confirmHuePresetDeleteModal() {
            const key = this.huePresetDeleteKey;
            this.cancelHuePresetDeleteModal();
            if (key) {
                await this.deleteHuePreset(key);
            }
        },

        async saveCurrentAsHuePreset(name) {
            // B10M: do not block when colour matches an existing / active preset
            const trimmed = String(name || "").trim();
            if (!trimmed) return;
            if (this._huePresetDisplayNameTaken(trimmed)) {
                this.showToast(`A preset named "${trimmed}" already exists.`);
                return;
            }
            try {
                const res = await fetch("/api/hue-presets", {
                    method: "POST",
                    headers: { ...this.getAuthHeaders(), "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name: trimmed,
                        bri: parseInt(this.activeLightBri, 10),
                        rgb: String(this.activeLightHex || "").trim()
                    })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.showToast(data.error || "Failed to save preset");
                    return;
                }
                if (data.key && data.preset) {
                    this._applyHuePresetCatalogPatch(data.key, data.preset);
                    // Immediately treat the saved preset as "active" so Save-current disables.
                    this.activeHuePresetKey = data.key;
                    this.huePresetDirtySinceSelect = false;
                    this.activeLightBri = this._clampHueBri(data.preset.bri);
                    this.activeLightHex = data.preset.rgb
                        ? String(data.preset.rgb)
                        : this.xyToWheelHex(data.preset.xy[0], data.preset.xy[1]);
                }
                await this.refreshHuePresetsCatalog();
            } catch (e) {
                this.showToast(String(e && e.message ? e.message : e));
            }
        },

        async renameHuePreset(key, name) {
            const trimmed = String(name || "").trim();
            if (!trimmed) return;
            if (this._huePresetDisplayNameTaken(trimmed, key)) {
                this.showToast(`A preset named "${trimmed}" already exists.`);
                return;
            }
            try {
                const res = await fetch(`/api/hue-presets/${encodeURIComponent(key)}`, {
                    method: "PUT",
                    headers: { ...this.getAuthHeaders(), "Content-Type": "application/json" },
                    body: JSON.stringify({ name: trimmed })
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    this.showToast(data.error || "Failed to rename preset");
                    return;
                }
                if (data.key && data.preset) {
                    this._applyHuePresetCatalogPatch(data.key, data.preset);
                }
                await this.refreshHuePresetsCatalog();
            } catch (e) {
                this.showToast(String(e && e.message ? e.message : e));
            }
        },

        async deleteHuePreset(key) {
            try {
                const res = await fetch(`/api/hue-presets/${encodeURIComponent(key)}`, {
                    method: "DELETE",
                    headers: this.getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const extra = (data.usages && data.usages.length)
                        ? ` — in use: ${data.usages.join(", ")}`
                        : "";
                    this.showToast((data.error || "Failed to delete preset") + extra);
                    return;
                }
                if (this.activeHuePresetKey === key) {
                    this.activeHuePresetKey = null;
                    this.huePresetDirtySinceSelect = false;
                }
                this._applyHuePresetCatalogPatch(key, null);
                await this.refreshHuePresetsCatalog();
            } catch (e) {
                this.showToast(String(e && e.message ? e.message : e));
            }
        },

        updateActiveLightState() {
            if (!this.activeLightId) return;
            const xy = this.hexToXY(this.activeLightHex);
            const bri = this._clampHueBri(this.activeLightBri);
            this.activeLightBri = bri;

            // Dispatch a rich dictionary. We pass force: true so the backend guarantees
            // transmission even if the bulb's power state is already "ON".
            this.publishEvent("HUB_STATE_CHANGED", {
                idx: parseInt(this.activeLightId, 10),
                state: "ON",
                bri: bri,
                xy: xy,
                force: true
            });
        },

        // 🧮 Converts CIE 1931 [x, y] to hex for the iro.js wheel (fixed reference brightness).
        xyToWheelHex(x, y) {
            return this.xyToHex(x, y, 100);
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

        /** C27: local HH:MM plus relative parenthetical for Admin / Explorer sun chrome. */
        formatSunDiagnosticLine(targetUnix, nowUnix) {
            if (!targetUnix) return "";
            const hm = this.formatUnixTime(targetUnix).slice(0, 5);
            return `${hm} ${this.getRelativeTime(targetUnix, nowUnix)}`;
        },

        /** C25 Admin Outside weather: Td from live outside T/RH. */
        get owmAdminDewPointC() {
            const t = this.state.sensors && this.state.sensors.outside_temp;
            const h = this.state.sensors && this.state.sensors.outside_hum;
            return this._dewPointC(t, h);
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

            await this.publishEvent("CONFIG_RELOAD_REQUESTED", { source: "ui_button" });

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
                || this.actuatorFavoritesOnly === true
                || (this.isAdmin && this.showHiddenNodes === true);
        },

        // Rapidly clears all UI filters and sort modes back to their base defaults
        clearAllFilters() {
            this.searchQuery = "";
            this.actuatorSearchQuery = "";
            this.typeFilter = "ALL";
            this.statusFilter = "ALL";
            this.sortMode = "NAME";
            this.actuatorFavoritesOnly = false;
            this.showHiddenNodes = false;
            this.favoritesEditMode = false;
            this.appliedPresetIndex = null;
        },

        // Router for when a user clicks one of the 1-4 preset circles
        handlePresetClick(index) {
            if (this.presets[index] !== null) {
                const p = this.presets[index];
                // C12: non-admin cannot apply a Hidden view-preset
                if (!this.isAdmin && p.showHiddenNodes === true) {
                    this.showToast("Hidden preset is admin-only.");
                    return;
                }
                // APPLY PRESET: Slot is filled, instantly map the saved payload to the reactive filters
                this.searchQuery = p.searchQuery || "";
                this.typeFilter = p.typeFilter || "ALL";
                this.statusFilter = p.statusFilter || "ALL";
                this.sortMode = p.sortMode || "NAME";
                // C1: favoritesOnly only applies when at least one favorite exists
                this.actuatorFavoritesOnly = p.favoritesOnly === true && this.actuatorFavorites.length > 0;
                // Hidden is admin-only; non-admin always lands on normal (non-hidden) view
                this.showHiddenNodes = this.isAdmin && p.showHiddenNodes === true;
                this.appliedPresetIndex = index;
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
                    showHiddenNodes: this.isAdmin && this.showHiddenNodes === true,
                };
                this.presets[this.activePresetSlot] = payload;
                localStorage.setItem('wanos_view_presets', JSON.stringify(this.presets));
                this.appliedPresetIndex = this.activePresetSlot;
                this.activePresetSlot = null; // Release the lock
                document.getElementById('preset_save_modal').close();
            }
        },

        // Clears a specific slot and flushes the deletion to persistent storage
        removePreset(index) {
            this.presets[index] = null;
            if (this.appliedPresetIndex === index) this.appliedPresetIndex = null;
            localStorage.setItem('wanos_view_presets', JSON.stringify(this.presets));
        },

        // Compiles a human-readable summary of the payload for the edit menu / tooltip / caption.
        // omitSort: true → skip Sort: … (hover tooltip + selected caption under presets).
        getPresetSummary(index, omitSort = false) {
            const p = this.presets[index];
            if (!p) return "Empty";

            let parts = [];
            if (p.searchQuery) parts.push(`"${p.searchQuery}"`);
            if (p.typeFilter !== "ALL") parts.push(p.typeFilter);
            if (p.statusFilter !== "ALL") parts.push(p.statusFilter);
            if (p.favoritesOnly) parts.push("Favorites");
            if (p.showHiddenNodes) parts.push("Hidden");

            if (!omitSort) {
                if (p.sortMode === "STATUS") parts.push("Sort: Status");
                else if (p.sortMode === "TYPE") parts.push("Sort: Type, Name");
                else if (p.sortMode === "NAME") parts.push("Sort: Name");
            }

            // Fallback for edge cases, though isFilterActive normally guards against saving empty states
            return parts.length > 0 ? parts.join(" • ") : "Default View";
        },

        // Simple ephemeral UI feedback manager
        showToast(msg) {
            const ts = this._uiClockStamp();
            this.toastMessage = ts ? (ts + " · " + msg) : msg;
            if (this.toastTimeout) clearTimeout(this.toastTimeout);
            this.toastTimeout = setTimeout(() => { this.toastMessage = ""; }, 3000);
        },

        /** Local HH:MM:SS for ephemeral toasts (system alerts carry server timestamp). */
        _uiClockStamp() {
            try {
                const d = new Date();
                const p = (n) => String(n).padStart(2, "0");
                return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
            } catch (e) {
                return "";
            }
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