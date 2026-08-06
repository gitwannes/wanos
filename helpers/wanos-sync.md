# WanOS sync (copy / push / pull)

Single place for how PC ↔ Pi sync works: what the scripts do today, how credentials and tools are set up, and the planned move to **one transport: rsync over SSH** (no mapped `Z:` drive).

Related files (same folder):

| File | Role |
|------|------|
| `wanos-sync.bat` | Windows wrapper (modes, `Z:` check today, invokes PowerShell) |
| `wanos-sync.ps1` | Engine (normalize, mirror, stats pull, log pull) |
| `wanos-sync.config.txt` | Includes / excludes / `[PiSsh]` (not secrets) |
| `wanos-sync.md` | This document |

Legacy (superseded by the scripts above, keep only if you still need them): `robocopy-sync.bat`, `wanos.rcj`.

---

## Goals

- Push the git working tree to the Pi WanOS root (deploy code).
- Pull Pi-owned runtime / telemetry back to the PC (YAML into the repo; DBs / NVRAM / app logs into OneDrive).
- One auth story, one network path: **SSH key + rsync** for push and pull (including `/var/log/wanos`).
- Keep **LF normalization** of `*.sh` on real runs (transfer does not fix line endings).
- Samba may remain on the Pi for manual Explorer browsing / bootstrap; **after migration the sync script does not use SMB/`Z:` at all**.

---

## Current vs target

| Area | Today | Target |
|------|--------|--------|
| Push (mirror) | Copy Local → `Z:\` (Samba) | **rsync over SSH** Local → Pi home WanOS tree |
| Pull (stats / YAML / DBs) | Walk `Z:\` → repo / OneDrive | **rsync over SSH** (same includes) |
| Pull (app logs) | OpenSSH `scp` `/var/log/wanos` | **rsync over SSH** (same remote dir) |
| Auth | Samba mapped drive + separate SSH for logs | **SSH key only** (`BatchMode`) |
| `code-import` | Bundled into `run` / `runlocal` | **Separate CLI switch** + required Windows folder |
| Modes | `test` \| `run` \| `runlocal` | `test` \| `run` + e.g. `codeimport <path>` |

Prefer **rsync** over raw `scp` for mirror/pull: excludes, deletes, and incremental updates are first-class.

---

## Jobs (logical)

### Job 1 — Mirror (push)

- **Direction:** Local repo → Pi WanOS root.
- **Semantics:** Deploy code; excluded paths are neither copied nor deleted on the Pi (same idea as robocopy `/XD` + `/XF`).
- **Must not push:** Pi-owned live state (`entity_registry.auto.yaml`, `automations.auto.yaml`, `*.db`, `wanos-nvram.json`, …), local-only trees (`.git`, `docs`, `code-import`, venvs on Pi, …), sync tooling itself.

### Job 2 — Stats / repo pull

- **Direction:** Pi → Local.
- **Include-only** file name patterns (`StatsInclude`).
- **Repo pull** (`StatsRepoPull`): Pi wins always → overwrite into git repo root (rsync: `--ignore-times` on those files). Do not also mirror those Local→Pi in the same run.
- **Telemetry:** everything else in `StatsInclude` → OneDrive stats folder, newer-only (timestamp tolerance for Samba-era fuzz; revisit under rsync).

### Job 3 — Log pull

- **Direction:** Pi `/var/log/wanos` → `StatsDest\<LocalLogSubdir>\` (default `var-log-wanos`).
- **Glob:** `wanos*` (rotated + live: `wanos.log`, `wanos_debug*.log`, `wanos_automations.log`, `wanos_iwhw.log`, `wanos_power.log`, …).
- Not on the Samba share; already SSH today (`scp`). Target: same job via rsync.

---

## Paths (this machine — edit in `.ps1` until moved to config)

| Name | Typical value | Meaning |
|------|----------------|---------|
| Mirror source | `C:\data\git\wanos` | Git working tree |
| Mirror dest (today) | `Z:\` | Samba → Pi WanOS root |
| Remote WanOS root (target) | `wannes@10.32.251.30:/home/wannes/wanos/` | rsync SSH destination (confirm path on Pi) |
| Stats dest | `C:\data\OneDrive\data\professional\wanos\logs` | DBs, NVRAM, pulled app logs |
| Code folder (today) | `C:\data\git\wanos\code-import` | Extra local mirror; leave default `run` |

Normalize scans (today): repo root + `helpers\` for `*.sh`.

---

## Modes (today)

| Mode | Behavior | Needs `Z:` today |
|------|----------|------------------|
| `test` | Dry-run preview (no writes). No normalize. | Yes |
| `run` | Normalize → mirror Pi (+ CodeFolder) → pull Samba → SSH log pull | Yes |
| `runlocal` | Normalize → mirror to CodeFolder only | No |

Wrapper:

```text
helpers\wanos-sync.bat test [verbose]
helpers\wanos-sync.bat run [verbose]
helpers\wanos-sync.bat runlocal [verbose]
```

`verbose` → `-VerboseSync` (config counts, skips, paths).

### Planned CLI (not implemented yet)

- `test` / `run` — Pi only via SSH/rsync; **no** `Z:`; **no** CodeFolder.
- `codeimport <windows-folder>` — required path; error + quit if omitted.
- Drop or alias `runlocal`.
- Single “Mode: …” banner (today both `.bat` and `.ps1` print it).

---

## Config file (`wanos-sync.config.txt`)

- One pattern / name per line in list sections; blank lines and `#` comments ignored.
- Inline trailing comments: `pattern  # comment` (space + `#`).
- Do **not** pass this file to `robocopy /JOB:…`.

