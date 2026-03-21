# Greyfield Hive — 虫群核心 v0.2

> 泰伦虫族式多 Agent 调度系统，基于 OpenClaw 框架，适配 Greyfield 宿主。
> 设计文档: [Greyfield Module E v2.2](../Greyfield/docs/design/module-e-hive/design-v2.md)

## 核心架构（v2.2 对齐）

### 四层层级（精简后）

```
L3 Overmind（主脑）
    └── 全局战略、复杂度判断、赛马仲裁、进化决策

L2 Submind（小主脑）
    └── 领域战术、任务分解、Brood协调、三态管理（常驻/试验/休眠）

L1 Brood（虫群工作组）
    └── 任务隔离、内部协作、执行协调

L0 Unit（战斗单位）
    ├── Core：专业执行者（设计虫/前端虫/后端虫/审核虫）
    ├── ToolAction：原子任务（原 Drone 层级并入）
    └── GeneSeed：领域经验注入（Constitution + Playbook + Lessons）
```

### 三大核心机制

**1. 条件赛马（Conditional Trial Broods）**
- 触发条件：外部执行 + 多路径 + 高风险 + 历史失败率高（满足2项以上）
- 固定两路：不允许3路以上
- 硬门槛：成功完成、不违反约束、通过审查
- 软评分：质量40%、速度20%、健壮性15%、复用10%、成本-15%

**2. 基因分层注入（强制落盘）**
- **Constitution（宪法）**：极稳定规则，直灌 prompt
- **Playbook（战术手册）**：领域经验，检索注入
- **Lessons（近期教训）**：高频写入，30天衰减

**3. 消息持久化与总结（Cat Cafe 式）**
- 所有消息实时持久化到 SQLite
- 事件驱动总结（任务完成、分支淘汰、用户插话）
- 原文保留，支持检索和"展开查看"

### 多频道结构（Discord 式）

```
左侧频道栏          中间 Trunk（主干）              右侧详情面板（折叠）
───────────        ───────────────────────         ───────────────────
• 主频道（Trunk）    主脑: 分析需求，复杂度: 中等...   [Trial Panel]（展开）
• Hive: 爬虫任务     小主脑-A: 方案A，预计95%        - 分支A进度
• Trial: task-001    小主脑-B: 方案B，预计98%        - 分支B进度
• Ledger             主脑: 选择方案B...              [Hive Channel]
                                                             - 资源状态
                                                             [Ledger View]
                                                             - 战功记录
```

- **Trunk（主干）**：仅 10-15 条关键节点，领导视角
- **右侧详情面板**：默认折叠，用户主动展开

## 目录结构（v2.2 对齐）

```
greyfield-hive/
├── config/
│   ├── governance/
│   │   └── tyranid.yaml          # 治理模式定义（4层结构）
│   ├── synapses/                 # 小主脑配置（文件驱动）
│   │   ├── code-expert.yaml
│   │   └── research-analyst.yaml
│   └── genes/                    # 基因库（三层结构）
│       ├── constitution/         # 宪法（极稳定规则）
│       │   └── baseline.yaml
│       ├── playbook/             # 战术手册（领域经验）
│       │   ├── frontend.yaml
│       │   ├── backend.yaml
│       │   └── designer.yaml
│       └── lessons/              # 近期教训（JSONL，高频写入）
│           └── 2026-03-21.jsonl
│
├── src/greyfield_hive/
│   ├── __init__.py
│   ├── claw.py                   # TyranidClaw（主脑）
│   ├── config.py                 # 配置模型
│   │
│   ├── core/                     # 核心层级实现
│   │   ├── overmind.py           # L3 主脑
│   │   ├── synapse.py            # L2 小主脑（三态管理）
│   │   ├── brood.py              # L1 工作组
│   │   └── unit.py               # L0 战斗单位（含 ToolAction）
│   │
│   ├── systems/                  # 核心系统
│   │   ├── evolution.py          # 进化引擎（战功/晋升）
│   │   ├── trial_race.py         # 条件赛马
│   │   ├── gene_seed.py          # 基因种子（三层加载）
│   │   ├── synapse_net.py        # 虫巢意识网
│   │   └── message_store.py      # 消息持久化（Cat Cafe 式）
│   │
│   ├── units/                    # 专业 Unit 类型
│   │   ├── designer.py           # 设计虫
│   │   ├── frontend.py           # 前端虫
│   │   ├── backend.py            # 后端虫
│   │   └── reviewer.py           # 审核虫
│   │
│   └── adapters/
│       ├── openclaw.py           # OpenClaw 框架适配
│       └── greyfield.py          # Greyfield 宿主适配
│
├── data/                         # 运行时数据
│   ├── greyfield-hive.db         # SQLite（消息、战功）
│   └── lessons/                  # JSONL 高频写入
│
├── tests/
└── docs/
```

