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
    Standard, mathematically correct eISCP binary packing.
    Used for newer receivers (Cinema).
    """
    data = f"!1{command}\r\n".encode('ascii')
    header = b'ISCP' + (16).to_bytes(4, 'big') + len(data).to_bytes(4, 'big') + b'\x01\x00\x00\x00'
    return header + data


def pack_legacy_malformed(ts: str) -> bytes:
    """
    EXACT byte-for-byte recreation of the legacy Node-RED JavaScript buffer.
    Recreates the mathematically malformed length header and string coercions.
    """
    # command.payload = "ISCP"
    header = b'ISCP'

    # command.payload += new Buffer([ 0x00, 0x00, 0x00, 0x10 ])
    header += b'\x00\x00\x00\x10'

    # command.payload += new Buffer([ 0x00, 0x00, 0x00 ])
    header += b'\x00\x00\x00'

    # len = ts.length+2; len = len.toString(16).toUpperCase();
    # command.payload += len;
    len_val = len(ts) + 2
    len_hex_str = format(len_val, 'X')  # e.g. 7 -> '7', 9 -> '9'
    header += len_hex_str.encode('ascii')  # ASCII string character appended to bytes

    # command.payload += new Buffer([ 0x01 ]);
    header += b'\x01'

    # command.payload += new Buffer([ 0x00, 0x00, 0x00 ]);
    header += b'\x00\x00\x00'

    # command.payload += new Buffer([ 0x21, 0x31 ]); -> This is '!1'
    # command.payload += ts;
    # command.payload += new Buffer([ 0x0d, 0x0a ]); -> This is '\r\n'
    payload = b'!1' + ts.encode('ascii') + b'\x0d\x0a'

    return header + payload


# ---------------------------------------------------------------------------
# CONNECTION LIFECYCLE
# ---------------------------------------------------------------------------
async def handle_receiver(name: str, ip: str, target_state: Optional[str] = None) -> None:
    print(f"[{name.upper()} ({ip})] Attempting TCP connection on port 60128...")

    try:
        # Open TCP socket
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 60128), timeout=5.0)
        print(f"[{name.upper()} ({ip})] 🟢 Connected successfully.")

        # Build the exact command queue array (like `otsend` in JS)
        command_queue: List[str] = []
        if target_state == "ON":
            command_queue.append("PWR01")
        elif target_state == "OFF":
            command_queue.append("PWR00")

        command_queue.append("PWRQSTN")
        command_queue.append("MVLQSTN")

        # -------------------------------------------------------------------
        # EXECUTION PHASE (Cloning the JS setTimeout loop)
        # -------------------------------------------------------------------
        for i, cmd in enumerate(command_queue):
            if name == "living":
                # LEGACY BEHAVIOR:
                # setTimeout(sendonkyo, i*2*1000, otsend[i]);
                # First command sends immediately (i*2 = 0s).
                # Subsequent commands wait exactly 2 seconds.
                if i > 0:
                    print(f"[{name.upper()}] ⏳ Legacy wait 2.0s...")
                    await asyncio.sleep(2.0)

                print(f"[{name.upper()}] 🚀 Sending (LEGACY PACKING): {cmd}")
                writer.write(pack_legacy_malformed(cmd))
                await writer.drain()

            else:
                # MODERN BEHAVIOR (Cinema): Fast execution
                if i > 0:
                    await asyncio.sleep(0.2)

                print(f"[{name.upper()}] 🚀 Sending (STANDARD PACKING): !1{cmd}")
                writer.write(pack_standard(cmd))
                await writer.drain()

        # -------------------------------------------------------------------
        # LISTENING PHASE
        # -------------------------------------------------------------------
        buffer = b""
        end_time = asyncio.get_event_loop().time() + 3.0

        while asyncio.get_event_loop().time() < end_time:
            try:
                data = await asyncio.wait_for(reader.read(256), timeout=0.5)
                if not data:
                    print(f"[{name.upper()} ({ip})] 🔴 Connection closed cleanly by receiver.")
                    break

                buffer += data

                while b"ISCP" in buffer:
                    start_idx = buffer.find(b"ISCP")
                    if len(buffer) < start_idx + 16:
                        break

                    msg_size = int.from_bytes(buffer[start_idx + 8:start_idx + 12], 'big')
                    total_len = start_idx + 16 + msg_size

                    if len(buffer) < total_len:
                        break

                    payload = buffer[start_idx + 16:total_len]
                    buffer = buffer[total_len:]

                    msg_str = payload.decode('ascii', errors='ignore').strip().replace('\x1a', '')
                    print(f"[{name.upper()} ({ip})] 📡 Received: {msg_str}")

            except asyncio.TimeoutError:
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
    if len(sys.argv) < 2:
        print("Usage: python3 test_onkyo.py <cinema|living> [ON|OFF]")
        sys.exit(1)

    target_name = sys.argv[1].lower()
    if target_name not in RECEIVERS:
        print(f"Error: Invalid target switch '{sys.argv[1]}'.")
        sys.exit(1)

    target_ip = RECEIVERS[target_name]
    target_state = None

    if len(sys.argv) > 2:
        arg = sys.argv[2].upper()
        if arg in ["ON", "OFF"]:
            target_state = arg
        else:
            print("Usage: python3 test_onkyo.py <cinema|living> [ON|OFF]")
            sys.exit(1)

    await handle_receiver(target_name, target_ip, target_state)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript terminated by user.")