# 一嗨 PushDeer 通知 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在一嗨请求通过现有接受判定后发送不含凭据或响应密文的 PushDeer 通知，同时保证通知失败不影响签到退出码。

**Architecture:** `ehigh_checkin.py` 增加可选导入的 PushDeer 客户端和独立 `send_push_notification()` 函数，函数只接收 SendKey 与安全的 `CheckinOutcome`。主流程先完成请求及安全日志，再尝试通知；工作流仅向签到步骤注入现有 `PUSHDEER_SENDKEY`，README 说明通知语义和失败隔离。

**Tech Stack:** Python 3.13、`pypushdeer`、`requests`、标准库 `unittest`/`unittest.mock`、GitHub Actions YAML

---

## File Structure

- Modify: `ehigh_checkin.py` - 可选加载 PushDeer、格式化安全通知、隔离通知失败并接入主流程。
- Modify: `tests/test_ehigh_checkin.py` - 覆盖发送、跳过、依赖缺失、异常脱敏、失败隔离和请求失败不通知。
- Modify: `.github/workflows/ehighCheck.yml` - 安装 `pypushdeer`，仅向签到步骤注入 `PUSHDEER_SENDKEY`。
- Modify: `tests/test_ehigh_workflow.py` - 验证两个 Secret 的精确映射和作用域，以及依赖安装。
- Modify: `README.md` - 说明可选 PushDeer 配置、通知语义和失败行为。

### Task 1: Isolated PushDeer Notification Function

**Files:**
- Modify: `ehigh_checkin.py`
- Modify: `tests/test_ehigh_checkin.py`

- [ ] **Step 1: Write failing notification unit tests**

Extend the `ehigh_checkin` import in `tests/test_ehigh_checkin.py` with `send_push_notification` and add:

```python
class EhiPushNotificationTests(unittest.TestCase):
    def setUp(self):
        self.outcome = CheckinOutcome(
            status_code=200,
            result_length=24,
            result_sha256="a" * 64,
        )

    @patch("ehigh_checkin.PushDeer")
    def test_sends_only_safe_accepted_metadata(self, pushdeer_class):
        sent = send_push_notification("fake-push-key", self.outcome)

        self.assertTrue(sent)
        pushdeer_class.assert_called_once_with(pushkey="fake-push-key")
        pushdeer_class.return_value.send_text.assert_called_once_with(
            "一嗨签到请求已接受",
            desp=(
                "HTTP: 200\n"
                "Result 长度: 24\n"
                f"Result SHA-256: {'a' * 64}\n"
                "业务结果仍需在一嗨 App 中确认"
            ),
        )

    @patch("ehigh_checkin.PushDeer")
    def test_missing_or_empty_key_skips_without_constructing_client(self, pushdeer_class):
        for push_key in (None, ""):
            with self.subTest(push_key=push_key):
                self.assertFalse(send_push_notification(push_key, self.outcome))

        pushdeer_class.assert_not_called()

    def test_missing_dependency_skips_notification(self):
        with patch("ehigh_checkin.PushDeer", None):
            with self.assertLogs("ehigh_checkin", level="ERROR") as captured:
                sent = send_push_notification("fake-push-key", self.outcome)

        self.assertFalse(sent)
        self.assertIn("缺少 pypushdeer 依赖", "\n".join(captured.output))

    @patch("ehigh_checkin.PushDeer")
    def test_push_exception_logs_type_only_and_does_not_escape(self, pushdeer_class):
        pushdeer_class.return_value.send_text.side_effect = RuntimeError(
            "fake-push-key and sensitive notification"
        )

        with self.assertLogs("ehigh_checkin", level="ERROR") as captured:
            sent = send_push_notification("fake-push-key", self.outcome)

        output = "\n".join(captured.output)
        self.assertFalse(sent)
        self.assertIn("RuntimeError", output)
        self.assertNotIn("fake-push-key", output)
        self.assertNotIn("sensitive notification", output)
```

Import `CheckinOutcome` in the existing combined import so tests construct only safe metadata.

