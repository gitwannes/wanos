# --- file: core/entity_registry.py ---
"""
System-owned stable entity_id ↔ idx registry.

Persists to entity_registry.auto.yaml at the WanOS root. Ids are assigned once at
device birth and frozen across display-name renames. See docs/todo/install_blocky.md.
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional, Set

import yaml
from loguru import logger


REGISTRY_FILENAME = "entity_registry.auto.yaml"

# Name-token classifiers for switch subclasses (checked in order).
_SSR_TOKENS = ("ssr",)
_SAFETY_TOKENS = ("safety", "wisc")
_VENT_TOKENS = ("ventilatie", "vent", "fan")


def slugify(name: str) -> str:
    """Normalize a display name into a stable slug segment."""
    if not name:
        return "unnamed"
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unnamed"


def classify_entity_prefix(
    *,
    device_type: Optional[str],
    name: Optional[str],
    origin: Optional[str] = None,
    hue_kind: Optional[str] = None,
) -> str:
    """
    Return the entity_id prefix (without trailing slug), e.g. 'switch.vent' or 'hue.light'.
    """
    dtype = (device_type or "unknown").lower().strip()
    origin_l = (origin or "").lower().strip()
    name_l = (name or "").lower()
    hue_kind_l = (hue_kind or "").lower().strip()

    if origin_l == "hue":
        return "hue.group" if hue_kind_l == "group" else "hue.light"

    if dtype == "blinds":
        return "blinds"
    if dtype == "power":
        return "sensor.power"
    if dtype == "temp_hum":
        return "sensor.temp_hum"
    if dtype == "energy":
        return "sensor.energy"
    if dtype == "fluid":
        return "sensor.fluid"
    if dtype == "door":
        return "sensor.door"
    if dtype == "speaker":
        return "media_player"
    if dtype == "scene":
        return "scene"
    if dtype == "unknown":
        return "unknown"

    if dtype == "sensor":
        if "temp" in name_l or "hum" in name_l:
            return "sensor.temp_hum"
        if "power" in name_l or "watt" in name_l:
            return "sensor.power"
        return "sensor.generic"

    if dtype in ("switch", "light"):
        # Non-Hue actuators (Z-Wave/RFX/Epson). Names may say "licht" but id stays switch.*.
        if any(tok in name_l for tok in _SSR_TOKENS):
            return "switch.ssr"
        if any(tok in name_l for tok in _SAFETY_TOKENS):
            return "switch.safety"
        if any(tok in name_l for tok in _VENT_TOKENS):
            return "switch.vent"
        return "switch"

    return "unknown"


class EntityRegistry:
    """Load/save entity_registry.auto.yaml and resolve entity_id ↔ idx."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.file_path = self.base_dir / REGISTRY_FILENAME
        self.temp_path = self.base_dir / f"{REGISTRY_FILENAME}.tmp"
        # idx (int) -> {entity_id, status?, name_at_birth?}
        self._by_idx: Dict[int, Dict[str, Any]] = {}
        self._entity_to_idx: Dict[str, int] = {}
        self._dirty: bool = False
        self._loaded: bool = False

    def load(self) -> None:
        if self._loaded:
            return
        self._by_idx.clear()
        self._entity_to_idx.clear()
        if not self.file_path.exists():
            logger.info("No entity_registry.auto.yaml found — will create on first birth.")
            self._loaded = True
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            entries = raw.get("entities", raw) if isinstance(raw, dict) else {}
            if not isinstance(entries, dict):
                entries = {}
            for key, val in entries.items():
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    continue
                if isinstance(val, str):
                    row = {"entity_id": val, "status": "active"}
                elif isinstance(val, dict) and val.get("entity_id"):
                    row = {
                        "entity_id": str(val["entity_id"]),
                        "status": str(val.get("status") or "active"),
                    }
                    if "name_at_birth" in val:
                        row["name_at_birth"] = val["name_at_birth"]
                else:
                    continue
                self._by_idx[idx] = row
                eid = row["entity_id"]
                if row.get("status") != "removed":
                    self._entity_to_idx[eid] = idx
            logger.success(f"Entity registry loaded ({len(self._by_idx)} rows) from {self.file_path.name}.")
        except Exception as e:
            logger.error(f"Failed to load entity_registry.auto.yaml: {e}")
        self._loaded = True

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            payload = {"entities": {}}
            for idx in sorted(self._by_idx.keys()):
                row = dict(self._by_idx[idx])
                payload["entities"][idx] = row
            serialized = yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True, sort_keys=False)
            with open(self.temp_path, "w", encoding="utf-8") as f:
                f.write(serialized)
            os.replace(self.temp_path, self.file_path)
            self._dirty = False
            logger.debug(f"Entity registry flushed ({len(self._by_idx)} rows).")
        except Exception as e:
            logger.error(f"Failed to save entity_registry.auto.yaml: {e}")

    def resolve(self, entity_id: str) -> Optional[int]:
        """entity_id → idx. Returns None if missing or removed."""
        self.load()
        if not entity_id:
            return None
        idx = self._entity_to_idx.get(entity_id)
        if idx is None:
            return None
        row = self._by_idx.get(idx) or {}
        if row.get("status") == "removed":
            return None
        return idx

    def entity_id_for(self, idx: int) -> Optional[str]:
        self.load()
        row = self._by_idx.get(int(idx))
        if not row:
            return None
        return row.get("entity_id")

    def mark_removed(self, idx: int) -> None:
        self.load()
        idx = int(idx)
        row = self._by_idx.get(idx)
        if not row:
            return
        if row.get("status") == "removed":
            return
        eid = row.get("entity_id")
        row["status"] = "removed"
        if eid and self._entity_to_idx.get(eid) == idx:
            self._entity_to_idx.pop(eid, None)
        self._dirty = True
        logger.info(f"Entity registry: idx {idx} ({eid}) marked status=removed.")

    def _allocate_unique(self, prefix: str, slug: str) -> str:
        base = f"{prefix}.{slug}"
        if base not in self._entity_to_idx:
            return base
        n = 2
        while f"{base}_{n}" in self._entity_to_idx:
            n += 1
        candidate = f"{base}_{n}"
        logger.warning(f"Entity id collision on '{base}' — using '{candidate}'.")
        return candidate

    def ensure(self, idx: int, meta: Dict[str, Any]) -> str:
        """
        Ensure meta has a frozen entity_id. Births if missing. Mutates meta in place.
        Returns the entity_id.
        """
        self.load()
        idx = int(idx)
        existing_row = self._by_idx.get(idx)
        if existing_row and existing_row.get("entity_id"):
            eid = str(existing_row["entity_id"])
            # Reactivate if it was removed but device is back
            if existing_row.get("status") == "removed":
                existing_row["status"] = "active"
                self._entity_to_idx[eid] = idx
                self._dirty = True
                logger.info(f"Entity registry: reactivated {eid} for idx {idx}.")
            meta["entity_id"] = eid
            return eid

        # Honor entity_id already stamped on meta (e.g. prior RAM) if registry empty for idx
        stamped = meta.get("entity_id")
        if stamped and stamped not in self._entity_to_idx:
            self._by_idx[idx] = {
                "entity_id": str(stamped),
                "status": "active",
                "name_at_birth": meta.get("name"),
            }
            self._entity_to_idx[str(stamped)] = idx
            self._dirty = True
            return str(stamped)

        prefix = classify_entity_prefix(
            device_type=meta.get("type"),
            name=meta.get("name"),
            origin=meta.get("origin"),
            hue_kind=meta.get("hue_kind"),
        )
        slug = slugify(meta.get("name") or f"idx_{idx}")
        eid = self._allocate_unique(prefix, slug)
        self._by_idx[idx] = {
            "entity_id": eid,
            "status": "active",
            "name_at_birth": meta.get("name"),
        }
        self._entity_to_idx[eid] = idx
        meta["entity_id"] = eid
        self._dirty = True
        logger.info(f"Entity birth: idx {idx} → {eid}")
        return eid

    def reconcile(self, device_metadata: Dict[Any, Any]) -> Set[int]:
        """
        Ensure every live metadata dict has an entity_id.
        Does NOT mark missing registry rows as removed — Z-Wave (and others) may
        load after the first rebuild; removal is only via explicit purge paths.
        """
        self.load()
        active: Set[int] = set()
        for key, meta in list(device_metadata.items()):
            if not isinstance(meta, dict):
                continue
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            active.add(idx)
            self.ensure(idx, meta)

        self.save()
        return active
