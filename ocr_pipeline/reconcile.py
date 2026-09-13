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


def _to_canonical(t: str) -> Optional[str]:
    """Resolve US/EU thousands & decimal separators to a plain Python decimal string.

    Rules (both US '1,234.56' and EU '1.234,56' parse exactly):
      * Both separators present -> the one that appears LAST is the decimal separator;
        the other is the thousands separator.
      * Only one separator kind present -> it is a thousands separator when it repeats
        (e.g. '1.000.000', '1,234,567') or when a single occurrence groups the number
        into a 3-digit trailing group ('5,000', '12,345', '1.234' EU); otherwise it is a
        decimal separator ('84.19', '1,50', '1234,5').
    Returns None if the grouping is internally inconsistent (e.g. two glued numbers).
    """
    has_comma, has_dot = "," in t, "." in t
    if has_comma and has_dot:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        thou = "." if dec == "," else ","
        int_part, _, frac = t.partition(dec) if t.count(dec) == 1 else (None, None, None)
        if int_part is None:  # decimal separator can't appear twice
            return None
        if not _valid_groups(int_part, thou):
            return None
        return int_part.replace(thou, "") + ("." + frac if frac != "" else "")
    sep = "," if has_comma else ("." if has_dot else None)
    if sep is None:
        return t  # plain integer
    parts = t.split(sep)
    # thousands if it repeats, or a single split into a clean 3-digit trailing group
    if len(parts) > 2:
        if not all(len(p) == 3 for p in parts[1:]) or not (1 <= len(parts[0]) <= 3):
            return None
        return "".join(parts)
    left, right = parts
    if len(right) == 3 and left.isdigit() and 1 <= len(left) <= 3:
        return left + right          # single thousands group: 5,000 / 1.234 -> 5000 / 1234
    return left + "." + right        # decimal: 84.19 / 1,50 -> 84.19 / 1.50


def _valid_groups(int_part: str, thou: str) -> bool:
    """True if int_part is a valid thousands-grouped integer for separator `thou`."""
    if thou not in int_part:
        return True
    groups = int_part.split(thou)
    return all(len(g) == 3 for g in groups[1:]) and 1 <= len(groups[0]) <= 3


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
    # Keep digits / separators / spaces / minus; drop currency, letters (CR/DR/USD)
    # and stray marks. Spaces are kept for now so we can tell an EU space-thousands
    # separator ("1 234,56") from two glued number tokens ("1043 100.00").
    core = re.sub(r"[^\d.,\s\-]", "", t).strip()
    tokens = core.split()
    if len(tokens) > 1:
        # A money cell must be a SINGLE number. Multiple whitespace-separated tokens are
        # a valid number only if they are space-grouped thousands (first group 1-3 digits,
        # every later group exactly 3 digits, last group may carry a ,dd / .dd decimal).
        # Anything else (a description token leaked into the money column, a footnote) is
        # rejected rather than glued into one giant fake amount.
        first = tokens[0].lstrip("-")
        if not (first.isdigit() and 1 <= len(first) <= 3):
            return None
        for g in tokens[1:-1]:
            if not (g.isdigit() and len(g) == 3):
                return None
        if not re.fullmatch(r"\d{3}([.,]\d+)?", tokens[-1]):
            return None
    t = core.replace(" ", "")
    if t.endswith("-"):  # trailing minus
        neg = True
        t = t[:-1]
    if t.startswith("-"):
        neg = True
        t = t[1:]
    if not re.search(r"\d", t):
        return None
    t = _to_canonical(t)
    if t is None:
        return None
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
    """Balance change for a row. sign=+1: debit raises; sign=-1: debit lowers.

    For a single signed-amount column the value is multiplied by `sign` too, so the sign
    vote can actually pick a convention (amount raises vs lowers the balance) instead of
    tying and giving up — a signed column reconciles, and a real balance typo is flagged.
    """
    d, c, a = rec.get("_debit"), rec.get("_credit"), rec.get("_amount")
    if d is None and c is None and a is not None:
        return sign * a  # single signed amount column
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

    # Does the statement carry debit/credit columns, or a single (signed) amount column?
    uses_dc = any(r.get("_debit") is not None or r.get("_credit") is not None for r in rows)
    amount_only = (not uses_dc) and any(r.get("_amount") is not None for r in with_bal)

    v_pos, v_neg = _fit_score(with_bal, 1), _fit_score(with_bal, -1)
    if amount_only:
        # No debit/credit means no sign convention to vote on -- the sign lives in the
        # amount itself. Pick whichever direction fits best (handles both a truly signed
        # column and an unsigned magnitude register) and always reconcile, so a running-
        # balance typo on this statement shape is flagged instead of silently passing.
        sign = 1 if v_pos >= v_neg else -1
        convention = "single_amount_column"
    elif max(v_pos, v_neg) < 2 or v_pos == v_neg:
        # For debit/credit statements, require a strict majority and >=2 votes, else
        # 'unknown' -> skip reconciliation rather than guess.
        sign = 0  # unknown
        convention = "unknown"
    else:
        sign = 1 if v_pos > v_neg else -1
        convention = "debit_lowers_balance" if sign == -1 else "debit_raises_balance"

    flags = 0
    comparisons = 0
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
            if bal is not None:
                comparisons += 1
                if abs(expected - bal) > TOL:
                    rec["flag"] = f"balance mismatch: expected {expected:.2f}, got {bal:.2f}"
                    flags += 1

    # Distinguish "reconciled clean" (0 mismatches over real comparisons) from "could not
    # check" (no balance column, or an ambiguous sign convention): a bare 0 is misleading.
    checked = comparisons > 0
    summary = {
        "rows": len(rows),
        "rows_with_balance": len(with_bal),
        "sign_convention": convention,
        "balance_checked": checked,
        "balance_mismatches": flags if checked else None,
    }
    return rows, summary
