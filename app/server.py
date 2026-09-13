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
import ipaddress
import json
import os
import re
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import sys

from ocr_pipeline.pipeline import process
from ocr_pipeline import extract as EX
from ocr_pipeline import validate as VAL


def _base_dir():
    # When frozen by PyInstaller, bundled data lives under sys._MEIPASS.
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


HERE = _base_dir()
INDEX = os.path.join(HERE, "static", "index.html")
MAX_BYTES = 40 * 1024 * 1024
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}

# Strips absolute Windows/Unix paths out of any text before it reaches the client
# (SEC-P3-5): keep error messages plain-English, never echo local filesystem paths.
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s'\"]+|(?:/[^\s'\"/]+){2,}/?")


def _friendly_error(e: Exception) -> str:
    """Map a raw pipeline exception to a plain-English, path-free message.

    Covers the common layperson case (password-protected / corrupt PDFs) and, for
    anything else, sanitizes local paths out of the text before returning it.
    """
    name = type(e).__name__
    msg = str(e)
    low = (name + " " + msg).lower()
    if "password" in low or "encrypt" in low or "decrypt" in low:
        return ("This PDF is password-protected. Open it and remove the password "
                "(for example, re-save or \"Print to PDF\" without a password), then try again.")
    if "no /root" in low or "eof" in low or "syntaxerror" in low or "not a pdf" in low \
            or "cannot open" in low or "damaged" in low or "invalid" in low:
        return "This file could not be read — it may be corrupt or not a valid PDF/image. Try re-exporting or re-scanning it."
    safe = _PATH_RE.sub("[path]", msg).strip()
    return f"Sorry, this file could not be processed ({name}). {safe}".strip()


class Handler(BaseHTTPRequestHandler):
    # Set by serve(): the exact Host header values accepted, or None to disable the
    # check (only when the operator opted into LAN binding via --allow-lan).
    allowed_hosts = None

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet
        pass

    def _host_ok(self) -> bool:
        """Reject requests whose Host header isn't the local server (SEC-P3-1).

        Defense-in-depth against DNS-rebinding: a rebound remote name resolves to
        127.0.0.1 but still carries its own Host header, which won't be in the set.
        """
        if type(self).allowed_hosts is None:
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        return host in type(self).allowed_hosts

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, json.dumps({"error": "forbidden host"}))
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
        if not self._host_ok():
            return self._send(403, json.dumps({"error": "forbidden host"}))
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
            return self._send(200, json.dumps({"ok": False, "error": _friendly_error(e)}))


def _slim(r):
    llm = r.get("llm") or {}
    return {
        "date": r.get("date", ""), "description": r.get("description", ""),
        "debit": r.get("debit", ""), "credit": r.get("credit", ""),
        "amount": r.get("amount", ""), "balance": r.get("balance", ""),
        "flag": r.get("flag") or "",
        "llm": (llm.get("classification", "") if isinstance(llm, dict) else ""),
    }


def _is_loopback(host: str) -> bool:
    if host.lower() in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_header_allowlist(host: str, port: int):
    """The Host header values we accept. For a loopback bind, the fixed local names;
    for a LAN bind (--allow-lan) return None to disable the check (operator opted in)."""
    if not _is_loopback(host):
        return None
    names = ["127.0.0.1", "localhost", "[::1]", "::1"]
    allowed = set()
    for n in names:
        allowed.add(f"{n}:{port}")
        allowed.add(n)
    return allowed


def serve(host="127.0.0.1", port=8765, open_browser=False, allow_lan=False):
    """Start the server. port=0 picks a free port automatically."""
    srv = ThreadingHTTPServer((host, port), Handler)
    port = srv.server_address[1]  # resolve the real port (port=0 -> OS-assigned) first
    Handler.allowed_hosts = _host_header_allowlist(host, port)
    url = f"http://{host}:{port}"
    print(f"OCR-Pipeline running at {url}  (close this window to stop)")
    if not _is_loopback(host):
        print("  WARNING: bound to a non-loopback address. This service has NO "
              "authentication — anyone on your network can upload files and read results.")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--allow-lan", action="store_true",
                    help="allow binding a non-loopback address (exposes an UNAUTHENTICATED "
                         "file service to your LAN); required to bind anything but localhost")
    args = ap.parse_args()
    if not _is_loopback(args.host) and not args.allow_lan:
        ap.error(f"refusing to bind non-loopback host {args.host!r}: there is no authentication, "
                 f"so this would expose an open file-processing service to your network. "
                 f"Re-run with --allow-lan only if you understand and accept that risk.")
    serve(args.host, args.port, args.open, allow_lan=args.allow_lan)


if __name__ == "__main__":
    main()
