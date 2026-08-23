# WanOS Sensor & Utility History — Architecture Reference

This document is the master specification for how WanOS **collects, stores, retains, and displays** historical data for power meters, water meters, and heating sessions (sauna / IR).

Related documents:
* [sauna-ir.md](sauna-ir.md) — sauna/IR safety, live power analytics, and session schema (session rows live there; long-term utility time-series is defined here).

**Status:** Implemented (ECharts UI on `frontend/sensorhistory.html`).

---

## 1. Goals & Non-Goals

### 1.1 Goals
* Persist and visualize **power** history for:
  * Whole-house kWh pulse meter (IDX `11001`)
  * Z-Wave instantaneous power sensors (IDX `74001`, `74003`)
* Persist and visualize **water** consumption history for:
  * Cold water (IDX `11002`)
  * Hot water (IDX `11003`)
* Provide stacked charts: **day / month / year** (Watt usage for power; consumption bars for water).
* Expose **consumption summaries**: today / this month / this year / **lifetime total**.
* Keep **all** sauna and IR session records forever, including **outdoor temperature at session start**.
* Admin-only UI on a dedicated page: `frontend/sensorhistory.html`.

### 1.2 Non-Goals
* Do not reuse `device_history.db` (switch/door/shutter event counts) for utility time-series.
* Do not treat `/var/log/wanos/wanos_power.log` as the history store.
* Do not invent interpolated wattage across outages (see §7 Gap Policy).
* PHP is not part of this stack; the UI is static HTML served by FastAPI.

---

## 2. Decisions

| # | Topic | Decision |
|---|--------|----------|
| 1 | Outage / missing samples | mark gap periods incomplete; attribute counter delta to the recovery interval; show a gap in charts — do not invent spread values |
| 2 | Timezone / day boundary | **Europe/Brussels**, calendar day closes at **local midnight** |
| 3 | Hi-res sample triggers (pulses) | **Water:** one history sample per **1.0 L** advanced. **kWh:** one history sample per **0.1 kWh** (100 Wh) advanced |
| 4 | Hourly retention | **31 days** |
| 5 | Water charts | Same page; **consumption-only** (liters) — no Watt min/max series |
| 6 | Access control | **Admin only** |
| 7 | Year power chart | **monthly min/max Watts**, rolled up from daily aggregates |

### 2.1 Z-Wave instantaneous power sampling
Pulse meters are event-threshold based (§2 row 3). Z-Wave sensors emit `POWER_UPDATED` at device rate.

**Locked:** enqueue a hi-res Watt sample on each `POWER_UPDATED`, **throttled to at most one sample per 60 seconds per IDX**. Integrated Wh (W×Δt) is accrued into hourly/daily consumption for kWh summary tiles.

### 2.2 Chart library
**Apache ECharts 5** (CDN) on `sensorhistory.html` — day / month / year panels with dataZoom; water uses bar series.

Operator day-to-day charts live on **Device Explorer → History** (`deviceexplorer.html`), not the standalone admin page. Open detail auto-refreshes every **60s** while the tab is visible (**C6** / **C19** ✅ **2026-08-16**): merge `setOption` with `replaceMerge: ['series', 'dataZoom']` (saved zoom copied onto the option); rebind the ECharts instance if Alpine replaced the chart DOM node. Hard open / row switch still full replace. `sensorhistory.html` session list is out of **C19**.

### 2.3 PC power kWh
Z-Wave power IDXs (`74001`, `74003`) include **integrated kWh** in summary tiles (today / month / year). Lifetime total remains N/A (no hardware kWh accumulator ingested).

---

## 3. Tracked assets

| IDX | Name | Kind | History series |
|-----|------|------|----------------|
| `11001` | House kWh pulse | Energy pulse (1 pulse = 1 Wh) | Instant W (from Δt at sample points) + Wh consumption buckets |
| `74001` | PC power | Z-Wave Power (W) | Instant W + daily min/avg/max W |
| `74003` | PC monitors power | Z-Wave Power (W) | Instant W + daily min/avg/max W |
| `11002` | Cold water | Fluid pulse (396 pulses = 1 L) | Liter consumption buckets only |
| `11003` | Hot water | Fluid pulse | Liter consumption buckets only |

**Lifetime totals (not time-series):** cumulative counters in NVRAM (`wanos-nvram.json`) for IDX `11001`–`11003` remain the source of truth for **total** Wh / L.

**Sauna / IR:** session rows in `sauna_sessions.db` (see §6 and [sauna-ir.md](sauna-ir.md) §5), retention **forever**.

