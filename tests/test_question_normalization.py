import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))

from app.normalization import normalize_question  # noqa: E402
from app.routing import classify_intent  # noqa: E402


class TestQuestionNormalization(unittest.TestCase):
    def test_study_plan_chat_shorthand_is_normalized(self) -> None:
        normalized = normalize_question("ปี 1 เรียนไรบ้าง")
        self.assertEqual(normalized, "ชั้นปีที่ 1 เรียนอะไรบ้าง")
        self.assertEqual(classify_intent(normalized), "curriculum_course_info")

    def test_common_colloquial_question_tokens_are_normalized(self) -> None:
        self.assertEqual(normalize_question("วิชาไรบ้าง"), "วิชาอะไรบ้าง")
        self.assertEqual(normalize_question("มีไรบ้าง"), "มีอะไรบ้าง")
        self.assertEqual(
            classify_intent(normalize_question("ปี 2 มีไรบ้าง")),
            "curriculum_course_info",
        )


if __name__ == "__main__":
    unittest.main()
