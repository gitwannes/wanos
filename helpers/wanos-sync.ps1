<#
================================================================================
WANOS Sync Script (PowerShell)
--------------------------------------------------------------------------------
ASCII-only file on purpose: Windows PowerShell 5.1 reads .ps1 as system ANSI
unless a UTF-8 BOM is present. UTF-8 arrows/dashes/ellipsis become mojibake and
can inject smart-quotes that break parsing (e.g. Run-StatsJob never defined).

Three jobs (same idea as robocopy-sync.bat + wanos.rcj):

1) MIRROR JOB  - Local repo  -->  Pi (Z:\)   [and optionally CodeFolder]
2) STATS / PULL JOB  - Pi (Z:\)  -->  Local
3) LOG PULL JOB  - Pi /var/log/wanos  -->  StatsDest via SSH/SCP

Includes / excludes: helpers/wanos-sync.config.txt (loaded at startup).
Paths (repo, Z:, CodeFolder, StatsDest): still in this .ps1.
SSH log pull: [PiSsh] in the config (not on Samba Z:).

Modes:
   test | run | runlocal

Switches:
   -VerboseSync   Extra diagnostics (config load, validation, skips, paths)

Usage:
   powershell -NoProfile -ExecutionPolicy Bypass -File helpers\wanos-sync.ps1 -Mode test
   powershell -NoProfile -ExecutionPolicy Bypass -File helpers\wanos-sync.ps1 -Mode test -VerboseSync
================================================================================
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("test", "run", "runlocal")]
    [string]$Mode,

    # Named VerboseSync (not -Verbose) to avoid clashing with PS common parameters.
    [switch]$VerboseSync
)

# Non-terminating errors (e.g. CommandNotFound) must fail the script so the
# .bat wrapper does not print "finished OK".
$ErrorActionPreference = "Stop"

# Script-scoped so nested functions can see it
$script:VerboseSync = [bool]$VerboseSync

function Write-SyncVerbose {
    param([string]$Message)
    if ($script:VerboseSync) {
        Write-Host $Message
    }
}

# =============================================================================
# PATHS (machine-local) + load includes/excludes from config file
# =============================================================================

# Directories scanned for *.sh line-ending normalization
$SourceDirs = @(
    "C:\data\git\wanos",
    "C:\data\git\wanos\helpers"
)

# Job 1 source = git working tree; Job 2 repo-pull destination uses the same path
$MirrorSource = "C:\data\git\wanos"
$MirrorDest   = "Z:\"   # Samba share / Pi WanOS root

$CodeFolder = "C:\data\git\wanos\code-import"
$StatsDest  = "C:\data\OneDrive\data\professional\wanos\logs"

# Includes / excludes live here (not hardcoded below)
$SyncConfigPath = Join-Path $PSScriptRoot "wanos-sync.config.txt"

# Samba/FAT timestamp fuzz (robocopy /FFT ~= 2 seconds)
$TimestampToleranceSeconds = 2

# =============================================================================
# CONFIG LOADER
# =============================================================================

