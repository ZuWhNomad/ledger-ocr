# OCR-Pipeline

Local, privacy-first document-to-data for accountants. Drag in a **bank statement / general-ledger
PDF** (or a scan/image) and get back a clean **CSV / XLSX**. Everything runs on your machine —
no cloud OCR, no cloud LLM. See [`PLAN.md`](PLAN.md) for the architecture and the research behind
the design choices.

- **Deterministic first.** Born-digital PDFs are parsed by exact text/table extraction.
- **OCR only for scans.** Images / scanned PDFs use local Tesseract; born-digital PDFs never do.
- **Running-balance reconciliation.** Flags rows where `previous ± amount ≠ balance`.
- **Optional local LLM error-check.** A local Ollama model classifies *flagged* rows only. It
  never creates or edits numbers, and the pipeline works fully without it.

## For non-technical users (packaged installer)

No Python, no terminal. See [`GETTING_STARTED.md`](GETTING_STARTED.md). Either double-click
**`LedgerOCR-Setup.exe`**, or, with the fallback folder, double-click **`INSTALL.bat`**. It sets
everything up (bundled runtime, shortcuts, optional error-check model) and opens the app.

To build that installer from source (needs `pip install pyinstaller` and Inno Setup 6):

```powershell
powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
# -> installer\Output\LedgerOCR-Setup.exe   (and installer\dist\LedgerOCR\ for the INSTALL.bat fallback)
```

## Run from source (developers)

Requires Python 3.12+ (Node not needed).

```powershell
pip install -r requirements.txt -c constraints.txt
```

`constraints.txt` pins the exact tested versions (including transitive deps) for a
reproducible install; drop the `-c` flag only if you deliberately want the latest.

Core deps: `pdfplumber`, `openpyxl`. Optional: `pytesseract` + `requests`.

### Optional: OCR for scans/images

Install the Tesseract binary (Python package alone is not enough):

```powershell
winget install UB-Mannheim.TesseractOCR
# or download the installer: https://github.com/UB-Mannheim/tesseract/wiki
```

The app auto-detects Tesseract at `C:\Program Files\Tesseract-OCR\tesseract.exe` (and a few other
common spots). If yours is elsewhere, set `OCR_TESSERACT` to the full path to `tesseract.exe`.
Born-digital PDFs do **not** require Tesseract.

### Optional: local LLM error-checking

Needs [Ollama](https://ollama.com) running locally with a model pulled. On a RAM-constrained
machine a small model is recommended:

```powershell
ollama pull qwen2.5:3b
```

Enable it with the checkbox in the app (or `use_llm=True` in code). If Ollama is down or slow, the
pipeline simply skips this step.

## Run the app

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
# or:
python server.py --port 8765 --open
```

Then open <http://127.0.0.1:8765>, drag a PDF/image onto the drop zone, and download the CSV or
XLSX. Flagged rows are highlighted. Runs on localhost, no auth.

## Use from Python / command line

```python
from ocr_pipeline.pipeline import process

result = process("statement.pdf", outdir="out", strategy="words", use_llm=False)
print(result["summary"])          # rows, mismatches, sign convention, route
# -> out/statement.csv and out/statement.xlsx
```

- `strategy`: `"words"` (default, header-anchored coordinates) or `"lines"` (ruled/text tables).
- `use_llm`: run the optional Ollama error-check on flagged rows.
- `llm_model`: Ollama model name (default `qwen2.5:3b`, override with `OCR_LLM_MODEL`).

## Output columns

`date, description, debit, credit, amount, balance, flag, llm_classification`

`flag` explains any running-balance mismatch (e.g. `expected 8357.54, got 8457.54`);
`llm_classification` is the optional model's guess at the cause (advisory only).

## Test & sample

```powershell
python samples/make_sample.py     # (re)generate the synthetic sample PDF
python tests/test_pipeline.py     # run tests + the A/B extraction comparison
```

`samples/bank_statement.pdf` is a synthetic statement with one deliberately corrupted running
balance; `samples/out/` holds the exported CSV/XLSX. The suite also runs the A/B test (see
[`PLAN.md`](PLAN.md#ab-extraction-test-recorded)).

## Project layout

```
ocr_pipeline/      extract.py  tables.py  reconcile.py  validate.py  export.py  pipeline.py
server.py          tiny stdlib HTTP server for the drag-and-drop app
static/index.html  the drag-and-drop UI (vanilla JS)
samples/           synthetic sample generator, sample PDF, exported outputs
tests/             end-to-end tests + the A/B comparison
```
