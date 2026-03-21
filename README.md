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
宿主(Host) 下令 → 主脑(Overmind) 决策 → 小主脑(Submind) 调度 → 虫群组(Brood) 执行 → 单位(Unit) 作战
                          │
                          ├─ Conditional Trial（双路赛马）
                          ├─ Vision Arbiter（愿景判尺）
                          └─ Gene Evolution（基因沉淀）
```

**一句话**：在 Hive 中，复杂任务先经过两路小主脑的狩猎竞赛，胜者晋升常驻，败者休眠——不是"协作"，是"优胜劣汰"。

---

## 💡 为什么选 Hive？

### 传统多 Agent 框架的问题

| 问题 | 表现 |
|------|------|
| 单路径依赖 | 任务只走单一路径，失败全凭运气 |
| 审核软化 | 审核与仲裁不是强制流程，质量不可控 |
| 经验流失 | 教训停留在上下文，不能复用，下次照犯 |
| Agent 不进化 | 做了 100 次任务和做了 1 次没有区别 |

### Tyranid Hive 的回答

| 机制 | 实现 | 收益 |
|------|------|------|
| **分层治理** | Overmind → Submind → Brood → Unit 硬分层 | 每层职责清晰，可定位、可干预 |
| **条件赛马** | 复杂任务触发双路 Submind 并行竞争 | 用竞争降低单路径失误，用评分收敛质量 |
| **小主脑复用** | 胜者晋升常驻，败者休眠，不是一次性消耗品 | 积累领域能力，越用越强 |
| **基因进化** | Constitution / Playbook / Lessons 三层沉淀 | 经验写入基因，强制注入，不看也得看 |
| **多频道审计** | Trunk / Trial / Hive / Ledger 分层暴露 | 领导看主干，开发者看详情，审计看记录 |

<details>
<summary><b>🔍 为什么「小主脑复用」才是核心竞争力？（点击展开）</b></summary>

<br>

CrewAI 和 AutoGen 的 Agent 是一次性的：任务完成就销毁，经验归零。

Hive 的 **Submind（小主脑）** 是**可复用的治理资产**：

- 每个 Submind 有独立状态（**常驻 / 试验 / 休眠** 三态）
- 在赛马中表现优异的 Submind 会**晋升为常驻领域专家**，下次同类任务优先调度
- 持续低战功的 Submind 会进入休眠，再次失败则淘汰（Purge）
- 这意味着系统会逐渐形成一批**经过真实任务验证的专家小主脑**

**核心主张**：对复杂任务来说，单路径不是效率，而是赌运气。Trial 的意义，是让结果先经过狩猎，再让胜者成为下一次的主力。

</details>

---

## 🎬 Demo

以下是虫群处理"帮我写个爬虫抓取豆瓣 Top250"的完整真实流程：

```
用户输入: "帮我写个爬虫抓取豆瓣 Top250"
           ↓
[主频道 · Trunk]────────────────────────────────────────────────────
│ [主脑]    分析需求：复杂度高，触发双路赛马
│ [主脑]    孵化试验小主脑 Submind-A（requests）、Submind-B（playwright）
│ [主脑]    @用户 两个方案并行中，预计 2 分钟完成，可在 Trial 面板查看
│ ...
│ [愿景]    比较结果：方案B成功率更高（98% vs 95%），符合愿景
│ [主脑]    Trial 完成 → 选择 Submind-B（playwright）
│ [主脑]    Submind-B 表现优异，晋升为常驻代码专家 +1
│ [系统]    Submind-A 进入休眠
├────────────────────────────────────────────────────────────────────

[Trial 面板 · 折叠]─────────────────────────────────────────────────
│ ├─ [Submind-A · requests]    成功率 95% · 耗时 30s · 评分 82.1
│ └─ [Submind-B · playwright]  成功率 98% · 耗时 36s · 评分 89.4  ← 胜者
├────────────────────────────────────────────────────────────────────

