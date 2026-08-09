# ⚡ WanOS Phase G — Integrations

Integrations reliability — Hue color/state truth, Epson projector power truth, and OWM outside climate poll.

**Status:** Spec **LOCKED** (intent). G2 assess-on-Pi first; G1 analysis-gated; **G3** config anytime.

**Related:** Sequence → [`pipeline.md`](pipeline.md). Blocky Hue **editor** bugs stay **B10A** ([`phaseB-blocky.md`](phaseB-blocky.md)); soft-hide picker → **B10C** ✅. This phase is **runtime** bridge ↔ WanOS state/UI (+ OWM poll).

---

## Subphases

| Subphase | Focus |
|---|---|
| **G2 — Hue state** | Boot + live color/bri truth; UI must match bridge |
| **G1 — Epson boot** | `get_power_state` when safe |
| **G3 — OWM poll** | Outside temp/hum every **10′** (was 30′) |

Pipeline may run **G2 before G1** if daily color lies hurt more than Epson boot lies. **G3** is config-only and may ship anytime.

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

**G2 DoD:** After WanOS restart, Explorer color matches bridge for ON lights with color. After changing color on the Hue app, WanOS state/UI update without a WanOS command. ON-only automation still leaves color unchanged. Pi smoke + no false FFD180-as-truth.

---

## 📋 G1 — Epson `get_power_state` at boot 🔜 TODO

* Implement Epson **get_power_state** at boot.
* Review when it is correct to call for **reliable** results (warm-up, network, projector ready).

**No code until analysis** — see Epson integration docs / code when implementing.

**to be checked:** call timing constraints.

**G1 DoD:** Boot path queries power when safe; documented when *not* to call; Pi smoke shows consistent Epson state after restart.

---

## 📋 G3 — OWM outside poll interval 🔜 TODO

**Origin:** operator request **2026-08-09**.

* Only production outside source: OWM **`30001`** / `sensor.temp_hum.outside_temp_hum` (`config.yaml` `weather.poll_interval_mins`).
* Change **30 → 10** minutes. Lab `outside_tick` unchanged.

**G3 DoD:** Live OWM climate refresh ≤10′; Pi smoke outside temp/hum updates on that cadence.
