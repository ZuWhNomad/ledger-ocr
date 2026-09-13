================================================================================
LEDGER OCR
================================================================================

WHAT IT DOES
Ledger OCR converts bank-statement and general-ledger PDFs, scans, and photos
into clean spreadsheets (CSV and Excel .xlsx).

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
2. Drag a PDF or image onto the drop area (or click to choose a file). Wait a
   few seconds.
3. A table preview of the transactions appears. Rows the tool thinks may
   contain an error are highlighted.
4. Click "Download CSV" or "Download XLSX". The file saves to your Downloads
   folder. Open it in Excel or Google Sheets.

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
- (Advanced, safe to ignore: power users can change which local model it uses
  via the OCR_LLM_MODEL setting.)


PRIVACY AND OFFLINE USE
- Everything runs locally on your machine.
- Safe for confidential client files.
- Works fully with no internet connection.
