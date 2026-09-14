# Research: Deskew + OCR accuracy for LedgerOCR

**Status: research / decision-support only. Nothing here is implemented.** This document
recommends options and lays out the tradeoffs; the choices that would relax LedgerOCR's current
"no heavy/native deps" rule are flagged explicitly for a human to decide.

---

## Executive summary

LedgerOCR today OCRs images and scans with **Tesseract** (`pytesseract`, `--psm 6`) and does **no
image preprocessing**. On clean scans this is fine. On real-world phone photos it degrades badly:
in our own smoke test, a rotated pharmacy-receipt photo OCR'd into near-useless mirrored/garbled
text even though the pipeline correctly returned it as raw text. That failure is an **orientation**
problem, not an engine problem.

The single highest-value fix requires **no new dependency at all**: run Tesseract's built-in
**OSD (Orientation & Script Detection)** to auto-rotate the page to upright before OCR. Tesseract
is already bundled, `osd.traineddata` ships with the UB-Mannheim build we install, and this alone
fixes the 90°/180°/270° misrotation that produced the garbled receipt.

The next tier — a light **OpenCV** preprocessing pass (grayscale → threshold → fine-angle deskew →
upscale to ~300 dpi) — is where real photo robustness comes from, at the cost of **one native
Python wheel** (`opencv-python-headless`, pip-installable, ~40–50 MB). That is the one rule-relaxation
worth seriously considering.

Everything beyond that (docTR, PaddleOCR, EasyOCR, Kraken, OCRmyPDF+Ghostscript) buys accuracy at
the price of hundreds of MB of runtime, model downloads, and/or AGPL dependencies — a large
departure from the current lightweight, offline, PyInstaller-friendly design. Adopt only if the
firm decides general-purpose photo quality outweighs bundle size.

**Recommended path:** (1) Tesseract OSD auto-rotate + smarter `--psm`, then (2) optional OpenCV
preprocessing/deskew as an add-on. Treat heavy DL engines as a separate, later decision.

---

## Current baseline (what we're comparing against)

| Aspect | Today |
|---|---|
| OCR engine | Tesseract via `pytesseract`, `image_to_data --psm 6` (word boxes) + `image_to_string` fallback |
| Preprocessing | **None** (raw PIL image → Tesseract) |
| Orientation handling | **None** (a sideways/upside-down photo stays that way) |
| PDF raster | `pdfplumber` + `pypdfium2` (no Poppler, no PyMuPDF/AGPL) |
| Images | Pillow |
| Rule | Offline only; pure-Python or already-bundled native libs; freezes with PyInstaller |
| License posture | Everything Apache/BSD/MIT-ish; **AGPL avoided on purpose** (no PyMuPDF) |

---

## 1. Local, offline deskew / preprocessing options

"Deskew" is really two problems, and they need different tools:
- **Orientation** — page is rotated a multiple of 90° (the receipt case). Fixed by OSD.
- **Skew** — page is rotated a few degrees (hand-held photo, imperfect scan). Fixed by angle
  estimation + rotate.
- **Quality** — low contrast, noise, low DPI, shadows. Fixed by thresholding/denoise/upscale.

