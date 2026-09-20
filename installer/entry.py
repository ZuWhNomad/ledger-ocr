"""Frozen entry point: LedgerOCR.exe == run-ledger-ocr (no arguments -> the drag-and-drop page)."""
import sys

from ledger_ocr.cli import main

sys.exit(main())
