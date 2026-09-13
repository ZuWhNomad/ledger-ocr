# Improvement Log

Dated entries, newest first. Each phase of the production-readiness pass appends here.

## 2026-09-13 — Phase 7: Final verification & push

**Verified**
- Full suite: `python app/tests/test_pipeline.py` -> **18/18**. Benchmarks: born-digital
  micro-F1 **0.9948** (row recall 38/38, balance catch 2/2); OCR word-box **0.9140** vs
  text-only 0.5419.
- Source app (the `run.cmd` path, `python server.py`) launched and served over HTTP:
  `/api/env` -> ocr+llm available, model qwen2.5:3b; posting `samples/bank_statement.pdf` ->
  ok, born-digital, 15 rows, 1 balance flag, and **all three downloads (csv+xlsx+docx)** returned.
- Installer fully rebuilt: `installer/build_installer.ps1` -> PyInstaller freeze + Inno Setup ->
  `installer/Output/LedgerOCR-Setup.exe` (~36.8 MB, unsigned, git-ignored). Confirmed the fresh
  `_internal/` bundles `docx`, `requests`, `certifi` (Phase 5/6 features work when frozen).
- Frozen `LedgerOCR.exe` smoke test: `/api/env` healthy and posting the sample produced
  csv+xlsx+docx from the packaged build.
- `git status` clean of artifacts (no `.exe`/`__pycache__`/`.pyc` tracked; both Setup.exe paths
  ignored; binaries protected by `.gitattributes`).

**Pushed**
- Remote `origin` = https://github.com/ZuWhNomad/ledger-ocr.git. Fast-forward push of `main`
  (bb0a344..b6a529a, 9 commits). This Phase 7 entry is the final commit on top.

**Still needs a manual clean-VM test (cannot be simulated on this dev machine)**
- A true clean Windows box (no Python/Tesseract/Ollama/winget) install of `LedgerOCR-Setup.exe`,
  a genuine non-admin (cannot-elevate) account, and a full silent install -> uninstall cycle
  verifying the Tesseract/model/Ollama removal prompts and that no files/registry keys are orphaned.
- The installer is UNSIGNED (no cert configured), so SmartScreen will warn until it is signed
  (see docs/SIGNING.txt; build_installer.ps1 signs automatically when a cert env is set).

## 2026-09-13 — Phase 6: Local model sweep, suggestion & user selection

**Empirical validation (measured this machine, my own probe)**
- All fitting installed models emit valid classification JSON with `format=json`+`think=false`:
  qwen2.5:3b (1.9 GB, ~3.6 s), n2ft (8.1 GB, ~9 s), qwen3.8 (17.7 GB, ~35 s). qwen3.6 (~24 GB)
  does not fit ~16 GB free RAM; nomic-embed is an embedding model. **qwen2.5:3b remains the best
  default** (lowest cold-start, largest RAM headroom, valid JSON). Note: n2ft now complies with
  the schema (the old PLAN note that it ignored the schema no longer holds with format=json).

**Added (validate.py)**
- `list_installed` (excludes embedding models), `_ram_gb` (Windows ctypes / Linux /proc/meminfo),
  `probe_model` (one canned classification, checks JSON schema), pure `suggest_from`, and `sweep`
  (RAM fit + probe + suggestion). All network calls never raise -> LLM stays optional.
- Persisted user choice: `get_model()` precedence **OCR_LLM_MODEL env > config.json > default**;
  `set_model()` writes `%LOCALAPPDATA%/LedgerOCR/config.json` (test-injectable via LEDGEROCR_CONFIG).
- `check_row`/`validate_flagged` now resolve `model or get_model()`.

**Wired**
- server.py: `GET /api/models` (10-min cached sweep, `?refresh=1`), `POST /api/model` (validates
  the name is installed, persists), `/api/process` passes the chosen model, `/api/env` reports it.
- index.html: a "Choose model" button runs the sweep and shows a dropdown (each model labelled with
  size, "too large for RAM", and "suggested"); selecting one persists it and updates the badge.
- pipeline.process: `llm_model` defaults to None so EVERY entry point resolves via get_model()
  (the OCR_LLM_MODEL override now holds for direct callers too, not just the server).

**Verified (ran myself)**
- `python app/tests/test_pipeline.py` -> 18/18 (3 new: env>config precedence, set/get round-trip,
  suggest_from ranking). Live `sweep()` on this machine returns suggested `qwen2.5:3b`, qwen3.6
  `fits_ram:false`, nomic-embed excluded, qwen3.8 `json_ok:false` (slower than the 30 s probe).
  Confirmed `sweep()` returns `available:false` (no raise) when Ollama is unreachable.

**Docs**
- Updated README.txt / GETTING_STARTED.txt for the new Excel/Word inputs, DOCX output, and the
  in-app "Choose model" picker (folds in the Phase 5 documentation that was deferred here).

## 2026-09-13 — Phase 5: Accept .xlsx/.docx inputs + add DOCX output

**Inputs**
- `extract.STRUCTURED_EXTS = {.xlsx,.xlsm,.docx}` + `extract_structured(path)`: reads office
  ledgers and maps columns via the SAME `tables._table_to_records` used for PDF tables (xlsx via
  openpyxl read-only; docx tables via python-docx). xlsx date cells are formatted `%Y-%m-%d` and
  whole-number floats lose the trailing `.0` so parse_money stays exact.
- `pipeline.process` branches on extension BEFORE the PDF/scan logic (office files must not be
  opened as PDFs); route `structured`, strategy `table-xlsx` / `table-docx`. A missing python-docx
  on a .docx upload returns a clear message (not a crash).
- `server.ALLOWED_EXT` + the UI file `accept` (both branches) now include .xlsx/.xlsm/.docx.

**Output**
- `export.to_docx(rows, path)`: a clean "Transactions" table document (Table Grid, bold headers).
  Flagged rows are visibly marked — every cell shaded `F4CCCC` (matching the XLSX highlight) and
  the flag text in red. Wired into `pipeline` (guarded like xlsx: `docx_error` on failure so
  CSV/XLSX are still delivered), the server (`docx_b64`, correct MIME), and the UI (Download DOCX
  button next to CSV/XLSX).

**Dependency**
- `python-docx` added as OPTIONAL: requirements (`>=1.1`), constraints (`python-docx==1.2.0`,
  `lxml==6.0.2`), and the PyInstaller spec (`docx` in collect_all). The pdfplumber+openpyxl-only
  invariant still holds — python-docx is optional for both .docx input and .docx output.

**Verified (ran myself)**
- `python app/tests/test_pipeline.py` -> 15/15 (3 new: xlsx input end-to-end flags an injected
  error and reports route=structured; docx input round-trips a table; docx export opens and has
  the table). `python app/tests/bench.py` unchanged (0.9948). Reviewed to_docx, server, and UI
  diffs directly.

**Deferred**
- The README/Getting Started mention of Excel/Word input + DOCX output is folded into the Phase 6
  documentation pass (which also revises the model-selection section) to avoid editing the same
  lines twice.

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
