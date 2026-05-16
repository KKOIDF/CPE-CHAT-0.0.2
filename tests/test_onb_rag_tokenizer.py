import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
for key in list(sys.modules):
    if key == 'app' or key.startswith('app.'):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.onb_rag.tokenizer import count_tokens, split_by_tokens, tokenize  # noqa: E402


def test_tokenize_preserves_course_code_and_clause_anchor():
    tokens = tokenize('ข้อ 5 นักศึกษาต้องเรียน CPE101 และผ่าน 120 หน่วยกิต')
    assert any('CPE101' in token.replace(' ', '') for token in tokens)
    assert any('ข้อ 5' in token or token == 'ข้อ' for token in tokens)


def test_split_by_tokens_produces_multiple_chunks_for_long_thai_text():
    text = ' '.join(['นักศึกษาต้องเรียนครบ 120 หน่วยกิต'] * 120)
    chunks = split_by_tokens(text, max_tokens=40, overlap_tokens=10)
    assert len(chunks) > 1
    assert all(count_tokens(chunk) <= 45 for chunk in chunks)
