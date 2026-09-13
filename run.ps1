# Launch the OCR-Pipeline drag-and-drop app on Windows.
# Usage:  powershell -ExecutionPolicy Bypass -File run.ps1
$ErrorActionPreference = "Stop"
$py = "C:\Users\m.DESKTOP-T2DPGBS.000\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Set-Location $PSScriptRoot
& $py server.py --port 8765 --open
