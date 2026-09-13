# ledger-ocr — review backlog (2026-09-13 Opus 5 lens fan-out)

Collect all lenses, dedupe, verify, then fix (per the conductor review framework).

## Lens: security & privacy (REVIEW-security.md)
Verdict: "nothing leaves the machine" holds — only runtime network path is the OPTIONAL LLM at hardcoded localhost:11434. No telemetry/CDN/update-check.
- [ ] SEC-P2-1 — installer/install_ollama.ps1:28-30,50: downloads OllamaSetup.exe + `ollama pull` over HTTPS with NO hash/signature check → MITM/compromised-release code execution. **Only finding that ends in code exec; fix before shipping.**
- [ ] SEC-P3-1 — server.py:39-102: no Host/Origin check (DNS-rebind/CSRF). Low impact (stateless, no file-read route); add a one-line Host allow-list as defense-in-depth.
- [ ] SEC-P3-2 — server.py:133: `--host` can bind non-loopback → unauthenticated LAN file service. Default is loopback; warn/guard.
- [ ] SEC-P3-3 — requirements.txt unpinned (>= only, no lockfile). Pin / add a lockfile for the from-source path.
- [ ] SEC-P3-4 — extract.py:107,113: pytesseract writes the page image to %TEMP% internally; a crash mid-OCR could leave a statement page. Consider a scoped temp dir.
- [ ] SEC-P3-5 — server.py:101-102: exception text (may include local paths) echoed to client; loopback-only, negligible. Sanitize.
Verified-good: LLM off by default, sends only a 3-row window (max 25), non-overridable localhost; upload allow-list + 40MB cap; no download route/path param; installer needs no elevation.

## Lens: packaging & UX (REVIEW-packaging.md)
- [ ] PKG-P1-1 — installer unsigned (LedgerOCR.iss, build_installer.ps1, frozen exe, OllamaSetup.exe) → SmartScreen "Windows protected your PC" wall, undocumented. Document the "More info → Run anyway" step at minimum; sign if feasible. (real install-blocker)
- [ ] PKG-P1-2 — scans/photos advertised (GETTING_STARTED:3, index.html:46,50) but no installer path installs Tesseract; scanned statement dead-ends at pipeline.py:62-64 with a README the layperson lacks. Either bundle/auto-install Tesseract or stop advertising scans until then.
- [ ] PKG-P2-1 — LLM checkbox silently no-ops when Ollama absent (index.html:56,116); show "error-checker not installed".
- [ ] PKG-P2-2 — encrypted/corrupt PDF shows raw ExceptionName:msg (server.py:101-102); plain-English mapping (esp. password-protected).
- [ ] PKG-P2-3 — no progress indication; long OCR/LLM looks frozen (index.html:96).
- [ ] PKG-P2-4 — INSTALL.bat fallback has no uninstaller / Add-Remove entry.
- [ ] PKG-P2-5 — uninstall leaves Ollama + ~2GB model behind.
- [ ] PKG-P2-6 — Inno error-checker step default-on, synchronous, 2GB, looks hung (LedgerOCR.iss:36,46-47).
- [ ] PKG-P3 — stale README model qwen3.8 vs qwen2.5:3b (validate.py:14); port-8765 troubleshooting mismatch; generic icon; closable console; multi-file drop ignores extras; no page/time guard on scans.
Verified-good: freeze self-contained; Ollama optional/non-fatal; privacy/temp clean; UI offline; oversized/unsupported give plain errors; per-user no-admin install.

## Lens: extraction correctness (REVIEW-correctness.md) — ALL verified by running the code
### P1 — SILENT WRONG NUMBER (most dangerous for a financial tool)
- [ ] COR-P1-1 — parse_money locale mis-guess (reconcile.py:58-63): locale decided by which separator is LAST, so `5,000`→5.00, `1,500`→1.50, `12,345`→12.345; `1,234,567`/EU `1.000.000`→None (dropped). Hits whole-dollar GL amounts + EU formats.
- [ ] COR-P1-2 — single signed-amount statements never reconciled (reconcile.py:90-94,127): _delta ignores sign → votes tie → 'unknown' → balance check skipped; a wrong balance says "0 mismatches". (== general P2-1)
- [ ] COR-P1-3 — description text leaks past column boundary → giant fake amount (tables.py:79-87,106-120): midpoint bounds put desc/amount boundary too far left; verified 100.00 exported as 1,043,100.00.
- [ ] COR-P1-4 — _canon 'cr'/'dr' substring mislabels headers (tables.py:27-35): 'Descr'→credit.
### P2
- [ ] COR-P2-5 — multi-page drop (tables.py:102-104): a page whose header doesn't repeat returns [] → rows vanish silently.
- [ ] COR-P2-6 — OCR parser (pipeline.py:21): whole-number amounts match no token branch (dropped); EU 1.234,56 → 1.23.
- [ ] COR-P2-7 — multi-account (reconcile.py:136-147): one cumulative series floods flags across a second account.
- [ ] COR-P2-8 — no-balance statements report 0 mismatches despite zero checks.
### General lens P2 dupes/adds (REVIEW-general.md): validate max_rows unbounded on LLM failure (validate.py:77-83); XLSX amounts as text not numbers (export.py:34-52); no-header page misextract (tables.py:63-76).
Highest-value test fixtures: single-amount column + page-2 no-header (each turns a silent bug into a visible failure).
