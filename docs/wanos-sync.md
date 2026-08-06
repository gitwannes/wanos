# WanOS sync (PC ↔ Pi)

Day-to-day deploy and pull between the Windows workstation and the Pi. Transport: **rsync over SSH** (no Samba/`Z:` required for sync).

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
| Mirror | Local → Pi | `rsync --delete` + excludes from config |
| Stats / repo pull | Pi → Local | YAML Pi-wins (`--ignore-times`); DBs/NVRAM → OneDrive (`-u`) |
| Log pull | Pi → Local | `/var/log/wanos/wanos*` → OneDrive `logs\` (flat; same folder as DBs) |

Also: LF-normalize `*.sh` on `run` / `codeimport`.

### Modes

```text
helpers\wanos-sync.bat test [verbose]
helpers\wanos-sync.bat run [verbose]
helpers\wanos-sync.bat codeimport <windows-folder> [verbose]
```

| Mode | Behaviour |
|------|-----------|
| `test` | Dry-run only (`rsync -n`) |
| `run` | Normalize + mirror + pulls |
| `codeimport <path>` | Local mirror into folder only (path required; no SSH) |

`verbose` → config counts and full rsync command lines.

### Paths (this machine)

| Name | Value | Where |
|------|--------|--------|
| Repo | `C:\data\git\wanos` | `.ps1` |
| Stats / logs | `C:\data\OneDrive\data\professional\wanos\logs` | `.ps1` |
| Pi host / user / root | `wannes@10.32.251.30:/home/wannes/wanos` | `[PiSsh]` in config |
| App logs remote | `/var/log/wanos` | `[PiSsh] RemoteLogDir` |

Edit `[PiSsh]` Host/User/RemoteRoot if your Pi differs. Secrets never go in the config — only SSH keys.

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

# MSYS DLLs from Scoop git must be on PATH
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

- `[MirrorExcludeDirs]` / `[MirrorExcludeFiles]` — not copied, not deleted on Pi (`docs/` is excluded; this doc lives under `docs/`)
- `[StatsInclude]` / `[StatsRepoPull]` — pull rules (repo YAML always overwrite)
- `[PiSsh]` — Host, User, RemoteRoot, RemoteLogDir, LocalLogSubdir (empty = flat into StatsDest), RemoteGlob

Never push Pi-owned YAML/DBs/NVRAM in the same workflow that pulls them. Always `test` before the first `run` on a new machine.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `rsync not found` / `--version` silent | Scoop shims + git `usr\bin` on PATH; new shell |
| `Permission denied (publickey)` | Pubkey in Pi `authorized_keys`; BatchMode test |
| `Host key verification failed` | `ssh-keygen -R 10.32.251.30` then reconnect |
| Mass `deleting wanos_venv/...` | Excludes broken — stop; check config; dry-run only |
| `Unexpected remote arg` | MSYS glob — script uses `--exclude=*`; do not hand-split `*` |
| Local path as remote host | Use `/c/data/...` not `C:/...` (script converts) |
| `codeimport` without path | Path is required |
