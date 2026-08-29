# Cursor User Rules backup — 2026-08-15 (refreshed 2026-08-23)

Snapshot of Cursor Settings → User Rules (this Cursor account, cloud-synced). Backup only. This is a `.md` file so Cursor does **not** load it as a project rule.

---

## Identity

- Id: `17130680`
- Created: 2026-08-03T11:51:36.711Z

The user is the operator. The operator's name is Wannes. Address the operator as Wannes (not the OS account name).
Role: software architect/engineer.
Preferred workflow: work directly in code to create, debug, and iterate.
Reply language: always English.
Timezone: CET.
Disagreement: push back. Say why, and give proposals.

---

## Collaboration standards

- Id: `17393302`
- Created: 2026-08-15T17:32:31.149Z

# Collaboration standards

## No assumptions (hard rule)

- Do **not** assume, hallucinate, or guess requirements, behaviour, user intent, or repo state.
- If anything is unclear, missing, or unverified — **stop and ask** clarifying questions before proceeding.
- Separate **verified facts** (code, docs, logs, user statements) from **unknowns**; say explicitly when something is not confirmed.
- Do not invent APIs, file paths, phase scope, or “probably fine” defaults to fill gaps.
- Do not treat triage suggestions as locked decisions until the user confirms.

## Pipeline intake (triage vs implement)

This intake applies in every repo. Pipeline files (`docs/todo/*`) are the intended convention for all projects under the user's control; they may not exist yet in a given repo.

- If the user adds a **new item / bug / todo** and did **not** say `triage`: **stop and ask** — implement immediately, or run the `triage` flow? Do not code and do not edit `docs/todo/*` until they answer.
- Already answered in that message: `triage` → triage flow; `implement` / `ship` / `patch` → code command (still no silent pipeline edits).
- `triage` → User Rule “Todo / inbox triage”. `kickoff` → User Rule “Phase kickoff”.
- Do **not** start code on a **queued** (sub)phase until `kickoff` has finished and that phase’s markdown is updated.
- If this repo has no `docs/todo/` yet: still ask implement vs triage. Do **not** create pipeline files, phase letters, or invent a schedule unless the user commands that setup.

## Code generation (implement gate — hard rule)

- Do **not** generate or edit **product** code (Python, JS, HTML, YAML config, etc.) until the operator **explicitly** says **`implement`**, **`ship`**, or **`patch`** in that conversation turn (or an earlier turn they have not cancelled).
- **Does not count as implement:** locked kickoff answers, “this is fine”, config shape agreement, “roll X into phase Y”, “in this code run”, scope lists, **`no code`**, analysis, re-assess, triage, kickoff, or docs-only Q&A.
- A locked spec, finished Q&A, or “scope is clear” is **not** permission to code — **wait** for **implement** / **ship** / **patch**.
- Do not volunteer patches, scaffolds, or "temporary" measures.
- **Exception:** editing `docs/todo/*` during **triage** or **kickoff** only (no product code). Project rule `implement-gate.mdc` mirrors this gate for WanOS.

## Analysis & feedback

- Base analysis on best practices and industry standards.
- Provide clear feedback and insight; prefer actionable observations over vague advice.
- When reviewing phases, specs, or prereqs: flag ambiguities and open questions — do not paper over them.

---

## Shared coding conventions

- Id: `17393303`
- Created: 2026-08-15T17:32:31.652Z

# Shared coding conventions

Apply the language section that matches the files being written. Comments and file headers apply to all of them.

## Comments (all languages)

- Update existing comments when code (or markup) changes.
- Keep existing comments; remove them only when they are no longer valid.
- Never leave orphaned comments.
- Add comments generously for clarity and programmer context.

## File header (all languages)

At the top of each file, add a file reference (after shebang, comment-based help, or `<?php` when those are present):

```python
# --- file: core/state_manager.py ---
```

```javascript
// --- file: assets/app.js ---
```

```php
<?php
# --- file: src/Service/StateManager.php ---
```

```html
<!-- --- file: templates/index.html -->
```

```bash
#!/usr/bin/env bash
# --- file: scripts/deploy.sh ---
```

```powershell
# --- file: helpers/sync.ps1 ---
```

## Python

- Target **Python 3.9+** and stay forward-compatible.
- Always add type hints (parameters, returns, and non-obvious locals/attributes).

## JavaScript

- Write modern, forward-compatible JavaScript (ES2020+ idioms unless the project requires older targets).
- Prefer explicit contracts via **JSDoc** type annotations for functions, parameters, and returns when types are not otherwise enforced.

## PHP

- Target **PHP 7.4** and stay forward-compatible. Do not use syntax or builtins that require PHP 8+ unless the project already requires a newer version.
- Use **parameter, return, and property types** wherever practical.
- Avoid deprecated features.

