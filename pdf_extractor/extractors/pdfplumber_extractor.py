"""
Primary PDF text extraction using pdfplumber.

Chosen as the default because pdfplumber preserves table layouts and
provides character-level positioning — critical for invoice parsing.
Uses lazy page iteration to minimize memory footprint.
"""

from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional, Tuple

import pdfplumber

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text(pdf_path: str) -> str:
    """
    Extract all text from every page of a PDF.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    str
        Concatenated text from all pages (separated by ``\\n\\n``).
    """
    pages_text: List[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                logger.debug(
                    "pdfplumber page %d: extracted %d chars", page_num, len(text)
                )
                pages_text.append(text)
    except Exception:
        logger.exception("pdfplumber failed to read '%s'", pdf_path)
        return ""

    return "\n\n".join(pages_text)


def extract_tables(pdf_path: str) -> List[List[List[Optional[str]]]]:
    """
    Extract tabular data from every page.

    Returns
    -------
    list
        A list (one entry per page) of tables.  Each table is a list of
        rows, each row a list of cell strings.
    """
    all_tables: List[List[List[Optional[str]]]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                logger.debug(
                    "pdfplumber page %d: found %d table(s)", page_num, len(tables)
                )
                all_tables.extend(tables)
    except Exception:
        logger.exception("pdfplumber table extraction failed for '%s'", pdf_path)

    return all_tables


def extract_page_texts(pdf_path: str) -> Generator[Tuple[int, str], None, None]:
    """
    Lazily yield ``(page_number, text)`` tuples — memory-efficient for
    large multi-page PDFs.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                yield page_num, (page.extract_text() or "")
    except Exception:
        logger.exception("pdfplumber page iteration failed for '%s'", pdf_path)
