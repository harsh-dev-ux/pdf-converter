"""
Batch & folder processor with thread-pool parallelism.

Supports:
- Processing a list of individual PDF paths.
- Recursively scanning a directory for ``*.pdf`` files.
- Parallel execution via ``concurrent.futures.ThreadPoolExecutor``.
"""

from __future__ import annotations

import glob
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pdf_extractor.core.pipeline import InvoicePipeline
from pdf_extractor.models.invoice import Invoice
from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BatchResult:
    """Container for the results of a batch processing run."""
    invoices: List[Invoice] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.invoices) + len(self.errors)

    @property
    def success_count(self) -> int:
        return len(self.invoices)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class BatchProcessor:
    """
    Process multiple PDFs in parallel.

    Parameters
    ----------
    max_workers : int or None
        Thread-pool size.  ``None`` lets the executor choose a default
        based on CPU count.

    Usage::

        bp = BatchProcessor(max_workers=4)
        result = bp.process_files(["a.pdf", "b.pdf"])
        result = bp.process_directory("./invoices")
    """

    def __init__(self, max_workers: Optional[int] = None):
        self._max_workers = max_workers
        self._pipeline = InvoicePipeline()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_files(self, pdf_paths: List[str]) -> BatchResult:
        """Process an explicit list of PDF file paths."""
        logger.info("Batch: processing %d file(s) (workers=%s)",
                     len(pdf_paths), self._max_workers or "auto")
        return self._run(pdf_paths)

    def process_directory(self, directory: str, recursive: bool = True) -> BatchResult:
        """
        Scan a directory for ``*.pdf`` files and process them.

        Parameters
        ----------
        directory : str
            Root folder to scan.
        recursive : bool
            If True, search sub-folders as well.
        """
        pattern = os.path.join(directory, "**", "*.pdf") if recursive else \
                  os.path.join(directory, "*.pdf")
        pdf_paths = glob.glob(pattern, recursive=recursive)

        if not pdf_paths:
            logger.warning("No PDF files found in '%s'", directory)
            return BatchResult()

        logger.info("Batch: found %d PDF(s) in '%s'", len(pdf_paths), directory)
        return self._run(pdf_paths)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, pdf_paths: List[str]) -> BatchResult:
        result = BatchResult()

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_path = {
                executor.submit(self._safe_process, path): path
                for path in pdf_paths
            }
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                invoice, error = future.result()
                if error:
                    result.errors[path] = error
                else:
                    result.invoices.append(invoice)

        logger.info(
            "Batch complete: %d succeeded, %d failed",
            result.success_count, result.error_count,
        )
        return result

    def _safe_process(self, pdf_path: str):
        """Wrapper that catches exceptions so one file can't crash the pool."""
        try:
            invoice = self._pipeline.process(pdf_path)
            return invoice, None
        except Exception as exc:
            logger.exception("Failed to process '%s'", pdf_path)
            return None, str(exc)