- [ ] **Step 2: Run notification tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiPushNotificationTests -v`

Expected: FAIL because `send_push_notification` and `PushDeer` are not defined.

- [ ] **Step 3: Add optional dependency loading and notification function**

After the `requests` import in `ehigh_checkin.py`, add:

```python
try:
    from pypushdeer import PushDeer
except ModuleNotFoundError:
    PushDeer = None
```

After `CheckinOutcome`, add:

```python
PUSH_TITLE = "一嗨签到请求已接受"


def send_push_notification(push_key: str | None, outcome: CheckinOutcome) -> bool:
    if not push_key:
        logger.info("未设置推送密钥，跳过 PushDeer 通知。")
        return False
    if PushDeer is None:
        logger.error("缺少 pypushdeer 依赖，无法发送 PushDeer 通知。")
        return False

    content = (
        f"HTTP: {outcome.status_code}\n"
        f"Result 长度: {outcome.result_length}\n"
        f"Result SHA-256: {outcome.result_sha256}\n"
        "业务结果仍需在一嗨 App 中确认"
    )
    try:
        pushdeer = PushDeer(pushkey=push_key)
        pushdeer.send_text(PUSH_TITLE, desp=content)
    except Exception as error:
        error_name = type(error).__name__
    else:
        logger.info("PushDeer 通知发送成功。")
        return True

    logger.error("PushDeer 通知发送失败: %s", error_name)
    return False
```

The function catches the SDK exception and only retains its class name; it never logs or rethrows the original exception.

- [ ] **Step 4: Run focused and complete tests**

Run: `python -m unittest tests.test_ehigh_checkin.EhiPushNotificationTests -v`

Expected: 4 tests PASS.

Run: `python -m unittest tests.test_ehigh_checkin -v`

Expected: all one-hai tests PASS.

- [ ] **Step 5: Commit the isolated notification function**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: add 1hai pushdeer notification"
```

### Task 2: Main-Flow Notification Integration

**Files:**
- Modify: `ehigh_checkin.py`
- Modify: `tests/test_ehigh_checkin.py`

- [ ] **Step 1: Write failing main-flow tests**

Add to `EhiMainTests`:

```python
    @patch("ehigh_checkin.send_push_notification")
    @patch("ehigh_checkin.requests.Session")
    def test_accepted_request_sends_push_and_keeps_success_exit(
        self, session_class, send_push
    ):
        response = Mock(status_code=200)
        response.json.return_value = {"Result": "fake-response-ciphertext"}
        session_class.return_value.__enter__.return_value.post.return_value = response
        environment = {**VALID_ENV, "PUSHDEER_SENDKEY": "fake-push-key"}

        with patch.dict("os.environ", environment, clear=True):
            exit_code = main()

        self.assertEqual(exit_code, 0)
        send_push.assert_called_once()
        push_key, outcome = send_push.call_args.args
        self.assertEqual(push_key, "fake-push-key")
        self.assertEqual(outcome.status_code, 200)

    @patch("ehigh_checkin.send_push_notification", return_value=False)
    @patch("ehigh_checkin.requests.Session")
    def test_push_failure_does_not_change_accepted_request_exit(
        self, session_class, send_push
    ):
        response = Mock(status_code=200)
        response.json.return_value = {"Result": "fake-response-ciphertext"}
        session_class.return_value.__enter__.return_value.post.return_value = response

        with patch.dict(
            "os.environ",
            {**VALID_ENV, "PUSHDEER_SENDKEY": "fake-push-key"},
            clear=True,
        ):
            self.assertEqual(main(), 0)

        send_push.assert_called_once()

    @patch("ehigh_checkin.send_push_notification")
    @patch("ehigh_checkin.requests.Session")
    def test_rejected_request_does_not_send_push(self, session_class, send_push):
        session_class.return_value.__enter__.return_value.post.return_value = Mock(
            status_code=500
        )

        with patch.dict(
            "os.environ",
            {**VALID_ENV, "PUSHDEER_SENDKEY": "fake-push-key"},
            clear=True,
        ):
            self.assertEqual(main(), 1)

        send_push.assert_not_called()
```

