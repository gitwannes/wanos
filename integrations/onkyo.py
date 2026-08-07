# --- file: integrations/onkyo.py ---
import asyncio
from typing import Dict, Any
from loguru import logger
from core.models import Event, EventType


def pack_standard(command: str) -> bytes:
    """
    Used for modern Onkyo receivers (Cinema).
    This creates a perfectly standard eISCP binary TCP packet.
    CRITICAL: Modern Onkyos require the \x1a (EOF) byte before the \r\n to process reliably.
    """
    data = f"!1{command}\x1a\r\n".encode('ascii')

    # b'ISCP' = Magic Word
    # (16) = Header Size
    # len(data) = Accurate Payload Size
    # \x01... = Version and reserved bytes
    header = b'ISCP' + (16).to_bytes(4, 'big') + len(data).to_bytes(4, 'big') + b'\x01\x00\x00\x00'
    return header + data


def pack_legacy_malformed(ts: str) -> bytes:
    """
    Used for 2012-era Onkyo receivers (Living).
    EXACT byte-for-byte recreation of the legacy Node-RED JavaScript buffer.
    CRITICAL: The TX-NR616 firmware has a bug where it requires the payload length
    to be passed as an ASCII string of an incorrect length, rather than a true integer.
    """
    header = b'ISCP'
    header += b'\x00\x00\x00\x10'  # Header Size (16 bytes)
    header += b'\x00\x00\x00'  # Empty padding

    # Recreate the legacy JS bug: len = ts.length+2; len = len.toString(16);
    len_val = len(ts) + 2
    len_hex_str = format(len_val, 'X')
    header += len_hex_str.encode('ascii')

    header += b'\x01'  # Version 1
    header += b'\x00\x00\x00'  # Reserved

    # Payload excludes the \x1a EOF byte, uses strict \r\n terminator
    payload = b'!1' + ts.encode('ascii') + b'\x0d\x0a'
    return header + payload


