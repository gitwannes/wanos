# WanOS Security Architecture: Hybrid HMAC & Network Perimeter Defenses

This document outlines the zero-exposure, cryptographic bridge security architecture designed to securely expose the WanOS Python backend to a public web server (`hofmans.be`) via port-forwarding, while maintaining an unauthenticated local-network bypass for home automation hardware and family terminals.

---

## 1. Topography Overview & Trust Zones

The architecture splits the network topography into three distinct security perimeters:

```text
 [ Public Client ] ---> [ PHP Cloud Host ] (hofmans.be / 103.149.169.109)
                            |
                     (WAN Interface)
                            |  [Layer 1: Router Drops All Non-103.149.169.109 IPs]
                            v
                    [ Home Router ] (NAT Forwarding)
                            |
                     (LAN Interface)
                            |  [Layer 2: FastAPI Middleware Route Guard]
                            v
                   [ Raspberry Pi Backend ] (WanOS Engine)
                            ^
                            |  [Layer 3: Local Network PIN Pass]
                     [ Home Users ] (10.32.251.0/24)
```

1. **The Public Zone (Untrusted):** General web browsers accessing `hofmans.be`. They undergo the cloud host's standard website authentication.
2. **The Cloud DMZ (Semi-Trusted):** The PHP runtime environment at `hofmans.be` (103.149.169.109). It has exclusive proxy access to the home network edge and possesses the cryptographic shared secret.
3. **The Local Network (Trusted Home LAN):** Physical terminals, smart displays, and local network devices on subnet `10.32.251.0/24`.

---

## 2. Layer 1: Network Perimeter Security (Hardware Firewall)

To ensure the Raspberry Pi does not become a target for wide-internet port scans or automated bot exploits, the edge entry point is strictly hardened at the home router.

- **Strict DNAT / Port Forwarding:** A single external WAN port (`18443`) maps directly to the internal Pi node on port `8000`.
- **Source IP Filtering (Whitelisting):** The firewall rule must be configured with a restricted **Source IP / Allowed External IP Range** matched exactly to the static IPv4 address of the `hofmans.be` cloud server: `103.149.169.109`.
- **Security Enforcement:** Any TCP sync packet arriving from an IP address other than `103.149.169.109` is dropped immediately (*DROP* or *DENY* policy). To the rest of the internet, the port reports as completely closed (stealth mode).

> **⚠️ Dynamic Home WAN IP Warning:** If your home router's public WAN IP is assigned by your ISP via DHCP (i.e. not a static IP), it can change after a DHCP lease renewal. This does **not** affect the source IP whitelist (which filters the *cloud server's* IP, which is static), but it does mean the cloud host's cURL destination address — your home WAN IP — must stay current. Ensure Dynamic DNS (e.g. DuckDNS, Cloudflare DDNS) is active and that `proxy.php` resolves your home address via the DDNS hostname rather than a hardcoded IP.

---

## 3. Layer 2: Cryptographic Message Integrity (HMAC-SHA256)

Because IP headers can theoretically be spoofed over raw networks, a second layer of defense enforces application-level cryptographic verification. All communication passing from the cloud host to the home node must use a shared-secret signing pipeline.

### The Secrets Configuration (`.env`)

Both environments must be provisioned with an identical, high-entropy secret string:

```env
WANOS_BRIDGE_SECRET="A_64_CHARACTER_RANDOM_CRYPTOGRAPHIC_HEX_STRING_HERE"
ALLOWED_CLOUD_IP="103.149.169.109"
```

> **⚠️ Secret Rotation Policy:** Treat `WANOS_BRIDGE_SECRET` as a credential that can expire. If it is ever exposed (shared hosting logs, accidental git commit, etc.), rotate it using this procedure:
> 1. Generate a new 64-character hex secret.
> 2. Deploy the new secret to the Pi first (temporarily accept both old and new in middleware).
> 3. Deploy the new secret to the PHP host.
> 4. Remove the old secret acceptance from the Pi.

