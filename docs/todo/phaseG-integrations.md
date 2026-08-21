# ⚡ WanOS Phase G — Integrations

Integrations reliability — Hue color/state truth, Epson projector power truth, OWM outside climate / daily forecast (hot-sun cinema blinds), scoped config hot-reload, and integration log tag parity.

**Status:** Spec **LOCKED** (intent). **G3 ✅ Done 2026-08-15** (config **30→10** on cold boot; one code run with **B10K**). **G5 ✅ Done 2026-08-16** — dashboard UE/UR `Cinema rolluik half` (open % > 50 → set 50%; legacy canvas + **B9C**). G2 assess-on-Pi first; G1 analysis-gated; **G4** needs One Call 4.0 (subscribed ✅ 2026-08-10); **G6** scoped reload + Admin modal + Automations deferred Save config (**expanded 2026-08-15**); **G7** log prefixes (**2026-08-11**); **G8** boot autostart timing — **A+B** (**spec locked 2026-08-12**); **G14** manual enable status + ON bell (**assess**, inbox **2026-08-15**); **G9–G13** five new vendor bridges (sequential own ships) — inbox **2026-08-14**.

**Related:** Sequence → [`pipeline.md`](pipeline.md). **G9–G13 how-to** → [`docs/integration-playbook.md`](../integration-playbook.md) (code/config/C18/IDX/logging checklist; not a kickoff). Blocky Hue **editor** bugs stay **B10A** ([`phaseB-blocky.md`](phaseB-blocky.md)); soft-hide picker → **B10C** ✅. **G6** scopes what reload recycles **and** defers Automations reload until Save config (B1/B5 auto-dispatch on every rule save does **not** stay). Explorer Hue **COLOR OUTPUT** text remove → **C10** ✅ (not G2). This phase is **runtime** bridge ↔ WanOS state/UI (+ OWM + reload scope + log tags + **G9–G13** new vendor bridges).

**DoD convention:** every G subphase ends with **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## Subphases

| Subphase | Focus |
|---|---|
| **G2 — Hue state** | Boot + live color/bri truth; UI must match bridge |
| **G6 — Scoped reload** | Automations deferred Save config + scoped recycle (hide / auto-off / Admin modal) |
| **G7 — Log prefixes** | `[Onkyo]` (and peer) tag parity with `[HUE]` |
| **G8 — Boot autostart** | ~30s “integrations disabled” after restart — shorten enable + honest Admin UX |
| **G14 — Manual enable UX** | After network-failure disable: enabling status + ON bell; assess all integrations |
| **G1 — Epson boot** | `get_power_state` when safe |
| **G3 — OWM poll** | ✅ **Done 2026-08-15** — outside temp/hum every **10′** (was 30′) |
| **G4 — OWM daily + hot sun** | One Call 4.0 once/day; hot+full-sun → cinema opens to **60% open** |
| **G5 — Cinema rolluik half** | ✅ **Done 2026-08-16** — dashboard UE/UR; open % **> 50** → set **50%** open (stored **50**); legacy canvas + **B9C** |
| **G11 — Samsung SmartThings** | Airco climate — **own ship** (1st of 5) — kickoff **locked 2026-08-20** |
| **G9 — Honeywell** | Thermostats / Evohome — **own ship** (2nd) |
| **G10 — HomeWizard** | Energy local API — **own ship** (3rd) |
| **G12 — SMA** | Solar inverters — **own ship** (4th) |
| **G13 — HomeConnect** | BSH appliances — **own ship** (5th) |

Pipeline may run **G2 before G1** if daily color lies hurt more than Epson boot lies. **G6** may jump ahead of **G2/G1** if Blocky-save bridge thrash / timer re-arm pain wins. **G7** anytime (low). **G8** may jump on boot UX pain (separate from **B10G** / **B10H**). **G14** may jump on manual-enable pain (separate from **G8**). **G3** ✅ **Done 2026-08-15** (config-only; cold boot; one code run with **B10K**). **G5** ✅ **Done 2026-08-16** (manual cinema half). **G4** still owns the automatic hot-sun morning open.

**G11 → G9 → G10 → G12 → G13:** five **new** bridges — **one integration per code run**, this order, **never combined**. Operator reordered **G11 first** **2026-08-20**. After current G reliability ships (default: after **G4**, before **F**). Credentials / IPs / device maps = home-specific → **P**. **Library assessment and choice** (candidates in operator inbox) = **in-scope of each phase at that phase’s kickoff** — **not now**, not this triage. **How to add any new vendor** (files, C18 success/fail, IDX bands, logging, Admin/reload) → [`docs/integration-playbook.md`](../integration-playbook.md). Do not duplicate that checklist into G9–G13 stubs.

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

**Also in G1 (moved from B9A 2026-08-11):** review Epson force policy with boot truth. **Today:** RFX always-force; Epson/Sonos/Onkyo force **OFF only** (hub + AutomationEngine). Keep as-is unless G1 analysis says otherwise. Blockly already omits FORCE_* for RFX/Epson.

**No code until analysis** — see Epson integration docs / code when implementing.

**to be checked:** call timing constraints.

**G1 DoD:** Boot path queries power when safe; documented when *not* to call; Pi smoke shows consistent Epson state after restart; force-policy note resolved (keep OFF-only or change). **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G3 — OWM outside poll interval ✅ DONE (2026-08-15)

**Shipped summary:** One code run with **B10K**. Pi smoke OK (operator **2026-08-15**). `config.yaml` `weather.poll_interval_mins`: **30 → 10**. Lab `outside_tick` unchanged. No OWM loop rewrite. Interval takes effect on **cold boot** only.

**G3 DoD:**

- [x] `poll_interval_mins: 10`
- [x] After `wanos` restart, `[OWM] … climate every 10m`
- [x] Different polled values show in Explorer + graphs
- [x] Same code run as B10K
- [x] Pi smoke — **2026-08-15**
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-15**

