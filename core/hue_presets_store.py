# --- file: core/hue_presets_store.py ---
"""Surgical read/write of hue.presets in config_hue_presets.auto.yaml (B9A)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from core.automations_store import load_automations_roundtrip
from core.config import HuePresetConfig

HUE_PRESETS_AUTO_FILENAME = "config_hue_presets.auto.yaml"


def _root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _hue_presets_auto_path() -> Path:
    return _root_dir() / HUE_PRESETS_AUTO_FILENAME


def _rt_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_hue_presets_roundtrip() -> Tuple[Any, Path]:
    """Load Pi-owned presets file; create hue.presets skeleton when missing."""
    path = _hue_presets_auto_path()
    yaml = _rt_yaml()
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            root = yaml.load(f)
    else:
        root = CommentedMap()
    if not isinstance(root, dict):
        root = CommentedMap()
    _presets_map(_hue_map(root))
    return root, path


def _dump_hue_presets(root: Any, path: Path) -> None:
    yaml = _rt_yaml()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(root, f)


def _hue_map(root: Any) -> CommentedMap:
    if not isinstance(root, dict):
        raise ValueError(f"{HUE_PRESETS_AUTO_FILENAME} root must be a mapping")
    hue = root.get("hue")
    if hue is None:
        hue = CommentedMap()
        root["hue"] = hue
    if not isinstance(hue, dict):
        raise ValueError(f"{HUE_PRESETS_AUTO_FILENAME} hue: must be a mapping")
    return hue


def _presets_map(hue: Any) -> CommentedMap:
    presets = hue.get("presets")
    if presets is None:
        presets = CommentedMap()
        hue["presets"] = presets
    if not isinstance(presets, dict):
        raise ValueError("hue.presets must be a mapping")
    return presets


def _preset_entry_from_raw(key: str, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one YAML preset row (always includes xy for the Explorer wheel)."""
    k = str(key).strip()
    if not k or not isinstance(raw, dict):
        return None
    try:
        cfg = HuePresetConfig(
            name=str(raw.get("name") or k),
            bri=int(raw.get("bri") or 0),
            xy=list(raw["xy"]) if raw.get("xy") is not None else None,
            rgb=raw.get("rgb"),
        )
    except (ValueError, TypeError):
        return None
    entry: Dict[str, Any] = {
        "name": cfg.name,
        "bri": int(cfg.bri),
        "xy": list(cfg.xy or []),
    }
    if cfg.rgb:
        entry["rgb"] = str(cfg.rgb)
    return entry


