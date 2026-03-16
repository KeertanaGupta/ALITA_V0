from pydantic import BaseModel

class DocumentProcessRequest(BaseModel):
    document_id: str
    file_path: str
    project_id: str

class DocumentProcessResponse(BaseModel):
    document_id: str
    status: str
    extracted_length: int
    total_chunks: int
    message: str

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]