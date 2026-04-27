import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "promote_request_logs_to_regression.py"


class TestPromoteRequestLogsToRegression(unittest.TestCase):
    def test_promotes_bad_requests_from_explicit_input_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs_dir = root / "exported" / "requests"
            out_dir = root / "out"
            logs_dir.mkdir(parents=True, exist_ok=True)
            payload = [
                {
                    "question": "LNG 220 มีวิชาบังคับก่อนอะไร",
                    "answer": "",
                    "answer_chars": 0,
                    "ctx_n": 0,
                    "domain": "curriculum",
                    "intent_primary": "prerequisite_lookup",
                    "total_ms": 3210,
                    "structured_path_miss_reason": "no_exact_match",
                },
                {
                    "question": "LNG 220 มีวิชาบังคับก่อนอะไร",
                    "answer": "empty response",
                    "answer_chars": 14,
                    "ctx_n": 0,
                    "domain": "curriculum",
                    "intent_primary": "prerequisite_lookup",
                    "total_ms": 2980,
                },
                {
                    "question": "ข้อ 12 ถ้ามาสายเกิน 15 นาทีต้องทำอย่างไร",
                    "answer": "สั้น",
                    "answer_chars": 3,
                    "ctx_n": 1,
                    "domain": "regulations",
                    "intent_primary": "exam_policy",
                    "total_ms": 1800,
                },
            ]
            (logs_dir / "requests_sample.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in payload) + "\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--input-dir",
                    str(root / "exported"),
                    "--request-log-dir",
                    "requests",
                    "--out-dir",
                    str(out_dir),
                    "--top-k",
                    "10",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("events_total=3", proc.stdout)
            self.assertIn("candidates_total=2", proc.stdout)

            json_reports = sorted(out_dir.glob("promoted_regression_candidates_*.json"))
            self.assertTrue(json_reports)

            report = json.loads(json_reports[-1].read_text(encoding="utf-8"))
            candidates = report.get("candidates") or []
            self.assertEqual(len(candidates), 2)
            top = candidates[0]
            self.assertEqual(top.get("question"), "LNG 220 มีวิชาบังคับก่อนอะไร")
            self.assertEqual(top.get("priority"), "P1")

    def test_expands_local_tracking_uri_into_mlflow_artifact_globs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            req_dir = root / "mlruns" / "123" / "abc" / "artifacts" / "requests"
            out_dir = root / "out"
            req_dir.mkdir(parents=True, exist_ok=True)
            (req_dir / "requests_sample.jsonl").write_text(
                json.dumps(
                    {
                        "question": "วันสุดท้ายของการชำระเงินคือวันไหน",
                        "answer": "timeout",
                        "answer_chars": 7,
                        "ctx_n": 0,
                        "domain": "announcements",
                        "intent_primary": "announcements_schedule",
                        "total_ms": 4567,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--tracking-uri",
                    str(root / "mlruns"),
                    "--out-dir",
                    str(out_dir),
                    "--top-k",
                    "5",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("events_total=1", proc.stdout)
            self.assertIn("candidates_total=1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
