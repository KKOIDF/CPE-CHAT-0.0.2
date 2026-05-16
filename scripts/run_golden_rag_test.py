from __future__ import annotations

import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / 'data' / 'raw' / 'test_domain'
GOLDEN_FILE = GOLDEN_DIR / 'graduation_test.txt'
GOLDEN_TEXT = 'หลักสูตรทดสอบกำหนดให้นักศึกษาต้องเรียนครบ 120 หน่วยกิต ผ่านรายวิชาบังคับทั้งหมด และยื่นเอกสารสำเร็จการศึกษาตามประกาศล่าสุด\n'
QUESTION = 'จบหลักสูตรต้องผ่านอะไรบ้าง'


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_FILE.write_text(GOLDEN_TEXT, encoding='utf-8')

    os.environ['CPE_DOMAIN'] = 'test_domain'
    os.environ['RAG_ENGINE'] = 'open_notebook_style'
    os.environ['CPE_USE_SERVICE_DATA'] = '1'
    os.environ['EMBEDDING_MODEL'] = 'BAAI/bge-m3'
    os.environ['EMBEDDING_DIM'] = '1024'
    os.environ['THAI_TOKENIZER_PROVIDER'] = 'pythainlp'
    os.environ['THAI_TOKENIZER_ENGINE'] = 'newmm'

    ingest_root = REPO_ROOT / 'services' / 'ingestion-service'
    rag_root = REPO_ROOT / 'services' / 'rag-service'
    if str(ingest_root) not in sys.path:
        sys.path.insert(0, str(ingest_root))

    from app.open_notebook_chunking import ChunkingConfig, build_chunks_from_records  # type: ignore  # noqa: E402
    from app.db import init_db, insert_chunks  # type: ignore  # noqa: E402
    from app.chroma_client import upsert_chunks  # type: ignore  # noqa: E402

    cfg = ChunkingConfig(
        corpus_id='cpe_chat',
        domain='test_domain',
        embedding_provider='local',
        embedding_model='BAAI/bge-m3',
        chunk_size=400,
        chunk_overlap=60,
        min_tokens=40,
        max_tokens=650,
        char_fallback_size=1200,
        char_fallback_overlap=180,
    )
    records = [{'source': str(GOLDEN_FILE), 'page_no': 1, 'text': GOLDEN_TEXT}]
    chunks, report = build_chunks_from_records(records, str(GOLDEN_FILE), cfg)
    if not chunks:
        raise SystemExit('golden test failed: chunking produced no chunks')
    init_db()
    insert_chunks(chunks)
    upsert_chunks(chunks)

    if str(ingest_root) in sys.path:
        sys.path.remove(str(ingest_root))
    for key in list(sys.modules):
        if key == 'app' or key.startswith('app.'):
            sys.modules.pop(key, None)
    sys.path.insert(0, str(rag_root))

    from app.onb_rag.engine import answer_with_context, retrieve_context  # type: ignore  # noqa: E402
    from app.config import RAG_CHROMA_COLLECTION, RAG_CHROMA_DIR  # type: ignore  # noqa: E402
    import chromadb  # noqa: E402
    from chromadb.config import Settings  # noqa: E402

    payload = retrieve_context(QUESTION)
    if not payload.get('selected_chunks'):
        raise SystemExit('golden test failed: selected_chunks is empty')
    if not payload.get('formatted_context'):
        raise SystemExit('golden test failed: formatted_context is empty')
    if not payload.get('sources_used'):
        raise SystemExit('golden test failed: sources_used is empty')

    top_source = str((payload.get('selected_chunks') or [{}])[0].get('source_name') or (payload.get('selected_chunks') or [{}])[0].get('source') or '')
    if top_source != 'graduation_test.txt':
        raise SystemExit(f'golden test failed: expected top selected chunk from graduation_test.txt, got {top_source!r}')
    if 'graduation_test.txt' not in (payload.get('sources_used') or []):
        raise SystemExit('golden test failed: graduation_test.txt missing from sources_used')
    if len(payload.get('sources_used') or []) > 5:
        raise SystemExit(f"golden test failed: too many noisy sources in context: {payload.get('sources_used') or []}")

    answer = answer_with_context(QUESTION, str(payload.get('formatted_context') or ''), citation_map=payload.get('citation_map') or {})
    client = chromadb.PersistentClient(path=str(Path(RAG_CHROMA_DIR).resolve()), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=RAG_CHROMA_COLLECTION)

    print(f'golden_file: {GOLDEN_FILE}')
    print(f'chunk_report: {report}')
    print(f'chroma_count: {collection.count()}')
    print(f"vector_candidates: {len(payload.get('vector_candidates') or [])}")
    print(f"keyword_candidates: {len(payload.get('keyword_candidates') or [])}")
    print(f"selected_chunks: {len(payload.get('selected_chunks') or [])}")
    print(f"sources_used: {payload.get('sources_used') or []}")
    print('context:')
    print(payload.get('formatted_context') or '')
    print('answer:')
    print(answer)

    required = ['120', 'รายวิชาบังคับ', 'เอกสาร']
    for item in required:
        if item not in answer:
            raise SystemExit(f'golden test failed: expected {item!r} in answer')
    if '[' not in answer:
        raise SystemExit('golden test failed: expected citation in answer')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
