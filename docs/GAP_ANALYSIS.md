# Tyranid Hive — 缺口分析与设计规格

> Opus 设计，Sonnet 实现。本文档记录 README 愿景与当前代码之间的每一个结构性缺口，
> 并给出可直接编码的设计规格。

---

## 一、完成度矩阵

| 模块 | README 承诺 | 当前实现 | 完成度 | 优先级 |
|------|------------|---------|--------|--------|
| 执行模式自动路由 | 主脑判断 Solo/Trial/Chain/Swarm | 用户手动调不同 API | 10% | **P0** |
| 收敛引擎（Trial 评分） | 硬门槛 + 六维软评分 | stdout 长度比较 | 15% | **P1** |
| Submind 实体 | L2 域内 CEO，三态管理，跨域协商 | 不存在 | 0% | **P2** |
| 生物质消耗侧 | Drain = 待机+执行+协调 token 成本 | 只有 Harvest | 30% | **P3** |
| 进化大师增强 | 两阶段复盘 + TrialClosed 订阅 + Skill 自合成 | 计数≥5 → 拼 Markdown | 20% | **P4** |
| 赛前论证 | ~500 token 快速推理决定是否开赛 | 不存在 | 0% | P0 子项 |
| 失败分类 | 环境/理解/策略/质量 四级惩罚 | 统一 0.3 惩罚 | 10% | P3 子项 |
| 基因本源追踪 | GeneSeed 谱系连续性决定身份 | 不存在 | 0% | P2 子项 |
| Playbook 语义聚类审计 | 冗余检测 + 孤岛标记 + 域边界 | 不存在 | 0% | P4 子项 |
| Discord 式三栏 UI | Trunk/Trial/Hive/Ledger 四频道 | React 脚手架 | 5% | P5（本轮不做） |

---

## 二、现有数据流（理解集成点）

```
用户 POST /tasks
  → task.created 事件
  → OrchestratorWorker._on_task_created()
    → 发布 task.dispatch(synapse="overmind", next_state=Planning)
  → DispatchWorker._dispatch()
    → 调用 OvermindAgent.analyze() 或 OpenClaw CLI
    → 写回 todos / progress_log
    → 发布 task.status(to=Planning)
  → OrchestratorWorker._on_task_status()
    → STATE_SYNAPSE_MAP[Planning] = "overmind" → 再次派发
    → ... 最终到 Spawning → Executing → dispatcher 调用实际 synapse
    → Complete → evolution-master 复盘
```

关键集成点：
- **模式路由插入点**：Reviewing → Spawning 之间（orchestrator 层）
- **收敛引擎插入点**：trial_race.py 的 `_pick_winner()` 方法
- **Drain 记录插入点**：dispatcher._dispatch() 执行前后
- **进化增强插入点**：evolution_master.py 的 `evolve_domain()` 方法

---

## 三、P0 — 执行模式自动路由

### 现状
- `OvermindAgent.analyze()` 返回 `recommended_state`（Planning/Executing/Dormant），不返回 exec_mode
- `Task.exec_mode` 字段存在但从未被自动填充
- 用户必须手动调用 `POST /tasks/<id>/trial`、`/chain`、`/swarm`

### 目标
主脑分析任务后自动判断 Solo/Trial/Chain/Swarm，无需用户干预。

### 设计规格

#### 3.1 扩展 OvermindResult

```python
# agents/overmind_agent.py — 修改 OvermindResult
@dataclass
class OvermindResult:
    summary: str
    todos: list[str]
    risks: list[str]
    recommended_state: str
    domain: str
    # ── 新增 ──
    exec_mode: str = "solo"           # solo/trial/chain/swarm
    mode_justification: str = ""      # 为什么选这个模式
    trial_candidates: list[str] = field(default_factory=list)   # Trial 时的两条路径描述
    chain_stages: list[dict] = field(default_factory=list)      # Chain 时的阶段定义
    swarm_units: list[dict] = field(default_factory=list)       # Swarm 时的并发单元定义
    raw_response: str = ""
```

#### 3.2 修改 LLM Prompt

在 `_SYSTEM_TEMPLATE` 的 JSON 输出格式中增加：

```json
{
  "exec_mode": "solo | trial | chain | swarm",
  "mode_justification": "选择该模式的理由（一句话）",
  "trial_candidates": ["路径A描述", "路径B描述"],
  "chain_stages": [
    {"stage": 1, "domain": "...", "description": "...", "synapse": "..."}
  ],
  "swarm_units": [
    {"domain": "...", "message": "...", "synapse": "..."}
  ]
}
```

在 system prompt 中注入模式选择规则（从 README 提取）：

```
## 执行模式判断规则（优先级从高到低）
1. 有多条独立可行路径 + 结果可客观比较 → trial
2. 子任务之间有线性依赖，必须串行 → chain
3. 子任务完全独立，无状态依赖 → swarm
4. 单文件/顺序工具链/日常问答 → solo

注意：trial 模式需要 trial_candidates 非空；chain 需要 chain_stages 非空；swarm 需要 swarm_units 非空。
```

#### 3.3 新建 ModeRouter 服务

