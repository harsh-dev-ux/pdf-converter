"""
Line-item table parser.

Strategy:
1. Try to use structured tables from pdfplumber (best quality).
2. Fall back to regex-based row extraction from raw text.
"""

from __future__ import annotations

import re
from typing import List, Optional

from pdf_extractor.models.invoice import LineItem
from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Header-detection patterns (case-insensitive)
# ---------------------------------------------------------------------------
_HEADER_KEYWORDS = re.compile(
    r"description|item|product|service|particular|qty|quantity|"
    r"price|rate|unit\s*price|amount|total",
    re.IGNORECASE,
)

# Regex for a line-item row in unstructured text:
#   description   qty   unit_price   total
_LINE_ITEM_ROW = re.compile(
    r"(?P<desc>[A-Za-z][A-Za-z0-9 &.,/\-]{2,60}?)"  # description
    r"\s+"
    r"(?P<qty>\d+(?:\.\d+)?)"                         # quantity
    r"\s+"
    r"(?P<price>\d{1,3}(?:[,. ]\d{3})*(?:\.\d{1,2})?)"  # unit price
    r"\s+"
    r"(?P<total>\d{1,3}(?:[,. ]\d{3})*(?:\.\d{1,2})?)"  # line total
)


# ---------------------------------------------------------------------------
# Table-based extraction
# ---------------------------------------------------------------------------

def _identify_columns(header_row: list) -> dict:
    """
    Map column indices to semantic roles based on header keywords.

    Returns a dict like ``{"desc": 0, "qty": 1, "price": 2, "total": 3}``.
    """
    mapping: dict = {}
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        cell_lower = cell.strip().lower()

        if any(kw in cell_lower for kw in ("description", "item", "product",
                                            "service", "particular")):
            mapping.setdefault("desc", idx)
        elif any(kw in cell_lower for kw in ("qty", "quantity", "units")):
            mapping.setdefault("qty", idx)
        elif any(kw in cell_lower for kw in ("price", "rate", "unit")):
            mapping.setdefault("price", idx)
        elif any(kw in cell_lower for kw in ("amount", "total", "line total")):
            mapping.setdefault("total", idx)

    return mapping


def _safe_float(val: Optional[str]) -> Optional[float]:
    """Convert a cell value to float, returning None on failure."""
    if val is None:
        return None
    cleaned = re.sub(r"[^\d.,]", "", str(val))
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", "")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def from_tables(tables: list) -> List[LineItem]:
    """
    Extract ``LineItem`` objects from pdfplumber-style table data.

    Parameters
    ----------
    tables : list
        List of tables, where each table is a list of rows (list of cells).
    """
    items: List[LineItem] = []

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Find the header row
        col_map: dict = {}
        data_start = 0
        for row_idx, row in enumerate(table):
            row_text = " ".join(str(c) for c in row if c)
            if _HEADER_KEYWORDS.search(row_text):
                col_map = _identify_columns(row)
                data_start = row_idx + 1
                break

        if not col_map:
            logger.debug("No header row found in table, skipping")
            continue

        # Extract data rows
        for row in table[data_start:]:
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            desc = ""
            if "desc" in col_map and col_map["desc"] < len(row):
                desc = str(row[col_map["desc"]] or "").strip()

            qty = None
            if "qty" in col_map and col_map["qty"] < len(row):
                qty = _safe_float(row[col_map["qty"]])

            price = None
            if "price" in col_map and col_map["price"] < len(row):
                price = _safe_float(row[col_map["price"]])

            total = None
            if "total" in col_map and col_map["total"] < len(row):
                total = _safe_float(row[col_map["total"]])

            # Skip empty / junk rows
            if not desc and qty is None and price is None and total is None:
                continue

            items.append(LineItem(
                description=desc, quantity=qty,
                unit_price=price, total=total,
            ))

    logger.info("Table extraction: found %d line item(s)", len(items))
    return items


# ---------------------------------------------------------------------------
# Regex fallback
# ---------------------------------------------------------------------------

def from_text(text: str) -> List[LineItem]:
    """
    Extract line items from raw text via regex when no table is available.
    """
    items: List[LineItem] = []

    for m in _LINE_ITEM_ROW.finditer(text):
        desc = m.group("desc").strip()
        qty = _safe_float(m.group("qty"))
        price = _safe_float(m.group("price"))
        total = _safe_float(m.group("total"))
        items.append(LineItem(
            description=desc, quantity=qty,
            unit_price=price, total=total,
        ))

    logger.info("Regex fallback: found %d line item(s)", len(items))
    return items