#### Locked decisions archive (Q&A 2026-08-15)

Only production outside source: OWM **`30001`** / `sensor.temp_hum.outside_temp_hum`. Running loop captures seconds at task start; CONFIG_RELOAD does not restart it. Unchanged poll values may stay skipped (existing duplicate ignore).

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

* Current 2.5 climate poll cadence → **G3** ✅ (**2026-08-15**).
* Manual dashboard half → **G5** ✅ (**`Cinema rolluik half`**, **50% open**).
* Paid Weather Startup / `/forecast/daily` — **not required** (One Call 4.0 is enough).

**G4 DoD:** Morning assess stores hot-sun flag from One Call 1-day; Pi smoke on a qualifying forecast day shows cinema at **60% open** after blinds-open (others full open); cool/cloudy day still full-open cinema; Admin Debug clean; ≤ a few One Call calls/day in normal use. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G5 — Dashboard `Cinema rolluik half` ✅ DONE (2026-08-16)

**Origin:** operator request **2026-08-10**. Blockly **%** capability via **B9C** (**2026-08-16**). **DoD revised 2026-08-16** (operator): accept live Pi rule as shipped — no B19 re-author, no rename to “rolluik zon half”, no 40%/≠0 condition.

**Shipped summary:** Operator YAML on Pi (legacy `When` + `case` canvas + **B9C** shutter open-%). Dashboard button + rule **`Cinema rolluik half`**. Misnamed Hue-on-OPEN rule **`Rolluik cinema half (zon)`** absent on Pi. No product-code ship for G5 itself.

| Piece | Live |
|---|---|
| UE | `856d0f0d-1f6b-4a1a-ace8-a5856a5ee491` — name **`Cinema rolluik half`**, `origin: user`, `show_on_dashboard: true`, `enabled: true` |
| UR | `0efe3829-625e-4979-a234-1b70dfdc8af6` — trigger that UE |
| Condition | `blinds.cinema` `attribute: position` `op: <` `is: '50'` (YAML closed %; Blockly UI = open % **> 50**) |
| Action | `blinds.cinema` `state: '50'` (**50% open** / stored closed **50**) |
| Canvas | Legacy + **B9C** (not **B19**) |

**% convention (B6C/B9C):** Blockly UI = **open %**; YAML/`state` = **closed %** (`100 − open`); inequalities via `blockyInvertCompareOp`.

#### Locked decisions archive (close **2026-08-16**)

* Label stays **`Cinema rolluik half`** (not “rolluik zon half”).
* Target **50% open** (stored **50**), not 40%/60.
* Gate = open % **> 50** (stored closed **< 50**), not “not fully closed” (≠ 0).
* Authored on **legacy + B9C**; **B19** re-author **out** of G5.
* Prior B19-authoring lock from kickoff **2026-08-16** **superseded** by this close.

**G5 DoD:**

- [x] Dashboard UE visible (`show_on_dashboard`)
- [x] UR: when UE → if cinema open % **> 50** → set **50%** open
- [x] Misnamed Hue-on-OPEN rule gone (not on Pi)
- [x] Pi smoke (operator; B9C session + close confirm)
- [x] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.** — ✅ **2026-08-16**

---

## 📋 G6 — Scoped `CONFIG_RELOAD` + Admin scoped-reload modal 🔜 TODO

**Origin:** triage **2026-08-11** (Pi log after Blocky automation rule save). **Expanded 2026-08-12** — Admin UX: keep **full** reload; add **scoped** reload with operator-selectable parts. **Expanded 2026-08-15** — Automations save: load-style step overlay + **defer** reload until Save config (dirty + leave modal). Not a separate phase.

**Operator request (verbatim, triage 2026-08-15):**
> when saving presets in the automation page : this takes long: add visibility: show steps to be taken, same timings as the one we use to load the automation page itself // maybe don't reload config on every rule change, but whenever a rule is changed, set the dirty mode for the reload config - a button "save config" then appears, or is enabled at least. when this reload config is not done while moving away from the page, show a modal similar to the modal which exists for the dirty-rule: with buttons "save config" "cancel" and "discard all rule changes"

**Problem:** Blocky / soft-hide / auto-off / events / hue-preset CRUD correctly dispatch `CONFIG_RELOAD_REQUESTED`, but `handle_config_reload_requested` almost always runs a **full** recycle: `load_config()` + full `rebuild_core_metadata()` + Hue stop/start + Onkyo TCP bounce + RFX/Sonos map refresh + Z-Wave remap + MQTT re-subscribe + NVRAM re-read + passive post-reload sweep (~2s). Z-Wave listens to **any** reload and forces `_is_mapped` / `_integration_enabled` reset.

**Observed harm (automation-only save):** ~15s Hue outage + init state flood; Onkyo reconnect; Z-Wave discovery flood; brief `DEAD`→live transitions that can **re-arm auto-off timers** (e.g. `berging 2e`).

---

### Today (shipped) — Admin **“Reload Config”** = **full reload**

Admin → **Reload Config** → `CONFIG_RELOAD_REQUESTED` `{ source: "ui_button" }` (no `scope`) → **full path**:

| Step | What runs |
|------|-----------|
| 1 | `load_config()` — **all** YAML profiles from disk (`config.yaml`, `config_hardware.yaml`, `config_hue.yaml`, `config_hue_presets.auto.yaml`, `config_zwave.auto.yaml`, `automations.auto.yaml`) |
| 2 | `AutomationEngine._config = None` |
| 3 | `rebuild_core_metadata()` — full metadata purge/rebuild, orphan eviction, NVRAM re-read, scenes/events extract, soft-hide idxs, `hue_presets`, `sonos_stations`, entity_registry ensure/flush |
| 4 | **Hue bridge recycle** — `stop()` → new config → `_initialize_mappings()` → `start()` (full initial sync) |
| 5 | **RFX** — rebuild in/outbound translation maps |
| 6 | **Sonos** — device/station maps + speaker socket refresh |
| 7 | **Onkyo** — stop/start TCP listeners |
| 8 | **Z-Wave** (async listener) — `_is_mapped = False` → remap + MQTT re-subscribe on next state tick |
| 9 | **Post-reload sweep** scheduled (+2s, passive — skips blinds movement) |

