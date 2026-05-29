"""
OCR engine for scanned / image-based PDFs.

Pipeline:
1. Convert each PDF page to a high-DPI image via PyMuPDF.
2. Pre-process with OpenCV (grayscale → Otsu threshold → denoise).
3. Run Tesseract OCR via pytesseract.

Requires Tesseract to be installed on the system:
    - Windows: https://github.com/UB-Mannheim/tesseract/wiki
    - Linux:   ``sudo apt install tesseract-ocr``
    - macOS:   ``brew install tesseract``
"""

from __future__ import annotations

from typing import List

import numpy as np

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy imports — allow the rest of the project to work without Tesseract /
# OpenCV when OCR isn't needed.
_cv2 = None
_pytesseract = None
_fitz = None


def _lazy_imports():
    """Import heavy OCR dependencies on first use."""
    global _cv2, _pytesseract, _fitz
    if _cv2 is None:
        import cv2
        import pytesseract
        import fitz
        _cv2 = cv2
        _pytesseract = pytesseract
        _fitz = fitz


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------

def _preprocess_image(img_array: np.ndarray) -> np.ndarray:
    """
    Prepare an image for Tesseract.

    Steps:
        1. Convert to grayscale.
        2. Apply Otsu's binarization.
        3. Denoise with morphological opening.
    """
    _lazy_imports()
    gray = _cv2.cvtColor(img_array, _cv2.COLOR_BGR2GRAY)

    # Otsu threshold
    _, binary = _cv2.threshold(gray, 0, 255, _cv2.THRESH_BINARY + _cv2.THRESH_OTSU)

    # Morphological denoise (removes small noise spots)
    kernel = _cv2.getStructuringElement(_cv2.MORPH_RECT, (1, 1))
    cleaned = _cv2.morphologyEx(binary, _cv2.MORPH_OPEN, kernel)

    return cleaned


def _page_to_image(page, dpi: int = 300) -> np.ndarray:
    """Render a PyMuPDF page to a numpy BGR array at the given DPI."""
    zoom = dpi / 72  # 72 is the default PDF DPI
    mat = _fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    # Convert RGBA → BGR if needed
    if pix.n == 4:
        img = _cv2.cvtColor(img, _cv2.COLOR_RGBA2BGR)
    elif pix.n == 1:
        img = _cv2.cvtColor(img, _cv2.COLOR_GRAY2BGR)
    return img


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ocr_pdf(pdf_path: str, dpi: int = 300, lang: str = "eng") -> str:
    """
    Run OCR on every page of a PDF and return the full text.

    Parameters
    ----------
    pdf_path : str
        Path to the (scanned) PDF.
    dpi : int
        Render resolution.  Higher → better accuracy but slower.
    lang : str
        Tesseract language pack (e.g. ``eng``, ``deu``).

    Returns
    -------
    str
        Concatenated OCR text from all pages.
    """
    _lazy_imports()
    pages_text: List[str] = []

    try:
        doc = _fitz.open(pdf_path)
        total_pages = len(doc)
        logger.info("OCR: processing %d page(s) at %d DPI", total_pages, dpi)

        for page_num, page in enumerate(doc, start=1):
            logger.debug("OCR page %d/%d", page_num, total_pages)
            img = _page_to_image(page, dpi=dpi)
            processed = _preprocess_image(img)
            text = _pytesseract.image_to_string(processed, lang=lang)
            pages_text.append(text)
            logger.debug("OCR page %d: got %d chars", page_num, len(text))

        doc.close()
    except Exception:
        logger.exception("OCR failed for '%s'", pdf_path)
        return ""

    return "\n\n".join(pages_text)