| Section | Purpose |
|---------|---------|
| `[MirrorExcludeDirs]` | Dir name patterns (any path segment) — skip copy and delete |
| `[MirrorExcludeFiles]` | File **name** patterns — skip copy and delete |
| `[StatsInclude]` | Pull include-only (file name) |
| `[StatsRepoPull]` | Subset of include → always overwrite into git repo |
| `[PiSsh]` | `key=value`: Host, User, RemoteLogDir, LocalLogSubdir, RemoteGlob (extend for rsync remote root) |

**Secrets never go in this file** — only host, user, paths, globs.

---

## Line-ending normalization

Still required after switching to rsync/SSH.

- Windows editors often write CRLF; Pi shell scripts need LF.
- rsync/scp copy bytes unchanged.
- On `run` (and today’s `runlocal`), the engine rewrites `*.sh` under configured dirs to LF before push.
- Optional hardening later: `.gitattributes` `*.sh text eol=lf` — does not replace the sync normalize step for already-checked-out files.

---

## Credentials & tools (procedure)

Nothing below belongs in git except public setup notes. Private keys stay on the PC.

### Greenfield Windows setup (one script)

Run in **PowerShell** on a fresh PC. Safe to re-run: skips Scoop/key steps that already exist.

Edit `$PiHost` / `$PiUser` if your `[PiSsh]` config differs.

```powershell
# --- WanOS sync workstation bootstrap (Windows greenfield) ---
$PiUser = "wannes"
$PiHost = "10.32.251.30"
$KeyPath = "$env:USERPROFILE\.ssh\id_ed25519"

# 1) OpenSSH Client (elevate this window if Add-WindowsCapability fails)
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
}
ssh -V
Get-Command ssh, scp -ErrorAction SilentlyContinue | Format-Table Name, Source

# 2) Scoop (package manager for rsync on Windows)
if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
    irm get.scoop.sh | iex
}
# Refresh PATH so this session sees scoop
$env:Path = "$env:USERPROFILE\scoop\shims;$env:Path"
scoop --version

# 3) rsync via Scoop (NOT "scoop install rsync" — that manifest does not exist)
scoop install git
scoop bucket add raisercostin https://github.com/raisercostin/raiser-scoop-bucket 2>$null
scoop install rsync-msys2
# rsync-msys2 is an MSYS2 binary: it needs Git's MSYS runtime DLLs (e.g. msys-2.0.dll)
# on PATH or rsync --version exits silently / crash (0xC0000135).
$GitUsrBin = "$env:USERPROFILE\scoop\apps\git\current\usr\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$GitUsrBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$GitUsrBin;$userPath", "User")
    Write-Host "Added to user PATH: $GitUsrBin"
}
$env:Path = "$env:USERPROFILE\scoop\shims;$GitUsrBin;$env:Path"

where.exe rsync
rsync --version
if ($LASTEXITCODE -ne 0) { throw "rsync --version failed; open a new PowerShell and retry" }

# 4) Optional: ssh-agent (only needed if the key has a passphrase)
# Run in elevated PowerShell:
#   Set-Service ssh-agent -StartupType Automatic; Start-Service ssh-agent

# 5) SSH key (skip if you already have one)
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
if (-not (Test-Path -LiteralPath $KeyPath)) {
    ssh-keygen -t ed25519 -C "wanos-sync-pc" -f $KeyPath
} else {
    Write-Host "Key already exists: $KeyPath"
}
Get-Content "$KeyPath.pub"

# 6) One-time: install public key on Pi (password prompt OK on first run)
Write-Host @"

NEXT — run once (accept host key if asked):

  Get-Content `"$KeyPath.pub`" | ssh ${PiUser}@${PiHost} "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

