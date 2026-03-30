# ai_engine/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.vectorstores import FAISS
from sentence_transformers import CrossEncoder
from pydantic import BaseModel
import os
import traceback

from schemas import DocumentProcessRequest, DocumentProcessResponse, ChatRequest, ChatResponse
from services.document_processor import extract_text_from_pdf
from services.chunking_service import chunk_document_text
from services.vector_store import embed_and_store, FAISS_INDEX_PATH, embed_model
from services.llm_service import generate_answer, set_active_model, get_active_model_name, is_explanatory


class ModelSwitchRequest(BaseModel):
    model_name: str


app = FastAPI(
    title="ALITA AI Engine",
    description="Offline RAG and AI Microservices API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# CROSS-ENCODER RERANKER — loaded once at startup
# ==========================================
print("[ALITA] Loading cross-encoder reranker...")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
print("[ALITA] Reranker ready.")


def rerank(question: str, docs: list) -> list:
    if not docs:
        return docs
    pairs = [(question, doc.page_content) for doc in docs]
    scores = reranker.predict(pairs)
    scored = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored[:10]]


# ==========================================
# BGE MULTI-QUERY EXPANSION
# ==========================================
def expand_query(question: str) -> list[str]:
    stripped = question.strip().rstrip("?")
    bge_prefix = "Represent this sentence for searching relevant passages: "
    return [
        f"{bge_prefix}{question}",
        f"{bge_prefix}what is {stripped}",
        f"{bge_prefix}define {stripped}",
    ]


# ==========================================
# KEYWORD EXTRACTION
# ==========================================
STOP_WORDS = {
    "what", "when", "where", "which", "define", "explain",
    "about", "does", "have", "with", "this", "that", "from",
    "give", "write", "short", "note", "state", "describe",
    "degree", "units", "value", "show", "find", "each",
    "type", "form", "water", "the", "and", "for", "are",
    "how", "why", "can", "its", "their", "your",
}


def extract_key_terms(question: str) -> list[str]:
    words = question.lower().replace("?", "").replace(",", "").replace(".", "").split()
    return [w for w in words if len(w) >= 3 and w not in STOP_WORDS]


# ==========================================
# SECTION-AWARE CONTEXT BUILDER
# After reranking, for each top result we also
# pull its neighbouring parent chunks (±1 index).
# This gives the LLM the full surrounding section,
# not just isolated fragments.
# Only applied for explanatory questions where
# complete coverage matters.
# ==========================================
def build_section_context(results: list, vectorstore, question: str) -> tuple[list, list]:
    """
    For each top result, fetches neighbouring parent chunks
    to give the LLM complete section coverage.
    Returns (context_texts, sources).
    """
    # Build a lookup: parent_index -> parent_chunk text, keyed by doc_id
    # We need this to fetch neighbours without extra DB calls
    seen_parent_keys = set()
    context_texts = []
    sources = []

    # Collect all parent indices we want (top hit ± 1 neighbour)
    parent_targets = []
    for doc in results:
        doc_id = doc.metadata.get("document_id")
        parent_idx = doc.metadata.get("parent_index")
        if parent_idx is not None:
            # Add the hit itself and its immediate neighbours
            for offset in [-1, 0, 1]:
                neighbour_idx = parent_idx + offset
                if neighbour_idx >= 0:
                    parent_targets.append((doc_id, neighbour_idx, doc))

    # Now extract context for each target, deduplicating by parent key
    for doc_id, target_parent_idx, source_doc in parent_targets:
        parent_key = f"{doc_id}_{target_parent_idx}"
        if parent_key in seen_parent_keys:
            continue
        seen_parent_keys.add(parent_key)

        # For the exact hit we have the parent_chunk in metadata
        hit_parent_idx = source_doc.metadata.get("parent_index")
        if target_parent_idx == hit_parent_idx:
            parent_text = source_doc.metadata.get("parent_chunk", source_doc.page_content)
            context_texts.append(parent_text)
            sources.append(source_doc.metadata)
        # For neighbours (±1), we do a targeted similarity search
        # using the hit's content to find nearby chunks
        else:
            neighbour_results = vectorstore.similarity_search(
                source_doc.page_content,
                k=20,
                filter={"document_id": doc_id} if doc_id else None
            )
            for neighbour in neighbour_results:
                if neighbour.metadata.get("parent_index") == target_parent_idx:
                    n_key = f"{doc_id}_{target_parent_idx}"
                    if n_key not in seen_parent_keys:
                        seen_parent_keys.add(n_key)
                        neighbour_text = neighbour.metadata.get("parent_chunk", neighbour.page_content)
                        context_texts.append(neighbour_text)
                        sources.append(neighbour.metadata)
                    break

    return context_texts, sources


