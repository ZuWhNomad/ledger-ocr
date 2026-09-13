<#
  Build the whole distributable in one step:
    1. freeze the app with PyInstaller (one-folder) -> installer\dist\LedgerOCR
    2. (optional) code-sign the frozen LedgerOCR.exe
    3. compile the Inno Setup installer            -> installer\Output\LedgerOCR-Setup.exe
       (Inno signs the generated Setup.exe too, when signing is configured)

  Usage (from the repo root or anywhere):
    powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1

  Requires: Python with pyinstaller (pip install pyinstaller) and Inno Setup 6 (ISCC.exe).
  If Inno Setup is missing, the PyInstaller step still runs and you can ship the
  installer\dist\LedgerOCR folder with INSTALL.bat as the fallback installer.

  CODE SIGNING (PKG-P1-1) -- entirely optional, skipped cleanly when no cert is set:
    Provide EITHER
      $env:CODESIGN_THUMBPRINT  = "<sha1 thumbprint of a cert in your store>"
    OR
      $env:CODESIGN_PFX  = "C:\path\to\cert.pfx"
      $env:CODESIGN_PASS = "<pfx password>"
    Optional: $env:CODESIGN_TS = timestamp URL (default http://timestamp.digicert.com).
    When set, both the frozen exe and the Setup.exe are signed with an RFC3161
    timestamp (/tr), SHA-256 file digest (/fd) and SHA-256 timestamp digest (/td).
    When unset, the build proceeds UNSIGNED and prints a note. See SIGNING.md.
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# 1) find a Python that has PyInstaller
$py = "C:\Users\m.DESKTOP-T2DPGBS.000\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# --- resolve optional code-signing config -----------------------------------
function Find-SignTool {
  $c = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $roots = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "$env:ProgramFiles\Windows Kits\10\bin")
  foreach ($r in $roots) {
    if (Test-Path $r) {
      $hit = Get-ChildItem -Path $r -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
             Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1
      if ($hit) { return $hit.FullName }
    }
  }
  return $null
}

$TS = if ($env:CODESIGN_TS) { $env:CODESIGN_TS } else { "http://timestamp.digicert.com" }
$signtool = $null
$certArgs = @()
$signConfigured = $false
if ($env:CODESIGN_THUMBPRINT -or ($env:CODESIGN_PFX -and $env:CODESIGN_PASS)) {
  $signtool = Find-SignTool
  if (-not $signtool) {
    Write-Host "A signing cert is set but signtool.exe was not found (install the Windows 10/11 SDK). Building UNSIGNED." -ForegroundColor Yellow
  } else {
    if ($env:CODESIGN_THUMBPRINT) {
      $certArgs = @("/sha1", $env:CODESIGN_THUMBPRINT)
    } else {
      $certArgs = @("/f", $env:CODESIGN_PFX, "/p", $env:CODESIGN_PASS)
    }
    $signConfigured = $true
    Write-Host "Code signing ENABLED (signtool: $signtool)" -ForegroundColor Green
  }
} else {
  Write-Host "No code-signing cert configured (set CODESIGN_THUMBPRINT or CODESIGN_PFX + CODESIGN_PASS)." -ForegroundColor Yellow
  Write-Host "Building UNSIGNED -- users will see a SmartScreen prompt. See SIGNING.md and GETTING_STARTED.md." -ForegroundColor Yellow
}

function Sign-File([string]$path) {
  if (-not $signConfigured) { return }
  Write-Host "Signing $path ..." -ForegroundColor Cyan
  & $signtool sign /fd sha256 /tr $TS /td sha256 @certArgs "$path"
  if ($LASTEXITCODE -ne 0) { throw "signtool failed for $path" }
}

# 1) freeze
Write-Host "== Freezing app with PyInstaller ==" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --distpath installer\dist --workpath installer\build LedgerOCR.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# 2) sign the frozen exe (before it is packed into the installer)
Sign-File "installer\dist\LedgerOCR\LedgerOCR.exe"

# 3) compile the installer if Inno Setup is present
$iscc = @(
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
  Write-Host "== Compiling installer with Inno Setup ==" -ForegroundColor Cyan
  $isccArgs = @("installer\LedgerOCR.iss")
  if ($signConfigured) {
    # Inno signs the produced Setup.exe by invoking this command with $f = file to sign.
    $certArgsStr = ($certArgs -join ' ')
    $signCmd = "`"$signtool`" sign /fd sha256 /tr $TS /td sha256 $certArgsStr `$f"
    $isccArgs = @("/DSIGN", "/Sledgerocrsign=$signCmd", "installer\LedgerOCR.iss")
  }
  & $iscc @isccArgs
  if ($LASTEXITCODE -ne 0) { throw "ISCC compile failed" }
  Write-Host "Done: installer\Output\LedgerOCR-Setup.exe" -ForegroundColor Green
  if (-not $signConfigured) {
    Write-Host "(unsigned build -- see GETTING_STARTED.md 'If Windows shows a blue warning')" -ForegroundColor Yellow
  }
} else {
  Write-Host "Inno Setup not found. Ship the folder installer\dist\LedgerOCR alongside" -ForegroundColor Yellow
  Write-Host "installer\INSTALL.bat, installer\install_ollama.ps1 and installer\uninstall_cleanup.ps1 as the fallback installer." -ForegroundColor Yellow
}
