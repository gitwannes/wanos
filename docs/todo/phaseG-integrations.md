# ⚡ WanOS Phase G — Integrations

Integrations reliability — Hue color/state truth, Epson projector power truth, OWM outside climate / daily forecast (hot-sun cinema blinds), scoped config hot-reload, and integration log tag parity.

**Status:** Spec **LOCKED** (intent). G2 assess-on-Pi first; G1 analysis-gated; **G3** config anytime; **G4** needs One Call 4.0 (subscribed ✅ 2026-08-10); **G5** still TODO — partial `Cinema rolluik half` (Open→50) live, **DoD gaps** in § G5; **G6** scoped `CONFIG_RELOAD` (assessed **2026-08-11**); **G7** log prefixes (**2026-08-11**).

**Related:** Sequence → [`pipeline.md`](pipeline.md). Blocky Hue **editor** bugs stay **B10A** ([`phaseB-blocky.md`](phaseB-blocky.md)); soft-hide picker → **B10C** ✅. Blocky CRUD still dispatches `CONFIG_RELOAD_REQUESTED` (B1/B5) — **G6** narrows what that recycle does. Explorer Hue **COLOR OUTPUT** text remove → **C10** ✅ (not G2). This phase is **runtime** bridge ↔ WanOS state/UI (+ OWM + reload scope + log tags).

**DoD convention:** every G subphase ends with **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## Subphases

| Subphase | Focus |
|---|---|
| **G2 — Hue state** | Boot + live color/bri truth; UI must match bridge |
| **G6 — Scoped reload** | Automations / hide / auto-off save ≠ Hue·Onkyo·Z-Wave recycle |
| **G7 — Log prefixes** | `[Onkyo]` (and peer) tag parity with `[HUE]` |
| **G1 — Epson boot** | `get_power_state` when safe |
| **G3 — OWM poll** | Outside temp/hum every **10′** (was 30′) |
| **G4 — OWM daily + hot sun** | One Call 4.0 once/day; hot+full-sun → cinema opens to **60% open** |
| **G5 — Rolluik zon half** | Dashboard control: cinema → **60% closed** if not fully closed (**partial** UE/UR live — gaps documented) |

Pipeline may run **G2 before G1** if daily color lies hurt more than Epson boot lies. **G6** may jump ahead of **G2/G1** if Blocky-save bridge thrash / timer re-arm pain wins. **G7** anytime (low). **G3** is config-only and may ship anytime. **G4** before **G5** preferred (shared cinema-sun story); **G5** can ship alone if operator wants the manual button first.

---

## 📋 G2 — Hue color / brightness truth 🔜 TODO

**Locked intent:** WanOS **state and UI must match the Hue bridge** after boot and after bridge-side color/brightness changes (app, dimmer, scene on the Hue side).

### Confirm (assess on Pi first)

* Does boot `_sync_initial_state` actually land `bri`/`xy` in live device state for each light?
* ON-only commands must **not** change color/bri (confirm rich idempotency) — expected.
* When color or brightness is changed **on the Hue bridge** (not via WanOS), does WanOS update? Code has SSE `bri`/`xy` paths — **confirm in practice**; treat gaps as bugs.
* Does the UI show **`#FFD180`** when `xy` is missing? That is a **display fallback** in Explorer (`xyToHex` / defaults) — not proof that WanOS “wrote” warm-white to the bulb. Find why operators see FFD180 at startup and whether state lacks `xy` or UI ignores it.

### Fix (after confirm)

* Close any hole so boot sync and SSE keep `on` + `bri` + `xy` in state.
* UI: show bridge color when present; do not present FFD180 as “known state” when `xy` is unknown (explicit unknown / last-known policy — pick in impl).
* Badkamer red / washed color checks (was ops inbox) fold into this assess pass.

**G2 DoD:** After WanOS restart, Explorer color matches bridge for ON lights with color. After changing color on the Hue app, WanOS state/UI update without a WanOS command. ON-only automation still leaves color unchanged. Pi smoke + no false FFD180-as-truth. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G1 — Epson `get_power_state` at boot 🔜 TODO

* Implement Epson **get_power_state** at boot.
* Review when it is correct to call for **reliable** results (warm-up, network, projector ready).

**No code until analysis** — see Epson integration docs / code when implementing.

**to be checked:** call timing constraints.

