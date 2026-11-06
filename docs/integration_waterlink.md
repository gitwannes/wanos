# --- file: docs/integration_waterlink.md ---
# Water-Link digital meter

Mijn Water-Link portal (`portaaldigitalemeters.water-link.be`) cumulative water meter.

| Ship | Status |
|---|---|
| **G23** scout | **Done 2026-11-04** — standalone `waterlink_scout.py` |
| **G24** WanOS bridge | **Done 2026-11-05** — poll / ingest / Admin (Pi smoke OK) |

## Bridge (G24)

Telemetry-only portal poll into WanOS. **No C18** (no outbound commands).

| Config / secret | Role |
|---|---|
| `config.yaml` → `waterlink:` | `meter_id`, `poll_interval_hours` (default **6**), `idx` (**82001**), `name` |
| `.env` | `WATERLINK_USER`, `WATERLINK_PASSWORD` (service restart after change) |

| Runtime | Behaviour |
|---|---|
| **Poll** | Every `poll_interval_hours`: full OIDC PKCE + SAP form login → `GET /api/meters/{id}` → cumulative m³ |
| **Ingest** | `WATERLINK_METRIC` → `devices[82001]` absolute m³; history via `note_absolute_fluid` |
| **Entity** | Frozen `sensor.fluid.waterlink.digital_meter` (display name from `waterlink.name`) |
| **Admin** | Water-Link row — LIVE / DISABLED / OFFLINE + master switch (enabled at boot when bridge starts / `WANOS_AUTOSTART`) |
| **Health** | **No** portal ping every health tick. Offline after **2 consecutive** poll failures; health-monitor auto-kill then disables the integration |
| **Reload** | Full config reload remaps `waterlink:` (no G6 scoped row) |
| **Explorer / History** | Read-only fluid row; value as **m³** (`nl-BE`, e.g. portal `"3,616"` → **3,616 m³** ≈ 3616 L). History: **month** (daily bars) + **year** (monthly bars), same shape as cold/hot water — no day chart. If period consumption is absurd vs face total (poisoned deltas after a scale fix), history auto-purges that idx. Hidden when disabled |
| **Logs** | `[WaterLink]` |

**Code:** `integrations/waterlink.py` + shared `integrations/waterlink_client.py` (scout reuses the client).

**Out of scope:** replacing pulse meters `11002`/`11003`; billing/invoices; portal chart APIs; G6 scoped-reload checkbox.

## Scout (`waterlink_scout.py`)

One-shot read of cumulative m³ for the configured meter. Does **not** ingest into WanOS.

```bash
python waterlink_scout.py
python waterlink_scout.py --debug
python waterlink_scout.py --meter-id <serial>
```

**Auth:** OIDC **authorization_code + PKCE S256** against SAP CIAM. Loads public `clientId` / `authority` from `GET /api/config`, opens authorize, POSTs SAP `#logOnForm` (`j_username` / `j_password`), exchanges `code` + `code_verifier` for Bearer. Resource Owner Password is **not** allowed for this SPA client.

**Telemetry:** `GET /api/meters/{meter_id}` → `meterReading` (Belgian locale: comma = decimal, e.g. `"3,616"` → **3.616** m³) + `latestMeterReading`.

**Notes:** Access token `expires_in` ~840 s; no refresh_token in observed flow. Each poll/scout run performs a full headless login. Incapsula + SAP form HTML can churn — treat failures as vendor-UI risk.

Delivery archive pointers: [`docs/todo/phaseG-integrations.md`](todo/phaseG-integrations.md) § G23 / § G24.
