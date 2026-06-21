// --- file: frontend/app.js ---

function wanosApp() {
    return {
        connected: false,

        state: {
            system: {
                wanos_mqtt_connected: false,
                domoticz_mqtt_connected: false,
                ip_address: "0.0.0.0",
                os_boot_unix: null,
                app_boot_unix: null,
                os_uptime_formatted: "00:00:00",
                app_uptime_formatted: "00:00:00",
                automations_enabled: true, // Master switch for the logic engine
                domoticz_integration_enabled: false, // ⚡ Switch to block/allow Domoticz messages
                owm_integration_enabled: false, // ⚡ Switch to block/allow OWM polling
                rfxcom_connected: false, // ⚡ Live USB mounting health status
                rfxcom_integration_enabled: false, // ⚡ Switch to block/allow native RFXCOM transmission/reception
                native_rfx_devices: [] // ⚡ Enables reactivity for the dynamic panel
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
                live_mode: false,
                simulations_enabled: false, // Master switch for the physics engine
                safety_pin_active: false, // Hardwired GPIO. Instantly verified locally, safe to default false.
                sensor_errors: []
            },
            // PESSIMISTIC UI ARCHITECTURE: All Domoticz-driven relays are initialized
            // strictly to `null`. This keeps the UI buttons disabled and grayed out
            // until the Python backend explicitly pushes their verified state.
            // ⚡ REFACTORED: Utilizing pure numeric IDXs directly instead of semantic names!
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
            boot_seed: null
        },

        // Dedicated UI Toggle to lock/unlock manual manipulation of the physics simulator
        labControlsEnabled: false,

        // Tracks the execution state of the Sweeper
        sweepRunning: false,

        // Tracks the execution state of the configuration hot-reload loop
        configReloading: false,

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
        irStepIndex: 5, // Defaults to index 6 (75%)
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
            // Defensive defaults for any fields that may be absent
            if (!fullState.sauna.phases_pwm) {
                fullState.sauna.phases_pwm = [0, 0, 0];
            } else {
                fullState.sauna.phases_pwm = fullState.sauna.phases_pwm.map(v =>
                    (v === null || v === undefined || isNaN(v)) ? 0 : v
                );
            }
            if (!fullState.hardware.sensor_errors) fullState.hardware.sensor_errors = [];
            fullState.sauna.modulation_pwm = fullState.sauna.modulation_pwm ?? 0;

            // Alpine Reactivity Preservation
            for (const domain of ["system", "sensors", "sauna", "ir", "metrics", "hardware"]) {
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
            // Merges a single changed domain subtree into the reactive store.
            if (domain === "sauna") {
                if (data.phases_pwm) {
                    data.phases_pwm = data.phases_pwm.map(v =>
                        (v === null || v === undefined || isNaN(v)) ? 0 : v
                    );
                }
                data.modulation_pwm = data.modulation_pwm ?? 0;
            }
            if (domain === "hardware") {
                if (!data.sensor_errors) data.sensor_errors = [];
            }
            if (domain === "devices") {
                // Merge device keys individually natively!
                this.state.devices = Object.assign({}, this.state.devices, data);
                if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                    this.syncLabControls();
                }
                return;
            }

            this.state[domain] = Object.assign({}, this.state[domain], data);

            // ⚡ INTELLIGENT UI UNLOCKER: Watch for backend sweep or config completion strings
            if (domain === "system" && data.system_alert_msgs) {
                if (data.system_alert_msgs.some(msg => msg.includes("Sweeper complete"))) {
                    this.sweepRunning = false;
                }
                if (data.system_alert_msgs.some(msg => msg.includes("Config reloaded") || msg.includes("Config reload failed"))) {
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
                const eventSource = new EventSource("/api/state/sse");

                // ⏱️ Sliding Watchdog Guardian Loop
                const resetWatchdog = () => {
                    if (this.sseWatchdog) clearTimeout(this.sseWatchdog);
                    this.sseWatchdog = setTimeout(() => {
                        console.warn("⚠️ Watchdog Timeout! No server signal detected for 10s. Forcing reconnect...");
                        this.connected = false;
                        eventSource.close();
                        setTimeout(() => this.connectSSE(), 3000);
                    }, 10000); // 2x the 5-second backend ping interval
                };

                resetWatchdog();

                eventSource.onmessage = (event) => {
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

                eventSource.onerror = (err) => {
                    if (this.sseWatchdog) clearTimeout(this.sseWatchdog);
                    this.connected = false;
                    console.error("❌ SSE stream broke. Re-linking context in 3s...");
                    eventSource.close();
                    // On reconnect, fetch a fresh full snapshot before resuming deltas
                    setTimeout(() => this.connectSSE(), 3000);
                };
            });
        },

        ticker() {
            const now = Math.floor(Date.now() / 1000);

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

            return `${durationStr} (${bootStr})`;
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

        async dispatchEvent(eventType, payload = {}) {
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

        // ⚡ REFACTORED: Now natively accepts and dispatches numeric IDXs for sensor data
        injectLabMetric(eventType, idx, targetValue) {
            const payload = {
                idx: parseInt(idx, 10),
                value: eventType === "TEMP_UPDATED" ? parseFloat(targetValue) : parseInt(targetValue, 10),
                lab_override: true
            };
            this.dispatchEvent(eventType, payload);
        },

        toggleSauna() {
            if (this.state.sensors.sauna_calc_temp == null) {
                console.warn("UI locked: Cannot start Sauna without valid temperature data.");
                return;
            }
            const action = this.state.sauna.active ? "SAUNA_OFF" : "SAUNA_ON";
            this.dispatchEvent(action);
        },

        updateSaunaSetpoint() {
            this.dispatchEvent("SAUNA_SETPOINT_CHANGED", { target: parseFloat(this.state.sauna.target_temp) });
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
            this.dispatchEvent("IR_MODULATION_UPDATED", { pwm: pwm, freq: freq });
        },

        toggleSaunaHold() {
            this.dispatchEvent("SAUNA_HOLD_TOGGLED");
        },

        adjustSaunaTimer(minutesToAdd) {
            this.dispatchEvent("SAUNA_TIMER_ADJUSTED", { minutes: minutesToAdd });
        },

        toggleIR() {
            if (this.state.sensors.sauna_calc_temp == null) {
                console.warn("UI locked: Cannot start IR without valid temperature data.");
                return;
            }
            const action = this.state.ir.active ? "IR_OFF" : "IR_ON";
            this.dispatchEvent(action);
        },

        toggleHardwareMode() {
            const nextMode = !this.state.hardware.live_mode;
            this.dispatchEvent("HARDWARE_LIVE_MODE_CHANGED", { live: nextMode });
        },

        toggleAutomations() {
            const nextState = !this.state.system.automations_enabled;
            this.dispatchEvent("AUTOMATIONS_TOGGLED", { enabled: nextState });
        },

        toggleDomoticz() {
            const nextState = !this.state.system.domoticz_integration_enabled;
            this.dispatchEvent("DOMOTICZ_TOGGLED", { enabled: nextState });
        },

        toggleRFXCOM() {
            const nextState = !this.state.system.rfxcom_integration_enabled;
            this.dispatchEvent("RFXCOM_TOGGLED", { enabled: nextState });
        },

        toggleOWM() {
            const nextState = !this.state.system.owm_integration_enabled;
            this.dispatchEvent("OWM_TOGGLED", { enabled: nextState });
        },

        toggleSimulations() {
            const nextState = !this.state.hardware.simulations_enabled;
            this.dispatchEvent("SIMULATIONS_TOGGLED", { enabled: nextState });
        },

        // ⚡ REFACTORED: Now natively accepts and dispatches numeric IDXs for doors
        injectLabDoorChange(idx, isOpen) {
            this.dispatchEvent("DOOR_CHANGED", { idx: parseInt(idx, 10), is_open: isOpen });
        },

        // ⚡ REFACTORED: Now natively accepts and dispatches numeric IDXs for switches
        injectLabHubStateChange(idx, isOn) {
            // 🛡️ GHOST CLICK GUARD:
            if (this.state.devices[idx] === null) {
                console.warn(`[UI Guard] Blocked browser ghost click for IDX ${idx}. System still syncing.`);
                return;
            }

            const targetState = isOn ? "ON" : "OFF";

            if (this.state.devices[idx] === targetState) {
                return;
            }

            this.dispatchEvent("HUB_STATE_CHANGED", { idx: parseInt(idx, 10), state: targetState });
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

        // 🛡️ Hardware Bus Safety Interceptor
        handleHardwareToggleClick(event) {
            event.preventDefault(); // Stop the toggle from visually flipping
            document.getElementById('hardware_mode_modal').showModal();
        },

        // Executed only if the user confirms the bus switch
        confirmHardwareModeToggle() {
            document.getElementById('hardware_mode_modal').close();
            this.toggleHardwareMode();
        },

        injectWaterPulse(fluidType) {
            // Injects 396 pulses = exactly 1 liter for lab testing
            this.dispatchEvent("WATER_PULSE", { fluid: fluidType, count: 396, lab_override: true });
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
            this.dispatchEvent("TEST_ALERT_INJECTED", { msg_text: msg });
        },

        async requestSystemSweep() {
            if (this.sweepRunning) return;
            this.sweepRunning = true;

            this.dispatchEvent("TEST_ALERT_INJECTED", { msg_text: "🧹 System sweep running..." });

            await this.dispatchEvent("SYSTEM_SWEEP_REQUESTED");

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

            this.dispatchEvent("TEST_ALERT_INJECTED", { msg_text: "🔄 Reloading config.yaml configurations..." });

            await this.dispatchEvent("CONFIG_RELOAD_REQUESTED");

            setTimeout(() => {
                if (this.configReloading) {
                    this.configReloading = false;
                    console.warn("UI Guard: Config reload lock released via timeout failsafe.");
                }
            }, 10 * 1000);
        }
    };
}