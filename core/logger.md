# Understanding WanOS Logging & Alert Architecture: A Learning Guide

When building a smart home operating system like WanOS, the system must communicate information to different audiences through entirely different channels:
1. **The Web UI User:** Needs to see instant, critical toast alerts on their dashboard (e.g., "Broker Offline").
2. **The Network Admin:** Needs to monitor a live stream of backend events across the network via an MQTT client.
3. **The Developer & Homeowner:** Need permanent, quiet records on the hard drive for debugging and auditing without slowing down the live system.

To solve this, WanOS uses a strictly separated **Multi-Channel Telemetry Architecture**. This guide explains these systems, why they are separate, and how to use them correctly.

---

## Concept 1: The User UI Alert (`_push_alert`)

Think of `_push_alert` as the **Frontend Intercom**.

### How it works
This is a synchronous Python method living inside `state_manager.py`. When called, it formats a message, deduplicates it, and injects it into `SystemState.system_alert_msgs`. The State Manager then pushes this updated state over the SSE (Server-Sent Events) stream to the web browser, which renders it as a dismissible red or green toast notification on the dashboard.

### When to use it
Use this *only* for critical, actionable alerts that the human looking at the web dashboard needs to see immediately.
* ✅ *Example:* "🔴 CRITICAL: Local MQTT Broker offline"
* ✅ *Example:* "🟢 SUCCESS: Local MQTT Broker back online"

```python
# Example usage inside state_manager.py
ch, dom = self._push_alert("🔴 CRITICAL: Local MQTT Broker offline")
state_changed |= ch
changed_domains |= dom
```

---

## Concept 2: Live Network Telemetry (`WanosLogger`)

Think of the `WanosLogger` as a **Network Broadcaster**. 

### How it works
`WanosLogger` is a custom Python class. It takes a message, writes it to the disk, wraps it in JSON, and transmits it over the network via MQTT to topics like `wanos/console/status`. **The web UI user never sees this.** This is strictly for admins monitoring the system state via external MQTT clients (like MQTT Explorer, Node-RED, or external debugging tools).

* **It is Asynchronous:** Because talking to a network takes time, the `WanosLogger` methods use `async def`. You must use `await` when calling them.
* **Where it lives:** It is instantiated *once* in `main.py` and handed directly to the `StateManager`.

### When to use it
Use `WanosLogger` for important system transitions that an admin monitoring the MQTT broker needs to track in real-time.
* ✅ *Example:* `await self.logger.warning("Sauna door opened! Emergency cutoff triggered.")`

---

## Concept 3: Silent Disk Diagnostics (`loguru`)

Think of the standard `logger` and `automation_logger` as **Silent Archivists**.

### How it works
WanOS uses the `loguru` library to handle writing text to the Raspberry Pi's hard drive (`wanos.log`, `wanos_debug.log`, and `wanos_automations.log`). Those files are **not** `/var/log/syslog`. Host rsyslog `syslog` is OS-capped at 20 MiB and `daemon.log` is disabled (`helpers/wanos_rsyslog_logcap.sh`). Operator tails: `wanoslog.sh` (app files + `journalctl -u wanos.service`). 

* **It is Synchronous:** You do not need to use `await`.
* **It is Network-Free:** Messages sent here *never* go to MQTT and *never* show up on the UI.
* **How is it safe for async loops?** To prevent disk writes from freezing WanOS, we use Loguru's `enqueue=True` setting. This instantly drops the log message into a hidden background queue, allowing your physics engine to keep running while a separate background thread safely writes the file.

### When to use it
Use the silent loggers for **Developer Debugging** and **Business Auditing**.
* ✅ *Developer Debug:* `logger.debug("Evaluating rule 'Go Cosy Scene'...")`
* ✅ *Business Audit:* `automation_logger.info("Rule 'Bathroom Vent' -> Set IDX 7558 to ON")`

---

## Concept 4: The Golden Rule of Imports & Type Hinting

You might notice that `state_manager.py` imports `WanosLogger`, but `automation_rules.py` does not. This is a fundamental architectural rule in Python.

**The Golden Rule:** *If a file receives an object as a parameter, it MUST import that object's class for type hinting. If a file never receives or holds the object, do not import it.*

### Why `state_manager.py` requires the import
The `StateManager` requires the main engine to hand it an active `WanosLogger` instance when it boots up. To satisfy Python's type checker, you must import the class definition.
```python
# We MUST import it here because we use it as a Type Hint on the next line
from .logger import WanosLogger

def __init__(self, mqtt_client: MqttClientManager, logger: WanosLogger) -> None:
    self.logger: WanosLogger = logger
```

### Why `automation_rules.py` ignores the import
The `AutomationEngine` calculates logic statically. It does not ask for a `WanosLogger` in its arguments, and it never touches the network. Therefore, importing it would waste memory. It only imports the static archivists it actually needs.
```python
# Import the standard logger for developer diagnostics
from loguru import logger  

# Import the custom bound logger for the audit trail
from core.logger import automation_logger
```

---

## Summary Cheat Sheet

When you need to communicate an event, ask yourself: **Who needs to read this?**

| Intent			| Who is reading?			| Which Tool?			| Example Code
| :--- 				| :---						| :---					| :---
| **Web UI Alert**	| The End-User (Web Browser)| `_push_alert`			| `self._push_alert("🔴 Heater Overload!")`
| **Network Admin**	| Admin (MQTT Explorer)		| `WanosLogger`			| `await self.logger.warning("Hardware Bus Switched")`
| **Diagnostic**	| The Developer (Log file)	| Standard `logger`		| `logger.debug("Checking rule conditions...")`
| **Audit Trail**	| The Homeowner (Log file)	| `automation_logger`	| `automation_logger.info("Timer expired. Lights OFF.")`