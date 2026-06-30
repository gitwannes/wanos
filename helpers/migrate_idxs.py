"""
WanOS Configuration Migration Tool
----------------------------------
This script safely traverses `config.yaml`, searching explicitly defined
hardware arrays (dashboard, lighting, automations) for legacy Domoticz IDXs (< 10000).
It translates them to their new Z-Wave counterparts based on the mappings found
in `config_zwave.yaml`, and exports a non-destructive `config_migrated.yaml` file.

!!! Be careful not to run Robocopy while doing this: it might delete files!

# 1. Create a temporary virtual environment folder
python3 -m venv migration_venv

# 2. Activate the virtual environment
source migration_venv/bin/activate

# 3. Install the required YAML library
pip install ruamel.yaml

# 4. Copy the configfiles to this folder
cp ../config.yaml .
cp ../config_zwave.yaml .

# 5. Run the script (assuming you placed it in the same folder as your config files)
python3 migrate_idxs.py

# 6. Check the script output

# 7. If all correct: copy the new script to the app
cp ./config_migrated.yaml ../config.yaml

# 8. Reload the config on the admin page

# 9. When done, deactivate and delete the temporary bubble
deactivate
rm -rf migration_venv
"""

import sys
from pathlib import Path
from typing import Any, Dict, Set
from ruamel.yaml import YAML


def replace_dict_key_preserve_comments(cm: Any, old_key: int, new_key: int) -> None:
    """
    Replaces a dictionary key in a ruamel.yaml CommentedMap while ensuring
    that its position and any inline/preceding comments are perfectly preserved.
    """
    if old_key not in cm:
        return

    # Find the exact positional index of the old key
    keys = list(cm.keys())
    pos = keys.index(old_key)
    val = cm[old_key]

    # Insert the new key at the exact same position
    cm.insert(pos, new_key, val)

    # Transfer the comment object from the old key to the new key
    if hasattr(cm, 'ca') and old_key in cm.ca.items:
        cm.ca.items[new_key] = cm.ca.items.pop(old_key)

    # Delete the old key
    del cm[old_key]


def process_automation_node(node: Any, found_set: Set[int], used_set: Set[int], t_map: Dict[int, int]) -> None:
    """Recursively parses automation conditions/actions to update the 'idx' fields."""
    if isinstance(node, dict) and 'idx' in node:
        val = node.get('idx')
        if isinstance(val, int) and val < 10000:
            found_set.add(val)
            if val in t_map:
                node['idx'] = t_map[val]
                used_set.add(val)
    elif isinstance(node, list):
        for item in node:
            process_automation_node(item, found_set, used_set, t_map)


