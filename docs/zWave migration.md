# 📑 MIGRATION BLUEPRINT: DOMOTICZ TO Z-WAVE JS UI & WANOS INTEGRATION

This plain-text document contains your complete operational blueprint to safely migrate your 40+ Z-Wave nodes from an ancient Domoticz environment over to a modern, decentralized, and self-healing architecture. Following this process guarantees zero sensor re-pairing because the network data is preserved directly inside the radio controller hardware.

---

## Phase 1: Pre-Migration Data Extraction

Before touching any hardware, you must extract human-readable naming mappings from your existing setup. The Z-Wave controller chip handles the network communication, but it does not store your custom text labels.

1. **Build the Node Mapping Table:**
   * Go to your Domoticz Device/Hardware tab and take complete screenshots or print out the list of your devices.
   * Document the correlation between the **Z-Wave Node ID** (e.g., Node 05, derived from Hex ID structures) and your custom **Friendly Name** (e.g., `kerstverl achter`).
2. **Document Multi-Function Nodes:**
   * Identify nodes like smart plugs that contain multiple properties (Switch, Watts, kWh) under identical IDs. You will use this mapping reference to clean up the configuration profile inside the new UI.

---

## Phase 2: Hardware Migration & Pi OS Preparation

In this stage, you physically migrate the existing Z-Wave controller and modify the WanOS host Linux kernel to cleanly communicate with the RaZberry shield's hardware serial lines.

### 1. Physical Relocation
1. Gracefully shut down your ancient Debian Jessie Raspberry Pi.
2. Unplug the power source and unseat the physical **RaZberry Plus** GPIO expansion card from the motherboard.
3. Power down your modern **WanOS Raspberry Pi**.
4. Align the RaZberry card pins and press it firmly onto the active GPIO header block of the WanOS Pi.

### 2. Liberating the Linux Hardware UART Lanes
By default, the Raspberry Pi operating system routes its onboard Bluetooth mesh module through the primary hardware UART pins. You must disable Bluetooth to grant the Z-Wave card exclusive serial hardware lanes.

1. edit /boot/config.txt
2. Append the following parameters to the absolute bottom of the configuration profile:
```text
   # Free up primary hardware serial lanes for the RaZberry Z-Wave controller
   dtoverlay=disable-bt
   enable_uart=1
   ```
3. edit /boot/cmdline.txt and remove all 'console=serial0' from the 1-liner
4. Save the modifications (`Ctrl+O`, then `Enter`) and close the file editor (`Ctrl+X`).
5. Reboot the host operating system to enforce kernel changes:
```bash
   sudo reboot
   ```

---

## Phase 3: Deploying & Configuring Z-Wave JS UI

We utilize a lightweight, containerized instance of Z-Wave JS UI to drive the RaZberry board. This decouples hardware polling overhead from your core WanOS execution loop.

### 1. Docker Engine Deployment
NOT inside a virtual environment (venv)!
```bash
deactivate
sudo apt update && sudo apt upgrade -y          # Refresh repository package lists and automatically upgrade all installed system packages
curl -fsSL [https://get.docker.com](https://get.docker.com) -o get-docker.sh # Securely download the official Docker convenience installation script to the local drive
sudo sh get-docker.sh                           # Execute the downloaded script with root privileges to automatically install the Docker engine
rm get-docker.sh                                # Delete the temporary installer script file to clean up the local workspace
sudo usermod -aG docker $USER                   # Add the currently logged-in user to the 'docker' security group to grant non-root privileges
newgrp docker                                   # Reload user group memberships instantly so the new Docker permissions take effect without a reboot
docker run hello-world                          # Download and run a tiny diagnostic container to verify that the Docker daemon works perfectly
docker compose version                          # Display the installed version of Docker Compose V2 to confirm the orchestration tool is ready
```

