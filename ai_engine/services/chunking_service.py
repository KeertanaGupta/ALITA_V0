# ai_engine/services/chunking_service.py

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter
import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Chunking defaults tuned for offline RAG on PDFs/resumes/technical docs.
# These are character-based, not token-based.
PARENT_CHUNK_SIZE = 2200
PARENT_CHUNK_OVERLAP = 300

CHILD_CHUNK_SIZE = 850
CHILD_CHUNK_OVERLAP = 150

MIN_CHUNK_LEN = 40
MIN_PAGE_TEXT_LEN = 20
MAX_STITCH_TAIL = 180

_PARENT_SEPARATORS = [
    "\n\n",
    "\n",
    "•",
    "- ",
    ". ",
    "? ",
    "! ",
    "; ",
    ": ",
    " ",
]

_CHILD_SEPARATORS = [
    "\n\n",
    "\n",
    "•",
    "- ",
    ". ",
    "? ",
    "! ",
    "; ",
    ": ",
    " ",
]


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_page_text(text: str) -> str:
    """
    Conservative cleaning:
    - normalize whitespace
    - remove null/control chars
    - keep bullets, punctuation, and line breaks
    """
    text = _normalize_text(text)

    # Remove weird isolated control chars but preserve readable content.
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)

    return text.strip()


def _looks_like_continuation(prev_text: str, current_text: str) -> bool:
    """
    Heuristic for page stitching:
    stitch if the previous page likely ends mid-thought and the new page
    starts like a continuation.
    """
    prev_text = (prev_text or "").strip()
    current_text = (current_text or "").lstrip()

    if not prev_text or not current_text:
        return False

    prev_tail = prev_text[-MAX_STITCH_TAIL:]
    prev_tail = prev_tail.strip()

    if not prev_tail:
        return False

    # Strong terminal punctuation usually means the thought is complete.
    ends_cleanly = bool(re.search(r"[.!?】【：:]$", prev_tail))

    # If the next page starts with a lowercase word, bullet, or dash,
    # it's more likely a continuation.
    starts_like_continuation = bool(
        re.match(r"^([a-z]|[-•*]|\d+[.)])", current_text)
    )

    # Hyphenated wraps across pages should be stitched.
    ends_hyphenated = prev_tail.endswith("-")

    # Resume/page layouts often split bullets or sentences across pages.
    return ends_hyphenated or (not ends_cleanly and starts_like_continuation)


def _stitch_pages(prev_text: str, current_text: str) -> str:
    """
    Add only a small tail from previous page when the page break looks
    like a true continuation.
    """
    prev_text = (prev_text or "").strip()
    current_text = (current_text or "").strip()

    if not prev_text:
        return current_text

    tail = prev_text[-MAX_STITCH_TAIL:].strip()
    if not tail:
        return current_text

    return f"{tail} {current_text}".strip()


def _is_boilerplate_line(line: str) -> bool:
    """
    Light boilerplate filter.
    Avoid aggressive removal because resumes often contain short meaningful lines.
    """
    low = line.lower().strip()

    if not low:
        return True

    # Pure page numbers / separators
    if re.fullmatch(r"[\-|_|= ]+", low):
        return True
    if re.fullmatch(r"(page\s*)?\d+(\s*/\s*\d+)?", low):
        return True

    # Common noisy artifacts from OCR / PDFs
    if low in {"confidential", "resume", "curriculum vitae"}:
        return False  # may be meaningful as a section heading

    return False


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen = set()
    out = []
    for line in lines:
        key = re.sub(r"\s+", " ", line).strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _prepare_page_text(page_text: str) -> str:
    page_text = _clean_page_text(page_text)
    if not page_text:
        return ""

    lines = [ln.strip() for ln in page_text.splitlines()]
    lines = [ln for ln in lines if ln and not _is_boilerplate_line(ln)]

    # Preserve ordering, but avoid repeated headers/footers from OCR/PDF rendering.
    lines = _dedupe_lines(lines)

    return "\n".join(lines).strip()


def _make_splitters():
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=_PARENT_SEPARATORS,
        keep_separator=True,
    )

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=_CHILD_SEPARATORS,
        keep_separator=True,
    )

    return parent_splitter, child_splitter