"@

# 7) Verify BatchMode + rsync smoke (run AFTER step 6 succeeds)
Write-Host @"

After pubkey is on the Pi, verify:

  `$GitUsrBin = `"$env:USERPROFILE\scoop\apps\git\current\usr\bin`"
  `$env:Path = `"$env:USERPROFILE\scoop\shims;`$GitUsrBin;`$env:Path`"
  ssh -o BatchMode=yes -o ConnectTimeout=10 ${PiUser}@${PiHost} `"echo ok`"
  rsync --version
  ssh -o BatchMode=yes ${PiUser}@${PiHost} `"rsync --version`"

Mirror dry-run (always -n; full excludes in wanos-sync.md E.5):

  rsync -avzn --delete -e `"ssh -o BatchMode=yes`" `
    --exclude wanos_venv/ --exclude billit_venv/ --exclude __pycache__/ `
    --exclude entity_registry.auto.yaml --exclude automations.auto.yaml `
    /c/data/git/wanos/ ${PiUser}@${PiHost}:/home/wannes/wanos/

"@
```

**Pi side** (once per Pi image, or if `rsync` missing):

```bash
sudo apt update && sudo apt install -y rsync
rsync --version
```

Bootstrap also lists `rsync` in `helpers/bootstrap/backend/apt-packages.txt`.

---

### What lives where

| Item | Location |
|------|----------|
| Host / user / remote paths | `wanos-sync.config.txt` `[PiSsh]` (and later rsync root) |
| Private SSH key | Windows `%USERPROFILE%\.ssh\` (e.g. `id_ed25519`) — **never commit** |
| Public key on Pi | `~wannes/.ssh/authorized_keys` |
| Known hosts | `%USERPROFILE%\.ssh\known_hosts` |
| Optional passphrase unlock | Windows OpenSSH Authentication Agent |
| Samba (optional browse) | Windows Credential Manager / mapped drive — **not used by target sync** |

### Detail (reference)

Use the greenfield script above first. Sections A–F below expand individual steps and alternatives.

### A. OpenSSH Client on Windows

1. Install (elevated PowerShell), or use Settings → Apps → Optional features → **OpenSSH Client**:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
Get-WindowsCapability -Online -Name OpenSSH.Client*
```

2. Confirm on PATH:

```powershell
ssh -V
Get-Command ssh, scp, sftp
```

(`scp`/`sftp` come with OpenSSH; **rsync is separate** — see section E.)

3. Optional — Authentication Agent (passphrase keys + non-interactive sync):

```powershell
# Elevated PowerShell
Get-Service ssh-agent
Set-Service -Name ssh-agent -StartupType Automatic
Start-Service ssh-agent
```

### B. Create an SSH key (once per PC)

No admin required. Prefer PowerShell so `$env:USERPROFILE` expands correctly:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -C "wanos-sync-pc" -f "$env:USERPROFILE\.ssh\id_ed25519"
```

cmd equivalent:

```bat
ssh-keygen -t ed25519 -C "wanos-sync-pc" -f %USERPROFILE%\.ssh\id_ed25519
```

- Empty passphrase = simplest for BatchMode scripts; or set a passphrase and `ssh-add` (below).
- Public: `id_ed25519.pub`. Private: `id_ed25519` — never copy to the Pi or commit to git.

Show the public line (you will append this on the Pi):

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

### C. Install the public key on the Pi

Use the SSH target from `[PiSsh]` in `wanos-sync.config.txt` (today: user `wannes`, host `10.32.251.30`). If you change those keys, use the new values in the commands below.

#### C.1 Prepare `~/.ssh` on the Pi (as `wannes`)

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
# Only if files were created as another user:
# chown -R wannes:wannes ~/.ssh
```

