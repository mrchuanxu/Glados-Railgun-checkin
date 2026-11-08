# GLaDOS Chrome 定时签到实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建个人 Skill，并配置一个每天 15:00 使用本机 Chrome 完成 GLaDOS 网页签到的本地定时任务。

**Architecture:** 个人 Skill 只定义可复用的浏览器签到方法、成功标准与停止条件；Codex 本地独立定时任务只负责按时显式调用该 Skill。启用调度前先用同一 Chrome 登录态手动运行一次，并以页面可见状态验证流程。

**Tech Stack:** Codex Skills、Codex 本地 Scheduled tasks、Chrome Computer Use、RFC 5545 RRULE

**Spec:** `docs/superpowers/specs/2026-11-08-glados-browser-checkin-automation-design.md`

## Global Constraints

- 目标页面固定为 `https://glados.network/console/checkin`。
- 使用本机 Chrome 的现有登录状态，不调用仓库中的接口签到脚本。
- Asia/Shanghai 时区每天 15:00 执行。
- 单次运行最多点击一次 Checkin。
- “签到成功”或“今日已签到”等价页面状态才算成功。
- 登录失效、验证码、按钮缺失、页面错误或结果不可确认时停止并报告。
- 不修改账户资料、套餐、支付信息或其他设置。

## Review Focus

- 页面打开时已经签到：应直接成功结束，不点击 Checkin。
- Chrome 登录失效：应停止并报告需要重新登录，不尝试填写凭据。
- Checkin 按钮缺失且无已签到状态：应失败结束，不点击其他控件。
- 点击后反馈延迟或文案变化：只依据明确等价的成功状态，不重复点击。
- Chrome 控制不可用：应报告权限或连接问题，不改用接口脚本绕过。

---

### Task 1: 创建个人签到 Skill

**Files:**
- Create: `/Users/trans/.codex/skills/glados-browser-checkin/SKILL.md`
- Create: `/Users/trans/.codex/skills/glados-browser-checkin/agents/openai.yaml`

**Interfaces:**
- Consumes: Chrome Computer Use 和已登录的 `glados.network` 会话。
- Produces: 可由 `$glados-browser-checkin` 显式调用的个人 Skill。

- [ ] **Step 1: 使用 Skill 初始化器创建 `glados-browser-checkin`**

仅创建必需的 `SKILL.md` 和 `agents/openai.yaml`，不创建无用途的 scripts、references 或 assets。

- [ ] **Step 2: 写入 Skill 操作规则**

`SKILL.md` 必须规定：使用 Chrome 打开固定 URL；先检查已签到状态；仅在需要时点击一次 Checkin；等待并确认明确成功状态；遇到登录、验证码、权限或结果不明确时停止并报告；禁止进入账户、套餐或支付设置。

- [ ] **Step 3: 验证 Skill 结构**

Run: `python3 /Users/trans/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/trans/.codex/skills/glados-browser-checkin`

Expected: 验证成功，且无未替换的脚手架占位内容。

- [ ] **Step 4: 复核失败模式**

检查 Skill 对“已签到”“登录失效”“按钮缺失”“点击后无法确认”“Chrome 不可用”五种情况都有确定的停止或成功行为。

### Task 2: 手动验证真实 Chrome 流程

**Files:**
- None.

**Interfaces:**
- Consumes: Task 1 的 `$glados-browser-checkin` 和当前 Chrome 登录状态。
- Produces: 一次可观察的手动运行结果，证明页面、权限和成功判断可用。

- [ ] **Step 1: 使用 Chrome 打开签到页面**

打开 `https://glados.network/console/checkin`，确认使用的是用户已登录的 Chrome 会话。

- [ ] **Step 2: 执行一次 Skill 流程**

如果页面已显示今日已签到，则不点击；否则只点击一次 Checkin。

- [ ] **Step 3: 验证页面结果**

Expected: 页面明确显示“签到成功”“今日已签到”或语义等价状态。若出现登录、验证码、按钮缺失、权限问题或结果不可确认，则停止，不创建自动任务，并把可见问题交给用户处理。

### Task 3: 创建并检查每日本地定时任务

**Files:**
- Create through Codex automation management: one active local standalone scheduled task.

**Interfaces:**
- Consumes: Task 1 的 `$glados-browser-checkin` 和 Task 2 的成功验证结果。
- Produces: 每天 15:00 执行的独立本地任务，运行记录出现在 Scheduled。

- [ ] **Step 1: 解析当前本地项目标识**

从 Codex 项目列表中选择工作目录为 `/Users/trans/Documents/Glados-Railgun-checkin` 的项目，不猜测项目 ID。

- [ ] **Step 2: 创建独立本地定时任务**

名称使用 `GLaDOS Chrome 每日签到`；状态为 ACTIVE；执行环境为 local；计划使用 `RRULE:FREQ=DAILY;BYHOUR=15;BYMINUTE=0`；提示词显式调用 `$glados-browser-checkin`，要求使用本机 Chrome、固定 URL、最多点击一次并返回简短成功或失败结果。

- [ ] **Step 3: 读取并核对任务配置**

Expected: 任务为启用状态、每天 15:00、绑定正确本地项目，提示词包含 Skill 名称、Chrome、固定 URL、成功判断与停止条件。

- [ ] **Step 4: 报告运行前提和首轮复核点**

向用户说明电脑和 Codex 桌面应用需在执行时运行，Chrome 登录态及控制授权需保持有效；首个自动运行后在 Scheduled 中检查结果。
