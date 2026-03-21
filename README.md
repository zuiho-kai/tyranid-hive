<div align="center">

# 🧬 Tyranid Hive

**受泰伦虫族社会结构启发的多 Agent 编排框架**

它通过分层治理、条件赛马、战功进化与多频道审计，让复杂任务的执行过程更可控、更可追溯、更容易进化。

<br>

<p align="center">
  <a href="#-demo">🎬 Demo</a> ·
  <a href="#-为什么选-hive">💡 为什么选 Hive</a> ·
  <a href="#️-架构">🏛️ 架构</a> ·
  <a href="#-核心机制">🧬 核心机制</a> ·
  <a href="#️-对比">⚔️ 对比</a> ·
  <a href="#-快速开始">🚀 快速开始</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/OpenClaw-Required-orange?style=flat-square" alt="OpenClaw">
  <img src="https://img.shields.io/badge/Layers-4_Tiers-8B5CF6?style=flat-square" alt="4 Layers">
  <img src="https://img.shields.io/badge/Evolution-Neural-22C55E?style=flat-square" alt="Neural Evolution">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

</div>

---

## 这是什么？

**Tyranid Hive** 是一个多 Agent 编排框架。

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

## 💡 为什么选 Hive？

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

<details>
<summary><b>🔍 为什么「条件赛马」是杀手锏？（点击展开）</b></summary>

<br>

CrewAI 和 AutoGen 的任务分配是 **"先到先得"**——第一个 Agent 接了任务就开始做，做得好与坏全凭运气。

虫群的 **条件赛马** 机制完全不同：

- 🎯 **智能触发** —— 只在复杂任务时启动赛马（外部执行、多路径、高风险、历史失败率高）
- ⚔️ **固定双路** —— 两路 Brood 并行执行，硬门槛筛选 + 软评分收敛
- 📊 **实时干预** —— 用户可在 Trial Panel 实时查看进度、干预选择
- 🧬 **基因强化** —— 胜者的战术会被提取到 Playbook，败者的基因会被标记

这不是可选的插件——**它是架构的一部分**。每一个复杂任务都必须经过赛马的淬炼，没有例外。

**核心主张**：对复杂任务来说，单路径不是效率，而是赌运气；Trial 的意义，就是让结果先经过狩猎，再交付给宿主。

</details>

---

## 🎬 Demo

下面是虫群处理一个复杂任务时的真实输出结构：

```
[Trunk] task.received    : 帮我研究 Python 爬虫框架并写个示例
[Trunk] overmind.decision: 复杂度高 → 触发 Hive 模式 + Trial 赛马

[Trial] brood_a.start    : 路径 A → Scrapy / Playwright / requests-html
[Trial] brood_b.start    : 路径 B → aiohttp / httpx / mechanize

[Hive]  unit.search (A)  : Scrapy 星数 48k，适合大规模爬取...
[Hive]  unit.search (B)  : httpx 异步优先，适合 API 场景...
[Hive]  unit.analyze (A) : 分析框架适用场景，生成对比矩阵...
[Hive]  unit.analyze (B) : 异步爬取性能测试，生成基准数据...

[Trial] brood_a.score    : 87.3  ←  胜者
[Trial] brood_b.score    : 79.1

[Trunk] trial.result     : Brood A 胜出 → 更新战功 · 提取 Playbook
[Trunk] task.completed   : 输出 Python 爬虫示例代码（含框架对比）
```

> **Trunk** 只有关键节点；**Trial** 展示双路对比；**Hive** 记录完整执行链；**Ledger** 留存战功与晋升。

```bash
# 本地启动（Docker，即将到来）
docker run -p 7892:7892 greyfield/hive-demo
open http://localhost:7892
```

---

## 🏛️ 架构

虫群不是扁平的 Agent 集合，而是**严格分层的神经等级结构**：

