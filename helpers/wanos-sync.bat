@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM WANOS Sync Wrapper (Batch)
REM ----------------------------------------------------------------------------
REM Thin launcher for helpers\wanos-sync.ps1
REM
REM Modes (must match ValidateSet in the .ps1; pick exactly one):
REM   test         Dry-run rsync Local<->Pi + log pull preview (SSH, no Z:)
REM   run          Normalize --> rsync mirror --> stats pull --> log pull --> sessionlog --> logcopy
REM   logcopy      Log/sessionlog pull --> copy logs into git docs\logs
REM   codeimport   Mirror only to a local Windows folder (required path arg)
REM   diff         Compare one repo-relative file PC vs Pi (normalized text diff)
REM Combining two modes (e.g. "test run") is an error.
REM
REM Optional trailing (any order after mode):
REM   lcd       Target LCD Pi (\_lcd-agent --> 10.32.251.51:/home/wannes/wanos)
REM   wlw       Target WLW portal (be90webserver --> 10.32.251.30:/home/wannes/be90webserver)
REM   logcopy   With test only: also dry-run the git docs\logs copy
REM             (run always logcopies; logcopy-as-mode already does it)
REM   verbose   Pass -VerboseSync to the .ps1
REM diff mode: required relpath arg after mode; only lcd, wlw, and verbose allowed.
REM lcd and wlw are mutually exclusive.
REM
REM Includes/excludes: wanos-sync.config.txt  |  engine: wanos-sync.ps1
REM Doc: docs\wanos-sync.md  |  WLW locks: be90webserver docs\wlw-sync.md
REM ============================================================================

set "PS_SCRIPT=%~dp0wanos-sync.ps1"
set "MODE="
set "CODEIMPORT_PATH="
set "DIFF_FILE="
set "VERBOSE=0"
set "LCD=0"
set "WLW=0"
set "LOGCOPY=0"
set "PS_VERBOSE_ARG="
set "PS_LCD_ARG="
set "PS_WLW_ARG="
set "PS_LOGCOPY_ARG="
set "PS_CODEIMPORT_ARG="
set "PS_DIFF_ARG="

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
if /I "%~1"=="wlw"      set "WLW=1" & shift & goto :parse_args
if /I "%~1"=="-wlw"     set "WLW=1" & shift & goto :parse_args
REM logcopy as a trailing flag (test preview, or redundant with run / logcopy mode)
if /I "%~1"=="logcopy" (
    if /I "%MODE%"=="diff" goto :err_diff_bad_flag
    set "LOGCOPY=1" & shift & goto :parse_args
)
if /I "%~1"=="-logcopy" (
    if /I "%MODE%"=="diff" goto :err_diff_bad_flag
    set "LOGCOPY=1" & shift & goto :parse_args
)
REM Reject a second mode keyword after the first mode.
REM (Trailing "logcopy" is a flag, handled above - not a second mode.)
if /I "%~1"=="test" goto :err_two_modes
if /I "%~1"=="run" goto :err_two_modes
if /I "%~1"=="codeimport" goto :err_two_modes
if /I "%~1"=="diff" goto :err_two_modes
if /I "%~1"=="logcopy" goto :err_two_modes
REM Free-form path for codeimport or diff; anything else is unexpected.
if /I "%MODE%"=="codeimport" (
    if not defined CODEIMPORT_PATH (
        set "CODEIMPORT_PATH=%~1"
        shift
        goto :parse_args
    )
    echo ERROR: Unexpected argument "%~1"
    echo.
    goto :show_help
)
if /I "%MODE%"=="diff" (
    if not defined DIFF_FILE (
        set "DIFF_FILE=%~1"
        shift
        goto :parse_args
    )
    echo ERROR: Unexpected argument "%~1"
    echo.
    goto :show_help
)
if /I not "%MODE%"=="codeimport" (
    echo ERROR: Unexpected argument "%~1" after mode "%MODE%".
    echo Modes test / run / logcopy / codeimport / diff are mutually exclusive; use one mode only.
    echo.
    goto :show_help
)

:err_two_modes
echo ERROR: Cannot combine modes "%MODE%" and "%~1".
echo Use exactly one of: test ^| run ^| logcopy ^| codeimport ^| diff
echo.
goto :show_help

:err_diff_bad_flag
echo ERROR: Mode diff only allows trailing lcd, wlw, and verbose.
echo Example: wanos-sync.bat diff helpers/bootstrap/wlw_bootstrap.sh wlw verbose
echo.
goto :show_help

:args_done
if "!LCD!"=="1" if "!WLW!"=="1" (
    echo ERROR: lcd and wlw cannot be combined.
    echo.
    exit /b 1
)

REM run always logcopies; logcopy mode always logcopies
if /I "%MODE%"=="run" set "LOGCOPY=1"
if /I "%MODE%"=="logcopy" set "LOGCOPY=1"

if "!VERBOSE!"=="1" set "PS_VERBOSE_ARG=-VerboseSync"
if "!LCD!"=="1" set "PS_LCD_ARG=-Lcd"
if "!WLW!"=="1" set "PS_WLW_ARG=-Wlw"
if "!LOGCOPY!"=="1" set "PS_LOGCOPY_ARG=-LogCopy"
if defined DIFF_FILE set PS_DIFF_ARG=-DiffFile "!DIFF_FILE!"

