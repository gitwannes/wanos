@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM WANOS Sync Wrapper (Batch)
REM ----------------------------------------------------------------------------
REM Thin launcher for helpers\wanos-sync.ps1
REM
REM Modes (must match ValidateSet in the .ps1; pick exactly one):
REM   test         Dry-run rsync Local<->Pi + log pull preview (SSH, no Z:)
REM   run          Normalize --> rsync mirror --> stats pull --> log pull --> logcopy
REM   logcopy      Log pull --> copy wanos* into git docs\logs (no mirror/stats)
REM   codeimport   Mirror only to a local Windows folder (required path arg)
REM Combining two modes (e.g. "test run") is an error.
REM
REM Optional trailing (any order after mode):
REM   lcd       Target LCD Pi (\_lcd-agent --> 10.32.251.51:/home/wannes/wanos)
REM   logcopy   With test only: also dry-run the git docs\logs copy
REM             (run always logcopies; logcopy-as-mode already does it)
REM   verbose   Pass -VerboseSync to the .ps1
REM
REM Includes/excludes: wanos-sync.config.txt  |  engine: wanos-sync.ps1
REM Doc: docs\wanos-sync.md
REM ============================================================================

set "PS_SCRIPT=%~dp0wanos-sync.ps1"
set "MODE="
set "CODEIMPORT_PATH="
set "VERBOSE=0"
set "LCD=0"
set "LOGCOPY=0"
set "PS_VERBOSE_ARG="
set "PS_LCD_ARG="
set "PS_LOGCOPY_ARG="
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

REM Parse remaining args: optional path for codeimport, optional switches.
REM Modes are mutually exclusive - a second mode word must error (e.g. "test run").
shift
:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="verbose"  set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="-verbose" set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="--verbose" set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="/verbose" set "VERBOSE=1" & shift & goto :parse_args
if /I "%~1"=="lcd"      set "LCD=1" & shift & goto :parse_args
if /I "%~1"=="-lcd"     set "LCD=1" & shift & goto :parse_args
REM logcopy as a trailing flag (test preview, or redundant with run / logcopy mode)
if /I "%~1"=="logcopy"  set "LOGCOPY=1" & shift & goto :parse_args
if /I "%~1"=="-logcopy" set "LOGCOPY=1" & shift & goto :parse_args
REM Reject a second mode keyword after the first mode.
REM (Trailing "logcopy" is a flag, handled above - not a second mode.)
if /I "%~1"=="test" goto :err_two_modes
if /I "%~1"=="run" goto :err_two_modes
if /I "%~1"=="codeimport" goto :err_two_modes
REM If first mode was already logcopy, a second primary mode word errors here via test/run/codeimport.
REM Free-form path only valid for codeimport; anything else is unexpected.
if /I not "%MODE%"=="codeimport" (
    echo ERROR: Unexpected argument "%~1" after mode "%MODE%".
    echo Modes test / run / logcopy / codeimport are mutually exclusive; use one mode only.
    echo.
    goto :show_help
)
if not defined CODEIMPORT_PATH (
    set "CODEIMPORT_PATH=%~1"
    shift
    goto :parse_args
)
echo ERROR: Unexpected argument "%~1"
echo.
goto :show_help

:err_two_modes
echo ERROR: Cannot combine modes "%MODE%" and "%~1".
echo Use exactly one of: test ^| run ^| logcopy ^| codeimport
echo.
goto :show_help

:args_done
REM run always logcopies; logcopy mode always logcopies
if /I "%MODE%"=="run" set "LOGCOPY=1"
if /I "%MODE%"=="logcopy" set "LOGCOPY=1"

if "!VERBOSE!"=="1" set "PS_VERBOSE_ARG=-VerboseSync"
if "!LCD!"=="1" set "PS_LCD_ARG=-Lcd"
if "!LOGCOPY!"=="1" set "PS_LOGCOPY_ARG=-LogCopy"

if /I "%MODE%"=="test"       goto :mode_test
if /I "%MODE%"=="run"        goto :mode_run
if /I "%MODE%"=="logcopy"    goto :mode_logcopy
if /I "%MODE%"=="codeimport" goto :mode_codeimport

