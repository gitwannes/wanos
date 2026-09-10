#!/usr/bin/env python3
# --- file: helpers/homewizard_discovery.py ---
"""
HomeWizard Energy Local API v2 scout (G10 step 0).

Pairs a bearer token (button press on the device), dumps device + measurement
fields so you can pick which metrics become WanOS 810xx idxs (Z-Wave-style
curated device_map - not auto-import-all).

Requires:
  aiohttp (already in WanOS venv / requirements.txt)
  pip install zeroconf   (optional; mDNS scan - without it, scan uses --sweep)

Note: PyPI packages that export HomeWizardEnergyV2 need Python >=3.12.
This scout talks to Local API v2 over HTTPS with aiohttp so it works on Pi
Python 3.9. Do not require python-homewizard-energy for this helper.

Tokens are stored OUTSIDE the repo tree (default:
~/.config/wanos/homewizard_tokens.json). Do not commit tokens.

Examples (ASCII console):
  python helpers/homewizard_discovery.py scan
  python helpers/homewizard_discovery.py scan --seconds 8
  python helpers/homewizard_discovery.py scan --sweep
  python helpers/homewizard_discovery.py pair --host 10.32.251.50
  python helpers/homewizard_discovery.py dump --host 10.32.251.50
  python helpers/homewizard_discovery.py measure --host 10.32.251.50
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TOKEN_FILE = Path.home() / ".config" / "wanos" / "homewizard_tokens.json"
DEFAULT_USER_NAME = "wanos"
PAIR_RETRY_SECS = 2.0
PAIR_TIMEOUT_SECS = 120.0
SCAN_MDNS_SECS = 5.0
SCAN_SWEEP_CONCURRENCY = 64
MDNS_V2 = "_homewizard._tcp.local."
MDNS_V1 = "_hwenergy._tcp.local."


def _require_aiohttp() -> None:
    """Fail fast if aiohttp is missing."""
    try:
        import aiohttp  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "aiohttp is not installed. Activate wanos_venv or: pip install aiohttp"
        ) from exc


def _v2_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Headers for HomeWizard Local API v2."""
    headers = {"X-Api-Version": "2", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _jsonable(value: Any) -> Any:
    """Convert objects into plain JSON-serializable data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _suggest_type(field: str, unit: Optional[str] = None) -> str:
    """Heuristic WanOS product type for a measurement field."""
    key = field.lower()
    u = (unit or "").lower()
    if "power_w" in key or key.endswith("_w") or u in ("w", "watt", "watts"):
        return "power"
    if "kwh" in key or u in ("kwh", "wh"):
        return "energy"
    if "liter" in key or "m3" in key or "gas" in key or u in ("m3", "m^3", "l", "lpm"):
        return "fluid"
    if "volt" in key or key.endswith("_v"):
        return "sensor"
    if "current" in key or key.endswith("_a"):
        return "sensor"
    return "sensor"


def _load_tokens(path: Path) -> Dict[str, str]:
    """Read host -> token map from disk."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read token file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Token file must be a JSON object: {path}")
    out: Dict[str, str] = {}
    for host, token in data.items():
        if isinstance(host, str) and isinstance(token, str) and token.strip():
            out[host.strip()] = token.strip()
    return out


