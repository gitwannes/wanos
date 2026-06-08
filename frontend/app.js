// --- file: frontend/app.js ---

function wanosApp() {
    return {
        connected: false, // Prevents early UI interactions on load

        // Local reactive proxy matching the core SystemState Pydantic model exactly
        state: {
            environment: {
                outside_temp: null,
                outside_hum: null,
                bathroom_temp: null,
                bathroom_hum: null,
                bathroom_vent_on: false,
                cinema_temp: null,
                cinema_hum: null,
                sauna_high_temp: null,
                sauna_high_hum: null,
                sauna_low_temp: null,
                sauna_low_hum: null,
                sauna_calc_temp: null,
                sauna_calc_hum: null,
                sauna_extraction_vent_on: false
            },
            sauna: {
                active: false,
                target_temp: 70, // Safe range-slider initialization baseline
                current_temp: null,
                current_humidity: null,
                door_open: false,
                hold_mode: "autohold",
                modulation_pwm: 0,
                phases_pwm: [0, 0, 0],
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
                water_cold_liters: 0.0,
                water_hot_liters: 0.0,
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
            lab_seed: null
        },

        // Explicit interactive models for Lab Mode override interfaces
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

        // Local UI Countdown String Tickers
        elapsedText: "00:00:00",
        remainingText: "00:00:00",
        progressPercent: 0,
        ventRemainingText: "00:00:00",
        irRemainingText: "00:00:00",
        doucheElapsedText: "00:00:00",

        init() {
            console.log("🚀 WanOS Web Controller initializing...");
            this.connectSSE();
            setInterval(this.ticker.bind(this), 1000); // Start system clock tracking
        },

        connectSSE() {
            const eventSource = new EventSource("/api/state/sse");

            eventSource.onmessage = (event) => {
                try {
                    const parsedState = JSON.parse(event.data);

                    // --- ANTI-FLICKER SANITIZATION GATEWAY ---
                    // Map empty phase elements cleanly to 0% to protect the progress bars
                    if (!parsedState.sauna.phases_pwm) {
                        parsedState.sauna.phases_pwm = [0, 0, 0];
                    } else {
                        parsedState.sauna.phases_pwm = parsedState.sauna.phases_pwm.map(v =>
                            (v === null || v === undefined || isNaN(v)) ? 0 : v
                        );
                    }

                    if (!parsedState.hardware.sensor_errors) parsedState.hardware.sensor_errors = [];

                    // Save values to active viewport memory
                    this.state = parsedState;

                    // Sync lab mode sliders if the user isn't currently dragging one
                    if (!document.activeElement || !document.activeElement.classList.contains('lab-slider')) {
                        this.syncLabControls();
                    }

                    // 🟢 Drop the network overlay mask only after the DOM is ready
                    this.connected = true;

                } catch (err) {
                    console.error("⚠️ Failed parsing network state update:", err);
                }
            };

            eventSource.onerror = (err) => {
                this.connected = false; // Connection severed, raise loading screen instantly
                console.error("❌ SSE stream broke. Re-linking context in 3s...");
                eventSource.close();
                setTimeout(() => this.connectSSE(), 3000);
            };
        },

        ticker() {
            const now = Math.floor(Date.now() / 1000);

            // Sauna Session Clocks
            if (this.state.sauna.active && this.state.sauna.session_start_time && this.state.sauna.session_end_time) {
                const start = this.state.sauna.session_start_time;
                const end = this.state.sauna.session_end_time;
                const elapsed = Math.max(0, now - start);
                const remaining = Math.max(0, end - now);
                const totalDuration = end - start;

                this.elapsedText = this.formatTime(elapsed);
                this.remainingText = this.formatTime(remaining);
                this.progressPercent = totalDuration > 0 ? Math.min(100, (elapsed / totalDuration) * 100) : 0;
            } else {
                this.elapsedText = "00:00:00";
                this.remainingText = "00:00:00";
                this.progressPercent = 0;
            }

            // Cooldown Ventilation Clocks
            if (this.state.sauna.ventilation_state !== "OFF" && this.state.sauna.ventilation_deadline) {
                const vRemain = Math.max(0, this.state.sauna.ventilation_deadline - now);
                this.ventRemainingText = this.formatTime(vRemain);
            } else {
                this.ventRemainingText = "00:00:00";
            }

            // Infrared Timers
            if (this.state.ir.active && this.state.ir.session_end_time) {
                const irRemain = Math.max(0, this.state.ir.session_end_time - now);
                this.irRemainingText = this.formatTime(irRemain);
            } else {
                this.irRemainingText = "00:00:00";
            }

            // Douche Flow Trackers
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

        syncLabControls() {
            const env = this.state.environment;
            const seed = this.state.lab_seed;

            if (!seed) return;

            this.labDoorSaunaOpen = this.state.sauna.door_open;
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
                ui_override: true
            };
            this.dispatchEvent(eventType, payload);
        },

        toggleSauna() {
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
            const action = this.state.ir.active ? "IR_OFF" : "IR_ON";
            this.dispatchEvent(action);
        },

        toggleHardwareMode() {
            const nextMode = !this.state.hardware.live_mode;
            this.dispatchEvent("HARDWARE_LIVE_MODE_CHANGED", { live: nextMode });
        },

        injectLabDoorChange() {
            this.dispatchEvent("DOOR_CHANGED", { sensor_id: "sauna", is_open: this.labDoorSaunaOpen });
        }
    }
}