import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from services.document_processor import extract_pages_from_pdf
from services.chunking_service import chunk_pages

pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_doc.pdf")
print("Extracting:", pdf_path)
try:
    pages = extract_pages_from_pdf(pdf_path)
    print(f"Extracted {len(pages)} pages.")
    for idx, p in enumerate(pages):
        print(f"Page {idx}: len={len(p.get('text', ''))}")

    print("Chunking...")
    chunks = chunk_pages(pages)
    print(f"Generated {len(chunks)} chunks.")
except Exception as e:
    import traceback
    traceback.print_exc()