[Ledger · 折叠]──────────────────────────────────────────────────────
│  Submind-B 战功 +1 → 常驻代码专家（playwright 领域）
│  Submind-A 战功 -1 → 休眠（同类任务优先级降低）
│  Lesson 写入：豆瓣反爬 → playwright 成功率显著高于 requests
└────────────────────────────────────────────────────────────────────
```

**Trunk 只有 10-15 条关键消息**；Trial、Ledger 默认折叠——你不会被 50 条 Agent 日志淹没。

```bash
# 本地启动（Docker，即将到来）
docker run -p 7892:7892 greyfield/hive-demo
open http://localhost:7892
```

---

## 🏛️ 架构

### UI 结构（Discord 式三栏）

```
┌──────────────────┬──────────────────────────────────┬────────────────────────────────┐
│ 左侧：频道导航   │ 中间：主频道 Trunk               │ 右侧：详情面板（默认折叠）      │
│                  │                                  │                                │
│ • Trunk  [默认]  │ [主脑]  分析需求，触发赛马...    │ ┌─────────┐ ┌────────────────┐│
│ • Trial  [折叠]  │ [小主脑-A] 方案A：requests       │ │ Trial   │ │ Ledger         ││
│ • Hive   [折叠]  │ [小主脑-B] 方案B：playwright     │ │ 赛马进度 │ │ 晋升记录       ││
│ • Ledger [折叠]  │ [主脑]  @用户 进行中，2分钟...   │ │ 双路对比 │ │ 战功排行       ││
│                  │ [主脑]  选B，Submind-B晋升 +1    │ └─────────┘ └────────────────┘│
└──────────────────┴──────────────────────────────────┴────────────────────────────────┘
```

### 等级制（四层神经结构）

| 层级 | 角色 | 职责 | 状态 |
|:---:|:---|:---|:---|
| **L3** | 🧠 主脑 · Overmind | 战略决策、赛马触发与仲裁、进化裁决 | 系统唯一，永不沉睡 |
| **L2** | 🎯 小主脑 · Submind | 领域级战术调度、任务分解、Brood 协调 | **常驻 / 试验 / 休眠** 三态 |
| **L1** | 🐛 虫群组 · Brood | 动态组建的协作执行组，内部直接协作 | 动态创建，任务完成后解散 |
| **L0** | ⚔️ 单位 · Unit | 专业执行者（前端虫 / 后端虫 / 设计虫 / 审核虫）+ ToolAction | 基因注入，战功积累 |

> **Hive（虫巢容器）** 不是治理层级，而是 Session 级资源隔离环境——负责上下文边界与生命周期，不参与决策。

```
                    ┌─────────────┐
                    │   👤 宿主   │
                    └──────┬──────┘
                           │ submit_task()
                    ┌──────▼──────────────────────────┐
                    │  🧠 主脑 · Overmind (L3)         │
                    │  复杂度判断 · 赛马仲裁 · 进化裁决 │
                    └──────┬──────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ↓                         ↓
    ┌─────────────────┐      ┌─────────────────┐
    │ 🎯 小主脑-A     │      │ 🎯 小主脑-B     │
    │ Submind (Trial) │      │ Submind (Trial) │
    │ 方案 A          │      │ 方案 B          │
    └────────┬────────┘      └────────┬────────┘
             │                        │
    ┌────────▼────────┐      ┌────────▼────────┐
    │  Brood + Units  │      │  Brood + Units  │
    │  前端虫/后端虫  │      │  前端虫/后端虫  │
    └─────────────────┘      └─────────────────┘
              │                        │
              └────────────┬───────────┘
                           ↓
                    ┌──────▼──────────────────────────┐
                    │  👁️ Vision Arbiter（愿景判尺）   │
                    │  一致标准比较 · 发现需求缺口      │
                    └──────┬──────────────────────────┘
                           │ 胜者晋升常驻 / 败者休眠
                    ┌──────▼──────────────────────────┐
                    │  🧠 主脑收敛 · 写入 Ledger       │
                    └──────────────────────────────────┘
