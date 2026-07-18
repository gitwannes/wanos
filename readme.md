# WanOS

**A High-Performance, Event-Driven Smart Home OS & Industrial Sauna Controller**

WanOS is a custom-built, highly concurrent Python backend and reactive frontend designed to orchestrate a complex smart home environment. It bridges the gap between standard consumer smart home hubs (like Domoticz or Home Assistant) and raw, bare-metal hardware control (GPIO). 

Originally engineered to safely manage a 9kW 3-phase electric sauna and infrared heating system, WanOS has evolved into a full-stack, zero-latency automation engine with deeply integrated safety interlocks, physics simulations, and a modern, reactive UI.

---

## Key Features

### Reactive, Event-Driven Core
* Built on `asyncio` and `FastAPI`, WanOS uses a centralized asynchronous queue to process events with zero-blocking operations.
* The Alpine.js frontend subscribes to an SSE stream, instantly diffing and rendering JSON state payloads without polling.
* A powerful YAML-based rule engine that supports complex `AND/OR` triggers, time/environment conditions, and rich payloads (like Hue color presets or Sonos URIs).

### Sauna Control
* **EN 60335-2-53 Compliance:** Built-in hardware start-gates, physical door interlocks, 30-second grace periods, and absolute 6-hour hardware cutoffs.
* **Dynamic PID Control:** A custom proportional-integral-derivative controller perfectly manages thermal mass, distributing asymmetrical wattage via a dynamic phase-waterfall across U, V, and W elements.
* **Software-Defined Disaggregation:** Analyzes live line voltage and high-frequency kWh pulse meters to mathematically extract active element degradation.

---

## Supported Integrations

WanOS uses generic plugins to implement optimized wrappers:

* **Z-Wave:** Hooks directly into the Z-Wave JS UI MQTT data plane.
* **Philips Hue:** Local API v2 integration via HTTP/2 SSE streams for instant switch/bulb telemetry.
* **Sonos & Onkyo:** Direct TCP/IP socket control (`soco` and `eISCP`).
* **RFXCOM (433MHz):** Native `serial_asyncio` protocol mapping, bypassing legacy library locking.
* **OpenWeatherMap:** Continuous background polling for environmental bounding (twilight & blinds scheduling).
* **Hardware GPIO:** Direct memory-mapped `lgpio` output multiplexing and C-threaded interrupt edge detection.
<future>
* ** Samsung SmartThings:** airco control
* ** Siemens HomeConnect:** kitchen appliances
* ** Honeywell Home:** central heating control
* ** SMA:** PV inverter
* ** HomeWizard:** P1 & PV
* ** LG:** TV
* ** EZVIZ:** doorbell

---

## Technology Stack

**Backend:**
* Raspbian GNU/Linux 11 (bullseye)
* Python 3.9
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
├── helpers/               # Discovery tools (Hue, Sonos) and sync scripts
├── integrations/          # Dedicated API bridges (Z-Wave, Hue, Onkyo, etc.)
├── logic/                 # The "Brain" (PID, Automations, Analytics, Timers)
├── main.py                # FastApi Entrypoint & Boot Sequence