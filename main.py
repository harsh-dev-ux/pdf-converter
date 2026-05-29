#!/usr/bin/env python3
"""
PDF Invoice Extractor — CLI Entry Point
========================================

Usage examples::

    # Single file → JSON
    python main.py --input invoice.pdf --output json

    # Multiple files → CSV
    python main.py --input inv1.pdf inv2.pdf --output csv

    # Entire folder → Excel
    python main.py --input-dir ./invoices --output excel --out-dir ./results

    # Folder processing with custom thread count
    python main.py --input-dir ./invoices --output json --workers 8
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from pdf_extractor.core.batch_processor import BatchProcessor
from pdf_extractor.core.pipeline import InvoicePipeline
from pdf_extractor.exporters import exporter
from pdf_extractor.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

# Supported output formats
OUTPUT_FORMATS = {"json", "csv", "excel"}


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdf-invoice-extractor",
        description="Extract structured data from PDF invoices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --input invoice.pdf --output json\n"
            "  python main.py --input a.pdf b.pdf --output csv --out-dir results\n"
            "  python main.py --input-dir ./invoices --output excel\n"
        ),
    )
    # Input — mutually exclusive: file list OR directory
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input", "-i",
        nargs="+",
        metavar="FILE",
        help="One or more PDF file paths.",
    )
    input_group.add_argument(
        "--input-dir", "-d",
        metavar="DIR",
        help="Directory to scan for *.pdf files (recursive).",
    )

    # Output
    parser.add_argument(
        "--output", "-o",
        choices=sorted(OUTPUT_FORMATS),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        default="output",
        help="Directory to write output files (default: ./output).",
    )

    # Performance
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        metavar="N",
        help="Thread-pool size for batch processing (default: auto).",
    )

    return parser


def _output_path(out_dir: str, fmt: str) -> str:
    """Generate a default output file path based on format."""
    ext_map = {"json": ".json", "csv": ".csv", "excel": ".xlsx"}
    return os.path.join(out_dir, f"invoices{ext_map[fmt]}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on error."""
    setup_logging()
    args = build_parser().parse_args(argv)
    start_time = time.perf_counter()

    os.makedirs(args.out_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Collect invoices
    # ------------------------------------------------------------------
    invoices = []
    errors = {}

    if args.input_dir:
        # Folder / batch mode
        bp = BatchProcessor(max_workers=args.workers)
        result = bp.process_directory(args.input_dir)
        invoices = result.invoices
        errors = result.errors
    elif len(args.input) > 1:
        # Multiple explicit files → batch
        bp = BatchProcessor(max_workers=args.workers)
        result = bp.process_files(args.input)
        invoices = result.invoices
        errors = result.errors
    else:
        # Single file
        pipeline = InvoicePipeline()
        try:
            inv = pipeline.process(args.input[0])
            invoices.append(inv)
        except Exception as exc:
            logger.exception("Failed to process '%s'", args.input[0])
            errors[args.input[0]] = str(exc)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    if invoices:
        out_path = _output_path(args.out_dir, args.output)
        if args.output == "json":
            exporter.to_json(invoices, out_path)
        elif args.output == "csv":
            exporter.to_csv(invoices, out_path)
        elif args.output == "excel":
            exporter.to_excel(invoices, out_path)
        print(f"\n[OK] Exported {len(invoices)} invoice(s) -> {out_path}")
    else:
        print("\n[WARN] No invoices were extracted successfully.")

    # ------------------------------------------------------------------
    # Report errors
    # ------------------------------------------------------------------
    if errors:
        print(f"\n[FAIL] {len(errors)} file(s) failed:")
        for path, err in errors.items():
            print(f"    - {path}: {err}")

    elapsed = time.perf_counter() - start_time
    print(f"\n[TIME] Completed in {elapsed:.2f}s")
    return 0 if invoices else 1


if __name__ == "__main__":
    sys.exit(main())
