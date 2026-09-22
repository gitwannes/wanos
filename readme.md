# WanOS

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0.svg)](https://alpinejs.dev)
[![MQTT](https://img.shields.io/badge/MQTT-aiomqtt-660066.svg)](https://mqtt.org)
[![License: Source Available](https://img.shields.io/badge/License-Source%20Available-lightgrey.svg)](LICENSE)

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
- **PID control** — v1 heat-up is P-only (`kp=12`, `ki=kd=0`) with a −1 °C autohold setpoint bias so MOD reaches 0 just below target; phase-waterfall across U / V / W. See [`docs/sauna-ir.md`](docs/sauna-ir.md) § 3.8.
- **Disaggregation** — line voltage and kWh pulse metering used to infer active element behaviour and degradation.
- **Remote LCD status** — dual 16×2 I2C screens on a dedicated Pi (`_lcd-agent/`), driven over MQTT (`wanos/lcd/screen1|2`); see [`docs/sauna-ir.md`](docs/sauna-ir.md) § 3.7.
- **Remote LCDs** — WISC-compatible 16×2 screens on a dedicated Pi (`wanos/lcd/screen1|2`); WISC mirrors screen1. See [`docs/sauna-ir.md`](docs/sauna-ir.md) § 3.7.

---

## Integrations

### Active
| Integration | Role |
|---|---|
| **Z-Wave** | Z-Wave JS UI MQTT data plane |
| **Philips Hue** | Local API v2 (HTTP/2 SSE) |
| **Sonos & Onkyo** | TCP control (`soco`, eISCP) |
| **LG webOS TV** | WOL + SSAP (`pywebostv`); power + OFF latch (**G20**) + Blockly app catalog |
| **HomeWizard Energy** | Local API v2 (aiohttp) — P1 + PV kWh (`810xx`); sockets deferred |
| **RFXCOM** | 433 MHz via `serial_asyncio` |
| **OpenWeatherMap** | Environment / twilight for scheduling |
| **GPIO** | `lgpio` outputs and interrupt edges |

### Roadmap
- Samsung SmartThings (AC)
- Siemens HomeConnect
- Honeywell Home (central heating)
- SMA (PV inverter)
- HomeWizard Energy Sockets (API v1 on site today)
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
├── _lcd-agent/     # LCD Pi agent tree (sync with wanos-sync lcd)
├── core/           # Event routing, state, models, SSE hub
├── frontend/       # Alpine.js UI assets
├── hardware/       # GPIO actuators, sensors, simulator
├── helpers/        # Ops / discovery / sync utilities
├── integrations/   # Protocol bridges (Z-Wave, Hue, Onkyo, …)
├── logic/          # PID, automations, analytics, timers, LCD composer
└── main.py         # FastAPI entrypoint
```

Deeper design notes live under [`docs/`](docs/) (architecture, integrations, sauna/IR).

---

## Related repositories

| Repo | Role |
|---|---|
| [**wanos-pcb**](https://github.com/gitwannes/wanos-pcb) | KiCad design and JLCPCB fabrication for the WanOS Raspberry Pi carrier board (GPIO break-out, pulse inputs, SHT11 headers, sauna/IR SSR drives). Pipeline and phase specs live **only** in that repo; this repo owns runtime pin mapping in `config_hardware.yaml`. |

---

## License

Source available — personal use OK, no redistribution. See [LICENSE](LICENSE).

Copyright (c) 2026 [Johan Wannes Hofmans](https://github.com/gitwannes). All rights reserved.
