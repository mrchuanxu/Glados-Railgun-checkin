import re
import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "gladosCheck.yml"


class WorkflowScheduleTests(unittest.TestCase):
    def test_cron_window_is_exactly_noon_through_four_pm_beijing(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        expressions = re.findall(r"cron:\s*'([^']+)'", workflow)

        self.assertEqual(expressions, ["*/15 4-7 * * *", "0 8 * * *"])

        utc_minutes = [
            hour * 60 + minute
            for hour in range(4, 8)
            for minute in (0, 15, 30, 45)
        ]
        utc_minutes.append(8 * 60)
        beijing_minutes = [value + 8 * 60 for value in utc_minutes]

        self.assertEqual(beijing_minutes[0], 12 * 60)
        self.assertEqual(beijing_minutes[-1], 16 * 60)
        self.assertEqual(len(beijing_minutes), 17)
        self.assertNotIn(16 * 60 + 15, beijing_minutes)


if __name__ == "__main__":
    unittest.main()
