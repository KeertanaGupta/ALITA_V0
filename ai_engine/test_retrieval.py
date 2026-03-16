from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import FAISS
import os

FAISS_INDEX_PATH = "faiss_index"

# 1. Initialize the exact same embedding model
print("Loading BGE-Small Embedding Model...")
embed_model = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

# 2. Load our saved database
if not os.path.exists(FAISS_INDEX_PATH):
    print("❌ Error: FAISS index not found. Did the ingestion pipeline run?")
    exit()

print("Loading FAISS Database...")
vectorstore = FAISS.load_local(
    FAISS_INDEX_PATH, 
    embed_model, 
    allow_dangerous_deserialization=True # Safe because we built it locally
)

# 3. Define a test question
# CHANGE THIS TO SOMETHING RELEVANT TO YOUR PDF!
query = "What is Keertana's salary?"

print(f"\n🔍 Searching for: '{query}'")

# 4. Perform the Vector Similarity Search (Fetch top 2 most relevant chunks)
results = vectorstore.similarity_search_with_score(query, k=2)

print("\n🎯 TOP RESULTS FOUND:\n" + "-"*40)
for i, (doc, score) in enumerate(results):
    print(f"RESULT {i+1} (Score: {score:.4f}):")
    print(f"Metadata: {doc.metadata}")
    print(f"Text Chunk:\n{doc.page_content}\n")
    print("-" * 40)