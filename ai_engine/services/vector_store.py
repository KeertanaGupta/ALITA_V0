from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
import os

# This will now successfully route the heavy math to your RTX 5050!
embed_model = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={'device': 'cpu'}, 
    encode_kwargs={'normalize_embeddings': True}
)

FAISS_INDEX_PATH = "faiss_index"

def embed_and_store(chunks: list[str], document_id: str, project_id: str):
    """
    Converts text chunks into embeddings and saves them to the local FAISS index.
    """
    if not chunks:
        return False

    # 1. Convert raw strings into LangChain Document objects so we can attach metadata
    documents = [
        Document(
            page_content=chunk,
            metadata={"document_id": document_id, "project_id": project_id, "chunk_index": i}
        ) for i, chunk in enumerate(chunks)
    ]

    # 2. Check if we already have a database, otherwise create a new one
    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(f"{FAISS_INDEX_PATH}/index.faiss"):
        # Load existing vector store
        vectorstore = FAISS.load_local(
            FAISS_INDEX_PATH, 
            embed_model, 
            allow_dangerous_deserialization=True # Safe because we generated the file locally
        )
        vectorstore.add_documents(documents)
    else:
        # Create brand new vector store
        vectorstore = FAISS.from_documents(documents, embed_model)

    # 3. Save it to disk
    vectorstore.save_local(FAISS_INDEX_PATH)
    
    return True