import os
from pathlib import Path

# Attempt to load .env automatically if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

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
TY_OCR_TIMEOUT = int(os.getenv('TY_OCR_TIMEOUT', '60'))  # per request timeout seconds
TY_OCR_RETRIES = int(os.getenv('TY_OCR_RETRIES', '3'))   # number of retry attempts on transient errors
TY_OCR_RETRY_BACKOFF = float(os.getenv('TY_OCR_RETRY_BACKOFF', '2'))  # base seconds for exponential backoff
TY_OCR_BATCH_SIZE = int(os.getenv('TY_OCR_BATCH_SIZE', '5'))  # max pages per Typhoon OCR API request
TY_OCR_MAX_TIMEOUTS = int(os.getenv('TY_OCR_MAX_TIMEOUTS', '2'))  # disable Typhoon OCR after this many timeouts in a process

# OCR engine selection: 'auto' (fallback logic), 'poppler', 'tesseract', 'typhoon'
OCR_ENGINE = os.getenv('OCR_ENGINE', 'auto').lower()

# MuPDF-only fast path (skip all OCR fallback if set)
MUPDF_ONLY = os.getenv('MUPDF_ONLY', '0').lower() in ('1','true','yes')

# Whether to embed flagged (low-quality) chunks
EMBED_FLAGGED = os.getenv('EMBED_FLAGGED', 'false').lower() in ('1','true','yes')

for d in [RAW_DIR, TEXT_DIR, DB_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)