function Read-WanosSyncConfig {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Sync config missing: $Path"
    }

    $sectionLists = @{
        "MirrorExcludeDirs"  = New-Object System.Collections.Generic.List[string]
        "MirrorExcludeFiles" = New-Object System.Collections.Generic.List[string]
        "StatsInclude"       = New-Object System.Collections.Generic.List[string]
        "StatsRepoPull"      = New-Object System.Collections.Generic.List[string]
    }
    $piSsh = @{
        Host           = "10.32.251.30"
        User           = "wannes"
        RemoteLogDir   = "/var/log/wanos"
        LocalLogSubdir = "var-log-wanos"
        RemoteGlob     = "wanos*"
    }
    $current = $null

    $lineNo = 0
    foreach ($raw in Get-Content -LiteralPath $Path) {
        $lineNo++
        $line = $raw.Trim()
        if ($line.Length -eq 0) { continue }
        if ($line.StartsWith("#")) { continue }

        # [SectionName]
        if ($line -match '^\[([A-Za-z0-9_]+)\]$') {
            $name = $Matches[1]
            if ($name -eq "PiSsh") {
                $current = "PiSsh"
                continue
            }
            if (-not $sectionLists.ContainsKey($name)) {
                throw "Unknown config section [$name] at line $lineNo in $Path"
            }
            $current = $name
            continue
        }

        if ($null -eq $current) {
            throw "Config value before any [Section] at line $lineNo in $Path : $line"
        }

        # Strip inline trailing comment: pattern  # comment
        if ($line -match '^(.*?)\s+#') {
            $line = $Matches[1].Trim()
            if ($line.Length -eq 0) { continue }
        }

        if ($current -eq "PiSsh") {
            if ($line -notmatch '^([A-Za-z0-9_]+)=(.*)$') {
                throw "PiSsh expects key=value at line $lineNo in $Path : $line"
            }
            $key = $Matches[1]
            $val = $Matches[2].Trim()
            if (-not $piSsh.ContainsKey($key)) {
                throw "Unknown PiSsh key '$key' at line $lineNo in $Path"
            }
            $piSsh[$key] = $val
            continue
        }

        [void]$sectionLists[$current].Add($line)
    }

    foreach ($key in @("MirrorExcludeDirs", "MirrorExcludeFiles", "StatsInclude", "StatsRepoPull")) {
        if ($sectionLists[$key].Count -eq 0) {
            throw "Config section [$key] is empty in $Path"
        }
    }

    return @{
        MirrorExcludeDirs  = @($sectionLists["MirrorExcludeDirs"])
        MirrorExcludeFiles = @($sectionLists["MirrorExcludeFiles"])
        StatsInclude       = @($sectionLists["StatsInclude"])
        StatsRepoPull      = @($sectionLists["StatsRepoPull"])
        PiSsh              = $piSsh
    }
}

Write-SyncVerbose "Loading sync config: $SyncConfigPath"
$SyncConfig = Read-WanosSyncConfig -Path $SyncConfigPath
$MirrorExcludeDirs  = $SyncConfig.MirrorExcludeDirs
$MirrorExcludeFiles = $SyncConfig.MirrorExcludeFiles
$StatsInclude       = $SyncConfig.StatsInclude
$StatsRepoPull      = $SyncConfig.StatsRepoPull
$PiSsh              = $SyncConfig.PiSsh
Write-SyncVerbose ("  MirrorExcludeDirs : {0}" -f $MirrorExcludeDirs.Count)
Write-SyncVerbose ("  MirrorExcludeFiles: {0}" -f $MirrorExcludeFiles.Count)
Write-SyncVerbose ("  StatsInclude      : {0}" -f $StatsInclude.Count)
Write-SyncVerbose ("  StatsRepoPull     : {0}" -f $StatsRepoPull.Count)
Write-SyncVerbose ("  PiSsh Host        : {0}@{1}:{2}" -f $PiSsh.User, $PiSsh.Host, $PiSsh.RemoteLogDir)
Write-SyncVerbose ""

# =============================================================================
# PATH HELPERS
# =============================================================================

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Description,
        [int]$ExitCode = 10
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Error "Required path missing: $Description --> $Path"
        exit $ExitCode
    }
}

function Ensure-Directory {
    param(
        [string]$Path,
        [switch]$DryRun
    )
    if (Test-Path -LiteralPath $Path) { return }
    if ($DryRun) {
        Write-SyncVerbose "[DRY] Would create directory: $Path"
    } else {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Write-SyncVerbose "Created directory: $Path"
    }
}

