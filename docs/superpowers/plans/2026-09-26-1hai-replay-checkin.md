# 一嗨静态重放自动签到 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个使用 GitHub Secrets 原样重放已捕获请求的一嗨每日自动签到任务，并在不泄露凭据的前提下验证服务端是否接受请求。

**Architecture:** 使用独立的 `ehigh_checkin.py` 读取和校验配置、构造固定接口请求、检查 HTTP/JSON/`Result` 三层响应并输出脱敏摘要。独立 GitHub Actions 工作流每天北京时间 09:17 运行，不接入现有 GLaDOS 的状态、兑换或通知逻辑；所有测试通过 mock HTTP Session 离线执行。

**Tech Stack:** Python 3.13、`requests`、标准库 `dataclasses`/`hashlib`/`logging`/`unittest`、GitHub Actions YAML

---

## File Structure

- Create: `ehigh_checkin.py` - 一嗨环境配置、原始请求构造、响应校验、脱敏日志和 CLI 退出码。
- Create: `tests/test_ehigh_checkin.py` - 配置、请求字节、Cookie、成功与失败响应、网络异常及日志脱敏的离线测试。
- Create: `.github/workflows/ehighCheck.yml` - 独立的手动/每日定时一嗨签到工作流和 Secret 注入。
- Create: `tests/test_ehigh_workflow.py` - 工作流调度、权限、Secret 引用和隔离性测试。
- Modify: `README.md` - 一嗨抓包字段、Secrets、首次验证、失效更新和静态重放限制。

### Task 1: Typed Configuration

**Files:**
- Create: `ehigh_checkin.py`
- Create: `tests/test_ehigh_checkin.py`

- [ ] **Step 1: Write the failing configuration tests**

Create `tests/test_ehigh_checkin.py` with:

```python
import unittest

from ehigh_checkin import ConfigError, EhiConfig


VALID_ENV = {
    "EHI_TOKEN": "secret-token",
    "EHI_APP_IDENTITY": "secret-app-identity",
    "EHI_AUTHORIZATION": "secret-authorization",
    "EHI_CONTENT_MD5": "secret-content-md5",
    "EHI_NONCESTR": "secret-nonce",
    "EHI_REQUEST_ROOT_ID": "secret-root-id",
    "EHI_REQUEST_BODY": "encrypted$request/body*",
}


class EhiConfigTests(unittest.TestCase):
    def test_loads_required_values_and_omits_optional_cookie(self):
        config = EhiConfig.from_env(VALID_ENV)

        self.assertEqual(config.token, "secret-token")
        self.assertEqual(config.request_body, "encrypted$request/body*")
        self.assertIsNone(config.cookie)

    def test_preserves_optional_cookie_verbatim(self):
        environment = {**VALID_ENV, "EHI_COOKIE": "session=a; device=b"}

        self.assertEqual(EhiConfig.from_env(environment).cookie, "session=a; device=b")

    def test_each_missing_or_empty_required_value_fails_with_name_only(self):
        for name in EhiConfig.REQUIRED_ENV:
            with self.subTest(name=name):
                environment = {**VALID_ENV, name: ""}

                with self.assertRaisesRegex(ConfigError, f"缺少环境变量: {name}") as context:
                    EhiConfig.from_env(environment)

                self.assertNotIn("secret-", str(context.exception))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the configuration tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiConfigTests -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ehigh_checkin'`.

- [ ] **Step 3: Implement the minimal immutable configuration**

Create `ehigh_checkin.py` with:

```python
import os
from dataclasses import dataclass
from typing import ClassVar, Mapping, Optional, Tuple


class ConfigError(ValueError):
    """一嗨请求配置无效。"""


@dataclass(frozen=True)
class EhiConfig:
    token: str
    app_identity: str
    authorization: str
    content_md5: str
    noncestr: str
    request_root_id: str
    request_body: str
    cookie: Optional[str] = None

    REQUIRED_ENV: ClassVar[Tuple[str, ...]] = (
        "EHI_TOKEN",
        "EHI_APP_IDENTITY",
        "EHI_AUTHORIZATION",
        "EHI_CONTENT_MD5",
        "EHI_NONCESTR",
        "EHI_REQUEST_ROOT_ID",
        "EHI_REQUEST_BODY",
    )

    @classmethod
    def from_env(cls, environment: Mapping[str, str] = os.environ) -> "EhiConfig":
        for name in cls.REQUIRED_ENV:
            if not environment.get(name):
                raise ConfigError(f"缺少环境变量: {name}")

        return cls(
            token=environment["EHI_TOKEN"],
            app_identity=environment["EHI_APP_IDENTITY"],
            authorization=environment["EHI_AUTHORIZATION"],
            content_md5=environment["EHI_CONTENT_MD5"],
            noncestr=environment["EHI_NONCESTR"],
            request_root_id=environment["EHI_REQUEST_ROOT_ID"],
            request_body=environment["EHI_REQUEST_BODY"],
            cookie=environment.get("EHI_COOKIE") or None,
        )
```