def main():
    # --- 1. SETUP PATHS ---
    base_dir = Path(__file__).resolve().parent
    config_path = base_dir / "config.yaml"
    zwave_path = base_dir / "config_zwave.yaml"
    output_path = base_dir / "config_migrated.yaml"

    if not config_path.exists() or not zwave_path.exists():
        print(f"❌ Error: Cannot find config files.")
        print(f"Ensure {config_path.name} and {zwave_path.name} exist in the current directory.")
        sys.exit(1)

    yaml = YAML()
    yaml.preserve_quotes = True

    # Force standard 2-space indentation for lists
    yaml.indent(mapping=2, sequence=4, offset=2)

    # Disable the 80-character auto-wrap limit to keep inline arrays [1, 2, 3] intact
    yaml.width = 4096

    # --- 2. BUILD TRANSLATION MATRIX ---
    print("⏳ Parsing Z-Wave translation matrices...")
    try:
        with open(zwave_path, "r", encoding="utf-8") as f:
            zwave_data = yaml.load(f)
    except Exception as e:
        print(f"❌ Failed to parse {zwave_path.name}: {e}")
        sys.exit(1)

    translation_map: Dict[int, int] = {}
    zwave_map = zwave_data.get('zwave', {}).get('device_map', {})

    for z_idx, mapping_str in zwave_map.items():
        parts = [s.strip() for s in mapping_str.split('|')]
        # If the string has a 3rd parameter, we treat it as the legacy Domoticz IDX
        if len(parts) >= 3:
            try:
                dom_idx = int(parts[2])
                translation_map[dom_idx] = int(z_idx)
            except ValueError:
                continue

    print(f"✅ Found {len(translation_map)} valid legacy mappings in {zwave_path.name}.")

    # --- 3. PARSE MAIN CONFIGURATION ---
    print(f"⏳ Loading {config_path.name} safely into memory...")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.load(f)
    except Exception as e:
        print(f"❌ Failed to parse {config_path.name}: {e}")
        sys.exit(1)

    found_dom_idxs: Set[int] = set()
    used_translations: Set[int] = set()

    # --- 4. EXECUTE SURGICAL REPLACEMENTS ---
    print("⏳ Running surgical replacement across target sections...")

    # Target A: Dashboard Map (Dictionary Keys)
    if 'dashboard' in config_data and isinstance(config_data['dashboard'], dict):
        dashboard = config_data['dashboard']
        # Convert keys to a list first because we are mutating the dictionary during iteration
        for old_idx in list(dashboard.keys()):
            if isinstance(old_idx, int) and old_idx < 10000:
                found_dom_idxs.add(old_idx)
                if old_idx in translation_map:
                    new_idx = translation_map[old_idx]
                    replace_dict_key_preserve_comments(dashboard, old_idx, new_idx)
                    used_translations.add(old_idx)

    # Target B: Lighting Arrays
    if 'lighting' in config_data and isinstance(config_data['lighting'], dict):
        lighting = config_data['lighting']

        # B1: managed_lights (List of ints)
        if 'managed_lights' in lighting and isinstance(lighting['managed_lights'], list):
            ml_list = lighting['managed_lights']
            for i, val in enumerate(ml_list):
                if isinstance(val, int) and val < 10000:
                    found_dom_idxs.add(val)
                    if val in translation_map:
                        ml_list[i] = translation_map[val]
                        used_translations.add(val)

        # B2: auto_off_delays (Dictionary Keys)
        if 'auto_off_delays' in lighting and isinstance(lighting['auto_off_delays'], dict):
            delays = lighting['auto_off_delays']
            for old_idx in list(delays.keys()):
                if isinstance(old_idx, int) and old_idx < 10000:
                    found_dom_idxs.add(old_idx)
                    if old_idx in translation_map:
                        new_idx = translation_map[old_idx]
                        replace_dict_key_preserve_comments(delays, old_idx, new_idx)
                        used_translations.add(old_idx)

    # Target C: Automations (Deep Traversal)
    if 'automations' in config_data and isinstance(config_data['automations'], list):
        for rule in config_data['automations']:
            if 'trigger' in rule:
                process_automation_node(rule['trigger'], found_dom_idxs, used_translations, translation_map)
            if 'conditions' in rule:
                process_automation_node(rule['conditions'], found_dom_idxs, used_translations, translation_map)
            if 'actions' in rule:
                process_automation_node(rule['actions'], found_dom_idxs, used_translations, translation_map)

    # --- 5. SAVE MIGRATED OUTPUT ---
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)
        print(f"✅ Migration successful! Output safely saved to: {output_path.name}")
    except Exception as e:
        print(f"❌ Failed to write {output_path.name}: {e}")
        sys.exit(1)

    # --- 6. GENERATE DISCREPANCY REPORTS ---
    print("\n" + "=" * 50)
    print("📊 MIGRATION DISCREPANCY REPORT")
    print("=" * 50)

    # Report 1: Unmapped legacy nodes remaining in the config
    unmapped_remaining = found_dom_idxs - set(translation_map.keys())
    print("\n🔴 LIST 1: Legacy Domoticz IDXs (< 10000) remaining in config.yaml")
    print(
        "   (These nodes were found in dashboard/lighting/automations but had NO matching mapping in config_zwave.yaml)")
    if unmapped_remaining:
        for idx in sorted(list(unmapped_remaining)):
            print(f"   - IDX {idx}")
    else:
        print("   -> Clean! No unmapped legacy IDXs found.")

    # Report 2: Unused mappings in config_zwave
    unused_zwave_mappings = set(translation_map.keys()) - used_translations
    print("\n🟡 LIST 2: Orphaned Z-Wave Mappings")
    print(
        "   (These Domoticz IDXs were defined as comments in config_zwave.yaml, but were NEVER found inside config.yaml)")
    if unused_zwave_mappings:
        for dom_idx in sorted(list(unused_zwave_mappings)):
            z_idx = translation_map[dom_idx]
            print(f"   - Domoticz {dom_idx} -> Z-Wave {z_idx}")
    else:
        print("   -> Clean! All Z-Wave mappings were successfully utilized.")

    print("\nDone. Please manually review config_migrated.yaml and replace config.yaml when ready.")


if __name__ == "__main__":
    main()