@echo off
REM robocopy-sync.bat
REM Convert a single script to LF, then run robocopy jobs.

setlocal

REM ---------- configure ----------
set "SRC_FILE=C:\data\git\wanos\wanos_boot.sh"
set "TARGET_Z=Z:"
set "CODE_IMPORT=C:\data\git\wanos\code-import"
set "RCJ=wanos.rcj"
REM -------------------------------

echo.
echo --- Normalizing line endings for: "%SRC_FILE%"

REM Single-line PowerShell command to avoid quoting/Param issues.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Test-Path '%SRC_FILE%') { $t = Get-Content -Raw -Encoding UTF8 '%SRC_FILE%'; $n = $t -replace \"`r`n\",\"`n\"; if ($n -ne $t) { Set-Content -NoNewline -Encoding UTF8 -Value $n -Path '%SRC_FILE%'; Write-Host 'Converted: %SRC_FILE%'; } else { Write-Host 'Already LF: %SRC_FILE%'; } } else { Write-Host 'Not found: %SRC_FILE%'; }"

echo.
echo --- Starting robocopy to Pi (Z:\) ...
robocopy /JOB:"%RCJ%" "%TARGET_Z%"

echo.
echo --- Starting robocopy to CodeFolder ...
robocopy /JOB:"%RCJ%" "%CODE_IMPORT%"

echo.
echo --- Sync Complete!
endlocal