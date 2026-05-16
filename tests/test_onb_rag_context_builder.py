import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
for key in list(sys.modules):
    if key == 'app' or key.startswith('app.'):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.onb_rag.context_builder import build_source_labeled_context  # noqa: E402


def test_context_builder_keeps_source_labels_and_metadata():
    payload = build_source_labeled_context(
        'จบหลักสูตรต้องผ่านอะไรบ้าง',
        [
            {
                'stable_chunk_id': 'chunk-1',
                'source_id': 'src-1',
                'source_name': 'graduation_test.txt',
                'domain': 'test_domain',
                'section_heading': 'เงื่อนไขการสำเร็จการศึกษา',
                'page': 1,
                'text': 'นักศึกษาต้องเรียนครบ 120 หน่วยกิต และผ่านรายวิชาบังคับทั้งหมด',
            }
        ],
        token_budget=400,
    )
    ctx = payload['formatted_context']
    assert '[1]' in ctx
    assert 'source_id: src-1' in ctx
    assert 'source_name: graduation_test.txt' in ctx
    assert 'domain: test_domain' in ctx
    assert 'section: เงื่อนไขการสำเร็จการศึกษา' in ctx
    assert payload['sources_used'] == ['graduation_test.txt']
    assert payload['citation_map'][1] == 'graduation_test.txt, หน้า 1'