### The Message Payload Contract

To block replay attacks, every payload requires a strict, short-lived Unix timestamp **and a unique nonce**. The combination of timestamp windowing plus a one-time nonce prevents both old replays and fast replays within the validity window.

```json
{
  "timestamp": 1781234567,
  "nonce": "a3f1c8e2-9b4d-4f2a-8e1d-0c7b5a2d9f3e",
  "action": "TOGGLE_SAUNA",
  "params": { "state": true }
}
```

### The Transaction Routine

1. **PHP Core Preparation:** The PHP controller groups the intended action, the current Unix timestamp, and a freshly generated UUID nonce into a raw plaintext JSON string.
2. **Signature Calculation:** The PHP wrapper computes a keyed hash value using the SHA-256 algorithm:
   $$\text{Signature} = \text{HMAC-SHA256}(\text{JSON Payload}, \text{Shared Secret})$$
3. **Transmission Execution:** The signature is appended to the custom outbound HTTP headers:
   - `X-WanOS-Signature: <calculated_hex_string>`
   - `Content-Type: application/json`

> **Note:** HMAC-SHA256 provides message integrity and authenticity, but **not confidentiality**. Without TLS, the payload is readable in transit. See the TLS setup in Section 5.

---

## 4. Layer 3: FastAPI Application Gateway (Network Middleware)

The FastAPI framework acts as the internal bouncer, evaluating requests using a split-logic routine based on the origin source subnet before allowing processing to hit any operational execution routes.

### Middleware Logic Execution Path

```text
[ Incoming Request ]
         |
         v
     [ Extract Request Source IP ]
         |
         +---> Is Source IP in 10.32.251.0/24?
         |        |
         |        +-- [YES] --> Bypass Cryptography
         |                      Require: Basic 4-Digit Local PIN Check (for now)
         |                      Route Execution Granted
         |
         +---> Is Source IP == 103.149.169.109?
                  |
                  +-- [NO]  --> Log Security Alert -> HTTP 403 Forbidden
                  |
                  +-- [YES] --> Extract JSON Payload & 'X-WanOS-Signature' Header
                                   |
                                   v
                                [ Is Timestamp Older Than 30 Seconds? ]
                                   |
                                   +-- [YES] --> Reject Replay Attack -> HTTP 403
                                   |
                                   +-- [NO]  --> Has This Nonce Been Seen Before?
                                                   |
                                                   +-- [YES] --> Reject Replay -> HTTP 403
                                                   |
                                                   +-- [NO]  --> Record Nonce in Seen-Set
                                                                   |
                                                                   v
                                                             [ Compute Local HMAC Hash ]
                                                                   |
                                                             [ Do Hashes Match? ]
                                                                   |
                                                                   +-- [NO]  --> Reject Token -> HTTP 403
                                                                   +-- [YES] --> Route Execution Granted
```

---

## 5. Reference Implementation Snippets

### 5.1 TLS Certificate Generation (Raspberry Pi)

Uvicorn terminates TLS directly — no reverse proxy is required. The certificate must include a **Subject Alternative Name (SAN)** for the Pi's LAN IP, as modern TLS clients (including curl) validate SANs and will reject CN-only certificates.

```bash
# Run once on the Pi.
# Replace 10.32.251.X with your Pi's actual static LAN IP.
openssl req -x509 -newkey rsa:4096 \
  -keyout wanos_key.pem \
  -out wanos_cert.pem \
  -days 3650 -nodes \
  -subj "/CN=wanos-pi" \
  -addext "subjectAltName=IP:10.32.251.X"

# Lock down permissions — readable only by wanos_user (see Section 5.4)
chmod 600 wanos_key.pem wanos_cert.pem
chown wanos_user:wanos_user wanos_key.pem wanos_cert.pem

# Copy wanos_cert.pem to the hofmans.be host so cURL can pin it via CURLOPT_CAINFO.
```

