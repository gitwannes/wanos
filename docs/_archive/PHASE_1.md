================================================================================
WANOS ARCHITECTURE 101: HOW PHASE 1 WORKS
================================================================================

Welcome to modern Python backend development. What we just built is a robust, 
event-driven architecture. To understand it, we need to break it down into four 
core concepts: The Engine, The Bouncer, The Vault, and The Megaphone.

--------------------------------------------------------------------------------
1. THE ENGINE: FastAPI & Uvicorn (main.py)
--------------------------------------------------------------------------------
If you write a standard Python script and run it (`python script.py`), Python 
reads it from top to bottom and then immediately shuts down. 

For a backend controlling a sauna, the code needs to run forever, constantly 
listening for API requests, temperature changes, or UI clicks.

* Uvicorn: This is your web server. When you run `uvicorn main:app`, Uvicorn 
  starts an infinite loop. It keeps Python alive and actively listens to the 
  network (port 8000) for incoming traffic.
* FastAPI: This is the framework inside Uvicorn. It takes incoming web requests 
  (like when you click "Try it out" in the Swagger UI) and routes them to the 
  correct Python function (e.g., `inject_dummy_temp`).

--------------------------------------------------------------------------------
2. THE BOUNCER: Pydantic (core/models.py & core/config.py)
--------------------------------------------------------------------------------
Python is a "dynamically typed" language. This means you can create a variable 
`temp = 85`, and two lines later do `temp = "eighty"`, and Python won't stop you. 
When dealing with physical hardware that can catch fire, this flexibility is 
extremely dangerous. A typo could cause the system to crash mid-sauna.

Pydantic is a data validation library that acts as a strict bouncer for your data.

* How it works: You create a class (like `SaunaConfig` or `SystemState`) and explicitly 
  declare the types: `sauna_temp: float`. 
* The Magic: Whenever data tries to enter your system (whether from the `config.yaml` 
  file, or an HTTP request from the frontend), Pydantic intercepts it. If it expects 
  an integer but gets a string, it instantly throws a loud error and rejects it.
* Why we use it: By defining our State and Events with Pydantic in `models.py`, 
  we guarantee that our system will *never* process corrupted or misformatted data. 
  Your IDE (like VSCode) also reads these Pydantic models to give you perfect autocomplete.

--------------------------------------------------------------------------------
3. THE VAULT: The State Manager & asyncio.Queue (core/state_manager.py)
--------------------------------------------------------------------------------
In the legacy Kivy architecture, the state was just a massive dictionary (`wp`). 
The timer loop, the physical GPIO pins, the MQTT client, and the UI were all 
reading and changing that dictionary at the exact same time. This causes "race 
conditions"—where two parts of the code overwrite each other, causing silent, 
impossible-to-track bugs.

Our new `StateManager` fixes this completely.

* The Private State: Notice that `self._state` has an underscore. In Python, this 
  means "Do not touch this from the outside." No file is allowed to change the state directly.
* The Queue: Instead of letting everyone touch the state, we created a single-file 
  line (`asyncio.Queue`).
* How it works: If a physical button is pressed, the hardware file isn't allowed 
  to change the state. It must write an `Event` on a slip of paper and hand it to 
  the Queue (using `dispatch()`). 
* The Consumer: The `_process_events` loop is the only guy with the key to the Vault. 
  He takes one event from the Queue at a time, reads it, updates the private `_state`, 
  and then moves to the next event. Because he only handles ONE thing at a time, 
  race conditions are mathematically impossible.

--------------------------------------------------------------------------------
4. THE MEGAPHONE: aiomqtt (core/mqtt_client.py)
--------------------------------------------------------------------------------
Once the State Manager processes an event and updates the state (for example, 
`sauna_temp` changes from 20 to 85), the frontend Pi needs to know about it.

* We use `aiomqtt` because it is specifically designed to work alongside FastAPI's 
  asynchronous engine without blocking it.
* Every time the State Manager finishes updating the vault, it tells the MQTT 
  Client to take a JSON snapshot of the state and blast it out to the Mosquitto 
  broker on the `wisc/system/state` topic.

