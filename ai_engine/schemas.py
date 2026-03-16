from pydantic import BaseModel

class DocumentProcessRequest(BaseModel):
    document_id: str
    file_path: str  # The absolute path where Django saved the file
    project_id: str

class DocumentProcessResponse(BaseModel):
    document_id: str
    status: str
    extracted_length: int
    message: str