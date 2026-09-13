from __future__ import annotations
import os
import sys
import csv
from typing import Dict, List, Tuple
from decimal import Decimal

TESTS_DIR = os.path.dirname(os.path.abspath(__file__)) # app/tests
APP_DIR = os.path.dirname(TESTS_DIR)                 # app
REPO_ROOT = os.path.dirname(APP_DIR)                 # F:\Ledger-OCR

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, APP_DIR)

from ocr_pipeline.pipeline import process
from ocr_pipeline.reconcile import parse_money


def score_rows(pred_rows: List[Dict], truth_rows: List[Dict]) -> Dict:
    """Score predicted rows against ground truth rows using greedy matching and field-level micro metrics."""
    used_pred = set()
    matches: List[Tuple[int, int]] = []

    # Greedy row matching: iterate truth rows in order
    for t_idx, t in enumerate(truth_rows):
        t_date = t.get("date", "").strip()
        t_bal = parse_money(t.get("balance"))
        t_amt = parse_money(t.get("amount"))
        t_deb = parse_money(t.get("debit"))
        t_cred = parse_money(t.get("credit"))

        matched_p_idx = None
        for p_idx, p in enumerate(pred_rows):
            if p_idx in used_pred:
                continue
            if p.get("date", "").strip() != t_date:
                continue

            if t_bal is not None:
                p_bal = parse_money(p.get("balance"))
                if p_bal == t_bal:
                    matched_p_idx = p_idx
                    break
            else:
                p_amt = parse_money(p.get("amount"))
                if t_amt is not None:
                    if p_amt == t_amt:
                        matched_p_idx = p_idx
                        break
                else:
                    p_deb = parse_money(p.get("debit"))
                    p_cred = parse_money(p.get("credit"))
                    if p_deb == t_deb and p_cred == t_cred:
                        matched_p_idx = p_idx
                        break

        if matched_p_idx is not None:
            used_pred.add(matched_p_idx)
            matches.append((t_idx, matched_p_idx))

    # Field metrics over date, debit, credit, balance
    FIELDS = ["date", "debit", "credit", "balance"]
    tp = 0
    fp = 0
    fn = 0

    matched_truth_indices = {m[0] for m in matches}
    matched_pred_indices = {m[1] for m in matches}

    for t_idx, p_idx in matches:
        t_row = truth_rows[t_idx]
        p_row = pred_rows[p_idx]
        for field in FIELDS:
            t_val = (t_row.get(field) or "").strip()
            p_val = (p_row.get(field) or "").strip()

            if t_val != "":
                if p_val == t_val:
                    tp += 1
                else:
                    fn += 1
                    if p_val != "":
                        fp += 1
            else:
                if p_val != "":
                    fp += 1

    # Unmatched truth rows
    for t_idx, t_row in enumerate(truth_rows):
        if t_idx not in matched_truth_indices:
            for field in FIELDS:
                t_val = (t_row.get(field) or "").strip()
                if t_val != "":
                    fn += 1

    # Unmatched predicted rows
    for p_idx, p_row in enumerate(pred_rows):
        if p_idx not in matched_pred_indices:
            for field in FIELDS:
                p_val = (p_row.get(field) or "").strip()
                if p_val != "":
                    fp += 1

    # Balance-error catch rate numerator and denominator
    balance_flag_truth_count = 0
    balance_flag_caught_count = 0

    for t_idx, t_row in enumerate(truth_rows):
        t_flag = t_row.get("flag") or ""
        if "balance" in t_flag:
            balance_flag_truth_count += 1
            # Check if matched predicted row has non-empty flag
            for tm, pm in matches:
                if tm == t_idx:
                    p_flag = pred_rows[pm].get("flag") or ""
                    if p_flag.strip():
                        balance_flag_caught_count += 1

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "matched": len(matches),
        "truth": len(truth_rows),
        "truth_rows_count": len(truth_rows),
        "pred_rows_count": len(pred_rows),
        "matched_rows_count": len(matches),
        "balance_flag_truth_count": balance_flag_truth_count,
        "balance_flag_caught_count": balance_flag_caught_count,
    }


def evaluate_fixture(pdf_path: str, csv_path: str) -> Dict:
    res = process(pdf_path, strategy="words")
    pred_rows = res.get("rows", [])

    with open(csv_path, "r", encoding="utf-8") as f:
        truth_rows = list(csv.DictReader(f))

    return score_rows(pred_rows, truth_rows)


