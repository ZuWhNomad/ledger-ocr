"""Is a newer LedgerOCR published? The ONLY network call in this package.

One unauthenticated GET to the GitHub releases API. Nothing about the machine, the user or any
document is sent -- not even the installed version. It never raises, never blocks startup (the
UI runs it in a background thread), and is skipped entirely when LEDGEROCR_NO_UPDATE_CHECK is
set, so the app still works with no internet at all.
"""
from __future__ import annotations
import json
import os
import re
import urllib.request

from . import __version__

RELEASES_API = "https://api.github.com/repos/ZuWhNomad/ledger-ocr/releases/latest"
RELEASES_PAGE = "https://github.com/ZuWhNomad/ledger-ocr/releases/latest"
TIMEOUT = 4.0


def _parts(version: str):
    """'v1.2.10' -> (1, 2, 10). Compared as numbers, so 0.10 beats 0.9."""
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3]) or (0,)


def check(url: str = RELEASES_API, timeout: float = TIMEOUT) -> dict:
    """{"current", "checked", and when checked: "latest", "newer", "url"}. Never raises."""
    out = {"current": __version__, "checked": False}
    if os.environ.get("LEDGEROCR_NO_UPDATE_CHECK"):
        out["reason"] = "update check turned off"
        return out
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "LedgerOCR"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            release = json.load(response)
        latest = str(release.get("tag_name") or "").strip()
        if not latest:
            out["reason"] = "no release published yet"
            return out
        out.update(checked=True, latest=latest, newer=_parts(latest) > _parts(__version__),
                   url=str(release.get("html_url") or RELEASES_PAGE))
    except Exception as e:      # offline, rate-limited, no release, bad JSON: all the same here
        out["reason"] = f"could not check ({type(e).__name__})"
    return out
