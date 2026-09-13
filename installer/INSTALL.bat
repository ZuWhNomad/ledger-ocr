@echo off
REM ============================================================
REM  LedgerOCR installer (no admin, no Python, no terminal use)
REM  Double-click this file. It copies the app, makes shortcuts,
REM  optionally sets up the smart error-checker, and launches it.
REM ============================================================
setlocal EnableExtensions
title LedgerOCR Setup

set "SRC=%~dp0LedgerOCR"
set "DEST=%LOCALAPPDATA%\Programs\LedgerOCR"
REM (advanced/testing) override the install location:  set LEDGEROCR_DEST=... before running
if defined LEDGEROCR_DEST set "DEST=%LEDGEROCR_DEST%"

if not exist "%SRC%\LedgerOCR.exe" (
  echo ERROR: cannot find the app files next to this installer.
  echo Expected: "%SRC%\LedgerOCR.exe"
  echo Make sure you unzipped the whole folder before running INSTALL.
  pause & exit /b 1
)

echo.
echo Installing LedgerOCR to:
echo   %DEST%
echo.
if not exist "%DEST%" mkdir "%DEST%"
robocopy "%SRC%" "%DEST%" /E /NFL /NDL /NJH /NJS /NP >nul
if exist "%~dp0install_ollama.ps1" copy /y "%~dp0install_ollama.ps1" "%DEST%\" >nul
if exist "%~dp0GETTING_STARTED.md" copy /y "%~dp0GETTING_STARTED.md" "%DEST%\" >nul

echo Creating shortcuts...
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut((Join-Path([Environment]::GetFolderPath('Desktop')) 'LedgerOCR.lnk')); $s.TargetPath='%DEST%\LedgerOCR.exe'; $s.WorkingDirectory='%DEST%'; $s.Save()"
powershell -NoProfile -Command "$p=Join-Path([Environment]::GetFolderPath('Programs')) 'LedgerOCR'; New-Item -ItemType Directory -Force -Path $p ^| Out-Null; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut((Join-Path $p 'LedgerOCR.lnk')); $s.TargetPath='%DEST%\LedgerOCR.exe'; $s.WorkingDirectory='%DEST%'; $s.Save()"

echo.
echo LedgerOCR works right now without any extra download.
echo The "smart error-checker" is optional: it downloads a helper (Ollama) and a
echo model (~2 GB) so the app can flag suspicious rows for you.
echo.
choice /C YN /M "Install the smart error-checker now (recommended)"
if errorlevel 2 goto :launch
echo Setting up the smart error-checker (this can take several minutes)...
powershell -ExecutionPolicy Bypass -NoProfile -File "%DEST%\install_ollama.ps1"

:launch
echo.
echo Done. Opening LedgerOCR...
start "" "%DEST%\LedgerOCR.exe"
echo You can also use the new LedgerOCR icon on your Desktop any time.
echo.
pause
endlocal
