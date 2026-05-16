from __future__ import annotations

from pathlib import Path
import sqlite3
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.config import RAG_CHROMA_COLLECTION, RAG_CHROMA_DIR, RAG_GLOBAL_SQLITE_PATH  # noqa: E402
from app.onb_rag.engine import answer_with_context, retrieve_context  # noqa: E402
import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402


def main() -> int:
    sqlite_path = Path(RAG_GLOBAL_SQLITE_PATH).resolve()
    conn = sqlite3.connect(str(sqlite_path))
    sqlite_count = conn.execute('SELECT COUNT(*) FROM rag_chunks').fetchone()[0]
    conn.close()

    client = chromadb.PersistentClient(path=str(Path(RAG_CHROMA_DIR).resolve()), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=RAG_CHROMA_COLLECTION)
    chroma_count = collection.count()

    query = 'จบหลักสูตรต้องผ่านอะไรบ้าง มีประกาศอะไรเกี่ยวไหม'
    payload = retrieve_context(query)
    forced_answer = answer_with_context('จบหลักสูตรต้องผ่านอะไรบ้าง', '[Source 1]\nsource_name: test.pdf\ndomain: test_domain\ncontent:\nนักศึกษาต้องเรียนครบ 120 หน่วยกิตจึงจะสำเร็จการศึกษา')

    print(f'sqlite_count: {sqlite_count}')
    print(f'chroma_count: {chroma_count}')
    print(f"vector_candidates: {len(payload.get('vector_candidates') or [])}")
    print(f"keyword_candidates: {len(payload.get('keyword_candidates') or [])}")
    print(f"selected_chunks: {len(payload.get('selected_chunks') or [])}")
    print(f"sources_used: {payload.get('sources_used') or []}")
    print('context_preview:')
    print(str(payload.get('formatted_context') or '')[:2000])
    print('forced_context_answer:')
    print(forced_answer)
    print('no_context_fallback: ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