Update the existing success-log test to patch `send_push_notification` so its assertion remains focused and no optional dependency is involved.

- [ ] **Step 2: Run main-flow tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_checkin.EhiMainTests -v`

Expected: FAIL because `main()` does not call `send_push_notification`.

- [ ] **Step 3: Call notification only after accepted response**

In `main()`, after the existing accepted-response log and before `return 0`, add:

```python
    send_push_notification(os.environ.get("PUSHDEER_SENDKEY"), outcome)
```

Do not call it from the exception path. Ignore its Boolean return value so notification failure cannot change the accepted request exit code.

- [ ] **Step 4: Run script and full repository tests**

Run: `python -m unittest tests.test_ehigh_checkin -v`

Expected: all one-hai tests PASS.

Run: `python -m unittest discover -s tests -v`

Expected: all repository tests PASS with no real network or PushDeer calls.

- [ ] **Step 5: Commit main-flow integration**

```bash
git add ehigh_checkin.py tests/test_ehigh_checkin.py
git commit -m "feat: notify accepted 1hai requests"
```

### Task 3: Workflow Dependency and Secret Scope

**Files:**
- Modify: `.github/workflows/ehighCheck.yml`
- Modify: `tests/test_ehigh_workflow.py`

- [ ] **Step 1: Write the failing workflow contract**

Replace `EXPECTED_SECRET` with:

```python
EXPECTED_SECRETS = {"EHI_CONFIG", "PUSHDEER_SENDKEY"}
```

Update the secret-scope test so the check-in step environment is parsed as a mapping and asserted equal to:

```python
expected_env = {
    name: "${{ secrets." + name + " }}" for name in EXPECTED_SECRETS
}
```

Keep assertions that Job-level env and every other step contain no `secrets.` reference, and that all eight legacy one-hai Secret names are absent.

Update the dependency test to require exactly:

```python
self.assertIn(
    "      run: python -m pip install requests pypushdeer\n",
    self.workflow,
)
```

- [ ] **Step 2: Run workflow tests to verify they fail**

Run: `python -m unittest tests.test_ehigh_workflow -v`

Expected: FAIL because `pypushdeer` and `PUSHDEER_SENDKEY` are not in the workflow.

- [ ] **Step 3: Update dependency installation and run-step environment**

Change `.github/workflows/ehighCheck.yml` to:

```yaml
    - name: Install dependencies
      run: python -m pip install requests pypushdeer
    - name: Run 1hai checkin
      run: python ehigh_checkin.py
      env:
        EHI_CONFIG: ${{ secrets.EHI_CONFIG }}
        PUSHDEER_SENDKEY: ${{ secrets.PUSHDEER_SENDKEY }}
```

Do not alter schedule, permissions, concurrency or checkout settings.

- [ ] **Step 4: Run workflow, YAML and full tests**

Run: `python -m unittest tests.test_ehigh_workflow -v`

Expected: all workflow tests PASS.

Run: `ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |path| YAML.load_file(path) }; puts "all workflows valid"'`

Expected: prints `all workflows valid`.

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit workflow changes**

```bash
git add .github/workflows/ehighCheck.yml tests/test_ehigh_workflow.py
git commit -m "ci: configure pushdeer for 1hai"
```

### Task 4: PushDeer Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add optional notification setup and semantics**

In the one-hai section, add:

```markdown
### PushDeer 通知（可选）

如需通知，可配置 Repository Secret `PUSHDEER_SENDKEY`；它可与 GLaDOS 签到共用。未配置时一嗨任务会跳过通知。

一嗨请求满足 HTTP 2xx、JSON 对象且包含非空 `Result` 后，通知会显示 HTTP 状态、`Result` 长度和 SHA-256 摘要。通知中的“请求已接受”不代表已经确认签到成功或积分到账，最终结果仍需在一嗨 App 中核验。

PushDeer 依赖缺失、初始化失败或发送失败只会记录脱敏错误，不会把已经被一嗨服务端接受的请求改为失败。签到请求本身失败时不会发送“请求已接受”通知。
```

