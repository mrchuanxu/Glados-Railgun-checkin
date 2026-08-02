import unittest
from datetime import datetime, timedelta, timezone

from schedule_gate import BEIJING_TZ, daily_target, decide


class ScheduleGateTests(unittest.TestCase):
    def setUp(self):
        self.noon = datetime(2026, 8, 2, 12, 0, tzinfo=BEIJING_TZ)

    def test_target_is_stable_and_inside_window(self):
        first = daily_target("owner/repository", self.noon)
        second = daily_target("owner/repository", self.noon + timedelta(hours=2))

        self.assertEqual(first, second)
        self.assertGreaterEqual((first.hour, first.minute), (12, 0))
        self.assertLessEqual((first.hour, first.minute), (17, 45))
        self.assertEqual(first.minute % 15, 0)

    def test_scheduled_run_waits_until_target(self):
        target = daily_target("owner/repository", self.noon)

        before = decide(target - timedelta(minutes=1), "schedule", "owner/repository", None)
        at_target = decide(target, "schedule", "owner/repository", None)

        self.assertFalse(before.should_run)
        self.assertTrue(at_target.should_run)

    def test_completed_day_never_runs_again(self):
        decision = decide(
            self.noon.astimezone(timezone.utc),
            "workflow_dispatch",
            "owner/repository",
            "2026-08-02",
        )

        self.assertFalse(decision.should_run)

    def test_manual_run_bypasses_target_time(self):
        early = datetime(2026, 8, 2, 8, 0, tzinfo=BEIJING_TZ)
        decision = decide(early, "workflow_dispatch", "owner/repository", None)

        self.assertTrue(decision.should_run)


if __name__ == "__main__":
    unittest.main()
