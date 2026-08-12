<#
================================================================================
WANOS Sync Script (PowerShell)
--------------------------------------------------------------------------------
ASCII-only file on purpose: Windows PowerShell 5.1 reads .ps1 as system ANSI
unless a UTF-8 BOM is present. UTF-8 arrows/dashes/ellipsis become mojibake and
can inject smart-quotes that break parsing.

Three jobs (rsync over SSH -- no Samba/Z:):

1) MIRROR JOB  - Local repo  -->  Pi WanOS root (rsync --delete + excludes)
2) STATS / PULL JOB  - Pi  -->  Local (repo YAML Pi-wins; telemetry to StatsDest)
3) LOG PULL JOB  - Pi /var/log/wanos  -->  StatsDest (or StatsDest\<LocalLogSubdir>)

Includes / excludes: helpers/wanos-sync.config.txt
Paths (repo, StatsDest): in this .ps1. Remote host/paths: [PiSsh] in config.

Modes:
   test | run | codeimport

Switches:
   -VerboseSync              Extra diagnostics
   -CodeImportPath <folder>  Required for mode codeimport

Usage:
   powershell -NoProfile -ExecutionPolicy Bypass -File helpers\wanos-sync.ps1 -Mode test
   powershell -NoProfile -ExecutionPolicy Bypass -File helpers\wanos-sync.ps1 -Mode run -VerboseSync
   powershell -NoProfile -ExecutionPolicy Bypass -File helpers\wanos-sync.ps1 -Mode codeimport -CodeImportPath C:\data\git\wanos\code-import
================================================================================
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("test", "run", "codeimport")]
    [string]$Mode,

    [string]$CodeImportPath = "",

    # Named VerboseSync (not -Verbose) to avoid clashing with PS common parameters.
    [switch]$VerboseSync
)

$ErrorActionPreference = "Stop"
$script:VerboseSync = [bool]$VerboseSync

function Write-SyncVerbose {
    param([string]$Message)
    if ($script:VerboseSync) {
        Write-Host $Message -ForegroundColor DarkGray
    }
}

function Write-SyncJobHeader {
    param([string]$Message)
    Write-Host $Message -ForegroundColor White
}

