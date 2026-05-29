"""
PDF type detector — determines if a PDF is text-based or scanned.

Uses a character-count heuristic: if pdfplumber can extract more than
``MIN_CHARS_PER_PAGE`` characters on average, the PDF is text-based.
Otherwise we assume it's scanned and must go through OCR.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

import pdfplumber

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)


class PDFType(Enum):
    TEXT = "text"
    SCANNED = "scanned"


# Minimum average characters per page to consider a PDF text-based.
MIN_CHARS_PER_PAGE = 50


def detect(pdf_path: str) -> Tuple[PDFType, int]:
    """
    Determine whether a PDF is text-based or scanned.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    tuple[PDFType, int]
        The detected type and total page count.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            if total_pages == 0:
                logger.warning("PDF has 0 pages: '%s'", pdf_path)
                return PDFType.SCANNED, 0

            total_chars = 0
            for page in pdf.pages:
                text = page.extract_text() or ""
                total_chars += len(text.strip())

            avg_chars = total_chars / total_pages
            pdf_type = PDFType.TEXT if avg_chars >= MIN_CHARS_PER_PAGE else PDFType.SCANNED

            logger.info(
                "Detected '%s' as %s (%d pages, avg %.0f chars/page)",
                pdf_path, pdf_type.value, total_pages, avg_chars,
            )
            return pdf_type, total_pages

    except Exception:
        logger.exception("Detection failed for '%s', defaulting to SCANNED", pdf_path)
        return PDFType.SCANNED, 0
