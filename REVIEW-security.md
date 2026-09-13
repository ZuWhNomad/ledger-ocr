# Security & Privacy Review — ledger-ocr (LedgerOCR)

**Scope:** `PLAN.md`, `README.md`, `GETTING_STARTED.md`, `ocr_pipeline/`, `server.py`, `run_app.py`, `static/index.html`, `installer/`, `requirements.txt`.
**Lens:** security & privacy. Core promise reviewed: *"nothing leaves the machine"* for financial documents.
**Method:** read-only. Full-tree grep for network / telemetry / socket egress; manual trace of the HTTP routes, temp-file lifecycle, LLM path, and installer.

## Verdict

**The "nothing leaves the machine" promise holds for the app itself.** In the entire source tree there is exactly **one** outbound network path at runtime — the *optional* LLM error-check, hardcoded to `http://127.0.0.1:11434` (localhost Ollama). There is **no telemetry, no crash reporting, no analytics, no update check, no external/CDN asset, and no cloud OCR/LLM**. The UI (`static/index.html`) loads zero third-party resources (all CSS/JS inline; only same-origin `fetch`). The server binds `127.0.0.1` by default and holds no persistent state.

The genuine issues are concentrated in the **installer** (unverified binary download) and in **defense-in-depth gaps** on the local server. None of them break the core privacy promise on their own.

---

## Findings (ranked by severity)

### P2-1 — Installer downloads and silently executes Ollama with no integrity check
**File:** `installer/install_ollama.ps1:28-30`
**Confidence: HIGH** (real)

```
Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $setup ...
Start-Process -FilePath $setup -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait
```

The optional error-checker setup fetches `OllamaSetup.exe` and runs it silently with **no hash pinning and no signature/publisher verification**. The only protection is TLS (Invoke-WebRequest validates the cert). Scenario: a compromised `ollama.com` release, a CDN/DNS/TLS compromise, or a corporate MITM proxy substitutes the exe → arbitrary code executes on the accountant's machine. The subsequent `& $exe pull $Model` (`:50`) likewise trusts whatever the Ollama registry returns, with no digest verification at this layer.
*Mitigating context:* runs at per-user privilege (no elevation — see P3-5 note), is opt-in, and exits 0 on failure so it never blocks the app. Still, this is the highest-impact real issue because it ends in code execution.
**Fix direction:** pin an expected SHA-256 of `OllamaSetup.exe` (or verify the Authenticode signature / publisher) before `Start-Process`; document the pinned version.

---

### P3-1 — Local server has no Host/Origin check (DNS-rebinding / CSRF), but low real impact
**File:** `server.py:39-102` (no `Host`/`Origin`/`Referer` validation on any route)
**Confidence: HIGH** that the check is absent; **MEDIUM** that impact is low.

`ThreadingHTTPServer` on `127.0.0.1:8765` accepts POST `/api/process` with no CSRF token, no Origin allow-list, and no Host-header pinning. A page the user visits while the app is running could attempt cross-origin requests, and a DNS-rebinding attack could make a remote origin resolve to `127.0.0.1` and be treated as same-origin.

**Why impact is low here (this is the honest part):**
- The server is **stateless and holds no documents.** Each `/api/process` call must *supply its own file bytes* and gets only its own result back. There is nothing belonging to the user for a cross-origin attacker to read or exfiltrate.
- There is **no file-read primitive**: GET serves only the fixed `INDEX` path and `/api/env` (`server.py:51-62`); there is no download route and no path parameter, so an attacker cannot make the server read arbitrary local files.
- The browser's own CORS rules block a cross-origin script from *reading* the JSON response (server sets no `Access-Control-Allow-Origin`), and the UI's custom `X-Filename` header (`index.html:100`) forces a CORS preflight the server never satisfies, so the normal request shape is blocked outright.

So this is a legitimate missing defense-in-depth control, not an exploitable data-exfiltration path given the current stateless design.
**Fix direction:** reject requests whose `Host` header is not `127.0.0.1:<port>`/`localhost:<port>` — a few lines, and it forecloses DNS-rebinding permanently even if a stateful feature is added later.

---

### P3-2 — `--host` allows binding to non-loopback interfaces
**File:** `server.py:133` (`ap.add_argument("--host", default="127.0.0.1")`), used at `server.py:118`
**Confidence: HIGH** (real, but user-initiated)

The default is loopback and the frozen entry point hardcodes `127.0.0.1` (`run_app.py:14,17`), so normal users are safe. But a developer running `python server.py --host 0.0.0.0` exposes an **unauthenticated** file-processing service (there is no auth — stated in `server.py:1`) to the LAN, where anyone can submit files and read results. No warning is emitted.
**Fix direction:** warn loudly (or refuse) when `host` is not a loopback address; document that there is no authentication.

---

### P3-3 — Dependencies are unpinned (lower-bound only)
**File:** `requirements.txt:2-14` (`pdfplumber>=0.11`, `openpyxl>=3.1`, `pytesseract>=0.3.10`, `requests>=2.31`, `reportlab>=4.0`)
**Confidence: HIGH** (real, standard-practice risk)

`>=` with no upper bound and no lockfile means `pip install -r requirements.txt` resolves to whatever is newest, so a future compromised release of any dependency (or its transitive deps — Pillow, pypdfium2, pdfminer) is pulled without review. All listed packages are mainstream and none run suspicious code on import in the reviewed source. The frozen build bundles concrete versions (e.g. `cryptography-49.0.0` in `installer/dist/`), which is better, but the from-source path is unpinned.
**Fix direction:** ship a hash-pinned lockfile (`pip-compile`/`requirements.lock`) for reproducible, tamper-evident installs.

