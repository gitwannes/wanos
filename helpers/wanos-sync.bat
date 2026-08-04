@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM WANOS Sync Wrapper (Batch)
REM ----------------------------------------------------------------------------
REM Thin launcher for helpers\wanos-sync.ps1
REM
REM Modes (must match ValidateSet in the .ps1):
REM   test      Dry-run Local-->Pi + Pi-->Local pull preview (needs Z:)
REM   run       Real sync: normalize --> mirror Pi + CodeFolder --> pull (needs Z:)
REM   runlocal  Mirror only to CodeFolder (no Z:, no pull)
REM
REM Optional 2nd arg:
REM   verbose   Pass -VerboseSync to the .ps1 (config/skips/paths details)
REM
REM Includes/excludes: wanos-sync.config.txt  |  engine: wanos-sync.ps1
REM ============================================================================

set "PS_SCRIPT=%~dp0wanos-sync.ps1"
set "MODE="
set "VERBOSE=0"
set "PS_VERBOSE_ARG="

echo.
echo ======================================================================
echo WANOS Sync Wrapper
echo Timestamp: %DATE% %TIME%
echo Host: %COMPUTERNAME%   User: %USERNAME%
echo ======================================================================
echo.

if not exist "%PS_SCRIPT%" (
    echo ERROR: PowerShell sync script not found:
    echo   %PS_SCRIPT%
    exit /b 3
)

REM -------------------------- ARG PARSING --------------------------------------
if "%~1"=="" goto :show_help

REM Accept: mode [verbose]   or   mode -verbose / --verbose
set "MODE=%~1"
set "ARG2=%~2"

if /I "%ARG2%"=="verbose"  set "VERBOSE=1"
if /I "%ARG2%"=="-verbose" set "VERBOSE=1"
if /I "%ARG2%"=="--verbose" set "VERBOSE=1"
if /I "%ARG2%"=="/verbose" set "VERBOSE=1"

if "!VERBOSE!"=="1" set "PS_VERBOSE_ARG=-VerboseSync"

if /I "%MODE%"=="test"     goto :mode_test
if /I "%MODE%"=="run"      goto :mode_run
if /I "%MODE%"=="runlocal" goto :mode_runlocal

echo ERROR: Unknown mode "%MODE%"
echo.
goto :show_help

REM -------------------------- HELP ---------------------------------------------
:show_help
echo Usage:
echo     wanos-sync.bat test [verbose]      -- Dry-run ^(no writes^). Needs Z:.
echo     wanos-sync.bat run [verbose]       -- Full sync. Needs Z:.
echo     wanos-sync.bat runlocal [verbose]  -- Mirror only to CodeFolder. No Z:.
echo.
echo     verbose  Show config load, path validation, skips, Source/Dest details.
echo.
exit /b 1

REM -------------------------- shared: require Z: --------------------------------
:require_z
if exist "Z:\" (
    echo Z: reachable
    goto :eof
)
echo ERROR: Z: drive is not reachable.
echo Mode "%MODE%" requires the Pi share mapped as Z:.
exit /b 2

REM -------------------------- shared: invoke ps1 --------------------------------
:invoke_ps1
if "!VERBOSE!"=="1" (
    echo Invoking: powershell -File "%PS_SCRIPT%" -Mode %MODE% !PS_VERBOSE_ARG!
    echo Script: %PS_SCRIPT%
    echo.
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Mode %MODE% !PS_VERBOSE_ARG!
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
    echo.
    echo ERROR: wanos-sync.ps1 exited with code !RC!
    exit /b !RC!
)
exit /b 0

REM -------------------------- MODE: TEST ---------------------------------------
:mode_test
echo Mode: TEST
if "!VERBOSE!"=="1" (
    echo Dry-run only. No normalization. No writes/deletes.
    echo Jobs: mirror Local-^>Pi ^(preview^) + pull Pi-^>Local ^(preview^)
    echo.
)

call :require_z
if errorlevel 1 exit /b %ERRORLEVEL%

call :invoke_ps1
exit /b %ERRORLEVEL%

REM -------------------------- MODE: RUN ----------------------------------------
:mode_run
echo Mode: RUN
if "!VERBOSE!"=="1" (
    echo Real sync. Normalization enabled.
    echo Jobs: mirror Local-^>Pi + Local-^>CodeFolder + pull Pi-^>Local
    echo.
)

call :require_z
if errorlevel 1 exit /b %ERRORLEVEL%

call :invoke_ps1
exit /b %ERRORLEVEL%

REM -------------------------- MODE: RUNLOCAL -----------------------------------
:mode_runlocal
echo Mode: RUNLOCAL
if "!VERBOSE!"=="1" (
    echo Mirror only Local-^>CodeFolder. Normalization enabled. Z: not required.
    echo.
)

call :invoke_ps1
exit /b %ERRORLEVEL%

endlocal
