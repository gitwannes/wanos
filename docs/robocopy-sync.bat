@echo off
REM robocopy-sync.bat
REM Sync tool with switches: test | run | runlocal

setlocal ENABLEDELAYEDEXPANSION

REM ---------- configure ----------
set "SRC_FILE=C:\data\git\wanos\wanos_boot.sh"
set "TARGET_Z=Z:"
set "CODE_IMPORT=C:\data\git\wanos\code-import"
set "RCJ=wanos.rcj"
REM -------------------------------

REM ---------- environment checks ----------
echo.
echo ================================
echo Checking environment...

echo Checking Z: drive...
if exist "%TARGET_Z%\" (
    echo Z: reachable
) else (
    echo Z: NOT reachable
)

echo Checking CodeFolder...
if exist "%CODE_IMPORT%\" (
	echo CodeFolder ^(for use with AI^) exists
) else (
    echo CodeFolder NOT found
)

echo ================================
REM ---------- argument parsing ----------
if "%~1"=="" goto :show_help
if /I "%~1"=="test"     goto :mode_test
if /I "%~1"=="run"      goto :mode_run
if /I "%~1"=="runlocal" goto :mode_runlocal

echo.
echo.
REM ---------- HELP ----------
:show_help
echo.
echo Usage:
echo     robocopy-sync.bat test      ^> Dry-run, show what WOULD be copied
echo     robocopy-sync.bat run       ^> Perform full sync (Z: + CodeFolder)
echo     robocopy-sync.bat runlocal  ^> Sync ONLY to CodeFolder (no Z:)
echo.
echo No actions performed.
goto :eof


REM ---------- TEST MODE ----------
:mode_test
echo.
echo ================================
echo Running in TEST MODE
echo No files will be copied or deleted.
echo ================================
echo.

echo --- Starting robocopy to Pi (Z:\) [DRY RUN] ...
robocopy /JOB:"%RCJ%" "%TARGET_Z%" /L

echo.
echo Test run complete.
goto :eof


REM ---------- RUN MODE ----------
:mode_run
echo.
echo ================================
echo Running in RUN MODE
echo Files WILL be copied and deleted.
echo ================================
echo.

echo --- Normalizing line endings for: "%SRC_FILE%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Test-Path '%SRC_FILE%') { $t = Get-Content -Raw -Encoding UTF8 '%SRC_FILE%'; $n = $t -replace \"`r`n\",\"`n\"; if ($n -ne $t) { Set-Content -NoNewline -Encoding UTF8 -Value $n -Path '%SRC_FILE%'; Write-Host 'Converted: %SRC_FILE%'; } else { Write-Host 'Already LF: %SRC_FILE%'; } } else { Write-Host 'Not found: %SRC_FILE%'; }"

echo.
echo --- Starting robocopy to Pi (Z:\) ...
robocopy /JOB:"%RCJ%" "%TARGET_Z%"

echo.
echo --- Starting robocopy to CodeFolder ...
robocopy /JOB:"%RCJ%" "%CODE_IMPORT%"

echo.
echo Sync complete.
goto :eof


REM ---------- RUNLOCAL MODE ----------
:mode_runlocal
echo.
echo ================================
echo Running in RUNLOCAL MODE
echo Only syncing to CodeFolder
echo ================================
echo.

echo --- Starting robocopy to CodeFolder (RUNLOCAL) ...
robocopy /JOB:"%RCJ%" "%CODE_IMPORT%"

echo.
echo Local-only sync complete.
goto :eof

endlocal