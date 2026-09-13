"""Tiny local server for the drag-and-drop app. Stdlib only, localhost, no auth.

    python server.py            # -> http://127.0.0.1:8765
    python server.py --port 9000 --open

The browser POSTs the raw file bytes to /api/process (filename in the X-Filename
header, options in the query string). We run the pipeline in a temp dir and return
JSON: summary, a row preview, and base64 CSV/XLSX for one-click download. Nothing
leaves this machine.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from ocr_pipeline.pipeline import process
from ocr_pipeline import extract as EX
from ocr_pipeline import validate as VAL

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "static", "index.html")
MAX_BYTES = 40 * 1024 * 1024
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(INDEX, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/env":
            return self._send(200, json.dumps({
                "ocr_available": EX.ocr_available(),
                "llm_available": VAL.available(),
                "llm_model": VAL.DEFAULT_MODEL,
            }))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/process":
            return self._send(404, json.dumps({"error": "not found"}))
        q = parse_qs(parsed.query)
        strategy = (q.get("strategy", ["words"])[0])
        use_llm = q.get("llm", ["0"])[0] in ("1", "true", "yes")
        filename = self.headers.get("X-Filename", "upload.pdf")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            return self._send(400, json.dumps({"ok": False, "error": f"unsupported file type: {ext}"}))
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_BYTES:
            return self._send(400, json.dumps({"ok": False, "error": "empty or too-large upload (max 40MB)"}))
        raw = self.rfile.read(length)
        try:
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, "input" + ext)
                with open(src, "wb") as f:
                    f.write(raw)
                out = process(src, outdir=td, strategy=strategy, use_llm=use_llm, basename="result")
                if not out.get("ok"):
                    return self._send(200, json.dumps(out))
                resp = {
                    "ok": True,
                    "filename": filename,
                    "route": out["route"],
                    "summary": out["summary"],
                    "rows": [_slim(r) for r in out["rows"]],
                }
                for kind, mime in (("csv", "text/csv"), ("xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")):
                    p = out["outputs"].get(kind)
                    if p and os.path.exists(p):
                        with open(p, "rb") as f:
                            resp[kind + "_b64"] = base64.b64encode(f.read()).decode()
                return self._send(200, json.dumps(resp))
        except Exception as e:
            return self._send(200, json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))


def _slim(r):
    llm = r.get("llm") or {}
    return {
        "date": r.get("date", ""), "description": r.get("description", ""),
        "debit": r.get("debit", ""), "credit": r.get("credit", ""),
        "amount": r.get("amount", ""), "balance": r.get("balance", ""),
        "flag": r.get("flag") or "",
        "llm": (llm.get("classification", "") if isinstance(llm, dict) else ""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"OCR-Pipeline running at {url}  (Ctrl+C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
