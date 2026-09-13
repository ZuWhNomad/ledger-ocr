"""Optional local-LLM error checking (Ollama). VALIDATION ONLY -- never extraction.

Only rows already flagged by deterministic reconciliation (or garbled-looking OCR
rows) are sent to the model. The model classifies the likely problem; it is never
allowed to rewrite numbers. Fully optional and non-blocking: if Ollama is down or
slow, the pipeline continues and rows keep their deterministic flags.
"""
from __future__ import annotations
import json
import os
import time
from typing import List, Dict, Optional, Tuple

# Light model by default (small cold-start); fallback when no config/env set.
DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_URL = "http://127.0.0.1:11434/api/generate"

_SYS = (
    "You are an audit assistant. You are given a suspicious row from a bank statement or "
    "general ledger, plus the rows immediately before and after it, and a deterministic "
    "finding. Classify the most likely cause. You MUST NOT invent or correct any numbers. "
    'Reply with ONLY compact JSON: {"classification": one of '
    '["ocr_misread","merged_transaction","missing_row","transposed_digits","sign_error","genuine_error","unclear"], '
    '"confidence": 0..1, "note": "<=15 words"}.'
)


def _config_path() -> str:
    """Return path to stored config JSON.

    Honors LEDGEROCR_CONFIG env var for test isolation.
    """
    if "LEDGEROCR_CONFIG" in os.environ:
        return os.environ["LEDGEROCR_CONFIG"]
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(base, "LedgerOCR", "config.json")
    return os.path.expanduser("~/.config/ledgerocr/config.json")


def get_model() -> str:
    """Get the active model. Precedence: env OCR_LLM_MODEL > config.json model > DEFAULT_MODEL."""
    if "OCR_LLM_MODEL" in os.environ:
        return os.environ["OCR_LLM_MODEL"]
    path = _config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if isinstance(cfg, dict) and cfg.get("model"):
                    return str(cfg["model"])
        except Exception:
            pass
    return DEFAULT_MODEL


def set_model(name: str) -> str:
    """Write {"model": name} to config.json (creating directories if needed)."""
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"model": name}, f)
    return name


def available(url: str = DEFAULT_URL, timeout: float = 2.0) -> bool:
    try:
        import requests
        base = url.rsplit("/api/", 1)[0]
        return requests.get(base + "/api/tags", timeout=timeout).ok
    except Exception:
        return False


def list_installed(url: str = DEFAULT_URL, timeout: float = 3.0) -> List[Dict]:
    """Return installed Ollama models excluding embedding models: [{"name", "size_gb"}]."""
    try:
        import requests
        base = url.rsplit("/api/", 1)[0]
        r = requests.get(base + "/api/tags", timeout=timeout)
        if not r.ok:
            return []
        data = r.json()
        models = data.get("models", []) if isinstance(data, dict) else []
        res = []
        for m in models:
            name = m.get("name", "")
            details = m.get("details", {}) or {}
            family = details.get("family", "")
            families = details.get("families", []) or []
            all_str = (name + " " + family + " " + " ".join(families)).lower()
            if "embed" in all_str:
                continue
            size_bytes = m.get("size", 0)
            size_gb = round(size_bytes / 1e9, 1)
            res.append({"name": name, "size_gb": size_gb})
        return res
    except Exception:
        return []


def _ram_gb() -> Tuple[Optional[float], Optional[float]]:
    """Return (total_gb, free_gb) of physical system RAM. On failure return (None, None)."""
    try:
        if os.name == "nt":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 1), round(stat.ullAvailPhys / (1024**3), 1)
            return None, None
        else:
            if os.path.exists("/proc/meminfo"):
                mem_total = mem_avail = None
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val_str = parts[1].strip().split()[0]
                            if key == "MemTotal":
                                mem_total = float(val_str)
                            elif key == "MemAvailable":
                                mem_avail = float(val_str)
                if mem_total is not None and mem_avail is not None:
                    return round(mem_total / (1024 * 1024), 1), round(mem_avail / (1024 * 1024), 1)
            return None, None
    except Exception:
        return None, None


