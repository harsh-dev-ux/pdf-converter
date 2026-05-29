"""
Invoice processing pipeline — single-file orchestrator.

Flow:
    detect → extract (with fallback chain) → clean → parse → score → return Invoice
"""

from __future__ import annotations

import os
from typing import List

from pdf_extractor.core.detector import PDFType, detect
from pdf_extractor.extractors import pdfplumber_extractor, pymupdf_extractor
from pdf_extractor.models.invoice import ConfidenceScorer, Invoice, LineItem
from pdf_extractor.ocr.ocr_engine import ocr_pdf
from pdf_extractor.parsers import field_parser, line_item_parser
from pdf_extractor.utils.logger import get_logger
from pdf_extractor.utils.text_cleaner import clean_text

logger = get_logger(__name__)

# Minimum chars to accept from the primary extractor before trying fallback
_MIN_USEFUL_TEXT = 30


class InvoicePipeline:
    """
    End-to-end processor for a single PDF invoice.

    Usage::

        pipeline = InvoicePipeline()
        invoice = pipeline.process("path/to/invoice.pdf")
        print(invoice.to_dict())
    """

    def process(self, pdf_path: str) -> Invoice:
        """
        Process a single PDF and return a populated ``Invoice`` object.

        Parameters
        ----------
        pdf_path : str
            Absolute or relative path to the PDF file.

        Returns
        -------
        Invoice
            Parsed invoice data with confidence scores attached.
        """
        pdf_path = os.path.abspath(pdf_path)
        logger.info("=" * 60)
        logger.info("Processing: %s", pdf_path)

        invoice = Invoice(source_file=pdf_path)

        # ------------------------------------------------------------------
        # 1. DETECT
        # ------------------------------------------------------------------
        pdf_type, page_count = detect(pdf_path)

        # ------------------------------------------------------------------
        # 2. EXTRACT raw text (with fallback chain)
        # ------------------------------------------------------------------
        raw_text = ""
        tables: list = []

        if pdf_type == PDFType.TEXT:
            # Primary: pdfplumber
            raw_text = pdfplumber_extractor.extract_text(pdf_path)
            tables = pdfplumber_extractor.extract_tables(pdf_path)
            invoice.extraction_method = "pdfplumber"

            # Fallback: PyMuPDF if pdfplumber gave too little
            if len(raw_text.strip()) < _MIN_USEFUL_TEXT:
                logger.warning("pdfplumber returned insufficient text, trying PyMuPDF")
                raw_text = pymupdf_extractor.extract_text(pdf_path)
                invoice.extraction_method = "pymupdf"
        else:
            # Scanned → OCR
            raw_text = ocr_pdf(pdf_path)
            invoice.extraction_method = "ocr"

            # If OCR also fails, try PyMuPDF as last resort (some "scanned"
            # PDFs still embed selectable text layers)
            if len(raw_text.strip()) < _MIN_USEFUL_TEXT:
                logger.warning("OCR returned insufficient text, trying PyMuPDF")
                raw_text = pymupdf_extractor.extract_text(pdf_path)
                invoice.extraction_method = "pymupdf"

        # ------------------------------------------------------------------
        # 3. CLEAN
        # ------------------------------------------------------------------
        cleaned_text = clean_text(raw_text)
        logger.debug("Cleaned text length: %d chars", len(cleaned_text))

        if not cleaned_text:
            logger.error("No text could be extracted from '%s'", pdf_path)
            ConfidenceScorer.score(invoice)
            return invoice

        # ------------------------------------------------------------------
        # 4. PARSE header fields
        # ------------------------------------------------------------------
        fields = field_parser.parse_all(cleaned_text)
        invoice.invoice_number = fields["invoice_number"]
        invoice.invoice_date = fields["invoice_date"]
        invoice.vendor_name = fields["vendor_name"]
        invoice.buyer_name = fields["buyer_name"]
        invoice.subtotal = fields["subtotal"]
        invoice.tax = fields["tax"]
        invoice.grand_total = fields["grand_total"]

        # ------------------------------------------------------------------
        # 5. PARSE line items (tables first, then regex fallback)
        # ------------------------------------------------------------------
        items: List[LineItem] = []
        if tables:
            items = line_item_parser.from_tables(tables)
        if not items:
            items = line_item_parser.from_text(cleaned_text)
        invoice.line_items = items

        # ------------------------------------------------------------------
        # 6. SCORE confidence
        # ------------------------------------------------------------------
        ConfidenceScorer.score(invoice)

        logger.info(
            "Done — method=%s, confidence=%.2f",
            invoice.extraction_method,
            invoice.confidence.get("overall", 0),
        )
        return invoice
