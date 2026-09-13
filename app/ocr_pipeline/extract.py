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
SCAN_CHARS_PER_PAGE = 40  # below this average -> treat as scanned


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


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


def ocr_to_text(path: str, dpi: int = 300) -> str:
    """OCR a scanned PDF or image locally.

    PDF pages are rasterized with pdfplumber's built-in renderer (pypdfium2, an
    existing dependency) -- no Poppler, and no extra AGPL-licensed PyMuPDF dependency.
    """
    tpath = _tesseract_available()
    if not tpath:
        raise RuntimeError(
            "Tesseract not found. Install it (Windows: winget install UB-Mannheim.TesseractOCR "
            "or https://github.com/UB-Mannheim/tesseract/wiki) or set OCR_TESSERACT to the exe path."
        )
    import pytesseract
    import tempfile
    from PIL import Image
    texts: List[str] = []
    # SEC-P3-4: pytesseract writes each page image to a NamedTemporaryFile in the OS
    # temp dir before shelling out to tesseract. Point tempfile at a scoped dir that is
    # purged on exit (even on crash) so no rendered statement page lingers in %TEMP%.
    # (Single-user local app: one file processed at a time, so the process-wide swap is safe.)
    with tempfile.TemporaryDirectory(prefix="ledgerocr_ocr_") as ocr_tmp:
        prev_tmp = tempfile.tempdir
        tempfile.tempdir = ocr_tmp
        try:
            if is_image(path):
                texts.append(pytesseract.image_to_string(Image.open(path)))
            else:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        img = page.to_image(resolution=dpi).original  # PIL image via pypdfium2
                        texts.append(pytesseract.image_to_string(img))
        finally:
            tempfile.tempdir = prev_tmp
    return "\n".join(texts)
