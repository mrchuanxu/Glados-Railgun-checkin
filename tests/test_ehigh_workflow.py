import re
import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "ehighCheck.yml"
EXPECTED_SECRET = "EHI_CONFIG"
LEGACY_SECRETS = {
    "EHI_TOKEN",
    "EHI_APP_IDENTITY",
    "EHI_AUTHORIZATION",
    "EHI_CONTENT_MD5",
    "EHI_NONCESTR",
    "EHI_REQUEST_ROOT_ID",
    "EHI_REQUEST_BODY",
    "EHI_COOKIE",
}


def extract_indented_block(text, header, indent):
    lines = text.splitlines(keepends=True)
    header_line = f"{' ' * indent}{header}:"
    starts = [index for index, line in enumerate(lines) if line.rstrip() == header_line]
    if len(starts) != 1:
        raise AssertionError(f"Expected one {header!r} block, found {len(starts)}")

    block = []
    for line in lines[starts[0] + 1 :]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            line_indent = len(line) - len(line.lstrip(" "))
            if line_indent <= indent:
                break
        block.append(line)
    return "".join(block)


def extract_named_steps(text):
    matches = list(re.finditer(r"(?m)^    - name: ([^\n]+)\n", text))
    return {
        match.group(1): text[
            match.start() : next_match.start() if next_match else len(text)
        ]
        for match, next_match in zip(matches, matches[1:] + [None])
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
        permissions = extract_indented_block(self.workflow, "permissions", 0)
        effective_permissions = [
            line.rstrip()
            for line in permissions.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        checkin_job = extract_indented_block(self.workflow, "checkin", 2)

        self.assertEqual(effective_permissions, ["  contents: read"])
        self.assertNotRegex(checkin_job, r"(?m)^    permissions:\s*$")
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

    def test_checkout_does_not_persist_credentials(self):
        self.assertRegex(
            self.workflow,
            r"(?m)^    - name: Checkout code\n"
            r"      uses: actions/checkout@v6\n"
            r"      with:\n"
            r"        persist-credentials: false$",
        )

    def test_checkin_job_has_display_name(self):
        self.assertRegex(
            self.workflow,
            r"(?m)^  checkin:\s*\n    name: 1hai checkin\s*$",
        )

    def test_installs_requests_with_current_python(self):
        self.assertIn("      run: python -m pip install requests\n", self.workflow)

    def test_only_checkin_step_receives_single_ehigh_secret(self):
        checkin_job = extract_indented_block(self.workflow, "checkin", 2)
        job_env = extract_indented_block(checkin_job, "env", 4)
        steps = extract_named_steps(self.workflow)
        self.assertIn("Run 1hai checkin", steps)

        checkin_env = extract_indented_block(steps["Run 1hai checkin"], "env", 6)
        env_lines = [
            line.rstrip()
            for line in checkin_env.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertEqual(
            env_lines,
            [f"        {EXPECTED_SECRET}: ${{{{ secrets.{EXPECTED_SECRET} }}}}"],
        )
        self.assertNotIn("secrets.", job_env)
        for name, step in steps.items():
            if name != "Run 1hai checkin":
                self.assertNotIn("secrets.", step)
        for legacy_name in LEGACY_SECRETS:
            self.assertNotIn(legacy_name, self.workflow)


if __name__ == "__main__":
    unittest.main()