echo ERROR: Unknown mode "%MODE%"
echo.
goto :show_help

:show_help
echo Usage - all valid combinations:
echo.
echo   WanOS ^(main Pi .30^)
echo     wanos-sync.bat test
echo     wanos-sync.bat test verbose
echo     wanos-sync.bat test logcopy
echo     wanos-sync.bat test logcopy verbose
echo         Dry-run mirror, stats pull, log pull. Needs SSH key auth.
echo         Trailing logcopy = also dry-run copy into git docs\logs.
echo.
echo     wanos-sync.bat run
echo     wanos-sync.bat run verbose
echo         Full sync: normalize, mirror, stats pull, log pull, logcopy.
echo         logcopy is always included ^(no need to pass logcopy^).
echo.
echo     wanos-sync.bat logcopy
echo     wanos-sync.bat logcopy verbose
echo         Log pull then copy wanos* into git docs\logs only.
echo         No mirror, no stats, no normalize.
echo.
echo   LCD ^(LCD Pi .51; _lcd-agent --^> /home/wannes/wanos^)
echo     wanos-sync.bat test lcd
echo     wanos-sync.bat test lcd verbose
echo     wanos-sync.bat test lcd logcopy
echo     wanos-sync.bat test lcd logcopy verbose
echo         Dry-run mirror + log pull for LCD Pi. No stats pull.
echo         Trailing logcopy = also dry-run copy into _lcd-agent\docs\logs.
echo.
echo     wanos-sync.bat run lcd
echo     wanos-sync.bat run lcd verbose
echo         Mirror _lcd-agent + log pull + logcopy ^(always^). No stats.
echo.
echo     wanos-sync.bat logcopy lcd
echo     wanos-sync.bat logcopy lcd verbose
echo         Log pull + copy wanos* into _lcd-agent\docs\logs only.
echo.
echo   codeimport ^(local mirror only; no SSH^)
echo     wanos-sync.bat codeimport ^<windows-folder^>
echo     wanos-sync.bat codeimport ^<windows-folder^> verbose
echo         Mirror repo into the given folder. Path is required. Not with lcd.
echo.
echo     verbose  Show config load, rsync command lines, paths.
echo     Config:  helpers\wanos-sync.config.txt
echo     Docs:    docs\wanos-sync.md
echo.
exit /b 1

:invoke_ps1
if "!VERBOSE!"=="1" (
    echo Invoking: powershell -File "%PS_SCRIPT%" -Mode %MODE% !PS_LCD_ARG! !PS_LOGCOPY_ARG! !PS_CODEIMPORT_ARG! !PS_VERBOSE_ARG!
    echo Script: %PS_SCRIPT%
    echo.
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Mode %MODE% !PS_LCD_ARG! !PS_LOGCOPY_ARG! !PS_CODEIMPORT_ARG! !PS_VERBOSE_ARG!
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
    echo.
    echo ERROR: wanos-sync.ps1 exited with code !RC!
    exit /b !RC!
)
exit /b 0

:mode_test
if "!LCD!"=="1" (
    echo Mode: test lcd  ^(dry-run LCD Pi^)
) else (
    echo Mode: test  ^(dry-run, rsync/SSH^)
)
if "!LOGCOPY!"=="1" echo Option: logcopy
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_run
if "!LCD!"=="1" (
    echo Mode: run lcd  ^(rsync/SSH LCD Pi; always logcopy^)
) else (
    echo Mode: run  ^(rsync/SSH; always logcopy^)
)
echo Option: logcopy ^(always on for run^)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_logcopy
if "!LCD!"=="1" (
    echo Mode: logcopy lcd  ^(log pull + git docs\logs; LCD Pi^)
) else (
    echo Mode: logcopy  ^(log pull + git docs\logs; main Pi^)
)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_codeimport
if "!LCD!"=="1" (
    echo ERROR: lcd cannot be combined with codeimport.
    echo.
    exit /b 1
)
if "!LOGCOPY!"=="1" (
    echo ERROR: logcopy cannot be combined with codeimport.
    echo.
    exit /b 1
)
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
