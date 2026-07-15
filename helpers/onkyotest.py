#!/usr/bin/env python3
import asyncio
import sys
from typing import Optional, Dict, List

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
RECEIVERS: Dict[str, str] = {
    "cinema": "10.32.251.35",  # Newer TX-NR575E: Standard eISCP protocol
    "living": "10.32.251.78"  # Older TX-NR616: Legacy malformed protocol
}


# ---------------------------------------------------------------------------
# PACKING PROTOCOLS
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# CONNECTION LIFECYCLE
# ---------------------------------------------------------------------------
async def handle_receiver(name: str, ip: str, target_state: Optional[str] = None) -> None:
    print(f"[{name.upper()} ({ip})] Attempting TCP connection on port 60128...")

    try:
        # Open TCP socket (Standard eISCP port)
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 60128), timeout=5.0)
        print(f"[{name.upper()} ({ip})] 🟢 Connected successfully.")

        # Build the command queue
        command_queue: List[str] = []
        if target_state == "ON":
            command_queue.append("PWR01")
        elif target_state == "OFF":
            command_queue.append("PWR00")

        # Only append status queries if we are NOT in strict RECEIVE mode
        if target_state != "RECEIVE":
            command_queue.append("PWRQSTN")
            command_queue.append("MVLQSTN")

        # -------------------------------------------------------------------
        # EXECUTION PHASE (Dynamic Routing)
        # Skip execution entirely if target_state is 'RECEIVE'
        # -------------------------------------------------------------------
        if command_queue:
            for i, cmd in enumerate(command_queue):
                if name == "living":
                    # LIVING: Requires strict 2.0-second spacing to prevent TCP buffer overflow
                    if i > 0:
                        print(f"[{name.upper()}] ⏳ Legacy wait 2.0s...")
                        await asyncio.sleep(2.0)

                    print(f"[{name.upper()}] 🚀 Sending (LEGACY PACKING): {cmd}")
                    writer.write(pack_legacy_malformed(cmd))
                    await writer.drain()

                else:
                    # CINEMA: Can handle rapid-fire streams with standard packing
                    if i > 0:
                        await asyncio.sleep(0.2)

                    print(f"[{name.upper()}] 🚀 Sending (STANDARD PACKING): !1{cmd}")
                    writer.write(pack_standard(cmd))
                    await writer.drain()

        # -------------------------------------------------------------------
        # LISTENING PHASE (Sliding Frame Buffer)
        # -------------------------------------------------------------------
        buffer = b""

        # If in RECEIVE mode, keep the end_time infinitely in the future
        if target_state == "RECEIVE":
            print(
                f"[{name.upper()} ({ip})] 🎧 Entering continuous RECEIVE mode. Listening for broadcasts (Ctrl+C to exit)...")
            end_time = float('inf')
        else:
            # Standard queries timeout after 3 seconds
            end_time = asyncio.get_event_loop().time() + 3.0

        # Loop until the designated end_time is reached (or infinitely)
        while asyncio.get_event_loop().time() < end_time:
            try:
                # Read incoming bytes from the receiver safely
                # Timeout is kept short so the loop remains responsive to Ctrl+C
                data = await asyncio.wait_for(reader.read(256), timeout=0.5)

                # If connection drops, break loop
                if not data:
                    print(f"[{name.upper()} ({ip})] 🔴 Connection closed cleanly by receiver.")
                    break

                buffer += data

                # Parse the stream looking for the 'ISCP' magic word
                while b"ISCP" in buffer:
                    start_idx = buffer.find(b"ISCP")
                    if len(buffer) < start_idx + 16:
                        break  # Incomplete header

                    msg_size = int.from_bytes(buffer[start_idx + 8:start_idx + 12], 'big')
                    total_len = start_idx + 16 + msg_size

                    if len(buffer) < total_len:
                        break  # Incomplete payload

                    payload = buffer[start_idx + 16:total_len]
                    buffer = buffer[total_len:]

                    # Decode and strip control characters like \x1a before printing
                    msg_str = payload.decode('ascii', errors='ignore').strip().replace('\x1a', '')
                    print(f"[{name.upper()} ({ip})] 📡 Received: {msg_str}")

            except asyncio.TimeoutError:
                # Expected timeout of the read chunk, simply loop again
                continue

        # -------------------------------------------------------------------
        # TEARDOWN PHASE
        # -------------------------------------------------------------------
        print(f"[{name.upper()} ({ip})] Closing TCP socket.")
        writer.close()
        await writer.wait_closed()

    except Exception as e:
        print(f"[{name.upper()} ({ip})] 🔴 Failed: {repr(e)}")


# ---------------------------------------------------------------------------
# MAIN SCRIPT ENTRYPOINT
# ---------------------------------------------------------------------------
async def main() -> None:
    # Ensure obligatory target switch
    if len(sys.argv) < 2:
        print("Usage: python3 test_onkyo.py <cinema|living> [ON|OFF|RECEIVE]")
        sys.exit(1)

    target_name = sys.argv[1].lower()
    if target_name not in RECEIVERS:
        print(f"Error: Invalid target switch '{sys.argv[1]}'. Must be 'cinema' or 'living'.")
        sys.exit(1)

    target_ip = RECEIVERS[target_name]
    target_state = None

    # Parse optional action switch
    if len(sys.argv) > 2:
        arg = sys.argv[2].upper()
        if arg in ["ON", "OFF", "RECEIVE"]:
            target_state = arg
        else:
            print("Usage: python3 test_onkyo.py <cinema|living> [ON|OFF|RECEIVE]")
            sys.exit(1)

    await handle_receiver(target_name, target_ip, target_state)


if __name__ == "__main__":
    # Cross-platform async execution loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript terminated by user.")