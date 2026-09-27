# 一嗨单 Secret 配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将一嗨签到从八个独立 GitHub Secrets 迁移为一个严格校验的 URL 编码 `EHI_CONFIG` Secret。

**Architecture:** `EhiConfig.from_env()` 只读取 `EHI_CONFIG`，先验证 percent-encoding，再使用标准库 `urllib.parse.parse_qsl` 解码固定八键配置，拒绝缺失、重复、未知和空必填字段。请求发送和响应处理保持不变；工作流仅向签到步骤注入一个 Secret，README 提供安全生成单行配置的方法。

**Tech Stack:** Python 3.13、标准库 `urllib.parse`/`re`/`unittest`、GitHub Actions YAML、`requests`

---

## File Structure

- Modify: `ehigh_checkin.py` - 将环境变量加载改为严格解析单个 `EHI_CONFIG`。
- Modify: `tests/test_ehigh_checkin.py` - 覆盖 URL 编码特殊字符、严格键校验、错误脱敏及现有请求行为。
- Modify: `.github/workflows/ehighCheck.yml` - 只向签到步骤注入 `secrets.EHI_CONFIG`。
- Modify: `tests/test_ehigh_workflow.py` - 将 Secret 作用域契约改为单 Secret。
- Modify: `README.md` - 说明单 Secret 格式、生成方法和迁移步骤。

### Task 1: Strict Single-Secret Parser

**Files:**
- Modify: `ehigh_checkin.py:1-60`
- Modify: `tests/test_ehigh_checkin.py:1-80`

- [ ] **Step 1: Replace the configuration fixtures and write failing success-path tests**

In `tests/test_ehigh_checkin.py`, add:

```python
from urllib.parse import urlencode
```

Replace `VALID_ENV` with:

```python
VALID_FIELDS = {
    "token": "fake-token",
    "app_identity": "fake-app-identity",
    "authorization": "fake-authorization",
    "content_md5": "fake-content-md5",
    "noncestr": "fake-nonce",
    "request_root_id": "fake-root-id",
    "request_body": "fake$request/body*",
    "cookie": "",
}
VALID_CONFIG = urlencode(VALID_FIELDS)
VALID_ENV = {"EHI_CONFIG": VALID_CONFIG}
```

Replace the configuration tests with tests equivalent to:

```python
class EhiConfigTests(unittest.TestCase):
    def test_loads_all_fields_from_single_secret(self):
        config = EhiConfig.from_env(VALID_ENV)

        self.assertEqual(config.token, "fake-token")
        self.assertEqual(config.app_identity, "fake-app-identity")
        self.assertEqual(config.authorization, "fake-authorization")
        self.assertEqual(config.content_md5, "fake-content-md5")
        self.assertEqual(config.noncestr, "fake-nonce")
        self.assertEqual(config.request_root_id, "fake-root-id")
        self.assertEqual(config.request_body, "fake$request/body*")
        self.assertIsNone(config.cookie)

    def test_key_order_does_not_matter(self):
        reversed_config = urlencode(list(reversed(tuple(VALID_FIELDS.items()))))

        self.assertEqual(
            EhiConfig.from_env({"EHI_CONFIG": reversed_config}),
            EhiConfig.from_env(VALID_ENV),
        )

    def test_url_encoded_special_characters_are_restored_verbatim(self):
        values = {
            **VALID_FIELDS,
            "request_body": "value&with=percent% plus+ space 中文",
            "cookie": "session=a&flag=1; note=中文 + %",
        }

        config = EhiConfig.from_env({"EHI_CONFIG": urlencode(values)})

        self.assertEqual(config.request_body, values["request_body"])
        self.assertEqual(config.cookie, values["cookie"])

    def test_empty_cookie_is_allowed_but_key_is_required(self):
        config = EhiConfig.from_env({"EHI_CONFIG": urlencode(VALID_FIELDS)})

        self.assertIsNone(config.cookie)

    def test_configuration_is_frozen(self):
        config = EhiConfig.from_env(VALID_ENV)

        with self.assertRaises(FrozenInstanceError):
            config.token = "replacement"
```

