# --- file: integrations/waterlink_client.py ---
"""
Shared Water-Link portal client (G23 scout + G24 bridge).

OIDC authorization_code + PKCE S256 with headless SAP #logOnForm login,
then GET /api/meters/{meter_id} for cumulative m3.
"""

from __future__ import annotations

import base64
import hashlib
import html as html_lib
import json
import logging
import re
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import aiohttp

PORTAL_BASE_URL = "https://portaaldigitalemeters.water-link.be"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WanOS/1.0"
)

logger = logging.getLogger("waterlink.client")


def parse_meter_reading_m3(raw: Any) -> Optional[float]:
    """
    Portal meterReading uses Belgian/Dutch locale for m3.

    Comma = decimal separator, dot = thousands.
    Examples: "3,616" -> 3.616; "2.841,5" -> 2841.5; "2841" -> 2841.0

    Operator correction 2026-11-06: earlier G23 thousands-comma parse was wrong
    (face reading is ~3.6 m3 / ~3600 L, not thousands of m3).
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        return None
    if "," in text and "." in text:
        # 1.234,567 -> 1234.567
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        # 3,616 -> 3.616 (decimal comma)
        text = text.replace(",", ".")
    # Single '.' (or plain digits): standard float decimal
    return float(text)


def make_pkce_pair() -> Tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256 PKCE."""
    verifier = secrets.token_hex(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def parse_logon_form(html: str) -> Tuple[str, Dict[str, str]]:
    """
    Extract action URL path and input name->value from SAP #logOnForm.
    Falls back to first POST form if id is missing.
    """
    open_match = re.search(
        r'<form\b[^>]*id=["\']logOnForm["\'][^>]*>',
        html,
        flags=re.I,
    )
    if not open_match:
        open_match = re.search(
            r'<form\b[^>]*method=["\']post["\'][^>]*>',
            html,
            flags=re.I,
        )
    if not open_match:
        raise RuntimeError("Could not find SAP logOnForm in authorize HTML")

    form_tag = open_match.group(0)
    start = open_match.end()
    close = re.search(r"</form>", html[start:], flags=re.I)
    if not close:
        raise RuntimeError("logOnForm is not closed in authorize HTML")
    form_inner = html[start : start + close.start()]

    action_match = re.search(r'action=["\']([^"\']+)["\']', form_tag, flags=re.I)
    action = action_match.group(1) if action_match else "/oauth2/authorize"

    fields: Dict[str, str] = {}
    for m in re.finditer(r"<input\b([^>]*)>", form_inner, flags=re.I):
        attrs = m.group(1)
        name_m = re.search(r'\bname=["\']([^"\']+)["\']', attrs, flags=re.I)
        if not name_m:
            continue
        name = html_lib.unescape(name_m.group(1))
        val_m = re.search(r'\bvalue=["\']([^"\']*)["\']', attrs, flags=re.I)
        value = html_lib.unescape(val_m.group(1)) if val_m else ""
        fields[name] = value

    if "j_username" not in fields or "j_password" not in fields:
        raise RuntimeError(
            "logOnForm missing j_username/j_password "
            f"(fields={sorted(fields.keys())})"
        )
    return action, fields


def extract_auth_code(redirect_url: str, expected_state: str) -> str:
    """Parse authorization code from redirect URL; validate state when present."""
    parsed = urlparse(redirect_url)
    qs = parse_qs(parsed.query)
    if "error" in qs:
        desc = qs.get("error_description", [""])[0]
        raise RuntimeError(
            f"OIDC authorize redirect error: {qs['error'][0]} {desc}"
        )
    code = (qs.get("code") or [None])[0]
    if not code:
        raise RuntimeError(f"Redirect URL missing code: {redirect_url[:200]}")
    state = (qs.get("state") or [None])[0]
    if state is not None and state != expected_state:
        raise RuntimeError("OIDC state mismatch on authorize redirect")
    return code


class WaterLinkPortalClient:
    """OIDC auth-code+PKCE (headless form login) + REST meter read."""

    def __init__(
        self,
        username: str,
        password: str,
        meter_id: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self.username = username
        self.password = password
        self.meter_id = meter_id
        self.session = session
        self.access_token: Optional[str] = None
        self.client_id: Optional[str] = None
        self.authority: Optional[str] = None
        self.redirect_uri: Optional[str] = None
        self.token_endpoint: Optional[str] = None
        self.authorization_endpoint: Optional[str] = None

    def _browser_headers(self, *, json_accept: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "nl-BE,nl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"{PORTAL_BASE_URL}/",
            "Origin": PORTAL_BASE_URL,
        }
        if json_accept:
            headers["Accept"] = "application/json, text/plain, */*"
            headers["Content-Type"] = "application/json"
        else:
            headers["Accept"] = (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            )
        return headers

    async def _load_portal_oidc_config(self) -> None:
        """Landing + /api/config + OIDC discovery."""
        headers = self._browser_headers()
        async with self.session.get(f"{PORTAL_BASE_URL}/", headers=headers) as resp:
            logger.debug("Portal landing: HTTP %d", resp.status)
            await resp.read()

        async with self.session.get(
            f"{PORTAL_BASE_URL}/api/config",
            headers=self._browser_headers(json_accept=True),
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(
                    f"GET /api/config failed: HTTP {resp.status}: {body[:300]}"
                )
            data = json.loads(body)

        self.client_id = str(data.get("clientId") or "").strip()
        self.authority = str(data.get("authority") or "").rstrip("/")
        self.redirect_uri = str(
            data.get("redirectUri") or PORTAL_BASE_URL
        ).rstrip("/")
        if not self.redirect_uri:
            self.redirect_uri = PORTAL_BASE_URL
        if not self.client_id or not self.authority:
            raise RuntimeError(
                f"/api/config missing clientId/authority: keys={list(data.keys())}"
            )
        logger.info(
            "Portal OIDC client_id=%s authority=%s redirect_uri=%s",
            self.client_id,
            self.authority,
            self.redirect_uri,
        )

        oidc_url = f"{self.authority}/.well-known/openid-configuration"
        async with self.session.get(
            oidc_url,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(
                    f"OIDC discovery failed: HTTP {resp.status}: {body[:300]}"
                )
            oidc = json.loads(body)

        self.token_endpoint = str(oidc.get("token_endpoint") or "").strip()
        self.authorization_endpoint = str(
            oidc.get("authorization_endpoint") or ""
        ).strip()
        if not self.token_endpoint or not self.authorization_endpoint:
            raise RuntimeError(
                "OIDC discovery missing token_endpoint or authorization_endpoint"
            )
        logger.debug("authorization_endpoint=%s", self.authorization_endpoint)
        logger.debug("token_endpoint=%s", self.token_endpoint)

    async def login_authorization_code_pkce(self) -> None:
        """
        Headless authorization_code + PKCE:
        GET authorize (login form) -> POST j_username/j_password -> code -> token.
        """
        await self._load_portal_oidc_config()
        assert self.authorization_endpoint and self.token_endpoint
        assert self.client_id and self.redirect_uri

        code_verifier, code_challenge = make_pkce_pair()
        state = secrets.token_hex(16)

        auth_params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        authorize_url = f"{self.authorization_endpoint}?{urlencode(auth_params)}"

        logger.info("Opening OIDC authorize (PKCE S256)...")
        async with self.session.get(
            authorize_url,
            headers=self._browser_headers(),
            allow_redirects=True,
        ) as resp:
            login_html = await resp.text()
            login_url = str(resp.url)
            logger.debug("Authorize landed HTTP %d url=%s", resp.status, login_url)
            if resp.status != 200:
                raise RuntimeError(
                    f"GET authorize failed: HTTP {resp.status}: {login_html[:300]}"
                )

        # Already logged in / silent auth may redirect straight to portal with code.
        if "code=" in str(login_url) and urlparse(str(login_url)).netloc.endswith(
            "water-link.be"
        ):
            code = extract_auth_code(str(login_url), state)
        else:
            action_path, form_fields = parse_logon_form(login_html)
            form_fields["j_username"] = self.username
            form_fields["j_password"] = self.password
            form_fields.pop("rememberme", None)

            post_url = urljoin(f"{self.authority}/", action_path.lstrip("/"))
            if action_path.startswith("http"):
                post_url = action_path

            post_headers = self._browser_headers()
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            post_headers["Origin"] = self.authority
            post_headers["Referer"] = login_url

            logger.info("Submitting SAP logOnForm (headless)...")
            async with self.session.post(
                post_url,
                data=form_fields,
                headers=post_headers,
                allow_redirects=False,
            ) as resp:
                location = resp.headers.get("Location")
                body = await resp.text()
                logger.debug(
                    "logOnForm POST HTTP %d location=%s",
                    resp.status,
                    (location or "")[:180],
                )
                if resp.status not in (302, 303, 307, 308) or not location:
                    raise RuntimeError(
                        "SAP logOnForm did not redirect with auth code "
                        f"(HTTP {resp.status}). Check credentials or form churn. "
                        f"Body[:400]={body[:400]}"
                    )
                redirect_url = urljoin(post_url, location)
                code = extract_auth_code(redirect_url, state)

        logger.info("Exchanging authorization code for access_token...")
        token_form = {
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
            "client_id": self.client_id,
        }
        token_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": PORTAL_BASE_URL,
            "Referer": f"{PORTAL_BASE_URL}/",
        }
        async with self.session.post(
            self.token_endpoint,
            data=token_form,
            headers=token_headers,
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(
                    f"OIDC token exchange failed (HTTP {resp.status}): {body[:500]}"
                )
            try:
                token_payload = json.loads(body)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"OIDC token response was not JSON: {body[:300]}"
                ) from exc

        token = token_payload.get("access_token")
        if not token:
            raise RuntimeError(
                "OIDC token exchange returned no access_token "
                f"(keys={list(token_payload.keys())})"
            )
        self.access_token = str(token)
        logger.info(
            "Access token acquired (expires_in=%s, token_type=%s)",
            token_payload.get("expires_in"),
            token_payload.get("token_type"),
        )

    async def get_meter_reading(self) -> Dict[str, Any]:
        """GET /api/meters/{meter_id} with Bearer access_token."""
        if not self.access_token:
            raise RuntimeError(
                "Not authenticated - call login_authorization_code_pkce first"
            )

        url = f"{PORTAL_BASE_URL}/api/meters/{self.meter_id}"
        headers = self._browser_headers(json_accept=True)
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Referer"] = f"{PORTAL_BASE_URL}/water-meter/{self.meter_id}"

        logger.info("Fetching meter telemetry: %s", url)
        async with self.session.get(url, headers=headers) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(
                    f"GET /api/meters/{self.meter_id} failed: "
                    f"HTTP {resp.status}: {body[:500]}"
                )
            try:
                data = json.loads(body)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Meter response was not JSON: {body[:300]}"
                ) from exc

        raw_reading = data.get("meterReading")
        total_m3 = parse_meter_reading_m3(raw_reading)
        return {
            "meter_id": str(data.get("meterNumber") or self.meter_id),
            "total_m3": total_m3,
            "meter_reading_raw": raw_reading,
            "reading_date": data.get("latestMeterReading"),
            "is_active": bool(data.get("isActive", False)),
            "has_leak_alert": bool(data.get("divergentConsumption", False)),
            "meter_reading_available": bool(data.get("meterReadingAvailable", False)),
            "days_offset": data.get("daysOffset"),
            "address": data.get("address"),
            "raw_payload": data,
        }