def _legacy_presets_from_main_hue_yaml() -> Dict[str, Dict[str, Any]]:
    """Read presets still embedded in config_hue.yaml (pre-split or pre-migration)."""
    path = _root_dir() / "config_hue.yaml"
    if not path.exists():
        return {}
    yaml = _rt_yaml()
    with path.open("r", encoding="utf-8") as f:
        root = yaml.load(f)
    if not isinstance(root, dict):
        return {}
    hue = root.get("hue")
    if not isinstance(hue, dict):
        return {}
    presets = hue.get("presets")
    if not isinstance(presets, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for key, raw in presets.items():
        entry = _preset_entry_from_raw(str(key), raw if isinstance(raw, dict) else {})
        if entry:
            out[str(key).strip()] = entry
    return out


def read_presets() -> Dict[str, Dict[str, Any]]:
    """Return presets as plain dict key → {name, bri, xy, rgb?}."""
    auto_path = _hue_presets_auto_path()
    if auto_path.exists():
        root, _ = load_hue_presets_roundtrip()
        preset_items = _presets_map(_hue_map(root)).items()
    else:
        return _legacy_presets_from_main_hue_yaml()

    out: Dict[str, Dict[str, Any]] = {}
    for key, raw in preset_items:
        if not isinstance(raw, dict):
            continue
        entry = _preset_entry_from_raw(str(key), raw)
        if entry:
            out[str(key).strip()] = entry
    return out


def _normalized_display_name(name: str) -> str:
    return (name or "").strip().casefold()


def display_name_taken(
    presets: Dict[str, Any],
    display_name: str,
    *,
    exclude_key: Optional[str] = None,
) -> bool:
    """True when another preset already uses this display name (case-insensitive)."""
    target = _normalized_display_name(display_name)
    if not target:
        return False
    skip = (exclude_key or "").strip()
    for key, raw in presets.items():
        k = str(key).strip()
        if skip and k == skip:
            continue
        if not isinstance(raw, dict):
            continue
        existing = _normalized_display_name(str(raw.get("name") or k))
        if existing == target:
            return True
    return False


def slugify_preset_key(display_name: str, existing: Dict[str, Any]) -> str:
    """Unique text key from display name (never collide with existing keys)."""
    base = re.sub(r"[^a-z0-9]+", "_", (display_name or "").strip().lower()).strip("_")
    if not base:
        base = "preset"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


def rule_names_using_preset(preset_key: str) -> List[str]:
    """Scan automations.auto.yaml for actions with preset: <key>; return rule names."""
    key = str(preset_key).strip()
    if not key:
        return []
    root, _ = load_automations_roundtrip()
    autos = root.get("automations") if isinstance(root, dict) else None
    if not isinstance(autos, list):
        return []
    names: List[str] = []
    for rule in autos:
        if not isinstance(rule, dict):
            continue
        hit = False
        # v2 cases
        for case in rule.get("cases") or []:
            if not isinstance(case, dict):
                continue
            for act in case.get("actions") or []:
                if isinstance(act, dict) and str(act.get("preset") or "") == key:
                    hit = True
                    break
            if hit:
                break
        # flat / Y1 branches
        if not hit:
            for branch_key in ("actions", "on", "off"):
                branch = rule.get(branch_key)
                acts = branch.get("actions") if isinstance(branch, dict) else branch
                if not isinstance(acts, list):
                    continue
                for act in acts:
                    if isinstance(act, dict) and str(act.get("preset") or "") == key:
                        hit = True
                        break
                if hit:
                    break
        if hit:
            nm = str(rule.get("name") or rule.get("id") or "?").strip()
            if nm and nm not in names:
                names.append(nm)
    return names


def add_preset(*, name: str, bri: int, xy: Optional[List[float]] = None, rgb: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    Create a new preset key from display name + colour.
    Never overwrites an existing key. Returns (key, entry).
    """
    display = (name or "").strip()
    if not display:
        raise ValueError("Preset name is required")
    # Validate via Pydantic (normalizes rgb→xy)
    cfg = HuePresetConfig(name=display, bri=int(bri), xy=xy, rgb=rgb)
    root, path = load_hue_presets_roundtrip()
    hue = _hue_map(root)
    presets = _presets_map(hue)
    if display_name_taken(presets, display):
        raise ValueError(f"Preset display name already exists: {display}")
    key = slugify_preset_key(display, presets)
    if key in presets:
        raise ValueError(f"Preset key already exists: {key}")
    entry = CommentedMap()
    entry["name"] = cfg.name
    entry["bri"] = int(cfg.bri)
    # Persist exactly one colour key (Pydantic rejects both on reload).
    if rgb is not None:
        entry["rgb"] = cfg.rgb
    elif cfg.xy is not None:
        entry["xy"] = list(cfg.xy)
    presets[key] = entry
    _dump_hue_presets(root, path)
    return key, {"name": cfg.name, "bri": int(cfg.bri), "xy": list(cfg.xy or [])}


def rename_preset(key: str, new_name: str) -> Dict[str, Any]:
    """Change display name only; YAML key unchanged."""
    k = str(key).strip()
    display = (new_name or "").strip()
    if not k:
        raise ValueError("Preset key is required")
    if not display:
        raise ValueError("Preset name is required")
    root, path = load_hue_presets_roundtrip()
    hue = _hue_map(root)
    presets = _presets_map(hue)
    if k not in presets:
        raise KeyError(f"Unknown preset key: {k}")
    if display_name_taken(presets, display, exclude_key=k):
        raise ValueError(f"Preset display name already exists: {display}")
    raw = presets[k]
    if not isinstance(raw, dict):
        raise ValueError(f"Corrupt preset entry: {k}")
    raw["name"] = display
    _dump_hue_presets(root, path)
    out: Dict[str, Any] = {"name": display, "bri": int(raw.get("bri") or 0)}
    if raw.get("xy") is not None:
        out["xy"] = list(raw["xy"])
    if raw.get("rgb") is not None:
        out["rgb"] = raw["rgb"]
    return out


def delete_preset(key: str) -> None:
    """Delete preset; raises ValueError if automations still reference the key."""
    k = str(key).strip()
    if not k:
        raise ValueError("Preset key is required")
    usages = rule_names_using_preset(k)
    if usages:
        raise ValueError(
            f"Preset in use by: {', '.join(usages)}"
        )
    root, path = load_hue_presets_roundtrip()
    hue = _hue_map(root)
    presets = _presets_map(hue)
    if k not in presets:
        raise KeyError(f"Unknown preset key: {k}")
    del presets[k]
    _dump_hue_presets(root, path)
