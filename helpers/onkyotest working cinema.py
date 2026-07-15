#!/usr/bin/env python3
import asyncio
import sys
from typing import Optional, Dict

RECEIVERS: Dict[str, str] = {
    "cinema": "10.32.251.35",
    "living": "10.32.251.78"
}


def pack_standard(command: str) -> bytes:
    """Standard, perfect eISCP packing (including the required EOF byte)."""
    # De \x1a is teruggeplaatst, dit repareert de Cinema receiver!
    data = f"!1{command}\x1a\r\n".encode('ascii')
    header = b'ISCP' + (16).to_bytes(4, 'big') + len(data).to_bytes(4, 'big') + b'\x01\x00\x00\x00'
    return header + data


async def handle_receiver(name: str, ip: str, target_state: Optional[str] = None) -> None:
    print(f"[{name.upper()}] Attempting TCP connection on port 60128...")

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 60128), timeout=5.0)
        print(f"[{name.upper()}] 🟢 Connected successfully.")

        pacing_delay = 2.0 if name == "living" else 0.2

        if target_state == "ON":
            print(f"[{name.upper()}] ⚡ Sending Power ON...")
            writer.write(pack_standard("PWR01"))
            await writer.drain()
            await asyncio.sleep(pacing_delay)

        elif target_state == "OFF":
            print(f"[{name.upper()}] 💤 Sending Power OFF...")
            writer.write(pack_standard("PWR00"))
            await writer.drain()
            await asyncio.sleep(pacing_delay)

        print(f"[{name.upper()}] 🔍 Querying Power Status...")
        writer.write(pack_standard("PWRQSTN"))
        await writer.drain()
        await asyncio.sleep(pacing_delay)

        print(f"[{name.upper()}] 🔍 Querying Volume Status...")
        writer.write(pack_standard("MVLQSTN"))
        await writer.drain()

        buffer = b""
        end_time = asyncio.get_event_loop().time() + 3.0

        while asyncio.get_event_loop().time() < end_time:
            try:
                data = await asyncio.wait_for(reader.read(256), timeout=0.5)
                if not data:
                    print(f"[{name.upper()}] 🔴 Connection closed cleanly by receiver.")
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

                    # Verwijder de \x1a visueel uit de print-output zodat de logs netjes blijven
                    msg_str = payload.decode('ascii', errors='ignore').strip().replace('\x1a', '')
                    print(f"[{name.upper()}] 📡 Received: {msg_str}")

            except asyncio.TimeoutError:
                continue

        print(f"[{name.upper()}] Closing TCP socket.")
        writer.close()
        await writer.wait_closed()

    except Exception as e:
        print(f"[{name.upper()}] 🔴 Failed: {repr(e)}")


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