#### C.2 Append `id_ed25519.pub` (one line) into `authorized_keys`

**Preferred — from the Windows PC** (password SSH still OK for this one-time step):

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | ssh wannes@10.32.251.30 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

**Alternative — scp file then append on Pi:**

```powershell
scp "$env:USERPROFILE\.ssh\id_ed25519.pub" wannes@10.32.251.30:~/id_ed25519.pub
```

On the Pi as `wannes`:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat ~/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
rm ~/id_ed25519.pub
```

**Manual:** paste the single line from `id_ed25519.pub` into `~/.ssh/authorized_keys` (e.g. `nano`), then `chmod 600 ~/.ssh/authorized_keys`.

Pi account needs read/write on the WanOS deploy tree and read on `/var/log/wanos`.

### D. First connect & BatchMode check

From the PC:

```powershell
ssh wannes@10.32.251.30
```

Accept host key once (script may use `StrictHostKeyChecking=accept-new`). Then verify **non-interactive** auth:

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=10 wannes@10.32.251.30 "echo ok"
```

Must print `ok` with **no** password prompt. If this fails, sync will soft-fail or abort on SSH jobs.

Agent (if the key has a passphrase):

```powershell
ssh-add "$env:USERPROFILE\.ssh\id_ed25519"
ssh-add -l
```

If host key changed after a Pi reinstall:

```powershell
ssh-keygen -R 10.32.251.30
ssh wannes@10.32.251.30
```

### E. Install rsync on Windows (preferred transfer)

Windows does **not** ship rsync. OpenSSH (`ssh`/`scp`) alone is not enough — install rsync separately and keep it on PATH for the same user that runs `wanos-sync.bat`.

The Pi side is covered by bootstrap (`helpers/bootstrap/backend/apt-packages.txt` includes `rsync`). If an older Pi image lacks it:

```bash
sudo apt update && sudo apt install -y rsync
rsync --version
```

#### E.1 Scoop (`rsync-msys2`) — same as greenfield script

`rsync` is **not** in Scoop's `main` or `extras` buckets. The greenfield script installs **`rsync-msys2`** from the `raisercostin` bucket:

```powershell
scoop install git
scoop bucket add raisercostin https://github.com/raisercostin/raiser-scoop-bucket
scoop install rsync-msys2
```

**Do not** run `scoop install rsync` — that manifest does not exist.

`rsync-msys2` depends on MSYS DLLs from Scoop **git**. If `where.exe rsync` works but `rsync --version` prints nothing, add Git's `usr\bin` to your user PATH (the greenfield script does this automatically):

```powershell
$GitUsrBin = "$env:USERPROFILE\scoop\apps\git\current\usr\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$GitUsrBin;$userPath", "User")
$env:Path = "$env:USERPROFILE\scoop\shims;$GitUsrBin;$env:Path"
rsync --version
```

