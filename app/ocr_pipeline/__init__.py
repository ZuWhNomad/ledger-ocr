"""Local, privacy-first OCR / document-to-data pipeline for accountants.

No cloud services: born-digital PDFs are parsed deterministically; scans use a
local Tesseract fallback; an optional local LLM (Ollama) does error-checking only.
"""
__version__ = "0.1.0"
