@echo off
REM robocopy-sync.bat
REM Modes: test | run | runlocal
REM Normalizes all .sh files in SRC_DIR then runs robocopy.
REM Aborts if Z: is not reachable for modes test and run. runlocal ignores Z:.

setlocal ENABLEDELAYEDEXPANSION

REM ---------- configure ----------
set "SRC_DIR=C:\data\git\wanos"
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

REM Validate mode
if /I NOT "%MODE%"=="test" if /I NOT "%MODE%"=="run" if /I NOT "%MODE%"=="runlocal" goto :show_help

REM ---------- Pre-checks ----------
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

echo Checking SRC_DIR...
if exist "%SRC_DIR%\" (
    echo SRC_DIR: %SRC_DIR% - reachable
) else (
    echo ERROR: SRC_DIR: %SRC_DIR% - NOT reachable.
    echo Aborting.
    exit /b 3
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

REM ---------- MODE DISPATCH (single entry point) ----------
if /I "%MODE%"=="test" goto :do_test
if /I "%MODE%"=="run" goto :do_run
if /I "%MODE%"=="runlocal" goto :do_runlocal

goto :show_help

REM ---------- HELP ----------
:show_help
echo.
echo Usage:
echo     robocopy-sync.bat test      ^> Dry-run, show what WOULD be copied (requires Z:)
echo     robocopy-sync.bat run       ^> Perform full sync (Z: + CodeFolder) (requires Z:)
echo     robocopy-sync.bat runlocal  ^> Sync ONLY to CodeFolder (no Z:)
echo.
echo No actions performed.
exit /b 1

REM ---------- helper: normalize all .sh files in SRC_DIR ----------
:normalize_sh_files
echo.
echo ================================
echo Normalizing line endings for all .sh files in "%SRC_DIR%"
echo (Removes CRLF, strips BOM if present)
echo ================================
echo.

pushd "%SRC_DIR%" 2>nul || (echo Failed to enter "%SRC_DIR%"; exit /b 3)

REM If no .sh files, inform and continue
dir /b *.sh >nul 2>&1
if errorlevel 1 (
    echo No .sh files found in "%SRC_DIR%".
    popd
    goto :normalize_done
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
:normalize_done
echo.
echo Normalization complete.
echo.
goto :eof

REM ---------- MODE IMPLEMENTATIONS ----------
:do_test
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

:do_run
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

:do_runlocal
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
