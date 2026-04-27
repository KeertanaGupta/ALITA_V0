import sys
import os
import traceback
import asyncio
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def test_api():
    try:
        from main import process_document
        from schemas import DocumentProcessRequest
        req = DocumentProcessRequest(document_id="test_doc_001", project_id="test_proj_001", file_path=os.path.abspath("test_doc.pdf"))
        resp = await process_document(req)
        with open("error_trace.txt", "w") as f:
            f.write("Success")
    except Exception as e:
        with open("error_trace.txt", "w") as f:
            f.write(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_api())