Then update `wanos_boot.sh` to launch uvicorn with TLS on port 8000 (router forwards 18443 → 8000):

```bash
APP_ARGS="main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile /path/to/wanos_key.pem \
  --ssl-certfile /path/to/wanos_cert.pem"
```

> **Note:** Do not use `CURLOPT_SSL_VERIFYPEER = false` on the PHP side. Disabling peer verification defeats TLS entirely by accepting any certificate, including forged ones. Instead, pin the Pi's specific cert via `CURLOPT_CAINFO` as shown in the PHP snippet below.

---

### 5.2 FastAPI Application Hardening (`main.py`)

FastAPI auto-generates interactive API documentation at `/docs`, `/redoc`, and `/openapi.json`. In production these must be disabled — they provide a full, interactive map of every control endpoint to anyone who can reach the server.

```python
# Initialize FastAPI for production — all documentation endpoints disabled
app: FastAPI = FastAPI(
    lifespan=lifespan,
    title="WanOS Backend API",
    docs_url=None,      # Disables /docs Swagger UI
    redoc_url=None,     # Disables /redoc UI
    openapi_url=None,   # Disables the underlying /openapi.json schema
)
```

---

### 5.3 Process Isolation: Dedicated `wanos_user` (Raspberry Pi)

Running WanOS as root means any vulnerability in FastAPI or Uvicorn grants an attacker total control of the Pi. Create a dedicated, unprivileged system user instead.

```bash
# Create a system user with no login shell and no home directory
sudo useradd --system --no-create-home --shell /usr/sbin/nologin wanos_user

# Grant GPIO access — required for sauna and hardware control on Raspberry Pi OS.
# Without this group membership, GPIO calls fail silently at runtime.
sudo usermod -aG gpio wanos_user

# Grant ownership of the WanOS directory only
sudo chown -R wanos_user:wanos_user /path/to/wanos
sudo chmod -R 750 /path/to/wanos
```

Update `wanos_boot.sh` to run the process as `wanos_user`:

```bash
# Drop privileges before launching — never run as root
exec sudo -u wanos_user uvicorn $APP_ARGS
```

Or if using a systemd service (recommended for auto-restart on reboot):

```ini
[Unit]
Description=WanOS Backend
After=network.target

[Service]
User=wanos_user
Group=wanos_user
WorkingDirectory=/path/to/wanos
ExecStart=uvicorn main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile /path/to/wanos_key.pem \
  --ssl-certfile /path/to/wanos_cert.pem
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

### 5.4 Cloud Host: PHP Secret Storage (`hofmans.be`)

The `WANOS_BRIDGE_SECRET` must **never** be stored inside the Apache public web root (`public_html` or `/var/www/html`). If Apache ever misconfigures and serves PHP files as plain text — a common shared hosting failure mode — the secret becomes publicly downloadable.

Store it in a directory above the web root, with permissions locked to the PHP process user:

```bash
# On hofmans.be — create a private config directory above the web root
mkdir -p /home/your_cpanel_user/private_config
chmod 700 /home/your_cpanel_user/private_config
chown your_php_user:your_php_user /home/your_cpanel_user/private_config

# Create the secrets file
echo 'WANOS_BRIDGE_SECRET="YOUR_64_CHARACTER_HEX_SECRET"' \
  > /home/your_cpanel_user/private_config/.env
chmod 600 /home/your_cpanel_user/private_config/.env
```

Reference it in PHP without ever touching the web root:

```php
// Load secret from outside the public web directory
$config = parse_ini_file('/home/your_cpanel_user/private_config/.env');
$shared_secret = $config['WANOS_BRIDGE_SECRET'];
```

---

### 5.5 Cloud Host: PHP Outbound Request Signer (`proxy.php`)

```php
<?php
// Load secret from outside the public web root (see Section 5.4)
$config = parse_ini_file('/home/your_cpanel_user/private_config/.env');
$shared_secret = $config['WANOS_BRIDGE_SECRET'];
$backend_url   = "https://your-ddns-hostname.duckdns.org:18443/api/event";

