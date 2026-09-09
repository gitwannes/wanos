# WanOS Phase S — Sauna plant (vent + start gate)

Sauna ventilator cutover to Library + Timers & types, and door closed-duration start lock. Not Blocky feature work (**B**); not general shell chrome (**C**). Broader “sauna/IR hardcoded → rules” assess remains **B17**.

**Status:** **S1** kickoff in progress (**2026-09-08**). No code until operator says **implement** / **ship** / **patch**.

**Product home (after ship):** [`docs/sauna-ir.md`](../sauna-ir.md). Sequence → [`pipeline.md`](pipeline.md).

**DoD convention:** Last DoD = audit & update ALL `docs/**/*.md` (and root README) against shipped behavior.

---

## Subphases

| Id | What | Status |
|----|------|--------|
| **S1** | Strip hardcoded sauna vent automation + door closed ≤5 min start gate (same ship) | Kickoff |

---

## Operator requests (verbatim)

**2026-09-08 — vent after sauna / door lock (assess thread):**

> - does the sauna ventilator auto-start after the sauna ends? what are the constraints?
> - add an additional lock: the sauna door must be opened maximum 5 minutes prior to starting the sauna - in other words: if the sauna door is open for more than 5 minutes: block the starting - change the "cannot start" message which already exists
> no code, assess first

**2026-09-08 — corrected door wording:**

> door sauna: my wording was inverted, I meant this: if the sauna door is CLOSED for more than 5 minutes: block the starting - change the "cannot start" message which already exists

**2026-09-08 — operator owns vent rules; strip hardcoded:**

> I will creat an automation rule for the ventilator: when the sauna turns off, the ventilator starts in 10 minutes
> the ventilator OFF then sits in "Timers & types": I will configure an auto-off time
> this will rule out all hardcoded code for the sauna ventilator: confirm

**2026-09-08 — message + locks for S1:**

> change to "Cannot start sauna, open sauna door first and check if all is ok"
> …
> 1: ship code now, I'll make sure the needed rules are in place
> 2: remove all - 8577 was an old domoticz idx and just lives as comment now, remove
> 3: yes, remove those - also remove "sauna timer expired"
> 4: give it a new letter
> 5: kickoff now, I'll ask to implement when ready (no code just yet)
> 6: same ship

---

## S1 — Vent strip + door start gate

### Intent

1. **Vent:** Remove all hardcoded post-`SAUNA_OFF` ventilator wait/run automation. Operator provides Library rule (Sauna OFF → delayed ON) + Timers & types auto-off for `zwave.vent.sauna`. Code must not double-fire.
2. **Door:** Block `SAUNA_ON` when door is **CLOSED** longer than **5 minutes** (or `door_sauna_closed_since_unix` is null). Keep existing block when door is **OPEN**. Commander message for the closed-too-long case (locked below).

### Locks (confirmed 2026-09-08)

| # | Lock |
|---|---|
| L1 | Operator owns replacement vent behaviour (rule + auto-off); code ship may land while operator ensures rules are in place |
| L2 | Strip **all** hardcoded sauna vent automation paths listed in scope; remove legacy Domoticz IDX **8577** vent writes/comments |
| L3 | Remove catalog events: Sauna ventilator run start, Sauna ventilator run expired, **and** Sauna timer expired (see open Q on internal bus) |
| L4 | New pipeline letter **S** / id **S1** |
| L5 | Door gate + vent strip = **same ship** |
| L6 | Closed-too-long Commander text: `Cannot start sauna, open sauna door first and check if all is ok` |
| L7 | Threshold in **config** (proposed key `sauna.door_closed_max_mins: 5`) |
| L8 | Null `door_sauna_closed_since_unix` → **block** start |
| L9 | No product code until operator commands **implement** / **ship** / **patch** |

### In scope (code + docs — at implement)

**Vent strip**

* `handle_sauna_off` vent wait arming; `handle_vent_wait_expired` / `handle_vent_run_expired`; registry wiring
* `sauna.vent_delay_mins` / `sauna.vent_run_mins` from `config.yaml` + `SaunaConfig`
* `ventilation_state` / `ventilation_deadline` model + Commander WAITING/RUNNING UI + `ventRemainingText`
* Catalog / seed: `VENT_WAIT_EXPIRED`, `VENT_RUN_EXPIRED` (YAML `events:` + `core/event_catalog.py`)
* Any remaining **8577** vent device writes/comments in this path
* Product docs: post-OFF vent = Library + Timers & types (`sauna-ir.md`)

**Door gate**

* Start Gate + bouncer + Commander: CLOSED age &gt; max (or null) → block; OPEN → existing close-door path
* Config `sauna.door_closed_max_mins` (name confirm at implement if needed)
* Banner reason aligned (proposed: `Door closed too long`)
* `sauna-ir.md` §2.1

**Catalog**

* Remove YAML + seed row for **Sauna timer expired** per L3 — **internal timer behaviour open** (Q1)

### Out of scope

* Authoring the operator’s Library rule / Timers & types row (operator)
* Broader Sauna/IR hardcoded → automation assess (**B17**)
* Changing mid-session door grace / pause (30 s) behaviour
* IR start gates beyond existing mutual exclusion

### Open questions (kickoff — no assumptions)

1. **Sauna timer expired:** Today `SAUNA_TIMER_EXPIRED` is a **catalog** SE; the bus still schedules it and `handle_sauna_timer_expired` dispatches **`SAUNA_OFF`** (session soft timer). **IR_TIMER_EXPIRED** is already internal-only (not catalog). Confirm intended meaning of “remove”:
   - **A (recommended):** Remove from pickable catalog / YAML / seed only; **keep** internal `SAUNA_TIMER_EXPIRED` → `SAUNA_OFF` (mirror IR timer).
   - **B:** Something else (say what) — removing the handler without a replacement would leave the session timer unable to end via that path.
2. **Door OPEN Commander line:** Keep existing `Cannot start sauna, please close door`, or use the new L6 string for **both** OPEN and closed-too-long?
3. **Start Gate banner** for closed-too-long: OK with `Door closed too long` (→ `Sauna start blocked: Door closed too long`), or exact alternate text?

### Prereqs

* None blocking kickoff. Operator will place vent rule + auto-off before/at implement.
* **B14** timed Set (already shipped) required for operator’s delayed ON rule — not a code dependency of the strip itself.

### DoD (stub — finalize at implement)

- [ ] Hardcoded vent wait/run path gone; no 8577 vent writes
- [ ] Catalog/seed: vent run events + Sauna timer expired removed per locked Q1
- [ ] Door closed-duration start gate + config + Commander/banner
- [ ] Pi smoke: start blocked when closed too long / null; OPEN still blocked; after `SAUNA_OFF`, vent behaviour follows operator rule + auto-off only
- [ ] **Last DoD:** audit & update ALL `docs/**/*.md` (+ root README) against shipped behavior

---

## Relation to B17

**B17** remains assess-only for other Sauna/IR hardcoded device actions. **S1** is the vent cutover + door start gate only — do not fold full B17 into this ship.
