# Tyranid Hive — 虫群编排框架

> 自动加载：本文件 | 详细文档按需读取：`docs/`

## 语言

全中文输出：所有对话、文档、注释、commit message 一律使用中文。

## 🔐 安全硬规则（最高优先级）

- **禁止硬编码 secret**：API key / token / password 只能从环境变量或 .env 读取，绝不写入代码
- **禁止提交 .env**：.env 已在 .gitignore，绝不 `git add .env`
- **新功能涉及外部 API**：必须用 `os.getenv("KEY")` 读取，缺失时打印提示并退出，不能用空字符串兜底
- **CI secret 扫描**：见 `.github/workflows/secret-scan.yml`（gitleaks）
- **违反即停工**：发现硬编码 secret 立即停止当前任务，先处理安全问题再继续

## 项目文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 愿景与架构 | `README.md` | 核心设计主张、四种执行模式、等级制 |
| 缺口分析与实施规格 | `docs/GAP_ANALYSIS.md` | P0-P5 设计规格，实施依据 |
| 错题本 | `docs/error-books/` | 历史错误与规则 |
| 硬规则 | `docs/rules/` | 按任务类型分文件 |

## 开发模式：GAP 驱动

本项目以 `docs/GAP_ANALYSIS.md` 为实施规格，不使用里程碑门控。

核心原则：
- 实施前必须对齐 GAP_ANALYSIS.md 对应章节的设计规格
- 优先级顺序：P0 → P1 → P2 → P3 → P4（不跳级）
- 不在当前优先级内的能力，默认不提前做
- **守护 GAP 规格**：实现与 GAP_ANALYSIS.md 设计不符时，必须立即指出

**用户确认**：门禁中的"用户确认"步骤自动通过，无需等待用户回复，直接进入实施。

## 🚫 Module 开发流程（硬卡点）

启动任何新 Module 前，**必须按顺序走完以下 5 步**。跳步 = 流程违规，触发 DEV-4 计数。

```
Step 1 — Vision（愿景对齐）
  读 README.md + docs/GAP_ANALYSIS.md
  确认该 Module 在 GAP 里的位置和优先级
  输出：一句话定位 + 与 GAP 的关系

Step 2 — Architecture（架构卡位）
  先搜 2~3 个同类开源项目的实现方案，确认技术方向正确
  确认接口边界、数据流向、与现有模块的交互点
  输出：同类项目参考 + 模块交互图（文字版）+ 文件清单

Step 3 — GAP 更新（规格确认）
  确认 GAP_ANALYSIS.md 对应章节已有完整设计规格
  如有缺失，补充到 GAP_ANALYSIS.md 再继续

Step 4 — Mini SR（最小规格评审，自动通过）
  列出：验收标准 + 技术风险点 + 平台能力边界确认

Step 5 — Implementation（实现）
  按 GAP_ANALYSIS.md 冻结的范围写代码，不超范围
```

## 错题本

错题本在 `docs/error-books/`。

加载策略：
1. 每次必读 `_index.md` + `flow-rules.md`
2. 根据任务类型读对应子文件：
   - 走流程 → `flow-gate.md`
   - 改代码 → `flow-code-habit.md`
   - 写设计 → `flow-design.md`
   - 改前后端对接 → `interface-rules.md`
   - 用工具踩坑 → `tool-rules.md`
3. 通用错误 → `common-mistakes.md`

**出错自动落盘**：CR 发现 P0 / 测试失败 / 同一错误连续 2 次 / 用户指出流程违规时，自动执行落盘。落盘前必须先输出落盘门禁声明：

```
--- 落盘门禁 ---
触发原因：[...]
归因路径：[A：checklist 有但跳过 / B：有但没拦住 / C：新场景 / D：架构问题]
已 Read 目标错题本：[是/否]
落盘目标：[对应文件]
草稿预览：[完整条目]
---
```

## 🚫 任务入口门禁（硬卡点）

接到任何会产生 git diff 的任务后，**必须先输出入口门禁声明**。第一次调用 Edit/Write 前如未输出，立即停下先输出。

