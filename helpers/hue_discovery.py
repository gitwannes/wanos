#!/usr/bin/env python3
import urllib.request
import json
import ssl
import sys
import os
import argparse

# 🛡️ Bypass self-signed certificate warnings (standard for local network Hue Bridge connections)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ⚡ Master List of Philips Hue Default/Gallery Scene Names (English + Dutch) to facilitate filtering
HUE_DEFAULT_SCENE_NAMES = {
    # English Defaults
    "bright", "dimmed", "nightlight", "rest", "relax", "read", "concentrate", "energise",
    "savanna sunset", "tropical twilight", "arctic aurora", "spring blossom", "chinatown",
    "ibiza", "tokyo", "motown", "golden ponds", "sunset savanna", "blossom spring",
    "forest adventure", "blue planet", "painted sky", "amber bloom", "orange fields",
    "soho", "magneto", "disturbia", "hal", "winter mountain", "spring lake",

    # Dutch (Nederlands) Defaults
    "helder", "gedimd", "nachtlampje", "ontspannen", "lezen", "concentreren", "energie",
    "savanne zonsondergang", "tropische schemering", "arctische dageraad", "lentebloesem"
}


def _find_file_path(filename: str) -> str:
    """
    Intelligently searches for a configuration file.
    Checks the current working directory first, then checks the parent directory
    to ensure scripts run from subfolders find the root config files.
    """
    if os.path.exists(filename):
        return filename

    parent_path = os.path.join("..", filename)
    if os.path.exists(parent_path):
        return parent_path

    return ""


def _get_env_token() -> str:
    """Safely parses the local .env file without requiring the python-dotenv pip package."""
    token = os.getenv("HUE_API_KEY", "")
    if not token:
        env_path = _find_file_path(".env")
        if env_path:
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("HUE_API_KEY="):
                            token = line.split("=", 1)[1].strip().strip('"\'')
                            break
            except Exception as e:
                print(f"⚠️ Warning: Could not read .env file: {e}")
    return token


def _get_config_ip() -> str:
    """
    Safely parses configuration files to extract the Hue bridge IP without requiring PyYAML.
    Checks config_hue.yaml first (split-config architecture), then falls back to config.yaml.
    """
    ip = ""
    for target_file in ["config_hue.yaml", "config.yaml"]:
        config_path = _find_file_path(target_file)
        if config_path:
            try:
                with open(config_path, "r") as f:
                    in_hue_block = False
                    for line in f:
                        stripped = line.strip()

                        if stripped.startswith("hue:"):
                            in_hue_block = True
                            continue

                        if target_file == "config_hue.yaml" and stripped.startswith("bridge_ip:"):
                            in_hue_block = True

                        if in_hue_block:
                            if target_file == "config.yaml" and not line.startswith(" ") and not line.startswith(
                                    "\t") and stripped != "" and not stripped.startswith("#"):
                                in_hue_block = False
                                continue

                            if stripped.startswith("bridge_ip:"):
                                parts = stripped.split(":", 1)
                                if len(parts) > 1:
                                    ip = parts[1].strip().strip('"\'')
                                    return ip
            except Exception as e:
                print(f"⚠️ Warning: Could not read {target_file}: {e}")
    return ip


def generate_token(ip: str) -> str:
    print("\n" + "=" * 70)
    print(" 🚨 ACTION REQUIRED: PRESS THE HUE BRIDGE BUTTON 🚨")
    print("=" * 70)
    print("Please walk over to your Philips Hue Bridge and press the big circular link button.")
    input("Press ENTER here *after* you have pressed the physical button...")

    url = f"https://{ip}/api"
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
                print("\n⚠️ SAVE THIS TOKEN in your .env file under HUE_API_KEY!")
                return token
    except Exception as e:
        print(f"\n❌ Failed to connect to the Hue bridge: {e}")
        sys.exit(1)


