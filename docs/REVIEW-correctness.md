# OCR-Pipeline — Correctness Review (Extraction & Reconciliation)

Lens: extraction & reconciliation correctness for financial data. A *silent wrong number* is
the worst outcome and is ranked first. Read-only review; no code changed. All findings verified
against the actual code by running it (concrete inputs and observed outputs shown).

Severity: **P1** = silent wrong number, **P2** = crash / silently dropped row, **P3** = cosmetic.

---

## P1 — silent wrong numbers (ranked first)

### P1-1. `parse_money` mis-guesses locale on any amount with a thousands separator and no decimals → off by ~1000× (or dropped)
`ocr_pipeline/reconcile.py:58-63`. Locale is decided purely from *which separator appears last*:

```
last_comma, last_dot = t.rfind(","), t.rfind(".")
if last_comma > last_dot:   # EU: comma is decimal
    t = t.replace(".", "").replace(",", ".")
else:                       # US: comma is thousands
    t = t.replace(",", "")
```

When a value has a comma but **no** decimal point, the only separator is the comma, so it is
always treated as an EU decimal comma. Verified (`python -c` against the real function):

| Input (US whole-dollar / EU) | parsed | correct |
|---|---|---|
| `5,000`   | `5.000`  | 5000 |
| `1,500`   | `1.500`  | 1500 |
| `2,000`   | `2.000`  | 2000 |
| `12,345`  | `12.345` | 12345 |
| `1,234,567` | `None` (InvalidOperation → dropped) | 1234567 |
| `1.234` (EU = 1234) | `1.234` | 1234 |
| `1.000.000` (EU = 1M) | `None` (dropped) | 1000000 |

Concrete failure: a general-ledger row `PAYROLL RUN … 5,000` or a rounded entry `Transfer 1,500`
silently becomes **5.00 / 1.50**. Amounts ≥ 1,000,000 with commas and no cents parse to
`InvalidOperation` and return `None` → the amount is silently dropped from the row.
The bundled sample only ever uses `.00`, so the last separator is the dot and the bug is masked
in tests. Real bank statements usually print cents (safe), but **general ledgers frequently use
whole-dollar amounts with thousands separators**, and PLAN.md explicitly targets both general
ledgers and EU formats.
Downstream: if the row still has a printed balance, the wrong amount cascades a reconciliation
flag (loud) — but for single-amount / no-balance statements (see P1-2) it exports silently wrong.
**Severity P1. Confidence: high (verified).**

### P1-2. Single signed-amount-column statements are never reconciled — a balance typo passes silently as "0 mismatches"
`ocr_pipeline/reconcile.py:90-94` + `:126-132`. For an amount-only row, `_delta` returns the
amount **ignoring `sign`**:

```
if d is None and c is None and a is not None:
    return a  # single signed amount column
```

So `_fit_score(rows, +1) == _fit_score(rows, -1)` for an amount-only statement. The sign vote at
`:127` (`if max(v_pos, v_neg) < 2 or v_pos == v_neg: sign = 0  # unknown`) therefore *always*
resolves to `unknown`, and the running-balance loop at `:135` (`if sign != 0:`) is skipped
entirely. Verified with a 4-row signed-amount statement containing an obvious typo
(printed balance `999.00` where the running balance should be `850.00`):

```
summary: {'sign_convention': 'unknown', 'balance_mismatches': 0}
2026-02-03 flag= None    # the wrong balance is NOT flagged
```

The whole class of "single signed Amount column" statements — which `_delta` explicitly claims to
support — gets **zero** running-balance validation, and the summary reports `balance_mismatches: 0`,
which a user reads as "reconciled clean". A wrong number sails through unflagged.
**Severity P1. Confidence: high (verified).**

### P1-3. Header-anchored column boundaries let description text leak into a money column → two tokens concatenate into a huge fake amount
`ocr_pipeline/tables.py:79-87` computes each column boundary as the **midpoint between adjacent
header-word centres**, and `:106-111` assigns a word by its own midpoint. Because a short header
word (e.g. "Description") sits at the *left* of a wide description column, the description/amount
boundary lands far left — roughly the left third of the visual description column — so any
description text in the right ~60% of that column is assigned to the next (money) column. The
cell's words are then joined with a space at `:120` (`" ".join(v)`), and `parse_money` strips the
space, gluing the tokens into one number.

