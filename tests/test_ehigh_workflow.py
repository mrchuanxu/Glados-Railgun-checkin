import re
import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "ehighCheck.yml"
EXPECTED_SECRETS = {
    "EHI_TOKEN",
    "EHI_APP_IDENTITY",
    "EHI_AUTHORIZATION",
    "EHI_CONTENT_MD5",
    "EHI_NONCESTR",
    "EHI_REQUEST_ROOT_ID",
    "EHI_REQUEST_BODY",
    "EHI_COOKIE",
}


class EhighWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW_PATH.exists(), f"Missing workflow: {WORKFLOW_PATH}")
        self.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_supports_manual_and_daily_beijing_0917_triggers(self):
        self.assertIn("name: 1hai auto checkin", self.workflow)
        self.assertRegex(self.workflow, r"(?m)^on:\s*$")
        self.assertRegex(self.workflow, r"(?m)^  workflow_dispatch:\s*$")
        self.assertEqual(
            re.findall(r"cron:\s*'([^']+)'", self.workflow),
            ["17 1 * * *"],
        )
        self.assertIn("    # UTC 01:17 = 北京时间 09:17\n", self.workflow)

    def test_has_restricted_permissions_and_dedicated_concurrency(self):
        self.assertRegex(
            self.workflow,
            r"(?ms)^permissions:\s*\n  contents: read\s*$",
        )
        self.assertRegex(
            self.workflow,
            r"(?ms)^concurrency:\s*\n  group: ehigh-checkin\s*\n"
            r"  cancel-in-progress: false\s*$",
        )
        self.assertIn("runs-on: ubuntu-latest", self.workflow)
        self.assertIn("FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true", self.workflow)
        self.assertIn("uses: actions/checkout@v6", self.workflow)
        self.assertIn("uses: actions/setup-python@v6", self.workflow)
        self.assertRegex(self.workflow, r"python-version:\s*['\"]?3\.13['\"]?")
        self.assertNotIn("GLADOS", self.workflow)
        self.assertNotIn("schedule_gate", self.workflow)
        self.assertNotIn("actions/cache", self.workflow)
        self.assertNotIn("set -x", self.workflow)

    def test_checkin_job_has_display_name(self):
        self.assertRegex(
            self.workflow,
            r"(?m)^  checkin:\s*\n    name: 1hai checkin\s*$",
        )

    def test_installs_requests_with_current_python(self):
        self.assertIn("      run: python -m pip install requests\n", self.workflow)

    def test_only_checkin_step_receives_exact_ehigh_secrets(self):
        steps = re.split(r"(?m)^\s{4}- name: ", self.workflow)[1:]
        checkin_steps = [step for step in steps if "python ehigh_checkin.py" in step]

        self.assertEqual(len(checkin_steps), 1)
        checkin_step = checkin_steps[0]
        env_keys = set(re.findall(r"(?m)^\s{8}([A-Z][A-Z0-9_]*):", checkin_step))
        secret_refs = re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", self.workflow)

        self.assertEqual(env_keys, EXPECTED_SECRETS)
        self.assertEqual(set(secret_refs), EXPECTED_SECRETS)
        self.assertEqual(len(secret_refs), len(EXPECTED_SECRETS))
        for step in steps:
            if step != checkin_step:
                self.assertNotRegex(step, r"(?m)^\s{6}env:\s*$")
                self.assertNotIn("secrets.", step)


if __name__ == "__main__":
    unittest.main()
