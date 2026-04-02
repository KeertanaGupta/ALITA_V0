# ai_engine/services/document_processor.py

from __future__ import annotations

import concurrent.futures
import hashlib
import io
import logging
import os
import platform
import re
import shutil
from dataclasses import dataclass
from typing import Any, Iterable

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

# Tabula is optional. If Java/tabula is unavailable, we degrade gracefully.
try:
    import tabula  # type: ignore
except Exception:  # pragma: no cover
    tabula = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
OCR_MIN_NATIVE_TEXT_LEN = 80
MIN_ACCEPTABLE_PAGE_TEXT_LEN = 20
MAX_WORKERS = 4
OCR_DPI = 300
OCR_PSM = 6
MAX_TABLE_PAGES = 1  # keep table extraction lightweight and predictable


# ---------------------------------------------------------------------
# Tesseract resolver
# ---------------------------------------------------------------------
def resolve_tesseract_path() -> str:
    """
    Resolve Tesseract automatically across common environments.
    Works on:
    - Linux/macOS via PATH
    - Windows via standard install locations
    """
    if shutil.which("tesseract"):
        return "tesseract"

    if platform.system() == "Windows":
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path

    # Best-effort fallback
    return "tesseract"


pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_path()


# ---------------------------------------------------------------------
# Hashing / text cleaning
# ---------------------------------------------------------------------
def get_file_hash(file_path: str) -> str:
    """
    Stable file fingerprint used for deduplication, reindexing, and deletion.
    """
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def clean_text(text: str) -> str:
    """
    Conservative cleaning:
    - removes control characters
    - normalizes whitespace
    - preserves punctuation and line breaks
    """
    if not text:
        return ""

    text = str(text)
    text = text.replace("\x00", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _dedupe_consecutive_lines(text: str) -> str:
    """
    Removes repeated headers/footers that often appear in PDFs and OCR output.
    Keeps order intact.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    out = []
    seen = set()

    for line in lines:
        if not line:
            out.append("")
            continue

        norm = re.sub(r"\s+", " ", line).strip().lower()
        if not norm:
            continue

        # If the same line repeats in a small window, remove it.
        if norm in seen:
            continue

        seen.add(norm)
        out.append(line)

    return clean_text("\n".join(out))


def _looks_like_table_text(text: str) -> bool:
    """
    Lightweight heuristic to mark extracted content as table-like.
    Useful for debugging and downstream reranking.
    """
    if not text:
        return False

    t = text.strip()
    digit_ratio = sum(ch.isdigit() for ch in t) / max(1, len(t))
    pipe_count = t.count("|")
    tab_count = t.count("\t")

    return pipe_count >= 3 or tab_count >= 3 or digit_ratio > 0.18


# ---------------------------------------------------------------------
# Native PDF text extraction
# ---------------------------------------------------------------------
def _extract_text_from_blocks(page: fitz.Page) -> str:
    """
    Reconstruct text using text blocks sorted in reading order.
    This often works better than plain page.get_text("text") for:
    - multi-column layouts
    - resumes
    - PDFs with irregular spacing
    """
    try:
        blocks = page.get_text("blocks")
        if not blocks:
            return ""

        # block format: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = [b for b in blocks if len(b) >= 5 and str(b[4]).strip()]
        blocks.sort(key=lambda b: (round(float(b[1]), 1), round(float(b[0]), 1)))

        texts = []
        for b in blocks:
            block_text = str(b[4]).strip()
            if block_text:
                texts.append(block_text)

        return clean_text("\n".join(texts))
    except Exception:
        return ""


def _extract_native_text(page: fitz.Page) -> str:
    """
    Try standard extraction first, then block-based reconstruction.
    """
    try:
        text = page.get_text("text") or ""
        text = clean_text(text)

        # If the page is too short or looks broken, reconstruct from blocks.
        if len(text) < OCR_MIN_NATIVE_TEXT_LEN:
            block_text = _extract_text_from_blocks(page)
            if len(block_text) > len(text):
                text = block_text

        return _dedupe_consecutive_lines(text)
    except Exception:
        return ""


# ---------------------------------------------------------------------
# OCR fallback
# ---------------------------------------------------------------------
def _ocr_page(page: fitz.Page, page_number: int) -> str:
    """
    OCR fallback for scanned/image-based pages.
    """
    try:
        pix = page.get_pixmap(dpi=OCR_DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        raw_ocr = pytesseract.image_to_string(img, config=f"--psm {OCR_PSM}")
        cleaned = clean_text(raw_ocr)
        cleaned = _dedupe_consecutive_lines(cleaned)
        if cleaned:
            return f"[OCR Page {page_number}]\n{cleaned}"
    except Exception as e:
        logger.warning(
            "OCR failed on page %s. Ensure Tesseract is installed and working. Error: %s",
            page_number,
            e,
        )
    return ""


# ---------------------------------------------------------------------
# Single-page extraction
# ---------------------------------------------------------------------
def process_single_page(page_num: int, file_path: str, *, file_hash: str = "") -> dict[str, Any] | None:
    """
    Thread-safe page extraction.
    Returns a metadata-rich dict so downstream chunking/retrieval can stay reliable.
    """
    try:
        with fitz.open(file_path) as doc:
            page = doc.load_page(page_num)
            human_page_num = page_num + 1

            native_text = _extract_native_text(page)

            source_type = "native"
            extracted_text = native_text

            # OCR fallback for short or suspicious pages.
            if len(native_text) < OCR_MIN_NATIVE_TEXT_LEN:
                ocr_text = _ocr_page(page, human_page_num)
                if ocr_text:
                    extracted_text = ocr_text
                    source_type = "ocr"

            extracted_text = clean_text(extracted_text)

            if not extracted_text or len(extracted_text) < MIN_ACCEPTABLE_PAGE_TEXT_LEN:
                return None

            return {
                "page_number": human_page_num,
                "text": extracted_text,
                "raw_text": native_text,
                "source_type": source_type,
                "ocr_used": source_type == "ocr",
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "file_hash": file_hash,
                "page_hash": _md5(extracted_text),
                "char_count": len(extracted_text),
                "table_like": _looks_like_table_text(extracted_text),
            }

    except Exception as e:
        logger.error("Error processing page %s of %s: %s", page_num + 1, file_path, e)
        return None


# ---------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------
def _extract_tables_from_pdf(file_path: str, file_hash: str = "") -> list[dict[str, Any]]:
    """
    Gracefully extract tables if tabula + Java are available.
    The output is appended as a separate synthetic page so chunking can index it.
    """
    if tabula is None:
        return []

    try:
        tables = tabula.read_pdf(
            file_path,
            pages="all",
            multiple_tables=True,
            silent=True,
        )
    except Exception as e:
        logger.warning(
            "Table extraction skipped for %s. (Java/tabula may be unavailable). Msg: %s",
            file_path,
            e,
        )
        return []

    if not tables:
        return []

    synthetic_pages: list[dict[str, Any]] = []
    for i, table in enumerate(tables[:MAX_TABLE_PAGES], start=1):
        try:
            if hasattr(table, "to_markdown"):
                table_text = table.to_markdown(index=False)
            else:
                table_text = str(table)

            table_text = clean_text(table_text)
            if not table_text:
                continue

            synthetic_pages.append(
                {
                    "page_number": 10_000 + i,  # keep tables at the end
                    "text": f"[EXTRACTED TABLE {i}]\n{table_text}",
                    "raw_text": table_text,
                    "source_type": "table",
                    "ocr_used": False,
                    "file_path": file_path,
                    "file_name": os.path.basename(file_path),
                    "file_hash": file_hash,
                    "page_hash": _md5(table_text),
                    "char_count": len(table_text),
                    "table_like": True,
                }
            )
        except Exception as e:
            logger.warning("Failed to serialize table %s from %s: %s", i, file_path, e)

    return synthetic_pages


# ---------------------------------------------------------------------
# Public extraction API
# ---------------------------------------------------------------------
def extract_pages_from_pdf(
    file_path: str,
    *,
    document_id: str = "",
    project_id: str = "",
    document_name: str = "",
    owner_name: str = "",
    enable_tables: bool = True,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    """
    Extract PDF text page-by-page with OCR fallback and optional table extraction.

    Returns a list of page dictionaries with rich metadata.
    The extra metadata is intentionally designed to support:
    - better chunking
    - deduplication
    - deletion/reindexing
    - debugging retrieval errors
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")

    file_hash = get_file_hash(file_path)

    try:
        with fitz.open(file_path) as doc:
            total_pages = len(doc)

        if total_pages == 0:
            raise RuntimeError("NO_PAGES_FOUND: PDF appears to be empty.")

        workers = min(MAX_WORKERS, max_workers or os.cpu_count() or 2)
        workers = max(1, workers)

        logger.info(
            "[PDF] Extracting %s pages from %s using %s workers",
            total_pages,
            os.path.basename(file_path),
            workers,
        )

        pages: list[dict[str, Any]] = []

        # Threaded per-page extraction is safe enough here because each task opens
        # its own document handle. This improves throughput for larger PDFs.
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(process_single_page, i, file_path, file_hash=file_hash)
                for i in range(total_pages)
            ]

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    # Attach higher-level document metadata here so downstream code
                    # can keep using the same page dicts for chunking/retrieval.
                    result.update(
                        {
                            "document_id": document_id,
                            "project_id": project_id,
                            "document_name": document_name or os.path.basename(file_path),
                            "owner_name": owner_name,
                        }
                    )
                    pages.append(result)

        # Keep page order stable.
        pages.sort(key=lambda x: x["page_number"])

        # Optional table extraction as a synthetic page at the end.
        if enable_tables:
            pages.extend(_extract_tables_from_pdf(file_path, file_hash=file_hash))

        if not pages:
            raise RuntimeError(
                "NO_READABLE_TEXT_FOUND: Document is empty, image-only, or OCR failed."
            )

        # De-duplicate identical page texts while preserving order.
        seen_page_hashes = set()
        deduped_pages = []
        for p in pages:
            page_hash = p.get("page_hash") or _md5(p.get("text", ""))
            if page_hash in seen_page_hashes:
                continue
            seen_page_hashes.add(page_hash)
            deduped_pages.append(p)

        logger.info(
            "[PDF] Extraction complete for %s | pages=%s | file_hash=%s",
            os.path.basename(file_path),
            len(deduped_pages),
            file_hash,
        )

        return deduped_pages

    except Exception as e:
        raise RuntimeError(f"Failed to process PDF: {str(e)}")


