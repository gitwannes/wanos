# --- file: docs/todo/phaseO-optimization.md ---
# WanOS Phase O — Optimization (WanOS + WLW co-tenancy)

Cross-repo optimization track for shared-host co-tenancy with **be90webserver** (WLW). Not product feature backlog (Blocky / shell / integrations).

**Status:** hold (prereq **Ops7**) · **Size:** high · Sequence id **O1**  
**Pipeline:** [`pipeline.md`](pipeline.md) Sequence **O1**  
**Sibling (be90):** [`C:\data\git\be90webserver\docs\todo\phaseO-optimization.md`](file:///C:/data/git/be90webserver/docs/todo/phaseO-optimization.md) · relative [`../../../be90webserver/docs/todo/phaseO-optimization.md`](../../../be90webserver/docs/todo/phaseO-optimization.md) § **O1**  
**Product reference (canonical analysis + roadmap):** [`../wanos-wlw-cotenancy-architecture.md`](../wanos-wlw-cotenancy-architecture.md)

---

## O1 — WanOS + WLW co-tenancy optimization

Umbrella ship for Tracks A–D in the product MD (A = Ops7 prereq, not coded under O1).

---

## Verbatim (operator)

**2026-11-26:**

> triage this as optimization-track in both repos: cross-link

**Prior (same day — analysis → MD):**

> check wanos + be90webserver repos  
> check cross-functionality; what can be optimized, give insights, architectural plan mode  
> …  
> put this analysis + plan in an MD  
> wanos/docs and pointer in be90webserver/docs  
> filename: wanos-wlw-cotenancy-architecture.md

---

## Scope (from product MD)

| Track | What | Notes |
|---|---|---|
| **A** | Ops7 cutover (wanos host → be90 overlay → combined smoke) | Delivery = **Ops7** / be90 Ops7 — not re-coded here; O waits on Done |
| **B** | Edge hygiene (`/api/` mux smoke, cookie-only assess, `gw.inc` WanOS path inventory, WanOS public-surface assess, H10/H6 combined edge) | Mostly be90 nginx/gateway; WanOS cooperates on entrypoint list |
| **C** | Keep co-tenancy contract current; strip `php7.4` / bridge `3.9` drift at Ops7 close-out; log2ram SIZE joint note | Docs both repos |
| **D** | Post-Ops7 triple-Python smoke; mail-stack decision **before** Phase **E** implement | Assess — no code until kickoff + `implement` |
| **E** | Out of scope for O | Letter product backlog (B88, B26, G9–G13, …) |

**Depends on:** **Ops7** Done (host + WLW overlay smoke).  
**Blocks / informs:** be90 **B30b** already waits on Ops7; WanOS **E** mail design should wait on Track D decision.

---

## Cross-link locks

| Repo | Role |
|---|---|
| **wanos** | Host Ops7; sync SSoT; this phase file; canonical product MD |
| **be90webserver** | Overlay Ops7; gateway/nginx Track B; sibling `phaseO-optimization.md` |

Do **not** maintain a second full analysis copy in `docs/todo/`. Product truth for the review = [`../wanos-wlw-cotenancy-architecture.md`](../wanos-wlw-cotenancy-architecture.md).

---

## Status / DoD (track)

- [ ] Ops7 Done (prereq) — then re-open Sequence **O1** from hold
- [ ] Kickoff locks per sub-ship (B/C/D) before any `implement`
- [ ] Last DoD: audit product MD + both pipelines + sibling phaseO § O1 stay cross-linked

**Out of scope:** Merging repos; moving sync into be90; SSO; `/gw/wanos/` rewrite without WanOS base-path redesign.
