"""
Fallback PDF text extraction using PyMuPDF (fitz).

Activated when pdfplumber returns empty / minimal text, which can happen
with certain PDF producers.  PyMuPDF also powers the OCR image-conversion
step (see ``ocr/ocr_engine.py``).
"""

from __future__ import annotations

from typing import List

import fitz  # PyMuPDF

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text(pdf_path: str) -> str:
    """
    Extract all text using PyMuPDF.

    Returns
    -------
    str
        Concatenated page text separated by ``\\n\\n``.
    """
    pages_text: List[str] = []
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            logger.debug(
                "PyMuPDF page %d: extracted %d chars", page_num, len(text)
            )
            pages_text.append(text)
        doc.close()
    except Exception:
        logger.exception("PyMuPDF failed to read '%s'", pdf_path)
        return ""

    return "\n\n".join(pages_text)


def page_count(pdf_path: str) -> int:
    """Return the total number of pages."""
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        logger.exception("PyMuPDF could not open '%s'", pdf_path)
        return 0
