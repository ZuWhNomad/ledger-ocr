# installer/

Packages the app into a single double-click installer for non-technical Windows users.

**Build (one command):** `powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1`
- freezes the app with PyInstaller (`../LedgerOCR.spec`, one-folder) -> `dist/LedgerOCR/`
- compiles `LedgerOCR.iss` with Inno Setup -> `Output/LedgerOCR-Setup.exe`

**Two delivery forms (same frozen app):**
- **`LedgerOCR-Setup.exe`** (preferred) — Inno Setup, per-user (no admin), Desktop + Start Menu
  shortcuts, an optional "smart error-checker" task that runs `install_ollama.ps1`.
- **Folder + `INSTALL.bat`** (fallback) — for when Inno Setup isn't available. Ship
  `dist/LedgerOCR/` (renamed/placed as `LedgerOCR/`) next to `INSTALL.bat`, `install_ollama.ps1`,
  and `GETTING_STARTED.md`. The .bat copies the app to `%LOCALAPPDATA%\Programs\LedgerOCR`, makes
  shortcuts, optionally sets up the model, and launches the app.

**Entry point of the frozen app:** `../run_app.py` -> `server.serve(port=8765, open_browser=True)`.

**Invariants**
- Build outputs (`dist/`, `build/`, `Output/`, `*.exe`) are git-ignored; only source is committed.
- The app must launch and serve with no model present; `install_ollama.ps1` is optional and must
  never fail the install (it exits 0 even on download errors).

**Tested:** the frozen exe serves the drop zone and processes `samples/bank_statement.pdf`; both
the Inno `Setup.exe` (silent install + uninstall) and `INSTALL.bat` (copy + shortcuts + launch)
were verified on Windows 10.
