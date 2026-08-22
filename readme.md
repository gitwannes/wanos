# WanOS

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0.svg)](https://alpinejs.dev)
[![MQTT](https://img.shields.io/badge/MQTT-aiomqtt-660066.svg)](https://mqtt.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**Event-driven smart home OS and industrial sauna controller**

WanOS is a concurrent Python backend and reactive web UI that orchestrates a smart home: consumer protocols (Z-Wave, Hue, Sonos, RFXCOM, and more) plus bare-metal GPIO where needed.

It started as a safe controller for a 9 kW three-phase electric sauna and infrared heating system, and grew into a full automation stack with safety interlocks, thermal control, and a live dashboard.

> **Safety notice**  
> WanOS can drive industrial heating (including 3-phase 400 V AC). Always install hardware thermal cutoffs and a manual kill switch in addition to software control. Use at your own risk.

---

## Features

### Event-driven core
- **Async architecture** — `asyncio` and FastAPI with a central event queue (no blocking request path for domain work).
- **Live UI** — Alpine.js clients subscribe over Server-Sent Events (SSE); state updates are pushed, not polled.
- **Declarative rules** — YAML **branch** schema (`If` / `Else-if`; bare `Else` retired) with Blockly authoring; flat **If/Do** or nested **If/Then** via branch `then:` (WanOS extension — Domoticz does not support nested If/Do); conditions (device / event / time / numeric) and actions load into the automation engine.

### Sauna and thermal control
- **Safety gates** — start interlocks, door checks, grace periods, and long-run hardware cutoffs aligned with EN 60335-2-53 practice.
- **PID control** — proportional–integral–derivative control of thermal mass, with phase-waterfall distribution across U / V / W elements.
- **Disaggregation** — line voltage and kWh pulse metering used to infer active element behaviour and degradation.

---

## Integrations

### Active
| Integration | Role |
|---|---|
| **Z-Wave** | Z-Wave JS UI MQTT data plane |
| **Philips Hue** | Local API v2 (HTTP/2 SSE) |
| **Sonos & Onkyo** | TCP control (`soco`, eISCP) |
| **RFXCOM** | 433 MHz via `serial_asyncio` |
| **OpenWeatherMap** | Environment / twilight for scheduling |
| **GPIO** | `lgpio` outputs and interrupt edges |

### Roadmap
- Samsung SmartThings (AC)
- Siemens HomeConnect
- Honeywell Home (central heating)
- SMA (PV inverter)
- HomeWizard (P1 / PV)
- LG webOS TV
- EZVIZ doorbell

---

## Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.9+, FastAPI / Uvicorn, `aiomqtt`, Loguru, SQLite |
| **Frontend** | HTML5, Alpine.js, Tailwind CSS, DaisyUI, Apache ECharts 5 |
| **Host** | Raspberry Pi / Debian Linux |

---

## Repository layout

```text
wanos/
├── core/           # Event routing, state, models, SSE hub
├── frontend/       # Alpine.js UI assets
├── hardware/       # GPIO actuators, sensors, simulator
├── helpers/        # Ops / discovery / sync utilities
├── integrations/   # Protocol bridges (Z-Wave, Hue, Onkyo, …)
├── logic/          # PID, automations, analytics, timers
└── main.py         # FastAPI entrypoint
```

Deeper design notes live under [`docs/`](docs/) (architecture, integrations, sauna/IR).

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

*Copyright (c) 2026 https://github.com/gitwannes. All Rights Reserved.*