def chunk_document_text(raw_text: str) -> list[dict]:
    """
    Legacy fallback for raw text files (.txt).
    Wraps raw text as a single page and sends it through the same pipeline.
    """
    raw_text = _clean_page_text(raw_text)
    if not raw_text:
        logger.warning("Empty raw text provided to chunker.")
        return []

    return chunk_pages([{"page_number": 1, "text": raw_text}])


def chunk_pages(
    pages: list[dict],
    document_id: str = "",
    project_id: str = "",
    document_name: str = "",
    owner_name: str = "",
    file_path: str = "",
) -> list[dict]:
    """
    Production-grade chunking for offline RAG.

    Input:
        [
            {"page_number": 1, "text": "..."},
            {"page_number": 2, "text": "..."},
        ]

    Output:
        [
            {
                "child": str,
                "parent": str,
                "parent_index": int,
                "page_number": int,
                "document_id": str,
                "project_id": str,
                "document_name": str,
                "owner_name": str,
                "file_path": str,
                "parent_hash": str,
                "chunk_hash": str,
                "page_text_hash": str,
                "chunk_index": int,
                "parent_chunk": str,   # alias for compatibility
                "child_chunk": str,    # alias for compatibility
            },
            ...
        ]

    Design goals:
    - preserve meaning across page boundaries
    - keep chunks large enough for semantic answerability
    - avoid duplicated headers/footers
    - attach stable hashes for deletion/rebuild/debugging
    - remain backward-compatible with existing code
    """
    if not pages:
        return []

    parent_splitter, child_splitter = _make_splitters()

    # Keep page order stable even if the input arrives scrambled.
    normalized_pages = []
    for page in pages:
        try:
            page_number = int(page.get("page_number", 1))
        except Exception:
            page_number = 1
        text = _prepare_page_text(page.get("text", ""))
        if len(text) >= MIN_PAGE_TEXT_LEN:
            normalized_pages.append({"page_number": page_number, "text": text})

    normalized_pages.sort(key=lambda x: x["page_number"])

    if not normalized_pages:
        logger.warning("No usable page text found during chunking.")
        return []

    result: list[dict] = []
    parent_index = 0
    chunk_index = 0
    previous_page_text = ""

    for page in normalized_pages:
        page_number = page["page_number"]
        page_text = page["text"]

        # Controlled page stitching only when it looks like a continuation.
        stitched_text = page_text
        if previous_page_text and _looks_like_continuation(previous_page_text, page_text):
            stitched_text = _stitch_pages(previous_page_text, page_text)

        previous_page_text = page_text

        parent_chunks = parent_splitter.split_text(stitched_text)
        if not parent_chunks:
            continue

        for parent_text in parent_chunks:
            parent_text = _normalize_text(parent_text)
            if len(parent_text) < MIN_CHUNK_LEN:
                continue

            parent_hash = _md5(parent_text)
            child_chunks = child_splitter.split_text(parent_text)

            # Fallback: if the child splitter collapses too much, keep the parent.
            if not child_chunks:
                child_chunks = [parent_text]

            for child_text in child_chunks:
                child_text = _normalize_text(child_text)
                if len(child_text) < MIN_CHUNK_LEN:
                    continue

                chunk_hash = _md5(child_text)

                result.append(
                    {
                        # Backward-compatible keys
                        "child": child_text,
                        "parent": parent_text,
                        "parent_index": parent_index,
                        "page_number": page_number,

                        # Strong retrieval metadata
                        "document_id": document_id,
                        "project_id": project_id,
                        "document_name": document_name,
                        "owner_name": owner_name,
                        "file_path": file_path,

                        # Traceability / deletion / dedup
                        "parent_hash": parent_hash,
                        "chunk_hash": chunk_hash,
                        "page_text_hash": _md5(page_text),
                        "chunk_index": chunk_index,

                        # Compatibility aliases for downstream code
                        "parent_chunk": parent_text,
                        "child_chunk": child_text,
                    }
                )
                chunk_index += 1

            parent_index += 1

    # Final dedupe across identical child chunks while preserving order.
    seen_hashes = set()
    deduped: list[dict] = []
    for item in result:
        key = item["chunk_hash"]
        if key in seen_hashes:
            continue
        seen_hashes.add(key)
        deduped.append(item)

    logger.info(
        "Chunking complete. pages=%s parents=%s children=%s",
        len(normalized_pages),
        parent_index,
        len(deduped),
    )
    return deduped