from decimal import Decimal

from ledger_ocr import reconcile as RC


def test_parse_money_edge_cases():
    p = RC.parse_money
    assert p("1,234.56") == Decimal("1234.56")
    assert p("$2,000.00") == Decimal("2000.00")
    assert p("(84.19)") == Decimal("-84.19")        # parentheses = negative
    assert p("-25.00") == Decimal("-25.00")
    assert p("84.19 DR") == Decimal("-84.19")       # trailing debit marker
    assert p("1,234.56 CR") == Decimal("1234.56")   # credit marker stays positive
    assert p("1234.56-") == Decimal("-1234.56")     # trailing minus
    assert p("−1,234.56") == Decimal("-1234.56")  # unicode minus
    assert p("") is None
    assert p("N/A") is None
    assert p("OCR-Pipeline tool.") is None


def test_parse_money_locale_thousands():
    """'5,000' must not become 5.00, and '1.000.000' must not be dropped."""
    p = RC.parse_money
    assert p("5,000") == Decimal("5000")
    assert p("1,500") == Decimal("1500")
    assert p("12,345") == Decimal("12345")
    assert p("1,234,567") == Decimal("1234567")
    assert p("12,345.67") == Decimal("12345.67")
    assert p("1.234") == Decimal("1234")
    assert p("1.000.000") == Decimal("1000000")
    assert p("1.234,56") == Decimal("1234.56")
    assert p("1 234,56") == Decimal("1234.56")
    assert p("1 000 000") == Decimal("1000000")
    assert p("5000") == Decimal("5000")
    assert p("100.00") == Decimal("100.00")
    # a money cell that is really two tokens (leaked description) is REJECTED, never glued
    assert p("1043 100.00") is None
    assert p("1,234.56 (2)") is None


def test_sign_autodetect_ledger_debit_raises():
    """Asset-side ledger where debits INCREASE the balance -> auto-detected."""
    raw = [
        {"date": "2026-02-01", "description": "open", "balance": "100.00"},
        {"date": "2026-02-02", "description": "buy", "debit": "40.00", "balance": "140.00"},
        {"date": "2026-02-03", "description": "sell", "credit": "10.00", "balance": "130.00"},
    ]
    rows, summary = RC.reconcile(RC.normalize_rows(raw))
    assert summary["sign_convention"] == "debit_raises_balance", summary
    assert summary["balance_mismatches"] == 0


def test_single_amount_column_reconciles():
    """A single signed-amount column is reconciled, not declared 'unknown'."""
    raw = [
        {"date": "2026-02-01", "description": "open", "amount": "0.00", "balance": "1000.00"},
        {"date": "2026-02-02", "description": "dep", "amount": "200.00", "balance": "1200.00"},
        {"date": "2026-02-03", "description": "wire", "amount": "-350.00", "balance": "999.00"},  # should be 850
        {"date": "2026-02-04", "description": "refund", "amount": "50.00", "balance": "900.00"},
    ]
    rows, summary = RC.reconcile(RC.normalize_rows(raw))
    assert summary["sign_convention"] == "single_amount_column", summary
    assert summary["balance_checked"] is True, summary
    assert summary["balance_mismatches"] == 1, summary
    flagged = [r for r in rows if r.get("flag")]
    assert len(flagged) == 1 and flagged[0]["date"] == "2026-02-03", flagged


def test_no_balance_reports_not_checked():
    """No balance column -> 'not checked', not a misleading '0 mismatches'."""
    raw = [{"date": "2026-02-01", "description": "a", "amount": "10.00"},
           {"date": "2026-02-02", "description": "b", "amount": "-30.00"}]
    rows, summary = RC.reconcile(RC.normalize_rows(raw))
    assert summary["balance_checked"] is False, summary
    assert summary["balance_mismatches"] is None, summary
