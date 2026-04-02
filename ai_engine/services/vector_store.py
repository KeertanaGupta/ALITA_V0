# ai_engine/services/vector_store.py
from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import torch
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from services.entity_service import clean_line, extract_candidate_entities

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[ALITA] Embedding device: {device.upper()}")

FAISS_INDEX_PATH = "faiss_index"
MANIFEST_FILE = os.path.join(FAISS_INDEX_PATH, "manifest.jsonl")

EMBEDDING_MODEL_NAME = os.getenv("ALITA_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
_embed_model = None


# ---------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------
def get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": device},
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": 64 if device == "cuda" else 32,
            },
        )
    return _embed_model


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _ensure_index_dir():
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)


def _is_index_present() -> bool:
    return os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss")) and os.path.exists(
        os.path.join(FAISS_INDEX_PATH, "index.pkl")
    )


def _md5(text: str) -> str:
    import hashlib

    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def _record_id_for_doc(document_id: str, chunk_index: int, chunk_hash: str, page_number: int) -> str:
    base = f"{document_id}:{chunk_index}:{page_number}:{chunk_hash}"
    return _md5(base)


def _serialize_document(doc: Document) -> dict[str, Any]:
    return {
        "record_id": doc.metadata.get("record_id") or _md5(
            f"{doc.metadata.get('document_id','')}:{doc.metadata.get('chunk_index',-1)}:{doc.metadata.get('page_number',-1)}:{_normalize(doc.page_content)}"
        ),
        "page_content": doc.page_content,
        "metadata": doc.metadata,
        "is_active": bool(doc.metadata.get("is_active", True)),
        "created_at": doc.metadata.get("created_at", _now_iso()),
        "updated_at": _now_iso(),
    }


def _deserialize_record(record: dict[str, Any]) -> Document:
    metadata = dict(record.get("metadata") or {})
    metadata.setdefault("record_id", record.get("record_id", ""))
    metadata.setdefault("is_active", record.get("is_active", True))
    metadata.setdefault("created_at", record.get("created_at", _now_iso()))
    metadata.setdefault("updated_at", record.get("updated_at", _now_iso()))
    return Document(page_content=record["page_content"], metadata=metadata)


def _load_manifest_records() -> list[dict[str, Any]]:
    if not os.path.exists(MANIFEST_FILE):
        return []

    records: list[dict[str, Any]] = []
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("is_active", True):
                        records.append(rec)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []

    return records


def _write_manifest_records(records: list[dict[str, Any]]) -> None:
    _ensure_index_dir()
    tmp_path = MANIFEST_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")
    os.replace(tmp_path, MANIFEST_FILE)


def _seed_manifest_from_existing_index() -> list[dict[str, Any]]:
    """
    Backward-compatibility path:
    if the manifest does not exist but FAISS does, recover docs from docstore
    and create the manifest so delete/rebuild starts working.
    """
    if not _is_index_present():
        return []

    try:
        embed_model = get_embed_model()
        vectorstore = FAISS.load_local(
            FAISS_INDEX_PATH,
            embed_model,
            allow_dangerous_deserialization=True,
        )
        docs = list(vectorstore.docstore._dict.values())
        records = [_serialize_document(doc) for doc in docs if getattr(doc, "page_content", None)]
        if records:
            _write_manifest_records(records)
        return records
    except Exception as e:
        print(f"[ALITA] Failed to seed manifest from existing index: {e}")
        return []


def _get_all_records() -> list[dict[str, Any]]:
    records = _load_manifest_records()
    if records:
        return records
    return _seed_manifest_from_existing_index()


def _build_vectorstore_from_records(records: list[dict[str, Any]]) -> Optional[FAISS]:
    if not records:
        return None

    embed_model = get_embed_model()
    docs = [_deserialize_record(r) for r in records if r.get("page_content")]
    if not docs:
        return None

    return FAISS.from_documents(docs, embed_model)


def _rebuild_index_from_records(records: list[dict[str, Any]]) -> bool:
    _ensure_index_dir()

    if not records:
        # Remove FAISS artifacts if the index becomes empty.
        for fname in ("index.faiss", "index.pkl", "manifest.jsonl"):
            path = os.path.join(FAISS_INDEX_PATH, fname)
            if os.path.exists(path):
                os.remove(path)
        return True

    vectorstore = _build_vectorstore_from_records(records)
    if vectorstore is None:
        return False

    vectorstore.save_local(FAISS_INDEX_PATH)
    _write_manifest_records(records)
    return True


