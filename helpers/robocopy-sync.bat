@echo off
REM robocopy-sync.bat
REM Modes: test | run | runlocal
REM Normalizes all .sh files in one or more SRC_DIRS then runs robocopy.
REM This file preserves your original robocopy /JOB: usage and RCJ file.

setlocal ENABLEDELAYEDEXPANSION

REM ---------- configure ----------
REM Edit this line only to list your source directories (one quoted path per directory)
REM Example (no extra outer quotes):
REM set SRC_DIRS="C:\data\git\wanos" "C:\data\git\wanos\helpers"
set SRC_DIRS="C:\data\git\wanos" "C:\data\git\wanos\helpers"

set "TARGET_Z=Z:"
set "CODE_IMPORT=C:\data\git\wanos\code-import"
set "RCJ=wanos.rcj"
REM -------------------------------

echo.
echo ================================
echo Checking environment...
echo Timestamp: %DATE% %TIME%
echo Host: %COMPUTERNAME% / User: %USERNAME%
echo ================================
echo.

REM ---------- argument parsing ----------
if "%~1"=="" goto :show_help
set "MODE=%~1"
if /I "%MODE%"=="test"     set "MODE=test"
if /I "%MODE%"=="run"      set "MODE=run"
if /I "%MODE%"=="runlocal" set "MODE=runlocal"

REM Validate mode explicitly and jump to the handler
if /I "%MODE%"=="test" goto :mode_test
if /I "%MODE%"=="run" goto :mode_run
if /I "%MODE%"=="runlocal" goto :mode_runlocal

goto :show_help

REM ---------- Z: availability check (skip for runlocal) ----------
:check_z_and_paths
if /I "%MODE%"=="runlocal" (
    echo Mode: RUNLOCAL (Z: check skipped)
) else (
    echo Checking Z: drive "%TARGET_Z%"...
    if exist "%TARGET_Z%\" (
        echo Z: reachable
    ) else (
        echo ERROR: Z: drive "%TARGET_Z%" is NOT reachable.
        echo Aborting because mode "%MODE%" requires Z: to be available.
        exit /b 2
    )
)

echo Checking SRC_DIRS configuration...
if "%SRC_DIRS%"=="" (
    echo ERROR: SRC_DIRS is empty. Edit the script and set SRC_DIRS to one or more quoted paths.
    exit /b 4
)

echo Checking CodeFolder...
if exist "%CODE_IMPORT%\" (
    echo CodeFolder ^(for use with AI^) exists
) else (
    echo CodeFolder NOT found - will attempt to create when needed
)

echo ================================
echo Mode selected: %MODE%
echo ================================
echo.

REM ---------- HELP ----------
:show_help
echo.
echo Usage:
echo     robocopy-sync.bat test      ^> Dry-run, show what WOULD be copied (requires Z:)
echo     robocopy-sync.bat run       ^> Perform full sync (Z: + CodeFolder) (requires Z:)
echo     robocopy-sync.bat runlocal  ^> Sync ONLY to CodeFolder (no Z:)
echo.
echo Configure SRC_DIRS at the top of this script as quoted paths separated by spaces.
echo Example:
echo     set SRC_DIRS="C:\data\git\wanos" "D:\other\scripts"
echo.
echo No actions performed.
exit /b 1

REM ---------- helper: normalize .sh files in a single directory ----------
:normalize_dir
REM %1 = directory (quoted or unquoted)
set "THIS_DIR=%~1"
echo.
echo -------------------------------
echo Normalizing .sh files in: "%THIS_DIR%"
echo (Removes CRLF, strips BOM if present)
echo -------------------------------
if not exist "%THIS_DIR%\" (
    echo WARNING: directory "%THIS_DIR%" does not exist, skipping.
    exit /b 0
)

pushd "%THIS_DIR%" 2>nul || (echo Failed to enter "%THIS_DIR%"; exit /b 0)

dir /b *.sh >nul 2>&1
if errorlevel 1 (
    echo No .sh files found in "%THIS_DIR%".
    popd
    exit /b 0
)

for %%F in (*.sh) do (
    echo Processing: "%%~fF"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$path = '%%~fF'; if (Test-Path $path) { $bytes = [System.IO.File]::ReadAllBytes($path); " ^
      "$enc = New-Object System.Text.UTF8Encoding $false; " ^
      "$text = $null; " ^
      "try { $text = [System.Text.Encoding]::UTF8.GetString($bytes) } catch { $text = [System.Text.Encoding]::Default.GetString($bytes) }; " ^
      "$n = $text -replace \"`r`n\",\"`n\"; " ^
      "if ($n -ne $text) { [System.IO.File]::WriteAllText($path, $n, $enc); Write-Host '  Converted CRLF->LF:' $path } else { Write-Host '  Already LF:' $path } } else { Write-Host '  Not found:' $path }"
)

popd
exit /b 0

REM ---------- process all configured source directories ----------
:normalize_sh_files
echo.
echo ================================
echo Normalizing line endings for all .sh files in configured source directories
echo ================================
echo.

echo Configured SRC_DIRS tokens:
echo %SRC_DIRS%
echo.

REM Iterate each quoted path in SRC_DIRS and call the subroutine (no labels inside parentheses)
for %%D in (%SRC_DIRS%) do (
    if "%%~D"=="" (
        echo Skipping empty SRC_DIR token
    ) else (
        call :normalize_dir "%%~D"
    )
)

echo.
echo Normalization complete.
echo.
goto :eof

REM ---------- MODE IMPLEMENTATIONS (preserve original robocopy /JOB: behavior) ----------
:mode_test
call :check_z_and_paths
echo ================================
echo Running in TEST MODE (dry-run)
echo No files will be copied or deleted.
echo ================================
echo.

call :normalize_sh_files

echo --- Starting robocopy to Pi (Z:\) [DRY RUN] ...
robocopy /JOB:"%RCJ%" "%TARGET_Z%" /L

echo.
echo Test run complete.
exit /b 0

:mode_run
call :check_z_and_paths
echo ================================
echo Running in RUN MODE
echo Files WILL be copied and deleted.
echo ================================
echo.

call :normalize_sh_files

echo --- Starting robocopy to Pi (Z:\) ...
robocopy /JOB:"%RCJ%" "%TARGET_Z%"

echo.
echo --- Starting robocopy to CodeFolder ...
robocopy /JOB:"%RCJ%" "%CODE_IMPORT%"

echo.
echo Sync complete.
exit /b 0

:mode_runlocal
REM runlocal skips Z: check
echo ================================
echo Running in RUNLOCAL MODE
echo Only syncing to CodeFolder
echo ================================
echo.

call :normalize_sh_files

echo --- Starting robocopy to CodeFolder (RUNLOCAL) ...
robocopy /JOB:"%RCJ%" "%CODE_IMPORT%"

echo.
echo Local-only sync complete.
exit /b 0

endlocal