```

---

## 🧬 核心机制

### 一、条件赛马（Conditional Trial）

**硬规则触发**——满足 2 项以上才开赛马，不随意消耗资源：

| 触发条件 | 说明 |
|----------|------|
| 需要外部执行 | 涉及浏览器/桌面/API 等外部操作 |
| 存在多可行路径 | 技术方案不唯一（如 requests vs playwright） |
| 高风险操作 | 数据修改、安全敏感、不可回滚 |
| 历史失败率高 | 同 domain 近 7 天失败率 > 30% |

**收敛判据（两层）**：

第一层：硬门槛（全部通过才进入评分）

```
outcome_success      任务是否成功完成
constraint_violation 是否违反约束
review_passed        是否通过审查
```

第二层：软评分（在通过硬门槛的候选中比较）

| 维度 | 权重 |
|------|------|
| 结果质量（功能正确性、代码质量） | +40% |
| 速度奖励 | +20% |
| 健壮性（错误处理、边界情况） | +15% |
| 复用价值（方案可复用性） | +10% |
| Token 成本 | −10% |
| 协作开销（Brood 协调成本） | −5% |

**赛马规则**：固定两路，不允许三路以上；隔离环境执行；用户可在 Trial Panel 实时查看并手动干预。

---

### 二、小主脑复用（Submind Lifecycle）

小主脑是**可复用治理资产**，不是一次性消耗品：

```
常驻（Resident）  ←─── 持续正向增益 + 可量化优势
      ↕                转正条件：交接质量稳定 + 历史胜率
试验（Trial）     ←─── 新领域 / 赛马需求 / 过载 / 退化检测
      ↕
休眠（Dormant）   ←─── 持续低战功 / 赛马落败
      ↓
淘汰（Purge）     ←─── 重复失败（策略/质量类），四级惩罚到底
```

**实际效果**：随着任务积累，系统会形成一批"经过真实任务验证的常驻领域专家"，再遇到同类任务时，优先调度战功最高的那一个。

---

### 三、愿景分身（Vision Arbiter）

- **不是第二主脑**，而是赛马的一致判尺
- 维护任务愿景边界和 done-when 定义
- 作为两路结果比较的公平标准
- 发现需求缺口时上抛给主脑或用户

没有它，赛马收敛就是主脑的主观判断；有了它，比较有了客观依据。

---

### 四、基因进化（Gene Evolution）

经验不是聊天记录，而是会被提炼、固化、继承和淘汰的基因。

**三层结构**：

| 层级 | 名称 | 注入方式 | 特点 |
|:---|:---|:---|:---|
| **L1** | Constitution（宪法） | 直灌 prompt，强制 | 安全规范 / 编码底线，永不衰减 |
| **L2** | Playbook（战术手册） | 检索后注入，Top-K | 领域经验，版本化管理，RAG 召回 |
| **L3** | Lessons（近期教训） | 检索后注入，自然衰减 | 30 天时效，越用越精确 |

**Lessons 衰减公式**：

```
score = exp(−0.1 × days) × log(1 + frequency) × domain_match × tag_overlap
```

老经验自然沉底，常被复用的经验自动浮上来，无需人工归档。

**强制落盘**——两条硬规则：

```python
# 规则一：Unit 启动时强制加载基因，失败则无法启动
self.constitution = GeneSeed.load_constitution(required=True)

# 规则二：任务失败时强制写入 Lessons，不能跳过
def on_failure(self, task, unit, error):
    LessonsBank.add(lesson)   # 同步写入，立即生效