Verified end-to-end with a generated PDF (a `CHECK 1043` description whose check-number token
crosses the boundary, real amount `100.00`):

```
{'date':'2026-01-03','description':'CHECK','amount':'1043 100.00', ...}
parse_money('1043 100.00') -> Decimal('1043100.00')   # should be 100.00
```

`100.00` becomes **1,043,100.00** — silent, plausible-looking, catastrophic. This is systemic, not
a rare edge: long merchant names, addresses, memo/reference lines routinely fill the right side of
a description column. Related amplifier: any two numeric tokens landing in the same money cell
(stray footnote, two amounts) merge into one number via the same space-strip
(`reconcile.py:47`). In debit/credit statements this cascades reconciliation flags (loud); in
amount-only statements (P1-2) it is fully silent.
**Severity P1. Confidence: high (verified for the leak + concatenation; the exact trigger is
layout-dependent).**

### P1-4. `_canon` 2-letter substring match ("cr"/"dr") mislabels description headers as credit/debit
`ocr_pipeline/tables.py:27-35`, `s in t` substring match with `credit` synonym `"cr"` and `debit`
synonym `"dr"`. Verified:

```
_canon('Descr')  -> 'credit'
```

A statement whose description header is abbreviated `Descr` / `Descr.` maps the **description
column to the credit column**. All description text then flows into "credit" (mostly `None` via
`parse_money`, but any embedded digits become fake credits), and the real credit column is left
unmapped/merged. The debit synonym `"dr"` is an equal hazard for any header containing that
bigram. Header-only (data cells in the `words` strategy are assigned by geometry, not `_canon`),
but a mislabelled money column corrupts every row and can flip the sign convention.
**Severity P1 (mislabelled money column → wrong signs). Confidence: high (verified for `Descr`).**

---

## P2 — dropped rows / crashes

### P2-1. Multi-page statements silently drop every page whose header does not repeat
`ocr_pipeline/tables.py:102-104`: `_find_header` returns `-1` when a page has no recognizable
header row, and `extract_words_table` then `return []` for that page. `extract.py:54-57` iterates
pages and `extend`s, with no cross-page header carry-over. Verified with a 2-page PDF (header only
on page 1):

```
rows extracted: 2      # page 1 only
2026-01-02 Open
2026-01-03 Buy A
# page 2's "Buy B" / "Buy C" silently absent
```

Continuation pages that don't repeat the header (very common) are dropped with no warning; the
CSV/XLSX is an incomplete financial record and nothing flags the omission. PLAN.md lists
"page-2 with no header" as unhandled, but the failure mode is a *silent* drop, not a warning.
**Severity P2 (borderline P1 — silent incompleteness of a financial record). Confidence: high
(verified).**

### P2-2. OCR line parser drops whole-number amounts and mis-tokenizes EU numbers
`ocr_pipeline/pipeline.py:21`, `_MONEY_TOKEN` requires either a `.dd` decimal or comma groups:
`\(?\$?-?[\d,]+\.\d{2}\)?|\(?\$?-?\d{1,3}(,\d{3})+\)?`.
- A bare integer amount (`500`, `1200`) matches neither branch → the row is emitted with **no
  amount/balance** (silently). Scanned ledgers with whole-dollar amounts lose their numbers.
- EU `1.234,56` is matched greedily by `[\d,]+\.\d{2}` as `1.23` (dot + first two digits),
  truncating/splitting the value on OCR'd EU statements.

The OCR path also assumes "last token = balance, second-last = amount" (`pipeline.py:43-47`); a
decimalized check/reference number on the line shifts both assignments. PLAN.md acknowledges the
OCR path is the weak spot, but these are silent mis-parses, not omissions the user can see.
**Severity P2 (P1 within a scanned document). Confidence: high (by construction; regex verified by
reading).**

### P2-3. Multi-account statements flag the entire second account
`ocr_pipeline/reconcile.py:136-147`. All rows are one cumulative series anchored on the first
printed balance. At the boundary into a second account the balance jumps; `expected` is now offset
by the second account's opening balance, so **every** subsequent row mismatches and is flagged.
This is loud (not a silent wrong number) but floods flags and can perturb the sign vote. PLAN.md
notes multi-table pages are not special-cased.
**Severity P2. Confidence: high (by construction).**

