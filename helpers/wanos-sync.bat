@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM WANOS Sync Wrapper (Batch)
REM ----------------------------------------------------------------------------
REM Responsibilities:
REM   - Mode selection (test | run | runlocal)
REM   - Z: availability check (only for test/run)
REM   - Call wanos-sync.ps1 with correct mode
REM   - Display timestamps and host info
REM
REM All sync logic, path validation, normalization, mirror/stats jobs
REM live in wanos-sync.ps1
REM ============================================================================

set "PS_SCRIPT=%~dp0wanos-sync.ps1"

echo.
echo ======================================================================
echo WANOS Sync Wrapper
echo Timestamp: %DATE% %TIME%
echo Host: %COMPUTERNAME%   User: %USERNAME%
echo ======================================================================
echo.

REM -------------------------- MODE PARSING -------------------------------------
if "%~1"=="" goto :show_help
set "MODE=%~1"

if /I "%MODE%"=="test"     goto :mode_test
if /I "%MODE%"=="run"      goto :mode_run
if /I "%MODE%"=="runlocal" goto :mode_runlocal

goto :show_help

REM -------------------------- HELP ---------------------------------------------
:show_help
echo Usage:
echo     wanos-sync.bat test      --> Dry-run (no writes, no normalization)
echo     wanos-sync.bat run       --> Full sync (mirror + stats + normalization)
echo     wanos-sync.bat runlocal  --> Mirror only to CodeFolder (normalization)
echo.
exit /b 1

REM -------------------------- MODE: TEST ---------------------------------------
:mode_test
echo Mode: TEST
echo Dry-run only. No normalization. No writes.
echo.

REM Z: must exist for test mode
if not exist "Z:\" (
    echo ERROR: Z: drive is not reachable.
    exit /b 2
)

powershell -NoProfile -ExecutionPolicy Bypass ^
    -File "%PS_SCRIPT%" -Mode test

exit /b 0

REM -------------------------- MODE: RUN ----------------------------------------
:mode_run
echo Mode: RUN
echo Real sync. Normalization enabled.
echo.

REM Z: must exist
if not exist "Z:\" (
    echo ERROR: Z: drive is not reachable.
    exit /b 2
)

powershell -NoProfile -ExecutionPolicy Bypass ^
    -File "%PS_SCRIPT%" -Mode run

exit /b 0

REM -------------------------- MODE: RUNLOCAL -----------------------------------
:mode_runlocal
echo Mode: RUNLOCAL
echo Mirror only → CodeFolder. Normalization enabled.
echo.

powershell -NoProfile -ExecutionPolicy Bypass ^
    -File "%PS_SCRIPT%" -Mode runlocal

exit /b 0

endlocal
