# Environmental schedule & system events

**Status:** **shipped** with **B10B+D+E** (**2026-08-10**). Catalog / UI display names below are authoritative.  
**Code keys** (`SUNSET_TRIGGER`, …) stay until a later rename pass (**B15** may demote schedule edges to `origin: user` — deferred).  
**Not in this doc’s ship:** demote schedule edges → [`pipeline.md`](todo/pipeline.md), [`phaseB-blocky.md`](todo/phaseB-blocky.md) § B15.

Same scheduler math as today — clearer admin names and one mental model. No `TWILIGHT_*` aliases in the product story (D1 removed with B10B close-out).

**Authority (implementation):**

| Piece | File |
|---|---|
| Clamp + timer deploy | [`logic/environment_scheduler.py`](../logic/environment_scheduler.py) |
| Sweeper alignment | [`core/event_handlers/system_handlers.py`](../core/event_handlers/system_handlers.py) |
| Catalog UUID + display names | [`core/event_catalog.py`](../core/event_catalog.py) |
| Live clamps / clocks | [`config.yaml`](../config.yaml) `environmental_schedule` |
| Sauna/IR handlers | [`core/event_handlers/sauna_handlers.py`](../core/event_handlers/sauna_handlers.py) |

---

## 1. Deprecated aliases

| What | Target |
|---|---|
| `TWILIGHT_*_TRIGGER` names | Gone from docs/UI; never reintroduce |
| `SCHEDULE_EVENT_ALIASES` / `canonicalize_schedule_event` | **Deleted** with B10B migrator (D1, **2026-08-10**) |
| Family keys / `SCHEDULE_WINDOW_EDGES` | **Deleted** with B10B migrator (**2026-08-10**) |

---

## 2. Three daily windows

| Window | Purpose | START | STOP |
|---|---|---|---|
| **Blinds** | Blinds open for the day | **Blinds open** | **Blinds close** |
| **Morning lights** | Early outdoor/kerst lights | **Morning lights on** | **Morning lights off** |
| **Evening lights** | Outdoor/kerst lights after dark | **Evening lights on** | **Evening lights off** |

Each START/STOP = one **system** catalog event (**SE**) → **at most one** companion automation rule (**SR**; name always equals SE catalog name).  
Sauna / IR are separate (handlers ± optional Blocky).

---

## 3. Catalog display names (locked)

Keep **UUIDs and timing**. UI/catalog labels:

| Catalog / UI name | Meaning | Pre-migration label | `EventType` key (keep for now) |
|---|---|---|---|
| **Blinds open** | Open at clamped morning time | Blinds open | `BLINDS_OPEN_TRIGGER` |
| **Blinds close** | Close at clamped evening time | Blinds close | `BLINDS_CLOSE_TRIGGER` |
| **Morning lights on** | Accent lights on at clock | Morning on | `MORNING_ON_TRIGGER` |
| **Morning lights off** | Those lights off at sunrise | Sunrise | `SUNRISE_TRIGGER` |
| **Evening lights on** | Accent lights on at sunset | Sunset | `SUNSET_TRIGGER` |
| **Evening lights off** | Those lights off at late clock | Evening off | `EVENING_OFF_TRIGGER` |

Name = what the house does. Astronomy belongs in the “when” column, not the title.

**Sun-cycle refresh (not a window edge):** bus type **`SUNRISE_SUNSET_UPDATE`** (was `EXTERNAL_WEATHER_UPDATED`; same UUID). Catalog display **Sunrise/sunset update**. Emitted by OWM on daily sun refresh / boot / enable — not on climate polls.

---

## 4. Where the time comes from

1. **Sun** — sunrise / sunset from OWM (daily).  
2. **Clocks / clamps** — `config.yaml` so actions stay in sane bands.

| Event | Time source | Config |
|---|---|---|
| Morning lights on | Clock | `twilight.morning_on_time` (`06:00`) |
| Morning lights off | Sunrise | — |
| Evening lights on | Sunset (raw) | — |
| Evening lights off | Clock | `twilight.evening_off_time` (`23:00`) |
| Blinds open | Sunrise, clamped | `blinds.morning_open_earliest` / `latest` (`07:00`–`09:00`) |
| Blinds close | Sunset, clamped | `blinds.evening_close_earliest` / `latest` (`16:30`–`22:00`) |

*(Config path keys still say `twilight.*` — product labels do not.)*

---

## 5. Timing rules

*(Blinds + morning skip + evening skip = live math as of **B10F**.)*

```text
blinds_open = max(sunrise, morning_open_earliest)
if morning_open_latest is set:
    blinds_open = min(blinds_open, morning_open_latest)

blinds_close = max(sunset, evening_close_earliest)
if evening_close_latest is set:
    blinds_close = min(blinds_close, evening_close_latest)

# Morning lights — only if sunrise is still after the on-clock
if sunrise > morning_on_time:
    Morning lights on  @ morning_on_time
    Morning lights off @ sunrise
else:
    schedule neither

# Evening lights — only if sunset is still before the off-clock (B10F)
if sunset < evening_off_time:
    Evening lights on  @ sunset
    Evening lights off @ evening_off_time
else:
    schedule neither
```

