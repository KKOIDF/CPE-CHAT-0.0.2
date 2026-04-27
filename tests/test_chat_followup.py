import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))

from app.chat_followup import InMemorySessionStore, RedisSessionStore, prepare_chat_request  # noqa: E402


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
