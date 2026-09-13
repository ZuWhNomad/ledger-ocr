<#
  Runs during LedgerOCR uninstall (both the Inno and the INSTALL.bat delivery forms).

  The optional error-checker pulled a ~2 GB model and, if LedgerOCR installed it,
  Ollama itself. Uninstalling LedgerOCR would otherwise leave both behind silently
  (PKG-P2-5). This offers to remove them:
    - the pulled model: always offered (Ollama may be used by other apps, so we only
      remove the ONE model we pulled -- never Ollama itself here).
    - Ollama itself: offered ONLY if the marker shows WE installed it.

  Non-blocking and fail-safe: every prompt times out to "No", and any error exits 0 so
  uninstall always completes.
#>
$ErrorActionPreference = "Continue"

$ModelMarker         = Join-Path $PSScriptRoot ".ledgerocr_model"
$InstalledByUsMarker = Join-Path $PSScriptRoot ".ollama_by_ledgerocr"

$Model = "qwen2.5:3b"
if (Test-Path $ModelMarker) {
  try { $m = (Get-Content $ModelMarker -ErrorAction Stop | Select-Object -First 1).Trim(); if ($m) { $Model = $m } } catch {}
}

function Ask([string]$text, [string]$title) {
  # Returns $true only on an explicit Yes; times out to No after 120s so uninstall never hangs.
  try {
    $w = New-Object -ComObject WScript.Shell
    $r = $w.Popup($text, 120, $title, 4 + 32)   # 4=Yes/No, 32=question
    return ($r -eq 6)
  } catch { return $false }
}
function Ollama-Exe {
  $c = Get-Command ollama -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $p = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
  if (Test-Path $p) { return $p }
  return $null
}

$exe = Ollama-Exe
if ($exe) {
  if (Ask("Also remove the ~2 GB error-check model '$Model' that LedgerOCR downloaded?`n`n(Ollama itself will be kept unless you choose to remove it next.)", "LedgerOCR uninstall")) {
    Write-Host "Removing model '$Model'..."
    & $exe rm $Model
  }
}

if (Test-Path $InstalledByUsMarker) {
  if (Ask("LedgerOCR installed Ollama (the local error-checker engine) for you. Remove Ollama as well?`n`n(Choose No if you use it with other apps.)", "LedgerOCR uninstall")) {
    $uninst = "$env:LOCALAPPDATA\Programs\Ollama\uninstall.exe"
    if (Test-Path $uninst) {
      Write-Host "Uninstalling Ollama..."
      Start-Process -FilePath $uninst -ArgumentList "/S" -Wait -ErrorAction SilentlyContinue
    } else {
      Write-Host "Could not find the Ollama uninstaller. Remove it from Settings > Apps if you no longer want it." -ForegroundColor Yellow
    }
  }
}
exit 0
