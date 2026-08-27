#!/usr/bin/env python3
# --- file: helpers/lg_webos_power.py ---
"""
Standalone LG webOS TV discovery + power / Netflix probe (G16 scout).

Uses pywebostv for SSAP over the LAN (Python 3.9+; matches WanOS Pi).
Cold power-on needs Wake-on-LAN (TV setting + MAC) — pywebostv has no
SSAP power_on. Pairing: accept the prompt on the TV the first time.

Pairing keys are stored OUTSIDE the repo tree (default:
~/.config/wanos/lg_webos_client_keys.json). Keys next to this script are
wiped by wanos-sync rsync --delete (Windows → Pi mirror).

Requires: pip install pywebostv wakeonlan

Examples:
  python helpers/lg_webos_power.py discover
  python helpers/lg_webos_power.py status --host 10.32.251.39
  python helpers/lg_webos_power.py set --host 10.32.251.39 --on --mac 20:17:42:f7:d9:4b
  python helpers/lg_webos_power.py set --host 10.32.251.39 --netflix
  python helpers/lg_webos_power.py set --host 10.32.251.39 --on --netflix --mac 20:17:42:f7:d9:4b
  python helpers/lg_webos_power.py set --host 10.32.251.39 --off

Power sense: SSAP ports open → ON; closed → OFF.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# webOS SSAP WebSocket ports (ws / wss)
WS_PORT = 3000
WSS_PORT = 3001

# Survives wanos-sync --delete of ~/wanos (repo mirror)
DEFAULT_KEY_FILE = Path.home() / ".config" / "wanos" / "lg_webos_client_keys.json"
# Legacy location (inside repo) — read/migrate only; do not write here by default
LEGACY_KEY_FILE = Path(__file__).resolve().parent / "lg_webos_client_keys.json"


def _require_pywebostv() -> None:
    """Fail fast with an install hint if pywebostv is missing."""
    try:
        import pywebostv  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "pywebostv is not installed. Run: pip install pywebostv wakeonlan"
        ) from exc


def _local_subnet_prefix() -> str:
    """Return a.b.c for the primary local IPv4 interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        my_ip = sock.getsockname()[0]
    except OSError as exc:
        raise SystemExit(f"Could not determine local IP: {exc}") from exc
    finally:
        sock.close()
    parts = my_ip.split(".")
    if len(parts) != 4:
        raise SystemExit(f"Unexpected local IP format: {my_ip}")
    return ".".join(parts[:3])


def _tcp_open(ip: str, port: int, timeout: float = 0.4) -> bool:
    """Return True if TCP connect to ip:port succeeds within timeout."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((ip, port))
            return True
        except OSError:
            return False


def scan_subnet_for_webos(subnet_prefix: Optional[str] = None) -> List[str]:
    """Sweep /24 for hosts listening on webOS SSAP ports (3000 or 3001)."""
    prefix = subnet_prefix or _local_subnet_prefix()
    print(f"TCP scan {prefix}.0/24 for ports {WS_PORT}/{WSS_PORT}...")
    candidates = [f"{prefix}.{i}" for i in range(1, 255)]
    found: List[str] = []

    def probe(ip: str) -> Optional[str]:
        if _tcp_open(ip, WS_PORT) or _tcp_open(ip, WSS_PORT):
            return ip
        return None

    with ThreadPoolExecutor(max_workers=64) as pool:
        for hit in pool.map(probe, candidates):
            if hit:
                found.append(hit)

    return sorted(found, key=lambda s: tuple(int(p) for p in s.split(".")))


def ssdp_discover_hosts() -> List[str]:
    """SSDP discovery for LG MediaRenderer hosts (same filter as pywebostv)."""
    from pywebostv.discovery import discover

    hosts: List[str] = []
    try:
        found = discover(
            "urn:schemas-upnp-org:device:MediaRenderer:1",
            keyword="LG",
            hosts=True,
            retries=3,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"SSDP discover failed: {exc}")
        return hosts

    for ip in sorted(found):
        hosts.append(str(ip))
        print(f"SSDP found {ip}")
    return hosts


def _extract_client_key(value: Any) -> Optional[str]:
    """Normalise a per-host key file entry to a client_key string."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key_name in ("client_key", "client-key"):
            raw = value.get(key_name)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


