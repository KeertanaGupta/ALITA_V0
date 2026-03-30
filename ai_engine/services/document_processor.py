# ai_engine/services/document_processor.py
import fitz  # PyMuPDF
import os
import tabula
import pytesseract
from PIL import Image
import io
import re

# Point Python to your Windows Tesseract installation
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def clean_text(text: str) -> str:
    """
    Cleans OCR output by fixing broken spacing and artifacts.
    - Collapses multiple spaces/newlines into single space
    - Preserves paragraph breaks (double newline)
    - Removes stray special chars from OCR misreads
    """
    # Preserve paragraph breaks first
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Fix lines that got broken mid-sentence by OCR
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    # Remove zero-width and non-printable characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text using PyMuPDF.
    Scanned pages use Tesseract OCR at 300 DPI with PSM 6
    for accurate recognition of scientific symbols (°Cl, °Fr etc.)
    OCR output is cleaned before being added to extracted text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at path: {file_path}")

    extracted_text = ""

    try:
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text").strip()

            if len(page_text) < 50:
                # Scanned image page — use OCR at 300 DPI
                try:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_bytes))

                    # PSM 6 = uniform block of text, best for book pages
                    ocr_text = pytesseract.image_to_string(image, config="--psm 6")

                    # Clean OCR artifacts before storing
                    cleaned = clean_text(ocr_text)
                    extracted_text += f"\n\n--- OCR Extracted Page {page_num + 1} ---\n{cleaned}\n"

                except Exception as ocr_e:
                    print(f"OCR skipped on page {page_num + 1}: {ocr_e}")
            else:
                # Native text page — still clean it for consistency
                extracted_text += clean_text(page_text) + "\n\n"

        doc.close()

        # Extract tables using Tabula
        try:
            tables = tabula.read_pdf(file_path, pages='all', multiple_tables=True, silent=True)
            if tables:
                extracted_text += "\n\n--- EXTRACTED TABLES ---\n"
                for i, table in enumerate(tables):
                    extracted_text += f"\nTable {i+1}:\n{table.to_markdown(index=False)}\n\n"
        except Exception:
            pass

        final_text = extracted_text.strip()
        if not final_text:
            return "NO_READABLE_TEXT_FOUND: This document appears to be an image-based scan, and OCR extraction failed."

        return final_text

    except Exception as e:
        raise RuntimeError(f"Failed to process PDF: {str(e)}")