Update all later tests in this file to construct configuration through `VALID_ENV`. For the Cookie request test, use:

```python
config = EhiConfig.from_env(
    {"EHI_CONFIG": urlencode({**VALID_FIELDS, "cookie": "session=fake-cookie"})}
)
```

Update main-log tests so their secret loop uses `(VALID_CONFIG, *VALID_FIELDS.values())` rather than the old environment values.

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiConfigTests -v`

Expected: FAIL because `EhiConfig.from_env()` still expects the old eight environment variables.

- [ ] **Step 3: Implement the strict successful parser path**

In `ehigh_checkin.py`, add imports:

```python
import re
from urllib.parse import parse_qsl
```

Replace `REQUIRED_ENV` and `from_env` with:

```python
    CONFIG_ENV: ClassVar[str] = "EHI_CONFIG"
    REQUIRED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "token",
            "app_identity",
            "authorization",
            "content_md5",
            "noncestr",
            "request_root_id",
            "request_body",
            "cookie",
        }
    )
    NON_EMPTY_KEYS: ClassVar[frozenset[str]] = REQUIRED_KEYS - {"cookie"}

    @classmethod
    def from_env(cls, environment: Mapping[str, str] = os.environ) -> "EhiConfig":
        raw_config = environment.get(cls.CONFIG_ENV)
        if not raw_config:
            raise ConfigError(f"缺少环境变量: {cls.CONFIG_ENV}")

        if re.search(r"%(?![0-9A-Fa-f]{2})", raw_config):
            raise ConfigError("EHI_CONFIG URL 编码无效")

        try:
            pairs = parse_qsl(
                raw_config,
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
            )
        except (UnicodeDecodeError, ValueError) as error:
            raise ConfigError("EHI_CONFIG URL 编码无效") from None

        values = dict(pairs)
        return cls(
            token=values["token"],
            app_identity=values["app_identity"],
            authorization=values["authorization"],
            content_md5=values["content_md5"],
            noncestr=values["noncestr"],
            request_root_id=values["request_root_id"],
            request_body=values["request_body"],
            cookie=values["cookie"] or None,
        )
```

This step intentionally leaves strict key-set validation for the next red-green step; focused success tests should pass with all eight fields present.

- [ ] **Step 4: Run successful parser and request tests**

Run: `python -m unittest tests.test_ehigh_checkin.EhiConfigTests tests.test_ehigh_checkin.EhiRequestTests -v`

Expected: success-path configuration and existing request behavior tests PASS.

- [ ] **Step 5: Commit the successful single-secret parser**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: parse 1hai single secret config"
```

### Task 2: Strict Validation and Secret-Safe Errors

**Files:**
- Modify: `ehigh_checkin.py:24-80`
- Modify: `tests/test_ehigh_checkin.py:29-100`

- [ ] **Step 1: Write failing strict-validation tests**

Add these tests to `EhiConfigTests`:

```python
    def test_missing_or_empty_environment_fails(self):
        for environment in ({}, {"EHI_CONFIG": ""}):
            with self.subTest(environment=environment):
                with self.assertRaisesRegex(ConfigError, "缺少环境变量: EHI_CONFIG"):
                    EhiConfig.from_env(environment)

    def test_missing_key_names_only_the_key(self):
        for name in VALID_FIELDS:
            with self.subTest(name=name):
                fields = {key: value for key, value in VALID_FIELDS.items() if key != name}

                with self.assertRaisesRegex(ConfigError, f"缺少配置键: {name}") as context:
                    EhiConfig.from_env({"EHI_CONFIG": urlencode(fields)})

                self.assertNotIn(VALID_CONFIG, str(context.exception))

    def test_unknown_key_is_rejected(self):
        raw_config = urlencode({**VALID_FIELDS, "extra": "fake-extra-secret"})

        with self.assertRaisesRegex(ConfigError, "未知配置键: extra") as context:
            EhiConfig.from_env({"EHI_CONFIG": raw_config})

        self.assertNotIn("fake-extra-secret", str(context.exception))

    def test_duplicate_key_is_rejected(self):
        raw_config = f"{VALID_CONFIG}&token=second-fake-token"

        with self.assertRaisesRegex(ConfigError, "重复配置键: token") as context:
            EhiConfig.from_env({"EHI_CONFIG": raw_config})

        self.assertNotIn("second-fake-token", str(context.exception))

    def test_each_non_cookie_value_must_be_non_empty(self):
        for name in EhiConfig.NON_EMPTY_KEYS:
            with self.subTest(name=name):
                raw_config = urlencode({**VALID_FIELDS, name: ""})

                with self.assertRaisesRegex(ConfigError, f"配置值不能为空: {name}"):
                    EhiConfig.from_env({"EHI_CONFIG": raw_config})

    def test_invalid_form_or_percent_encoding_is_rejected_without_values(self):
        invalid_values = (
            "token",
            f"{VALID_CONFIG}&broken=%",
            f"{VALID_CONFIG}&broken=%ZZ",
            f"{VALID_CONFIG}&broken=%FF",
        )
        for raw_config in invalid_values:
            with self.subTest(raw_config=raw_config):
                with self.assertRaisesRegex(ConfigError, "EHI_CONFIG URL 编码无效") as context:
                    EhiConfig.from_env({"EHI_CONFIG": raw_config})

                self.assertNotIn(raw_config, str(context.exception))
```