def _save_tokens(path: Path, tokens: Dict[str, str]) -> None:
    """Write host -> token map."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(tokens, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _resolve_token(
    host: str,
    token_arg: Optional[str],
    token_file: Path,
) -> str:
    """Prefer CLI token, else token file entry for this host."""
    if token_arg and token_arg.strip():
        return token_arg.strip()
    stored = _load_tokens(token_file).get(host)
    if stored:
        return stored
    raise SystemExit(
        f"No token for {host}. Run: python helpers/homewizard_discovery.py "
        f"pair --host {host}"
    )


async def _pair_host(
    host: str,
    user_name: str,
    token_file: Path,
    timeout_secs: float,
) -> str:
    """Request a v2 bearer token via POST /api/user."""
    from aiohttp import ClientSession, ClientTimeout

    local_name = user_name if user_name.startswith("local/") else f"local/{user_name}"
    url = f"https://{host}/api/user"
    print(f"[{host}] Pairing as {local_name} ...")
    print(
        f"[{host}] Press the button on the device within {int(timeout_secs)}s "
        "(kWh meter: hold WiFi-pair 1-3s)."
    )
    deadline = time.monotonic() + timeout_secs
    last_err = "no response"
    timeout = ClientTimeout(total=5)
    async with ClientSession() as session:
        while time.monotonic() < deadline:
            try:
                async with session.post(
                    url,
                    json={"name": local_name},
                    headers=_v2_headers(),
                    ssl=False,
                    timeout=timeout,
                ) as res:
                    body_text = await res.text()
                    if res.status == 403:
                        last_err = "button not pressed yet (403)"
                        await asyncio.sleep(PAIR_RETRY_SECS)
                        continue
                    if res.status != 200:
                        last_err = f"HTTP {res.status}: {body_text[:200]}"
                        print(f"[{host}] Pair error: {last_err}")
                        await asyncio.sleep(PAIR_RETRY_SECS)
                        continue
                    try:
                        payload = json.loads(body_text)
                    except json.JSONDecodeError:
                        last_err = f"non-JSON body: {body_text[:200]}"
                        await asyncio.sleep(PAIR_RETRY_SECS)
                        continue
                    token = str(payload.get("token") or "").strip()
                    if not token:
                        last_err = f"no token in response: {payload}"
                        await asyncio.sleep(PAIR_RETRY_SECS)
                        continue
                    tokens = _load_tokens(token_file)
                    tokens[host] = token
                    _save_tokens(token_file, tokens)
                    print(f"[{host}] Token saved to {token_file}")
                    print(f"[{host}] token={token}")
                    return token
            except Exception as exc:
                last_err = str(exc)
                print(f"[{host}] Pair error: {last_err}")
                await asyncio.sleep(PAIR_RETRY_SECS)
    raise SystemExit(
        f"[{host}] Pair timed out after {int(timeout_secs)}s "
        f"(last error: {last_err})"
    )


def _normalize_external(measurement: Dict[str, Any]) -> Dict[str, Any]:
    """Copy measurement; map API list `external` into flatten-friendly shape."""
    data = dict(measurement)
    external = data.get("external")
    if isinstance(external, list):
        # Keep list for display; flatten reads both list and dict forms.
        data["external_devices"] = {
            str(i): item for i, item in enumerate(external) if isinstance(item, dict)
        }
    return data


def _flatten_measurement(meas: Any) -> List[Tuple[str, Any, str]]:
    """Flatten measurement into (field_path, value, suggested_type) rows."""
    data = _jsonable(meas)
    if not isinstance(data, dict):
        return [("measurement", data, "sensor")]

    rows: List[Tuple[str, Any, str]] = []
    external = data.pop("external_devices", None)
    data.pop("external", None)

    for key in sorted(data.keys()):
        val = data[key]
        if val is None:
            continue
        rows.append((key, val, _suggest_type(key)))

    if isinstance(external, dict):
        for ext_id, ext in sorted(external.items(), key=lambda x: str(x[0])):
            if not isinstance(ext, dict):
                rows.append((f"external.{ext_id}", ext, "sensor"))
                continue
            unit = ext.get("unit")
            etype = ext.get("type")
            value = ext.get("value")
            # Prefer type-based field id for bridge maps: external.gas_meter
            type_key = f"external.{etype}" if etype else f"external.{ext_id}.value"
            rows.append(
                (
                    type_key,
                    value,
                    _suggest_type(str(etype or type_key), str(unit) if unit else None),
                )
            )
    return rows


def _print_pick_table(host: str, rows: List[Tuple[str, Any, str]]) -> None:
    """Print operator pick list."""
    print("")
    print(f"=== PICK LIST [{host}] - mark which fields to import into 810xx ===")
    print(f"{'field':<42} {'type':<8} value")
    print("-" * 72)
    for field, value, stype in rows:
        print(f"{field:<42} {stype:<8} {value}")
    print("-" * 72)
    print(
        f"[{host}] {len(rows)} non-null field(s). Reply which to keep "
        "(or paste a shortlist). Unlisted fields stay unused."
    )


async def _v2_get_json(
    session: Any,
    host: str,
    path: str,
    token: str,
) -> Any:
    """GET https://host<path> with v2 bearer token."""
    from aiohttp import ClientTimeout

    url = f"https://{host}{path}"
    async with session.get(
        url,
        headers=_v2_headers(token),
        ssl=False,
        timeout=ClientTimeout(total=10),
    ) as res:
        body = await res.text()
        if res.status != 200:
            raise SystemExit(f"[{host}] GET {path} HTTP {res.status}: {body[:300]}")
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[{host}] GET {path} non-JSON: {body[:300]}") from exc


