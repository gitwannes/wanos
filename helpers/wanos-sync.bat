@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM WANOS Sync Wrapper (Batch)
REM ----------------------------------------------------------------------------
REM Thin launcher for helpers\wanos-sync.ps1
REM
REM Modes (must match ValidateSet in the .ps1):
REM   test         Dry-run rsync Local<->Pi + log pull preview (SSH, no Z:)
REM   run          Normalize --> rsync mirror --> stats pull --> log pull
REM   codeimport   Mirror only to a local Windows folder (required path arg)
REM
REM Optional trailing:
REM   verbose   Pass -VerboseSync to the .ps1
REM
REM Includes/excludes: wanos-sync.config.txt  |  engine: wanos-sync.ps1
REM Doc: docs\wanos-sync.md
REM ============================================================================

set "PS_SCRIPT=%~dp0wanos-sync.ps1"
set "MODE="
set "CODEIMPORT_PATH="
set "VERBOSE=0"
set "PS_VERBOSE_ARG="
set "PS_CODEIMPORT_ARG="

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

if "%~1"=="" goto :show_help

set "MODE=%~1"

REM Parse remaining args: optional path for codeimport, optional verbose
shift
:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="verbose"  set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="-verbose" set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="--verbose" set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="/verbose" set "VERBOSE=1" & shift & goto :parse_args
REM First non-verbose arg after mode is CodeImportPath (for codeimport)
if not defined CODEIMPORT_PATH (
    set "CODEIMPORT_PATH=%~1"
    shift
    goto :parse_args
)
echo ERROR: Unexpected argument "%~1"
echo.
goto :show_help

:args_done
if "!VERBOSE!"=="1" set "PS_VERBOSE_ARG=-VerboseSync"

if /I "%MODE%"=="test"       goto :mode_test
if /I "%MODE%"=="run"        goto :mode_run
if /I "%MODE%"=="codeimport" goto :mode_codeimport

echo ERROR: Unknown mode "%MODE%"
echo.
goto :show_help

:show_help
echo Usage:
echo     wanos-sync.bat test [verbose]
echo         Dry-run rsync push/pull/logs. Needs SSH key auth.
echo.
echo     wanos-sync.bat run [verbose]
echo         Full sync: normalize, rsync mirror, stats pull, log pull.
echo.
echo     wanos-sync.bat codeimport ^<windows-folder^> [verbose]
echo         Local mirror only into the given folder. Path is required.
echo.
echo     verbose  Show config load, rsync command lines, paths.
echo     Config:  helpers\wanos-sync.config.txt
echo     Docs:    docs\wanos-sync.md
echo.
exit /b 1

:invoke_ps1
if "!VERBOSE!"=="1" (
    echo Invoking: powershell -File "%PS_SCRIPT%" -Mode %MODE% !PS_CODEIMPORT_ARG! !PS_VERBOSE_ARG!
    echo Script: %PS_SCRIPT%
    echo.
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Mode %MODE% !PS_CODEIMPORT_ARG! !PS_VERBOSE_ARG!
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
    echo.
    echo ERROR: wanos-sync.ps1 exited with code !RC!
    exit /b !RC!
)
exit /b 0

:mode_test
echo Mode: test  ^(dry-run, rsync/SSH^)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_run
echo Mode: run  ^(rsync/SSH^)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_codeimport
if "!CODEIMPORT_PATH!"=="" (
    echo ERROR: Mode codeimport requires a Windows folder path.
    echo Example: wanos-sync.bat codeimport C:\data\git\wanos\code-import
    echo.
    exit /b 1
)
if not exist "!CODEIMPORT_PATH!\" (
    echo Creating folder: !CODEIMPORT_PATH!
    mkdir "!CODEIMPORT_PATH!" 2>nul
)
echo Mode: codeimport --^> !CODEIMPORT_PATH!
if "!VERBOSE!"=="1" (
    echo Invoking: powershell -File "%PS_SCRIPT%" -Mode codeimport -CodeImportPath "!CODEIMPORT_PATH!" !PS_VERBOSE_ARG!
    echo.
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Mode codeimport -CodeImportPath "!CODEIMPORT_PATH!" !PS_VERBOSE_ARG!
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
    echo.
    echo ERROR: wanos-sync.ps1 exited with code !RC!
    exit /b !RC!
)
exit /b 0

endlocal