**G1 DoD:** Boot path queries power when safe; documented when *not* to call; Pi smoke shows consistent Epson state after restart. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G3 — OWM outside poll interval 🔜 TODO

**Origin:** operator request **2026-08-09**.

* Only production outside source: OWM **`30001`** / `sensor.temp_hum.outside_temp_hum` (`config.yaml` `weather.poll_interval_mins`).
* Change **30 → 10** minutes. Lab `outside_tick` unchanged.

**G3 DoD:** Live OWM climate refresh ≤10′; Pi smoke outside temp/hum updates on that cadence. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G4 — OWM One Call daily + hot-sun cinema open 🔜 TODO

**Origin:** operator request **2026-08-10** (assess after One Call by Call 4.0 subscribe).

**Prerequisite:** Account has **One Call API 4.0** (“One Call by Call”) — same `OWM_API_KEY` as Current 2.5; free tier **1,000 calls/day** (home use ≈1 call/day).

### Intent

* **Assess** once daily with the existing sun-refresh window (**≥ `sun_refresh_hour` / 03:00**, or before blinds open): One Call **`/data/4.0/onecall/timeline/1day`** for Borsbeek/Antwerp (**lat/lon**, `units=metric`).
* If **today’s `temp.max` > 25°C** and **full sun** (define threshold — e.g. low `clouds` and/or `weather` Clear / id 800) → set a day flag (e.g. hot-sun cinema).
* On **`BLINDS_OPEN_TRIGGER`** (clamped sunup / 07:00): **cinema** opens only to **60% open** (= stored closed **`state: 40`**); other blinds unchanged (fully open as today).
* Non-hot / non-sun days: cinema fully open as today (`state: 0`).
* Watch interactions: **CINEMA OFF** / other rules that force cinema fully open must not undo the heat rule without intent.

### Not this item

* Current 2.5 climate poll cadence → **G3**.
* Manual dashboard half-close → **G5**.
* Paid Weather Startup / `/forecast/daily` — **not required** (One Call 4.0 is enough).

**G4 DoD:** Morning assess stores hot-sun flag from One Call 1-day; Pi smoke on a qualifying forecast day shows cinema at **60% open** after blinds-open (others full open); cool/cloudy day still full-open cinema; Admin Debug clean; ≤ a few One Call calls/day in normal use. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G5 — Dashboard “rolluik zon half” 🔜 TODO

**Origin:** operator request **2026-08-10**.

**Status check 2026-08-11:** **still TODO** — operator added a **partial** UE/UR on Pi/repo; **does not satisfy DoD**. Keep queued.

### Live partial (not DoD)

* **UE/UR name:** `Cinema rolluik half` (`events:` UUID `856d0f0d-…`, rule id `0efe3829-…`).
* **Dashboard:** UE `show_on_dashboard: true` (button exists).
* **Rule today:** When UE → if `blinds.cinema` **is Open (`0`)** → set `state: '50'` (50% closed).
* **Gaps vs DoD:** label not **“rolluik zon half”**; target **50** not **60** closed; condition **Open-only** (mid positions no-op) instead of **not fully closed** (`≠ 100`); misnamed old Hue-on-OPEN cleanup still **to be checked**.

### Intent (DoD — unchanged)

* Add a **dashboard** control labeled **“rolluik zon half”** (**user** catalog event + rule; Explorer via `show_on_dashboard` / `dashboard_events` — B10B+D+E shipped).
* Action: if **`blinds.cinema` is not fully closed** (`state` ≠ `100`) → set cinema to **60% closed** (`state: 60`).
* If already fully closed → **no-op** (do not open / crack the blind).

### Cleanup

* Existing rule **“Rolluik cinema half (zon)”** is misnamed: trigger `blinds.cinema` → `OPEN` turns on **badkamer Hue** — does **not** set a half position. **Retire or rename** when G5 lands so operators are not confused.

**to be checked:** whether “not fully closed” needs a new Blocky/device-state condition (**B9A**), a small hub guard, or an always-set-to-60 with explicit skip-if-100 in rule engine. (Open-only condition in the partial rule is **not** accepted as DoD.)

