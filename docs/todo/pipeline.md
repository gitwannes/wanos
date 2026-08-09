# ⚡ WanOS — Implementation pipeline

High-level **what’s next** and where the detailed specs live. This file does **not** hold phase DoD / locked-decision novels — those live in `phaseX-yyy.md`.

**Last updated:** 2026-08-09

---

## How to use

| Band | Meaning |
|---|---|
| **Now / next** | Spec locked; implement when capacity allows |
| **Queued** | Spec exists; schedule after “now” |
| **Ops / Manual** | Operator / site work — stays in this file |

**One detail file per letter.** Pipeline links only to those filenames.

| Letter | Affinity | Detail file |
|---|---|---|
| **B** | Blocky / Blockly / automations | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **C** | Operator shell (Explorer, Admin, History charts, force sweep, HTML names) | [`phaseC-shell.md`](phaseC-shell.md) |
| **D** | Device typing (switch vs light) | [`phaseD-typing.md`](phaseD-typing.md) |
| **E** | Gmail transport (OAuth, outbox, spooler) | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **F** | Public bridge / perimeter security | [`phaseF-security.md`](phaseF-security.md) |
| **G** | Integrations reliability (Hue state, Epson) | [`phaseG-integrations.md`](phaseG-integrations.md) |

**Naming note:** Deny-list decision **D1** in Blocky ≠ phase **D**.

---

## Sequence

```text
1. B10A     Blocky editor trust (Hue / Delete / dirty)
2. C1       Explorer chrome
3. C2       Admin + system pages
4. C5       History graphs (landscape / dew / Y-axis)
5. B10B     user events + rule enable
6. D        switch vs light typing
7. B9A      sensors / thresholds / remove JSON
8. E        Gmail transport / outbox
9. B9B      bathroom + H4/H5/H12  (H5 email needs E)
10. C3      Force ALL-OFF
11. C4      Rename HTML entrypoints
12. G2      Hue color/bri truth (assess → fix)
13. G1      Epson get_power_state (analysis → impl)
14. F       Security bridge (F1→F7 as deployed)
15. Later B multi-flow; HA H1–H3/H6–H11
16. Ops     Inbox below when convenient
```

### Why this order

* **B10A first** — daily Blocky trust bugs; FE-only; unblocks operator confidence before bigger model work.
* **C1 → C2 next** — small shell polish; no schema; ships while Blocky calm.
* **C5 after C2** — History chart UX; same shell letter; phone landscape pain is daily-path; not Blocky/B9A.
* **B10B before B9A** — user events / rule enable are the live scene pain; sensors/JSON removal is larger and can wait.
* **D after B10B / with C2 consumers** — typing benefits Planned Automations and Blocky light/switch wording; not a Blocky editor rewrite.
* **B9A then E then B9B** — compares/sensors first; Gmail transport (**E**) can start early but **B9B H5 email** waits on E; bathroom/H12/H4 sit on B9A primitives.
* **C3 / C4 later** — Admin force-sweep is powerful but not daily-path; HTML renames are mechanical and safer after shell churn settles.
* **G2 before G1** — Hue color lie affects daily Explorer; Epson boot query is analysis-gated and rarer. Swap if Epson pain wins.
* **F when deploying remote access** — independent perimeter track; interleave only when exposing the bridge.
* **Do not fold B10\* into B9\*** — different jobs (trust/events vs sensors/climate). **G2 ≠ B10A** — runtime bridge truth vs Blockly editor chrome.

Near-term = **B10A → C1 → C2 → C5**. Then **B10B** / **D** / **B9A** flexible. **E** may run parallel to B9A; B9B email DoD needs E. **G2** can jump forward if color truth is blocking.

---

## Now / next (pointers only)

| Step | Detail |
|---|---|
| **B10A** | [`phaseB-blocky.md`](phaseB-blocky.md) § B10A — Hue a/b/c · toolbar Delete · dirty leave |
| **C1** | [`phaseC-shell.md`](phaseC-shell.md) § C1 — Hidden filter · favorites |
| **C2** | [`phaseC-shell.md`](phaseC-shell.md) § C2 — Planned Automations · bell · reboot · leave-guards |
| **C5** | [`phaseC-shell.md`](phaseC-shell.md) § C5 — landscape filters · dew point · Y-axis 5°/10% |
| **B10B** | [`phaseB-blocky.md`](phaseB-blocky.md) § B10B — `user_events` · rule `enabled` |
| **D** | [`phaseD-typing.md`](phaseD-typing.md) — infer + override · freeze `entity_id` · 71/72 |

---

## Queued

| Phase | Detail file |
|---|---|
| **B9A** / **B9B** | [`phaseB-blocky.md`](phaseB-blocky.md) |
| **E** | [`phaseE-gmail.md`](phaseE-gmail.md) |
| **C3** / **C4** | [`phaseC-shell.md`](phaseC-shell.md) |
| **G2** / **G1** | [`phaseG-integrations.md`](phaseG-integrations.md) |
| **F1–F7** | [`phaseF-security.md`](phaseF-security.md) |

**Later (still B):** multi-flow one Blockly page; rule-list folder/tag; HA H1–H3, H6–H11 — see [`phaseB-blocky.md`](phaseB-blocky.md).

---

## Inbox — Ops / Manual (2026-08-09)

Not lettered product phases. Unclear parts marked **to be checked**.

### Ops — pull from Pi

| Label | Source (Pi) | Destination (stated) |
|---|---|---|
| REPO1 | `entity_registry.auto.yaml` | `C:\data\git\wanos` |
| REPO2 | `automations.auto.yaml` | `C:\data\git\wanos` |
| STATS | telemetry | `C:\data\OneDrive\data\professional\wanos\logs` |
| LOGS | `wannes@10.32.251.30:/var/log/wanos/wanos*` (rsync) | `C:\data\OneDrive\data\professional\wanos\logs` |

**Open decision — auto.yaml into `git\wanos`?** Overwriting the working tree from Pi can fight local edits / git history.

| Option | Idea |
|---|---|
| **1** | Pull to a **non-repo** dir (OneDrive `…\wanos\pi-pull\`) — **recommended for inspect-Pi** |
| **2** | gitignore `*.auto.yaml` and treat Pi as sole author — **to be checked** vs cutover workflow |

### Read SQLite history DBs on Windows

Copy DBs off Pi (include `-wal`/`-shm` if present) → DB Browser / `sqlite3` / VS Code SQLite. Prefer **copies**, not live files. **to be checked:** exact Pi paths.

### Manual / site

| Item | Notes |
|---|---|
| Background Leak = **0.0 W** | Verify — **check!** |
| Where is the **3-phase kWh meter** connected? | Site / wiring — **manual** |
| Where do the **Pis** get power? | Site / UPS / circuit — **manual** |

*(Hue badkamer red / preset checks → folded into **G2** assess in [`phaseG-integrations.md`](phaseG-integrations.md). Blocky preset picker gap → confirm under **B6C** / **B9A** if still missing.)*

---

## Change log (short)

| When | What |
|---|---|
| 2026-08 | **B0–B8** done on Pi (schema v2, rich actions, soft-hide, auto-off). **B9A/B9B** + **B10A/B10B** specs locked. |
| 2026-08-09 | Intermediary shell/typing + pipeline; letter rename B/C/D/E/F/G. |
| 2026-08-09 | Specs collapsed to `phaseX-yyy.md`; this file = sequence + ops only. |
| 2026-08-09 | Added **C5** History graphs; **G2** Hue state; renamed G file → `phaseG-integrations.md`. |

Detail chronology / DoD checkboxes → [`phaseB-blocky.md`](phaseB-blocky.md).
