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

# LLM settings
LLM_MODEL = os.getenv('LLM_MODEL', 'scb10x/typhoon2.5-qwen3-30b-a3b')
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '512'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.4'))
LLM_ENABLE = os.getenv('LLM_ENABLE', '0') in ('1', 'true', 'True')
LLM_4BIT = os.getenv('LLM_4BIT', '1') in ('1','true','True')