| 层级 | 角色 | 英文名 | 职责 | 状态 |
|:---:|:---|:---|:---|:---|
| **L3** | 🧠 主脑 | Overmind | 战略决策、复杂度判断、赛马仲裁、进化决策 | 系统唯一，永不沉睡 |
| **L2** | 🎯 脑虫 | Synapse | 战术调度、任务分解、Brood 协调 | 常驻/试验/休眠三态 |
| **L1** | 🐛 虫巢 | Brood | 任务隔离、内部协作、执行协调 | 动态组建 |
| **L0** | ⚔️ 单位 | Unit | 专业执行 + ToolAction<br>枪虫(搜索) · 脑虫(分析) · 刀虫(编码) | 基因注入 · 战功积累 · 可晋升/淘汰 |

```
                    ┌─────────────┐
                    │   👤 宿主   │
                    │  (用户)     │
                    └──────┬──────┘
                           │ submit_task()
                    ┌──────▼──────┐
                    │  🧠 主脑    │
                    │  Overmind   │ 复杂度判断 · 赛马仲裁 · 进化决策
                    │  (L3)       │
                    └──────┬──────┘
                           │ dispatch()
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
         │ 🎯 脑虫 │  │ 🎯 脑虫 │  │ 🎯 脑虫 │
         │ Synapse │  │ Synapse │  │ Synapse │
         │  (L2)   │  │  (L2)   │  │  (L2)   │
         └────┬────┘  └────┬────┘  └────┬────┘
              │            │            │
         ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
         │ 🐛 Brood│  │ 🐛 Brood│  │ 🐛 Brood│
         │  (L1)   │  │  Trial  │  │  (L1)   │
         │         │  │ 双路赛马 │  │         │
         └────┬────┘  └────┬────┘  └────┬────┘
              │            │            │
         ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
         │ ⚔️ Unit │  │ ⚔️ Unit │  │ ⚔️ Unit │
         │ 枪虫    │  │ 刀虫    │  │ 脑虫    │
         │  (L0)   │  │  (L0)   │  │  (L0)   │
         └─────────┘  └─────────┘  └─────────┘
```

---

## 🧬 核心机制

### 条件赛马（Conditional Trial）

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

### 基因进化（Gene Evolution）

经验不是聊天记录，而是会被提炼、固化、继承和淘汰的基因。

| 层级 | 英文名 | 稳定性 | 写入方式 | 用途 |
|:---|:---|:---:|:---|:---|
| **宪法** | Constitution | ⭐⭐⭐⭐⭐ | 手动维护 | 极稳定规则，直灌 Prompt |
| **战术手册** | Playbook | ⭐⭐⭐ | 检索注入 | 领域经验，RAG 召回 |
| **近期教训** | Lessons | ⭐⭐ | 高频自动 | 30 天衰减，JSONL 追加 |

**进化逻辑**：
- Trial 胜者经验 → 提升相关 Playbook 权重
- Trial 败者教训 → 写入 Lessons，提醒后续任务
- 长期高战功 Unit → 升级为 Synapse（常驻脑虫）
- 持续低战功 Unit → 休眠或淘汰（Purge）

---

### 多频道暴露（Multi-Channel）

Discord 式频道结构，不同角色看不同层级：

| 频道 | 内容 | 默认 | 受众 |
|:---|:---|:---:|:---|
| **Trunk** | 关键节点（10-15 条） | 展开 | 决策者、领导 |
| **Trial** | 赛马详情、双路对比 | 折叠 | 开发者、调试者 |
| **Hive** | 完整执行链、层级关系 | 折叠 | 架构师、审计 |
| **Ledger** | 战功记录、晋升/淘汰 | 折叠 | 管理员、治理 |

---

### 人机仲裁（Human Arbitration）

虫群不是黑箱，人类可以随时干预：

- **插话**：在任意节点插入人类指令
- **审批**：关键操作需要人工确认
- **终止**：可随时停止 Trial 或任务
- **仲裁**：当双路赛马评分接近时，人类做最终裁决

---

## ⚔️ 对比