Add a main-level test proving an invalid aggregate secret is not logged:

```python
    @patch("ehigh_checkin.requests.Session")
    def test_invalid_config_is_not_logged(self, session_class):
        aggregate_secret = f"{VALID_CONFIG}&token=duplicate-sensitive-value"

        with patch.dict("os.environ", {"EHI_CONFIG": aggregate_secret}, clear=True):
            with self.assertLogs("ehigh_checkin", level="ERROR") as captured:
                exit_code = main()

        output = "\n".join(captured.output)
        self.assertEqual(exit_code, 1)
        self.assertIn("重复配置键: token", output)
        self.assertNotIn(aggregate_secret, output)
        self.assertNotIn("duplicate-sensitive-value", output)
        session_class.assert_not_called()
```

- [ ] **Step 2: Run strict-validation tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiConfigTests tests.test_ehigh_checkin.EhiMainTests.test_invalid_config_is_not_logged -v`

Expected: FAIL because missing, duplicate, unknown and empty-value checks are not implemented.

- [ ] **Step 3: Implement deterministic strict validation**

After parsing `pairs` and before creating `values`, add:

```python
        seen = set()
        for key, _ in pairs:
            if key in seen:
                raise ConfigError(f"重复配置键: {key}")
            seen.add(key)

        unknown_keys = seen - cls.REQUIRED_KEYS
        if unknown_keys:
            name = sorted(unknown_keys)[0]
            raise ConfigError(f"未知配置键: {name}")

        missing_keys = cls.REQUIRED_KEYS - seen
        if missing_keys:
            name = sorted(missing_keys)[0]
            raise ConfigError(f"缺少配置键: {name}")

        values = dict(pairs)
        empty_keys = {name for name in cls.NON_EMPTY_KEYS if not values[name]}
        if empty_keys:
            name = sorted(empty_keys)[0]
            raise ConfigError(f"配置值不能为空: {name}")
```

Remove the earlier unvalidated `values = dict(pairs)`. Keep errors deterministic by sorting sets and never interpolate values.

- [ ] **Step 4: Run all one-hai script tests**

Run: `python -m unittest tests.test_ehigh_checkin -v`

Expected: all configuration, request, failure and main tests PASS.

- [ ] **Step 5: Run the complete test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with no network requests.

- [ ] **Step 6: Commit strict validation**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: validate 1hai single secret config"
```

### Task 3: Workflow Migration to One Secret

**Files:**
- Modify: `.github/workflows/ehighCheck.yml:33-43`
- Modify: `tests/test_ehigh_workflow.py:7-16,106-135`

- [ ] **Step 1: Write the failing one-secret workflow contract**

Replace `EXPECTED_SECRETS` with:

```python
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
```

Replace the Secret scope test with:

