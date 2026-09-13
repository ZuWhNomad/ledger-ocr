from __future__ import annotations
import os
import sys
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__)) # app/tests/fixtures
TESTS_DIR = os.path.dirname(FIXTURES_DIR)                  # app/tests
APP_DIR = os.path.dirname(TESTS_DIR)                       # app
REPO_ROOT = os.path.dirname(APP_DIR)                       # F:\Ledger-OCR

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, APP_DIR)
SAMPLES_DIR = os.path.join(APP_DIR, "samples")
sys.path.insert(0, SAMPLES_DIR)

import make_sample


def make_full_grid_pdf(path: str):
    """Full-grid table WITH vertical + horizontal rules."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    right = left + 7.0 * inch
    top = h - 1.0 * inch
    rowh = 0.3 * inch

    cols = {
        "date": left,
        "desc": left + 1.1 * inch,
        "debit": left + 4.0 * inch,
        "credit": left + 5.0 * inch,
        "balance": left + 6.0 * inch,
    }

    # Grid boundaries
    xs = [left, cols["desc"], cols["debit"], cols["credit"], cols["balance"], right]

    rows_data = [
        ("2026-03-01", "Opening Balance", "", "", "1000.00"),
        ("2026-03-02", "Office Supplies Store", "150.00", "", "850.00"),
        ("2026-03-03", "Client Payment Recd", "", "500.00", "1350.00"),
        ("2026-03-04", "Monthly Internet Bill", "65.00", "", "1285.00"),
    ]

    # Draw header
    y = top
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols["date"] + 4, y - 18, "Date")
    c.drawString(cols["desc"] + 4, y - 18, "Description")
    c.drawRightString(cols["debit"] + 0.95 * inch - 4, y - 18, "Debit")
    c.drawRightString(cols["credit"] + 0.95 * inch - 4, y - 18, "Credit")
    c.drawRightString(cols["balance"] + 0.95 * inch - 4, y - 18, "Balance")

    # Horizontal lines for header
    c.setLineWidth(1.0)
    c.line(left, y, right, y)
    c.line(left, y - rowh, right, y - rowh)

    # Data rows
    c.setFont("Helvetica", 8.5)
    cur_y = y - rowh
    for date, desc, deb, cred, bal in rows_data:
        c.drawString(cols["date"] + 4, cur_y - 18, date)
        c.drawString(cols["desc"] + 4, cur_y - 18, desc)
        if deb:
            c.drawRightString(cols["debit"] + 0.95 * inch - 4, cur_y - 18, deb)
        if cred:
            c.drawRightString(cols["credit"] + 0.95 * inch - 4, cur_y - 18, cred)
        if bal:
            c.drawRightString(cols["balance"] + 0.95 * inch - 4, cur_y - 18, bal)
        cur_y -= rowh
        c.line(left, cur_y, right, cur_y)

    # Vertical lines
    for x in xs:
        c.line(x, top, x, cur_y)

    c.showPage()
    c.save()


def make_eu_format_pdf(path: str):
    """EU number formats, e.g. 1.234,56 thousands/decimal."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    right = left + 7.0 * inch
    top = h - 1.0 * inch
    rowh = 0.26 * inch

    cols = {
        "date": left,
        "desc": left + 1.1 * inch,
        "debit": left + 4.0 * inch,
        "credit": left + 5.0 * inch,
        "balance": left + 6.0 * inch,
    }

    c.setFont("Helvetica-Bold", 9)
    y = top
    c.drawString(cols["date"], y, "Date")
    c.drawString(cols["desc"], y, "Description")
    c.drawRightString(cols["debit"] + 0.9 * inch, y, "Debit")
    c.drawRightString(cols["credit"] + 0.9 * inch, y, "Credit")
    c.drawRightString(cols["balance"] + 0.9 * inch, y, "Balance")

    rows_data = [
        ("2026-04-01", "Start balance", "", "", "5.000,00"),
        ("2026-04-02", "Equipment Purchase", "1.234,56", "", "3.765,44"),
        ("2026-04-03", "EU Invoice Payment", "", "2.500,00", "6.265,44"),
        ("2026-04-04", "Software License", "300,00", "", "5.965,44"),
    ]

    c.setFont("Helvetica", 8.5)
    for date, desc, deb, cred, bal in rows_data:
        y -= rowh
        c.drawString(cols["date"], y, date)
        c.drawString(cols["desc"], y, desc)
        if deb:
            c.drawRightString(cols["debit"] + 0.9 * inch, y, deb)
        if cred:
            c.drawRightString(cols["credit"] + 0.9 * inch, y, cred)
        if bal:
            c.drawRightString(cols["balance"] + 0.9 * inch, y, bal)

    c.showPage()
    c.save()


