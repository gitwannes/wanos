# WanOS Z-Wave Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Z-Wave integration acts as a **lazy, event-driven MQTT bridge**. Rather than actively polling devices over TCP or HTTP, it relies entirely on the local Z-Wave JS UI MQTT broker to push state changes. Below is the step-by-step lifecycle of how WanOS manages the Z-Wave network.

## 1. The Boot & Connection Phase (Silent Standby)
When the WanOS backend boots, the `ZWaveJSUIBridge` is instantiated, but it does not immediately subscribe to device telemetry. 

*   **Silent Standby:** The bridge subscribes exclusively to the Z-Wave JS UI driver status (`driver/status`) and an out-of-band data plane heartbeat (`_EVENTS/+/controller/statistics_updated`). 
*   **Lazy Boot:** The integration waits for two distinct hardware flags to become `True`: the physical USB stick connection (`zwave_hardware_connected`) and the MQTT engine status (`is_mqtt_engine_alive`). Only when both are verified does the bridge parse `config_zwave.yaml` to map the network.
*   **Armed Subscription:** Once the UI master toggle enables the integration, the bridge opens the telemetry stream (`zwave/#`) to actively listen for node updates.

## 2. Protocol Variations: Command Classes
Unlike integrations that abstract device complexity, the Z-Wave bridge natively parses raw Z-Wave Command Classes (CC):

*   **CC 37:** Binary Switches.
*   **CC 38:** Multilevel Switches (Blinds / Dimmers).
*   **CC 48:** Binary Sensors (Physical Motion Transceivers / Tamper Flags).
*   **CC 49:** Multilevel Sensors (Live Wattage Power, Air Temperature, Illuminance Lux).
*   **CC 50:** Meters (Electric Meters and Line Voltage Monitors).

## 3. The Mapping & Seeding Sequence
When the hardware is fully detected and mapped, the bridge performs an atomic RAM injection:

*   **Ghost Buster (Orphan Purge):** It compares the newly loaded config against the RAM dictionary. If a previously mapped Z-Wave node is no longer in the configuration, the bridge dynamically purges it from memory and dispatches a `None` state to erase it from the frontend instantly.
*   **Metadata Seeding:** It evaluates the configuration path strings to assign specific UI semantics. For example, `73xxx` blocks are mapped as `blinds`, `74xxx` as `power`, and explicit node paths (like `66561`) are mapped as `sensor` to prevent AC Line Voltage monitors from rendering as toggle switches.
*   **"Sync..." Placeholder:** It forces the frontend to render the newly mapped devices instantly with a `"Sync..."` state.

## 4. UI Quirks & State Synchronization
The Z-Wave bridge incorporates several specialized routing mechanisms to handle hardware quirks and UI representations.

*   **100% Clamping (CC 38):** Hardware Z-Wave dimmers and blinds max out at an internal byte limit of `99`. The bridge explicitly intercepts a `99` value and translates it to `100` so the WanOS UI sliders show a perfect 100%. When a user sends a `100%` command, the bridge translates it back to `99` before MQTT transmission.
*   **Dual-Dispatch (Power & Sensors):** For sensors reporting power (W), temperature (deg C), or humidity (%), the bridge dispatches two distinct events simultaneously. One routes the raw float for background math engines (`POWER_UPDATED`, `TEMP_UPDATED`), while the other routes a pre-formatted string (e.g., `233.0 V` or `15 W`) directly to the Device Explorer UI (`HUB_STATE_CHANGED`).
*   **Infinite Echo Guard:** If an outbound command originates from `zwave` itself, the bridge silently drops it to prevent bouncing commands back into the MQTT broker, unless explicitly flagged with `force: True`.
*   **Read-Only Safety Interlock:** To protect foundational hardware, the bridge explicitly intercepts and drops unauthorized outbound switch commands to the master 5V and 12V safety relays (IDXs `71036` and `71040`).

## 5. The Continuous Listening Loop (The Inbox)
While armed, the bridge parses all incoming MQTT JSON payloads. 

*   **The Inbox Interceptor:** If the bridge receives telemetry from a node that is *not* currently mapped in `config_zwave.yaml`, it filters out generic network noise (Node 1 Controller pings) and forwards actionable Command Classes (like a new motion sensor) directly to the WanOS "Inbox" via a `ZWAVE_DISCOVERY` event for UI provisioning.

## 6. Failure, Disconnection, and Reconnecting
Because Z-Wave relies on a fragile chain of hardware and software, the bridge handles failures at the specific node level:

*   **Dead Node Interceptor:** The bridge actively listens for paths ending in `/status`. If the Z-Wave JS controller reports a node status as `"dead"`, the bridge instantly updates the UI state for that specific node to `"DEAD"`.

