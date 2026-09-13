# Getting Started with LedgerOCR

LedgerOCR turns a bank statement or ledger (PDF, or a scan/photo) into a clean spreadsheet.
Everything happens on your own computer — your financial documents are never uploaded anywhere.

You do **not** need to install Python, use a command line, or understand any settings.

---

## 1. Install it (one time)

**If you were given `LedgerOCR-Setup.exe`:**
1. Double-click **`LedgerOCR-Setup.exe`**.
2. Click **Next** / **Install** through the short wizard.
3. When asked *"Install the smart error-checker?"* — leave it checked if you want the app to
   double-check the math on your statements (this downloads a helper the first time and takes a
   few minutes). You can safely **uncheck** it; the app still works fully.
4. Click **Finish**. LedgerOCR opens automatically.

**If you were given a folder with `INSTALL.bat` inside:**
1. Unzip the folder if it came as a `.zip` (right-click → **Extract All**).
2. Double-click **`INSTALL.bat`**.
3. A black window appears. When it asks *"Install the smart error-checker now?"*, press **Y**
   (recommended) or **N** to skip. Then wait for it to finish.
4. The app opens automatically.

A **LedgerOCR** icon is now on your Desktop and in your Start Menu.

---

## 2. Use it (every time)

1. Double-click the **LedgerOCR** icon on your Desktop.
2. A small window opens, and your web browser opens to the LedgerOCR page. (Leave the small
   window alone — it just needs to stay open while you work.)
3. **Drag a PDF, scan, or photo of a statement onto the big drop area** — or click it to pick a file.
4. In a moment you'll see the transactions in a table.
   - Rows with a math problem (the running balance doesn't add up) are **highlighted**.
5. Click **Download CSV** or **Download XLSX** to save the spreadsheet wherever you like
   (for example, your Desktop or a client folder).

That's it.

---

## 3. Finishing up

- To stop LedgerOCR, just **close the small window** that opened with it.
- To open it again later, use the **LedgerOCR** Desktop icon.

---

## Good to know

- **Nothing leaves your computer.** There is no login and no internet upload of your documents.
- **The "smart error-checker" is optional.** With it, the app also suggests *why* a row might be
  wrong (a typo, a merged transaction, etc.). Without it, the app still reads your statement and
  flags math that doesn't add up.
- **Clear scans work best.** For paper statements, a straight, high-quality scan reads far better
  than a crooked phone photo.
- **Trouble opening it?** If your browser didn't open, look for the small LedgerOCR window; it
  shows a web address like `http://127.0.0.1:8765` — type that into your browser.