function Get-RelativePath {
    param(
        [string]$Root,
        [string]$FullPath
    )
    $rootNorm = $Root.TrimEnd("\", "/")
    $fullNorm = $FullPath
    if ($fullNorm.Length -le $rootNorm.Length) { return "" }
    return $fullNorm.Substring($rootNorm.Length).TrimStart("\", "/")
}

function Test-NameMatchesAny {
    param(
        [string]$Name,
        [string[]]$Patterns
    )
    foreach ($pattern in $Patterns) {
        if ($Name -like $pattern) { return $true }
    }
    return $false
}

# True if this relative path should be ignored for mirror copy AND mirror delete
# (robocopy /XD + /XF behaviour).
function Test-MirrorExcluded {
    param(
        [string]$RelativePath,
        [string]$FileName,
        [string[]]$ExcludeDirPatterns,
        [string[]]$ExcludeFilePatterns
    )

    if ($FileName -and (Test-NameMatchesAny -Name $FileName -Patterns $ExcludeFilePatterns)) {
        return $true
    }

    # Match each path segment so "foo\.git\bar" and top-level ".git" both hit
    $segments = $RelativePath -split "[\\/]" | Where-Object { $_ -ne "" }
    foreach ($segment in $segments) {
        if (Test-NameMatchesAny -Name $segment -Patterns $ExcludeDirPatterns) {
            return $true
        }
    }
    return $false
}

function Should-CopyFile {
    param(
        [System.IO.FileInfo]$Source,
        [System.IO.FileInfo]$Dest,
        [int]$ToleranceSeconds
    )

    # Missing on dest --> copy
    if (-not $Dest) { return $true }

    # Only copy when source is clearly newer (skip older / equal within tolerance)
    $delta = ($Source.LastWriteTimeUtc - $Dest.LastWriteTimeUtc).TotalSeconds
    return ($delta -gt $ToleranceSeconds)
}

# Samba/Z: can make Test-Path true while Get-Item throws (ghost/reparse quirks).
# With $ErrorActionPreference=Stop that aborts the whole sync - always soft-get.
function Get-ItemOrNull {
    param([string]$Path)
    return Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
}

# =============================================================================
# NORMALIZE *.sh (CRLF --> LF, UTF-8 no BOM)
# =============================================================================

function Normalize-ShFiles {
    param([string[]]$Dirs)

    Write-Host "=== NORMALIZE .sh (CRLF --> LF) ==="

    foreach ($dir in $Dirs) {
        if (-not (Test-Path -LiteralPath $dir)) {
            Write-Warning "Skipping missing directory: $dir"
            continue
        }

        # Non-recursive in repo root + helpers only (matches bat SRC_DIRS behaviour)
        Get-ChildItem -LiteralPath $dir -Filter *.sh -File -ErrorAction SilentlyContinue | ForEach-Object {
            $path = $_.FullName
            $bytes = [System.IO.File]::ReadAllBytes($path)

            try {
                $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            } catch {
                $text = [System.Text.Encoding]::Default.GetString($bytes)
            }

            # Drop UTF-8 BOM if present in the decoded string start
            if ($text.Length -gt 0 -and [int][char]$text[0] -eq 0xFEFF) {
                $text = $text.Substring(1)
            }

            $newText = $text -replace "`r`n", "`n" -replace "`r", "`n"

            if ($newText -ne $text) {
                Write-Host "Converted CRLF-->LF: $path"
                if (-not $script:DryRun) {
                    [System.IO.File]::WriteAllText($path, $newText, [System.Text.UTF8Encoding]::new($false))
                }
            } else {
                Write-SyncVerbose "Already LF: $path"
            }
        }
    }
}

# =============================================================================
# JOB 1 - MIRROR (Local --> Dest)
# =============================================================================

function Invoke-WanosMirrorJob {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$ExcludeDirs,
        [string[]]$ExcludeFiles,
        [switch]$DryRun
    )

    Write-Host "=== MIRROR JOB (Local --> Dest) ==="
    Write-SyncVerbose "Source: $Source"
    Write-SyncVerbose "Dest:   $Dest"
    Write-SyncVerbose "Note:   Pi-owned files (entity_registry.auto.yaml, *.db, ...) are excluded from copy AND delete"

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Mirror source missing: $Source"
    }

    Ensure-Directory -Path $Dest -DryRun:$DryRun
    if ($DryRun -and -not (Test-Path -LiteralPath $Dest)) {
        Write-Host "[DRY] Dest missing - skipping walk"
        return
    }

    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
    $destRoot   = (Resolve-Path -LiteralPath $Dest).Path

    # ----- Copy phase: repo --> dest (skip excluded; only if source newer) -----
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $src = $_
        $relative = Get-RelativePath -Root $sourceRoot -FullPath $src.FullName

        if (Test-MirrorExcluded -RelativePath $relative -FileName $src.Name `
                -ExcludeDirPatterns $ExcludeDirs -ExcludeFilePatterns $ExcludeFiles) {
            return
        }

        $destPath = Join-Path $destRoot $relative
        $destFile = Get-ItemOrNull -Path $destPath

        if (Should-CopyFile -Source $src -Dest $destFile -ToleranceSeconds $TimestampToleranceSeconds) {
            if ($DryRun) {
                Write-Host "[DRY] Copy: $relative"
            } else {
                $destDir = Split-Path -Parent $destPath
                if (-not (Test-Path -LiteralPath $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                Copy-Item -LiteralPath $src.FullName -Destination $destPath -Force
                Write-Host "Copy: $relative"
            }
        }
    }

    # ----- Delete phase: remove dest files not present in source -----
    # CRITICAL: must honour the same excludes as robocopy /XF+/XD, otherwise
    # Pi-only files (*.db, nvram, entity_registry.auto.yaml if ever missing locally, venvs)
    # would be wiped because they are "extra" on the destination.
    if (-not (Test-Path -LiteralPath $destRoot)) { return }

    Get-ChildItem -LiteralPath $destRoot -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $dest = $_
        $relative = Get-RelativePath -Root $destRoot -FullPath $dest.FullName

        if (Test-MirrorExcluded -RelativePath $relative -FileName $dest.Name `
                -ExcludeDirPatterns $ExcludeDirs -ExcludeFilePatterns $ExcludeFiles) {
            return
        }

        $srcPath = Join-Path $sourceRoot $relative
        if (-not (Test-Path -LiteralPath $srcPath)) {
            if ($DryRun) {
                Write-Host "[DRY] Delete: $relative"
            } else {
                Remove-Item -LiteralPath $dest.FullName -Force
                Write-Host "Delete: $relative"
            }
        }
    }
}

