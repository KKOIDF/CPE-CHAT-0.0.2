import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = REPO_ROOT / 'services' / 'rag-service'
for key in list(sys.modules):
    if key == 'app' or key.startswith('app.'):
        sys.modules.pop(key, None)
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))

from app.onb_rag.prompting import build_prompt, finalize_answer  # noqa: E402


def test_answer_style_definition_prompt_contains_numeric_citations_and_references():
    ctx = """[1]
source_id: s1
source_name: assessment_rules.pdf
domain: regulations
page: 8
content:
S หมายถึงผ่าน U หมายถึงไม่ผ่าน

[2]
source_id: s2
source_name: obem_guideline.pdf
domain: curriculum
section: Competency-based Assessment
content:
ใช้สัญลักษณ์ S/U ในการประเมินบางกรณี"""
    prompt = build_prompt('สัญลักษณ์ S และ U มีความหมายว่าอะไร', ctx, cites={1: 'assessment_rules.pdf, หน้า 8', 2: 'obem_guideline.pdf, section Competency-based Assessment'})
    assert 'ใช้ citation แบบตัวเลข' in prompt
    assert '[1] - source:assessment_rules.pdf, หน้า 8' in prompt
    assert 'References ที่ใช้ได้' in prompt


def test_finalize_answer_appends_numeric_references_block():
    answer = """S หมายถึง ผ่าน [1]
U หมายถึง ไม่ผ่าน [2]"""
    out = finalize_answer(answer, {1: 'assessment_rules.pdf, หน้า 8', 2: 'obem_guideline.pdf, section Competency-based Assessment'})
    assert 'References:' in out
    assert '[1] - source:assessment_rules.pdf, หน้า 8' in out
    assert '[2] - source:obem_guideline.pdf, section Competency-based Assessment' in out


def test_partial_context_answer_keeps_partial_instead_of_not_found():
    answer = 'พบเฉพาะเงื่อนไขการยื่นคำร้อง [1]'
    out = finalize_answer(answer, {1: 'leave_rules.pdf, หน้า 3'})
    assert 'ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้' not in out
    assert '[1] - source:leave_rules.pdf, หน้า 3' in out
