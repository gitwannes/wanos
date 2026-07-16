# --- file: integrations/rfxcom.py ---
import asyncio
import os
from typing import Any, Dict, List, Optional

from core.models import Event, EventType, SystemState
from core.state_manager import StateManager
from core.logger import WanosComponent

try:
    import serial_asyncio
    import RFXtrx.lowlevel as lowlevel
    DEPENDENCIES_AVAILABLE = True
except ImportError as lib_err:
    from loguru import logger
    logger.critical(f"⚠️ [Native RFX] Required library missing: {lib_err}")
    DEPENDENCIES_AVAILABLE = False


class WanOSRFXProtocol(asyncio.Protocol):
    """Native Asyncio Serial Protocol to handle the RFX stream directly on the main event loop."""
    def __init__(self, bridge):
        self.bridge = bridge
        self.buffer = bytearray()

    def connection_made(self, transport):
        self.bridge.transport = transport
        self.bridge.is_connected = True

    def data_received(self, data):
        self.buffer.extend(data)
        # RFXCOM packets always start with a length byte (packet length = byte[0] + 1)
        while len(self.buffer) > 0:
            pkt_len = self.buffer[0] + 1
            if len(self.buffer) >= pkt_len:
                packet = self.buffer[:pkt_len]
                self.buffer = self.buffer[pkt_len:]
                self.bridge.handle_raw_packet(packet)
            else:
                break

    def connection_lost(self, exc):
        self.bridge.is_connected = False
        self.bridge.transport = None


