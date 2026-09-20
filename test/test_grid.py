"""Generic tables (no ledger header): a tax slip, an invoice, a price list -> spreadsheet."""
import os

import pytest

from conftest import FIXTURES
from ledger_ocr import readers as R
from ledger_ocr import tables as T
from ledger_ocr.pipeline import process

needs_engine = pytest.mark.parametrize(
    "engine", R.available_engines() or [pytest.param("none", marks=pytest.mark.skip("no OCR engine installed"))])


def _line(top, *cells):
    return [{"text": t, "x0": x, "x1": x + 6 * len(t), "top": top, "bottom": top + 10} for t, x in cells]


SLIP = (_line(0, ("2021", 40), ("T4", 75), ("Statement", 95), ("of", 160), ("remuneration", 180))   # title spans columns
        + _line(30, ("Box", 60), ("number", 85), ("Box", 170), ("name", 195), ("Box", 480), ("value", 505))
        + _line(50, ("14", 60), ("Employment", 170), ("income", 240), ("35,744.60", 480))
        + _line(70, ("16", 60), ("Employee's", 170), ("CPP", 240), ("contributions", 265), ("1,757.32", 480))
        + _line(90, ("22", 60), ("Income", 170), ("tax", 215), ("deducted", 240), ("4,178.91", 480)))


def test_columns_are_the_white_gaps_shared_by_the_rows():
    grid = T.grid_from_words(SLIP, 612)
    assert grid[1] == ["Box number", "Box name", "Box value"]
    assert grid[2] == ["14", "Employment income", "35,744.60"]
    assert grid[4] == ["22", "Income tax deducted", "4,178.91"]


def test_prose_is_not_a_table():
    prose = []
    for i, line in enumerate(["the quick brown fox jumps over the lazy dog again and", "again until every gap between the words",
                              "lands somewhere else so no column can be seen", "in this paragraph of ordinary running text"]):
        x = 40
        for word in line.split():
            prose.append({"text": word, "x0": x, "x1": x + 6 * len(word), "top": i * 14, "bottom": i * 14 + 10})
            x += 6 * len(word) + 4
    assert T.grid_from_words(prose, 612) == []


def _slip_pdf(path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica", 11)
    c.drawString(60, 720, "2021 T4 Statement of remuneration")
    rows = [("Box number", "Box name", "Box value"), ("14", "Employment income", "35,744.60"),
            ("16", "Employee's CPP contributions", "1,757.32"), ("22", "Income tax deducted", "4,178.91")]
    for i, (a, b, v) in enumerate(rows):
        y = 680 - 22 * i
        c.drawString(60, y, a)
        c.drawString(170, y, b)
        c.drawRightString(540, y, v)
    c.save()


def test_born_digital_slip_becomes_a_spreadsheet(tmp_path):
    pdf = str(tmp_path / "slip.pdf")
    _slip_pdf(pdf)
    r = process(pdf, outdir=str(tmp_path))
    assert r["document_shape"] == "table" and r["rows"] == []
    assert ["14", "Employment income", "35,744.60"] in r["grid"]
    assert os.path.exists(r["outputs"]["xlsx"]) and os.path.exists(r["outputs"]["csv"])
    import openpyxl
    ws = openpyxl.load_workbook(r["outputs"]["xlsx"]).active
    assert any(c.value == 35744.60 or str(c.value) == "35744.60" for row in ws.iter_rows() for c in row)


@needs_engine
def test_scanned_slip_becomes_a_spreadsheet(tmp_path, engine):
    import pdfplumber
    pdf, png = str(tmp_path / "slip.pdf"), str(tmp_path / "slip.png")
    _slip_pdf(pdf)
    with pdfplumber.open(pdf) as doc:
        doc.pages[0].to_image(resolution=300).original.save(png)
    r = process(png, outdir=str(tmp_path), engine=engine)
    assert r["document_shape"] == "table", r
    assert any(row[0] == "22" and row[1].startswith("Income tax") for row in r["grid"]), r["grid"]


def test_ledger_still_wins_over_generic_table():
    r = process(os.path.join(FIXTURES, "bank_statement.pdf"))
    assert r["document_shape"] == "ledger" and r["grid"] == []


def test_text_mode_skips_tables(tmp_path):
    pdf = str(tmp_path / "slip.pdf")
    _slip_pdf(pdf)
    assert process(pdf, mode="text")["document_shape"] == "text"


def test_receipt_style_label_value_lines_become_two_columns():
    text = ("OFFICIAL RECEIPT\nRx: SC-123\nDIN: 02386437 Mfr: SDZ Remain: 0 CAP\n"
            "Total: 51.77 Patient Pays: 51.77\nMonday to Friday 9:00 am to 8:00 pm\nCONCERNS ?")
    grid = T.pairs_from_text(text)
    assert grid[0] == ["field", "value"]
    assert ["Rx", "SC-123"] in grid and ["Mfr", "SDZ"] in grid and ["Patient Pays", "51.77"] in grid
    assert not any("Monday" in r[0] for r in grid)          # 9:00 is a time, not a pair
    assert T.pairs_from_text("just one: pair") == []
