<div align="center">

# 🦠 虫巢 · Tyranid Hive

**我用 4 亿年前的虫群进化论，重新设计了 AI 多 Agent 协作架构。**

**结果发现，自然选择比人工规则更懂优胜劣汰。**

<br>

<p align="center">
  <strong>虫群</strong>是一个基于<strong>泰伦虫族社会结构</strong>的多 Agent 调度系统，具备神经进化能力、条件赛马机制和战功晋升体系。
  <br>
  对外呈现 Discord 式多频道结构，对内以严格等级制运行。
</p>

<br>

<p align="center">
  <a href="#-demo">🎬 看 Demo</a> ·
  <a href="#-30-秒快速体验">🚀 30 秒体验</a> ·
  <a href="#-架构">🏛️ 架构</a> ·
  <a href="#-核心机制">🧬 核心机制</a> ·
  <a href="#-对比">⚔️ 对比</a>
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

## 🎬 Demo

<p align="center">
  <!-- TODO: 添加演示视频/GIF -->
  <img src="docs/assets/hive-demo.gif" width="80%" alt="虫群演示">
  <br>
  <sub>🎥 虫群多 Agent 协作全流程演示</sub>
</p>

> 🐳 **快速体验：** 一行命令启动虫巢
> ```bash
> docker run -p 7892:7892 greyfield/hive-demo
> ```

---

## 🤔 为什么是虫群？

大多数 Multi-Agent 框架的套路是：

> *"来，你们几个 AI 自己聊，聊完把结果给我。"*

然后你拿到一坨不知道经过了什么处理的结果，无法追溯，无法优化，无法进化。

**虫群的思路完全不同** —— 我们借鉴了自然界最成功的分布式系统：**虫群智能**

```
你 (宿主) → 主脑 (Overmind) → 小主脑 (Synapse) → 工作组 (Brood) → 战斗单位 (Unit)
                                              ↓
                                        条件赛马 Trial
                                              ↓
                                        战功晋升 / 基因淘汰
```

这不是花哨的 metaphor，这是**真正的进化压力**：

| | CrewAI | MetaGPT | AutoGen | **虫群** |
|:---:|:---:|:---:|:---:|:---:|
| **治理模式** | 现代团队 | 软件公司 | 平等协商 | **虫群等级制** |
| **审核机制** | 可选 | 可选 | 无 | **强制审查（脑虫专职）** |
| **任务赛马** | ❌ | ❌ | ❌ | **✅ 条件双路赛马** |
| **进化体系** | ❌ | ❌ | ❌ | **✅ 战功晋升/降级** |
| **频道化** | ❌ | ❌ | ❌ | **✅ Discord 式多频道** |
| **人机协作** | 弱 | 弱 | 中等 | **✅ 人类可插话/审批** |
| **经验落盘** | 记忆 | 记忆 | 上下文 | **✅ 三层基因强制注入** |

> **核心差异：自然选择 + 强制赛马 + 战功进化**

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

这就是为什么虫群能处理复杂任务而结果可靠：因为在交付给你之前，它已经经历了自然选择的残酷筛选。4 亿年前的三叶虫就想明白了——**不适应者终将被淘汰**。

</details>

---

## 🏛️ 架构：四层神经等级

虫群不是扁平的 Agent 集合，而是**严格分层的神经等级结构**：

| 层级 | 角色 | 英文名 | 职责 | 状态 |
|:---:|:---|:---|:---|:---|
| **L3** | 🧠 主脑 | Overmind | 战略决策、复杂度判断、赛马仲裁、进化决策 | 系统唯一，永不沉睡 |
| **L2** | 🎯 小主脑 | Synapse | 战术调度、任务分解、Brood 协调 | 常驻/试验/休眠三态 |
| **L1** | 🐛 工作组 | Brood | 任务隔离、内部协作、执行协调 | 动态组建 |
| **L0** | ⚔️ 战斗单位 | Unit | 专业执行（设计虫/前端虫/后端虫）+ ToolAction 基因注入 | 战功决定晋升 |