---

## 4. Storage tiers

Industry-aligned rollup: high-resolution samples → hourly → daily → derived month/year. Separate SQLite database from switch history.

| Tier | Table (proposed) | Contents | Retention | Primary UI use |
|------|------------------|----------|------------|----------------|
| **Hi-res** | `sensor_samples` | `(idx, ts, value, unit)` — W for power; L step markers optional for water | **7 days**, then cull | Day chart buffer: full **`hires_days`** hi-res; **24 h viewport** pannable (**C16 ✅**). |
| **Hourly** | `sensor_hourly` | Per IDX/hour: `w_min`, `w_max`, `w_avg`, `wh` or `liters`, `incomplete` flag | **31 days**, then cull | Drill-down; backup if hi-res thin |
| **Daily** | `sensor_daily` | Per IDX/local-date: min/max/avg W (power); `wh` or `liters` consumed; counter snapshots; `incomplete` | **1 year**, then cull | Month chart (min/max W); consumption bars |
| **Month / year / total** | *(derived)* | Month/year = aggregate of daily; total = NVRAM counter (cross-check vs sum of daily when complete) | N/A | Year chart; summary tiles |
| **Sessions** | `sauna_sessions` / `ir_sessions` | Existing session aggregates + `temp_outside_start` | **Forever** | Session list / insights |

**Database file:** `sensor_history.db` (WAL mode, batched writes — same SD-friendly pattern as `DeviceHistoryManager`).

**Do not store separate monthly/yearly raw tables** at this scale; roll up in queries (or optional materialized views later).

---

## 5. Ingest rules

### 5.1 House kWh (`11001`)
* Hardware continues to count every pulse into NVRAM / `devices[11001]` (1 Wh per pulse).
* **History hi-res:** when cumulative Wh advanced since last history sample ≥ **100 Wh (0.1 kWh)**:
  * Compute instantaneous watts from pulse timing (same `3600/Δt` family as live analytics, using the interval covering that 0.1 kWh window or last known rate — implementation detail).
  * Insert `sensor_samples` row `(11001, ts, watts, 'W')`.
  * Accrue Wh into the current hour and current local day buckets.
* Live PowerAnalytics (leak / element disaggregation) remains independent and may still process every pulse in RAM; this document only defines **persisted** history cadence.

### 5.2 Water (`11002`, `11003`)
* Counters continue per pulse → liters in NVRAM.
* **History:** when cumulative liters advanced since last history sample ≥ **1.0 L**, record consumption into current hour/day buckets (`liters`). No Watt series.

### 5.3 Z-Wave power (`74001`, `74003`)
* On throttled `POWER_UPDATED`: insert hi-res Watt sample; update running hour/day min/max/avg.
* No Z-Wave kWh accumulators (CC50 paths remain suppressed in `integrations/zwave.py`). Daily Wh for these IDXs is **not** a billing meter unless later derived from integrating W×Δt (optional; default charts are Watt usage, not kWh bills).

### 5.4 Midnight close (Europe/Brussels)
* Close previous local day: finalize `sensor_daily` from counter deltas (11001/11002/11003) and Watt stats from samples.
* Open new day buckets; run retention culls (7d / 31d / 1y).

### 5.5 Sauna / IR session start
* When a sauna or IR session starts, snapshot `state.sensors.outside_temp` into the session record as `temp_outside_start` (nullable if OWM/outside sensor unavailable).
* On terminate: existing commit path to `sauna_sessions.db` unchanged aside from the new column.

---

## 6. Session history extensions

Existing schemas in [sauna-ir.md](sauna-ir.md) §5 gain:

```sql
-- Added to both sauna_sessions and ir_sessions
temp_outside_start REAL  -- °C at session start; NULL if unknown
```

* **Retention:** all sessions kept forever (no cull).
* **UI:** paginated/filterable list on `sensorhistory.html` (energy, runtime, temps, humidity, outdoor start temp).
* Live admin “last session” cards may remain; full history lives on the new page.

---

## 7. Gap policy (outages)

When WanOS was offline (or samples missing) but counters advanced:

1. Do **not** synthesize intermediate hi-res Watt points.
2. Mark affected hourly/daily rows with `incomplete = 1` (or equivalent).
3. Attribute the full counter **delta** to the first closed interval after recovery (typically the recovery day / hour).
4. Charts should render a **visible gap** (null break) across missing hi-res time ranges rather than a flat or interpolated line.

---

## 8. UI specification

### 8.1 Page
* **File:** `frontend/sensorhistory.html`
* **Access:** admin JWT only; redirect non-admins.
* **Nav:** link from existing shell pages (Commander, Admin, Explorer, etc.).

