================================================================================
LEDGER OCR
================================================================================

WHAT IT DOES
Ledger OCR reads a document on your computer and turns it into something you can
use. Bank statements and general ledgers become clean tables (CSV, Excel, Word),
with any row whose running balance does not add up flagged. Other tables (a tax
slip, an invoice, a price list) and receipts or forms with "Label: value" lines
become a spreadsheet (CSV, Excel). Everything else becomes text (TXT, Word).
It reads PDFs, scans, phone photos, and Excel and Word files, and it never
refuses a readable file - if a page is not a table, you get its text.

Everything runs 100% on your computer. No internet connection is needed, no
cloud service is used, and nothing is uploaded.


INSTALL
- Run LedgerOCR-Setup.exe and click through. No administrator rights needed.
- Windows may show a blue "protected your PC" screen because the installer is
  not yet signed: click "More info", then "Run anyway".


HOW TO USE
1. Open "Ledger OCR" from the Desktop or Start menu. A small black window
   appears (leave it open - closing it stops the app) and your browser opens
   the Ledger OCR page.
2. Drag one or more files onto the drop area, or click it to choose.
3. Each file gets its own panel: a table with any suspect row highlighted, or
   a text preview. Click Download CSV / XLSX / DOCX / TXT. Files save to your
   Downloads folder.
4. "output" lets you force a table or plain text instead of auto-detecting.


FROM THE COMMAND LINE (optional)
    LedgerOCR.exe statement.pdf photo.jpg --out results
    LedgerOCR.exe --health          (what is installed, which OCR was found)
    LedgerOCR.exe --help
  --mode auto|table|text   --engine auto|winocr|tesseract   --json


FROM SOURCE (developers; Python 3.10+)
    python -m venv .venv
    .venv\Scripts\python -m pip install -e .[dev]
    run-ledger-ocr.cmd                      (or: .venv\Scripts\python -m pytest)
    powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1


SCANS AND PHOTOS
Reading scans and photos uses the text recognition built into Windows 10 and
11 - nothing extra to install. If Tesseract OCR is also installed, both are
tried and the result whose balances add up is kept.


PRIVACY AND OFFLINE USE
- Your documents are read on this machine only. Nothing about them is ever sent
  anywhere, and no cloud OCR or cloud AI is used.
- Safe for confidential client files.
- Works fully with no internet connection.
- The one thing that touches the internet: at start-up the app asks GitHub
  whether a newer version has been released, so it can show a "new version
  available" link. It sends nothing at all - not your version, not your name,
  not a word about your files - and it gives up quietly when offline. To switch
  it off, set the environment variable LEDGEROCR_NO_UPDATE_CHECK=1.