```python
# services/mode_router.py
class ModeRouter:
    """根据 OvermindResult.exec_mode 路由到对应执行路径"""

    def __init__(self, db, bus, trial_svc, chain_svc, swarm_svc):
        self.db = db
        self.bus = bus
        self.trial = trial_svc
        self.chain = chain_svc
        self.swarm = swarm_svc

    async def route(self, task_id: str, result: OvermindResult) -> None:
        mode = ExecutionMode(result.exec_mode)

        # 写入 task.exec_mode
        async with self.db() as session:
            svc = TaskService(session)
            await svc.update_exec_mode(task_id, mode)

        if mode == ExecutionMode.Solo:
            await self._route_solo(task_id, result)
        elif mode == ExecutionMode.Trial:
            await self._route_trial(task_id, result)
        elif mode == ExecutionMode.Chain:
            await self._route_chain(task_id, result)
        elif mode == ExecutionMode.Swarm:
            await self._route_swarm(task_id, result)

    async def _route_solo(self, task_id, result):
        """Solo: 走现有 Spawning → Executing 流程"""
        await self.bus.publish(
            topic=TOPIC_TASK_STATUS,
            event_type="task.status.change",
            producer="mode-router",
            payload={"task_id": task_id, "to": TaskState.Spawning.value},
        )

    async def _route_trial(self, task_id, result):
        """Trial: 调用 TrialRaceService"""
        if len(result.trial_candidates) < 2:
            # 降级为 Solo
            return await self._route_solo(task_id, result)
        # 从 Submind 注册表选两个 synapse（P2 实现前用默认值）
        synapse_a = result.trial_candidates[0] if ... else "synapse-a"
        synapse_b = result.trial_candidates[1] if ... else "synapse-b"
        trial_result = await self.trial.run(task_id, synapse_a, synapse_b, message=...)
        # 写回结果，转 Consolidating
        ...

    async def _route_chain(self, task_id, result):
        """Chain: 构建 stages 调用 ChainRunnerService"""
        stages = [(s["synapse"], s["description"]) for s in result.chain_stages]
        chain_result = await self.chain.run(task_id, stages, message=...)
        ...

    async def _route_swarm(self, task_id, result):
        """Swarm: 构建 units 调用 SwarmRunnerService"""
        units = [SwarmUnit(synapse=u["synapse"], message=u["message"], domain=u["domain"])
                 for u in result.swarm_units]
        swarm_result = await self.swarm.run(task_id, units)
        ...
```

#### 3.4 修改 Orchestrator 集成

在 `_on_task_status` 中，当状态变为 Reviewing 且 exec_mode 已设置时，
不再走 STATE_SYNAPSE_MAP 路由，而是调用 ModeRouter：

```python
# workers/orchestrator.py — _on_task_status 修改
async def _on_task_status(self, event):
    new_state = TaskState(event.payload["to"])
    task_id = event.payload["task_id"]

    # ── 新增：Reviewing 完成后走 ModeRouter ──
    if new_state == TaskState.Reviewing:
        async with SessionLocal() as db:
            task = await TaskService(db).get(task_id)
        if task and task.exec_mode and task.exec_mode != ExecutionMode.Solo:
            await self.mode_router.route(task_id, ...)
            return

    # 原有逻辑
    synapse = STATE_SYNAPSE_MAP.get(new_state)
    ...
```

#### 3.5 文件变更清单

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `agents/overmind_agent.py` | 修改 | OvermindResult 新增字段 + prompt 修改 |
| `services/mode_router.py` | **新建** | ~120 行 |
| `workers/orchestrator.py` | 修改 | _on_task_status 增加 ModeRouter 分支 |
| `services/task_service.py` | 修改 | 新增 update_exec_mode 方法 |

---

## 四、P1 — 收敛引擎升级（Trial 多维评分）

### 现状
- `trial_race.py` 的 `_pick_winner()`: 成功 > 失败；双方都成功时比 `len(stdout)`
- 无赛前论证，直接开跑
- 无硬门槛检查

### 目标
硬门槛（全部通过才进入评分）→ 六维软评分 → 赛前论证过滤

### 设计规格

#### 4.1 TrialScore 数据结构

```python
# services/convergence_engine.py
@dataclass
class TrialScore:
    """六维评分，权重来自 README"""
    quality: float = 0.0       # 0-1, LLM 判定输出质量
    speed: float = 0.0         # 0-1, 归一化耗时（越快越高）
    robustness: float = 0.0    # 0-1, 错误处理/边界覆盖
    reuse: float = 0.0         # 0-1, 可复用性/模块化
    token_cost: float = 0.0    # 0-1, token 消耗（越低越好，作为惩罚项）
    coordination: float = 0.0  # 0-1, 协调开销（越低越好，作为惩罚项）

    WEIGHTS = {
        "quality": 0.40, "speed": 0.20, "robustness": 0.15,
        "reuse": 0.10, "token_cost": -0.10, "coordination": -0.05,
    }

    @property
    def weighted(self) -> float:
        return sum(getattr(self, k) * w for k, w in self.WEIGHTS.items())
```

#### 4.2 ConvergenceEngine

