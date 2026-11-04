# --- file: docs/todo/_archive/ops8-php2shell-bridge.md ---
# Ops8 — PHP2Shell bridge (archived)

**Status:** Done · **Close-out:** 2026-11-04 (CET) · **Size:** mid  
**Product / operator (as-is):** [`../../ops8-operator-checklist.md`](../../ops8-operator-checklist.md) · helpers [`../../../helpers/ops8-php2shell/`](../../../helpers/ops8-php2shell/)  
**Permanent fix:** **Ops7** (Trixie PHP ≥ 8.4.27) — [`../ops7-fresh-install.md`](../ops7-fresh-install.md)

---

## Shipped summary

Live Bullseye **PHP 7.4.33** / `deb11u12` armhf on `.30` bridged against PHP2Shell (**CVE-2026-109618** / **CVE-2026-109619**) until Ops7.

| Piece | Outcome |
|---|---|
| Path | **B2** — php.net `php-7.4.33.tar.xz` + official bailout patch (`712e60f9ed…`, security hunks only) + replace `/usr/bin/php7.4` and `/usr/sbin/php-fpm7.4` |
| Mitigation | FPM `session.upload_progress.enabled=Off` → `/etc/php/7.4/fpm/conf.d/99-ops8-php2shell.ini` |
| Marker | `/var/lib/wanos-ops8/bridge` (`bridged=1`, `method=pristine-orig`) |
| Hold | `apt-mark hold` on real `php7.4*` packages |
| Verify | `ops8_status.py` → **`OK_bridged_and_mitigated`**; FPM `active` (needs `--with-fpm-systemd` for Debian `Type=notify`) |
| Abandoned | Freexian ELTS (A); Debian quilt on packaged tree (B1); `/usr/local` / Surý (C) |

**Pi smoke 2026-11-04:** bridged CLI+FPM build same day; mitigation on; holds set; WLW smoke OK (operator).

---

## Verbatim (operator)

**2026-11-03:**

> I meant PHP, not python - forget python backport, I'm talking about backporting the PHP2shell in our version

> Ops7 is weeks out  
> so we need to do this - triage, put on top and kickoff now  
> create an operator script, create a shell or python script to automate as much as possible

---

## Delivery locks (record)

| # | Lock |
|---|---|
| Path | **B** (source rebuild); A/C out |
| Mitigation | Always on, even after rebuild |
| Automation | Bash helper + Python status; tmux for long build |
| Downtime | FPM restart OK |
| be90 | Pointer-only (wanos owns host PHP) |

---

## Out of scope (unchanged)

Ops7 flash; Python upgrade; WLW app PHP code; LCD `.51`.