For SSH with this build, the bucket installs **`sshgit`** (Git's MSYS ssh). Example: `rsync -avz -e sshgit ...` — see manifest notes if Windows OpenSSH and rsync disagree.

#### E.2 Alternative — Chocolatey (admin)

```powershell
# Elevated PowerShell; Chocolatey must already be installed
choco install rsync -y

where.exe rsync
rsync --version
```

#### E.3 Alternative — MSYS2

1. Install [MSYS2](https://www.msys2.org/).
2. In the **MSYS2 UCRT64** (or MINGW64) shell:

```bash
pacman -Syu
pacman -S rsync
```

3. Add the MSYS2 `usr\bin` (or the environment’s `bin`) to your **user** PATH, e.g. `C:\msys64\usr\bin`, then open a new PowerShell:

```powershell
where.exe rsync
rsync --version
```

#### E.4 Alternative — WSL

Useful if you already use WSL; path mapping is awkward for a `.bat` wrapper (`C:\data\...` → `/mnt/c/data/...`).

```powershell
wsl --install
```

Inside WSL (Ubuntu):

```bash
sudo apt update && sudo apt install -y rsync
rsync --version
```

From PowerShell (example):

```powershell
wsl rsync --version
# Later: wsl rsync -avz -e ssh ... /mnt/c/data/git/wanos/ wannes@host:/home/wannes/wanos/
```

Prefer Scoop/Chocolatey/MSYS2 for `wanos-sync` so the script can call `rsync` directly without `wsl`.

#### E.5 Verify + smoke over SSH

Run in PowerShell **after** greenfield steps 1–6. Ensure Git MSYS `usr\bin` is on PATH (greenfield step 3) — required for `rsync --version` to work.

```powershell
$GitUsrBin = "$env:USERPROFILE\scoop\apps\git\current\usr\bin"
$env:Path = "$env:USERPROFILE\scoop\shims;$GitUsrBin;$env:Path"

# Tools
where.exe rsync
rsync --version
ssh -V

# SSH key auth (must print ok, no password prompt)
ssh -o BatchMode=yes -o ConnectTimeout=10 wannes@10.32.251.30 "echo ok"
ssh -o BatchMode=yes wannes@10.32.251.30 "rsync --version"
```

**MSYS2 rsync** (Scoop `rsync-msys2`): local paths must use **`/c/...`**, not `C:/...` — otherwise rsync treats `C` as a remote host (*"source and destination cannot both be remote"*).

**Mirror dry-run** — always `-n` first. `--delete` without Pi-only excludes would wipe `wanos_venv/` on the Pi; excludes below match `wanos-sync.config.txt` `[MirrorExcludeDirs]` / key file patterns:

```powershell
rsync -avzn --delete `
  -e "ssh -o BatchMode=yes" `
  --exclude .git/ --exclude .idea/ --exclude .venv/ `
  --exclude docs/ --exclude code-import/ --exclude bootstrap/ `
  --exclude logs/ --exclude temp/ --exclude backup*/ `
  --exclude wanos_venv/ --exclude migration_venv/ --exclude billit_venv/ `
  --exclude __pycache__/ `
  --exclude entity_registry.auto.yaml --exclude automations.auto.yaml `
  --exclude wanos-nvram.json --exclude wanos-nvram.json.tmp `
  --exclude .lgd-nfy0 --exclude "*.db" --exclude ".env*" `
  "/c/data/git/wanos/" `
  "wannes@10.32.251.30:/home/wannes/wanos/"
```

Expect mostly file updates under the repo tree — **not** thousands of `deleting wanos_venv/...`. End with `(DRY RUN)`.

**Repo pull** (Job 2). No filename printed = local already matches Pi (normal). Use `--itemize-changes` to confirm (`.` = unchanged):

```powershell
rsync -avz --itemize-changes `
  -e "ssh -o BatchMode=yes" `
  "wannes@10.32.251.30:/home/wannes/wanos/entity_registry.auto.yaml" `
  "/c/data/git/wanos/"
```

For **Pi-wins** repo files (`StatsRepoPull`), force overwrite even when timestamps differ:

```powershell
rsync -avz --ignore-times `
  -e "ssh -o BatchMode=yes" `
  "wannes@10.32.251.30:/home/wannes/wanos/entity_registry.auto.yaml" `
  "/c/data/git/wanos/"
```

**Log pull** (Job 3):

```powershell
New-Item -ItemType Directory -Force -Path "C:\data\OneDrive\data\professional\wanos\logs\var-log-wanos" | Out-Null
rsync -avz `
  -e "ssh -o BatchMode=yes" `
  "wannes@10.32.251.30:/var/log/wanos/wanos*" `
  "/c/data/OneDrive/data/professional/wanos/logs/var-log-wanos/"
```

**SSH post-quantum warning** on LAN (`store now, decrypt later`) is informational — safe to ignore for home Pi sync.

Target implementation will generate `--exclude-from` from `wanos-sync.config.txt` instead of hand-maintaining the list above.

### F. Samba vs sync

Mapped `Z:` can remain for browsing. After migration, `wanos-sync` must not call `require_z` or copy via SMB — **SSH + rsync only**.

---

## Migration todo

1. Confirm SSH BatchMode login (section D).
2. Install rsync on the PC; confirm `rsync --version` in the same environment the `.bat` uses.
3. Confirm remote WanOS root on the Pi (expected `/home/wannes/wanos`); add e.g. `RemoteRoot=/home/wannes/wanos` to `[PiSsh]` in config.
4. Implement Job 1 (mirror) with rsync over SSH + current exclude lists (`--delete` only within allowed tree; never delete excluded Pi-only dirs).
5. Implement Job 2 (stats / repo pull) with rsync over SSH + include / repo-pull rules.
6. Switch Job 3 (logs) from `scp` to rsync (same remote dir / local subdir).
7. Remove `Z:` requirement from `test` / `run`.
8. Keep LF normalization on real runs.
9. Split `code-import` to a separate switch requiring a Windows folder path; remove from default `run`.
10. Deduplicate Mode banner; refresh bat help and this doc’s “today” sections when done.
11. Smoke: `test` then `run`; confirm repo YAML, OneDrive DBs/NVRAM, and `var-log-wanos` logs.

---

## Safety rules (do not break)

- Never push Pi-owned YAML/DBs/NVRAM from PC in the same workflow that pulls them (push+pull fight).
- Never run mirror **`rsync --delete`** without full `[MirrorExcludeDirs]` / `[MirrorExcludeFiles]` — always dry-run (`-n`) first.
- Never delete Pi venvs / `__pycache__` / other Pi-only trees via mirror delete.
- Never commit private keys, `.env*`, or Samba passwords.
- `.ps1` stays **ASCII-only** (or UTF-8 BOM): Windows PowerShell 5.1 otherwise misreads Unicode punctuation and can break parsing.
- Log / SSH failures should not silently report overall success if you later make SSH mandatory for all jobs; today log pull soft-fails so Samba jobs can still finish.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `Z: drive is not reachable` | Today’s modes need Samba map; after migration this check goes away |
| `Host key verification failed` | New/changed Pi key; `ssh-keygen -R 10.32.251.30` then reconnect, or fix real MiTM |
| `Permission denied (publickey)` | Pubkey not in `authorized_keys`, wrong user, or agent missing passphrase key |
| BatchMode fails but interactive works | Passphrase key not in agent, or wrong key selected |
| `rsync` / `ssh` not found | Not on PATH for the account that runs the `.bat` |
| Scripts fail on Pi after push | CRLF left in `*.sh` — run real `run` normalize, or fix endings |
| Repo YAML thrashing | Still mirroring excluded Pi-owned files, or pull not using Pi-wins for repo patterns |
| `rsync --version` prints nothing | MSYS DLL missing — add Scoop git `usr\bin` to user PATH (greenfield step 3) |
| Pull shows no filename, small sent/received | File already in sync — use `--itemize-changes`; use `--ignore-times` for Pi-wins repo YAML |
| Thousands of `deleting wanos_venv/...` in dry-run | Mirror `--delete` missing venv excludes — do not run without `-n`; see E.5 full exclude list |
| `The source and destination cannot both be remote` | MSYS rsync parsed `C:/...` as host `C` — use `/c/data/...` for local paths |
| Huge unexpected deletes (other) | Mirror `--delete` without matching excludes — dry-run (`-n`) first |

---

## Quick reference

```powershell
# PATH (each new shell, until user PATH is set permanently)
$GitUsrBin = "$env:USERPROFILE\scoop\apps\git\current\usr\bin"
$env:Path = "$env:USERPROFILE\scoop\shims;$GitUsrBin;$env:Path"

# SSH smoke
ssh -o BatchMode=yes wannes@10.32.251.30 "echo ok"
ssh -o BatchMode=yes wannes@10.32.251.30 "ls -lh /var/log/wanos/wanos*"

# rsync smoke — see E.5 for full mirror excludes
rsync -avzn --delete -e "ssh -o BatchMode=yes" --exclude wanos_venv/ /c/data/git/wanos/ wannes@10.32.251.30:/home/wannes/wanos/
```

```text
# Sync script (today — still uses Z: + scp for logs until migration)
helpers\wanos-sync.bat test verbose
helpers\wanos-sync.bat run verbose
```

Config patterns and `[PiSsh]` defaults: see `wanos-sync.config.txt`. Engine paths: see top of `wanos-sync.ps1`.
