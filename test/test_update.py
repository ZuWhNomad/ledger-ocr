"""The version check: never raises, never blocks, never says anything about this machine."""
import io
import json
import urllib.error
import urllib.request

import pytest

from ledger_ocr import update as U


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.delenv("LEDGEROCR_NO_UPDATE_CHECK", raising=False)   # conftest turns it off globally


def _serves(payload, seen=None):
    def fake(req, timeout=None):
        if seen is not None:
            seen.append(req)
        return io.BytesIO(json.dumps(payload).encode())
    return fake


@pytest.mark.parametrize("tag, newer", [("v0.3.0", True), ("v0.2.0", False), ("v0.1.9", False),
                                        ("v0.10.0", True), ("0.2.1", True)])
def test_compares_release_tag_with_the_running_version(monkeypatch, tag, newer):
    monkeypatch.setattr(U, "__version__", "0.2.0")
    monkeypatch.setattr(urllib.request, "urlopen", _serves({"tag_name": tag, "html_url": "https://x/r"}))
    r = U.check()
    assert r["checked"] and r["latest"] == tag and r["newer"] is newer
    assert r["current"] == "0.2.0" and r["url"] == "https://x/r"


def test_sends_nothing_about_this_machine(monkeypatch):
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", _serves({"tag_name": "v9.9.9"}, seen))
    U.check()
    req = seen[0]
    assert req.data is None                                   # a plain GET, no body
    assert req.get_method() == "GET"
    assert dict(req.header_items())["User-agent"] == "LedgerOCR"     # no version, no machine
    assert not any("token" in k.lower() or "cookie" in k.lower() for k in dict(req.header_items()))


@pytest.mark.parametrize("boom", [
    urllib.error.HTTPError("u", 404, "no release", {}, None),     # nothing published yet
    urllib.error.URLError("offline"),
    TimeoutError(),
])
def test_failures_are_silent(monkeypatch, boom):
    def raise_it(req, timeout=None):
        raise boom
    monkeypatch.setattr(urllib.request, "urlopen", raise_it)
    r = U.check()
    assert r["checked"] is False and "reason" in r and r["current"]


def test_release_without_a_tag_is_not_an_update(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _serves({}))
    assert U.check()["checked"] is False


def test_switch_stops_it_before_any_request(monkeypatch):
    monkeypatch.setenv("LEDGEROCR_NO_UPDATE_CHECK", "1")
    def explode(*a, **k):
        raise AssertionError("must not reach the network")
    monkeypatch.setattr(urllib.request, "urlopen", explode)
    r = U.check()
    assert r["checked"] is False and "off" in r["reason"]
