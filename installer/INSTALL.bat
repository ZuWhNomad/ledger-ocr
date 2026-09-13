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
  echo.
  echo This INSTALL.bat is the "folder" install option and must sit NEXT TO the built
  echo LedgerOCR app folder (both come together in the distributed zip).
  echo.
  echo   * If you unzipped a release: make sure you extracted the WHOLE folder, then run
  echo     INSTALL.bat from there ^(not from inside a sub-folder^).
  echo   * If this is the source code repo: just run  LedgerOCR-Setup.exe  in the top
  echo     folder instead. ^(Or build first: installer\build_installer.ps1.^)
  pause & exit /b 1
)

echo.
echo Installing LedgerOCR to:
echo   %DEST%
echo.
if not exist "%DEST%" mkdir "%DEST%"
robocopy "%SRC%" "%DEST%" /E /NFL /NDL /NJH /NJS /NP >nul
if exist "%~dp0install_tesseract.ps1" copy /y "%~dp0install_tesseract.ps1" "%DEST%\" >nul
if exist "%~dp0install_ollama.ps1" copy /y "%~dp0install_ollama.ps1" "%DEST%\" >nul
if exist "%~dp0uninstall_cleanup.ps1" copy /y "%~dp0uninstall_cleanup.ps1" "%DEST%\" >nul
if exist "%~dp0UNINSTALL.bat" copy /y "%~dp0UNINSTALL.bat" "%DEST%\" >nul
if exist "%~dp0GETTING_STARTED.txt" copy /y "%~dp0GETTING_STARTED.txt" "%DEST%\" >nul

echo Creating shortcuts...
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut((Join-Path([Environment]::GetFolderPath('Desktop')) 'LedgerOCR.lnk')); $s.TargetPath='%DEST%\LedgerOCR.exe'; $s.WorkingDirectory='%DEST%'; $s.Save()"
powershell -NoProfile -Command "$p=Join-Path([Environment]::GetFolderPath('Programs')) 'LedgerOCR'; New-Item -ItemType Directory -Force -Path $p ^| Out-Null; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut((Join-Path $p 'LedgerOCR.lnk')); $s.TargetPath='%DEST%\LedgerOCR.exe'; $s.WorkingDirectory='%DEST%'; $s.Save()"

echo Registering in Add/Remove Programs...
set "UNINST=%DEST%\UNINSTALL.bat"
set "REGKEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\LedgerOCR"
reg add "%REGKEY%" /v DisplayName /t REG_SZ /d "LedgerOCR" /f >nul
reg add "%REGKEY%" /v DisplayVersion /t REG_SZ /d "0.1.0" /f >nul
reg add "%REGKEY%" /v Publisher /t REG_SZ /d "LedgerOCR" /f >nul
reg add "%REGKEY%" /v InstallLocation /t REG_SZ /d "%DEST%" /f >nul
reg add "%REGKEY%" /v DisplayIcon /t REG_SZ /d "%DEST%\LedgerOCR.exe" /f >nul
reg add "%REGKEY%" /v UninstallString /t REG_SZ /d "\"%UNINST%\"" /f >nul
reg add "%REGKEY%" /v NoModify /t REG_DWORD /d 1 /f >nul
reg add "%REGKEY%" /v NoRepair /t REG_DWORD /d 1 /f >nul

echo.
echo Installing the OCR engine so scans and photos work (about 50 MB)...
powershell -ExecutionPolicy Bypass -NoProfile -File "%DEST%\install_tesseract.ps1"

echo.
echo LedgerOCR works right now. Born-digital PDFs need nothing more; the OCR engine
echo above lets it also read scans and photos.
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
