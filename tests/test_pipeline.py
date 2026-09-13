"""End-to-end tests + the A/B extraction-strategy comparison.

Runnable two ways:
    python -m pytest tests/            # if pytest is installed
    python tests/test_pipeline.py      # plain runner, no pytest needed
"""
from __future__ import annotations
import os
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ocr_pipeline.pipeline import process, parse_text_rows  # noqa: E402
from ocr_pipeline import reconcile as RC  # noqa: E402

SAMPLE = os.path.join(ROOT, "samples", "bank_statement.pdf")


def _ensure_sample():
    if not os.path.exists(SAMPLE):
        sys.path.insert(0, os.path.join(ROOT, "samples"))
        import make_sample
        make_sample.make_pdf(SAMPLE)


def test_words_strategy_extracts_and_flags():
    _ensure_sample()
    r = process(SAMPLE, strategy="words")
    assert r["ok"] and r["route"] == "born-digital"
    assert r["summary"]["rows"] == 15, r["summary"]
    # every row has a non-empty description (field fidelity)
    assert all(row.get("description") for row in r["rows"])
    # the one injected error is flagged, on the right row, and nothing else
    flagged = [row for row in r["rows"] if row.get("flag")]
    assert len(flagged) == 1, flagged
    assert flagged[0]["date"] == "2026-01-14"
    assert r["summary"]["sign_convention"] == "debit_lowers_balance"


def test_ab_words_beats_lines_on_fidelity():
    """A/B: both may capture rows, but 'words' preserves the description column."""
    _ensure_sample()
    def desc_fidelity(strat):
        rows = process(SAMPLE, strategy=strat)["rows"]
        if not rows:
            return 0.0
        return sum(1 for x in rows if (x.get("description") or "").strip()) / len(rows)
    words = desc_fidelity("words")
    lines = desc_fidelity("lines")
    print(f"\n[A/B] description fidelity: words={words:.2f} lines={lines:.2f} -> "
          f"winner={'words' if words >= lines else 'lines'}")
    assert words == 1.0
    assert words >= lines  # header-anchored clustering never loses to generic text tables


def test_parse_money_edge_cases():
    p = RC.parse_money
    assert p("1,234.56") == Decimal("1234.56")
    assert p("$2,000.00") == Decimal("2000.00")
    assert p("(84.19)") == Decimal("-84.19")   # parentheses = negative
    assert p("-25.00") == Decimal("-25.00")
    assert p("1.234,56") == Decimal("1234.56")     # EU thousands/decimal
    assert p("1 234,56") == Decimal("1234.56")     # EU with space thousands
    assert p("84.19 DR") == Decimal("-84.19")      # trailing debit marker
    assert p("1,234.56 CR") == Decimal("1234.56")  # credit marker stays positive
    assert p("1234.56-") == Decimal("-1234.56")    # trailing minus
    assert p("−1,234.56") == Decimal("-1234.56")  # unicode minus
    assert p("") is None
    assert p("N/A") is None
    assert p("OCR-Pipeline tool.") is None


def test_sign_autodetect_ledger_debit_raises():
    """Asset-side ledger where debits INCREASE the balance -> auto-detected."""
    raw = [
        {"date": "2026-02-01", "description": "open", "balance": "100.00"},
        {"date": "2026-02-02", "description": "buy", "debit": "40.00", "balance": "140.00"},
        {"date": "2026-02-03", "description": "sell", "credit": "10.00", "balance": "130.00"},
    ]
    rows = RC.normalize_rows(raw)
    rows, summary = RC.reconcile(rows)
    assert summary["sign_convention"] == "debit_raises_balance", summary
    assert summary["balance_mismatches"] == 0


def test_ocr_textline_parser():
    """The scanned-page fallback parser reads date + trailing amounts from raw text."""
    text = "2026-03-01 COFFEE SHOP 12.50 987.50\n2026-03-02 PAYCHECK 2,000.00 2,987.50"
    rows = parse_text_rows(text)
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-03-01"
    assert rows[0]["balance"] == "987.50"
    assert rows[1]["amount"] == "2,000.00"


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