```python
class ConvergenceEngine:
    """硬门槛 + 软评分 收敛引擎"""

    def __init__(self, llm_client: AnthropicClient):
        self.llm = llm_client

    def hard_gate(self, result: SynapseResult) -> tuple[bool, list[str]]:
        """硬门槛检查，返回 (通过, 失败原因列表)"""
        failures = []
        if not result.success:
            failures.append("execution_failed")
        if not result.stdout or not result.stdout.strip():
            failures.append("empty_output")
        if result.returncode != 0 and "error" in (result.stderr or "").lower():
            failures.append("critical_error")
        return (len(failures) == 0, failures)

    async def score(self, result: SynapseResult, task_context: str) -> TrialScore:
        """对通过硬门槛的结果做六维软评分"""
        # speed: 归一化（假设 budget 120s）
        speed = max(0, 1.0 - result.elapsed_sec / 120.0)

        # quality + robustness + reuse: 调用 LLM 做结构化评分
        judge_result = await self._llm_judge(result.stdout, task_context)

        return TrialScore(
            quality=judge_result["quality"],
            speed=speed,
            robustness=judge_result["robustness"],
            reuse=judge_result["reuse"],
            token_cost=self._estimate_token_cost(result),
            coordination=0.0,  # 单路无协调开销
        )

    async def _llm_judge(self, output: str, context: str) -> dict:
        """~300 token LLM 调用，评判输出质量/健壮性/复用性"""
        prompt = f"""对以下任务输出打分（0-1），返回 JSON：
任务: {context[:200]}
输出: {output[:500]}
返回: {{"quality": 0.x, "robustness": 0.x, "reuse": 0.x}}"""
        raw = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            system="你是代码质量评审员，只返回 JSON。",
            max_tokens=100, temperature=0.0,
        )
        return json.loads(raw)  # 需要容错

    def pick_winner(self, scores: dict[str, TrialScore]) -> tuple[str, TrialScore]:
        """从评分中选出胜者"""
        return max(scores.items(), key=lambda x: x[1].weighted)
```

#### 4.3 PreTrialReasoner（赛前论证）

```python
# services/pre_trial_reasoner.py
@dataclass
class PreTrialVerdict:
    should_trial: bool
    reason: str
    confidence: float  # 0-1

class PreTrialReasoner:
    """~500 token 快速推理：是否值得开赛"""

    def __init__(self, llm_client: AnthropicClient):
        self.llm = llm_client

    async def judge(self, task_title: str, task_desc: str,
                    candidates: list[str], domain_fail_rate: float) -> PreTrialVerdict:
        """
        硬触发条件（满足 ≥2 项才进入推理）：
        1. 需要外部执行（浏览器/API）
        2. 存在多可行路径
        3. 高风险操作
        4. 同 domain 近 7 天失败率 > 30%
        """
        hard_triggers = self._check_hard_triggers(task_desc, candidates, domain_fail_rate)
        if hard_triggers < 2:
            return PreTrialVerdict(False, f"硬触发条件不足({hard_triggers}/2)", 0.9)

        # 快速推理
        prompt = f"""任务: {task_title}
两条候选路径: {candidates[0]} vs {candidates[1]}
问题: 能否通过推理直接判断哪条更优？还是必须实验？
只回答 JSON: {{"should_trial": true/false, "reason": "一句话"}}"""

        raw = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            system="你是决策顾问，判断是否需要实验验证。只返回 JSON。",
            max_tokens=100, temperature=0.0,
        )
        data = json.loads(raw)
        return PreTrialVerdict(
            should_trial=data["should_trial"],
            reason=data["reason"],
            confidence=0.8,
        )

    def _check_hard_triggers(self, desc, candidates, fail_rate) -> int:
        count = 0
        if len(candidates) >= 2: count += 1
        if fail_rate > 0.3: count += 1
        ext_keywords = ["浏览器", "browser", "api", "http", "爬虫", "scrape"]
        if any(k in desc.lower() for k in ext_keywords): count += 1
        risk_keywords = ["删除", "delete", "修改数据", "不可回滚", "安全"]
        if any(k in desc.lower() for k in risk_keywords): count += 1
        return count
```

#### 4.4 修改 trial_race.py 集成

```python
# services/trial_race.py — 修改 _pick_winner → 使用 ConvergenceEngine
async def run(self, task_id, synapse_a, synapse_b, message, ...):
    # 1. 赛前论证（新增）
    verdict = await self.pre_trial.judge(...)
    if not verdict.should_trial:
        # 跳过 Trial，降级为 Solo
        return TrialResult(task_id=task_id, winner=synapse_a, ...)

    # 2. 并行执行（现有）
    results = await asyncio.gather(...)

    # 3. 硬门槛（新增）
    gates = {s: self.engine.hard_gate(r) for s, r in results.items()}

    # 4. 软评分（新增，替代 stdout 长度比较）
    scores = {}
    for synapse, (passed, _) in gates.items():
        if passed:
            scores[synapse] = await self.engine.score(results[synapse], task_context)

    # 5. 选胜者
    if not scores:
        return TrialResult(task_id=task_id, winner=None, tie=True, ...)
    winner, score = self.engine.pick_winner(scores)
    return TrialResult(task_id=task_id, winner=winner, scores=scores, ...)
```

#### 4.5 文件变更清单

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `services/convergence_engine.py` | **新建** | ~150 行 |
| `services/pre_trial_reasoner.py` | **新建** | ~80 行 |
| `services/trial_race.py` | 修改 | 替换 _pick_winner，集成 engine + reasoner |

---

## 五、P2 — Submind 实体化

### 现状
- 无 Submind 模型，synapse 只是字符串 ID
- 无三态管理（常驻/试验/休眠）
- 无基因本源追踪
- 无跨域协商机制

### 目标
Submind 作为一等公民实体，有生命周期、基因谱系、生物质净值。

### 设计规格

#### 5.1 Submind 模型