def extract_pages_from_pdfs(
    file_paths: Iterable[str],
    *,
    document_id_prefix: str = "",
    project_id: str = "",
    enable_tables: bool = True,
) -> list[dict[str, Any]]:
    """
    Batch helper for multiple PDFs.
    Returns a flat list of pages with file metadata included.

    Use this when you want to index multiple documents in one pass.
    """
    all_pages: list[dict[str, Any]] = []

    for idx, file_path in enumerate(file_paths, start=1):
        doc_id = f"{document_id_prefix}{idx}" if document_id_prefix else ""
        pages = extract_pages_from_pdf(
            file_path,
            document_id=doc_id,
            project_id=project_id,
            document_name=os.path.basename(file_path),
            owner_name="",
            enable_tables=enable_tables,
        )
        all_pages.extend(pages)

    return all_pages


def extract_text_from_pdf(file_path: str) -> str:
    """
    Legacy compatibility function.
    Joins all extracted page texts into one large string.
    """
    pages = extract_pages_from_pdf(file_path)
    return "\n\n".join([p["text"] for p in pages if p.get("text")])


def preview_extracted_text(file_path: str, chars: int = 2000) -> str:
    """
    Debug helper: quickly inspect the first part of extracted text.
    Useful for diagnosing extraction quality before embedding.
    """
    pages = extract_pages_from_pdf(file_path)
    joined = "\n\n".join([p["text"] for p in pages if p.get("text")])
    return joined[:chars]