## 与 Greyfield 集成

```yaml
# greyfield/conf.yaml
plugins:
  hive:
    enabled: true
    mode: "auto"                    # auto | simple | hive

    overmind:
      model: "claude-sonnet-4-20250514"
      complexity_threshold: 0.7     # 触发 Hive 的阈值

    synapses:
      - name: "code-expert"
        domains: ["code", "debug"]
        model: "gpt-4o"
        state: "resident"           # resident | trial | dormant

    storage:
      phase: "sqlite"               # sqlite | postgres
      path: "data/hive.db"

    channels:
      expose_to_user: true
      default_collapsed: true       # 详情面板默认折叠

    evolution:
      enabled: false                # Phase E3 开启
```

## 关键实现（v2.2 对齐）

### 1. 基因强制加载（启动时）

```python
class Unit:
    def __init__(self, unit_type: str, domain: str):
        # 强制加载三层基因
        self.constitution = GeneSeed.load_constitution()      # 直灌
        self.playbook = GeneSeed.load_playbook(domain)        # 检索
        self.lessons = GeneSeed.load_lessons(domain, days=30) # 检索

        # 组装系统提示词
        self.system_prompt = self._assemble_prompt()
```

### 2. 条件赛马（固定两路）

```python
class Overmind:
    def should_trigger_trial(self, task: Task) -> bool:
        """判断是否触发赛马（满足2项以上）"""
        conditions = [
            task.requires_external_execution(),      # 需要外部执行
            task.has_multiple_paths(),               # 存在多路径
            task.is_high_risk(),                     # 高风险
            task.recent_failure_rate() > 0.3,        # 历史失败率高
        ]
        return sum(conditions) >= 2

    def create_trial_broods(self, task: Task) -> Tuple[Brood, Brood]:
        """固定创建两路 Brood"""
        return (Brood(strategy="A"), Brood(strategy="B"))
```

### 3. 消息存储（事件驱动总结）

```python
class MessageStore:
    """三层存储"""

    async def save_message(self, msg: Message):
        # 1. 原文写入 SQLite（实时）
        await self.db.insert("messages", msg)

    async def generate_summary(self, event: Event):
        # 2. 事件驱动生成摘要（非定时）
        if event.type in ["brood_complete", "trial_eliminated", "user_intervention"]:
            summary = await self.summarize(event.context)
            await self.vector_store.insert("summaries", summary)
```

## 安装

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 集成到 Greyfield
# 1. 在 greyfield/conf.yaml 中启用 plugins.hive
# 2. 确保 greyfield-hive 在 Python 路径中
```

## Phase 计划（与 Module E 对齐）

| Phase | 目标 | 关键交付 |
|-------|------|---------|
| **E0** | 接口锁定 | DecisionRuntime 接口、4层抽象、基因加载接口 |
| **E1** | 单路跑通 | Overmind→Submind→Brood→Unit 链路、SQLite消息存储 |
| **E2** | 条件赛马 | 固定两路赛马、硬门槛筛选、软评分收敛 |
| **E3** | 基因库 + 强制落盘 | Constitution/Playbook/Lessons 三层、30天衰减、战功系统 |
| **E4** | Dashboard + PG | Web管理界面、PostgreSQL迁移 |

## 协议

MIT License — 与 OpenClaw、Greyfield 保持一致。
