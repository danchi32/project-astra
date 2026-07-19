@echo off
REM ============================================================
REM  ASTRA Agent Uninstaller  --  just double-click this file.
REM  Self-elevates to Administrator, then runs the PowerShell
REM  uninstaller sitting next to it (Uninstall-AstraAgent.ps1).
REM ============================================================

REM --- Re-launch elevated if we are not already Administrator ---
net session >nul 2>&1
if %errorlevel% NEQ 0 (
    echo Requesting Administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ==== Uninstalling ASTRA agent ====
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-AstraAgent.ps1" %*

echo.
echo Done. Press any key to close.
pause >nul
