from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.vectorstores import FAISS
import os

# Import our custom schemas
from schemas import DocumentProcessRequest, DocumentProcessResponse, ChatRequest, ChatResponse

# Import our custom microservices
from services.document_processor import extract_text_from_pdf
from services.chunking_service import chunk_document_text
from services.vector_store import embed_and_store, FAISS_INDEX_PATH, embed_model
from services.llm_service import generate_answer

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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Engine"}

@app.post("/api/v1/process-document", response_model=DocumentProcessResponse)
async def process_document(request: DocumentProcessRequest):
    """
    Ingests a document, extracts text, chunks it, embeds it, and saves to FAISS.
    """
    try:
        # Step 1: Extract Text
        raw_text = extract_text_from_pdf(request.file_path)
        text_length = len(raw_text)
        
        # Step 2: Chunking
        chunks = chunk_document_text(raw_text)
        total_chunks = len(chunks)
        
        # Step 3 & 4: Embeddings & Save to FAISS Vector DB
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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest):
    """
    The main RAG pipeline: Retrieves context from FAISS, then generates an answer with Ollama.
    """
    try:
        # 1. Check if we have a database
        if not os.path.exists(FAISS_INDEX_PATH):
            raise HTTPException(status_code=400, detail="No documents have been indexed yet.")
            
        # 2. Retrieve the context (The Librarian)
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embed_model, allow_dangerous_deserialization=True)
        # We fetch top 3 chunks to give the LLM maximum context
        results = vectorstore.similarity_search(request.question, k=3) 
        
        # 3. Extract the text and metadata
        context_texts = [doc.page_content for doc in results]
        sources = [doc.metadata for doc in results]
        
        # 4. Generate the answer (The Brain)
        answer = generate_answer(request.question, context_texts)
        
        return ChatResponse(
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))