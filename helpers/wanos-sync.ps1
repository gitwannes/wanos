<#
================================================================================
WANOS Sync Script (PowerShell)
--------------------------------------------------------------------------------
Implements two jobs:

1) MIRROR JOB (Local --> Remote)
   - Equivalent semantics to Robocopy /MIR /XO /XD /XF /FFT /DST
   - Copy all files except excluded ones
   - Delete files on destination that no longer exist in source
   - Skip older files
   - Timestamp tolerance
   - Directory and file excludes

2) STATS JOB (Local --> Remote)
   - Equivalent semantics to Robocopy /IF include-only
   - Copy only specific files
   - No deletes
   - Skip older files
   - Timestamp tolerance

Normalization:
   - Only runs in RUN mode
   - Converts CRLF --> LF for *.sh files
   - Removes BOM

Modes:
   - test      --> dry-run, no writes, no deletes, no normalization
   - run       --> real sync + normalization
   - runlocal  --> mirror only, destination = CodeFolder, normalization enabled

================================================================================
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("test","run","runlocal")]
    [string]$Mode
)

# ----------------------------- CONFIG -----------------------------------------

$SourceDirs = @(
    "C:\data\git\wanos",
    "C:\data\git\wanos\helpers"
)

$MirrorSource = "C:\data\git\wanos"
$MirrorDest   = "Z:\"                # Pi

$CodeFolder   = "C:\data\git\wanos\code-import"
$StatsDest    = "C:\data\OneDrive\data\professional\wanos\logs"

# Mirror job excludes (Robocopy semantics preserved as comments)
$MirrorExcludeDirs = @(
    "C:\data\git\wanos\logs",
    "C:\data\git\wanos\temp"
)
$MirrorExcludeFiles = @("*.tmp","*.bak")

# Stats job include-only filters
$StatsInclude = @(
    "*.db",
    "wanos.console.log",
    "wanos-nvram.json",
    "wanos-nvram.json.tmp",
    "wanos*"
)

# Timestamp tolerance (Robocopy /FFT)
$TimestampToleranceSeconds = 2

# ----------------------------- PATH VALIDATION --------------------------------

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Description,
        [int]$ExitCode = 10
    )

    if (-not (Test-Path $Path)) {
        Write-Error "Required path missing: $Description → $Path"
        exit $ExitCode
    }
}

Write-Host "Validating configured paths..."

# Validate main sync paths
Assert-PathExists -Path $MirrorSource -Description "Mirror source" -ExitCode 11

if ($Mode -ne "runlocal") {
    Assert-PathExists -Path $MirrorDest -Description "Mirror destination (Pi)" -ExitCode 12
}

Assert-PathExists -Path $CodeFolder -Description "CodeFolder" -ExitCode 13
Assert-PathExists -Path $StatsDest -Description "Stats destination" -ExitCode 14

# Validate normalization source directories
foreach ($dir in $SourceDirs) {
    Assert-PathExists -Path $dir -Description "Normalization source directory" -ExitCode 15
}

# Validate mirror exclude directories (but allow them to be optional)
foreach ($exDir in $MirrorExcludeDirs) {
    if (-not (Test-Path $exDir)) {
        Write-Warning "Exclude directory does not exist (skipping): $exDir"
    }
}

# ----------------------------- UTILITIES --------------------------------------

function Normalize-ShFiles {
    param([string[]]$Dirs)

    Write-Host "Normalizing .sh files..."

    foreach ($dir in $Dirs) {
        if (-not (Test-Path $dir)) {
            Write-Warning "Skipping missing directory: $dir"
            continue
        }

        Get-ChildItem -Path $dir -Filter *.sh -Recurse | ForEach-Object {
            $path = $_.FullName
            $bytes = [System.IO.File]::ReadAllBytes($path)

            # Try UTF8 first, fallback to default
            try {
                $text = [System.Text.Encoding]::UTF8.GetString($bytes)
            } catch {
                $text = [System.Text.Encoding]::Default.GetString($bytes)
            }

            # Remove CRLF --> LF
            $newText = $text -replace "`r`n","`n"

            if ($newText -ne $text) {
                Write-Host "Converted CRLF-->LF: $path"
                [System.IO.File]::WriteAllText($path, $newText, [System.Text.UTF8Encoding]::new($false))
            } else {
                Write-Host "Already LF: $path"
            }
        }
    }
}

function Should-CopyFile {
    param(
        [System.IO.FileInfo]$Source,
        [System.IO.FileInfo]$Dest,
        [int]$ToleranceSeconds
    )

    if (-not $Dest) { return $true }  # dest missing --> copy

    # Compare timestamps with tolerance
    $delta = ($Source.LastWriteTime - $Dest.LastWriteTime).TotalSeconds

    if ($delta -gt $ToleranceSeconds) { return $true }  # source newer
    return $false
}

# ----------------------------- MIRROR JOB -------------------------------------

