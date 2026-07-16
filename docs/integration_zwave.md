# WanOS Z-Wave Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Z-Wave integration acts as a **lazy, event-driven MQTT bridge**[cite: 7]. Rather than actively polling devices over TCP or HTTP, it relies entirely on the local Z-Wave JS UI MQTT broker to push state changes[cite: 7]. Below is the step-by-step lifecycle of how WanOS manages the Z-Wave network.

## 1. The Boot & Connection Phase (Silent Standby)
When the WanOS backend boots, the `ZWaveJSUIBridge` is instantiated, but it does not immediately subscribe to device telemetry[cite: 7]. 

*   **Silent Standby:** The bridge subscribes exclusively to the Z-Wave JS UI driver status (`driver/status`) and an out-of-band data plane heartbeat (`_EVENTS/+/controller/statistics_updated`)[cite: 7]. 
*   **Lazy Boot:** The integration waits for two distinct hardware flags to become `True`: the physical USB stick connection (`zwave_hardware_connected`) and the MQTT engine status (`is_mqtt_engine_alive`)[cite: 7]. Only when both are verified does the bridge parse `config_zwave.yaml` to map the network[cite: 7].
*   **Armed Subscription:** Once the UI master toggle enables the integration, the bridge opens the telemetry stream (`zwave/#`) to actively listen for node updates[cite: 7].

## 2. Protocol Variations: Command Classes
Unlike integrations that abstract device complexity, the Z-Wave bridge natively parses raw Z-Wave Command Classes (CC)[cite: 7]:

*   **CC 37:** Binary Switches[cite: 7].
*   **CC 38:** Multilevel Switches (Blinds / Dimmers)[cite: 7].
*   **CC 48:** Binary Sensors (Physical Motion Transceivers / Tamper Flags)[cite: 7].
*   **CC 49:** Multilevel Sensors (Live Wattage Power, Air Temperature, Illuminance Lux)[cite: 7].
*   **CC 50:** Meters (Electric Meters and Line Voltage Monitors)[cite: 7].

## 3. The Mapping & Seeding Sequence
When the hardware is fully detected and mapped, the bridge performs an atomic RAM injection[cite: 7]:

*   **Ghost Buster (Orphan Purge):** It compares the newly loaded config against the RAM dictionary[cite: 7]. If a previously mapped Z-Wave node is no longer in the configuration, the bridge dynamically purges it from memory and dispatches a `None` state to erase it from the frontend instantly[cite: 7].
*   **Metadata Seeding:** It evaluates the configuration path strings to assign specific UI semantics[cite: 7]. For example, `73xxx` blocks are mapped as `blinds`, `74xxx` as `power`, and explicit node paths (like `66561`) are mapped as `sensor` to prevent AC Line Voltage monitors from rendering as toggle switches[cite: 7].
*   **"Sync..." Placeholder:** It forces the frontend to render the newly mapped devices instantly with a `"Sync..."` state[cite: 7].

## 4. UI Quirks & State Synchronization
The Z-Wave bridge incorporates several specialized routing mechanisms to handle hardware quirks and UI representations[cite: 7].

*   **100% Clamping (CC 38):** Hardware Z-Wave dimmers and blinds max out at an internal byte limit of `99`[cite: 7]. The bridge explicitly intercepts a `99` value and translates it to `100` so the WanOS UI sliders show a perfect 100%[cite: 7]. When a user sends a `100%` command, the bridge translates it back to `99` before MQTT transmission[cite: 7].
*   **Dual-Dispatch (Power & Sensors):** For sensors reporting power (W), temperature (°C), or humidity (%), the bridge dispatches two distinct events simultaneously[cite: 7]. One routes the raw float for background math engines (`POWER_UPDATED`, `TEMP_UPDATED`), while the other routes a pre-formatted string (e.g., `233.0 V` or `15 W`) directly to the Device Explorer UI (`HUB_STATE_CHANGED`)[cite: 7].
*   **Infinite Echo Guard:** If an outbound command originates from `zwave` itself, the bridge silently drops it to prevent bouncing commands back into the MQTT broker, unless explicitly flagged with `force: True`[cite: 7].
*   **Read-Only Safety Interlock:** To protect foundational hardware, the bridge explicitly intercepts and drops unauthorized outbound switch commands to the master 5V and 12V safety relays (IDXs `71036` and `71040`)[cite: 7].

## 5. The Continuous Listening Loop (The Inbox)
While armed, the bridge parses all incoming MQTT JSON payloads[cite: 7]. 

*   **The Inbox Interceptor:** If the bridge receives telemetry from a node that is *not* currently mapped in `config_zwave.yaml`, it filters out generic network noise (Node 1 Controller pings) and forwards actionable Command Classes (like a new motion sensor) directly to the WanOS "Inbox" via a `ZWAVE_DISCOVERY` event for UI provisioning[cite: 7].

## 6. Failure, Disconnection, and Reconnecting
Because Z-Wave relies on a fragile chain of hardware and software, the bridge handles failures at the specific node level[cite: 7]:

*   **Dead Node Interceptor:** The bridge actively listens for paths ending in `/status`[cite: 7]. If the Z-Wave JS controller reports a node status as `"dead"`, the bridge instantly updates the UI state for that specific node to `"DEAD"`[cite: 7].

