# --- file: core/analytics_config_store.py ---
"""Surgical read/write of sauna/IR effective_watts baselines in config.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from ruamel.yaml import YAML


def _root_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _config_path() -> Path:
    return _root_dir() / "config.yaml"


def _rt_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _load_root() -> Tuple[Any, Path]:
    path = _config_path()
    yaml = _rt_yaml()
    if not path.exists():
        raise FileNotFoundError(f"Runtime configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        root = yaml.load(fh)
    if not isinstance(root, dict):
        raise ValueError("config.yaml root must be a mapping")
    return root, path


def read_effective_watts() -> Dict[str, float]:
    """Return calc-model baseline watts from disk."""
    root, _ = _load_root()
    sauna = root.get("sauna") if isinstance(root.get("sauna"), dict) else {}
    ir = root.get("ir") if isinstance(root.get("ir"), dict) else {}
    return {
        "ir_effective_watts": float(ir.get("effective_watts", 525.0)),
        "sauna_effective_watts_u": float(sauna.get("effective_watts_u", 3500.0)),
        "sauna_effective_watts_v": float(sauna.get("effective_watts_v", 3500.0)),
        "sauna_effective_watts_w": float(sauna.get("effective_watts_w", 2000.0)),
    }


def write_effective_watts(
    *,
    ir_effective_watts: float,
    sauna_effective_watts_u: float,
    sauna_effective_watts_v: float,
    sauna_effective_watts_w: float,
) -> Dict[str, float]:
    """Persist calc-model baselines to config.yaml; return written values."""
    for label, val in (
        ("ir_effective_watts", ir_effective_watts),
        ("sauna_effective_watts_u", sauna_effective_watts_u),
        ("sauna_effective_watts_v", sauna_effective_watts_v),
        ("sauna_effective_watts_w", sauna_effective_watts_w),
    ):
        if not isinstance(val, (int, float)) or val <= 0 or val > 50000:
            raise ValueError(f"{label} must be a positive number <= 50000")

    root, path = _load_root()
    if not isinstance(root.get("sauna"), dict):
        root["sauna"] = {}
    if not isinstance(root.get("ir"), dict):
        root["ir"] = {}

    root["sauna"]["effective_watts_u"] = float(sauna_effective_watts_u)
    root["sauna"]["effective_watts_v"] = float(sauna_effective_watts_v)
    root["sauna"]["effective_watts_w"] = float(sauna_effective_watts_w)
    root["ir"]["effective_watts"] = float(ir_effective_watts)

    yaml = _rt_yaml()
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(root, fh)

    return read_effective_watts()
