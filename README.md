# 虫群 · Tyranid Hive

> **我用 4 亿年前的虫群进化论，重新设计了 AI 多 Agent 协作架构。**
> 结果发现，自然选择比人工规则更懂优胜劣汰。

**虫群**是一个基于**泰伦虫族社会结构**的多 Agent 调度系统，具备神经进化能力、条件赛马机制和战功晋升体系。对外呈现 Discord 式多频道结构，对内以严格等级制运行。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![OpenClaw](https://img.shields.io/badge/Built%20on-OpenClaw-orange)

---

## 🚀 30 秒快速体验

```bash
# Docker 一键启动（即将到来）
docker run -p 7892:7892 greyfield/hive-demo

# 打开浏览器
open http://localhost:7892
```

---

## 📐 架构：四层神经等级

| 层级 | 角色 | 英文名 | 职责 | 状态 |
|------|------|--------|------|------|
| **L3** | 🧠 主脑 | Overmind | 战略决策、复杂度判断、赛马仲裁、进化决策 | 系统唯一，永不沉睡 |
| **L2** | 🎯 小主脑 | Submind | 战术调度、任务分解、Brood 协调 | 常驻/试验/休眠三态 |
| **L1** | 🐛 工作组 | Brood | 任务隔离、内部协作、执行协调 | 动态组建 |
| **L0** | ⚔️ 战斗单位 | Unit | 专业执行（设计虫/前端虫/后端虫）+ ToolAction | 基因注入 |

### 三大核心机制

**🔬 条件赛马（Conditional Trial）**
- 满足 2 项以上触发：外部执行、多路径、高风险、历史失败率高
- 固定两路 Brood 并行，硬门槛筛选 + 软评分收敛
- 用户可在 Trial Panel 实时干预

**🧬 基因分层进化（Gene Evolution）**
- **Constitution（宪法）**：极稳定规则，直灌 Prompt
- **Playbook（战术手册）**：领域经验，检索注入
- **Lessons（近期教训）**：高频写入，30 天衰减

**📊 多频道暴露（Multi-Channel）**
- **Trunk（主干）**：仅 10-15 条关键节点，领导视角
- **Trial/Hive/Ledger**：详情面板默认折叠，用户主动展开

---

## 🆚 与 CrewAI / MetaGPT / AutoGen 对比

| 特性 | CrewAI | MetaGPT | AutoGen | **虫群** |
|------|--------|---------|---------|----------|
| **治理模式** | 现代团队 | 软件公司 | 平等协商 | **虫群进化** |
| **审核机制** | 可选 | 可选 | 无 | **强制审查（脑虫专职）** |
| **任务赛马** | ❌ | ❌ | ❌ | **✅ 条件双路赛马** |
| **进化体系** | ❌ | ❌ | ❌ | **✅ 战功晋升/降级** |
| **频道化** | ❌ | ❌ | ❌ | **✅ Discord 式多频道** |
| **人机协作** | 弱 | 弱 | 中等 | **✅ 人类可插话/审批** |
| **经验落盘** | 记忆 | 记忆 | 上下文 | **✅ 三层基因强制注入** |

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
> "帮我研究 Python 爬虫框架并写个示例"

虫群会自动：
1. 判断复杂度 → 触发 Hive 模式
2. 调度枪虫（搜索框架）→ 脑虫（分析对比）→ 刀虫（写代码）
3. 在 Trial Panel 展示过程

### 方式二：独立使用

```python
from greyfield_hive import TyranidClaw, HiveConfig

hive = TyranidClaw(config=HiveConfig())

# 提交任务
async for event in hive.submit_task("帮我设计一个API"):
    print(f"[{event.type}] {event.payload}")
```

---

## 🏛️ 目录结构

```
tyranid-hive/
├── config/                     # 配置（文件驱动）
│   ├── governance/
│   │   └── tyranid.yaml        # 虫群治理模式定义
│   ├── synapses/               # 小主脑配置
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
│   │   ├── synapse.py          # L2 小主脑
│   │   ├── brood.py            # L1 工作组
│   │   └── unit.py             # L0 战斗单位
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
|------|------|
| 🟡 **queued** | 任务排队等待 |
| 🔵 **analyzing** | 主脑分析中 |
| 🟠 **planning** | 小主脑分解任务 |
| 🟣 **racing** | 赛马进行中（两路） |
| 🔴 **reviewing** | 脑虫审查中 |
| 🟢 **completed** | 任务完成 |
| ⚫ **failed** | 任务失败 |

---

## 🎮 Dashboard 功能（即将到来）

1. **主频道（Trunk）** — 关键节点流，领导视角
2. **赛马面板** — 双路 Trial 实时进度对比
3. **战功排行榜** — Unit 战功积累可视化
4. **基因库** — Constitution/Playbook/Lessons 管理
5. **小主脑状态** — 常驻/试验/休眠三态切换
6. **Ledger** — 晋升记录、淘汰审计
7. **频道浏览器** — 多频道切换、历史检索

---

## 🛠️ 技术栈

- **Python**: 3.10+
- **异步框架**: asyncio
- **配置**: Pydantic + YAML
- **存储**: SQLite（Phase 1-2）→ PostgreSQL（Phase 3+）
- **向量检索**: ChromaDB
- **宿主集成**: Greyfield（Electron + Live2D）
- **框架**: OpenClaw

---

## 📜 协议

MIT License — 与 OpenClaw、Greyfield、edict 保持一致。

---

## 🙏 致谢

- [OpenClaw](https://github.com/OpenClaw) — 框架基础
- [edict](https://github.com/cft0808/edict) — 三省六部制灵感
- [Greyfield](https://github.com/zuiho-kai/greyfield) — 宿主系统

---

**用虫群的方式，让 AI 协作进化。**
