import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw_files'
TEXT_DIR = DATA_DIR / 'text'
DB_DIR = DATA_DIR / 'db'
CHROMA_DIR = DATA_DIR / 'chroma'
SQLITE_PATH = DB_DIR / 'ingestion.db'

# Environment overrides
OCR_LANG_DEFAULT = os.getenv('OCR_LANG', 'tha')  # "tha" or "tha+eng"
OCR_DPI = int(os.getenv('OCR_DPI', '450'))
MIN_QUALITY_SCORE = float(os.getenv('MIN_QUALITY_SCORE', '0.2'))
MIN_LENGTH = int(os.getenv('MIN_LENGTH', '50'))
CHUNK_MIN_TOKENS = int(os.getenv('CHUNK_MIN_TOKENS', '400'))
CHUNK_MAX_TOKENS = int(os.getenv('CHUNK_MAX_TOKENS', '800'))
CHUNK_OVERLAP_RATIO = float(os.getenv('CHUNK_OVERLAP_RATIO', '0.12'))
CHAR_PER_TOKEN = float(os.getenv('CHAR_PER_TOKEN', '4.0'))

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
EMBED_BATCH = int(os.getenv('EMBED_BATCH', '32'))

POPPLER_PATH = os.getenv('POPPLER_PATH')  # For pdf2image on Windows
TESSERACT_PATH = os.getenv('TESSERACT_PATH')  # If not on PATH

# Typhoon / LLaMA embedding or external service placeholder
EMBEDDING_API_BASE = os.getenv('EMBEDDING_API_BASE')
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY')

# Typhoon OCR settings
TY_OCR_BASE = os.getenv('TY_OCR_BASE')  # e.g. http://typhoon-ocr:8080
TY_OCR_API_KEY = os.getenv('TY_OCR_API_KEY')
TY_OCR_MODEL = os.getenv('TY_OCR_MODEL', 'typhoon-ocr')
TY_OCR_ENABLE = os.getenv('TY_OCR_ENABLE', '0') in ('1','true','True')

for d in [RAW_DIR, TEXT_DIR, DB_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)