**Partial today:** Timers & types API already sends `scope: "timers_types"` — skips step 4–7 only; still runs full steps 1–3 and 9.

**Not re-read from disk on reload:** `entity_registry.auto.yaml` (runtime-written births; Pi sync pull only). `.env` / auth secrets (process env; service restart if changed).

---

### Target Admin UX (locked intent)

| Control | Behaviour |
|---------|-----------|
| **Full reload** (rename/clarify current **Reload Config** row) | Unchanged semantics — everything in table above. Use after multi-file edits, deploy, or “something feels stale”. |
| **Scoped reload** (new row + modal) | **12** checkboxes (see catalog) — each with a one-line **summary** of what reloads + **when**; **Select all** / **Clear** only (no preset bundles). **Apply** → `{ mode: "scoped", scopes: [...] }`. |
| Automations **Save config** (deferred reload) | Rule YAML may persist on rule Save; **`CONFIG_RELOAD` does not run on every rule change.** Rule change → reload **dirty**. **Save config** appears or enables; that click runs scoped `automations` reload (see mapping). Leave Automations while dirty → modal like dirty-rule: **Save config** / **Cancel** / **Discard all rule changes**. While that reload runs: **same step checklist + timings as B10G overlay 2** (Automations cold load) — reuse, do not invent a second overlay spec. |
| Other API auto-reload | Soft-hide / events / timers / etc. still auto-dispatch with **minimal** `scopes` (not Admin full) unless kickoff says otherwise. |

**Admin UI home:** [`frontend/admin.html`](../frontend/admin.html) (shell) — detail cross-link → [`phaseC-shell.md`](phaseC-shell.md) when C docs mention Admin maintenance row.

---

### Event payload (kickoff design)

```json
{
  "type": "CONFIG_RELOAD_REQUESTED",
  "payload": {
    "source": "ui_button",
    "mode": "full"
  }
}
```

```json
{
  "type": "CONFIG_RELOAD_REQUESTED",
  "payload": {
    "source": "ui_button",
    "mode": "scoped",
    "scopes": ["automations", "hue_presets"]
  }
}
```

* **`mode: "full"`** — equivalent to today’s Admin button (ignore `scopes`).
* **`mode: "scoped"`** — run only listed scopes; empty `scopes` → reject 400.
* **API callers** use `"source": "api"` + minimal `scopes` (see mapping table below).
* **Legacy:** bare `{ source: "api" }` with no `mode`/`scopes` → treat as **full** until callers migrated.

**Implementation fork (pick at kickoff):**

1. **Explicit scopes** (preferred) — handler + Z-Wave listener branch on `scopes[]`.
2. **Hash skip** — optional add-on: within a scope, skip bridge recycle if YAML mtime unchanged (Admin dumb paths benefit).

---

### Scope catalog — **12** modal checkboxes (locked **2026-08-12**)