--------------------------------------------------------------------------------
5. PUTTING IT ALL TOGETHER: The Flow of Data
--------------------------------------------------------------------------------
Let's trace exactly what happened when you booted the Pi and saw those successful logs:

(wisc_backend_venv) wannes@raspitst4:~/wisc_backend $ uvicorn main:app --host 0.0.0.0 --port 8000 --reload
INFO:     Will watch for changes in these directories: ['/home/wannes/wisc_backend']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [x] using WatchFiles
INFO:     Started server process [x]
INFO:     Waiting for application startup.
✅ MQTT Connected to localhost:1883
✅ State Manager worker started.

1. You typed `uvicorn main:app --reload`.
2. `main.py` wakes up. The first thing it does is call `load_config()`.
3. `core/config.py` opens `config.yaml`, reads the text, and passes it through the 
   Pydantic bouncer. It succeeds, returning a strictly typed `AppConfig` object.
4. `main.py` uses that config to start the MQTT Client and State Manager.
5. `main.py` drops a piece of paper into the Queue: `Event(type="INITIAL_STATE_LOADED")`.
6. Inside `state_manager.py`, the `_process_events` loop wakes up, grabs that paper, 
   sets `hardware_live_mode` to `False`, and asks Pydantic for a JSON snapshot.
7. The State Manager hands the snapshot to `mqtt_client.py`, which publishes it.
8. The system goes to sleep, waiting for the next event!

--------------------------------------------------------------------------------
6. WANOS CRASH COURSE: CODING STYLE & TWEAKING
--------------------------------------------------------------------------------
Transitioning from a classic synchronous loop to an asynchronous, event-driven 
architecture requires a shift in mindset. Here is how to live, breathe, and tweak 
the Wanos codebase.

6.1 Adding Variables (The Russian Doll Strategy & Dot Notation)
In legacy code, state was a flat dictionary (`wp['door_open'] = True`). In Wanos, 
we use strictly typed nested models to prevent the state from becoming a junk drawer.

* Define it first: To track a new variable, you must declare it in `core/models.py`. 
  Instead of a flat list, nest it logically. E.g., add `door_open: bool = False` 
  inside a `HardwareState` model, which sits inside `SystemState`.
* Dot Notation: Access and update it cleanly via dots, not brackets.
  GOOD: `self._state.hardware.door_open = True`
  BAD:  `self._state['door_open'] = True`
* Configuration variables work exactly the same way in `core/config.py`.

6.2 How the System Polls (The Async Golden Rule)
NEVER use `time.sleep()`. Because Wanos runs on a single async event loop, 
`time.sleep(5)` will freeze the entire backend, dropping API requests and MQTT messages.

* The Wanos Way: Use `await asyncio.sleep(5)`. This tells Python: "Pause this 
  specific background task for 5 seconds, but run the rest of the app in the meantime."
* Polling loops (like reading sensors) should run indefinitely in background tasks, 
  read hardware, dispatch an Event, and then `await asyncio.sleep()` before looping.

6.3 Tweaking Logic (The Router)
In Wanos, logic doesn't live where the data is collected. If a sensor reads a 
temperature, it just dispatches an Event to say "Hey, temp changed!" and its job is done.

All decision-making and tweaking happens inside `core/state_manager.py` in the 
`_handle_event` function. If you want the system to kill the heater when a door 
opens, you intercept the `DOOR_CHANGED` event right there in the State Manager and 
apply your business rules safely.

6.4 Derived vs. Cached State (LCDs & Domoticz)
* Derived State (LCD): Don't store `lcd_line_1 = "Sauna: 85°C"` in the state vault. 
  The vault only holds raw facts (`sauna_temp = 85`). Background display workers 
  read those facts and format the text for the physical screen dynamically.
* Cached State (Domoticz): Wanos acts as a proxy. It listens to Domoticz, updates 
  its own local cache (`self._state.lighting.bathroom_light_on`), and broadcasts 
  that to the Vue frontend. The UI only ever talks to Wanos.

6.5 Summary of the Wanos Mindset
1. Think in Events: Don't call functions directly to change things. Create an 
   Event and `dispatch()` it.
