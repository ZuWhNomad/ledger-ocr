# Improvement Log

Dated entries, newest first. Each phase of the production-readiness pass appends here.

## 2026-09-13 — Phase 2: Installer & uninstaller robustness

**Changed**
- `installer/LedgerOCR.spec`: bundle `requests` (+ `certifi`, `urllib3`, `charset_normalizer`,
  `idna`) into the frozen app. `requests` is imported lazily and swallowed on ImportError, so
  before this the FROZEN app silently reported the local error-checker as unavailable even when
  Ollama was running. Now the optional Ollama error-check works from the packaged build.
- `installer/uninstall_cleanup.ps1`: the uninstaller now also offers to remove **Tesseract**
  when we installed it (`.tesseract_by_ledgerocr` marker) — via its NSIS `tesseract-uninstall.exe
  /S`, falling back to `winget uninstall`. Previously the marker was written but never read, so a
  base dependency we installed was orphaned on uninstall. Model + Ollama removal already handled.

**Verified (on this Windows 10 machine)**
- `installer/build_installer.ps1` runs end to end: PyInstaller freeze + Inno Setup compile ->
  `installer/Output/LedgerOCR-Setup.exe` (36.3 MB, unsigned; git-ignored). Inno Setup 6 is
  present at `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`.
- `requests` and `certifi/cacert.pem` are present in `dist/LedgerOCR/_internal/` (fix confirmed).
- Frozen `LedgerOCR.exe` launched and served: `GET /` -> 200 (index), `GET /api/env` -> 200 with
  `{"ocr_available":true,"llm_available":true,"llm_model":"qwen2.5:3b"}`. `llm_available:true`
  proves the bundled `requests` reaches the local Ollama end-to-end (was impossible pre-fix).

**Reviewed and judged already-robust (no change needed)**
- Per-user install (`PrivilegesRequired=lowest`) — no admin prompt.
- Offline / blocked-download fallbacks: `install_tesseract.ps1` (winget -> direct download ->
  clear "still works for born-digital PDFs" message) and `install_ollama.ps1` (download -> verify
  -> pull) both exit 0 on failure and never block the install. Downloads are integrity-checked
  (Authenticode + optional pinned SHA256), fail-closed.
- Already-installed dependencies are detected and skipped (`Have-Tesseract` / `Have-Ollama`).

**Still needs a manual clean-VM test (cannot be simulated here)**
- A true clean Windows machine with nothing installed (no Tesseract/Ollama/winget), and a
  genuine non-admin (cannot-elevate) account, to confirm the graceful-degradation messages and
  that the Tesseract/Ollama installers themselves behave under those conditions.
- A full silent install -> uninstall cycle of the compiled `LedgerOCR-Setup.exe`, verifying no
  orphaned files/registry keys and that the model/Ollama/Tesseract removal prompts fire.

## 2026-09-13 — Phase 1: Repo cleanup

**Changed**
- `.gitignore`: removed the `!/LedgerOCR-Setup.exe` negation that was force-tracking the
  ~36 MB built installer at the repo root. Both `LedgerOCR-Setup.exe` (root) and
  `installer/Output/LedgerOCR-Setup.exe` are now ignored as the build artifacts they are.
- Untracked the root `LedgerOCR-Setup.exe` with `git rm --cached` (local copy left in place
  for distribution; only the git tracking was removed).

**Verified**
- `git ls-files` shows no `.exe`, `.pyc`, `__pycache__/`, `dist/`, or `build/` tracked.
- `git check-ignore` confirms both Setup.exe paths are now ignored.
- Layout is coherent: user-facing files at root (`README.txt`, `GETTING_STARTED.txt`,
  `run.cmd`), code in `app/`, docs in `docs/`, build in `installer/`. Nothing misplaced.
- App test suite still green (11/11, `python app/tests/test_pipeline.py`) — no runtime file removed.
