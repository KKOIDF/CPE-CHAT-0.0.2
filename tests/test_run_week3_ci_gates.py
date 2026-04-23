import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_week3_ci_gates.sh"


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class TestRunWeek3CIGates(unittest.TestCase):
    def _run_with_stubs(self, curl_mode: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            fakebin = tdp / "fakebin"
            fakebin.mkdir(parents=True, exist_ok=True)
            calls = tdp / "calls.log"

            _write_exec(
                fakebin / "curl",
                "#!/bin/bash\n"
                "if [[ \"${CURL_MODE:-success}\" == \"success\" ]]; then exit 0; fi\n"
                "exit 22\n",
            )

            _write_exec(fakebin / "sleep", "#!/bin/bash\nexit 0\n")

            _write_exec(
                fakebin / "bash",
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    if [[ "$1" == "scripts/run_canary_guard.sh" ]]; then
                      {
                        echo "CANARY LIMIT=${LIMIT:-} OUTPUT_PREFIX=${OUTPUT_PREFIX:-}"
                        echo "GATE_OVERALL_DROP_PCT=${GATE_OVERALL_DROP_PCT:-} GATE_PROTECTED_CATEGORIES=${GATE_PROTECTED_CATEGORIES:-}"
                        echo "PROD_MIN_ANSWER_HIT_RATE=${PROD_MIN_ANSWER_HIT_RATE:-} PROD_MAX_P95_LATENCY_MS=${PROD_MAX_P95_LATENCY_MS:-}"
                      } >> "${TEST_CALLS_LOG}"
                      exit 0
                    fi
                    exec /bin/bash "$@"
                    """
                ),
            )

            _write_exec(
                fakebin / "python3",
                textwrap.dedent(
                    """\
                    #!/bin/bash
                    if [[ "$1" == "scripts/check_eval_metric_sanity.py" ]]; then
                      echo "SANITY $*" >> "${TEST_CALLS_LOG}"
                      exit 0
                    fi
                    if [[ "$1" == "scripts/check_ranking_robustness.py" ]]; then
                      echo "ROBUSTNESS $*" >> "${TEST_CALLS_LOG}"
                      exit 0
                    fi
                    exec /usr/bin/python3 "$@"
                    """
                ),
            )

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{fakebin}:{env.get('PATH', '')}",
                    "TEST_CALLS_LOG": str(calls),
                    "CURL_MODE": curl_mode,
                    "HEALTH_RETRIES": "2",
                    "HEALTH_SLEEP_SEC": "0",
                    "FAST_LIMIT": "12",
                    "FULL_LIMIT": "40",
                    "FAST_OUTPUT_PREFIX": "qball_week3_fast_gate",
                    "FULL_OUTPUT_PREFIX": "qball_week3_full_gate",
                }
            )

            proc = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            log_text = calls.read_text(encoding="utf-8") if calls.exists() else ""
            proc.log_text = log_text  # type: ignore[attr-defined]
            return proc

    def test_health_failure_holds_and_skips_expensive_steps(self) -> None:
        proc = self._run_with_stubs(curl_mode="fail")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("CI_ROLLOUT_DECISION=hold", proc.stdout)
        self.assertNotIn("CANARY", proc.log_text)  # type: ignore[attr-defined]
        self.assertNotIn("SANITY", proc.log_text)  # type: ignore[attr-defined]
        self.assertNotIn("ROBUSTNESS", proc.log_text)  # type: ignore[attr-defined]

    def test_success_path_runs_fast_full_sanity_and_robustness(self) -> None:
        proc = self._run_with_stubs(curl_mode="success")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[week3-ci] completed", proc.stdout)

        log = proc.log_text  # type: ignore[attr-defined]
        self.assertEqual(log.count("CANARY"), 2)
        self.assertIn("CANARY LIMIT=12 OUTPUT_PREFIX=qball_week3_fast_gate", log)
        self.assertIn("CANARY LIMIT=40 OUTPUT_PREFIX=qball_week3_full_gate", log)
        self.assertIn("GATE_OVERALL_DROP_PCT=100", log)
        self.assertIn("GATE_PROTECTED_CATEGORIES=__fast_subset__", log)
        self.assertIn("PROD_MIN_ANSWER_HIT_RATE=0", log)
        self.assertIn("PROD_MAX_P95_LATENCY_MS=999999", log)
        self.assertIn("SANITY scripts/check_eval_metric_sanity.py --report-json qball_week3_full_gate.json", log)
        self.assertIn("ROBUSTNESS scripts/check_ranking_robustness.py --report-json qball_week3_full_gate.json", log)


if __name__ == "__main__":
    unittest.main()