# ---------------------------------------------------------------------
# Owner inference
# ---------------------------------------------------------------------
def infer_owner_from_filename(filename: str) -> str:
    """
    Best-effort fallback only.
    Real owner detection is stronger when extracted from the PDF text itself.

    Examples:
      Keertana_Gupta_Resume.pdf    -> Keertana Gupta
      chitreshgurjarResume (4).pdf -> may still be incomplete, so text inference is preferred
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    base = re.sub(r"(?i)(resume|cv|curriculum|vitae|profile|document|doc|file)", " ", base)
    base = re.sub(r"[_\-]+", " ", base)
    base = re.sub(r"\([^)]*\)", " ", base)
    base = re.sub(r"[^A-Za-z\s]", " ", base)
    base = re.sub(r"\s+", " ", base).strip()

    if not base:
        return ""

    words = [w for w in base.split() if len(w) > 1]
    if len(words) >= 2:
        # Title-case likely name words.
        candidate = " ".join(words[:3]).title()
        candidate_words = candidate.split()
        if 2 <= len(candidate_words) <= 4:
            return candidate

    # Handle compact lowercase filenames like "chitreshgurjarResume"
    compact = re.sub(r"(?i)(resume|cv|profile|curriculum|vitae)", "", os.path.basename(filename))
    compact = re.sub(r"[^A-Za-z]", "", compact)
    if len(compact) >= 8:
        # This is only a fallback; it won't always be correct.
        # Keep it conservative rather than inventing a name.
        return ""

    return ""


def infer_owner_from_chunks(chunks: list[dict], document_name: str = "") -> str:
    """
    Stronger owner inference from the first few chunk texts.
    This is the important fix for files whose filenames are messy.
    """
    texts: list[str] = []
    for chunk in chunks[:6]:
        texts.append(clean_line(chunk.get("parent") or chunk.get("child") or chunk.get("text") or ""))

    candidates = extract_candidate_entities(texts)
    if candidates:
        counts = Counter()
        for text in texts:
            low = text.lower()
            for cand in candidates:
                if cand.lower() in low:
                    counts[cand] += 1

        if counts:
            # Prefer the most frequent candidate from top-of-document content.
            best = sorted(counts.items(), key=lambda x: (-x[1], len(x[0])))[0][0]
            return best

        return candidates[0]

    return infer_owner_from_filename(document_name)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def embed_and_store(
    chunks: list[dict],
    document_id: str,
    project_id: str,
    document_name: str = "",
    file_url: str = "",
    owner_name: str = "",
    document_kind: str = "",
    replace_existing: bool = True,
) -> bool:
    """
    Embeds chunks and stores them in FAISS with manifest-backed persistence.

    Why this version is safer:
    - metadata is richer
    - owner is inferred from content first, filename second
    - duplicate document_id uploads can replace old chunks
    - delete operations can rebuild cleanly from the manifest
    """
    if not chunks:
        return False

    _ensure_index_dir()

    # Seed manifest if this is an older installation.
    existing_records = _get_all_records()

    # Prefer explicit owner_name if provided.
    resolved_owner = clean_line(owner_name) if owner_name else ""
    if not resolved_owner:
        resolved_owner = infer_owner_from_chunks(chunks, document_name=document_name)

    # If the document looks personal/resume-like, mark it as such.
    resolved_kind = (document_kind or "").strip().lower()
    if not resolved_kind:
        resolved_kind = "resume" if resolved_owner else "technical"

    print(
        f"[ALITA] Ingesting '{document_name}' | owner_name='{resolved_owner or 'UNKNOWN'}' | kind='{resolved_kind}'"
    )

    new_documents: list[Document] = []
    new_records: list[dict[str, Any]] = []

    for i, chunk in enumerate(chunks):
        child = str(chunk.get("child") or chunk.get("child_chunk") or "").strip()
        parent = str(chunk.get("parent") or chunk.get("parent_chunk") or child).strip()

        if not child:
            continue

        chunk_owner = clean_line(chunk.get("owner_name") or resolved_owner)
        chunk_kind = clean_line(chunk.get("document_kind") or resolved_kind).lower() or "technical"

        chunk_hash = chunk.get("chunk_hash") or _md5(child)
        parent_hash = chunk.get("parent_hash") or _md5(parent)
        page_number = int(chunk.get("page_number", 1) or 1)
        chunk_index = int(chunk.get("chunk_index", i) or i)

        metadata = {
            "record_id": _record_id_for_doc(document_id, chunk_index, chunk_hash, page_number),
            "document_id": document_id,
            "project_id": project_id,
            "chunk_index": chunk_index,
            "parent_index": int(chunk.get("parent_index", 0) or 0),
            "page_number": page_number,
            "parent_chunk": parent,
            "source_text": child[:300],
            "document_name": document_name,
            "file_url": file_url,
            "owner_name": chunk_owner,
            "document_kind": chunk_kind,
            "parent_hash": parent_hash,
            "chunk_hash": chunk_hash,
            "file_hash": chunk.get("file_hash", ""),
            "page_text_hash": chunk.get("page_text_hash", ""),
            "is_active": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

        new_documents.append(Document(page_content=child, metadata=metadata))
        new_records.append(
            {
                "record_id": metadata["record_id"],
                "page_content": child,
                "metadata": metadata,
                "is_active": True,
                "created_at": metadata["created_at"],
                "updated_at": metadata["updated_at"],
            }
        )

    if not new_documents:
        return False

    # If the same document_id already exists, rebuild from manifest for correctness.
    document_id_norm = _normalize(document_id)
    had_existing = any(_normalize(r.get("metadata", {}).get("document_id", "")) == document_id_norm for r in existing_records)

    if replace_existing and had_existing:
        remaining_records = [
            r for r in existing_records
            if _normalize(r.get("metadata", {}).get("document_id", "")) != document_id_norm
        ]
        combined_records = remaining_records + new_records
        ok = _rebuild_index_from_records(combined_records)
        if ok:
            print(
                f"[ALITA] Replaced document_id='{document_id}' | old_records_removed={len(existing_records) - len(remaining_records)} | new_records={len(new_records)}"
            )
        return ok

    # Normal append path
    try:
        if _is_index_present():
            embed_model = get_embed_model()
            vectorstore = FAISS.load_local(
                FAISS_INDEX_PATH,
                embed_model,
                allow_dangerous_deserialization=True,
            )
            vectorstore.add_documents(new_documents)
            vectorstore.save_local(FAISS_INDEX_PATH)
        else:
            vectorstore = FAISS.from_documents(new_documents, get_embed_model())
            vectorstore.save_local(FAISS_INDEX_PATH)

        _write_manifest_records(existing_records + new_records)
        return True
    except Exception as e:
        print(f"[ALITA] embed_and_store failed: {e}")
        return False


def rebuild_index_excluding(
    document_id: Optional[str] = None,
    project_id: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> bool:
    """
    Rebuild index after removing matching records.
    This is the real delete mechanism.
    """
    records = _get_all_records()
    if not records:
        return True

    doc_id_norm = _normalize(document_id)
    project_id_norm = _normalize(project_id)
    file_hash_norm = _normalize(file_hash)

    remaining: list[dict[str, Any]] = []

    for record in records:
        md = record.get("metadata", {}) or {}
        rec_doc = _normalize(md.get("document_id"))
        rec_proj = _normalize(md.get("project_id"))
        rec_hash = _normalize(md.get("file_hash"))

        remove = False
        if doc_id_norm and rec_doc == doc_id_norm:
            remove = True
        if project_id_norm and rec_proj == project_id_norm:
            remove = True
        if file_hash_norm and rec_hash == file_hash_norm:
            remove = True

        if not remove:
            remaining.append(record)

    return _rebuild_index_from_records(remaining)


def delete_document_from_index(document_id: str) -> bool:
    return rebuild_index_excluding(document_id=document_id)


def delete_project_from_index(project_id: str) -> bool:
    return rebuild_index_excluding(project_id=project_id)


def delete_file_from_index(file_hash: str) -> bool:
    return rebuild_index_excluding(file_hash=file_hash)


def get_index_doc_count() -> int:
    records = _get_all_records()
    if records:
        return len(records)

    if not _is_index_present():
        return 0

    try:
        embed_model = get_embed_model()
        vectorstore = FAISS.load_local(
            FAISS_INDEX_PATH,
            embed_model,
            allow_dangerous_deserialization=True,
        )
        return vectorstore.index.ntotal
    except Exception:
        return 0


def list_indexed_documents() -> list[dict[str, Any]]:
    """
    Summarized view of the current manifest for debugging/admin use.
    """
    records = _get_all_records()
    summary: dict[tuple[str, str], dict[str, Any]] = {}

    for record in records:
        md = record.get("metadata", {}) or {}
        key = (str(md.get("document_id", "")), str(md.get("project_id", "")))
        if key not in summary:
            summary[key] = {
                "document_id": md.get("document_id", ""),
                "project_id": md.get("project_id", ""),
                "document_name": md.get("document_name", ""),
                "owner_name": md.get("owner_name", ""),
                "document_kind": md.get("document_kind", ""),
                "chunk_count": 0,
            }
        summary[key]["chunk_count"] += 1

    return list(summary.values())


def get_all_documents() -> list[Document]:
    """
    Returns all active docs from the manifest.
    Useful for rebuilding BM25, debugging, or export tools.
    """
    records = _get_all_records()
    return [_deserialize_record(r) for r in records if r.get("page_content")]


def ensure_index_consistency() -> bool:
    """
    Heuristic safety check:
    - if manifest exists, it is treated as source of truth
    - if index is missing but manifest exists, rebuild it
    """
    records = _get_all_records()
    if records and not _is_index_present():
        return _rebuild_index_from_records(records)
    return True