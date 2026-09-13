"""Real-world / photo-robustness benchmark for Ledger-OCR.

Evaluates clean 300-dpi renders vs simulated phone-photo degradation on a synthetic bank statement,
tests a real pharmacy receipt phone photo, and appends an idempotent section to docs/BENCHMARK.md.
"""
from __future__ import annotations
import os
import sys
import csv
import tempfile
from typing import Dict, Tuple

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))  # app/tests
APP_DIR = os.path.dirname(TESTS_DIR)                  # app
REPO_ROOT = os.path.dirname(APP_DIR)                  # repo root

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, APP_DIR)

from ocr_pipeline.extract import _tesseract_available, ocr_to_rows, ocr_to_text
from ocr_pipeline.pipeline import process, parse_text_rows
from samples.make_sample import make_pdf
from bench import score_rows

import pdfplumber
from PIL import Image, ImageFilter, ImageEnhance


def compute_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def apply_simulated_photo_degradation(img: Image.Image) -> Image.Image:
    """Apply a fixed, deterministic transformation chain approximating a phone photo."""
    # Rotate ~3.5 degrees (expand=True, white fill)
    img_rot = img.rotate(3.5, expand=True, fillcolor="white")
    # Downscale to ~1100px wide
    w, h = img_rot.size
    target_w = 1100
    target_h = int(target_w * h / w)
    img_resized = img_rot.resize((target_w, target_h), Image.Resampling.LANCZOS)
    # Gaussian blur radius ~1.0
    img_blur = img_resized.filter(ImageFilter.GaussianBlur(radius=1.0))
    # Reduce contrast/brightness slightly and add mild brightness to mimic glare
    img_contrast = ImageEnhance.Contrast(img_blur).enhance(0.9)
    img_bright = ImageEnhance.Brightness(img_contrast).enhance(1.05)
    return img_bright