### 8.2 Layout (power sensors)
Device selector, then three stacked panels:

1. **Day — 24 hour window (pannable over hi-res retention)**  
   **C16 ✅:** API returns all hi-res samples within **`history.retention.hires_days`** (default 7), plus optional `retention_days` / `default_window_hours`. Chart **defaults** to the most recent **24 h**; user may **zoom out** to the full retention window or **pan** across the buffer. Soft refresh preserves pan or live-pins to now. Applies to climate / power / host hi-res and actuator `device_events` day charts. **Water day:** hourly bars over **`hires_days`** with the same 24 h pan UX.

2. **Month — “Usage last month”**  
   Series: **Usage min** and **Usage max** (Watt) per day from `sensor_daily`.

3. **Year — “Usage last year”**  
   Series: **Usage min** and **Usage max** (Watt) per month, rolled up from daily (min of mins, max of maxes).

### 8.3 Water
* Same page / selector.
* Charts: **liters consumed** per day / month / year (bar or step), not Watt min/max.
* Summary tiles: today / month / year / **total** (NVRAM).

### 8.4 Consumption summary tiles (meters)
For `11001` / `11002` / `11003`:
* Today, this month, this year (from daily aggregates)
* Total (NVRAM lifetime counter)

### 8.5 Sauna / IR section
* Table of historical sessions (all retained rows), including `temp_outside_start`.

---

## 9. API (proposed)