def make_two_tables_pdf(path: str):
    """Two separate tables on one page."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    left = 0.6 * inch
    cols = {
        "date": left,
        "desc": left + 1.1 * inch,
        "amount": left + 4.5 * inch,
        "balance": left + 5.8 * inch,
    }

    # Table 1: Checking Account
    y = h - 1.0 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Account 1: Checking")
    y -= 0.25 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols["date"], y, "Date")
    c.drawString(cols["desc"], y, "Description")
    c.drawRightString(cols["amount"] + 1.0 * inch, y, "Amount")
    c.drawRightString(cols["balance"] + 1.0 * inch, y, "Balance")

    rows_1 = [
        ("2026-05-01", "Checking Start", "0.00", "2000.00"),
        ("2026-05-02", "Deposit A", "500.00", "2500.00"),
    ]

    c.setFont("Helvetica", 8.5)
    for date, desc, amt, bal in rows_1:
        y -= 0.25 * inch
        c.drawString(cols["date"], y, date)
        c.drawString(cols["desc"], y, desc)
        c.drawRightString(cols["amount"] + 1.0 * inch, y, amt)
        c.drawRightString(cols["balance"] + 1.0 * inch, y, bal)

    # Table 2: Savings Account
    y -= 0.6 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Account 2: Savings")
    y -= 0.25 * inch

    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols["date"], y, "Date")
    c.drawString(cols["desc"], y, "Description")
    c.drawRightString(cols["amount"] + 1.0 * inch, y, "Amount")
    c.drawRightString(cols["balance"] + 1.0 * inch, y, "Balance")

    rows_2 = [
        ("2026-05-01", "Savings Start", "0.00", "10000.00"),
        ("2026-05-03", "Interest Earned", "15.00", "10015.00"),
    ]

    c.setFont("Helvetica", 8.5)
    for date, desc, amt, bal in rows_2:
        y -= 0.25 * inch
        c.drawString(cols["date"], y, date)
        c.drawString(cols["desc"], y, desc)
        c.drawRightString(cols["amount"] + 1.0 * inch, y, amt)
        c.drawRightString(cols["balance"] + 1.0 * inch, y, bal)

    c.showPage()
    c.save()


FIXTURES = [
    {
        "name": "base_ruled",
        "pdf": "base_ruled.pdf",
        "csv": "base_ruled.expected.csv",
        "builder": lambda p: make_sample.make_pdf(p),
        "rows": [
            ("2026-01-02", "Opening balance", "", "", "", "5000.00", ""),
            ("2026-01-03", "POS PURCHASE - OFFICE DEPOT #221", "84.19", "", "", "4915.81", ""),
            ("2026-01-05", "ACH DEPOSIT - CLIENT ACME LLC", "", "4200.00", "", "9115.81", ""),
            ("2026-01-06", "CHECK 1043 - RENT", "1850.00", "", "", "7265.81", ""),
            ("2026-01-09", "WIRE FEE", "25.00", "", "", "7240.81", ""),
            ("2026-01-09", "WIRE TRANSFER - VENDOR NORTHWIND", "1320.50", "", "", "5920.31", ""),
            ("2026-01-12", "ACH DEPOSIT - CLIENT GLOBEX", "", "2750.00", "", "8670.31", ""),
            ("2026-01-14", "CARD 4471 AMAZON WEB SERVICES", "312.77", "", "", "8457.54", "balance mismatch: expected 8357.54, got 8457.54"),
            ("2026-01-15", "INTEREST PAID", "", "3.11", "", "8360.65", ""),
            ("2026-01-18", "POS PURCHASE - FUEL SHELL", "62.40", "", "", "8298.25", ""),
            ("2026-01-20", "PAYROLL RUN JANUARY", "3900.00", "", "", "4398.25", ""),
            ("2026-01-22", "ACH DEPOSIT - CLIENT INITECH", "", "1500.00", "", "5898.25", ""),
            ("2026-01-25", "BANK SERVICE CHARGE", "18.00", "", "", "5880.25", ""),
            ("2026-01-28", "REFUND - OFFICE DEPOT", "", "84.19", "", "5964.44", ""),
            ("2026-01-30", "CHECK 1044 - UTILITIES", "236.65", "", "", "5727.79", ""),
        ]
    },
    {
        "name": "single_amount",
        "pdf": "single_amount.pdf",
        "csv": "single_amount.expected.csv",
        "builder": lambda p: make_sample.make_single_amount_pdf(p),
        "rows": [
            ("2026-02-01", "Opening balance", "", "", "0.00", "1000.00", ""),
            ("2026-02-02", "ACH DEPOSIT CLIENT", "", "", "200.00", "1200.00", ""),
            ("2026-02-03", "WIRE OUT VENDOR", "", "", "-350.00", "999.00", "balance mismatch: expected 850.00, got 999.00"),
            ("2026-02-04", "CARD REFUND", "", "", "50.00", "900.00", ""),
        ]
    },
    {
        "name": "two_page",
        "pdf": "two_page.pdf",
        "csv": "two_page.expected.csv",
        "builder": lambda p: make_sample.make_two_page_pdf(p),
        "rows": [
            ("2026-01-02", "Opening", "", "", "0.00", "1000.00", ""),
            ("2026-01-03", "Buy A", "", "", "-100.00", "900.00", ""),
            ("2026-01-04", "Buy B", "", "", "-50.00", "850.00", ""),
            ("2026-01-05", "Buy C", "", "", "-25.00", "825.00", ""),
        ]
    },
    {
        "name": "bleed_description",
        "pdf": "bleed_description.pdf",
        "csv": "bleed_description.expected.csv",
        "builder": lambda p: make_sample.make_bleed_pdf(p),
        "rows": [
            ("2026-01-02", "Opening balance", "", "", "", "5000.00", ""),
            ("2026-01-03", "CHECK 1043 PAYMENT TO NORTHWIND TRADING COMPANY LIMITED 1043", "", "", "100.00", "4900.00", ""),
            ("2026-01-04", "ACH DEPOSIT CLIENT ACME", "", "", "200.00", "5100.00", ""),
        ]
    },
    {
        "name": "full_grid",
        "pdf": "full_grid.pdf",
        "csv": "full_grid.expected.csv",
        "builder": make_full_grid_pdf,
        "rows": [
            ("2026-03-01", "Opening Balance", "", "", "", "1000.00", ""),
            ("2026-03-02", "Office Supplies Store", "150.00", "", "", "850.00", ""),
            ("2026-03-03", "Client Payment Recd", "", "500.00", "", "1350.00", ""),
            ("2026-03-04", "Monthly Internet Bill", "65.00", "", "", "1285.00", ""),
        ]
    },
    {
        "name": "eu_format",
        "pdf": "eu_format.pdf",
        "csv": "eu_format.expected.csv",
        "builder": make_eu_format_pdf,
        "rows": [
            ("2026-04-01", "Start balance", "", "", "", "5.000,00", ""),
            ("2026-04-02", "Equipment Purchase", "1.234,56", "", "", "3.765,44", ""),
            ("2026-04-03", "EU Invoice Payment", "", "2.500,00", "", "6.265,44", ""),
            ("2026-04-04", "Software License", "300,00", "", "", "5.965,44", ""),
        ]
    },
    {
        "name": "two_tables",
        "pdf": "two_tables.pdf",
        "csv": "two_tables.expected.csv",
        "builder": make_two_tables_pdf,
        "rows": [
            ("2026-05-01", "Checking Start", "", "", "0.00", "2000.00", ""),
            ("2026-05-02", "Deposit A", "", "", "500.00", "2500.00", ""),
            ("2026-05-01", "Savings Start", "", "", "0.00", "10000.00", ""),
            ("2026-05-03", "Interest Earned", "", "", "15.00", "10015.00", ""),
        ]
    },
]


def generate_all():
    fixtures_dir = os.path.join(APP_DIR, "tests", "fixtures")
    os.makedirs(fixtures_dir, exist_ok=True)

    for item in FIXTURES:
        pdf_path = os.path.join(fixtures_dir, item["pdf"])
        csv_path = os.path.join(fixtures_dir, item["csv"])

        item["builder"](pdf_path)

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            f.write("date,description,debit,credit,amount,balance,flag\n")
            for r in item["rows"]:
                # date,description,debit,credit,amount,balance,flag
                line = ",".join(f'"{val}"' if "," in val else val for val in r)
                f.write(line + "\n")


if __name__ == "__main__":
    generate_all()
    print("Successfully generated all fixtures.")
