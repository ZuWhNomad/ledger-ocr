# Improvement Log

Dated entries, newest first. Each phase of the production-readiness pass appends here.

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
