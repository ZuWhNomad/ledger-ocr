"""Optional local-LLM error checking (Ollama). VALIDATION ONLY -- never extraction.

Only rows already flagged by deterministic reconciliation (or garbled-looking OCR
rows) are sent to the model. The model classifies the likely problem; it is never
allowed to rewrite numbers. Fully optional and non-blocking: if Ollama is down or
slow, the pipeline continues and rows keep their deterministic flags.
"""
from __future__ import annotations
import json
import os
from typing import List, Dict, Optional

# Light model by default (small cold-start); override with OCR_LLM_MODEL.
DEFAULT_MODEL = os.environ.get("OCR_LLM_MODEL", "qwen2.5:3b")
DEFAULT_URL = "http://127.0.0.1:11434/api/generate"

_SYS = (
    "You are an audit assistant. You are given a suspicious row from a bank statement or "
    "general ledger, plus the rows immediately before and after it, and a deterministic "
    "finding. Classify the most likely cause. You MUST NOT invent or correct any numbers. "
    'Reply with ONLY compact JSON: {"classification": one of '
    '["ocr_misread","merged_transaction","missing_row","transposed_digits","sign_error","genuine_error","unclear"], '
    '"confidence": 0..1, "note": "<=15 words"}.'
)


def available(url: str = DEFAULT_URL, timeout: float = 2.0) -> bool:
    try:
        import requests
        base = url.rsplit("/api/", 1)[0]
        return requests.get(base + "/api/tags", timeout=timeout).ok
    except Exception:
        return False


def _row_view(rows: List[Dict], i: int) -> Dict:
    def slim(r):
        return {k: r.get(k) for k in ("date", "description", "debit", "credit", "balance", "amount") if r.get(k)}
    ctx = {"prev": slim(rows[i - 1]) if i > 0 else None,
           "row": slim(rows[i]),
           "next": slim(rows[i + 1]) if i + 1 < len(rows) else None,
           "finding": rows[i].get("flag")}
    return ctx


def check_row(ctx: Dict, model: str = DEFAULT_MODEL, url: str = DEFAULT_URL,
              timeout: float = 120.0) -> Optional[Dict]:
    """Return the model's classification dict, or None on any failure.

    Timeout is generous (120s) because a cold model load can take ~1 min; keep_alive
    keeps it resident across the flagged batch so later rows are fast.
    """
    try:
        import requests
        prompt = _SYS + "\n\nDATA:\n" + json.dumps(ctx, ensure_ascii=False)
        r = requests.post(url, timeout=timeout, json={
            "model": model, "prompt": prompt, "stream": False,
            "format": "json", "think": False, "keep_alive": "5m",
            "options": {"temperature": 0, "num_predict": 200},
        })
        r.raise_for_status()
        body = r.json()
        # "think: false" routes the answer to `response`; some thinking models still
        # emit it under `thinking`, so fall back to that.
        txt = (body.get("response") or body.get("thinking") or "").strip()
        return json.loads(txt)
    except Exception:
        return None


def validate_flagged(rows: List[Dict], model: str = DEFAULT_MODEL, url: str = DEFAULT_URL,
                     max_rows: int = 25) -> Dict:
    """Run the LLM over flagged rows only. Annotates rows in place with 'llm'. Non-blocking."""
    if not available(url):
        return {"enabled": False, "reason": "ollama_unavailable", "checked": 0}
    checked = 0
    for i, r in enumerate(rows):
        if r.get("flag") and checked < max_rows:
            res = check_row(_row_view(rows, i), model=model, url=url)
            if res is not None:
                r["llm"] = res
                checked += 1
    return {"enabled": True, "model": model, "checked": checked}
