================================================================================
LEDGER OCR
================================================================================

WHAT IT DOES
Ledger OCR reads a document on your computer and turns it into something you can
use. Bank statements, general ledgers, and spreadsheets become clean tables (CSV,
Excel, Word), with any row whose running balance does not add up flagged.
Receipts, letters, and other documents or photos become plain text (TXT, Word).
It reads PDFs, scans, phone photos, and Excel and Word files, and it never
refuses a readable file - if a page is not a table, you get its text.

Everything runs 100% on your computer. No internet connection is needed, no
cloud service is used, and nothing is uploaded.


STATUS
Version 0.2 is a rebuild. Today it is a command-line tool; the drag-and-drop
window and the installer come back once it reads real documents reliably.


SET UP (once; needs Python 3.10 or newer)
    python -m venv .venv
    .venv\Scripts\python -m pip install -e .[extras]


HOW TO USE
    run-ledger-ocr statement.pdf photo.jpg --out results
    run-ledger-ocr --health          (what is installed, which OCR was found)
    run-ledger-ocr --help

  --mode auto    a table if the file has one, otherwise text (default)
  --mode text    always plain text
  --engine ...   auto (default), winocr, tesseract
  --json         full result on screen, for other programs


SCANS AND PHOTOS
Reading scans and photos uses the text recognition built into Windows 10 and
11 - nothing extra to install. If Tesseract OCR is also installed, both are
tried and the result whose balances add up is kept.


PRIVACY AND OFFLINE USE
- Everything runs locally on your machine.
- Safe for confidential client files.
- Works fully with no internet connection.