---
```text
Client: Docker Engine - Community
 Version:           28.5.2
 API version:       1.51
 Go version:        go1.25.3
 Git commit:        ecc6942
 Built:             Wed Nov  5 14:43:49 2025
 OS/Arch:           linux/arm
 Context:           default

Server: Docker Engine - Community
 Engine:
  Version:          28.5.2
  API version:      1.51 (minimum version 1.24)
  Go version:       go1.25.3
  Git commit:       89c5e8f
  Built:            Wed Nov  5 14:43:49 2025
  OS/Arch:          linux/arm
  Experimental:     false
 containerd:
  Version:          v2.2.1
  GitCommit:        dea7da592f5d1d2b7755e3a161be07f43fad8f75
 runc:
  Version:          1.3.4
  GitCommit:        v1.3.4-0-gd6d73eb8
 docker-init:
  Version:          0.19.0
  GitCommit:        de40ad0
```
---

Execute the following deployment block on your WanOS Pi terminal to spin up the middleware container:

```bash
docker run -d \
  --name zwave-js-ui \
  --restart always \
  --privileged \
  --network host \
  -v /opt/zwave-js-ui:/usr/src/app/store \
  --device /dev/ttyAMA0 \
  zwavejs/zwave-js-ui:latest
```

For USB Z-Wave stick: /dev/ttyUSB0


### 2. Initializing Hardware Integration
1. Open a web browser window and navigate to your dashboard host endpoint on port `8091`: http://10.32.251.30:8091
2. Navigate to **Settings > Z-Wave**.
3. Configure the following hardware communication fields:
   * **Serial Port:** `/dev/ttyAMA0` (The hardware UART pin path mapping)
   * **Z-Wave API Boot Timeout:** `disabled`
4. Click **Save**. The middleware will initialize your RaZberry module, query its internal EEPROM memory, and automatically populate your 40+ hardware nodes directly onto the UI panel.

### 3. Restoring Device Profiles
1. Expand each discovered Node card on the interface and check its manufacturer specifications.
2. Cross-reference your pre-migration table and type the corresponding friendly label (e.g., `kerstverl_achter`) directly into the node's **Name** parameter block.
3. For battery-operated devices, walk through the physical environment and trip the sensor or press its manual wake-up button to quickly push its profile configuration values into the new database engine.

---

## Phase 4: Hardware Upgrading (Cloning to a New USB Device)

To completely eliminate ancient hardware dependencies, use this software-based process to securely clone your active network off the RaZberry card onto a modern 700 or 800-series Z-Wave USB Stick.

### 1. Backup the Network State
1. Inside the Z-Wave JS UI control interface, navigate to **Actions > Advanced Actions**.
2. Locate the **NVM Management** utility container and click **Backup**. This generates an exact binary clone (`NVM_backup.bin`) of your physical radio network token, tracking entries, and routing tables.
3. Go to the dashboard settings bar and execute an **Export** command to download your localized text naming profile map configuration as `nodes.json`.

### 2. Swap the Radio Devices
1. Safely pull the power cord of your WanOS Pi.
2. Carefully unplug the old RaZberry GPIO board from the hardware header block.
3. Insert your brand-new 700/800-series Z-Wave USB controller stick (using a short USB extension cable to insulate the antenna path from high-frequency EMF interference).
4. Power your WanOS Pi back online.