| 特性 | CrewAI | MetaGPT | AutoGen | **Tyranid Hive** |
|:---|:---|:---|:---|:---|
| **治理模式** | 现代团队 | 软件公司 | 平等协商 | **虫群等级制** |
| **复杂任务处理** | 单路径 | 单路径 | 单路径 | **✅ 双路赛马** |
| **审核机制** | 可选 | 可选 | 无 | **✅ 强制审查** |
| **经验沉淀** | 记忆 | 记忆 | 上下文 | **✅ 三层基因** |
| **人机协作** | 弱 | 弱 | 中等 | **✅ 可插话/审批** |
| **过程可见性** | 日志 | 日志 | 日志 | **✅ 多频道面板** |
| **进化机制** | ❌ | ❌ | ❌ | **✅ 战功晋升/淘汰** |

**一句话区别**：普通框架强调"协作"，Hive 强调"生存竞争后的交付"。

---

## 🚀 快速开始

### 方式一：作为 Greyfield 插件

```yaml
# greyfield/conf.yaml
plugins:
  hive:
    enabled: true
    mode: "auto"  # auto | simple | hive

    synapses:
      - name: "code-expert"
        domains: ["code", "debug"]
        model: "claude-sonnet-4-6"
      - name: "research-analyst"
        domains: ["research", "analysis"]
        model: "claude-sonnet-4-6"
```

然后启动 Greyfield，说：

> *"帮我研究 Python 爬虫框架并写个示例"*

虫群会自动：
- 主脑判断复杂度 → 触发 Hive 模式
- 调度枪虫（搜索框架）→ 脑虫（分析对比）→ 刀虫（写代码）
- 在 Trial Panel 展示双路赛马过程

### 方式二：独立使用

```python
from greyfield_hive import TyranidClaw, HiveConfig

hive = TyranidClaw(config=HiveConfig())

# 提交任务
async for event in hive.submit_task("帮我设计一个API"):
    print(f"[{event.channel}] {event.node}: {event.payload}")
```

---

## 📦 安装

### 前置条件

- Python 3.10+
- OpenClaw 已安装
- Greyfield 0.1.0+（作为宿主）

### 完整安装

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

### Docker（即将到来）

```bash
docker pull greyfield/hive
docker run -p 7892:7892 greyfield/hive
```

---

## ✅ 适用场景

### 适合使用

- ✅ 复杂任务需要多 Agent 协作，且不能容忍单路径失败
- ✅ 需要审计和追溯（关键业务、合规场景）
- ✅ 希望系统越用越强（经验沉淀、持续进化）
- ✅ 需要人机协作（人工插话、审批、仲裁）
- ✅ 团队需要分层可见（领导看主干，开发看详情）

### 不适合使用

- ❌ 简单任务，单 Agent 即可完成（overhead 太高）
- ❌ 需要实时响应（Trial 赛马会增加延迟）
- ❌ 完全自动化的无人值守场景（需要人工审批节点）

---

## 🏗️ 目录结构

```
tyranid-hive/
├── config/                          # 配置（文件驱动）
│   ├── governance/
│   │   └── tyranid.yaml             # 虫群治理模式定义
│   ├── synapses/                    # 脑虫配置
│   │   ├── code-expert.yaml
│   │   └── research-analyst.yaml
│   └── genes/                       # 基因库（三层）
│       ├── constitution/            # 宪法（极稳定）
│       ├── playbook/                # 战术手册（领域经验）
│       └── lessons/                 # 近期教训（JSONL）
│
├── src/greyfield_hive/              # 核心代码
│   ├── core/                        # 四层实现
│   │   ├── overmind.py              # L3 主脑
│   │   ├── synapse.py               # L2 脑虫
│   │   ├── brood.py                 # L1 虫巢
│   │   └── unit.py                  # L0 单位
│   ├── systems/                     # 核心系统
│   │   ├── evolution.py             # 进化引擎
│   │   ├── trial_race.py            # 条件赛马
│   │   ├── gene_seed.py             # 基因种子
│   │   └── message_store.py         # 消息持久化
│   └── adapters/
│       ├── openclaw.py              # OpenClaw 适配
│       └── greyfield.py             # Greyfield 适配
│
├── data/                            # 运行时数据
│   ├── greyfield-hive.db            # SQLite
│   └── lessons/                     # JSONL
│
├── tests/                           # 测试
└── docs/                            # 文档
```

