import fitz  # PyMuPDF
import os
import tabula
import pytesseract
from PIL import Image
import io

# Point Python to your Windows Tesseract installation
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text using PyMuPDF. If a page is a scanned image, it uses Tesseract OCR natively without Poppler!
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")

    extracted_text = ""
    
    try:
        # 1. Open the document using PyMuPDF
        doc = fitz.open(file_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text").strip()
            
            # THE OCR FIX: If the page has almost no real text, it's probably a scanned image!
            if len(page_text) < 50: 
                try:
                    # USE FITZ NATIVE RENDERER (No Poppler Required!)
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_bytes))
                    
                    # Run Tesseract OCR on the image
                    ocr_text = pytesseract.image_to_string(image)
                    extracted_text += f"\n\n--- OCR Extracted Page {page_num + 1} ---\n{ocr_text}\n"
                except Exception as ocr_e:
                    print(f"OCR skipped on page {page_num + 1}: {ocr_e}")
            else:
                # If it has normal text, just use that!
                extracted_text += page_text + "\n\n"
                
        doc.close()
        
        # 2. Extract Tables using Tabula (For Time Tables!)
        try:
            tables = tabula.read_pdf(file_path, pages='all', multiple_tables=True, silent=True)
            if tables:
                extracted_text += "\n\n--- EXTRACTED TABLES ---\n"
                for i, table in enumerate(tables):
                    extracted_text += f"\nTable {i+1}:\n{table.to_markdown(index=False)}\n\n"
        except Exception:
            pass # Skip tables if none found

        # 3. Final Safety Check
        final_text = extracted_text.strip()
        if not final_text:
            return "NO_READABLE_TEXT_FOUND: This document appears to be an image-based scan, and OCR extraction failed."
            
        return final_text
        
    except Exception as e:
        raise RuntimeError(f"Failed to process PDF: {str(e)}")