### 3. Restore the Mesh Network Data
1. Return to the Z-Wave JS UI dashboard web browser instance.
2. Navigate to **Settings > Z-Wave** and change the serial communications path string to target your new USB node location:
   * **Serial Port:** `/dev/ttyUSB0` (or your platform's mapped tracking address)
3. Click **Save**.
4. Go to **Actions > Advanced Actions > NVM Management**.
5. Select **Restore** and upload your downloaded `NVM_backup.bin` file. *The translation framework will automatically flash and expand your network maps onto the modern chip architecture.*
6. Import your `nodes.json` configuration file to immediately rebuild your custom naming labels across all nodes.

### 4. Advanced: Purging Ghost Nodes via NVM Binary Editing
If your legacy topology contains broken routing descriptors or dead "ghost nodes" that introduce transmission latency, you can securely modify the raw storage maps before writing them to the replacement controller stick using official Z-Wave JS tooling.

#### Option A: The Interactive Web Editor (Recommended)
1. Navigate your web browser to the official offline utility application: `https://zwave-js.github.io/nvmtool/`
2. Upload your pristine `NVM_backup.bin` data frame container.
3. Locate the dynamic Node Directory array panel, find the orphaned Node IDs, and click **Delete**.
4. Click download to generate a cryptographically valid firmware container image and name it `NVM_clean.bin`. Use this clean file for your final flash restore process.

#### Option B: The Local Host Command Line Engine
If you prefer manipulating database schemas locally inside your terminal core environment, utilize the Node.js runtime environment to decompile the raw memory blocks:

1. **Install Node/NPM dependencies on the host machine OS:**
```bash
   sudo apt install nodejs npm -y                          # Install JavaScript engine runtimes globally on the host operating system
   ```
2. **Decompile the binary container file to a structural JSON object mapping:**
```bash
   npx @zwave-js/nvmedit nvm2json --in /opt/zwave-js-ui/NVM_backup.bin --out /opt/zwave-js-ui/NVM_backup.json # Convert binary NVM blocks to human-editable structural JSON arrays
   ```
3. **Execute Data Record Purging:**
   Open `/opt/zwave-js-ui/NVM_backup.json` using Nano or your favorite text editor, locate the legacy or defective `nodeId` sub-trees, strip them out entirely, and save changes.
4. **Recompile modified JSON schema frames back to a validated hardware container:**
```bash
   npx @zwave-js/nvmedit json2nvm --in /opt/zwave-js-ui/NVM_backup.json --out /opt/zwave-js-ui/NVM_clean.bin --protocolVersion <SDK_VERSION> # Re-encode JSON definitions into a checksum-verified binary payload container
   ```
   *(Note: Swap `<SDK_VERSION>` with the specific firmware architecture matching your modern hardware module, e.g., `7.19.3` or `8.1.2`, derived directly from your Z-Wave JS UI status card).*

---

## Phase 5: Configuring the MQTT Gateway

Now that your Z-Wave controller is modernized and named, configure the built-in gateway service to broadcast state changes as decentralized MQTT topics.

1. Inside Z-Wave JS UI, go to **Settings > MQTT**.
2. Configure your local broker parameters to match your existing internal WanOS client credentials:
   * **Host/URL:** `mqtt://127.0.0.1` (or your primary local broker IP address)
   * **Port:** `1883`
3. Expand the **Gateway Settings** tree and enforce the following topic rules:
   * **Topic Prefix:** `zwave`
   * **Use Node Names:** `True` (Enforces clean formatting using your custom labels)
4. Save and enable the gateway. Your sensors will instantly begin streaming targeted property packets onto your local broker:
```text
   zwave/kerstverl_achter/switch_binary/endpoint_0/currentValue -> {"value": true, "time": 1782200000}
   ```

---

## Phase 6: Enabling the New Input in WanOS

Because your WanOS backend is already highly event-driven and manages background tasks via standard async listeners, handling these incoming Z-Wave updates requires minimal configuration.

You simply add a new subscription hook inside your MQTT subscriber loop to watch for your explicitly named Z-Wave sensor topics, extract the payload values, and merge them directly into the live `self._state.devices` memory dictionary.

### Operational Blueprint Block for `core/state_manager.py`

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

    # ⚡ Subscribe specifically to binary relays and switch status changes
    # Using wildcard paths lets you capture all friendly-named nodes dynamically
    zwave_switch_topic = "zwave/+/switch_binary/endpoint_0/currentValue"
    await self.mqtt_client.subscribe(zwave_switch_topic)
    logger.info(True, "🔗 WanOS background bridge securely bound to Z-Wave JS UI MQTT data stream.")

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
        
        # ⚡ Map the friendly node string name back to your hardcoded system layout IDXs
        # In this example case, 'kerstverl_achter' corresponds directly to device identity 9627
        if node_name == "kerstverl_achter":
            target_idx = 9627
            
            # Commit the evaluated state mutation directly to live system memory
            if self._state.devices.get(target_idx) != target_state:
                self._state.devices[target_idx] = target_state
                
                # Signal the SSE engine to push a partial delta frame to dashboard.html instantly
                self.publish_domain_update("devices", {target_idx: target_state})
                logger.debug(f"⚡ Z-Wave Node Sync: '{node_name}' [IDX {target_idx}] updated to {target_state}")
                
    except Exception as err:
        logger.error(f"💥 Failed processing incoming Z-Wave data packet: {err}")
```

Your system is now completely untethered from your legacy Domoticz instance, protected against database crashes, and running on advanced hardware with an organized data architecture.
`````</SDK_VERSION>