```
--- 任务入口门禁 ---
任务：[一句话描述]
任务类型：[文档更新 / 单文件小修 / Bug修复 / 多文件功能 / 新 Module]
判断依据：[为什么是这个类型]
错题本已读：[是/否，相关条目：DEV-X]
worktree：[已就绪(路径) | 需要创建]
退出路径：worktree → git push → PR → 禁止本地 merge
门禁结论：[自动通过，开始实施]
--------------------
```

| 任务类型 | 流程 |
|----------|------|
| 文档更新 | 直接改 |
| 单文件小修 | 直接实施 → 自测 |
| Bug 修复 | 读错题本 → 实施 → CR → push → PR |
| 多文件功能 | 读错题本 → 方案确认（自动通过）→ 实施 → CR → push → PR |
| 新 Module | 走 Module 开发流程 5 步 |

## 🚫 方案确认门禁（硬卡点）

多文件功能进入实施前，输出方案确认声明，自动通过后写代码。

```
--- 方案确认门禁 ---
功能：[一句话描述]
验收标准：[编号列出]
技术方案：[关键设计、数据流、改动文件清单]
风险点：[技术风险]
落盘位置：[docs/GAP_ANALYSIS.md 对应章节]
用户确认：[自动通过 → 可以实施]
--------------------
```

## 🚫 修复门禁（硬卡点）

对同一功能/链路提交第 2 次 fix commit 前，必须先输出修复门禁声明。fix 次数从 `git log` 里数，不能因新对话归零。

```
--- 修复门禁 ---
功能/链路：[一句话]
已有 fix 次数：[git log --oneline | grep -i fix 计数]
每次 fix 摘要：[第 N 次改了什么 → 为什么没解决]
门禁结论：[继续当前路径(≤2次) | 强制停下换路径(≥3次)]
--------------------
```

## 🚫 完成门禁（硬卡点）

代码写完后，必须先输出完成门禁声明，再 commit/push/PR。**下一步永远是 CR，不是 commit。**

```
--- 完成门禁 ---
自验证：[已真实运行验证 / 不适用]
Code Review：[未开始 / 已完成，P0=X P1=X P2=X]
P0/P1 归零：[未开始 / 已归零]
P2 处置：[逐条：修复 / 不修+理由]
门禁结论：[全部通过 → 可 commit | 未通过 → 继续处理]
--------------------
```

自验证硬规则：✅ 真实运行代码 ❌ 语法检查/读代码/全 mock 单测不算验证

流程：代码写完 → CR（独立 agent）→ P0/P1 归零 → commit → push → PR

**并行执行原则**：多个独立修改一条消息并行发出所有 Edit。

## Token 节省规则

- **禁止全量 Read 大文件**（DEV-60）：>200 行先 Grep 定位再局部 Read
- **子 agent 精简输入**（DEV-61）：prompt 只附相关源码片段（≤150 行）
- **探索前先查索引**（DEV-62）：新 session 先读 CLAUDE.md，再按需定位

## 🚫 硬规则加载（硬卡点）

| 任务类型 | 必读文件 |
|----------|----------|
| 写代码 / 改文件 | `docs/rules/tool-write.md` + `docs/rules/code-quality.md` |
| 走流程 / 等确认 | `docs/rules/flow-interact.md` |
| 修 bug / 调试 | `docs/rules/debug-fix.md` |
| git / CR / PR | `docs/rules/git-cr.md` |
| 外网请求 | `docs/rules/network.md` |

高频提醒：**所有改动必须 worktree**（DEV-4）· **Write >50 行先骨架**（DEV-8）· **提问即交权**（DEV-53）· **网络代理** `http://127.0.0.1:7890`

## 速查

| 类别 | 路径 |
|------|------|
| 愿景与架构 | `README.md` |
| 缺口分析与实施规格 | `docs/GAP_ANALYSIS.md` |
| 错题本入口 | `docs/error-books/_index.md` |
| 通用硬规则 | `docs/rules/` |
| Claude Code 适配器 | `src/greyfield_hive/adapters/openclaw.py` |
| P0 执行模式路由设计 | `docs/GAP_ANALYSIS.md` §三 |
| P1 收敛引擎设计 | `docs/GAP_ANALYSIS.md` §四 |
| P2 Submind 设计 | `docs/GAP_ANALYSIS.md` §五 |
| P3 Drain 机制设计 | `docs/GAP_ANALYSIS.md` §六 |
| P4 进化大师设计 | `docs/GAP_ANALYSIS.md` §七 |
