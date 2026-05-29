# PDF Invoice Extractor

I Created A production-ready Python tool that extracts structured data from PDF invoices — both text-based and scanned (OCR).

## Features

- **Dual extraction**: pdfplumber (primary) + PyMuPDF (fallback)
- **OCR support**: pytesseract + OpenCV for scanned/image PDFs
- **Smart detection**: automatically classifies text vs scanned PDFs
- **Robust regex**: compiled patterns with named groups, multi-format dates, locale-aware currency
- **Batch processing**: process multiple files in parallel via thread pool
- **Folder scanning**: recursively find and process all PDFs in a directory
- **Multiple exports**: JSON, CSV, Excel
- **Confidence scoring**: per-field + overall confidence (0–1)
- **Structured logging**: console + rotating file handler

## Extracted Fields

| Field | Examples |
|-------|---------|
| Invoice Number | INV-001, #12345 |
| Invoice Date | 01/15/2024, January 15, 2024 |
| Vendor Name | Acme Corp |
| Buyer Name | John Smith |
| Line Items | description, qty, unit price, total |
| Subtotal | 500.00 |
| Tax | 45.00 |
| Grand Total | 545.00 |

## Setup

```bash
# 1. Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Install Tesseract for OCR
#    Windows: https://github.com/UB-Mannheim/tesseract/wiki
#    Linux:   sudo apt install tesseract-ocr
#    macOS:   brew install tesseract
```

## Usage

```bash
# Single PDF → JSON
python main.py --input invoice.pdf --output json

# Multiple PDFs → CSV
python main.py --input inv1.pdf inv2.pdf --output csv

# Entire folder → Excel
python main.py --input-dir ./invoices --output excel

# Custom output directory & thread count
python main.py --input-dir ./invoices --output json --out-dir ./results --workers 8
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--input`, `-i` | One or more PDF file paths |
| `--input-dir`, `-d` | Directory to scan for PDFs (recursive) |
| `--output`, `-o` | Output format: `json`, `csv`, `excel` (default: json) |
| `--out-dir` | Output directory (default: `./output`) |
| `--workers`, `-w` | Thread pool size for batch mode (default: auto) |

## Project Structure

```
pdf converter/
├── main.py                              # CLI entry point
├── requirements.txt
├── README.md
└── pdf_extractor/
    ├── core/
    │   ├── detector.py                  # Text vs scanned classification
    │   ├── pipeline.py                  # Single-file orchestration
    │   └── batch_processor.py           # Parallel batch & folder processing
    ├── extractors/
    │   ├── pdfplumber_extractor.py       # Primary text extraction
    │   └── pymupdf_extractor.py          # Fallback extraction
    ├── ocr/
    │   └── ocr_engine.py                # Tesseract + OpenCV pipeline
    ├── parsers/
    │   ├── field_parser.py              # Regex field detection
    │   └── line_item_parser.py          # Table & text line-item parsing
    ├── models/
    │   └── invoice.py                   # Dataclasses + confidence scorer
    ├── exporters/
    │   └── exporter.py                  # JSON / CSV / Excel export
    └── utils/
        ├── logger.py                    # Logging configuration
        └── text_cleaner.py              # Text normalization
```

## Architecture Decisions

1. **Fallback chain** (`pdfplumber → PyMuPDF → OCR`): Different PDF producers create wildly different internal structures. A three-tier fallback ensures maximum coverage without requiring user intervention.

2. **Compiled regex with named groups**: Invoice formats vary enormously. Pre-compiled patterns with multiple alternatives per field handle the most common formats while keeping parsing fast (compile once, match many).

3. **ThreadPoolExecutor for batch**: PDF processing is I/O-heavy (disk reads, OCR). Threads give near-linear speedup on batch jobs without the overhead of multiprocessing.

4. **Lazy imports for OCR**: Tesseract and OpenCV are only imported if the OCR path is actually triggered. Users processing text-based PDFs don't need Tesseract installed at all.

5. **Dual CSV/Excel output**: Invoice headers and line items live in separate sheets/files because they have different row cardinalities — one summary row per invoice, multiple rows for line items.

6. **Confidence scoring**: Provides a quick quality signal so downstream consumers can flag invoices that need manual review.
