import asyncio
from typing import Optional
from loguru import logger

EPSON_INIT = bytes([
    0x45, 0x53, 0x43, 0x2F, 0x56, 0x50, 0x2E, 0x6E,
    0x65, 0x74, 0x10, 0x03, 0x00, 0x00, 0x00, 0x00,
    0x0D
])


class EpsonProjector:
    # Removed the hardcoded IP; it should be passed from config.yaml
    def __init__(self, host: str, port: int = 3629):
        self.host = host
        self.port = port

    async def power(self, state: str = "ON") -> bool:
        """Sends the power command and returns True if successful."""
        state = state.upper()
        if state not in ("ON", "OFF"):
            logger.error(f"Epson: Power state must be 'ON' or 'OFF', got {state}")
            return False

        try:
            # Added connection timeout so it doesn't hang indefinitely if offline
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=3.0
            )

            # Send INIT handshake
            writer.write(EPSON_INIT)
            await writer.drain()
            await asyncio.sleep(0.5)

            # Send actual command
            cmd_bytes = f"PWR {state}".encode("ascii") + b"\x0D"
            writer.write(cmd_bytes)
            await writer.drain()

            # Read response using native logger
            try:
                resp = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                # The exact byte string your Epson projector returns on a successful handshake
                expected_handshake = b'ESC/VP.net\x10\x03\x00\x00 \x00:'
                if resp == expected_handshake:
                    logger.debug("Epson: Handshake OK, command accepted.")
                else:
                    # Fallback: log the raw bytes if it's something different (like an error state)
                    logger.debug(f"Epson Response (Unknown): {resp}")

            except asyncio.TimeoutError:
                logger.debug("Epson: No response received (Timeout), assuming success.")

            writer.close()
            await writer.wait_closed()
            return True

        except Exception as e:
            logger.error(f"🔴 Epson communication failed: {e}")
            return False

    async def get_power_state(self) -> Optional[str]:
        """Returns 'ON', 'OFF', or None if no response."""
        reader, writer = await asyncio.open_connection(self.host, self.port)

        # Send INIT
        writer.write(EPSON_INIT)
        await writer.drain()
        await asyncio.sleep(0.5)

        # Send query
        writer.write(b"PWR?\x0D")
        await writer.drain()

        try:
            resp = await asyncio.wait_for(reader.read(1024), timeout=1.0)
            resp = resp.decode(errors="ignore").strip()
        except asyncio.TimeoutError:
            resp = None

        writer.close()
        await writer.wait_closed()

        if not resp:
            return None

        # Epson power states:
        # 01 = ON
        # 02 = WARMING UP (treat as ON)
        # 03 = COOLING DOWN (treat as OFF)
        # 00 = OFF

        if "PWR=01" in resp or "PWR=02" in resp:
            return "ON"

        if "PWR=00" in resp or "PWR=03" in resp:
            return "OFF"

        return None