## 7. The Health Monitor (The Auto-Kill Procedure)
Completely outside of the `zwave.py` script, the global `HealthMonitor` audits Z-Wave's entire multi-tiered architecture every 2.0 seconds.

*   **Tier 1 (Physical):** Checks if the actual USB stick file path (`/dev/serial/by-id/...`) exists on the host Linux OS.
*   **Tier 2 (Control Plane):** Attempts a TCP ping against the Z-Wave JS UI Web Server on port `8091`.
*   **Tier 3 (Data Plane):** Checks if the MQTT engine is alive and verifies that a controller heartbeat was received within the last 90 seconds.
*   **The Auto-Kill Execution:** USB disconnections are treated as instantly fatal (1 strike). Web UI or Data Stream freezes are granted a minor grace period (3 strikes / 6 seconds). If the threshold is breached, the monitor disables the integration and alerts the UI with the precise failure reason (e.g., *"Z-Wave Data Stream Frozen"*).

## 8. Turning the Integration OFF
If the integration is manually turned **OFF** in the UI (or if the Health Monitor kills it):

*   The internal `_integration_enabled` flag is flipped to `False`.
*   The bridge immediately stops parsing inbound MQTT payloads and drops any pending outbound commands.
*   The core engine retains the UI elements but stops updating their statuses until the connection is restored.

## 9. Migration & Middleware Deployment Blueprint
To decouple hardware polling overhead from the core WanOS execution loop, the Z-Wave controller is driven by a containerized Z-Wave JS UI instance. Below is the architecture for migrating from legacy environments (like Domoticz) to the modern middleware.

### 9.1 Pre-Migration Data Extraction
Before modifying hardware, you must extract human-readable mappings since the Z-Wave chip only stores numerical Node IDs.
1. **Node Mapping Table:** Document the correlation between the Z-Wave Node ID and your custom Friendly Name (e.g., `kerstverl_achter`) from your legacy system.
2. **Multi-Function Nodes:** Identify nodes containing multiple properties (Switch, Watts, kWh) under identical IDs to map them cleanly into the new UI.

### 9.2 Hardware Preparation & Serial UART Configuration
To grant the Z-Wave card or USB controller exclusive serial lanes, the Pi's onboard Bluetooth must be disabled.
1. Edit `/boot/config.txt` and append:
   ```text
   dtoverlay=disable-bt
   enable_uart=1
   ```
2. Edit `/boot/cmdline.txt` and remove all instances of `console=serial0`.
3. Execute `sudo reboot` to enforce kernel changes.
4. Unplug the legacy RaZberry GPIO card or verify the path of the new USB Stick via `ls -l /dev/serial/by-id/`.

### 9.3 Docker & Z-Wave JS UI Deployment
The middleware runs as a privileged Docker container bound to the host network.

