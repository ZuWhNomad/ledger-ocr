<#
  Optional "smart error-checker" setup for LedgerOCR.
  - Installs Ollama (silently) if it is not already present.
  - Pulls the light validation model (default qwen2.5:3b).
  The app works fine without any of this; a failure here never blocks LedgerOCR.

  Usage:  powershell -ExecutionPolicy Bypass -File install_ollama.ps1 [-Model qwen2.5:3b]
#>
param([string]$Model = "qwen2.5:3b")
$ErrorActionPreference = "Continue"

function Have-Ollama {
  if (Get-Command ollama -ErrorAction SilentlyContinue) { return $true }
  return (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")
}
function Ollama-Exe {
  $c = Get-Command ollama -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
}

Write-Host "=== LedgerOCR smart error-checker setup ===" -ForegroundColor Cyan

if (-not (Have-Ollama)) {
  Write-Host "Downloading Ollama (this can take a few minutes)..."
  $setup = "$env:TEMP\OllamaSetup.exe"
  try {
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup -UseBasicParsing
    Write-Host "Installing Ollama..."
    Start-Process -FilePath $setup -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
  } catch {
    Write-Host "Could not download/install Ollama automatically: $_" -ForegroundColor Yellow
    Write-Host "You can install it later from https://ollama.com and re-run this step."
    exit 0   # never fail the main install
  }
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
} else {
  Write-Host "Model download did not finish. LedgerOCR still works; error-checking stays off until you pull it." -ForegroundColor Yellow
}
exit 0
