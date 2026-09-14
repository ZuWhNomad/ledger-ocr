================================================================================
LEDGER OCR
================================================================================

WHAT IT DOES
Ledger OCR reads a document on your computer and turns it into something you can
use. Bank statements, general ledgers, and spreadsheets become clean, ready-to-
use tables (CSV, Excel, or Word). Receipts, letters, schoolwork, and other
documents or photos become plain text (TXT) or a Word (.docx) file. It reads
PDFs, scans, photos, and Excel and Word files, and it never refuses a file - if a
page is not a table, you get its text instead of nothing.

Everything runs 100% locally on your computer. No internet connection is
required, no cloud services are used, and nothing is uploaded. Confidential
financial data never leaves your machine.


INSTALLATION
- Run LedgerOCR-Setup.exe and click through the prompts.
- The installer creates Desktop and Start-menu shortcuts.
- No administrator rights are needed; it installs just for you.


HOW TO USE
1. Open "Ledger OCR" from the Desktop or Start menu (or double-click run.cmd).
   Your web browser opens a local page.
2. Drag a PDF, image, Excel, or Word file onto the drop area (or click to
   choose a file). Wait a few seconds.
3. Optional: use the "output" selector to choose what you get back -
   Auto-detect (recommended; a table if the file has one, otherwise text),
   Ledger table (force CSV / Excel), or Plain text (force TXT / Word).
4. For a table, a preview of the transactions appears (rows that may contain an
   error are highlighted); download it as CSV, XLSX (Excel), or DOCX (Word).
   For any other document, a text preview appears; download it as text (.txt)
   or Word (.docx). Files save to your Downloads folder.

For detailed step-by-step guidance, see GETTING_STARTED.txt.


SCANS AND PHOTOS
- PDFs exported from your bank or accounting software work out of the box.
- Scanned or photographed statements need the free OCR add-on: click
  "Install OCR add-on" in the app (one click; approve the Windows security
  prompt if it appears).


OPTIONAL ERROR-CHECKER
- An optional local assistant can double-check ONLY the rows the math already
  flagged.
- It never changes your numbers, and it runs entirely on your computer.
- It stays off unless it is installed and you turn it on.
- The app suggests a suitable local assistant automatically. To use a different
  one, click "Choose model" in the app and pick from the list; it is remembered.
- (Advanced, safe to ignore: power users can also set the model with the
  OCR_LLM_MODEL setting.)


PRIVACY AND OFFLINE USE
- Everything runs locally on your machine.
- Safe for confidential client files.
- Works fully with no internet connection.