**Blinds ≠ evening lights:** blinds use **clamped** sun; evening lights on uses **raw** sunset.

### Edge cases (operators)

| Situation | Behaviour |
|---|---|
| Sunrise ≤ morning-on clock | Whole **morning lights** window skipped |
| Sunset &lt; evening-off (normal) | On at sunset → off at clock |
| Sunset ≥ evening-off | Whole **evening lights** window skipped (same pattern as morning; no inverted timers) — **B10F** |
| Blinds open/close inverted by bad clamps | Scheduler does not skip; fix config |

**Sweeper** (active sweeps only): re-dispatch current side of each window (not replay missed edges). Passive/boot sweeps skip time-series alignment.

---

## 6. Way of working

| Goal | Do | Don’t |
|---|---|---|
| Lights on later morning | Raise `morning_on_time` | Duplicate rules |
| Lights off earlier night | Lower `evening_off_time` | Second listener on evening-on |
| Blinds not before 7:30 | Set `morning_open_earliest` | Hardcode times in Blocky |
| Behaviour at evening lights on | Edit the **one** **SR** under that **SE** | Retarget a dashboard user event onto a schedule edge |
| Manual scene (Cinema, GoCosy) | **UE** + **UR**(s) | Attach scene rule to schedule system UUID |

### Automations Library (shipped — B10E)

Detail + icons: [`phaseB-blocky.md`](todo/phaseB-blocky.md) § B10E.

- Left list = **Library**. Buttons: **New rule** | **New user event**.  
- Badges: **UE** (user event, teal) · **UR** (user-event rule, sky) · **SE** (system event, slate) · **SR** (system-event rule, darker slate) · **D** (device rule, amber) · **C** (confirm on **UE** only, rose).  
- **UE** = form only (not Blockly): name; **Appear on explorer** (always shown, default OFF); **Require confirmation** (always shown; **blocked** unless explorer ON; turning explorer OFF while confirm ON **forces confirm OFF**); disable when unused.  
- **SE** = view-only catalog (name + id); **cannot** disable; unused SE = no listening **SR** (not “disabled”) — **no** auto-created SR shell (YAML or UI memory); create **SR** only via **New rule** → When system event → Save. **Show disabled/unused** XOR: SE used↔unused; UE/UR/SR/D enabled↔disabled.  
- **SR** name **always equals** companion **SE** catalog name (API overwrites). One SR max per SE.  
- Sort **UE → UR → SE → SR → D**; When/Fire split user vs system.  
- **Event flags panel:** removed. System events **never** on Explorer (`show_on_dashboard` rejected). Fire-action: unused system not pickable except Sauna/IR ON/OFF.  
- Referenced **UE** (fire-action): cannot disable UE or listening **UR**; Show usages.

### Migration — evening-on listeners (done in B10E)

**Deleted** rules that listened to the old Sunset UUID (now **Evening lights on**). Operator re-creates flows under that single **SE**/**SR**.  
Restore any user scene incorrectly retargeted onto Sunset (e.g. **GoCosy** must listen to the GoCosy **UE** again if it remains a dashboard event). Scratch was intentional — no migrator preserve of Tuinlichten / GoCosy-as-sunset.

---

## 7. Example day (defaults, illustrative)

```text
# Typical
06:00  Morning lights on
08:10  Morning lights off (= sunrise)
08:10  Blinds open
17:00  Evening lights on (= sunset)
17:05  Blinds close (clamped; may differ slightly)
23:00  Evening lights off

# Midsummer (sunrise before 06:00)
(no morning lights)
07:00  Blinds open (earliest clamp)
21:30  Evening lights on
22:00  Blinds close (latest clamp if needed)
23:00  Evening lights off
```

---

## 8. Approval (locked 2026-08-10; shipped)

- [x] Three windows + START/STOP naming  
- [x] Catalog renames: Sunset → Evening lights on; Morning on / Sunrise → Morning lights on / off; Evening off → Evening lights off  
- [x] Drop all Sunset-listening rules in migration; recreate by hand  
- [x] Aliases out of product story; code delete with migrator (D1)  
- [x] Demote schedule edges → user origin remains **B15** (deferred)
- [x] Empty SE: **no** auto-create unused/disabled rule shell (SE view-only in Library from catalog; create SR via **Create System Rule** draft — **B10F** ✅)
- [x] List unused user events (**UE** with no listening **UR**)
- [x] SE / SR list titles = system catalog name (no `system:` prefix; badges mark origin); **SR YAML `name` forced to SE catalog** (bind + boot rewrite — **B10F** ✅)
- [x] Display **Sunrise/sunset update**; EventType **`SUNRISE_SUNSET_UPDATE`** (was `EXTERNAL_WEATHER_UPDATED`; UUID unchanged)
- [x] Evening skip: sunset ≥ evening-off → schedule **neither** evening edge (mirror morning) — **B10F** ✅ with fire-status API

Shipped in **B10E** with B10B+D. Detail DoD: [`phaseB-blocky.md`](todo/phaseB-blocky.md) § B10E. Evening skip + Automations fire-status + SR name bind → § **B10F** ✅.