async def _dump_host(
    host: str,
    token: str,
    *,
    measure_only: bool = False,
) -> None:
    """Fetch device + measurement via Local API v2; print pick table."""
    from aiohttp import ClientSession

    async with ClientSession() as session:
        if not measure_only:
            device = await _v2_get_json(session, host, "/api", token)
            print(f"=== DEVICE [{host}] ===")
            print(json.dumps(_jsonable(device), indent=2, sort_keys=True))
            print("")

        measurement = await _v2_get_json(session, host, "/api/measurement", token)
        print(f"=== MEASUREMENT [{host}] ===")
        print(json.dumps(_jsonable(measurement), indent=2, sort_keys=True))
        if isinstance(measurement, dict):
            measurement = _normalize_external(measurement)
        rows = _flatten_measurement(measurement)
        _print_pick_table(host, rows)


async def _cmd_pair(args: argparse.Namespace) -> None:
    """Pair tokens for one or more hosts."""
    _require_aiohttp()
    token_file = Path(args.token_file)
    for host in args.host:
        await _pair_host(
            host=host,
            user_name=args.user_name,
            token_file=token_file,
            timeout_secs=float(args.timeout),
        )


async def _cmd_dump(args: argparse.Namespace) -> None:
    """Dump device + measurement (+ pick table)."""
    _require_aiohttp()
    token_file = Path(args.token_file)
    for host in args.host:
        token = _resolve_token(host, args.token, token_file)
        await _dump_host(host, token, measure_only=False)


async def _cmd_measure(args: argparse.Namespace) -> None:
    """Dump measurement only (+ pick table)."""
    _require_aiohttp()
    token_file = Path(args.token_file)
    for host in args.host:
        token = _resolve_token(host, args.token, token_file)
        await _dump_host(host, token, measure_only=True)


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


def _txt_to_dict(info: Any) -> Dict[str, str]:
    """Decode zeroconf TXT properties to str->str."""
    props = getattr(info, "properties", None) or {}
    out: Dict[str, str] = {}
    for raw_k, raw_v in props.items():
        key = raw_k.decode("utf-8", errors="replace") if isinstance(raw_k, bytes) else str(raw_k)
        if raw_v is None:
            out[key] = ""
        elif isinstance(raw_v, bytes):
            out[key] = raw_v.decode("utf-8", errors="replace")
        else:
            out[key] = str(raw_v)
    return out


def _info_ipv4(info: Any) -> Optional[str]:
    """First IPv4 address from a ServiceInfo."""
    addrs: List[str] = []
    parsed = getattr(info, "parsed_addresses", None)
    if callable(parsed):
        try:
            addrs = list(parsed())
        except TypeError:
            addrs = list(parsed(version=4))
    if not addrs:
        for attr in ("addresses", "address"):
            raw = getattr(info, attr, None)
            if raw is None:
                continue
            if isinstance(raw, (bytes, bytearray)) and len(raw) == 4:
                addrs = [socket.inet_ntoa(bytes(raw))]
                break
            if isinstance(raw, (list, tuple)):
                for item in raw:
                    if isinstance(item, (bytes, bytearray)) and len(item) == 4:
                        addrs.append(socket.inet_ntoa(bytes(item)))
    for addr in addrs:
        if isinstance(addr, str) and addr.count(".") == 3:
            return addr
    return None


async def _scan_mdns(seconds: float) -> List[Dict[str, str]]:
    """Browse official HomeWizard mDNS services."""
    try:
        from zeroconf import ServiceStateChange
        from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
    except ImportError as exc:
        raise SystemExit(
            "zeroconf is not installed (needed for mDNS scan). "
            "Run: pip install zeroconf   - or use: scan --sweep"
        ) from exc

    pending: List[Tuple[str, str]] = []

    def on_service_state_change(
        zeroconf: Any,
        service_type: str,
        name: str,
        state_change: Any,
    ) -> None:
        if state_change is ServiceStateChange.Added:
            pending.append((service_type, name))

    print(f"Scanning mDNS ({MDNS_V2} + {MDNS_V1}) for {seconds:.0f}s ...")
    aiozc = AsyncZeroconf()
    browser = AsyncServiceBrowser(
        aiozc.zeroconf,
        [MDNS_V2, MDNS_V1],
        handlers=[on_service_state_change],
    )
    try:
        await asyncio.sleep(max(0.5, float(seconds)))
    finally:
        await browser.async_cancel()

    found: Dict[str, Dict[str, str]] = {}
    try:
        for service_type, name in pending:
            info = await aiozc.async_get_service_info(service_type, name)
            if info is None:
                continue
            ip = _info_ipv4(info)
            if not ip:
                continue
            txt = _txt_to_dict(info)
            api = "v2" if "homewizard" in service_type else "v1"
            row = {
                "ip": ip,
                "api": api,
                "instance": name.split(".")[0] if name else "",
                "product_name": txt.get("product_name", ""),
                "product_type": txt.get("product_type", ""),
                "serial": txt.get("serial", ""),
                "api_version": txt.get("api_version", ""),
                "api_enabled": txt.get("api_enabled", ""),
                "id": txt.get("id", ""),
            }
            prev = found.get(ip)
            if prev is None or (prev.get("api") == "v1" and api == "v2"):
                found[ip] = row
            elif prev.get("api") == api:
                found[ip] = row
    finally:
        await aiozc.async_close()

    return [
        found[k]
        for k in sorted(found.keys(), key=lambda x: tuple(int(p) for p in x.split(".")))
    ]


