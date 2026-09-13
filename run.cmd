@echo off
REM Launch LedgerOCR from source. Double-click this file.
REM (For the installed app, use the LedgerOCR desktop icon instead.)
cd /d "%~dp0app"
py -3 server.py --port 8765 --open 2>nul
if errorlevel 1 python server.py --port 8765 --open
echo.
echo LedgerOCR has stopped. Press any key to close this window.
pause >nul
