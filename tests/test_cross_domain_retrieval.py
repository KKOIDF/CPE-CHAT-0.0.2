import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / "services" / "rag-service"
for key in list(sys.modules):
    if key == "app" or key.startswith("app."):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

import app.retrieval as retrieval  # noqa: E402
from app.open_notebook_rag import build_source_labeled_context  # noqa: E402


def test_cross_domain_retrieval_selects_multiple_domains(monkeypatch):
    fake_rows = [
        {
            "stable_chunk_id": "curr-1",
            "source_id": "src-curr",
            "source_name": "curriculum.txt",
            "domain": "curriculum",
            "text": "หลักสูตรต้องเรียนครบ 120 หน่วยกิต",
            "vector_score": 0.9,
        },
        {
            "stable_chunk_id": "reg-1",
            "source_id": "src-reg",
            "source_name": "regulations.txt",
            "domain": "regulations",
            "text": "ต้องมีผลการเรียนและคุณสมบัติตามข้อบังคับ",
            "vector_score": 0.88,
        },
        {
            "stable_chunk_id": "ann-1",
            "source_id": "src-ann",
            "source_name": "announcement.txt",
            "domain": "announcements",
            "text": "ประกาศปีล่าสุดเปลี่ยนกำหนดการยื่นเอกสาร",
            "keyword_score": 0.95,
        },
    ]
    monkeypatch.setattr(retrieval, "semantic_search_global", lambda *args, **kwargs: fake_rows[:2])
    monkeypatch.setattr(retrieval, "keyword_search_global_chunks", lambda *args, **kwargs: fake_rows[1:])

    results = retrieval.retrieve_open_notebook_style("ถ้าจะจบหลักสูตรต้องดูเงื่อนไขและประกาศอะไรบ้าง")
    domains = {row.get("domain") for row in results}
    assert len(domains) >= 2
    context = build_source_labeled_context("ถ้าจะจบหลักสูตรต้องดูเงื่อนไขและประกาศอะไรบ้าง", results)
    assert len(context["sources_used"]) >= 2
    assert "[Source 1]" in context["formatted_context"]
