# ocr_pipeline/

Core engine for turning a bank-statement / ledger PDF or scan into structured rows.

**Entry point:** `pipeline.process(path, outdir, strategy, use_llm, llm_model)` — routes,
extracts, reconciles, optionally LLM-checks, and exports. Everything else is called from there.

**Modules**
- `extract.py` — routing (`looks_scanned`, per page), born-digital extraction dispatch, and the
  Tesseract OCR fallback (pages rasterized via pdfplumber/pypdfium2, no PyMuPDF/Poppler).
- `tables.py` — the two deterministic table strategies: `extract_words_table` (header-anchored
  word-coordinate clustering, the default) and `extract_lines_table` (pdfplumber ruled/text
  tables). Both return canonical dict rows.
- `reconcile.py` — `parse_money` (Decimal, locale-aware) and `reconcile` (sign-convention voting +
  running-balance verification, flags mismatches).
- `validate.py` — optional Ollama error-check of *flagged rows only*; non-blocking.
- `export.py` — CSV (stdlib) and XLSX (openpyxl, flags highlighted).

**Invariants**
- Deterministic extraction is primary; the LLM never produces or edits numbers, only classifies.
- The pipeline must run with only `pdfplumber` + `openpyxl` present (OCR and LLM are optional).
- Money is always `Decimal`, never float.

**Test:** `python tests/test_pipeline.py` (from repo root) — end-to-end + the A/B comparison.
