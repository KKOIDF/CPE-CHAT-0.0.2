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


def _domain_env_key(key: str) -> str:
    if DOMAIN:
        dom_prefix = f"{DOMAIN.upper()}_"
        if key.upper().startswith(dom_prefix):
            return key
        return f"{dom_prefix}{key}"
    return key


def _get_env(key: str, default: str) -> str:
    """Return domain override if set, else global, else default."""
    v = os.getenv(_domain_env_key(key))
    if v is None or str(v).strip() == '':
        v = os.getenv(key)
    if v is None or str(v).strip() == '':
        v = default
    return str(v)


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get_env(key, str(default)))
    except Exception:
        return int(default)


def _get_float(key: str, default: float) -> float:
    try:
        return float(_get_env(key, str(default)))
    except Exception:
        return float(default)


def _get_str(key: str, default: str) -> str:
    return _get_env(key, default)


# Chunking settings (domain-aware)
_DEFAULT_CHUNK_MIN = 400
_DEFAULT_CHUNK_MAX = 800
_DEFAULT_CHUNK_OVERLAP = 0.12
if DOMAIN == 'announcements':
    # Announcements are clause/schedule driven; smaller chunks work better.
    # NOTE: Keep min low enough that heading boundaries can flush chunks
    # in sentence/structure strategies (common OCR output yields many mid-size chunks).
    _DEFAULT_CHUNK_MIN = 150
    _DEFAULT_CHUNK_MAX = 450
    _DEFAULT_CHUNK_OVERLAP = 0.12
elif DOMAIN == 'regulations':
    # Regulations: clause/subclause oriented; keep overlap low.
    # NOTE: Lower min so heading boundaries can flush chunks in edge cases (e.g., COVID/calendar sections).
    _DEFAULT_CHUNK_MIN = 120
    _DEFAULT_CHUNK_MAX = 450
    _DEFAULT_CHUNK_OVERLAP = 0.08

CHUNK_MIN_TOKENS = _get_int('CHUNK_MIN_TOKENS', _DEFAULT_CHUNK_MIN)
CHUNK_MAX_TOKENS = _get_int('CHUNK_MAX_TOKENS', _DEFAULT_CHUNK_MAX)
CHUNK_OVERLAP_RATIO = _get_float('CHUNK_OVERLAP_RATIO', _DEFAULT_CHUNK_OVERLAP)
CHAR_PER_TOKEN = _get_float('CHAR_PER_TOKEN', 4.0)

# Chunking strategy (domain-aware)
# - 'structure' (default): paragraph+heading aware
# - 'sentence_window': pack Thai sentence segments into a token window
# - 'announcement_template': clause/table/calendar/memo template chunking
# - 'curriculum_course': course-centric chunking for curriculum domain
if DOMAIN == 'curriculum':
    _DEFAULT_CHUNK_STRATEGY = 'curriculum_course'
elif DOMAIN == 'announcements':
    _DEFAULT_CHUNK_STRATEGY = 'announcement_template'
elif DOMAIN == 'regulations':
    _DEFAULT_CHUNK_STRATEGY = 'regulation_template'
else:
    _DEFAULT_CHUNK_STRATEGY = 'structure'
CHUNK_STRATEGY = _get_str('CHUNK_STRATEGY', _DEFAULT_CHUNK_STRATEGY).strip().lower()

# Curriculum-specific metadata defaults (domain-aware)
CURRICULUM_PROGRAM = _get_str('CURRICULUM_PROGRAM', 'B.Eng. Computer Engineering')

EMBEDDING_MODEL = _get_str('EMBEDDING_MODEL', 'BAAI/bge-m3')
EMBED_BATCH = _get_int('EMBED_BATCH', 32)

# Target embedding dimension stored in vector DBs (Chroma/Neo4j).
# NOTE: Some models (e.g., BGE-M3) output 1024 dims; we may project/trim to this size.
EMBEDDING_DIM = _get_int('EMBEDDING_DIM', 512)

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
