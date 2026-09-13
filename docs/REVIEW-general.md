# OCR-Pipeline — General Correctness, Design & Maintainability Review

Lens: general correctness / design / maintainability. Read-only. Privacy/network and
table/money-extraction correctness are covered by separate lenses and are deferred to here.

Overall this is a clean, well-scoped codebase: the module split (extract / tables / reconcile /
validate / export / pipeline) is sound, the "deterministic-first, LLM-never-edits-numbers"
invariant is respected, and the dependency choices are deliberate and well-justified in PLAN.md.
The findings below are mostly edge cases, a couple of real logic bugs, dead code, and doc drift.

---

## P2 — real bugs / notable design gaps

### P2-1. Single signed-amount-column statements never reconcile (sign vote always ties)
`reconcile.py:87-94` + `:126-129`. CONFIDENCE: HIGH (confirmed by reading).
For a row that has only an `amount` (no debit/credit), `_delta` returns `a` **ignoring `sign`**
(line 90-91). So on a statement whose only money column is a single signed amount,
`_fit_score(rows, +1)` and `_fit_score(rows, -1)` compute identical deltas and therefore
identical scores → `v_pos == v_neg` → `sign = 0` → `convention = "unknown"` → the whole
running-balance check is skipped (the `if sign != 0:` guard at line 135).
Scenario: an amount-only ledger that reconciles perfectly is reported as `sign_convention:
"unknown"` and gets **zero** balance verification — the tool silently does no checking on exactly
the shape PLAN.md lists as a target fixture ("single signed-amount column"). Fix direction: when
every balance-bearing row is amount-only, sign is irrelevant — pick a sign and reconcile instead
of declaring unknown.

### P2-2. `validate_flagged` max_rows does not bound work when the model fails/times out
`validate.py:77-83`. CONFIDENCE: HIGH.
`checked` is incremented **only on success** (`if res is not None`), but the loop guard is
`checked < max_rows`. If the model returns None for every row (Ollama died mid-batch, JSON parse
fails, or each call hits the 120 s timeout), `checked` stays 0 and **every** flagged row is
attempted. On a document with, say, 80 flagged rows and a model that cold-loads or times out, this
serially issues up to 80 × 120 s requests. `available()` is only checked once up front, so a
mid-batch Ollama crash isn't re-detected. The cap should bound *attempts*, not *successes*.

### P2-3. XLSX amounts are written as text, not numbers
`export.py:34-52` (values come from the original strings via `_flat`). CONFIDENCE: HIGH (design).
`to_xlsx` appends the raw string cells (`"84.19"`, `"1,234.56"`, `"(84.19)"`). Excel renders these
as "number stored as text": they don't sum, sort numerically, or feed formulas without manual
conversion — a sharp edge for the accountant audience the tool targets. The parsed `Decimal`
values (`_debit`/`_credit`/`_balance`/`_amount`) already exist on each row and could be written as
real numeric cells. (The specific *value* correctness of those Decimals is the extraction lens's
call; this finding is only about the text-vs-number cell type in the export.)

### P2-4. No-header pages produce silent misextraction, not an empty/flagged result
`tables.py:63-76`, `extract_words_table:100-104`. CONFIDENCE: MEDIUM. Acknowledged in PLAN.md
("page-2 with no header" / repeated headers not special-cased).
`_find_header` picks the highest-scoring row as the header even on a continuation page that has no
header at all — a data row whose description contains a synonym (`DEPOSIT`→credit, `PAYMENT`/
`CHARGE`→debit, `REFERENCE`→description) can score ≥2 and be crowned the header, after which
column bounds are wrong and every subsequent row is mis-binned. The failure is silent (wrong
numbers out), which is worse than an empty result. Worth a guard (e.g. require `date` + a money
synonym, or detect "no plausible header" and skip the page) even though it's listed as future work.

---

## P3 — clarity, dead code, doc drift, minor robustness

### P3-1. Dead code in `parse_money`
`reconcile.py:47-49`. CONFIDENCE: HIGH.
- `t.replace(",", ",")` is a no-op (comma → comma), almost certainly a leftover typo.
- The `re.sub(r"[^\d.,\-]", "", ...)` on line 47 already strips every currency symbol, so the
  `for ch in _CURRENCY: t = t.replace(ch, "")` loop on lines 48-49 can never do anything.
