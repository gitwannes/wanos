# WanOS Phase L — Local character LCDs

Dedicated 16x2 HD44780 screens (WISC-compatible text). **L1** = agent on a second Pi (**Done**). **L2** = same screens on the WanOS Pi (queued).

**Status:** **L1** Done — Pi smoke **2026-08-24**. **L3** Done — shipped with **C34** **2026-09-02**. **L4** Done — shipped with **C38** **2026-09-08**. **L2** queued.

**Related:** Product home → [`docs/sauna-ir.md`](../sauna-ir.md) § 3.7. Sync → [`docs/wanos-sync.md`](../wanos-sync.md). Install → [`_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`](../../_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md). Sequence → [`pipeline.md`](pipeline.md).

**DoD convention:** Last DoD = audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.

---

## Subphases

| Id | What | Status |
|----|------|--------|
| **L1** | LCD Pi agent under `_lcd-agent/`, MQTT render, bootstrap/SSH, `wanos-sync` `lcd` + `logcopy`, WISC screen1 mirror | **Done** 2026-08-24 |
| **L2** | Move physical LCDs onto the WanOS Pi; retire dedicated LCD Pi | Queued |
| **L3** | LCD log `§1` → `°C` + DEBUG semantic dedupe (no countdown-only lines) | **Done** 2026-09-02 (with **C34**) |
| **L4** | WISC screen1 timer remaining + door-closed duration | **Done** 2026-09-08 (with **C38**) |

---

## L1 — LCD Pi agent ✅ Done (2026-08-24)

**Shipped (pointer):** Dedicated LCD Pi (`.51`) renders MQTT `wanos/lcd/screen1|2` from `_lcd-agent/`. WanOS composes screen1 in `logic/lcd_screen1.py` (also `sauna.lcd_line1/2` WISC preview). Sync `test|run|logcopy [lcd]` (`run` always logcopies); secrets in Pi `/home/wannes/wanos/.env`. Canonical product text: [`sauna-ir.md`](../sauna-ir.md) § 3.7. Deploy: [`wanos-sync.md`](../wanos-sync.md) + install md above.

**Delivery locks (archive):** `_lcd-agent/` contents → `/home/wannes/wanos` (not nested `_lcd-agent`); main mirror excludes `_lcd-agent`; same SSH key as WanOS Pi; log pull `/var/log/wanos/wanos*` (not journalctl); I2C `0x27` / `0x26`; `wanos_venv`; unit `wanos-lcd-agent.service`.

**DoD:** Agent + MQTT + sync lcd/logcopy ✅ Pi smoke. Last DoD docs audit ✅ **2026-08-24**.

---

## L2 — LCDs on WanOS Pi (queued)

Same hardware on `10.32.251.30`; drop the dedicated LCD Pi. Split at L2 kickoff (venv/service merge, I2C on WanOS Pi, retire `.51`).

### Operator note (2026-08-24) — config home when screens move

> all these things which now live in .env on the lcd pi should move to config_hardware.yaml when the screens are moved to the wanos pi

**L2 placement lock (delivery):** settings that today live only in the LCD Pi `/home/wannes/wanos/.env` (`WANOS_LCD_MQTT_*`, I2C bus/addrs, topics, screensaver timeout, …) must move into **`config_hardware.yaml`** (plain-text site config; overridable as today — not a second config system). Secrets that remain secrets (MQTT password) stay out of git — exact secret path vs YAML reference is locked at L2 kickoff. Retire LCD-only `.env` keys once WanOS Pi owns the screens.

**L2 compose gate (delivery):** when `lcd_integration_enabled` is false, skip LCD text composition in WanOS (no `compose_lcd_screen1`, no `sauna.lcd_line1/2` refresh) — not only MQTT publish. L1 ships publish-only gate + WISC disabled message.

**L2 DoD:** TBD at kickoff (include: hardware config cutover from LCD `.env` → `config_hardware.yaml`). Last DoD: all `docs/**/*.md` + README.

---

## ✅ L3 — LCD / log °C encoding — **Done 2026-09-02** (shipped with **C34**)

**Product reference:** [`sauna-ir.md`](../sauna-ir.md) §3.7 — LCD agent logging (`_lcd-agent/lcd_pi_agent.py`): pretty `°C` in DEBUG lines; semantic dedupe skips mm:ss-only ticks; MQTT wire format unchanged.

**Delivery record:** [`phaseC-shell.md`](phaseC-shell.md) § C34 (combined ship close-out **2026-09-02**).

**L3 DoD:** [x] Log pretty-print · [x] Semantic dedupe · [x] Docs audit with **C34** **2026-09-02**.

---

## ✅ L4 — WISC screen1 timer + door-closed duration — **Done 2026-09-08** (shipped with **C38**)

**Product reference:** [`sauna-ir.md`](../sauna-ir.md) §3.7 — `logic/lcd_screen1.py`: pre-arm `session_end_time` as duration seconds (no false `00:00`); mm:ss only when remaining &lt; 15 min; door closed → temp/hum + closed-duration right-aligned (WISC `lcdcontrol` parity).

**Delivery record:** [`phaseC-shell.md`](phaseC-shell.md) § C38 (combined ship close-out **2026-09-08**).

**L4 DoD:** [x] Timer remaining · [x] Door-closed line2 · [x] Docs audit with **C38** **2026-09-08**.
