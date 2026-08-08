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

- GitHub Actions 每天在北京时间 `12:00–16:00` 窗口内每 15 分钟触发；当天第一条实际到达的 cron 立即执行签到。
- 当天签到任务完成后，后续 cron 会通过完成状态直接跳过，不安装依赖、不请求 GLaDOS，也不发送通知。
- 签到成功和“今日已签到”都计为一个有效签到日，签到失败不计数；同一天最多累计一次。
- 每个 Cookie 与域名独立计时，一个账号兑换成功不会重置其他账号。
- 运行状态通过 GitHub Actions Cache 保存，状态中只保存 Cookie 的不可逆标识，不保存 Cookie 明文。
- 更换 Cookie 或 Cache 被 GitHub 清理后，对应任务会从第 1 个有效签到日安全地重新计时。

### **star**自己的仓库

![图片加载失败](imgs/4.png)

## 文件结构

```shell
│  checkin.py	# 签到脚本
│  exchange_policy.py	# 兑换周期和积分档位规则
│  schedule_gate.py	# 每日随机执行门控
│  state_store.py	# 跨工作流状态管理
│
├─.github
│  └─workflows
│          gladosCheck.yml	# Actions 配置文件
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