Both are confusing to a future maintainer. Behavior is correct; the code is just misleading.

### P3-2. Invalid `strategy` silently runs "lines" but is reported as the user's string
`extract.py:51` (`fn = ... if strategy == "words" else T.extract_lines_table`) +
`pipeline.py:78`. CONFIDENCE: HIGH.
Any strategy value other than exactly `"words"` falls through to the lines extractor. The server
accepts an arbitrary `?strategy=` query param (`server.py:69`), so `?strategy=word` (typo) runs
`lines` while `summary["strategy"]` reports `"word"` — a mislabel. A whitelist + explicit error (or
at least reporting the strategy actually used) would be clearer.

### P3-3. Doc/code disagreement on default LLM model
`validate.py:14` defaults to `qwen2.5:3b` (via `OCR_LLM_MODEL`), but `README.md:85` and the
PLAN.md library table say the default is `qwen3.8:latest`. CONFIDENCE: HIGH. One of them is stale.

### P3-4. Stale docstrings in `extract.py`
`extract.py:4-9`. CONFIDENCE: HIGH.
- Line 4 claims a "PyMuPDF fallback" — there is no PyMuPDF anywhere (PLAN.md explicitly rejects it).
- Lines 8-9 describe scan detection as "average extractable text per page below a threshold," but
  `looks_scanned` (line 42) uses **`max(counts) < THRESHOLD`** (per-page max). The docstring
  contradicts both the code and PLAN.md's own per-page description.

### P3-5. `validate.py` docstring promises a path that never runs
`validate.py:3-6` says garbled-looking OCR rows are sent to the model, but `pipeline.py:81` only
invokes the LLM when `summary["balance_mismatches"]` is set, and flags come exclusively from
balance reconciliation. There is no "garbled OCR" flag path. CONFIDENCE: HIGH. Doc overstates scope.

### P3-6. Duplicated row-flattening logic
`server.py:105-113` (`_slim`) and `export.py:9-23` (`_flat`) are two near-identical projections of
the same canonical row (date/description/debit/credit/amount/balance/flag/llm). CONFIDENCE: HIGH.
They will drift. One shared helper (e.g. in export or a small `rows` module) would do.

### P3-7. `_flat(rows)` recomputed many times in `to_xlsx`
`export.py:50-51`. CONFIDENCE: HIGH. The column-width loop calls `_flat(rows)` once per column in
`max(...)` *and* again inside the generator — ~2×len(COLUMNS) rebuilds of the whole flattened list
per export, plus the one at line 44. Compute `flat = _flat(rows)` once and reuse. Minor perf/clarity.

### P3-8. Born-digital PDF is opened and parsed twice
`extract.py:26-29` (`pdf_page_char_counts` for routing) then `:54-56`
(`extract_tables_born_digital`) each open and iterate the whole PDF. CONFIDENCE: HIGH. For large
PDFs the routing pass (`extract_text()` per page) is redundant work; the char counts could be
reused. Minor.

### P3-9. Server returns HTTP 200 on internal failure
`server.py:101-102` (and the `not ok` branch at :85-86) send `{"ok": false, ...}` with status 200.
CONFIDENCE: HIGH. The frontend keys off `d.ok` so it works, but 200-for-errors is semantically
wrong and would surprise any other client/tooling. Minor.

### P3-10. `Content-Length` parsed outside the try/except
`server.py:75` does `int(self.headers.get("Content-Length", 0))` before the `try` at line 79. A
non-integer header raises an unhandled `ValueError`. CONFIDENCE: MEDIUM (low real-world risk;
browsers always send a valid length). Edge robustness only.

### P3-11. OCR text parser can't read amounts without decimals
`pipeline.py:21` `_MONEY_TOKEN` requires either `.\d{2}` or a thousands separator. A whole-dollar
OCR amount like `1200` (no decimals, no comma) isn't recognized, so that line yields no money.
CONFIDENCE: MEDIUM. Affects the scanned/OCR fallback path only.