Do not change the existing GLaDOS PushDeer instructions or one-hai credential generation procedure.

- [ ] **Step 2: Verify documentation wording and Secret names**

Run:

```bash
python -c 'from pathlib import Path; text=Path("README.md").read_text(); section=text.split("## 一嗨自动签到",1)[1].split("## 文件结构",1)[0]; assert "`PUSHDEER_SENDKEY`" in section; assert "请求已接受" in section; assert "不代表已经确认签到成功或积分到账" in section; assert "不会把已经被一嗨服务端接受的请求改为失败" in section; print("PushDeer docs present")'
```

Expected: prints `PushDeer docs present`.

- [ ] **Step 3: Run complete tests and diff checks**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

Run: `git diff --check`

Expected: exits 0 with no output.

- [ ] **Step 4: Review and commit documentation**

Run: `git diff -- README.md`

Expected: only the optional one-hai PushDeer subsection is added.

```bash
git add README.md
git commit -m "docs: explain 1hai pushdeer notifications"
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

- [ ] **Step 2: Parse workflows and verify exact Secret scope**

Run:

```bash
ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |path| YAML.load_file(path) }; puts "all workflows valid"'
```

Expected: prints `all workflows valid`.

Run: `git grep -n 'secrets.EHI_CONFIG\|secrets.PUSHDEER_SENDKEY' -- .github/workflows/ehighCheck.yml`

Expected: exactly two matches, both in the `Run 1hai checkin` environment block.

- [ ] **Step 3: Smoke-test missing config without importing optional PushDeer at runtime**

Run: `env -i PATH="$PATH" python ehigh_checkin.py`

Expected: exits 1 with `缺少环境变量: EHI_CONFIG`, creates no request and sends no notification.

- [ ] **Step 4: Verify failure isolation offline**

Run:

```bash
python -m unittest \
  tests.test_ehigh_checkin.EhiMainTests.test_push_failure_does_not_change_accepted_request_exit \
  tests.test_ehigh_checkin.EhiMainTests.test_rejected_request_does_not_send_push \
  tests.test_ehigh_checkin.EhiPushNotificationTests.test_push_exception_logs_type_only_and_does_not_escape \
  -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Check branch diff and worktree**

Run: `git diff --check master...HEAD`

Expected: exits 0.

Run: `git status --short`

Expected: no output.

- [ ] **Step 6: Defer live notification verification until GitHub Secrets are configured**

Configure `EHI_CONFIG` and optional `PUSHDEER_SENDKEY` directly in GitHub, manually dispatch `1hai auto checkin`, and verify both the Actions log and PushDeer message. Confirm the App separately because the notification only proves protocol-level acceptance.

Expected: this external verification is performed without placing either Secret in commands, repository files, Issues, PRs or chat.

---

## Spec Coverage Self-Review

- Trigger condition: Tasks 2 and 5 call notification only after `perform_checkin()` returns a validated `CheckinOutcome`; rejected requests never notify.
- Existing PushDeer pattern: Tasks 1 and 3 use `pypushdeer.PushDeer`, `send_text()`, `PUSHDEER_SENDKEY` and workflow installation consistent with `auto check`.
- Safe content: Task 1 asserts the exact title/body and excludes request credentials and response ciphertext by accepting only `CheckinOutcome`.
- Failure isolation: Tasks 1, 2 and 5 cover missing key, dependency absence, SDK exceptions and unchanged exit code 0 after accepted requests.
- Secret scope: Task 3 permits `EHI_CONFIG` and `PUSHDEER_SENDKEY` only in the execution step; legacy one-hai Secrets remain forbidden.
- Documentation: Task 4 explains optional setup, shared key, protocol-level semantics and non-fatal notification failures.
- Existing behavior: All tasks preserve one-hai request validation, static replay, scheduling and GLaDOS/Railgun behavior.
