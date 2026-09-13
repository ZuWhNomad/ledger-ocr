<#
  Build the whole distributable in one step:
    1. freeze the app with PyInstaller (one-folder) -> installer\dist\LedgerOCR
    2. compile the Inno Setup installer            -> installer\Output\LedgerOCR-Setup.exe

  Usage (from the repo root or anywhere):
    powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1

  Requires: Python with pyinstaller (pip install pyinstaller) and Inno Setup 6 (ISCC.exe).
  If Inno Setup is missing, the PyInstaller step still runs and you can ship the
  installer\dist\LedgerOCR folder with INSTALL.bat as the fallback installer.
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# 1) find a Python that has PyInstaller
$py = "C:\Users\m.DESKTOP-T2DPGBS.000\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "== Freezing app with PyInstaller ==" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --distpath installer\dist --workpath installer\build LedgerOCR.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# 2) compile the installer if Inno Setup is present
$iscc = @(
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
  Write-Host "== Compiling installer with Inno Setup ==" -ForegroundColor Cyan
  & $iscc "installer\LedgerOCR.iss"
  if ($LASTEXITCODE -ne 0) { throw "ISCC compile failed" }
  Write-Host "Done: installer\Output\LedgerOCR-Setup.exe" -ForegroundColor Green
} else {
  Write-Host "Inno Setup not found. Ship the folder installer\dist\LedgerOCR alongside" -ForegroundColor Yellow
  Write-Host "installer\INSTALL.bat and installer\install_ollama.ps1 as the fallback installer." -ForegroundColor Yellow
}
