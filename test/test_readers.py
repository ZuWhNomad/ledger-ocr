import os

import pytest
from PIL import Image

from conftest import FIXTURES
from ledger_ocr import readers as R

needs_engine = pytest.mark.parametrize(
    "engine", R.available_engines() or [pytest.param("none", marks=pytest.mark.skip("no OCR engine installed"))])


def _texts(page):
    return {w["text"].strip(".,:").lower() for w in page["words"]}


def test_pdf_text_layer_is_read_without_ocr():
    pages = R.read_pages(os.path.join(FIXTURES, "bank_statement.pdf"), engine="not-an-engine")  # never consulted
    assert [p["source"] for p in pages] == ["pdf-text"]
    assert {"date", "balance"} <= _texts(pages[0])


@needs_engine
def test_photo_rotation_stored_in_exif_is_honoured(statement_png, tmp_path, engine):
    """A phone stores 'this side up' in EXIF and leaves the pixels rotated. Feeding an engine the
    raw pixels is what made v0 read photos upside-down."""
    exif = Image.Exif()
    exif[0x0112] = 3                                   # orientation: rotated 180
    photo = str(tmp_path / "photo.jpg")
    Image.open(statement_png).convert("RGB").rotate(180).save(photo, exif=exif, quality=90)
    page = R.read_pages(photo, engine)[0]
    assert page["source"] == engine
    assert {"date", "description", "balance"} <= _texts(page), page["text"][:300]


@needs_engine
def test_scanned_pdf_page_comes_back_in_pdf_points(statement_png, tmp_path, engine):
    scan = str(tmp_path / "scan.pdf")
    Image.open(statement_png).convert("RGB").save(scan, resolution=300)
    page = R.read_pages(scan, engine)[0]
    assert page["source"] == engine
    assert 600 < page["width"] < 625                   # US letter = 612pt, not 2550px
    assert max(w["x1"] for w in page["words"]) <= page["width"]


def test_scan_without_any_engine_is_a_clear_error(statement_png, monkeypatch):
    monkeypatch.setattr(R, "ENGINES", {})
    with pytest.raises(R.NoOcrEngine):
        R.read_pages(statement_png)


def test_grid_cells_keep_money_exact(tmp_path):
    import datetime
    import openpyxl
    path = str(tmp_path / "l.xlsx")
    wb = openpyxl.Workbook()
    wb.active.append([datetime.date(2026, 1, 2), 1200.0, 12.5, None])
    wb.save(path)
    assert R.read_grids(path) == [[["2026-01-02", "1200", "12.5", ""]]]
