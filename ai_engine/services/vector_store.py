# ai_engine/services/vector_store.py
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer  # Switch from Ollama!
from langchain_community.embeddings import HuggingFaceEmbeddings
import os
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[ALITA] Embedding device: {device.upper()}")

embed_model = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={"device": device},
    encode_kwargs={
        "normalize_embeddings": True,
        "batch_size": 64 if device == "cuda" else 32
    }
)

FAISS_INDEX_PATH = "faiss_index"

def embed_and_store(chunks: list[dict], document_id: str, project_id: str):
    """
    chunks: list of dicts with 'child', 'parent', 'parent_index'
    Embeds child chunks, stores parent chunk as metadata for context-rich retrieval.
    """
    if not chunks:
        return False

    documents = [
        Document(
            page_content=chunk["child"],          # embed the small chunk
            metadata={
                "document_id": document_id,
                "project_id": project_id,
                "chunk_index": i,
                "parent_chunk": chunk["parent"],  # 🔑 full context stored here
                "parent_index": chunk["parent_index"]
            }
        ) for i, chunk in enumerate(chunks)
    ]

    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(f"{FAISS_INDEX_PATH}/index.faiss"):
        vectorstore = FAISS.load_local(
            FAISS_INDEX_PATH,
            embed_model,
            allow_dangerous_deserialization=True
        )
        vectorstore.add_documents(documents)
    else:
        vectorstore = FAISS.from_documents(documents, embed_model)

    vectorstore.save_local(FAISS_INDEX_PATH)
    return True