```python
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
            ["        EHI_CONFIG: ${{ secrets.EHI_CONFIG }}"],
        )
        self.assertNotIn("secrets.", job_env)
        for name, step in steps.items():
            if name != "Run 1hai checkin":
                self.assertNotIn("secrets.", step)
        for legacy_name in LEGACY_SECRETS:
            self.assertNotIn(legacy_name, self.workflow)
```

- [ ] **Step 2: Run the workflow test to verify it fails**

Run: `python -m unittest tests.test_ehigh_workflow.EhighWorkflowTests.test_only_checkin_step_receives_single_ehigh_secret -v`

Expected: FAIL because the workflow still references eight Secrets.

- [ ] **Step 3: Replace workflow environment variables**

Replace the `Run 1hai checkin` environment block in `.github/workflows/ehighCheck.yml` with:

```yaml
      env:
        EHI_CONFIG: ${{ secrets.EHI_CONFIG }}
```

Do not change scheduling, permissions, concurrency, action versions or commands.

- [ ] **Step 4: Run workflow and full tests**

Run: `python -m unittest tests.test_ehigh_workflow -v`

Expected: all workflow tests PASS.

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 5: Parse both workflow files**

Run: `ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |path| YAML.load_file(path) }; puts "all workflows valid"'`

Expected: prints `all workflows valid`.

- [ ] **Step 6: Commit the workflow migration**

```bash
git add .github/workflows/ehighCheck.yml tests/test_ehigh_workflow.py
git commit -m "ci: use one secret for 1hai config"
```

### Task 4: Documentation and Migration Guide

**Files:**
- Modify: `README.md:77-111`

- [ ] **Step 1: Replace the eight-Secret setup with the single-Secret format**

Replace the one-hai configuration subsection with content containing:

```markdown
将同一次请求的字段组合为一个 URL 编码键值串，并保存为 GitHub Actions repository secret `EHI_CONFIG`：

```text
token=<URL编码值>&app_identity=<URL编码值>&authorization=<URL编码值>&content_md5=<URL编码值>&noncestr=<URL编码值>&request_root_id=<URL编码值>&request_body=<URL编码值>&cookie=<URL编码值或空>
```

| 配置键 | 抓包字段 | 规则 |
|---|---|---|
| `token` | 请求头 `Token` | 必填 |
| `app_identity` | 请求头 `AppIdentity` | 必填 |
| `authorization` | 请求头 `Authorization` | 必填 |
| `content_md5` | 请求头 `ehiContent-MD5` | 必填 |
| `noncestr` | 请求头 `noncestr` | 必填 |
| `request_root_id` | 请求头 `x-ms-request-root-id` | 必填 |
| `request_body` | 未修改的原始请求体 | 必填 |
| `cookie` | 请求头 `Cookie` | 键必填，值可为空 |
```

Add this safe local generator, which prompts without echo and never writes a file:

```bash
python - <<'PY'
from getpass import getpass
from urllib.parse import urlencode

fields = (
    ("token", "Token"),
    ("app_identity", "AppIdentity"),
    ("authorization", "Authorization"),
    ("content_md5", "ehiContent-MD5"),
    ("noncestr", "noncestr"),
    ("request_root_id", "x-ms-request-root-id"),
    ("request_body", "原始请求体"),
    ("cookie", "Cookie（可留空）"),
)
values = {key: getpass(f"{label}: ") for key, label in fields}
print(urlencode(values))
PY
```

Document these exact operational rules:

- All fields must come from one `SignIn` request.
- Copy the generated single line as the value of Repository Secret `EHI_CONFIG`.
- Never paste captured values into repository files, Issues, logs or chat.
- `cookie` must be present; leave it empty for the initial no-Cookie test.
- When rotating credentials, regenerate and replace the entire `EHI_CONFIG`.
- Existing deployments should create `EHI_CONFIG`, manually verify the workflow/App result, then delete the eight legacy Secrets.
- The script does not read legacy Secrets.

Update runtime instructions to refer to empty `cookie` inside `EHI_CONFIG`, not `EHI_COOKIE`.

- [ ] **Step 2: Verify README documents the one-secret contract**

Run:

