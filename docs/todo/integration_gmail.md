# WanOS Gmail Integration & Resilient Queue Architecture

This document outlines the architectural blueprint for integrating Gmail via SMTP (App Passwords) into WanOS. It includes a resilient, offline-capable queuing system to ensure critical automation alerts are dispatched when internet connectivity is restored, without blocking the core event loop.

---

## 1. Authentication & Secrets Management

To maintain security and comply with Google's modern authentication requirements for headless devices, WanOS will utilize TLS-secured SMTP with an App Password. 

*   **Credential Isolation:** Email credentials will never be hardcoded or placed in the YAML configuration. They must reside exclusively in the `.env` file (e.g., `SMTP_USER` and `SMTP_APP_PASSWORD`).
*   **Protocol Standards:** The system will connect to `smtp.gmail.com` using implicit TLS on Port 465 (or explicit STARTTLS on Port 587) to ensure payload encryption in transit.

## 2. Event-Driven Workflow & Pydantic Validation

Following the established WanOS architecture, automations will not send emails directly. They will dispatch an internal event that a dedicated handler processes.

*   **New Event Type:** `EMAIL_REQUESTED`
*   **Strict Payload Schema (Pydantic):** We will define an `EmailPayload` model in `core/models.py`. It will enforce strict typing for:
    *   `recipient` (Must pass basic email regex validation).
    *   `subject` (String, clamped to a maximum length to prevent SMTP rejection).
    *   `body` (String, supports plaintext or basic HTML).
    *   `priority` (Integer/Enum, allowing the queue to prioritize alarms over daily summaries).

## 3. The Offline-Capable Queue (The Spooler)

Because IoT edge devices can lose WAN access while local LAN/Z-Wave operations continue, the system must buffer outbound messages without leaking memory or losing data during a sudden Pi reboot.

*   **Storage Medium:** An SQLite table (e.g., `email_outbox` in `device_history.db`) or a lightweight local spool directory. SQLite is preferred for transactional safety.
*   **Queue Schema:**
    *   `id` (Primary Key)
    *   `timestamp` (Epoch creation time)
    *   `payload` (JSON string of the email data)
    *   `retry_count` (Integer tracking failed attempts)
    *   `status` (Pending, Failed, Sent)
*   **SD Card Wear Mitigation:** The SQLite database must operate in WAL (Write-Ahead Logging) mode, and successful emails should be batch-purged rather than deleted row-by-row to minimize flash memory wear.

## 4. The Asynchronous Dispatch Worker

A dedicated background task (`email_spooler_task`) will run alongside the main `StateManager` event loop to manage the queue asynchronously.

*   **Connectivity Polling:** Before attempting an SMTP handshake, the worker will perform a fast, low-overhead DNS resolution (e.g., pinging `8.8.8.8` or resolving `smtp.gmail.com`). If it fails, the worker sleeps.
*   **Exponential Backoff:** If the internet is down, the worker will not aggressively poll the SMTP server (which could trigger a temporary Google IP ban). It will back off (e.g., 30 seconds, then 1 minute, then 5 minutes) until connectivity returns.
*   **Non-Blocking I/O:** The actual dispatch will use an asynchronous SMTP library (like `aiosmtplib`). This guarantees that a slow TLS handshake with Google will never freeze the sauna PID controller or lighting handlers.

## 5. Automation Engine Hooks

The existing `automation_rules.py` engine will be extended to recognize a new action directive in your YAML files.

*   **YAML Syntax Blueprint:**
    The automation trigger will remain standard (e.g., `condition: SENSOR_VALUE > 50`). The action block will support a new type: `action_type: send_email`.
*   **Template Injection:** The automation engine will allow dynamic variable injection into the email body, passing live sensor states (e.g., *"Warning: Sauna temperature reached {{ sauna_calc_temp }}°C"*).

## 6. Anti-Spam & Rate Limiting (Guardrails)

Sensors flap, and logic gates bounce. A failing water sensor could theoretically trigger an automation 100 times in a minute. 

*   **Deduplication Window:** The email handler will implement a time-based hash lock in RAM. If an email with the exact same subject is requested within a defined cooldown window (e.g., 15 minutes), the duplicate request is silently dropped and logged as suppressed.
*   **Hard Queue Limits:** To prevent the Pi's storage from filling up during a multi-day internet outage, the SQLite outbox will have a hard cap (e.g., maximum 50 pending emails). Older non-critical emails will be overwritten (FIFO drop) to prioritize fresh alerts.

---

## 7. Implementation: File Modification Blueprint

To implement this architecture without breaking the decoupled nature of the WanOS event loop, the logic will be distributed across the following layers:

### The Configuration Layer
*   **`.env`:** Add `SMTP_USER` and `SMTP_APP_PASSWORD` to keep credentials secure and out of version control.
*   **`config.yaml`:** (Optional) Define a global `admin_email` address so automations do not need to hardcode the recipient every time.

### The Data Definition Layer
*   **`core/models.py`:** Add the new `EmailPayload` Pydantic model to strictly validate the incoming `recipient`, `subject`, and `body` before it ever reaches the database or network.

### The Automation & Logic Layer
*   **`logic/automation_rules.py`:** Update the engine to recognize the new action type (`action_type: send_email`). It will process the condition, inject live sensor data into the email body template, and dispatch an `EMAIL_REQUESTED` event to the `StateManager`.

### The Integration & Execution Layer
*   **`integrations/gmail.py` (NEW):** Create this standalone module containing the asynchronous function (e.g., `async def send_email(...)`) that takes a validated payload, handles the TLS handshake via `aiosmtplib`, and dispatches it to Google's SMTP servers.
*   **`core/event_handlers/email_handlers.py` (NEW):** Create a dedicated handler to intercept the `EMAIL_REQUESTED` event. It will validate the payload via Pydantic, check the anti-spam deduplication cache, and insert the payload into the SQLite outbox queue.

### The Storage & Background Queue Layer
*   **`core/database.py`:** Add an initialization block to create the `email_outbox` table (with columns for `id`, `timestamp`, `payload`, `retry_count`, and `status`) upon system boot if it does not already exist.
*   **`core/state_manager.py` (or `main.py`):** Register the new infinite background task (`email_spooler_task`). This asynchronous loop will wake up periodically, check the SQLite outbox for pending messages, test internet connectivity, call `integrations/gmail.py` to send them, and update or delete the database rows upon success or failure.