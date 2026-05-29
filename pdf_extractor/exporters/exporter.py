"""
Export helpers — JSON, CSV, and Excel output.

Supports single and batch invoice exports.  Batch mode merges all
invoices into one file; single mode produces one file per invoice.
"""

from __future__ import annotations

import json
import os
from typing import List

import pandas as pd

from pdf_extractor.models.invoice import Invoice
from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _invoice_to_flat_dict(inv: Invoice) -> dict:
    """Flatten an Invoice into a single-level dict suitable for tabular export."""
    base = {
        "source_file": inv.source_file,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "vendor_name": inv.vendor_name,
        "buyer_name": inv.buyer_name,
        "subtotal": inv.subtotal,
        "tax": inv.tax,
        "grand_total": inv.grand_total,
        "extraction_method": inv.extraction_method,
        "confidence_overall": inv.confidence.get("overall"),
    }
    return base


def _line_items_to_dicts(inv: Invoice) -> list[dict]:
    """Return a list of flat dicts for line-item rows."""
    rows = []
    for idx, item in enumerate(inv.line_items, start=1):
        rows.append({
            "source_file": inv.source_file,
            "invoice_number": inv.invoice_number,
            "line_item_index": idx,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total": item.total,
        })
    return rows


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_json(invoices: List[Invoice], output_path: str) -> str:
    """
    Export invoices to a JSON file.

    Returns the absolute path of the written file.
    """
    _ensure_dir(output_path)
    data = [inv.to_dict() for inv in invoices]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Exported JSON → %s", output_path)
    return os.path.abspath(output_path)


def to_csv(invoices: List[Invoice], output_path: str) -> str:
    """
    Export invoices to CSV.

    Produces two files:
    - ``<name>_summary.csv`` — one row per invoice header.
    - ``<name>_line_items.csv`` — one row per line item.

    Returns the summary CSV path.
    """
    _ensure_dir(output_path)
    base, ext = os.path.splitext(output_path)
    summary_path = f"{base}_summary.csv"
    items_path = f"{base}_line_items.csv"

    # Summary
    summary_rows = [_invoice_to_flat_dict(inv) for inv in invoices]
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False, encoding="utf-8")

    # Line items
    item_rows: list[dict] = []
    for inv in invoices:
        item_rows.extend(_line_items_to_dicts(inv))
    if item_rows:
        pd.DataFrame(item_rows).to_csv(items_path, index=False, encoding="utf-8")

    logger.info("Exported CSV → %s, %s", summary_path, items_path)
    return os.path.abspath(summary_path)


def to_excel(invoices: List[Invoice], output_path: str) -> str:
    """
    Export invoices to an Excel workbook with two sheets:
    ``Summary`` and ``Line Items``.
    """
    _ensure_dir(output_path)

    summary_rows = [_invoice_to_flat_dict(inv) for inv in invoices]
    item_rows: list[dict] = []
    for inv in invoices:
        item_rows.extend(_line_items_to_dicts(inv))

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        if item_rows:
            pd.DataFrame(item_rows).to_excel(writer, sheet_name="Line Items", index=False)

    logger.info("Exported Excel → %s", output_path)
    return os.path.abspath(output_path)
