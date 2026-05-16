import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / "services" / "rag-service"
for key in list(sys.modules):
    if key == "app" or key.startswith("app."):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.open_notebook_rag import rerank_results, rrf_merge  # noqa: E402


def test_hybrid_merge_and_dedupe():
    vector = [
        {"stable_chunk_id": "a", "text": "หลักสูตรต้องเรียนครบ 120 หน่วยกิต", "domain": "curriculum", "vector_score": 0.9},
        {"stable_chunk_id": "b", "text": "ต้องมีคุณสมบัติตามข้อบังคับ", "domain": "regulations", "vector_score": 0.7},
    ]
    keyword = [
        {"stable_chunk_id": "a", "text": "หลักสูตรต้องเรียนครบ 120 หน่วยกิต", "domain": "curriculum", "keyword_score": 1.0},
        {"stable_chunk_id": "c", "text": "ประกาศล่าสุดเปลี่ยนกำหนดการ", "domain": "announcements", "keyword_score": 0.8},
    ]
    merged = rrf_merge([vector, keyword])
    assert len(merged) == 3
    ranked = rerank_results(merged, "จบหลักสูตรต้องมีหน่วยกิตอะไรบ้าง")
    assert ranked[0]["stable_chunk_id"] == "a"
