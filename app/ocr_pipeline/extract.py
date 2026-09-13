"""PDF/image routing and text extraction.

Deterministic-first:
  * born-digital PDF  -> pdfplumber word extraction ('words') or ruled-table detection
  * scanned PDF/image -> local Tesseract OCR (only when there is no text layer)

Scan detection is per page (see looks_scanned): a PDF is treated as scanned only when NO
page carries a real text layer (the per-page MAX char count is below a threshold), so a
hybrid document with even one born-digital page still routes to deterministic extraction.
"""
from __future__ import annotations
import os
from typing import List, Dict, Optional

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
STRUCTURED_EXTS = {".xlsx", ".xlsm", ".docx"}
SCAN_CHARS_PER_PAGE = 40  # below this average -> treat as scanned


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


def extract_structured(path: str) -> List[Dict[str, str]]:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        from . import tables as T
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            rows: List[Dict[str, str]] = []
            for ws in wb.worksheets:
                grid = []
                for row in ws.iter_rows(values_only=True):
                    grid_row = []
                    for cell in row:
                        if cell is None:
                            grid_row.append("")
                        elif hasattr(cell, "strftime"):
                            grid_row.append(cell.strftime("%Y-%m-%d"))
                        elif isinstance(cell, (int, float)):
                            s = str(cell)
                            if isinstance(cell, float) and s.endswith(".0"):
                                s = s[:-2]
                            grid_row.append(s)
                        else:
                            grid_row.append(str(cell))
                    grid.append(grid_row)
                recs = T._table_to_records(grid)
                rows.extend(recs)
            return rows
        finally:
            wb.close()
    if ext == ".docx":
        import docx  # OPTIONAL — let ImportError propagate to the caller
        from . import tables as T
        d = docx.Document(path)
        rows: List[Dict[str, str]] = []
        for table in d.tables:
            grid = [[cell.text for cell in row.cells] for row in table.rows]
            recs = T._table_to_records(grid)
            rows.extend(recs)
        return rows
    return []


def pdf_page_char_counts(path: str) -> List[int]:
    """Extractable text-layer char count per page (born-digital)."""
    import pdfplumber
    counts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            counts.append(len((page.extract_text() or "")))
    return counts


def looks_scanned(path: str) -> bool:
    """True if a PDF has effectively no extractable text layer.

    Judged per page (not on the document average): a scan is flagged only when NO
    page carries a real text layer, so a hybrid PDF with even one born-digital page
    still routes to deterministic extraction (a footer/letterhead can't fake it).
    """
    if is_image(path):
        return True
    counts = pdf_page_char_counts(path)
    return not counts or max(counts) < SCAN_CHARS_PER_PAGE


def extract_tables_born_digital(path: str, strategy: str = "words") -> List[Dict[str, str]]:
    """Extract canonical dict rows from every page of a born-digital PDF.

    strategy: 'words' (header-anchored coords) or 'lines' (ruled/text tables).
    """
    from . import tables as T
    import pdfplumber
    rows: List[Dict[str, str]] = []
    with pdfplumber.open(path) as pdf:
        if strategy == "words":
            # Carry the header's column boundaries across pages so a continuation page that
            # doesn't repeat the header still yields rows instead of silently dropping them.
            carry = None
            for page in pdf.pages:
                page_rows, carry = T.extract_words_table(page, carry)
                rows.extend(page_rows)
        else:
            for page in pdf.pages:
                rows.extend(T.extract_lines_table(page))
    return rows


# ---- OCR fallback (only for scans) -------------------------------------------

def _tesseract_available() -> Optional[str]:
    """Return the tesseract binary path if usable, else None. Honors OCR_TESSERACT env."""
    try:
        import pytesseract
    except Exception:
        return None
    cand = os.environ.get("OCR_TESSERACT")
    common = [
        cand,
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
    ]
    for c in common:
        if c and os.path.isfile(c):
            pytesseract.pytesseract.tesseract_cmd = c
            return c
    # maybe on PATH
    from shutil import which
    p = which("tesseract")
    if p:
        return p
    return None


def ocr_available() -> bool:
    return _tesseract_available() is not None


_OCR_MISSING = (
    "Tesseract not found. Install it (Windows: winget install UB-Mannheim.TesseractOCR "
    "or https://github.com/UB-Mannheim/tesseract/wiki) or set OCR_TESSERACT to the exe path."
)


def _iter_page_images(path: str, dpi: int = 300):
    """Yield one PIL image per page: image files directly, PDF pages rasterized with
    pdfplumber's built-in renderer (pypdfium2, an existing dependency) -- no Poppler and
    no AGPL-licensed PyMuPDF."""
    from PIL import Image
    if is_image(path):
        yield Image.open(path)
    else:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                yield page.to_image(resolution=dpi).original


def _ocr_scope():
    """Context manager: scope pytesseract's NamedTemporaryFile writes into a dir that is
    purged on exit even on crash, so no rendered statement page lingers in %TEMP% (SEC-P3-4).
    Single-user local app: one file at a time, so the process-wide tempdir swap is safe."""
    import contextlib
    import tempfile

    @contextlib.contextmanager
    def _cm():
        with tempfile.TemporaryDirectory(prefix="ledgerocr_ocr_") as ocr_tmp:
            prev = tempfile.tempdir
            tempfile.tempdir = ocr_tmp
            try:
                yield
            finally:
                tempfile.tempdir = prev
    return _cm()


def ocr_to_text(path: str, dpi: int = 300) -> str:
    """OCR a scanned PDF or image to plain text (the textline fallback path)."""
    if not _tesseract_available():
        raise RuntimeError(_OCR_MISSING)
    import pytesseract
    texts: List[str] = []
    with _ocr_scope():
        for img in _iter_page_images(path, dpi):
            texts.append(pytesseract.image_to_string(img))
    return "\n".join(texts)


def _words_from_tsv(data: Dict) -> List[Dict]:
    """Convert a pytesseract image_to_data DICT into word boxes for header-anchored
    reconstruction (keys: text/x0/x1/top/bottom)."""
    out: List[Dict] = []
    for i in range(len(data["text"])):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        left, top, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        out.append({"text": txt, "x0": left, "x1": left + w, "top": top, "bottom": top + h})
    return out


def ocr_to_rows(path: str, dpi: int = 300) -> List[Dict[str, str]]:
    """PRIMARY scanned-document extraction: Tesseract word boxes (image_to_data, --psm 6)
    fed through the SAME header-anchored reconstruction used for born-digital pages
    (tables.build_rows_from_words). Unlike the plain-text path this recovers separate
    debit/credit columns and keeps wide descriptions out of the money cells -- a large
    accuracy win on scans (see docs/BENCHMARK.md, OCR engine comparison: F1 0.94 vs 0.54).

    Column boundaries carry across pages so continuation pages without a repeated header
    still yield rows. Returns [] when nothing is recovered (e.g. heavy table borders defeat
    header OCR under --psm 6) so the caller can fall back to the text-line parser."""
    if not _tesseract_available():
        raise RuntimeError(_OCR_MISSING)
    import pytesseract
    from . import tables as T
    rows: List[Dict[str, str]] = []
    carry = None
    with _ocr_scope():
        for img in _iter_page_images(path, dpi):
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 6")
            page_rows, carry = T.build_rows_from_words(_words_from_tsv(data), img.width, carry)
            rows.extend(page_rows)
    return rows
