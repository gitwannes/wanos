// --- file: frontend/app.js ---

function wanosApp() {
    return {
        // Local reactive proxy mirror matching the SystemState model structure
        state: {
            sauna: {
                active: false,
                current_temp: null,
                target_temp: 80,
                modulation_pwm: 0,
                phases_pwm: [0, 0, 0]
            },
            hardware: {
                live_mode: false
            }
        },
        
        // Dynamic variable bound to our Lab Mode simulation slider
        mockTemp: 20.0,

        init() {
            console.log("🚀 WISC Web Engine initializing open-source components...");
            this.connectSSE();
        },

        /**
         * Connects to the backend Server-Sent Events (SSE) broadcast pipe.
         * Keeps the UI perfectly updated with zero page refreshes.
         */
        connectSSE() {
            // Establishes the persistent event-source link to the Bouncer's stream
            const eventSource = new EventSource("/api/state/sse");

            eventSource.onmessage = (event) => {
                try {
                    const freshStateSnapshot = JSON.parse(event.data);
                    
                    // Smoothly map incoming server updates into our UI engine
                    this.state = freshStateSnapshot;
                    
                    // Keep the local lab mode slider updated unless the user is actively dragging it
                    if (this.state.sauna.current_temp !== null && document.activeElement !== document.querySelector('.range-warning')) {
                        this.mockTemp = this.state.sauna.current_temp;
                    }
                } catch (err) {
                    console.error("⚠️ Failed parsing live state snapshot chunk:", err);
                }
            };

            eventSource.onerror = (err) => {
                console.error("❌ SSE pipe dropped connection. Re-linking in 3s...", err);
                eventSource.close();
                setTimeout(() => this.connectSSE(), 3000);
            };
        },

        /**
         * Dispatches action events safely back to the universal backend router.
         */
        async dispatchEvent(eventType, payload = {}) {
            try {
                const response = await fetch("/api/event", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ type: eventType, payload: payload })
                });
                if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
            } catch (error) {
                console.error(`💥 Failed to dispatch event token [${eventType}]:`, error);
            }
        },

        /**
         * Triggers the Sauna ON/OFF command tokens
         */
        toggleSauna() {
            const nextAction = this.state.sauna.active ? "SAUNA_OFF" : "SAUNA_ON";
            this.dispatchEvent(nextAction);
        },

        /**
         * Triggers a modified target temperature setpoint modification
         */
        updateSetpoint() {
            const targetVal = parseFloat(this.state.sauna.target_temp);
            this.dispatchEvent("SETPOINT_CHANGED", { target: targetVal });
        },

        /**
         * Lab Mode Feature: Injects temperature simulation values directly 
         * into the running loop to test PID response metrics.
         */
        injectTemperature() {
            const simulatedVal = parseFloat(this.mockTemp);
            this.dispatchEvent("TEMP_UPDATED", { value: simulatedVal });
        }
    }
}