```python
# models/submind.py
class SubmindState(str, enum.Enum):
    Active  = "active"   # 常驻：有稳定域，持续执行
    Trial   = "trial"    # 试验：新孵化，待验证
    Dormant = "dormant"  # 休眠：净值为负，暂停

class Submind(Base):
    __tablename__ = "subminds"

    id            = Column(String(64), primary_key=True)  # e.g. "submind-code-alpha"
    display_name  = Column(String(128), nullable=False)
    domain        = Column(String(64), nullable=False, index=True)
    state         = Column(SAEnum(SubmindState), default=SubmindState.Trial)

    # 基因本源
    gene_seed_id  = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    gene_version  = Column(Integer, default=1)
    lineage_parent = Column(String(64), nullable=True)  # 前身 Submind ID（重孵时记录）

    # 生物质
    net_biomass   = Column(Float, default=0.0)
    dormancy_days = Column(Integer, default=0)  # 连续净值为负天数

    # 能力描述（注入 prompt 用）
    capabilities  = Column(JSON, default=list)   # ["python", "web-scraping", ...]
    system_prompt = Column(Text, default="")     # 域专属 system prompt

    # 统计
    total_tasks   = Column(Integer, default=0)
    success_rate  = Column(Float, default=0.0)

    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_active_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    meta          = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_subminds_domain_state", "domain", "state"),
    )
```

#### 5.2 SubmindRegistry 服务

```python
# services/submind_registry.py
class SubmindRegistry:
    """Submind 生命周期管理"""

    def __init__(self, db_factory):
        self.db = db_factory

    async def register(self, id, display_name, domain, capabilities=None, system_prompt=""):
        """注册新 Submind（初始状态 Trial）"""

    async def get(self, submind_id) -> Optional[Submind]:
        """获取单个 Submind"""

    async def list_by_domain(self, domain, state=None) -> list[Submind]:
        """按域查询，可选过滤状态"""

    async def list_active(self) -> list[Submind]:
        """获取所有 Active 状态的 Submind"""

    async def transition(self, submind_id, new_state: SubmindState, reason=""):
        """状态转换 + 审计日志"""
        # Trial → Active: 验证通过
        # Active → Dormant: 净值持续为负
        # Dormant → Active: 手动唤醒或净值恢复

    async def select_for_trial(self, domain, count=2) -> list[Submind]:
        """为 Trial 赛马选择 Submind
        优先选 Active 状态的同域 Submind；
        不足时从相近域选或创建临时 Trial 态 Submind"""

    async def update_biomass(self, submind_id, delta: float):
        """更新净生物质，检查是否触发休眠"""
        # 如果 net_biomass < 0 连续 N 天 → 自动转 Dormant

    async def promote(self, submind_id):
        """Trial → Active（验证通过后调用）"""

    async def reincarnate(self, old_submind_id, new_domain=None) -> Submind:
        """休眠后重孵：创建新 Submind，继承前身 50% 战功
        lineage_parent = old_submind_id
        gene_seed_id = 新 UUID（谱系断裂）
        net_biomass = old.net_biomass * 0.5（遗传起点）"""
```

#### 5.3 与现有代码的集成

**Task 模型扩展**：
```python
# models/task.py — 新增字段
assigned_submind_id = Column(String(64), ForeignKey("subminds.id"), nullable=True)
```

**Dispatcher 集成**：
```python
# workers/dispatcher.py — _dispatch 修改
# 现有: synapse = event.payload["synapse"]  (字符串)
# 新增: 如果 synapse 对应一个 Submind，加载其 system_prompt + capabilities
submind = await registry.get(synapse)
if submind:
    enriched_message = inject_submind_context(message, submind)
    await registry.update_biomass(submind.id, -drain_cost)  # 执行前扣 drain
```

**TrialRace 集成**：
```python
# services/trial_race.py — run 修改
# 现有: 接收 synapse_a, synapse_b 字符串
# 新增: 从 SubmindRegistry 选择
subminds = await registry.select_for_trial(domain, count=2)
synapse_a, synapse_b = subminds[0].id, subminds[1].id
```

#### 5.4 数据库迁移

```python
# migrations/versions/002_add_submind.py
def upgrade():
    op.create_table("subminds", ...)
    op.add_column("tasks", sa.Column("assigned_submind_id", sa.String(64), ...))

def downgrade():
    op.drop_column("tasks", "assigned_submind_id")
    op.drop_table("subminds")
```

#### 5.5 预置 Submind 种子数据

系统启动时自动注册默认 Submind（如果不存在）：

```python
DEFAULT_SUBMINDS = [
    {"id": "submind-code-alpha", "domain": "coding", "display_name": "Code Alpha",
     "capabilities": ["python", "javascript", "refactoring"]},
    {"id": "submind-devops-alpha", "domain": "devops", "display_name": "DevOps Alpha",
     "capabilities": ["docker", "ci-cd", "deployment"]},
    {"id": "submind-research-alpha", "domain": "research", "display_name": "Research Alpha",
     "capabilities": ["web-search", "summarization", "analysis"]},
]
```

#### 5.6 文件变更清单

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `models/submind.py` | **新建** | ~60 行 |
| `services/submind_registry.py` | **新建** | ~180 行 |
| `migrations/versions/002_add_submind.py` | **新建** | ~30 行 |
| `models/__init__.py` | 修改 | 导出 Submind |
| `models/task.py` | 修改 | 新增 assigned_submind_id |
| `workers/dispatcher.py` | 修改 | 集成 Submind 上下文注入 |
| `services/trial_race.py` | 修改 | 从 Registry 选 Submind |
| `main.py` | 修改 | 启动时注册默认 Submind |

---

## 六、P3 — 生物质消耗侧 Drain 机制

### 现状
- `FitnessService.record_execution()` 只记录 Harvest（成功/失败的 biomass_delta）
- 失败统一乘 0.3 惩罚，无分类
- 无 Drain（token 成本、待机成本、协调开销）
- 无净值计算，无休眠触发

