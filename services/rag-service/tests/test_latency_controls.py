from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import chroma_client, main  # type: ignore


def test_needs_langchain_retrieval_fallback_keeps_domain_context(monkeypatch):
    monkeypatch.setenv("RAG_LC_FALLBACK_MIN_CTX", "2")
    monkeypatch.setenv("RAG_LC_FALLBACK_LOW_SCORE", "0.9")
    rows = [{"domain": "curriculum", "score_rrf": 0.01}]

    assert main._needs_langchain_retrieval_fallback(
        rows,
        effective_domain="curriculum",
        question="วิชาบังคับของภาควิชาคือวิชาอะไรบ้าง",
        intent="curriculum_course_info",
    ) is False


def test_should_use_regulations_strict_fallback_for_exam_policy():
    assert main._should_use_regulations_strict_fallback(
        "หากนักศึกษาเข้าสอบสาย จะมีระเบียบหรือแนวทางปฏิบัติอย่างไร",
        "regulations",
    ) is True


def test_should_not_prefer_structured_curriculum_shortcut_for_group_list():
    decision = SimpleNamespace(effective_domain="curriculum")

    assert main._should_prefer_structured_curriculum_shortcut(
        "วิชาบังคับของภาควิชาคือวิชาอะไรบ้าง",
        decision,
    ) is False


def test_should_not_prefer_structured_curriculum_shortcut_for_prefix_list():
    decision = SimpleNamespace(effective_domain="curriculum")

    assert main._should_prefer_structured_curriculum_shortcut(
        "รหัสวิชาทั้งหมดในหมวดวิชาภาษาต่างๆ (LNG) ในหลักสูตรมีอะไรบ้าง",
        decision,
    ) is False


def test_should_skip_auto_evidence_verifier_for_trusted_exam_context():
    decision = SimpleNamespace(primary_intent="exam_policy")
    skip, reason = main._should_skip_auto_evidence_verifier(
        question="เข้าสอบสายได้ไหม",
        decision=decision,
        contexts=[{"source": "rule_exam2560.txt", "domain": "regulations"}],
    )

    assert skip is True
    assert reason == "trusted_exam_context"


def test_question_signal_terms_expand_w_to_withdrawn():
    terms = main._question_signal_terms("W คืออะไร")

    assert "withdrawn" in [t.lower() for t in terms]


def test_question_like_terms_are_not_strong_low_confidence_signals():
    assert main._is_strong_low_conf_signal_term("คืออะไร") is False
    assert main._is_strong_low_conf_signal_term("ทำอะไร") is False
    assert main._is_strong_low_conf_signal_term("ภาควิชา") is True
    assert main._is_strong_low_conf_signal_term("RO26") is True


def test_low_confidence_guardrail_allows_w_withdrawn_context_match():
    result = {
        "contexts": [{"domain": "regulations", "source": "ruleG2568.txt"}],
        "prompt": "บริบท\n[ruleG2568.txt/1] การถอนรายวิชาในช่วงเวลาดังกล่าวได้ผลการประเมินเป็น W (Withdrawn)\n\nคำตอบ:",
    }

    assert main._low_confidence_guardrail("W คืออะไร", result) is None


def test_low_confidence_guardrail_does_not_trigger_on_generic_question_terms_only():
    result = {
        "contexts": [{"domain": "regulations", "source": "forms.txt"}],
        "prompt": "บริบท\n[forms.txt/1] แบบฟอร์มคำร้องทั่วไปใช้สำหรับยื่นคำร้องต่อภาควิชา\n\nคำตอบ:",
    }

    assert main._low_confidence_guardrail("คืออะไร", result) is None


def test_query_embedding_cache_reuses_normalized_query(monkeypatch):
    calls: list[tuple[tuple[str, ...], bool]] = []

    def fake_embed_texts(texts, is_query=False):
        calls.append((tuple(texts), is_query))
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr(chroma_client, "embed_texts", fake_embed_texts)
    chroma_client._reset_query_embedding_cache_for_tests()

    first = chroma_client._cached_query_embedding("วิชาบังครับของภาควิชา", scope="domain", domain="curriculum")
    second = chroma_client._cached_query_embedding("  วิชาบังคับของภาควิชา  ", scope="domain", domain="curriculum")

    assert first == second
    assert len(calls) == 1