class OnkyoBridge:
    def __init__(self, state_manager: Any) -> None:
        self.manager = state_manager
        self.config = state_manager._config.onkyo
        self.device_map = self.config.device_map if self.config else {}
        self.max_vol = self.config.max_volume if self.config else 60
        self.receivers: Dict[int, asyncio.StreamWriter] = {}
        self._running: bool = False
        self._listen_tasks: Dict[int, asyncio.Task] = {}

    async def start(self) -> None:
        import time
        self.start_time = time.time()
        self._running = True
        for idx, node in self.device_map.items():
            self._listen_tasks[idx] = asyncio.create_task(self._receiver_loop(idx, node.ip))
        logger.info(f"Onkyo Bridge started. Monitoring {len(self.device_map)} receivers.")

    async def stop(self) -> None:
        self._running = False
        for task in self._listen_tasks.values():
            task.cancel()
        self._listen_tasks.clear()

        # Safely shut down all open sockets
        for writer in self.receivers.values():
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        self.receivers.clear()
        logger.info("Onkyo Bridge stopped.")

    async def _receiver_loop(self, idx: int, ip: str) -> None:
        """
        Maintains a persistent, zero-latency TCP socket connected to the receiver on port 60128.
        Instantly translates volume knob twists or CEC wakeups into WanOS UI updates.
        """
        # Retrieve the specific node configuration to check for legacy requirements
        node = self.device_map.get(idx)
        is_legacy = getattr(node, 'legacy', False) if node else False
        pacing_delay = 2.0 if is_legacy else 0.2

        # Dynamically assign the correct byte-packing function based on receiver generation
        pack_func = pack_legacy_malformed if is_legacy else pack_standard

        while self._running:
            logger.debug(f"Onkyo {idx}: Attempting TCP connection to {ip}:60128...")
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 60128), timeout=5.0)
                self.receivers[idx] = writer
                logger.success(f"Onkyo {idx} ({ip}) connected successfully.")

                # Force UI to clear "SYNC..." by pushing a default baseline immediately
                self._update_state(idx, state="OFF", volume=0)

                # Wait for the receiver's network card to stabilize before firing requests.
                # Legacy receivers require a much longer initial initialization buffer to prevent "Socket Shock".
                init_delay = 2.0 if is_legacy else 0.5
                await asyncio.sleep(init_delay)

                # 1. Ask for the initial state on connection
                # Note: The new packing functions prepend '!1' automatically
                writer.write(pack_func('PWRQSTN'))
                await writer.drain()

                # Strictly pace the queries to prevent overflowing tiny TCP buffers on older chips
                await asyncio.sleep(pacing_delay)

                writer.write(pack_func('MVLQSTN'))
                await writer.drain()

                buffer = b""
                # 2. Start endless listening loop for real-time feedback
                while self._running:
                    data = await reader.read(256)
                    if not data:
                        raise ConnectionError("TCP socket closed by remote host.")

                    buffer += data

                    # 3. Process all complete messages using a sliding frame buffer
                    while b"ISCP" in buffer:
                        start_idx = buffer.find(b"ISCP")
                        if len(buffer) < start_idx + 16:
                            break  # Wait for more data to get the full header

                        # Extract exact message payload size
                        msg_size = int.from_bytes(buffer[start_idx + 8:start_idx + 12], 'big')
                        total_len = start_idx + 16 + msg_size

                        if len(buffer) < total_len:
                            break  # Wait for the rest of the payload

                        # Extract the payload and advance the buffer
                        payload = buffer[start_idx + 16:total_len]
                        buffer = buffer[total_len:]

                        try:
                            msg_str = payload.decode('ascii', errors='ignore')
                            if '!1PWR' in msg_str:
                                pwr_idx = msg_str.find('!1PWR')
                                if len(msg_str) >= pwr_idx + 7:
                                    pwr = msg_str[pwr_idx + 5:pwr_idx + 7]
                                    self._update_state(idx, state="ON" if pwr == "01" else "OFF")

                            if '!1MVL' in msg_str:
                                vol_idx = msg_str.find('!1MVL')
                                if len(msg_str) >= vol_idx + 7:
                                    vol_hex = msg_str[vol_idx + 5:vol_idx + 7]
                                    if vol_hex.upper() != 'NA':
                                        try:
                                            # ⚡ Natively push absolute raw hardware integer to the UI (No percentages)
                                            # Also enforces a strict clamp so if the user manually turned the
                                            # physical knob above the config limit, the UI respects the max_volume cap.
                                            raw_vol = int(vol_hex, 16)
                                            self._update_state(idx, volume=min(self.max_vol, max(0, raw_vol)))
                                        except ValueError:
                                            pass
                        except Exception as e:
                            logger.debug(f"Onkyo eISCP parse error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                # 3. Connection lost: Drop receiver, mark as DEAD, and sleep before reconnecting
                self.receivers.pop(idx, None)
                err_msg = repr(e)

                if "TimeoutError" in err_msg:
                    logger.error(f"Onkyo {idx} ({ip}): Connection timed out. Is the IP correct in config.yaml?")
                else:
                    logger.error(f"Onkyo {idx} ({ip}) disconnected: {err_msg}")

                # Safely evaluate if the device is already marked DEAD (handles both string and dict states)
                current_dev = self.manager._state.devices.get(idx)
                is_dead = current_dev == "DEAD" or (
                            isinstance(current_dev, dict) and current_dev.get("state") == "DEAD")

                if not is_dead:
                    self.manager.dispatch(Event(type=EventType.HUB_STATE_CHANGED,
                                                payload={"idx": idx, "state": "DEAD", "origin": "onkyo"}))

                await asyncio.sleep(5.0)

    def _update_state(self, idx: int, state: str = None, volume: int = None) -> None:
        """Pushes state back to the WanOS Event loop seamlessly."""
        current = self.manager._state.devices.get(idx)
        new_state = current.get("state", "OFF") if isinstance(current, dict) else "OFF"
        new_vol = current.get("volume", 0) if isinstance(current, dict) else 0

        changed = False
        if state is not None and new_state != state:
            new_state = state
            changed = True
        if volume is not None and new_vol != volume:
            new_vol = volume
            changed = True

        # If it was null before (at boot), we must push to replace the "SYNC..." placeholder
        if not isinstance(current, dict):
            changed = True

        if changed:
            self.manager.dispatch(Event(
                type=EventType.HUB_STATE_CHANGED,
                payload={
                    "idx": idx,
                    "state": new_state,
                    "volume": new_vol,
                    "origin": "onkyo"
                }
            ))

    async def execute_command(self, payload: Dict[str, Any]) -> None:
        """Translates WanOS commands back into native Hexadecimal for the physical receivers."""
        idx = payload.get("idx")
        writer = self.receivers.get(idx)
        if not writer:
            return

        # ⚡ INFINITE ECHO GUARD
        # If the receiver broadcasted this state change itself (e.g., a physical knob turn),
        # abort immediately so we don't echo the same command back and cause a race condition.
        if payload.get("origin") == "onkyo":
            return

        node = self.device_map.get(idx)
        is_legacy = getattr(node, 'legacy', False) if node else False
        pacing_delay = 2.0 if is_legacy else 0.2
        pack_func = pack_legacy_malformed if is_legacy else pack_standard

        try:
            command_sent = False

            if "volume" in payload:
                # ⚡ Send absolute raw integer directly. No percentage translation!
                raw_vol = max(0, min(self.max_vol, int(payload["volume"])))
                hex_vol = f"{raw_vol:02X}"  # Convert int to uppercase 2-digit Hex

                # Note: pack_func prepends the '!1' automatically
                writer.write(pack_func(f"MVL{hex_vol}"))
                await writer.drain()
                command_sent = True

            target_state = payload.get("state")
            if target_state in ["ON", "OFF"]:
                # ⚡ Pacing Guard: If WanOS automation fires volume + power in the exact same payload,
                # we MUST pause between the two TCP packet blasts to prevent dropping the connection.
                if command_sent:
                    await asyncio.sleep(pacing_delay)

                if target_state == "ON":
                    # ⚡ CACHE INVALIDATION: Force backend UI state to null so the sliders instantly show "SYNC..."
                    self.manager._state.devices[idx] = {"state": "ON", "volume": None}
                    self.manager.dispatch(Event(
                        type=EventType.HUB_STATE_CHANGED,
                        payload={"idx": idx, "state": "ON", "volume": None, "origin": "system"}
                    ))

                    writer.write(pack_func("PWR01"))
                    await writer.drain()

                    # ⚡ STARTUP HANDSHAKE: Wait a moment for the amplifier to boot, then query its default volume
                    boot_delay = 2.0 if is_legacy else 0.5
                    await asyncio.sleep(boot_delay)
                    writer.write(pack_func("MVLQSTN"))
                    await writer.drain()

                elif target_state == "OFF":
                    writer.write(pack_func("PWR00"))
                    await writer.drain()

        except Exception as e:
            logger.error(f"Onkyo command transmission failed on {idx}: {e}")