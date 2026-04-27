from __future__ import annotations

import hashlib
import json
import os
import re
import time
import traceback
from collections import defaultdict
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel
from sentence_transformers import CrossEncoder

from schemas import DocumentProcessRequest, DocumentProcessResponse, ChatRequest, ChatResponse
from services.document_processor import extract_pages_from_pdf
from services.chunking_service import chunk_pages
from services import vector_store as vs
from services.llm_service import (
    generate_answer,
    set_active_model,
    get_active_model_name,
    is_explanatory,
    detect_question_type,
)
from services.entity_service import extract_candidate_entities

try:
    from langchain_community.retrievers import BM25Retriever  # type: ignore
except Exception:  # pragma: no cover
    BM25Retriever = None


APP_VERSION = "4.1.0"
EMBED_MODEL_NAME = "bge-small-en-v1.5"
RERANKER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
HYDE_MODEL = os.getenv("ALITA_HYDE_MODEL", "mistral")

MIN_CONTEXT_DOCS = 2
MAX_SOURCE_COUNT = 3
MAX_CANDIDATES = 40
MAX_BM25_CANDIDATES = 25
MAX_EXPANDED_QUERIES = 6
MAX_CONTEXT_CHUNKS = 8
LOW_CONFIDENCE_THRESHOLD = 0.38
VERY_LOW_CONFIDENCE_THRESHOLD = 0.22

_VECTORSTORE_CACHE: dict[str, Any] = {"signature": None, "value": None}
_BM25_CACHE: dict[str, Any] = {"signature": None, "value": None}
_RETRIEVAL_CACHE: dict[tuple, Any] = {}
_RETRIEVAL_CACHE_TTL_SECONDS = 120