Do not strip any value: the captured protocol fields and request body must remain byte-for-byte stable.

- [ ] **Step 4: Run the configuration tests to verify they pass**

Run: `python -m unittest tests.test_ehigh_checkin.EhiConfigTests -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit the typed configuration**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: add 1hai replay configuration"
```

### Task 2: Raw Request and Accepted Response

**Files:**
- Modify: `ehigh_checkin.py`
- Modify: `tests/test_ehigh_checkin.py`

- [ ] **Step 1: Write failing tests for raw request construction and accepted responses**

Add these imports at the top of `tests/test_ehigh_checkin.py`:

```python
import hashlib
from unittest.mock import Mock

from ehigh_checkin import perform_checkin
```

Replace the existing `from ehigh_checkin import ConfigError, EhiConfig` import with one combined import:

```python
from ehigh_checkin import ConfigError, EhiConfig, perform_checkin
```

Add this class before the `if __name__ == "__main__"` block:

```python
class EhiRequestTests(unittest.TestCase):
    def setUp(self):
        self.config = EhiConfig.from_env(VALID_ENV)
        self.session = Mock()
        self.response = Mock(status_code=200)
        self.response.json.return_value = {"Result": "encrypted-response"}
        self.session.post.return_value = self.response

    def test_posts_original_body_and_protocol_headers(self):
        perform_checkin(self.config, self.session)

        self.session.post.assert_called_once_with(
            "https://app.1hai.cn/SignCenter/UserAssets/SignIn",
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "AppVersion": "7431",
                "AppPlatform": "iPhone",
                "User-Agent": "%E4%B8%80%E5%97%A8%E7%A7%9F%E8%BD%A6/2904 CFNetwork/3860.700.2 Darwin/25.6.0",
                "Authorization": "secret-authorization",
                "ehiContent-MD5": "secret-content-md5",
                "noncestr": "secret-nonce",
                "x-ms-request-root-id": "secret-root-id",
                "Token": "secret-token",
                "AppIdentity": "secret-app-identity",
            },
            data=b"encrypted$request/body*",
            timeout=(10, 30),
        )

    def test_adds_cookie_only_when_configured(self):
        config = EhiConfig.from_env({**VALID_ENV, "EHI_COOKIE": "session=secret-cookie"})

        perform_checkin(config, self.session)

        headers = self.session.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Cookie"], "session=secret-cookie")

    def test_returns_only_safe_metadata_for_accepted_response(self):
        outcome = perform_checkin(self.config, self.session)

        self.assertEqual(outcome.status_code, 200)
        self.assertEqual(outcome.result_length, len("encrypted-response"))
        self.assertEqual(
            outcome.result_sha256,
            hashlib.sha256(b"encrypted-response").hexdigest(),
        )
        self.assertFalse(hasattr(outcome, "result"))
```

- [ ] **Step 2: Run the request tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiRequestTests -v`

Expected: FAIL because `perform_checkin` is not defined.

- [ ] **Step 3: Implement request construction and safe success metadata**

Add these imports to `ehigh_checkin.py`:

```python
import hashlib
from typing import Any, Dict
```

Add below `EhiConfig`:

```python
CHECKIN_URL = "https://app.1hai.cn/SignCenter/UserAssets/SignIn"
USER_AGENT = "%E4%B8%80%E5%97%A8%E7%A7%9F%E8%BD%A6/2904 CFNetwork/3860.700.2 Darwin/25.6.0"


@dataclass(frozen=True)
class CheckinOutcome:
    status_code: int
    result_length: int
    result_sha256: str


def _build_headers(config: EhiConfig) -> Dict[str, str]:
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "AppVersion": "7431",
        "AppPlatform": "iPhone",
        "User-Agent": USER_AGENT,
        "Authorization": config.authorization,
        "ehiContent-MD5": config.content_md5,
        "noncestr": config.noncestr,
        "x-ms-request-root-id": config.request_root_id,
        "Token": config.token,
        "AppIdentity": config.app_identity,
    }
    if config.cookie:
        headers["Cookie"] = config.cookie
    return headers


