# ⚡ WanOS Phase E — Gmail

Outbound email **transport** (OAuth, outbox, spooler). Sequence → [`pipeline.md`](pipeline.md).  
**Blocky hook:** Phase **B9B H5** emits `EMAIL_REQUESTED` only; rules never call Gmail. Transport (**E**) can ship before or parallel to B9B; H5 email DoD waits on E. **B10B** does **not** seed `EMAIL_REQUESTED` into the `events:` catalog — that seed lands with **E** (or with H5 when E is ready).

Architectural blueprint for outbound email from WanOS via **Google Workspace OAuth2** and the **Gmail API**. Includes an offline-capable outbox so critical alerts still leave the Pi when WAN returns, without blocking the core asyncio event loop.

**Locked decisions**

| Topic | Choice |
|-------|--------|
| Auth | OAuth2 (Workspace); not App Passwords |
| Send path | Gmail API `users.messages.send` with `gmail.send` scope |
| Body format | Plaintext only |
| Outbox storage | Dedicated `email_outbox.db` (SQLite + WAL) |
| Eviction | FIFO; no priority field in v1 |
| Dedup | D + E (source identity + producer hysteresis) |
| Permanent auth failure | Disable spooler + persistent UI alert |
| Producers | Automations **and** other system sources (health, admin, etc.) |

---

## 1. Authentication & Secrets Management

Google Workspace expects OAuth for third-party access. WanOS uses a one-time Desktop OAuth consent flow, then stores long-lived secrets on the Pi.

*   **Secrets (`.env` only — never YAML or git):**
    *   `GMAIL_CLIENT_ID`
    *   `GMAIL_CLIENT_SECRET`
    *   `GMAIL_REFRESH_TOKEN`
    *   `GMAIL_SENDER` (Workspace mailbox / alias used as `From`)
*   **Scope:** `https://www.googleapis.com/auth/gmail.send` (send-only; do not request full mail scope).
*   **Runtime:** The spooler exchanges the refresh token for short-lived access tokens. Do not persist access tokens as the source of truth.
*   **Provisioning:** Operator completes browser consent once (Desktop OAuth client in Google Cloud Console), copies the refresh token into `.env`, restarts WanOS.
*   **Permanent auth failure:** On `invalid_grant`, revoked client, or equivalent hard auth errors: **stop the spooler**, leave pending outbox rows untouched, raise a **persistent UI alert**, and do not increment retry counters while disabled. Recovery is an explicit operator action after fixing credentials (reload / re-enable), then FIFO resume.

---

## 2. Event-Driven Workflow & Pydantic Validation

Email is a **system service**, not an automation-only feature. No producer calls Gmail directly. Every sender dispatches an internal event; a dedicated handler validates, dedups, and enqueues.

```text
automation / health / admin / …
        → EMAIL_REQUESTED (EmailPayload)
        → email_handlers (dedup D, enqueue)
        → email_outbox.db
        → email_spooler_task (token refresh + Gmail API send)
        → Gmail
```

*   **Event type:** `EMAIL_REQUESTED`
*   **`EmailPayload` (Pydantic, handler-level validation):**
    *   `recipient` — validated email address
    *   `subject` — string, max length clamped for transport safety
    *   `body` — **plaintext only**
    *   `source_id` — stable producer identity for dedup/logging (see §6)
*   Optional later: `admin_email` in `config.yaml` as a default recipient so rules need not repeat it.

---

## 3. The Offline-Capable Queue (`email_outbox.db`)

Edge devices can lose WAN while LAN / Z-Wave keep running. Outbound mail must buffer without unbounded RAM growth and must survive Pi reboot.

*   **Storage:** Dedicated SQLite file `email_outbox.db` — not mixed into `device_history.db` or `sensor_history.db` (different lifecycle, retention, and failure semantics).
*   **WAL mode:** `PRAGMA journal_mode=WAL;`
*   **Table `email_outbox`:**
    *   `id` — primary key
    *   `timestamp` — epoch creation time
    *   `payload` — JSON (`EmailPayload`)
    *   `retry_count` — transient failure attempts only
    *   `status` — `Pending` | `Failed` | `Sent` (and optionally a short-lived `Sending` to limit duplicate sends after crash; treat stale `Sending` as `Pending` on boot)
*   **Eviction:** Hard cap (e.g. max **50** pending). When full, **FIFO drop** oldest pending rows. No priority column in v1.
*   **Purge:** Batch-delete (or mark then purge) successfully `Sent` rows; avoid per-row thrash. While the spooler is **auth-disabled**, do not churn `retry_count` / status writes.
*   **Expected volume:** Few messages per day; the cap and WAL pattern are resilience measures, not throughput tuning.

---

## 4. The Asynchronous Dispatch Worker

Background task `email_spooler_task` runs alongside the StateManager loop.

