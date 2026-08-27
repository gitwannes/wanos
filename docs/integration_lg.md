# --- file: docs/integration_lg.md ---
# LG webOS TV (G16)

Local SSAP + Wake-on-LAN bridge for one TV (`switch.lg_tv` / idx **62001**). **Shipped** — Pi smoke **2026-08-27**.

## Config (`config.yaml` → `lg:`)

| Key | Role |
|---|---|
| `host` | TV IPv4 |
| `mac` | WOL MAC (cold ON) |
| `device_map` | idx → `{ name }` (home: **62001** / LG TV) |
| `apps` | catalog key → `{ label, id }` (Blockly picker; fixed list) |
| `wol_wait_secs` | Wait after WOL before ON success (default **8**) |
| `poll_secs` / `poll_fast_secs` / `poll_fast_window_secs` | Adaptive power poll (**10** / **2.5** / **30**) |

Pairing client key: **`~/.config/wanos/lg_webos_client_keys.json`** (not in repo; survives `wanos-sync --delete`). Scout / re-pair: [`helpers/lg_webos_power.py`](../helpers/lg_webos_power.py).

## Runtime

- **Admin:** LG TV row — enable/disable; **enabled at boot** when the bridge starts.
- **Health** (`lg_connected`): bridge process up — **not** the same as TV power.
- **Power** (`62001`): TCP SSAP ports **3000/3001**; adaptive poll; boot probe once.
- **Commands:** C18 listener (`origin: lg`). ON = WOL if needed + ports open; OFF = SSAP `power_off` (idempotent); `app` = catalog key launch. App-only while OFF → fail. No FORCE_* in Blockly.
- **Explorer:** ON/OFF switch only (no app dropdown in v1).
- **Blockly:** ON + optional **app** dropdown from `system.lg_apps`.
- **History:** power may track like other switches; **app launches are not history**.
- **Logs:** `[LG]`
- **Reload:** full config reload refreshes maps; G6 scope id **`lg`** (handler + alerts; modal row when G6 UI lands).

## Dependencies

`pywebostv`, `wakeonlan` (see `requirements.txt`).

Delivery / DoD archive: [`docs/todo/phaseG-integrations.md`](todo/phaseG-integrations.md) § G16.