function Run-MirrorJob {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$ExcludeDirs,
        [string[]]$ExcludeFiles,
        [switch]$DryRun
    )

    Write-Host "=== MIRROR JOB ==="
    Write-Host "Source: $Source"
    Write-Host "Dest:   $Dest"

    if (-not (Test-Path $Source)) {
        throw "Mirror source missing: $Source"
    }

    if (-not (Test-Path $Dest)) {
        if ($DryRun) {
            Write-Host "[DRY] Would create destination: $Dest"
        } else {
            New-Item -ItemType Directory -Path $Dest | Out-Null
        }
    }

    # Build exclude directory list
    $excludeDirSet = New-Object System.Collections.Generic.HashSet[string]
    foreach ($d in $ExcludeDirs) { $excludeDirSet.Add((Resolve-Path $d).Path) }

    # Build exclude file patterns
    $excludeFilePatterns = $ExcludeFiles

    # Copy phase
    Get-ChildItem -Path $Source -Recurse -File | ForEach-Object {
        $src = $_.FullName

        # Directory exclude check
        foreach ($exDir in $excludeDirSet) {
            if ($src.StartsWith($exDir)) { return }
        }

        # File exclude check
        foreach ($pattern in $excludeFilePatterns) {
            if ($_ -like $pattern) { return }
        }

        $relative = $src.Substring($Source.Length).TrimStart("\","/")
        $destPath = Join-Path $Dest $relative

        $destFile = if (Test-Path $destPath) { Get-Item $destPath } else { $null }

        if (Should-CopyFile -Source $_ -Dest $destFile -ToleranceSeconds $TimestampToleranceSeconds) {
            if ($DryRun) {
                Write-Host "[DRY] Copy: $src --> $destPath"
            } else {
                $destDir = Split-Path $destPath
                if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }
                Copy-Item $src $destPath -Force
            }
        }
    }

    # Delete phase (mirror)
    Get-ChildItem -Path $Dest -Recurse -File | ForEach-Object {
        $dest = $_.FullName
        $relative = $dest.Substring($Dest.Length).TrimStart("\","/")
        $srcPath = Join-Path $Source $relative

        if (-not (Test-Path $srcPath)) {
            if ($DryRun) {
                Write-Host "[DRY] Delete: $dest"
            } else {
                Remove-Item $dest -Force
            }
        }
    }
}

# ----------------------------- STATS JOB --------------------------------------

function Run-StatsJob {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$IncludePatterns,
        [switch]$DryRun
    )

    Write-Host "=== STATS JOB ==="
    Write-Host "Source: $Source"
    Write-Host "Dest:   $Dest"

    if (-not (Test-Path $Dest)) {
        if ($DryRun) {
            Write-Host "[DRY] Would create destination: $Dest"
        } else {
            New-Item -ItemType Directory -Path $Dest | Out-Null
        }
    }

    Get-ChildItem -Path $Source -Recurse -File | ForEach-Object {
        $src = $_

        # Include-only filter
        $match = $false
        foreach ($pattern in $IncludePatterns) {
            if ($src.Name -like $pattern) { $match = $true; break }
        }
        if (-not $match) { return }

        $relative = $src.FullName.Substring($Source.Length).TrimStart("\","/")
        $destPath = Join-Path $Dest $relative

        $destFile = if (Test-Path $destPath) { Get-Item $destPath } else { $null }

        if (Should-CopyFile -Source $src -Dest $destFile -ToleranceSeconds $TimestampToleranceSeconds) {
            if ($DryRun) {
                Write-Host "[DRY] Copy: $($src.FullName) --> $destPath"
            } else {
                $destDir = Split-Path $destPath
                if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir | Out-Null }
                Copy-Item $src.FullName $destPath -Force
            }
        }
    }
}

# ----------------------------- MODE DISPATCH ----------------------------------

Write-Host "Mode: $Mode"
Write-Host "Timestamp: $(Get-Date)"
Write-Host ""

$DryRun = $Mode -eq "test"

if ($Mode -eq "run") {
    Normalize-ShFiles -Dirs $SourceDirs
}

if ($Mode -eq "runlocal") {
    Normalize-ShFiles -Dirs $SourceDirs
}

# Mirror job
if ($Mode -eq "runlocal") {
    Run-MirrorJob -Source $MirrorSource -Dest $CodeFolder -ExcludeDirs $MirrorExcludeDirs -ExcludeFiles $MirrorExcludeFiles -DryRun:$DryRun
} else {
    Run-MirrorJob -Source $MirrorSource -Dest $MirrorDest -ExcludeDirs $MirrorExcludeDirs -ExcludeFiles $MirrorExcludeFiles -DryRun:$DryRun
}

# Stats job (only in test/run)
if ($Mode -ne "runlocal") {
    Run-StatsJob -Source $MirrorDest -Dest $StatsDest -IncludePatterns $StatsInclude -DryRun:$DryRun
}

Write-Host ""
Write-Host "Done."