def perform_checkin(config: EhiConfig, session: Any) -> CheckinOutcome:
    response = session.post(
        CHECKIN_URL,
        headers=_build_headers(config),
        data=config.request_body.encode("utf-8"),
        timeout=(10, 30),
    )
    payload = response.json()
    result = payload["Result"]
    return CheckinOutcome(
        status_code=response.status_code,
        result_length=len(result),
        result_sha256=hashlib.sha256(result.encode("utf-8")).hexdigest(),
    )
```

- [ ] **Step 4: Run the request tests to verify they pass**

Run: `python -m unittest tests.test_ehigh_checkin.EhiRequestTests -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Run all one-hai script tests**

Run: `python -m unittest tests.test_ehigh_checkin -v`

Expected: 6 tests PASS.

- [ ] **Step 6: Commit raw replay behavior**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: replay 1hai checkin request"
```

### Task 3: Failure Handling, CLI, and Secret-Safe Logs

**Files:**
- Modify: `ehigh_checkin.py`
- Modify: `tests/test_ehigh_checkin.py`

- [ ] **Step 1: Write failing response-validation tests**

Add these imports to `tests/test_ehigh_checkin.py` and keep the existing combined `ehigh_checkin` import:

```python
import json
from unittest.mock import patch

import requests

from ehigh_checkin import CheckinError, main
```

Replace all `ehigh_checkin` imports with:

```python
from ehigh_checkin import (
    CheckinError,
    ConfigError,
    EhiConfig,
    main,
    perform_checkin,
)
```

Add before the `if __name__ == "__main__"` block:

```python
class EhiFailureTests(unittest.TestCase):
    def setUp(self):
        self.config = EhiConfig.from_env(VALID_ENV)
        self.session = Mock()
        self.response = Mock(status_code=200)
        self.session.post.return_value = self.response

    def test_rejects_non_2xx_without_parsing_body(self):
        self.response.status_code = 401

        with self.assertRaisesRegex(CheckinError, "HTTP 状态异常: 401"):
            perform_checkin(self.config, self.session)

        self.response.json.assert_not_called()

    def test_wraps_network_exception_without_exception_text(self):
        self.session.post.side_effect = requests.Timeout("secret-token leaked")

        with self.assertRaisesRegex(CheckinError, "网络请求失败: Timeout") as context:
            perform_checkin(self.config, self.session)

        self.assertNotIn("secret-token", str(context.exception))

    def test_rejects_invalid_json(self):
        self.response.json.side_effect = json.JSONDecodeError("bad", "x", 0)

        with self.assertRaisesRegex(CheckinError, "响应不是有效 JSON"):
            perform_checkin(self.config, self.session)

    def test_rejects_non_object_json(self):
        self.response.json.return_value = ["encrypted-response"]

        with self.assertRaisesRegex(CheckinError, "响应 JSON 不是对象"):
            perform_checkin(self.config, self.session)

    def test_rejects_missing_empty_or_non_string_result(self):
        for payload in ({}, {"Result": ""}, {"Result": 123}):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload

                with self.assertRaisesRegex(CheckinError, "响应缺少非空 Result"):
                    perform_checkin(self.config, self.session)


class EhiMainTests(unittest.TestCase):
    @patch("ehigh_checkin.requests.Session")
    def test_success_logs_only_safe_response_metadata(self, session_class):
        response = Mock(status_code=200)
        response.json.return_value = {"Result": "secret-response"}
        session_class.return_value.__enter__.return_value.post.return_value = response

        with patch.dict("os.environ", VALID_ENV, clear=True):
            with self.assertLogs("ehigh_checkin", level="INFO") as captured:
                exit_code = main()

        output = "\n".join(captured.output)
        self.assertEqual(exit_code, 0)
        self.assertIn("HTTP 200", output)
        self.assertIn("Result 长度=15", output)
        for secret in (*VALID_ENV.values(), "secret-response"):
            self.assertNotIn(secret, output)

    @patch("ehigh_checkin.requests.Session")
    def test_failure_returns_nonzero_and_does_not_log_secrets(self, session_class):
        session_class.return_value.__enter__.return_value.post.side_effect = requests.Timeout(
            "secret-token leaked"
        )

        with patch.dict("os.environ", VALID_ENV, clear=True):
            with self.assertLogs("ehigh_checkin", level="ERROR") as captured:
                exit_code = main()

        output = "\n".join(captured.output)
        self.assertEqual(exit_code, 1)
        self.assertIn("网络请求失败: Timeout", output)
        for secret in VALID_ENV.values():
            self.assertNotIn(secret, output)
