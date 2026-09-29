# 一嗨 PushDeer 通知设计

## 背景

一嗨静态重放签到目前在 GitHub Actions 日志中记录请求结果，但不会主动通知用户。现有 GLaDOS `auto check` 已使用 `pypushdeer.PushDeer` 和 Repository Secret `PUSHDEER_SENDKEY` 发送通知。本次在保持两个签到脚本业务隔离的前提下，为一嗨复用相同依赖、Secret 名称和基本发送方式。

## 触发条件

只有一嗨请求已经通过现有接受判定时才尝试发送通知：

- HTTP 状态为 2xx。
- 响应体能够解析为 JSON 对象。
- JSON 包含非空字符串 `Result`。

网络异常、非 2xx、无效 JSON、非对象 JSON、缺失或空 `Result` 均不会发送“请求已接受”通知。现有签到失败退出码保持不变。

## 配置

一嗨脚本继续使用 `EHI_CONFIG` 构造请求，并可选读取环境变量 `PUSHDEER_SENDKEY`：

- 未配置或值为空时，记录“未设置推送密钥，跳过通知”，签到成功退出码不受影响。
- 配置时，使用 `pypushdeer.PushDeer(pushkey=...)` 创建客户端，并调用 `send_text(title, desp=content)`。
- 不把 PushDeer SendKey 合并进 `EHI_CONFIG`，避免一嗨请求轮换时同时改动通知凭据，并与现有 `auto check` 共用同一个 Repository Secret。

工作流的依赖安装步骤增加 `pypushdeer`。`PUSHDEER_SENDKEY` 只注入 `Run 1hai checkin` 步骤，不进入 Job 级环境或其他步骤。

## 通知内容

通知标题固定为：

```text
一嗨签到请求已接受
```

通知正文为：

```text
HTTP: <状态码>
Result 长度: <密文长度>
Result SHA-256: <摘要>
业务结果仍需在一嗨 App 中确认
```

通知沿用程序已经计算的安全元数据，不包含：

- `EHI_CONFIG` 或其中任一字段。
- PushDeer SendKey。
- 请求头、Cookie 或原始请求体。
- 完整响应 `Result` 密文。

标题和正文使用“请求已接受”而不是“签到成功”或“积分到账”，因为程序无法解密业务响应。

## 失败隔离

PushDeer 通知是附属能力，不改变签到请求结果：

- 缺少 `pypushdeer` 依赖时记录错误并跳过。
- PushDeer 初始化或发送抛出异常时记录异常类型，不记录异常消息，避免第三方异常携带 SendKey 或通知正文。
- 通知发送失败时脚本仍以退出码 0 结束，只要一嗨请求已经满足接受判定。
- PushDeer SDK 返回值不作为一嗨签到成功或失败依据。

公开的通知错误不保留底层异常为 `__cause__` 或 `__context__`，也不向调用方重新抛出第三方异常。

## 代码结构

在 `ehigh_checkin.py` 内增加小型通知函数，不导入 `checkin.py` 的 `Config` 或 `PushService`。这样可以复用 PushDeer 的调用模式，同时避免加载 GLaDOS Cookie、状态存储、兑换和日志初始化逻辑。

主流程顺序为：

1. 读取并校验 `EHI_CONFIG`。
2. 执行一嗨请求并得到 `CheckinOutcome`。
3. 记录安全的“请求已接受”日志。
4. 若配置 SendKey，则尝试发送 PushDeer；否则跳过。
5. 无论通知发送成功、跳过或失败，只要步骤 2 成功，返回退出码 0。

## 测试

离线测试通过 mock PushDeer 覆盖：

- 请求被接受且配置 SendKey 时，以固定标题和安全正文调用 `send_text()`。
- 正文包含 HTTP 状态、`Result` 长度、SHA-256 和 App 人工确认提示。
- 正文不包含聚合配置、请求字段或完整响应密文。
- 未配置或空 SendKey 时不构造 PushDeer 客户端，签到仍返回 0。
- PushDeer 依赖不可用时签到仍返回 0。
- PushDeer 初始化或发送异常时签到仍返回 0，日志只包含异常类型，不包含异常消息、SendKey 或正文。
- 一嗨请求失败时不调用 PushDeer。
- 工作流只在签到步骤引用 `secrets.PUSHDEER_SENDKEY`，其他步骤和 Job 环境无 Secret 引用。
- 现有一嗨请求、配置安全和 GLaDOS/Railgun 测试继续通过。

## 文档

README 一嗨章节增加：

- 可选 Repository Secret `PUSHDEER_SENDKEY`，可与 GLaDOS 共用。
- 仅当请求通过 2xx、JSON 对象和非空 `Result` 判定后通知。
- 通知中的“已接受”不代表可验证的签到成功或积分到账。
- 未配置、依赖缺失或通知发送失败不会让已接受的一嗨请求任务失败。

## 验收标准

- 一嗨请求被接受后可通过 PushDeer 收到仅含安全元数据的通知。
- 一嗨请求失败时不发送成功通知。
- 通知缺失或失败不改变已接受请求的退出码 0。
- 日志和通知均不泄露一嗨请求凭据、响应密文或 PushDeer SendKey。
- `PUSHDEER_SENDKEY` 只暴露给一嗨签到执行步骤。
- README、工作流、实现和离线测试保持一致。
