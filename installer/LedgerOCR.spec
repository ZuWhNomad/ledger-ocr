# PyInstaller spec (one-folder). Build:  python -m PyInstaller installer\LedgerOCR.spec
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_dynamic_libs

ROOT = os.path.dirname(SPECPATH)
PKG = os.path.join(ROOT, "ledger_ocr")

datas = [(os.path.join(PKG, "static"), os.path.join("ledger_ocr", "static"))]
binaries = []
hiddenimports = ["ledger_ocr"]

# winrt-* is a namespace package of native modules (Windows OCR): collect every submodule + pyd.
hiddenimports += collect_submodules("winrt")
binaries += collect_dynamic_libs("winrt")

for pkg in ("pdfplumber", "pypdfium2", "pypdfium2_raw", "pdfminer", "openpyxl", "PIL",
            "pytesseract", "docx", "pillow_heif"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pandas", "numpy", "pytest", "reportlab"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LedgerOCR",
          console=True,          # the small window that says "running; close to stop"
          icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="LedgerOCR")