### 目标
Net Biomass = Harvest − Drain，净值持续为负 → 收缩 → 休眠。

### 设计规格

#### 6.1 Drain 模型

```python
# models/biomass_ledger.py
class LedgerEntryType(str, enum.Enum):
    Harvest   = "harvest"      # 收割：任务完成/Trial 胜出/进化贡献
    Drain     = "drain"        # 消耗：token/时间/协调成本

class DrainCategory(str, enum.Enum):
    Standby       = "standby"        # 待机成本（常驻 Submind 每日固定扣除）
    Execution     = "execution"      # 执行 token 成本
    Coordination  = "coordination"   # 跨域协调开销

class LedgerEntry(Base):
    __tablename__ = "biomass_ledger"

    id          = Column(String(36), primary_key=True, default=uuid4_str)
    submind_id  = Column(String(64), ForeignKey("subminds.id"), nullable=False, index=True)
    task_id     = Column(String(64), nullable=True)
    entry_type  = Column(SAEnum(LedgerEntryType), nullable=False)
    category    = Column(String(32), nullable=True)   # DrainCategory 或 harvest 来源
    amount      = Column(Float, nullable=False)        # 正数=收割，负数=消耗
    detail      = Column(Text, default="")
    created_at  = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_ledger_submind_created", "submind_id", "created_at"),
    )
```

#### 6.2 BiomassLedger 服务

```python
# services/biomass_ledger.py
class BiomassLedger:
    """生物质账本 —— 收割与消耗的完整记录"""

    def __init__(self, db):
        self._db = db

    async def record_harvest(self, submind_id, task_id, amount, source="task_complete"):
        """记录收割（正值）"""
        entry = LedgerEntry(
            submind_id=submind_id, task_id=task_id,
            entry_type=LedgerEntryType.Harvest,
            category=source, amount=abs(amount),
        )
        self._db.add(entry)
        await self._db.flush()

    async def record_drain(self, submind_id, category: DrainCategory,
                           amount: float, task_id=None, detail=""):
        """记录消耗（存为负值）"""
        entry = LedgerEntry(
            submind_id=submind_id, task_id=task_id,
            entry_type=LedgerEntryType.Drain,
            category=category.value, amount=-abs(amount),
            detail=detail,
        )
        self._db.add(entry)
        await self._db.flush()

    async def get_net_biomass(self, submind_id, days=30) -> float:
        """计算近 N 天净生物质（带时间衰减）"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (await self._db.execute(
            select(LedgerEntry).where(
                LedgerEntry.submind_id == submind_id,
                LedgerEntry.created_at >= cutoff,
            )
        )).scalars().all()
        now = datetime.now(timezone.utc)
        net = 0.0
        for r in rows:
            days_ago = (now - r.created_at).total_seconds() / 86400
            net += r.amount * math.exp(-0.05 * days_ago)
        return round(net, 4)

    async def check_dormancy_trigger(self, submind_id, threshold_days=7) -> bool:
        """检查是否连续 N 天净值为负 → 应触发休眠"""
        for d in range(threshold_days):
            day_start = datetime.now(timezone.utc) - timedelta(days=d+1)
            day_end = datetime.now(timezone.utc) - timedelta(days=d)
            rows = (await self._db.execute(
                select(func.sum(LedgerEntry.amount)).where(
                    LedgerEntry.submind_id == submind_id,
                    LedgerEntry.created_at.between(day_start, day_end),
                )
            )).scalar() or 0.0
            if rows >= 0:
                return False  # 有一天净值非负，不触发
        return True  # 连续 N 天为负

    async def get_ledger(self, submind_id, days=30, limit=100) -> list[LedgerEntry]:
        """查询账本明细"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (await self._db.execute(
            select(LedgerEntry).where(
                LedgerEntry.submind_id == submind_id,
                LedgerEntry.created_at >= cutoff,
            ).order_by(LedgerEntry.created_at.desc()).limit(limit)
        )).scalars().all()
        return list(rows)
```

#### 6.3 Drain 记录集成点

**执行 token 成本**（dispatcher.py）：
```python
# workers/dispatcher.py — _dispatch 方法中，执行完成后
token_cost = estimate_token_cost(result)  # 从 LLM 响应中提取 usage
await ledger.record_drain(
    submind_id=synapse_id,
    category=DrainCategory.Execution,
    amount=token_cost * TOKEN_COST_RATE,  # 归一化为生物质单位
    task_id=task_id,
    detail=f"tokens={token_cost}",
)
```

**待机成本**（定时任务，main.py 启动时注册）：
```python
# 每日凌晨扣除常驻 Submind 待机成本
async def daily_standby_drain():
    async with SessionLocal() as db:
        registry = SubmindRegistry(db)
        ledger = BiomassLedger(db)
        for submind in await registry.list_active():
            await ledger.record_drain(
                submind_id=submind.id,
                category=DrainCategory.Standby,
                amount=STANDBY_DAILY_COST,  # 配置项，默认 0.5
            )
            # 检查是否触发休眠
            if await ledger.check_dormancy_trigger(submind.id):
                await registry.transition(submind.id, SubmindState.Dormant,
                                          reason="连续7天净值为负")
        await db.commit()
```

#### 6.4 失败分类体系

