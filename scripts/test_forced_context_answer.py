from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.onb_rag.engine import answer_with_context  # noqa: E402


QUESTION = 'จบหลักสูตรต้องผ่านอะไรบ้าง'
CONTEXT = '''[1]
source_id: test-source
source_name: test.pdf
domain: test_domain
content:
นักศึกษาต้องเรียนครบ 120 หน่วยกิตจึงจะสำเร็จการศึกษา'''


def main() -> int:
    answer = answer_with_context(QUESTION, CONTEXT, citation_map={1: 'test.pdf'})
    print('question:', QUESTION)
    print('context:')
    print(CONTEXT)
    print('answer:')
    print(answer)
    if '120' not in answer:
        raise SystemExit('forced-context test failed: expected 120 credits in answer')
    if '[1]' not in answer:
        raise SystemExit('forced-context test failed: expected numeric citation in answer')
    if 'References:' not in answer:
        raise SystemExit('forced-context test failed: expected references block in answer')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
