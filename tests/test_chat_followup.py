import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))

from app.chat_followup import InMemorySessionStore, RedisSessionStore, prepare_chat_request  # noqa: E402
from app.main import RagRequest, _deterministic_domain_shortcut  # noqa: E402
from app.routing import analyze_route, select_resolution_strategy  # noqa: E402


class _FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        vals = list(self.lists.get(key) or [])
        if end < 0:
            return vals[start:]
        return vals[start : end + 1]

    def lpush(self, key: str, value: str) -> None:
        vals = list(self.lists.get(key) or [])
        vals.insert(0, value)
        self.lists[key] = vals

    def ltrim(self, key: str, start: int, end: int) -> None:
        vals = list(self.lists.get(key) or [])
        if end < 0:
            self.lists[key] = vals[start:]
        else:
            self.lists[key] = vals[start : end + 1]

    def expire(self, key: str, ttl_seconds: int) -> bool:
        return bool(key) and ttl_seconds > 0

    def get(self, key: str) -> str | None:
        return self.kv.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        if key and ttl_seconds > 0:
            self.kv[key] = value
            return True
        return False


class TestChatFollowupPipeline(unittest.TestCase):
    def test_build_effective_question_prefers_single_course_from_previous_assistant_answer(self) -> None:
        messages = [
            {"role": "user", "content": "อาจารย์ประพงษ์สอนวิชาอะไร"},
            {"role": "assistant", "content": "- CPE 324 ระบบสมองกลฝังตัว [records.jsonl/1]"},
            {"role": "user", "content": "วิชานี้กี่หน่วยกิต"},
        ]

        prepared = prepare_chat_request(
            question="วิชานี้กี่หน่วยกิต",
            domain="curriculum",
            session_id="s_assistant_anchor",
            messages=messages,
            session_store=InMemorySessionStore(),
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: CPE 324", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: วิชานี้กี่หน่วยกิต", prepared.question)

    def test_rag_request_exposes_optional_messages_for_query_endpoint(self) -> None:
        req = RagRequest(question="CPE 342 วิชาอะไร", domain="curriculum")

        self.assertIsNone(req.messages)

    def test_question_and_session_id_use_server_side_memory(self) -> None:
        store = InMemorySessionStore()
        store.append_chat_turn("s1", "วิชาเลือกมีอะไรบ้าง")

        prepared = prepare_chat_request(
            question="แล้ววิชาเลือกเสรีล่ะ",
            domain=None,
            session_id="s1",
            messages=None,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("วิชาเลือกมีอะไรบ้าง", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: แล้ววิชาเลือกเสรีล่ะ", prepared.question)

    def test_messages_and_session_id_prefer_explicit_message_history(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "CPE 214 คืออะไร"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "แล้วใครสอน"},
        ]

        prepared = prepare_chat_request(
            question="แล้วใครสอน",
            domain="curriculum",
            session_id="s2",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: CPE 214", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: แล้วใครสอน", prepared.question)

    def test_course_credit_followup_reuses_latest_course_code(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "CPE301"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "กี่หน่วยกิต"},
        ]

        prepared = prepare_chat_request(
            question="กี่หน่วยกิต",
            domain="curriculum",
            session_id="s2b",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: CPE 301", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: กี่หน่วยกิต", prepared.question)
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "course")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_value"), "CPE 301")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_confidence"), 3)

    def test_course_description_followup_reuses_latest_course_code(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "CPE301"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "เรียนเกี่ยวกับอะไร"},
        ]

        prepared = prepare_chat_request(
            question="เรียนเกี่ยวกับอะไร",
            domain="curriculum",
            session_id="s2c",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: CPE 301", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: เรียนเกี่ยวกับอะไร", prepared.question)

    def test_course_instructor_followup_supports_subject_first_wording(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "CPE 214 คืออะไร"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "วิชานี้ใครสอน"},
        ]

        prepared = prepare_chat_request(
            question="วิชานี้ใครสอน",
            domain="curriculum",
            session_id="s2c2",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: CPE 214", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: วิชานี้ใครสอน", prepared.question)
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "course")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_value"), "CPE 214")

    def test_course_instructor_followup_supports_predicate_first_wording(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "CPE 214 คืออะไร"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "ใครสอนวิชานี้"},
        ]

        prepared = prepare_chat_request(
            question="ใครสอนวิชานี้",
            domain="curriculum",
            session_id="s2c3",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: CPE 214", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: ใครสอนวิชานี้", prepared.question)
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "course")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_value"), "CPE 214")

    def test_course_reference_followup_prefers_single_course_from_previous_assistant_answer(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "อาจารย์ประพงษ์สอนวิชาอะไร"},
            {"role": "assistant", "content": "- CPE 324 ระบบสมองกลฝังตัว [records.jsonl/1]"},
            {"role": "user", "content": "วิชานี้กี่หน่วยกิต"},
        ]

        prepared = prepare_chat_request(
            question="วิชานี้กี่หน่วยกิต",
            domain="curriculum",
            session_id="s2c4",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "course")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_value"), "CPE 324")

    def test_course_reference_followup_requests_clarification_when_previous_assistant_answer_has_multiple_courses(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "อาจารย์ประพงษ์สอนวิชาอะไร"},
            {"role": "assistant", "content": "- CPE 100 ...\n- CPE 324 ..."},
            {"role": "user", "content": "วิชานี้กี่หน่วยกิต"},
        ]

        prepared = prepare_chat_request(
            question="วิชานี้กี่หน่วยกิต",
            domain="curriculum",
            session_id="s2c5",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertEqual(prepared.followup_meta.get("followup_needs_clarification"), 1)
        self.assertIn("CPE 100", str(prepared.followup_meta.get("followup_clarification_message") or ""))
        self.assertIn("CPE 324", str(prepared.followup_meta.get("followup_clarification_message") or ""))

    def test_instructor_course_list_followup_reuses_latest_instructor(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "วิชาอาจารย์ประพงษ์"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "วิชาที่สอน"},
        ]

        prepared = prepare_chat_request(
            question="วิชาที่สอน",
            domain="curriculum",
            session_id="s2d",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: อาจารย์ประพงษ์", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: วิชาที่สอน", prepared.question)
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "instructor")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_value"), "อาจารย์ประพงษ์")
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_confidence"), 3)

    def test_instructor_query_does_not_keep_question_suffix_in_resolved_entity(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "อาจารย์ประพงษ์ ปรีชาประพาฬวงศ์ สอนวิชาอะไร"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "ดร. ประพงษ์ ปรีชาประพาฬวงศ์ สอนวิชาอะไร"},
        ]

        prepared = prepare_chat_request(
            question="ดร. ประพงษ์ ปรีชาประพาฬวงศ์ สอนวิชาอะไร",
            domain="curriculum",
            session_id="s2d2",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q.replace("\n", " "),
        )

        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "instructor")
        self.assertEqual(
            prepared.followup_meta.get("followup_resolved_entity_value"),
            "อาจารย์ประพงษ์ ปรีชาประพาฬวงศ์",
        )
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_confidence"), 3)

    def test_short_topic_followup_reuses_latest_topic_from_history(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "เอกสารจบ"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "ต้องยื่นเมื่อไร"},
        ]

        prepared = prepare_chat_request(
            question="ต้องยื่นเมื่อไร",
            domain="announcements",
            session_id="s2e",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: เอกสารจบ", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: ต้องยื่นเมื่อไร", prepared.question)

    def test_generic_course_code_followup_reuses_previous_language_topic(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "ภาษาญี่ปุ่น"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "รหัสวิชา"},
        ]

        prepared = prepare_chat_request(
            question="รหัสวิชา",
            domain="curriculum",
            session_id="s2e2",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: ภาษาญี่ปุ่น", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: รหัสวิชา", prepared.question)

    def test_generic_form_signer_followup_reuses_previous_form_topic(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "ขอเอกสารใบลากิจ"},
            {"role": "assistant", "content": "- ต้องใช้ RO-16 ..."},
            {"role": "user", "content": "ต้องให้ใครเซ็นบ้าง"},
        ]

        prepared = prepare_chat_request(
            question="ต้องให้ใครเซ็นบ้าง",
            domain="regulations",
            session_id="s2e3",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("บริบทก่อนหน้า: ขอเอกสารใบลากิจ", prepared.question)
        self.assertIn("คำถามต่อเนื่อง: ต้องให้ใครเซ็นบ้าง", prepared.question)

    def test_resolved_entity_is_passed_into_route_analysis(self) -> None:
        decision = analyze_route(
            "วิชาที่สอน",
            "curriculum",
            resolved_entity={
                "type": "instructor",
                "value": "อาจารย์ประพงษ์",
                "confidence": 3,
            },
        )

        self.assertEqual(decision.resolved_entity_type, "instructor")
        self.assertEqual(decision.resolved_entity_value, "อาจารย์ประพงษ์")
        self.assertEqual(decision.resolved_entity_confidence, 3)
        self.assertEqual(decision.effective_domain, "curriculum")

    def test_followup_meta_sets_clarification_when_history_has_multiple_same_type_candidates(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "CPE 101"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "CPE 102"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "กี่หน่วยกิต"},
        ]

        prepared = prepare_chat_request(
            question="กี่หน่วยกิต",
            domain="curriculum",
            session_id="s2f",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertIn("course:CPE 102:3", str(prepared.followup_meta.get("followup_resolved_entity_candidates") or ""))
        self.assertEqual(prepared.followup_meta.get("followup_resolved_entity_type"), "course")

    def test_routing_prefers_full_rag_for_broad_announcement_procedure_questions(self) -> None:
        decision = analyze_route("การขอ transcript ต้องทำอย่างไร", "announcements")
        strategy = select_resolution_strategy(decision)

        self.assertEqual(decision.primary_intent, "general_info")
        self.assertEqual(strategy.resolution_path, "full_rag")

    def test_deterministic_shortcut_only_fires_for_data_backed_announcement_calendar(self) -> None:
        shortcut = _deterministic_domain_shortcut("นักศึกษาปี 3 รหัส 66 ลงทะเบียนภาค 2/2568 ช่วงวันใด", "announcements")
        broad = _deterministic_domain_shortcut("การขอ transcript ต้องทำอย่างไร", "announcements")

        self.assertIsNotNone(shortcut)
        self.assertIn("announcement", str((shortcut or {}).get("answer") or "").lower())
        self.assertIsNone(broad)

    def test_short_summary_followup_uses_session_hint(self) -> None:
        store = InMemorySessionStore()
        store.put_followup_hint(
            "s3",
            question="มาสายสอบได้ไหม",
            domain="regulations",
            intent="claim_verification",
        )

        prepared = prepare_chat_request(
            question="สรุปสั้นๆ",
            domain=None,
            session_id="s3",
            messages=None,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertTrue(prepared.lock_applied)
        self.assertEqual(prepared.domain, "regulations")
        self.assertEqual(prepared.question, "มาสายสอบได้ไหม")

    def test_cross_domain_followup_does_not_override_explicit_domain(self) -> None:
        store = InMemorySessionStore()
        store.put_followup_hint(
            "s4",
            question="มาสายสอบได้ไหม",
            domain="regulations",
            intent="claim_verification",
        )

        prepared = prepare_chat_request(
            question="สรุปสั้นๆ",
            domain="announcements",
            session_id="s4",
            messages=None,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertFalse(prepared.lock_applied)
        self.assertEqual(prepared.domain, "announcements")
        self.assertEqual(prepared.question, "สรุปสั้นๆ")

    def test_sessionless_followup_stays_unresolved_safely(self) -> None:
        store = InMemorySessionStore()
        prepared = prepare_chat_request(
            question="สรุปสั้นๆ",
            domain=None,
            session_id=None,
            messages=None,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertFalse(prepared.lock_applied)
        self.assertEqual(prepared.question, "สรุปสั้นๆ")
        self.assertEqual(prepared.session_id, "")

    def test_form_code_question_does_not_inherit_previous_form_context(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "ใบลาออก"},
            {"role": "assistant", "content": "- ต้องใช้ RO-13 ..."},
            {"role": "user", "content": "RO-26 ใช้ทำอะไร"},
        ]

        prepared = prepare_chat_request(
            question="RO-26 ใช้ทำอะไร",
            domain="regulations",
            session_id="forms1",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertEqual(prepared.question, "RO-26 ใช้ทำอะไร")

    def test_form_catalog_question_does_not_inherit_previous_form_context(self) -> None:
        store = InMemorySessionStore()
        messages = [
            {"role": "user", "content": "ใบลาออก"},
            {"role": "assistant", "content": "- ต้องใช้ RO-13 ..."},
            {"role": "user", "content": "มีแบบฟอร์มอะไรบ้าง"},
        ]

        prepared = prepare_chat_request(
            question="มีแบบฟอร์มอะไรบ้าง",
            domain="regulations",
            session_id="forms2",
            messages=messages,
            session_store=store,
            question_preparer=lambda q, _d: q,
        )

        self.assertEqual(prepared.question, "มีแบบฟอร์มอะไรบ้าง")

    def test_redis_session_store_shares_memory_across_instances(self) -> None:
        shared = _FakeRedis()
        store_a = RedisSessionStore(redis_url="redis://fake", ttl_seconds=120)
        store_b = RedisSessionStore(redis_url="redis://fake", ttl_seconds=120)
        store_a._redis = shared
        store_b._redis = shared

        store_a.append_chat_turn("s5", "วิชาเลือกมีอะไรบ้าง")
        store_a.put_followup_hint(
            "s5",
            question="วิชาเลือกมีอะไรบ้าง",
            domain="curriculum",
            intent="curriculum_course_info",
        )

        self.assertEqual(store_b.get_chat_history("s5"), ["วิชาเลือกมีอะไรบ้าง"])
        hint = store_b.get_followup_hint("s5")
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(hint.get("domain"), "curriculum")
        self.assertEqual(hint.get("question"), "วิชาเลือกมีอะไรบ้าง")


if __name__ == "__main__":
    unittest.main()