def resolve_key_file(path: Path) -> Path:
    """
    Resolve which key file to read.

    Prefer the requested path; if missing, try legacy helpers/ copy
    (pre-sync-wipe location) and ~/.config default.
    """
    path = path.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.is_file():
        return path
    for candidate in (DEFAULT_KEY_FILE, LEGACY_KEY_FILE, Path.cwd() / "lg_webos_client_keys.json"):
        if candidate.is_file() and candidate.resolve() != path.resolve():
            print(f"Note: using key file {candidate} (preferred {path} not found)")
            return candidate
    return path


def load_keys(path: Path) -> Dict[str, Any]:
    """Load persisted pairing data (host → {client_key})."""
    path = resolve_key_file(path)
    if not path.is_file():
        print(f"Key file not found: {path} (will pair as new client)")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read key file {path}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"Warning: key file {path} is not a JSON object", file=sys.stderr)
        return {}

    out: Dict[str, Any] = {}
    for host, value in data.items():
        client_key = _extract_client_key(value)
        if client_key:
            out[str(host).strip()] = {"client_key": client_key}
    print(f"Loaded {len(out)} saved key(s) from {path}: {', '.join(out) or '(none)'}")
    return out


def save_keys(path: Path, keys: Dict[str, Any]) -> None:
    """
    Persist host → store map.

    Always write under ~/.config/wanos/ when using the default path so
    wanos-sync rsync --delete cannot wipe the pairing key.
    """
    path = path.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    # If caller still points at the in-repo legacy file, redirect to durable default
    try:
        if path.resolve() == LEGACY_KEY_FILE.resolve():
            print(
                f"Note: refusing to save inside repo ({path}); "
                f"writing {DEFAULT_KEY_FILE} instead (survives wanos-sync)"
            )
            path = DEFAULT_KEY_FILE
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keys, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Saved client key(s) to {path}")


def _store_for_host(keys: Dict[str, Any], host: str) -> Dict[str, str]:
    """Return a mutable pywebostv store dict for this host (may be empty)."""
    host = host.strip()
    existing = keys.get(host)
    client_key = _extract_client_key(existing) if existing is not None else None
    if client_key:
        return {"client_key": client_key}
    return {}


def _apply_registration_key(store: Dict[str, str]) -> None:
    """Set or clear pywebostv's module-global REGISTRATION_PAYLOAD client-key."""
    from pywebostv.connection import REGISTRATION_PAYLOAD

    if store.get("client_key"):
        REGISTRATION_PAYLOAD["client-key"] = store["client_key"]
    else:
        REGISTRATION_PAYLOAD.pop("client-key", None)


def connect_and_register(
    host: str,
    keys: Dict[str, Any],
    key_file: Path,
    secure: Optional[bool] = None,
) -> Tuple[Any, bool]:
    """Connect + register. Returns (client, used_secure)."""
    from pywebostv.connection import WebOSClient

    host = host.strip()
    store = _store_for_host(keys, host)
    had_key = bool(store.get("client_key"))
    modes: List[bool] = [secure] if secure is not None else [False, True]

    if had_key:
        print(f"Using saved client_key for {host} ({store['client_key'][:8]}…)")
    else:
        print(f"No saved client_key for {host} — TV will show a pairing prompt")

    last_err: Optional[BaseException] = None
    for use_secure in modes:
        attempt_store = dict(store)
        client = WebOSClient(host, secure=use_secure)
        try:
            print(
                f"Connecting to {host} "
                f"(secure={use_secure}, "
                f"{'saved key' if had_key else 'pairing — accept prompt on TV'})..."
            )
            client.connect()
            _apply_registration_key(attempt_store)
            for status in client.register(attempt_store):
                if status == WebOSClient.PROMPTED:
                    if had_key:
                        print(
                            "TV requested re-authorization even with a saved key "
                            "(accept on TV once)..."
                        )
                    else:
                        print("Please accept the connection prompt on the TV...")
                elif status == WebOSClient.REGISTERED:
                    print("Registration OK.")
            if attempt_store.get("client_key"):
                keys[host] = {"client_key": attempt_store["client_key"]}
                save_keys(key_file, keys)
                store = dict(attempt_store)
                had_key = True
            return client, use_secure
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  connect secure={use_secure} failed: {type(exc).__name__}: {exc}")
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

    raise SystemExit(
        f"Could not connect/register to {host}: {type(last_err).__name__}: {last_err}"
    )