*   **Non-blocking I/O:** All Google HTTP/token work must stay off the critical path for sauna PID, lighting, and other handlers (async HTTP client and/or `asyncio.to_thread` as appropriate).
*   **No ICMP/DNS “connectivity” preflight as truth:** Attempt send (or token refresh) with short timeouts. Classify outcomes:
    *   **Transient** (timeout, 5xx, network error) → exponential backoff (e.g. 30s → 1m → 5m), bump `retry_count`, keep `Pending`
    *   **Permanent auth** → disable spooler + UI alert (§1)
    *   **Permanent message** (invalid recipient, etc.) → mark `Failed`, log, do not block the rest of the queue
*   **Backoff:** Prevents aggressive reconnect loops that look like abuse to Google.
*   **Order:** Drain pending rows FIFO by `id` / `timestamp`.

---

## 5. Producers & Automation Hooks

### Shared contract

Any code path that needs mail builds an `EmailPayload` (with a stable `source_id`) and emits `EMAIL_REQUESTED`. Prefer a small shared helper that only enqueues the event — keep Gmail and SQLite out of call sites.

### Automations

Extend `logic/automation_rules.py` in line with **existing** action shapes (`idx` / `state` / `event` / `target`), not a parallel `action_type:` vocabulary.

*   **Preferred shape:** an action that results in `EMAIL_REQUESTED` (e.g. dedicated email action fields, or an `event`-style action that carries email fields). Exact YAML keys are an implementation detail; the invariant is: rules never talk to Gmail.
*   **Templates:** Plaintext body/subject may interpolate live state (e.g. `Warning: Sauna temperature reached {{ sauna_calc_temp }}°C`). Escape or sanitize only as needed for plaintext; no HTML pipeline.
*   **Producer hysteresis (dedup layer E):** For flappy sensors, the rule/condition side should require stability (must stay true for N seconds / crossing with hysteresis) **before** emitting `EMAIL_REQUESTED`. Transport dedup is a safety net, not the primary flap filter.

### Other sources

Health monitor, admin actions, security/bridge failures, etc. use the same event. Each must supply its own `source_id` (e.g. `health.smtp_disabled`, `admin.test_mail`).

---

## 6. Anti-Spam & Rate Limiting (Dedup D + E)

Sensors flap; logic can bounce. Guardrails are two-layer:

| Layer | Where | Key | Behavior |
|-------|--------|-----|----------|
| **E — Producer hysteresis** | Automation conditions / callers | Domain-specific | Do not fire duplicate requests on noise; prefer “stayed true” / latch semantics |
| **D — Transport dedup** | `email_handlers` (RAM cooldown) | `(source_id, recipient)` | Within cooldown (e.g. 15 minutes), drop duplicate requests; log as suppressed |

*   **Automation `source_id`:** Stable rule identity — prefer explicit id if present; otherwise stable `rule.name` (renaming resets cooldown; document that).
*   **Not used for dedup:** Subject-only or full body hash (templated plaintext with live values would defeat body hashing; shared subjects would over-suppress).
*   **Hard queue cap:** See §3 (FIFO drop at 50 pending).

---

## 7. Message Format

*   **Plaintext only** — no HTML part, no `multipart/alternative` requirement for v1.
*   Build a correct RFC 2822 message (From = `GMAIL_SENDER`, To, Subject, body, charset) and base64url-encode for Gmail API `raw` as required by Google.
*   `From` must be the authorized Workspace user or an allowed send-as alias.

---

## 8. Implementation: File Modification Blueprint

Distribute logic so the event loop stays decoupled:

### Configuration
*   **`.env`:** `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER`
*   **`config.yaml`:** Optional `admin_email`; optional email/cooldown/cap tunables if not hardcoded

### Data definition
*   **`core/models.py`:** `EmailPayload` (+ `EventType.EMAIL_REQUESTED` if that is where event enums live)

### Automation & other producers
*   **`logic/automation_rules.py`:** Recognize email actions; apply producer hysteresis where needed; template plaintext; dispatch `EMAIL_REQUESTED` with `source_id`
*   Other modules (health, admin, …): same event, their own `source_id`

### Integration & handlers
*   **`integrations/gmail.py` (NEW):** OAuth token refresh + Gmail API send for a validated payload; map Google errors to transient vs permanent auth vs permanent message
*   **`core/event_handlers/email_handlers.py` (NEW):** Validate payload, apply transport dedup `(source_id, recipient)`, insert into outbox

### Storage & background worker
*   **Outbox manager / DB init:** Create/open `email_outbox.db`, ensure `email_outbox` table, WAL
*   **`core/state_manager.py` or `main.py`:** Register `email_spooler_task`; on auth-disable, surface UI alert via existing alert path; support operator re-enable after credential fix

---

## 9. Out of scope for v1

*   App Passwords / password SMTP auth
*   HTML bodies
*   Priority / non-FIFO scheduling
*   Reading or managing the mailbox (send-only scope)
*   Colocating the outbox inside history databases

---

## 10. DoD (standing)

When this phase ships: transport live; Blockly/producers emit `EMAIL_REQUESTED` only; Pi smoke. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**
