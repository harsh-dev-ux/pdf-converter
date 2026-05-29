/**
 * PDF Invoice Extractor — Frontend Logic
 *
 * Handles drag-and-drop, file validation, upload via fetch,
 * progress display, and result download.
 */

(function () {
    "use strict";

    // ── Constants ──────────────────────────────────────────────────────
    const MAX_FILES = 100;
    const MAX_FILE_SIZE_MB = 50;

    // ── DOM References ─────────────────────────────────────────────────
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const fileListContainer = document.getElementById("fileListContainer");
    const fileList = document.getElementById("fileList");
    const fileCountEl = document.getElementById("fileCount");
    const clearBtn = document.getElementById("clearBtn");
    const optionsCard = document.getElementById("optionsCard");
    const formatOptions = document.querySelectorAll(".format-option");
    const extractBtn = document.getElementById("extractBtn");
    const progressCard = document.getElementById("progressCard");
    const progressText = document.getElementById("progressText");
    const progressBar = document.getElementById("progressBar");
    const resultCard = document.getElementById("resultCard");
    const resultTitle = document.getElementById("resultTitle");
    const resultMessage = document.getElementById("resultMessage");
    const successIcon = document.getElementById("successIcon");
    const errorIcon = document.getElementById("errorIcon");
    const statsGrid = document.getElementById("statsGrid");
    const statProcessed = document.getElementById("statProcessed");
    const statFailed = document.getElementById("statFailed");
    const statConfidence = document.getElementById("statConfidence");
    const statTime = document.getElementById("statTime");
    const downloadBtn = document.getElementById("downloadBtn");
    const resetBtn = document.getElementById("resetBtn");
    const uploadCard = document.getElementById("uploadCard");

    // ── State ──────────────────────────────────────────────────────────
    let selectedFiles = [];

    // ── Helpers ─────────────────────────────────────────────────────────
    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / 1048576).toFixed(1) + " MB";
    }

    function getSelectedFormat() {
        const radio = document.querySelector('input[name="format"]:checked');
        return radio ? radio.value : "json";
    }

    // ── File Management ────────────────────────────────────────────────
    function addFiles(newFiles) {
        for (const file of newFiles) {
            if (selectedFiles.length >= MAX_FILES) {
                alert(`Maximum ${MAX_FILES} files allowed.`);
                break;
            }
            if (!file.name.toLowerCase().endsWith(".pdf")) {
                continue; // silently skip non-PDFs
            }
            if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
                alert(`"${file.name}" exceeds ${MAX_FILE_SIZE_MB} MB limit.`);
                continue;
            }
            // Prevent duplicates by name
            if (selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
                continue;
            }
            selectedFiles.push(file);
        }
        renderFileList();
    }

    function removeFile(index) {
        selectedFiles.splice(index, 1);
        renderFileList();
    }

    function clearFiles() {
        selectedFiles = [];
        renderFileList();
    }

    function renderFileList() {
        fileList.innerHTML = "";

        if (selectedFiles.length === 0) {
            fileListContainer.style.display = "none";
            optionsCard.style.display = "none";
            return;
        }

        fileListContainer.style.display = "block";
        optionsCard.style.display = "block";
        fileCountEl.textContent = `${selectedFiles.length} file${selectedFiles.length > 1 ? "s" : ""} selected`;

        selectedFiles.forEach((file, idx) => {
            const li = document.createElement("li");
            li.className = "file-item";
            li.style.animationDelay = `${idx * 0.03}s`;
            li.innerHTML = `
                <span class="file-item-name" title="${file.name}">${file.name}</span>
                <span class="file-item-size">${formatBytes(file.size)}</span>
                <button class="file-item-remove" data-index="${idx}" title="Remove">
                    <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14"><path d="M5.28 4.22a.75.75 0 00-1.06 1.06L6.94 8 4.22 10.72a.75.75 0 101.06 1.06L8 9.06l2.72 2.72a.75.75 0 101.06-1.06L9.06 8l2.72-2.72a.75.75 0 00-1.06-1.06L8 6.94 5.28 4.22z"/></svg>
                </button>
            `;
            fileList.appendChild(li);
        });
    }

    // ── Upload & Process ───────────────────────────────────────────────
    async function handleExtract() {
        if (selectedFiles.length === 0) return;

        const format = getSelectedFormat();

        // Show progress
        uploadCard.style.display = "none";
        optionsCard.style.display = "none";
        resultCard.style.display = "none";
        progressCard.style.display = "block";
        progressBar.style.width = "10%";
        progressText.textContent = `Uploading ${selectedFiles.length} file${selectedFiles.length > 1 ? "s" : ""}...`;

        // Build FormData
        const formData = new FormData();
        formData.append("format", format);
        selectedFiles.forEach((file) => formData.append("files", file));

        try {
            progressBar.style.width = "30%";
            progressText.textContent = "Processing invoices...";

            const response = await fetch("/upload", {
                method: "POST",
                body: formData,
            });

            progressBar.style.width = "80%";

            const data = await response.json();

            progressBar.style.width = "100%";

            setTimeout(() => {
                progressCard.style.display = "none";
                showResult(data, response.ok);
            }, 400);
        } catch (err) {
            progressCard.style.display = "none";
            showResult({ error: "Network error. Is the server running?" }, false);
        }
    }

    function showResult(data, ok) {
        resultCard.style.display = "block";
        resultCard.style.animation = "none";
        // Force reflow for re-animation
        void resultCard.offsetWidth;
        resultCard.style.animation = "fadeSlideUp 0.5s ease-out both";

        if (ok && data.success) {
            successIcon.style.display = "block";
            errorIcon.style.display = "none";
            resultTitle.textContent = "Extraction Complete!";
            resultMessage.textContent = `${data.files_processed} invoice(s) processed successfully.`;

            // Stats
            statsGrid.style.display = "grid";
            statProcessed.textContent = data.files_processed;
            statFailed.textContent = data.files_failed;
            statConfidence.textContent = Math.round(data.avg_confidence * 100) + "%";
            statTime.textContent = data.elapsed_seconds + "s";

            // Download
            downloadBtn.style.display = "flex";
            downloadBtn.href = data.download_url;
        } else {
            successIcon.style.display = "none";
            errorIcon.style.display = "block";
            resultTitle.textContent = "Something Went Wrong";
            resultMessage.textContent = data.error || "Unknown error occurred.";
            statsGrid.style.display = "none";
            downloadBtn.style.display = "none";
        }
    }

    function handleReset() {
        selectedFiles = [];
        fileList.innerHTML = "";
        fileListContainer.style.display = "none";
        optionsCard.style.display = "none";
        progressCard.style.display = "none";
        resultCard.style.display = "none";
        uploadCard.style.display = "block";
        uploadCard.style.animation = "none";
        void uploadCard.offsetWidth;
        uploadCard.style.animation = "fadeSlideUp 0.5s ease-out both";
    }

    // ── Event Listeners ────────────────────────────────────────────────

    // Drag and drop
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length) {
            addFiles(e.dataTransfer.files);
        }
    });

    // Click to browse
    dropZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) {
            addFiles(fileInput.files);
            fileInput.value = ""; // allow re-selecting same file
        }
    });

    // Clear
    clearBtn.addEventListener("click", clearFiles);

    // Remove individual file
    fileList.addEventListener("click", (e) => {
        const btn = e.target.closest(".file-item-remove");
        if (btn) {
            removeFile(parseInt(btn.dataset.index, 10));
        }
    });

    // Format selection
    formatOptions.forEach((opt) => {
        opt.addEventListener("click", () => {
            formatOptions.forEach((o) => o.classList.remove("selected"));
            opt.classList.add("selected");
            opt.querySelector("input").checked = true;
        });
    });

    // Extract
    extractBtn.addEventListener("click", handleExtract);

    // Reset
    resetBtn.addEventListener("click", handleReset);
})();
