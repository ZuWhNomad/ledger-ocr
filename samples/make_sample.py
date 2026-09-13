"""Generate synthetic but realistic bank-statement / general-ledger PDFs for testing.

Born-digital (text-layer) PDFs with a ruled table. Includes one deliberate
running-balance arithmetic error so reconciliation + LLM validation have
something to flag. Deterministic output (no randomness) for reproducible tests.

Usage:
    python make_sample.py            # writes bank_statement.pdf next to this file
"""
from __future__ import annotations
import os
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))

# (date, description, debit, credit) — balance is computed. One row is corrupted on purpose.
ROWS = [
    ("2026-01-02", "Opening balance", "", ""),
    ("2026-01-03", "POS PURCHASE - OFFICE DEPOT #221", "84.19", ""),
    ("2026-01-05", "ACH DEPOSIT - CLIENT ACME LLC", "", "4200.00"),
    ("2026-01-06", "CHECK 1043 - RENT", "1850.00", ""),
    ("2026-01-09", "WIRE FEE", "25.00", ""),
    ("2026-01-09", "WIRE TRANSFER - VENDOR NORTHWIND", "1320.50", ""),
    ("2026-01-12", "ACH DEPOSIT - CLIENT GLOBEX", "", "2750.00"),
    ("2026-01-14", "CARD 4471 AMAZON WEB SERVICES", "312.77", ""),
    ("2026-01-15", "INTEREST PAID", "", "3.11"),
    ("2026-01-18", "POS PURCHASE - FUEL SHELL", "62.40", ""),
    ("2026-01-20", "PAYROLL RUN JANUARY", "3900.00", ""),
    ("2026-01-22", "ACH DEPOSIT - CLIENT INITECH", "", "1500.00"),
    ("2026-01-25", "BANK SERVICE CHARGE", "18.00", ""),
    ("2026-01-28", "REFUND - OFFICE DEPOT", "", "84.19"),
    ("2026-01-30", "CHECK 1044 - UTILITIES", "236.65", ""),
]

OPENING = Decimal("5000.00")
# Row index (into ROWS) whose printed balance we corrupt to create a reconciliation error.
CORRUPT_INDEX = 7  # AWS row


def compute_rows():
    bal = OPENING
    out = []
    for i, (date, desc, deb, cred) in enumerate(ROWS):
        d = Decimal(deb) if deb else Decimal("0")
        c = Decimal(cred) if cred else Decimal("0")
        bal = bal - d + c
        printed = bal
        if i == CORRUPT_INDEX:
            printed = bal + Decimal("100.00")  # deliberate error: off by 100
        out.append((date, desc, deb, cred, f"{printed:.2f}"))
    return out


def make_pdf(path: str):
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    # header block
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, h - 0.7 * inch, "NORTHERN TRUST COMMUNITY BANK")
    c.setFont("Helvetica", 9)
    c.drawString(left, h - 0.9 * inch, "Business Checking Statement  -  Account ****3391  -  January 2026")
    c.drawString(left, h - 1.05 * inch, "Prepared for: Riverstone Bookkeeping Services")

    # column x positions (points from left)
    cols = {"date": left, "desc": left + 1.1 * inch, "debit": left + 4.6 * inch,
            "credit": left + 5.55 * inch, "balance": left + 6.5 * inch}
    right = left + 7.6 * inch
    top = h - 1.5 * inch
    rowh = 0.26 * inch

    def hline(y):
        c.setLineWidth(0.4)
        c.line(left, y, right, y)

    # header row
    c.setFont("Helvetica-Bold", 9)
    y = top
    hline(y + 0.16 * inch)
    c.drawString(cols["date"], y, "Date")
    c.drawString(cols["desc"], y, "Description")
    c.drawRightString(cols["debit"] + 0.7 * inch, y, "Debit")
    c.drawRightString(cols["credit"] + 0.7 * inch, y, "Credit")
    c.drawRightString(cols["balance"] + 0.85 * inch, y, "Balance")
    hline(y - 0.08 * inch)

    c.setFont("Helvetica", 8.5)
    for (date, desc, deb, cred, bal) in compute_rows():
        y -= rowh
        c.drawString(cols["date"], y, date)
        c.drawString(cols["desc"], y, desc)
        if deb:
            c.drawRightString(cols["debit"] + 0.7 * inch, y, deb)
        if cred:
            c.drawRightString(cols["credit"] + 0.7 * inch, y, cred)
        c.drawRightString(cols["balance"] + 0.85 * inch, y, bal)
    hline(y - 0.1 * inch)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(left, y - 0.35 * inch, "This statement is a synthetic sample generated for testing the OCR-Pipeline tool.")
    c.showPage()
    c.save()


