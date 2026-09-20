"""Accuracy bench: engines x fixtures -> field-level micro-F1. Prints a table; writes nothing.

    python bench/bench.py            # synthetic fixtures (+ private ones, see below)

Arms, per fixture PDF with a <name>.expected.csv beside it:
  pdf-text        the PDF as it is (text layer)
  <engine>/clean  page rendered at 300 dpi                     (an ideal flatbed scan)
  <engine>/rough  150 dpi, rotated 1.5 degrees, JPEG q35, grey (closer to a phone photo)
Real documents: any file in the folder named by LEDGEROCR_PRIVATE_FIXTURES that has a
<name>.expected.csv beside it is scored with every engine. Those numbers are the ones that
matter; the synthetic arms only catch regressions.
"""
from __future__ import annotations
import csv
import io
import os
import sys
from decimal import Decimal
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ledger_ocr import readers as R                  # noqa: E402
from ledger_ocr.pipeline import process              # noqa: E402
from ledger_ocr.reconcile import parse_money         # noqa: E402


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


def _truth(csv_path: str) -> List[Dict]:
    with open(csv_path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _render(pdf_path: str, out_dir: str, rough: bool) -> List[str]:
    """One image file per page (the bench fixtures that span pages are scored page-joined
    only in the pdf-text arm; image arms score page 1 .. n through a multi-page TIFF)."""
    import pdfplumber
    from PIL import Image
    frames = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=150 if rough else 300).original.convert("RGB")
            if rough:
                img = img.convert("L").rotate(1.5, expand=True, fillcolor=255)
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=35)
                img = Image.open(io.BytesIO(buf.getvalue())).convert("L")
            frames.append(img)
    path = os.path.join(out_dir, os.path.basename(pdf_path)[:-4] + ("_rough" if rough else "_clean") + ".tif")
    frames[0].save(path, save_all=True, append_images=frames[1:])
    return path


def run() -> None:
    import tempfile
    fixtures = os.path.join(ROOT, "test", "fixtures")
    engines = R.available_engines()
    arms: Dict[str, Dict[str, Dict]] = {}

    def score(arm, name, path, truth, **kw):
        res = process(path, **kw)
        arms.setdefault(arm, {})[name] = score_rows(res.get("rows", []), truth)

    with tempfile.TemporaryDirectory(prefix="ledgerocr_bench_") as tmp:
        for f in sorted(os.listdir(fixtures)):
            expected = os.path.join(fixtures, f[:-4] + ".expected.csv")
            if not f.endswith(".pdf") or not os.path.exists(expected):
                continue
            truth, pdf = _truth(expected), os.path.join(fixtures, f)
            score("pdf-text", f[:-4], pdf, truth)
            for rough in (False, True):
                img = _render(pdf, tmp, rough)
                for e in engines + ["auto"] * (len(engines) > 1):
                    score(f"{e}/{'rough' if rough else 'clean'}", f[:-4], img, truth, engine=e)

    private = os.environ.get("LEDGEROCR_PRIVATE_FIXTURES", "")
    if os.path.isdir(private):
        for f in sorted(os.listdir(private)):
            stem, ext = os.path.splitext(f)
            expected = os.path.join(private, stem + ".expected.csv")
            if ".expected" in f or not os.path.exists(expected):
                continue
            for e in engines + ["auto"] * (len(engines) > 1):
                score(f"{e}/REAL", stem, os.path.join(private, f), _truth(expected), engine=e)

    names = sorted({n for a in arms.values() for n in a})
    print(f"{'fixture':<22}" + "".join(f"{a:>17}" for a in arms))
    for n in names:
        print(f"{n:<22}" + "".join(f"{_f1([arms[a][n]]) if n in arms[a] else '':>17}" for a in arms))
    print(f"{'ALL (micro-F1)':<22}" + "".join(f"{_f1(list(arms[a].values())):>17}" for a in arms))
    print(f"{'rows matched':<22}" + "".join(
        f"{sum(r['matched_rows_count'] for r in arms[a].values())}/{sum(r['truth_rows_count'] for r in arms[a].values()):<0}".rjust(17)
        for a in arms))
    print(f"{'bad balances caught':<22}" + "".join(
        f"{sum(r['balance_flag_caught_count'] for r in arms[a].values())}/{sum(r['balance_flag_truth_count'] for r in arms[a].values())}".rjust(17)
        for a in arms))


def _f1(results: List[Dict]) -> str:
    tp, fp, fn = (sum(r[k] for r in results) for k in ("tp", "fp", "fn"))
    return f"{2 * tp / (2 * tp + fp + fn):.3f}" if tp else "0.000"


if __name__ == "__main__":
    run()
