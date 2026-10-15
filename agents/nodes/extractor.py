from pathlib import Path
import pdfplumber
import pytesseract
from docx import Document
from pdf2image import convert_from_path
from PIL import Image
from agents.state import InvoiceState








# 1. Extract text from PDF
def extract_pdf(state: InvoiceState) -> dict:
   file_path = Path(state["file_path"])




   with pdfplumber.open(file_path) as pdf:
       text = "\n\n".join(
           page.extract_text() or "" for page in pdf.pages
       ).strip()




   method = "pdfplumber"




   # Use OCR if embedded text is insufficient
   if len(text) < 50:
       images = convert_from_path(str(file_path))




       ocr_text = "\n\n".join(
           pytesseract.image_to_string(image, lang="eng")
           for image in images
       ).strip()




       if len(ocr_text) > len(text):
           text = ocr_text
           method = "tesseract"
   print("DEBUGGINGG extracted text"+repr(text))




   return {
       "raw_extracted_text": text,
       "extraction_method": method,
       "current_stage": "extraction_completed",
   }








# 2. Extract text from DOCX
def extract_docx(state: InvoiceState) -> dict:
   file_path = Path(state["file_path"])
   document = Document(str(file_path))




   parts = [
       paragraph.text.strip()
       for paragraph in document.paragraphs
       if paragraph.text.strip()
   ]




   for table in document.tables:
       for row in table.rows:
           parts.append(
               " | ".join(cell.text.strip() for cell in row.cells)
           )
   print("DEBUGGINGG extracted text"+repr("\n".join(parts).strip()))
   return {
       "raw_extracted_text": "\n".join(parts).strip(),
       "extraction_method": "docx",
       "current_stage": "extraction_completed",
   }








# 3. Extract text from images
def extract_image(state: InvoiceState) -> dict:
   file_path = Path(state["file_path"])




   with Image.open(file_path) as image:
       text = pytesseract.image_to_string(
           image, lang="eng"
       ).strip()
   print("DEBUGGINGG extracted text"+text)
   return {
       "raw_extracted_text": text,
       "extraction_method": "tesseract",
       "current_stage": "extraction_completed",
   }








# 4. Route invoice to the correct extraction node
def extract_invoice_info(state: InvoiceState) -> dict:
   file_path = state.get("file_path")




   if not file_path:
       raise ValueError("file_path is missing from InvoiceState")




   path = Path(file_path).expanduser().resolve()




   if not path.is_file():
       raise FileNotFoundError(f"Invoice file not found: {path}")




   extension = path.suffix.lower()




   if extension not in {
       ".pdf", ".docx", ".png", ".jpg", ".jpeg"
   }:
       raise ValueError(f"Unsupported file type: {extension}")




   return {
       "file_path": str(path),
       "file_type": extension,
   }
