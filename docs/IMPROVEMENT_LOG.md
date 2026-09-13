# Improvement Log

Dated entries, newest first. Each phase of the production-readiness pass appends here.

## 2026-09-13 — Phase 4B: OCR engine comparison + adopt the word-box path

**Research (quantified in docs/BENCHMARK.md, "OCR engine comparison")**
- Compared, locally, Tesseract `image_to_string` (Path A, the old textline parser) vs
  `image_to_data` word-boxes + header-anchored reconstruction (Path B), on all 7 fixtures
  rendered to clean 300-dpi images. **Path B aggregate micro-F1 ~0.91 vs Path A ~0.54** (and
  slightly faster). Path B recovers debit/credit as separate columns, keeps wide descriptions
  out of money cells, and carries columns across continuation pages. Path A cannot separate
  debit/credit at all. No other engine evaluated: EasyOCR/PaddleOCR/onnx/torch would violate
  the PLAN's no-heavy/native-dep rule — noted for the reviewer, not installed.

**Adopted (production change)**
- `tables.py`: extracted the header-anchored reconstruction into a shared
  `build_rows_from_words(words, page_width, carry_bounds)`; `extract_words_table` now calls it.
- `extract.py`: added `ocr_to_rows()` (rasterize -> `image_to_data --psm 6` ->
  `build_rows_from_words`, carrying column bounds across pages) plus shared `_iter_page_images`
  / `_ocr_scope` helpers. `ocr_to_text` kept for the fallback.
- `pipeline.py`: `_ocr_extract` uses the word-box path first and falls back to the text-line
  parser only when it recovers no rows (handles border-heavy scans like `full_grid`). The
  summary `strategy` now reports `ocr-words` or `ocr-textlines`.
- Scans and born-digital PDFs now share ONE tested column code path (PLAN's biggest OCR win).

**Verified (ran myself)**
- `python app/tests/test_pipeline.py` -> 12/12 (new `test_ocr_words_path_recovers_columns`
  renders the sample to a PNG, routes through OCR, and asserts debit AND credit are recovered
  and the injected balance error is still flagged; skips if Tesseract is absent).
- `python app/tests/bench.py` unchanged (born-digital micro-F1 0.9948).
- `python app/tests/bench_ocr.py` -> Path B 0.9140 vs Path A 0.5419 (Path B now runs the exact
  production `build_rows_from_words`, so the benchmark can't drift from shipped behavior).

**Note**
- The 4B worker (gemini-3.8-flash-low) claimed it updated docs/BENCHMARK.md but had not; I wrote
  that section myself from the reproduced numbers. bench.py's `score_rows` refactor was correct.

## 2026-09-13 — Phase 4A: Benchmark harness + ground-truth fixtures

**Added**
- `app/tests/fixtures/generate.py` — deterministic reportlab generator for 7 born-digital
  fixture shapes (reusing the existing `samples/make_sample.py` builders where a shape exists):
  base ruled statement, single signed-amount column, two-page (header only on page 1),
  wrapped/bleeding description, full-grid (v+h rules), EU number formats (`1.234,56`), and two
  tables on one page. Each fixture is committed as `<name>.pdf` + `<name>.expected.csv`
  (columns: date,description,debit,credit,amount,balance,flag).
- `app/tests/bench.py` — runs the `words` strategy over every fixture, greedily aligns rows to
  ground truth, and reports micro-F1 on `(date,debit,credit,balance)`, row recall, and the
  balance-error catch rate. Writes `docs/BENCHMARK.md`.

**Verified (ran myself, not the worker's word)**
- `python app/tests/fixtures/generate.py` regenerates all 7 fixtures with no stray output.
- `python app/tests/bench.py`: **micro-F1 0.9948** (P 0.9897 / R 1.0000), **row recall 38/38**,
  **balance catch rate 2/2 (100%)**. Writes only to `docs/BENCHMARK.md`.
- `python app/tests/test_pipeline.py` still 11/11.

**Finding surfaced by the benchmark**
- The one false positive is on `two_tables`: a section title row ("Account 2: Savings") matches
  the date-like heuristic and becomes a spurious extra row (5 predicted vs 4 truth). Multi-table
  pages are listed as future work in `docs/PLAN.md`; the benchmark now quantifies the gap.

**Cleanup**
- Removed concurrent-worker strays (`app/docs/BENCHMARK.md`, `app/samples/test_make_*.pdf`).

## 2026-09-13 — Phase 3: Plain-language README & Getting Started

**Changed**
- Rewrote `README.txt` (52 lines) and `GETTING_STARTED.txt` (58 lines) for non-technical
  accountants: what it does, one install path (run `LedgerOCR-Setup.exe`), how to process a
  document, where output lands (Downloads), scans/photos add-on, the optional error-checker,
  and the privacy/offline guarantee. Removed the old developer-oriented content.

**Verified**
- No jargon: `born-digital`, `localhost`, `pipeline`, `deterministic`, standalone `LLM` all
  absent (grep clean). No line exceeds 80 columns. Plain-text formatting (ALL-CAPS headings,
  `-` bullets).
- Facts checked against the actual app behavior (drop zone, Download CSV/XLSX buttons, in-app
  "Install OCR add-on", `OCR_LLM_MODEL` override). Model-selection wording will be revisited in
  Phase 6 when the in-app model picker lands.

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