// Assemble payload with replay protection (timestamp + unique nonce)
$payload_data = [
    "timestamp" => time(),
    "nonce"     => bin2hex(random_bytes(16)), // cryptographically random nonce
    "action"    => "TOGGLE_SAUNA",
    "params"    => ["state" => true]
];

$json_payload = json_encode($payload_data);

// Calculate the HMAC signature
$signature = hash_hmac('sha256', $json_payload, $shared_secret);

// Basic per-session rate limit — prevents rapid-fire relay abuse by
// an authenticated user hammering proxy.php.
session_start();
$now = time();
if (isset($_SESSION['last_wanos_call']) && ($now - $_SESSION['last_wanos_call']) < 2) {
    http_response_code(429);
    echo "Rate limit: too many requests.";
    exit;
}
$_SESSION['last_wanos_call'] = $now;

// Initialize cURL with TLS — pin the Pi's self-signed cert via CURLOPT_CAINFO.
// Never use CURLOPT_SSL_VERIFYPEER = false; that disables all certificate validation.
$ch = curl_init($backend_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "POST");
curl_setopt($ch, CURLOPT_POSTFIELDS, $json_payload);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, true);
curl_setopt($ch, CURLOPT_CAINFO, '/home/your_cpanel_user/private_config/pi_cert.pem');
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'X-WanOS-Signature: ' . $signature
]);

$response  = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($http_code === 200) {
    echo "Command Executed Successfully";
} else {
    echo "Access Denied / Execution Failure: " . $http_code;
}
?>
```

---

### 5.6 Home Node: FastAPI Guard Middleware (`middleware/security.py`)

```python
import time
import hmac
import hashlib
import ipaddress
import json
import logging
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

log = logging.getLogger("wanos.security")

# Nonce seen-set: maps nonce -> expiry timestamp.
# In a multi-worker setup, replace with Redis or shared memory.
_seen_nonces: dict[str, float] = {}
_NONCE_TTL = 60  # seconds — 2x the replay window for safety margin


def _purge_expired_nonces() -> None:
    """Remove nonces older than TTL to bound memory usage."""
    now = time.time()
    expired = [k for k, v in _seen_nonces.items() if v < now]
    for k in expired:
        del _seen_nonces[k]


class WanOSSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, secret_key: str, allowed_cloud_ip: str):
        super().__init__(app)
        self.secret_key = secret_key.encode("utf-8")
        self.allowed_cloud_ip = ipaddress.ip_address(allowed_cloud_ip)
        # Constrain LAN bypass to the actual home subnet — do NOT use is_private(),
        # which also matches CGNAT (100.64.x.x) and link-local (169.254.x.x).
        self.local_subnet = ipaddress.ip_network("10.32.251.0/24")

    async def dispatch(self, request: Request, call_next):
        client_ip_str = request.client.host
        client_ip = ipaddress.ip_address(client_ip_str)

        # Context 1: Local subnet bypass — pinned to 10.32.251.0/24
        if client_ip in self.local_subnet:
            return await call_next(request)

        # Context 2: Remote cloud bridge — IP must match 103.149.169.109
        if client_ip != self.allowed_cloud_ip:
            # 🚨 ESCALATION: This should be impossible due to the router firewall.
            # Trigger an immediate highest-priority alert.
            log.critical(
                f"SECURITY BREACH DETECTED! Perimeter violation on WAN interface. "
                f"Incoming request from UNTRUSTED IP: {client_ip_str}. "
                f"This indicates a firewall leak or active targeted scan!",
                extra={"category": "SEC"}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Perimeter Violation: Execution blocked."
            )

        # Validate cryptographic signature header
        signature = request.headers.get("X-WanOS-Signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing cryptographic identity signature."
            )

        # Consume body — re-injected below so downstream endpoints can also read it
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")

        try:
            payload = json.loads(body_str)
            request_ts = int(payload.get("timestamp", 0))
            nonce = str(payload.get("nonce", ""))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request structure."
            )

        # Replay attack mitigation — timestamp window (30 seconds)
        current_ts = int(time.time())
        if abs(current_ts - request_ts) > 30:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Stale transmission detected. Window expired."
            )

        # Replay attack mitigation — nonce uniqueness check
        _purge_expired_nonces()
        if not nonce or nonce in _seen_nonces:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Duplicate or missing nonce. Replay rejected."
            )
        _seen_nonces[nonce] = time.time() + _NONCE_TTL

        # Verify HMAC signature — constant-time comparison prevents timing attacks.
        # Uses hmac.HMAC() explicitly; hmac.new() is an undocumented alias — avoid it.
        expected_signature = hmac.HMAC(
            self.secret_key,
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cryptographic verification token failure."
            )

        # Re-inject body stream so downstream endpoint handlers can read it.
        # Constructs a new Request rather than patching the private _receive attribute.
        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        new_request = Request(request.scope, receive)
        return await call_next(new_request)
