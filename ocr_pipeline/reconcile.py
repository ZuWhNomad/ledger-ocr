"""Normalize extracted rows and reconcile running balances deterministically.

For every row with a printed balance we check that
    prev_balance  (+/-) delta  == printed_balance
and flag rows where it does not (within a small tolerance). The debit/credit sign
convention is auto-detected by whichever fits the statement best, so the same code
works for bank statements (debit lowers balance) and asset-side ledgers.
"""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Tuple

TOL = Decimal("0.02")
_DATE_LIKE = re.compile(
    r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s*[A-Za-z]{3,9}\s*\d{0,4}|[A-Za-z]{3,9}\s+\d{1,2}")


def _date_like(s) -> bool:
    return bool(s) and bool(_DATE_LIKE.search(str(s)))


import unicodedata

_CURRENCY = "$€£¥₹"


def parse_money(s: Optional[str]) -> Optional[Decimal]:
    """Parse a money cell to Decimal, or None. Handles US and EU thousands/decimal
    conventions, parentheses / trailing / unicode-minus negatives, currency symbols,
    and trailing DR/CR markers. Uses Decimal throughout (never float)."""
    if s is None:
        return None
    t = unicodedata.normalize("NFKC", str(s)).strip()
    if not t or t in ("-", "—", "N/A", "n/a", "NA"):
        return None
    # unicode minus / dashes -> ascii '-'
    t = t.replace("−", "-").replace("–", "-").replace("—", "-")
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    up = t.upper()
    if re.search(r"\bDR\b|DR$|DB$", up):
        neg = True
    # strip currency, spaces, letters (CR/DR/USD), stray footnote marks
    t = re.sub(r"[^\d.,\-]", "", t.replace(",", ",")).strip()
    for ch in _CURRENCY:
        t = t.replace(ch, "")
    if t.endswith("-"):  # trailing minus
        neg = True
        t = t[:-1]
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if not re.search(r"\d", t):
        return None
    # locale from the LAST separator: last ',' => EU decimal comma; last '.' => US
    last_comma, last_dot = t.rfind(","), t.rfind(".")
    if last_comma > last_dot:            # EU: 1.234,56  or  1 234,56
        t = t.replace(".", "").replace(",", ".")
    else:                                # US: 1,234.56  (Indian 1,23,456.78)
        t = t.replace(",", "")
    try:
        val = Decimal(t)
    except InvalidOperation:
        return None
    return -val if neg else val


def normalize_rows(raw: List[Dict[str, str]]) -> List[Dict]:
    """Attach parsed Decimal fields; keep original strings. Drops junk (no date, no money)."""
    out = []
    for r in raw:
        rec = dict(r)
        rec["_debit"] = parse_money(r.get("debit"))
        rec["_credit"] = parse_money(r.get("credit"))
        rec["_balance"] = parse_money(r.get("balance"))
        rec["_amount"] = parse_money(r.get("amount"))
        has_money = any(rec[k] is not None for k in ("_debit", "_credit", "_balance", "_amount"))
        if not _date_like(r.get("date")) and not has_money:
            continue  # footnotes / stray text (first column isn't a date and no numbers)
        out.append(rec)
    return out


def _delta(rec: Dict, sign: int) -> Optional[Decimal]:
    """Balance change for a row. sign=+1: debit raises; sign=-1: debit lowers."""
    d, c, a = rec.get("_debit"), rec.get("_credit"), rec.get("_amount")
    if d is None and c is None and a is not None:
        return a  # single signed amount column
    if d is None and c is None:
        return None
    return sign * ((d or Decimal(0)) - (c or Decimal(0)))


def _fit_score(rows: List[Dict], sign: int) -> int:
    """How many consecutive (prev,cur) balance pairs are explained by this sign."""
    score, prev = 0, None
    for rec in rows:
        bal = rec.get("_balance")
        if bal is None:
            continue
        if prev is not None:
            delta = _delta(rec, sign)
            if delta is not None and abs((prev + delta) - bal) <= TOL:
                score += 1
        prev = bal
    return score


def reconcile(rows: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Flag rows whose running balance does not follow. Returns (rows, summary).

    Uses a pure cumulative series anchored on the first printed balance and driven by
    the per-row amounts, rather than chaining printed balances. That way a single
    corrupted/typo'd printed balance is flagged on exactly one row instead of two, while
    a wrong amount or a missing row still cascades from the break point (informative).
    """
    for rec in rows:
        rec["flag"] = None
    with_bal = [r for r in rows if r.get("_balance") is not None]

    # Vote for the sign convention on consecutive printed balances; require a strict
    # majority and >=2 votes, else 'unknown' -> skip reconciliation rather than guess.
    v_pos, v_neg = _fit_score(with_bal, 1), _fit_score(with_bal, -1)
    if max(v_pos, v_neg) < 2 or v_pos == v_neg:
        sign = 0  # unknown
        convention = "unknown"
    else:
        sign = 1 if v_pos > v_neg else -1
        convention = "debit_lowers_balance" if sign == -1 else "debit_raises_balance"

    flags = 0
    if sign != 0:
        anchored = False
        expected: Optional[Decimal] = None
        for rec in rows:
            bal = rec.get("_balance")
            if not anchored:
                if bal is not None:
                    expected, anchored = bal, True  # anchor on first printed balance
                continue
            expected = expected + (_delta(rec, sign) or Decimal(0))
            if bal is not None and abs(expected - bal) > TOL:
                rec["flag"] = f"balance mismatch: expected {expected:.2f}, got {bal:.2f}"
                flags += 1

    summary = {
        "rows": len(rows),
        "rows_with_balance": len(with_bal),
        "sign_convention": convention,
        "balance_mismatches": flags,
    }
    return rows, summary