```
                    ┌─────────────┐
                    │   👤 宿主   │
                    │  (用户)     │
                    └──────┬──────┘
                           │ 提交任务
                    ┌──────▼──────┐
                    │  🧠 主脑    │
                    │  Overmind   │ 复杂度判断
                    │  (L3)       │ 赛马仲裁
                    └──────┬──────┘
                           │ 调度
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
         │ 🎯 小主脑 │  │ 🎯 小主脑 │  │ 🎯 小主脑 │
         │ Synapse │  │ Synapse │  │ Synapse │
         │  (L2)   │  │  (L2)   │  │  (L2)   │
         └────┬────┘  └────┬────┘  └────┬────┘
              │            │            │
         ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
         │ 🐛 Brood │  │ 🐛 Brood │  │ 🐛 Brood │
         │  (L1)   │  │  Trial  │  │  (L1)   │
         │         │  │  双路赛马 │  │         │
         └────┬────┘  └────┬────┘  └────┬────┘
              │            │            │
         ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
         │ ⚔️ Unit │  │ ⚔️ Unit │  │ ⚔️ Unit │
         │ 枪虫    │  │ 刀虫    │  │ 脑虫    │
         │  (L0)   │  │  (L0)   │  │  (L0)   │
         └─────────┘  └─────────┘  └─────────┘
```

### 三大核心机制

#### 🔬 条件赛马（Conditional Trial）

- 满足 2 项以上触发：外部执行、多路径、高风险、历史失败率高
- 固定两路 Brood 并行，硬门槛筛选 + 软评分收敛
- 用户可在 Trial Panel 实时干预

#### 🧬 基因分层进化（Gene Evolution）

三层基因存储，对应不同稳定性要求：

| 层级 | 名称 | 稳定性 | 写入方式 |
|:---|:---|:---:|:---|
| **宪法** | Constitution | ⭐⭐⭐⭐⭐ | 极稳定规则，直灌 Prompt |
| **战术手册** | Playbook | ⭐⭐⭐ | 领域经验，检索注入 |
| **近期教训** | Lessons | ⭐⭐ | 高频写入，30 天衰减 |

> 📝 **经验即基因**：每一次任务执行都会产生基因片段，胜者强化，弱者淘汰。

#### 📊 多频道暴露（Multi-Channel）

- **Trunk（主干）**：仅 10-15 条关键节点，领导视角
- **Trial/Hive/Ledger**：详情面板默认折叠，用户主动展开

---

## 🚀 30 秒快速体验

### Docker 一键启动

```bash
docker run -p 7892:7892 greyfield/hive-demo
```

打开 http://localhost:7892 即可体验虫巢看板。

### 完整安装

#### 前置条件

- Python 3.10+
- OpenClaw 已安装
- Greyfield 0.1.0+（作为宿主）

#### 安装

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
    mode: "auto"  # auto | simple | hive
    synapses:
      - name: "code-expert"
        domains: ["code", "debug"]
        model: "gpt-4o"
```

---

## 🎯 快速开始

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
        model: "gpt-4o"
```

然后启动 Greyfield，说：

> *"帮我研究 Python 爬虫框架并写个示例"*

虫群会自动：
- 判断复杂度 → 触发 Hive 模式
- 调度枪虫（搜索框架）→ 脑虫（分析对比）→ 刀虫（写代码）
- 在 Trial Panel 展示过程

### 方式二：独立使用

```python
from greyfield_hive import TyranidClaw, HiveConfig

hive = TyranidClaw(config=HiveConfig())

# 提交任务
async for event in hive.submit_task("帮我设计一个API"):
    print(f"[{event.type}] {event.payload}")
```

---

## 🆚 与 CrewAI / MetaGPT / AutoGen 对比

