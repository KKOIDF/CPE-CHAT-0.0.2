import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))


class TestMultiDocumentRetrievalHelpers(unittest.TestCase):
    def test_subquery_inherits_parent_anchor(self) -> None:
        import app.retrieval as retrieval  # noqa: E402

        expanded = retrieval._augment_subquery_with_parent_context(
            "RO-16 ต้องใช้อะไร แล้วต้องให้ใครเซ็น",
            "ต้องให้ใครเซ็น",
        )

        self.assertIn("RO-16", expanded)
        self.assertIn("ต้องให้ใครเซ็น", expanded)

    def test_multi_doc_coverage_boost_rewards_rows_supporting_multiple_subqueries(self) -> None:
        import app.retrieval as retrieval  # noqa: E402

        items = [
            {
                "doc_id": "doc-a",
                "source": "forms.txt",
                "text": "RO-16 ใช้สำหรับลาป่วย ลากิจ และต้องให้อาจารย์ที่ปรึกษาเซ็น",
                "score_rrf": 0.40,
            },
            {
                "doc_id": "doc-b",
                "source": "forms.txt",
                "text": "RO-16 ใช้สำหรับลาป่วย ลากิจ",
                "score_rrf": 0.41,
            },
        ]

        boosted = retrieval._apply_multi_doc_coverage_boost(
            items,
            ["RO-16 ใช้สำหรับอะไร", "RO-16 ต้องให้ใครเซ็น"],
        )

        self.assertEqual(boosted[0]["doc_id"], "doc-a")
        self.assertGreater(
            float(boosted[0].get("score_final") or 0.0),
            float(boosted[1].get("score_final") or 0.0),
        )


class TestRetrievalCache(unittest.TestCase):
    class _FakeRedis:
        def __init__(self) -> None:
            self.kv: dict[str, str] = {}

        def get(self, key: str) -> str | None:
            return self.kv.get(key)

        def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
            if not key or ttl_seconds <= 0:
                return False
            self.kv[key] = value
            return True

        def delete(self, *keys: str) -> int:
            removed = 0
            for key in keys:
                if key in self.kv:
                    self.kv.pop(key, None)
                    removed += 1
            return removed

        def keys(self, pattern: str) -> list[str]:
            if pattern == "rag:retrieval_cache:*":
                return [k for k in self.kv if k.startswith("rag:retrieval_cache:")]
            return []

    def test_domain_rag_query_reuses_cached_retrieval(self) -> None:
        import app.orchestration as orchestration  # noqa: E402

        old_retrieve_by_domain = orchestration._retrieve_by_domain
        old_search_fact_index = orchestration.search_fact_index
        old_fact_boost = orchestration.apply_intent_aware_fact_boost
        old_filter_chunks = orchestration._filter_chunks_by_reference
        old_curriculum_bypass = orchestration._CURRICULUM_BYPASS_VECTOR
        old_search_all = orchestration._SEARCH_ALL_DOMAINS
        old_redis_client = orchestration._RETRIEVAL_REDIS_CLIENT
        old_get_redis = orchestration._get_retrieval_redis_client
        calls = {"n": 0}
        fake_redis = self._FakeRedis()

        try:
            orchestration._clear_retrieval_cache()
            orchestration._CURRICULUM_BYPASS_VECTOR = False
            orchestration._SEARCH_ALL_DOMAINS = False
            orchestration._RETRIEVAL_REDIS_CLIENT = fake_redis
            orchestration._get_retrieval_redis_client = lambda: fake_redis

            def fake_retrieve(query: str, domain: str | None = None, vector_enabled: bool = True):
                calls["n"] += 1
                return [
                    {
                        "doc_id": f"{domain}:1",
                        "domain": domain,
                        "source": "forms.txt",
                        "path": "forms.txt",
                        "page_start": 1,
                        "page_end": 1,
                        "text": f"{query} ต้องใช้แบบฟอร์ม RO-16",
                        "score_rrf": 0.5,
                    }
                ]

            orchestration._retrieve_by_domain = fake_retrieve
            orchestration.search_fact_index = lambda *args, **kwargs: []
            orchestration.apply_intent_aware_fact_boost = lambda rows, **kwargs: rows
            orchestration._filter_chunks_by_reference = lambda rows, *args, **kwargs: rows

            first = orchestration.rag_query_domain("RO-16 ต้องใช้อะไร", "regulations")
            second = orchestration.rag_query_domain("RO-16 ต้องใช้อะไร", "regulations")
        finally:
            orchestration._retrieve_by_domain = old_retrieve_by_domain
            orchestration.search_fact_index = old_search_fact_index
            orchestration.apply_intent_aware_fact_boost = old_fact_boost
            orchestration._filter_chunks_by_reference = old_filter_chunks
            orchestration._CURRICULUM_BYPASS_VECTOR = old_curriculum_bypass
            orchestration._SEARCH_ALL_DOMAINS = old_search_all
            orchestration._RETRIEVAL_REDIS_CLIENT = old_redis_client
            orchestration._get_retrieval_redis_client = old_get_redis
            orchestration._clear_retrieval_cache()

        self.assertEqual(calls["n"], 1)
        self.assertEqual(first["contexts"][0]["source"], second["contexts"][0]["source"])
        self.assertEqual(second["meta"].get("retrieval_cache", {}).get("hit"), 1)
        self.assertTrue(fake_redis.keys("rag:retrieval_cache:*"))


if __name__ == "__main__":
    unittest.main()
