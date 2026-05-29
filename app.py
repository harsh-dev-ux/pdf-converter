"""
PDF Invoice Extractor — Flask Web Application
===============================================

Provides a drag-and-drop web UI for uploading PDF invoices and
downloading extracted data as JSON, CSV, or Excel.

Usage::

    python app.py
    # Open http://localhost:5000 in your browser
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
import zipfile
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    send_from_directory,
)

from pdf_extractor.core.batch_processor import BatchProcessor
from pdf_extractor.core.pipeline import InvoicePipeline
from pdf_extractor.exporters import exporter
from pdf_extractor.utils.logger import get_logger, setup_logging

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 50 * 1024 * 1024  # 100 files x 50 MB
UPLOAD_DIR = Path("temp_uploads")
RESULTS_DIR = Path("temp_results")
MAX_FILES = 100
ALLOWED_EXTENSIONS = {".pdf"}

setup_logging()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _cleanup_dir(directory: Path) -> None:
    """Remove a temporary directory and its contents."""
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main upload page."""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """
    Accept PDF uploads, process them, and return a download link.

    Expects:
        - ``files``: one or more PDF files (multipart/form-data)
        - ``format``: output format — ``json``, ``csv``, or ``excel``
    """
    start = time.perf_counter()

    # --- Validate format ---
    output_format = request.form.get("format", "json").lower()
    if output_format not in ("json", "csv", "excel"):
        return jsonify({"error": "Invalid format. Use json, csv, or excel."}), 400

    # --- Validate files ---
    files = request.files.getlist("files")
    if not files or files[0].filename == "":
        return jsonify({"error": "No files uploaded."}), 400
    if len(files) > MAX_FILES:
        return jsonify({"error": f"Maximum {MAX_FILES} files allowed."}), 400

    # --- Save uploads ---
    job_id = str(uuid.uuid4())[:8]
    upload_dir = UPLOAD_DIR / job_id
    result_dir = RESULTS_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    rejected = []
    for f in files:
        if f.filename and _allowed_file(f.filename):
            safe_name = f"{len(saved_paths) + 1}_{Path(f.filename).name}"
            save_path = upload_dir / safe_name
            f.save(str(save_path))
            saved_paths.append(str(save_path))
        else:
            rejected.append(f.filename or "unknown")

    if not saved_paths:
        _cleanup_dir(upload_dir)
        return jsonify({"error": "No valid PDF files found."}), 400

    logger.info("Job %s: %d file(s) uploaded, %d rejected", job_id, len(saved_paths), len(rejected))

    # --- Process ---
    try:
        if len(saved_paths) == 1:
            pipeline = InvoicePipeline()
            invoice = pipeline.process(saved_paths[0])
            invoices = [invoice]
            errors = {}
        else:
            bp = BatchProcessor(max_workers=4)
            result = bp.process_files(saved_paths)
            invoices = result.invoices
            errors = result.errors
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        _cleanup_dir(upload_dir)
        _cleanup_dir(result_dir)
        return jsonify({"error": f"Processing failed: {str(exc)}"}), 500

    if not invoices:
        _cleanup_dir(upload_dir)
        _cleanup_dir(result_dir)
        return jsonify({"error": "Could not extract data from any uploaded PDF."}), 422

    # --- Export ---
    ext_map = {"json": ".json", "csv": ".csv", "excel": ".xlsx"}
    out_filename = f"invoices_{job_id}{ext_map[output_format]}"
    out_path = str(result_dir / out_filename)

    try:
        if output_format == "json":
            exporter.to_json(invoices, out_path)
        elif output_format == "csv":
            exporter.to_csv(invoices, out_path)
            # CSV produces two files — zip them
            base = os.path.splitext(out_path)[0]
            summary_csv = f"{base}_summary.csv"
            items_csv = f"{base}_line_items.csv"
            zip_name = f"invoices_{job_id}.zip"
            zip_path = str(result_dir / zip_name)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(summary_csv):
                    zf.write(summary_csv, os.path.basename(summary_csv))
                if os.path.exists(items_csv):
                    zf.write(items_csv, os.path.basename(items_csv))
            out_filename = zip_name
        elif output_format == "excel":
            exporter.to_excel(invoices, out_path)
    except Exception as exc:
        logger.exception("Job %s export failed", job_id)
        _cleanup_dir(upload_dir)
        _cleanup_dir(result_dir)
        return jsonify({"error": f"Export failed: {str(exc)}"}), 500

    # --- Cleanup uploads ---
    _cleanup_dir(upload_dir)

    elapsed = round(time.perf_counter() - start, 2)
    logger.info("Job %s complete in %.2fs", job_id, elapsed)

    # --- Build response ---
    confidence_scores = [
        inv.confidence.get("overall", 0.0) for inv in invoices
    ]
    avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 3)

    return jsonify({
        "success": True,
        "job_id": job_id,
        "download_url": f"/download/{job_id}/{out_filename}",
        "files_processed": len(invoices),
        "files_failed": len(errors),
        "avg_confidence": avg_confidence,
        "elapsed_seconds": elapsed,
        "rejected_files": rejected,
    })


@app.route("/download/<job_id>/<filename>")
def download(job_id: str, filename: str):
    """Serve a result file for download."""
    result_dir = RESULTS_DIR / job_id
    if not result_dir.exists():
        return jsonify({"error": "Result not found or expired."}), 404
    return send_from_directory(
        str(result_dir.resolve()), filename, as_attachment=True
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    UPLOAD_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    print("\n  PDF Invoice Extractor — Web UI")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