```python
# services/failure_classifier.py
class FailureType(str, enum.Enum):
    Environment   = "environment"     # 网络/权限/超时 → 不惩罚
    Understanding = "understanding"   # 理解错误 → 轻微
    Strategy      = "strategy"        # 策略失败 → 中等
    Quality       = "quality"         # 质量不达标 → 严重

FAILURE_PENALTY: dict[FailureType, float] = {
    FailureType.Environment:   0.0,
    FailureType.Understanding: 0.3,
    FailureType.Strategy:      0.6,
    FailureType.Quality:       1.0,
}

class FailureClassifier:
    """基于 stderr/returncode/output 启发式分类失败类型"""

    ENVIRONMENT_PATTERNS = [
        r"timeout", r"connection refused", r"permission denied",
        r"ECONNRESET", r"ETIMEDOUT", r"rate limit", r"503", r"502",
    ]
    UNDERSTANDING_PATTERNS = [
        r"not found", r"no such", r"invalid argument", r"type error",
        r"key error", r"attribute error",
    ]

    def classify(self, returncode: int, stdout: str, stderr: str) -> FailureType:
        text = (stderr or "") + (stdout or "")
        text_lower = text.lower()

        # 环境失败优先判断
        for pat in self.ENVIRONMENT_PATTERNS:
            if re.search(pat, text_lower):
                return FailureType.Environment

        # 理解失败
        for pat in self.UNDERSTANDING_PATTERNS:
            if re.search(pat, text_lower):
                return FailureType.Understanding

        # returncode 非零但无明显模式 → 策略失败
        if returncode != 0:
            return FailureType.Strategy

        # 有输出但质量差 → 质量失败
        return FailureType.Quality
```

#### 6.5 修改 FitnessService 集成

```python
# services/fitness_service.py — record_execution 修改
async def record_execution(self, synapse_id, task_id, domain, success, score=1.0,
                           failure_type: Optional[FailureType] = None):
    if not success and failure_type:
        penalty = FAILURE_PENALTY[failure_type]
        score = score * (1.0 - penalty)  # 环境失败: score不变; 质量失败: score=0
    # ... 现有逻辑
```

#### 6.6 文件变更清单

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `models/biomass_ledger.py` | **新建** | ~40 行 |
| `services/biomass_ledger.py` | **新建** | ~120 行 |
| `services/failure_classifier.py` | **新建** | ~60 行 |
| `migrations/versions/003_add_biomass_ledger.py` | **新建** | ~25 行 |
| `services/fitness_service.py` | 修改 | 集成 failure_type 分类惩罚 |
| `workers/dispatcher.py` | 修改 | 执行后记录 Drain |
| `models/fitness.py` | 修改 | KillMark 新增 failure_type 字段 |
| `main.py` | 修改 | 注册每日待机扣除定时任务 |

---

## 七、P4 — 进化大师增强

### 现状
- `evolve_domain()`: 统计成功 Lesson ≥ 5 → 取 top-10 → 拼 Markdown → 创建 Playbook
- 无 Reflect/Write 两阶段
- 无 TrialClosed 事件订阅
- 无失败根因诊断
- 无 Playbook 语义聚类审计

### 目标
两阶段复盘 + 事件驱动 + 根因诊断 + 语义聚类。

### 设计规格

#### 7.1 两阶段复盘：Reflect → Write

```python
# services/reflect_engine.py
@dataclass
class ReflectResult:
    """Reflect 阶段输出 —— 诊断，不做更新"""
    domain: str
    root_cause: str          # "tool" / "sequence" / "understanding" / "environment"
    diagnosis: str           # 详细诊断文本
    confidence: float        # 0-1
    affected_lessons: list[str]  # 相关 Lesson ID
    recommended_action: str  # "update_playbook" / "create_skill" / "no_action"

@dataclass
class WriteResult:
    """Write 阶段输出 —— 实际更新"""
    lessons_updated: list[str]
    playbook_updated: Optional[str]
    playbook_version: int
    skill_candidate: Optional[str]  # 未来 Skill 自合成候选描述

class ReflectEngine:
    """Reflect 阶段 —— 诊断失败根因，不做任何写入"""

    def __init__(self, llm_client: AnthropicClient):
        self.llm = llm_client

    async def reflect(self, domain: str, lessons: list[Lesson],
                      trial_result: Optional[dict] = None) -> ReflectResult:
        """分析经验，诊断根因"""
        prompt = self._build_reflect_prompt(domain, lessons, trial_result)
        raw = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            system="你是进化大师，专职诊断失败根因。只返回 JSON。",
            max_tokens=500, temperature=0.1,
        )
        data = json.loads(raw)  # 需容错
        return ReflectResult(
            domain=domain,
            root_cause=data.get("root_cause", "unknown"),
            diagnosis=data.get("diagnosis", ""),
            confidence=data.get("confidence", 0.5),
            affected_lessons=[l.id for l in lessons[:5]],
            recommended_action=data.get("recommended_action", "no_action"),
        )

    def _build_reflect_prompt(self, domain, lessons, trial_result):
        lesson_text = "\n".join([
            f"- [{l.outcome}] {l.content[:100]}" for l in lessons[:10]
        ])
        trial_text = json.dumps(trial_result, ensure_ascii=False)[:300] if trial_result else "无"
        return f"""域: {domain}
近期经验:
{lesson_text}

Trial 结果: {trial_text}

请诊断:
1. 失败根因是什么？(tool/sequence/understanding/environment)
2. 详细诊断
3. 建议操作 (update_playbook/create_skill/no_action)

返回 JSON: {{"root_cause": "...", "diagnosis": "...", "confidence": 0.x, "recommended_action": "..."}}"""
```

#### 7.2 增强 EvolutionMasterService

