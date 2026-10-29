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
                    "narrative", "transaction", "reference", "payee", "name"],
    # General-ledger columns (QuickBooks: Type Date Num Name Debit Credit Balance)
    "type": ["type"],
    "num": ["num"],
    "debit": ["debit", "withdrawal", "withdrawals", "payment", "payments", "money out", "funds out",
              "dr", "charge"],
    "credit": ["credit", "deposit", "deposits", "money in", "funds in", "cr", "receipt"],
    "balance": ["balance"],
    "amount": ["amount"],
    "account": ["account"],     # an expense category column (T2125-style expense lists)
}
_TEXT_COLS = ("type", "date", "num", "description", "account")
# Pieces of a printed date: '6/07/21', '2021', 'Dec', '16,'. A date cell's words after its
# date pieces belong to the next column (a right-aligned date sits one space from the name).
_WORDY = re.compile(r"[A-Za-z]{2,}")
_MARKER = re.compile(r"\(?(CR|DR|DB|Cr|Dr)\)?\.?")   # sign markers stay with their number
_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?"
_DATE_PIECE = re.compile(r"\d[\d/.\-]*,?|" + _MONTH, re.I)
_FULL_DATE = re.compile(r"\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}")    # nothing more of the date follows
_DATE_WORD = re.compile(r"\d{1,4}[/.\-]\d{1,2}([/.\-]\d{1,4})?|" + _MONTH, re.I)   # unmistakably a date


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
        # A header one space from the previous word is one phrase: 'Funds Out', 'CR Amount'.
        cw = sorted((w["x1"] - w["x0"]) / max(1, len(w["text"])) for w in row)[len(row) // 2]
        phrases: List[dict] = []
        for w in row:
            p = phrases[-1] if phrases else None
            if p and w["x0"] - p["x1"] <= 1.5 * cw:
                phrases[-1] = dict(p, text=p["text"] + " " + w["text"], x1=w["x1"])
            else:
                phrases.append(w)
        cmap: Dict[str, tuple] = {}
        for w in phrases:
            canon = _canon(w["text"])
            if canon and canon not in cmap:
                cmap[canon] = ((w["x0"] + w["x1"]) / 2, w["x0"], w["x1"])
        # need at least date + one money column to count as a real header
        score = len(cmap) + (2 if "date" in cmap else 0)
        if score > best_score and len(cmap) >= 2:
            best_i, best_map, best_score = i, cmap, score
    return best_i, best_map


def _column_bounds(header_map: Dict[str, tuple], page_width: float):
    """Turn header x-centers into (canon, lo, hi, header left edge) per column, left to right."""
    items = sorted(header_map.items(), key=lambda kv: kv[1][0])
    bounds = []
    for idx, (canon, (cx, x0, x1)) in enumerate(items):
        lo = 0 if idx == 0 else (items[idx - 1][1][0] + cx) / 2
        hi = page_width if idx == len(items) - 1 else (items[idx + 1][1][0] + cx) / 2
        bounds.append((canon, lo, hi, x0))
    return bounds


_MONEY_COLS = ("debit", "credit", "amount", "balance")


def _text_starts(bounds, header_map, data_rows, cw):
    """Text columns are left-aligned under a header that is often centred, so a midpoint
    between header centres cuts through them (a GL's Name column starts left of 'Name').
    Move each text column's left edge to where its data actually starts: the most common
    word x0 between the previous header's centre and this header's left edge. A word votes
    when it follows a real gap ('General' in 'Receiver General' does not start a column) or a
    date (a right-aligned date sits one space from the name); a date itself never votes.
    Money columns are right-aligned and keep their midpoint bounds (a text column right of
    them still moves its own left edge). A column with no data keeps its bound."""
    xs = [round(w["x0"]) for row in data_rows for i, w in enumerate(row)
          if not _DATE_WORD.fullmatch(w["text"])
          and (i == 0 or w["x0"] - row[i - 1]["x1"] > 2 * cw or _DATE_PIECE.fullmatch(row[i - 1]["text"]))]
    out = list(bounds)
    for i in range(1, len(out)):
        canon, lo, hi, right = out[i]
        prev = out[i - 1][0]
        if canon in _MONEY_COLS:
            continue
        cands = [x for x in xs if header_map[prev][0] < x <= header_map[canon][1] + cw]
        if cands:
            start = max(set(cands), key=cands.count) - cw / 2
            out[i - 1] = (prev, out[i - 1][1], start, out[i - 1][3])
            out[i] = (canon, start, hi, right)
    return out


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
        data_rows = rows[hdr_i + 1:]
        cws = sorted((w["x1"] - w["x0"]) / max(1, len(w["text"])) for w in words)
        bounds = _text_starts(_column_bounds(hdr_map, page_width), hdr_map, data_rows, cws[len(cws) // 2])

    # Left of the money columns, words are placed by their left edge (text is left-aligned).
    # A money word goes to the rightmost money column whose header starts before the number
    # ends: numbers are right-aligned, and a header may sit left-aligned over them.
    money_lo = min((b[1] for b in bounds if b[0] in _MONEY_COLS), default=page_width)
    names = [b[0] for b in bounds]
    after_date = names[names.index("date") + 1] if "date" in names[:-1] else None
    money_starts = [(b[3], b[0]) for b in bounds if b[0] in _MONEY_COLS]

    def assign(w) -> Optional[str]:
        mid = (w["x0"] + w["x1"]) / 2
        x = mid if mid >= money_lo else w["x0"]
        for canon, lo, hi, _ in bounds:
            if lo <= x < hi:
                if canon in _MONEY_COLS:
                    return ([c for start, c in money_starts if start <= w["x1"]] or [money_starts[0][1]])[-1]
                return canon
        return None

    out: List[Dict[str, str]] = []
    for row in data_rows:
        # gap tolerance from the row's own type size: a real inter-word space is ~1 char
        # wide; a column gap is many times that. 3x median char width sits safely between.
        cw = sorted((w["x1"] - w["x0"]) / max(1, len(w["text"])) for w in row)
        cw = cw[len(cw) // 2] if cw else 1.0
        gap_tol = 3.0 * cw
        cells: Dict[str, List[dict]] = {}
        prev, prev_canon = None, None
        for w in row:
            canon = assign(w)
            # A phrase runs on across a column edge (a long GL account name, a description
            # into the money columns): a word only a space after the previous text word stays
            # in that word's column. Numbers and CR/DR markers are never part of the phrase.
            if (canon and prev_canon and canon != prev_canon and prev_canon not in _MONEY_COLS
                    and w["x0"] - prev["x1"] <= cw
                    and (canon not in _MONEY_COLS
                         or (_WORDY.search(w["text"]) and not _MARKER.fullmatch(w["text"])))):
                canon = prev_canon
            if canon:
                cells.setdefault(canon, []).append(w)
            prev, prev_canon = w, canon
        dw = cells.get("date", [])
        k = next((i for i, w in enumerate(dw) if not _DATE_PIECE.fullmatch(w["text"])
                  or (i and _FULL_DATE.fullmatch(dw[i - 1]["text"]))), len(dw))
        if 0 < k < len(dw):
            cells["date"], spill = dw[:k], dw[k:]
            cells.setdefault(after_date if after_date in _TEXT_COLS else "description", []).extend(spill)
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

def grid_from_ruled(words, vlines):
    """A printed spreadsheet: the cells are drawn, so a word's column is the gap between the
    vertical rulings (x, [(top, bottom)]) its centre falls in - exact even when cells sit one
    space apart. Text overflowing into the next cell crosses a ruling that is not drawn on that
    row, and stays in the cell it started in."""
    import bisect
    xs = [x for x, _ in vlines]
    grid = []
    for row in _cluster_rows(words) if words else []:
        y = sum((w["top"] + w["bottom"]) / 2 for w in row) / len(row)
        drawn = [any(t <= y <= b for t, b in spans) for _, spans in vlines]
        cells = [[] for _ in range(len(xs) + 1)]
        prev = None
        for w in row:
            col = bisect.bisect(xs, (w["x0"] + w["x1"]) / 2)
            if prev is not None and col > prev and not any(drawn[prev:col]):
                col = prev
            cells[col].append(w["text"])
            prev = col
        grid.append([" ".join(c) for c in cells])
    return grid


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