def send_wol(mac: str) -> None:
    """Send a Wake-on-LAN magic packet to mac."""
    try:
        from wakeonlan import send_magic_packet
    except ImportError as exc:
        raise SystemExit(
            "wakeonlan is not installed. Run: pip install pywebostv wakeonlan"
        ) from exc
    print(f"Sending WOL magic packet to {mac}...")
    send_magic_packet(mac)


def _probe_info(client: Any) -> Dict[str, Any]:
    """Fetch SystemControl.info() when available."""
    from pywebostv.controls import SystemControl

    system = SystemControl(client)
    try:
        info = system.info()
        return info if isinstance(info, dict) else {"raw": info}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _mac_from_info(info: Dict[str, Any]) -> Optional[str]:
    """Pick a WOL MAC candidate from system.info() (often device_id)."""
    for key in ("device_id", "deviceId", "wifi_mac", "wired_mac", "macAddress"):
        value = info.get(key)
        if not value or not isinstance(value, str):
            continue
        cleaned = value.strip().lower().replace("-", ":")
        parts = cleaned.split(":")
        if len(parts) == 6 and all(len(p) == 2 for p in parts):
            return cleaned
    return None


def ssap_ports_open(host: str) -> bool:
    """True if webOS SSAP TCP port is accepting connections (TV likely ON)."""
    return _tcp_open(host, WS_PORT, timeout=0.8) or _tcp_open(host, WSS_PORT, timeout=0.8)


def _app_field(app: Any, key: str, default: str = "?") -> str:
    """Read a field from a pywebostv Application (dict-like via __getitem__)."""
    try:
        value = app[key]
        if value is not None and str(value).strip():
            return str(value)
    except (KeyError, TypeError, IndexError):
        pass
    data = getattr(app, "data", None)
    if isinstance(data, dict) and data.get(key) is not None:
        return str(data[key])
    return default


def find_app(client: Any, needle: str) -> Any:
    """
    Find an installed app by title or id substring (case-insensitive).

    Returns the Application object for ApplicationControl.launch().
    """
    from pywebostv.controls import ApplicationControl

    app_ctl = ApplicationControl(client)
    apps = app_ctl.list_apps()
    needle_l = needle.lower().strip()
    matches = []
    for app in apps:
        title = _app_field(app, "title", "")
        app_id = _app_field(app, "id", "")
        if needle_l in title.lower() or needle_l in app_id.lower():
            matches.append(app)
    if not matches:
        titles = [_app_field(a, "title") for a in apps]
        sample = ", ".join(titles[:20]) + ("…" if len(titles) > 20 else "")
        raise SystemExit(
            f"No installed app matching {needle!r}. "
            f"Sample titles: {sample or '(none)'}"
        )
    if len(matches) > 1:
        for app in matches:
            if _app_field(app, "title", "").lower() == needle_l:
                return app
    return matches[0]


def launch_app(client: Any, needle: str) -> None:
    """Launch the first app matching needle (e.g. 'netflix')."""
    from pywebostv.controls import ApplicationControl

    app = find_app(client, needle)
    title = _app_field(app, "title", needle)
    app_id = _app_field(app, "id")
    print(f"Launching app title={title!r} id={app_id!r}...")
    ApplicationControl(client).launch(app)
    print("Launch requested.")