# =============================================================================
# JOB 2 - STATS / PULL (Pi --> Local, include-only, no deletes)
# =============================================================================

function Invoke-WanosStatsJob {
    param(
        [string]$Source,              # Pi root (Z:\)
        [string]$StatsDest,           # OneDrive logs (dbs, nvram)
        [string]$RepoDest,            # Git repo root (entity_registry.auto.yaml)
        [string[]]$IncludePatterns,
        [string[]]$RepoPullPatterns,
        [string[]]$SkipDirPatterns,   # do not walk Pi venvs etc.
        [switch]$DryRun
    )

    Write-Host "=== STATS / PULL JOB (Pi --> Local, include-only) ==="
    Write-SyncVerbose "Source (Pi):     $Source"
    Write-SyncVerbose "Stats dest:      $StatsDest"
    Write-SyncVerbose "Repo pull dest:  $RepoDest  (patterns: $($RepoPullPatterns -join ', '))"

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Stats source (Pi) missing: $Source"
    }

    Ensure-Directory -Path $StatsDest -DryRun:$DryRun
    Ensure-Directory -Path $RepoDest -DryRun:$DryRun

    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path

    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $src = $_
        $relative = Get-RelativePath -Root $sourceRoot -FullPath $src.FullName

        # Skip noisy / huge Pi trees (venvs, caches)
        $segments = $relative -split "[\\/]" | Where-Object { $_ -ne "" }
        foreach ($segment in $segments) {
            if (Test-NameMatchesAny -Name $segment -Patterns $SkipDirPatterns) {
                return
            }
        }

        # Include-only filter on file name
        if (-not (Test-NameMatchesAny -Name $src.Name -Patterns $IncludePatterns)) {
            return
        }

        # Route: system-owned YAML --> git repo; telemetry --> OneDrive logs
        $isRepoPull = Test-NameMatchesAny -Name $src.Name -Patterns $RepoPullPatterns
        $destRoot = if ($isRepoPull) { $RepoDest } else { $StatsDest }
        $destPath = Join-Path $destRoot $relative

        # entity_registry.auto.yaml lives at WanOS root on both sides - keep flat name at repo root
        if ($isRepoPull) {
            $destPath = Join-Path $RepoDest $src.Name
        }

        $destFile = Get-ItemOrNull -Path $destPath

        # Repo-pull files (entity_registry.auto.yaml): Pi is source of truth - always
        # overwrite local, even when the PC copy looks newer (stale upload / clock skew).
        # Stats/telemetry: keep newer-only so we do not thrash OneDrive logs.
        $shouldCopy = if ($isRepoPull) {
            $true
        } else {
            Should-CopyFile -Source $src -Dest $destFile -ToleranceSeconds $TimestampToleranceSeconds
        }

        if ($shouldCopy) {
            $label = if ($isRepoPull) { "REPO" } else { "STATS" }
            if ($DryRun) {
                Write-Host "[DRY] [$label] $($src.Name) --> $destPath"
            } else {
                $destDir = Split-Path -Parent $destPath
                if (-not (Test-Path -LiteralPath $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                Copy-Item -LiteralPath $src.FullName -Destination $destPath -Force
                Write-Host "[$label] $($src.Name) --> $destPath"
            }
        } else {
            Write-SyncVerbose "Skip (local newer/equal): $($src.Name)"
        }
    }
}