---

### P3-4 — OCR path transiently writes page images to the system temp dir (via pytesseract)
**File:** `ocr_pipeline/extract.py:107,113` (`pytesseract.image_to_string(...)`)
**Confidence: MEDIUM** (behavior is pytesseract-internal, not visible in this repo)

Uploaded files and the pipeline's own outputs are correctly sandboxed and auto-cleaned: `server.py:80` uses `tempfile.TemporaryDirectory()` (context-managed, removed even on exception), and rendered PDF pages are held as in-memory PIL images (`extract.py:112`). **However**, `pytesseract.image_to_string` internally writes the image to a `NamedTemporaryFile` in the OS temp dir (`%TEMP%`), invokes the `tesseract` binary on it, then deletes it. So during scan processing, page images of the financial document briefly hit disk outside the app's control. Normal operation cleans up; a crash/kill mid-OCR could leave a rendered statement page in `%TEMP%`.
*Note:* this only affects the scan/OCR route, not born-digital PDFs. It does not leave the machine.
**Fix direction:** document it; optionally set `TMPDIR`/`TEMP` to the app's own auto-cleaned temp dir for the OCR call so stray images land somewhere that gets purged.

---

### P3-5 — Server exception text is echoed to the client
**File:** `server.py:101-102` (`return ... json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})`)
**Confidence: HIGH** (real, negligible impact)

Unhandled exceptions are returned verbatim, which can include local filesystem paths. The recipient is the local user over loopback, so impact is negligible; noted for completeness.

---

## Positive findings (privacy promise verified)

- **No egress except localhost Ollama.** Full-tree grep (`http|socket|urllib|requests|fetch|telemetry|analytics|sentry|Invoke-WebRequest|curl|wget|api.` over `.py/.html/.js/.ps1/.bat/.iss`, excluding build artifacts) returns only: `validate.py:15,31,56` (127.0.0.1:11434) and the installer's Ollama download. Nothing else.
- **LLM endpoint cannot be redirected off-box.** `DEFAULT_URL` (`validate.py:15`) is a hardcoded `127.0.0.1` constant and is **not** environment-overridable, so the optional model call can't be silently pointed at a remote host. Only the model *name* is env-configurable (`validate.py:14`).
- **LLM is truly optional and off by default.** UI checkbox defaults off (`index.html:56`); `pipeline.process` only calls the model when `use_llm` **and** there are balance mismatches (`pipeline.py:81`); `validate_flagged` first probes availability with a 2s timeout and returns cleanly if Ollama is down (`validate.py:74-75`). The spreadsheet is produced identically without it.
- **LLM prompt sends minimal context, not the document.** `_row_view` (`validate.py:36-43`) sends only the flagged row plus its immediate neighbor rows (date/description/debit/credit/balance/amount), capped at 25 rows (`validate.py:72,78`) — a 3-row window per flag, never the whole statement. Reasonable data minimization; the only sensitive field is the transaction `description`, which is the point of the check.
- **No arbitrary file read/write via the server.** GET serves only the fixed index page and `/api/env`; POST writes solely inside a `TemporaryDirectory`; results are returned inline as base64 (`server.py:99`) with **no download route and no path parameter** — this design choice eliminates path-traversal on download entirely.
- **Upload path-traversal is contained.** The `X-Filename` value is used only for its *extension* (`server.py:72`), which must exactly match the `ALLOWED_EXT` allow-list (`server.py:36,73`); the on-disk name is the fixed `"input"+ext` inside the temp dir (`server.py:81`). The echoed filename is HTML-escaped in the UI (`index.html:140`), so no stored/reflected XSS.
- **Upload size is bounded.** 40 MB cap enforced before reading the body (`server.py:35,76-77`).
- **No request logging.** `log_message` is overridden to no-op (`server.py:48`), so filenames/paths aren't written to any access log — a privacy plus.
- **Installer needs no elevation.** `LedgerOCR.iss:15` sets `PrivilegesRequired=lowest`; `INSTALL.bat` and shortcuts are per-user (`%LOCALAPPDATA%`). No unexpected elevated actions.
- **Deliberately avoids heavier native deps** (no PyMuPDF/Ghostscript/Java/Poppler — `requirements.txt`, `PLAN.md`), reducing the native attack surface.

---

## Summary table

| ID | Severity | Confidence | Issue | Location |
|----|----------|-----------|-------|----------|
| P2-1 | P2 | HIGH | Ollama installer exe downloaded & run with no hash/signature check | `installer/install_ollama.ps1:28-30,50` |
| P3-1 | P3 | HIGH / MED impact | No Host/Origin check (DNS-rebinding/CSRF); low impact due to stateless design | `server.py:39-102` |
| P3-2 | P3 | HIGH | `--host` can bind non-loopback; unauthenticated service on LAN | `server.py:118,133` |
| P3-3 | P3 | HIGH | Unpinned dependencies, no lockfile | `requirements.txt:2-14` |
| P3-4 | P3 | MED | OCR route leaks page images to `%TEMP%` transiently (pytesseract internal) | `ocr_pipeline/extract.py:107,113` |
| P3-5 | P3 | HIGH | Exception text (may include local paths) echoed to client | `server.py:101-102` |

**Top priority:** P2-1 (installer integrity) is the only finding that ends in code execution and the only one worth fixing before shipping to non-technical users. Everything else is defense-in-depth. The central privacy claim — financial documents never leave the machine — is upheld by the code as written.
