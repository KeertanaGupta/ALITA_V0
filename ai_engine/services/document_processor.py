import fitz  # PyMuPDF
import os

def extract_text_from_pdf(file_path: str) -> str:
    """
    Reads a PDF file from the given local path and extracts all text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")

    extracted_text = ""
    
    try:
        # Open the document using PyMuPDF
        doc = fitz.open(file_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # We add a newline after each page to maintain some structural boundary
            extracted_text += page.get_text("text") + "\n\n"
            
        doc.close()
        return extracted_text.strip()
        
    except Exception as e:
        raise RuntimeError(f"Failed to process PDF: {str(e)}")