def ensure_powered_on(
    host: str,
    mac: Optional[str],
    wait: float,
    keys: Dict[str, Any],
    key_file: Path,
) -> Any:
    """
    Make sure the TV is reachable over SSAP; WOL if needed.

    Returns a connected+registered WebOSClient (caller must close).
    """
    if not ssap_ports_open(host):
        if not mac:
            raise SystemExit(
                f"TV at {host} looks OFF (SSAP ports closed). "
                "Pass --mac AA:BB:… for Wake-on-LAN, or turn the TV on first."
            )
        send_wol(mac)
        print(f"Waiting {wait:.0f}s for TV network stack...")
        time.sleep(wait)
        if not ssap_ports_open(host):
            raise SystemExit(
                "WOL sent but SSAP still closed — check WOL setting, MAC, "
                "Ethernet vs Wi-Fi, Quick Start+."
            )
    return connect_and_register(host, keys, key_file)[0]


def cmd_discover(args: argparse.Namespace) -> None:
    """SSDP + TCP scan; probe each unique host for model / pairing."""
    _require_pywebostv()
    keys = load_keys(args.key_file)

    hosts: List[str] = []
    print("--- SSDP (pywebostv) ---")
    for ip in ssdp_discover_hosts():
        if ip not in hosts:
            hosts.append(ip)

    print("--- TCP sweep ---")
    for ip in scan_subnet_for_webos(args.subnet):
        if ip not in hosts:
            hosts.append(ip)

    if not hosts:
        print(
            "No LG webOS candidates found.\n"
            "Leave the TV ON, enable LG Connect Apps, then retry."
        )
        return

    print(f"\nFound {len(hosts)} candidate(s): {', '.join(hosts)}")
    for host in hosts:
        print(f"\n=== {host} ===")
        client = None
        try:
            client, used_secure = connect_and_register(host, keys, args.key_file)
            info = _probe_info(client)
            mac = _mac_from_info(info)
            print(f"  status       : ON")
            print(f"  Secure WS    : {used_secure}")
            print(f"  Info         : {info}")
            print(f"  Client key   : {keys.get(host, {}).get('client_key', '?')}")
            if mac:
                print(f"  MAC (WOL)    : {mac}  (from info device_id)")
            else:
                print("  MAC (WOL)    : unknown — TV Network settings / router DHCP")
            if args.list_apps:
                from pywebostv.controls import ApplicationControl

                apps = ApplicationControl(client).list_apps()
                print(f"  Apps ({len(apps)}):")
                for app in apps:
                    title = _app_field(app, "title")
                    app_id = _app_field(app, "id")
                    print(f"    - {title}  ({app_id})")
        except SystemExit as exc:
            print(f"  status       : OFF (or unreachable)")
            print(f"  Probe detail : {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  status       : OFF (or unreachable)")
            print(f"  Probe detail : {type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass


def cmd_status(args: argparse.Namespace) -> None:
    """Report power as ON or OFF."""
    host = args.host
    ports_up = ssap_ports_open(host)
    if not ports_up:
        print(f"host={host}")
        print("status=OFF")
        print("detail=SSAP ports 3000/3001 closed (TV off, sleeping, or wrong IP)")
        return

    if args.ports_only:
        print(f"host={host}")
        print("status=ON")
        print("detail=SSAP port open (--ports-only; no WebSocket register)")
        return

    _require_pywebostv()
    keys = load_keys(args.key_file)
    client = None
    try:
        client, used_secure = connect_and_register(host, keys, args.key_file)
        info = _probe_info(client)
        mac = _mac_from_info(info)
        print(f"host={host}")
        print("status=ON")
        print(f"secure={used_secure}")
        if mac:
            print(f"mac={mac}")
        print(f"info={info}")
    except SystemExit as exc:
        print(f"host={host}")
        print("status=ON")
        print(f"detail=SSAP port open but register failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"host={host}")
        print("status=ON")
        print(f"detail=SSAP port open but error: {type(exc).__name__}: {exc}")
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass


def cmd_set(args: argparse.Namespace) -> None:
    """
    Combinable switches: --on, --netflix (together OK); --off alone.

    --on without SSAP up requires --mac (WOL).
    """
    want_on = bool(args.on)
    want_off = bool(args.off)
    want_netflix = bool(args.netflix)

    if want_off and (want_on or want_netflix):
        raise SystemExit("--off cannot be combined with --on or --netflix")
    if not (want_on or want_off or want_netflix):
        raise SystemExit("Specify at least one of --on, --off, --netflix")

    _require_pywebostv()
    host = args.host.strip()
    keys = load_keys(args.key_file)
    client = None

    try:
        if want_off:
            client = connect_and_register(host, keys, args.key_file)[0]
            from pywebostv.controls import SystemControl

            print("Calling SSAP power_off...")
            SystemControl(client).power_off()
            print("power_off requested.")
            return

        # --on and/or --netflix
        if want_on or not ssap_ports_open(host):
            # Power path: WOL if needed, then connect
            client = ensure_powered_on(host, args.mac, args.wait, keys, args.key_file)
            if want_on:
                print("status=ON (SSAP up)")
        else:
            # Netflix-only while already on
            client = connect_and_register(host, keys, args.key_file)[0]
            print("status=ON (already reachable)")

        if want_netflix:
            # Brief settle after cold WOL so launcher is ready
            if want_on and args.mac:
                time.sleep(min(3.0, max(0.0, args.wait / 3.0)))
            launch_app(client, args.app)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass


def build_parser() -> argparse.ArgumentParser:
    """CLI for discover / status / set."""
    parser = argparse.ArgumentParser(
        description=(
            "Discover LG webOS TVs; status; set --on/--off/--netflix "
            "(pywebostv + WOL). Keys default to ~/.config/wanos/."
        )
    )
    parser.add_argument(
        "--key-file",
        type=Path,
        default=DEFAULT_KEY_FILE,
        help=f"JSON map host->store (default: {DEFAULT_KEY_FILE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_disc = sub.add_parser(
        "discover", help="SSDP + TCP scan; probe each host (TV must be ON)"
    )
    p_disc.add_argument(
        "--subnet",
        default=None,
        help="Optional a.b.c prefix for TCP sweep (default: auto from local IP)",
    )
    p_disc.add_argument(
        "--list-apps",
        action="store_true",
        help="After pairing, list installed apps (titles + ids)",
    )
    p_disc.set_defaults(func=cmd_discover)

    p_st = sub.add_parser("status", help="Print status=ON or status=OFF")
    p_st.add_argument("--host", required=True, help="TV IPv4 address")
    p_st.add_argument(
        "--ports-only",
        action="store_true",
        help="Only check TCP 3000/3001 (no pairing / WebSocket)",
    )
    p_st.set_defaults(func=cmd_status)

    p_set = sub.add_parser(
        "set",
        help="Switches: --on and/or --netflix (combinable); or --off alone",
    )
    p_set.add_argument("--host", required=True, help="TV IPv4 address")
    p_set.add_argument(
        "--on",
        action="store_true",
        help="Power on (WOL if SSAP down — needs --mac)",
    )
    p_set.add_argument(
        "--off",
        action="store_true",
        help="Power off via SSAP (not combinable with --on/--netflix)",
    )
    p_set.add_argument(
        "--netflix",
        action="store_true",
        help="Launch Netflix (or --app name); combinable with --on",
    )
    p_set.add_argument(
        "--app",
        default="netflix",
        help="App title/id substring for --netflix (default: netflix)",
    )
    p_set.add_argument(
        "--mac",
        default=None,
        help="MAC for Wake-on-LAN when powering on from cold",
    )
    p_set.add_argument(
        "--wait",
        type=float,
        default=8.0,
        help="Seconds to wait after WOL before SSAP (default: 8)",
    )
    p_set.set_defaults(func=cmd_set)

    return parser


def main() -> None:
    """Entry point."""
    if sys.version_info < (3, 9):
        raise SystemExit(f"Python >= 3.9 required (got {sys.version})")
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
