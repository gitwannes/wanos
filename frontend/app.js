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
                app_uptime_formatted: "00:00:00"
            },
            environment: {
                outside_temp: null,
                outside_hum: null,
                bathroom_temp: null,
                bathroom_hum: null,
                door_bathroom_open: false,
                cinema_temp: null,
                cinema_hum: null,
                sauna_high_temp: null,
                sauna_high_hum: null,
                sauna_low_temp: null,
                sauna_low_hum: null,
                sauna_calc_temp: null,
                sauna_calc_hum: null,
            },
            sauna: {
                active: false,
                target_temp: 70,
                current_temp: null,
                max_temp: null,
                current_humidity: null,
                door_open: false,
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
                // Liters pre-rounded by the backend (1 decimal). No conversion needed here.
                water_cold_liters: 0.0,
                water_hot_liters: 0.0,
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
                safety_pin_active: false,
                sensor_errors: []
            },
            devices: {}, // Generic peripheral payload dict (hues, ventilators, relays)
            lab_seed: null
        },

        labSaunaHighTemp: null,
        labSaunaHighHum: null,
        labSaunaLowTemp: null,
        labSaunaLowHum: null,
        labBathroomTemp: null,
        labBathroomHum: null,
        labCinemaTemp: null,
        labCinemaHum: null,
        labOutsideTemp: null,
        labOutsideHum: null,
        labDoorSaunaOpen: false,
        labDoorBathroomOpen: false,
        labCinemaHueOn: false,
        labSaunaHueOn: false,
        labBathroomVentOn: false,

        elapsedText: "00:00:00",
        remainingText: "00:00:00",
        progressPercent: 0,
        ventRemainingText: "00:00:00",
        irRemainingText: "00:00:00",
        doucheElapsedText: "00:00:00",

        init() {
            console.log("🚀 WanOS Web Controller initializing...");
            this.connectSSE();
            setInterval(this.ticker.bind(this), 1000);
        },

        async fetchFullSnapshot() {
            // Fetches the complete state from /api/state and replaces the local store.
            // Called on first connect and on every reconnect to guarantee full sync
            // before delta updates resume.
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
            fullState.environment.door_bathroom_open = fullState.environment.door_bathroom_open ?? false;
            fullState.system = fullState.system || this.state.system;
            fullState.devices = fullState.devices || {};

            this.state = fullState;

            if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                this.syncLabControls();
            }
        },

        _applyDomainDelta(domain, data) {
            // Merges a single changed domain subtree into the reactive store.
            // Per-domain defensive normalization mirrors _applyFullSnapshot.
            if (domain === "sauna") {
                if (data.phases_pwm) {
                    data.phases_pwm = data.phases_pwm.map(v =>
                        (v === null || v === undefined || isNaN(v)) ? 0 : v
                    );
                }
                data.modulation_pwm = data.modulation_pwm ?? 0;
            }
            if (domain === "environment") {
                data.door_bathroom_open = data.door_bathroom_open ?? false;
            }
            if (domain === "hardware") {
                if (!data.sensor_errors) data.sensor_errors = [];
            }
            if (domain === "devices") {
                // Merge device keys individually rather than replacing the whole object,
                // so keys not present in this delta are preserved from prior state.
                this.state.devices = Object.assign({}, this.state.devices, data);
                return;
            }

            this.state[domain] = Object.assign({}, this.state[domain], data);

            // Re-sync lab controls whenever environment or sauna domain updates arrive
            if ((domain === "environment" || domain === "sauna") &&
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

                // Arm watchdog immediately on link orchestration
                resetWatchdog();

                eventSource.onmessage = (event) => {
                    try {
                        // Any incoming data frame proves the underlying pipeline is alive
                        resetWatchdog();

                        const msg = JSON.parse(event.data);

                        // If it's a keep-alive frame, intercept and return early without altering UI metrics
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

            if (this.state.sauna.active && this.state.sauna.session_start_time && this.state.sauna.session_end_time) {
                const start = this.state.sauna.session_start_time;
                const end = this.state.sauna.session_end_time;

                if (end < 1000000000) {
                    // Timer not yet triggered: session_end_time holds raw duration seconds,
                    // not an absolute Unix timestamp. Display as countdown without progress bar.
                    this.elapsedText = this.formatTime(Math.max(0, now - start));
                    this.remainingText = this.formatTime(end);
                    this.progressPercent = 0;
                } else {
                    // Timer triggered: session_end_time is an absolute Unix timestamp.
                    const elapsed = Math.max(0, now - start);
                    const remaining = Math.max(0, end - now);
                    const totalDuration = end - start;

                    this.elapsedText = this.formatTime(elapsed);
                    this.remainingText = this.formatTime(remaining);
                    this.progressPercent = totalDuration > 0 ? Math.min(100, (elapsed / totalDuration) * 100) : 0;
                }
            } else {
                this.elapsedText = "00:00:00";
                this.remainingText = "00:00:00";
                this.progressPercent = 0;
            }

            if (this.state.sauna.ventilation_state !== "OFF" && this.state.sauna.ventilation_deadline) {
                const vRemain = Math.max(0, this.state.sauna.ventilation_deadline - now);
                this.ventRemainingText = this.formatTime(vRemain);
            } else {
                this.ventRemainingText = "00:00:00";
            }

            if (this.state.ir.active && this.state.ir.session_end_time) {
                const irRemain = Math.max(0, this.state.ir.session_end_time - now);
                this.irRemainingText = this.formatTime(irRemain);
            } else {
                this.irRemainingText = "00:00:00";
            }

            if (this.state.metrics.douche_active && this.state.metrics.douche_start_time) {
                const dElapsed = Math.max(0, now - this.state.metrics.douche_start_time);
                this.doucheElapsedText = this.formatTime(dElapsed);
            } else if (this.state.metrics.douche_duration_secs > 0) {
                this.doucheElapsedText = this.formatTime(this.state.metrics.douche_duration_secs);
            } else {
                this.doucheElapsedText = "00:00:00";
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

            // Combine into unified output format
            return `${durationStr} (${bootStr})`;
        },

        syncLabControls() {
            const env = this.state.environment;
            const seed = this.state.lab_seed;

            if (!seed) return;

            this.labDoorSaunaOpen = this.state.sauna.door_open;
            this.labDoorBathroomOpen = env.door_bathroom_open;
            this.labCinemaHueOn = this.state.devices.cinema_hue === 'ON';
            this.labSaunaHueOn = this.state.devices.sauna_hue === 'ON';
            this.labBathroomVentOn = this.state.devices.bathroom_ventilator === 'ON';

            this.labSaunaHighTemp = env.sauna_high_temp ?? seed.sauna_high_temp;
            this.labSaunaHighHum  = env.sauna_high_hum  ?? seed.sauna_high_hum;
            this.labSaunaLowTemp  = env.sauna_low_temp  ?? seed.sauna_low_temp;
            this.labSaunaLowHum   = env.sauna_low_hum   ?? seed.sauna_low_hum;
            this.labBathroomTemp  = env.bathroom_temp   ?? seed.bathroom_temp;
            this.labBathroomHum   = env.bathroom_hum    ?? seed.bathroom_hum;
            this.labCinemaTemp    = env.cinema_temp     ?? seed.cinema_temp;
            this.labCinemaHum     = env.cinema_hum      ?? seed.cinema_hum;
            this.labOutsideTemp   = env.outside_temp    ?? seed.outside_temp;
            this.labOutsideHum    = env.outside_hum     ?? seed.outside_hum;
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

        injectLabMetric(eventType, sensorId, targetValue) {
            const payload = {
                sensor_id: sensorId,
                value: eventType === "TEMP_UPDATED" ? parseFloat(targetValue) : parseInt(targetValue),
                lab_override: true
            };
            this.dispatchEvent(eventType, payload);
        },

        toggleSauna() {
            if (this.state.sauna.current_temp == null) {
                console.warn("UI locked: Cannot start Sauna without valid temperature data.");
                return;
            }
            const action = this.state.sauna.active ? "SAUNA_OFF" : "SAUNA_ON";
            this.dispatchEvent(action);
        },

        updateSetpoint() {
            this.dispatchEvent("SETPOINT_CHANGED", { target: parseFloat(this.state.sauna.target_temp) });
        },

        toggleHold() {
            this.dispatchEvent("HOLD_TOGGLED");
        },

        adjustTimer(minutesToAdd) {
            this.dispatchEvent("TIMER_ADJUSTED", { minutes: minutesToAdd });
        },

        toggleIR() {
            if (this.state.sauna.current_temp == null) {
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

        injectLabDoorChange(doorName, isOpen) {
            this.dispatchEvent("DOOR_CHANGED", { sensor_id: doorName, is_open: isOpen });
        },

        injectLabHubStateChange(deviceId, isOn) {
            this.dispatchEvent("HUB_STATE_CHANGED", { device_id: deviceId, state: isOn ? "ON" : "OFF" });
        },

        injectWaterPulse(fluidType) {
            // Injects 396 pulses = exactly 1 liter for lab testing
            this.dispatchEvent("WATER_PULSE", { fluid: fluidType, count: 396, lab_override: true });
        },

        // ⚡ NEW FRONTEND RELOAD HOOK
        reloadFrontend() {
            console.log("♻️ Administrator triggered UI reload...");
            window.location.reload(true);
        }
    };
}
