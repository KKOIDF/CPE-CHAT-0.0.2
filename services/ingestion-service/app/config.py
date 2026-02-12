import os
from pathlib import Path

# Attempt to load .env automatically if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent.parent  # repo root (..../CPE-CHAT-0.0.2)

# Domain-aware storage
# - Set CPE_DOMAIN=announcements|regulations|curriculum to isolate indexes per domain
# - Default uses workspace data/ + indexes/ when available
CPE_DOMAIN = os.getenv('CPE_DOMAIN', '').strip().lower()
_KNOWN_DOMAINS = {'announcements', 'regulations', 'curriculum'}
DOMAIN = CPE_DOMAIN if CPE_DOMAIN in _KNOWN_DOMAINS else ''

SERVICE_DATA_DIR = BASE_DIR / 'data'
WORKSPACE_DATA_DIR = ROOT_DIR / 'data'

USE_SERVICE_DATA = os.getenv('CPE_USE_SERVICE_DATA', '').lower() in ('1', 'true', 'yes')
DATA_DIR = SERVICE_DATA_DIR if USE_SERVICE_DATA or not WORKSPACE_DATA_DIR.exists() else WORKSPACE_DATA_DIR

# Raw/text folders (used by some scripts; main CLI accepts --input anyway)
RAW_DIR = (DATA_DIR / DOMAIN) if DOMAIN else (DATA_DIR / 'raw_files')
TEXT_DIR = (DATA_DIR / 'text' / DOMAIN) if DOMAIN else (DATA_DIR / 'text')

# Vector index + SQLite are stored under repo-level indexes/ per domain
INDEX_ROOT = Path(os.getenv('CPE_INDEX_ROOT', str(ROOT_DIR / 'indexes')))
if DOMAIN:
    CHROMA_DIR = INDEX_ROOT / DOMAIN / 'vector' / 'chroma'
    DB_DIR = INDEX_ROOT / DOMAIN / 'vector' / 'sqlite'
    SQLITE_PATH = DB_DIR / 'ingestion.db'
    REVIEW_DIR = INDEX_ROOT / DOMAIN / 'vector' / 'review'
else:
    DB_DIR = DATA_DIR / 'db'
    CHROMA_DIR = DATA_DIR / 'chroma'
    SQLITE_PATH = DB_DIR / 'ingestion.db'
    REVIEW_DIR = DB_DIR / 'review'

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

# OCR engine selection: 'auto' (fallback logic), 'poppler', 'tesseract'
OCR_ENGINE = os.getenv('OCR_ENGINE', 'auto').lower()

# Thai NLP tokenizer settings
# Word tokenizer: 'newmm' (fast), 'attacut' (best accuracy), 'longest' (formal text), 'deepcut'
THAI_WORD_TOKENIZER = os.getenv('THAI_WORD_TOKENIZER', 'attacut').lower()
# Sentence tokenizer: 'crfcut' (best for Thai), 'tltk' (mixed Thai/English)
THAI_SENT_TOKENIZER = os.getenv('THAI_SENT_TOKENIZER', 'crfcut').lower()

# MuPDF-only fast path (skip all OCR fallback if set)
MUPDF_ONLY = os.getenv('MUPDF_ONLY', '0').lower() in ('1','true','yes')

# OCR post-processing (opt-in)
OCR_POSTPROCESS = os.getenv('OCR_POSTPROCESS', '0').lower() in ('1', 'true', 'yes')
OCR_MERGE_LINES = os.getenv('OCR_MERGE_LINES', '0').lower() in ('1', 'true', 'yes')
OCR_NORMALIZE_THAI_DIGITS = os.getenv('OCR_NORMALIZE_THAI_DIGITS', '0').lower() in ('1', 'true', 'yes')
OCR_SPELL_CORRECT_THAI = os.getenv('OCR_SPELL_CORRECT_THAI', '0').lower() in ('1', 'true', 'yes')

# Whether to embed flagged (low-quality) chunks
EMBED_FLAGGED = os.getenv('EMBED_FLAGGED', 'True').lower() in ('1','true','yes')

for d in [RAW_DIR, TEXT_DIR, DB_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

REVIEW_DIR.mkdir(parents=True, exist_ok=True)
