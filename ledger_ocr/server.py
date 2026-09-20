"""Local web UI: a drag-and-drop page in the browser, served on 127.0.0.1 only.

    run-ledger-ocr --ui            (or double-click LedgerOCR.exe)

The page POSTs the file's bytes to /api/process (name in the X-Filename header, ?mode= and
?engine= as on the CLI) and gets back the same result as `pipeline.process` plus each output
file base64-encoded, so the browser can save them. Nothing is written outside a temp folder
that is deleted after every request. No authentication: therefore loopback only, and the Host
header must name this server (defence against DNS rebinding from a hostile web page).
"""
from __future__ import annotations
import base64
import json
import os
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import readers as R
from .pipeline import MODES, process

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
MAX_BYTES = 100 * 1024 * 1024
MIME = {"csv": "text/csv", "text": "text/plain",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def env() -> dict:
    return {"ocr_engines": R.available_engines(), "modes": list(MODES), "version": _version()}


def _version() -> str:
    from importlib import metadata
    try:
        return metadata.version("ledger-ocr")
    except metadata.PackageNotFoundError:
        return "dev"


class Handler(BaseHTTPRequestHandler):
    allowed_hosts: set = set()

    def log_message(self, *a):   # quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self) -> bool:
        return (self.headers.get("Host") or "").strip().lower() in self.allowed_hosts

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden host"})
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(INDEX, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/env":
            return self._send(200, env())
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden host"})
        parsed = urlparse(self.path)
        if parsed.path != "/api/process":
            return self._send(404, {"error": "not found"})
        q = parse_qs(parsed.query)
        filename = os.path.basename(unquote(self.headers.get("X-Filename", "upload")))  # percent-encoded by the page
        ext = os.path.splitext(filename)[1].lower()
        if ext not in R.IMAGE_EXTS | R.GRID_EXTS | {".pdf"}:
            return self._send(200, {"ok": False, "error": f"Unsupported file type '{ext}'. "
                              "Supported: PDF, images (PNG, JPG, HEIC, TIFF, BMP, WEBP, GIF), XLSX, XLSM, DOCX."})
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_BYTES:
            return self._send(200, {"ok": False, "error": "empty or too-large upload (max 100 MB)"})
        raw = self.rfile.read(length)
        try:
            with tempfile.TemporaryDirectory(prefix="ledgerocr_ui_") as td:
                src = os.path.join(td, "input" + ext)
                with open(src, "wb") as f:
                    f.write(raw)
                out = process(src, outdir=td, mode=q.get("mode", ["auto"])[0],
                              engine=q.get("engine", ["auto"])[0], basename="result")
                if out["ok"]:
                    out["filename"] = filename
                    out["rows"] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in out["rows"]]
                    for kind, path in list(out["outputs"].items()):
                        if kind in MIME:
                            with open(path, "rb") as f:
                                out[kind + "_b64"] = base64.b64encode(f.read()).decode()
                    out["outputs"] = {k: os.path.basename(v) for k, v in out["outputs"].items()}
                return self._send(200, out)
        except Exception as e:
            return self._send(200, {"ok": False, "error": f"{type(e).__name__}: {e}"})


def serve(port: int = 8765, open_browser: bool = True, ready: threading.Event | None = None) -> None:
    """Serve on 127.0.0.1; port 0 = pick a free one. `ready` is set (with `serve.url`) once bound."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    port = srv.server_address[1]
    Handler.allowed_hosts = {f"{h}{p}" for h in ("127.0.0.1", "localhost") for p in ("", f":{port}")}
    serve.url = f"http://127.0.0.1:{port}"
    print(f"Ledger OCR is running at {serve.url}  (close this window to stop)")
    if ready:
        ready.set()
    if open_browser:
        webbrowser.open(serve.url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
