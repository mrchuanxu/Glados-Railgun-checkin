# Glados自动签到

## 食用方式：

### 注册一个GLaDOS的账号([注册地址](https://glados.space/landing/0A58E-NV28S-6U3QV-33VMG))

#### 我的邀请码：([0A58E-NV28S-6U3QV-33VMG](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

#### 我的优惠码（9折）：([DEVILSTORE](https://0a58e-nv28s-6u3qv-33vmg.glados.space)) 

### **Fork**本仓库

![图片加载失败](imgs/1.png)

### 添加**secret**

1. 跳转至自己的仓库的`Settings`->`Secrets and variables`->`Action`

2. 添加1个`repository secret`，命名为`GLADOS_COOKIES`，其值对应GLaDOS账号的cookie值中的有效部分（获取方式如下）

- 在GLaDOS的签到页面按`F12`

- 切换到`Network`页面下，刷新

![图片加载失败](imgs/2.png)

- 点击第一个选项卡后在`Request Headers`下找到`Cookie`，右键复制cookie的值即可

  > 参考格式：koa:sess=eyJ1c2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxAwMH0=; koa:sess.sig=xJkOxxxxxxxxxxxxxxxtnM;

![图片加载失败](imgs/3.png)

- 多账号请在 `COOKIES` 中 添加多个 `cookies` 中间使用 `&`连接即可。（例如： `c1&c3&c3...`）

3. 配置兑换轮询周期（非必须）

- 添加1个`repository secret`，命名为`GLADOS_EXCHANGE_INTERVAL_DAYS`，配置累计多少个有效签到日后尝试兑换：

| 值 | 说明 |
|---|---|
| `20` | 每累计 20 个有效签到日后尝试兑换 |
| `30` | 每累计 30 个有效签到日后尝试兑换（默认） |
| `50` | 每累计 50 个有效签到日后尝试兑换 |

> 不配置或配置无效时使用 `30` 天。旧的 `GLADOS_EXCHANGE_PLAN` 已不再使用。

到达轮询周期时，程序查询 `/api/user/points` 返回的实时积分，并选择当前可兑换的最高档位：

| 当前积分 | 兑换计划 |
|---|---|
| 大于或等于 500 | `plan500` |
| 大于或等于 200、小于 500 | `plan200` |
| 大于或等于 100、小于 200 | `plan100` |
| 小于 100 | 暂不兑换 |

积分不足、积分查询失败或兑换失败时，任务保持到期状态，并在 5 个北京时间自然日后重试。只有兑换成功后才会清零，并重新累计有效签到日。

4. 手机推送（非必须）

- 添加1个`repository secret`，命名为`PUSHDEER_SENDKEY`，其值对应 PushDeer key: ([获取地址](https://www.pushdeer.com/product.html))。

## 运行时间与状态

- GitHub Actions 正常计划在北京时间 `12:07–15:52` 每 15 分钟错峰触发，并在 `16:00` 最后触发一次。
- GitHub 定时任务可能延迟或丢弃。为尽量保证每天签到，延迟到窗口外的任务在当天尚未完成时仍会立即补签。
- 当天签到任务完成后，后续 cron 会通过完成状态直接跳过，不安装依赖、不请求 GLaDOS，也不发送通知。
- 工作流会保留运行历史，并输出计划 cron、Runner 实际 UTC/北京时间、状态 Cache 匹配键和门控结果，方便排查延迟。
- 签到成功和“今日已签到”都计为一个有效签到日，签到失败不计数；同一天最多累计一次。
- 每个 Cookie 与域名独立计时，一个账号兑换成功不会重置其他账号。
- 运行状态通过 GitHub Actions Cache 保存，状态中只保存 Cookie 的不可逆标识，不保存 Cookie 明文。
- 更换 Cookie 或 Cache 被 GitHub 清理后，对应任务会从第 1 个有效签到日安全地重新计时。

### **star**自己的仓库

![图片加载失败](imgs/4.png)

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

这些字段必须来自同一次请求，不能只更新其中一部分。不要把真实值写入仓库、Issue 或 Actions 日志。已经公开的凭据应先通过重新登录轮换，再捕获新的整组请求字段用于正式部署。

### 运行与验证

- `.github/workflows/ehighCheck.yml` 计划每天北京时间 09:17 运行，也支持手动执行。
- 首次配置后先手动运行工作流，再打开一嗨 App 确认当天已签到且积分增加。
- HTTP 2xx 和非空加密 `Result` 只表示请求被服务端接受。脚本无法解密业务响应，因此这不能证明签到成功或积分到账。
- 首次测试先不配置 `EHI_COOKIE`；如果人工验证失败，再补充同一次抓包请求的 Cookie。
- 工作流失败或 App 未显示签到时，重新登录并捕获一组完整的新请求，然后一起更新所有 `EHI_*` Secrets。
- GitHub Actions 定时任务可能延迟或丢失，重要日期可在 Actions 页面检查运行记录。

## 文件结构

```shell
│  checkin.py	# 签到脚本
│  ehigh_checkin.py	# 一嗨静态重放签到脚本
│  exchange_policy.py	# 兑换周期和积分档位规则
│  schedule_gate.py	# 每日随机执行门控
│  state_store.py	# 跨工作流状态管理
│
├─.github
│  └─workflows
│          ehighCheck.yml	# 一嗨签到 Actions 配置
│          gladosCheck.yml	# GLaDOS/Railgun Actions 配置
│
└─tests	# 离线自动化测试
```

## 更新日志

- **2026-01**: 重构代码，添加log输出方便定位，支持新版网址，支持配置积分兑换策略。
- **2026-04**: 优化代码逻辑，优化日志输出，支持[新版域名](https://railgun.info) ，在 GLADOS_COOKIES 中添加新版域名下的 cookies 即可使用。


## 问题排查与定位
- 大家可以通过查询 actions 中的 running checkin 日志快速定位问题，有其他问题提交issue。

  <img width="1684" height="844" alt="image" src="https://github.com/user-attachments/assets/45348a5f-43e4-45f5-8fdf-ce84d343b30d" />

## 声明

本项目不保证稳定运行与更新, 因GitHub相关规定可能会删库, 请注意备份







