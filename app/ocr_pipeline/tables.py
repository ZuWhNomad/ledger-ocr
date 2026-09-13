"""Deterministic table extraction from a born-digital PDF page.

Two strategies (A/B tested in tests/):
  * "words"  - header-anchored word-coordinate clustering (our default). Works on
               whitespace-delimited (unruled) financial tables where line-based
               detectors fail. Uses word x-coordinates only, no ML.
  * "lines"  - pdfplumber's built-in ruled-table detector (extract_tables). Good
               when the PDF has real table borders.

Both return List[List[str]] (rows of cells) so downstream code is strategy-agnostic.
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional

# Header synonyms -> canonical column name. Matched on whole words (see _canon).
HEADER_SYNONYMS: Dict[str, List[str]] = {
    "date": ["date", "posting", "trans date", "value date"],
    "description": ["description", "desc", "descr", "details", "memo", "particulars",
                    "narrative", "transaction", "reference", "payee"],
    "debit": ["debit", "withdrawal", "withdrawals", "payment", "payments", "money out", "dr", "charge"],
    "credit": ["credit", "deposit", "deposits", "money in", "cr", "receipt"],
    "balance": ["balance"],
    "amount": ["amount"],
}


def _canon(label: str) -> Optional[str]:
    """Map a header label to a canonical column, matching synonyms on WHOLE words only.

    Whole-word matching (not substring) is essential: a substring match makes the 2-letter
    'cr'/'dr' synonyms fire inside unrelated words -- e.g. 'Descr' contains 'cr' and would
    mislabel a description column as credit, corrupting every row's sign.
    """
    words = re.findall(r"[a-z0-9]+", label.strip().lower())
    if not words:
        return None
    wordset = set(words)
    for canon, syns in HEADER_SYNONYMS.items():
        for s in syns:
            parts = s.split()
            if len(parts) == 1:
                if parts[0] in wordset:
                    return canon
            elif all(p in wordset for p in parts):
                return canon
    return None


def _cluster_rows(words: List[dict], y_tol: Optional[float] = None) -> List[List[dict]]:
    """Group words into visual rows by their vertical (top) position.

    The tolerance is derived from the median word height (~0.4x) rather than a fixed
    3pt, so tight or large leading both cluster correctly.
    """
    if y_tol is None:
        heights = sorted(w["bottom"] - w["top"] for w in words)
        med = heights[len(heights) // 2] if heights else 8.0
        y_tol = max(2.0, 0.4 * med)
    rows: List[List[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        placed = False
        for row in rows:
            if abs(row[0]["top"] - w["top"]) <= y_tol:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w["x0"])
    return rows


def _find_header(rows: List[List[dict]]):
    """Return (header_row_index, {canon: (x_center, x0, x1)}) for the best header row."""
    best_i, best_map, best_score = -1, {}, 0
    for i, row in enumerate(rows):
        cmap: Dict[str, tuple] = {}
        for w in row:
            canon = _canon(w["text"])
            if canon and canon not in cmap:
                cmap[canon] = ((w["x0"] + w["x1"]) / 2, w["x0"], w["x1"])
        # need at least date + one money column to count as a real header
        score = len(cmap) + (2 if "date" in cmap else 0)
        if score > best_score and len(cmap) >= 2:
            best_i, best_map, best_score = i, cmap, score
    return best_i, best_map


def _column_bounds(header_map: Dict[str, tuple], page_width: float):
    """Turn header x-centers into [lo, hi) boundaries per column, left to right."""
    items = sorted(header_map.items(), key=lambda kv: kv[1][0])
    bounds = []
    for idx, (canon, (cx, x0, x1)) in enumerate(items):
        lo = 0 if idx == 0 else (items[idx - 1][1][0] + cx) / 2
        hi = page_width if idx == len(items) - 1 else (items[idx + 1][1][0] + cx) / 2
        bounds.append((canon, lo, hi))
    return bounds


_MONEY_COLS = ("debit", "credit", "amount", "balance")


def _degroup_money_cell(cell_words: List[dict], gap_tol: float):
    """Money columns are right-aligned, so the real number is the rightmost cluster of
    words with only normal (space-sized) gaps between them. Any word separated from that
    cluster by a large gap is leaked description text that drifted across the (approximate)
    column boundary. Return (money_words, leaked_words) split at the first large gap
    walking right-to-left. A single space-grouped number ("1 234,56") stays intact
    because its inner gaps are small; a leaked token ("... 1043   100.00") splits off.
    """
    ws = sorted(cell_words, key=lambda w: w["x0"])
    if len(ws) <= 1:
        return ws, []
    split = 0  # index where the rightmost small-gap cluster starts
    for i in range(len(ws) - 1, 0, -1):
        if ws[i]["x0"] - ws[i - 1]["x1"] > gap_tol:
            split = i
            break
    return ws[split:], ws[:split]


def extract_words_table(page, carry_bounds=None):
    """Strategy 'words': return (rows, bounds) using header-anchored clustering.

    Handles multi-line descriptions: a wrapped line (text only in the description
    column, no date/amounts) is appended to the previous row's description.

    Multi-page carry-over: `carry_bounds` are the column boundaries found on an earlier
    page. A continuation page often does NOT repeat the header; when none is found here we
    reuse the carried boundaries and treat every clustered row as data, instead of
    silently dropping the whole page (its rows would vanish from the financial record).
    Returns the boundaries used so the caller can carry them to the next page.
    """
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False,
                               extra_attrs=["size"])
    return build_rows_from_words(words, page.width, carry_bounds)


def build_rows_from_words(words, page_width, carry_bounds=None):
    """Header-anchored row reconstruction from a list of word boxes.

    Shared by the born-digital 'words' strategy (pdfplumber word coordinates) and the
    scanned-document OCR path (Tesseract image_to_data word boxes). Each word is a dict
    with text/x0/x1/top/bottom. This is the single source of truth for column anchoring,
    leaked-token de-grouping, and wrapped-description merging, so scans and born-digital
    pages share identical, tested column logic (the biggest OCR robustness win in PLAN.md).
    """
    if not words:
        return [], carry_bounds
    rows = _cluster_rows(words)
    hdr_i, hdr_map = _find_header(rows)
    if hdr_i < 0:
        if carry_bounds is None:
            return [], None
        bounds = carry_bounds        # continuation page: reuse the prior header's columns
        data_rows = rows             # no header row to skip
    else:
        bounds = _column_bounds(hdr_map, page_width)
        data_rows = rows[hdr_i + 1:]

    def assign(w) -> Optional[str]:
        mid = (w["x0"] + w["x1"]) / 2
        for canon, lo, hi in bounds:
            if lo <= mid < hi:
                return canon
        return None

    out: List[Dict[str, str]] = []
    for row in data_rows:
        cells: Dict[str, List[dict]] = {}
        for w in row:
            canon = assign(w)
            if canon:
                cells.setdefault(canon, []).append(w)
        # gap tolerance from the row's own type size: a real inter-word space is ~1 char
        # wide; a column gap is many times that. 3x median char width sits safely between.
        cw = sorted((w["x1"] - w["x0"]) / max(1, len(w["text"])) for w in row)
        gap_tol = 3.0 * (cw[len(cw) // 2] if cw else 3.0)
        # A wide description column can push text across the approximate boundary into a
        # right-aligned money column; pull those leaked tokens back into the description.
        for mc in _MONEY_COLS:
            if mc in cells and len(cells[mc]) > 1:
                money_ws, leaked = _degroup_money_cell(cells[mc], gap_tol)
                if leaked:
                    cells[mc] = money_ws
                    cells.setdefault("description", [])
                    cells["description"].extend(leaked)
        for canon in cells:
            cells[canon].sort(key=lambda w: w["x0"])
        rec = {canon: " ".join(w["text"] for w in v).strip() for canon, v in cells.items()}
        if not rec:
            continue
        has_date = bool(rec.get("date"))
        has_money = any(rec.get(k) for k in ("debit", "credit", "balance", "amount"))
        # wrapped continuation line -> merge into previous description
        if not has_date and not has_money and rec.get("description") and out:
            out[-1]["description"] = (out[-1].get("description", "") + " " + rec["description"]).strip()
            continue
        out.append(rec)
    return out, bounds


def extract_lines_table(page) -> List[Dict[str, str]]:
    """Strategy 'lines': pdfplumber ruled/text table detection, mapped to canonical keys."""
    settings_variants = [
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
        {"vertical_strategy": "text", "horizontal_strategy": "text"},
    ]
    for settings in settings_variants:
        try:
            tables = page.extract_tables(table_settings=settings)
        except Exception:
            tables = []
        for tbl in tables or []:
            recs = _table_to_records(tbl)
            if recs:
                return recs
    return []


def _table_to_records(tbl: List[List[str]]) -> List[Dict[str, str]]:
    if not tbl or len(tbl) < 2:
        return []
    # locate header row (first row with >=2 recognizable headers)
    header_idx = -1
    header_cols: List[Optional[str]] = []
    for i, r in enumerate(tbl[:10]):
        cols = [_canon((c or "")) for c in r]
        if sum(1 for c in cols if c) >= 2:
            header_idx, header_cols = i, cols
            break
    if header_idx < 0:
        return []
    out = []
    for r in tbl[header_idx + 1:]:
        rec = {}
        for canon, val in zip(header_cols, r):
            if canon and val and str(val).strip():
                rec[canon] = str(val).strip().replace("\n", " ")
        if rec:
            out.append(rec)
    return out
