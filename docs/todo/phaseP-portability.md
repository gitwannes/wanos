# ⚡ WanOS Phase P — Other homes / portability

Make WanOS **usable for another house**: engine stays generic; **home-specific** facts live only in clearly marked config (and docs). Today much of Borsbeek is YAML **and** duplicated in Python/HTML.

**Status:** Spec **stub**. **Very low prio** — last in pipeline (after **F** / **B15–B18**). **Assess at kickoff** before any extraction ship.

**Related:** Cursor rule [`.cursor/rules/general-purpose-code.mdc`](../../.cursor/rules/general-purpose-code.mdc). Sauna/IR handlers vs automations → **B17** (subset; do not double-implement). Sequence → [`pipeline.md`](pipeline.md).

**DoD convention:** **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**

---

## Operator request (verbatim)

> create a pipeline item, very low prio, which goal is to make wanos useable for other homes as well, in which case it needs to be very clear which config is home-specific - lots of changes need to be made, put the list above, both what you suggested in previous answers and my list in the in-scope -

**Operator list (verbatim, 2026-08-14 Q4):**

> environment-specific = ip address of py, url, username, all idxs, hue key path, all credentials, sauna & ir: sht sensor use, number & config, sauna heater control, etc

**Process lock (2026-08-14 Q3):** when moving hardcoded site facts into config — **propose, ask, do not apply** until operator confirms. Collaboration-standards still win (no unsolicited patches).

---

## Goal

1. A second install can run the **same code** with **different home config**.
2. Operators can see **at a glance** which files/keys are home-specific vs engine.
3. No new hardcodes of the in-scope list (rule already always-on).

**Kickoff first:** inventory + docs (what is home vs engine). Code extraction is **many ships** — split only at kickoff (not this triage).

---

## In scope (home-specific — config **and** current code leaks)

### Operator list

* Pi **IP**, **URLs**, **usernames**
* **All IDX** numbers
* **Hue key path**
* **All credentials**
* **Sauna / IR:** SHT11 use, sensor **count** and wiring/config, **heater control**, and similar plant-specific control

### Config files (correct place today — must stay clearly “home”)

| File | Home content |
|---|---|
| `config.yaml` | `10.32.251.x` (Epson, Sonos, Onkyo), RFX names/hex, OWM `Borsbeek,BE`, MQTT user, kWh/water/PC power links, sauna/IR/bathroom1 PID & times, blinds travel, env schedule clocks, IDX **band** comments |
| `config_hardware.yaml` | GPIO pins, SHT11 count/wiring (sauna high/low, cinema, badk 1e), 3-phase sauna + IR + safety relays, doors, `indicator_lights` Hue IDXs |
| `config_hue.yaml` | Bridge IP, Hue group/device UUIDs |
| `config_zwave.auto.yaml` | Z-Wave node map (Pi-owned) |
| `entity_registry.auto.yaml` | entity_id ↔ idx |
| `automations.auto.yaml` | Rules, hide, auto-off, product types |
| `config_hue_presets.auto.yaml` | Colour presets |
| `config_lab.yaml` | Lab boot seeds keyed to this house’s IDXs |
| `helpers/wanos-sync.config.txt` | Pi host, `wannes`, remote root |
| Bootstrap / sudoers docs | Linux user, unit names |
| `.env` (not in git) | OWM, MQTT password, Hue application key, `SECRET_KEY` |

### Code that still assumes this house (extract or parameterize)

* `state_manager.py` — sauna composite **0.7×20001 + 0.3×20002**, hum from 20001, virtual **20101**; SHT locks `[20001, 20002]`; lab inject `[20001–20004]`
* `logic/history_ids.py` — `SAUNA_CALC_IDX = 20101`
* `hardware/actuators.py` — **topology** fixed: 3 sauna phases + IR + one safety GPIO (pins from config)
* `core/well_known_entities.py` — sauna door/probes, badk 1e vent/hum, Epson, SSR/WISC 5V
* `logic/automation_rules.py` — bathroom1 humidity → `zwave.vent.badk_1e`
* `logic/history_manager.py` — doors **10001 / 10002**
* `core/entity_id_list.py` — IDX band → origin
* WISC / kiosk / Admin lab **HTML/JS** — hardcoded IDXs (`10001`, `51002`, `71036`, `72004`, `71038`, `20001`…, `72001`, …) and house copy
* Helpers: `hue_discovery.py` default IP; sync/bootstrap Pi identity

### Grey (call at kickoff)

* Auth tokens `user` / `kiosk` in `config.yaml`
* Timezone `Europe/Brussels`
* Overlap **B17** (sauna/IR hardcoded → automation assess)
* **G9–G13** new vendor bridges (IPs, tokens, device maps) — home pack when those ships land

---

## Out of scope (this triage)

* Implementing extraction now
* Inventing a second config system or settings UI unless operator asks at kickoff
* Changing Blockly cluster / F / G ships to wait on **P**
* Deleting working Borsbeek config

---

## Assess at kickoff

* Doc shape: which files are “home pack” vs engine (README / `docs/` inventory).
* Ship split (docs-only first vs code).
* Whether well-known eids stay as **names** in code (resolved via registry) vs all plant policy in YAML/rules.
* **B17** vs **P**: B17 may land first; **P** takes leftover plant-in-code.
* Sample `config.yaml` / hardware template without Borsbeek IPs (no secrets).

**P DoD (stub):** Kickoff assess recorded; home vs engine documented; extraction ships (if any) only after operator OK per item. **Last DoD: audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.**
