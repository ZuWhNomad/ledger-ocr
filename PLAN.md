# OCR-Pipeline — Architecture & Plan

A local, privacy-first tool that turns an accountant's **bank statement / general-ledger PDF**
(or a scan/image) into a clean **CSV/XLSX**. Financial data never leaves the machine: no cloud
OCR, no cloud LLM. Deterministic extraction first; a local LLM is used *only* to flag suspect
rows, never to produce or "fix" the numbers.

## Pipeline

```
file ──► route ──► extract ──► reconcile ──► (optional) LLM error-check ──► export
          │           │            │                                          │
   born-digital?   pdfplumber   running-balance                          CSV + XLSX
   vs scanned      word coords   verification                         (flags highlighted)
   (per page)      or OCR text   + sign auto-detect
```

1. **Route** (`extract.looks_scanned`) — per page, not on the document average: a PDF is
   treated as scanned only when *no* page carries a real text layer, so a hybrid PDF (text
   letterhead + one born-digital table page) still routes to deterministic extraction. Images
   always go to OCR.
2. **Extract** — born-digital: `pdfplumber` word coordinates (default) or its ruled/text table
   detector (fallback). Scanned: local Tesseract, with the page rasterized by pdfplumber's own
   renderer. If born-digital extraction yields **zero** rows and OCR is available, it falls back
   to OCR automatically.
3. **Reconcile** (`reconcile`) — parse money to `Decimal`, auto-detect the debit sign convention
   by voting on consecutive printed balances, then verify a running balance and flag mismatches.
4. **LLM error-check** (`validate`, optional) — only *flagged* rows go to a local Ollama model,
   which classifies the likely cause. It is never allowed to change a number.
5. **Export** (`export`) — CSV via the stdlib; XLSX via openpyxl with flagged rows highlighted.

## Research synthesis (Gemini 3.1 Pro + Grok 4.6, via Conductor)

Two models researched the deterministic approach; Gemini's findings were fed into Grok, which
then verified them against this actual machine and repo. Where they disagreed, Grok's
machine-checked position won.

**Agreed (and adopted):**
- **`pdfplumber` is the default extractor.** Pure Python, deterministic coordinate access, zero
  Windows install friction. **Camelot** (needs Ghostscript) and **tabula-py** (needs Java) were
  rejected — install friction and no benefit here.
- **OCR only for scans**, detected by an absent text layer; a small local LLM is used **only to
  validate flagged rows**, wrapped so a missing/slow model never blocks the pipeline.
- **Column detection by word x-coordinates, no ML.** Cluster words into rows by vertical
  position; assign each word to a column.

**Grok's corrections to the naive plan (adopted):**
- **Anchor columns on the header row, not on the "densest right-edge band."** The densest-band
  heuristic breaks on amounts embedded in descriptions (check/invoice numbers), sparse credit
  columns, single signed-amount columns, and totals. We map header keywords
  (Date/Description/Debit/Credit/Balance/Amount, with synonyms) to column x-ranges instead.
- **Auto-detect the debit sign convention** rather than assuming `credit − debit`. Bank
  statements lower the balance on a debit; asset-side ledgers raise it. We vote on consecutive
  printed balances and require a strict majority with ≥2 votes, else report `unknown` and skip
  reconciliation rather than guess.
- **Don't chain printed balances / "reset to printed" on a mismatch** — that flags two rows for
  one corrupt balance. We compute a pure cumulative series anchored on the first printed balance
  and driven by per-row amounts, so an isolated typo flags exactly one row (verified on the
  sample), while a wrong amount or missing row still cascades from the break (informative).
- **Scan detection must be per page**, not the document average (a letterhead can push a scanned
  page's average over the threshold).
- **`pytesseract` + render, not `ocrmypdf`/`pdf2image`.** But render with **pdfplumber's built-in
  renderer (pypdfium2, Apache-licensed, already a dependency)** rather than PyMuPDF — PyMuPDF is
  AGPL and its word y-coordinates differ from pdfplumber's, which would corrupt shared row
  clustering. This also means one fewer dependency and no Poppler.
- **Money parsing is locale-aware:** US (`1,234.56`) and EU (`1.234,56`, `1 234,56`), parentheses
  and trailing/unicode minus, currency symbols, and trailing `DR`/`CR` markers. `Decimal`
  throughout, never float.
- **Ollama thinking-model gotcha:** Qwen3 emits its answer in a `thinking` field and leaves
  `response` empty unless thinking is disabled. We send top-level `think: false` (verified: the
  answer then lands in `response` in ~8s warm) and use a generous timeout (cold load ≈ 60s) with
  `keep_alive` so a batch of flags stays fast.

## Library & model choices

| Concern | Choice | Why |
|---|---|---|
| Born-digital extraction | **pdfplumber** (default), its table detector (fallback) | pure Python, deterministic coords, no native deps |
| Page rasterization for OCR | **pypdfium2** (via `pdfplumber.Page.to_image`) | Apache license, already a dep, no Poppler, no AGPL PyMuPDF |
| OCR engine | **Tesseract** via **pytesseract** (optional) | the local, offline standard; only used for scans |
| XLSX export | **openpyxl** | standard; CSV needs only the stdlib |
| Ollama call | **requests** | one local HTTP POST; no heavy SDK |
| Error-check LLM | **`qwen2.5:3b`** (Ollama) by default, optional & configurable | low cold-start / RAM headroom and reliably emits the required JSON schema (override with `OCR_LLM_MODEL`) |

**Model note (this machine):** 32 GB RAM, ~18 GB free. `qwen3.8` (17.7 GB) fits but is tight;
`qwen3.6` (23.9 GB) does **not** fit and is not used. `n2ft` (a 4 B model present here) ignored
the classification schema in testing. Recommendation for lower cold-start and RAM headroom:
`ollama pull qwen2.5:3b` and set it as the model. The whole LLM stage is optional — the pipeline
produces the same spreadsheet without it.

## A/B extraction test (recorded)

On `samples/bank_statement.pdf` (a ruled statement with horizontal lines only):

| Strategy | Rows | Balance error caught | Field fidelity |
|---|---|---|---|
| **`words`** (header-anchored coords) | 15/15 | yes | **1.00** — every field clean |
| `lines` (pdfplumber `extract_tables`) | 15 | yes | **0.00** — date+description collapse into one column (`"2026-01-02 Open"`), description lost |

**Winner: `words`.** Both capture rows and the injected balance error, but the generic
text-table detector infers column boundaries from whitespace density and misplaces them, losing
the description column entirely. Header-anchored word clustering gets exact column x-ranges.
Metric: description-fidelity (fraction of rows with a non-empty description); see
`tests/test_pipeline.py::test_ab_words_beats_lines_on_fidelity`. Grok's stronger metric —
micro-F1 on the `(date, debit, credit, balance)` tuple against ground truth — is the right one
for a larger fixture set; documented as future work below.

## Known limitations / future work

- OCR uses `image_to_string` (text only); columns are recovered by a line regex. `image_to_data`
  (word bounding boxes) would let the same header-anchored column logic run on scans — the
  biggest single robustness win for scanned statements.
- One synthetic fixture. Grok listed 10 fixture shapes worth adding (full-grid vlines, wrapped
  descriptions, page-2 with no header, EU number formats, single signed-amount column, two tables
  on a page, hybrid scanned page). Each is a small PDF + expected CSV.
- Multi-table pages and repeated headers across pages are not yet special-cased.
