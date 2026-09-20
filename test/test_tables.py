from ledger_ocr import tables as T


def _line(top, *cells):
    """cells: (text, x0). Boxes are 10 high and 6 wide per character."""
    return [{"text": t, "x0": x, "x1": x + 6 * len(t), "top": top, "bottom": top + 10} for t, x in cells]


HEADER = _line(0, ("Date", 10), ("Description", 100), ("Debit", 300), ("Credit", 400), ("Balance", 500))


def test_header_anchored_rows_and_wrapped_description():
    words = (HEADER
             + _line(20, ("2026-01-02", 10), ("Coffee", 100), ("shop", 142), ("12.50", 300), ("987.50", 500))
             + _line(40, ("downtown", 100))                      # wrapped description line
             + _line(60, ("2026-01-03", 10), ("Pay", 100), ("2,000.00", 400), ("2,987.50", 500)))
    rows, bounds = T.build_rows_from_words(words, 600)
    assert [r["date"] for r in rows] == ["2026-01-02", "2026-01-03"]
    assert rows[0]["description"] == "Coffee shop downtown"
    assert rows[0]["debit"] == "12.50" and "credit" not in rows[0]
    assert rows[1]["credit"] == "2,000.00" and rows[1]["balance"] == "2,987.50"


def test_continuation_page_reuses_carried_columns():
    _, bounds = T.build_rows_from_words(HEADER, 600)
    page2 = _line(0, ("2026-01-04", 10), ("Rent", 100), ("900.00", 300), ("2,087.50", 500))
    rows, _ = T.build_rows_from_words(page2, 600, bounds)
    assert rows == [{"date": "2026-01-04", "description": "Rent", "debit": "900.00", "balance": "2,087.50"}]


def test_no_header_no_rows():
    assert T.build_rows_from_words(_line(0, ("hello", 10), ("world", 60)), 600) == ([], None)


def test_header_synonyms_match_whole_words_only():
    assert T._canon("Descr") == "description"     # contains 'cr' but is NOT a credit column
    assert T._canon("Money In") == "credit"
    assert T._canon("Withdrawals") == "debit"
    assert T._canon("Notes") is None


def test_records_from_grid():
    grid = [["Statement"], ["Date", "Details", "Amount"], ["2026-01-02", "Fee", "-5.00"], ["", "", ""]]
    assert T.records_from_grid(grid) == [{"date": "2026-01-02", "description": "Fee", "amount": "-5.00"}]
