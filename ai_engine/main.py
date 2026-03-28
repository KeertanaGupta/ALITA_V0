from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel
import os
import traceback

# Import our custom schemas
from schemas import DocumentProcessRequest, DocumentProcessResponse, ChatRequest, ChatResponse

# Import our custom microservices
from services.document_processor import extract_text_from_pdf
from services.chunking_service import chunk_document_text
from services.vector_store import embed_and_store, FAISS_INDEX_PATH, embed_model

# Import the new getters and setters from our fixed llm_service!
from services.llm_service import generate_answer, set_active_model, get_active_model_name

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
        # ADD THIS: Force Python to print the exact crash log to the terminal!
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
    """Returns live metrics about the AI Engine and Vector Database."""
    try:
        # Safely fetch the active model from our llm_service!
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
    """The main RAG pipeline with Metadata Filtering."""
    try:
        if not os.path.exists(FAISS_INDEX_PATH):
            raise HTTPException(status_code=400, detail="No documents have been indexed yet.")
            
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embed_model, allow_dangerous_deserialization=True)
        
        # Safely determine 'k' so FAISS never crashes if the database is small!
        safe_k = min(8, vectorstore.index.ntotal)
        if safe_k == 0:
            raise HTTPException(status_code=400, detail="The database is empty.")
            
        search_kwargs = {"k": safe_k}
        if request.project_id and request.project_id != "all":
            search_kwargs["filter"] = {"project_id": request.project_id}
            
        results = vectorstore.similarity_search(request.question, **search_kwargs)
        
        context_texts = [doc.page_content for doc in results]
        sources = [doc.metadata for doc in results]
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/models/switch")
async def switch_model(request: ModelSwitchRequest):
    """Dynamically switches the active local LLM."""
    try:
        # Cleanly update the model through our setter function!
        set_active_model(request.model_name)
        return {"status": "success", "active_model": request.model_name}
    except Exception as e:
        print("MODEL SWITCH ERROR:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))