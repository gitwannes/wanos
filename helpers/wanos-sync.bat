@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM WANOS Sync Wrapper (Batch)
REM ----------------------------------------------------------------------------
REM Thin launcher for helpers\wanos-sync.ps1
REM
REM Modes (must match ValidateSet in the .ps1; pick exactly one):
REM   test         Dry-run MIRROR only (rsync -n Local-->Pi). No stats/log/state pull.
REM   run          Normalize --> rsync mirror --> stats pull --> log pull --> sessionlog --> logcopy
REM   push         Code only: Normalize --> rsync mirror
REM   pull         State only: stats pull --> log pull --> sessionlog --> logcopy
REM   logcopy      Log/sessionlog pull --> copy logs into git docs\logs
REM   codeimport   Mirror only to a local Windows folder (required path arg)
REM   diff         Compare one repo-relative file PC vs Pi (normalized text diff)
REM Combining two modes (e.g. "push run") is an error.
REM
REM Optional trailing modifiers:
REM   push/pull With test: push = same as default (mirror dry-run);
REM             pull = dry-run stats/log/state only (no mirror)
REM   lcd       Target LCD Pi (\_lcd-agent --> 10.32.251.51:/home/wannes/wanos)
REM   wlw       Target WLW portal (be90webserver --> 10.32.251.30:/home/wannes/be90webserver)
REM   logcopy   With "test pull" only: also dry-run the git docs\logs copy
REM             (run/pull always logcopies; logcopy-as-mode already does it)
REM   verbose   Pass -VerboseSync to the .ps1
REM diff mode: required relpath arg after mode; only lcd, wlw, and verbose allowed.
REM lcd and wlw are mutually exclusive.
REM
REM Includes/excludes: wanos-sync.config.txt  |  engine: wanos-sync.ps1
REM Doc: docs\wanos-sync.md  |  WLW locks: be90webserver docs\wlw-sync.md
REM ============================================================================

set "PS_SCRIPT=%~dp0wanos-sync.ps1"
set "MODE="
set "DIRECTION="
set "CODEIMPORT_PATH="
set "DIFF_FILE="
set "VERBOSE=0"
set "LCD=0"
set "WLW=0"
set "LOGCOPY=0"
set "PS_DIRECTION_ARG="
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
REM Modes are mutually exclusive - a second mode word must error (e.g. "push run").
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
REM logcopy as a trailing flag (test preview, or redundant with run / pull / logcopy mode)
if /I "%~1"=="logcopy" (
    if /I "%MODE%"=="diff" goto :err_diff_bad_flag
    set "LOGCOPY=1" & shift & goto :parse_args
)
if /I "%~1"=="-logcopy" (
    if /I "%MODE%"=="diff" goto :err_diff_bad_flag
    set "LOGCOPY=1" & shift & goto :parse_args
)
REM Trailing push / pull direction allowed only with test
if /I "%~1"=="push" (
    if /I "%MODE%"=="test" (
        if defined DIRECTION goto :err_two_modes
        set "DIRECTION=push" & shift & goto :parse_args
    )
    goto :err_two_modes
)
if /I "%~1"=="pull" (
    if /I "%MODE%"=="test" (
        if defined DIRECTION goto :err_two_modes
        set "DIRECTION=pull" & shift & goto :parse_args
    )
    goto :err_two_modes
)
REM Reject a second mode keyword after the first mode.
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
    echo Modes test / run / push / pull / logcopy / codeimport / diff are mutually exclusive.
    echo.
    goto :show_help
)

:err_two_modes
echo ERROR: Cannot combine modes "%MODE%" and "%~1".
echo Use exactly one of: test ^| run ^| push ^| pull ^| logcopy ^| codeimport ^| diff
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

REM run, pull, and logcopy modes always include logcopy
if /I "%MODE%"=="run" set "LOGCOPY=1"
if /I "%MODE%"=="pull" set "LOGCOPY=1"
if /I "%MODE%"=="logcopy" set "LOGCOPY=1"

if defined DIRECTION set "PS_DIRECTION_ARG=-Direction !DIRECTION!"
if "!VERBOSE!"=="1" set "PS_VERBOSE_ARG=-VerboseSync"
if "!LCD!"=="1" set "PS_LCD_ARG=-Lcd"
if "!WLW!"=="1" set "PS_WLW_ARG=-Wlw"
if "!LOGCOPY!"=="1" set "PS_LOGCOPY_ARG=-LogCopy"
if defined DIFF_FILE set PS_DIFF_ARG=-DiffFile "!DIFF_FILE!"

