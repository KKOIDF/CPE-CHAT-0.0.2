import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_eval_metric_sanity.py"


class TestCheckEvalMetricSanity(unittest.TestCase):
    def run_script(self, payload: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "report.json"
            report.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), "--report-json", str(report)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_passes_when_all_rate_metrics_in_range(self) -> None:
        payload = {
            "summary": {
                "overall_pass_rate": 1.0,
                "retrieval_mrr": 0.8,
                "citation_precision": 0.9,
                "citation_recall": 0.7,
                "by_category": {
                    "curriculum_fact_lookup": {
                        "retrieval_top_1_rate": 0.6,
                        "retrieval_top_3_rate": 1.0,
                    }
                },
                "by_domain": {
                    "curriculum": {
                        "retrieval_top_5_rate": 1.0,
                        "must_not_contain_pass_rate": 1.0,
                    }
                },
            }
        }

        proc = self.run_script(payload)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("METRIC SANITY PASSED", proc.stdout)

    def test_ignores_non_rate_fields_like_generation_latency(self) -> None:
        payload = {
            "summary": {
                "avg_generation_latency_ms": 1234.56,
                "median_generation_latency_ms": 321.0,
                "p95_generation_latency_ms": 9999.0,
                "overall_pass_rate": 0.5,
            }
        }

        proc = self.run_script(payload)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_fails_on_out_of_range_rate(self) -> None:
        payload = {
            "summary": {
                "overall_pass_rate": 1.2,
                "by_category": {},
                "by_domain": {},
            }
        }

        proc = self.run_script(payload)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("METRIC SANITY FAILED", proc.stdout)
        self.assertIn("summary.overall_pass_rate", proc.stdout)

    def test_fails_on_non_numeric_rate(self) -> None:
        payload = {
            "summary": {
                "overall_pass_rate": "abc",
            }
        }

        proc = self.run_script(payload)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("non-finite or non-numeric", proc.stdout)


if __name__ == "__main__":
    unittest.main()
