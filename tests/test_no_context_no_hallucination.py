import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / "services" / "rag-service"
for key in list(sys.modules):
    if key == "app" or key.startswith("app."):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.open_notebook_rag import not_found_payload  # noqa: E402


def test_no_context_returns_not_found_without_citations():
    payload = not_found_payload("มีทุนไปดาวอังคารไหม")
    assert payload["answer"] == "ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้"
    assert payload["sources_used"] == []
    assert payload["chunks_used"] == []