| Option | What it fixes | Accuracy impact | Windows install friction | License | Dep weight | Fits "no heavy/native deps"? |
|---|---|---|---|---|---|---|
| **Tesseract OSD** (`--psm 0` / `image_to_osd`) | Orientation (90/180/270), script | **High** on misrotated photos — turns garbage into readable text | **None** — Tesseract already installed; `osd.traineddata` ships with UB-Mannheim | Apache-2.0 | 0 (reuses bundled engine) | ✅ **Yes** — no new dep |
| **OpenCV deskew** (`minAreaRect` on a binarized text mask, or Hough lines) + preprocessing (grayscale, adaptive threshold, denoise, upscale) | Fine skew + quality | **High** on real-world photos; the standard first step in most OCR pipelines | **Low** — `pip install opencv-python-headless`, prebuilt Windows/py3.12 wheel, no external exe | Apache-2.0 (OpenCV ≥4.5; older was BSD-3) | ~40–50 MB installed; native, but self-contained DLLs PyInstaller collects fine | ⚠️ **Relaxes it** — one native wheel (no external exe) |
| **scikit-image** (`transform`, `filters.threshold_*`) deskew | Fine skew + quality | High, comparable to OpenCV | **Medium** — pulls **numpy + scipy** (both currently excluded in our PyInstaller spec) | BSD-3-Clause | numpy+scipy+skimage ≈ 80–120 MB | ⚠️ Relaxes it more than OpenCV (bigger transitive deps) |
| **Leptonica** (`deskew`, `pixDeskew`) | Skew + binarization | High; battle-tested (it's what Tesseract uses internally) | **High** as a *standalone* dep — it's a C lib with no maintained Python binding; bundled *inside* Tesseract but not exposed to us | BSD-2-Clause | — | ❌ Not practical to call directly from Python |
| **ImageMagick `-deskew`** | Skew | Medium (threshold-based angle) | **High** — external `magick.exe` (~30–50 MB) to bundle or require installed; spawns a subprocess | ImageMagick License (Apache-2.0-compatible) | ~30–50 MB external exe | ❌ External native exe — against the rule |
| **ScanTailor**-style pipeline | Skew, dewarp, content box | High for scans | **High** — separate GPL desktop app, not a library | GPL | large | ❌ Not embeddable |
| **`unpaper`** (used by OCRmyPDF) | Deskew, despeckle, borders | Medium–High | **High** — external exe | GPL-2.0 | external exe | ❌ External native exe |

**Takeaways**
- OSD is free and fixes the exact failure we observed. Do it regardless of what else is chosen.
- OpenCV (headless) is the pragmatic deskew/preprocessing engine: one clean pip wheel, no external
  process, Apache-2.0. It is a *native* wheel, so it does cross the "no native deps" line — but it's
  the least-cost crossing (no Poppler/Ghostscript/exe, PyInstaller collects it).
- Leptonica/ImageMagick/unpaper are all either not Python-callable or require shipping an external
  native binary — worse fits than OpenCV for our packaging model.

---

## 2. Better local OCR engines / approaches

### 2a. Stay on Tesseract, tune it (cheapest, no new deps)
Most of our real-world loss is preprocessing, not the engine. Levers, all zero-dependency:
- **OSD auto-rotate** before OCR (see §1).
- **`--psm` selection.** `--psm 6` ("uniform block") is wrong for many receipts. `--psm 4`
  (single column of variable-size text), `--psm 3` (full auto page segmentation), or `--psm 11/12`
  (sparse text, with/without OSD) often win on receipts and free-form documents. A cheap heuristic
  or a two-pass "pick the result with the higher mean word confidence" is a known, effective trick.
- **`--oem 1`** (LSTM engine) is already the modern default; confirm it's used.
- **DPI / upscaling.** Tesseract wants ~300 dpi. Upscaling small phone crops before OCR helps.
- **Confidence data.** `image_to_data` already returns per-word confidence — usable to choose PSM,
  flag low-quality pages, or trigger the preprocessing path only when confidence is poor.

License: Apache-2.0. Friction: none. **This is the highest ROI per unit of effort/risk.**

### 2b. Alternative engines

| Engine | Offline? | Accuracy on skewed/real-world | License | Windows / dep friction | Verdict for us |
|---|---|---|---|---|---|
| **Tesseract (tuned)** | ✅ | Good once deskewed/oriented | Apache-2.0 | None (already shipped) | **Keep as the base** |
| **PaddleOCR / PP-OCR** | ✅ after model download | **Best-in-class** on rotated/skewed text — ships a built-in **text-angle classifier** and strong detection | Apache-2.0 | **High** — `paddlepaddle` runtime (hundreds of MB), model files (~10–20 MB), Windows install can be finicky | Strong quality, heavy; only if quality justifies size |
| **docTR** (Mindee) | ✅ after model download | High; modern detection+recognition | Apache-2.0 | **High** — needs **TensorFlow or PyTorch** backend (very large), model downloads | Overkill for our footprint |
| **EasyOCR** | ✅ after model download | High; simplest API of the DL engines | Apache-2.0 | **High** — **PyTorch** (~1 GB+ with CUDA-less CPU wheels still large), model downloads | Simplest DL option, still very heavy |
| **Kraken** | ✅ | High for historical/handwritten; not our use case | Apache-2.0 | **High** — PyTorch; Linux-first, more Windows friction | Not a fit |
| **OCRmyPDF** | ✅ | Inherits Tesseract accuracy; adds **`--deskew` and `--rotate-pages`** (via OSD) and produces searchable PDFs | **MPL-2.0** (the tool) | **High** — orchestrates **Ghostscript (AGPL/commercial)** + Tesseract + optionally unpaper; external exes | Great ideas to borrow; **Ghostscript = AGPL flag** |

**Takeaways**
- No engine swap is needed to fix the current failures — preprocessing + OSD closes most of the gap.
- If the firm wants genuinely robust *photo* OCR (crumpled receipts, angled shots), **PaddleOCR** is
  the strongest offline option and its angle classifier directly targets our rotation problem — but
  it's a heavyweight, model-downloading, native-runtime dependency.
- docTR/EasyOCR/Kraken are all in the "ship a deep-learning runtime" category — hundreds of MB to
  >1 GB, first-run model downloads (which also complicates a strictly-offline install: models must
  be pre-bundled). Big departure from the current design.

---

## 3. Open-source projects worth dissecting / borrowing from

- **OCRmyPDF** (`ocrmypdf/OCRmyPDF`, MPL-2.0) — borrow its **`--rotate-pages` (OSD-based
  auto-rotate)** and **`--deskew`** logic and its overall "preprocess → OCR → assemble" ordering.
  Best reference for doing orientation/deskew correctly with Tesseract. (Don't necessarily adopt the
  package — it drags in Ghostscript/AGPL — but the approach is exactly right.)
- **PaddleOCR** (`PaddlePaddle/PaddleOCR`, Apache-2.0) — borrow the **text-angle-classification**
  concept (classify each detected text line's orientation and rotate before recognition). Even a
  lightweight reimplementation of "detect dominant text angle, rotate, re-OCR" captures much of it.
- **Standard OpenCV deskew routines** — the widely published `minAreaRect`-on-threshold deskew (and
  the Hough-line variant) are the canonical, ~30-line implementations to adapt. No single repo to
  clone; it's a well-known recipe.
- **`unpaper`** (`unpaper/unpaper`, GPL-2.0) — reference for despeckle/border-removal heuristics
  (read the algorithm; GPL means don't copy code into an Apache/BSD-licensed codebase).
- **`jbarlow83`/OCRmyPDF's `_pipeline`** specifically for how it decides *when* to deskew/rotate
  based on OSD confidence — a good model for a "only preprocess when Tesseract confidence is low"
  gate that keeps clean scans fast.

License caution: OCRmyPDF is MPL-2.0 (file-level copyleft, generally OK to depend on), but unpaper
and ScanTailor are GPL — **read for ideas, don't lift code**.

---

## 4. Ranked recommendation (with the rule-relaxation flags)

Ordered cheapest/lowest-risk first. Each step is independently shippable.

### Rank 1 — Tesseract OSD auto-rotate + `--psm` tuning · **keeps all current rules**
- **Do:** before OCR, call `image_to_osd` (or `--psm 0`); if it reports a rotation, rotate the PIL
  image to upright, then OCR. Add a small `--psm` strategy (try 6 and 4/11; keep the higher mean
  confidence).
- **Cost:** no new dependency (Tesseract + `osd.traineddata` already installed), a modest code
  change, a few ms per page. **No rule relaxation.**
- **Payoff:** fixes the observed garbled-receipt failure (misorientation) and improves receipts/free
  documents broadly. **This is the recommendation to act on first.**
- ⚠️ Minor: confirm `osd.traineddata` is present in the installed Tesseract and in any bundled
  language-data path; if a minimal Tesseract install lacks it, ship it (a small file).

### Rank 2 — OpenCV preprocessing + fine deskew · **relaxes "no native deps" (one wheel)**
- **Do:** add an optional preprocessing pass with `opencv-python-headless`: grayscale → adaptive/Otsu
  threshold → fine-angle deskew (`minAreaRect`) → denoise → upscale to ~300 dpi, gated on low OCR
  confidence so clean scans stay fast.
- **Cost / RULE FLAG:** adds a **native Python wheel** (`opencv-python-headless`), ~40–50 MB
  installed, pip-installable with a prebuilt Windows/py3.12 wheel, self-contained DLLs that
  PyInstaller collects. **No external exe, no Poppler/Ghostscript.** This is the *smallest* way to
  cross the "no heavy/native deps" line, and it should stay **optional** (degrade to no-preprocessing
  if the wheel is absent, exactly like OCR/LLM are optional today).
- **Payoff:** the main real-world photo-robustness gain. High value for an accounting firm shooting
  receipts/statements with a phone.

### Rank 3 — OCRmyPDF-style path for PDFs · **relaxes rules significantly (Ghostscript = AGPL)**
- **Do (only for the PDF route):** either depend on OCRmyPDF or replicate its rotate/deskew.
- **Cost / RULE FLAG:** OCRmyPDF pulls **Ghostscript (AGPL/commercial)** and external exes. AGPL is
  the exact thing the project avoided by rejecting PyMuPDF. **Do not adopt without a licensing
  decision.** Better to *borrow the approach* (Rank 1+2) than take the dependency.

### Rank 4 — PaddleOCR (or docTR/EasyOCR) · **major rule relaxation (DL runtime + model downloads)**
- **Do:** swap/augment the engine with PaddleOCR for hard photos, using its angle classifier.
- **Cost / RULE FLAG:** hundreds of MB (`paddlepaddle` runtime + models), first-run model download
  (must be **pre-bundled** to stay offline), heavier Windows install, larger PyInstaller output.
  Apache-2.0 (license is fine); the cost is **size and complexity**, not licensing.
- **Payoff:** best accuracy on genuinely difficult rotated/low-quality images. Choose only if Rank
  1+2 prove insufficient and the firm accepts a much larger installer.

### Avoid
- **PyMuPDF** (AGPL) — already correctly avoided; don't reintroduce for rasterization.
- **ImageMagick/unpaper/ScanTailor as bundled binaries** — external native exes and/or GPL; worse
  fit than OpenCV.

### Suggested decision
Ship **Rank 1** (no rules relaxed) and offer **Rank 2** as an optional "photo-quality add-on"
(mirrors how OCR and the LLM are already optional). Defer Rank 3/4 unless photo quality demands it.

---

## "Verify current" caveats (not fully confirmed at write time)

These should be checked against current sources before acting (author relied on domain knowledge,
web verification was not confirmed for this pass):

- Exact current versions of OpenCV, PaddleOCR/paddlepaddle, docTR, EasyOCR, OCRmyPDF, ImageMagick.
- That a prebuilt **`opencv-python-headless` wheel exists for Windows + CPython 3.12** (expected yes)
  and its exact installed size.
- Whether the **installed UB-Mannheim Tesseract includes `osd.traineddata`** on this machine (needed
  for OSD); if not, where to source the small file.
- **PaddleOCR offline story:** whether models can be pre-downloaded/bundled and pointed at with a
  local path so no network is needed at runtime; current Windows install steps for `paddlepaddle`.
- **OCRmyPDF's Ghostscript requirement and version** and whether any deskew/rotate feature works
  without Ghostscript (affects the AGPL flag).
- Current license texts: confirm **OpenCV = Apache-2.0** (post-4.5), **Leptonica = BSD-2-Clause**,
  **OCRmyPDF = MPL-2.0**, **ImageMagick = ImageMagick License**, and that **PaddleOCR/docTR/EasyOCR/
  Kraken remain Apache-2.0**.
- Rough measured accuracy deltas (Tesseract-only vs +OSD vs +OpenCV-deskew vs PaddleOCR) on a small
  set of the firm's real skewed receipts — worth a quick benchmark before committing to Rank 2/4.