app = FastAPI(
    title="ALITA AI Engine",
    description="Offline RAG and AI Microservices API",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import torch

def _get_torch_device():
    device = "cpu"
    if torch.cuda.is_available():
        try:
            _ = torch.zeros(1).cuda()
            device = "cuda"
        except Exception:
            pass
    return os.getenv("ALITA_DEVICE", device)

_main_device = _get_torch_device()
print(f"[ALITA] Main Embedding device: {_main_device.upper()}")

print("[ALITA] Loading cross-encoder reranker...")
reranker = CrossEncoder(RERANKER_NAME, device=_main_device)
print("[ALITA] Reranker ready.")


class ModelSwitchRequest(BaseModel):
    model_name: str


STOP_WORDS = {
    "what", "when", "where", "which", "define", "explain", "about", "does",
    "have", "with", "this", "that", "from", "give", "write", "short", "note",
    "state", "describe", "degree", "units", "value", "show", "find", "each",
    "type", "form", "water", "the", "and", "for", "are", "how", "why", "can",
    "its", "their", "your", "tell", "something", "who", "brief", "detail",
    "complete", "full", "long", "please", "compare", "difference", "differences",
    "between", "of", "in", "on", "to", "is", "was", "were", "be", "being",
    "has", "had", "do", "does", "did", "me", "us", "it", "they", "them",
}


# -----------------------------
# Helpers
# -----------------------------

def log_event(event: str, **payload):
    record = {"event": event, "ts": round(time.time(), 3), **payload}
    try:
        print(json.dumps(record, ensure_ascii=False, default=str))
    except Exception:
        print(f"[LOG] {event} | {payload}")


def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = text.replace("+", " plus ").replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_entity_from_question(question: str) -> str | None:
    q = normalize_text(question)
    if not q:
        return None

    # Direct person lookup
    m = re.search(r"\bwho\s+is\s+([a-z][a-z\s]{1,60})$", q)
    if not m:
        m = re.search(r"\btell\s+me\s+about\s+([a-z][a-z\s]{1,60})$", q)
    if m:
        candidate = m.group(1).strip()
        candidate = re.sub(r"\b(?:and|or|please)\b.*$", "", candidate).strip()
        parts = [p for p in candidate.split() if p not in STOP_WORDS and len(p) > 1]
        if parts:
            return " ".join(parts[:4]).title()

    # Compare X and Y
    m = re.search(r"\bcompare\s+(.+?)\s+and\s+(.+)$", q)
    if m:
        left = " ".join([w for w in m.group(1).split() if w not in STOP_WORDS and len(w) > 1]).strip()
        right = " ".join([w for w in m.group(2).split() if w not in STOP_WORDS and len(w) > 1]).strip()
        if left:
            return left.title()
        if right:
            return right.title()

    return None


def _request_project_filter(project_id: str | None) -> str | None:
    if not project_id or project_id == "all":
        return None
    return str(project_id).strip().lower()


def _doc_project_match(doc, project_id: str | None, document_ids: list[str] | None = None) -> bool:
    if document_ids is not None:
        doc_id = str(doc.metadata.get("document_id", "")).strip()
        if doc_id not in document_ids:
            return False

    target = _request_project_filter(project_id)
    if target is None:
        return True
    doc_project = str(doc.metadata.get("project_id", "")).strip().lower()
    return doc_project == target


def _doc_key(doc) -> tuple:
    return (str(doc.metadata.get("document_id", "")), int(doc.metadata.get("chunk_index", -1)))


def _source_key(src: dict) -> str:
    return f"{src.get('document_id', '')}_{src.get('page_number', '')}_{src.get('chunk_index', '')}"


def is_resume_doc(doc) -> bool:
    name = (doc.metadata.get("document_name", "") or "").lower()
    kind = (doc.metadata.get("document_kind", "") or "").lower()
    owner = (doc.metadata.get("owner_name", "") or "").lower()
    blob = f"{name} {kind} {owner}"
    return any(x in blob for x in ["resume", "cv", "curriculum vitae", "profile"])


def is_technical_doc(doc) -> bool:
    return not is_resume_doc(doc)


def owner_matches_entity(owner: str, entity: str) -> bool:
    owner_norm = normalize_text(owner)
    entity_norm = normalize_text(entity)
    if not owner_norm or not entity_norm:
        return False
    if entity_norm in owner_norm:
        return True
    entity_first = entity_norm.split()[0] if entity_norm.split() else ""
    return bool(entity_first and entity_first in owner_norm)


def _get_embed_model():
    getter = getattr(vs, "get_embed_model", None)
    if callable(getter):
        return getter()
    embed_model = getattr(vs, "embed_model", None)
    if embed_model is None:
        raise RuntimeError(
            "No embedding model found in services.vector_store. Define either get_embed_model() or embed_model."
        )
    return embed_model


def _vectorstore_signature() -> str:
    path = getattr(vs, "FAISS_INDEX_PATH", "")
    if not path or not os.path.exists(path):
        return "missing"

    total = 0
    latest_mtime = 0.0
    for root, _, files in os.walk(path):
        for file in files:
            fp = os.path.join(root, file)
            try:
                st = os.stat(fp)
            except FileNotFoundError:
                continue
            total += st.st_size
            latest_mtime = max(latest_mtime, st.st_mtime)
    return f"{path}:{total}:{round(latest_mtime, 3)}"


@lru_cache(maxsize=1)
def _load_vectorstore_cached(signature: str):
    embed_model = _get_embed_model()
    return FAISS.load_local(vs.FAISS_INDEX_PATH, embed_model, allow_dangerous_deserialization=True)


def _get_vectorstore():
    sig = _vectorstore_signature()
    if _VECTORSTORE_CACHE["signature"] != sig or _VECTORSTORE_CACHE["value"] is None:
        _VECTORSTORE_CACHE["signature"] = sig
        _VECTORSTORE_CACHE["value"] = _load_vectorstore_cached(sig)
    return _VECTORSTORE_CACHE["value"]


def _all_docs_from_vectorstore(vectorstore) -> list:
    try:
        if hasattr(vectorstore, "docstore") and hasattr(vectorstore.docstore, "_dict"):
            docs = list(vectorstore.docstore._dict.values())
            return [d for d in docs if getattr(d, "page_content", None)]
    except Exception:
        pass
    return []


def _get_global_docs(project_id: str | None = None, document_ids: list[str] | None = None) -> list:
    vectorstore = _get_vectorstore()
    docs = _all_docs_from_vectorstore(vectorstore)
    if project_id or document_ids:
        docs = [d for d in docs if _doc_project_match(d, project_id, document_ids)]
    return docs


def _docs_matching_entity(docs: list, entity: str) -> list:
    if not entity:
        return []

    entity_norm = normalize_text(entity)
    entity_first = entity_norm.split()[0] if entity_norm.split() else ""
    matched = []

    for doc in docs:
        owner = doc.metadata.get("owner_name", "") or ""
        doc_name = doc.metadata.get("document_name", "") or ""
        source_text = doc.metadata.get("source_text", "") or ""
        page_content = getattr(doc, "page_content", "") or ""
        blob = normalize_text(f"{owner} {doc_name} {source_text[:400]} {page_content[:400]}")

        if (
            owner_matches_entity(owner, entity)
            or owner_matches_entity(doc_name, entity)
            or entity_norm in blob
            or (entity_first and entity_first in blob)
        ):
            matched.append(doc)

    return matched


def _bm25_signature(docs: list) -> str:
    if not docs:
        return "empty"
    parts = [str(len(docs))]
    sample = docs[:10]
    for doc in sample:
        parts.append(str(len(doc.page_content)))
        parts.append(str(doc.metadata.get("document_id", "")))
    return "|".join(parts)


def _build_bm25_retriever(docs: list):
    if BM25Retriever is None or not docs:
        return None
    try:
        retriever = BM25Retriever.from_documents(docs)
        retriever.k = min(MAX_BM25_CANDIDATES, len(docs))
        return retriever
    except Exception as e:
        log_event("bm25_build_failed", error=str(e))
        return None


def _get_bm25_retriever(vectorstore) -> Any:
    docs = _all_docs_from_vectorstore(vectorstore)
    sig = _bm25_signature(docs)
    if _BM25_CACHE["signature"] != sig or _BM25_CACHE["value"] is None:
        _BM25_CACHE["signature"] = sig
        _BM25_CACHE["value"] = _build_bm25_retriever(docs)
    return _BM25_CACHE["value"]


def extract_key_terms(question: str) -> list[str]:
    words = question.lower().replace("?", "").replace(",", "").replace(".", "").split()
    return [w for w in words if len(w) >= 3 and w not in STOP_WORDS]


def detect_domain_signals(question: str) -> dict[str, float]:
    q = normalize_text(question)
    resume_keywords = {
        "resume", "cv", "profile", "projects", "skills", "internship", "certifications",
        "experience", "education", "who is", "who cleared", "who got", "who has", "who have",
        "codevita", "nptel", "linkedin", "github",
    }
    tech_keywords = {
        "explain", "working of", "working principle", "define", "what is", "why", "how",
        "dc generator", "degree clarke", "water hardness", "machine", "electrical", "physics",
        "chemistry", "algorithm", "database", "python", "java", "c++", "cloud",
    }
    return {
        "resume": float(sum(1 for k in resume_keywords if k in q)),
        "technical": float(sum(1 for k in tech_keywords if k in q)),
    }


def expand_query(question: str, q_type: str) -> list[str]:
    stripped = question.strip().rstrip("?")
    prefix = "Represent this sentence for searching relevant passages: "
    signals = detect_domain_signals(question)
    expanded = [f"{prefix}{question}", f"{prefix}what is {stripped}", f"{prefix}define {stripped}"]

    if q_type == "comparison":
        expanded = [f"{prefix}{question}", f"{prefix}{stripped}", f"{prefix}{stripped} resume"]
        if signals["resume"] > 0:
            expanded.extend([f"{prefix}{stripped} codevita", f"{prefix}{stripped} nptel"])
    else:
        if signals["resume"] > 0:
            expanded.append(f"{prefix}{stripped} resume")
            if any(k in normalize_text(question) for k in ["codevita", "nptel"]):
                expanded.append(f"{prefix}{stripped} codevita nptel")

    uniq = []
    seen = set()
    for q in expanded:
        if q not in seen:
            seen.add(q)
            uniq.append(q)
    return uniq[:MAX_EXPANDED_QUERIES]


def prefer_domain_docs(question: str, q_type: str, docs: list):
    if not docs:
        return docs

    q = normalize_text(question)
    signals = detect_domain_signals(question)
    resume_docs = [d for d in docs if is_resume_doc(d)]
    tech_docs = [d for d in docs if is_technical_doc(d)]

    def score_doc(doc) -> float:
        score = 0.0
        score += 1.0 if is_resume_doc(doc) else 0.6
        owner = normalize_text(doc.metadata.get("owner_name", ""))
        doc_name = normalize_text(doc.metadata.get("document_name", ""))
        source_blob = normalize_text(f"{owner} {doc_name} {doc.page_content[:200]}")

        for token in q.split():
            if len(token) >= 3 and token in source_blob:
                score += 0.03

        if q_type in {"comparison", "conversational", "extraction"} and is_resume_doc(doc):
            score += 1.5
        if q_type in {"explanatory", "factual"} and is_technical_doc(doc):
            score += 1.2
        if signals["resume"] > signals["technical"] and is_resume_doc(doc):
            score += 0.7
        if signals["technical"] > signals["resume"] and is_technical_doc(doc):
            score += 0.7
        return score

    if q_type == "comparison" and resume_docs:
        return sorted(docs, key=score_doc, reverse=True)
    if q_type in {"conversational", "extraction"} and resume_docs:
        return sorted(docs, key=score_doc, reverse=True)
    if q_type in {"explanatory", "factual"} and tech_docs:
        return sorted(docs, key=score_doc, reverse=True)
    return sorted(docs, key=score_doc, reverse=True)


def clean_entities(entities):
    cleaned = []
    seen = set()
    for e in entities:
        e = re.sub(r"\s+", " ", str(e).replace("_", " ")).strip()
        if not e:
            continue
        low = e.lower()
        if any(
            x in low
            for x in [
                "github", "linkedin", "email", "www", "http", "resume", "cv",
                "codevita", "season", "nptel", "data analysis", "job simulation",
            ]
        ):
            continue
        if len(e.split()) < 2 or len(e.split()) > 4:
            continue
        if low not in seen:
            seen.add(low)
            cleaned.append(e)
    return cleaned


def extract_entities_from_results(results: list, context_texts: list) -> list:
    candidates = []
    seen_owners = set()
    for doc in results:
        owner = (doc.metadata.get("owner_name") or "").strip()
        if owner and owner.lower() not in seen_owners:
            seen_owners.add(owner.lower())
            candidates.append(owner)
    if not candidates:
        candidates.extend(extract_candidate_entities(context_texts))
    return clean_entities(candidates)


def select_target_entity(question: str, entities: list[str]) -> str | None:
    if not entities:
        return None
    q = normalize_text(question)
    scored = []
    for entity in entities:
        en = normalize_text(entity)
        score = 0
        if en in q:
            score += 4
        parts = en.split()
        if parts:
            if parts[0] in q:
                score += 2
            if len(parts) > 1 and parts[-1] in q:
                score += 1
        if score > 0:
            scored.append((score, entity))
    if scored:
        scored.sort(key=lambda x: (-x[0], len(x[1])))
        return scored[0][1]
    return None if len(entities) > 1 else entities[0]


def extract_names_from_answer(answer: str, candidate_entities: list[str]) -> list[str]:
    if not answer or not candidate_entities:
        return []
    answer_norm = normalize_text(answer)
    matched = []
    for entity in candidate_entities:
        entity_norm = normalize_text(entity)
        entity_first = entity_norm.split()[0] if entity_norm.split() else ""
        if entity_norm in answer_norm or (entity_first and entity_first in answer_norm):
            matched.append(entity)
    return matched


def _build_source(doc) -> dict:
    m = doc.metadata
    return {
        "document_id": m.get("document_id", ""),
        "document_name": m.get("document_name", "Unknown Document"),
        "page_number": m.get("page_number", 1),
        "source_text": m.get("source_text", doc.page_content[:300]),
        "file_url": m.get("file_url", ""),
        "chunk_index": m.get("chunk_index", 0),
        "owner_name": m.get("owner_name", m.get("document_name", "Unknown")),
        "document_kind": m.get("document_kind", ""),
    }


def build_context(results: list) -> tuple[list, list]:
    seen = set()
    context_texts = []
    sources = []
    for doc in results:
        key = f"{doc.metadata.get('document_id')}_{doc.metadata.get('parent_index')}"
        if key in seen:
            continue
        seen.add(key)
        context_texts.append(doc.metadata.get("parent_chunk", doc.page_content))
        sources.append(_build_source(doc))
    return context_texts, sources


def build_owner_context(results: list) -> tuple[list, list]:
    owner_map: dict[str, list] = {}
    sources = []
    seen_sources = set()
    seen_chunks: dict[str, set] = {}

    for doc in results:
        owner = (doc.metadata.get("owner_name") or doc.metadata.get("document_name") or "Unknown").strip() or "Unknown"
        chunk_key = f"{doc.metadata.get('document_id')}_{doc.metadata.get('parent_index')}"

        if owner not in owner_map:
            owner_map[owner] = []
            seen_chunks[owner] = set()
        if chunk_key not in seen_chunks[owner]:
            seen_chunks[owner].add(chunk_key)
            owner_map[owner].append(doc.metadata.get("parent_chunk", doc.page_content))

        src = _build_source(doc)
        src_key = _source_key(src)
        if src_key not in seen_sources:
            seen_sources.add(src_key)
            sources.append(src)

    context_texts = []
    for owner, chunks in owner_map.items():
        block = "\n---\n".join(chunks[:4])
        context_texts.append(f"=== {owner} ===\n{block}")
    return context_texts, sources


def filter_docs_by_entity(docs: list, entity: str) -> list:
    if not entity or not docs:
        return docs
    entity_norm = normalize_text(entity)
    entity_first = entity_norm.split()[0] if entity_norm.split() else ""
    matched = []
    for doc in docs:
        owner = normalize_text(doc.metadata.get("owner_name", ""))
        doc_name = normalize_text(doc.metadata.get("document_name", ""))
        if entity_norm in owner or entity_norm in doc_name or (entity_first and (entity_first in owner or entity_first in doc_name)):
            matched.append(doc)
    return matched if matched else docs


def build_entity_filtered_context(results: list, entity: str) -> tuple[list, list]:
    filtered = filter_docs_by_entity(results, entity)
    log_event("entity_filter", entity=entity, before=len(results), after=len(filtered))
    return build_context(filtered)


def filter_sources_strict(sources: list, entity: str) -> list:
    if not entity:
        return sources[:MAX_SOURCE_COUNT]
    entity_norm = normalize_text(entity)
    entity_first = entity_norm.split()[0] if entity_norm.split() else ""
    matched = []
    for s in sources:
        owner = normalize_text(s.get("owner_name", ""))
        doc_name = normalize_text(s.get("document_name", ""))
        if entity_norm in owner or entity_norm in doc_name or (entity_first and (entity_first in owner or entity_first in doc_name)):
            matched.append(s)
    return matched if matched else sources[:2]


def filter_sources_for_comparison(sources: list, matched_entities: list) -> list:
    if not matched_entities:
        return sources[:MAX_SOURCE_COUNT]
    result = []
    for s in sources:
        owner = normalize_text(s.get("owner_name", ""))
        doc_name = normalize_text(s.get("document_name", ""))
        for entity in matched_entities:
            entity_norm = normalize_text(entity)
            entity_first = entity_norm.split()[0] if entity_norm.split() else ""
            if entity_norm in owner or entity_norm in doc_name or (entity_first and (entity_first in owner or entity_first in doc_name)):
                result.append(s)
                break
    return result if result else sources[:MAX_SOURCE_COUNT]


def filter_sources_by_answer_and_domain(answer: str, sources: list, q_type: str):
    if not sources:
        return sources

    if q_type == "comparison":
        domain_sources = [
            s for s in sources
            if "resume" in (s.get("document_kind", "") or "").lower()
            or "resume" in (s.get("document_name", "") or "").lower()
            or "cv" in (s.get("document_name", "") or "").lower()
        ]
        if domain_sources:
            sources = domain_sources
    else:
        if q_type in ("explanatory", "factual", "extraction"):
            domain_sources = [s for s in sources if "resume" not in (s.get("document_kind", "") or "").lower()]
            if domain_sources:
                sources = domain_sources

    if not answer:
        return sources[:MAX_SOURCE_COUNT]

    ans_norm = normalize_text(answer)
    tokens = [t for t in ans_norm.split() if len(t) >= 4]
    if not tokens:
        return sources[:MAX_SOURCE_COUNT]

    scored = []
    for s in sources:
        blob = normalize_text(f"{s.get('document_name', '')} {s.get('source_text', '')} {s.get('owner_name', '')}")
        score = sum(1 for t in tokens if t in blob)
        if score > 0:
            scored.append((s, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    filtered = [s for s, _ in scored]
    return filtered if filtered else sources[:MAX_SOURCE_COUNT]


def _candidate_priority_boost(doc, q_type: str, question: str) -> float:
    boost = 0.0
    q_norm = normalize_text(question)
    owner = normalize_text(doc.metadata.get("owner_name", ""))
    doc_name = normalize_text(doc.metadata.get("document_name", ""))
    blob = f"{owner} {doc_name} {normalize_text(doc.page_content[:300])}"

    if is_resume_doc(doc):
        if q_type in {"comparison", "conversational", "extraction"}:
            boost += 0.35
        elif q_type in {"explanatory", "factual"}:
            boost -= 0.12
    else:
        if q_type in {"explanatory", "factual"}:
            boost += 0.35
        elif q_type in {"comparison", "conversational", "extraction"}:
            boost += 0.05

    if owner and owner_matches_entity(owner, q_norm):
        boost += 0.5
    if doc_name and owner_matches_entity(doc_name, q_norm):
        boost += 0.3

    terms = extract_key_terms(question)
    overlap = sum(1 for t in terms if t in blob)
    boost += min(0.35, overlap * 0.04)
    return boost


def _rank_candidates(question: str, q_type: str, candidates: list) -> list:
    if not candidates:
        return []
    pairs = [(question, doc.metadata.get("parent_chunk", doc.page_content)) for doc in candidates]
    try:
        ce_scores = list(reranker.predict(pairs))
    except Exception as e:
        log_event("reranker_failed", error=str(e))
        ce_scores = [0.0] * len(candidates)

    min_s = min(ce_scores) if ce_scores else 0.0
    max_s = max(ce_scores) if ce_scores else 1.0
    denom = (max_s - min_s) if (max_s - min_s) != 0 else 1.0

    ranked = []
    for doc, ce in zip(candidates, ce_scores):
        ce_norm = (ce - min_s) / denom
        meta_boost = _candidate_priority_boost(doc, q_type, question)
        final = (0.70 * ce_norm) + (0.30 * meta_boost)
        ranked.append((doc, final, ce))

    ranked.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [doc for doc, _, _ in ranked]


def _dense_and_sparse_retrieval(vectorstore, bm25, question: str, q_type: str, project_id: str | None, document_ids: list[str] | None = None):
    dynamic_k = 30 if q_type == "comparison" else 20 if is_explanatory(question) else 10
    dense_k = dynamic_k * 3
    sparse_k = min(MAX_BM25_CANDIDATES, max(10, dynamic_k * 2))

    expanded_queries = expand_query(question, q_type)
    key_terms = extract_key_terms(question)

    docs_by_key = {}
    score_buckets = defaultdict(lambda: {"dense": 0.0, "bm25": 0.0, "kw": 0.0, "hits": 0})

    for q in expanded_queries:
        try:
            dense_hits = vectorstore.max_marginal_relevance_search(q, k=dense_k)
        except Exception:
            dense_hits = vectorstore.similarity_search(q, k=dense_k)

        for rank, doc in enumerate(dense_hits):
            if not _doc_project_match(doc, project_id, document_ids):
                continue
            key = _doc_key(doc)
            docs_by_key[key] = doc
            score_buckets[key]["dense"] += 1.0 / (rank + 1)
            score_buckets[key]["hits"] += 1

    if bm25 is not None:
        try:
            bm25.k = sparse_k
            sparse_hits = bm25.get_relevant_documents(question)
        except Exception:
            sparse_hits = []

        for rank, doc in enumerate(sparse_hits[:sparse_k]):
            if not _doc_project_match(doc, project_id, document_ids):
                continue
            key = _doc_key(doc)
            docs_by_key[key] = doc
            score_buckets[key]["bm25"] += 1.0 / (rank + 1)
            score_buckets[key]["hits"] += 1

    if key_terms:
        for key, doc in list(docs_by_key.items()):
            blob = normalize_text(doc.page_content)
            overlap = sum(1 for t in key_terms if t in blob)
            if overlap:
                score_buckets[key]["kw"] += min(0.8, overlap * 0.12)

    if len(docs_by_key) < MIN_CONTEXT_DOCS and key_terms:
        try:
            broad = vectorstore.similarity_search(question, k=min(60, dense_k * 2))
        except Exception:
            broad = []
        for doc in broad:
            if not _doc_project_match(doc, project_id, document_ids):
                continue
            key = _doc_key(doc)
            docs_by_key[key] = doc
            if any(t in normalize_text(doc.page_content) for t in key_terms):
                score_buckets[key]["kw"] += 0.2

    pre_ranked = []
    for key, doc in docs_by_key.items():
        s = score_buckets[key]
        combined = (0.45 * s["dense"]) + (0.30 * s["bm25"]) + (0.15 * s["kw"]) + (0.10 * min(5, s["hits"]) / 5)
        pre_ranked.append((doc, combined, s))

    pre_ranked.sort(key=lambda x: x[1], reverse=True)
    docs = [doc for doc, _, _ in pre_ranked[:MAX_CANDIDATES]]
    docs = _rank_candidates(question, q_type, docs)
    return docs, pre_ranked


def _source_overlap_confidence(answer: str, sources: list) -> float:
    if not answer or not sources:
        return 0.0
    ans = normalize_text(answer)
    tokens = [t for t in ans.split() if len(t) >= 4]
    if not tokens:
        return 0.0

    scored = []
    for s in sources:
        blob = normalize_text(f"{s.get('document_name', '')} {s.get('source_text', '')} {s.get('owner_name', '')}")
        overlap = sum(1 for t in tokens if t in blob)
        scored.append(overlap)

    if not scored:
        return 0.0
    return min(1.0, max(scored) / max(1, len(tokens)))


def estimate_confidence(question: str, q_type: str, docs: list, sources: list, answer: str | None = None) -> float:
    if not docs:
        return 0.0

    sample = docs[:5]
    if sample:
        try:
            scores = list(reranker.predict([(question, d.metadata.get("parent_chunk", d.page_content)) for d in sample]))
        except Exception:
            scores = [0.0] * len(sample)
        max_s = max(scores) if scores else 0.0
        min_s = min(scores) if scores else 0.0
        rerank_conf = 0.5 if max_s == min_s else (max_s - min_s) / (abs(max_s) + abs(min_s) + 1e-6)
        rerank_conf = max(0.0, min(1.0, 0.45 + rerank_conf / 2))
    else:
        rerank_conf = 0.0

    source_conf = min(1.0, len(sources) / 3.0)
    doc_conf = min(1.0, len(docs) / 8.0)
    overlap_conf = _source_overlap_confidence(answer or question, sources) if sources else 0.0

    if q_type == "comparison":
        base = 0.20
    elif q_type in {"conversational", "extraction"}:
        base = 0.25
    elif q_type in {"explanatory", "factual"}:
        base = 0.22
    else:
        base = 0.20

    confidence = base + 0.35 * rerank_conf + 0.20 * source_conf + 0.15 * doc_conf + 0.10 * overlap_conf
    return max(0.0, min(1.0, confidence))


def hyde_query(question: str, model_name: str = HYDE_MODEL) -> str:
    try:
        from langchain_ollama import OllamaLLM
        llm = OllamaLLM(model=model_name, base_url="http://localhost:11434")
        prompt = (
            "Write a concise hypothetical answer or paraphrase that would help retrieve documents for this question. "
            "Keep important nouns and entities. Do not answer with uncertainty.\n\n"
            f"Question: {question}\n\nHypothetical retrieval text:"
        )
        text = str(llm.invoke(prompt)).strip()
        return text[:500] if text else question
    except Exception:
        return question


def compress_context_for_llm(question: str, context_texts: list[str]) -> list[str]:
    ranked = sorted(context_texts, key=lambda x: len(x), reverse=True)
    compressed = []
    total = 0
    for chunk in ranked[:MAX_CONTEXT_CHUNKS]:
        snippet = chunk.strip()
        if len(snippet) > 1800:
            snippet = snippet[:1800]
        compressed.append(snippet)
        total += len(snippet)
        if total > 12000:
            break
    return compressed


def needs_table(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in ["compare", "difference", "table", "vs", "between", "among"])


def build_comparison_table(answer: str, sources: list[dict], entities: list[str]) -> str:
    if not entities:
        return answer
    rows = ["\n\n📊 **Structured Comparison**"]
    for entity in entities[:6]:
        matched_sources = [
            s for s in sources
            if owner_matches_entity(s.get("owner_name", ""), entity)
            or owner_matches_entity(s.get("document_name", ""), entity)
        ]
        page_ref = matched_sources[0].get("page_number", "?") if matched_sources else "?"
        doc_name = matched_sources[0].get("document_name", "") if matched_sources else ""
        rows.append(f"- **{entity}** | Source: {doc_name} | Page: {page_ref}")
    return answer.rstrip() + "\n" + "\n".join(rows)


def debug_retrieved_chunks(question: str, context_texts: list[str]):
    print(f"[ALITA] Debug retrieved chunks for: {question}")
    for i, chunk in enumerate(context_texts):
        preview = chunk[:500].replace("\n", " ")
        print(f"--- Chunk {i + 1} ---")
        print(preview)


def get_directory_size(path):
    total_size = 0
    if os.path.exists(path):
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    return total_size


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _embed_and_store_compat(chunks: list[dict], document_id: str, project_id: str, document_name: str = "", file_url: str = ""):
    try:
        return vs.embed_and_store(
            chunks=chunks,
            document_id=document_id,
            project_id=project_id,
            document_name=document_name,
            file_url=file_url,
            replace_existing=True,
        )
    except TypeError:
        try:
            return vs.embed_and_store(
                chunks=chunks,
                document_id=document_id,
                project_id=project_id,
                document_name=document_name,
                file_url=file_url,
            )
        except TypeError:
            return vs.embed_and_store(chunks, document_id, project_id, document_name, file_url)


# -----------------------------
# Routes
# -----------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Engine", "version": APP_VERSION}


@app.post("/api/v1/process-document", response_model=DocumentProcessResponse)
async def process_document(request: DocumentProcessRequest):
    try:
        file_name = os.path.basename(request.file_path)
        _ = _file_hash(request.file_path)

        if "media" in request.file_path.replace("\\", "/"):
            parts = request.file_path.replace("\\", "/").split("media/")
            file_url = f"/media/{parts[-1]}"
        else:
            file_url = f"/media/uploads/{file_name}"

        pages = extract_pages_from_pdf(request.file_path)
        text_length = sum(len(p["text"]) for p in pages)
        chunks = chunk_pages(pages)

        success = _embed_and_store_compat(
            chunks=chunks,
            document_id=request.document_id,
            project_id=request.project_id,
            document_name=file_name,
            file_url=file_url,
        )

        if not success:
            raise ValueError("Failed to generate and store embeddings.")

        _VECTORSTORE_CACHE["signature"] = None
        _VECTORSTORE_CACHE["value"] = None
        _BM25_CACHE["signature"] = None
        _BM25_CACHE["value"] = None
        _RETRIEVAL_CACHE.clear()

        return DocumentProcessResponse(
            document_id=request.document_id,
            status="SUCCESS",
            extracted_length=text_length,
            total_chunks=len(chunks),
            message=f"Processed {len(pages)} pages into {len(chunks)} chunks.",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log_event("process_document_error", error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats")
async def get_system_stats():
    try:
        llm_model = get_active_model_name()
        faiss_size_bytes = get_directory_size(vs.FAISS_INDEX_PATH)
        faiss_size_mb = round(faiss_size_bytes / (1024 * 1024), 2)
        vectorstore = _get_vectorstore() if os.path.exists(vs.FAISS_INDEX_PATH) else None
        total_chunks = vectorstore.index.ntotal if vectorstore is not None else 0
        return {
            "active_model": llm_model,
            "embedding_model": EMBED_MODEL_NAME,
            "reranker": RERANKER_NAME,
            "vector_store_size_mb": faiss_size_mb,
            "indexed_chunks": total_chunks,
            "status": "Online",
            "version": APP_VERSION,
        }
    except Exception as e:
        log_event("stats_error", error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    try:
        if request.image_data:
            from services.llm_service import generate_vision_answer
            vision_answer = generate_vision_answer(request.question, request.image_data)
            return ChatResponse(answer=vision_answer, sources=[])

        if not os.path.exists(vs.FAISS_INDEX_PATH):
            raise HTTPException(status_code=400, detail="No documents have been indexed yet.")

        cache_key = (
            normalize_text(request.question),
            str(getattr(request, "project_id", None) or "all"),
            str(",".join(sorted(getattr(request, "document_ids", None) or []))),
            APP_VERSION,
            _vectorstore_signature(),
        )
        now = time.time()
        cached = _RETRIEVAL_CACHE.get(cache_key)
        if cached and now - cached[0] <= _RETRIEVAL_CACHE_TTL_SECONDS:
            return cached[1]

        vectorstore = _get_vectorstore()
        total_chunks = vectorstore.index.ntotal
        if total_chunks == 0:
            raise HTTPException(status_code=400, detail="The database is empty.")

        q_type = detect_question_type(request.question)
        explicit_entity = extract_entity_from_question(request.question)
        if explicit_entity:
            explicit_entity = explicit_entity.strip().title()
        explanatory = is_explanatory(request.question)
        project_filter = _request_project_filter(request.project_id)
        dynamic_k = 30 if q_type == "comparison" else 20 if explanatory else 10
        bm25 = _get_bm25_retriever(vectorstore)

        log_event(
            "query_received",
            question=request.question,
            q_type=q_type,
            project_id=request.project_id,
            dynamic_k=dynamic_k,
            indexed_chunks=total_chunks,
            explicit_entity=explicit_entity,
        )

        # Fast-path for explicit people questions.
        if explicit_entity and q_type in {"conversational", "extraction", "factual"}:
            all_docs = _get_global_docs(project_filter, getattr(request, "document_ids", None))
            matched_docs = _docs_matching_entity(all_docs, explicit_entity)
            if matched_docs:
                context_texts, sources = build_entity_filtered_context(matched_docs, explicit_entity)
                context_texts = compress_context_for_llm(request.question, context_texts)
                debug_retrieved_chunks(request.question, context_texts)

                answer = generate_answer(
                    request.question,
                    context_texts,
                    entities=[explicit_entity],
                    conversation_history=getattr(request, "conversation_history", None),
                    include_followups=True,
                )

                confidence = estimate_confidence(request.question, q_type, matched_docs, sources, answer)
                if confidence < VERY_LOW_CONFIDENCE_THRESHOLD:
                    answer = (
                        "I could not find strong evidence for this in the indexed documents. "
                        "Please check whether the relevant file has been uploaded, or refine the question."
                    )
                elif confidence < LOW_CONFIDENCE_THRESHOLD:
                    answer = (
                        answer.strip()
                        + "\n\nConfidence note: the retrieved evidence is limited, so this answer should be treated cautiously."
                    )

                final_sources = filter_sources_strict(sources, explicit_entity)[:MAX_SOURCE_COUNT]
                resp = ChatResponse(answer=answer, sources=final_sources)
                _RETRIEVAL_CACHE[cache_key] = (now, resp)
                return resp

            if project_filter is None:
                return ChatResponse(answer=f"I couldn't find {explicit_entity} in the indexed documents.", sources=[])
            return ChatResponse(answer=f"I couldn't find {explicit_entity} in this project.", sources=[])

        hyde_text = hyde_query(request.question)
        query_bundle = [request.question]
        if hyde_text and normalize_text(hyde_text) != normalize_text(request.question):
            query_bundle.append(hyde_text)

        results, pre_ranked = _dense_and_sparse_retrieval(
            vectorstore=vectorstore,
            bm25=bm25,
            question=query_bundle[0],
            q_type=q_type,
            project_id=project_filter,
            document_ids=getattr(request, "document_ids", None),
        )

        if len(query_bundle) > 1:
            hyde_results, _ = _dense_and_sparse_retrieval(
                vectorstore=vectorstore,
                bm25=bm25,
                question=query_bundle[1],
                q_type=q_type,
                project_id=project_filter,
                document_ids=getattr(request, "document_ids", None),
            )
            merged = []
            seen = set()
            for d in results + hyde_results:
                key = _doc_key(d)
                if key not in seen:
                    seen.add(key)
                    merged.append(d)
            results = merged[:MAX_CANDIDATES]

        log_event(
            "retrieved_candidates",
            count=len(results),
            top_preview=[
                {
                    "document_name": d.metadata.get("document_name", ""),
                    "owner_name": d.metadata.get("owner_name", ""),
                    "chunk_index": d.metadata.get("chunk_index"),
                }
                for d in results[:5]
            ],
        )

        results = prefer_domain_docs(request.question, q_type, results)
        log_event("domain_routed", count=len(results), q_type=q_type)

        if q_type == "comparison":
            context_texts, sources = build_owner_context(results)
            entities = clean_entities(extract_entities_from_results(results, context_texts))
            log_event("comparison_entities", entities=entities)
        elif q_type == "conversational":
            all_entities = clean_entities(extract_entities_from_results(results, []))
            target_entity = select_target_entity(request.question, all_entities)
            log_event("conversational_target", target_entity=target_entity, entities=all_entities)
            if target_entity:
                context_texts, sources = build_entity_filtered_context(results, target_entity)
                entities = [target_entity]
            else:
                context_texts, sources = build_context(results)
                entities = all_entities
        elif q_type == "extraction":
            resume_first = [d for d in results if is_resume_doc(d)]
            if resume_first:
                context_texts, sources = build_context(resume_first)
                entities = clean_entities(extract_entities_from_results(resume_first, context_texts))
            else:
                context_texts, sources = build_context(results)
                entities = clean_entities(extract_entities_from_results(results, context_texts))
        else:
            tech_results = [d for d in results if not is_resume_doc(d)]
            context_texts, sources = build_context(tech_results if tech_results else results)
            entities = []

        if not context_texts:
            if request.project_id != "all":
                resp = ChatResponse(answer="I couldn't find any information about that in this specific project.", sources=[])
            else:
                resp = ChatResponse(answer="I couldn't find any reliable information in the indexed documents.", sources=[])
            _RETRIEVAL_CACHE[cache_key] = (now, resp)
            return resp

        if len(context_texts) > MAX_CONTEXT_CHUNKS:
            context_texts = context_texts[:MAX_CONTEXT_CHUNKS]
        context_texts = compress_context_for_llm(request.question, context_texts)
        debug_retrieved_chunks(request.question, context_texts)

        conversation_history = getattr(request, "conversation_history", None)
        answer = generate_answer(
            request.question,
            context_texts,
            entities=entities if q_type == "comparison" else entities[:5],
            conversation_history=conversation_history,
            include_followups=True,
        )

        confidence = estimate_confidence(request.question, q_type, results, sources, answer)
        log_event("confidence_estimate", confidence=round(confidence, 3), q_type=q_type)

        if confidence < VERY_LOW_CONFIDENCE_THRESHOLD:
            answer = (
                "I could not find strong evidence for this in the indexed documents. "
                "Please check whether the relevant file has been uploaded, or refine the question."
            )
        elif confidence < LOW_CONFIDENCE_THRESHOLD:
            answer = (
                answer.strip()
                + "\n\nConfidence note: the retrieved evidence is limited, so this answer should be treated cautiously."
            )

        if needs_table(request.question) and q_type in {"comparison", "conversational", "extraction"}:
            answer = build_comparison_table(answer, sources, entities)

        if q_type == "comparison":
            matched_entities = extract_names_from_answer(answer, entities)
            allowed = matched_entities if matched_entities else entities
            sources = filter_sources_for_comparison(sources, allowed)
        elif q_type == "conversational":
            sources = filter_sources_strict(sources, entities[0]) if entities else sources[:2]
        elif q_type in {"explanatory", "factual", "extraction"}:
            sources = filter_sources_by_answer_and_domain(answer, sources, q_type)
        else:
            sources = sources[:MAX_SOURCE_COUNT]

        final_sources = sources[:MAX_SOURCE_COUNT]
        log_event(
            "final_response",
            confidence=round(confidence, 3),
            source_count=len(final_sources),
            answer_preview=answer[:180],
        )

        resp = ChatResponse(answer=answer, sources=final_sources)
        _RETRIEVAL_CACHE[cache_key] = (now, resp)
        return resp

    except Exception as e:
        log_event("chat_error", error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/models/switch")
async def switch_model(request: ModelSwitchRequest):
    try:
        set_active_model(request.model_name)
        return {"status": "success", "active_model": request.model_name}
    except Exception as e:
        log_event("model_switch_error", error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/debug-retrieval")
async def debug_retrieval(request: ChatRequest):
    try:
        vectorstore = _get_vectorstore()
        bm25 = _get_bm25_retriever(vectorstore)
        q_type = detect_question_type(request.question)
        project_filter = _request_project_filter(request.project_id)
        results, pre_ranked = _dense_and_sparse_retrieval(
            vectorstore=vectorstore,
            bm25=bm25,
            question=request.question,
            q_type=q_type,
            project_id=project_filter,
        )

        return {
            "total_chunks_in_index": vectorstore.index.ntotal,
            "query": request.question,
            "question_type": q_type,
            "retrieved": [
                {
                    "rank": i + 1,
                    "child_chunk_preview": doc.page_content[:200],
                    "parent_chunk_preview": doc.metadata.get("parent_chunk", "")[:300],
                    "page_number": doc.metadata.get("page_number", "?"),
                    "document_name": doc.metadata.get("document_name", ""),
                    "owner_name": doc.metadata.get("owner_name", ""),
                    "document_kind": doc.metadata.get("document_kind", ""),
                    "chunk_index": doc.metadata.get("chunk_index"),
                }
                for i, doc in enumerate(results[:20])
            ],
            "candidate_debug": [
                {
                    "document_name": doc.metadata.get("document_name", ""),
                    "owner_name": doc.metadata.get("owner_name", ""),
                    "score_hint": round(score, 4),
                    "hits": stats["hits"],
                    "dense": round(stats["dense"], 4),
                    "bm25": round(stats["bm25"], 4),
                    "kw": round(stats["kw"], 4),
                }
                for doc, score, stats in pre_ranked[:20]
            ],
        }
    except Exception as e:
        log_event("debug_retrieval_error", error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/delete-document")
async def delete_document(request: dict):
    try:
        document_id = str((request or {}).get("document_id", "")).strip()
        if not document_id:
            raise HTTPException(status_code=400, detail="document_id is required")
        ok = vs.delete_document_from_index(document_id)
        _VECTORSTORE_CACHE["signature"] = None
        _VECTORSTORE_CACHE["value"] = None
        _BM25_CACHE["signature"] = None
        _BM25_CACHE["value"] = None
        _RETRIEVAL_CACHE.clear()
        return {"status": "success", "deleted_document_id": document_id, "deleted": ok}
    except HTTPException:
        raise
    except Exception as e:
        log_event("delete_document_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/delete-project")
async def delete_project(request: dict):
    try:
        project_id = str((request or {}).get("project_id", "")).strip()
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")
        ok = vs.delete_project_from_index(project_id)
        _VECTORSTORE_CACHE["signature"] = None
        _VECTORSTORE_CACHE["value"] = None
        _BM25_CACHE["signature"] = None
        _BM25_CACHE["value"] = None
        _RETRIEVAL_CACHE.clear()
        return {"status": "success", "deleted_project_id": project_id, "deleted": ok}
    except HTTPException:
        raise
    except Exception as e:
        log_event("delete_project_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


DEFAULT_EVAL_CASES = [
    {"name": "resume_lookup", "question": "Who is this person?", "project_id": "all", "expected_type": "conversational"},
    {"name": "comparison", "question": "Compare the profiles of the people in the indexed documents.", "project_id": "all", "expected_type": "comparison"},
    {"name": "technical_explain", "question": "Explain the working of the topic in the document.", "project_id": "all", "expected_type": "explanatory"},
]


def _run_single_eval_case(case: dict) -> dict:
    vectorstore = _get_vectorstore()
    bm25 = _get_bm25_retriever(vectorstore)
    q_type = detect_question_type(case["question"])
    results, _ = _dense_and_sparse_retrieval(
        vectorstore=vectorstore,
        bm25=bm25,
        question=case["question"],
        q_type=q_type,
        project_id=_request_project_filter(case.get("project_id")),
    )
    results = prefer_domain_docs(case["question"], q_type, results)

    if q_type == "comparison":
        context_texts, sources = build_owner_context(results)
        entities = clean_entities(extract_entities_from_results(results, context_texts))
    elif q_type == "conversational":
        ents = clean_entities(extract_entities_from_results(results, []))
        target = select_target_entity(case["question"], ents)
        if target:
            context_texts, sources = build_entity_filtered_context(results, target)
            entities = [target]
        else:
            context_texts, sources = build_context(results)
            entities = ents
    else:
        tech_results = [d for d in results if is_technical_doc(d)]
        context_texts, sources = build_context(tech_results if tech_results else results)
        entities = []

    answer = generate_answer(
        case["question"],
        context_texts[:MAX_CONTEXT_CHUNKS],
        entities=entities[:5],
        conversation_history=None,
        include_followups=False,
    )
    confidence = estimate_confidence(case["question"], q_type, results, sources, answer)

    source_purity = None
    if q_type in {"explanatory", "factual"}:
        source_purity = sum(1 for s in sources if "resume" not in (s.get("document_name", "") or "").lower()) / max(1, len(sources))
    elif q_type in {"conversational", "extraction"} and entities:
        source_purity = sum(1 for s in sources if filter_sources_strict([s], entities[0])) / max(1, len(sources))

    return {
        "name": case["name"],
        "question": case["question"],
        "detected_type": q_type,
        "expected_type": case.get("expected_type"),
        "retrieved_docs": len(results),
        "sources": len(sources),
        "confidence": round(confidence, 4),
        "source_purity": None if source_purity is None else round(float(source_purity), 4),
        "answer_preview": answer[:300],
    }


@app.post("/api/v1/evaluate")
async def evaluate_pipeline(request: dict | None = None):
    try:
        cases = (request or {}).get("cases") or DEFAULT_EVAL_CASES
        results = [_run_single_eval_case(case) for case in cases]

        avg_conf = sum(r["confidence"] for r in results) / max(1, len(results))
        avg_sources = sum(r["sources"] for r in results) / max(1, len(results))
        avg_retrieved = sum(r["retrieved_docs"] for r in results) / max(1, len(results))

        return {
            "version": APP_VERSION,
            "cases_run": len(results),
            "avg_confidence": round(avg_conf, 4),
            "avg_sources": round(avg_sources, 4),
            "avg_retrieved_docs": round(avg_retrieved, 4),
            "results": results,
        }
    except Exception as e:
        log_event("evaluation_error", error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/evaluate")
async def evaluate_pipeline_get():
    return await evaluate_pipeline({})
