# 一嗨单 Secret 配置设计

## 背景

当前一嗨签到工作流使用八个 GitHub Actions Repository Secrets，分别承载 Token、设备身份、签名、nonce、请求追踪 ID、请求体和 Cookie。配置一组请求时必须逐项创建或更新，容易出现字段来自不同抓包请求、遗漏更新或名称拼写错误。

本次改为一个 Repository Secret：`EHI_CONFIG`。它使用 URL 编码键值对保存同一次抓包请求的全部字段，并以 `&` 分隔。请求发送、响应判定、调度时间和 GLaDOS/Railgun 功能均不改变。

## 配置格式

`EHI_CONFIG` 的规范格式为：

```text
token=<URL编码值>&app_identity=<URL编码值>&authorization=<URL编码值>&content_md5=<URL编码值>&noncestr=<URL编码值>&request_root_id=<URL编码值>&request_body=<URL编码值>&cookie=<URL编码值或空>
```

允许的键固定为：

| 键 | 抓包字段 | 值规则 |
|---|---|---|
| `token` | 请求头 `Token` | 非空 |
| `app_identity` | 请求头 `AppIdentity` | 非空 |
| `authorization` | 请求头 `Authorization` | 非空 |
| `content_md5` | 请求头 `ehiContent-MD5` | 非空 |
| `noncestr` | 请求头 `noncestr` | 非空 |
| `request_root_id` | 请求头 `x-ms-request-root-id` | 非空 |
| `request_body` | 原始加密请求体 | 非空 |
| `cookie` | 请求头 `Cookie` | 键必须存在，值可为空 |

键的顺序不影响解析。每个值必须使用标准 URL form 编码，以确保值中的 `&`、`=`、`%`、`+`、空格或非 ASCII 字符能够无损保存。解码后不再执行 `strip`、字符替换或其他规范化。

## 严格校验

脚本只读取环境变量 `EHI_CONFIG`，不再读取八个独立的 `EHI_*` 环境变量，也不保留兼容分支。

解析必须满足：

- `EHI_CONFIG` 存在且非空。
- 八个固定键全部出现。
- 不允许未知键。
- 不允许同一个键重复出现。
- 除 `cookie` 外，所有值必须非空。
- `cookie=` 合法，并映射为不发送 Cookie 请求头。
- URL 编码必须可按 UTF-8 解码；格式或编码无效时配置失败。

配置错误只报告错误类型和相关键名，不记录 `EHI_CONFIG` 原文、局部值或解析后的字段值。

## 数据流

GitHub Actions 将 `${{ secrets.EHI_CONFIG }}` 作为同名环境变量仅注入 `Run 1hai checkin` 步骤。脚本解析并校验配置，构造现有不可变 `EhiConfig`，后续请求构造和响应处理逻辑保持不变。

工作流中的其他步骤和 Job 级环境变量不能访问 `EHI_CONFIG`。仓库权限、checkout 凭据设置、并发组和北京时间 09:17 调度保持不变。

## 配置生成

README 提供本地 Python 命令，通过交互式或临时环境变量读取八个原始字段，再使用标准库 `urllib.parse.urlencode` 生成 `EHI_CONFIG`。生成过程必须：

- 输出可直接粘贴到 GitHub Secret 的单行字符串。
- 对所有值执行 URL 编码。
- 始终包含 `cookie` 键；不需要 Cookie 时使用空字符串。
- 不将真实值写入仓库文件。

文档不提供真实值，也不建议用户手工替换 URL 编码字符。所有字段仍必须来自同一次 `SignIn` 请求。

## 测试

配置单元测试覆盖：

- 完整的 `EHI_CONFIG` 能生成正确的 `EhiConfig`。
- 键顺序变化不影响解析。
- `&`、`=`、`%`、`+`、空格、Unicode 等字符编码后可无损恢复。
- `cookie=` 映射为 `None`，非空 Cookie 原样恢复。
- 环境变量缺失或为空时失败。
- 任一键缺失时失败。
- 任一未知键存在时失败。
- 任一键重复时失败。
- 任一非 Cookie 值为空时失败。
- 无效 URL/UTF-8 编码时失败。
- 所有错误和日志都不包含聚合 Secret 或字段值。

工作流测试改为断言：

- 只引用一个 Secret：`secrets.EHI_CONFIG`。
- 该 Secret 只出现在 `Run 1hai checkin` 步骤。
- Job 环境和其他步骤不引用任何一嗨 Secret。
- 原先八个独立 Secret 名称不再出现。

现有请求构造、响应校验、日志脱敏及 GLaDOS/Railgun 测试继续通过。

## 文档迁移

README 将八 Secret 表格替换为：

- 单一 Secret 名称 `EHI_CONFIG`。
- 八个配置键与抓包字段的映射表。
- URL 编码生成方法。
- `cookie` 键必填但值可为空的说明。
- 更新时必须重新生成并整体替换 `EHI_CONFIG`，不能拼接不同请求字段。

已有部署需要先创建 `EHI_CONFIG`，确认新工作流可运行后，再删除旧的八个 Repository Secrets。脚本不会回退读取旧 Secrets。

## 验收标准

- 工作流只注入一个 `EHI_CONFIG` Secret。
- 脚本只从 `EHI_CONFIG` 构建一嗨请求配置。
- 严格拒绝缺失、重复、未知或空的必填字段。
- 所有合法特殊字符经 URL 编码后无损恢复。
- 空 Cookie 不产生 Cookie 请求头。
- 配置错误和日志不泄露聚合 Secret 或字段值。
- README 能指导用户生成、配置和整体轮换单 Secret。
- 一嗨请求重放行为、响应语义、调度和现有 GLaDOS/Railgun 行为不变。
