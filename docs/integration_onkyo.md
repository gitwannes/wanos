# WanOS Onkyo Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Onkyo integration acts as a highly resilient, asynchronous **persistent bridge**. Below is the step-by-step lifecycle of exactly how WanOS manages the receivers, including critical protocol variations and UI synchronization logic.

## 1. The Boot & Connection Phase (Turning it ON)
When the Onkyo integration is toggled to **ON** in the WanOS Admin UI (or when the system autostarts), it dispatches an `ONKYO_TOGGLED` event. This triggers the `start()` method inside the `OnkyoBridge`.

*   **Task Spawning:** The bridge reads the `device_map` from `config.yaml` and spawns an independent, background `_receiver_loop` task for each receiver.
*   **The Persistent Socket:** The script attempts to open a TCP connection to the receiver on port `60128`. **This connection is kept open indefinitely.** It is a persistent, zero-latency socket designed to instantly catch manual volume knob twists or HDMI CEC wakeups.

## 2. Protocol Variations: Native vs. Legacy
The integration supports two distinct hardware generations, controlled by a `legacy` boolean in the configuration. 

*   **Native (Modern Cinema Receivers):** Uses perfectly standard eISCP binary TCP packets. Modern receivers process commands rapidly and strictly require the `\x1a` (EOF) byte before the `\r\n` terminator to process reliably.
*   **Legacy (2012-era Receivers, e.g., TX-NR616):** These units contain a firmware bug. The bridge employs a specific `pack_legacy_malformed` function to recreate an exact byte-for-byte legacy Node-RED JavaScript buffer (passing payload length as an ASCII string of an incorrect length, omitting the EOF byte, and using a strict `\r\n` terminator). 

## 3. The Initial Query Sequence
The moment the TCP socket connects successfully, the bridge actively interrogates the receiver to sync the UI. Timings are heavily dictated by the hardware generation to prevent "Socket Shock" (buffer overflows on older chips).

1.  It immediately pushes a placeholder `"OFF"` state to the UI to clear any "SYNC..." loading text.
2.  It waits for the receiver's network card to stabilize: **0.5 seconds** (Native) or **2.0 seconds** (Legacy).
3.  It sends the Power Status query (`!1PWRQSTN`).
4.  It strictly paces the next query: waiting **0.2 seconds** (Native) or **2.0 seconds** (Legacy).
5.  It sends the Master Volume query (`!1MVLQSTN`).

## 4. UI Quirks & State Synchronization
The Onkyo bridge employs several advanced Optimistic UI mechanisms to mask network latency and prevent race conditions.

*   **Raw Integers vs. Percentages:** The WanOS backend and Alpine.js frontend do *not* translate volume into a 0-100% scale. The UI dynamically binds its maximum slider limit directly to the `max_volume` integer defined in the config (e.g., `60`). This eliminates rounding errors and prevents the slider from snapping to incorrect values if a user physically turns the knob past a software-defined limit. **Sonos uses the same `max_volume` meta / slider / history-axis pattern** (`config.sonos.max_volume`, e.g. `70`); only the underlying protocol differs (eISCP hex vs SoCo 0–100).
*   **State Invalidation (The "SYNC..." Decoupling):** When a user turns the receiver **ON** via the UI, the frontend instantly sets the volume state to `null` while leaving the power state `ON`. This triggers an `is_syncing` flag, which visually disables the volume slider and displays "SYNC...". The slider remains physically locked until the receiver boots, answers the backend's automatic volume query, and returns its actual startup volume. When turning **OFF**, the volume cache is intentionally left intact so the UI instantly displays "OFF" without a syncing delay.
*   **The Infinite Echo Guard:** If a user physically turns the receiver's volume dial, the receiver broadcasts the change over TCP, updating the WanOS UI. To prevent the backend from blindly echoing that same volume command back to the receiver (which causes violent rubberbanding on the physical knob), the backend employs an `origin == "onkyo"` check. If the command originated from the hardware, it updates the UI but strictly aborts TCP transmission.
*   **Slider Lock TTL:** While actively dragging the volume slider, the UI applies a 2-second lock to ignore network echoes. The absolute moment the user releases the slider, this lock is dropped to `0`. This allows the blazing-fast 0.2s network reply from the receiver to instantly populate and confirm the final value.

## 5. The Continuous Listening Loop
After the initial queries, the bridge enters an infinite `while self._running:` loop.

*   **Chunk Reading:** It sits quietly and reads the open TCP stream in 256-byte chunks.
*   **Sliding Frame Buffer:** Because TCP streams can fragment, it uses a sliding frame buffer to hunt for the `ISCP` magic word, mathematically calculate the exact payload size, and extract the messages cleanly.

## 6. Failure, Disconnection, and Reconnecting
If the receiver loses Wi-Fi, loses power, or drops the TCP socket, the script handles it aggressively:

*   **Instant Death Detection:** If the TCP reader returns empty data or throws an exception (like a `TimeoutError`), the bridge instantly breaks the listening loop.
*   **UI Update:** It removes the receiver from its internal active registry and immediately dispatches a `"DEAD"` state to the WanOS UI.
*   **The Reconnect Loop:** The script sleeps for exactly **5.0 seconds**. After 5 seconds, the loop cycles back to the top and attempts to open a brand-new TCP socket. It retries this every 5 seconds infinitely, for as long as the integration remains "ON".

## 7. The Health Monitor (The Auto-Kill Procedure)
Completely outside of the `onkyo.py` script, WanOS runs a global `HealthMonitor` background worker that audits the entire system every **2.0 seconds**.

*   **The 8-Second Grace Period:** When the Onkyo bridge first starts, the Health Monitor gives it an 8-second grace period to establish its sockets without throwing false alarms.
*   **The Strike System:** If the Health Monitor detects that the Onkyo bridge has no active receivers connected, it issues a "strike". 
*   **The Auto-Kill:** If the bridge accumulates **3 strikes (6 seconds total)** of complete disconnection, the Health Monitor actively intervenes. It fires an emergency payload to disable the integration completely and logs: *"Onkyo connection lost after 3 retries. Integration disabled."*

## 8. Turning the Integration OFF
If the integration is manually turned **OFF** in the UI (or if the Health Monitor kills it):

*   The `stop()` method is called.
*   The `_running` flag is flipped to `False`, commanding the infinite retry loops to die.
*   It iterates through every actively open TCP socket, executes a `writer.close()`, and safely hangs up the connection.