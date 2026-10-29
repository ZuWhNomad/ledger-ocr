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
    assert T._canon("Funds Out") == "debit" and T._canon("CR Amount") == "credit"


def test_general_ledger_centred_headers_and_account_labels():
    # QuickBooks GL: headers centred over left-aligned Type/Date/Num/Name text.
    words = (_line(0, ("Type", 30), ("Date", 100), ("Num", 170), ("Name", 250),
                   ("Debit", 400), ("Credit", 470), ("Balance", 560))
             + _line(20, ("Savers", 14), ("Chequing", 56), ("1,000.00", 554))
             + _line(40, ("Payment", 10), ("10/01/2020", 85), ("2998", 160), ("Smith,", 200), ("Jo", 242),
                     ("100.00", 394), ("1,100.00", 554))
             + _line(60, ("Cheque", 10), ("10/02/2020", 85), ("Service", 200), ("Charge", 248),
                     ("50.00", 476), ("1,050.00", 554))
             + _line(80, ("Total", 14), ("Employee", 50), ("Advances", 104), ("and", 158), ("Loans", 182),
                     ("0.00", 578)))
    rows, _ = T.build_rows_from_words(words, 620)
    assert rows[0] == {"type": "Savers Chequing", "balance": "1,000.00"}
    assert rows[1] == {"type": "Payment", "date": "10/01/2020", "num": "2998", "description": "Smith, Jo",
                       "debit": "100.00", "balance": "1,100.00"}
    assert rows[2]["description"] == "Service Charge" and rows[2]["credit"] == "50.00"
    assert rows[3] == {"type": "Total Employee Advances and Loans", "balance": "0.00"}   # one phrase


def test_right_aligned_date_left_aligned_amount_header_and_account_column():
    # Expense list: date right-aligned one space from the name, 'Amount' header left-aligned
    # over right-aligned numbers, 'CR Amount' as one header, a text column after the money.
    words = (_line(0, ("Date", 40), ("Description", 100), ("Amount", 300), ("CR", 380), ("Amount", 398),
                   ("Account", 450))
             + _line(20, ("01/04/2022", 34), ("Garage", 100), ("500.00", 314), ("Auto", 450), ("Repairs", 480))
             + _line(40, ("1/13/22", 52), ("INTERAC", 100), ("Administrator", 148), ("ACMEHOLD", 232),
                     ("IND", 280), ("1200", 410), ("Research", 450))
             + _line(60, ("2/24/22", 52), ("5", 100), ("guys", 112), ("8.80", 326), ("Meals", 450)))
    rows, _ = T.build_rows_from_words(words, 620)
    assert rows[0] == {"date": "01/04/2022", "description": "Garage", "amount": "500.00", "account": "Auto Repairs"}
    assert rows[1] == {"date": "1/13/22", "description": "INTERAC Administrator ACMEHOLD IND", "credit": "1200",
                       "account": "Research"}
    assert rows[2]["date"] == "2/24/22" and rows[2]["description"] == "5 guys"


def test_records_from_grid():
    grid = [["Statement"], ["Date", "Details", "Amount"], ["2026-01-02", "Fee", "-5.00"], ["", "", ""]]
    assert T.records_from_grid(grid) == [{"date": "2026-01-02", "description": "Fee", "amount": "-5.00"}]