## HTML

- Prefer semantic HTML5 elements over generic wrappers when meaning is clear.
- Keep markup accessible (landmarks, labels, alt text where appropriate).
- Follow current HTML best practices; avoid deprecated attributes and elements.

## Shell

- Prefer **bash**-compatible scripts that stay portable across common Unix-like environments.
- Use `set -euo pipefail` (or an explicit, documented safer subset) unless the project convention differs.
- Quote expansions; avoid unquoted variables and brittle `cd`/path assumptions.

## PowerShell

- Target **Windows PowerShell 5.1**-compatible scripts unless the project already requires PowerShell 7+ (`pwsh`). Stay forward-compatible with 7.
- Add `#requires -Version 5.1` (or 7 when the project requires `pwsh`).
- Use a `param()` block with types; set `$ErrorActionPreference = 'Stop'` unless a safer documented subset is required.
- Use `Set-StrictMode -Version Latest`.
- Use approved verbs (`Get-`/`Set-`/`Write-`/…). Do not use aliases (`%`, `?`, `ls`).
- Quote paths; use `Join-Path` rather than string-concatenated paths; avoid unquoted variables.
- Prefer ASCII, or UTF-8 **with BOM**, in `.ps1` files so Windows PowerShell 5.1 does not mis-parse non-ASCII.
- Destructive scripts: support `-WhatIf` via `SupportsShouldProcess`.

---

## Todo / inbox triage

- Id: `17393347`
- Created: 2026-08-15T17:36:45.280Z

# Todo / inbox triage

**Start command:** `triage`

Only follow these steps when the user says `triage` (or collaboration intake selected triage). Otherwise ignore this rule.

Place new work. Do not design it. Do not write product code.

If this repo has no `docs/todo/` yet: stop and say the pipeline files are missing. Do not create them or invent phases unless the user commands that setup.

## Steps

1. Read `docs/todo/pipeline.md` and the lettered `docs/todo/phaseX-*.md` files (or whatever phase detail files **this repo** defines).
2. For **each** new item: existing vs new; which **letter / track** and detail file from **this repo’s** pipeline map (affinity table / Detail column) — **not** a fixed cross-repo alphabet; **Ops / Manual** (or this repo’s equivalent) for non-lettered leftovers; which (sub)phase; sequence vs parallel vs Inbox. If placement or letters are unclear — **ask**.
3. Ask **only** questions needed to **place** the item. If placement is already clear, edit the markdown in that turn.
4. Update `pipeline.md` **and** the matching phase detail file.
5. On every new phase/item, paste the user’s **original request verbatim** (do not paraphrase). Date it.
6. **Duplicates:** stop and **ask** — merge into the existing item, or add a new subphase. Do not decide.
7. **bugfix Sequence prefix:** If the item is a **bugfix**, the `pipeline.md` **Sequence** line’s “What” text starts with `bugfix: ` (lowercase, colon, space). Do **not** prefix features, assess-only ships, or Ops. Apply when adding or moving that item’s Sequence row.

## Do not

- Code, patches, scaffolds, root-cause deep-dives, or DoD novels
- Invent phase letters, ids, or schedule without asking
- Treat placement as locked if the user has not confirmed a question you asked
- Assume another repo’s letter map (e.g. a past project’s B/C/D…) applies here

---

## Phase kickoff

- Id: `17393348`
- Created: 2026-08-15T17:36:45.529Z

# Phase / subphase kickoff

**Start command:** `kickoff` plus the id (e.g. `kickoff C18`, `kickoff B2`).

Only follow these steps when the user says `kickoff` with an id. Otherwise ignore this rule.

Assess whether a **queued** (sub)phase is ready to spec/lock. Do not write product code.

If this repo has no `docs/todo/` yet: stop and say the pipeline files are missing. Do not create them unless the user commands that setup.

## Steps

1. Confirm the id exists in `docs/todo/pipeline.md` (Sequence / Queued / pointers) and open its `docs/todo/phaseX-*.md` section.
2. Check **prereqs** and gates (Depends on, parallel-track rules, “not now”, Done blockers).
3. Is the **scope** clear? List verified facts vs gaps. No assumptions — **ask**.
4. Do not implement. Do not volunteer patches.

## Markdown

- Updating phase docs **during** the Q&A is optional.
- Updating that (sub)phase’s markdown **is required before any code** on it. If the user later says implement/ship/patch and the kickoff answers are not in the phase file yet, write the docs first (or stop and say they are missing).

## Do not

- Start a kickoff for work that is not already in the pipeline — tell the user to `triage` first
- Treat answers as locked until the user confirms
- Skip prereq failures — flag them and ask whether to proceed anyway

---

## Phase / ship docs close-out

