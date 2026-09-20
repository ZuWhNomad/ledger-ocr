<#
  Build the distributable:
    1. freeze with PyInstaller (one-folder)      -> installer\dist\LedgerOCR\LedgerOCR.exe
    2. smoke-test the frozen exe (--health must list an OCR engine)
    3. compile the Inno Setup installer           -> installer\Output\LedgerOCR-Setup.exe
  Usage:  powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
  Needs: the repo's .venv with `pip install -e .[extras] pyinstaller`, and Inno Setup 6 for step 3.

  Code signing (optional, skipped when unset): CODESIGN_THUMBPRINT, or CODESIGN_PFX + CODESIGN_PASS;
  CODESIGN_TS overrides the timestamp server. Unsigned builds trigger SmartScreen on other machines.
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "no .venv: python -m venv .venv; .venv\Scripts\python -m pip install -e .[extras] pyinstaller" }

# --- optional signing --------------------------------------------------------
function Find-SignTool {
  $c = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($r in @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "$env:ProgramFiles\Windows Kits\10\bin")) {
    if (Test-Path $r) {
      $hit = Get-ChildItem -Path $r -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
             Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1
      if ($hit) { return $hit.FullName }
    }
  }
  return $null
}
$TS = if ($env:CODESIGN_TS) { $env:CODESIGN_TS } else { "http://timestamp.digicert.com" }
$signtool = $null; $certArgs = @(); $signConfigured = $false
if ($env:CODESIGN_THUMBPRINT -or ($env:CODESIGN_PFX -and $env:CODESIGN_PASS)) {
  $signtool = Find-SignTool
  if ($signtool) {
    $certArgs = if ($env:CODESIGN_THUMBPRINT) { @("/sha1", $env:CODESIGN_THUMBPRINT) } else { @("/f", $env:CODESIGN_PFX, "/p", $env:CODESIGN_PASS) }
    $signConfigured = $true
    Write-Host "Code signing ENABLED ($signtool)" -ForegroundColor Green
  } else { Write-Host "Signing cert set but signtool.exe not found (Windows SDK). Building UNSIGNED." -ForegroundColor Yellow }
} else { Write-Host "No signing cert configured: building UNSIGNED (SmartScreen will warn on other machines)." -ForegroundColor Yellow }
function Sign-File([string]$path) {
  if (-not $signConfigured) { return }
  & $signtool sign /fd sha256 /tr $TS /td sha256 @certArgs "$path"
  if ($LASTEXITCODE -ne 0) { throw "signtool failed for $path" }
}

# 1) freeze
Write-Host "== PyInstaller ==" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --distpath installer\dist --workpath installer\build installer\LedgerOCR.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
Sign-File "installer\dist\LedgerOCR\LedgerOCR.exe"

# 2) smoke test: the frozen exe must find an OCR engine and read the sample
Write-Host "== Smoke test ==" -ForegroundColor Cyan
$health = & "installer\dist\LedgerOCR\LedgerOCR.exe" --health | ConvertFrom-Json
if (-not $health.ocr_engines) { throw "frozen exe found no OCR engine: $($health | ConvertTo-Json -Compress)" }
$out = Join-Path $env:TEMP ("ledgerocr-smoke-" + [guid]::NewGuid())
$r = & "installer\dist\LedgerOCR\LedgerOCR.exe" "test\fixtures\bank_statement.pdf" --out $out --json | ConvertFrom-Json
Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
if (-not $r.ok -or $r.rows.Count -ne 15) { throw "frozen exe did not read the sample statement" }
Write-Host "frozen exe OK: engines $($health.ocr_engines -join '+'), sample -> $($r.rows.Count) rows" -ForegroundColor Green

# 3) installer
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Write-Host "Inno Setup not found; ship the folder installer\dist\LedgerOCR as is." -ForegroundColor Yellow; exit 0 }
Write-Host "== Inno Setup ==" -ForegroundColor Cyan
$isccArgs = @("installer\LedgerOCR.iss")
if ($signConfigured) {
  $signCmd = "`"$signtool`" sign /fd sha256 /tr $TS /td sha256 $($certArgs -join ' ') `$f"
  $isccArgs = @("/DSIGN", "/Sledgerocrsign=$signCmd", "installer\LedgerOCR.iss")
}
& $iscc /Q @isccArgs
if ($LASTEXITCODE -ne 0) { throw "ISCC compile failed" }
Write-Host "Done: installer\Output\LedgerOCR-Setup.exe" -ForegroundColor Green