async def _probe_v2_api(session: Any, host: str) -> bool:
    """True if host speaks HomeWizard API v2 (HTTPS /api -> 401)."""
    from aiohttp import ClientTimeout

    try:
        async with session.get(
            f"https://{host}/api",
            ssl=False,
            raise_for_status=False,
            timeout=ClientTimeout(total=3),
        ) as res:
            return res.status == 401
    except Exception:
        return False


async def _probe_v1_api(session: Any, host: str) -> Optional[Dict[str, str]]:
    """If host speaks API v1 HTTP /api, return product fields."""
    from aiohttp import ClientTimeout

    try:
        async with session.get(
            f"http://{host}/api",
            raise_for_status=False,
            timeout=ClientTimeout(total=3),
        ) as res:
            if res.status != 200:
                return None
            data = await res.json(content_type=None)
            if not isinstance(data, dict):
                return None
            if not (
                data.get("product_type")
                or data.get("product_name")
                or data.get("serial")
            ):
                return None
            return {
                "product_name": str(data.get("product_name") or ""),
                "product_type": str(data.get("product_type") or ""),
                "serial": str(data.get("serial") or ""),
                "api_version": str(data.get("api_version") or "v1"),
            }
    except Exception:
        return None


async def _scan_sweep(prefix: Optional[str] = None) -> List[Dict[str, str]]:
    """Sweep /24 for HomeWizard API v1/v2."""
    from aiohttp import ClientSession

    subnet = prefix or _local_subnet_prefix()
    print(f"Sweeping {subnet}.0/24 for HomeWizard API v1/v2 ...")
    hosts = [f"{subnet}.{i}" for i in range(1, 255)]
    sem = asyncio.Semaphore(SCAN_SWEEP_CONCURRENCY)
    found: Dict[str, Dict[str, str]] = {}

    async with ClientSession() as session:

        async def probe(host: str) -> None:
            async with sem:
                row: Optional[Dict[str, str]] = None
                if await _probe_v2_api(session, host):
                    row = {
                        "ip": host,
                        "api": "v2",
                        "instance": "",
                        "product_name": "",
                        "product_type": "",
                        "serial": "",
                        "api_version": "",
                        "api_enabled": "",
                        "id": "",
                    }
                else:
                    v1 = await _probe_v1_api(session, host)
                    if v1 is not None:
                        row = {
                            "ip": host,
                            "api": "v1",
                            "instance": "",
                            "product_name": v1.get("product_name", ""),
                            "product_type": v1.get("product_type", ""),
                            "serial": v1.get("serial", ""),
                            "api_version": v1.get("api_version", ""),
                            "api_enabled": "",
                            "id": "",
                        }
                if row is not None:
                    found[host] = row

        await asyncio.gather(*(probe(h) for h in hosts))

    return [
        found[k]
        for k in sorted(found.keys(), key=lambda x: tuple(int(p) for p in x.split(".")))
    ]


async def _enrich_with_tokens(
    rows: List[Dict[str, str]],
    token_file: Path,
) -> None:
    """If a stored token exists, fill product fields from GET /api."""
    from aiohttp import ClientSession, ClientTimeout

    tokens = _load_tokens(token_file)
    if not tokens:
        return
    timeout = ClientTimeout(total=5)
    async with ClientSession() as session:
        for row in rows:
            host = row.get("ip") or ""
            token = tokens.get(host)
            if not token:
                continue
            try:
                async with session.get(
                    f"https://{host}/api",
                    headers=_v2_headers(token),
                    ssl=False,
                    timeout=timeout,
                ) as res:
                    if res.status != 200:
                        continue
                    data = await res.json(content_type=None)
            except Exception as exc:
                print(f"[{host}] token present but device lookup failed: {exc}")
                continue
            if not isinstance(data, dict):
                continue
            for key in ("product_name", "product_type", "serial", "api_version", "id"):
                if data.get(key):
                    row[key] = str(data[key])


