import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_ROOT = REPO_ROOT / "services" / "ingestion-service"
if str(INGEST_ROOT) not in sys.path:
    sys.path.insert(0, str(INGEST_ROOT))

from app.open_notebook_chunking import ChunkingConfig, build_chunks_from_records  # noqa: E402


def _cfg() -> ChunkingConfig:
    return ChunkingConfig(
        corpus_id="cpe_chat",
        domain="curriculum",
        embedding_provider="test",
        embedding_model="test-model",
        chunk_size=120,
        chunk_overlap=20,
        min_tokens=10,
        max_tokens=80,
        char_fallback_size=320,
        char_fallback_overlap=40,
    )


def test_markdown_with_headings_preserves_heading_metadata():
    records = [{
        "source": "sample.md",
        "page_no": 1,
        "text": "# หลักสูตร\nเนื้อหาส่วนแรก\n## เงื่อนไขการสำเร็จการศึกษา\nต้องเรียนครบ 120 หน่วยกิต",
    }]
    chunks, report = build_chunks_from_records(records, "sample.md", _cfg())
    assert chunks
    assert all(chunk["text"].strip() for chunk in chunks)
    assert any(chunk.get("section_heading") for chunk in chunks)
    assert report["chunk_count"] == len(chunks)


def test_thai_plain_text_secondary_split_for_long_text():
    long_text = "\n".join([f"ข้อ {i} นักศึกษาต้องผ่านเงื่อนไขที่กำหนดและเรียนครบตามแผนการศึกษา" for i in range(1, 40)])
    records = [{"source": "curriculum.txt", "page_no": 1, "text": long_text}]
    chunks, report = build_chunks_from_records(records, "curriculum.txt", _cfg())
    assert len(chunks) > 1
    assert all(chunk["token_count"] > 0 for chunk in chunks)
    assert report["oversized_chunks"] >= 1


def test_table_like_text_keeps_non_empty_chunks():
    records = [{
        "source": "table.csv",
        "page_no": 1,
        "text": "รหัสวิชา,ชื่อวิชา,หน่วยกิต\nCPE 101,Programming,3\nCPE 102,Data Structures,3",
    }]
    chunks, report = build_chunks_from_records(records, "table.csv", _cfg())
    assert chunks
    assert report["content_type"] == "table_like"
    assert all(chunk["text"].strip() for chunk in chunks)

