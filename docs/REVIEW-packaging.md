# LedgerOCR — Packaging & Luddite-Proof UX Review

Scope: read-only review of install path, model step, layperson failure modes, the
drag-drop page, `GETTING_STARTED.md`, and uninstall/data. Lens: a non-technical
accountant on a fresh Windows 10/11 machine with **no** Python, Ollama, or Tesseract.

Overall: the freeze is genuinely self-contained and the privacy story is clean
(temp-dir processing, no leftover files, fully offline UI). The two things that will
actually stop or mislead a layperson are (1) the unsigned installer vs. SmartScreen and
(2) the advertised "scan/photo" path that silently requires Tesseract, which is never
installed. Everything else is degradation-quality and polish.

---

## P1 — blocks or dead-ends a layperson

### P1-1. Unsigned installer → SmartScreen wall, no guidance. CONFIDENCE: HIGH
`installer/LedgerOCR.iss` (no `SignTool`/signing directive anywhere; `build_installer.ps1`
does no code signing). `LedgerOCR-Setup.exe`, the frozen `LedgerOCR.exe`, and the
downloaded `OllamaSetup.exe` are all unsigned.
- Scenario: the accountant double-clicks `LedgerOCR-Setup.exe` on a fresh machine and
  gets the blue "Windows protected your PC" SmartScreen dialog. The only way forward is
  "More info → Run anyway", which is deliberately hidden. Many non-technical users stop
  here or assume it's a virus.
- Neither `GETTING_STARTED.md` nor `README.md` mentions SmartScreen or the "Run anyway"
  step. For the stated luddite audience this is the single most likely install-blocker.
- Fix direction: sign the installer + exe, or add an explicit screenshot-level
  "if you see a blue warning, click More info → Run anyway" step to `GETTING_STARTED.md`.

