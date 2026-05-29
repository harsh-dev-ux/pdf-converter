"""
Data models for structured invoice representation.

Uses dataclasses for clarity and includes a confidence scoring system
that assigns a 0–1 score per field based on presence + format validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Line Item
# ---------------------------------------------------------------------------
@dataclass
class LineItem:
    """A single row in the invoice line-item table."""
    description: str = ""
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------
@dataclass
class Invoice:
    """Top-level invoice object aggregating all extracted fields."""
    source_file: str = ""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    vendor_name: Optional[str] = None
    buyer_name: Optional[str] = None
    line_items: List[LineItem] = field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    grand_total: Optional[float] = None
    confidence: Dict[str, float] = field(default_factory=dict)
    extraction_method: str = ""  # "pdfplumber" | "pymupdf" | "ocr"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["line_items"] = [item.to_dict() for item in self.line_items]
        return data


# ---------------------------------------------------------------------------
# Confidence Scorer
# ---------------------------------------------------------------------------
# Pre-compiled validation patterns
_RE_INVOICE_NUM = re.compile(r"[A-Za-z0-9\-/#]{2,}", re.IGNORECASE)
_RE_DATE = re.compile(
    r"\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4}"
    r"|[A-Za-z]+\s+\d{1,2},?\s+\d{4}"
)
_RE_MONEY = re.compile(r"\d+[.,]?\d*")


class ConfidenceScorer:
    """
    Assigns a 0-1 confidence score to each extracted field.

    Scoring rules:
    - 0.0  → field missing
    - 0.5  → field present but fails format validation
    - 1.0  → field present and passes validation
    - Line items scored as fraction of items with all sub-fields filled
    - Overall = weighted average of all field scores
    """

    # Weights for overall score calculation
    WEIGHTS: Dict[str, float] = {
        "invoice_number": 1.5,
        "invoice_date": 1.5,
        "vendor_name": 1.0,
        "buyer_name": 1.0,
        "line_items": 2.0,
        "subtotal": 1.0,
        "tax": 0.8,
        "grand_total": 1.5,
    }

    @classmethod
    def score(cls, invoice: Invoice) -> Dict[str, float]:
        """Compute per-field and overall confidence, then attach to invoice."""
        scores: Dict[str, float] = {}

        scores["invoice_number"] = cls._score_text(
            invoice.invoice_number, _RE_INVOICE_NUM
        )
        scores["invoice_date"] = cls._score_text(
            invoice.invoice_date, _RE_DATE
        )
        scores["vendor_name"] = cls._score_presence(invoice.vendor_name)
        scores["buyer_name"] = cls._score_presence(invoice.buyer_name)
        scores["subtotal"] = cls._score_numeric(invoice.subtotal)
        scores["tax"] = cls._score_numeric(invoice.tax)
        scores["grand_total"] = cls._score_numeric(invoice.grand_total)
        scores["line_items"] = cls._score_line_items(invoice.line_items)

        # Weighted average
        total_weight = sum(cls.WEIGHTS.values())
        weighted = sum(
            scores.get(k, 0.0) * w for k, w in cls.WEIGHTS.items()
        )
        scores["overall"] = round(weighted / total_weight, 3) if total_weight else 0.0

        invoice.confidence = scores
        logger.info("Confidence scored — overall: %.2f", scores["overall"])
        return scores

    # --- private helpers ---------------------------------------------------

    @staticmethod
    def _score_presence(value: Optional[str]) -> float:
        if not value or not value.strip():
            return 0.0
        return 1.0 if len(value.strip()) >= 2 else 0.5

    @staticmethod
    def _score_text(value: Optional[str], pattern: re.Pattern) -> float:
        if not value:
            return 0.0
        return 1.0 if pattern.search(value) else 0.5

    @staticmethod
    def _score_numeric(value: Optional[float]) -> float:
        if value is None:
            return 0.0
        return 1.0 if value >= 0 else 0.5

    @staticmethod
    def _score_line_items(items: List[LineItem]) -> float:
        if not items:
            return 0.0
        filled = sum(
            1 for i in items
            if i.description and i.quantity is not None
            and i.unit_price is not None and i.total is not None
        )
        return round(filled / len(items), 3)
