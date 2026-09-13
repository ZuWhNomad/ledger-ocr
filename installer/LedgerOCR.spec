# PyInstaller spec for LedgerOCR (one-folder). Build:  python -m PyInstaller installer\LedgerOCR.spec
import os
from PyInstaller.utils.hooks import collect_all

# This spec lives in installer/; the app source lives in ../app. Resolve paths from the
# spec's own location (SPECPATH) so the build works regardless of the current directory.
APP = os.path.join(os.path.dirname(SPECPATH), "app")

datas = [(os.path.join(APP, "static"), "static")]
binaries = []
hiddenimports = ["ocr_pipeline"]

# pdfplumber pulls pdfminer + pypdfium2 (native .dll used for rasterization); collect
# their data/binaries so the frozen app has no missing-DLL / missing-module surprises.
# `requests` (+ its certifi CA bundle) is required for the optional local-Ollama error-check
# and the model sweep: it is imported lazily and swallowed on ImportError, so without it the
# FROZEN app would silently report the LLM as unavailable even when Ollama is running.
for pkg in ("pdfplumber", "pypdfium2", "pypdfium2_raw", "pdfminer", "openpyxl", "pytesseract",
            "PIL", "requests", "certifi", "urllib3", "charset_normalizer", "idna"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    [os.path.join(APP, "run_app.py")],
    pathex=[APP],
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
