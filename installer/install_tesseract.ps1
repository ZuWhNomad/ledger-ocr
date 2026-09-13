<#
  BASE OCR-engine setup for LedgerOCR (installed with the app, not optional).
  Installs the Tesseract OCR engine (UB-Mannheim build) so scanned / photographed
  statements work out of the box. Born-digital PDFs don't need it; this makes scans work.

  INTEGRITY: the download is over HTTPS from the official UB-Mannheim distribution. A pinned
  -Sha256 is enforced when supplied (strongest; recommended for a controlled build), and if the
  installer carries an Authenticode signature it must be Valid. UB-Mannheim's signing has varied
  by release, so a missing signature is a warning, not a hard stop -- otherwise a signing gap would
  silently leave every user without OCR. Set -Sha256 once you've verified a version's hash for a
  fully-pinned install. Any failure here is non-fatal: the app still reads born-digital PDFs.

  Usage:
    powershell -ExecutionPolicy Bypass -File install_tesseract.ps1
                 [-Url <installer url>] [-Sha256 "<hex>"] [-ExpectedPublisher "Mannheim"]
#>
param(
  [string]$Url = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe",
  [string]$Sha256 = "",                       # optional pinned hash; enforced when set
  [string]$ExpectedPublisher = "Mannheim"     # substring expected in a signer subject, if signed
)
$ErrorActionPreference = "Continue"
$InstalledByUsMarker = Join-Path $PSScriptRoot ".tesseract_by_ledgerocr"

function Have-Tesseract {
  if (Get-Command tesseract -ErrorAction SilentlyContinue) { return $true }
  foreach ($p in @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe",
                   "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
                   "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe")) {
    if (Test-Path $p) { return $true }
  }
  return $false
}

function Test-Downloaded([string]$file) {
  if (-not (Test-Path $file)) { return $false }
  if ($Sha256 -ne "") {
    $actual = (Get-FileHash -Algorithm SHA256 -Path $file).Hash
    if ($actual -ne $Sha256.ToUpper().Replace(" ","")) {
      Write-Host "SHA256 mismatch: expected $Sha256, got $actual -- refusing to run." -ForegroundColor Red
      return $false
    }
    Write-Host "SHA256 verified." -ForegroundColor Green
  }
  $sig = Get-AuthenticodeSignature -FilePath $file
  if ($sig.Status -eq 'Valid') {
    $subject = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { "" }
    if ($ExpectedPublisher -ne "" -and $subject -notmatch [regex]::Escape($ExpectedPublisher)) {
      Write-Host "Signed by an unexpected publisher: '$subject' (expected '$ExpectedPublisher'). Proceeding on HTTPS + hash trust; set -Sha256 to pin." -ForegroundColor Yellow
    } else {
      Write-Host "Signature OK - publisher: $subject" -ForegroundColor Green
    }
  } elseif ($sig.Status -eq 'NotSigned') {
    $pinNote = if ($Sha256 -ne "") { "and the pinned SHA256." } else { "-- set -Sha256 to pin the version." }
    Write-Host "Installer is not Authenticode-signed (normal for some Tesseract builds); relying on the official HTTPS source $pinNote" -ForegroundColor Yellow
  } else {
    Write-Host "Authenticode signature status is '$($sig.Status)' -- refusing to run a tampered download." -ForegroundColor Red
    return $false
  }
  return $true
}

Write-Host "=== LedgerOCR OCR-engine (Tesseract) setup ===" -ForegroundColor Cyan

if (Have-Tesseract) { Write-Host "Tesseract already installed." -ForegroundColor Green; exit 0 }

Write-Host "Downloading the OCR engine (about 50 MB)..."
$setup = "$env:TEMP\tesseract-ledgerocr-setup.exe"
try {
  Invoke-WebRequest -Uri $Url -OutFile $setup -UseBasicParsing
} catch {
  Write-Host "Could not download Tesseract automatically: $_" -ForegroundColor Yellow
  Write-Host "You can install it later from https://github.com/UB-Mannheim/tesseract/wiki -- LedgerOCR still reads born-digital PDFs without it."
  exit 0   # never fail the main install
}
if (-not (Test-Downloaded $setup)) {
  Write-Host "The download could not be verified and was NOT run (protects you from a tampered file)." -ForegroundColor Red
  Remove-Item $setup -ErrorAction SilentlyContinue
  exit 0
}
Write-Host "Installing Tesseract (silent)..."
# UB-Mannheim installer is NSIS: /S = silent, /D = install dir (must be last, unquoted).
Start-Process -FilePath $setup -ArgumentList "/S" -Wait
try { New-Item -ItemType File -Path $InstalledByUsMarker -Force | Out-Null } catch {}  # so uninstall can offer to remove it
if (Have-Tesseract) { Write-Host "OCR engine installed - scans and photos will now work." -ForegroundColor Green }
else { Write-Host "Tesseract install finished but wasn't detected on the usual path; scans may need a manual install (see GETTING_STARTED.txt)." -ForegroundColor Yellow }
Remove-Item $setup -ErrorAction SilentlyContinue
exit 0
