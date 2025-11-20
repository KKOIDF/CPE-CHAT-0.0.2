from pathlib import Path
from typing import Tuple
from pdfminer.high_level import extract_text
from .ocr_pipeline import ocr_pdf
import re

TEXT_RATIO_THRESHOLD = 0.2  # heuristic: if extracted text length / file size < threshold -> OCR


def extract_pdf_text(path: str) -> Tuple[str, bool]:
    """Return (text, used_ocr)."""
    file_path = Path(path)
    raw_text = extract_text(str(file_path))
    text_clean = _clean_text(raw_text)
    # Heuristic: if too little text characters compared to size, fallback to OCR
    size = file_path.stat().st_size or 1
    ratio = len(text_clean) / size
    if ratio < TEXT_RATIO_THRESHOLD:
        ocr_text = ocr_pdf(str(file_path))
        ocr_text = _clean_text(ocr_text)
        if len(ocr_text) > len(text_clean):
            return ocr_text, True
    return text_clean, False


def _clean_text(text: str) -> str:
    # Basic cleanup: collapse whitespace, remove control chars
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[\t\f]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    # Trim trailing spaces per line
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <pdf_path>")
    else:
        t, o = extract_pdf_text(sys.argv[1])
        print(f"Used OCR: {o}")
        print(t[:1000])