def _print_scan_table(rows: List[Dict[str, str]]) -> None:
    """Print discovered devices."""
    print("")
    if not rows:
        print("No HomeWizard devices found.")
        print("Tips: same LAN/VLAN; multicast for mDNS; or retry with: scan --sweep")
        return
    print(f"Found {len(rows)} HomeWizard device(s):")
    print(
        f"{'ip':<16} {'api':<4} {'product_name':<22} {'product_type':<12} "
        f"{'serial':<14} instance"
    )
    print("-" * 96)
    for row in rows:
        print(
            f"{row.get('ip', ''):<16} "
            f"{row.get('api', ''):<4} "
            f"{(row.get('product_name') or '-'):<22} "
            f"{(row.get('product_type') or '-'):<12} "
            f"{(row.get('serial') or '-'):<14} "
            f"{row.get('instance') or '-'}"
        )
    print("-" * 96)
    print("Next: pair --host <ip>   then   dump --host <ip>")


async def _cmd_scan(args: argparse.Namespace) -> None:
    """Discover HomeWizard devices via mDNS or --sweep."""
    _require_aiohttp()
    token_file = Path(args.token_file)
    if args.sweep:
        rows = await _scan_sweep(args.subnet)
    else:
        try:
            import zeroconf  # noqa: F401
        except ImportError:
            print(
                "zeroconf not installed - falling back to --sweep "
                "(pip install zeroconf for mDNS)."
            )
            rows = await _scan_sweep(args.subnet)
        else:
            rows = await _scan_mdns(float(args.seconds))
    await _enrich_with_tokens(rows, token_file)
    _print_scan_table(rows)


def _build_parser() -> argparse.ArgumentParser:
    """CLI for scan / pair / dump / measure."""
    parser = argparse.ArgumentParser(
        description=(
            "HomeWizard Energy v2 discovery scout (G10). "
            "Scan LAN, pair tokens, dump measurements, pick fields for 810xx."
        )
    )
    parser.add_argument(
        "--token-file",
        default=str(DEFAULT_TOKEN_FILE),
        help=f"JSON host->token map (default: {DEFAULT_TOKEN_FILE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser(
        "scan",
        help="List HomeWizard devices (mDNS default; --sweep = HTTPS/HTTP /24)",
    )
    p_scan.add_argument(
        "--seconds",
        type=float,
        default=SCAN_MDNS_SECS,
        help=f"mDNS browse duration (default: {int(SCAN_MDNS_SECS)})",
    )
    p_scan.add_argument(
        "--sweep",
        action="store_true",
        help="Sweep local /24 via HTTPS/HTTP probes instead of mDNS",
    )
    p_scan.add_argument(
        "--subnet",
        default=None,
        help="With --sweep: a.b.c prefix (default: auto-detect)",
    )
    p_scan.set_defaults(func=_cmd_scan)

    p_pair = sub.add_parser("pair", help="Button-pair and store bearer token")
    p_pair.add_argument("--host", action="append", required=True, help="Device IP")
    p_pair.add_argument(
        "--user-name",
        default=DEFAULT_USER_NAME,
        help=f"local/<name> user (default: {DEFAULT_USER_NAME})",
    )
    p_pair.add_argument(
        "--timeout",
        type=float,
        default=PAIR_TIMEOUT_SECS,
        help=f"Seconds to wait for button (default: {int(PAIR_TIMEOUT_SECS)})",
    )
    p_pair.set_defaults(func=_cmd_pair)

    p_dump = sub.add_parser("dump", help="Print device + measurement JSON and pick list")
    p_dump.add_argument("--host", action="append", required=True, help="Device IP")
    p_dump.add_argument("--token", default=None, help="Bearer token override")
    p_dump.set_defaults(func=_cmd_dump)

    p_meas = sub.add_parser("measure", help="Print measurement JSON and pick list only")
    p_meas.add_argument("--host", action="append", required=True, help="Device IP")
    p_meas.add_argument("--token", default=None, help="Bearer token override")
    p_meas.set_defaults(func=_cmd_measure)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