# =============================================================================
# JOB 3 - LOG PULL (Pi /var/log/wanos --> StatsDest via OpenSSH scp)
# Soft-fail: missing scp/ssh or auth errors do not abort mirror/stats.
# =============================================================================

function Invoke-WanosLogPullJob {
    param(
        [hashtable]$Ssh,
        [string]$StatsDest,
        [switch]$DryRun
    )

    Write-Host "=== LOG PULL JOB (Pi /var/log/wanos --> Local via SSH) ==="

    $scpCmd = Get-Command scp -ErrorAction SilentlyContinue
    $sshCmd = Get-Command ssh -ErrorAction SilentlyContinue
    if (-not $scpCmd -or -not $sshCmd) {
        Write-Host "SKIP log pull: OpenSSH scp/ssh not found on PATH"
        return
    }

    $localDir = Join-Path $StatsDest $Ssh.LocalLogSubdir
    $remoteDir = $Ssh.RemoteLogDir.TrimEnd("/")
    $remoteSpec = "{0}@{1}:{2}/{3}" -f $Ssh.User, $Ssh.Host, $remoteDir, $Ssh.RemoteGlob
    $sshTarget = "{0}@{1}" -f $Ssh.User, $Ssh.Host
    $sshOpts = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new")

    Write-SyncVerbose "Remote: $remoteSpec"
    Write-SyncVerbose "Local:  $localDir"

    Ensure-Directory -Path $localDir -DryRun:$DryRun

    if ($DryRun) {
        Write-Host "[DRY] Would scp: $remoteSpec --> $localDir\"
        $lsRemote = "ls -lh -- $remoteDir/$($Ssh.RemoteGlob) 2>/dev/null || true"
        Write-SyncVerbose "Listing remote: ssh $sshTarget $lsRemote"
        & ssh.exe @sshOpts $sshTarget $lsRemote
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARN: remote log list failed (exit $LASTEXITCODE). Check SSH key / host."
        }
        return
    }

    # Quote-free single arg so PowerShell does not expand RemoteGlob locally.
    & scp.exe @sshOpts $remoteSpec "$localDir\"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: log pull failed (exit $LASTEXITCODE). Mirror/stats already done; check SSH key / host."
        return
    }

    $copied = @(Get-ChildItem -LiteralPath $localDir -File -Force -ErrorAction SilentlyContinue |
        Where-Object { Test-NameMatchesAny -Name $_.Name -Patterns @($Ssh.RemoteGlob) })
    Write-Host ("LOG: pulled {0} file(s) --> {1}" -f $copied.Count, $localDir)
    foreach ($f in $copied) {
        Write-SyncVerbose ("  {0}  ({1:N0} bytes)" -f $f.Name, $f.Length)
    }
}

