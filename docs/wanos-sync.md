# WanOS sync (PC ↔ Pi)

Day-to-day deploy and pull between the Windows workstation and the Pi. Transport: **rsync over SSH** (no Samba/`Z:` required for sync). The engine uses Scoop git **MSYS** `ssh.exe` with `rsync-msys2` — not Windows OpenSSH.

| File | Role |
|------|------|
| `helpers/wanos-sync.bat` | Windows wrapper |
| `helpers/wanos-sync.ps1` | Engine (normalize, mirror, stats pull, log pull) |
| `helpers/wanos-sync.config.txt` | Includes / excludes / `[PiSsh]` (no secrets) |
| `docs/wanos-sync.md` | This document |

Samba on the Pi is optional (Explorer browse). Sync does not use it.

---

## What it does

| Job | Direction | Behaviour |
|-----|-----------|-----------|
| Mirror | Local → Pi | `rsync --delete` + excludes from config (main), `_lcd-agent` (`lcd`), or be90webserver excludes (`wlw`) |
| Stats / repo pull | Pi → Local | YAML Pi-wins (`--ignore-times`); DBs/NVRAM → OneDrive (`-u`) — **main Pi only** |
| Log pull | Pi → Local | `/var/log/wanos/wanos*` → OneDrive `logs\` (main, flat) or `logs\lcd-agent\` (`lcd`); WLW: `/var/log/wlw/wlw*` + Nginx vhost logs → `logs\wlw\` |
| Sessionlog pull | Pi → Local | `{RemoteRoot}/sessionlog/*` → OneDrive `logs\` (flat) — **main WanOS only**; skip if remote dir missing |
| Logcopy | Local → git | `wanos*` (+ session CSVs/DB on main) → `docs\logs` or `_lcd-agent\docs\logs`; WLW: `wlw*` + `hofmans.synology.me.*` → `be90webserver\docs\logs` — **always** after `run`; also mode `logcopy` alone. Locked/in-use dest files: red warn, skip, continue |

### Split Hue config (maps vs presets)

| File | Owner | Mirror (Local→Pi) | StatsRepoPull (Pi→Local) |
|------|-------|-------------------|---------------------------|
| `config_hue.yaml` | PC | Yes | No |
| `config_hue_presets.auto.yaml` | Pi (Explorer CRUD) | **No** (MirrorExclude); **Bootstrap** if missing on Pi | **Yes** (Pi wins) |

Edit lights/groups locally → `run` pushes `config_hue.yaml`. Edit presets on Pi → next `run` pulls `config_hue_presets.auto.yaml` into git. On first deploy, bootstrap pushes `.auto` from git when the Pi file is missing.

Pi cutover for Hue presets is complete; `config_hue_presets.auto.yaml` is now the operational source of truth.

Also: LF-normalize `*.sh` on `run` / `codeimport`.

### Modes

**WanOS (main Pi `.30`)**

```text
helpers\wanos-sync.bat test
helpers\wanos-sync.bat test verbose
helpers\wanos-sync.bat test logcopy
helpers\wanos-sync.bat test logcopy verbose

helpers\wanos-sync.bat run
helpers\wanos-sync.bat run verbose

helpers\wanos-sync.bat logcopy
helpers\wanos-sync.bat logcopy verbose
```

**LCD (LCD Pi `.51`; `_lcd-agent` → `/home/wannes/wanos`)**

```text
helpers\wanos-sync.bat test lcd
helpers\wanos-sync.bat test lcd verbose
helpers\wanos-sync.bat test lcd logcopy
helpers\wanos-sync.bat test lcd logcopy verbose

helpers\wanos-sync.bat run lcd
helpers\wanos-sync.bat run lcd verbose

helpers\wanos-sync.bat logcopy lcd
helpers\wanos-sync.bat logcopy lcd verbose
```

**WLW (main Pi `.30`; sibling repo `be90webserver` → `/home/wannes/be90webserver`)**

Product locks: `C:\data\git\be90webserver\docs\wlw-sync.md`.

```text
helpers\wanos-sync.bat test wlw
helpers\wanos-sync.bat test wlw verbose
helpers\wanos-sync.bat test wlw logcopy
helpers\wanos-sync.bat test wlw logcopy verbose

helpers\wanos-sync.bat run wlw
helpers\wanos-sync.bat run wlw verbose

helpers\wanos-sync.bat logcopy wlw
helpers\wanos-sync.bat logcopy wlw verbose
```

**codeimport (local mirror only; no SSH)**

```text
helpers\wanos-sync.bat codeimport <windows-folder>
helpers\wanos-sync.bat codeimport <windows-folder> verbose
```

**diff (one file PC vs Pi; SSH only; no mirror / stats / logcopy)**

```text
helpers\wanos-sync.bat diff <repo-relative-file>
helpers\wanos-sync.bat diff <repo-relative-file> verbose
helpers\wanos-sync.bat diff <repo-relative-file> lcd
helpers\wanos-sync.bat diff <repo-relative-file> lcd verbose
helpers\wanos-sync.bat diff <repo-relative-file> wlw
helpers\wanos-sync.bat diff <repo-relative-file> wlw verbose
```

| Mode / flags | Behaviour |
|--------------|-----------|
| `test` | Dry-run only (`rsync -n`) against main Pi |
| `run` | Normalize + mirror + stats pull + log pull + sessionlog pull + **logcopy** (main WanOS) |
| `logcopy` | Log pull + sessionlog pull + copy `wanos*` / `sauna_session_*.csv` / `sauna_sessions.db` into git `docs\logs` only (no mirror / stats / normalize) |
| `diff <path>` | Compare one repo-relative file PC vs Pi (normalized text); binary = sizes only; missing-side info (exit 0) |
| `… lcd` | Same modes against **LCD Pi**: mirror `_lcd-agent/` → `10.32.251.51:/home/wannes/wanos` (no stats/YAML pull); logcopy → `_lcd-agent\docs\logs`; diff uses `_lcd-agent` as local root |
| `… wlw` | Same modes against **WLW**: mirror `C:\data\git\be90webserver` → `10.32.251.30:/home/wannes/be90webserver` (no stats/sessionlog); log pull `/var/log/wlw/wlw*` + Nginx vhost logs; logcopy → `be90webserver\docs\logs`; diff uses be90 tree as local root. Mutually exclusive with `lcd`. |
| `test … logcopy` | Dry-run also previews the git `docs\logs` copy |
| `codeimport <path>` | Local mirror into folder only (path required; no SSH; not with `lcd` / `wlw` / `logcopy`) |

Modes are **mutually exclusive**. `wanos-sync.bat test run` (or any two of `test` / `run` / `logcopy` / `codeimport` / `diff`) exits with an error — do not combine them. Do not pass trailing `logcopy` with `run` — it is always included. Mode `diff` allows only trailing `lcd`, `wlw`, and `verbose`.

`verbose` → config counts and full rsync command lines.

### diff mode

Compare one **repo-relative** file between the PC and Pi over SSH. No rsync mirror, stats pull, or logcopy.

| Case | Output | Exit |
|------|--------|------|
| Both exist, text, normalized content same | `Same (normalized text): …` | 0 |
| Both exist, text, different | unified diff via `git diff --no-index` | 1 (not a batch error) |
| Both exist, binary (by extension or NUL byte) | `Binary - not diffed` + PC/Pi sizes | 0 if same bytes, 1 if different |
| Local only | `Only on PC: …` | 0 |
| Remote only | `Only on Pi: …` | 0 |
| Neither | `Missing from both: …` | 0 |

Normalization before text compare: UTF-8 decode, strip BOM, CRLF/CR → LF (same rules as `.sh` normalize, read-only). Mirror excludes do **not** block diff — Pi-owned files such as `automations.auto.yaml` are valid targets.

Allowed trailing flags: `lcd`, `wlw`, `verbose` only.

Exit code **1** means the files differ after normalization; the batch wrapper does not treat that as a failure. Exit **2+** indicates a script or SSH error.

### Paths (this machine)

| Name | Value | Where |
|------|--------|--------|
| Repo | `C:\data\git\wanos` | `.ps1` |
| WLW source | `C:\data\git\be90webserver` | `.ps1` (sibling repo) |
| Stats / logs | `C:\data\OneDrive\data\professional\wanos\logs` | `.ps1` |
| Main Pi | `wannes@10.32.251.30:/home/wannes/wanos` | `[PiSsh]` |
| LCD Pi | `wannes@10.32.251.51:/home/wannes/wanos` | `[LcdPiSsh]` |
| WLW app root | `wannes@10.32.251.30:/home/wannes/be90webserver` | `[WlwPiSsh]` |
| LCD log pull local | `…\wanos\logs\lcd-agent` | `[LcdPiSsh] LocalLogSubdir` |
| WLW log pull local | `…\wanos\logs\wlw` | `[WlwPiSsh] LocalLogSubdir` |
| App logs remote | `/var/log/wanos/wanos*` (main/LCD) or `/var/log/wlw/wlw*` (WLW) | SSH sections |
| WLW Nginx logs | `/var/log/nginx/hofmans.synology.me.*.log` (+ `.log.1`; skip `.gz`) | `[WlwExtraLogFiles]` |
| Session CSVs remote | `{RemoteRoot}/sessionlog/*` (e.g. `sauna_session_YYYYMMDD_HHMMSS.csv`) | main WanOS only; mirror-excluded |

Edit `[PiSsh]` / `[LcdPiSsh]` / `[WlwPiSsh]` Host/User/RemoteRoot if your Pis differ. Secrets never go in the config — only SSH keys. Reuse the same `id_ed25519` for both Pis (install pubkey on `.51` once — see `_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`). WLW uses the same key as main Pi `.30`.

**SSH binary:** `helpers/wanos-sync.ps1` calls `%USERPROFILE%\scoop\apps\git\current\usr\bin\ssh.exe` (full path, and that dir prepended on PATH). MSYS `rsync` plus `C:\Windows\System32\OpenSSH\ssh.exe` resets the protocol stream (`safe_read` 4 bytes / `Connection reset` / `0 bytes received`). Both binaries read the same `%USERPROFILE%\.ssh\` keys. Windows OpenSSH is still fine for one-time `ssh-keygen` and pubkey install from a normal prompt.

Console colours: yellow = files changing, red = deletes, cyan = section, green = done.

---

## Fresh Windows workstation setup

Run once on a new PC. Safe to re-run (skips existing Scoop/key).

```powershell
# --- WanOS sync workstation bootstrap ---
$PiUser = "wannes"
$PiHost = "10.32.251.30"
$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519"

# 1) OpenSSH Client (elevate if Add-WindowsCapability fails)
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
}
ssh -V

# 2) Scoop
if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
    irm get.scoop.sh | iex
}
$env:Path = "$env:USERPROFILE\scoop\shims;$env:Path"

# 3) rsync (NOT "scoop install rsync" — use rsync-msys2)
scoop install git
scoop bucket add raisercostin https://github.com/raisercostin/raiser-scoop-bucket 2>$null
scoop install rsync-msys2

# MSYS DLLs from Scoop git must be on PATH (rsync.exe). Sync itself pins this ssh.exe;
# User PATH still often has Windows OpenSSH first after reboot.
$GitUsrBin = "$env:USERPROFILE\scoop\apps\git\current\usr\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$GitUsrBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$GitUsrBin;$userPath", "User")
}
$env:Path = "$env:USERPROFILE\scoop\shims;$GitUsrBin;$env:Path"
where.exe rsync
rsync --version
if ($LASTEXITCODE -ne 0) { throw "rsync --version failed; open a new PowerShell and retry" }

# 4) SSH key
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
if (-not (Test-Path -LiteralPath $KeyPath)) {
    ssh-keygen -t ed25519 -C "wanos-sync-pc" -f $KeyPath
}
Get-Content "$KeyPath.pub"

# 5) Install pubkey on Pi (password OK once)
Get-Content "$KeyPath.pub" | ssh "${PiUser}@${PiHost}" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# 6) Verify
ssh -o BatchMode=yes -o ConnectTimeout=10 "${PiUser}@${PiHost}" "echo ok"
ssh -o BatchMode=yes "${PiUser}@${PiHost}" "rsync --version"
```

**Pi:** `rsync` is in `helpers/bootstrap/backend/apt-packages.txt` (Phase 1). If missing:

```bash
sudo apt update && sudo apt install -y rsync
```

### First sync

```text
helpers\wanos-sync.bat test
helpers\wanos-sync.bat run
```

---

## Config notes

`helpers/wanos-sync.config.txt`:

- `[MirrorExcludeDirs]` / `[MirrorExcludeFiles]` — not copied, not deleted on Pi (`docs/` is excluded; this doc lives under `docs/`). Path segment **`bootstrap`** is excluded, so `helpers/bootstrap/**` is not mirrored to the **main** Pi. Path **`_lcd-agent`** is excluded from the main mirror (LCD deploy uses `lcd` mode only). Path **`sessionlog`** is Pi-owned (sauna session CSVs); pulled to OneDrive / `docs\logs`, never mirrored. Rsyslog logcap lives in **`helpers/`** (`wanos_rsyslog_logcap.sh`, `wanos-syslog-truncate.sh`, `logrotate.rsyslog`) so it **does** sync to the main Pi. File excludes include `*.bak` and `*.bak-*` (migrator stamps like `automations.auto.yaml.bak-YYYYMMDD-HHMMSS`). Repo meta not deployed: `readme.md`, `LICENSE`, `entity_id-list.txt`, and any other `*.md` outside excluded dirs (e.g. `core/logger.md`).
- **`.cursor`** — IDE rules (`.cursor/rules/`) and other Cursor project files; PC-only, not deployed to the Pi
- `[StatsInclude]` / `[StatsRepoPull]` — pull rules (repo YAML always overwrite; missing remote file skipped with warning)
- `[PiSsh]` — Host, User, RemoteRoot, RemoteLogDir, LocalLogSubdir (empty = flat into StatsDest), RemoteGlob
- `[LcdPiSsh]` — LCD Pi (same keys); `LocalLogSubdir=lcd-agent` lands pulls under OneDrive `logs\lcd-agent`
- `[WlwPiSsh]` — WLW on main Pi `.30`; source `C:\data\git\be90webserver`; `LocalLogSubdir=wlw`; no bare `bootstrap` exclude (helpers/bootstrap syncs)
- `[WlwExtraLogFiles]` — absolute Nginx log paths pulled flat into `logs\wlw\` (+ `.log.1` when present; skip `.gz`)

Never push Pi-owned YAML/DBs/NVRAM in the same workflow that pulls them. Always `test` before the first `run` on a new machine. First LCD deploy: `test lcd` then `run lcd` (install: `_lcd-agent/helpers/bootstrap/wanos-install-lcd-agent.md`). First WLW deploy: `test wlw` then `run wlw`, then on Pi `sudo bash /home/wannes/be90webserver/helpers/bootstrap/wlw_bootstrap.sh` (creates `/var/lib/wlw` + `/var/log/wlw`). Product locks: be90webserver `docs/wlw-sync.md`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `rsync not found` / `--version` silent | Scoop shims + git `usr\bin` on PATH; new shell |
| `safe_read` 4 bytes / `Connection reset` / `0 bytes` `[Receiver]` | MSYS rsync used Windows OpenSSH (common after reboot: System32 `ssh` wins). Sync forces Scoop git `usr\bin\ssh.exe`; `verbose` must show that path |
| `Permission denied (publickey)` | Pubkey in Pi `authorized_keys`; BatchMode test |
| `Host key verification failed` | `ssh-keygen -R 10.32.251.30` then reconnect |
| Mass `deleting wanos_venv/...` | Excludes broken — stop; check config; dry-run only |
| `Unexpected remote arg` | MSYS glob — script uses `--exclude=*`; do not hand-split `*` |
| Local path as remote host | Use `/c/data/...` not `C:/...` (script converts) |
| `codeimport` without path | Path is required |
