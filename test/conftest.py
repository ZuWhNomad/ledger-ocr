"""Preloaded by pytest for every test file: nothing a test does may touch real user state."""
import os
import sys
import tempfile

import pytest

os.environ["LEDGEROCR_STATE"] = tempfile.mkdtemp(prefix="ledgerocr_test_state_")

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
sys.path.insert(0, FIXTURES)   # make_sample: the synthetic-PDF builders


@pytest.fixture(scope="session")
def statement_png(tmp_path_factory):
    """The sample statement as a clean 300-dpi 'scan'."""
    import pdfplumber
    png = str(tmp_path_factory.mktemp("scan") / "statement.png")
    with pdfplumber.open(os.path.join(FIXTURES, "bank_statement.pdf")) as pdf:
        pdf.pages[0].to_image(resolution=300).original.save(png)
    return png