### P3-12. `parse_text_rows` belongs with the extractors, not the orchestrator
`pipeline.py:24-49`. CONFIDENCE: MEDIUM (design taste). The OCR text→rows parser is an extraction
strategy living in the orchestration module; `extract.py`/`tables.py` would be a more natural home
and would keep `pipeline.py` purely about wiring stages together.

### P3-13. Hard-coded personal Python path committed in `run.ps1`
`run.ps1:4` pins `C:\Users\m.DESKTOP-T2DPGBS.000\AppData\...\python.exe`. CONFIDENCE: HIGH. It
falls back to `python` if absent, so it's not broken, but a specific developer's absolute home path
is checked into the repo — noise for other contributors.

### P3-14. LLM failures are swallowed with no diagnostic
`validate.py:67-68` catches every exception and returns None; the summary reports only a `checked`
count, never a failure count or reason. CONFIDENCE: HIGH. Non-blocking is the right design, but a
maintainer debugging "the LLM never annotates anything" has zero signal. A failure tally in the
summary would help.

### P3-15. `chr(64 + i)` column addressing caps at 26 columns
`export.py:51`. CONFIDENCE: HIGH (latent, not currently triggered — 8 columns). If COLUMNS ever
exceeds 26, `chr(64+27)` yields `'['`, not `'AA'`. Use `openpyxl.utils.get_column_letter`.

### P3-16. `Image.open` not closed in image OCR path
`extract.py:107`. CONFIDENCE: MEDIUM. `pytesseract.image_to_string(Image.open(path))` leaves the
PIL image/file handle to GC. Harmless in the short-lived request but not tidy; a `with` would fix.

---

## Test coverage assessment

Tested well: `parse_money` edge cases, the words-strategy happy path + single injected flag, the
A/B fidelity comparison, one sign-autodetect direction (debit-raises), and the OCR text-line parser
in isolation. Deterministic, no-network, runnable without pytest — good.

Biggest untested / risky gaps, ranked by value:
1. **Single signed-amount-column reconcile** — would immediately expose **P2-1**. Highest value.
2. **No-header / page-2 continuation extraction** — would expose the silent misextraction in
   **P2-4**.
3. **Server request handling** (`server.py`) — entirely untested: extension whitelist, size limit,
   base64 round-trip, the 200-on-error contract. Pure-stdlib, easily testable with a local request.
4. **Export content** (`export.py`) — CSV/XLSX are never asserted; the text-vs-number issue
   (**P2-3**) has no test.
5. **`validate.py`** — untestable as written without Ollama, but `check_row`/`validate_flagged`
   could be tested against a mocked `requests` to lock in the non-blocking contract and would catch
   **P2-2** (the max_rows-doesn't-bound-attempts bug).
6. **OCR routing** (`looks_scanned` per-page max, hybrid PDF) — the routing decision is untested;
   char counts could be stubbed without a real scan.
7. Wrapped-description merge, EU number formats end-to-end, multi-table pages.

Of PLAN.md's 10 proposed fixtures, the two that pay for themselves first are **single
signed-amount column** and **page-2 with no header**, because each turns a currently-silent bug
(P2-1, P2-4) into a visible failure.

---

## Config & robustness summary

- `OCR_LLM_MODEL` (validate.py) and `OCR_TESSERACT` (extract.py) env overrides: good, documented.
- Port is configurable via `--port`; `run_app.py` degrades from 8765 to a free port sensibly.
- Hard-coded but reasonable module constants: `SCAN_CHARS_PER_PAGE=40`, `TOL=0.02`, `MAX_BYTES=40MB`,
  OCR `dpi=300`. The dpi is the only one a scan-quality edge case might want to tune; not urgent.
- The committed personal Python path (P3-13) is the one config wart worth removing.

## Architecture summary

The stage split is clean and the extractor strategy dispatch is appropriately simple for two
strategies (a plugin registry would be over-engineering today). The two things worth tidying are
the duplicated flatten logic (P3-6) and moving `parse_text_rows` in with the other extractors
(P3-12). No tangled coupling or leaks found: pdfplumber handles and the temp dir are all
`with`-scoped; the Ollama client is stateless `requests`.
