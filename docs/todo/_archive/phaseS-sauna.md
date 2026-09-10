<!-- --- file: docs/todo/_archive/phaseS-sauna.md -->
# WanOS Phase S — Sauna plant (vent + start gate) — ARCHIVED

Sauna ventilator cutover to Library + Timers & types, and door closed-duration start lock. Not Blocky (**B**); not shell chrome (**C**). Broader “sauna/IR hardcoded → rules” assess remains **B17**.

**Status:** **Done** — track closed **2026-09-10** (Pi smoke OK). Archived from `docs/todo/`.

**Product home:** [`docs/sauna-ir.md`](../../sauna-ir.md) §2.1 (start gate + soft timers) · §2.2 (post-OFF vent) · §3.7.1 (door stamps / Admin Site info). Pipeline → [`../pipeline.md`](../pipeline.md).

---

## Subphases

| Id | What | Status |
|----|------|--------|
| **S1** | Strip hardcoded sauna vent automation + door closed ≤5 min start gate (same ship) | ✅ **Done 2026-09-10** (Pi smoke OK) |

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

**2026-09-09 — vent strip authorize:**

> S1: I've created the needed automations (vent ON 10 minutes after sauna OFF + 180 min auto-off) - check code/config & confirm - if ok: remove hardcode
> 180 min is now configured
> check & remove hardcode sauna vent automation

**2026-09-10 — timer hop + door Qs:**

> 1: IR_TIMER_EXPIRED & sauna timer expired are not used today - I can use sauna off and IR off for that, can I - confirm - if yes: both IR_TIMER_EXPIRED & sauna timer expired can be removed everywhere
> 2: Keep Cannot start sauna, please close door - closed-too-long is another string
> 3: banner "reason"? … proposal ok

**2026-09-10 — close:**

> ok, smokes all ok - close S1

---

## S1 — Shipped summary

### Vent strip (2026-09-09)

Operator: Sauna OFF → Set after 10 min → `zwave.vent.sauna` ON; Timers & types auto-off **180** min. Hub wait/run timers and catalog vent SEs removed. See [`sauna-ir.md`](../../sauna-ir.md) §2.2.

### Door start gate + timer hop (2026-09-10)

* Config `sauna.door_closed_max_mins: 5`; null `doors.sauna_closed_since_unix` blocks start.
* Start Gate + bouncer + WISC: OPEN → `Cannot start sauna, please close door`; closed-too-long → `Cannot start sauna, open sauna door first and check if all is ok`; banner fragment `Door closed too long`.
* Soft timers schedule **`SAUNA_OFF` / `IR_OFF` directly**; `SAUNA_TIMER_EXPIRED` / `IR_TIMER_EXPIRED` removed.
* Door stamps: nested `state.doors` + SSE `doors`; reconcile on every `DOOR_CHANGED` (incl. cold-boot seed). Admin Site info: label from device, timer from stamp.

### DoD

- [x] Hardcoded vent wait/run path gone; no 8577 vent writes — **2026-09-09**
- [x] Catalog/seed: vent run events + Sauna/IR timer expired removed
- [x] Door closed-duration start gate + config + Commander + Start Gate fragment
- [x] Pi smoke: start blocked when closed too long / null; OPEN still blocked; soft timer end → Sauna/IR OFF (+ Library); vent = rule + auto-off — **2026-09-10**
- [x] **Last DoD (docs):** `sauna-ir.md` §2.1/§2.2/§3.7.1; `reference.md`; `sensor_history.md` Site info; phaseB catalog notes — **2026-09-10**

---

## Relation to B17

**B17** remains assess-only for other Sauna/IR hardcoded device actions. **S1** did not fold full B17.