if /I "%MODE%"=="test"       goto :mode_test
if /I "%MODE%"=="run"        goto :mode_run
if /I "%MODE%"=="push"       goto :mode_push
if /I "%MODE%"=="pull"       goto :mode_pull
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
echo     wanos-sync.bat test [push] [verbose]
echo         Dry-run MIRROR only ^(rsync -n^). No stats/log/state pull.
echo.
echo     wanos-sync.bat test pull [logcopy] [verbose]
echo         Dry-run pull jobs only ^(stats/logs/sessionlog; optional docs\logs^).
echo.
echo     wanos-sync.bat push [verbose]
echo         Code only: normalize, bootstrap, and mirror to Pi. No state/log pull.
echo.
echo     wanos-sync.bat pull [verbose]
echo         State only: pull stats, logs, sessionlog, and docs\logs. No mirror push.
echo.
echo     wanos-sync.bat run [verbose]
echo         Full bidirectional sync: push code, then pull stats and logs.
echo         logcopy is always included ^(no need to pass logcopy^).
echo.
echo     wanos-sync.bat logcopy [verbose]
echo         Log + sessionlog pull, then copy logs into git docs\logs only.
echo         No mirror, no stats, no normalize.
echo.
echo   LCD ^(LCD Pi .51; _lcd-agent --^> /home/wannes/wanos^)
echo     wanos-sync.bat test lcd [push] [verbose]
echo     wanos-sync.bat test pull lcd [logcopy] [verbose]
echo     wanos-sync.bat push lcd [verbose]
echo     wanos-sync.bat pull lcd [verbose]
echo     wanos-sync.bat run lcd [verbose]
echo     wanos-sync.bat logcopy lcd [verbose]
echo         Operate on LCD Pi. run/push = mirror _lcd-agent. pull = logs.
echo.
echo   WLW ^(main Pi .30; be90webserver --^> /home/wannes/be90webserver^)
echo     wanos-sync.bat test wlw [push] [verbose]
echo     wanos-sync.bat test pull wlw [logcopy] [verbose]
echo     wanos-sync.bat push wlw [verbose]
echo     wanos-sync.bat pull wlw [verbose]
echo     wanos-sync.bat run wlw [verbose]
echo     wanos-sync.bat logcopy wlw [verbose]
echo         Operate on WLW portal. run/push = mirror be90webserver. pull = state/logs.
echo.
echo   codeimport ^(local mirror only; no SSH^)
echo     wanos-sync.bat codeimport ^<windows-folder^> [verbose]
echo         Mirror repo into the given folder. Path is required. Not with lcd/wlw.
echo.
echo   diff ^(one file PC vs Pi; SSH only; no mirror/stats/logcopy^)
echo     wanos-sync.bat diff ^<repo-relative-file^> [lcd^|wlw] [verbose]
echo         Normalized text diff when both sides exist and file is text.
echo.
echo     verbose  Config load, rsync command lines, paths; LogCopy per-file;
echo              WLW STATE every path ^(normal: transfers + counts only^).
echo     Config:  helpers\wanos-sync.config.txt
echo     Docs:    docs\wanos-sync.md
echo.
exit /b 1

:invoke_ps1
if "!VERBOSE!"=="1" (
    echo Invoking: powershell -File "%PS_SCRIPT%" -Mode %MODE% !PS_DIRECTION_ARG! !PS_LCD_ARG! !PS_WLW_ARG! !PS_LOGCOPY_ARG! !PS_CODEIMPORT_ARG! !PS_DIFF_ARG! !PS_VERBOSE_ARG!
    echo Script: %PS_SCRIPT%
    echo.
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Mode %MODE% !PS_DIRECTION_ARG! !PS_LCD_ARG! !PS_WLW_ARG! !PS_LOGCOPY_ARG! !PS_CODEIMPORT_ARG! !PS_DIFF_ARG! !PS_VERBOSE_ARG!
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
set "DRY_LBL=dry-run mirror only"
if "!DIRECTION!"=="push" set "DRY_LBL=dry-run mirror only"
if "!DIRECTION!"=="pull" set "DRY_LBL=dry-run pull only"
if "!LOGCOPY!"=="1" if /I not "!DIRECTION!"=="pull" (
    echo ERROR: logcopy with test requires "test pull" ^(pull dry-run^).
    echo Default test is mirror-only and has no log/state pull to copy.
    echo.
    exit /b 1
)
if "!LCD!"=="1" (
    echo Mode: test lcd  ^(!DRY_LBL! LCD Pi^)
) else if "!WLW!"=="1" (
    echo Mode: test wlw  ^(!DRY_LBL! WLW / be90webserver^)
) else (
    echo Mode: test  ^(!DRY_LBL!^)
)
if "!LOGCOPY!"=="1" echo Option: logcopy
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_run
if "!LCD!"=="1" (
    echo Mode: run lcd  ^(bidirectional LCD Pi; always logcopy^)
) else if "!WLW!"=="1" (
    echo Mode: run wlw  ^(bidirectional WLW; always logcopy^)
) else (
    echo Mode: run  ^(bidirectional main Pi; always logcopy^)
)
echo Option: logcopy ^(always on for run^)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_push
if "!LOGCOPY!"=="1" (
    echo ERROR: logcopy cannot be combined with push.
    echo.
    exit /b 1
)
if "!LCD!"=="1" (
    echo Mode: push lcd  ^(code only PC --^> LCD Pi^)
) else if "!WLW!"=="1" (
    echo Mode: push wlw  ^(code only PC --^> WLW Pi^)
) else (
    echo Mode: push  ^(code only PC --^> main Pi^)
)
call :invoke_ps1
exit /b %ERRORLEVEL%

:mode_pull
if "!LCD!"=="1" (
    echo Mode: pull lcd  ^(logs + docs\logs LCD Pi --^> PC^)
) else if "!WLW!"=="1" (
    echo Mode: pull wlw  ^(logs + state + docs\logs WLW Pi --^> PC^)
) else (
    echo Mode: pull  ^(stats + logs + sessionlog + docs\logs main Pi --^> PC^)
)
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