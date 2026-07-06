import soco
import socket
import concurrent.futures


def check_sonos_port(ip):
    # Knock on the Sonos API port (1400)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)  # Fast 500ms timeout
        try:
            s.connect((ip, 1400))
            return ip
        except:
            return None


def brute_force_scan():
    print("🔥 Bypassing UDP Multicast Lottery. Initiating TCP Brute-Force Sweep...")

    # 1. Determine local subnet automatically
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        my_ip = s.getsockname()[0]
    except Exception:
        my_ip = "10.32.251.1"  # Fallback to your known subnet
    finally:
        s.close()

    subnet_prefix = '.'.join(my_ip.split('.')[:3])
    print(f"📡 Scanning subnet: {subnet_prefix}.0/24 on Port 1400...")

    ips_to_test = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
    found_ips = []

    # 2. Sweep the subnet rapidly using 50 parallel threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        for result in executor.map(check_sonos_port, ips_to_test):
            if result:
                found_ips.append(result)

    if not found_ips:
        print("❌ No Sonos speakers found on this subnet.")
        return

    print(f"✅ Found {len(found_ips)} device(s) listening on Sonos port 1400. Extracting data...\n")

    # 3. Interrogate each found IP directly (Bypassing discovery completely)
    for count, ip in enumerate(found_ips, 1):
        try:
            speaker = soco.SoCo(ip)
            name = getattr(speaker, 'player_name', 'Unknown Name')
            uid = getattr(speaker, 'uid', 'Unknown UID')
            is_coord = getattr(speaker, 'is_coordinator', 'Unknown')

            print(f"{count}. [{name}]")
            print(f"   IP Address    : {ip}")
            print(f"   UID           : {uid}")
            print(f"   Is Coordinator: {is_coord}")

            try:
                info = speaker.get_speaker_info()
                model = info.get('model_name', 'Unknown Model')
                print(f"   Model         : {model}")
            except Exception:
                print(f"   Model         : Unknown/Legacy")

            try:
                state = speaker.get_current_transport_info().get('current_transport_state', 'UNKNOWN')
                vol = speaker.volume
                print(f"   Playback      : {state} (Volume: {vol}%)")

                # ⚡ Extract currently playing media to grab the exact URI for config.yaml
                if state in ['PLAYING', 'TRANSITIONING']:
                    media = speaker.get_current_media_info()
                    track = speaker.get_current_track_info()

                    # Radio streams usually populate media info, while Spotify/Apple Music populate track info
                    uri = media.get('uri') or track.get('uri', '')
                    title = track.get('title') or media.get('title') or 'Unknown Title'

                    if uri:
                        print(f"   Now Playing   : {title}")
                        print(f"   Station URI   : {uri}")
            except Exception:
                print(f"   Playback      : State Unreachable")

            print("-" * 40)
        except Exception as e:
            print(f"{count}. [Device at {ip}] - Error connecting: {e}")
            print("-" * 40)


if __name__ == "__main__":
    brute_force_scan()