2. Respect the Bouncer: Always tell Pydantic about new variables first.
3. Never Block the Loop: `await asyncio.sleep()` is mandatory for delays.
4. The State Manager is God: Only the State Manager is allowed to mutate 
   `self._state`. Every other file is just an observer or a messenger.


================================================================================
WANOS PHASE 1: BACKEND CORE SKELETON
================================================================================

1. OVERVIEW
-----------
Phase 1 establishes the fundamental architecture of the new WISC backend. The goal 
is to prove that the asynchronous event loop, state protection, configuration 
parsing, and MQTT broadcasting all work together flawlessly. 

In this phase, there is no physical hardware (GPIO/LCDs) and no business logic 
(PID math/timers). It is purely a software skeleton that ingests dummy events, 
updates a state safely, and broadcasts that state.

2. FILE DIRECTORY & RESPONSIBILITIES
------------------------------------
Below are the files required for Phase 1 and what each one does:

* `requirements.txt`
  Pins the exact versions of external Python libraries (FastAPI, Uvicorn, 
  Pydantic, python-dotenv, aiomqtt, PyYAML) to guarantee the environment is reproducible.

* `.env` (Ignored by Git)
  Stores critical secrets like MQTT passwords and Auth PINs securely, separate from codebase.

* `config.yaml`
  The single source of truth for structural system configurations (ports, setpoints).

* `main.py`
  The ASGI entry point for the application. Run via `uvicorn main:app --reload`.
  Responsibilities:
  - Bootstraps the application (loads config, starts MQTT, starts State Manager).
  - Handles graceful startup and shutdown lifecycles.
  - Exposes REST API endpoints (e.g., `/api/state`) for HTTP testing utilizing request body models.

* `core/config.py`
  Combines `.env` secrets with `config.yaml` using Pydantic models. Ensures that if a 
  setting is supposed to be an integer, it actually is one, crashing safely on boot 
  if formatted incorrectly. Uses `__file__` anchoring to ensure paths work globally.

* `core/models.py`
  Uses Pydantic to strictly define the shape of internal data. Contains an `EventType` Enum 
  to prevent typos from entering the queue silently.

* `core/mqtt_client.py`
  An asynchronous wrapper around the `aiomqtt` library. Includes protections against 
  silent failures if the connection drops.

* `core/state_manager.py`
  The most critical file in Phase 1. It acts as the vault for the system state.
  - Holds the private `_state` variable.
  - Runs an internal `asyncio.Queue` event loop.
  - Provides a thread-safe `dispatch()` method utilizing `call_soon_threadsafe()`.
  - Employs deep copying (`model_copy(deep=True)`) to ensure the state cannot be modified externally.


3. HOW PHASE 1 WORKS (THE EVENT FLOW)
-------------------------------------
** running the app
source /home/wannes/wisc_backend/wisc_backend_venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

When you run Uvicorn, `main.py` reads `config.yaml` and `.env`, instantiates the MQTT Client 
and State Manager, and starts their background tasks. It fires a dummy 
"INITIAL_STATE_LOADED" event to prime the system.

Step B: Event Injection
View the state: http://10.32.251.28:8000/api/state
Fire a dummy hardware event: Open the Swagger UI at http://10.32.251.28:8000/docs, POST to /api/test/temp with JSON body {"temp": 85.5}.
Observe: Look at the FastAPI terminal. You will see the event enter the queue, mutate the state safely, and broadcast to MQTT.
You send an HTTP POST request to `http://0.0.0.0:8000/api/test/temp` with a JSON body 
containing `{"temp": 85.5}`. `main.py` packages this into an `Event` object and calls 
`state_manager.dispatch(event)`. The event crosses thread boundaries safely and is dropped into the Queue.

Step C: Sequential Processing
Inside `state_manager.py`, the background `_process_events` loop wakes up, pulls 
the event from the Queue, and routes it to `_handle_event`. 

Step D: State Mutation & Broadcast
The State Manager matches the strict `EventType.TEMP_UPDATED`, extracts the payload, 
and updates its private `_state.sauna_temp` variable. Because the state was 
mutated, the State Manager takes a deep copy snapshot, converts it to JSON, 
and tells `mqtt_client.py` to publish it to the MQTT broker.