def fetch_v2_resource(ip: str, token: str, resource_type: str) -> list:
    url = f"https://{ip}/clip/v2/resource/{resource_type}"
    req = urllib.request.Request(url, method="GET")
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
    # Setup command-line argument switch processing
    parser = argparse.ArgumentParser(description="WanOS Philips Hue Local Discovery Tool (API v2)")
    parser.add_argument(
        '--custom-only',
        action='store_true',
        help='Filters out all official factory gallery/default scenes, leaving only your custom ones.'
    )
    args = parser.parse_args()

    print("=== ⚡ WanOS Philips Hue Local Discovery Tool ===")

    # 1. Attempt to resolve the Bridge IP from config files
    ip = _get_config_ip()
    if ip:
        print(f"✅ Found Hue Bridge IP in configuration: {ip}")
    else:
        default_ip = "10.32.251.73"
        ip_input = input(f"Enter your Hue Bridge local IP address (default {default_ip}): ").strip()
        ip = ip_input if ip_input else default_ip

    # 2. Attempt to resolve the API Token from environmental variable fields
    token = ""
    env_token = _get_env_token()

    if env_token:
        masked_token = f"{env_token[:6]}.......{env_token[-6:]}" if len(env_token) > 12 else "***"
        print(f"✅ Found existing HUE_API_KEY in configuration environment: {masked_token}")
        token = env_token
    else:
        token = input("\nEnter your existing Hue API token (or leave blank to generate a new one): ").strip()

    # 3. Generate token if completely missing
    if not token:
        token = generate_token(ip)

    print("\n🔍 Fetching your Smart Home topology from the Hue Bridge API v2...")

    lights = fetch_v2_resource(ip, token, "light")
    scenes = fetch_v2_resource(ip, token, "scene")
    rooms = fetch_v2_resource(ip, token, "room")
    zones = fetch_v2_resource(ip, token, "zone")

    # Combine rooms and zones for group extraction processing
    groups = rooms + zones

    print("\n" + "=" * 70)
    print(" 💡 LIGHTS (Copy these into config.yaml -> device_map)")
    print("=" * 70)
    idx = 50001
    for light in lights:
        name = light.get("metadata", {}).get("name", "Unknown Light")
        l_id = light.get("id")
        print(f"    {idx}: \"{l_id}\"  # {name}")
        idx += 1

    print("\n" + "=" * 70)
    print(" 🏠 ROOMS & ZONES (Copy these into config_hue.yaml -> group_map)")
    print("=" * 70)
    group_idx = 51001

    room_to_idx = {}
    for group in groups:
        name = group.get("metadata", {}).get("name", "Unknown Group")
        group_id = group.get("id")
        gl_id = None

        for service in group.get("services", []):
            if service.get("rtype") == "grouped_light":
                gl_id = service.get("rid")
                break

        if gl_id:
            print(f"    {group_idx}: \"{gl_id}\"  # {name}")
            room_to_idx[group_id] = {"idx": group_idx, "name": name}
            group_idx += 1

    print("\n" + "=" * 70)
    if args.custom_only:
        print(" 🎬 CUSTOM SCENES (Excluding factory defaults via --custom-only)")
    else:
        print(" 🎬 ALL REGISTERED SCENES (Run with --custom-only to isolate your own)")
    print("=" * 70)

    # Group scenes inside respective parent Room/Zone structures
    scenes_by_room = {}
    for scene in scenes:
        name = scene.get("metadata", {}).get("name", "Unknown Scene")
        group_ref = scene.get("group", {}).get("rid")

        # Switch Intercept: Skip if the scene belongs to an unmapped configuration space
        if group_ref not in room_to_idx:
            continue

        # Switch Intercept: If the switch is armed, reject any scene matching factory names
        if args.custom_only and name.lower() in HUE_DEFAULT_SCENE_NAMES:
            continue

        room_info = room_to_idx[group_ref]
        r_idx = room_info["idx"]
        r_name = room_info["name"]

        if r_idx not in scenes_by_room:
            scenes_by_room[r_idx] = {"room_name": r_name, "scenes": []}

        scenes_by_room[r_idx]["scenes"].append(name)

    # Output formatting engine execution
    for r_idx, data in scenes_by_room.items():
        if not data["scenes"]:
            continue
        print(f"\n  Room: {data['room_name']} (WanOS IDX: {r_idx})")
        for s_name in data["scenes"]:
            clean_name = "".join(
                c for c in s_name.lower().replace(" ", "_").replace("-", "_") if c.isalnum() or c == "_")
            print(f"    - scene: \"{s_name}\"  # Backend translates this to -> '{clean_name}'")

    print("\n✅ Discovery complete. Clean topology mapped successfully.")


if __name__ == "__main__":
    main()