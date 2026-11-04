<!-- --- file: helpers/ops8-php2shell/README.md --- -->
# Ops8 — PHP2Shell bridge helpers

Temporary bridge for live main Pi **Bullseye PHP 7.4** (`7.4.33-1+deb11u12` armhf) until **Ops7** (Trixie PHP ≥ 8.4.27).

| | |
|---|---|
| Status | **Done** on `.30` **2026-11-04** (temporary until Ops7) |
| Product / operator | [`docs/ops8-operator-checklist.md`](../../docs/ops8-operator-checklist.md) |
| Delivery archive | [`docs/todo/_archive/ops8-php2shell-bridge.md`](../../docs/todo/_archive/ops8-php2shell-bridge.md) |
| Sync | Mirrored by `wanos-sync` (`helpers/`; not under excluded `bootstrap/`) |

## Method (B2)

Debian **quilt cannot** apply the official upstream 7.4 backport on top of Raspbian/Debian `debian/patches` (hunks reject).  

**B2:** download **php.net** `php-7.4.33.tar.xz` (SHA256 verified) → apply official patch `712e60f9ed…` → `./configure` from `php-config7.4 --configure-options` (only `--*` tokens; drops `CFLAGS` leftovers; **forces `--enable-fpm`** + **`--with-fpm-systemd`** for Debian `Type=notify`) → `make` → replace `/usr/bin/php7.4` and `/usr/sbin/php-fpm7.4` → `apt-mark hold` → FPM mitigation.  
(Does **not** use Debian `.orig` / `.asc` — that path failed on this Pi.)  

`dpkg` version stays `…deb11u12`; success is **`/var/lib/wanos-ops8/bridge`** (`bridged=1`, `method=pristine-orig`) + mitigation on.

## Run on the Pi

Compile takes **45–75+ minutes** with `parallel=1`. Use **tmux**.

```bash
sudo apt-get install -y tmux   # if missing
# after wanos-sync run (main)
tmux new -s ops8
cd ~/wanos/helpers/ops8-php2shell
python3 ops8_status.py
df -h /
sudo ./ops8_php2shell.sh all
python3 ops8_status.py          # want: OK_bridged_and_mitigated
```

Detach: `Ctrl-b` `d`. Reattach: `tmux attach -t ops8`.

### Commands

| Command | Role |
|---|---|
| `status` | Inventory |
| `mitigate` | FPM `session.upload_progress.enabled=Off` + restart |
| `reset` | Wipe prior attempt trees under `OPS8_BUILD_ROOT` (keeps verified tarball) |
| `rebuild` | **reset first**, then B2 pristine build + binary replace + marker |
| `hold` | `apt-mark hold` php7.4\* |
| `restart` | restart FPM |
| `all` | mitigate → rebuild → hold → restart |

### Safeguards

- Enable commented **`deb-src`** (backups under `/var/lib/wanos-ops8/apt-bak/`, not in `sources.list.d`)
- Grow swap toward **2048 MiB** when tiny
- **`parallel=1`** when RAM < 3 GiB
- Abort if `/` avail < **5120 MiB**
- Binary backups: `/var/lib/wanos-ops8/bin-bak/`

Env: `OPS8_BUILD_ROOT`, `OPS8_BUILD_PARALLEL`, `OPS8_SWAP_TARGET_MB`, `OPS8_MIN_ROOT_AVAIL_MB`, `OPS8_RESUME=1` (reconfigure+make only), `OPS8_FPM_USER` / `OPS8_FPM_GROUP`.

### Status verdicts

| Verdict | Meaning |
|---|---|
| `OK_bridged_and_mitigated` | Marker (or `+wanosops8` pkg) + mitigation on |
| `MITIGATED_only_rebuild_pending` | Stopgap only |
| `VULNERABLE_…` | Not done |

## Rollback

```bash
sudo apt-mark unhold $(dpkg-query -W -f='${Package}\n' 'php7.4*')
# restore stock binaries if bak exists:
sudo cp -a /var/lib/wanos-ops8/bin-bak/php7.4 /usr/bin/php7.4
sudo cp -a /var/lib/wanos-ops8/bin-bak/php-fpm7.4 /usr/sbin/php-fpm7.4
# or reinstall stock packages:
sudo apt-get install --reinstall php7.4-cli=7.4.33-1+deb11u12 php7.4-fpm=7.4.33-1+deb11u12
sudo systemctl restart php7.4-fpm
sudo rm -f /var/lib/wanos-ops8/bridge
```

## Patch provenance

`php-7.4-CVE-2026-109618-109619.patch` = php-src security bailout from `712e60f9edfd03f0960fc4fc3c2c375f42b90aa2` (compare vs tag `php-7.4.33`; version-bump hunks stripped).

## Out of scope

Freexian ELTS, Surý full stack swap, `/usr/local` prefix install, Ops7 flash, auto-shrink swap.
