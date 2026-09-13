# Ledger-OCR Deterministic Pipeline Accuracy Benchmark

**Date:** 2026-09-13  
**Corpus:** Synthetic-with-known-truth  
**Strategy:** `words` (deterministic)  

## Per-Fixture Results

| Fixture | Truth Rows | Pred Rows | Matched Rows | TP | FP | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `base_ruled` | 15 | 15 | 15 | 44 | 0 | 0 |
| `bleed_description` | 3 | 3 | 3 | 6 | 0 | 0 |
| `eu_format` | 4 | 4 | 4 | 11 | 0 | 0 |
| `full_grid` | 4 | 4 | 4 | 11 | 0 | 0 |
| `single_amount` | 4 | 4 | 4 | 8 | 0 | 0 |
| `two_page` | 4 | 4 | 4 | 8 | 0 | 0 |
| `two_tables` | 4 | 5 | 4 | 8 | 1 | 0 |
| **Aggregate** | **38** | **39** | **38** | **96** | **1** | **0** |

## Summary Metrics

| Metric | Value |
| :--- | :--- |
| **Micro Precision** | 0.9897 |
| **Micro Recall** | 1.0000 |
| **Micro F1** | 0.9948 |
| **Row Recall** | 1.0000 (38/38) |
| **Balance-Error Catch Rate** | 100.0% (2/2) |

## Methodology & Evaluation

The benchmark evaluates the deterministic `words` strategy across seven synthetic born-digital PDF fixtures with exact known ground truth.

- **Row Matching:** Greedy ordering alignment. A predicted row matches a truth row iff dates are identical and normalized money values (`parse_money`) match on balance (or amount/debit/credit if balance is omitted).
- **Field Metrics:** Micro-averaged Precision, Recall, and F1 calculated over the four primary fields (`date`, `debit`, `credit`, `balance`).
- **Balance Catch Rate:** Fraction of deliberate running-balance arithmetic errors correctly flagged by reconciliation.
