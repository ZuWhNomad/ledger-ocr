"""Deterministic ledger-table reconstruction. No ML, and no knowledge of where words came from.

  * build_rows_from_words - header-anchored clustering of word boxes (text/x0/x1/top/bottom)
                            from ANY source: a PDF text layer or an OCR engine.
  * records_from_grid     - the same header mapping for an already-gridded source (xlsx/docx).

Both return List[Dict[canonical column -> str]].
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


def build_rows_from_words(words, page_width, carry_bounds=None):
    """Header-anchored row reconstruction from a list of word boxes. Returns (rows, bounds).

    Each word is a dict with text/x0/x1/top/bottom. This is the single source of truth for
    column anchoring, leaked-token de-grouping, and wrapped-description merging (a line with
    text only in the description column is appended to the previous row), so scans and
    born-digital pages share identical, tested column logic.

    Multi-page carry-over: `carry_bounds` are the column boundaries found on an earlier
    page. A continuation page often does NOT repeat the header; when none is found here we
    reuse the carried boundaries and treat every clustered row as data, instead of
    silently dropping the whole page (its rows would vanish from the financial record).
    Returns the boundaries used so the caller can carry them to the next page.
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


def records_from_grid(tbl: List[List[str]]) -> List[Dict[str, str]]:
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


# ---- generic tables (no ledger header) -------------------------------------------------------

def grid_from_words(words, page_width, min_rows: int = 3):
    """Any table, without knowing its headers: columns are the vertical white gaps that run
    through the rows. Returns a grid of cell strings, or [] when the page does not look tabular
    (fewer than `min_rows` rows with two or more cells). Column choice: a 1pt bin is a
    separator when at most a quarter of the rows spanning it have ink there; separators
    narrower than three character widths are ignored (those are plain word spaces)."""
    if not words:
        return []
    rows = _cluster_rows(words)
    cw = sorted((w["x1"] - w["x0"]) / max(1, len(w["text"])) for w in words)
    min_gap = 3.0 * cw[len(cw) // 2]
    width = int(page_width) + 1
    spanning = [0] * width      # rows with ink on both sides of this x
    inked = [0] * width         # of those, rows with ink AT this x
    for row in rows:
        lo, hi = min(w["x0"] for w in row), max(w["x1"] for w in row)
        for x in range(max(0, int(lo)), min(width, int(hi) + 1)):
            spanning[x] += 1
        for w in row:
            for x in range(max(0, int(w["x0"])), min(width, int(w["x1"]) + 1)):
                inked[x] += 1
    seps, start = [], None
    for x in range(width + 1):
        empty = x < width and spanning[x] >= 2 and inked[x] <= 0.25 * spanning[x]
        if empty and start is None:
            start = x
        elif not empty and start is not None:
            if x - start >= min_gap:
                seps.append((start + x) / 2)
            start = None
    if not seps:
        return []
    grid = []
    for row in rows:
        cells = [[] for _ in range(len(seps) + 1)]
        for w in row:
            mid = (w["x0"] + w["x1"]) / 2
            cells[sum(mid > s for s in seps)].append(w["text"])
        grid.append([" ".join(c) for c in cells])
    if sum(1 for r in grid if sum(bool(c) for c in r) >= 2) < min_rows:
        return []
    return grid


_PAIR = re.compile(r"([A-Za-z][A-Za-z .#/'-]{0,28}?)\s*(?<!\d)[:•](?!\d)\s*(.+?)(?=\s+[A-Za-z][A-Za-z .#/'-]{0,28}?\s*(?<!\d)[:•](?!\d)\s|$)")


def pairs_from_text(text: str, min_pairs: int = 3):
    """'Label: value' pairs from free text (a receipt, a form, a slip): a two-column grid, or []
    when fewer than `min_pairs` are found. A colon between digits (10:00) is a time, not a pair."""
    grid = [["field", "value"]]
    for line in text.splitlines():
        for m in _PAIR.finditer(line.strip()):
            label, value = m.group(1).strip(" .-"), m.group(2).strip(" .:•-")
            if label and value:
                grid.append([label, value])
    return grid if len(grid) > min_pairs else []
