import importlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
INGESTION_SERVICE_ROOT = REPO_ROOT / "services" / "ingestion-service"
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))


class TestAutoRagRuntime(unittest.TestCase):
    def test_rewrite_followup_uses_llm_json(self) -> None:
        import app.auto_rag as auto_rag  # noqa: E402

        old_generate = auto_rag.generate_text
        try:
            auto_rag.generate_text = lambda *args, **kwargs: (
                '{"standalone_question":"รหัสวิชาของรายวิชาภาษาญี่ปุ่นคืออะไร","is_followup":true,"entities":{"language":"ภาษาญี่ปุ่น"},"confidence":0.93}'
            )
            result = auto_rag.rewrite_followup_with_llm(
                "รหัสวิชา",
                [
                    {"role": "user", "content": "ภาษาญี่ปุ่น"},
                    {"role": "assistant", "content": "..."},
                    {"role": "user", "content": "รหัสวิชา"},
                ],
                "curriculum",
            )
        finally:
            auto_rag.generate_text = old_generate

        self.assertIn("รหัสวิชาของรายวิชาภาษาญี่ปุ่นคืออะไร", result["standalone_question"])
        self.assertTrue(result["is_followup"])
        self.assertGreaterEqual(float(result["confidence"]), 0.9)

    def test_retrieval_planner_uses_llm_json(self) -> None:
        import app.auto_rag as auto_rag  # noqa: E402

        old_generate = auto_rag.generate_text
        try:
            auto_rag.generate_text = lambda *args, **kwargs: (
                '{"intent":"form_lookup","search_queries":["RO-16 ลาป่วย ลากิจ","ใบลากิจ RO-16"],'
                '"preferred_domains":["regulations"],"needed_evidence":["form_code","purpose","link"],"answer_type":"procedure"}'
            )
            result = auto_rag.plan_retrieval_with_llm("ถ้าต้องการลาป่วยต้องทำไง", "regulations")
        finally:
            auto_rag.generate_text = old_generate

        self.assertEqual(result["intent"], "form_lookup")
        self.assertEqual(result["preferred_domains"], ["regulations"])
        self.assertIn("RO-16", " ".join(result["search_queries"]))

    def test_retrieval_planner_includes_document_profiles_in_prompt_context(self) -> None:
        import app.auto_rag as auto_rag  # noqa: E402

        old_generate = auto_rag.generate_text
        old_profiles = auto_rag.summarize_document_profiles
        captured = {}
        try:
            auto_rag.summarize_document_profiles = lambda *args, **kwargs: {
                "curriculum": [{"source_name": "teacher_profiles_by_course.csv", "doc_type": "teacher_profile_csv"}]
            }
            def fake_generate(prompt, messages=None, **kwargs):
                captured["content"] = (messages or [{}])[-1].get("content", "")
                return '{"intent":"contact_lookup","search_queries":["CPE101 ติดต่ออาจารย์"],"preferred_domains":["curriculum"],"needed_evidence":["email","phone"],"answer_type":"contact"}'
            auto_rag.generate_text = fake_generate
            result = auto_rag.plan_retrieval_with_llm("ติดต่ออาจารย์ CPE101", "curriculum")
        finally:
            auto_rag.generate_text = old_generate
            auto_rag.summarize_document_profiles = old_profiles

        self.assertEqual(result["intent"], "contact_lookup")
        self.assertIn("teacher_profile_csv", captured.get("content", ""))

    def test_evidence_verifier_fallback_detects_no_overlap(self) -> None:
        import app.auto_rag as auto_rag  # noqa: E402

        result = auto_rag.verify_evidence_with_llm(
            "ภาษาญี่ปุ่น รหัสวิชาอะไร",
            [{"source": "foo.txt", "text": "ภาษาจีนกลาง 1 LNG 275"}],
        )

        self.assertIn(result["support_level"], ("none", "weak"))
        self.assertIn(result["safe_answer_strategy"], ("say_not_found", "answer_with_caveat"))

    def test_structured_memory_tracks_course_form_and_language(self) -> None:
        import app.auto_rag as auto_rag  # noqa: E402

        state = auto_rag.extract_structured_memory(
            "ถ้าจะลง 22 หน่วยกิตต้องใช้ RO-18 ไหม",
            [
                {"role": "user", "content": "ภาษาญี่ปุ่น"},
                {"role": "assistant", "content": "..."},
            ],
        )

        self.assertEqual(state.get("last_language"), "ภาษาญี่ปุ่น")
        self.assertEqual(state.get("last_form"), "RO-18")

    def test_structured_memory_tracks_response_style_preference(self) -> None:
        import app.auto_rag as auto_rag  # noqa: E402

        short_state = auto_rag.extract_structured_memory("ขอสรุปสั้นๆ เรื่องถอนรายวิชา", [])
        detailed_state = auto_rag.extract_structured_memory("อธิบายละเอียดหน่อยเรื่อง RO-16", [])

        self.assertEqual(short_state.get("preferred_response_style"), "short")
        self.assertEqual(detailed_state.get("preferred_response_style"), "detailed")

    def test_answer_policy_builds_chatgpt_notebook_style_messages(self) -> None:
        import app.answer_policy as answer_policy  # noqa: E402

        msgs = answer_policy.build_answer_messages(
            original_question="รหัสวิชา",
            standalone_question="รหัสวิชาของรายวิชาภาษาญี่ปุ่นคืออะไร",
            retrieval_prompt="คำถาม: ...",
            intent="course_lookup",
            verdict={"support_level": "partial"},
            structured_state={"last_language": "ภาษาญี่ปุ่น"},
        )

        self.assertEqual(len(msgs), 2)
        self.assertIn("NotebookLM", msgs[0]["content"])
        self.assertIn("ภาษาญี่ปุ่น", msgs[1]["content"])

    def test_followup_guard_keeps_self_contained_total_credit_question(self) -> None:
        import app.main as main  # noqa: E402
        import app.auto_rag as auto_rag  # noqa: E402

        old_rewrite = main.rewrite_followup_with_llm
        try:
            main.rewrite_followup_with_llm = lambda *args, **kwargs: {
                "standalone_question": "ภาคการศึกษาที่ 2/2568 จำนวนหน่วยกิตรวมทั้งหมดที่จำเป็นต้องเรียนคือเท่าไร",
                "is_followup": True,
                "entities": {"term": "2/2568"},
                "confidence": 0.98,
                "source": "llm",
            }
            rewritten, meta = main._apply_auto_followup_rewrite(
                "ต้องการทราบจำนวนหน่วยกิตรวมทั้งหมดที่จำเป็นต้องเรียน",
                "curriculum",
                [{"role": "user", "content": "เทอม 2/2568 ปิดเทอมวันไหน"}],
                structured_state={"last_term": "2/2568"},
            )
        finally:
            main.rewrite_followup_with_llm = old_rewrite

        self.assertEqual(rewritten, "ต้องการทราบจำนวนหน่วยกิตรวมทั้งหมดที่จำเป็นต้องเรียน")
        self.assertFalse(meta.get("is_followup"))
        self.assertIn("guarded_standalone", str(meta.get("source") or ""))

    def test_announcement_fast_answer_handles_term2_close(self) -> None:
        import app.announcement_deterministic as ann  # noqa: E402

        answer = ann.render_fast_announcement_calendar_answer("เทอม 2/2568 ปิดเทอมวันไหน")
        self.assertIsNotNone(answer)
        self.assertIn("30 พฤษภาคม 2569", answer or "")
        self.assertIn("ภาคการศึกษาที่ 2/2568", answer or "")

    def test_announcement_generalized_answer_explains_w_in_transcript(self) -> None:
        import app.announcement_deterministic as ann  # noqa: E402

        answer = ann.render_generalized_announcement_answer("w ใน transcript คืออะไร")
        self.assertIsNotNone(answer)
        self.assertIn("W (Withdrawn)", answer or "")
        self.assertIn("Transcript", answer or "")

    def test_calculator_routes_to_exam_policy(self) -> None:
        import app.routing as routing  # noqa: E402

        self.assertEqual(routing.classify_intent("เครื่องคิดเลขแบบไหนที่ใช้เข้าห้องสอบได้"), "exam_policy")
        self.assertEqual(routing.infer_domain("เครื่องคิดเลขแบบไหนที่ใช้เข้าห้องสอบได้"), "regulations")

    def test_smalltalk_routes_cleanly(self) -> None:
        import app.routing as routing  # noqa: E402

        self.assertEqual(routing.classify_intent("สวัสดี"), "smalltalk")
        self.assertEqual(routing.classify_intent("คุณเป็นใคร"), "smalltalk")

    def test_smalltalk_help_examples_answer_lists_practical_examples(self) -> None:
        import app.main as main  # noqa: E402

        answer = main._build_smalltalk_answer("ถามอะไรได้บ้าง")
        self.assertIn("ตัวอย่าง", answer)
        self.assertIn("RO-16", answer)
        self.assertIn("เครื่องคิดเลข", answer)


