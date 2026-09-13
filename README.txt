====================================================================
 OCR-Pipeline  —  Statement to Spreadsheet
====================================================================

Local, privacy-first document-to-data for accountants. Drag in a bank
statement / general-ledger PDF (or a scan/image) and get back a clean
CSV / XLSX. Everything runs on your machine — no cloud OCR, no cloud
LLM. See docs/PLAN.md for the architecture and the research behind the
design choices.

  * Deterministic first. Born-digital PDFs are parsed by exact
    text/table extraction.
  * OCR only for scans. Images / scanned PDFs use local Tesseract;
    born-digital PDFs never do.
  * Running-balance reconciliation. Flags rows where
    previous +/- amount does not equal balance.
  * Optional local LLM error-check. A local Ollama model classifies
    flagged rows only. It never creates or edits numbers, and the
    pipeline works fully without it.


--------------------------------------------------------------------
 FOR NON-TECHNICAL USERS (packaged installer)
--------------------------------------------------------------------

No Python, no terminal. See GETTING_STARTED.txt. Either double-click
LedgerOCR-Setup.exe, or, with the fallback folder, double-click
INSTALL.bat. It sets everything up (bundled runtime, shortcuts,
optional error-check model) and opens the app.

To build that installer from source (needs "pip install pyinstaller"
and Inno Setup 6):

    powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
    (produces installer\Output\LedgerOCR-Setup.exe, and
     installer\dist\LedgerOCR\ for the INSTALL.bat fallback)


--------------------------------------------------------------------
 RUN FROM SOURCE (developers)
--------------------------------------------------------------------

Requires Python 3.12+ (Node not needed).

    pip install -r app
equirements.txt -c app\constraints.txt

constraints.txt pins the exact tested versions (including transitive
deps) for a reproducible install; drop the "-c" flag only if you
deliberately want the latest.

Core deps: pdfplumber, openpyxl.  Optional: pytesseract + requests.

Optional: OCR for scans/images
------------------------------
Install the Tesseract binary (the Python package alone is not enough):

    winget install UB-Mannheim.TesseractOCR
    (or download the installer:
     https://github.com/UB-Mannheim/tesseract/wiki )

The app auto-detects Tesseract at
C:\Program Files\Tesseract-OCR\tesseract.exe (and a few other common
spots). If yours is elsewhere, set the OCR_TESSERACT environment
variable to the full path to tesseract.exe. Born-digital PDFs do NOT
require Tesseract.

Optional: local LLM error-checking
----------------------------------
Needs Ollama (https://ollama.com) running locally with a model pulled.
On a RAM-constrained machine a small model is recommended:

    ollama pull qwen2.5:3b

Enable it with the checkbox in the app (or use_llm=True in code). If
Ollama is down or slow, the pipeline simply skips this step.


--------------------------------------------------------------------
 RUN THE APP
--------------------------------------------------------------------

    run.cmd  (double-click it)
    (or:  python app\server.py --port 8765 --open )

Then open http://127.0.0.1:8765 , drag a PDF/image onto the drop zone,
and download the CSV or XLSX. Flagged rows are highlighted. Runs on
localhost, no auth.


--------------------------------------------------------------------
 USE FROM PYTHON / COMMAND LINE
--------------------------------------------------------------------

    from ocr_pipeline.pipeline import process

    result = process("statement.pdf", outdir="out",
                     strategy="words", use_llm=False)
    print(result["summary"])   # rows, mismatches, sign convention, route
    # -> out/statement.csv and out/statement.xlsx

  * strategy: "words" (default, header-anchored coordinates) or
    "lines" (ruled/text tables).
  * use_llm: run the optional Ollama error-check on flagged rows.
  * llm_model: Ollama model name (default qwen2.5:3b, override with
    the OCR_LLM_MODEL environment variable).


--------------------------------------------------------------------
 OUTPUT COLUMNS
--------------------------------------------------------------------

date, description, debit, credit, amount, balance, flag,
llm_classification

"flag" explains any running-balance mismatch (e.g. "expected 8357.54,
got 8457.54"); "llm_classification" is the optional model's guess at
the cause (advisory only).


--------------------------------------------------------------------
 TEST & SAMPLE
--------------------------------------------------------------------

    python app\samples\make_sample.py   # (re)generate the synthetic sample PDF
    python app	ests	est_pipeline.py   # run tests + the A/B extraction comparison

app\samplesank_statement.pdf is a synthetic statement with one
deliberately corrupted running balance; app\samples\out\ holds the
exported CSV/XLSX. The suite also runs the A/B test (see docs/PLAN.md).


--------------------------------------------------------------------
 PROJECT LAYOUT
--------------------------------------------------------------------

    app/ocr_pipeline/  extract.py  tables.py  reconcile.py
                       validate.py  export.py  pipeline.py
    app/server.py      tiny stdlib HTTP server for the drop-and-drop app
    app/static/index.html  the drag-and-drop UI (vanilla JS)
    app/samples/       synthetic sample generator, sample PDF, outputs
    app/tests/         end-to-end tests + the A/B comparison
    installer/         PyInstaller spec + Inno Setup script + build scripts
    docs/              PLAN.md, SIGNING.txt, REVIEWs, FIXES_BACKLOG.md
