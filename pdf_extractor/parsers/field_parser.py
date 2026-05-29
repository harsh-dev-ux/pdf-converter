"""
Regex-based field parser for invoice header / summary fields.

Design decisions
----------------
- All patterns are **pre-compiled** for performance.
- Named capture groups make extraction self-documenting.
- Multiple alternative patterns per field cover common invoice layouts
  (e.g. "Invoice #", "Inv No.", "Invoice Number:").
- Currency patterns handle ``$``, ``€``, ``£`` and both ``,`` / ``.``
  decimal separators.
"""

from __future__ import annotations

import re
from typing import Optional

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================================
# COMPILED PATTERN REGISTRY
# ============================================================================

# --- Invoice Number --------------------------------------------------------
_INVOICE_NUM_PATTERNS = [
    re.compile(
        r"(?:invoice|inv)[.\s]*(?:no|number|#|num)[.:]*\s*(?P<value>[A-Za-z0-9\-/]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:invoice|inv)[.\s]*[#:]\s*(?P<value>[A-Za-z0-9\-/]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"#\s*(?P<value>INV[\-]?\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:bill|receipt)\s*(?:no|number|#)[.:]*\s*(?P<value>[A-Za-z0-9\-/]+)",
        re.IGNORECASE,
    ),
]

# --- Invoice Date ----------------------------------------------------------
_DATE_PATTERNS = [
    # MM/DD/YYYY or DD/MM/YYYY or YYYY/MM/DD  (with / - .)
    re.compile(
        r"(?:invoice\s*date|date\s*of\s*invoice|date|dated|billing\s*date)"
        r"[:\s]*(?P<value>\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        re.IGNORECASE,
    ),
    # Month DD, YYYY  /  DD Month YYYY
    re.compile(
        r"(?:invoice\s*date|date|dated|billing\s*date)[:\s]*"
        r"(?P<value>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\.?\s+\d{1,2},?\s+\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:invoice\s*date|date|dated|billing\s*date)[:\s]*"
        r"(?P<value>\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\.?,?\s+\d{4})",
        re.IGNORECASE,
    ),
    # Standalone ISO date (fallback)
    re.compile(
        r"(?P<value>\d{4}-\d{2}-\d{2})",
    ),
]

# --- Vendor / Seller -------------------------------------------------------
_VENDOR_PATTERNS = [
    re.compile(
        r"(?:vendor|seller|supplier|from|sold\s*by|company)[:\s]*"
        r"(?P<value>[A-Za-z0-9 &.,'\-]{2,60})",
        re.IGNORECASE,
    ),
]

# --- Buyer / Bill To -------------------------------------------------------
_BUYER_PATTERNS = [
    re.compile(
        r"(?:buyer|bill\s*to|billed\s*to|customer|sold\s*to|ship\s*to|client)"
        r"[:\s]*(?P<value>[A-Za-z0-9 &.,'\-]{2,60})",
        re.IGNORECASE,
    ),
]

# --- Currency & Monetary Values -------------------------------------------
_CURRENCY = r"[\$€£₹]?\s*"
_AMOUNT = r"(?P<value>\d{1,3}(?:[,. ]\d{3})*(?:[.,]\d{1,2})?)"

_SUBTOTAL_PATTERNS = [
    re.compile(
        r"(?:sub\s*total|subtotal)[:\s]*" + _CURRENCY + _AMOUNT,
        re.IGNORECASE,
    ),
]

_TAX_PATTERNS = [
    re.compile(
        r"(?:tax|vat|gst|sales\s*tax|hst)[:\s]*" + _CURRENCY + _AMOUNT,
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:tax|vat|gst)\s*\(\s*\d+\.?\d*\s*%\s*\)[:\s]*" + _CURRENCY + _AMOUNT,
        re.IGNORECASE,
    ),
]

_GRAND_TOTAL_PATTERNS = [
    re.compile(
        r"(?:grand\s*total|total\s*due|total\s*amount|amount\s*due|balance\s*due|total)"
        r"[:\s]*" + _CURRENCY + _AMOUNT,
        re.IGNORECASE,
    ),
]


# ============================================================================
# EXTRACTION HELPERS
# ============================================================================

def _first_match(patterns: list[re.Pattern], text: str) -> Optional[str]:
    """Return the ``value`` group from the first matching pattern, or None."""
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            value = m.group("value").strip()
            if value:
                return value
    return None


def _parse_money(raw: Optional[str]) -> Optional[float]:
    """Normalize a monetary string like ``1,234.56`` → ``1234.56`` float."""
    if not raw:
        return None
    # Remove spaces and currency symbols
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if not cleaned:
        return None

    # Determine decimal separator (last occurrence of . or ,)
    if "." in cleaned and "," in cleaned:
        # e.g. "1,234.56" or "1.234,56"
        if cleaned.rfind(",") > cleaned.rfind("."):
            # European: 1.234,56
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # US: 1,234.56
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) == 2:
            # likely decimal comma
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


# ============================================================================
# PUBLIC API
# ============================================================================

def parse_invoice_number(text: str) -> Optional[str]:
    """Extract invoice number from raw text."""
    result = _first_match(_INVOICE_NUM_PATTERNS, text)
    logger.debug("Parsed invoice_number: %s", result)
    return result


def parse_invoice_date(text: str) -> Optional[str]:
    """Extract invoice date from raw text."""
    result = _first_match(_DATE_PATTERNS, text)
    logger.debug("Parsed invoice_date: %s", result)
    return result


def parse_vendor_name(text: str) -> Optional[str]:
    """Extract vendor / seller name."""
    result = _first_match(_VENDOR_PATTERNS, text)
    logger.debug("Parsed vendor_name: %s", result)
    return result


def parse_buyer_name(text: str) -> Optional[str]:
    """Extract buyer / bill-to name."""
    result = _first_match(_BUYER_PATTERNS, text)
    logger.debug("Parsed buyer_name: %s", result)
    return result


def parse_subtotal(text: str) -> Optional[float]:
    """Extract subtotal amount."""
    raw = _first_match(_SUBTOTAL_PATTERNS, text)
    result = _parse_money(raw)
    logger.debug("Parsed subtotal: %s", result)
    return result


def parse_tax(text: str) -> Optional[float]:
    """Extract tax amount."""
    raw = _first_match(_TAX_PATTERNS, text)
    result = _parse_money(raw)
    logger.debug("Parsed tax: %s", result)
    return result


def parse_grand_total(text: str) -> Optional[float]:
    """Extract grand total / amount due."""
    raw = _first_match(_GRAND_TOTAL_PATTERNS, text)
    result = _parse_money(raw)
    logger.debug("Parsed grand_total: %s", result)
    return result


def parse_all(text: str) -> dict:
    """
    Run every field parser and return results as a dict.

    Useful when you want all fields at once from a single text blob.
    """
    return {
        "invoice_number": parse_invoice_number(text),
        "invoice_date": parse_invoice_date(text),
        "vendor_name": parse_vendor_name(text),
        "buyer_name": parse_buyer_name(text),
        "subtotal": parse_subtotal(text),
        "tax": parse_tax(text),
        "grand_total": parse_grand_total(text),
    }