class TestFactIndexArtifacts(unittest.TestCase):
    def _reload_ingestion_structured(self, domain: str):
        old_domain = os.environ.get("CPE_DOMAIN")
        os.environ["CPE_DOMAIN"] = domain
        saved_modules = {k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")}
        for key in list(saved_modules.keys()):
            sys.modules.pop(key, None)
        sys.path.insert(0, str(INGESTION_SERVICE_ROOT))
        import app.structured_artifacts as ingest_structured  # type: ignore  # noqa: E402

        ingest_structured = importlib.reload(ingest_structured)
        return ingest_structured, old_domain, saved_modules

    def _restore_ingestion_structured(self, old_domain: str | None, saved_modules: dict[str, object]) -> None:
        if sys.path and sys.path[0] == str(INGESTION_SERVICE_ROOT):
            sys.path.pop(0)
        for key in list(sys.modules.keys()):
            if key == "app" or key.startswith("app."):
                sys.modules.pop(key, None)
        sys.modules.update(saved_modules)
        if old_domain is None:
            os.environ.pop("CPE_DOMAIN", None)
        else:
            os.environ["CPE_DOMAIN"] = old_domain

    def test_ingestion_builds_regulation_fact_index_from_forms(self) -> None:
        ingest_structured, old_domain, saved_modules = self._reload_ingestion_structured("regulations")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                forms = root / "forms.txt"
                forms.write_text(
                    "ชื่อเอกสาร: คำร้องขอลาป่วย/ลากิจ\n"
                    "รายละเอียด: ใช้เมื่อไม่สามารถเข้าเรียนได้ชั่วคราวเนื่องจากป่วยหรือต้องทำธุระส่วนตัว\n"
                    "ลิงก์: http://regis.kmutt.ac.th/service/form/RO-16.pdf\n",
                    encoding="utf-8",
                )
                artifact = ingest_structured._build_fact_index([forms])
                profiles = ingest_structured._build_document_profiles([forms])
        finally:
            self._restore_ingestion_structured(old_domain, saved_modules)

        facts = list(artifact.get("facts") or [])
        self.assertTrue(any(f.get("entity_type") == "form" and f.get("form_code") == "RO-16" for f in facts))
        self.assertTrue(any(f.get("entity_type") == "procedure" for f in facts))
        self.assertEqual(profiles["profiles"][0]["doc_type"], "form_directory")

    def test_ingestion_extracts_curriculum_course_blocks_and_teacher_profiles(self) -> None:
        ingest_structured, old_domain, saved_modules = self._reload_ingestion_structured("curriculum")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                lng = root / "lng.txt"
                lng.write_text(
                    "LNG 220 Academic English 3 (3-0-6)\n"
                    "(ภาษาอังกฤษเชิงวิชาการ)\n"
                    "Pre-requisite LNG 120 General English\n"
                    "The course aims at developing English communication skills.\n"
                    "รายวิชามุ่งเน้นพัฒนาทักษะภาษาอังกฤษเพื่อการสื่อสาร\n"
                    "ผลลัพธ์การเรียนรู้ (Learning Outcomes)\n",
                    encoding="utf-8",
                )
                csv_path = root / "teacher_profiles_by_course.csv"
                csv_path.write_text(
                    "name,teaching_part,level,course_code,course_title_th,credits\n"
                    "ผศ.ดร. จุมพล พลวิชัย,ภาระงานสอนในหลักสูตรนี้,ปริญญาตรี,CPE 101,เปิดโลกวิศวกรรมศาสตร์,3\n",
                    encoding="utf-8",
                )
                artifact = ingest_structured._build_fact_index([lng, csv_path])
        finally:
            self._restore_ingestion_structured(old_domain, saved_modules)

        facts = list(artifact.get("facts") or [])
        course = next((f for f in facts if f.get("entity_type") == "course" and f.get("course_code") == "LNG 220"), None)
        self.assertIsNotNone(course)
        self.assertEqual(course.get("course_name_th"), "ภาษาอังกฤษเชิงวิชาการ")
        self.assertEqual(course.get("prerequisites"), "LNG 120 General English")
        instructor = next((f for f in facts if f.get("entity_type") == "course_instructor" and f.get("course_code") == "CPE 101"), None)
        self.assertIsNotNone(instructor)
        self.assertIn("จุมพล พลวิชัย", str(instructor.get("person_name") or ""))

    def test_ingestion_dedupes_courses_across_curriculum_files(self) -> None:
        ingest_structured, old_domain, saved_modules = self._reload_ingestion_structured("curriculum")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                a = root / "a.txt"
                b = root / "b.txt"
                shared = (
                    "LNG 220 Academic English 3 (3-0-6)\n"
                    "(ภาษาอังกฤษเชิงวิชาการ)\n"
                    "Pre-requisite LNG 120 General English\n"
                )
                a.write_text(shared, encoding="utf-8")
                b.write_text(shared + "รายวิชามุ่งเน้นพัฒนาทักษะภาษาอังกฤษเพื่อการสื่อสาร\n", encoding="utf-8")
                artifact = ingest_structured._build_fact_index([a, b])
        finally:
            self._restore_ingestion_structured(old_domain, saved_modules)

        courses = [f for f in list(artifact.get("facts") or []) if f.get("entity_type") == "course" and f.get("course_code") == "LNG 220"]
        self.assertEqual(len(courses), 1)

    def test_ingestion_extracts_regulation_contacts(self) -> None:
        ingest_structured, old_domain, saved_modules = self._reload_ingestion_structured("regulations")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                contacts = root / "contacts.txt"
                contacts.write_text(
                    "SOURCE: kmutt_all_boards\nTYPE: contact\n\n"
                    "ชื่อ: ผศ. ดร. ประพงษ์ ใจดี\n"
                    "โทร: 02-470-9999\n"
                    "อีเมล: prapong.jai@kmutt.ac.th\n"
                    "\n========================================\n",
                    encoding="utf-8",
                )
                artifact = ingest_structured._build_fact_index([contacts])
        finally:
            self._restore_ingestion_structured(old_domain, saved_modules)

        facts = list(artifact.get("facts") or [])
        contact = next((f for f in facts if f.get("entity_type") == "person_contact"), None)
        self.assertIsNotNone(contact)
        self.assertEqual(contact.get("phone"), "02-470-9999")
        self.assertEqual(contact.get("email"), "prapong.jai@kmutt.ac.th")

    def test_ingestion_extracts_announcement_procedure_and_form(self) -> None:
        ingest_structured, old_domain, saved_modules = self._reload_ingestion_structured("announcements")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                announcement = root / "calendar.txt"
                announcement.write_text(
                    "📢 แจ้งเตือนกำหนดการลดรายวิชา\n"
                    "โมดูล 5 สัปดาห์ ช่วงที่ 1 ภาคการศึกษาที่ 2/2568\n"
                    "ระหว่าง วันเสาร์ที่ 24 มกราคม 2569 – วันศุกร์ที่ 6 กุมภาพันธ์ 2569\n"
                    "นักศึกษาที่ประสงค์จะลดรายวิชา\n"
                    "ให้ยื่น คำร้องลดรายวิชา สทน.26 หรือ สทน.27\n"
                    "Download คำร้อง\n"
                    "สทน.26 https://regis.kmutt.ac.th/service/form/RO-26Updated.pdf\n"
                    "การถอนรายวิชาในช่วงเวลาดังกล่าวจะได้รับผลการประเมินเป็น “W” (Withdrawn)\n"
                    "🔹 ขั้นตอนการถอนรายวิชาออนไลน์ผ่านระบบ 🔸\n"
                    "1) เข้าสู่ระบบ https://sinfo.kmutt.ac.th/\n"
                    "2) เลือกเมนู คำร้องผ่านเว็บ\n"
                    "3) เลือก ยื่นคำร้องถอนรายวิชา\n",
                    encoding="utf-8",
                )
                artifact = ingest_structured._build_fact_index([announcement])
        finally:
            self._restore_ingestion_structured(old_domain, saved_modules)

        facts = list(artifact.get("facts") or [])
        self.assertTrue(any(f.get("entity_type") == "form" and f.get("form_code") == "สทน.26" for f in facts))
        self.assertTrue(any(f.get("entity_type") == "procedure" and "ถอนรายวิชาออนไลน์" in str(f.get("action_name") or "") for f in facts))
        self.assertTrue(any(f.get("entity_type") == "regulation" and "Withdrawn" in str(f.get("rule_summary") or "") for f in facts))
        events = [f for f in facts if f.get("entity_type") == "calendar_event"]
        self.assertTrue(events)
        self.assertEqual(events[0].get("term"), "2/2568")
        self.assertEqual(events[0].get("academic_year"), "2568")
        self.assertTrue(any(f.get("start_date") for f in events))

    def test_ingestion_parses_thai_date_range_with_missing_second_month(self) -> None:
        ingest_structured, old_domain, saved_modules = self._reload_ingestion_structured("announcements")
        try:
            fields = ingest_structured._extract_date_range_fields("ระหว่าง 24 มกราคม - 6 กุมภาพันธ์ 2569")
        finally:
            self._restore_ingestion_structured(old_domain, saved_modules)

        self.assertEqual(fields["start_date"], "2026-01-24")
        self.assertEqual(fields["end_date"], "2026-02-06")

    def test_runtime_fact_search_reads_artifact(self) -> None:
        import app.structured_artifacts as rag_structured  # noqa: E402

        old_root = rag_structured.ROOT_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                art_dir = root / "indexes" / "curriculum" / "structured"
                art_dir.mkdir(parents=True, exist_ok=True)
                (art_dir / "fact_index.json").write_text(
                    '{"domain":"curriculum","kind":"fact_index","facts":['
                    '{"entity_type":"course","source_doc":"lng.txt","source":"lng.txt","page":1,'
                    '"evidence_text":"LNG 272 ภาษาญี่ปุ่น 1 3 (3-0-6)",'
                    '"confidence":0.95,"course_code":"LNG 272","course_name":"ภาษาญี่ปุ่น 1",'
                    '"credits":"3 (3-0-6)","blob":"LNG 272 ภาษาญี่ปุ่น 1 Japanese"}]}',
                    encoding="utf-8",
                )
                rag_structured.ROOT_DIR = root
                rag_structured.load_fact_index_artifact.cache_clear()
                rows = rag_structured.search_fact_index("ภาษาญี่ปุ่น รหัสวิชา", domains=["curriculum"], limit=3)
        finally:
            rag_structured.ROOT_DIR = old_root
            rag_structured.load_fact_index_artifact.cache_clear()

        self.assertTrue(rows)
        self.assertEqual(rows[0]["domain"], "curriculum")
        self.assertIn("LNG 272", str(rows[0].get("text") or ""))

    def test_runtime_loads_document_profiles_summary(self) -> None:
        import app.structured_artifacts as rag_structured  # noqa: E402

        old_root = rag_structured.ROOT_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                art_dir = root / "indexes" / "regulations" / "structured"
                art_dir.mkdir(parents=True, exist_ok=True)
                (art_dir / "document_profiles.json").write_text(
                    json.dumps(
                        {
                            "domain": "regulations",
                            "kind": "document_profiles",
                            "profiles": [
                                {
                                    "source_name": "forms.txt",
                                    "doc_type": "form_directory",
                                    "semantic_chunk_strategy": "regulation_template",
                                    "extractor_profile": "form_blocks",
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                rag_structured.ROOT_DIR = root
                rag_structured.load_document_profiles_artifact.cache_clear()
                summary = rag_structured.summarize_document_profiles(["regulations"])
        finally:
            rag_structured.ROOT_DIR = old_root
            rag_structured.load_document_profiles_artifact.cache_clear()

        self.assertIn("regulations", summary)
        self.assertEqual(summary["regulations"][0]["doc_type"], "form_directory")

    def test_runtime_fact_search_boosts_contact_facts_for_contact_intent(self) -> None:
        import app.structured_artifacts as rag_structured  # noqa: E402

        old_root = rag_structured.ROOT_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                art_dir = root / "indexes" / "curriculum" / "structured"
                art_dir.mkdir(parents=True, exist_ok=True)
                (art_dir / "fact_index.json").write_text(
                    json.dumps(
                        {
                            "domain": "curriculum",
                            "kind": "fact_index",
                            "facts": [
                                {
                                    "entity_type": "course",
                                    "source_doc": "cpe.txt",
                                    "source": "cpe.txt",
                                    "page": 1,
                                    "evidence_text": "CPE 101 เปิดโลกวิศวกรรมศาสตร์ 3 หน่วยกิต",
                                    "confidence": 0.95,
                                    "course_code": "CPE 101",
                                    "course_name": "เปิดโลกวิศวกรรมศาสตร์",
                                    "blob": "CPE 101 เปิดโลกวิศวกรรมศาสตร์ 3 หน่วยกิต",
                                },
                                {
                                    "entity_type": "person_contact",
                                    "source_doc": "contact.txt",
                                    "source": "contact.txt",
                                    "page": 1,
                                    "evidence_text": "ผศ.ดร. จุมพล พลวิชัย อีเมล jumpol@example.com โทร 02-470-1111",
                                    "confidence": 0.85,
                                    "person_name": "ผศ.ดร. จุมพล พลวิชัย",
                                    "email": "jumpol@example.com",
                                    "phone": "02-470-1111",
                                    "blob": "ผศ.ดร. จุมพล พลวิชัย อีเมล jumpol@example.com โทร 02-470-1111 CPE 101",
                                },
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                rag_structured.ROOT_DIR = root
                rag_structured.load_fact_index_artifact.cache_clear()
                rows = rag_structured.search_fact_index(
                    "ติดต่อ CPE101 ยังไง",
                    domains=["curriculum"],
                    limit=3,
                    intent="contact_lookup",
                    needed_evidence=["email", "phone"],
                )
        finally:
            rag_structured.ROOT_DIR = old_root
            rag_structured.load_fact_index_artifact.cache_clear()

        self.assertTrue(rows)
        self.assertEqual(rows[0]["metadata"]["entity_type"], "person_contact")


if __name__ == "__main__":
    unittest.main()