---

## 🔄 任务流程

```
用户输入
    ↓
主脑分析（复杂度判断）
    ↓
    ├─ 简单 → 直接调度 Unit 执行
    └─ 复杂 → 创建脑虫 → 分解任务
              ↓
        创建 Brood（虫巢）
              ↓
        ├─ 单路 → 顺序执行
        └─ 赛马 → 固定两路并行
              ↓
        硬门槛筛选（成功/约束/审查）
              ↓
        软评分收敛（质量/速度/健壮性）
              ↓
        选择胜者 → 更新战功
              ↓
        流式返回用户
```

### 状态流转

| 状态 | 说明 |
|:---|:---|
| 🟡 **queued** | 任务排队等待 |
| 🔵 **analyzing** | 主脑分析中 |
| 🟠 **planning** | 脑虫分解任务 |
| 🟣 **racing** | 赛马进行中（两路） |
| 🔴 **reviewing** | 脑虫审查中 |
| 🟢 **completed** | 任务完成 |
| ⚫ **failed** | 任务失败 |

---

## 🗺️ Roadmap

### Phase 1 — 神经觉醒 ✅

- [x] 四层神经等级架构（Overmind/Synapse/Brood/Unit）
- [x] 条件赛马机制（硬门槛 + 软评分）
- [x] 三层基因进化（Constitution/Playbook/Lessons）
- [x] 战功晋升/降级体系
- [x] Discord 式多频道结构
- [x] OpenClaw/Greyfield 双适配

### Phase 2 — 虫巢扩张 🚧

- [ ] 实时 Dashboard（Trunk/Trial/Hive/Ledger）
- [ ] 基因库可视化（Playbook 检索、Lessons 衰减）
- [ ] 脑虫试验/休眠自动化
- [ ] PostgreSQL 迁移

### Phase 3 — 星际航行

- [ ] 跨 Hive 协作（多个 Greyfield 实例间）
- [ ] 基因市场（Playbook 交易/分享）
- [ ] 自适应进化（自动 Constitution 调整）

---

## 🛠️ 技术栈

| 组件 | 技术 |
|:---|:---|
| **语言** | Python 3.10+ |
| **异步框架** | asyncio |
| **配置** | Pydantic + YAML |
| **存储** | SQLite（Phase 1-2）→ PostgreSQL（Phase 3+） |
| **向量检索** | ChromaDB |
| **宿主集成** | Greyfield（Electron + Live2D） |
| **框架** | OpenClaw |

---

## 🙏 致谢

| 项目 | 贡献 |
|:---|:---|
| [OpenClaw](https://github.com/OpenClaw) | 框架基础 |
| [edict](https://github.com/cft0808/edict) | 三省六部制灵感 |
| [Greyfield](https://github.com/zuiho-kai/greyfield) | 宿主系统 |
| [Stellaris](https://store.steampowered.com/app/281990/Stellaris/) | 灰蛊风暴美学 |

---

<div align="center">

**In the Hive, coordination is instinct. Reliability is earned by selection.**

> *"我们并非个体，我们是虫群。"*
>
> *—— 主脑 Overmind*

</div>

---

## 📜 协议

MIT License — 与 OpenClaw、Greyfield、edict 保持一致。

---

## 术语表

| 术语 | 英文 | 含义 |
|:---|:---|:---|
| 宿主 | Host | 用户或上层系统（如 Greyfield） |
| 主脑 | Overmind | L3 战略决策层，系统唯一 |
| 脑虫 | Synapse | L2 战术调度层，可常驻或动态 |
| 虫巢 | Brood | L1 任务执行组，动态组建 |
| 单位 | Unit | L0 专业执行者，有基因和战功 |
| 赛马 | Trial | 双路竞争机制，复杂任务触发 |
| 基因 | Gene | 经验沉淀的三层结构 |
| 进化 | Evolution | 基因更新、战功晋升、淘汰清洗 |
