# Architecture (current state only)

**Goal:** drop any document in, get a ledger table (CSV/XLSX/DOCX, suspect rows flagged) or, when there is no
table, its plain text. Offline: no document data ever leaves the machine. The only network call in the
package is `update.py` (below).

## How it works

```
file -> readers -> pages of word boxes -> tables -> rows -> reconcile -> export
        (per page: PDF text layer,        (header-      (Decimal money, sign
         else OCR; office files -> grids)  anchored)     vote, running balance)
```

1. **readers.py** - per PDF page: a real text layer is read exactly (pdfplumber); otherwise the page is rendered
   at 300 dpi and OCR'd. Images go straight to OCR. Every image is EXIF-transposed once. After the first OCR pass
   the page's skew and text height are measured from the word boxes; a leaning (> 0.3 deg) or small-text (< 20 px)
   page is levelled / enlarged and read once more. OCR'd PDF pages are scaled back to PDF points so column
   positions carry across pages. `.xlsx/.xlsm/.docx` become cell grids. Text-layer words use a gap tolerance
   relative to type size (spreadsheet exports leave cells ~0.35 em apart with no space glyph); words that touch
   exactly are re-joined (a stray space glyph drawn over a digit splits `233.10`).
2. **tables.py** - engine-agnostic. Ledger: finds the header row by keyword synonyms (one-space phrases such as
   `Funds Out` / `CR Amount` are one header), turns header x-centres into column bounds, then moves each text
   column's left edge to where its data starts (a vote over word x0; centred headers sit right of left-aligned
   text). Text words are placed by x0, money words by "rightmost money header starting before the number ends"
   (right-aligned numbers under left-aligned or centred headers). A phrase one space long stays in one column
   (long GL account names; descriptions running into the money area); non-date words in the date cell move to
   the next column (right-aligned dates). Pulls leaked description tokens out of money cells, merges wrapped
   description lines, carries column bounds to continuation pages. Columns: date, description, debit, credit,
   amount, balance, plus `type`/`num` (QuickBooks GL) and `account` (expense lists). Any other table
   (`grid_from_words`): columns are the vertical white gaps shared by the rows. Forms/receipts
   (`pairs_from_text`): `Label: value` lines.
3. **reconcile.py** - money to `Decimal` (US/EU formats, negatives, DR/CR; OCR digit look-alikes `o/O/l/I/|` are
   mapped only inside otherwise-numeric tokens; a letter inside a number, or a whole word such as a `Page 2`
   footer, rejects the cell rather than inventing a value). Votes on the debit sign convention, then flags rows
   whose running balance does not follow. General ledgers: a dateless row with a balance and empty movement cells
   (an account's opening line) restarts the running balance; `Total ...` rows are skipped.
4. **pipeline.py** - orchestration. With `engine="auto"` and several engines present, the balance check is the
   judge: engines are tried in turn until one yields rows that all reconcile; otherwise most verified rows wins
   (tie: fewest unparseable money cells). Document shape, in order: `ledger` (balances checked) -> `table`
   (generic grid, then label/value pairs; CSV/XLSX, no balance check) -> `text`. Never an empty CSV.
5. **export.py** - CSV (stdlib, BOM for Excel), XLSX (flagged rows highlighted), DOCX table / DOCX text.
   `type`/`num`/`account` columns appear only when the document has them.
6. **cli.py** - the entry point: `run-ledger-ocr FILE...` (`--json` for callers, `--health` for diagnostics);
   with no files, or `--ui`, it starts **server.py** and opens the browser.
7. **server.py + static/index.html** - the drag-and-drop page. Loopback only, Host header checked, one
   `POST /api/process` per file (bytes in, `pipeline.process` result + base64 output files out), temp folder
   deleted per request. No state on the server.
8. **update.py** - one anonymous GET to the GitHub releases API at launch, in a background thread, to ask
   whether a newer version exists; the UI then shows a download link. Sends nothing, never raises, skipped by
   `LEDGEROCR_NO_UPDATE_CHECK`. Version truth is `ledger_ocr.__version__`, which `pyproject.toml` reads.
9. **installer/** - `LedgerOCR.exe` (PyInstaller; the exe *is* the CLI, no args = the page) and
   `LedgerOCR-Setup.exe` (Inno Setup, per user). See `installer/CONTEXT.md`.

## Directory map

| path | what |
|---|---|
| `ledger_ocr/` | the product (flat); `CONTEXT.md` is its index |
| `test/` | pytest; mirrors `ledger_ocr/`; `conftest.py` isolates state; `fixtures/` = synthetic PDFs + expected CSVs (`generate.py`, `make_sample.py` rebuild them) |
| `bench/bench.py` | engines x fixtures micro-F1 table (clean scan, rough scan, real private documents). Prints; writes nothing |
| `run-ledger-ocr.cmd` | launcher (uses `.venv` when present) |
| `installer/` | freeze + Setup.exe build; outputs (`dist/`, `build/`, `Output/`) are git-ignored |

## External programs

| program | needed for | detect | get it |
|---|---|---|---|
| Windows 10/11 OCR (`Windows.Media.Ocr`) | scans/photos (primary) | `run-ledger-ocr --health` -> `ocr_engines` has `winocr` | built in; languages: Settings > Time & Language > Language |
| Tesseract 5 (optional) | second OCR opinion | `--health` -> `tesseract` path; env `OCR_TESSERACT` overrides | https://github.com/UB-Mannheim/tesseract/wiki |

## State, config, environment

No persistent state yet. When there is, it goes in `%LOCALAPPDATA%\LedgerOCR`, overridable by `LEDGEROCR_STATE`
(tests already point it at a temp folder). `LEDGEROCR_PRIVATE_FIXTURES` names a folder of real documents
(+ optional `<name>.expected.csv`) used by one smoke test and by the bench; it is never inside the repo.

## Not built yet

Local-model row checker (part 2; may flag, never edit), handling of 90-degree-rotated images without EXIF,
multi-table pages, code signing (SmartScreen warns on unsigned builds).