```

---

### 5.7 Home Node: Middleware Registration (`main.py`)

```python
from core.config import settings
from middleware.security import WanOSSecurityMiddleware

app.add_middleware(
    WanOSSecurityMiddleware,
    secret_key=settings.WANOS_BRIDGE_SECRET,
    allowed_cloud_ip=settings.ALLOWED_CLOUD_IP,  # "103.149.169.109"
)
```

---

## 6. Implementation Master Plan

Because we are building a custom cryptographic bridge, the order of operations is critical. Establish the secrets and the router rules *before* turning on the Python middleware to avoid locking yourself out.

### Phase 1: Infrastructure & Secrets Preparation

1. **Generate the Shared Secret:**
   ```bash
   openssl rand -hex 32
   ```
   This produces your `WANOS_BRIDGE_SECRET` — a 64-character cryptographic hex string.

2. **Confirm the Cloud IP:** The static IPv4 address of `hofmans.be` is `103.149.169.109`. This is the only external IP your home will trust.

3. **Home WAN IP / DDNS:** Ensure Dynamic DNS is active (e.g. DuckDNS, Cloudflare DDNS). Configure `proxy.php` to target your home address via the DDNS hostname, not a hardcoded IP.

### Phase 2: System User & Filesystem Preparation (Raspberry Pi)

1. Create `wanos_user` and add it to the `gpio` group (see Section 5.3). Missing the `gpio` group causes silent hardware control failures at runtime.
2. Set ownership and permissions on the WanOS directory and TLS key files.

### Phase 3: TLS Certificate Generation (Raspberry Pi)

1. Run the `openssl` command from Section 5.1, substituting your Pi's actual LAN IP in the SAN field.
2. Set `chmod 600` on both `.pem` files and `chown` them to `wanos_user`.
3. Transfer `wanos_cert.pem` to `hofmans.be` — store it alongside `proxy.php`'s private config directory (outside the web root).

### Phase 4: Router Configuration (The Invisible Shield)

1. **Create the Port Forwarding Rule:** Forward external port `18443` to your Pi's LAN IP on port `8000`.
2. **Apply Source IP Whitelisting:** Set the *Source IP* / *External Host* field to `103.149.169.109`.
   - *Security check:* Connect your phone to 4G mobile data and try `https://<your-home-wan-ip>:18443`. It should time out with no response.

### Phase 5: Backend Security Enactment (The Bouncer)

1. **Update `.env`:** Add `WANOS_BRIDGE_SECRET` and `ALLOWED_CLOUD_IP="103.149.169.109"`.
2. **Update `core/config.py`:** Load and validate these fields on boot via Pydantic.
3. **Disable API docs:** Set `docs_url=None`, `redoc_url=None`, `openapi_url=None` in the `FastAPI()` constructor (Section 5.2).
4. **Register `WanOSSecurityMiddleware`** in `main.py` (Section 5.7).
5. **Update `wanos_boot.sh`:** Add TLS flags and run as `wanos_user` (Section 5.3).

