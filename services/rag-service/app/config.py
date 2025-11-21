import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv('DATA_DIR', BASE_DIR.parent.parent / 'services' / 'ingestion-service' / 'data'))
CHROMA_DIR = DATA_DIR / 'chroma'
SQLITE_PATH = DATA_DIR / 'db' / 'ingestion.db'

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
EMBED_BATCH = int(os.getenv('EMBED_BATCH', '32'))
TOKEN_BUDGET = int(os.getenv('TOKEN_BUDGET', '1200'))
RRF_K = int(os.getenv('RRF_K', '60'))
MAX_CONTEXTS = int(os.getenv('MAX_CONTEXTS', '8'))

