import importlib
import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INGESTION_SERVICE_ROOT = REPO_ROOT / "services" / "ingestion-service"
RAG_SERVICE_ROOT = REPO_ROOT / "services" / "rag-service"
if str(INGESTION_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(INGESTION_SERVICE_ROOT))
if str(RAG_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_ROOT))


class TestDocumentProfiles(unittest.TestCase):
    def _load_document_profiles_module(self):
        mod_path = INGESTION_SERVICE_ROOT / "app" / "document_profiles.py"
        spec = importlib.util.spec_from_file_location("ingestion_document_profiles_test", mod_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module

    def test_curriculum_mapping_table_prefers_table_aware_strategy(self) -> None:
        document_profiles = self._load_document_profiles_module()

        text = """
        ตารางแมป PLO กับรายวิชา
        | Course | PLO1 | PLO2 | 1A | 2B |
        | CPE 101 | X |  | X |  |
        | CPE 102 |  | X |  | X |
        """
        profile = document_profiles.infer_document_profile(
            "mapping.txt",
            text,
            domain_hint="curriculum",
        )

        self.assertEqual(profile["doc_type"], "mapping_table")
        self.assertEqual(profile["semantic_chunk_strategy"], "table_aware")

    def test_regulations_fee_table_prefers_table_aware_strategy(self) -> None:
        document_profiles = self._load_document_profiles_module()

        text = """
        อัตราค่าธรรมเนียม
        รายการ | จำนวนเงิน | หมายเหตุ
        ค่าลงทะเบียน | 12,000 บาท | ภาคปกติ
        ค่าประกัน | 500 บาท | ต่อปี
        """
        profile = document_profiles.infer_document_profile(
            "fees.txt",
            text,
            domain_hint="regulations",
        )

        self.assertEqual(profile["doc_type"], "fee_table")
        self.assertEqual(profile["semantic_chunk_strategy"], "table_aware")

    def test_announcement_calendar_prefers_table_aware_when_schedule_is_tabular(self) -> None:
        document_profiles = self._load_document_profiles_module()

        text = """
        ปฏิทินการศึกษา 2568
        ภาคการศึกษาที่ 1/2568
        วันที่ | กิจกรรม
        01/08/2568 | เปิดภาคการศึกษา
        05/08/2568 | เริ่มลงทะเบียน
        """
        profile = document_profiles.infer_document_profile(
            "calendar.txt",
            text,
            domain_hint="announcements",
        )

        self.assertEqual(profile["doc_type"], "academic_calendar")
        self.assertEqual(profile["semantic_chunk_strategy"], "table_aware")


class TestEvalFormatHelpers(unittest.TestCase):
    def test_expected_document_format_uses_profile_lookup(self) -> None:
        eval_mod = importlib.import_module("eval_retrieval_csv")

        fmt, extractor = eval_mod._expected_document_format(
            ["forms.txt"],
            "regulations",
            {
                "forms.txt": {
                    "domain": "regulations",
                    "doc_type": "form_directory",
                    "extractor_profile": "form_blocks",
                }
            },
        )

        self.assertEqual(fmt, "form_directory")
        self.assertEqual(extractor, "form_blocks")


if __name__ == "__main__":
    unittest.main()
