# --- file: docs/todo/ops8-php2shell-bridge.md ---
# Ops8 — PHP2Shell bridge (current Pi PHP, before Ops7)

**Status:** open · **Size:** mid · **Pipeline:** [`pipeline.md`](pipeline.md) Sequence **#1** / Manual § Ops8  
**Date:** 2026-11-03 (CET) · **Triage + kickoff:** 2026-11-03  
**Hardware:** main Pi **`10.32.251.30`** (WanOS + WLW co-host)  
**Does not replace:** [`ops7-fresh-install.md`](ops7-fresh-install.md) (Trixie + PHP ≥ 8.4.27 + Python 3.13)

**Goal:** Until Ops7 cutover (weeks out), harden / patch the **live** PHP that serves WLW against **PHP2Shell** (CVE-2026-109618 / CVE-2026-109619), with an **operator runbook + automated helper** doing as much as is safe.

---

## Verbatim (operator)

**2026-11-03:**

> I meant PHP, not python - forget python backport, I'm talking about backporting the PHP2shell in our version

> Ops7 is weeks out  
> so we need to do this - triage, put on top and kickoff now  
> create an operator script, create a shell or python script to automate as much as possible

---

## Placement

| | |
|---|---|
| Affinity | **Ops** (host / PHP packages — not lettered WanOS product) |
| Id | **Ops8** |
| Sequence | **#1** (ahead of Ops7) |
| Parallel | Ops7 scripts/docs may continue; **do not** flash/cutover Ops7 until Ops8 Done or operator revokes |
| Out of scope | Python upgrade; Trixie re-image; WLW app feature work; LCD `.51` |

---

## Kickoff (2026-11-03)

### Prereqs / gates

| Check | Result |
|---|---|
| In pipeline Sequence / Manual | Yes — **Ops8** #1 |
| Blocks Ops7 cutover? | No — bridge only; Ops7 remains the permanent fix |
| Live PHP on `.30` | **Confirmed 2026-11-04** — see inventory below |
| Fix path | **B locked 2026-11-04** — source rebuild (official 7.4 backport); **A out** (Freexian paid / wrong fit for weeks bridge) |
| Code allowed | **No** until operator says **`implement`** |

### Live inventory (operator `.30`, 2026-11-04)

| Item | Value |
|---|---|
| CLI | PHP **7.4.33** NTS · built **2026-08-11** |
| FPM | **php-fpm7.4** · PHP **7.4.33** fpm-fcgi · same build date |
| Arch packages | **`7.4.33-1+deb11u12`** · **armhf** |
| Meta packages | `php-fpm` / `php-cli` / … → `2:7.4+76` |
| PHP2Shell status | **Unpatched** — need ≥ **`deb11u14`** (ELTS) or official 7.4 source backport rebuild |

Extensions present (7.4.*): cli, common, curl, fpm, json, mbstring, opcache, readline, sqlite3, xml, zip.

### Locked (operator 2026-11-04)

| # | Topic | Lock |
|---|---|---|
| 1 | Inventory | Recorded above (`7.4.33` / `deb11u12` / armhf — unpatched) |
| 2 | Fix path | **B** — official PHP 7.4 source backport (`PHP-7.4-CVE-2026-109618-109619` / `712e60f9ed…`). **A out** (ELTS quote-based / PHP LTS ≥ ~1 200 €/yr — wrong fit for weeks-to-Ops7). **C out**. |
| 3 | Mitigation | **Yes** — always apply FPM `session.upload_progress.enabled=off` (step 0) even after rebuild |
| 4 | Automation | **Bash on Pi** + short operator MD checklist; Python only if useful for status/changelog |
| 5 | Downtime | FPM restart OK; WanOS Python unaffected |
| 6 | be90webserver | **Pointer-only** (wanos owns host PHP) |

### Locked B method (operator 2026-11-04)

Rebuild **Debian packages** from `apt-get source php7.4` (live `7.4.33-1+deb11u12`), apply official backport into `debian/patches`, `dpkg-buildpackage`, install resulting `.deb`s, `apt-mark hold` against clobber, restart FPM.  
**Reject:** naked `/usr/local` PHP install.

### Locked doc / helper homes (operator 2026-11-04)

| Deliverable | Path |
|---|---|
| Operator checklist | `docs/ops8-operator-checklist.md` |
| Bash helper | `helpers/ops8-php2shell/` (detect → mitigate → rebuild path → verify → restart FPM) |
| Python status script | same dir — inventory / patch / CVE-status report |
| Crosslinks (wanos) | `bootstrap-main-pi.md` + Ops7 note — at **`implement`** |
| be90webserver | **Pointer-only** — **done 2026-11-04**: `docs/bootstrap-host.md`, `docs/ops-checklist.md` § wanos Ops8, `docs/todo/ops7-fresh-install.md`. Note: be90 **Ops8** id = audit retention (unrelated). |

No other lettered phases need PHP2Shell content.

### Deliverables (after `implement`)

| Deliverable | Intent |
|---|---|
| This file | Delivery locks / DoD / verbatim |
| `docs/ops8-operator-checklist.md` | Tick-list |
| `helpers/ops8-php2shell/*.sh` | Detect → mitigate → **B** rebuild → verify → restart FPM |
| `helpers/ops8-php2shell/*.py` | Status / inventory / CVE-status report |
| Crosslinks | bootstrap-main-pi + Ops7 note + be90 pointer |

**Not in scope:** WLW app PHP code changes (cannot patch the interpreter).

### DoD (draft)

- [x] Live PHP inventory recorded
- [x] Fix path **B** locked (A/C out)
- [x] B method = Debian `.deb` rebuild (not `/usr/local`)
- [x] Doc/helper homes locked; Python status script **yes**
- [ ] Operator checklist + helper scripts after `implement`
- [ ] On `.30`: mitigation applied **and** patched package/binary verified
- [ ] FPM restarted; WLW smoke; WanOS untouched
- [ ] Verify method documented
- [ ] Ops7 remains permanent cutover; bridge marked temporary
- [ ] Last DoD: audit `docs/**/*.md` (+ root README)
- [x] be90webserver pointer (wanos Ops8; not be90 Ops8 id)

### Out of scope

- Ops7 flash / Python 3.13
- Compiling PHP into WanOS venv
- Exposing `:443` while knowingly unpatched without operator acceptance of residual risk
- LCD Pi / kiosk site PHP

---

## Relation to Ops7

| | Ops8 | Ops7 |
|---|---|---|
| When | Now (weeks before cutover) | Later re-image |
| PHP | Patch / mitigate **current** stack | Fresh **≥ 8.4.27** |
| Python | No change | **3.13** |
| OS | Keep current card | Trixie Lite 64-bit |

After Ops7 ships, Ops8 helpers become historical (archive or mark superseded).
