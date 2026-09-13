"""Orchestration: route -> extract -> reconcile -> (optional) LLM validate -> export.

    from ocr_pipeline.pipeline import process
    result = process("statement.pdf", outdir="out", strategy="words", use_llm=True)
"""
from __future__ import annotations
import os
import re
from typing import Dict, List, Optional

from . import extract as EX
from . import tables as T
from . import reconcile as RC
from . import validate as VAL
from . import export as XP

_DATE_RE = re.compile(
    r"^\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})"
)
_MONEY_TOKEN = re.compile(r"\(?\$?-?[\d,]+\.\d{2}\)?|\(?\$?-?\d{1,3}(,\d{3})+\)?")


def parse_text_rows(text: str) -> List[Dict[str, str]]:
    """Line-based fallback for OCR'd/scanned pages: a leading date + trailing amounts.

    The last money token on the line is treated as the balance; the one before it as
    the transaction amount. Deterministic and conservative -- ambiguous lines get the
    amount only. Reconciliation later verifies whatever balances were captured.
    """
    rows: List[Dict[str, str]] = []
    for line in text.splitlines():
        if not _DATE_RE.match(line):
            if rows and line.strip() and not _MONEY_TOKEN.search(line):
                rows[-1]["description"] = (rows[-1].get("description", "") + " " + line.strip()).strip()
            continue
        dm = _DATE_RE.match(line)
        date = dm.group(1)
        rest = line[dm.end():]
        monies = [m.group(0) for m in _MONEY_TOKEN.finditer(rest)]
        desc = _MONEY_TOKEN.sub("", rest).strip(" .-\t")
        rec = {"date": date, "description": desc}
        if len(monies) >= 2:
            rec["amount"] = monies[-2]
            rec["balance"] = monies[-1]
        elif len(monies) == 1:
            rec["amount"] = monies[0]
        rows.append(rec)
    return rows


def _ocr_extract(path: str):
    """OCR extraction with graceful degradation. Returns (rows, method).

    Primary: the word-box path (Tesseract image_to_data) reconstructed with the shared
    header-anchored logic, which recovers separate debit/credit columns. Fallback: the
    plain-text line parser, used when the word-box path recovers nothing (e.g. heavy table
    borders defeat header OCR). See docs/BENCHMARK.md (OCR engine comparison).
    """
    rows = EX.ocr_to_rows(path)
    if rows:
        return rows, "ocr-words"
    return parse_text_rows(EX.ocr_to_text(path)), "ocr-textlines"


def process(path: str, outdir: Optional[str] = None, strategy: str = "words",
            use_llm: bool = False, llm_model: Optional[str] = None,
            basename: Optional[str] = None) -> Dict:
    """Run the full pipeline on one file. Returns a result dict with rows, summary, outputs."""
    if strategy not in ("words", "lines"):
        # Reject rather than silently falling through to 'lines' while the summary echoes
        # the user's (possibly typo'd) string as if it had been honored.
        return {"ok": False, "error": f"unknown strategy '{strategy}' (expected 'words' or 'lines')"}
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    ocr_method: Optional[str] = None
    if ext in EX.STRUCTURED_EXTS:
        try:
            raw = EX.extract_structured(path)
        except ImportError:
            return {"ok": False, "error": "Reading Word (.docx) files needs the free "
                    "python-docx add-on. Save the ledger as .xlsx or CSV, or install the "
                    "add-on (see the Getting Started guide)."}
        route = "structured"
        ocr_method = "table-" + ext.lstrip(".")
    else:
        scanned = EX.looks_scanned(path)
        route = "ocr" if scanned else "born-digital"

        if scanned:
            if not EX.ocr_available():
                return {"ok": False, "route": route,
                        "error": "This looks like a scan or photo, which needs the free OCR add-on "
                                 "to read. Born-digital PDFs (exported from your bank or accounting "
                                 "software) work without it. To read scans and photos, install the OCR "
                                 "add-on — see \"Reading scans and photos\" in the Getting Started guide."}
            raw, ocr_method = _ocr_extract(path)
        else:
            raw = EX.extract_tables_born_digital(path, strategy=strategy)
            # Safety net: a text layer that yields no table rows (e.g. an image table on
            # an otherwise-digital page) falls back to OCR when it is available.
            if not raw and EX.ocr_available():
                route = "born-digital->ocr-fallback"
                raw, ocr_method = _ocr_extract(path)

    rows = RC.normalize_rows(raw)
    rows, summary = RC.reconcile(rows)
    summary["route"] = route
    summary["strategy"] = ocr_method or strategy

    llm_info = {"enabled": False}
    if use_llm and summary.get("balance_mismatches"):
        llm_info = VAL.validate_flagged(rows, model=llm_model)
    summary["llm"] = llm_info

    outputs = {}
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        stem = basename or os.path.splitext(os.path.basename(path))[0]
        outputs["csv"] = XP.to_csv(rows, os.path.join(outdir, stem + ".csv"))
        try:
            outputs["xlsx"] = XP.to_xlsx(rows, os.path.join(outdir, stem + ".xlsx"))
        except Exception as e:  # openpyxl missing -> CSV still delivered
            outputs["xlsx_error"] = str(e)
        try:
            outputs["docx"] = XP.to_docx(rows, os.path.join(outdir, stem + ".docx"))
        except Exception as e:  # python-docx missing -> CSV/XLSX still delivered
            outputs["docx_error"] = str(e)

    return {"ok": True, "route": route, "summary": summary, "rows": rows, "outputs": outputs}
