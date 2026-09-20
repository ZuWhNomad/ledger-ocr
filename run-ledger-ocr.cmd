@echo off
rem Launcher: uses the local .venv when there is one, else whatever "python" is on PATH.
setlocal
set "HERE=%~dp0"
set "PY=python"
if exist "%HERE%.venv\Scripts\python.exe" set "PY=%HERE%.venv\Scripts\python.exe"
set "PYTHONPATH=%HERE%;%PYTHONPATH%"
"%PY%" -m ledger_ocr %*