```

- [ ] **Step 2: Run failure and CLI tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiFailureTests tests.test_ehigh_checkin.EhiMainTests -v`

Expected: FAIL because `CheckinError` and `main` are not defined and response validation is incomplete.

- [ ] **Step 3: Implement sanitized validation and CLI behavior**

Add these imports to `ehigh_checkin.py`:

```python
import json
import logging

import requests
```

Add near `ConfigError`:

```python
logger = logging.getLogger("ehigh_checkin")


class CheckinError(RuntimeError):
    """一嗨签到请求未被安全地接受。"""
```

Replace `perform_checkin` with:

```python
def perform_checkin(config: EhiConfig, session: Any) -> CheckinOutcome:
    try:
        response = session.post(
            CHECKIN_URL,
            headers=_build_headers(config),
            data=config.request_body.encode("utf-8"),
            timeout=(10, 30),
        )
    except requests.RequestException as error:
        raise CheckinError(f"网络请求失败: {type(error).__name__}") from error

    if not 200 <= response.status_code < 300:
        raise CheckinError(f"HTTP 状态异常: {response.status_code}")

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise CheckinError("响应不是有效 JSON") from error

    if not isinstance(payload, dict):
        raise CheckinError("响应 JSON 不是对象")

    result = payload.get("Result")
    if not isinstance(result, str) or not result:
        raise CheckinError("响应缺少非空 Result")

    return CheckinOutcome(
        status_code=response.status_code,
        result_length=len(result),
        result_sha256=hashlib.sha256(result.encode("utf-8")).hexdigest(),
    )
```

Add at the end of `ehigh_checkin.py`:

```python
def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        config = EhiConfig.from_env()
        with requests.Session() as session:
            outcome = perform_checkin(config, session)
    except (ConfigError, CheckinError) as error:
        logger.error("一嗨签到请求失败: %s", error)
        return 1

    logger.info(
        "一嗨签到请求已被服务端接受: HTTP %s, Result 长度=%s, SHA-256=%s；业务结果仍需 App 验证",
        outcome.status_code,
        outcome.result_length,
        outcome.result_sha256,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run all script tests**

Run: `python -m unittest tests.test_ehigh_checkin -v`

Expected: 13 tests PASS.

- [ ] **Step 5: Verify the source never prints protocol values directly**

Run: `python -m unittest tests.test_ehigh_checkin.EhiMainTests -v`

Expected: 2 tests PASS and captured logs contain status/length/hash only.

- [ ] **Step 6: Commit robust error handling**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: validate 1hai replay responses"
```

### Task 4: Independent GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/ehighCheck.yml`
- Create: `tests/test_ehigh_workflow.py`

- [ ] **Step 1: Write failing workflow contract tests**

Create `tests/test_ehigh_workflow.py`:

```python
import re
import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "ehighCheck.yml"


class EhiWorkflowTests(unittest.TestCase):
    def test_runs_once_daily_at_0917_beijing_and_manually(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertEqual(re.findall(r"cron:\s*'([^']+)'", workflow), ["17 1 * * *"])

    def test_has_minimal_permissions_and_independent_concurrency(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("contents: read", workflow)
        self.assertIn("group: ehigh-checkin", workflow)
        self.assertNotIn("GLADOS_", workflow)
        self.assertNotIn("schedule_gate.py", workflow)
        self.assertNotIn("actions/cache", workflow)

    def test_injects_only_the_expected_ehi_secrets(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        referenced = set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow))

        self.assertEqual(
            referenced,
            {
                "EHI_TOKEN",
                "EHI_APP_IDENTITY",
                "EHI_AUTHORIZATION",
                "EHI_CONTENT_MD5",
                "EHI_NONCESTR",
                "EHI_REQUEST_ROOT_ID",
                "EHI_REQUEST_BODY",
                "EHI_COOKIE",
            },
        )
        self.assertNotIn("set -x", workflow)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run workflow tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_workflow -v`

Expected: ERROR with `FileNotFoundError` for `.github/workflows/ehighCheck.yml`.

- [ ] **Step 3: Add the independent workflow**

