# --- file: core/bridge_api_key.py ---
"""Power dashboard machine API key (W2 / shared with W1 design).

Generate a 32-byte key once; store SHA-256 hex only under ~/.config/wanos/.
Plaintext is returned only at generate time.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_KEY_FILE = Path.home() / ".config" / "wanos" / "power_bridge_api_key.json"


def key_file_path() -> Path:
    override = (os.getenv("WANOS_POWER_BRIDGE_KEY_FILE") or "").strip()
    if override:
        return Path(override)
    return DEFAULT_KEY_FILE


def _hash_key(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def load_status() -> Dict[str, Any]:
    """Admin status: whether a key hash is configured."""
    path = key_file_path()
    if not path.is_file():
        return {"configured": False, "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"configured": False, "path": str(path), "error": "unreadable"}
    digest = str(data.get("sha256") or "").strip().lower()
    ok = len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    return {"configured": ok, "path": str(path)}


def verify_plain_key(plain: Optional[str]) -> bool:
    """Constant-time compare of presented key against stored hash."""
    if not plain or not isinstance(plain, str):
        return False
    presented = plain.strip()
    if not presented:
        return False
    path = key_file_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        expected = str(data.get("sha256") or "").strip().lower()
    except (OSError, json.JSONDecodeError):
        return False
    if len(expected) != 64:
        return False
    got = _hash_key(presented)
    return secrets.compare_digest(got, expected)


def generate_and_store() -> Tuple[str, Dict[str, Any]]:
    """Create a new 32-byte key (64 hex chars), store hash, return plaintext once."""
    plain = secrets.token_hex(32)
    digest = _hash_key(plain)
    path = key_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sha256": digest, "algo": "sha256", "bytes": 32}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return plain, {"configured": True, "path": str(path)}
