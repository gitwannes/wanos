# WanOS

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0.svg)](https://alpinejs.dev)
[![MQTT](https://img.shields.io/badge/MQTT-aiomqtt-660066.svg)](https://mqtt.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**A High-Performance, Event-Driven Smart Home OS & Industrial Sauna Controller**

WanOS is a custom-built, highly concurrent Python backend and reactive frontend designed to orchestrate a complex smart home environment. It bridges consumer smart-home protocols (Z-Wave, Hue, Sonos, RFXCOM, and more) with raw, bare-metal hardware control (GPIO). 

Originally engineered to safely manage a 9kW 3-phase electric sauna and infrared heating system, WanOS has evolved into a full-stack, zero-latency automation engine with deeply integrated safety interlocks, physics simulations, and a modern, reactive UI.

> ⚠️ **Disclaimer & Safety Notice**  
> WanOS interfaces directly with industrial heating elements (3-phase 400V AC). Always ensure hardware-level physical thermal cutoffs and manual kill switches are installed alongside software controls. Use at your own risk.

---

## Key Features

### Reactive, Event-Driven Core
* **Zero-Blocking Architecture:** Built on `asyncio` and `FastAPI`, WanOS uses a centralized asynchronous queue to process events.
* **Real-Time Telemetry:** The Alpine.js frontend subscribes to an SSE (Server-Sent Events) stream, instantly diffing and rendering JSON state payloads without polling. The hub is event-driven (`core/sse_hub.py`); `SseClient` is identity-hashable so the hub `set` can subscribe (**C23**); Control sibling rows follow request-level command commit (**C18**).
* **Declarative Rules:** A powerful YAML-based rule engine that supports complex `AND/OR` triggers, time/environment conditions, and rich payloads (like Hue color presets or Sonos URIs).

### Sauna Control & Thermal Management
* **EN 60335-2-53 Compliance:** Built-in hardware start-gates, physical door interlocks, 30-second grace periods, and absolute 6-hour hardware cutoffs.
* **Dynamic PID Control:** A custom proportional-integral-derivative controller manages thermal mass, distributing asymmetrical wattage via a dynamic phase-waterfall across U, V, and W elements.
* **Software-Defined Disaggregation:** Analyzes live line voltage and high-frequency kWh pulse meters to mathematically extract active element degradation.

---

## Supported Integrations

### Active Integrations
* **Z-Wave:** Hooks directly into the Z-Wave JS UI MQTT data plane.
* **Philips Hue:** Local API v2 integration via HTTP/2 SSE streams for instant switch/bulb telemetry.
* **Sonos & Onkyo:** Direct TCP/IP socket control (`soco` and `eISCP`).
* **RFXCOM (433MHz):** Native `serial_asyncio` protocol mapping, bypassing legacy library locking.
* **OpenWeatherMap:** Continuous background polling for environmental bounding (twilight & blinds scheduling).
* **Hardware GPIO:** Direct memory-mapped `lgpio` output multiplexing and C-threaded interrupt edge detection.

### Planned Integrations (Roadmap)
* [ ] **Samsung SmartThings:** Air conditioner control
* [ ] **Siemens HomeConnect:** Kitchen appliances
* [ ] **Honeywell Home:** Central heating control
* [ ] **SMA:** PV inverter telemetry
* [ ] **HomeWizard:** P1 & PV monitoring
* [ ] **LG:** WebOS TV control
* [ ] **EZVIZ:** Smart doorbell events

---

## Technology Stack

**Backend:**
* Raspbian GNU/Linux 11 (Bullseye)
* Python 3.9+
* FastAPI & Uvicorn (REST & SSE)
* `aiomqtt` (Asynchronous MQTT)
* Loguru (Multi-sink, thread-safe asynchronous logging)
* SQLite (30-day rolling history and NVM caching)

**Frontend:**
* HTML5 / Vanilla JS
* Alpine.js (Reactive State Management)
* Tailwind CSS & DaisyUI (Component Styling)

---

## Architecture Overview

```text
wanos/
├── core/                  # Event routing, State Manager, and Models
├── frontend/              # Alpine.js, Tailwind, and HTML assets
├── hardware/              # Raw GPIO actuators, sensors, and the Simulator
├── helpers/               # Discovery tools, sync, rsyslog logcap (`wanos_rsyslog_logcap.sh`)
├── integrations/          # Dedicated API bridges (Z-Wave, Hue, Onkyo, etc.)
├── logic/                 # The "Brain" (PID, Automations, Analytics, Timers)
└── main.py                # FastAPI Entrypoint & Boot Sequence
```

## License
This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

*Copyright (c) 2026 https://github.com/gitwannes. All Rights Reserved.*