### Phase 6: Cloud Host Implementation (The Proxy Signer)

1. **Create the private config directory** above the web root and store `WANOS_BRIDGE_SECRET` and `pi_cert.pem` there with `chmod 700` / `chmod 600` (Section 5.4).
2. **Create `proxy.php`** (Section 5.5). Verify it:
   - Loads the secret from outside the web root.
   - Generates a fresh nonce per request.
   - Signs with HMAC-SHA256.
   - Uses `CURLOPT_CAINFO` pointing to `pi_cert.pem` — never `CURLOPT_SSL_VERIFYPEER = false`.
   - Enforces per-session rate limiting.

### Phase 7: Frontend Routing Adjustment (The Smart Dashboard)

1. **Dynamic API Paths in `app.js`:** Detect `window.location.hostname` and branch:
   - **Local** (`10.32.251.x`): commands → `/api/event` directly, live updates → SSE at `/api/state/sse`.
   - **Remote** (`hofmans.be`): commands → `proxy.php`, live updates → HTTP polling at `/api/state` every 2 seconds.

> **⚠️ Critical Architecture Warning (Shared Hosting & SSE):** Standard PHP shared hosting enforces output buffering and a `max_execution_time` of ~60 seconds, which terminates long-running SSE streams. The remote dashboard path must use polling, not SSE.

---

## 7. Master File Modification List

| File Location | File Name | Summary of Changes |
|:---|:---|:---|
| **Raspberry Pi** | `.env` | Add `WANOS_BRIDGE_SECRET` and `ALLOWED_CLOUD_IP="103.149.169.109"` |
| **Raspberry Pi** | `core/config.py` | Add `WANOS_BRIDGE_SECRET` and `ALLOWED_CLOUD_IP` to `AppConfig` Pydantic schema |
| **Raspberry Pi** | `main.py` | Register `WanOSSecurityMiddleware`; disable docs/redoc/openapi URLs |
| **Raspberry Pi** | `wanos_boot.sh` | Add `--ssl-keyfile` / `--ssl-certfile` TLS flags; run process as `wanos_user` |
| **Raspberry Pi** | `middleware/security.py` | New file — `WanOSSecurityMiddleware` with nonce tracking, subnet pinning, `hmac.HMAC()`, safe body re-injection |
| **Raspberry Pi** | `wanos_cert.pem` / `wanos_key.pem` | Generated via `openssl` with SAN; `chmod 600`, owned by `wanos_user` |
| **Raspberry Pi** | `frontend/app.js` | Detect hostname; switch SSE → polling and direct → proxy when remote |
| **Cloud Server** | `private_config/.env` | `WANOS_BRIDGE_SECRET` stored outside web root; `chmod 600` |
| **Cloud Server** | `private_config/pi_cert.pem` | Pi's self-signed cert for cURL pinning; `chmod 600` |
| **Cloud Server** | `proxy.php` *(New)* | Signs requests with nonce + timestamp + HMAC; rate limiting; `CURLOPT_CAINFO` pinning |
| **Cloud Server** | `index.html` *(New)* | Upload `index.html` + `app.js` to `hofmans.be/wanos/` to serve UI to authenticated users |

---

## 8. WanOS Security Architecture — Weaknesses & Improvement Suggestions
---> to incorporate into the document above

## 1. Router & Network Perimeter Weaknesses
- **Consumer routers may silently drop source-IP filtering rules** after firmware updates or resets.  
  *Suggestion:* Implement an automated external self-test that periodically attempts to connect back to your WAN port and alerts if the port is reachable.

- **Some routers apply source filtering after NAT**, meaning the port may still appear open to scanners.  
  *Suggestion:* Validate with an external scanning service after every router change.

- **No automated monitoring of firewall integrity.**  
  *Suggestion:* Add a cron-based watchdog that verifies the port is closed to all non-whitelisted IPs.

---