Create `.github/workflows/ehighCheck.yml`:

```yaml
name: 1hai auto checkin

on:
  workflow_dispatch:
  schedule:
    # UTC 01:17 = 北京时间 09:17
    - cron: '17 1 * * *'

concurrency:
  group: ehigh-checkin
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  checkin:
    name: 1hai checkin
    runs-on: ubuntu-latest
    env:
      FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
    steps:
      - name: Checkout code
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: python -m pip install requests

      - name: Run 1hai checkin
        env:
          EHI_TOKEN: ${{ secrets.EHI_TOKEN }}
          EHI_APP_IDENTITY: ${{ secrets.EHI_APP_IDENTITY }}
          EHI_AUTHORIZATION: ${{ secrets.EHI_AUTHORIZATION }}
          EHI_CONTENT_MD5: ${{ secrets.EHI_CONTENT_MD5 }}
          EHI_NONCESTR: ${{ secrets.EHI_NONCESTR }}
          EHI_REQUEST_ROOT_ID: ${{ secrets.EHI_REQUEST_ROOT_ID }}
          EHI_REQUEST_BODY: ${{ secrets.EHI_REQUEST_BODY }}
          EHI_COOKIE: ${{ secrets.EHI_COOKIE }}
        run: python ehigh_checkin.py
```

- [ ] **Step 4: Run workflow tests**

Run: `python -m unittest tests.test_ehigh_workflow -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Parse the workflow as YAML using Ruby's built-in parser**

Run: `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ehighCheck.yml", aliases: true); puts "valid yaml"'`

Expected: prints `valid yaml` and exits 0.

- [ ] **Step 6: Commit the workflow**

```bash
git add .github/workflows/ehighCheck.yml tests/test_ehigh_workflow.py
git commit -m "ci: schedule daily 1hai checkin"
```

### Task 5: User Documentation and Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the one-hai setup and operations section**

Insert the following section before the existing `## 文件结构` heading in `README.md`:

```markdown
## 一嗨自动签到（静态重放）

本仓库可独立运行一嗨签到任务。该方案不会生成一嗨客户端的加密参数，而是原样重放一组已经验证可跨日使用的 `SignIn` 请求。它可能在 Token 过期、接口协议变化或服务端增加防重放校验后失效。

### 获取配置

在一嗨 App 中捕获以下请求：

```text
POST https://app.1hai.cn/SignCenter/UserAssets/SignIn
```

将同一次请求的字段分别保存为 GitHub Actions repository secrets：

| Secret | 抓包字段 |
|---|---|
| `EHI_TOKEN` | 请求头 `Token` |
| `EHI_APP_IDENTITY` | 请求头 `AppIdentity` |
| `EHI_AUTHORIZATION` | 请求头 `Authorization` |
| `EHI_CONTENT_MD5` | 请求头 `ehiContent-MD5` |
| `EHI_NONCESTR` | 请求头 `noncestr` |
| `EHI_REQUEST_ROOT_ID` | 请求头 `x-ms-request-root-id` |
| `EHI_REQUEST_BODY` | 未修改的原始请求体 |
| `EHI_COOKIE` | 请求头 `Cookie`，可选 |

这些字段必须来自同一次请求，不能只更新其中一部分。不要把真实值写入仓库、Issue 或 Actions 日志。已经公开的 Token 和请求字段应先通过重新登录刷新，再用于正式部署。

### 运行与验证

- `.github/workflows/ehighCheck.yml` 计划每天北京时间 09:17 运行，也支持手动执行。
- 首次配置后先手动运行工作流，再打开一嗨 App 确认当天已签到且积分增加。
- HTTP 2xx 和非空加密 `Result` 只表示请求被服务端接受。脚本无法解密业务响应，因此不会把它直接声明为积分到账。
- 如果未配置 `EHI_COOKIE` 也能通过首次人工验证，则无需保存 Cookie；失败时再补充同一次抓包请求的 Cookie。
- 工作流失败或 App 未显示签到时，重新登录并捕获一组完整的新请求，然后一起更新所有 `EHI_*` Secrets。
- GitHub Actions 定时任务可能延迟或丢失，重要日期可在 Actions 页面检查运行记录。
```

Update the existing file tree block so it also lists:

```text
│  ehigh_checkin.py	# 一嗨静态重放签到脚本
│
├─.github
│  └─workflows
│          ehighCheck.yml	# 一嗨签到 Actions 配置
│          gladosCheck.yml	# GLaDOS/Railgun Actions 配置
```

