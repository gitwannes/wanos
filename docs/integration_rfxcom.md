# WanOS Native RFXCOM Integration: Lifecycle & Architecture

Based on the WanOS backend architecture, the Native RFXCOM integration acts as a **low-level serial hardware bridge**. It communicates directly with the physical USB transceiver via `serial_asyncio`, entirely bypassing traditional MQTT middleware[cite: 9].

## 1. The Boot & Connection Phase (Turning it ON)
When toggled to **ON**, the `start()` method is invoked inside `NativeRFXCOMBridge`[cite: 9].

*   **Dependency Check:** It performs an immediate global check for `serial_asyncio` and `RFXtrx.lowlevel`[cite: 9]. If missing, it aborts the mount[cite: 9].
*   **Hardware Verification:** It checks if the physical `/dev/tty...` path exists on the Linux host[cite: 9].
*   **Asyncio Serial Protocol:** It utilizes Python's native `asyncio.Protocol` paradigm to bind directly to the USB serial stream at `38400` baud[cite: 9].

## 2. Triggering Outbound Commands (Stateless Radio)
Because 433MHz is an unencrypted, simplex (one-way) protocol, devices cannot confirm they received a command. WanOS architecture explicitly handles this limitation.

*   **The Global Force Guard:** Inside `hub_handlers.py`, any outbound command targeted at a device with `origin: "rfxcom"` is forcibly injected with `force: True`[cite: 4]. This universally bypasses WanOS's internal duplicate-state filters[cite: 4].
*   **Always Transmit:** Even if the UI thinks a light is already "ON", clicking "ON" again will *always* transmit the radio wave to ensure the physical hardware syncs[cite: 9]. RFX actuator `entity_id`s use the **`rfx.<slug>`** birth pattern (Phase **D** ✅).
*   **Lighting4 Direct Byte Generation:** To prevent "Poison Pill" crashes caused by the underlying `pyRFXtrx` library failing to parse PT2262 hexadecimal payloads, the bridge intercepts `Lighting4` protocol commands and manually generates the exact 10-byte binary packet structure[cite: 9].

## 3. The Continuous Listening Loop (The Antenna Firehose)
The `WanOSRFXProtocol` continuously reads the USB buffer as data arrives[cite: 9].

*   **Length-Prefixed Parsing:** RFXCOM packets are strictly structured where the first byte dictates the total packet length (`pkt_len = buffer[0] + 1`)[cite: 9]. The protocol slices perfect packet frames from the sliding buffer and passes them to `handle_raw_packet`[cite: 9].
*   **Hex Translation:** The raw hex is compared against the `_inbound_map` (seeded from `config.yaml`)[cite: 9]. If a physical remote control press matches an expected hex string, it translates it into a WanOS `HUB_STATE_CHANGED` event to instantly update the UI[cite: 9].

## 4. The Dual Health Monitors (The Auto-Kill Procedure)
Because USB serial hardware is notoriously fragile, this integration features an aggressive, two-tiered health monitoring system.

*   **Internal USB Watchdog:** The bridge itself runs a continuous background task (`_usb_watchdog`) that checks `os.path.exists()` every 3.0 seconds[cite: 9]. If the USB stick is physically yanked out of the server while the integration is running, it instantly detects the hardware loss, closes the dead transport, and voluntarily self-disables the integration[cite: 9].
*   **Global Auto-Kill:** Simultaneously, the global `HealthMonitor` audits `sm.rfxcom_bridge.is_connected`[cite: 3]. Unlike network integrations that get 3 strikes, a USB serial drop is deemed immediately fatal. A single strike instantly kills the integration across the system[cite: 3].

## 5. Turning the Integration OFF
*   The `stop()` method flips `is_connected` to `False`[cite: 9].
*   It executes `self.transport.close()` to release the lock on the physical Linux `/dev/` file descriptor, allowing other processes to access the USB stick if necessary[cite: 9].