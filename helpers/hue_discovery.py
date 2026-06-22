#!/usr/bin/env python3
# import urllib.request
import urllib.request
import json
import ssl
import sys

# 🛡️ Bypass self-signed certificate warnings (standard for local network Hue Bridge connections)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def generate_token(ip: str) -> str:
    print("\n" + "=" * 70)
    print(" 🚨 ACTION REQUIRED: PRESS THE HUE BRIDGE BUTTON 🚨")
    print("=" * 70)
    print("Please walk over to your Philips Hue Bridge and press the big circular link button.")
    input("Press ENTER here *after* you have pressed the physical button...")

    url = f"https://{ip}/api"
    # devicetype requires an 'app_name#instance_name' format. We request generateclientkey for v2 compatibility.
    payload = json.dumps({"devicetype": "wanos#bridge", "generateclientkey": True}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode('utf-8'))
            if isinstance(data, list) and "error" in data[0]:
                print(f"\n❌ Error: {data[0]['error']['description']}")
                print("Did you forget to press the link button? Try running the script again.")
                sys.exit(1)
            elif isinstance(data, list) and "success" in data[0]:
                token = data[0]['success']['username']
                print("\n✅ SUCCESS! Your Hue Application Key (Token) is:")
                print(f"   {token}")
                print("\n⚠️ SAVE THIS TOKEN in your config.yaml under hue -> application_key!")
                return token
    except Exception as e:
        print(f"\n❌ Failed to connect to the Hue bridge: {e}")
        sys.exit(1)


def fetch_v2_resource(ip: str, token: str, resource_type: str) -> list:
    url = f"https://{ip}/clip/v2/resource/{resource_type}"
    req = urllib.request.Request(url, method="GET")
    # API v2 requires the token to be passed in this specific header
    req.add_header("hue-application-key", token)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("data", [])
    except Exception as e:
        print(f"Error fetching {resource_type}: {e}")
        return []


def main():
    print("=== ⚡ WanOS Philips Hue Local Discovery Tool ===")
    default_ip = "10.32.251.73"
    ip_input = input(f"Enter your Hue Bridge local IP address (default {default_ip}): ").strip()
    ip = ip_input if ip_input else default_ip

    token = input("Enter your existing Hue API token (or leave blank to generate a new one): ").strip()

    if not token:
        token = generate_token(ip)

    print("\n🔍 Fetching your Smart Home topology from the Hue Bridge API v2...")

    lights = fetch_v2_resource(ip, token, "light")
    scenes = fetch_v2_resource(ip, token, "scene")
    rooms = fetch_v2_resource(ip, token, "room")
    zones = fetch_v2_resource(ip, token, "zone")

    # Combine rooms and zones for group extraction
    groups = rooms + zones

    print("\n" + "=" * 70)
    print(" 💡 LIGHTS (Copy these into config.yaml -> device_map)")
    print("=" * 70)
    # Start numbering at 50001 and increment for each light
    idx = 50001
    for light in lights:
        name = light.get("metadata", {}).get("name", "Unknown Light")
        l_id = light.get("id")
        print(f"    {idx}: \"{l_id}\"  # {name}")
        idx += 1

    print("\n" + "=" * 70)
    print(" 🎬 SCENES (Copy these into config.yaml -> scene_map)")
    print("=" * 70)
    for scene in scenes:
        name = scene.get("metadata", {}).get("name", "Unknown Scene")
        s_id = scene.get("id")

        # Cross-reference the room ID to print a friendly location tag
        room_name = "Unknown Room"
        group_ref = scene.get("group", {}).get("rid")
        if group_ref:
            for room in rooms:
                if room.get("id") == group_ref:
                    room_name = room.get("metadata", {}).get("name")
                    break

        # Strict WanOS Scene Sanitizer
        raw_key = f"hue_{room_name}_{name}"
        # Replace spaces with underscores for clean YAML mapping
        clean_name = "".join(
            c for c in raw_key.lower().replace(" ", "_").replace("-", "_") if c.isalnum() or c == "_")
        print(f"    \"{clean_name}\": \"{s_id}\"")

    print("\n" + "=" * 70)
    print(" 🏠 ROOMS & ZONES (Copy these into config_hue.yaml -> group_map)")
    print("=" * 70)
    group_idx = 51001
    for group in groups:
        name = group.get("metadata", {}).get("name", "Unknown Group")
        gl_id = None
        # Extract the hidden 'grouped_light' service inside the room/zone
        for service in group.get("services", []):
            if service.get("rtype") == "grouped_light":
                gl_id = service.get("rid")
                break

        if gl_id:
            print(f"    {group_idx}: \"{gl_id}\"  # {name}")
            group_idx += 1

    print("\n✅ Discovery complete. You now have the keys to the castle.")


if __name__ == "__main__":
    main()
