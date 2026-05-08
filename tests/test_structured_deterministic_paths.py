import sys
import tempfile
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
import app.curriculum_deterministic as curriculum_deterministic  # noqa: E402
from app.curriculum_deterministic import structured_curriculum_lookup  # noqa: E402
from app.main import _finalize_user_answer_text  # noqa: E402
from app.regulations_deterministic import fetch_exam_clause, structured_regulations_lookup  # noqa: E402


class TestStructuredDeterministicPaths(unittest.TestCase):
    def test_finalize_user_answer_text_polishes_regulation_schema_for_chat(self) -> None:
        raw = (
            "- ทำได้/ไม่ได้: ได้เมื่อได้รับอนุญาต\n"
            "- อ้างอิงระเบียบข้อใด: ระเบียบการสอบ\n"
            "- เงื่อนไขหลัก: ต้องแจ้งกรรมการคุมสอบทันที\n"
            "- ข้อยกเว้น: พิจารณาเป็นรายกรณี\n"
            "- ต้องติดต่อใคร: กรรมการคุมสอบ\n"
            "- เอกสารที่ต้องใช้: คำร้องและหลักฐาน\n"
            "- ขั้นตอนทีละข้อ: แจ้งเหตุและยื่นคำร้อง\n"
            "- หากถูกปฏิเสธ/เลยกำหนด ต้องทำอย่างไร: ติดต่อหน่วยงานวิชาการ\n"
            "- ข้อมูลที่เอกสารไม่ได้ระบุ: ยังยืนยันไม่ได้จากเอกสาร"
        )

        answer = _finalize_user_answer_text("ถ้าเข้าสอบสายต้องทำยังไง", raw)

        self.assertIn("เรื่องนี้", answer)
        self.assertIn("แนะนำให้", answer)
        self.assertIn("ติดต่อ", answer)
        self.assertNotIn("อ้างอิงระเบียบข้อใด:", answer)
        self.assertNotIn("ข้อมูลที่เอกสารไม่ได้ระบุ:", answer)

    def test_finalize_user_answer_text_polishes_announcement_schema_for_chat(self) -> None:
        raw = (
            "- แหล่งประกาศ: ประกาศล่าสุดของงานทะเบียน\n"
            "- ขั้นตอน: ยื่นคำร้องผ่านช่องทางที่กำหนด\n"
            "- เงื่อนไข: ต้องแนบเหตุผล\n"
            "- ข้อจำกัด: หากไม่มีประกาศรองรับจะทำไม่ได้\n"
            "- ขั้นตอนถัดไป: ตรวจประกาศล่าสุดอีกครั้ง"
        )

        answer = _finalize_user_answer_text("เลย deadline เพิ่มรายวิชาต้องทำยังไง", raw)

        self.assertIn("ควรอ้างอิงจาก", answer)
        self.assertIn("แนะนำให้", answer)
        self.assertIn("เงื่อนไขสำคัญคือ", answer)
        self.assertIn("ถัดจากนี้", answer)
        self.assertNotIn("แหล่งประกาศ:", answer)

    def test_instructor_record_fallback_uses_root_dir_in_shallow_layout(self) -> None:
        old_root_dir = curriculum_deterministic.ROOT_DIR
        old_cache = curriculum_deterministic._STAFF_COURSE_RECORDS_CACHE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                data_dir = root / "data" / "db"
                data_dir.mkdir(parents=True, exist_ok=True)
                (data_dir / "records.jsonl").write_text(
                    '{"text":"1|ดร. ทดสอบ ระบบ|x|x|x|[{\\"code\\": \\"CPE101\\", \\"title\\": \\"Computer Programming\\"}]","source":"records.jsonl"}\n',
                    encoding="utf-8",
                )
                curriculum_deterministic.ROOT_DIR = root
                curriculum_deterministic._STAFF_COURSE_RECORDS_CACHE = None

                rows, canonical_name, cite = curriculum_deterministic._lookup_courses_for_instructor_from_records(
                    "ดร. ทดสอบ ระบบ"
                )

                self.assertEqual(canonical_name, "ดร. ทดสอบ ระบบ")
                self.assertEqual(cite, "records.jsonl/1")
                self.assertEqual(rows, [("CPE 101", "Computer Programming", "records.jsonl/1")])
        finally:
            curriculum_deterministic.ROOT_DIR = old_root_dir
            curriculum_deterministic._STAFF_COURSE_RECORDS_CACHE = old_cache

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

    def test_curriculum_followup_description_answer_uses_course_description(self) -> None:
        result = structured_curriculum_lookup("บริบทก่อนหน้า: PHY 103\nคำถามต่อเนื่อง: เรียนเกี่ยวกับอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "exact_code")
        self.assertIn("PHY 103", answer)
        self.assertIn("เน้นการประยุกต์ใช้กฎต่างๆ ทางฟิสิกส์", answer)
        self.assertNotIn("คือ ฟิสิกส์ทั่วไปสำหรับนักศึกษาวิศวกรรมศาสตร์ 1", answer)

    def test_curriculum_title_plus_description_question_maps_title_to_description(self) -> None:
        result = structured_curriculum_lookup("ฟิสิกส์ทั่วไปสำหรับนักศึกษาวิศวกรรมศาสตร์ 1 เรียนเกี่ยวกับอะไร")
        answer = str(result.get("answer") or "")
        self.assertIn("PHY 103", answer)
        self.assertIn("เน้นการประยุกต์ใช้กฎต่างๆ ทางฟิสิกส์", answer)

    def test_curriculum_instructor_name_question_returns_courses_taught(self) -> None:
        result = structured_curriculum_lookup("## **ดร. ประพงษ์ ปรีชาประพาฬวงศ์ สอนวิชาอะไร**")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "instructor_course_list")
        self.assertIn("ประพงษ์", answer)
        self.assertIn("CPE 100", answer)
        self.assertIn("CPE 324", answer)

    def test_curriculum_short_instructor_name_question_returns_courses_taught(self) -> None:
        result = structured_curriculum_lookup("อาจารย์ประพงษ์สอนวิชาอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "instructor_course_list")
        self.assertIn("ประพงษ์", answer)
        self.assertIn("CPE 100", answer)
        self.assertIn("CPE 324", answer)
        self.assertNotIn("ไม่พบข้อมูล", answer)

    def test_curriculum_abbrev_instructor_name_question_returns_courses_taught(self) -> None:
        result = structured_curriculum_lookup("อ.ประพงษ์สอนอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "instructor_course_list")
        self.assertIn("ประพงษ์", answer)
        self.assertIn("CPE 324", answer)
        self.assertNotIn("ไม่พบข้อมูล", answer)

    def test_curriculum_doctor_instructor_name_question_returns_courses_taught(self) -> None:
        result = structured_curriculum_lookup("ดร.ประพงษ์สอนอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "instructor_course_list")
        self.assertIn("ประพงษ์", answer)
        self.assertIn("CPE 324", answer)

    def test_curriculum_instructor_identity_followup_returns_canonical_name(self) -> None:
        result = structured_curriculum_lookup(
            "บริบทก่อนหน้า: อาจารย์ประพงษ์\nคำถามต่อเนื่อง: คือใคร",
            resolved_entity={"type": "instructor", "value": "อาจารย์ประพงษ์", "confidence": 3},
        )
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "instructor_course_list")
        self.assertIn("หมายถึง", answer)
        self.assertIn("ประพงษ์", answer)

    def test_curriculum_language_followup_uses_context_for_course_code_lookup(self) -> None:
        result = structured_curriculum_lookup("บริบทก่อนหน้า: ภาษาญี่ปุ่น\nคำถามต่อเนื่อง: รหัสวิชา")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "lng_language_list")
        self.assertIn("ภาษาญี่ปุ่น", answer)
        self.assertIn("LNG", answer)

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

    def test_generalized_announcement_answer_handles_wrong_course_registration(self) -> None:
        answer = render_generalized_announcement_answer("หากลงทะเบียนผิดวิชา ต้องแก้ไขอย่างไร")
        self.assertIsNotNone(answer)
        self.assertIn("announcements", str(answer))
        self.assertIn("ลงทะเบียน", str(answer))
        self.assertIn("คำร้อง", str(answer))

    def test_regulations_form_followup_for_signers_stays_grounded(self) -> None:
        result = structured_regulations_lookup("บริบทก่อนหน้า: ขอเอกสารใบลากิจ\nคำถามต่อเนื่อง: ต้องให้ใครเซ็นบ้าง")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_lookup")
        self.assertIn("RO-16", answer)
        self.assertIn("ยังไม่พบการระบุ", answer)

    def test_regulations_form_followup_for_steps_mentions_known_and_unknown_parts(self) -> None:
        result = structured_regulations_lookup("บริบทก่อนหน้า: ขอเอกสารใบลากิจ\nคำถามต่อเนื่อง: มีขั้นตอนการยื่นเอกสารยังไงบ้าง")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_lookup")
        self.assertIn("RO-16", answer)
        self.assertIn("ขั้นตอนที่ยืนยันได้จากเอกสาร", answer)
        self.assertIn("ยังไม่ระบุชัด", answer)

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

    def test_structured_regulations_lookup_returns_specific_resignation_form(self) -> None:
        result = structured_regulations_lookup("ใบลาออก")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_lookup")
        self.assertIn("RO-13Updated.pdf", answer)
        self.assertNotIn("service/form/]", answer)

    def test_structured_regulations_lookup_returns_specific_sick_business_leave_form(self) -> None:
        result = structured_regulations_lookup("ขอใบลากิจ")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_lookup")
        self.assertIn("RO-16.pdf", answer)
        self.assertNotIn("service/form/]", answer)

    def test_structured_regulations_lookup_returns_specific_general_request_form(self) -> None:
        result = structured_regulations_lookup("คำร้องทั่วไปใช้ทำอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_lookup")
        self.assertIn("RO-01.pdf", answer)
        self.assertIn("ยื่นคำร้องทั่วไป", answer)

    def test_structured_regulations_lookup_matches_form_code_directly(self) -> None:
        result = structured_regulations_lookup("RO-26 ใช้ทำอะไร")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_lookup")
        self.assertIn("RO-26Updated.pdf", answer)
        self.assertIn("เพิ่ม ลด ถอนรายวิชา", answer)

    def test_structured_regulations_lookup_returns_catalog_instead_of_forbidden_directory(self) -> None:
        result = structured_regulations_lookup("มีแบบฟอร์มอะไรบ้าง")
        answer = str(result.get("answer") or "")
        self.assertEqual(result.get("lookup_mode"), "form_catalog")
        self.assertIn("RO-01", answer)
        self.assertIn("RO-26", answer)
        self.assertIn("RO-16.pdf", answer)


if __name__ == "__main__":
    unittest.main()