# =============================================================================
# VALIDATION (after all functions are defined)
# =============================================================================

Write-SyncVerbose "Validating configured paths..."
Write-Host "Mode: $Mode"
Write-SyncVerbose "Timestamp: $(Get-Date)"
Write-SyncVerbose ""

Assert-PathExists -Path $MirrorSource -Description "Mirror source (repo)" -ExitCode 11

if ($Mode -ne "runlocal") {
    Assert-PathExists -Path $MirrorDest -Description "Mirror destination (Pi Z:)" -ExitCode 12
}

foreach ($dir in $SourceDirs) {
    Assert-PathExists -Path $dir -Description "Normalization source directory" -ExitCode 15
}

$DryRun = ($Mode -eq "test")

# CodeFolder / StatsDest are created on demand (bat already behaved this way for CodeFolder)
if ($Mode -eq "runlocal" -or $Mode -eq "run" -or $Mode -eq "test") {
    Ensure-Directory -Path $CodeFolder -DryRun:$DryRun
}
if ($Mode -ne "runlocal") {
    Ensure-Directory -Path $StatsDest -DryRun:$DryRun
}

# =============================================================================
# MODE DISPATCH
# =============================================================================

if ($Mode -eq "run" -or $Mode -eq "runlocal") {
    Normalize-ShFiles -Dirs $SourceDirs
}

# Job 1: push code
if ($Mode -eq "runlocal") {
    Invoke-WanosMirrorJob -Source $MirrorSource -Dest $CodeFolder `
        -ExcludeDirs $MirrorExcludeDirs -ExcludeFiles $MirrorExcludeFiles -DryRun:$DryRun
} else {
    # test / run --> Pi
    Invoke-WanosMirrorJob -Source $MirrorSource -Dest $MirrorDest `
        -ExcludeDirs $MirrorExcludeDirs -ExcludeFiles $MirrorExcludeFiles -DryRun:$DryRun

    # run also mirrors into CodeFolder (parity with robocopy-sync.bat)
    if ($Mode -eq "run") {
        Write-Host ""
        Invoke-WanosMirrorJob -Source $MirrorSource -Dest $CodeFolder `
            -ExcludeDirs $MirrorExcludeDirs -ExcludeFiles $MirrorExcludeFiles -DryRun:$DryRun
    }
}

# Job 2: pull from Pi (not in runlocal)
if ($Mode -ne "runlocal") {
    Write-Host ""
    # Reuse mirror dir-excludes so we do not recurse into wanos_venv etc. on Z:\
    Invoke-WanosStatsJob `
        -Source $MirrorDest `
        -StatsDest $StatsDest `
        -RepoDest $MirrorSource `
        -IncludePatterns $StatsInclude `
        -RepoPullPatterns $StatsRepoPull `
        -SkipDirPatterns $MirrorExcludeDirs `
        -DryRun:$DryRun

    # Job 3: application logs under /var/log/wanos (SSH; not on Samba Z:)
    Write-Host ""
    Invoke-WanosLogPullJob -Ssh $PiSsh -StatsDest $StatsDest -DryRun:$DryRun
}

Write-Host ""
Write-Host "Done."
