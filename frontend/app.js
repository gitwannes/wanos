// --- file: frontend/app.js ---

function wanosApp() {
    return {
        // Local reactive proxy matching the SystemState model
        state: {
            sauna: {
                active: false,
                current_temp: null,
                target_temp: 80,
                modulation_pwm: 0,
                phases_pwm: [0, 0, 0],
                current_humidity: null,
                door_open: false,
                hold_mode: "autohold",
                session_start_time: null,
                session_end_time: null,
                light_color: "#FFD180",
                lcd_text: "",
                ventilation_state: "OFF",
                ventilation_deadline: null
            },
            hardware: { live_mode: false }
        },

        // Lab mode interactive bounds
        mockTemp: 20.0,
        mockHum: 50.0,
        mockDoorOpen: false,

        // Local UI Ticker Variables
        elapsedText: "00:00:00",
        remainingText: "00:00:00",
        progressPercent: 0,
        ventRemainingText: "00:00",

        init() {
            console.log("🚀 WISC Web Engine initializing...");
            this.connectSSE();

            // Start the local metronome to process absolute backend timestamps
            setInterval(this.ticker.bind(this), 1000);
        },

        connectSSE() {
            const eventSource = new EventSource("/api/state/sse");

            eventSource.onmessage = (event) => {
                try {
                    this.state = JSON.parse(event.data);

                    // Sync mock sliders if they aren't actively being dragged
                    if (this.state.sauna.current_temp !== null && document.activeElement !== document.querySelector('.range-warning')) {
                        this.mockTemp = this.state.sauna.current_temp;
                    }
                    if (this.state.sauna.current_humidity !== null && document.activeElement !== document.querySelector('.range-info')) {
                        this.mockHum = this.state.sauna.current_humidity;
                    }
                    this.mockDoorOpen = this.state.sauna.door_open;
                } catch (err) {
                    console.error("⚠️ Failed parsing state snapshot:", err);
                }
            };

            eventSource.onerror = (err) => {
                console.error("❌ SSE connection dropped. Re-linking in 3s...");
                eventSource.close();
                setTimeout(() => this.connectSSE(), 3000);
            };
        },

        /**
         * Local UI Ticker: Runs 1x per second to render backend Unix timestamps smoothly.
         */
        ticker() {
            const now = Math.floor(Date.now() / 1000); // Current Unix Timestamp in seconds

            // 1. Process Main Sauna Session Timers
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

            // 2. Process Ventilation Cooldown Timers
            if (this.state.sauna.ventilation_state !== "OFF" && this.state.sauna.ventilation_deadline) {
                const vRemain = Math.max(0, this.state.sauna.ventilation_deadline - now);
                this.ventRemainingText = this.formatTime(vRemain).substring(3); // Just MM:SS
            } else {
                this.ventRemainingText = "00:00";
            }
        },

        formatTime(totalSeconds) {
            const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
            const s = (Math.floor(totalSeconds) % 60).toString().padStart(2, '0');
            return `${h}:${m}:${s}`;
        },

        // --- Event Dispatchers ---
        async dispatchEvent(eventType, payload = {}) {
            try {
                await fetch("/api/event", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ type: eventType, payload: payload })
                });
            } catch (error) {
                console.error(`💥 Failed dispatching [${eventType}]:`, error);
            }
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

        toggleDoor() {
            this.dispatchEvent("DOOR_CHANGED", { is_open: this.mockDoorOpen });
        },

        injectTemperature() {
            this.dispatchEvent("TEMP_UPDATED", { value: parseFloat(this.mockTemp) });
        },

        injectHumidity() {
            this.dispatchEvent("HUMIDITY_UPDATED", { value: parseFloat(this.mockHum) });
        }
    }
}