- Id: `17393393`
- Created: 2026-08-15T17:41:24.592Z

# Phase / ship docs close-out

Every phase or ship close-out is incomplete until docs match **shipped** code.

Only apply the steps below when declaring a phase/ship **done**, or when the operator says ship/close-out. Do not run a docs audit on unrelated chats.

If this repo has no `docs/todo/` yet: still audit and update existing markdown (`docs/**/*.md`, root readme) to match shipped code. Do not create a pipeline or phase files unless the operator commands that setup. Skip pipeline-only steps (3, 6, and the Pointers) when those files are absent.

## Mandatory last DoD step

Before calling a phase/ship done:

1. **Audit** all project markdown: `docs/**/*.md` and root `readme.md` / `README.md` (if present).
2. **Update** anything that drifted — behavior, APIs, UI, config, status, links.
3. Do **not** stop at `docs/todo/*`. Todo/pipeline updates alone are not enough.
4. **Delete migrator files** for that phase/ship (one-shot helpers under `helpers/migrate_*.py` or equivalent) once cutover/soak is done — **only after explicit operator confirmation** in the conversation. Do not delete migrators unprompted.
5. Treat steps 1–4 as the **last** Definition-of-Done actions for every phase.
6. **Phase-out completed detail files:** when a `docs/todo/phaseX-*.md` is **fully finished** (Done in pipeline + Last DoD executed), **update that file for archive** — status Done, move open spec to shipped summary, strip queued work — then **tell the operator explicitly** so they can **manually move** the file out of the repo into offline archive. Do **not** delete or move phase files yourself unless the operator asks.

## Pointers

- Pipeline / phase sequence: `docs/todo/pipeline.md` (move Done vs Sequence; link detail files).
- **Delivery** DoD / status / kickoff record: phase files under `docs/todo/` — keep accurate.
- **Product reference** for shipped behaviour: `docs/` **outside** `todo/` — move canonical formulas/contracts there on close-out (User Rule “Documentation as-is vs pipeline”); phase sections keep short pointers, not a second full copy.

---

## Documentation as-is vs pipeline

- Id: `17560700`
- Created: 2026-08-23T11:09:59.667Z

# Documentation as-is vs pipeline

Applies in every repo that uses (or may use) the `docs/todo/` convention.

## Two trees

| Path | Role |
|---|---|
| **`docs/**/*.md` outside `docs/todo/`** (+ root README) | **Documentation as-is** — product truth for shipped / running behaviour, APIs, formulas, config, operator guides. |
| **`docs/todo/`** (`pipeline.md`, `phaseX-*.md`, …) | **Coding / delivery** — backlog, kickoff, DoD, sequence, verbatim inbox. Working material — **not** the long-term home for product reference. |

If this repo has no `docs/todo/`: product docs still apply; skip todo-only steps (same gate as triage / kickoff / close-out).

## Pre-ship vs post-ship

- **Kickoff / before code:** locks and formulas may live in the phase file (kickoff: phase markdown required before code).
- **Implement / ship / close-out:** if that material describes **running** behaviour, **move** the canonical body into the right product doc under `docs/` (not under `todo/`). Leave in the phase section only a **short pointer** (link + one-line summary) plus status / DoD / verbatim / out-of-scope. Do **not** keep a second full copy in todo as the lookup place.

Prefer **one** product home per topic. If the target path is unclear — **ask** (no assumptions).

## What stays in `docs/todo/`

Sequence, status, DoD checklists, verbatim operator requests, kickoff Q&A history, out-of-scope, archive summaries, and **delivery** lock tables that point at product docs.

## Relation to other rules

| User Rule | How this fits |
|---|---|
| **Phase / ship docs close-out** | Still audit **all** `docs/**/*.md`. “Do not stop at todo” means product docs must match shipped code. This rule defines *what* belongs where: close-out **moves** shipped reference into product docs, then trims the phase body to pointers + Done summary. |
| **Kickoff** | Unchanged: locks go into the phase file before code. Move to product docs when shipping / closing, not during kickoff Q&A unless the operator asks. |
| **Triage** | Unchanged: placement + verbatim stay in `docs/todo/`. |
| **Collaboration** | Unchanged: no silent pipeline edits; no inventing doc homes. |

**Refines** close-out “locked decisions live in phase files”: phase files remain authoritative for **delivery** (what was locked, DoD, status). **Product reference** for how the shipped product works lives in **`docs/` outside `todo/`**.

## Agent behaviour

- “How does the shipped product work?” → product `docs/**` outside `todo/`.
- “What are we building / locking / closing?” → `docs/todo/`.
- On ship/close-out Last DoD: ensure shipped behaviour is documented in product docs; strip duplicated implementation detail from the finished phase section in favour of pointers.
