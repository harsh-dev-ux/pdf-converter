"""
Text cleaning utilities for raw PDF / OCR output.

Handles:
- Extra whitespace collapse
- Broken-line rejoining
- Non-printable character removal
- Unicode normalization
"""

import re
import unicodedata

from pdf_extractor.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pre-compiled patterns (performance: compile once, use many times)
# ---------------------------------------------------------------------------
_RE_MULTI_SPACE = re.compile(r"[ \t]+")
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")
_RE_BROKEN_LINE = re.compile(r"(?<=[a-z,])\n(?=[a-z])")
_RE_NON_PRINTABLE = re.compile(
    r"[^\x20-\x7E\n\r\t"
    r"\u00A0-\u00FF"      # Latin-1 Supplement
    r"\u0100-\u024F"      # Latin Extended-A/B
    r"\u2000-\u206F"      # General Punctuation
    r"\u20A0-\u20CF"      # Currency Symbols
    r"]"
)


def normalize_unicode(text: str) -> str:
    """Normalize to NFC form so combining characters are collapsed."""
    return unicodedata.normalize("NFC", text)


def strip_non_printable(text: str) -> str:
    """Remove characters that don't contribute to readable invoice data."""
    return _RE_NON_PRINTABLE.sub("", text)


def collapse_whitespace(text: str) -> str:
    """Replace runs of spaces / tabs with a single space (per line)."""
    lines = text.splitlines()
    cleaned = [_RE_MULTI_SPACE.sub(" ", line).strip() for line in lines]
    return "\n".join(cleaned)


def fix_broken_lines(text: str) -> str:
    """
    Rejoin lines that were broken mid-sentence (common in OCR output).

    Heuristic: if a line ends with a lowercase letter or comma and the
    next line starts with a lowercase letter, merge them.
    """
    return _RE_BROKEN_LINE.sub(" ", text)


def reduce_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive newlines to 2."""
    return _RE_MULTI_NEWLINE.sub("\n\n", text)


def clean_text(text: str) -> str:
    """
    Full cleaning pipeline applied to every page of extracted text.

    Order matters:
    1. Unicode normalize
    2. Strip non-printable
    3. Collapse whitespace
    4. Fix broken lines
    5. Reduce blank lines
    """
    if not text:
        return ""

    logger.debug("Cleaning text (%d chars)", len(text))
    text = normalize_unicode(text)
    text = strip_non_printable(text)
    text = collapse_whitespace(text)
    text = fix_broken_lines(text)
    text = reduce_blank_lines(text)
    return text.strip()
