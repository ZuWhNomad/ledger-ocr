# installer/

Packages the app into a single double-click installer for non-technical Windows users.

**Build (one command):** `powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1`
- freezes the app with PyInstaller (`LedgerOCR.spec`, one-folder) -> `dist/LedgerOCR/`
- compiles `LedgerOCR.iss` with Inno Setup -> `Output/LedgerOCR-Setup.exe`

**Two delivery forms (same frozen app):**
- **`LedgerOCR-Setup.exe`** (preferred) — Inno Setup, per-user (no admin), Desktop + Start Menu
  shortcuts, an optional "smart error-checker" task (OFF by default, runs `install_ollama.ps1`
  non-blocking). Its uninstaller runs `uninstall_cleanup.ps1` to offer removing the pulled model.
- **Folder + `INSTALL.bat`** (fallback) — for when Inno Setup isn't available. Ship
  `dist/LedgerOCR/` (renamed/placed as `LedgerOCR/`) next to `INSTALL.bat`, `install_ollama.ps1`,
  `uninstall_cleanup.ps1`, `UNINSTALL.bat`, and `GETTING_STARTED.txt`. The .bat copies the app to
  `%LOCALAPPDATA%\Programs\LedgerOCR`, makes shortcuts, registers an Add/Remove Programs entry
  (HKCU) pointing at `UNINSTALL.bat`, optionally sets up the model, and launches the app.

**Entry point of the frozen app:** `../app/run_app.py` -> `server.serve(port=8765, open_browser=True)`.

**Code signing (optional, PKG-P1-1):** `build_installer.ps1` signs the frozen exe and the
Setup.exe when `CODESIGN_THUMBPRINT` or `CODESIGN_PFX`+`CODESIGN_PASS` are set (skips cleanly
otherwise). The .iss enables signing of its output via `#ifdef SIGN` -> `SignTool=ledgerocrsign`,
which the build defines with `/DSIGN /Sledgerocrsign=...`. See `../docs/SIGNING.txt`.

**Download integrity (SEC-P2-1):** `install_ollama.ps1` verifies the downloaded `OllamaSetup.exe`
(Authenticode signature Valid + publisher match, optional pinned SHA256) and fails closed —
deletes and does not run — if verification fails.

**Invariants**
- Build outputs (`dist/`, `build/`, `Output/`, `*.exe`) are git-ignored; only source is committed.
- The app must launch and serve with no model present; `install_ollama.ps1` is optional and must
  never fail the install (it exits 0 even on download/verification errors).
- Signing must be optional: no cert env set -> unsigned build, never a hard failure.

**Tested:** the frozen exe serves the drop zone and processes `samples/bank_statement.pdf`. The
PowerShell/Inno/bat scripts here were edited but the full `Setup.exe` (re)build was NOT re-run in
this pass — re-verify `build_installer.ps1` (signed and unsigned), a silent install/uninstall, and
`INSTALL.bat`/`UNINSTALL.bat` on Windows before shipping.
