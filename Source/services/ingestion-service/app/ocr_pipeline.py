from pathlib import Path
from typing import List
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

# Placeholder for Typhoon OCR integration
def typhoon_ocr_image(image: Image.Image) -> str:
    # TODO: integrate Typhoon OCR API
    return ""


def ocr_pdf(pdf_path: str, use_typhoon: bool = False, dpi: int = 200) -> str:
    pages = convert_from_path(pdf_path, dpi=dpi)
    texts: List[str] = []
    for img in pages:
        if use_typhoon:
            t_text = typhoon_ocr_image(img)
            if t_text.strip():
                texts.append(t_text)
                continue
        text = pytesseract.image_to_string(img)
        texts.append(text)
    return "\n".join(texts)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr_pipeline.py <pdf_path>")
    else:
        print(ocr_pdf(sys.argv[1])[:1000])
