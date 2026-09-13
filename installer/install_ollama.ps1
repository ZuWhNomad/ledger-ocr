<#
  Optional "smart error-checker" setup for LedgerOCR.
  - Installs Ollama (silently) if it is not already present.
  - Pulls the light validation model (default qwen2.5:3b).
  The app works fine without any of this; a failure here never blocks LedgerOCR.

  SECURITY (SEC-P2-1): the downloaded OllamaSetup.exe is verified BEFORE it is run.
  We require a *valid* Authenticode signature whose publisher matches -ExpectedPublisher
  (default "Ollama"); optionally a pinned -Sha256 as well. If verification fails we
  fail closed (delete the file, do NOT execute it). TLS alone is not trusted.

  Usage:
    powershell -ExecutionPolicy Bypass -File install_ollama.ps1 [-Model qwen2.5:3b]
                 [-ExpectedPublisher "Ollama"] [-Sha256 "<hex>"]
#>
param(
  [string]$Model = "qwen2.5:3b",
  [string]$ExpectedPublisher = "Ollama",   # substring expected in the signer's subject
  [string]$Sha256 = ""                      # optional pinned hash; enforced when set
)
$ErrorActionPreference = "Continue"

$InstalledByUsMarker = Join-Path $PSScriptRoot ".ollama_by_ledgerocr"
$ModelMarker         = Join-Path $PSScriptRoot ".ledgerocr_model"

function Have-Ollama {
  if (Get-Command ollama -ErrorAction SilentlyContinue) { return $true }
  return (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")
}
function Ollama-Exe {
  $c = Get-Command ollama -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
}

function Test-Downloaded([string]$file) {
  # Fail-closed integrity check. Returns $true only if the file is trustworthy.
  if (-not (Test-Path $file)) { return $false }

  if ($Sha256 -ne "") {
    $actual = (Get-FileHash -Algorithm SHA256 -Path $file).Hash
    if ($actual -ne $Sha256.ToUpper().Replace(" ","")) {
      Write-Host "SHA256 mismatch: expected $Sha256, got $actual" -ForegroundColor Red
      return $false
    }
    Write-Host "SHA256 verified." -ForegroundColor Green
  }

  $sig = Get-AuthenticodeSignature -FilePath $file
  if ($sig.Status -ne 'Valid') {
    Write-Host "Authenticode signature is not valid (status: $($sig.Status)). Refusing to run the download." -ForegroundColor Red
    return $false
  }
  $subject = ""
  if ($sig.SignerCertificate) { $subject = $sig.SignerCertificate.Subject }
  if ($ExpectedPublisher -ne "" -and $subject -notmatch [regex]::Escape($ExpectedPublisher)) {
    Write-Host "Signed, but by an unexpected publisher: '$subject' (expected to contain '$ExpectedPublisher'). Refusing." -ForegroundColor Red
    return $false
  }
  Write-Host "Signature OK - publisher: $subject" -ForegroundColor Green
  return $true
}

Write-Host "=== LedgerOCR smart error-checker setup ===" -ForegroundColor Cyan
Write-Host "You can keep using LedgerOCR while this runs; error-checking simply turns on once it finishes."

if (-not (Have-Ollama)) {
  Write-Host "Downloading Ollama (this can take a few minutes)..."
  $setup = "$env:TEMP\OllamaSetup.exe"
  try {
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup -UseBasicParsing
  } catch {
    Write-Host "Could not download Ollama automatically: $_" -ForegroundColor Yellow
    Write-Host "You can install it later from https://ollama.com and re-run this step."
    exit 0   # never fail the main install
  }
  if (-not (Test-Downloaded $setup)) {
    Write-Host "The Ollama installer could not be verified and was NOT run (this protects you from a tampered download)." -ForegroundColor Red
    Write-Host "Install Ollama yourself from https://ollama.com, then re-run this step. LedgerOCR still works without it."
    Remove-Item $setup -ErrorAction SilentlyContinue
    exit 0   # opt-in extra; never block the app
  }
  Write-Host "Installing Ollama..."
  Start-Process -FilePath $setup -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
  # record that WE installed Ollama, so uninstall can offer to remove it (SEC/PKG-P2-5)
  try { New-Item -ItemType File -Path $InstalledByUsMarker -Force | Out-Null } catch {}
} else {
  Write-Host "Ollama already installed."
}

$exe = Ollama-Exe
if (-not (Test-Path $exe) -and -not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama not found on PATH yet; open a new session or reboot, then run this again." -ForegroundColor Yellow
  exit 0
}

# make sure the background service is up, then pull the model
Start-Process -FilePath $exe -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Write-Host "Downloading the error-check model '$Model' (a few GB, one time)..."
& $exe pull $Model
if ($LASTEXITCODE -eq 0) {
  Write-Host "Done. LedgerOCR will use '$Model' for optional error-checking." -ForegroundColor Green
  try { Set-Content -Path $ModelMarker -Value $Model -Encoding utf8 } catch {}
} else {
  Write-Host "Model download did not finish. LedgerOCR still works; error-checking stays off until you pull it." -ForegroundColor Yellow
}
exit 0
