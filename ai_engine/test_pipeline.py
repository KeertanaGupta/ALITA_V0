import requests
import os

# 1. Define the API endpoint
URL = "http://localhost:8001/api/v1/process-document"

# 2. Get the absolute path to the PDF
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(current_dir, "test_doc.pdf")

if not os.path.exists(pdf_path):
    print(f"❌ Error: Could not find '{pdf_path}'. Please add it and try again.")
    exit()

# 3. Create the payload matching our FastAPI Pydantic schema
payload = {
    "document_id": "test_doc_001",
    "project_id": "test_proj_001",
    "file_path": pdf_path
}

print("🚀 Sending PDF to ALITA AI Engine...")
print(f"File: {pdf_path}")
print("Working... (This might take a few seconds as it downloads the embedding model the first time).")

# 4. Make the request
try:
    response = requests.post(URL, json=payload)
    
    # 5. Print the results beautifully
    if response.status_code == 200:
        print("\n✅ PIPELINE SUCCESS!")
        data = response.json()
        print(f"Document ID: {data['document_id']}")
        print(f"Status: {data['status']}")
        print(f"Text Extracted: {data['extracted_length']} characters")
        print(f"Total Chunks Generated: {data['total_chunks']}")
        print(f"Message: {data['message']}")
    else:
        print(f"\n❌ PIPELINE FAILED! Status Code: {response.status_code}")
        print("Error Details:", response.text)
        
except requests.exceptions.ConnectionError:
    print("\n❌ Error: Could not connect to FastAPI. Is your Uvicorn server running on port 8001?")