### P2-4. No balance column → no validation at all, still reported as `balance_mismatches: 0`
`ocr_pipeline/reconcile.py:122,126-132`. A debit/credit or amount statement with **no** Balance
column has `with_bal == []`, both fit-scores 0 → `unknown` → loop skipped. Any misread digit
passes with `balance_mismatches: 0` and `sign_convention: unknown`. Expected (nothing to check
against), but the summary does not distinguish "reconciled OK" from "could not reconcile", so a
user sees `0` and assumes validation happened.
**Severity P2 (misleading summary). Confidence: high.**

---

## P3 — cosmetic / lower impact

- **XLSX writes every value as text**, not numbers. `export.py:44-45` appends the *original strings*
  (`rec[c]`), so Excel stores `84.19`, `-84.19`, `(84.19)` as text (green-triangle "number stored
  as text"); sums/filters won't work without a re-parse. This *does* preserve exact source values
  (no float rounding — Decimals are never written back), which is the right call for fidelity, but
  numeric columns should be typed. **P3. Confidence: high.**
- **CSV encoding is correct**: `utf-8-sig` (BOM) at `export.py:27` opens cleanly in Excel. No issue.
- **Only reconciler-flagged rows are highlighted.** `export.py` has no "low-confidence extraction"
  flag, so a garbled OCR row or a leaked-token row that happens to still reconcile (or that lives in
  a non-reconcilable statement) is exported unmarked. **P3→P2 depending on statement type.**
- **`parse_money` footnote/paren edge cases** (`reconcile.py:40-56`): a trailing footnote digit
  (`1,234.56 (2)` → `1234.562`) or paren-negative combined with a trailing `CR` (`(1,234.56) CR` →
  `+1234.56`, sign lost because the string no longer *ends* with `)`) parse wrong. Rare. **P3.**
- **Dead code**: `reconcile.py:47` `t.replace(",", ",")` is a no-op; the currency-strip loop at
  `:48-49` runs after the regex at `:47` has already removed all currency symbols. Harmless. **P3.**
- **`looks_scanned` uses `max(counts) < 40`** (`extract.py:42`). A born-digital PDF that already
  carries a stale/garbage text layer from a prior OCR pass is treated as born-digital and pdfplumber
  reads its (possibly wrong) coordinates rather than re-OCRing. Edge. **P3.**

---

## Determinism

Same PDF in twice → identical numeric output. Row clustering sorts before grouping
(`tables.py:49`), header selection breaks ties by first-max (`:74`, strict `>`), parse and
reconcile are pure `Decimal`, and export order is stable. The optional LLM (`validate.py`) only
annotates already-flagged rows and is forbidden from changing numbers, so it cannot affect the
figures. **No determinism issue found. Confidence: high.**

---

## Ranked summary (silent wrong numbers first)

1. **P1-1** `parse_money` locale guess: `5,000` → `5.00`, EU millions dropped — any thousands-sep
   amount without decimals (`reconcile.py:58-63`).
2. **P1-2** Single signed-amount statements never reconciled; typo passes as `0 mismatches`
   (`reconcile.py:90-94, 126-132`).
3. **P1-3** Description text leaks past the header-midpoint column boundary and concatenates into a
   giant fake amount, e.g. `100.00` → `1043100.00` (`tables.py:79-87, 106-120`; `reconcile.py:47`).
4. **P1-4** `_canon` "cr"/"dr" substring mislabels description headers (`Descr` → credit)
   (`tables.py:27-35`).
5. **P2-1** Multi-page statements silently drop pages without a repeated header (`tables.py:102-104`).
6. **P2-2** OCR parser drops whole-number amounts and mis-tokenizes EU numbers (`pipeline.py:21`).
7. **P2-3** Multi-account statements flag the entire second account (`reconcile.py:136-147`).
8. **P2-4** No-balance statements report `balance_mismatches: 0` despite doing no checks
   (`reconcile.py:126-132`).
9. **P3** XLSX numbers stored as text; extraction-confidence never flagged; minor parse edge cases;
   dead code; scan-detection edge.
