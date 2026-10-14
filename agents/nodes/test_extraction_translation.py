from translation import translate_invoice_info
from Extractor import extract_invoice_info

file_path = "/home/labuser/Desktop/aug26-sp1-l1-fa3-proj-group-38/data/incoming/INV_EN_002.pdf"
file_type = ".pdf"

extraction_result = extract_invoice_info(file_path,file_type)
print("exctraction result:\n",extraction_result)

translation_result = translate_invoice_info(extraction_result)

print("translation result:\n",translation_result)
