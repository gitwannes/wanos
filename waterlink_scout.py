#!/usr/bin/env python3
"""
WanOS Water-Link Standalone Bridge & Scout Tool
=================================================
Communicates with 'Mijn Water-Link' portal (portaaldigitalemeters.water-link.be).
Reads credentials and meter configuration from `.env` and `config.yaml`.

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
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
import yaml
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Constants & Defaults
# -----------------------------------------------------------------------------
PORTAL_BASE_URL = "https://portaaldigitalemeters.water-link.be"
DEFAULT_CLIENT_ID = "waterlink-prod"  # Fallback client ID used by the portal
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WanOS/1.0"
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("waterlink_scout")


# -----------------------------------------------------------------------------
# Configuration Loader (Identical to WanOS core/config.py)
# -----------------------------------------------------------------------------
def load_wanos_config(config_path: Path, env_path: Path) -> Dict[str, Any]:
    """
    Loads WanOS config.yaml and .env file and extracts waterlink parameters.
    """
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)
        logger.debug("Loaded environment variables from %s", env_path)
    else:
        logger.warning(".env file not found at %s. Relying on system env vars.", env_path)

    if not config_path.is_file():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    wl_config = config_data.get("waterlink", {})

    # Extract credentials from .env
    user = os.getenv("WATERLINK_USER") or os.getenv("WATERLINK_USERNAME")
    password = os.getenv("WATERLINK_PASSWORD")

    # Extract meter parameters from config.yaml
    meter_id = str(wl_config.get("meter_id", "")).strip()
    idx = wl_config.get("idx", 82001)
    poll_interval_hours = wl_config.get("poll_interval_hours", 6)

    return {
        "user": user,
        "password": password,
        "meter_id": meter_id,
        "idx": idx,
        "poll_interval_hours": poll_interval_hours,
    }


# -----------------------------------------------------------------------------
# Water-Link Portal Client
# -----------------------------------------------------------------------------
class WaterLinkPortalClient:
    """
    Handles authentication and REST polling against Mijn Water-Link.
    """

    def __init__(
        self,
        username: str,
        password: str,
        meter_id: str,
        session: aiohttp.ClientSession,
    ):
        self.username = username
        self.password = password
        self.meter_id = meter_id
        self.session = session
        self.access_token: Optional[str] = None

    async def login(self) -> bool:
        """
        Executes the authentication handshake.
        Water-Link routes logins through an OpenID/OAuth2 SAP backend.
        Preserves session cookies and collects JWT / bearer tokens.
        """
        logger.info("Initiating authentication with Mijn Water-Link...")

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-BE,nl;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Step 1: Hit portal landing to initialize session cookies and CSRF/anti-forgery tokens
        landing_url = f"{PORTAL_BASE_URL}/"
        async with self.session.get(landing_url, headers=headers) as resp:
            logger.debug("Portal landing response: %d", resp.status)
            landing_html = await resp.text()

        # Step 2: Query authentication endpoint
        # The portal posts to /api/auth or SAP Gigya/IdP endpoints
        login_endpoints = [
            f"{PORTAL_BASE_URL}/api/auth/login",
            f"{PORTAL_BASE_URL}/auth/login",
            f"{PORTAL_BASE_URL}/api/login",
        ]

        auth_payload = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
            "client_id": DEFAULT_CLIENT_ID,
        }

        login_success = False
        for endpoint in login_endpoints:
            try:
                json_headers = {
                    **headers,
                    "Content-Type": "application/json",
                    "Referer": PORTAL_BASE_URL,
                }
                async with self.session.post(endpoint, json=auth_payload, headers=json_headers) as resp:
                    if resp.status in (200, 204):
                        data = await resp.json() if resp.status == 200 else {}
                        self.access_token = data.get("access_token") or data.get("token")
                        logger.info("Authentication succeeded via %s", endpoint)
                        login_success = True
                        break
            except Exception as e:
                logger.debug("Endpoint %s failed: %s", endpoint, e)

        # Fallback: Check if session cookies alone authenticated us
        if not login_success:
            test_url = f"{PORTAL_BASE_URL}/water-meter/{self.meter_id}"
            async with self.session.get(test_url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info("Cookie-based session established successfully.")
                    login_success = True

        return login_success

    async def get_meter_reading(self) -> Dict[str, Any]:
        """
        Fetches the current meter reading and attributes for the configured meter_id.
        """
        logger.info("Fetching meter telemetry for meter_id: %s...", self.meter_id)

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{PORTAL_BASE_URL}/water-meter/{self.meter_id}",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # Potential API paths used by the portal dashboard
        candidate_urls = [
            f"{PORTAL_BASE_URL}/api/water-meter/{self.meter_id}",
            f"{PORTAL_BASE_URL}/api/meters/{self.meter_id}/details",
            f"{PORTAL_BASE_URL}/api/water-meter/{self.meter_id}/measurements/latest",
            f"{PORTAL_BASE_URL}/water-meter/{self.meter_id}",
        ]

        last_error = None
        for url in candidate_urls:
            try:
                async with self.session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            data = await resp.json()
                            logger.info("Received JSON telemetry from %s", url)
                            return self._parse_telemetry(data)
                        else:
                            # HTML page returned - parse embedded Next.js/React state or JSON payloads
                            html_text = await resp.text()
                            parsed = self._extract_state_from_html(html_text)
                            if parsed:
                                logger.info("Extracted meter data from embedded page state.")
                                return parsed
                    else:
                        logger.debug("Query to %s returned HTTP %d", url, resp.status)
            except Exception as e:
                last_error = e

        raise RuntimeError(f"Could not retrieve meter telemetry: {last_error}")

    def _extract_state_from_html(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extracts hydration JSON (e.g., __NEXT_DATA__ or window.__INITIAL_STATE__)
        from the rendered HTML.
        """
        # Look for Next.js hydration payload
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">({.*?})</script>', html)
        if match:
            try:
                payload = json.loads(match.group(1))
                page_props = payload.get("props", {}).get("pageProps", {})
                return self._parse_telemetry(page_props)
            except Exception as e:
                logger.debug("Failed parsing __NEXT_DATA__: %e", e)

        # Look for inline regex patterns if JSON blob is absent
        total_m3_match = re.search(r'([0-9]+[\.,][0-9]+)\s*m³', html)
        date_match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', html)
        if total_m3_match:
            val = float(total_m3_match.group(1).replace(",", "."))
            return {
                "meter_id": self.meter_id,
                "total_m3": val,
                "reading_date": date_match.group(1) if date_match else None,
                "is_active": True,
            }
        return None

    def _parse_telemetry(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes varying portal schemas into WanOS entity format.
        """
        # Handle nesting (meter, details, or direct reading)
        reading = raw.get("reading") or raw.get("measurement") or raw

        total_m3 = (
            reading.get("total_consumption")
            or reading.get("total_m3")
            or reading.get("consumption")
            or reading.get("reading")
            or reading.get("value")
        )

        reading_date = (
            reading.get("reading_date")
            or reading.get("last_reading_date")
            or reading.get("timestamp")
            or raw.get("date")
        )

        return {
            "meter_id": self.meter_id,
            "serial_number": str(raw.get("serial_number") or raw.get("serial") or self.meter_id),
            "total_m3": float(total_m3) if total_m3 is not None else None,
            "reading_date": reading_date,
            "is_active": raw.get("is_active", True),
            "has_leak_alert": raw.get("divergent_consumption", False),
            "raw_payload": raw,
        }


# -----------------------------------------------------------------------------
# Main Execution Entry Point
# -----------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(description="WanOS Water-Link Scout & Ingest Tool")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--env", default=".env", help="Path to .env (default: .env)")
    parser.add_argument("--meter-id", help="Override meter_id / serial number")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

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
            "Missing credentials! Ensure WATERLINK_USER and WATERLINK_PASSWORD are set in %s",
            env_file.name,
        )
        sys.exit(1)

    if not meter_id:
        logger.error(
            "Missing meter_id! Set waterlink.meter_id in %s or pass --meter-id <id>",
            config_file.name,
        )
        sys.exit(1)

    print("=" * 65)
    print(" WanOS Water-Link Standalone Integration Scout")
    print("=" * 65)
    print(f" Target Meter ID / Serial : {meter_id}")
    print(f" WanOS Ingest IDX         : {idx} (fluid)")
    print(f" Portal Account User      : {user}")
    print(f" Poll Interval Configured : {cfg['poll_interval_hours']} hours")
    print("-" * 65)

    cookie_jar = aiohttp.CookieJar(unsafe=True)
    timeout = aiohttp.ClientTimeout(total=30.0)

    async with aiohttp.ClientSession(cookie_jar=cookie_jar, timeout=timeout) as session:
        client = WaterLinkPortalClient(
            username=user,
            password=password,
            meter_id=meter_id,
            session=session,
        )

        try:
            ok = await client.login()
            if not ok:
                logger.warning("Portal login flow did not explicitly succeed, attempting telemetry fetch anyway...")

            telemetry = await client.get_meter_reading()

            print("\n[SUCCESS] Telemetry Retrieved:")
            print("-" * 65)
            print(f" Cumulative Consumption : {telemetry['total_m3']} m³")
            print(f" Reading Timestamp      : {telemetry['reading_date']}")
            print(f" Meter Active Status    : {telemetry['is_active']}")
            print(f" Leak / Divergent Alert : {telemetry['has_leak_alert']}")
            print("-" * 65)

            # WanOS Telemetry Emission Structure
            wanos_event_payload = {
                "idx": idx,
                "name": "Water-Link Kamstrup",
                "type": "fluid",
                "value": telemetry["total_m3"],
                "unit": "m3",
                "meter_serial": telemetry["serial_number"],
                "last_reading": telemetry["reading_date"],
            }
            print("\nWanOS Event Dispatch Format (EventType.TELEMETRY_UPDATED):")
            print(json.dumps(wanos_event_payload, indent=2))

        except Exception as e:
            logger.error("Scout failed to pull data: %s", e)
            if args.debug:
                logger.exception("Traceback:")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())