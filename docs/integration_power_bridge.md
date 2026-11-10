# --- file: docs/integration_power_bridge.md ---
# Power dashboard bridge (W2)

**Status:** shipped **2026-11-06** (homepower_dashboard **W2** Done).

Machine-to-machine link so **homepower_dashboard** can read selected WanOS sensors (display only). API key design is shared with future **W1** (Power → WanOS).

## Auth

| Piece | Detail |
|---|---|
| Key | 32 random bytes → **64 hex** chars |
| Store | SHA-256 hex in `~/.config/wanos/power_bridge_api_key.json` (override: `WANOS_POWER_BRIDGE_KEY_FILE`) |
| Generate | Admin → Site info → **Generate** (plaintext shown once) |
| Call | `Authorization: Bearer <api_key>` over **HTTPS** (nginx 301s HTTP→HTTPS; clients should not start on `http://`) |
| Role | `bridge` — **only** `/api/bridge/*` |

Smoke on the Pi (nginx `server_name` is **app.wanos.be**, not localhost):

```bash
curl -sk -H "Authorization: Bearer <key>" https://app.wanos.be/api/bridge/probe
curl -sk -H "Authorization: Bearer <key>" https://app.wanos.be/api/bridge/sensors
# or bypass nginx:
curl -s -H "Authorization: Bearer <key>" http://127.0.0.1:8080/api/bridge/probe
```

Do not use Admin PIN for Power.

## Endpoints

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/bridge/probe` | bridge, admin | Connectivity |
| GET | `/api/bridge/sensors` | bridge, admin | Allowlist + live values + `updated_unix` |
| GET | `/api/bridge/api-key/status` | admin | Hash configured? |
| POST | `/api/bridge/api-key/generate` | admin | New key (plaintext once) |

### `/api/bridge/sensors` row shape

Each allowlisted sensor that is present:

| Field | Meaning |
|---|---|
| `entity_id` | Stable FK for Power mappings |
| `kind` | `water_official` / `water_cold` / `water_hot` / `ambient` |
| `unit` | `m3` / `L` / `C` |
| `name` | WanOS display name |
| `value` | Live numeric (or null) |
| `available` | true when value is non-null |
| `updated_unix` | Last update epoch: waters = `sensor_history` last ingest; ambient = `owm_last_poll_unix` (may be null until first sample) |

## Allowlist (entity_id)

| entity_id | kind | unit |
|---|---|---|
| `sensor.fluid.waterlink.digital_meter` | water_official | m³ |
| `sensor.fluid.koud_water` | water_cold | L |
| `sensor.fluid.warm_water` | water_hot | L |
| `sensor.temp_hum.outside_temp_hum` | ambient | °C (from `sensors.outside_temp`) |

## Code

- `core/bridge_api_key.py`
- `core/bridge_sensors.py`
- `logic/sensor_history_manager.py` (`last_seen_unix`)
- `main.py` (middleware + routes)
- Admin UI: `frontend/admin.html` / `app.js`