### P1-2. "Scan/photo" is advertised but OCR (Tesseract) is never installed. CONFIDENCE: HIGH
`GETTING_STARTED.md:3` ("PDF, or a scan/photo"), `GETTING_STARTED.md` step 2.3 ("Drag a
PDF, scan, or photo"), `static/index.html:46,50` ("scan/image (PNG/JPG/TIFF)"). But no
installer path installs Tesseract — `LedgerOCR.iss` `[Run]` and `INSTALL.bat` only ever
run `install_ollama.ps1`. Tesseract is documented only in `README.md` (developer doc the
layperson never sees).
- Scenario: the accountant photographs or scans a paper statement (exactly what the docs
  invite), drops it, and `pipeline.process` returns
  `server.py`-relayed error from `ocr_pipeline/pipeline.py:62-64`:
  "This document has no text layer and Tesseract OCR is not installed. Install Tesseract
  (see README)…". There is no README on their machine and they don't know what Tesseract
  is. The core advertised path is a dead end with an unactionable message.
- Fix direction: either bundle/optionally-install Tesseract the same way Ollama is
  offered, or stop advertising scans/photos to the packaged audience and say plainly
  "born-digital PDFs only in this version".

---

## P2 — confusing or degraded for a layperson

### P2-1. Enabling the LLM checkbox when it's unavailable does nothing, silently. CONFIDENCE: HIGH
`static/index.html:56` (checkbox always enabled), `:116` (summary chip only rendered when
`s.llm && s.llm.enabled`). `validate_flagged` returns `{"enabled": False, …}` when Ollama
is down (`ocr_pipeline/validate.py:74-75`).
- Scenario: badge shows "LLM: off" (`index.html:78`) but the checkbox is still tickable.
  The user ticks "Error-check with local LLM", runs a file, and sees no LLM column and no
  explanation. They can't tell whether it ran, found nothing, or was skipped.
- Fix direction: when `llm_available` is false, disable the checkbox with a tooltip; and
  when a run had the box ticked but LLM was skipped, show a chip like "error-check
  skipped — checker not installed".

### P2-2. Encrypted/corrupt PDF surfaces a raw exception string. CONFIDENCE: MEDIUM-HIGH
`server.py:101-102` catches everything and returns `f"{type(e).__name__}: {e}"`; the UI
prints it verbatim (`index.html:102`).
- Scenario: a password-protected bank statement (common) yields something like
  "PdfminerException: …" / "PDFPasswordIncorrect: …" in red. Not a crash, but not
  plain-English either — the layperson can't tell it just needs the password removed.
- Fix direction: detect the encrypted/parse cases and map to "This PDF is
  password-protected — remove the password and try again."

### P2-3. No real progress indication; long OCR/LLM runs look frozen. CONFIDENCE: HIGH
`index.html:96` sets a static "Processing <file> …" and never updates. No spinner, no
percentage, no per-page count. OCR at 300 dpi (`extract.py:107-113`) over a multi-page
scan plus a cold LLM load (~60s, `validate.py:47-52`) can run for minutes.
- Scenario: the user drops a big file, sees a frozen line, assumes it hung, closes the
  window or re-drops repeatedly.
- Fix direction: at minimum an animated spinner + "this can take a minute for scans";
  ideally stream progress.

### P2-4. INSTALL.bat delivery has no uninstall path at all. CONFIDENCE: HIGH
`INSTALL.bat` copies to `%LOCALAPPDATA%\Programs\LedgerOCR` and creates shortcuts
(`:26-33`) but writes no uninstaller and no Add/Remove Programs entry. The Inno path has
a proper uninstaller (`LedgerOCR.iss:41`), but the fallback-folder path leaves the user
with no supported way to remove the app except manually deleting a folder and two
shortcuts they'd have to know to find.
- Fix direction: have `INSTALL.bat` drop an `UNINSTALL.bat` (or register an uninstall
  string) alongside the copied app.

### P2-5. Uninstalling LedgerOCR leaves Ollama + the ~2 GB model behind. CONFIDENCE: HIGH
The optional step installs Ollama as a separate product and pulls a model into
`%USERPROFILE%\.ollama` (`install_ollama.ps1:28-50`). Neither the Inno uninstaller nor
INSTALL.bat removes any of it.
- Scenario: the accountant uninstalls LedgerOCR to "clean up" and silently keeps a
  multi-GB Ollama install + model with no hint it exists or how to remove it.
- Fix direction: note it in the uninstall/finishing docs, or offer to remove the model.

### P2-6. Inno error-checker runs synchronously during setup and can look hung. CONFIDENCE: MEDIUM-HIGH
`LedgerOCR.iss:46-47` runs `install_ollama.ps1` with `waituntilterminated` and a single
static `StatusMsg`. This task is **checked by default** (`:36`) and downloads Ollama +
pulls ~2 GB.
- Scenario: on a slow/metered connection the wizard sits on "Setting up the smart
  error-checker…" for many minutes with no progress bar. A layperson may force-close the
  installer mid-pull. (The app files are copied before `[Run]`, so the app still works —
  but the experience reads as a hang, and the 2 GB default-on download may be unwanted.)
- Fix direction: default the task off, or make it non-blocking/background with clear
  "you can keep using the app while this finishes" messaging.

---

## P3 — polish

- **P3-1. README default model is stale/contradictory. CONFIDENCE: HIGH.**
  `README.md` ("Use from Python") says `llm_model` default `qwen3.8:latest`, but
  `validate.py:14` uses `qwen2.5:3b` and `install_ollama.ps1:9` pulls `qwen2.5:3b`.
  Developer-facing only, but confusing.
- **P3-2. Port 8765 fallback vs. the doc. CONFIDENCE: HIGH.** `run_app.py:14-17` correctly
  falls back to a random free port if 8765 is taken (good), and the console prints the
  real URL (`server.py:121`). But `GETTING_STARTED.md`'s troubleshooting tells the user to
  type `http://127.0.0.1:8765`, which is wrong after a fallback. Point them at the URL
  printed in the small window instead.
- **P3-3. Generic exe/shortcut icon. CONFIDENCE: HIGH.** `LedgerOCR.spec:37` sets
  `icon=None`, so the Desktop/Start-menu shortcuts and Uninstall entry get the default
  icon — less trustworthy-looking for a shipped product.
- **P3-4. Console window is closable/alarming. CONFIDENCE: MEDIUM.** `console=True`
  (`spec:36`) shows a black window. It's explained in `GETTING_STARTED.md`, but a layperson
  may close it (killing the server) or be spooked. Acceptable given the explanation.
- **P3-5. Multi-file drop silently ignores extras. CONFIDENCE: HIGH.** `index.html:85`
  uses `files[0]` only; dropping several statements processes just the first with no
  notice.
- **P3-6. Big-but-under-40 MB scan has no page/time guard. CONFIDENCE: MEDIUM.** `server.py:35`
  caps at 40 MB, but a 39 MB multi-page scan triggers unbounded 300-dpi OCR with no
  timeout — compounds P2-3.

---

## Things that are done well (no action)
- Frozen app is self-contained: `LedgerOCR.spec:10-17` `collect_all` for pdfplumber /
  pypdfium2 / pdfminer / openpyxl / pytesseract / PIL, `datas=[("static","static")]`,
  `_base_dir()` reads `sys._MEIPASS` (`server.py:28-34`). No system Python needed.
- Ollama step is genuinely optional and non-fatal: `install_ollama.ps1` exits 0 on every
  failure path (`:34,44,55`); `pipeline.process` produces the same spreadsheet with LLM
  off; download failure degrades cleanly.
- Privacy/temp handling: uploads processed in `tempfile.TemporaryDirectory()`
  (`server.py:80`) and auto-deleted; results returned as in-memory base64; no financial
  data persisted.
- Offline: `static/index.html` is fully inline CSS/JS with no CDN/external fetches — works
  with no internet. XLSX/CSV download via Blob + `a.download` works offline; flagged rows
  clearly highlighted (`tr.flagged`, `index.html:37,128`).
- Oversized upload gives a plain-English message ("empty or too-large upload (max 40MB)",
  `server.py:77`); unsupported type is clear too (`:74`).
- Per-user install, no admin prompt (`LedgerOCR.iss:15`), Desktop + Start-menu shortcuts
  and postinstall launch in both delivery forms.