| 特性 | CrewAI | MetaGPT | AutoGen | **虫群** |
|:---|:---|:---|:---|:---|
| **治理模式** | 现代团队 | 软件公司 | 平等协商 | **虫群进化** |
| **审核机制** | 可选 | 可选 | 无 | **强制审查（脑虫专职）** |
| **任务赛马** | ❌ | ❌ | ❌ | **✅ 条件双路赛马** |
| **进化体系** | ❌ | ❌ | ❌ | **✅ 战功晋升/降级** |
| **频道化** | ❌ | ❌ | ❌ | **✅ Discord 式多频道** |
| **人机协作** | 弱 | 弱 | 中等 | **✅ 人类可插话/审批** |
| **经验落盘** | 记忆 | 记忆 | 上下文 | **✅ 三层基因强制注入** |

---

## 🏛️ 目录结构

```
tyranid-hive/
├── config/                          # 配置（文件驱动）
│   ├── governance/
│   │   └── tyranid.yaml            # 虫群治理模式定义
│   ├── synapses/                    # 小主脑配置
│   │   ├── code-expert.yaml
│   │   └── research-analyst.yaml
│   └── genes/                       # 基因库（三层）
│       ├── constitution/            # 宪法（极稳定）
│       ├── playbook/                # 战术手册（领域经验）
│       └── lessons/                 # 近期教训（JSONL）
│
├── src/greyfield_hive/              # 核心代码
│   ├── core/                        # 四层实现
│   │   ├── overmind.py             # L3 主脑
│   │   ├── synapse.py              # L2 小主脑
│   │   ├── brood.py                # L1 工作组
│   │   └── unit.py                 # L0 战斗单位
│   ├── systems/                     # 核心系统
│   │   ├── evolution.py            # 进化引擎
│   │   ├── trial_race.py           # 条件赛马
│   │   ├── gene_seed.py            # 基因种子
│   │   └── message_store.py        # 消息持久化
│   └── adapters/
│       ├── openclaw.py             # OpenClaw 适配
│       └── greyfield.py            # Greyfield 适配
│
├── data/                            # 运行时数据
│   ├── greyfield-hive.db           # SQLite
│   └── lessons/                     # JSONL
│
├── tests/                           # 测试
└── docs/                            # 文档
```

---

## 📊 任务流程

```
用户输入
    ↓
主脑分析（复杂度判断）
    ↓
    ├─ 简单 → 直接调度 Unit 执行
    └─ 复杂 → 创建小主脑 → 分解任务
              ↓
        创建 Brood（工作组）
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
| 🟡 queued | 任务排队等待 |
| 🔵 analyzing | 主脑分析中 |
| 🟠 planning | 小主脑分解任务 |
| 🟣 racing | 赛马进行中（两路） |
| 🔴 reviewing | 脑虫审查中 |
| 🟢 completed | 任务完成 |
| ⚫ failed | 任务失败 |

---

## 🎮 Dashboard 功能（即将到来）

- **主频道（Trunk）** — 关键节点流，领导视角
- **赛马面板** — 双路 Trial 实时进度对比
- **战功排行榜** — Unit 战功积累可视化
- **基因库** — Constitution/Playbook/Lessons 管理
- **小主脑状态** — 常驻/试验/休眠三态切换
- **Ledger** — 晋升记录、淘汰审计
- **频道浏览器** — 多频道切换、历史检索

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
- [ ] 小主脑试验/休眠自动化
- [ ] PostgreSQL 迁移

### Phase 3 — 星际航行

- [ ] 跨 Hive 协作（多个 Greyfield 实例间）
- [ ] 基因市场（Playbook 交易/分享）
- [ ] 自适应进化（自动 Constitution 调整）

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

**用虫群的方式，让 AI 协作进化。**

> *"我们并非个体，我们是虫群。"*
>
> *—— 主脑 Overmind*

[![Star History Chart](https://api.star-history.com/svg?repos=zuiho-kai/tyranid-hive&type=Date)](https://star-history.com/#zuiho-kai/tyranid-hive&Date)

</div>

---

## 📜 协议

MIT License — 与 OpenClaw、Greyfield、edict 保持一致。
