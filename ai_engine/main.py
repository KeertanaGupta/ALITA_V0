from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="ALITA AI Engine",
    description="Offline RAG and AI Microservices API",
    version="1.0.0"
)

# Configure CORS for the AI Engine
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in dev
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Engine"}