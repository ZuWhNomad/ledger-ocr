@echo off
REM ============================================================
REM  LedgerOCR uninstaller (fallback / INSTALL.bat delivery).
REM  Lives inside the install folder; run it from Add/Remove
REM  Programs or by double-clicking. Removes shortcuts, the
REM  Add/Remove entry, and the app folder, and offers to remove
REM  the optional ~2 GB error-check model.
REM ============================================================
setlocal EnableExtensions
title LedgerOCR Uninstall
set "DEST=%~dp0"
set "DESTNB=%DEST:~0,-1%"

echo Removing LedgerOCR from:
echo   %DESTNB%
echo.

REM Offer to remove the optional model / Ollama (if we installed it).
if exist "%DEST%uninstall_cleanup.ps1" (
  powershell -ExecutionPolicy Bypass -NoProfile -File "%DEST%uninstall_cleanup.ps1"
)

REM Remove shortcuts.
del /q "%USERPROFILE%\Desktop\LedgerOCR.lnk" 2>nul
powershell -NoProfile -Command "Remove-Item -Recurse -Force (Join-Path ([Environment]::GetFolderPath('Programs')) 'LedgerOCR') -ErrorAction SilentlyContinue"

REM Remove the Add/Remove Programs entry (per-user).
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\LedgerOCR" /f >nul 2>nul

echo Done. Cleaning up the program folder...
REM Delete the install folder after this script exits (it can't delete itself while running).
start "" /min cmd /c "timeout /t 2 >nul & rmdir /s /q ""%DESTNB%"""
endlocal