def probe_model(name: str, url: str = DEFAULT_URL, timeout: float = 30.0) -> Dict:
    """Send ONE classification request probe to Ollama. Never raises."""
    import requests
    allowed = {"ocr_misread", "merged_transaction", "missing_row", "transposed_digits", "sign_error", "genuine_error", "unclear"}
    canned_ctx = {
        "prev": {"date": "2026-01-01", "description": "Opening", "balance": "100.00"},
        "row": {"date": "2026-01-02", "description": "Deposit", "amount": "50.00", "balance": "200.00"},
        "next": None,
        "finding": "balance mismatch: row balance 200.00 != expected 150.00"
    }
    t0 = time.monotonic()
    try:
        prompt = _SYS + "\n\nDATA:\n" + json.dumps(canned_ctx, ensure_ascii=False)
        r = requests.post(url, timeout=timeout, json={
            "model": name, "prompt": prompt, "stream": False,
            "format": "json", "think": False,
            "options": {"temperature": 0, "num_predict": 200},
        })
        r.raise_for_status()
        latency = round(time.monotonic() - t0, 2)
        body = r.json()
        txt = (body.get("response") or body.get("thinking") or "").strip()
        data = json.loads(txt)
        cls = data.get("classification") if isinstance(data, dict) else None
        if isinstance(cls, str) and cls in allowed:
            return {"json_ok": True, "latency_s": latency, "classification": cls}
        return {"json_ok": False, "latency_s": latency, "classification": cls if isinstance(cls, str) else None}
    except Exception:
        latency = round(time.monotonic() - t0, 2)
        return {"json_ok": False, "latency_s": latency, "classification": None}


def suggest_from(models: List[Dict]) -> Optional[str]:
    """Pure function to determine suggested model from sweep model list."""
    ok_cands = [m for m in models if m.get("fits_ram") is True and m.get("json_ok") is True]
    if ok_cands:
        for m in ok_cands:
            name = m.get("name", "")
            if name == DEFAULT_MODEL or name == f"{DEFAULT_MODEL}:latest":
                return name
        sorted_ok = sorted(
            ok_cands,
            key=lambda x: (x.get("size_gb", 0), x.get("latency_s") if x.get("latency_s") is not None else float("inf"))
        )
        return sorted_ok[0]["name"]

    fits_cands = [m for m in models if m.get("fits_ram") is True]
    if fits_cands:
        sorted_fits = sorted(fits_cands, key=lambda x: x.get("size_gb", 0))
        return sorted_fits[0]["name"]

    return None


def sweep(url: str = DEFAULT_URL, do_probe: bool = True, per_model_timeout: float = 30.0) -> Dict:
    """Sweep local Ollama models, test RAM fit and JSON compliance, and suggest best."""
    avail = available(url)
    ram_total, ram_free = _ram_gb()
    current = get_model()
    if not avail:
        return {
            "available": False,
            "ram_total_gb": ram_total,
            "ram_free_gb": ram_free,
            "current": current,
            "models": [],
            "suggested": None
        }

    installed = list_installed(url=url)
    models_res = []
    for m in installed:
        name = m["name"]
        size_gb = m["size_gb"]
        fits_ram = bool(ram_total is not None and size_gb <= 0.85 * ram_total and (ram_free is None or size_gb <= ram_free + 2))
        json_ok = None
        latency_s = None
        if fits_ram and do_probe:
            pr = probe_model(name, url=url, timeout=per_model_timeout)
            json_ok = pr["json_ok"]
            latency_s = pr["latency_s"]

        models_res.append({
            "name": name,
            "size_gb": size_gb,
            "fits_ram": fits_ram,
            "json_ok": json_ok,
            "latency_s": latency_s
        })

    suggested = suggest_from(models_res)
    return {
        "available": True,
        "ram_total_gb": ram_total,
        "ram_free_gb": ram_free,
        "current": current,
        "models": models_res,
        "suggested": suggested
    }


def _row_view(rows: List[Dict], i: int) -> Dict:
    def slim(r):
        return {k: r.get(k) for k in ("date", "description", "debit", "credit", "balance", "amount") if r.get(k)}
    ctx = {"prev": slim(rows[i - 1]) if i > 0 else None,
           "row": slim(rows[i]),
           "next": slim(rows[i + 1]) if i + 1 < len(rows) else None,
           "finding": rows[i].get("flag")}
    return ctx


def check_row(ctx: Dict, model: Optional[str] = None, url: str = DEFAULT_URL,
              timeout: float = 120.0) -> Optional[Dict]:
    """Return the model's classification dict, or None on any failure."""
    model = model or get_model()
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
        txt = (body.get("response") or body.get("thinking") or "").strip()
        return json.loads(txt)
    except Exception:
        return None


def validate_flagged(rows: List[Dict], model: Optional[str] = None, url: str = DEFAULT_URL,
                     max_rows: int = 25, max_consecutive_failures: int = 3) -> Dict:
    """Run the LLM over flagged rows only. Annotates rows in place with 'llm'. Non-blocking."""
    model = model or get_model()
    if not available(url):
        return {"enabled": False, "reason": "ollama_unavailable", "checked": 0}
    checked = attempts = consecutive_failures = 0
    for i, r in enumerate(rows):
        if not r.get("flag"):
            continue
        if attempts >= max_rows or consecutive_failures >= max_consecutive_failures:
            break
        attempts += 1
        res = check_row(_row_view(rows, i), model=model, url=url)
        if res is not None:
            r["llm"] = res
            checked += 1
            consecutive_failures = 0
        else:
            consecutive_failures += 1
    return {"enabled": True, "model": model, "checked": checked,
            "attempted": attempts, "failed": attempts - checked}

