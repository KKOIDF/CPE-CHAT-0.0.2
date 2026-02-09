import os
from pathlib import Path

load_dotenv = None  # type: ignore
try:
	from dotenv import load_dotenv as _load_dotenv  # type: ignore
	load_dotenv = _load_dotenv
except Exception:
	try:
		from dotenv.main import load_dotenv as _load_dotenv  # type: ignore
		load_dotenv = _load_dotenv
	except Exception:
		load_dotenv = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent.parent

# Repo root (..../CPE-CHAT-0.0.2)
ROOT_DIR = BASE_DIR.parent.parent

# Load repo-level .env if available (best-effort)
if load_dotenv:
	try:
		load_dotenv(ROOT_DIR / '.env', override=False)
	except Exception:
		pass

# Legacy data dir (ingestion-service default). Still useful for tooling/scripts.
DATA_DIR = Path(os.getenv('DATA_DIR', str(ROOT_DIR / 'services' / 'ingestion-service' / 'data')))

_KNOWN_DOMAINS = {'announcements', 'regulations', 'curriculum'}

# Public, stable ordering for "query all domains" behavior.
KNOWN_DOMAINS = ('announcements', 'regulations', 'curriculum')

def domain_paths(domain: str | None):
	"""Return (chroma_dir, sqlite_path) for a domain.

	- If domain is one of announcements/regulations/curriculum: use repo-level indexes/
	- Otherwise: fall back to legacy DATA_DIR (default points to ingestion-service/data)
	"""
	dom = (domain or '').strip().lower()
	if dom in _KNOWN_DOMAINS:
		index_root = Path(os.getenv('CPE_INDEX_ROOT', str(ROOT_DIR / 'indexes')))
		chroma_dir = index_root / dom / 'vector' / 'chroma'
		sqlite_path = index_root / dom / 'vector' / 'sqlite' / 'ingestion.db'
		return chroma_dir, sqlite_path

	return DATA_DIR / 'chroma', DATA_DIR / 'db' / 'ingestion.db'


# Backward-compatible defaults (no explicit domain)
CHROMA_DIR, SQLITE_PATH = domain_paths(os.getenv('CPE_DOMAIN'))

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
EMBED_BATCH = int(os.getenv('EMBED_BATCH', '32'))
TOKEN_BUDGET = int(os.getenv('TOKEN_BUDGET', '1200'))
RRF_K = int(os.getenv('RRF_K', '60'))
MAX_CONTEXTS = int(os.getenv('MAX_CONTEXTS', '8'))

# LLM settings (default switched to lighter 7B for 6GB GPUs)
LLM_MODEL = os.getenv('LLM_MODEL', 'Qwen/Qwen2.5-7B-Instruct')
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '384'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.4'))
LLM_ENABLE = os.getenv('LLM_ENABLE', '0') in ('1', 'true', 'True')
LLM_4BIT = os.getenv('LLM_4BIT', '1') in ('1','true','True')
LLM_PIPELINE = os.getenv('LLM_PIPELINE', '0') in ('1','true','True')
LLM_CPU_FALLBACK = os.getenv('LLM_CPU_FALLBACK', '1') in ('1','true','True')  # attempt CPU/offload if GPU OOM
LLM_DEVICE_MAP = os.getenv('LLM_DEVICE_MAP', 'auto')  # override accelerate device_map

# Remote LLM (OpenAI) settings (optional)
LLM_PROVIDER = os.getenv('LLM_PROVIDER', '').strip().lower()  # '', 'hf', 'openai', 'typhoon'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
OPENAI_TIMEOUT_S = float(os.getenv('OPENAI_TIMEOUT_S', '60'))

# Typhoon API settings (optional)
TYPHOON_API_KEY = os.getenv('TYPHOON_API_KEY', '')
TYPHOON_BASE_URL = os.getenv('TYPHOON_BASE_URL', 'https://api.opentyphoon.ai/v1')
TYPHOON_TIMEOUT_S = float(os.getenv('TYPHOON_TIMEOUT_S', '60'))

