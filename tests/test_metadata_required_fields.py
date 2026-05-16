import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_ROOT = REPO_ROOT / "services" / "ingestion-service"
if str(INGEST_ROOT) not in sys.path:
    sys.path.insert(0, str(INGEST_ROOT))

from app.open_notebook_chunking import ChunkingConfig, build_chunks_from_records  # noqa: E402


def test_metadata_required_fields_present():
    cfg = ChunkingConfig(
        corpus_id="cpe_chat",
        domain="regulations",
        embedding_provider="test",
        embedding_model="test-model",
    )
    records = [{"source": "rules.txt", "page_no": 2, "text": "ข้อ 5 นักศึกษาต้องมีคุณสมบัติตามข้อบังคับ"}]
    chunks, _ = build_chunks_from_records(records, "rules.txt", cfg)
    assert chunks
    required = {
        "corpus_id",
        "source_id",
        "domain",
        "source_name",
        "chunk_id",
        "stable_chunk_id",
        "chunk_index",
        "content_type",
    }
    for chunk in chunks:
        assert required.issubset(chunk.keys())

