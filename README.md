# Tyranid Hive

> **一个受虫巢神经体系启发的多 Agent 编排系统。**
> 它不让 Agent "自由聊天"，而是让它们在分层治理、条件赛马和基因进化中完成任务。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Built on](https://img.shields.io/badge/Built%20on-OpenClaw-orange)](https://github.com/OpenClaw)

[看 Demo](#demo) · [30 秒体验](#quick-start) · [架构](#architecture) · [核心机制](#core-mechanics) · [对比](#comparison)

---

## What is Tyranid Hive?

**Tyranid Hive** 是一个受泰伦虫族社会结构启发的多 Agent 编排框架。

如果说普通 Multi-Agent 框架是"几个 Agent 自由讨论"，那 Tyranid Hive 更像一支被 Hive Mind 指挥的生物舰队：

- **更稳**：复杂任务自动触发双路赛马，降低单 Agent 失误
- **更可控**：分层调度与审查节点，支持人工插话和仲裁
- **更可追溯**：关键节点、多频道日志、Trial 面板完整可见
- **越跑越强**：经验沉淀为 Constitution / Playbook / Lessons，可复用、可进化

```
宿主(Host) 下令 → 主脑(Overmind) 决策 → 脑虫(Synapse) 调度 → 虫巢(Brood) 执行 → 单位(Unit) 作战
                          │
                          ├─ Conditional Trial（双路赛马）
                          ├─ Audit / Approval（人工仲裁）
                          └─ Gene Evolution（基因沉淀）
```

**一句话**：在 Hive 中，每个复杂任务都要先经过狩猎竞赛，胜者才能交付给宿主。

---

## Why a Hive?

### 传统多 Agent 框架的问题

| 问题 | 表现 |
|------|------|
| 单路径依赖 | 任务通常只走单一路径，失败高度依赖运气 |
| 审核软化 | 审核与仲裁不是强制流程，质量不可控 |
| 经验流失 | 教训常停留在上下文，而非可复用的基因 |

### Tyranid Hive 的回答

| 机制 | 实现 | 收益 |
|------|------|------|
| **分层治理** | Overmind → Synapse → Brood → Unit 硬分层 | 每层职责清晰，可定位、可干预 |
| **条件赛马** | 复杂任务触发双路 Brood 并行竞争 | 用竞争降低单路径失误，用评分收敛质量 |
| **基因进化** | Constitution / Playbook / Lessons 三层沉淀 | 经验写入基因，越跑越强 |
| **多频道审计** | Trunk / Trial / Hive / Ledger 分层暴露 | 领导看主干，开发者看详情，审计看记录 |

**核心主张**：对复杂任务来说，单路径不是效率，而是赌运气；Trial 的意义，就是让结果先经过狩猎，再交付给宿主。

---

## Demo

```bash
# 30 秒体验（Docker 即将到来）
docker run -p 7892:7892 greyfield/hive-demo

# 打开浏览器
open http://localhost:7892
```

**你将看到**：
- Trunk 频道：关键节点流，10-15 条核心事件
- Trial 面板：双路赛马实时进度对比
- Hive 视图：完整执行链与层级关系
- Ledger：战功晋升与淘汰审计记录

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Host / 宿主                          │
│                     （用户 / Greyfield）                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ submit_task()
┌──────────────────────────▼──────────────────────────────────┐
│                   Overmind / 主脑 (L3)                       │
│              复杂度判断 · 赛马仲裁 · 进化决策                  │
│              系统唯一，永不沉睡                                │
└──────────────────────────┬──────────────────────────────────┘
                           │ dispatch()
┌──────────────────────────▼──────────────────────────────────┐
│                   Synapse / 脑虫 (L2)                        │
│              战术调度 · 任务分解 · Brood 协调                 │
│              常驻 / 试验 / 休眠 三态                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ create_brood()
┌──────────────────────────▼──────────────────────────────────┐
│                    Brood / 虫巢 (L1)                         │
│              任务隔离 · 内部协作 · 执行协调                   │
│              ├─ 单路执行                                     │
│              └─ Trial：双路赛马（条件触发）                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ assign()
┌──────────────────────────▼──────────────────────────────────┐
│                    Unit / 单位 (L0)                          │
│              专业执行 + ToolAction                           │
│              枪虫(搜索) · 脑虫(分析) · 刀虫(编码)            │
│              基因注入 · 战功积累 · 可晋升/淘汰                │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Mechanics

### Conditional Trial（条件赛马）

当任务满足 2 项以上触发条件时，自动进入 Trial 模式：

**触发条件**：
- 需要外部执行（调用工具/API）
- 存在多路径可能（多种实现方案）
- 高风险操作（生产环境部署、数据变更）
- 历史失败率高（同类任务曾失败）

**执行流程**：
```
创建双路 Brood A / Brood B 并行执行
        ↓
硬门槛筛选（成功/约束/审查）
        ↓
软评分收敛（质量/速度/健壮性）
        ↓
选择胜者 → 更新战功 → 败者降级
        ↓
流式返回用户
```

**人工仲裁**：用户可在 Trial Panel 实时插话、审批或终止。

---

### Gene Evolution（基因进化）

经验不是聊天记录，而是会被提炼、固化、继承和淘汰的基因。

| 层级 | 英文名 | 稳定性 | 写入方式 | 用途 |
|------|--------|--------|----------|------|
| 宪法 | Constitution | 极高 | 手动维护 | 极稳定规则，直灌 Prompt |
| 战术手册 | Playbook | 中 | 检索注入 | 领域经验，RAG 召回 |
| 近期教训 | Lessons | 低 | 高频自动 | 30 天衰减，JSONL 追加 |

**进化逻辑**：
- Trial 胜者经验 → 提升相关 Playbook 权重
- Trial 败者教训 → 写入 Lessons，提醒后续任务
- 长期高战功 Unit → 升级为 Synapse（常驻小主脑）
- 持续低战功 Unit → 休眠或淘汰（Purge）

---

### Multi-Channel Visibility（多频道暴露）

Discord 式频道结构，不同角色看不同层级：

| 频道 | 内容 | 默认 | 受众 |
|------|------|------|------|
| **Trunk** | 关键节点（10-15 条） | 展开 | 决策者、领导 |
| **Trial** | 赛马详情、双路对比 | 折叠 | 开发者、调试者 |
| **Hive** | 完整执行链、层级关系 | 折叠 | 架构师、审计 |
| **Ledger** | 战功记录、晋升/淘汰 | 折叠 | 管理员、治理 |

---

### Human Arbitration（人工仲裁）

虫群不是黑箱，人类可以随时干预：

- **插话**：在任意节点插入人类指令
- **审批**：关键操作需要人工确认
- **终止**：可随时停止 Trial 或任务
- **仲裁**：当双路赛马评分接近时，人类做最终裁决

---

## Comparison

| 特性 | CrewAI | MetaGPT | AutoGen | **Tyranid Hive** |
|------|--------|---------|---------|------------------|
| **治理模式** | 现代团队 | 软件公司 | 平等协商 | **虫群等级制** |
| **复杂任务处理** | 单路径 | 单路径 | 单路径 | **✅ 双路赛马** |
| **审核机制** | 可选 | 可选 | 无 | **✅ 强制审查** |
| **经验沉淀** | 记忆 | 记忆 | 上下文 | **✅ 三层基因** |
| **人机协作** | 弱 | 弱 | 中等 | **✅ 可插话/审批** |
| **过程可见性** | 日志 | 日志 | 日志 | **✅ 多频道面板** |
| **进化机制** | ❌ | ❌ | ❌ | **✅ 战功晋升/淘汰** |

**一句话区别**：普通框架让 Agent "协作"，Hive 让 Agent "在生存竞争中交付"。

---

## Quick Start

### 30 秒体验（即将到来）

```bash
docker run -p 7892:7892 greyfield/hive-demo
open http://localhost:7892
```

### 5 分钟本地安装

```bash
# 1. 克隆仓库
git clone https://github.com/zuiho-kai/tyranid-hive.git
cd tyranid-hive

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 配置（在 Greyfield 中启用）
# greyfield/conf.yaml
plugins:
  hive:
    enabled: true
    mode: "auto"
```

### 作为 Greyfield 插件

```yaml
# greyfield/conf.yaml
plugins:
  hive:
    enabled: true
    mode: "auto"  # auto | simple | hive

    synapses:
      - name: "code-expert"
        domains: ["code", "debug"]
        model: "gpt-4o"
      - name: "research-analyst"
        domains: ["research", "analysis"]
        model: "claude-sonnet-4-6"
```

然后启动 Greyfield，说：
> "帮我研究 Python 爬虫框架并写个示例"

虫群会自动：
1. 主脑判断复杂度 → 触发 Hive 模式
2. 调度枪虫（搜索框架）→ 脑虫（分析对比）→ 刀虫（写代码）
3. 在 Trial Panel 展示双路赛马过程

### 独立使用

```python
from greyfield_hive import TyranidClaw, HiveConfig

hive = TyranidClaw(config=HiveConfig())

# 提交任务
async for event in hive.submit_task("帮我设计一个API"):
    print(f"[{event.channel}] {event.node}: {event.payload}")
```

---

## When to Use

- ✅ 复杂任务需要多 Agent 协作，且不能容忍单路径失败
- ✅ 需要审计和追溯（关键业务、合规场景）
- ✅ 希望系统越用越强（经验沉淀、持续进化）
- ✅ 需要人机协作（人工插话、审批、仲裁）
- ✅ 团队需要分层可见（领导看主干，开发看详情）

## When NOT to Use

- ❌ 简单任务，单 Agent 即可完成（ overhead 太高）
- ❌ 需要实时响应（Trial 赛马会增加延迟）
- ❌ 完全自动化的无人值守场景（需要人工审批节点）

---

## Project Structure

```
tyranid-hive/
├── config/                     # 配置（文件驱动）
│   ├── governance/
│   │   └── tyranid.yaml        # 虫群治理模式定义
│   ├── synapses/               # 脑虫配置
│   │   ├── code-expert.yaml
│   │   └── research-analyst.yaml
│   └── genes/                  # 基因库（三层）
│       ├── constitution/       # 宪法（极稳定）
│       ├── playbook/           # 战术手册（领域经验）
│       └── lessons/            # 近期教训（JSONL）
│
├── src/greyfield_hive/         # 核心代码
│   ├── core/                   # 四层实现
│   │   ├── overmind.py         # L3 主脑
│   │   ├── synapse.py          # L2 脑虫
│   │   ├── brood.py            # L1 虫巢
│   │   └── unit.py             # L0 单位
│   ├── systems/                # 核心系统
│   │   ├── evolution.py        # 进化引擎
│   │   ├── trial_race.py       # 条件赛马
│   │   ├── gene_seed.py        # 基因种子
│   │   └── message_store.py    # 消息持久化
│   └── adapters/
│       ├── openclaw.py         # OpenClaw 适配
│       └── greyfield.py        # Greyfield 适配
│
├── data/                       # 运行时数据
│   ├── greyfield-hive.db       # SQLite
│   └── lessons/                # JSONL
│
├── tests/                      # 测试
└── docs/                       # 文档
```

---

## Roadmap

| 阶段 | 目标 | 时间 |
|------|------|------|
| Phase 1 | Core 四层架构 + Conditional Trial | Q1 2026 |
| Phase 2 | Gene Evolution + Dashboard | Q2 2026 |
| Phase 3 | PostgreSQL 迁移 + 规模化 | Q3 2026 |

---

## License

MIT License — 与 [OpenClaw](https://github.com/OpenClaw)、[Greyfield](https://github.com/zuiho-kai/greyfield)、[edict](https://github.com/cft0808/edict) 保持一致。

---

## Terminology（术语表）

| 术语 | 英文 | 含义 |
|------|------|------|
| 宿主 | Host | 用户或上层系统（如 Greyfield） |
| 主脑 | Overmind | L3 战略决策层，系统唯一 |
| 脑虫 | Synapse | L2 战术调度层，可常驻或动态 |
| 虫巢 | Brood | L1 任务执行组，动态组建 |
| 单位 | Unit | L0 专业执行者，有基因和战功 |
| 赛马 | Trial | 双路竞争机制，复杂任务触发 |
| 基因 | Gene | 经验沉淀的三层结构 |
| 进化 | Evolution | 基因更新、战功晋升、淘汰清洗 |

---

**In the Hive, coordination is instinct. Reliability is earned by selection.**

---

## Acknowledgments

- [OpenClaw](https://github.com/OpenClaw) — 框架基础
- [edict](https://github.com/cft0808/edict) — 三省六部制灵感
- [Greyfield](https://github.com/zuiho-kai/greyfield) — 宿主系统