```python
# services/evolution_master.py — 增强版
class EvolutionMasterService:
    LESSON_THRESHOLD = 5

    def __init__(self, db, llm_client=None):
        self._db = db
        self._bank = LessonsBank(db)
        self._pb_svc = PlaybookService(db)
        # ── 新增 ──
        self._reflect = ReflectEngine(llm_client) if llm_client else None
        self._bus = get_event_bus()

    async def start(self):
        """启动时订阅 TrialClosed 事件"""
        q = self._bus.subscribe("trial.closed")
        asyncio.create_task(self._listen_trial_closed(q))

    async def _listen_trial_closed(self, queue):
        """TrialClosed 事件驱动复盘"""
        while True:
            event = await queue.get()
            task_id = event.payload.get("task_id")
            domain = event.payload.get("domain", "general")
            trial_result = event.payload.get("trial_result")
            logger.info(f"[EvolutionMaster] TrialClosed → 复盘 {task_id}")
            await self.two_stage_review(domain, trial_result)

    async def two_stage_review(self, domain, trial_result=None) -> Optional[WriteResult]:
        """两阶段复盘：Reflect → Write（不可合并）"""
        lessons = await self._get_success_lessons(domain)
        if not lessons:
            return None

        # Stage 1: Reflect（诊断）
        if self._reflect:
            reflect_result = await self._reflect.reflect(domain, lessons, trial_result)
            logger.info(
                f"[EvolutionMaster] Reflect 完成: root_cause={reflect_result.root_cause}, "
                f"action={reflect_result.recommended_action}"
            )
            if reflect_result.recommended_action == "no_action":
                return None
        else:
            reflect_result = None

        # Stage 2: Write（更新）
        return await self._write_stage(domain, lessons, reflect_result)

    async def _write_stage(self, domain, lessons, reflect_result) -> WriteResult:
        """Write 阶段 —— 基于诊断结果更新 Playbook"""
        # 如果有 Reflect 结果，用诊断信息增强合成
        if reflect_result:
            content = self._synthesize_with_diagnosis(domain, lessons, reflect_result)
        else:
            content = self._synthesize(domain, lessons)

        slug = f"evolved-{domain}"
        existing = await self._pb_svc._get_active(slug)
        if existing is None:
            pb = await self._pb_svc.create(slug=slug, domain=domain,
                title=f"{domain} 最佳实践（Evolution Master 生成）", content=content)
        else:
            pb = await self._pb_svc.create_new_version(slug=slug, content=content,
                notes=f"两阶段复盘更新，根因: {reflect_result.root_cause if reflect_result else 'N/A'}")

        for lesson in lessons[:self.LESSON_THRESHOLD]:
            await self._bank.promote_to_playbook(lesson.id, pb.id)

        return WriteResult(
            lessons_updated=[l.id for l in lessons[:self.LESSON_THRESHOLD]],
            playbook_updated=pb.id,
            playbook_version=pb.version,
            skill_candidate=reflect_result.recommended_action if reflect_result
                            and reflect_result.recommended_action == "create_skill" else None,
        )

    @staticmethod
    def _synthesize_with_diagnosis(domain, lessons, reflect_result) -> str:
        """增强版合成：注入诊断信息"""
        base = EvolutionMasterService._synthesize(domain, lessons)
        diagnosis_section = f"""

## 进化诊断

> 根因分析: {reflect_result.root_cause}
> 诊断: {reflect_result.diagnosis}
> 置信度: {reflect_result.confidence:.0%}
"""
        return base + diagnosis_section
```

#### 7.3 TrialClosed 事件发布点

```python
# services/trial_race.py — run() 方法末尾新增
await self._bus.publish(
    topic="trial.closed",
    event_type="trial.closed",
    producer="trial-race",
    trace_id=trace_id,
    payload={
        "task_id": task_id,
        "domain": domain,
        "winner": winner,
        "trial_result": {
            "synapse_a": synapse_a, "synapse_b": synapse_b,
            "winner": winner, "scores": {k: v.__dict__ for k, v in scores.items()},
        },
    },
)
```

#### 7.4 Playbook 语义聚类审计（Tier 3+ 预留）

```python
# services/playbook_auditor.py（预留接口，Tier 3 实现）
@dataclass
class AuditReport:
    redundant_pairs: list[tuple[str, str]]   # 高度相似的 Playbook 对
    orphan_entries: list[str]                 # 语义孤岛
    fuzzy_boundaries: list[tuple[str, str]]   # 域边界模糊的 Playbook 对
    semantic_entropy: float                   # 0-1, 越低越结构化

class PlaybookAuditor:
    """Playbook 库健康审计 —— Tier 3+ 实现"""

    async def audit(self, domain: Optional[str] = None) -> AuditReport:
        """语义聚类审计（需要 embedding 支持）"""
        raise NotImplementedError("Tier 3+ feature")
```

#### 7.5 文件变更清单

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `services/reflect_engine.py` | **新建** | ~100 行 |
| `services/evolution_master.py` | 重构 | 增加两阶段复盘 + 事件订阅 |
| `services/trial_race.py` | 修改 | 末尾发布 trial.closed 事件 |
| `services/event_bus.py` | 修改 | 新增 TOPIC_TRIAL_CLOSED 常量 |
| `services/playbook_auditor.py` | **新建** | ~30 行（预留接口） |

---

## 八、实施顺序与依赖关系

```
P0 执行模式自动路由 ←── 最高优先级，解锁"双模架构"核心卖点
  │
  ├─→ P1 收敛引擎 ←── P0 的 Trial 路径需要多维评分
  │
  ├─→ P2 Submind 实体化 ←── P0 的 Trial/Chain/Swarm 需要 Submind 选择
  │     │
  │     └─→ P3 Drain 机制 ←── 依赖 Submind 模型存在
  │
  └─→ P4 进化大师增强 ←── 依赖 P1 的 TrialClosed 事件
```