**Count: 12.** One checkbox each; no quick-pick bundles. Each row shows **label** + **summary** (what reloads) + **when** (why you'd pick it). Anything **not** listed (GPIO/SHT11 in `config_hardware.yaml`, NVRAM, full metadata orphan pass) → use **Full reload** only.

| # | Scope id | Modal label | Summary (what it reloads) | When you'd reload this | Recycle? |
|---|----------|-------------|---------------------------|-------------------------|----------|
| 1 | `automations` | Automation rules | Re-read `automations:` from `automations.auto.yaml`; clear rules engine cache | After hand-editing rules on disk, restoring from backup, or Blocky save didn't hot-reload and rules behave stale | No |
| 2 | `events` | Events catalog | Re-read `events:`; refresh Library SE rows + Explorer dashboard buttons | After editing event names/UUIDs/show flags, or dashboard/Library buttons don't match `automations.auto.yaml` | No |
| 3 | `soft_hide` | Explorer soft-hide | Re-read `deviceexplorer_hide:`; refresh hidden-device idx list | After editing hide list on disk or hidden devices still visible after Hidden-devices save | No |
| 4 | `timers_types` | Timers & product types | Re-read `auto_off_devices:` + `device_product_types:`; refresh auto-off + type labels | After Timers & types save glitch, hand-editing auto-off minutes/types, or Explorer shows wrong light/switch type | No |
| 5 | `hue_presets` | Hue colour presets | Re-read `config_hue_presets.auto.yaml` → `system.hue_presets` | After `wanos-sync` pulled `.auto` from Pi, hand-editing presets on disk, or colour-wheel chips missing/wrong (no bridge work) | No |
| 6 | `hue_maps` | Hue bridge & maps | Re-read `config_hue.yaml` (bridge, lights, groups, scenes); **Hue bridge stop → remap → sync** | After adding/mapping Hue lights/groups locally (`hue_discovery.py`), changing bridge IP, or Explorer Hue names/idx wrong | **Hue** |
| 7 | `zwave_map` | Z-Wave device map | Re-read `config_zwave.auto.yaml`; **MQTT re-subscribe + endpoint remap** | After Z-Wave config page save, provisioning new nodes, or Z-Wave devices missing/wrong in Explorer | **Z-Wave** |
| 8 | `config_yaml` | Runtime config | Re-read **`config.yaml`** runtime blocks: `sauna`, `ir`, `bathroom1`, `blinds`, `environmental_schedule`, `weather`, `history`, `hardware_links`, `wanos` (non-secret); refresh domain config + OWM idx metadata + schedule clamps | After hand-editing sauna/IR/blinds/schedule/weather/history/power-link settings on PC and syncing, or env-schedule / sauna timing behaves stale — **without** touching integrations (pick 9–12 separately) | No |
| 9 | `sonos` | Sonos | Re-read `sonos:` in `config.yaml`; speaker map + station dictionary | After changing speaker IPs, TuneIn station keys, or Blocky station picker / Explorer Sonos names stale | No |
| 10 | `onkyo` | Onkyo AVR | Re-read `onkyo:` in `config.yaml`; **TCP listeners stop/start** | After receiver IP change, adding/removing a zone, or Onkyo volume/power UI stuck after config edit | **Onkyo** |
| 11 | `rfx_native` | Native RFX (433 MHz) | Re-read `rfxcom:` + `native_rfx:` in `config.yaml`; rebuild RF translation maps | After editing virtual RFX devices or USB path, or 433 MHz switches not responding to mapped idx | No |
| 12 | `epson` | Epson projector | Re-read `epson:` in `config.yaml`; projector idx metadata | After changing projector IP in `config.yaml` or cinema projector switch misnamed/offline in UI | No |

**Modal layout:** numbered list 1–12; checkbox + **bold label** + grey **summary** line + grey **When:** line; ⚠ icon when row 6, 7, or 10 selected (bridge/TCP recycle). **Select all** / **Clear** at top — no bundle shortcuts.

**Note:** Row **8** (`config_yaml`) and rows **9–12** all read from `config.yaml`; handler may re-read the file once if multiple are selected. Row 8 intentionally **excludes** integration blocks covered by 9–12 so operators can reload sauna/schedule without Sonos/Onkyo/RFX/Epson recycle.

**Full reload still includes (not in the 12):** `config_hardware.yaml` (GPIO/SHT11); `wanos-nvram.json`; full `rebuild_core_metadata()` orphan pass; post-reload passive sweep. **`.env` / auth secrets** — service restart. **`entity_registry.auto.yaml`** — never a disk read on reload (runtime births).

**When to use Full reload:** after `wanos-sync` deploy, editing **several** YAML files at once, changing **GPIO/SHT11**, NVRAM/counters, or when you don't know which slice is stale — accepts ~15s Hue outage + integration recycle.

#### Not in modal (operator cannot hot-reload)

| Item | Why |
|------|-----|
| `entity_registry.auto.yaml` | Runtime births / freeze — not a config read path |
| `.env` / JWT secrets | Process environment — **service restart** |
| `config_lab.yaml` | Lab/sim profile — separate from production reload path |

---

### API → minimal scope mapping (after G6)

| Writer | Today | Target `scopes` |
|--------|-------|-----------------|
| `POST/PUT/DELETE /api/automations` | full (every rule save) | **Defer** reload until Automations **Save config**; then `automations` |
| Events CRUD | full | `events` (+ `automations` if listener rules reference changed rules) |
| `PUT /api/soft-hide` | full | `soft_hide` |
| `PUT /api/auto-off-timer` | `timers_types` | `timers_types` *(keep)* |
| Hue preset CRUD | ✅ B10G Part D | `hue_presets` only |
| Z-Wave config save | full | `zwave_map` |
| Admin **Full reload** | full | `mode: "full"` |

**First implementation:** **`hue_presets` API path** ✅ **B10G Part D** (handler fast-path + Z-Wave ignore + scope alerts). **G6:** Admin 12-checkbox modal + remaining scoped writers (see § Reload alerts follow-up).

---

### Reload alerts — G6 follow-up (after B10G Option A)

**B10G ✅:** writers that still **full-recycle** without `scope` use the **`full`** alert row ([`pipeline.md`](pipeline.md) § B10G). **G6 must migrate each writer atomically:** add `scope` (or `mode`/`scopes`) to dispatch **+** scoped handler branch **+** matching alert row — never intent-specific alerts while handler still full-recycles.

**Additional alert rows (ship with G6 when handler scoped)** — same 3 levels as B10G (`info` / `success` / `error`); exact strings for T4-C suppress:

| Scope key | In-progress (`info`, 🔄) | Complete (`success`, 🟢) | Failed (`error`, `ERROR:`) |
|---|---|---|---|
| **`automations`** | `🔄 Reloading automations…` | `🟢 Automations reloaded.` | `ERROR: Automations reload failed: …` |
| **`events`** | `🔄 Reloading events catalog…` | `🟢 Events catalog reloaded.` | `ERROR: Events catalog reload failed: …` |
| **`soft_hide`** | `🔄 Reloading hidden devices…` | `🟢 Hidden devices reloaded.` | `ERROR: Hidden devices reload failed: …` |
| **`zwave_map`** | `🔄 Reloading Z-Wave map…` | `🟢 Z-Wave map reloaded.` | `ERROR: Z-Wave map reload failed: …` |

*(B10G table already locks **`full`**, **`hue_presets`**, **`timers_types`** — [`pipeline.md`](pipeline.md) § B10G.)*

**G6 API migration (reminder):** when each row above lands, update the writer dispatch from bare `{ source: "api" }` to `{ source: "api", scope: "<id>" }` (or scoped modal `scopes[]`) **in the same PR** as the handler branch and alert row.

---

### Dependencies (enforce in UI + handler)

* `config_yaml` (row 8) reloads runtime `config.yaml` blocks only — **does not** imply Sonos/Onkyo/RFX/Epson recycle (rows 9–12).
* `hue_maps` ⊃ implies Hue bridge recycle; independent of `hue_presets`.
* `zwave_map` ⊃ Z-Wave listener reset — do **not** fire on `automations` / `hue_presets` alone.
* `events` may require `automations` if engine reads cross-linked rule names — handler may auto-add or document order.
* Selecting **only** `hue_presets` must **not** stop Hue bridge (operator expectation after split-file work).

---

### Not this item

* Hue live color/bri truth vs bridge → **G2**.
* Blocky save chrome / Library polish → **B10F** ✅.
* B10G overlay **2** load checklist itself (reuse for Save config; do not respec).
* Explorer Hue preset duplicate-settings → **B10M**.
* Replacing `wanos-sync` — sync remains file transport; reload applies RAM.

**G6 DoD:** Admin shows **Full reload** (today’s behaviour, labelled) + **Scoped reload** modal with **12** checkboxes (summaries + when per row; no bundles). Automations: rule save does **not** full-recycle; **Save config** + dirty leave-modal; reload uses overlay-2-style steps/timings; scoped `automations` only (no Hue torn-down / Onkyo stopped / Z-Wave remap). Hue preset CRUD: scope 5 only (handler + alerts — ✅ **B10G Part D**). Soft-hide / timers saves: scopes 3 / 4 only. Full reload still remaps all integrations + remaining YAML. API callers migrated to minimal scopes **with matching scope-specific reload alerts** (see § Reload alerts — G6 follow-up). Pi smoke + docs. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G7 — Integration log tag prefixes 🔜 TODO

**Origin:** inbox **2026-08-11**. Size **low**.

* Hue logs use `[HUE]`; Onkyo lines like `Onkyo Bridge stopped.` lack a bracket tag.
* Normalize integration lifecycle / bridge lines to a consistent `[Onkyo]` (and audit peers for the same gap).

**Not this item:** device-ref shape → **C9** (done); Automations CRUD INFO → **B10F** item 11 ✅.

**G7 DoD:** Onkyo bridge start/stop (and peers audited) use `[Onkyo]`-style tags in `wanos.log`; Pi smoke one reload/start path. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G8 — Boot autostart timing (integrations “disabled” ~30s) 🔜 TODO

**Origin:** operator inbox **2026-08-12** + bootlog analysis. Size **mid**. **Separate from B10G** (Automations overlays / NOT CONNECTED) and **B10H** ✅ (Automations cold-load shorten). Pipeline detail → [`pipeline.md`](pipeline.md) § **G8**.

**Problem:** With `WANOS_AUTOSTART=true`, Admin shows integration master switches **DISABLED** for **~26–30s** after HTTP/SSE is online. Bootlog: +5s autostart delay; sync `load_config()` in simulator blocks event loop ~10s; ten separate toggle events → staggered SSE updates (~11s between first and rest). `*_integration_enabled` defaults **false** in `SystemState`; bridges may already be running from `lifespan`.

**Ship:** **Option A + Option B** in one PR. **Out of scope:** persist last-known enabled flags to NVM (separate design decision). **Manual** enable after network-failure disable (yellow DISABLED while switch ON; missing turned-ON bell) → **G14** — do not duplicate here.

### Option A — shorten real enablement (backend)

| Lever | Where |
|---|---|
| Offload `load_config()` | `hardware/simulator.py`, `core/event_handlers/system_handlers.py` — `asyncio.to_thread` |
| Single `MASTER_START` event | `main.py`, new handler — atomic flags, one broadcast |
| Trim / overlap 5s autostart delay | `main.py` `delayed_autostart` |
| Non-blocking Sonos / Onkyo `start()` | `core/event_handlers/integration_handlers.py` — `create_task` |
| Boot timing logs | Master Start → each flag true |

Kickoff: profile `on_state_changed` if gap persists after thread offload.

### Option B — honest Admin UX

| Lever | Where |
|---|---|
| `system.autostart_in_progress` | `core/models.py`, `main.py`, SSE `system` domain |
| Admin **STARTING** / **ARMING** states | `frontend/admin.html`, `app.js` |
| Z-Wave “arming” copy | Match defer-until-MQTT behaviour |

**G8 DoD:**

- [ ] Option A: measurable shorter time from HTTP online to all intended `*_integration_enabled` true on Pi (baseline = bootlog **2026-08-12**).
- [ ] Option B: Admin shows **STARTING** (not **DISABLED**) during autostart; Z-Wave defer shows **ARMING** until auto-recover.
- [ ] Pi smoke: full `wanos` restart with `WANOS_AUTOSTART=true`; Admin opened within first 30s — no misleading “all disabled” without starting indicator.
- [ ] **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## Inbox 2026-08-14 — five new bridges (verbatim, all five ships)

> - 5 integrations, each to be done seperately, not in the same code run - but in this order
>
> 🌡️ Honeywell Home Heater (Thermostats & Evohome)
> The Library: somecomfort (for Total Connect Comfort), evohomeclient (for multi-zone Evohome hardware), or aiolyric (for Resideo Lyric lines).
> How it works: These libraries handle login states for Resideo’s developer platform and allow you to read room target setpoints, ambient temperatures, and toggle HVAC firing states over HTTPS.
>
> ⚡ HomeWizard (Energy Monitoring)
> The Library: python-homewizard-energy
> How it works: This is an asynchronous client wrapper built for their Local API v1/v2. It reads metrics directly from your HomeWizard P1 Meter, Wi-Fi kWh meters, or Energy Sockets via rapid local HTTP/JSON hooks without touching the cloud.
>
> ❄️ Samsung Airco (Climate Control)
> The Library: python-smartthings
> How it works: Modern Samsung residential HVAC systems channel telemetry entirely through the SmartThings Cloud API. This library uses a REST client with bearer tokens to manage setpoints, blade adjustments, and power flags. Note: If you have an older generation unit (pre-2018), community libraries like samsungrac can handle direct local token handshakes over TCP port 8888 or 2878.
>
> ☀️ SMA (Solar Inverters)
> The Library: pysma or native pymodbus
> How it works: * pysma communicates asynchronously directly with the built-in Webconnect/WebUI server on modern Sunny Boy and Tripower inverters.
> Alternatively, because SMA natively adheres to the SunSpec Modbus TCP standard (Port 502), you can drop standard pymodbus into a background logic service to fetch live grid production variables directly.
>
> 🍳 HomeConnect (Bosch / Siemens / Neff Appliances)
> The Library: homeconnect or aiohomeconnect
> How it works: This library interfaces with the official BSH Home Connect REST API. It establishes a local Server-Sent Events (SSE) stream connected to their cloud servers, allowing your Python code to listen for real-time oven temperatures, dishwasher states, or laundry cycle updates.

**Locked for all five:** **one integration per PR / code run**; order **G11 → G9 → G10 → G12 → G13** (operator reordered **2026-08-20**); do not combine. Size **high** each. Default sequence: after **G4**, before **F**. Config/creds/IPs/device maps → home pack (**P**). **Library pick stays inside each phase** (G9/G11/G12/G13 kickoff) — **not this triage**. Admin enable + Explorer/Blockly surface + G6 reload row: **assess at that ship’s kickoff**. Shared procedure (do not copy into each stub): [`docs/integration-playbook.md`](../integration-playbook.md).

---

## 📋 G9 — Honeywell Home (thermostats / Evohome) 🔜 TODO

**Origin:** operator inbox **2026-08-14**. **2nd of 5.** Own ship. After **G11**.

**Operator request (verbatim):**
> - 5 integrations, each to be done seperately, not in the same code run - but in this order
>
> 🌡️ Honeywell Home Heater (Thermostats & Evohome)
> The Library: somecomfort (for Total Connect Comfort), evohomeclient (for multi-zone Evohome hardware), or aiolyric (for Resideo Lyric lines).
> How it works: These libraries handle login states for Resideo’s developer platform and allow you to read room target setpoints, ambient temperatures, and toggle HVAC firing states over HTTPS.
>
> *(Plus HomeWizard, Samsung, SMA, HomeConnect — full inbox text in § Inbox 2026-08-14.)*

**Intent:** Bridge Resideo / Honeywell Home — read room setpoints, ambient temp, HVAC firing over HTTPS.

**Playbook:** follow [`docs/integration-playbook.md`](../integration-playbook.md); this stub is G9-only (library, devices, C18 row).

**Library:** `somecomfort` | `evohomeclient` | `aiolyric` — **in-scope of G9 kickoff** (not now).

**G9 DoD:** One Honeywell/Evohome path live on Pi; not bundled with G10–G13. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G10 — HomeWizard energy 🔜 TODO

**Origin:** operator inbox **2026-08-14**. **3rd of 5.** Own ship. After **G9**. **Not** same run as G9/G11+.

**Operator request (verbatim):**
> - 5 integrations, each to be done seperately, not in the same code run - but in this order
>
> ⚡ HomeWizard (Energy Monitoring)
> The Library: python-homewizard-energy
> How it works: This is an asynchronous client wrapper built for their Local API v1/v2. It reads metrics directly from your HomeWizard P1 Meter, Wi-Fi kWh meters, or Energy Sockets via rapid local HTTP/JSON hooks without touching the cloud.
>
> *(Full five-integration inbox text in § Inbox 2026-08-14.)*

**Intent:** Local API v1/v2 via `python-homewizard-energy` — P1 / Wi-Fi kWh / Energy Sockets; no cloud.

**Playbook:** follow [`docs/integration-playbook.md`](../integration-playbook.md); this stub is G10-only.

**G10 DoD:** HomeWizard metrics in WanOS on Pi; own ship. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G11 — Samsung SmartThings / Airco 🔜 TODO — kickoff **locked 2026-08-20**

**Origin:** operator inbox **2026-08-14**; kickoff Q&A **2026-08-20**. **1st of 5** (operator moved ahead of G9/G10). Own ship.

**Operator request (verbatim 2026-08-14):**
> - 5 integrations, each to be done seperately, not in the same code run - but in this order
>
> ❄️ Samsung Airco (Climate Control)
> The Library: python-smartthings
> How it works: Modern Samsung residential HVAC systems channel telemetry entirely through the SmartThings Cloud API. This library uses a REST client with bearer tokens to manage setpoints, blade adjustments, and power flags. Note: If you have an older generation unit (pre-2018), community libraries like samsungrac can handle direct local token handshakes over TCP port 8888 or 2878.

**Operator kickoff (verbatim 2026-08-20):**
> kickoff G11 - Samsung Smartthings integration - currently I only have 1 device there: an airco unit
>
> Q1: move G11 before G9
> Q3: power: setpoint, hvac mode, temp & humidity
> Q4: C (ON/OFF + mode + setpoint)
> Q5: 810xx is ok
> Q6: A - is it possible to track power consumption as well? (currently in Watt & total in kWh)?
> Q7: yes, all integrations should have their own checkbox
> Q8: don't have it yet, guide me how to create this

**Playbook:** follow [`docs/integration-playbook.md`](../integration-playbook.md); this stub is G11-only.

### Locked decisions (2026-08-20)

| Topic | Decision |
|---|---|
| **Sequence** | **G11 first** among G9–G13 (operator override **2026-08-20**). Still one ship; not bundled with G9/G10. |
| **Devices in scope** | **1** SmartThings device today: Samsung **airco / climate** unit. |
| **Protocol** | **SmartThings Cloud REST API** only. **`samsungrac` / local TCP — out of scope.** |
| **Library** | **`pysmartthings`** (PyPI; inbox “python-smartthings” = informal name). Pin to **last release compatible with Pi Python** at implement (v4.x requires **3.13+**; v3.7.x requires **3.12+** — confirm Pi venv before pin). **Fallback:** thin **`aiohttp`** client against public REST if no compatible wheel. |
| **Auth — production** | **OAuth 2.0 refresh-token flow** (SmartThings-recommended for ongoing access). Tokens in **`.env`** / home pack — not git. |
| **Auth — discovery** | **PAT** acceptable for **initial device/capability discovery only** (see § PAT guide below). New PATs expire in **24 h** — not a production credential. |
| **IDX band** | **`810xx`** — **`81001`** = airco climate entity (only device today). |
| **Entity prefix** | **`climate.samsung.<slug>`** (from display name via registry birth). |
| **Bridge kind** | **Mixed / commandable climate** — C18 applies to outbound power / mode / setpoint commands. |
| **Commandable** | **Power** on/off · **cooling setpoint** (16–30 °C) · **HVAC mode** (`cool` / `dry` / `wind` / `auto` / `heat`) |
| **Read-only telemetry** | **Current temp** · **humidity** · **instant W** · **cumulative energy (Wh→kWh)** |
| **Power consumption** | **Yes** — `powerConsumptionReport.powerConsumption`: `power` (W) + `energy` / `persistedEnergy` (Wh). Track on idx **81001** + sensor history. |
| **Explorer Control** | **Option C:** ON/OFF + **HVAC mode selector** + **setpoint** control. Show current temp / humidity as read-only alongside controls. |
| **History** | **Yes** — at minimum **ON/OFF**; plus **setpoint**, **mode**, **temp**, **humidity** when present; plus **W / kWh** if device exposes them. |
| **Blockly** | Existing **`HUB_STATE_CHANGED`** pickers for ON/OFF / level where applicable; **no new block types** in G11 unless implement discovers a gap (assess then — default: metadata-only appearance). |
| **Log tag** | **`[Samsung]`** |
| **G6 scoped reload** | **Yes** — scope id **`samsung`**. Adds **row 13+** to G6 modal catalog when G6 ships (or ships with G11 if G6 lands first). Recycles Samsung bridge (stop → remap → poll restart). Scope alert row: `🔄 Reloading Samsung SmartThings…` / `🟢 Samsung SmartThings reloaded.` / `ERROR: Samsung SmartThings reload failed: …`. Full reload also recycles. |
| **Force policy** | **Ask at implement** — default **no force** until kickoff follow-up; do not copy Epson OFF-only silently. |
| **Product type (D1)** | **`climate`** — intrinsic read-only on Timers & types. |

### C18 success / fail row (locked at kickoff — implement against chosen library)

| Integration | Success | Fail |
|---|---|---|
| **Samsung SmartThings** | REST command **`POST /v1/devices/{id}/commands`** returns **HTTP 2xx** (body not parsed beyond status) | Non-2xx; exception; no device id / no session / empty payload; integration disabled |

Echo `origin: "samsung"` in `_INBOUND_ORIGINS`. Silent skip = fail.

### PAT guide (discovery only — operator **2026-08-20**)

Use a PAT to discover device id + capabilities before OAuth wiring. **Do not** rely on PAT for production WanOS.

1. Open **[https://account.smartthings.com/tokens](https://account.smartthings.com/tokens)** and sign in with your **Samsung account** (same account as the SmartThings app).
2. Click **Generate new token**.
3. **Name:** e.g. `WanOS discovery` (any label).
4. **Authorized scopes** — minimum for discovery:
   - **`r:devices:*`** — list devices + read status
   - **`w:devices:*`** — send test commands (optional for discovery smoke)
   - **`r:locations:*`** — list locations (needed to find device location)
5. Click **Generate Token**.
6. **Copy the token immediately** — it is shown **once only**. Store in Pi `.env` as e.g. `SMARTTHINGS_PAT=…` (never commit).
7. **Expiry:** newly issued PATs are valid **24 hours**. Use for discovery / Pi smoke only; production ship uses **OAuth refresh** (G11 implement).

**Quick discovery curl** (replace `{PAT}` and `{DEVICE_ID}` after listing devices):

```bash
curl -s -H "Authorization: Bearer {PAT}" https://api.smartthings.com/v1/devices
curl -s -H "Authorization: Bearer {PAT}" https://api.smartthings.com/v1/devices/{DEVICE_ID}/status
```

Second call reveals capabilities (temperature, humidity, switch, thermostatMode, thermostatSetpoint, powerMeter, etc.) — locks power-consumption answer for your unit.

### Device discovery (Pi PAT, **2026-08-20** — verified)

**Airco (G11 in-scope):**

| Field | Value |
|---|---|
| **deviceId** | `dc46cc64-2654-06d9-5e06-c4203668aa64` |
| **label** | `buro-cinema` |
| **name** | Samsung Room A/C |
| **type** | OCF · `AirConditioner` · presentation `DA-AC-RAC-000003` |
| **locationId** | `a42f8c0e-c3d4-46da-a82e-62d528aaa226` |
| **executionContext** | `CLOUD` |

**Capabilities relevant to locked G11 scope (main component):**

| Capability | Role |
|---|---|
| `switch` | Power on/off |
| `airConditionerMode` | HVAC mode (Samsung AC — not generic `thermostatMode`) |
| `thermostatCoolingSetpoint` | Target setpoint |
| `temperatureMeasurement` | Current temp |
| `relativeHumidityMeasurement` | Humidity |
| `powerConsumptionReport` | **Power present** — unlocks W / energy history (parse at status poll) |

**Also on device (out of G11 v1 command scope unless operator expands later):** `airConditionerFanMode`, `fanOscillationMode`, air-quality/dust/odor sensors, `audioVolume`, filters, SPI/optional modes, etc.

**Second account device (not G11):** Siemens dishwasher `Afwasmachien` (`deviceId` `e40db3c2-727e-4ce6-8739-844c32798418`) — **G13 / HomeConnect** territory. Do **not** bridge in G11.

**Status poll (Pi PAT, `info.log` **2026-08-20** — verified):**

| Attribute | Live value | Notes |
|---|---|---|
| **Power** | `switch` = **off** | Command: `on` / `off` |
| **Mode** | `airConditionerMode` = **cool** | Supported: **`cool` · `dry` · `wind` · `auto` · `heat`** (`availableAcModes` was null — use `supportedAcModes`) |
| **Setpoint** | `coolingSetpoint` = **23 °C** | Range **16–30 °C** via `custom.thermostatSetpointControl` |
| **Temp** | **23 °C** | `temperatureMeasurement` |
| **Humidity** | **52 %** | `relativeHumidityMeasurement` |
| **Instant power** | **`power` = 0 W** | Expected while OFF |
| **Cumulative energy** | **`energy` = 769530** | SmartThings convention = **Wh** → **769.53 kWh**; also `persistedEnergy` = 769530. Map both W + kWh into WanOS history. |

**Also live (out of G11 v1 command scope unless expanded later):** fan `auto` (modes: auto/low/medium/high/turbo); oscillation `horizontal`; optional mode `off` (incl. windFree / sleep / quiet / …).

**Disabled capabilities** (ignore for ship): air quality / dust / odor sensors, SPI, remote-control status, DRLC, several filter extras — listed under `custom.disabledCapabilities`.

### Open at implement (not blockers for kickoff)

* Pi Python version → **`pysmartthings` pin** vs aiohttp fallback.
* OAuth client registration (SmartThings developer workspace) — step-by-step in `docs/integration_samsung.md` at ship.
* Confirm energy unit display (Wh → kWh) in Explorer History / Control readouts.
* Poll interval default (propose in config YAML comment at implement).
* Stale cloud reads (CLOUD OCF RAC — monitor on Pi smoke; `reportStateRealtime` is **disabled** on this unit).

**G11 DoD:** One Samsung airco (`buro-cinema`, idx **81001**) live on Pi via SmartThings Cloud; Explorer ON/mode/setpoint + temp/humidity; history for ON/OFF + climate attrs + **power W + energy kWh from `powerConsumptionReport`**; C18 on commands; Admin enable + `[Samsung]` logs; G6 scope **`samsung`** (handler + alerts; modal row when G6 ships); OAuth refresh for ongoing auth; no `samsungrac`; dishwasher not in this ship. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G12 — SMA solar inverters 🔜 TODO

**Origin:** operator inbox **2026-08-14**. **4th of 5.** Own ship. After **G11**.

**Operator request (verbatim):**
> - 5 integrations, each to be done seperately, not in the same code run - but in this order
>
> ☀️ SMA (Solar Inverters)
> The Library: pysma or native pymodbus
> How it works: * pysma communicates asynchronously directly with the built-in Webconnect/WebUI server on modern Sunny Boy and Tripower inverters.
> Alternatively, because SMA natively adheres to the SunSpec Modbus TCP standard (Port 502), you can drop standard pymodbus into a background logic service to fetch live grid production variables directly.
>
> *(Full five-integration inbox text in § Inbox 2026-08-14.)*

**Intent:** Live grid production from Sunny Boy / Tripower.

**Playbook:** follow [`docs/integration-playbook.md`](../integration-playbook.md); this stub is G12-only.

**Library:** `pysma` (Webconnect) vs `pymodbus` SunSpec TCP 502 — **in-scope of G12 kickoff** (not now).

**G12 DoD:** SMA production in WanOS on Pi; own ship. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G13 — HomeConnect (Bosch / Siemens / Neff) 🔜 TODO

**Origin:** operator inbox **2026-08-14**. **5th of 5.** Own ship. After **G12**.

**Operator request (verbatim):**
> - 5 integrations, each to be done seperately, not in the same code run - but in this order
>
> 🍳 HomeConnect (Bosch / Siemens / Neff Appliances)
> The Library: homeconnect or aiohomeconnect
> How it works: This library interfaces with the official BSH Home Connect REST API. It establishes a local Server-Sent Events (SSE) stream connected to their cloud servers, allowing your Python code to listen for real-time oven temperatures, dishwasher states, or laundry cycle updates.
>
> *(Full five-integration inbox text in § Inbox 2026-08-14.)*

**Intent:** BSH cloud REST + SSE — oven / dishwasher / laundry cycle state (which appliances = **G13 kickoff**, not now).

**Playbook:** follow [`docs/integration-playbook.md`](../integration-playbook.md); this stub is G13-only.

**Library:** `homeconnect` | `aiohomeconnect` — **in-scope of G13 kickoff** (not now).

**G13 DoD:** HomeConnect appliances in WanOS on Pi; own ship. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## 📋 G14 — Manual integration enable status + ON alert 🔜 TODO (assess)

**Origin:** operator inbox **2026-08-15**. Size **mid**. Admin integration rows — **not** G8 boot autostart (boot STARTING/ARMING stays G8). **Not** G6 reload.

**Operator request (verbatim):**
> when Sonos (or possibly any other) integration is disabled (because of previous network failure, eg), and I manually enable it, the yellow disabled status stays for a good number of seconds while the switch is green and ON - the status in this case should be "enabling" or something to that effect. Also, I see a bell notification for the disabling of the Sonos ("Sonos connection lost after 3 retries. Integration disabled.") but I don't see the "Sonos Integration turned ON" after it successfully does turn on (only then the status should change from "enabling" to "Live". assess first wether this is only for sonos integration or the case for others as well - propose changes

**Locked triage intent:**

* **Assess first (kickoff):** Sonos-only vs **all** integrations that can disable after network failure. Propose one pattern; do not assume Sonos-only.
* While enabling: status **enabling** (not yellow disabled) even if the switch is already green/ON.
* After success: status **Live**; bell **turned ON** (parity with the existing disable bell).
* Reuse G8 **STARTING** copy/states if kickoff says they are the same UX — do not ship a second vocabulary without asking.

**Out of scope:** G8 boot delay; G6 Save config; persist enabled flags to NVM.

**G14 DoD:** Assess (Sonos vs all) recorded; enabling → Live + ON bell as decided; Pi smoke manual enable after disable. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

