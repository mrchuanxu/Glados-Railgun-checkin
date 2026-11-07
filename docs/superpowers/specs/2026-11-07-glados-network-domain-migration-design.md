# GLaDOS 主域名迁移至 glados.network 设计

## 目标

将项目默认使用的 GLaDOS 主域名从 `glados.cloud` 整体替换为 `glados.network`，同时继续支持 `railgun.info`。

## 请求行为

现有 API 路径和请求方式保持不变。域名替换后，GLaDOS 主域名上的请求为：

- `POST https://glados.network/api/user/checkin`
- `GET https://glados.network/api/user/status`
- `GET https://glados.network/api/user/points`
- `POST https://glados.network/api/user/exchange`

`railgun.info` 上对应的签到、状态、积分和兑换请求保持不变。Cookie、请求头、超时、响应解析和错误处理均不改变。

## 实现方式

将 `Config.DOMAINS` 中的 `glados.cloud` 替换为 `glados.network`。继续复用现有的域名与 API 路径拼接逻辑，不分别硬编码完整接口，也不新增环境变量。

同步更新直接依赖默认 GLaDOS 域名的测试和 README 域名说明。与状态存储内部机制有关、但不代表运行时默认目标的独立单元测试，可以保留其任意示例域名；测试名称和数据应避免让读者误以为旧域名仍是受支持目标。

## 状态迁移

运行状态以“Cookie 不可逆标识 + 域名”作为任务标识。切换到 `glados.network` 后，该域名会被识别为一个新任务，因此不会继承 `glados.cloud` 的累计有效签到日、上次尝试日期或兑换重试状态。

不迁移旧状态，也不复用旧域名的任务标识，以避免把不同服务端域名的历史状态错误合并。`railgun.info` 的状态不受影响。

## 测试与验收

采用测试驱动方式：

1. 先增加或调整测试，断言默认域名包含 `glados.network` 和 `railgun.info`，且不包含 `glados.cloud`。
2. 断言签到、状态、积分和兑换四类请求在主域名上都生成 `https://glados.network` 地址。
3. 观察测试因现有实现仍使用旧域名而按预期失败。
4. 最小化修改默认域名配置，使新增测试通过。
5. 运行完整测试套件，确认调度、状态、兑换策略、一嗨签到及其他既有行为没有回归。

验收标准是：运行时不再默认请求 `glados.cloud`，四类 GLaDOS API 均使用 `glados.network`，`railgun.info` 仍被处理，完整测试套件通过。
