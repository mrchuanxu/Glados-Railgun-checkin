# 停用 GLaDOS GitHub Actions 工作流设计

## 目标

停用现有 GLaDOS/Railgun 自动签到 GitHub Actions 工作流，同时完整保留工作流内容，便于以后恢复。

## 实现方式

将：

```text
.github/workflows/gladosCheck.yml
```

改名为：

```text
.github/workflows/gladosCheck.yml.disabled
```

文件内容保持不变。GitHub Actions 只识别 `.github/workflows` 下以 `.yml` 或 `.yaml` 结尾的工作流文件，因此改名后的文件不再作为工作流加载，定时任务和手动触发入口都会停用。

不修改 `checkin.py`、Cookie 配置、状态文件、兑换逻辑或一嗨签到工作流。

## 恢复方式

如需恢复，将文件名改回 `.github/workflows/gladosCheck.yml` 即可。恢复后原有定时和手动触发配置继续生效。

## 验证

- `.github/workflows/gladosCheck.yml` 不再存在。
- `.github/workflows/gladosCheck.yml.disabled` 存在，且内容与改名前完全一致。
- `.github/workflows` 下不存在其他有效的 GLaDOS 工作流定义。
- 现有离线测试全部通过，确认文件改名没有影响 Python 逻辑和其他工作流。

## 提交与推送

停用改动提交到当前 `master`。用户已确认推送当前 `master` 上的全部本地提交，包括此前两个浏览器签到设计/计划提交、本设计与后续实施提交。