def build_simple_context(results: list) -> tuple[list, list]:
    """Standard context extraction — used for factual questions."""
    seen_parent_keys = set()
    context_texts = []
    sources = []
    for doc in results:
        parent_idx = doc.metadata.get("parent_index")
        doc_id = doc.metadata.get("document_id")
        parent_key = f"{doc_id}_{parent_idx}"
        if parent_key not in seen_parent_keys:
            seen_parent_keys.add(parent_key)
            parent_text = doc.metadata.get("parent_chunk", doc.page_content)
            context_texts.append(parent_text)
            sources.append(doc.metadata)
    return context_texts, sources


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Engine"}


@app.post("/api/v1/process-document", response_model=DocumentProcessResponse)
async def process_document(request: DocumentProcessRequest):
    try:
        raw_text = extract_text_from_pdf(request.file_path)
        text_length = len(raw_text)
        chunks = chunk_document_text(raw_text)
        total_chunks = len(chunks)
        success = embed_and_store(
            chunks=chunks,
            document_id=request.document_id,
            project_id=request.project_id
        )
        if not success:
            raise ValueError("Failed to generate and store embeddings.")
        return DocumentProcessResponse(
            document_id=request.document_id,
            status="SUCCESS",
            extracted_length=text_length,
            total_chunks=total_chunks,
            message="Document fully processed, embedded, and stored in FAISS."
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print("\n=== DOCUMENT PROCESSING CRASH ===")
        traceback.print_exc()
        print("=================================\n")
        raise HTTPException(status_code=500, detail=str(e))


def get_directory_size(path):
    total_size = 0
    if os.path.exists(path):
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    return total_size


@app.get("/api/v1/stats")
async def get_system_stats():
    try:
        llm_model = get_active_model_name()
        faiss_size_bytes = get_directory_size(FAISS_INDEX_PATH)
        faiss_size_mb = round(faiss_size_bytes / (1024 * 1024), 2)
        return {
            "active_model": llm_model,
            "embedding_model": "bge-small-en-v1.5",
            "vector_store_size_mb": faiss_size_mb,
            "status": "Online"
        }
    except Exception as e:
        print("STATS ENDPOINT ERROR:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """
    Main RAG pipeline — Full Hybrid Search with Reranking + Section-Aware Context.

    Step 1: Detect question type — explanatory vs factual
    Step 2: Adaptive k — higher for explanatory questions
    Step 3: BGE multi-query MMR vector retrieval
    Step 4: Fuzzy keyword fallback
    Step 5: Cross-encoder reranking
    Step 6: Section-aware context (explanatory) or simple context (factual)
    Step 7: Adaptive prompt → LLM answer
    """
    try:
        if not os.path.exists(FAISS_INDEX_PATH):
            raise HTTPException(status_code=400, detail="No documents have been indexed yet.")

        vectorstore = FAISS.load_local(
            FAISS_INDEX_PATH, embed_model, allow_dangerous_deserialization=True
        )

        total_chunks = vectorstore.index.ntotal
        if total_chunks == 0:
            raise HTTPException(status_code=400, detail="The database is empty.")

        # ==========================================
        # STEP 1+2 — DETECT QUESTION TYPE, SET K
        # Explanatory questions need broader retrieval
        # to cover complete sections of the document.
        # ==========================================
        explanatory = is_explanatory(request.question)

        if explanatory:
            # Wide retrieval for full section coverage
            dynamic_k = max(15, min(25, 15 + (total_chunks // 100)))
            print(f"[ALITA] Explanatory question detected — k={dynamic_k}")
        else:
            # Tight retrieval for precise factual answers
            dynamic_k = max(8, min(15, 8 + (total_chunks // 50)))
            print(f"[ALITA] Factual question detected — k={dynamic_k}")

        search_kwargs = {"k": dynamic_k, "fetch_k": dynamic_k * 3}

        if request.project_id and request.project_id != "all":
            search_kwargs["filter"] = {"project_id": request.project_id}

        # ==========================================
        # STEP 3 — BGE MULTI-QUERY MMR RETRIEVAL
        # ==========================================
        all_results = []
        seen_chunk_ids = set()

        for query_variant in expand_query(request.question):
            variant_results = vectorstore.max_marginal_relevance_search(
                query_variant, **search_kwargs
            )
            for doc in variant_results:
                chunk_id = doc.metadata.get("chunk_index")
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_results.append(doc)

        # ==========================================
        # STEP 4 — FUZZY KEYWORD FALLBACK
        # ==========================================
        key_terms = extract_key_terms(request.question)
        print(f"[ALITA] Key terms: {key_terms}")

        keyword_matches = []
        if key_terms:
            broad_k = 60 if explanatory else 50
            broad_results = vectorstore.similarity_search(request.question, k=broad_k)

            scored_broad = []
            for doc in broad_results:
                content_lower = doc.page_content.lower()
                match_score = sum(term in content_lower for term in key_terms)
                threshold = max(1, len(key_terms) // 2)
                if match_score >= threshold:
                    scored_broad.append((doc, match_score))

            scored_broad.sort(key=lambda x: x[1], reverse=True)

            for doc, score in scored_broad:
                chunk_id = doc.metadata.get("chunk_index")
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    keyword_matches.append(doc)

            if not keyword_matches:
                print(f"[ALITA] Threshold match empty, using any-match fallback")
                for doc in broad_results:
                    content_lower = doc.page_content.lower()
                    if any(term in content_lower for term in key_terms):
                        chunk_id = doc.metadata.get("chunk_index")
                        if chunk_id not in seen_chunk_ids:
                            seen_chunk_ids.add(chunk_id)
                            keyword_matches.append(doc)

        print(f"[ALITA] Keyword: {len(keyword_matches)} | Vector: {len(all_results)}")

        combined = keyword_matches[:4] + all_results
        combined = combined[:dynamic_k * 2]

        # ==========================================
        # STEP 5 — CROSS-ENCODER RERANKING
        # ==========================================
        results = rerank(request.question, combined)

        # ==========================================
        # STEP 6 — CONTEXT EXTRACTION
        # Section-aware for explanatory questions:
        # fetches neighbouring parent chunks (±1)
        # so the LLM sees complete topic sections.
        # Simple extraction for factual questions.
        # ==========================================
        if explanatory:
            context_texts, sources = build_section_context(results, vectorstore, request.question)
        else:
            context_texts, sources = build_simple_context(results)

        if not context_texts and request.project_id != "all":
            return ChatResponse(
                answer="I couldn't find any information about that in this specific project.",
                sources=[]
            )

        answer = generate_answer(request.question, context_texts)

        return ChatResponse(
            answer=answer,
            sources=sources
        )

    except Exception as e:
        print("\n=== CHAT CRASH ===")
        traceback.print_exc()
        print("==================\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/models/switch")
async def switch_model(request: ModelSwitchRequest):
    try:
        set_active_model(request.model_name)
        return {"status": "success", "active_model": request.model_name}
    except Exception as e:
        print("MODEL SWITCH ERROR:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/debug-retrieval")
async def debug_retrieval(request: ChatRequest):
    """Debug endpoint — shows retrieved chunks before reranking."""
    vectorstore = FAISS.load_local(
        FAISS_INDEX_PATH, embed_model, allow_dangerous_deserialization=True
    )
    total_chunks = vectorstore.index.ntotal
    dynamic_k = max(4, min(10, 4 + (total_chunks // 50)))
    search_kwargs = {"k": dynamic_k, "fetch_k": dynamic_k * 3}
    if request.project_id and request.project_id != "all":
        search_kwargs["filter"] = {"project_id": request.project_id}
    results = vectorstore.max_marginal_relevance_search(request.question, **search_kwargs)
    debug_info = []
    for i, doc in enumerate(results):
        debug_info.append({
            "rank": i + 1,
            "child_chunk_preview": doc.page_content[:200],
            "parent_chunk_preview": doc.metadata.get("parent_chunk", "NO PARENT STORED")[:300],
            "chunk_index": doc.metadata.get("chunk_index"),
            "parent_index": doc.metadata.get("parent_index"),
        })
    return {
        "total_chunks_in_index": total_chunks,
        "query": request.question,
        "retrieved": debug_info
    }