建议分三轮实施：

| 轮次 | 内容 | 预估新增代码 |
|------|------|-------------|
| 第一轮 | P0（自动路由）+ P1（收敛引擎） | ~500 行 |
| 第二轮 | P2（Submind）+ P3（Drain） | ~500 行 |
| 第三轮 | P4（进化大师增强） | ~250 行 |

---

## 九、P5 — Demo 系统重建

### 背景
原 demo.py 被回退，因为 Sonnet 将 API key 硬编码在脚本中并推送到公共仓库。

### 安全硬规则（所有代码必须遵守）

```
1. API key / secret 只能从环境变量或 .env 文件读取，绝不硬编码
2. .env 必须在 .gitignore 中（已有）
3. demo 脚本启动时检查必要环境变量，缺失则报错退出并给出提示
4. CI 中增加 secret 扫描（建议 truffleHog 或 gitleaks）
```

### 设计规格

```python
# demo.py — 端到端演示脚本
"""
Tyranid Hive Demo — 演示四种执行模式

用法:
  export ANTHROPIC_API_KEY=sk-...
  python demo.py [scenario]

场景:
  solo    — Solo Mode 日常问答
  trial   — Trial Mode 爬虫赛马
  chain   — Chain Mode 系统重构
  swarm   — Swarm Mode 并行采集
  all     — 依次运行全部场景
"""
import os, sys, asyncio, httpx

API_BASE = os.getenv("HIVE_API_URL", "http://localhost:8000")

def _check_env():
    """启动前检查必要环境变量"""
    required = ["ANTHROPIC_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"错误: 缺少环境变量: {', '.join(missing)}")
        print("请设置后重试: export ANTHROPIC_API_KEY=sk-...")
        sys.exit(1)

async def demo_solo():
    """Solo Mode: 创建任务 → 主脑自动分析 → 直接执行"""
    async with httpx.AsyncClient(base_url=API_BASE) as c:
        r = await c.post("/api/tasks", json={
            "title": "用 Python 实现快速排序",
            "description": "写一个 quicksort 函数，支持自定义比较器",
        })
        task = r.json()
        print(f"[Solo] 任务创建: {task['id']}")
        # 轮询等待完成...
        await _poll_until_done(c, task["id"])

async def demo_trial():
    """Trial Mode: 创建任务 → 主脑判断需要赛马 → 双路竞争"""
    async with httpx.AsyncClient(base_url=API_BASE) as c:
        r = await c.post("/api/tasks", json={
            "title": "爬取豆瓣 Top250 电影列表",
            "description": "需要处理反爬，可用 requests 或 playwright",
        })
        task = r.json()
        print(f"[Trial] 任务创建: {task['id']}，等待主脑判断执行模式...")
        await _poll_until_done(c, task["id"])

async def demo_chain():
    """Chain Mode: 线性依赖的多阶段重构"""
    async with httpx.AsyncClient(base_url=API_BASE) as c:
        r = await c.post("/api/tasks", json={
            "title": "实现用户认证系统",
            "description": "P1:数据模型 → P2:注册接口 → P3:登录接口 → P4:JWT中间件",
        })
        task = r.json()
        print(f"[Chain] 任务创建: {task['id']}，串行链执行...")
        await _poll_until_done(c, task["id"])

async def demo_swarm():
    """Swarm Mode: 完全独立的并行采集"""
    async with httpx.AsyncClient(base_url=API_BASE) as c:
        r = await c.post("/api/tasks", json={
            "title": "并行采集三个数据源的今日新闻",
            "description": "RSS源/API接口/网页爬取 三路独立并行",
        })
        task = r.json()
        print(f"[Swarm] 任务创建: {task['id']}，并发执行...")
        await _poll_until_done(c, task["id"])

async def _poll_until_done(client, task_id, timeout=120):
    """轮询任务状态直到完成"""
    import time
    start = time.time()
    while time.time() - start < timeout:
        r = await client.get(f"/api/tasks/{task_id}")
        state = r.json()["state"]
        print(f"  状态: {state}")
        if state in ("Complete", "Cancelled"):
            break
        await asyncio.sleep(3)

SCENARIOS = {"solo": demo_solo, "trial": demo_trial,
             "chain": demo_chain, "swarm": demo_swarm}

async def main():
    _check_env()
    scenario = sys.argv[1] if len(sys.argv) > 1 else "all"
    if scenario == "all":
        for name, fn in SCENARIOS.items():
            print(f"\n{'='*40} {name.upper()} {'='*40}")
            await fn()
    elif scenario in SCENARIOS:
        await SCENARIOS[scenario]()
    else:
        print(f"未知场景: {scenario}，可选: {', '.join(SCENARIOS)} 或 all")

if __name__ == "__main__":
    asyncio.run(main())
```

### 关键设计原则
- 零硬编码：所有 secret 从 `os.getenv()` 读取
- 启动前校验：缺少环境变量立即报错，不会带着空 key 跑
- 场景独立：每个 demo 函数可单独运行
- 依赖 P0：demo 的 trial/chain/swarm 场景依赖自动路由实现后才能真正工作
- 当前可先实现 solo 场景作为 smoke test

### 建议增加的安全防护

在 `.github/workflows/` 中增加 secret 扫描：

```yaml
# .github/workflows/secret-scan.yml
name: Secret Scan
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
