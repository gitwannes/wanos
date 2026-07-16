# WanOS Hue Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Hue integration acts as an **Active HTTP/2 Integration**. It establishes a continuous, bidirectional local connection to the physical Philips Hue Bridge using the modern V2 CLIP API[cite: 11].

## 1. The Boot & Connection Phase (Turning it ON)
When toggled to **ON**, the `start()` method is invoked inside `HueLocalBridge`[cite: 11].

*   **Translation Maps:** It clears and rebuilds its internal O(1) translation dictionaries (`idx_to_uuid`, `idx_to_group_uuid`) directly from `config.yaml`[cite: 11].
*   **SSL Bypass:** Because local Hue hubs use self-signed certificates, it configures a specialized `aiohttp.TCPConnector` that explicitly ignores SSL verification[cite: 11].
*   **The Initial Sync:** It pauses the boot sequence to perform a massive REST GET sweep (`_sync_initial_state()`)[cite: 11]. It downloads all Rooms, Zones, Scenes, Lights, and Grouped Lights to perfectly synchronize the WanOS UI names and slider positions before going live[cite: 11].

## 2. The Continuous Listening Loop (Server-Sent Events)
Instead of polling the Hue hub for changes, WanOS opens a persistent HTTP/2 Server-Sent Events (SSE) stream to `/eventstream/clip/v2`[cite: 11].

*   **Zero-Latency Telemetry:** This socket stays open infinitely[cite: 11]. If a user presses a physical Zigbee wall switch, the Hue hub pushes the JSON payload down the stream instantly[cite: 11].
*   **Infinite Echo Guard:** When WanOS receives a live update from the SSE stream, it updates the UI and tags the event with `origin: "hue"`[cite: 11]. The outbound command handler explicitly ignores these events to prevent bouncing commands back to the bridge in an infinite loop[cite: 11].

## 3. Triggering Outbound Commands
When a UI interaction occurs, the `_on_state_changed` callback intercepts it[cite: 11].

*   **Data Translation:** It identifies if the target is a Light, a Group (Room/Zone), or a Scene[cite: 11].
*   **100% Clamping:** The backend enforces a strict `0.0` to `100.0` float constraint for brightness[cite: 11]. This prevents legacy `254` integer commands (from V1 API automations) from triggering HTTP 400 Bad Request errors[cite: 11].
*   **Multicast Scenes:** When a Hue Scene is triggered, WanOS sends an `"action": "active"` PUT request to the Scene UUID[cite: 11]. This natively utilizes Zigbee multicast to change the entire room's lights simultaneously without the "popcorn effect"[cite: 11].

## 4. Restarting & Hot-Reloading
Because Hue is an active stream with complex translation tables, it handles configuration reloads (`config.yaml` changes) uniquely[cite: 7].

*   **Atomic Recycle:** Inside `system_handlers.py`, when a reload is requested, the system explicitly calls `await manager.hue_bridge.stop()`, injects the new configuration, clears the translation maps via `_initialize_mappings()`, and calls `start()` again to re-sync the entire ecosystem[cite: 7, 11].

## 5. The Health Monitor (The Auto-Kill Procedure)
*   **SSE Validation:** The `HealthMonitor` checks the integration's health by evaluating `sm.hue_bridge.is_connected`[cite: 3]. This boolean is directly tied to the integrity of the SSE loop[cite: 11]. If the HTTP stream collapses, the boolean flips to `False`[cite: 11].
*   **The Auto-Kill:** After 3 strikes (6 seconds) of stream failure, the Health Monitor forces the integration OFF[cite: 3].

## 6. Turning the Integration OFF
*   The `stop()` method flips an `asyncio.Event` (`_stop_event`)[cite: 11].
*   The infinite SSE listener loop detects the flag, gracefully breaks, and explicitly closes the `aiohttp` session to sever the connection to the physical bridge[cite: 11].