## 7. The Health Monitor (The Auto-Kill Procedure)
Completely outside of the `zwave.py` script, the global `HealthMonitor` audits Z-Wave's entire multi-tiered architecture every 2.0 seconds[cite: 7].

*   **Tier 1 (Physical):** Checks if the actual USB stick file path (`/dev/serial/by-id/...`) exists on the host Linux OS[cite: 7].
*   **Tier 2 (Control Plane):** Attempts a TCP ping against the Z-Wave JS UI Web Server on port `8091`[cite: 7].
*   **Tier 3 (Data Plane):** Checks if the MQTT engine is alive and verifies that a controller heartbeat was received within the last 90 seconds[cite: 7].
*   **The Auto-Kill Execution:** USB disconnections are treated as instantly fatal (1 strike)[cite: 7]. Web UI or Data Stream freezes are granted a minor grace period (3 strikes / 6 seconds)[cite: 7]. If the threshold is breached, the monitor disables the integration and alerts the UI with the precise failure reason (e.g., *"Z-Wave Data Stream Frozen"*)[cite: 7].

## 8. Turning the Integration OFF
If the integration is manually turned **OFF** in the UI (or if the Health Monitor kills it):

*   The internal `_integration_enabled` flag is flipped to `False`[cite: 7].
*   The bridge immediately stops parsing inbound MQTT payloads and drops any pending outbound commands[cite: 7].
*   The core engine retains the UI elements but stops updating their statuses until the connection is restored[cite: 7].

## 9. Migration & Middleware Deployment Blueprint
To decouple hardware polling overhead from the core WanOS execution loop, the Z-Wave controller is driven by a containerized Z-Wave JS UI instance[cite: 6]. Below is the architecture for migrating from legacy environments (like Domoticz) to the modern middleware[cite: 6].

### 9.1 Pre-Migration Data Extraction
Before modifying hardware, you must extract human-readable mappings since the Z-Wave chip only stores numerical Node IDs[cite: 6].
1. **Node Mapping Table:** Document the correlation between the Z-Wave Node ID and your custom Friendly Name (e.g., `kerstverl_achter`) from your legacy system[cite: 6].
2. **Multi-Function Nodes:** Identify nodes containing multiple properties (Switch, Watts, kWh) under identical IDs to map them cleanly into the new UI[cite: 6].

### 9.2 Hardware Preparation
To grant the Z-Wave card exclusive serial lanes, the Pi's onboard Bluetooth must be disabled[cite: 6].
1. Edit `/boot/config.txt` and append[cite: 6]:
   ```text
   dtoverlay=disable-bt
   enable_uart=1
   ```
2. Edit `/boot/cmdline.txt` and remove all instances of `console=serial0`[cite: 6].
3. Execute `sudo reboot` to enforce kernel changes[cite: 6].
4. Unplug the legacy RaZberry GPIO card or verify the path of the new USB Stick via `ls -l /dev/serial/by-id/`[cite: 6].

### 9.3 Docker & Z-Wave JS UI Deployment
The middleware runs as a privileged Docker container bound to the host network[cite: 6].
1. **Install Docker Engine:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   curl -fsSL [https://get.docker.com](https://get.docker.com) -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```
2. **Deploy the Container:**
   ```bash
   docker run -d \
     --name zwave-js-ui \
     --restart always \
     --privileged \
     --network host \
     -v /opt/zwave-js-ui:/usr/src/app/store \
     --device /dev/serial/by-id/usb-Nabu_Casa_ZWA-2_1CDBD4AF8A6C-if00:/dev/zwave \
     zwavejs/zwave-js-ui:latest
   ```

### 9.4 Diagnostic & Deployment Checks
Use these commands to verify the middleware is running and routing correctly[cite: 6]:
```bash
ss -tulpn | grep 8091  # Verify Web UI port is open
docker ps              # Check container status
docker logs zwave-js-ui # Inspect startup logs
tail /opt/zwave-js-ui/logs/zwavejs_current.log -n 50 -f # Tail application logs
```

### 9.5 Hardware Upgrading (NVM Cloning)
To upgrade from an old RaZberry card to a modern 700/800-series USB Stick without re-pairing nodes[cite: 6]:
1. **Backup:** In the Z-Wave JS UI, go to Actions > Advanced Actions > NVM Management and generate an `NVM_backup.bin`[cite: 6]. Export `nodes.json` from the settings[cite: 6].
2. **Swap:** Power down, remove the GPIO card, insert the modern Z-Wave USB stick (preferably using a short USB extension cable to reduce EMF interference), and power back on[cite: 6].
3. **Restore:** In Settings > Z-Wave, update the serial port path (derived from `ls -l /dev/serial/by-id/`), then use NVM Management to upload the backup `.bin` file[cite: 6]. Import `nodes.json` to restore friendly names[cite: 6].

### 9.6 MQTT Gateway Configuration
Configure Z-Wave JS UI to broadcast decentralized state topics[cite: 6]:
1. Go to **Settings > MQTT** and point to `mqtt://127.0.0.1` (Port 1883)[cite: 6].
2. In **Gateway Settings**, set the Topic Prefix to `zwave` and enable `Use Node Names: True`[cite: 6].
3. Sensors will begin streaming to the local broker, ready to be ingested by WanOS[cite: 6]:
   ```text
   zwave/kerstverl_achter/switch_binary/endpoint_0/currentValue -> {"value": true, "time": 1782200000}
   ```