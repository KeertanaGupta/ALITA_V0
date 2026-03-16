from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import our custom logic
from schemas import DocumentProcessRequest, DocumentProcessResponse
from services.document_processor import extract_text_from_pdf

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
    Receives a request from Django to process a newly uploaded document.
    """
    try:
        # Step 1: Extract Text
        raw_text = extract_text_from_pdf(request.file_path)
        text_length = len(raw_text)
        
        # TODO: Step 2: Chunking
        # TODO: Step 3: Embedding
        # TODO: Step 4: Save to FAISS
        
        # For now, we return success if we successfully ripped the text
        return DocumentProcessResponse(
            document_id=request.document_id,
            status="SUCCESS",
            extracted_length=text_length,
            message="Text extracted successfully."
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))