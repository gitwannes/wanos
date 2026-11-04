# --- file: docs/integration_waterlink.md ---
# Water-Link digital meter

Mijn Water-Link portal (`portaaldigitalemeters.water-link.be`) cumulative water meter.

| Ship | Status |
|---|---|
| **G23** scout | **Done 2026-11-04** — standalone `waterlink_scout.py` |
| **G24** WanOS bridge | Open — poll / ingest / Admin (see [`phaseG-integrations.md`](todo/phaseG-integrations.md) § G24) |

## Scout (`waterlink_scout.py`)

One-shot read of cumulative m³ for the configured meter. Does **not** ingest into WanOS.

```bash
python waterlink_scout.py
python waterlink_scout.py --debug
python waterlink_scout.py --meter-id <serial>
```

| Source | Keys |
|---|---|
| `config.yaml` → `waterlink:` | `meter_id`, `poll_interval_hours`, `idx` (idx printed only; bridge deferred) |
| `.env` | `WATERLINK_USER`, `WATERLINK_PASSWORD` (see `.env.example`) |

**Auth:** OIDC **authorization_code + PKCE S256** against SAP CIAM. Scout loads public `clientId` / `authority` from `GET /api/config`, opens authorize, POSTs SAP `#logOnForm` (`j_username` / `j_password`), exchanges `code` + `code_verifier` for Bearer. Resource Owner Password is **not** allowed for this SPA client.

**Telemetry:** `GET /api/meters/{meter_id}` → `meterReading` (thousands comma, e.g. `"2,841"` → **2841.0** m³) + `latestMeterReading`.

**Notes:** Access token `expires_in` ~840 s; no refresh_token in observed flow. Each scout run performs a full headless login. Incapsula + SAP form HTML can churn — treat failures as vendor-UI risk.

Delivery archive: [`docs/todo/phaseG-integrations.md`](todo/phaseG-integrations.md) § G23.