## 2. HMAC Layer Weaknesses
- **Nonce storage is in-memory only.** A Pi reboot clears the nonce table, reopening a replay window until timestamps expire.  
  *Suggestion:* Persist nonces for 30–60 seconds using Redis, SQLite, or a tmpfs file.

- **Timestamp window depends on clock accuracy.** Clock drift between PHP host and Pi can cause false rejections or allow borderline replays.  
  *Suggestion:* Add a `/health/time` endpoint and let PHP adjust for drift.

- **No signature versioning.** Future changes to payload structure could break compatibility.  
  *Suggestion:* Add a `version` field to the signed payload.

---

## 3. FastAPI Middleware Weaknesses
- **LAN PIN bypass is extremely weak.** A 4-digit PIN is brute-forceable by any compromised LAN device.  
  *Suggestion:* Increase to 6 digits, add rate limiting, or replace with a LAN-shared secret.

- **LAN trust is too broad.** Any device on 10.32.251.0/24 is implicitly trusted.  
  *Suggestion:* Move IoT devices to a separate VLAN; restrict trusted subnet to specific MAC/IP pairs.

- **Critical logs are local only.** A compromise or filesystem issue could hide intrusion attempts.  
  *Suggestion:* Forward logs to a remote syslog server or Telegram/Matrix alert bot.

- **No rate limiting on cloud-origin requests.** Only PHP side limits frequency.  
  *Suggestion:* Add per-IP or per-route rate limiting inside FastAPI as a second layer.

---

## 4. TLS & Certificate Weaknesses
- **Certificate validity is 10 years.** Long-lived certs increase exposure if the key is ever leaked.  
  *Suggestion:* Rotate every 12–24 months and automate distribution to PHP host.

- **No certificate revocation mechanism.** If the Pi key leaks, PHP will continue trusting it.  
  *Suggestion:* Maintain a versioned certificate file and require explicit updates.

---

## 5. PHP Host Weaknesses
- **Shared hosting is inherently unstable.** PHP version changes, Apache misconfigurations, or cPanel resets can break the bridge.  
  *Suggestion:* Add a periodic health check from PHP → Pi and alert on failure.

- **Session-based rate limiting is fragile.** Session resets or multiple browsers bypass the limit.  
  *Suggestion:* Use IP-based or Redis-based rate limiting.

- **No CSRF protection on proxy.php.** If the user is logged in, a malicious site could trigger commands.  
  *Suggestion:* Add CSRF tokens or require a second header.

- **No Content-Security-Policy on frontend.** XSS could allow command injection via proxy.php.  
  *Suggestion:* Add strict CSP headers.

---

## 6. Frontend Weaknesses
- **Remote polling every 2 seconds is heavy.** Causes unnecessary load on PHP and Pi.  
  *Suggestion:* Switch to long-polling (30–60 seconds) or a lightweight push mechanism.

- **Frontend trust model is implicit.** Browser JS can be modified by extensions or compromised clients.  
  *Suggestion:* Add server-side validation of allowed actions.

---

## 7. Operational Weaknesses
- **No automated secret rotation.** Manual rotation increases risk of stale or forgotten secrets.  
  *Suggestion:* Implement a rotation schedule with dual-secret acceptance windows.

- **No backup strategy for TLS keys, secrets, or configs.**  
  *Suggestion:* Store encrypted backups off-device.

- **No intrusion detection.**  
  *Suggestion:* Add fail2ban rules for unexpected IPs or repeated failures.

---

## 8. Architectural Weaknesses
- **Single point of failure: PHP host.** If compromised, attacker gains full remote control.  
  *Suggestion:* Add a second factor (e.g., rotating token, IP-bound token, or short-lived signed challenge).

- **Single shared secret for all actions.**  
  *Suggestion:* Use per-action or per-route sub-keys derived via HKDF.

- **No audit trail of executed commands.**  
  *Suggestion:* Log all accepted commands with timestamp, IP, and nonce to append-only storage.

