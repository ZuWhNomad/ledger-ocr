"""Orchestration: read -> rows -> reconcile -> export. Never rejects a readable file.

    from ledger_ocr.pipeline import process
    result = process("statement.pdf", outdir="out")

mode: "auto"  ledger table found -> CSV/XLSX/DOCX; otherwise -> plain text (TXT/DOCX)
      "table" same, stated intent (zero rows still falls back to text, never an empty CSV)
      "text"  always plain text
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional

from . import readers as R
from . import tables as T
from . import reconcile as RC
from . import export as XP

MODES = ("auto", "table", "text")


def _rows_from_pages(pages: List[Dict]) -> List[Dict[str, str]]:
    rows, carry = [], None
    for p in pages:
        page_rows, carry = T.build_rows_from_words(p["words"], p["width"], carry)
        rows.extend(page_rows)
    return rows


def _read_verified(path: str, engine: str, force_ocr: bool = False):
    """Read the file and build rows. With engine="auto" and several engines installed, the
    running-balance check is the judge: no engine is best on every page (see bench/), so each
    gets a turn until one yields rows that all reconcile; otherwise the most verified rows win.
    A PDF text layer is exact, so it is never second-guessed."""
    best = None
    for name in (R.available_engines() if engine == "auto" else []) or [engine]:
        pages = R.read_pages(path, name, force_ocr)
        rows, summary = RC.reconcile(RC.normalize_rows(_rows_from_pages(pages)))
        verified = sum(1 for r in rows if r.get("_balance") is not None and not r.get("flag"))
        # tie-break: the read that lost fewer numbers (a misread money cell parses to None)
        parsed = sum(r.get(k) is not None for r in rows for k in ("_debit", "_credit", "_amount", "_balance"))
        if best is None or (verified, parsed) > best[0]:
            best = ((verified, parsed), pages, rows, summary)
        if (rows and verified == len(rows)) or all(p["source"] == "pdf-text" for p in pages):
            break
    return best[1:]


def process(path: str, outdir: Optional[str] = None, mode: str = "auto",
            engine: str = "auto", basename: Optional[str] = None) -> Dict:
    """Run the full pipeline on one file. Returns a result dict; errors come back as
    {"ok": False, "error": ...} rather than raising, so every entry point reports them alike."""
    if mode not in MODES:
        return {"ok": False, "error": f"unknown mode '{mode}' (expected {', '.join(MODES)})"}
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return {"ok": False, "error": f"file not found: {path}"}
    rows, summary = RC.reconcile([])
    try:
        if R.ext_of(path) in R.GRID_EXTS:
            grids = R.read_grids(path)
            if mode != "text":
                rows, summary = RC.reconcile(RC.normalize_rows(
                    [rec for g in grids for rec in T.records_from_grid(g)]))
            text = "\n".join(" ".join(c for c in row if c) for g in grids for row in g if any(row))
            sources = ["grid"]
        else:
            if mode == "text":
                pages = R.read_pages(path, engine)
            else:
                pages, rows, summary = _read_verified(path, engine)
                # A text layer that yields no table (e.g. a picture of a table on an otherwise
                # digital page) gets one more chance through OCR, when an engine exists.
                if not rows and any(p["source"] == "pdf-text" for p in pages) and R.available_engines():
                    ocr = _read_verified(path, engine, force_ocr=True)
                    if ocr[1]:
                        pages, rows, summary = ocr
            text = "\n".join(p["text"] for p in pages)
            sources = sorted({p["source"] for p in pages})
    except (R.NoOcrEngine, ValueError) as e:
        return {"ok": False, "error": str(e)}

    shape = "ledger" if rows else "text"
    summary.update(sources=sources, document_shape=shape)

    outputs: Dict[str, str] = {}
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        stem = os.path.join(outdir, basename or os.path.splitext(os.path.basename(path))[0])
        if rows:
            outputs["csv"] = XP.to_csv(rows, stem + ".csv")
            optional = (("xlsx", XP.to_xlsx, rows), ("docx", XP.to_docx, rows))
        else:
            outputs["text"] = XP.to_text(text, stem + ".txt")
            optional = (("docx", XP.to_docx_text, text),)
        for kind, write, payload in optional:
            try:
                outputs[kind] = write(payload, f"{stem}.{kind}")
            except Exception as e:     # optional writer missing -> the primary output still ships
                outputs[kind + "_error"] = str(e)

    result = {"ok": True, "document_shape": shape, "summary": summary, "rows": rows, "outputs": outputs}
    if not rows:
        result["text_preview"] = text[:2000]
        result["message"] = ("Plain text extracted." if mode == "text"
                             else "No ledger table was detected, so the full text was extracted.")
    return result
