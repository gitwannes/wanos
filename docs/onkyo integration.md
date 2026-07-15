# WanOS Onkyo Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Onkyo integration acts as a highly resilient, asynchronous **persistent bridge**. Below is the step-by-step lifecycle of exactly how WanOS manages the receivers.

## 1. The Boot & Connection Phase (Turning it ON)
When the Onkyo integration is toggled to **ON** in the WanOS Admin UI (or when the system autostarts), it dispatches an `ONKYO_TOGGLED` event. This triggers the `start()` method inside the `OnkyoBridge`.

*   **Task Spawning:** The bridge reads the `device_map` from `config.yaml` and spawns an independent, background `_receiver_loop` task for each receiver.
*   **The Persistent Socket:** The script attempts to open a TCP connection to the receiver on port `60128`. **This connection is kept open indefinitely.** It is a persistent, zero-latency socket designed to instantly catch manual volume knob twists or HDMI CEC wakeups.

## 2. The Initial Query Sequence
The moment the TCP socket connects successfully, the bridge actively interrogates the receiver to sync the UI.

1.  It immediately pushes a placeholder `"OFF"` state to the UI to clear any "SYNC..." loading text.
2.  It waits exactly **0.5 seconds** to allow the receiver's network card to stabilize.
3.  It sends the Power Status query (`!1PWRQSTN`).
4.  It waits exactly **0.2 seconds**, then sends the Master Volume query (`!1MVLQSTN`).

## 3. The Continuous Listening Loop
After the initial queries, the bridge enters an infinite `while self._running:` loop.

*   **Chunk Reading:** It sits quietly and reads the open TCP stream in 256-byte chunks.
*   **Sliding Frame Buffer:** Because TCP streams can fragment, it uses a sliding frame buffer to hunt for the `ISCP` magic word, mathematically calculate the exact payload size, and extract the messages cleanly.

## 4. Failure, Disconnection, and Reconnecting
If the receiver loses Wi-Fi, loses power, or drops the TCP socket, the script handles it aggressively:

*   **Instant Death Detection:** If the TCP reader returns empty data or throws an exception (like a `TimeoutError`), the bridge instantly breaks the listening loop.
*   **UI Update:** It removes the receiver from its internal active registry and immediately dispatches a `"DEAD"` state to the WanOS UI.
*   **The Reconnect Loop:** The script sleeps for exactly **5.0 seconds**. After 5 seconds, the loop cycles back to the top and attempts to open a brand-new TCP socket. It retries this every 5 seconds infinitely, for as long as the integration remains "ON".

## 5. The Health Monitor (The Auto-Kill Procedure)
Completely outside of the `onkyo.py` script, WanOS runs a global `HealthMonitor` background worker that audits the entire system every **2.0 seconds**.

*   **The 8-Second Grace Period:** When the Onkyo bridge first starts, the Health Monitor gives it an 8-second grace period to establish its sockets without throwing false alarms.
*   **The Strike System:** If the Health Monitor detects that the Onkyo bridge has no active receivers connected, it issues a "strike". 
*   **The Auto-Kill:** If the bridge accumulates **3 strikes (6 seconds total)** of complete disconnection, the Health Monitor actively intervenes. It fires an emergency payload to disable the integration completely and logs: *"Onkyo connection lost after 3 retries. Integration disabled."*

## 6. Turning the Integration OFF
If the integration is manually turned **OFF** in the UI (or if the Health Monitor kills it):

*   The `stop()` method is called.
*   The `_running` flag is flipped to `False`, commanding the infinite retry loops to die.
*   It iterates through every actively open TCP socket, executes a `writer.close()`, and safely hangs up the connection.