def run_benchmark():
    tesseract_bin = _tesseract_available()
    if not tesseract_bin:
        print("Tesseract not available on this system. Exiting.")
        sys.exit(0)

    # 1) SIMULATED PHONE-PHOTO DEGRADATION
    truth_csv_path = os.path.join(APP_DIR, "tests", "fixtures", "base_ruled.expected.csv")
    with open(truth_csv_path, "r", encoding="utf-8") as f:
        truth_rows = list(csv.DictReader(f))

    scores = {}

    with tempfile.TemporaryDirectory(prefix="ledgerocr_bench_real_") as tmpdir:
        pdf_path = os.path.join(tmpdir, "synthetic_statement.pdf")
        make_pdf(pdf_path)

        with pdfplumber.open(pdf_path) as pdf:
            clean_pil = pdf.pages[0].to_image(resolution=300).original

        clean_jpg_path = os.path.join(tmpdir, "clean-render.jpg")
        clean_pil.save(clean_jpg_path, "JPEG", quality=95)

        sim_pil = apply_simulated_photo_degradation(clean_pil)
        sim_jpg_path = os.path.join(tmpdir, "sim-photo.jpg")
        sim_pil.save(sim_jpg_path, "JPEG", quality=55)

        # Word-box path on clean-render
        wb_clean_rows = ocr_to_rows(clean_jpg_path)
        scores[("clean-render", "word-box")] = score_rows(wb_clean_rows, truth_rows)

        # Text-line path on clean-render
        tx_clean_rows = parse_text_rows(ocr_to_text(clean_jpg_path))
        scores[("clean-render", "text-line")] = score_rows(tx_clean_rows, truth_rows)

        # Word-box path on sim-photo
        wb_sim_rows = ocr_to_rows(sim_jpg_path)
        scores[("sim-photo", "word-box")] = score_rows(wb_sim_rows, truth_rows)

        # Text-line path on sim-photo
        tx_sim_rows = parse_text_rows(ocr_to_text(sim_jpg_path))
        scores[("sim-photo", "text-line")] = score_rows(tx_sim_rows, truth_rows)

    f1_dict = {}
    prec_dict = {}
    rec_dict = {}
    for key, sc in scores.items():
        p, r, f1 = compute_f1(sc["tp"], sc["fp"], sc["fn"])
        prec_dict[key] = p
        rec_dict[key] = r
        f1_dict[key] = f1

    # 2) REAL PHOTO (negative/scope example)
    real_receipt_path = os.path.join(APP_DIR, "tests", "fixtures", "real", "receipt_pharmacy.jpg")
    receipt_result = process(real_receipt_path)
    receipt_doc_shape = receipt_result.get("document_shape")
    receipt_row_count = len(receipt_result.get("rows", []))
    receipt_raw_text = ocr_to_text(real_receipt_path)
    receipt_char_count = len(receipt_raw_text)

    assert receipt_doc_shape == "unrecognized", f"Expected 'unrecognized', got '{receipt_doc_shape}'"
    assert receipt_row_count == 0, f"Expected 0 rows, got {receipt_row_count}"

    # Print stdout table
    print("\nSimulated Phone-Photo Degradation vs Clean Render:")
    print(f"{'Variant':<15} | {'Path':<10} | {'Prec':<8} | {'Rec':<8} | {'F1':<8} | {'TP':<4} | {'FP':<4} | {'FN':<4}")
    print("-" * 75)
    for variant in ["clean-render", "sim-photo"]:
        for path_name in ["word-box", "text-line"]:
            k = (variant, path_name)
            sc = scores[k]
            print(f"{variant:<15} | {path_name:<10} | {prec_dict[k]:<8.4f} | {rec_dict[k]:<8.4f} | {f1_dict[k]:<8.4f} | {sc['tp']:<4} | {sc['fp']:<4} | {sc['fn']:<4}")
    
    print("\nDrop from clean-render to sim-photo:")
    print(f"  word-box  F1: {f1_dict[('clean-render', 'word-box')]:.4f} -> {f1_dict[('sim-photo', 'word-box')]:.4f} (drop: {f1_dict[('clean-render', 'word-box')] - f1_dict[('sim-photo', 'word-box')]:.4f})")
    print(f"  text-line F1: {f1_dict[('clean-render', 'text-line')]:.4f} -> {f1_dict[('sim-photo', 'text-line')]:.4f} (drop: {f1_dict[('clean-render', 'text-line')] - f1_dict[('sim-photo', 'text-line')]:.4f})")

    print("\nReal Photo Negative Example (receipt_pharmacy.jpg):")
    print(f"  document_shape: {receipt_doc_shape}")
    print(f"  rows count:     {receipt_row_count}")
    print(f"  OCR char count: {receipt_char_count}")

    # 3) WRITE docs/BENCHMARK.md IDEMPOTENTLY
    docs_dir = os.path.join(REPO_ROOT, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    bench_md_path = os.path.join(docs_dir, "BENCHMARK.md")

    base_content = ""
    if os.path.exists(bench_md_path):
        with open(bench_md_path, "r", encoding="utf-8") as f:
            base_content = f.read()

    marker = "## Real-world vs synthetic (photo robustness)"
    if marker in base_content:
        base_content = base_content.split(marker)[0].rstrip()

    wb_clean_f1 = f1_dict[("clean-render", "word-box")]
    wb_sim_f1 = f1_dict[("sim-photo", "word-box")]
    tx_clean_f1 = f1_dict[("clean-render", "text-line")]
    tx_sim_f1 = f1_dict[("sim-photo", "text-line")]

    real_md_lines = [
        "",
        "## Real-world vs synthetic (photo robustness)",
        "",
        "- The headline F1 ~0.99 and OCR 0.54->0.94 numbers are measured on CLEAN 300-dpi synthetic born-digital renders and are an UPPER BOUND; they overstate accuracy on real photographed documents.",
        f"- Measured clean-render vs simulated-phone-photo F1 for both OCR paths: the word-box path collapsed from {wb_clean_f1:.4f} to {wb_sim_f1:.4f} (drop of {wb_clean_f1 - wb_sim_f1:.4f}), and the text-line path fell from {tx_clean_f1:.4f} to {tx_sim_f1:.4f} (drop of {tx_clean_f1 - tx_sim_f1:.4f}). A few degrees of skew defeats header/column anchoring, so a real phone photo can extract *worse* than the clean-render numbers suggest.",
        "- These are SIMULATED degradations, NOT real photographs; no real photographed BANK-STATEMENT fixture exists yet.",
        f"- The one real phone photo available is a pharmacy receipt, which is out of ledger scope; the pipeline now correctly flags it as document_shape=unrecognized rather than emitting an empty ledger CSV. Recognized character count: {receipt_char_count}.",
        "",
        "### Degradation Results Table",
        "",
        "| Variant | Path | Precision | Recall | F1 | TP | FP | FN |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        f"| `clean-render` | `word-box` | {prec_dict[('clean-render', 'word-box')]:.4f} | {rec_dict[('clean-render', 'word-box')]:.4f} | {wb_clean_f1:.4f} | {scores[('clean-render', 'word-box')]['tp']} | {scores[('clean-render', 'word-box')]['fp']} | {scores[('clean-render', 'word-box')]['fn']} |",
        f"| `clean-render` | `text-line` | {prec_dict[('clean-render', 'text-line')]:.4f} | {rec_dict[('clean-render', 'text-line')]:.4f} | {tx_clean_f1:.4f} | {scores[('clean-render', 'text-line')]['tp']} | {scores[('clean-render', 'text-line')]['fp']} | {scores[('clean-render', 'text-line')]['fn']} |",
        f"| `sim-photo` | `word-box` | {prec_dict[('sim-photo', 'word-box')]:.4f} | {rec_dict[('sim-photo', 'word-box')]:.4f} | {wb_sim_f1:.4f} | {scores[('sim-photo', 'word-box')]['tp']} | {scores[('sim-photo', 'word-box')]['fp']} | {scores[('sim-photo', 'word-box')]['fn']} |",
        f"| `sim-photo` | `text-line` | {prec_dict[('sim-photo', 'text-line')]:.4f} | {rec_dict[('sim-photo', 'text-line')]:.4f} | {tx_sim_f1:.4f} | {scores[('sim-photo', 'text-line')]['tp']} | {scores[('sim-photo', 'text-line')]['fp']} | {scores[('sim-photo', 'text-line')]['fn']} |",
        "",
    ]

    new_content = base_content.rstrip() + "\n" + "\n".join(real_md_lines)
    with open(bench_md_path, "w", encoding="utf-8") as f:
        f.write(new_content)


if __name__ == "__main__":
    run_benchmark()
