# WanOS Epson Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Epson projector integration is a **stateless, on-demand TCP bridge**. Unlike Onkyo or Hue, it does not maintain an infinite background loop or a persistent socket. It only connects to the network when explicitly commanded or audited.

## 1. The Boot & Connection Phase (Turning it ON)
When the Epson integration is toggled to **ON** in the WanOS Admin UI, it dispatches an `EPSON_TOGGLED` event[cite: 5].

*   **No Background Loop:** The `EpsonProjector` class does not spawn an `asyncio` background listener. It simply stands by in RAM[cite: 10].
*   **The UI Master Toggle:** Flipping the integration to ON simply flips the `epson_integration_enabled` boolean in the global System State[cite: 5]. 

## 2. Triggering Outbound Commands
When a user clicks the projector toggle (IDX `80001`) in the UI, the `StateManager` receives a `HUB_STATE_CHANGED` event[cite: 4].

*   **The Interceptor:** Inside `hub_handlers.py`, the core engine intercepts IDX `80001` / `entity_id` **`switch.epson`**[cite: 4]. If the integration is enabled, it spawns an ephemeral asynchronous task: `manager.epson_bridge.power(state_val)`[cite: 4].
*   **The TCP Handshake:** The bridge opens a temporary TCP socket to port `3629`[cite: 10]. It strictly sends the proprietary `EPSON_INIT` byte array (ESC/VP.net handshake), waits 0.5 seconds, and then transmits the ASCII command (`PWR ON` or `PWR OFF`) terminated by a carriage return (`\x0D`)[cite: 10].
*   **Socket Teardown:** Once the projector replies with the expected confirmation handshake, the script immediately closes the TCP socket and waits for the next command[cite: 10].

## 3. The Health Monitor (The Auto-Kill Procedure)
Because the Epson bridge does not hold a persistent socket, the global `HealthMonitor` must actively audit its availability[cite: 3].

*   **The TCP Ping:** Every 2 seconds, the Health Monitor executes `_ping_epson()`[cite: 3]. This opens a non-blocking TCP connection to port `3629` on the projector's IP[cite: 3]. It immediately closes the socket as soon as the connection succeeds[cite: 3].
*   **The Strike System:** If the projector is unplugged from the wall or drops off the Wi-Fi, the TCP ping times out[cite: 3]. 
*   **The Auto-Kill:** If the monitor accumulates **3 strikes (6 seconds total)** of TCP timeouts, it fires an emergency payload to disable the integration completely and logs: *"Epson Projector connection lost after 3 retries. Integration disabled."*[cite: 3]

## 4. Turning the Integration OFF
If the integration is manually turned **OFF** in the UI (or if the Health Monitor kills it):

*   The `epson_integration_enabled` boolean is set to `False`[cite: 5].
*   If a user tries to click the Projector toggle in the UI, `hub_handlers.py` intercepts the command, drops it entirely, and fires an alert banner: *"Epson command dropped: Integration is disabled."*[cite: 4]