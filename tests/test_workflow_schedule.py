import re
import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "gladosCheck.yml"


class WorkflowScheduleTests(unittest.TestCase):
    def test_cron_is_staggered_from_noon_through_four_pm_beijing(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        expressions = re.findall(r"cron:\s*'([^']+)'", workflow)

        self.assertEqual(expressions, ["7,22,37,52 4-7 * * *", "0 8 * * *"])

        utc_minutes = [
            hour * 60 + minute
            for hour in range(4, 8)
            for minute in (7, 22, 37, 52)
        ]
        utc_minutes.append(8 * 60)
        beijing_minutes = [value + 8 * 60 for value in utc_minutes]

        self.assertEqual(beijing_minutes[0], 12 * 60 + 7)
        self.assertEqual(beijing_minutes[-2], 15 * 60 + 52)
        self.assertEqual(beijing_minutes[-1], 16 * 60)
        self.assertEqual(len(beijing_minutes), 17)
        self.assertNotIn(16 * 60 + 15, beijing_minutes)

    def test_workflow_logs_non_secret_schedule_diagnostics(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        diagnostics = workflow.split("- name: Show schedule diagnostics", 1)[1].split("- name:", 1)[0]

        self.assertIn("github.event_name", diagnostics)
        self.assertIn("github.event.schedule", diagnostics)
        self.assertIn("steps.state-cache.outputs.cache-matched-key", diagnostics)
        self.assertIn("date -u", diagnostics)
        self.assertIn("TZ=Asia/Shanghai date", diagnostics)
        self.assertNotIn("secrets.", diagnostics)
        self.assertNotIn("GLADOS_COOKIES", diagnostics)

    def test_workflow_keeps_run_history(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertNotIn("Mattraks/delete-workflow-runs", workflow)


if __name__ == "__main__":
    unittest.main()
