from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import our custom logic
from schemas import DocumentProcessRequest, DocumentProcessResponse
from services.document_processor import extract_text_from_pdf
from services.chunking_service import chunk_document_text # <--- IMPORT THE CHUNKER
from services.vector_store import embed_and_store

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