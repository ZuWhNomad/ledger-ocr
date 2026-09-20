# ledger_ocr/

Purpose: any file -> ledger rows (flagged) or text, offline. Entry: `cli.main`, `pipeline.process(path, outdir, mode, engine)`.

Invariants: no network; numbers only from deterministic extraction, `Decimal` never float; `tables`/`reconcile`
never know which engine produced the words; unreadable money cell -> `None`, never a guess; no rows -> text.

Test: `pytest` (OCR tests run once per installed engine). Accuracy: `python bench/bench.py`.

| symptom | file |
|---|---|
| photo upside-down / skewed / tiny text; engine missing; PDF page wrongly OCR'd | `readers.py` |
| columns mixed up, header not found, description in amount, page 2 rows missing | `tables.py` |
| amount parsed wrong, false/missed balance flag, sign convention | `reconcile.py` |
| wrong engine chosen in auto, text vs table decision, error messages | `pipeline.py` |
| output file format, highlighting | `export.py` |
| flags, exit codes, `--health`, `--ui` | `cli.py` |
| page does not load, upload rejected, 403, download buttons | `server.py`, `static/index.html` |