All routes require admin authentication.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/history/sensors` | List trackable IDXs, labels, series kinds |
| `GET` | `/api/history/{idx}?range=day\|month\|year` | Chart series for selected range. **`range=day` (C16 ✅):** full **`hires_days`** buffer (FE applies 24 h viewport). Day responses may include `retention_days` / `default_window_hours` / `climate_max_interval_secs` / **`climate_sample_interval_secs`** (FE gap-break = **3 × sample interval** — break only when more than 2 samples are missing; OWM = poll interval, else history max-interval). |
| `GET` | `/api/history/{idx}/summary` | today / month / year / total |
| `GET` | `/api/history/sessions?type=sauna\|ir&limit=&offset=` | Paginated session history |

Static HTML under `/sensorhistory.html` is served like other frontend pages.

---

## 10. Configuration

Preferred home: `config.yaml` (optional subsection), e.g.:

* `history.timezone`: `Europe/Brussels`
* `history.retention.hires_days`: `7`
* `history.retention.hourly_days`: `31`
* `history.retention.daily_days`: `365`
* `history.sample.kwh_step_wh`: `100` (0.1 kWh)
* `history.sample.water_step_l`: `1.0`
* `history.sample.zwave_min_interval_secs`: `60`
* `history.tracked_entities`: entity_ids for utility history ingest, e.g. `[sensor.energy.kwh_meter, sensor.fluid.koud_water, …]` (resolved to idx at runtime)

---

## 11. Implementation file impact

### 11.1 New
| File | Role |
|------|------|
| `logic/sensor_history_manager.py` | Ingest, rollup, cull, SQLite, queries |
| `frontend/sensorhistory.html` | Charts, summaries, session list |
| `sensor_history.db` | Runtime DB (created on disk) |

### 11.2 Modify
| File | Role |
|------|------|
| `main.py` | History API routes |
| `core/state_manager.py` | Lifecycle for `SensorHistoryManager` |
| `core/event_handlers/telemetry_handlers.py` | Pulse / power hooks → history ingest |
| `logic/power_analytics.py` | `temp_outside_start` at session start; session schema migrate |
| `core/models.py` | Session record fields |
| `config.yaml` | History settings |
| `frontend/app.js` | Admin guard for new page; fetch helpers |
| Nav shells (`admin.html`, `commander.html`, `deviceexplorer.html`, `zwaveconfig.html`, …) | Link to Sensor History |

### 11.3 Unchanged (by design)
| File | Reason |
|------|--------|
| `logic/history_manager.py` | Switch-event insights only |
| `integrations/zwave.py` | Continues emitting `POWER_UPDATED`; history listens downstream |
| `core/nvm_manager.py` | Lifetime totals already persisted |

---

## 12. Relationship to live Power Analytics

| Concern | Live (`power_analytics.py`) | History (`sensor_history`) |
|---------|----------------------------|----------------------------|
| Every pulse W for leak/elements | Yes (RAM) | No — persist every **0.1 kWh** |
| Background leak baseline | RAM / admin live UI | Not historized as a first-class series |
| Sauna/IR session energy | Written to `sauna_sessions.db` | Listed on Sensor History UI |
| House daily kWh | Not previously stored | `sensor_daily` |

Session energy accounting and house utility history are complementary, not duplicates.

---

## 13. Implementation notes (utilities)

* Chart library: **Apache ECharts 5** (CDN on `sensorhistory.html`).
* Z-Wave hi-res throttle: **60 s** per IDX.
* PC power IDXs include integrated **kWh** summary tiles; lifetime total N/A.
* Host needs `tzdata` for `zoneinfo` (`Europe/Brussels`).

---

## 14. Actuator history (switches, shutters, doors, audio, lights)

Master–detail UI on `sensorhistory.html` → **Actuators** tab.

### Mapping to chart level
| Device | Rule |
|--------|------|
| Switch / light | OFF→0; ON→**brightness** when present else **100** |
| Speaker (Sonos / Onkyo) | OFF→0; ON→**volume**; chart / clamp ceiling = device meta **`max_volume`** (`config.sonos.max_volume` / `config.onkyo.max_volume`) — not a forced 0–100 scale |
| Shutters | native 0=OPEN … 100=CLOSED |
| Door | OPEN→0; CLOSED→100 |

Every state/level change counts toward today / month averages.  
**Avg/day** = calendar-month event total ÷ **days in month**.

### Retention (same tiers as utilities)
| Tier | Retention |
|------|-----------|
| Raw `device_events` (+ `level`) | 7 days |
| `device_hourly` | 31 days |
| `device_daily` | 1 year |

### UI (Explorer → History on `deviceexplorer.html`)
- List: Control inventory shared with History mode; **C10:** omit all `type === "scene"` catalog-event rows (logging still writes synthetic idxs; Control dashboard buttons unchanged).
- Detail charts for **selected** actuator:
  - **Day (C16 ✅):** same families as today; hi-res buffer = **`hires_days`**; **24 h max viewport**, pannable, zoom-in only; from/to subtitle when not live
  - **Binary** (switch / non-Hue light / door / …): day ON/OFF Y; month/year **duration ON** (**C12** ✅) — integer **minutes** / **hours** (1 decimal); clip; carry-in; open→now; Y snap ±10 min / ±1 h with ~5 tick labels
  - **Hue** + **Audio** (Sonos / Onkyo): day Level; month/year **duration ON** only (no Events, no Level min/max); same Y snap — **C12** ✅
  - **Level** (blinds): day Level step; month/year event counts + Level min/max
  - **Motion hits:** day impulse spikes with blank/`hit` Y labels; month/year **# hits** only (not duration)
- Climate legend/tooltip colors pinned to series line colors (**C10**)
- **C12 climate ✅:** day temp frost (temp &lt; dew → red, thicker); **no dew** on month/year (RH stays)

### API
- `GET /api/history/actuators`
- `GET /api/history/actuators/{idx}?range=day|month|year`

---

## 15. Climate history (temp / humidity)

All `temp_hum` / `temp` sensors plus virtual **`20101` sauna temp** (0.7×20001 + 0.3×20002; hum from 20001).

### Sampling
| Rule | Default |
|------|---------|
| Temp deadband | 0.5 °C |
| Humidity deadband | 2 %RH |
| Max interval | 300 s |

Stored in `sensor_samples` (`unit` = `C` / `%`) with `climate_hourly` / `climate_daily` rollups. Ingest runs on every successful poll/read; `note_climate_*` applies deadband + max-interval. When T/RH is unchanged, SHT11 and OWM still call history on each poll so **max-interval heartbeats** continue (stable rooms stay on the day chart; state/automation events remain change-only).
Outside (`weather.idx` / OWM) polls on `weather.poll_interval_mins` (**10** after **G3**; cold boot). Day API sets **`climate_sample_interval_secs`** to that poll period for OWM (else `climate_max_interval_secs`) so FE gap-break matches source cadence.

### Charts (ECharts, Sensors list)
| Range | Series |
|-------|--------|
| Day | Temp (°C) + humidity (%) + dew (day only, **C12**); smooth lines (**C5**). **C16 ✅:** load **`hires_days`** hi-res; default 24 h viewport, zoom-out to full retention; from/to subtitle when not live. **Gap break ✅:** day climate lines (inline + fullscreen) break when Δt &gt; **3 × `climate_sample_interval_secs`** (more than **2** missed samples: SHT11 default **15 min**; **OWM outside** default **30 min**) so empty time is not drawn as a value. **C19 ✅:** 60s auto-refresh must not blank the plot. **C24 ✅:** temp/hum day **tab overlay** — AH + **Feels-like humidity**, 5 checkboxes (+units), 3rd y-axis g/m³, frost on overlay temp, **CSV** of full `hires_days`; inherits inline pan; mobile compact chrome. **C25 (queued):** overlay **Dew likelihood %** + compare another temp(/hum). Month/year unchanged. |
| Month | Daily **min/max** temp (+ hum when present); **no dew** (**C12**). |
| Year | **Weekly** min/max (ISO week); **no dew** (**C12**). |

Temp-only devices: humidity series hidden.

### Day overlay (C24 ✅) — Absolute humidity + Feels-like humidity

Button **Open detail in full screen** (temp/hum **day** only) opens a **tab overlay** (not F11). Inline day chart stays T + RH + dew (+ frost). Overlay-only: five checkboxes with units; inherit inline pan/zoom; CSV = full `hires_days` buffer; soft refresh keeps checkboxes + window.

| Series | Axis | Notes |
|--------|------|--------|
| Temperature (°C) | left °C | Frost styling when temp &lt; dew (**C12**) |
| Humidity (%) | right % | |
| Dew point (°C) | left °C | FE Sonntag Magnus from paired T+RH (same as C5); never stored |
| Absolute humidity (g/m³) | 3rd axis g/m³ | From T + Td; omit when Td missing |
| Feels-like humidity (%) | right % | Comfort index from T + Td (below); tooltip band + integer % |

**Absolute humidity (g/m³)** — from dew point `Td` and air temp `T` (shipped FE constants):

```
e = 6.112 * exp((17.67 * Td) / (Td + 243.5))
AH = (216.7 * e) / (T + 273.15)
```

**Feels-like humidity (%)** (comfort index / CI):

```
CI_base = clamp(4.5 * Td - 30, 0, 100)
CI = clamp(CI_base + 0.8 * (T - 20), 0, 100)
```

Band labels (by Td °C): &lt;10 Dry · 10–15 Comfortable · 15–18 Moderately humid · 18–21 Humid · 21–24 Very humid · &gt;24 Tropically humid. One CI line width; piecewise color by band.

Omit Td / AH / Feels-like when T+RH are unpaired or invalid (same pairing rules as dew). Month/year: no overlay.

### Device Explorer
IDX **20101** registered as `sauna temp` (`type: temp_hum`, origin `system`).

---

## 16. Motion & event history

| Source | Behaviour |
|--------|-----------|
| Motion `75xxx` | Rising edge only (`ON`); day chart = impulse spike with **hit** Y labels (**C10**); month/year = **# hits**; insights = today / avg/day |
| Dashboard / user events (`events:` catalog) | Log on every fire (manual + automation). Synthetic series keyed by **event UUID** (`900000 + (crc32(uuid) & 0xFFFF)`). Pre-B10B used `scene: true` / `SCENE_*` name strings; migrator remapped idxs at cutover (script since removed). **C10:** Explorer History **list** omits all `type === "scene"` rows (UE + SE); Control `dashboard_events` unchanged. List membership model → **C11**. |

Same retention as actuators. Motion `75xxx` stays **soft-hidden** by default (Z-Wave maps idxs 75000–75999 into `hidden_explorer_idxs` / `deviceexplorer_hide`); not in Explorer Control or History list unless the operator enables **Hidden devices** (admin). Backend hit logging unchanged (**C12** item 3 — docs only, no list UX change).

---

## 17. Host gauges & mains voltage

| IDX | Label | Unit |
|-----|-------|------|
| 22001 | Host CPU Temperature | °C |
| 22002 | Host CPU Usage | % |
| 22003 | Host Memory Free | % |
| 22004 | Host Disk Free | % |
| 22005 | Host Log2Ram Free | % |
| 22006 | Host Load Average (1m) | % (of 4 cores) |
| 22009 | WanOS DB size | MB (MiB) |
| 71046 | Mains voltage | V |

`22009` = sum of `sensor_history.db` + `device_history.db` + `sauna_sessions.db` including `-wal`/`-shm` sidecars.

**Not recorded (live only):** `22007` / `22008` Host Load Average (5m / 15m) — omitted from `HOST_HISTORY_IDXS` (**C22** ✅).

Ingested from `HUB_STATE_CHANGED` (health_monitor ~60s; Z-Wave voltage). Charts: day line + month/year min/max (same shape as power). Visibility follows `deviceexplorer_hide` / Hidden toggle (same as Device Explorer; hide list lives in `automations.auto.yaml`).