class NativeRFXCOMBridge(WanosComponent):
    def __init__(self, state_manager: StateManager, serial_port: str) -> None:
        super().__init__(state_manager)

        self.serial_port: str = serial_port
        self.transport = None
        self.protocol = None

        self.is_connected: bool = False
        self._integration_enabled: bool = False
        self._listener_registered: bool = False

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._watchdog_task: Optional[asyncio.Task] = None

        self._last_known_states: Dict[int, str] = {}
        self._inbound_map: Dict[str, Dict[str, Any]] = {}
        self._outbound_map: Dict[int, Dict[str, str]] = {}

        self._build_translation_maps()

    def _build_translation_maps(self) -> None:
        if not hasattr(self.state_manager._config, "native_rfx"):
            return

        for device in self.state_manager._config.native_rfx:
            try:
                idx = device.virtual_idx
                on_id_str = str(device.on_id).strip().lower()
                off_id_str = str(device.off_id).strip().lower()

                if on_id_str == off_id_str:
                    continue

                self._outbound_map[idx] = {
                    "protocol": device.protocol,
                    "ON": on_id_str,
                    "OFF": off_id_str
                }

                self._inbound_map[on_id_str] = {"idx": idx, "state": "ON"}
                self._inbound_map[off_id_str] = {"idx": idx, "state": "OFF"}
            except Exception:
                pass

    async def start(self) -> None:
        if not DEPENDENCIES_AVAILABLE:
            await self.logger.error("[Native RFX] Missing serial_asyncio library. Aborting mount.")
            return

        self.loop = asyncio.get_running_loop()
        self._integration_enabled = self.state_manager._state.system.rfxcom_integration_enabled

        if not self._listener_registered:
            self.state_manager.register_listener(self._on_state_changed)
            self._listener_registered = True

        await self.logger.info("[Native RFX] Bridge class loaded. Standing by for USB mount.")

        if not os.path.exists(self.serial_port):
            await self.logger.error(f"[Native RFX] Port {self.serial_port} not found. Waiting for watchdog...")
        else:
            await self._mount_serial()

        if not self._watchdog_task:
            self._watchdog_task = self.loop.create_task(self._usb_watchdog())

    async def _mount_serial(self) -> None:
        try:
            await self.logger.info(f"[Native RFX] Mounting Native Asyncio Transport on {self.serial_port}...")
            coro = serial_asyncio.create_serial_connection(
                self.loop,
                lambda: WanOSRFXProtocol(self),
                self.serial_port,
                baudrate=38400
            )
            self.transport, self.protocol = await asyncio.wait_for(coro, timeout=5.0)
            await self.logger.success(f"[Native RFX] USB Transceiver mounted! {len(self._outbound_map)} device(s) registered.")
        except Exception as e:
            self.is_connected = False
            await self.logger.error(f"[Native RFX] Failed to mount: {e}")

    async def stop(self) -> None:
        if self._watchdog_task:
            self._watchdog_task.cancel()
        self.is_connected = False
        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
        self.transport = None

    async def _usb_watchdog(self) -> None:
        try:
            while True:
                try:
                    await asyncio.sleep(3.0)
                    port_exists = os.path.exists(self.serial_port)

                    if self.is_connected and not port_exists:
                        self.is_connected = False
                        await self.logger.error(f"[Native RFX] ⚠️ PHYSICAL DISCONNECT: {self.serial_port} lost!")

                        if self.transport:
                            try:
                                self.transport.close()
                            except Exception:
                                pass
                            self.transport = None

                        if self._integration_enabled:
                            self.state_manager.dispatch(Event(
                                type=EventType.RFXCOM_TOGGLED,
                                payload={"enabled": False, "error_msg": "RFXCOM physically unplugged!"}
                            ))

                    elif not self.is_connected and port_exists:
                        await self.logger.info(f"[Native RFX] Detected {self.serial_port}. Auto-remounting...")
                        await self._mount_serial()

                except Exception as inner_e:
                    await self.logger.error(f"[Native RFX Watchdog] Inner loop error safely caught: {inner_e}")
        except asyncio.CancelledError:
            pass

    def handle_raw_packet(self, packet: bytearray) -> None:
        """Called directly by the WanOSRFXProtocol when a full packet is assembled."""
        raw_hex = packet.hex().lower()

        # Bypass WanOS log filters so we can always see the firehose in consolelog!
        # print(f"📻 [Native RFX] [ANTENNA FIREHOSE] {raw_hex}")

        if not self._integration_enabled:
            return

        mapping = None
        for configured_hex, map_data in self._inbound_map.items():
            if configured_hex in raw_hex:
                mapping = map_data
                break

        if not mapping:
            return

        virtual_idx = mapping["idx"]
        target_state = mapping["state"]

        if self._last_known_states.get(virtual_idx) == target_state:
            return

        self._last_known_states[virtual_idx] = target_state
        virtual_name = self.state_manager._config.dashboard.get(virtual_idx, f"idx_{virtual_idx}")

        self.state_manager.dispatch(Event(
            type=EventType.HUB_STATE_CHANGED,
            payload={
                "idx": virtual_idx,
                "state": target_state,
                "name": virtual_name,
                "is_push_button": False,
                "rfx_origin": raw_hex
            }
        ))

        asyncio.ensure_future(self.logger.success(
            f"[Native RFX] Physical Remote Intercepted: Hex [{raw_hex}] mapped to Virtual IDX {virtual_idx} ({virtual_name}) -> {target_state}"
        ))

    async def _on_state_changed(self, state: SystemState, events: List[Event] = None) -> None:
        try:
            current_enabled = state.system.rfxcom_integration_enabled

            if current_enabled and not self._integration_enabled:
                self._integration_enabled = True
                await self.logger.success("[Native RFX] Engine ENABLED via UI.")
            elif not current_enabled and self._integration_enabled:
                self._integration_enabled = False
                await self.logger.info("[Native RFX] Engine DISABLED via UI.")

            if not current_enabled or not self.is_connected or not events:
                return

            for event in events:
                if event.type != EventType.HUB_STATE_CHANGED:
                    continue

                idx = event.payload.get("idx")
                new_state = event.payload.get("state")
                rfx_origin = event.payload.get("rfx_origin")
                is_init = event.payload.get("is_initialization", False)

                if idx is None or new_state is None or idx not in self._outbound_map:
                    continue

                # ⚡ STATELESS RADIO BYPASS ⚡
                # 433MHz devices cannot acknowledge receipt.
                # Outbound commands ALWAYS transmit over the air!

                if is_init:
                    self._last_known_states[idx] = new_state
                    continue

                self._last_known_states[idx] = new_state

                if rfx_origin is None:
                    await self._transmit_physical(idx, new_state)

        except Exception as e:
            await self.logger.error(f"[Native RFX] Unexpected error in _on_state_changed: {e}")

    async def _transmit_physical(self, idx: int, state: str) -> None:
        config = self._outbound_map.get(idx)
        if not config:
            return

        target_hex = config["ON"] if state == "ON" else config["OFF"]
        protocol = config["protocol"]

        if not self.transport:
            self.is_connected = False
            await self.logger.error(f"[Native RFX] Cannot transmit for IDX {idx}: transport is dead.")
            return

        try:
            payload_bytes = None

            # ⚡ NATIVE LIGHTING4 PACKET GENERATOR ⚡
            # Completely bypasses pyRFXtrx class complexity to prevent Poison Pill crashes.
            if protocol.lower() == "lighting4":
                # PT2262 payload is exactly 10 bytes.
                # Hex string must be exactly 6 characters (3 bytes).
                clean_hex = target_hex.zfill(6)
                payload_bytes = bytearray([
                    0x09,  # Length (9 bytes follow)
                    0x13,  # Packet type: Lighting4
                    0x00,  # Subtype: PT2262
                    0x00,  # Sequence number (0 is fine for TX)
                    int(clean_hex[0:2], 16),  # ID Byte 1
                    int(clean_hex[2:4], 16),  # ID Byte 2
                    int(clean_hex[4:6], 16),  # ID Byte 3
                    0x01,  # Pulse high (0x01A5 = 421 us)
                    0xA5,  # Pulse low
                    0x00  # Signal level (0 for TX)
                ])
            else:
                # ⚡ FALLBACK FOR OTHER PROTOCOLS ⚡
                pkt_class = getattr(lowlevel, protocol, None)
                if not pkt_class:
                    await self.logger.error(f"[Native RFX] Unknown protocol '{protocol}' for IDX {idx}.")
                    return

                pkt = pkt_class()

                # Assign arbitrary pulse so data property doesn't crash internally
                if hasattr(pkt, 'pulse'):
                    pkt.pulse = 400

                try:
                    pkt.parse_id(0, target_hex)
                except Exception:
                    try:
                        pkt.parse_id(0, int(target_hex, 16))
                    except Exception:
                        try:
                            pkt.parse_id(target_hex)
                        except Exception as parse_err:
                            await self.logger.error(f"[Native RFX] Parse failed for {target_hex}: {parse_err}")
                            return

                # The Poison Pill Guard
                if not hasattr(pkt, 'data') or pkt.data is None:
                    await self.logger.error(f"[Native RFX] Library failed to generate byte array for {target_hex}.")
                    return

                # Strict type casting
                payload_bytes = bytes(pkt.data) if isinstance(pkt.data, (bytearray, list)) else pkt.data

            # ⚡ FINAL TRANSMISSION ⚡
            if payload_bytes:
                self.transport.write(payload_bytes)
                await self.logger.info(
                    f"[Native RFX] Transmitted: IDX {idx} -> {state} | Protocol: {protocol} | Hex: {target_hex}")

        except Exception as e:
            await self.logger.error(f"[Native RFX] Transmission failed for IDX {idx}: {e}")