```bash
python -c 'from pathlib import Path; text=Path("README.md").read_text(); assert "`EHI_CONFIG`" in text; assert "urlencode(values)" in text; assert "cookie=" in text; assert "脚本不会读取旧" in text; print("single-secret docs present")'
```

Expected: prints `single-secret docs present`.

- [ ] **Step 3: Verify legacy Secret names are absent from active code and README**

Run:

```bash
git grep -n -E 'EHI_(TOKEN|APP_IDENTITY|AUTHORIZATION|CONTENT_MD5|NONCESTR|REQUEST_ROOT_ID|REQUEST_BODY|COOKIE)' -- ehigh_checkin.py .github/workflows/ehighCheck.yml README.md tests/test_ehigh_checkin.py
```

Expected: exits 1 with no matches. `tests/test_ehigh_workflow.py` intentionally contains legacy names only to assert their absence from the workflow.

- [ ] **Step 4: Run full offline verification**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with no real network request.

Run: `git diff --check`

Expected: exits 0 with no output.

- [ ] **Step 5: Review and commit documentation**

Run: `git diff -- README.md`

Expected: only the one-hai Secret setup and migration instructions change.

```bash
git add README.md
git commit -m "docs: explain 1hai single secret setup"
```

### Task 5: Final Integration Verification

**Files:**
- Verify: `ehigh_checkin.py`
- Verify: `tests/test_ehigh_checkin.py`
- Verify: `.github/workflows/ehighCheck.yml`
- Verify: `tests/test_ehigh_workflow.py`
- Verify: `README.md`

- [ ] **Step 1: Run all tests and compile changed Python files**

Run:

```bash
python -m unittest discover -s tests -v && python -m py_compile ehigh_checkin.py tests/test_ehigh_checkin.py tests/test_ehigh_workflow.py
```

Expected: all tests PASS and compilation exits 0.

- [ ] **Step 2: Parse workflows and verify the only active one-hai Secret reference**

Run:

```bash
ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |path| YAML.load_file(path) }; puts "all workflows valid"'
```

Expected: prints `all workflows valid`.

Run:

```bash
git grep -n 'secrets.EHI_' -- .github/workflows
```

Expected: exactly one match, `.github/workflows/ehighCheck.yml` referencing `secrets.EHI_CONFIG`.

- [ ] **Step 3: Smoke-test safe failure with no configuration**

Run:

```bash
env -i PATH="$PATH" python ehigh_checkin.py
```

Expected: exits 1 and logs only `缺少环境变量: EHI_CONFIG`; no network request is made.

- [ ] **Step 4: Check final diff and worktree**

Run: `git diff --check master...HEAD`

Expected: exits 0.

Run: `git status --short`

Expected: no output.

- [ ] **Step 5: Defer live verification until a new aggregate Secret is configured**

Generate `EHI_CONFIG` from one newly captured request, configure it directly in GitHub, manually dispatch `1hai auto checkin`, and verify the App shows the same Beijing date as signed in with points increased. Do not paste the generated value into a terminal command, repository, Issue, PR or chat.

Expected: this external verification is performed only after credential rotation; it is not part of the offline test suite.

---

## Spec Coverage Self-Review

- Single Secret and no compatibility branch: Tasks 1 and 3 replace all active eight-variable reads and workflow references with `EHI_CONFIG` only.
- URL form parsing: Task 1 uses strict UTF-8 `parse_qsl`, preserves decoded values, accepts arbitrary key order and covers special characters.
- Strict validation: Task 2 covers missing/empty aggregate config, missing/unknown/duplicate keys, empty required values and malformed percent/UTF-8 encoding.
- Cookie rule: Tasks 1, 2 and 4 require the key, permit only its value to be empty, and preserve existing omission of the HTTP Cookie header when empty.
- Error secrecy: Task 2 asserts aggregate and field values never appear in exceptions or logs.
- Workflow scope: Task 3 permits exactly one Secret reference only in the check-in step while preserving schedule, permissions and checkout hardening.
- Documentation/migration: Task 4 supplies a no-file generator, whole-config rotation rules, legacy deletion sequence and no-fallback warning.
- Existing behavior: Tasks 1-5 retain request construction, response semantics, scheduling and the complete GLaDOS/Railgun test suite.