if /I "%MODE%"=="test"       goto :mode_test
if /I "%MODE%"=="run"        goto :mode_run
if /I "%MODE%"=="logcopy"    goto :mode_logcopy
if /I "%MODE%"=="codeimport" goto :mode_codeimport
if /I "%MODE%"=="diff"       goto :mode_diff

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
echo         Dry-run mirror, stats pull, log pull, sessionlog pull. Needs SSH key auth.
echo         Trailing logcopy = also dry-run copy into git docs\logs.
echo.
echo     wanos-sync.bat run
echo     wanos-sync.bat run verbose
echo         Full sync: normalize, mirror, stats, log, sessionlog, logcopy.
echo         logcopy is always included ^(no need to pass logcopy^).
echo.
echo     wanos-sync.bat logcopy
echo     wanos-sync.bat logcopy verbose
echo         Log + sessionlog pull, then copy wanos*, sauna_session_*.csv,
echo         and sauna_sessions.db into git docs\logs only.
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
echo   WLW ^(main Pi .30; be90webserver --^> /home/wannes/be90webserver^)
echo     wanos-sync.bat test wlw
echo     wanos-sync.bat test wlw verbose
echo     wanos-sync.bat test wlw logcopy
echo     wanos-sync.bat test wlw logcopy verbose
echo         Dry-run mirror + log pull ^(app wlw* + Nginx vhost logs^). No stats.
echo         Trailing logcopy = also dry-run copy into be90webserver\docs\logs.
echo.
echo     wanos-sync.bat run wlw
echo     wanos-sync.bat run wlw verbose
echo         Mirror be90webserver + log pull + logcopy ^(always^). No stats.
echo.
echo     wanos-sync.bat logcopy wlw
echo     wanos-sync.bat logcopy wlw verbose
echo         Log pull + copy wlw* and hofmans.synology.me.* into be90webserver\docs\logs.
echo.
echo   codeimport ^(local mirror only; no SSH^)
echo     wanos-sync.bat codeimport ^<windows-folder^>
echo     wanos-sync.bat codeimport ^<windows-folder^> verbose
echo         Mirror repo into the given folder. Path is required. Not with lcd/wlw.
echo.
echo   diff ^(one file PC vs Pi; SSH only; no mirror/stats/logcopy^)
echo     wanos-sync.bat diff ^<repo-relative-file^>
echo     wanos-sync.bat diff ^<repo-relative-file^> verbose
echo     wanos-sync.bat diff ^<repo-relative-file^> lcd
echo     wanos-sync.bat diff ^<repo-relative-file^> lcd verbose
echo     wanos-sync.bat diff ^<repo-relative-file^> wlw
echo     wanos-sync.bat diff ^<repo-relative-file^> wlw verbose
echo         Normalized text diff when both sides exist and file is text.
echo         Binary: sizes only. Missing: info msg ^(exit 0^). Different text: exit 1.
echo.
echo     verbose  Show config load, rsync command lines, paths.
echo     Config:  helpers\wanos-sync.config.txt
echo     Docs:    docs\wanos-sync.md
echo.
exit /b 1

:invoke_ps1
if "!VERBOSE!"=="1" (
    echo Invoking: powershell -File "%PS_SCRIPT%" -Mode %MODE% !PS_LCD_ARG! !PS_WLW_ARG! !PS_LOGCOPY_ARG! !PS_CODEIMPORT_ARG! !PS_DIFF_ARG! !PS_VERBOSE_ARG!
    echo Script: %PS_SCRIPT%
    echo.
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Mode %MODE% !PS_LCD_ARG! !PS_WLW_ARG! !PS_LOGCOPY_ARG! !PS_CODEIMPORT_ARG! !PS_DIFF_ARG! !PS_VERBOSE_ARG!
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
    REM diff exit 1 = files differ (expected); not a script failure
    if /I "!MODE!"=="diff" if "!RC!"=="1" exit /b 1
    echo.
    echo ERROR: wanos-sync.ps1 exited with code !RC!
    exit /b !RC!
)
exit /b 0

:mode_test
if "!LCD!"=="1" (
    echo Mode: test lcd  ^(dry-run LCD Pi^)
) else if "!WLW!"=="1" (
    echo Mode: test wlw  ^(dry-run WLW / be90webserver^)
) else (
    echo Mode: test  ^(dry-run, rsync/SSH^)
)
if "!LOGCOPY!"=="1" echo Option: logcopy
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_run
if "!LCD!"=="1" (
    echo Mode: run lcd  ^(rsync/SSH LCD Pi; always logcopy^)
) else if "!WLW!"=="1" (
    echo Mode: run wlw  ^(rsync/SSH WLW; always logcopy^)
) else (
    echo Mode: run  ^(rsync/SSH; always logcopy^)
)
echo Option: logcopy ^(always on for run^)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_logcopy
if "!LCD!"=="1" (
    echo Mode: logcopy lcd  ^(log pull + git docs\logs; LCD Pi^)
) else if "!WLW!"=="1" (
    echo Mode: logcopy wlw  ^(log pull + be90webserver\docs\logs^)
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
if "!WLW!"=="1" (
    echo ERROR: wlw cannot be combined with codeimport.
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

:mode_diff
if "!LOGCOPY!"=="1" (
    echo ERROR: logcopy cannot be combined with diff.
    echo.
    exit /b 1
)
if "!DIFF_FILE!"=="" (
    echo ERROR: Mode diff requires a repo-relative file path.
    echo Example: wanos-sync.bat diff automations.auto.yaml
    echo.
    exit /b 1
)
if "!LCD!"=="1" (
    echo Mode: diff lcd  ^(PC _lcd-agent vs LCD Pi^)
) else if "!WLW!"=="1" (
    echo Mode: diff wlw  ^(PC be90webserver vs Pi RemoteRoot^)
) else (
    echo Mode: diff  ^(PC repo vs main Pi^)
)
echo File: !DIFF_FILE!
call :invoke_ps1
exit /b %ERRORLEVEL%

endlocal
