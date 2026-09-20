# installer/

Purpose: turn the package into `LedgerOCR.exe` (PyInstaller one-folder) and `LedgerOCR-Setup.exe` (Inno Setup,
per-user, no admin). Nothing else gets installed: OCR is Windows' own (`winrt` modules are frozen in).

Entry: `powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1` (freeze → smoke test → Setup.exe).
Outputs are git-ignored: `installer\dist\`, `installer\build\`, `installer\Output\`.

Invariants: the exe is the CLI (`entry.py` → `cli.main`); no arguments = the browser page. The build fails if the
frozen exe finds no OCR engine or cannot read the sample statement. Unsigned unless `CODESIGN_*` is set.

| symptom | file |
|---|---|
| frozen exe: ModuleNotFoundError / missing DLL / no `winocr` engine | `LedgerOCR.spec` (collect lists) |
| Setup.exe layout, shortcuts, version string | `LedgerOCR.iss` |
| build order, signing, smoke test | `build_installer.ps1` |
