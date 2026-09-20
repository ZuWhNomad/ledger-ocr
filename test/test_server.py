import json
import os
import threading
import urllib.request

import pytest

from conftest import FIXTURES
from ledger_ocr import server


@pytest.fixture(scope="module")
def url():
    ready = threading.Event()
    threading.Thread(target=server.serve, kwargs=dict(port=0, open_browser=False, ready=ready), daemon=True).start()
    assert ready.wait(5)
    return server.serve.url


def _post(url, name, data, host=None, query=""):
    req = urllib.request.Request(f"{url}/api/process{query}", data=data, method="POST",
                                 headers={"X-Filename": name, **({"Host": host} if host else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_page_and_env(url):
    assert b"Ledger" in urllib.request.urlopen(url + "/").read()
    assert "ocr_engines" in json.loads(urllib.request.urlopen(url + "/api/env").read())


def test_process_returns_rows_and_downloads(url):
    with open(os.path.join(FIXTURES, "bank_statement.pdf"), "rb") as f:
        status, d = _post(url, "statement.pdf", f.read())
    assert status == 200 and d["ok"] and d["filename"] == "statement.pdf"
    assert len(d["rows"]) == 15 and d["csv_b64"] and d["xlsx_b64"]
    assert not any(k.startswith("_") for k in d["rows"][0])


def test_non_latin1_filename_round_trips(url):
    """Header values are Latin-1 only; the page percent-encodes the name and the server decodes it."""
    from urllib.parse import quote
    with open(os.path.join(FIXTURES, "bank_statement.pdf"), "rb") as f:
        _, d = _post(url, quote("mêskanâs – relevé.pdf"), f.read())
    assert d["ok"] and d["filename"] == "mêskanâs – relevé.pdf"


def test_text_mode_and_bad_input(url):
    with open(os.path.join(FIXTURES, "bank_statement.pdf"), "rb") as f:
        _, d = _post(url, "statement.pdf", f.read(), query="?mode=text")
    assert d["ok"] and d["document_shape"] == "text" and d["text_b64"]
    assert not _post(url, "x.exe", b"MZ")[1]["ok"]


def test_foreign_host_header_is_refused(url):
    assert _post(url, "s.pdf", b"x", host="evil.example")[0] == 403