Preserve the existing entries for all other Python files and tests.

- [ ] **Step 2: Verify documentation contains every required Secret without values**

Run:

```bash
python -c 'import re; from pathlib import Path; text=Path("README.md").read_text(); names=("EHI_TOKEN","EHI_APP_IDENTITY","EHI_AUTHORIZATION","EHI_CONTENT_MD5","EHI_NONCESTR","EHI_REQUEST_ROOT_ID","EHI_REQUEST_BODY","EHI_COOKIE"); assert all(f"`{name}`" in text for name in names); assert not re.search(r"(?i)(replace[-_ ]?me|your[-_ ]?(token|secret|cookie)|<[^>]*(token|secret|cookie)[^>]*>)", text); print("README secrets documented safely")'
```

Expected: prints `README secrets documented safely`.

- [ ] **Step 3: Run the complete offline test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all existing and new tests PASS, with no real network requests.

- [ ] **Step 4: Check formatting and accidental credential inclusion**

Run: `git diff --check`

Expected: exits 0 with no output.

Manually review the current implementation and documentation diff for accidental hard-coded credentials:

```bash
git diff -- README.md ehigh_checkin.py .github/workflows/ehighCheck.yml tests/test_ehigh_checkin.py tests/test_ehigh_workflow.py
```

Expected: inspect every added or changed line and confirm it contains no captured Token, signature, Cookie, request body, or other credential value. Use obvious short placeholders in tests and examples. This manual current-diff review is not a comprehensive secret scanner or Git history audit.

- [ ] **Step 5: Review the final diff and commit documentation**

Run: `git diff -- README.md`

Expected: only the one-hai setup section and file-tree updates appear.

```bash
git add README.md
git commit -m "docs: explain 1hai replay setup"
```

### Task 6: Final Integration Verification

**Files:**
- Verify: `ehigh_checkin.py`
- Verify: `tests/test_ehigh_checkin.py`
- Verify: `.github/workflows/ehighCheck.yml`
- Verify: `tests/test_ehigh_workflow.py`
- Verify: `README.md`

- [ ] **Step 1: Run the complete test suite from a clean process**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 2: Verify both workflows parse and only the new workflow references EHI Secrets**

Run:

```bash
ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |path| YAML.load_file(path, aliases: true) }; puts "all workflows valid"'
```

Expected: prints `all workflows valid`.

Run: `git grep -n 'secrets.EHI_' -- .github/workflows`

Expected: matches occur only in `.github/workflows/ehighCheck.yml` and list exactly the eight documented Secret references.

- [ ] **Step 3: Confirm no uncommitted implementation changes remain**

Run: `git status --short`

Expected: no output. If unrelated pre-existing user changes are present, verify only that the files in this plan are clean and do not modify or revert those unrelated changes.

- [ ] **Step 4: Perform the first real request only after rotating credentials**

In GitHub repository settings, create all required `EHI_*` Secrets from one newly captured request. First omit `EHI_COOKIE`, manually dispatch `1hai auto checkin`, and inspect only the sanitized status/length/hash log.

Expected: workflow exits 0, then the one-hai App shows the same Beijing date as signed in and confirms the points increase. If it does not, add `EHI_COOKIE` from that same captured request and dispatch once more. Never paste the new values into a terminal command, commit, Issue, PR, or chat.

---

## Spec Coverage Self-Review

- Independent script/workflow: Tasks 1-4 create isolated files and explicitly test absence of GLaDOS state/cache references.
- Complete Secret set: Tasks 1 and 4 cover Token, AppIdentity, both authorization fields, nonce, request root ID, body, and optional Cookie.
- Exact replay: Task 2 asserts the original body bytes, fixed metadata, headers, timeout, and optional Cookie behavior.
- Safe outcome semantics: Task 3 accepts only 2xx + object JSON + non-empty string `Result`, logs “服务端接受” rather than business success, and returns nonzero for every defined failure.
- Secret safety: Tasks 3-5 provide targeted log-redaction tests, Secret scoping tests, no response ciphertext logging, and manual diff review.
- Schedule: Task 4 fixes the daily cron to Beijing 09:17 and keeps manual dispatch without adding state Cache or retries.
- Documentation/operations: Task 5 documents capture, setup, first manual verification, optional Cookie, whole-request rotation, and known replay limitations.
- Verification: Task 6 runs all offline tests, parses both workflows, checks isolation, and defines the credential-rotation gate before the sole live verification.
