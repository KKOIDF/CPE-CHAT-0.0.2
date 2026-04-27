import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))

from app.announcement_deterministic import render_fast_announcement_calendar_answer, select_announcement_calendar_entry  # noqa: E402
from app.curriculum_deterministic import structured_curriculum_lookup  # noqa: E402
from app.regulations_deterministic import fetch_exam_clause, structured_regulations_lookup  # noqa: E402


class TestStructuredDeterministicPaths(unittest.TestCase):
    def test_announcement_calendar_entry_is_selected_from_artifact(self) -> None:
        question = "นักศึกษาปี 3 รหัส 66 ลงทะเบียนภาค 2/2568 ช่วงวันใด"
        entry = select_announcement_calendar_entry(question)
        self.assertIsNotNone(entry)
        self.assertIn("66", str(entry.get("blob") or entry.get("label") or ""))

        answer = render_fast_announcement_calendar_answer(question)
        self.assertIsNotNone(answer)
        self.assertIn("ม.ค. 2569", str(answer))

    def test_curriculum_prerequisite_lookup_returns_structured_prereq(self) -> None:
        result = structured_curriculum_lookup("LNG 220 มีวิชาบังคับก่อนอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "exact_code")
        self.assertIn("LNG 220", answer)
        self.assertIn("LNG 120", answer)
        self.assertIn("O-NET", answer)

    def test_curriculum_elective_group_list_is_extracted_from_study_plan(self) -> None:
        result = structured_curriculum_lookup("วิชาเลือกมีอะไรบ้าง")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "study_plan_group_list")
        self.assertIn("GEN xxx วิชาเลือกหมวดวิชาศึกษาทั่วไป 1", answer)
        self.assertIn("CPE 3xx วิชาเลือกทางวิศวกรรมคอมพิวเตอร์ 1", answer)
        self.assertIn("XXX xxx วิชาเลือกหมวดวิชาเลือกเสรี 1", answer)

    def test_curriculum_required_group_list_is_extracted_from_study_plan(self) -> None:
        result = structured_curriculum_lookup("วิชาบังคับมีอะไรบ้าง")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "study_plan_group_list")
        self.assertIn("CPE 100 การเขียนโปรแกรมคอมพิวเตอร์สำหรับวิศวกร", answer)
        self.assertIn("LNG 120 ภาษาอังกฤษทั่วไป", answer)
        self.assertIn("CPE 401 โครงงานวิศวกรรมคอมพิวเตอร์ 1", answer)

    def test_fetch_exam_clause_uses_structured_artifact(self) -> None:
        clause = fetch_exam_clause("12")
        self.assertIsNotNone(clause)
        self.assertIn("ข้อ 12", str(clause))
        self.assertIn("สิบห้านาที", str(clause))
        self.assertIn("หกสิบนาที", str(clause))

    def test_structured_regulations_lookup_returns_clause_answer(self) -> None:
        result = structured_regulations_lookup("ข้อ 12 ถ้ามาสายเกิน 15 นาทีแต่ไม่เกิน 60 นาที ต้องทำอย่างไร")
        answer = str(result.get("answer") or "")
        self.assertIn("ข้อ 12", answer)
        self.assertIn("สิบห้านาที", answer)
        self.assertIn("หกสิบนาที", answer)
        self.assertIn("ยื่นคำร้อง", answer)


if __name__ == "__main__":
    unittest.main()
