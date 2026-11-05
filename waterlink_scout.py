#!/usr/bin/env python3
# --- file: waterlink_scout.py ---
"""
WanOS Water-Link Standalone Scout
=================================
Polls Mijn Water-Link digital-meter portal for one cumulative reading.

Auth/client: integrations/waterlink_client.py (shared with G24 bridge).
Config: config.yaml waterlink:  |  Secrets: .env WATERLINK_USER / WATERLINK_PASSWORD

Usage:
    python waterlink_scout.py
    python waterlink_scout.py --debug
    python waterlink_scout.py --meter-id 260202059
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

import aiohttp
import yaml
from dotenv import load_dotenv

from integrations.waterlink_client import WaterLinkPortalClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("waterlink_scout")


def load_wanos_config(config_path: Path, env_path: Path) -> Dict[str, Any]:
    """Load waterlink: from config.yaml and WATERLINK_* secrets from .env."""
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)
        logger.debug("Loaded environment variables from %s", env_path)
    else:
        logger.warning(".env file not found at %s. Relying on system env vars.", env_path)

    if not config_path.is_file():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    wl_config = config_data.get("waterlink", {}) or {}
    user = os.getenv("WATERLINK_USER") or os.getenv("WATERLINK_USERNAME")
    password = os.getenv("WATERLINK_PASSWORD")

    return {
        "user": user,
        "password": password,
        "meter_id": str(wl_config.get("meter_id", "")).strip(),
        "idx": wl_config.get("idx", 82001),
        "poll_interval_hours": wl_config.get("poll_interval_hours", 6),
        "name": str(wl_config.get("name") or "Water-Link m3").strip(),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="WanOS Water-Link Scout")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--env", default=".env", help="Path to .env")
    parser.add_argument("--meter-id", help="Override waterlink.meter_id")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("waterlink.client").setLevel(logging.DEBUG)

    base_dir = Path(__file__).resolve().parent
    config_file = base_dir / args.config
    env_file = base_dir / args.env

    try:
        cfg = load_wanos_config(config_file, env_file)
    except Exception as exc:
        logger.error("Failed to load WanOS configuration: %s", exc)
        sys.exit(1)

    meter_id = args.meter_id or cfg["meter_id"]
    user = cfg["user"]
    password = cfg["password"]
    idx = cfg["idx"]

    if not user or not password:
        logger.error(
            "Missing credentials. Set WATERLINK_USER and WATERLINK_PASSWORD in %s",
            env_file.name,
        )
        sys.exit(1)

    if not meter_id:
        logger.error(
            "Missing meter_id. Set waterlink.meter_id in %s or pass --meter-id",
            config_file.name,
        )
        sys.exit(1)

    print("=" * 65)
    print(" WanOS Water-Link Standalone Scout")
    print("=" * 65)
    print(f" Target Meter ID / Serial : {meter_id}")
    print(f" WanOS Ingest IDX         : {idx} (fluid) - scout does not ingest")
    print(f" Portal Account User      : {user}")
    print(f" Poll Interval (config)   : {cfg['poll_interval_hours']} hours")
    print("-" * 65)

    timeout = aiohttp.ClientTimeout(total=60.0)
    cookie_jar = aiohttp.CookieJar(unsafe=True)

    async with aiohttp.ClientSession(cookie_jar=cookie_jar, timeout=timeout) as session:
        client = WaterLinkPortalClient(
            username=user,
            password=password,
            meter_id=meter_id,
            session=session,
        )
        try:
            await client.login_authorization_code_pkce()
            telemetry = await client.get_meter_reading()
        except Exception as exc:
            logger.error("Scout failed: %s", exc)
            if args.debug:
                logger.exception("Traceback:")
            sys.exit(1)

    print("\n[SUCCESS] Telemetry Retrieved:")
    print("-" * 65)
    print(f" Cumulative Consumption : {telemetry['total_m3']} m3")
    print(f" Raw meterReading       : {telemetry['meter_reading_raw']}")
    print(f" Reading Timestamp      : {telemetry['reading_date']}")
    print(f" Meter Active Status    : {telemetry['is_active']}")
    print(f" Leak / Divergent Alert : {telemetry['has_leak_alert']}")
    print(f" Days Offset            : {telemetry['days_offset']}")
    print("-" * 65)
    print("\nRaw /api/meters payload:")
    print(json.dumps(telemetry["raw_payload"], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
