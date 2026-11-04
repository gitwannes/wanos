<!-- --- file: docs/ops8-operator-checklist.md --- -->
# Ops8 — PHP2Shell bridge (as-is)

Temporary bridge on live main Pi **Bullseye PHP 7.4** until **Ops7**.  
**Status:** **Done** on `.30` (**2026-11-04**) — delivery archive [`todo/_archive/ops8-php2shell-bridge.md`](todo/_archive/ops8-php2shell-bridge.md).  
Helpers: [`../helpers/ops8-php2shell/`](../helpers/ops8-php2shell/) · README: [`../helpers/ops8-php2shell/README.md`](../helpers/ops8-php2shell/README.md).

**Host:** `.30` · packages still report `7.4.33-1+deb11u12` (expected).  
**Success signal:** marker + mitigation + held packages + FPM `active` — not a new dpkg revision.

---

## What is running

| Item | Location / value |
|---|---|
| Bridged CLI | `/usr/bin/php7.4` (replaced; `php -v` build date = bridge day) |
| Bridged FPM | `/usr/sbin/php-fpm7.4` (must be built with **`--with-fpm-systemd`** — Debian unit is `Type=notify`) |
| Marker | `/var/lib/wanos-ops8/bridge` (`bridged=1`, `method=pristine-orig`, commit `712e60f9ed…`) |
| Mitigation | `/etc/php/7.4/fpm/conf.d/99-ops8-php2shell.ini` → `session.upload_progress.enabled=Off` |
| Binary bak | `/var/lib/wanos-ops8/bin-bak/` |
| Build tree | `/home/wannes/ops8-php-build` (optional; keep or wipe) |
| Holds | `apt-mark showhold \| grep php7.4` — real packages only |

**Method B2:** php.net `php-7.4.33.tar.xz` (SHA256 verified) → security patch (bailout / PHP2Shell) → configure from `php-config7.4` (filter noise; force `--enable-fpm`, `--with-fpm-systemd`, fpm user/group) → `make` → install binaries → hold → mitigate.

---

## Verify (anytime)

```bash
cd ~/wanos/helpers/ops8-php2shell
python3 ops8_status.py          # want: OK_bridged_and_mitigated
systemctl is-active php7.4-fpm  # active
apt-mark showhold | grep '^php7\.4'
```

---

## Re-run / resume (if binaries lost)

```bash
tmux new -s ops8
cd ~/wanos/helpers/ops8-php2shell
# full: sudo ./ops8_php2shell.sh all
# or reconfigure+make only (tree still present):
OPS8_RESUME=1 sudo ./ops8_php2shell.sh rebuild
sudo ./ops8_php2shell.sh hold
sudo systemctl restart php7.4-fpm
```

---

## Rollback

See helper README § Rollback (`bin-bak` or apt reinstall `deb11u12`).

---

## After Ops7

Old card discarded; this bridge is historical. Unhold / remove marker only if still on the old card before flash.
