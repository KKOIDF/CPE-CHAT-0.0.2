import os
import sys
from pathlib import Path

# Make app/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import dotenv  # type: ignore

    print('python-dotenv ok', getattr(dotenv, '__version__', '?'))
except Exception as e:
    print('python-dotenv import failed:', e)

try:
    from dotenv import load_dotenv  # type: ignore

    print('load_dotenv import ok', load_dotenv)
    # scripts/ -> rag-service/ -> services/ -> repo root/
    env_path = Path(__file__).resolve().parents[3] / '.env'
    print('manual env_path', env_path)
    ok = load_dotenv(env_path, override=False)
    print('manual load result', ok)
    try:
        raw = env_path.read_text(encoding='utf-8', errors='replace')
        print('raw contains LLM_ENABLE=', 'LLM_ENABLE=' in raw)
        print('raw contains OPENAI_API_KEY=', 'OPENAI_API_KEY=' in raw)
    except Exception as e3:
        print('raw read failed:', e3)
    try:
        from dotenv import dotenv_values  # type: ignore

        vals = dotenv_values(env_path)
        print('dotenv_values keys', len(vals or {}))
        for k in ['LLM_ENABLE', 'LLM_PROVIDER', 'LLM_MODEL', 'OPENAI_API_KEY', 'NEO4J_URI']:
            v = vals.get(k) if vals else None
            print(f'dotenv_values[{k}] set', bool(v))
    except Exception as e2:
        print('dotenv_values failed:', e2)

    print('os.getenv after manual load LLM_ENABLE', os.getenv('LLM_ENABLE'))
    print('os.getenv after manual load LLM_PROVIDER', os.getenv('LLM_PROVIDER'))
    print('os.getenv after manual load LLM_MODEL', os.getenv('LLM_MODEL'))
    print('os.getenv after manual load OPENAI_API_KEY set', bool(os.getenv('OPENAI_API_KEY')))
except Exception as e:
    print('load_dotenv import/manual load failed:', e)

from app import config

print('repo_root', config.ROOT_DIR)
print('env_file_exists', (config.ROOT_DIR / '.env').exists())
print('LLM_ENABLE(config)', config.LLM_ENABLE)
print('LLM_PROVIDER(config)', config.LLM_PROVIDER)
print('LLM_MODEL(config)', config.LLM_MODEL)
print('OPENAI_KEY_SET(config)', bool(config.OPENAI_API_KEY))
print('os.getenv(LLM_ENABLE)', os.getenv('LLM_ENABLE'))
print('os.getenv(LLM_PROVIDER)', os.getenv('LLM_PROVIDER'))
print('os.getenv(LLM_MODEL)', os.getenv('LLM_MODEL'))
print('os.getenv(OPENAI_API_KEY)_set', bool(os.getenv('OPENAI_API_KEY')))