```

**失败分类与惩罚**（先分类再惩罚，环境故障不背锅）：

| 失败类型 | 惩罚力度 | 说明 |
|----------|----------|------|
| 环境失败（网络/权限/超时） | **不惩罚** | 外部因素，不怪 Unit |
| 理解失败（误解任务/漏约束） | 轻微 | 可优化，不严重降级 |
| 策略失败（路线不优） | 中等 | 进入四级惩罚流程 |
| 质量失败（结果不达标） | 严重 | 进入四级惩罚流程 |

**四级惩罚**（策略/质量失败，同类同域重复触发）：

```
第 1 次 → Observe：仅记录，静默观察
第 2 次 → Warn：系统通知，战功标记警告
第 3 次 → Constrained：进入受限模式，只接低风险任务
第 4 次 → Dormant：主脑裁决休眠，等待评估
```

---

### 五、多频道暴露（Multi-Channel）

| 频道 | 内容 | 默认 | 受众 |
|:---|:---|:---:|:---|
| **Trunk** | 关键节点（10-15 条）· 主脑决策 · 小主脑汇报 | 展开 | 决策者 |
| **Trial** | 赛马双路实时进度 · 评分对比 | 折叠 | 开发者 |
| **Hive** | 完整执行链 · Brood 协作细节 | 折叠 | 架构师 |
| **Ledger** | 战功晋升/休眠 · 赛马审计 · 基因版本 | 折叠 | 管理员 |

---

## ⚔️ 对比

| 特性 | CrewAI | MetaGPT | AutoGen | **Tyranid Hive** |
|:---|:---|:---|:---|:---|
| **治理模式** | 现代团队 | 软件公司 | 平等协商 | **虫群等级制** |
| **复杂任务** | 单路径 | 单路径 | 单路径 | **✅ 双路赛马** |
| **审核机制** | 可选 | 可选 | 无 | **✅ 强制两层** |
| **Agent 进化** | ❌ | ❌ | ❌ | **✅ 小主脑三态 + 战功** |
| **经验沉淀** | 记忆 | 记忆 | 上下文 | **✅ 三层基因（强制注入）** |
| **人机协作** | 弱 | 弱 | 中等 | **✅ 可插话/审批/仲裁** |
| **过程可见性** | 日志 | 日志 | 日志 | **✅ 多频道面板** |
| **失败处理** | 记录 | 记录 | 记录 | **✅ 分类 + 四级惩罚** |

**一句话区别**：普通框架强调"协作"，Hive 强调"在生存竞争中形成可复用的领域专家"。

---

## 🚀 快速开始

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
        model: "claude-sonnet-4-6"
      - name: "research-analyst"
        domains: ["research", "analysis"]
        model: "claude-sonnet-4-6"
```

然后启动 Greyfield，说：

> *"帮我研究 Python 爬虫框架并写个示例"*

虫群会自动：
- 主脑判断复杂度 → 触发 Hive 模式
- 孵化双路试验小主脑（requests vs playwright）
- 在 Trial Panel 展示赛马过程
- 胜者晋升常驻，经验写入 Lessons

### 独立使用

```python
from greyfield_hive import TyranidClaw, HiveConfig

hive = TyranidClaw(config=HiveConfig())

async for event in hive.submit_task("帮我设计一个 API"):
    print(f"[{event.channel}] {event.node}: {event.payload}")
```

---

## 📦 安装

**前置条件**：Python 3.10+ · OpenClaw 已安装 · Greyfield 0.1.0+（作为宿主）

```bash
git clone https://github.com/zuiho-kai/tyranid-hive.git
cd tyranid-hive
pip install -e ".[dev]"
```

```bash
# Docker（即将到来）
docker pull greyfield/hive
docker run -p 7892:7892 greyfield/hive
```

---

## ✅ 适用场景

**适合**：
- 复杂任务不能容忍单路径失败，需要双路竞争收敛
- 需要审计追溯（关键业务、合规场景）
- 希望系统越用越强，积累可复用的领域专家小主脑
- 需要人机协作（插话、审批、仲裁）

**不适合**：
- 简单单步任务（overhead 不划算）
- 强实时响应场景（赛马增加延迟）
- 完全无人值守自动化（需要人工审批节点）

