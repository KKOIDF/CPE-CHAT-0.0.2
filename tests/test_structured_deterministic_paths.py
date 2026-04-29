import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))

from app.announcement_deterministic import (  # noqa: E402
    render_fast_announcement_calendar_answer,
    render_generalized_announcement_answer,
    select_announcement_calendar_entry,
)
from app.curriculum_deterministic import structured_curriculum_lookup  # noqa: E402
from app.main import _build_general_policy_answer  # noqa: E402
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

    def test_curriculum_course_study_plan_lookup_returns_term_and_guidance(self) -> None:
        result = structured_curriculum_lookup("ถ้าผมจะวางแผนเรียนให้จบตรงเวลา CPE 100 ควรลงช่วงไหนของแผนเรียน")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "study_plan_course")
        self.assertIn("CPE 100", answer)
        self.assertIn("เทอม/ชั้นปีที่อยู่ในแผน", answer)
        self.assertIn("คำแนะนำการลงทะเบียน", answer)

    def test_curriculum_followup_credit_answer_is_focused(self) -> None:
        result = structured_curriculum_lookup("บริบทก่อนหน้า: CPE 342\nคำถามต่อเนื่อง: แล้วกี่หน่วยกิต")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "exact_code")
        self.assertIn("CPE 342", answer)
        self.assertIn("3 หน่วยกิต", answer)
        self.assertNotIn("ชื่อวิชา:", answer)
        self.assertNotIn("ชั่วโมงเรียน:", answer)

    def test_announcement_open_term_answer_mentions_official_calendar(self) -> None:
        answer = render_fast_announcement_calendar_answer("ขออัปเดต วันเปิดภาคการศึกษา ล่าสุดหน่อยครับ")
        self.assertIsNotNone(answer)
        self.assertIn("ประกาศล่าสุด/ปฏิทินการศึกษา", str(answer))
        self.assertIn("วันเปิดภาคการศึกษา", str(answer))

    def test_announcement_w_deadline_answer_mentions_official_calendar(self) -> None:
        answer = render_fast_announcement_calendar_answer("ขออัปเดต วันสุดท้ายถอนวิชาแบบติด W ล่าสุดหน่อยครับ")
        self.assertIsNotNone(answer)
        self.assertIn("ประกาศล่าสุด/ปฏิทินการศึกษา", str(answer))
        self.assertIn("วันสุดท้ายถอนวิชาแบบติด W", str(answer))

    def test_generalized_announcement_answer_handles_transcript_procedure(self) -> None:
        answer = render_generalized_announcement_answer("การขอ transcript ต้องทำอย่างไร")
        self.assertIsNotNone(answer)
        self.assertIn("announcements", str(answer))
        self.assertIn("transcript", str(answer).lower())
        self.assertIn("งานทะเบียน", str(answer))

    def test_generalized_announcement_answer_handles_section_change(self) -> None:
        answer = render_generalized_announcement_answer("การเปลี่ยน section ทำได้ในช่วงเวลาใด")
        self.assertIsNotNone(answer)
        self.assertIn("announcements", str(answer))
        self.assertIn("เปลี่ยน section", str(answer))
        self.assertIn("add/drop", str(answer))

    def test_generalized_announcement_answer_handles_withdrawal_conditions(self) -> None:
        answer = render_generalized_announcement_answer("การถอนรายวิชามีเงื่อนไขอะไร และมีผลต่อเกรดอย่างไร")
        self.assertIsNotNone(answer)
        self.assertIn("announcements", str(answer))
        self.assertIn("W", str(answer))

    def test_generalized_announcement_answer_handles_petition_channel(self) -> None:
        answer = render_generalized_announcement_answer("การยื่นคำร้องต้องทำผ่านช่องทางใด")
        self.assertIsNotNone(answer)
        self.assertIn("announcements", str(answer))
        self.assertIn("ช่องทางของงานทะเบียน", str(answer))

    def test_generalized_announcement_answer_handles_system_outage(self) -> None:
        answer = render_generalized_announcement_answer("หากระบบลงทะเบียนล่มต้องทำอย่างไร")
        self.assertIsNotNone(answer)
        self.assertIn("ระบบลงทะเบียนล่ม", str(answer))
        self.assertIn("ประกาศล่าสุด", str(answer))

    def test_general_policy_answer_handles_project_topic_change(self) -> None:
        answer = _build_general_policy_answer("หากต้องการเปลี่ยนหัวข้อโปรเจคต้องทำอย่างไร")
        self.assertIsNotNone(answer)
        self.assertIn("general", str(answer))
        self.assertIn("อาจารย์ที่ปรึกษา", str(answer))

    def test_general_policy_answer_handles_course_withdrawal_timing(self) -> None:
        answer = _build_general_policy_answer("การลาออกจากรายวิชาทำได้เมื่อไร")
        self.assertIsNotNone(answer)
        self.assertIn("general", str(answer))
        self.assertIn("ปฏิทินการศึกษา", str(answer))

    def test_generalized_announcement_answer_handles_wrong_course_registration(self) -> None:
        answer = render_generalized_announcement_answer("หากลงทะเบียนผิดวิชา ต้องแก้ไขอย่างไร")
        self.assertIsNotNone(answer)
        self.assertIn("announcements", str(answer))
        self.assertIn("ลงทะเบียน", str(answer))
        self.assertIn("คำร้อง", str(answer))

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

    def test_structured_regulations_lookup_handles_appeal_procedure_eval_variant(self) -> None:
        result = structured_regulations_lookup('ถ้าเกิดเคส "อยากอุทธรณ์ผลการพิจารณาความผิดระหว่างสอบ" ขอขั้นตอนแบบทีละข้อหน่อย')
        answer = str(result.get("answer") or "")
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("15 วัน", answer)
        self.assertIn("คำร้องอุทธรณ์", answer)

    def test_structured_regulations_lookup_handles_cheating_penalty_eval_variant(self) -> None:
        result = structured_regulations_lookup('ถ้าเกิดเคส "สงสัยเรื่องบทลงโทษกรณีทุจริตสอบ" ขอขั้นตอนแบบทีละข้อหน่อย')
        answer = str(result.get("answer") or "")
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("ทุจริต", answer)
        self.assertIn("คณะกรรมการพิจารณาความผิด", answer)

    def test_structured_regulations_lookup_handles_cheating_penalty_binary_eval_variant(self) -> None:
        result = structured_regulations_lookup('ช่วยยืนยันให้หน่อยว่า “สงสัยเรื่องบทลงโทษกรณีทุจริตสอบ” ทำได้หรือไม่ได้?')
        answer = str(result.get("answer") or "")
        self.assertIn("ทำได้/ไม่ได้", answer)
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("ทุจริตสอบ", answer)

    def test_structured_regulations_lookup_handles_appeal_rejected_eval_variant(self) -> None:
        result = structured_regulations_lookup('กรณี “อยากอุทธรณ์ผลการพิจารณาความผิดระหว่างสอบ” ถ้าโดนปฏิเสธหน้างาน ควรดำเนินการต่อยังไง?')
        answer = str(result.get("answer") or "")
        self.assertIn("อุทธรณ์", answer)
        self.assertIn("หลักฐาน", answer)
        self.assertIn("ระเบียบการสอบ", answer)

    def test_structured_regulations_lookup_handles_emergency_rejected_eval_variant(self) -> None:
        result = structured_regulations_lookup('กรณี "เกิดเหตุฉุกเฉินระหว่างสอบ" ถ้าโดนปฏิเสธหน้างาน ควรดำเนินการต่อยังไง')
        answer = str(result.get("answer") or "")
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("เหตุฉุกเฉิน", answer)
        self.assertIn("กรรมการคุมสอบ", answer)

    def test_structured_regulations_lookup_handles_appeal_binary_eval_variant(self) -> None:
        result = structured_regulations_lookup('ช่วยยืนยันให้หน่อยว่า "อยากอุทธรณ์ผลการพิจารณาความผิดระหว่างสอบ" ทำได้หรือไม่ได้')
        answer = str(result.get("answer") or "")
        self.assertIn("ทำได้/ไม่ได้", answer)
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("15 วัน", answer)

    def test_structured_regulations_lookup_handles_emergency_binary_eval_variant(self) -> None:
        result = structured_regulations_lookup('ช่วยยืนยันให้หน่อยว่า "เกิดเหตุฉุกเฉินระหว่างสอบ" ทำได้หรือไม่ได้')
        answer = str(result.get("answer") or "")
        self.assertIn("ทำได้/ไม่ได้", answer)
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("กรรมการคุมสอบ", answer)

    def test_structured_regulations_lookup_handles_cheating_rejected_eval_variant(self) -> None:
        result = structured_regulations_lookup('กรณี "สงสัยเรื่องบทลงโทษกรณีทุจริตสอบ" ถ้าโดนปฏิเสธหน้างาน ควรดำเนินการต่อยังไง')
        answer = str(result.get("answer") or "")
        self.assertIn("ระเบียบการสอบ", answer)
        self.assertIn("ทุจริตสอบ", answer)
        self.assertIn("คณะกรรมการพิจารณาความผิด", answer)


if __name__ == "__main__":
    unittest.main()