def run_benchmark():
    fixtures_dir = os.path.join(APP_DIR, "tests", "fixtures")
    fixture_files = sorted([
        f for f in os.listdir(fixtures_dir)
        if f.endswith(".pdf")
    ])

    results = {}
    tot_truth_rows = 0
    tot_matched_rows = 0
    tot_tp = 0
    tot_fp = 0
    tot_fn = 0
    tot_bal_truth = 0
    tot_bal_caught = 0

    for pdf_file in fixture_files:
        base_name = pdf_file[:-4]
        csv_file = f"{base_name}.expected.csv"
        pdf_path = os.path.join(fixtures_dir, pdf_file)
        csv_path = os.path.join(fixtures_dir, csv_file)

        if not os.path.exists(csv_path):
            continue

        res = evaluate_fixture(pdf_path, csv_path)
        results[base_name] = res

        tot_truth_rows += res["truth_rows_count"]
        tot_matched_rows += res["matched_rows_count"]
        tot_tp += res["tp"]
        tot_fp += res["fp"]
        tot_fn += res["fn"]
        tot_bal_truth += res["balance_flag_truth_count"]
        tot_bal_caught += res["balance_flag_caught_count"]

    # Calculate metrics
    prec = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) > 0 else 0.0
    rec = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    row_recall = tot_matched_rows / tot_truth_rows if tot_truth_rows > 0 else 0.0
    bal_catch = (tot_bal_caught / tot_bal_truth) if tot_bal_truth > 0 else None

    bal_catch_str = f"{bal_catch:.1%}" if bal_catch is not None else "N/A"

    # Print readable stdout table
    print(f"{'Fixture':<20} | {'Truth Rows':<10} | {'Pred Rows':<10} | {'Matched':<8} | {'TP':<5} | {'FP':<5} | {'FN':<5}")
    print("-" * 75)
    for name, r in results.items():
        print(f"{name:<20} | {r['truth_rows_count']:<10} | {r['pred_rows_count']:<10} | {r['matched_rows_count']:<8} | {r['tp']:<5} | {r['fp']:<5} | {r['fn']:<5}")
    print("-" * 75)
    print(f"{'Aggregate':<20} | {tot_truth_rows:<10} | {sum(r['pred_rows_count'] for r in results.values()):<10} | {tot_matched_rows:<8} | {tot_tp:<5} | {tot_fp:<5} | {tot_fn:<5}")
    print("\nAggregate Metrics:")
    print(f"  Micro Precision:         {prec:.4f}")
    print(f"  Micro Recall:            {rec:.4f}")
    print(f"  Micro F1:                {f1:.4f}")
    print(f"  Row Recall:              {row_recall:.4f} ({tot_matched_rows}/{tot_truth_rows})")
    print(f"  Balance Catch Rate:      {bal_catch_str} ({tot_bal_caught}/{tot_bal_truth})")

    # Write docs/BENCHMARK.md
    docs_dir = os.path.join(REPO_ROOT, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    bench_md_path = os.path.join(docs_dir, "BENCHMARK.md")

    md_lines = [
        "# Ledger-OCR Deterministic Pipeline Accuracy Benchmark",
        "",
        "**Date:** 2026-09-13  ",
        "**Corpus:** Synthetic-with-known-truth  ",
        "**Strategy:** `words` (deterministic)  ",
        "",
        "## Per-Fixture Results",
        "",
        "| Fixture | Truth Rows | Pred Rows | Matched Rows | TP | FP | FN |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for name, r in results.items():
        md_lines.append(f"| `{name}` | {r['truth_rows_count']} | {r['pred_rows_count']} | {r['matched_rows_count']} | {r['tp']} | {r['fp']} | {r['fn']} |")

    md_lines.extend([
        f"| **Aggregate** | **{tot_truth_rows}** | **{sum(r['pred_rows_count'] for r in results.values())}** | **{tot_matched_rows}** | **{tot_tp}** | **{tot_fp}** | **{tot_fn}** |",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Micro Precision** | {prec:.4f} |",
        f"| **Micro Recall** | {rec:.4f} |",
        f"| **Micro F1** | {f1:.4f} |",
        f"| **Row Recall** | {row_recall:.4f} ({tot_matched_rows}/{tot_truth_rows}) |",
        f"| **Balance-Error Catch Rate** | {bal_catch_str} ({tot_bal_caught}/{tot_bal_truth}) |",
        "",
        "## Methodology & Evaluation",
        "",
        "The benchmark evaluates the deterministic `words` strategy across seven synthetic born-digital PDF fixtures with exact known ground truth.",
        "",
        "- **Row Matching:** Greedy ordering alignment. A predicted row matches a truth row iff dates are identical and normalized money values (`parse_money`) match on balance (or amount/debit/credit if balance is omitted).",
        "- **Field Metrics:** Micro-averaged Precision, Recall, and F1 calculated over the four primary fields (`date`, `debit`, `credit`, `balance`).",
        "- **Balance Catch Rate:** Fraction of deliberate running-balance arithmetic errors correctly flagged by reconciliation.",
        "",
    ])

    with open(bench_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


if __name__ == "__main__":
    run_benchmark()