function Write-SyncSection {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-SyncDone {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-SyncFileLine {
    param([string]$Line)
    if ($Line -match '^deleting |Delete:|\[DRY\] Delete:') {
        Write-Host $Line -ForegroundColor Red
    } else {
        Write-Host $Line -ForegroundColor Yellow
    }
}

# =============================================================================
# PATHS (machine-local)
# =============================================================================

$SourceDirs = @(
    "C:\data\git\wanos",
    "C:\data\git\wanos\helpers"
)

$MirrorSource = "C:\data\git\wanos"
$StatsDest    = "C:\data\OneDrive\data\professional\wanos\logs"
$SyncConfigPath = Join-Path $PSScriptRoot "wanos-sync.config.txt"

# =============================================================================
# CONFIG LOADER
# =============================================================================

function Read-WanosSyncConfig {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Sync config missing: $Path"
    }

    $sectionLists = @{
        "MirrorBootstrapFiles" = New-Object System.Collections.Generic.List[string]
        "MirrorExcludeDirs"  = New-Object System.Collections.Generic.List[string]
        "MirrorExcludeFiles" = New-Object System.Collections.Generic.List[string]
        "StatsInclude"       = New-Object System.Collections.Generic.List[string]
        "StatsRepoPull"      = New-Object System.Collections.Generic.List[string]
    }
    $piSsh = @{
        Host           = "10.32.251.30"
        User           = "wannes"
        RemoteRoot     = "/home/wannes/wanos"
        RemoteLogDir   = "/var/log/wanos"
        LocalLogSubdir = ""
        RemoteGlob     = "wanos*"
    }
    $current = $null

    $lineNo = 0
    foreach ($raw in Get-Content -LiteralPath $Path) {
        $lineNo++
        $line = $raw.Trim()
        if ($line.Length -eq 0) { continue }
        if ($line.StartsWith("#")) { continue }

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

    if ([string]::IsNullOrWhiteSpace($piSsh.RemoteRoot)) {
        throw "PiSsh RemoteRoot is required in $Path"
    }

    return @{
        MirrorBootstrapFiles = @($sectionLists["MirrorBootstrapFiles"])
        MirrorExcludeDirs  = @($sectionLists["MirrorExcludeDirs"])
        MirrorExcludeFiles = @($sectionLists["MirrorExcludeFiles"])
        StatsInclude       = @($sectionLists["StatsInclude"])
        StatsRepoPull      = @($sectionLists["StatsRepoPull"])
        PiSsh              = $piSsh
    }
}

Write-SyncVerbose "Loading sync config: $SyncConfigPath"
$SyncConfig = Read-WanosSyncConfig -Path $SyncConfigPath
$MirrorBootstrapFiles = $SyncConfig.MirrorBootstrapFiles
$MirrorExcludeDirs  = $SyncConfig.MirrorExcludeDirs
$MirrorExcludeFiles = $SyncConfig.MirrorExcludeFiles
$StatsInclude       = $SyncConfig.StatsInclude
$StatsRepoPull      = $SyncConfig.StatsRepoPull
$PiSsh              = $SyncConfig.PiSsh
Write-SyncVerbose ("  MirrorBootstrapFiles: {0}" -f $MirrorBootstrapFiles.Count)
Write-SyncVerbose ("  MirrorExcludeDirs : {0}" -f $MirrorExcludeDirs.Count)
Write-SyncVerbose ("  MirrorExcludeFiles: {0}" -f $MirrorExcludeFiles.Count)
Write-SyncVerbose ("  StatsInclude      : {0}" -f $StatsInclude.Count)
Write-SyncVerbose ("  StatsRepoPull     : {0}" -f $StatsRepoPull.Count)
Write-SyncVerbose ("  PiSsh             : {0}@{1}:{2}" -f $PiSsh.User, $PiSsh.Host, $PiSsh.RemoteRoot)
Write-SyncVerbose ""

# =============================================================================
# PATH / TOOL HELPERS
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

    $segments = $RelativePath -split "[\\/]" | Where-Object { $_ -ne "" }
    foreach ($segment in $segments) {
        if (Test-NameMatchesAny -Name $segment -Patterns $ExcludeDirPatterns) {
            return $true
        }
    }
    return $false
}

function Get-ItemOrNull {
    param([string]$Path)
    return Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
}

# C:\data\foo -> /c/data/foo  (MSYS2 / Scoop rsync-msys2)
function ConvertTo-RsyncLocalPath {
    param([string]$WindowsPath)

    $full = [System.IO.Path]::GetFullPath($WindowsPath)
    if ($full -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1].ToLowerInvariant()
        $rest = ($Matches[2] -replace '\\', '/')
        return "/{0}/{1}" -f $drive, $rest.TrimEnd('/')
    }
    return ($full -replace '\\', '/')
}

function Initialize-RsyncEnvironment {
    $candidates = @(
        (Join-Path $env:USERPROFILE "scoop\shims"),
        (Join-Path $env:USERPROFILE "scoop\apps\git\current\usr\bin")
    )
    foreach ($dir in $candidates) {
        if (Test-Path -LiteralPath $dir) {
            if ($env:Path -notlike ("*{0}*" -f $dir)) {
                $env:Path = "{0};{1}" -f $dir, $env:Path
            }
        }
    }
    # Avoid MSYS rewriting Windows paths / eating drive letters in args
    $env:MSYS_NO_PATHCONV = "1"
}

function Assert-RsyncAvailable {
    Initialize-RsyncEnvironment
    $cmd = Get-Command rsync -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Error "rsync not found on PATH. See docs\wanos-sync.md (Scoop rsync-msys2 + Git usr\bin)."
        exit 20
    }
    $ssh = Get-Command ssh -ErrorAction SilentlyContinue
    if (-not $ssh) {
        Write-Error "ssh not found on PATH. Install OpenSSH Client."
        exit 21
    }
    Write-SyncVerbose ("rsync: {0}" -f $cmd.Source)
    Write-SyncVerbose ("ssh:   {0}" -f $ssh.Source)
}