# --- regression fixtures for silent-bug findings -----------------------------------
# These reproduce specific reviewed bugs; each turns a silent wrong/missing number into a
# visible test failure. Deterministic, no randomness.

def _simple_table(c, header, data, page_width, cols_x, amount_right):
    """Draw a Date | Description | Amount | Balance table; header optional (continuation)."""
    from reportlab.lib.pagesizes import letter
    _, h = letter
    y = h - 1.0 * inch
    if header:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(cols_x["date"], y, "Date")
        c.drawString(cols_x["desc"], y, "Description")
        c.drawRightString(amount_right, y, "Amount")
        c.drawRightString(amount_right + 1.2 * inch, y, "Balance")
        y -= 0.26 * inch
    c.setFont("Helvetica", 8.5)
    for date, desc, amt, bal in data:
        c.drawString(cols_x["date"], y, date)
        c.drawString(cols_x["desc"], y, desc)
        if amt:
            c.drawRightString(amount_right, y, amt)
        c.drawRightString(amount_right + 1.2 * inch, y, bal)
        y -= 0.26 * inch


def make_single_amount_pdf(path):
    """A single signed-amount-column statement with a deliberate running-balance typo
    (printed 999.00 where it should be 850.00). Exercises reconcile.py P1-2/P2-1."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    cols_x = {"date": left, "desc": left + 0.9 * inch}
    amount_right = left + 5.4 * inch
    rows = [("2026-02-01", "Opening balance", "0.00", "1000.00"),
            ("2026-02-02", "ACH DEPOSIT CLIENT", "200.00", "1200.00"),
            ("2026-02-03", "WIRE OUT VENDOR", "-350.00", "999.00"),   # should be 850.00
            ("2026-02-04", "CARD REFUND", "50.00", "900.00")]         # 850+50=900 (consistent)
    _simple_table(c, True, rows, w, cols_x, amount_right)
    c.showPage()
    c.save()


def make_two_page_pdf(path):
    """Two pages; the header appears ONLY on page 1. Exercises tables.py P2-5 (continuation
    pages must not be silently dropped)."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    cols_x = {"date": left, "desc": left + 0.9 * inch}
    amount_right = left + 5.4 * inch
    _simple_table(c, True, [("2026-01-02", "Opening", "0.00", "1000.00"),
                            ("2026-01-03", "Buy A", "-100.00", "900.00")], w, cols_x, amount_right)
    c.showPage()
    _simple_table(c, False, [("2026-01-04", "Buy B", "-50.00", "850.00"),
                             ("2026-01-05", "Buy C", "-25.00", "825.00")], w, cols_x, amount_right)
    c.showPage()
    c.save()


def make_bleed_pdf(path):
    """A wide description whose trailing token drifts toward the right-aligned amount column.
    Exercises tables.py P1-3 (description text must not concatenate into a giant fake
    amount: real amount is 100.00, not 1,043,100.00)."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    cols = {"date": left, "desc": left + 0.9 * inch,
            "amount": left + 5.2 * inch, "balance": left + 6.3 * inch}
    y = h - 1.0 * inch
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols["date"], y, "Date")
    c.drawString(cols["desc"], y, "Description")
    c.drawRightString(cols["amount"] + 0.6 * inch, y, "Amount")
    c.drawRightString(cols["balance"] + 0.6 * inch, y, "Balance")
    rows = [("2026-01-02", "Opening balance", "", "5000.00"),
            ("2026-01-03", "CHECK 1043 PAYMENT TO NORTHWIND TRADING COMPANY LIMITED 1043",
             "100.00", "4900.00"),
            ("2026-01-04", "ACH DEPOSIT CLIENT ACME", "200.00", "5100.00")]
    c.setFont("Helvetica", 8.5)
    for date, desc, amt, bal in rows:
        y -= 0.26 * inch
        c.drawString(cols["date"], y, date)
        c.drawString(cols["desc"], y, desc)
        if amt:
            c.drawRightString(cols["amount"] + 0.6 * inch, y, amt)
        c.drawRightString(cols["balance"] + 0.6 * inch, y, bal)
    c.showPage()
    c.save()


if __name__ == "__main__":
    out = os.path.join(HERE, "bank_statement.pdf")
    make_pdf(out)
    print("wrote", out)
