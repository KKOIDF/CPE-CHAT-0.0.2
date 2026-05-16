from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import chromadb
from chromadb.config import Settings


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.config import RAG_CHROMA_COLLECTION, RAG_CHROMA_DIR  # noqa: E402


def main() -> int:
    chroma_dir = Path(RAG_CHROMA_DIR).resolve()
    client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=RAG_CHROMA_COLLECTION)
    total = collection.count()
    sample_n = min(total, 200)
    payload = collection.get(include=['metadatas'], limit=sample_n) if sample_n else {'ids': [], 'metadatas': []}
    ids = payload.get('ids') or []
    metas = payload.get('metadatas') or []
    by_domain = Counter(str((meta or {}).get('domain') or 'unknown') for meta in metas)
    by_source = Counter(str((meta or {}).get('source_name') or (meta or {}).get('source') or 'unknown') for meta in metas)
    print(f"resolved_chroma_dir: {chroma_dir}")
    print(f"collection_name: {collection.name}")
    print(f"total_chunks: {total}")
    print('chunks_by_domain:')
    for domain, count in by_domain.most_common():
        print(f"  - {domain}: {count}")
    print('chunks_by_source:')
    for source, count in by_source.most_common(15):
        print(f"  - {source}: {count}")
    print(f"sample_ids: {ids[:10]}")
    sample = metas[0] if metas else {}
    print('sample_metadata:')
    for key in sorted(sample.keys()):
        print(f"  - {key}: {sample.get(key)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