1. **Install Docker Engine:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   curl -fsSL [https://get.docker.com](https://get.docker.com) -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **Option A: Direct Docker Launch Command:**
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

3. **Option B: Docker Compose Configuration (`~/wanos/docker-compose.yml`):**
   Docker Compose handles hardware path verifications, eliminates boot race conditions, and restarts the container reliably on reboot.
   ```yaml
   version: '3.7'
   services:
     zwave-js-ui:
       container_name: zwave-js-ui
       image: zwavejs/zwave-js-ui:latest
       restart: always
       privileged: true
       network_mode: host
       volumes:
         - /opt/zwave-js-ui:/usr/src/app/store
       devices:
         - /dev/serial/by-id/usb-Nabu_Casa_ZWA-2_1CDBD4AF8A6C-if00:/dev/zwave
   ```
   Deploy using: `docker compose up -d`.

### 9.4 Initial Web UI Configuration & Diagnostic Checks
1. Open a web browser and navigate to the dashboard endpoint on port `8091` (e.g., `http://10.32.251.30:8091`).
2. Navigate to **Settings > Z-Wave**:
   * **Serial Port:** Set to `/dev/ttyACM0` or your mapped `/dev/serial/by-id/` address.
   * **Z-Wave API Boot Timeout:** Set to `disabled`.
3. Click **Save**. The middleware will query controller EEPROM memory and populate active hardware node cards.
4. **Battery Devices:** Walk through the space and trip sensor triggers or press manual wake-up buttons to push their configuration profiles into the database.
5. **Diagnostic Verification Commands:**
   ```bash
   ss -tulpn | grep 8091  # Verify Web UI port is open
   docker ps              # Check container status
   docker logs zwave-js-ui # Inspect startup logs
   tail /opt/zwave-js-ui/logs/zwavejs_current.log -n 50 -f # Tail application logs
   ```

### 9.5 Hardware Upgrading (NVM Cloning & Editing)
To upgrade from an old RaZberry card to a modern 700/800-series USB Stick without re-pairing nodes, perform an NVM migration.
1. **Initial Backup:** In Z-Wave JS UI, go to **Actions > Advanced Actions > NVM Management** and click **Backup** to generate `NVM_backup.bin`. Export `nodes.json` from settings.
2. **Legacy Format Conversion (SDK < 6.61):** If your old controller uses a Z-Wave SDK older than 6.61, translate the backup using `oldnvm-to-zwjs.pl`:
   ```bash
   perl oldnvm-to-zwjs.pl <name of bin>
   ```
3. **NVM Ghost Node Cleanup:**
   * **Option A (Interactive Web Editor):** Upload the converted `.bin` file to `https://zwave-js.github.io/nvmtool/`. Remove dead node IDs from the JSON panel, and download the modified binary (`NVM_clean.bin`).
   * **Option B (Local Terminal CLI Engine):** Convert the binary container to JSON locally using Node.js:
     ```bash
     sudo apt install nodejs npm -y
     npx @zwave-js/nvmedit nvm2json --in /opt/zwave-js-ui/NVM_backup.bin --out /opt/zwave-js-ui/NVM_backup.json
     ```
     Edit `NVM_backup.json` to strip out orphaned `nodeId` sub-trees, then recompile:
     ```bash
     npx @zwave-js/nvmedit json2nvm --in /opt/zwave-js-ui/NVM_backup.json --out /opt/zwave-js-ui/NVM_clean.bin --protocolVersion <SDK_VERSION>
     ```
4. **Swap Hardware:** Power down, remove the old GPIO card, insert the modern USB stick (using a short USB extension cable to reduce EMF interference), and power back on.
5. **Restore:** In **Settings > Z-Wave**, update the serial port path, then go to **NVM Management > Restore** and upload the cleaned `.bin` file. Import `nodes.json` to restore friendly names across all nodes.

### 9.6 MQTT Gateway Configuration
Configure Z-Wave JS UI to broadcast decentralized state topics:
1. Go to **Settings > MQTT** and point to `mqtt://127.0.0.1` (Port 1883).
2. In **Gateway Settings**, set the Topic Prefix to `zwave` and set **Use Node Names** to `True`.
3. Sensors will begin streaming to the local broker, ready to be ingested by WanOS:
   ```text
   zwave/kerstverl_achter/switch_binary/endpoint_0/currentValue -> {"value": true, "time": 1782200000}
   ```

---

## 10. WanOS StateManager Python Implementation

To process incoming MQTT Z-Wave state updates inside the WanOS Python runtime engine, integrate the following subscription listener and parser methods into `core/state_manager.py`:

```python
# Place this registration logic inside your async MQTT connection broker initialization block
# to safely bind to the incoming decentralized Z-Wave data stream.

async def _initialize_zwave_listeners(self) -> None:
    """
    Subscribes exclusively to structural Z-Wave state topics.
    Filters out heavy power telemetry counters and usage diagnostics
    to minimize CPU overhead and layout refresh thrashing.
    """
    if not self.mqtt_client or not self.mqtt_client.is_connected:
        return

    # Subscribe specifically to binary relays and switch status changes
    # Using wildcard paths captures all friendly-named nodes dynamically
    zwave_switch_topic = "zwave/+/switch_binary/endpoint_0/currentValue"
    await self.mqtt_client.subscribe(zwave_switch_topic)
    logger.info("WanOS background bridge securely bound to Z-Wave JS UI MQTT data stream.")

async def _process_incoming_zwave_message(self, topic: str, payload: dict[str, Any]) -> None:
    """
    Parses clean JSON state values from the Z-Wave JS UI translation layer
    and injects them directly into the core execution state.
    """
    try:
        # Extract the node name directly from the structured topic layout string
        # Topic example: "zwave/kerstverl_achter/switch_binary/endpoint_0/currentValue"
        parts = topic.split('/')
        node_name = parts[1]
        
        # Extract the logical value state container
        raw_val = payload.get("value")
        target_state = "ON" if raw_val in [True, "true", "ON", 1] else "OFF"
        
        # Map the friendly node string name back to system layout IDXs
        if node_name == "kerstverl_achter":
            target_idx = 9627
            
            # Commit the evaluated state mutation directly to live system memory
            if self._state.devices.get(target_idx) != target_state:
                self._state.devices[target_idx] = target_state
                
                # Signal the SSE engine to push a partial delta frame to the UI
                self.publish_domain_update("devices", {target_idx: target_state})
                logger.debug(f"Z-Wave Node Sync: '{node_name}' [IDX {target_idx}] updated to {target_state}")
                
    except Exception as err:
        logger.error(f"Failed processing incoming Z-Wave data packet: {err}")
```