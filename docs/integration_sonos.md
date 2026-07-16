# WanOS Sonos Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Sonos integration acts as an asynchronous, **decentralized polling bridge**. Unlike integrations that maintain open persistent TCP sockets, Sonos relies on scheduled HTTP/UPnP queries offloaded to background C-threads. Below is the step-by-step lifecycle of how WanOS manages the speakers.

## 1. The Boot & Connection Phase (Turning it ON)
When the Sonos integration is toggled to **ON** in the WanOS Admin UI (or when the system autostarts), it dispatches a `SONOS_TOGGLED` event. This triggers the `start()` method inside the `SonosBridge`.

*   **Object Instantiation:** The bridge reads the `device_map` from `config.yaml` and maps each IP address to a `soco.SoCo` object.
*   **The Polling Task:** Instead of spawning a listener for each speaker, the bridge spawns a single, unified `_poll_loop` background task that sweeps across all known speakers sequentially.

## 2. Protocol Variations: UPnP & SoCo Threading
Because the official `soco` library relies on synchronous, blocking HTTP requests (UPnP over XML), it poses a massive risk to the WanOS core: if a speaker drops off the Wi-Fi, the HTTP request could hang, instantly freezing the entire WanOS `asyncio` event loop.

*   **Thread Offloading:** To completely mitigate this, every single Sonos action (status queries, volume adjustments, play/pause commands) is executed using `asyncio.to_thread()`. This seamlessly offloads the blocking network request to a separate C-thread pool, keeping the WanOS central nervous system running at zero latency.
*   **Rich Commands:** The protocol supports passing complex, multi-attribute payloads in a single transaction (e.g., setting a specific volume, queuing a TuneIn Radio URI from the config, and asserting a PLAY state simultaneously).

## 3. The Continuous Polling Loop
Once started, the `_poll_loop` enters an infinite `while self._running:` cycle. 

*   **The 10-Second Sweep:** Every 10 seconds, the bridge iterates over every `SoCo` object.
*   **State Extraction:** It queries `get_current_transport_info` (to determine `PLAYING` vs `STOPPED`/`PAUSED`) and queries the integer `volume`.
*   **Silent Syncing:** If the speaker's physical state differs from what is stored in the WanOS RAM, it dispatches a `HUB_STATE_CHANGED` event to update the UI. It intentionally attaches an `is_initialization: True` flag to this event to suppress console logging noise, ensuring that routine background syncs don't flood the terminal.

## 4. UI Quirks & State Synchronization
The Sonos bridge aligns with WanOS's Optimistic UI but handles data differently than stateless protocols.

*   **Strict State-Diffing:** Unlike RFXCOM (which always blasts commands over the air), Sonos commands are highly stateful. The `StateManager` intercepts Sonos UI clicks and drops the event if the RAM already matches the requested state. This prevents WanOS from sending redundant `Play` commands to the UPnP API, which can cause audio buffer resets and micro-stutters.
*   **Standardized 0-100% Volume:** Unlike Onkyo's raw hexadecimal boundaries, Sonos handles volume purely on a standard 0 to 100 integer percentage scale. 
*   **Fall-Through Execution:** When parsing a command to switch radio stations, the code utilizes sequential fall-through execution. It loads the TuneIn URI first, and immediately cascades into the `play` command block to ensure playback starts instantly.

## 5. Failure, Disconnection, and Reconnecting
Because Sonos operates on a decentralized per-speaker basis, failure is handled gracefully at the granular level.

*   **Isolated Speaker Failure:** If a specific speaker is unplugged or loses Wi-Fi, the `asyncio.to_thread` HTTP request will throw a connection exception.
*   **Targeted DEAD State:** The bridge catches this exception and explicitly dispatches a `"DEAD"` state for *only that specific speaker IDX*. The rest of the Sonos network remains functional.
*   **Automatic Re-Discovery:** Because the bridge polls every 10 seconds unconditionally, the moment the speaker reconnects to the Wi-Fi, the next polling sweep will successfully read its volume and clear the `"DEAD"` state from the UI instantly.

## 6. The Health Monitor (The Auto-Kill Procedure)
Outside of the `sonos.py` script, the global `HealthMonitor` audits the overall integrity of the Sonos network.

*   **Subnet Ping:** Every 2 seconds, the monitor attempts a fast TCP ping against port `1400` on the mapped Sonos IPs. 
*   **The Strike System:** If *at least one* speaker answers the ping, the Sonos integration is considered healthy. If *zero* speakers respond, it issues a "strike".
*   **The Auto-Kill:** If the monitor accumulates **3 strikes (6 seconds total)** of complete network silence across all speakers, it intervenes, fires an emergency payload to disable the integration completely, and logs: *"Sonos connection lost after 3 retries. Integration disabled."*

## 7. Turning the Integration OFF
If the integration is manually turned **OFF** in the UI (or if the Health Monitor kills it):

*   The `stop()` method is called.
*   The `_running` flag is flipped to `False`.
*   The unified `_polling_task` is actively cancelled and awaited to guarantee clean memory garbage collection, silencing all HTTP traffic to the speakers.