**G5 DoD:** Dashboard button visible (label **rolluik zon half** or rename partial to match); with cinema **open or mid**, tap → **60% closed**; with cinema fully closed, tap leaves it closed; misnamed Hue-on-OPEN rule gone or clearly renamed; Pi smoke. Partial `Cinema rolluik half` / Open→50 must be updated or replaced. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G6 — Scoped `CONFIG_RELOAD` (automations save ≠ bridge recycle) 🔜 TODO

**Origin:** triage **2026-08-11** (Pi log after Blocky automation rule save).

**Problem:** Blocky / soft-hide / auto-off / events CRUD correctly dispatch `CONFIG_RELOAD_REQUESTED` (`source: api`), but `handle_config_reload_requested` always runs a **full** recycle: Hue stop/start + initial sync, Onkyo TCP bounce, RFX/Sonos map refresh, Z-Wave remap + MQTT re-subscribe, NVRAM reload via `rebuild_core_metadata`, passive post-reload sweep. Z-Wave listens to the same event and forces `_is_mapped` / `_integration_enabled` reset even when `config_zwave.auto.yaml` did not change.

**Observed harm (automation-only save):** ~15s Hue outage + init state flood; Onkyo reconnect; Z-Wave discovery flood; brief `DEAD`→live transitions that can **re-arm auto-off timers** (e.g. `berging 2e`).

### Locked intent

* After an **automations-only** write (`automations:` / `events:` surgical CRUD), reload must refresh **rules engine config** (and events/dashboard extract when that catalog changed) — **not** tear down Hue / Onkyo / Z-Wave / MQTT.
* Soft-hide / auto-off saves need their **own narrow** refresh (hide list / auto-off block + Explorer flags) — still **no** bridge recycle.
* **Admin “Reload config”** (and any write that changes Hue / Z-Wave / Onkyo / hardware maps) may keep today’s **full** path.
* Blocky operator policy unchanged: CRUD still auto-dispatches reload; no return to routine Admin reload for saves.

### Needed vs not (automation rule save) — triage baseline

| Action | Needed? |
|---|---|
| Re-read automations YAML into `AppConfig` + clear `AutomationEngine._config` | **Yes** |
| Events/dashboard extract | **Only if** `events:` changed |
| Soft-hide / auto-off rebuild | **No** (separate APIs) |
| Hue tear-down + full initial sync | **No** |
| Onkyo stop/start + TCP reconnect | **No** |
| Z-Wave remap + MQTT re-subscribe + discovery flood | **No** |
| NVRAM reload from disk | **No** (side effect of full metadata rebuild) |
| Full hardware metadata purge/rebuild | **No** |
| Post-reload sweeper | **Mostly no** (already passive / skips blinds) |

### Design fork (pick at kickoff — no code until chosen)

1. **Scoped reload reasons** on the event payload (`scope`: `automations` / `hide` / `auto_off` / `events` / `full`) — callers declare intent; handler + Z-Wave only do matching work.
2. **Hash / fingerprint skip** — still one event; skip Hue/Onkyo/Z-Wave recycle unless relevant YAML fingerprints changed since last load.

Prefer (1) if API writers already know what they touched; (2) if Admin/manual paths must stay dumb.

### Not this item

* Hue color/bri truth vs bridge → **G2**.
* Blocky save chrome / Library polish → **B10F** ✅.
* Changing *whether* CRUD dispatches reload (B1/B5 policy stays).

**G6 DoD:** Blocky automation (and events) save: rules live immediately; **no** Hue torn-down / Onkyo stopped / Z-Wave “Core config reload… Rebuilding…” / MQTT re-open in logs; no spurious auto-off re-arm from rediscovery. Soft-hide / auto-off saves update Explorer/timers without bridge recycle. Admin full reload still remaps integrations when hardware YAML changed. Pi smoke + docs. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G7 — Integration log tag prefixes 🔜 TODO

**Origin:** inbox **2026-08-11**. Size **low**.

* Hue logs use `[HUE]`; Onkyo lines like `Onkyo Bridge stopped.` lack a bracket tag.
* Normalize integration lifecycle / bridge lines to a consistent `[Onkyo]` (and audit peers for the same gap).

**Not this item:** device-ref shape → **C9** (done); Automations CRUD INFO → **B10F** item 11 ✅.

**G7 DoD:** Onkyo bridge start/stop (and peers audited) use `[Onkyo]`-style tags in `wanos.log`; Pi smoke one reload/start path. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**
