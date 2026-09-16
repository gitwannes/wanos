# --- file: docs/integration_homewizard.md ---
# HomeWizard Energy (G10)

Local API v2 poll bridge for **P1 Meter** and **PV kWh Meter** (`810xx`). Telemetry-only (no socket switching in this ship). Energy Sockets (API v1 today) are deferred. **Pi smoke OK 2026-09-10** — close-out Done.

## Config (`config.yaml` → `homewizard:`)

| Key | Role |
|---|---|
| `poll_secs` | REST poll interval (default **60**) |
| `token_file` | Optional override; default **`~/.config/wanos/homewizard_tokens.json`** |
| `device_map` | idx → `{ host, field, name, type }` — curated fields only (hand-YAML today; UI → **G17**) |

**Types:** `power` \| `energy` \| `fluid` \| `sensor`.  
**Field:** plain measurement key (`power_w`) or `external.<type>` (e.g. `external.gas_meter`).

Tokens are **not** in the repo (survive `wanos-sync --delete`). Scout / pair / dump:

```text
python helpers/homewizard_discovery.py scan
python helpers/homewizard_discovery.py pair --host <ip>
python helpers/homewizard_discovery.py dump --host <ip>
```

## Runtime

- **Transport:** HTTPS Local API v2 via **aiohttp** (Pi Python **3.9**). Do **not** pin `python-homewizard-energy` / `HomeWizardEnergyV2` until runtime ≥ **3.12** (Ops2).
- **Admin:** HomeWizard row — enable/disable; **enabled at boot** when the bridge starts (and on `WANOS_AUTOSTART`). Soft enable: reject only if the bridge object is missing; per-host online/offline logs on status change.
- **Health** (`homewizard_connected`): at least one configured host answers `/api` with a stored token.
- **Ingest:** power → `POWER_UPDATED`; energy / fluid / sensor → `HOMEWIZARD_METRIC` (Event Received = DEBUG). Energy stores **Wh** in `devices[]` (API kWh × 1000).
- **History:** `history.tracked_entities` lists power + energy + gas **and** gauge (`type: sensor`) entity_ids; hi-res **`hires_days` = 7**. Absolute kWh/gas meters accrue deltas; power and gauges use the existing **60 s** sample throttle (`zwave_min_interval_secs`). Gauges (V/A/Hz/PF/VA/VAR) ingest as **`kind: host`** via `note_gauge` on `HOMEWIZARD_METRIC`. Series kind/unit still partly hardcoded in `SENSOR_META` until **P1**.
- **Explorer:** read-only analog rows (`origin: homewizard`). **Power** filter includes HomeWizard (not water fluids). `11001` label = **Sauna kWh meter**.
- **Blockly:** no new blocks.
- **Logs:** `[HomeWizard]` — per-host online/offline status changes at INFO; steady `poll done` summary at DEBUG
- **Reload:** full config reload remaps `device_map` (no G6 scoped row in this ship). `load_config()` must pass `homewizard:` into compiled runtime config.

## IDX map (this site)

| Band | Device | Notes |
|---|---|---|
| `81001`–`81020` | P1 `10.32.251.56` | Import/export kWh + tariffs, phase power, gas, V/A |
| `81030`–`81038` | PV kWh `10.32.251.57` | Power, export/import kWh, V/A/Hz/PF/VA/VAR |

Entity prefixes: `sensor.power.homewizard.<slug>`, `sensor.energy.homewizard.<slug>`, `sensor.fluid.homewizard.<slug>`, `sensor.homewizard.<slug>`.

## Related

- Sauna-circuit pulse meter `11001` stays **Sauna kWh meter** (Admin Total kWh) — not whole-house. Whole-house → P1.
- Map UI / add-device without hand-YAML → **G17**. History series config → **P1**.
- Delivery archive: [`docs/todo/phaseG-integrations.md`](todo/phaseG-integrations.md) § G10.
- Playbook: [`docs/integration-playbook.md`](integration-playbook.md).
- Sensor history: [`docs/sensor_history.md`](sensor_history.md) §3 / §17.
