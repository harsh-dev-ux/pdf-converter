"""
Centralized logging configuration.

Provides per-module loggers with console (INFO) and rotating file (DEBUG)
handlers so every module simply calls ``get_logger(__name__)``.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "extractor.log")
LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file
BACKUP_COUNT = 3

_initialized = False


def _ensure_log_dir() -> None:
    """Create the log directory if it doesn't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging(console_level: int = logging.INFO,
                  file_level: int = logging.DEBUG) -> None:
    """
    Initialize the root logger once.

    Parameters
    ----------
    console_level : int
        Minimum severity printed to stdout.
    file_level : int
        Minimum severity written to the rotating log file.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    _ensure_log_dir()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger, initializing the logging system on first call.

    Usage::

        from pdf_extractor.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Processing started")
    """
    setup_logging()
    return logging.getLogger(name)