function Get-SshRsyncShellArg {
    # LogLevel=ERROR hides OpenSSH post-quantum banner noise on LAN.
    return "ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR"
}

function Get-RemoteSpec {
    param(
        [hashtable]$Ssh,
        [string]$RemotePath
    )
    $path = $RemotePath.TrimEnd("/")
    return "{0}@{1}:{2}" -f $Ssh.User, $Ssh.Host, $path
}

function Test-RemoteFileExists {
    param(
        [hashtable]$Ssh,
        [string]$RemoteFilePath
    )
    $remote = "{0}@{1}" -f $Ssh.User, $Ssh.Host
    # Single remote argv: test -f '<path>' (path embedded; Pi paths have no single quotes)
    $script = "test -f '$RemoteFilePath' && echo yes || echo no"
    $out = & ssh.exe -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR $remote $script 2>$null
    return ($out -match "yes")
}

function ConvertTo-RsyncExcludeArgs {
    param(
        [string[]]$ExcludeDirs,
        [string[]]$ExcludeFiles
    )

    # Use --exclude=PATTERN (one argv). Bare "*" / "*.db" as separate argv is
    # expanded by MSYS runtime and breaks rsync ("Unexpected remote arg").
    $args = New-Object System.Collections.Generic.List[string]
    foreach ($d in $ExcludeDirs) {
        if ($d -match '[\*\?\[]') {
            [void]$args.Add(("--exclude={0}" -f $d))
        } else {
            [void]$args.Add(("--exclude={0}/" -f $d.TrimEnd('/', '\')))
        }
    }
    foreach ($f in $ExcludeFiles) {
        [void]$args.Add(("--exclude={0}" -f $f))
    }
    return @($args)
}

function Test-RsyncNoiseLine {
    param([string]$Line)

    if ([string]::IsNullOrWhiteSpace($Line)) { return $true }
    if ($Line -match '^\*\*') { return $true }
    if ($Line -match 'post-quantum|store now, decrypt|server may need to be upgraded') { return $true }
    if ($Line -match '^(sending|receiving) incremental file list') { return $true }
    if ($Line -match '^receiving file list') { return $true }
    if ($Line -match '^sent \d+') { return $true }
    if ($Line -match '^total size is') { return $true }
    if ($Line -eq './') { return $true }
    # Directory-only markers from rsync -a (keep "deleting dir/" though)
    if ($Line -match '/$' -and $Line -notmatch '^deleting ') { return $true }
    return $false
}

function Invoke-Rsync {
    param(
        [string[]]$RsyncArgs,
        [string]$FailMessage
    )

    Write-SyncVerbose ("rsync {0}" -f ($RsyncArgs -join " "))
    $raw = & rsync.exe @RsyncArgs 2>&1
    $rc = $LASTEXITCODE

    foreach ($item in @($raw)) {
        if ($null -eq $item) { continue }
        $text = if ($item -is [System.Management.Automation.ErrorRecord]) {
            $item.ToString()
        } else {
            "$item"
        }
        if ($script:VerboseSync) {
            if (Test-RsyncNoiseLine -Line $text) {
                Write-Host $text -ForegroundColor DarkGray
            } else {
                Write-SyncFileLine -Line $text
            }
        } elseif (-not (Test-RsyncNoiseLine -Line $text)) {
            Write-SyncFileLine -Line $text
        }
    }

    if ($rc -ne 0) {
        throw ("{0} (rsync exit {1})" -f $FailMessage, $rc)
    }
}

# =============================================================================
# NORMALIZE *.sh (CRLF --> LF, UTF-8 no BOM)
# =============================================================================

function Normalize-ShFiles {
    param([string[]]$Dirs)

    Write-Host "=== NORMALIZE .sh (CRLF --> LF) ===" -ForegroundColor White

    foreach ($dir in $Dirs) {
        if (-not (Test-Path -LiteralPath $dir)) {
            Write-Warning "Skipping missing directory: $dir"
            continue
        }

        Get-ChildItem -LiteralPath $dir -Filter *.sh -File -ErrorAction SilentlyContinue | ForEach-Object {
            $path = $_.FullName
            $bytes = [System.IO.File]::ReadAllBytes($path)

            try {
                $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            } catch {
                $text = [System.Text.Encoding]::Default.GetString($bytes)
            }

            if ($text.Length -gt 0 -and [int][char]$text[0] -eq 0xFEFF) {
                $text = $text.Substring(1)
            }

            $newText = $text -replace "`r`n", "`n" -replace "`r", "`n"

            if ($newText -ne $text) {
                Write-Host "Converted CRLF-->LF: $path" -ForegroundColor Yellow
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
# LOCAL MIRROR (codeimport only -- no SSH)
# =============================================================================

function Invoke-WanosLocalMirrorJob {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$ExcludeDirs,
        [string[]]$ExcludeFiles,
        [switch]$DryRun
    )

    Write-SyncJobHeader "=== LOCAL MIRROR (Local --> CodeImport folder) ==="
    Write-SyncVerbose "Source: $Source"
    Write-SyncVerbose "Dest:   $Dest"

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Mirror source missing: $Source"
    }

    Ensure-Directory -Path $Dest -DryRun:$DryRun
    if ($DryRun -and -not (Test-Path -LiteralPath $Dest)) {
        Write-Host "[DRY] Dest missing - skipping walk" -ForegroundColor DarkYellow
        return
    }

    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
    $destRoot   = (Resolve-Path -LiteralPath $Dest).Path

    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $src = $_
        $relative = Get-RelativePath -Root $sourceRoot -FullPath $src.FullName

        if (Test-MirrorExcluded -RelativePath $relative -FileName $src.Name `
                -ExcludeDirPatterns $ExcludeDirs -ExcludeFilePatterns $ExcludeFiles) {
            return
        }

        $destPath = Join-Path $destRoot $relative
        $destFile = Get-ItemOrNull -Path $destPath
        $shouldCopy = $true
        if ($destFile) {
            $delta = ($src.LastWriteTimeUtc - $destFile.LastWriteTimeUtc).TotalSeconds
            $shouldCopy = ($delta -gt 2)
        }

        if ($shouldCopy) {
            if ($DryRun) {
                Write-SyncFileLine -Line ("[DRY] Copy: {0}" -f $relative)
            } else {
                $destDir = Split-Path -Parent $destPath
                if (-not (Test-Path -LiteralPath $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                Copy-Item -LiteralPath $src.FullName -Destination $destPath -Force
                Write-SyncFileLine -Line ("Copy: {0}" -f $relative)
            }
        }
    }

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
                Write-SyncFileLine -Line ("[DRY] Delete: {0}" -f $relative)
            } else {
                Remove-Item -LiteralPath $dest.FullName -Force
                Write-SyncFileLine -Line ("Delete: {0}" -f $relative)
            }
        }
    }
}

# =============================================================================
# JOB 0 - BOOTSTRAP (Local --> Pi when remote file missing)
# =============================================================================

function Invoke-WanosBootstrapPushJob {
    param(
        [string]$Source,
        [hashtable]$Ssh,
        [string[]]$BootstrapFiles,
        [switch]$DryRun
    )

    if ($BootstrapFiles.Count -eq 0) {
        return
    }

    Write-SyncJobHeader "=== BOOTSTRAP (Local --> Pi when missing) ==="
    $remoteRoot = $Ssh.RemoteRoot.TrimEnd("/")
    $sshShell = Get-SshRsyncShellArg
    $repoLocal = ConvertTo-RsyncLocalPath -WindowsPath $Source
    if (-not $repoLocal.EndsWith("/")) { $repoLocal = $repoLocal + "/" }

    foreach ($name in $BootstrapFiles) {
        $localPath = Join-Path $Source $name
        if (-not (Test-Path -LiteralPath $localPath)) {
            Write-Host ("Bootstrap skip (missing locally): {0}" -f $name) -ForegroundColor DarkYellow
            continue
        }

        $remoteFilePath = "{0}/{1}" -f $remoteRoot, $name
        if (Test-RemoteFileExists -Ssh $Ssh -RemoteFilePath $remoteFilePath) {
            Write-SyncVerbose ("Bootstrap skip (exists on Pi): {0}" -f $name)
            continue
        }

        $remoteFile = Get-RemoteSpec -Ssh $Ssh -RemotePath $remoteFilePath
        $args = New-Object System.Collections.Generic.List[string]
        [void]$args.Add("-avz")
        if ($DryRun) { [void]$args.Add("-n") }
        [void]$args.Add("-e")
        [void]$args.Add($sshShell)
        [void]$args.Add((ConvertTo-RsyncLocalPath -WindowsPath $localPath))
        [void]$args.Add($remoteFile)

        Write-SyncSection ("** BOOTSTRAP: {0} --> Pi" -f $name)
        Invoke-Rsync -RsyncArgs @($args) -FailMessage ("Bootstrap push failed for {0}" -f $name)
        Write-SyncDone ("* BOOTSTRAP: {0} done" -f $name)
        Write-Host ""
    }
}

# =============================================================================
# JOB 1 - MIRROR (Local --> Pi via rsync)
# =============================================================================

function Invoke-WanosRsyncMirrorJob {
    param(
        [string]$Source,
        [hashtable]$Ssh,
        [string[]]$ExcludeDirs,
        [string[]]$ExcludeFiles,
        [switch]$DryRun
    )

    Write-SyncJobHeader "=== MIRROR JOB (Local --> Pi via rsync/SSH) ==="

    $local = ConvertTo-RsyncLocalPath -WindowsPath $Source
    if (-not $local.EndsWith("/")) { $local = $local + "/" }
    $remote = (Get-RemoteSpec -Ssh $Ssh -RemotePath $Ssh.RemoteRoot)
    if (-not $remote.EndsWith("/")) { $remote = $remote + "/" }

    Write-SyncVerbose "Source: $local"
    Write-SyncVerbose "Dest:   $remote"

    $rsyncArgs = New-Object System.Collections.Generic.List[string]
    [void]$rsyncArgs.Add("-avz")
    if ($DryRun) { [void]$rsyncArgs.Add("-n") }
    [void]$rsyncArgs.Add("--delete")
    [void]$rsyncArgs.Add("-e")
    [void]$rsyncArgs.Add((Get-SshRsyncShellArg))

    foreach ($ex in (ConvertTo-RsyncExcludeArgs -ExcludeDirs $ExcludeDirs -ExcludeFiles $ExcludeFiles)) {
        [void]$rsyncArgs.Add($ex)
    }

    [void]$rsyncArgs.Add($local)
    [void]$rsyncArgs.Add($remote)

    Write-SyncSection "** rsync mirror Local --> Pi (see list below)"
    Invoke-Rsync -RsyncArgs @($rsyncArgs) -FailMessage "Mirror push failed"
    Write-Host ""
    Write-SyncDone "MIRROR: done"
}

# =============================================================================
# JOB 2 - STATS / PULL (Pi --> Local via rsync)
# =============================================================================

function Invoke-WanosRsyncStatsJob {
    param(
        [hashtable]$Ssh,
        [string]$StatsDest,
        [string]$RepoDest,
        [string[]]$IncludePatterns,
        [string[]]$RepoPullPatterns,
        [string[]]$SkipDirPatterns,
        [switch]$DryRun
    )

    Write-SyncJobHeader "=== STATS / PULL JOB (Pi --> Local via rsync/SSH) ==="

    Ensure-Directory -Path $StatsDest -DryRun:$DryRun
    Ensure-Directory -Path $RepoDest -DryRun:$DryRun

    $remoteRoot = $Ssh.RemoteRoot.TrimEnd("/")
    $sshShell = Get-SshRsyncShellArg
    $repoLocal = ConvertTo-RsyncLocalPath -WindowsPath $RepoDest
    if (-not $repoLocal.EndsWith("/")) { $repoLocal = $repoLocal + "/" }
    $statsLocal = ConvertTo-RsyncLocalPath -WindowsPath $StatsDest
    if (-not $statsLocal.EndsWith("/")) { $statsLocal = $statsLocal + "/" }

    # --- Repo pull: Pi wins (ignore times) ---
    $repoIndex = 0
    foreach ($name in $RepoPullPatterns) {
        $repoIndex++
        $remoteFilePath = "{0}/{1}" -f $remoteRoot, $name
        if (-not (Test-RemoteFileExists -Ssh $Ssh -RemoteFilePath $remoteFilePath)) {
            Write-Host ("* REPO{0}: skip (missing on Pi): {1}" -f $repoIndex, $name) -ForegroundColor DarkYellow
            Write-Host ""
            continue
        }
        $remoteFile = Get-RemoteSpec -Ssh $Ssh -RemotePath $remoteFilePath
        $args = New-Object System.Collections.Generic.List[string]
        [void]$args.Add("-avz")
        if ($DryRun) { [void]$args.Add("-n") }
        [void]$args.Add("--ignore-times")
        [void]$args.Add("-e")
        [void]$args.Add($sshShell)
        [void]$args.Add($remoteFile)
        [void]$args.Add($repoLocal)

        Write-SyncSection ("** REPO{0}: {1} --> {2}" -f $repoIndex, $name, $RepoDest)
        Invoke-Rsync -RsyncArgs @($args) -FailMessage ("Repo pull failed for {0}" -f $name)
        Write-SyncDone ("* REPO{0}: done" -f $repoIndex)
        Write-Host ""
    }

    # --- Telemetry pull: include-only, update (skip if local newer) ---
    $telemetryPatterns = @($IncludePatterns | Where-Object {
        -not (Test-NameMatchesAny -Name $_ -Patterns $RepoPullPatterns) -and
        $_ -ne $null -and $_.Length -gt 0
    })

    if ($telemetryPatterns.Count -eq 0) {
        Write-SyncVerbose "No telemetry patterns after removing repo-pull names"
        return
    }

    $args2 = New-Object System.Collections.Generic.List[string]
    [void]$args2.Add("-avzu")
    if ($DryRun) { [void]$args2.Add("-n") }
    [void]$args2.Add("-e")
    [void]$args2.Add($sshShell)

    foreach ($d in $SkipDirPatterns) {
        if ($d -match '[\*\?\[]') {
            [void]$args2.Add(("--exclude={0}" -f $d))
        } else {
            [void]$args2.Add(("--exclude={0}/" -f $d.TrimEnd('/', '\')))
        }
    }

    # Include directories for traversal, then named patterns, then exclude everything else.
    # One argv per flag (= form) so MSYS does not glob "*" / "*.db".
    [void]$args2.Add("--include=*/")
    foreach ($p in $telemetryPatterns) {
        [void]$args2.Add(("--include={0}" -f $p))
    }
    [void]$args2.Add("--exclude=*")
    [void]$args2.Add("--prune-empty-dirs")

    $remoteTree = (Get-RemoteSpec -Ssh $Ssh -RemotePath $remoteRoot)
    if (-not $remoteTree.EndsWith("/")) { $remoteTree = $remoteTree + "/" }
    [void]$args2.Add($remoteTree)
    [void]$args2.Add($statsLocal)

    Write-SyncSection ("** STATS: telemetry --> {0}" -f $StatsDest)
    Invoke-Rsync -RsyncArgs @($args2) -FailMessage "Stats/telemetry pull failed"
    Write-SyncDone "* STATS: done"
}

# =============================================================================
# JOB 3 - LOG PULL (Pi /var/log/wanos --> StatsDest via rsync)
# =============================================================================

function Invoke-WanosRsyncLogPullJob {
    param(
        [hashtable]$Ssh,
        [string]$StatsDest,
        [switch]$DryRun
    )

    Write-SyncJobHeader "=== LOG PULL JOB (Pi /var/log/wanos --> Local via rsync/SSH) ==="

    $subdir = if ($null -eq $Ssh.LocalLogSubdir) { "" } else { [string]$Ssh.LocalLogSubdir }
    $subdir = $subdir.Trim().Trim('\', '/')
    $localDir = if ([string]::IsNullOrWhiteSpace($subdir)) {
        $StatsDest
    } else {
        Join-Path $StatsDest $subdir
    }
    Ensure-Directory -Path $localDir -DryRun:$DryRun

    $localRsync = ConvertTo-RsyncLocalPath -WindowsPath $localDir
    if (-not $localRsync.EndsWith("/")) { $localRsync = $localRsync + "/" }

    $remoteDir = $Ssh.RemoteLogDir.TrimEnd("/")
    $remoteSpec = "{0}@{1}:{2}/{3}" -f $Ssh.User, $Ssh.Host, $remoteDir, $Ssh.RemoteGlob

    Write-SyncVerbose "Remote: $remoteSpec"
    Write-SyncVerbose "Local:  $localRsync"

    $args = New-Object System.Collections.Generic.List[string]
    [void]$args.Add("-avz")
    if ($DryRun) { [void]$args.Add("-n") }
    [void]$args.Add("-e")
    [void]$args.Add((Get-SshRsyncShellArg))
    [void]$args.Add($remoteSpec)
    [void]$args.Add($localRsync)

    Write-SyncSection ("** rsync logs: {0} --> {1}" -f $remoteSpec, $localDir)
    Invoke-Rsync -RsyncArgs @($args) -FailMessage "Log pull failed"
    Write-SyncDone ("* LOG: done --> {0}" -f $localDir)
}

# =============================================================================
# VALIDATION + DISPATCH
# =============================================================================

# Mode banner is printed by wanos-sync.bat; keep only in verbose when run via .ps1 alone
Write-SyncVerbose "Mode: $Mode"
Write-SyncVerbose "Timestamp: $(Get-Date)"
Write-SyncVerbose ""

Assert-PathExists -Path $MirrorSource -Description "Mirror source (repo)" -ExitCode 11

if ($Mode -eq "codeimport") {
    if ([string]::IsNullOrWhiteSpace($CodeImportPath)) {
        Write-Error "Mode codeimport requires -CodeImportPath <windows-folder>. Example: -CodeImportPath C:\data\git\wanos\code-import"
        exit 13
    }
    Ensure-Directory -Path $CodeImportPath -DryRun:($false)
}

foreach ($dir in $SourceDirs) {
    Assert-PathExists -Path $dir -Description "Normalization source directory" -ExitCode 15
}

$script:DryRun = ($Mode -eq "test")
$DryRun = $script:DryRun

if ($Mode -ne "codeimport") {
    Assert-RsyncAvailable
    Ensure-Directory -Path $StatsDest -DryRun:$DryRun
}

# Normalize on real writes (run + codeimport)
if ($Mode -eq "run" -or $Mode -eq "codeimport") {
    Normalize-ShFiles -Dirs $SourceDirs
}

if ($Mode -eq "codeimport") {
    Invoke-WanosLocalMirrorJob `
        -Source $MirrorSource `
        -Dest $CodeImportPath `
        -ExcludeDirs $MirrorExcludeDirs `
        -ExcludeFiles $MirrorExcludeFiles `
        -DryRun:$false
} else {
    # test / run --> Pi via rsync
    Invoke-WanosBootstrapPushJob `
        -Source $MirrorSource `
        -Ssh $PiSsh `
        -BootstrapFiles $MirrorBootstrapFiles `
        -DryRun:$DryRun

    Write-Host ""
    Invoke-WanosRsyncMirrorJob `
        -Source $MirrorSource `
        -Ssh $PiSsh `
        -ExcludeDirs $MirrorExcludeDirs `
        -ExcludeFiles $MirrorExcludeFiles `
        -DryRun:$DryRun

    Write-Host ""
    Invoke-WanosRsyncStatsJob `
        -Ssh $PiSsh `
        -StatsDest $StatsDest `
        -RepoDest $MirrorSource `
        -IncludePatterns $StatsInclude `
        -RepoPullPatterns $StatsRepoPull `
        -SkipDirPatterns $MirrorExcludeDirs `
        -DryRun:$DryRun

    Write-Host ""
    Invoke-WanosRsyncLogPullJob `
        -Ssh $PiSsh `
        -StatsDest $StatsDest `
        -DryRun:$DryRun
}

Write-Host ""
Write-SyncDone "--> All done."
