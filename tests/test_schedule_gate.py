import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from schedule_gate import BEIJING_TZ, GateDecision, decide, write_github_output


class ScheduleGateTests(unittest.TestCase):
    def setUp(self):
        self.noon = datetime(2026, 8, 2, 12, 0, tzinfo=BEIJING_TZ)

    def test_incomplete_day_runs_immediately(self):
        decision = decide(self.noon, None)

        self.assertTrue(decision.should_run)
        self.assertEqual(decision.beijing_date, "2026-08-02")

    def test_yesterday_completion_runs_immediately(self):
        decision = decide(self.noon, "2026-08-01")

        self.assertTrue(decision.should_run)

    def test_completed_day_never_runs_again(self):
        decision = decide(
            self.noon.astimezone(timezone.utc),
            "2026-08-02",
        )

        self.assertFalse(decision.should_run)

    def test_beijing_date_is_used_near_utc_boundary(self):
        utc_time = datetime(2026, 8, 2, 16, 30, tzinfo=timezone.utc)
        decision = decide(utc_time, "2026-08-02")

        self.assertTrue(decision.should_run)
        self.assertEqual(decision.beijing_date, "2026-08-03")

    def test_github_output_has_no_random_target(self):
        decision = GateDecision(True, "今天尚未完成，立即执行", "2026-08-02")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output"
            write_github_output(str(path), decision)
            content = path.read_text(encoding="utf-8")

        self.assertIn("should_run=true", content)
        self.assertIn("beijing_date=2026-08-02", content)
        self.assertNotIn("target_time", content)


if __name__ == "__main__":
    unittest.main()
