# Architecture (current state only)

**Goal:** drop any document in, get a ledger table (CSV/XLSX/DOCX, suspect rows flagged) or, when there is no
table, its plain text. Fully offline: no network call anywhere in `ledger_ocr/`.

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
   positions carry across pages. `.xlsx/.xlsm/.docx` become cell grids.
2. **tables.py** - engine-agnostic. Finds the header row by keyword synonyms, turns header x-centres into column
   bounds, assigns words to columns, pulls leaked description tokens out of money cells, merges wrapped
   description lines, carries column bounds to continuation pages.
3. **reconcile.py** - money to `Decimal` (US/EU formats, negatives, DR/CR; OCR digit look-alikes `o/O/l/I/|` are
   mapped only inside otherwise-numeric tokens; a letter inside a number rejects the cell rather than inventing a
   value). Votes on the debit sign convention, then flags rows whose running balance does not follow.
4. **pipeline.py** - orchestration. With `engine="auto"` and several engines present, the balance check is the
   judge: engines are tried in turn until one yields rows that all reconcile; otherwise most verified rows wins
   (tie: fewest unparseable money cells). No rows -> text output, never an empty CSV.
5. **export.py** - CSV (stdlib, BOM for Excel), XLSX (flagged rows highlighted), DOCX table / DOCX text.
6. **cli.py** - the only entry point today: `run-ledger-ocr`, `python -m ledger_ocr`. `--json` for callers,
   `--health` for diagnostics.

## Directory map

| path | what |
|---|---|
| `ledger_ocr/` | the product (flat); `CONTEXT.md` is its index |
| `test/` | pytest; mirrors `ledger_ocr/`; `conftest.py` isolates state; `fixtures/` = synthetic PDFs + expected CSVs (`generate.py`, `make_sample.py` rebuild them) |
| `bench/bench.py` | engines x fixtures micro-F1 table (clean scan, rough scan, real private documents). Prints; writes nothing |
| `run-ledger-ocr.cmd` | launcher (uses `.venv` when present) |

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

Local UI (thin layer over `pipeline.process`), installer, local-model row checker (part 2; may flag, never edit),
handling of 90-degree-rotated images without EXIF, multi-table pages.
