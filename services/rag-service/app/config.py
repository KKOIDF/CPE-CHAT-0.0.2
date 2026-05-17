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


def _find_repo_root(start_dir: Path) -> Path:
	"""Best-effort locate the project root.

	Prefer the root that contains the real global Open Notebook index.
	In this repo, services/rag-service may also contain an indexes/ folder,
	but it can be incomplete, so do not stop there too early.
	"""
	for p in (start_dir, *start_dir.parents):
		try:
			if (p / 'indexes' / 'global' / 'sqlite' / 'ingestion.db').exists():
				return p
		except Exception:
			continue

	for p in (start_dir, *start_dir.parents):
		try:
			if (p / '.env').exists() and (p / 'indexes').exists():
				return p
		except Exception:
			continue

	for p in (start_dir, *start_dir.parents):
		try:
			if (p / 'docker-compose.yml').exists():
				return p
		except Exception:
			continue

	for p in (start_dir, *start_dir.parents):
		try:
			if (p / 'indexes').exists():
				return p
		except Exception:
			continue
	return start_dir


# Repo root (best-effort; used to locate `indexes/` and optional `.env`)
ROOT_DIR = _find_repo_root(BASE_DIR)

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
RAG_ENGINE = (os.getenv('RAG_ENGINE', 'open_notebook_style') or 'open_notebook_style').strip().lower()
RAG_VECTOR_BACKEND = (os.getenv('RAG_VECTOR_BACKEND', 'chroma') or 'chroma').strip().lower()
RAG_CORPUS_ID = (os.getenv('RAG_CORPUS_ID', 'cpe_chat') or 'cpe_chat').strip()
RAG_CHROMA_COLLECTION = (os.getenv('RAG_CHROMA_COLLECTION', 'cpe_chat_sources') or 'cpe_chat_sources').strip()
RAG_CHROMA_DIR = Path(os.getenv('RAG_CHROMA_DIR', str(ROOT_DIR / 'indexes' / 'global' / 'chroma')))
RAG_GLOBAL_SQLITE_PATH = Path(os.getenv('RAG_GLOBAL_SQLITE_PATH', str(ROOT_DIR / 'indexes' / 'global' / 'sqlite' / 'ingestion.db')))
RAG_LEGACY_DOMAIN_INDEX_COMPAT = os.getenv('RAG_LEGACY_DOMAIN_INDEX_COMPAT', '1') in ('1', 'true', 'True')

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3')
EMBED_BATCH = int(os.getenv('EMBED_BATCH', '32'))


def _resolve_embedding_dim() -> int:
	raw_value = os.getenv('EMBEDDING_DIM', '').strip()
	if 'bge-m3' in (EMBEDDING_MODEL or '').lower():
		if raw_value and raw_value != '1024':
			print(f"[RAG] Overriding EMBEDDING_DIM={raw_value} to 1024 for {EMBEDDING_MODEL}.")
		return 1024
	try:
		return int(raw_value or '512')
	except Exception:
		return 512


EMBEDDING_DIM = _resolve_embedding_dim()
TOKEN_BUDGET = int(os.getenv('TOKEN_BUDGET', '2400'))
RRF_K = int(os.getenv('RRF_K', '60'))
MAX_CONTEXTS = int(os.getenv('MAX_CONTEXTS', '6'))
RAG_RESPONSE_PROFILE = (os.getenv('RAG_RESPONSE_PROFILE', 'balanced') or 'balanced').strip().lower()
if RAG_RESPONSE_PROFILE not in ('fast', 'balanced', 'quality'):
	RAG_RESPONSE_PROFILE = 'balanced'
RAG_FAST_MAX_CONTEXTS = max(2, int(os.getenv('RAG_FAST_MAX_CONTEXTS', '6') or '6'))

# LLM settings (default switched to lighter 7B for 6GB GPUs)
LLM_MODEL = os.getenv('LLM_MODEL', 'Qwen/Qwen2.5-7B-Instruct')
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '384'))
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.4'))
LLM_ENABLE = os.getenv('LLM_ENABLE', '0') in ('1', 'true', 'True')
LLM_4BIT = os.getenv('LLM_4BIT', '1') in ('1','true','True')
LLM_PIPELINE = os.getenv('LLM_PIPELINE', '0') in ('1','true','True')
LLM_CPU_FALLBACK = os.getenv('LLM_CPU_FALLBACK', '1') in ('1','true','True')  # attempt CPU/offload if GPU OOM
LLM_DEVICE_MAP = os.getenv('LLM_DEVICE_MAP', 'auto')  # override accelerate device_map

# Remote LLM settings (optional)
LLM_PROVIDER = os.getenv('LLM_PROVIDER', '').strip().lower()  # '', 'hf', 'openai', 'typhoon', 'ollama'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
OPENAI_TIMEOUT_S = float(os.getenv('OPENAI_TIMEOUT_S', '60'))

# Optional secondary/auxiliary model. Intended for lightweight sub-tasks
# such as rewrite/routing/multi-query while the primary model focuses on final answers.
LLM_AUX_PROVIDER = os.getenv('LLM_AUX_PROVIDER', '').strip().lower()
LLM_AUX_MODEL = os.getenv('LLM_AUX_MODEL', '').strip()
LLM_AUX_FOR_REWRITE = os.getenv('LLM_AUX_FOR_REWRITE', '1') in ('1', 'true', 'True')
LLM_AUX_FOR_MULTIQUERY = os.getenv('LLM_AUX_FOR_MULTIQUERY', '1') in ('1', 'true', 'True')
LLM_AUX_FOR_ROUTING = os.getenv('LLM_AUX_FOR_ROUTING', '1') in ('1', 'true', 'True')
LLM_AUX_FALLBACK_FOR_ANSWER = os.getenv('LLM_AUX_FALLBACK_FOR_ANSWER', '1') in ('1', 'true', 'True')

# Typhoon API settings (optional)
TYPHOON_API_KEY = os.getenv('TYPHOON_API_KEY', '')
TYPHOON_BASE_URL = os.getenv('TYPHOON_BASE_URL', 'https://api.opentyphoon.ai/v1')
TYPHOON_TIMEOUT_S = float(os.getenv('TYPHOON_TIMEOUT_S', '60'))

# Ollama API settings (optional)
OLLAMA_API_KEY = os.getenv('OLLAMA_API_KEY', '')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_TIMEOUT_S = float(os.getenv('OLLAMA_TIMEOUT_S', '120'))
OLLAMA_THINK = os.getenv('OLLAMA_THINK', '0') in ('1', 'true', 'True')
OLLAMA_KEEP_ALIVE = (os.getenv('OLLAMA_KEEP_ALIVE', '30m') or '30m').strip()
