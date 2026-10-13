from pathlib import Path
from typing import Any
import pdfplumber
import pytesseract
from docx import Document
from pdf2image import convert_from_path
from PIL import Image


def extract_pdf(file_path:Path) -> tuple[str,str]:
    """Extract embedded pdf text, use OCR if text is insufficient"""
    with pdfplumber.open(file_path) as pdf:
        pages = pdf.pages
        page_texts = [(page.extract_text() or "") for page in pages]

    extracted_text = "\n\n".join(page_texts).strip()

    #OCR fallback. Scanned pdf may still have digitally embedded text. it may not be completely empty

    #if len(extracted_text) < 50:
    if not extracted_text.strip():
        images = convert_from_path(str(file_path))

        # Should me modified.
        ocr_pages = [pytesseract.image_to_string(image,lang= "eng") for image in images]

        extracted_text = "\n\n".join(ocr_pages).strip()
        method = "pdf_ocr"

    else:
        method = "pdfplumber"

    # print(extracted_text)
    # print(method) 
    return extracted_text,method

def extract_docx(file_path: Path) -> tuple[str,str]:
    """Extract paragraphs and tables from a word document"""

    document = Document(str(file_path))
    parts = []

    for para in document.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            parts.append("|".join(cells))
    
    method = "python-docx"
    extracted_text = "\n".join(parts).strip()

    # print(extracted_text,method)
    return extracted_text,method


def extract_image(file_path:Path) -> tuple[str,str]:
    """Extract text from PNG/JPG using Tesseract OCR"""

    with Image.open(file_path) as image:
        extracted_text = pytesseract.image_to_string(image,lang= "eng").strip()

    method ="Tesseract_OCR"

    print(extracted_text,method)
    return extracted_text,method


# Function that routes the file based in file type 
def extract_invoice_info(file_path:str|Path, file_type : str|None = None )-> dict[str,Any]:
    """Route one invoice to its appropriate extraction function."""
    path = Path(file_path).resolve()
    extension = (file_type or path.suffix).lower()

    # print(path)
    # print(extension)

    if not path.is_file():
        print("provided path is Not a file")
        return {
            "file_name":path.name,
            "file_path":str(path),
            "file_type":extension,
            "raw_extracted_text":None,
            "extrcated_method":None,
            "status":"failed",
            "error":f"File not found:{path}"
        }

    try:
        if extension ==".pdf":
            # print("calling extract_pdf")
            extracted_text,method =extract_pdf(path)
            # print("called extract_pdf")
        elif extension ==".docx":
            extracted_text,method =extract_pdf(path)
        if extension in {".png",".png",".jpeg"}:
            extracted_text,method =extract_pdf(path)
        else:
            raise ValueError(f"Unsupported file type:{extension}")
        status = "success" if extracted_text else "empty"

        return {
            "file_name":path.name,
            "file_path":str(path),
            "file_type":extension,
            "raw_extracted_text":extracted_text,
            "extrcated_method":method,
            "status": status,
            "error":None if extracted_text else "No text was extracted"
        }

    except Exception as ex:
        return {
            "file_name":path.name,
            "file_path":str(path),
            "file_type":extension,
            "raw_extracted_text":None,
            "extrcated_method":None,
            "status":"failed",
            "error":f"{type(ex).__name__}:{ex}"
        }

# extract_invoice_info("data/incoming/INV_EN_001.pdf",".pdf")

