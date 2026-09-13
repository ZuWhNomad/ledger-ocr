# PyInstaller spec for LedgerOCR (one-folder). Build:  python -m PyInstaller LedgerOCR.spec
from PyInstaller.utils.hooks import collect_all

datas = [("static", "static")]
binaries = []
hiddenimports = ["ocr_pipeline"]

# pdfplumber pulls pdfminer + pypdfium2 (native .dll used for rasterization); collect
# their data/binaries so the frozen app has no missing-DLL / missing-module surprises.
for pkg in ("pdfplumber", "pypdfium2", "pypdfium2_raw", "pdfminer", "openpyxl", "pytesseract", "PIL"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "numpy.testing"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="LedgerOCR",
    console=True,          # a small window that says "running; close to stop"
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="LedgerOCR")