---

## 🗺️ Roadmap

### Phase 1 — 神经觉醒 ✅

- [x] 四层神经等级架构（Overmind / Submind / Brood / Unit）
- [x] 条件赛马（硬门槛 + 软评分双层收敛）
- [x] 三层基因进化（Constitution / Playbook / Lessons）
- [x] 小主脑三态管理（常驻 / 试验 / 休眠）
- [x] 战功四级惩罚体系
- [x] 多频道结构（Trunk / Trial / Hive / Ledger）
- [x] OpenClaw / Greyfield 双适配

### Phase 2 — 虫巢扩张 🚧

- [ ] 实时 Dashboard（三栏面板，Discord 式布局）
- [ ] Vision Arbiter 可视化（愿景边界 + 比较理由）
- [ ] 基因库可视化（Playbook 检索、Lessons 衰减曲线）
- [ ] 小主脑生命周期管理 UI
- [ ] PostgreSQL 迁移

### Phase 3 — 星际航行

- [ ] 跨 Hive 协作（多个 Greyfield 实例间）
- [ ] 基因市场（Playbook 交易/分享）
- [ ] 自适应进化（自动 Constitution 调整）

---

## 🏗️ 目录结构

```
tyranid-hive/
├── config/
│   ├── governance/tyranid.yaml      # 虫群治理模式定义
│   ├── synapses/                    # 小主脑配置
│   └── genes/                       # 基因库（三层）
│       ├── constitution/            # 宪法（直灌 prompt）
│       ├── playbook/                # 战术手册（按领域）
│       └── lessons/                 # 近期教训（SQLite）
│
├── src/greyfield_hive/
│   ├── core/
│   │   ├── overmind.py              # L3 主脑
│   │   ├── submind.py               # L2 小主脑
│   │   ├── submind_registry.py      # 小主脑三态注册表
│   │   ├── vision_arbiter.py        # 愿景判尺
│   │   ├── brood.py                 # L1 虫群组
│   │   └── unit.py                  # L0 战斗单位
│   ├── systems/
│   │   ├── trial_race.py            # 条件赛马
│   │   ├── convergence_engine.py    # 收敛引擎（硬门槛 + 软评分）
│   │   ├── evolution_engine.py      # 进化引擎（四级惩罚）
│   │   ├── gene_seed.py             # 基因种子
│   │   ├── lessons_bank.py          # 教训库（衰减公式）
│   │   ├── failure_capture.py       # 失败捕获（强制落盘）
│   │   └── message_store.py         # 消息持久化
│   └── adapters/
│       ├── openclaw.py
│       └── greyfield.py
│
└── data/
    ├── greyfield-hive.db            # SQLite（消息 + 战功 + Ledger）
    └── chroma/                      # 向量检索（Lessons）
```

---

## 🛠️ 技术栈

| 组件 | 技术 |
|:---|:---|
| **语言** | Python 3.10+ |
| **异步框架** | asyncio |
| **配置** | Pydantic + YAML |
| **存储** | SQLite（Phase 1-2）→ PostgreSQL（Phase 3+） |
| **向量检索** | ChromaDB（Phase 1-2）→ pgvector（Phase 3+） |
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
| 小主脑 | Submind | L2 领域专家，可复用，三态管理 |
| 虫群组 | Brood | L1 动态协作执行组 |
| 单位 | Unit | L0 专业执行者（前端虫/后端虫/设计虫/审核虫） |
| 愿景判尺 | Vision Arbiter | 赛马的一致比较标准，不是第二主脑 |
| 赛马 | Trial | 双路竞争机制，复杂任务触发 |
| 基因 | Gene | 经验沉淀的三层结构（宪法/手册/教训） |
| 进化 | Evolution | 基因更新、战功晋升、四级淘汰 |
| 虫巢容器 | Hive | Session 级资源隔离环境，不是治理层 |
