"""Headless entry: `run-ledger-ocr FILE... [--out DIR]`, or `python -m ledger_ocr`.

Exit code 0 when every file was read, 1 otherwise. `--json` prints one JSON object per file
(rows included) so another program or an agent can drive it.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from importlib import metadata, util

from . import readers as R
from .pipeline import MODES, process


def health() -> dict:
    def version(pkg):
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            return None
    return {
        "python": sys.version.split()[0],
        "ocr_engines": R.available_engines(),      # first one is what "auto" uses
        "tesseract": R._tesseract_cmd(),
        "packages": {p: version(p) for p in ("pdfplumber", "openpyxl", "pillow", "winrt-Windows.Media.Ocr",
                                             "pytesseract", "python-docx", "pillow-heif")},
        "heic": util.find_spec("pillow_heif") is not None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="run-ledger-ocr", description="Offline OCR: any document -> ledger table or text.")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--out", default=".", help="output folder (default: current folder)")
    ap.add_argument("--mode", choices=MODES, default="auto")
    ap.add_argument("--engine", choices=["auto", *R.ENGINES], default="auto")
    ap.add_argument("--json", action="store_true", help="machine-readable result on stdout")
    ap.add_argument("--health", action="store_true", help="report versions and which OCR engines were found")
    ap.add_argument("--ui", action="store_true", help="open the drag-and-drop page in the browser (default with no files)")
    ap.add_argument("--port", type=int, default=8765, help="port for --ui (0 = any free port)")
    args = ap.parse_args(argv)

    if args.health:
        print(json.dumps(health(), indent=2))
        return 0
    if args.ui or not args.files:
        from .server import serve
        serve(port=args.port)
        return 0
    failed = 0
    for f in args.files:
        r = process(f, outdir=args.out, mode=args.mode, engine=args.engine)
        failed += not r["ok"]
        if args.json:
            print(json.dumps({"file": f, **r}, default=str))
        elif not r["ok"]:
            print(f"{f}: ERROR {r['error']}", file=sys.stderr)
        else:
            s = r["summary"]
            flagged = f"{s['balance_mismatches']} flagged" if s["balance_checked"] else "balance not checked"
            what = (f"{len(r['rows'])} rows, {flagged}" if r["rows"] else
                    f"table, {len(r['grid'])} rows" if r["grid"] else "text")
            print(f"{f}: {what} [{'+'.join(s['sources'])}] -> "
                  + ", ".join(os.path.basename(p) for k, p in r["outputs"].items() if not k.endswith("_error")))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
