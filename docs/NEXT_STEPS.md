# Tyranid Hive — 下一步行动清单

> 更新于 2026-04-02。Phase 1/2/3 已合并主干（PR #11/13/12）。
> 本文档记录已知缺口、优先级和建议行动。

---

## 当前系统状态

```
Phase 1（虫巢底座）✅ 已合并
  EpisodeStore + TaskFingerprintService + BiomassLedger step 粒度
  → 系统开始留痕

Phase 2（信息素与选择）✅ 已合并
  PolicyRegistry + Shadow + CreditAssignment + 历史权重路由
  → 系统开始用数据做决策

Phase 3（格式塔合成）✅ 已合并
  SkillRegistry + OrganCrystallizer + WorldModel + SemanticAuditor
  → 系统开始长器官
```

---

## 必须补（系统无法自运转）

### N-1 进化循环无调度器 🔴

**问题**：`evolution_master.scan_and_evolve()`、`auto_decay_stale()`、`retire_degrading()` 全部写好但没人定时调用。策略蒸馏和器官结晶永远不会自动触发。

**修复**：在 `main.py` 的 lifespan 里注册定时任务：

```python
async def _evolution_loop():
    """每完成 10 个任务跑一次进化"""
    while True:
        await asyncio.sleep(600)  # 每 10 分钟检查
        async with SessionLocal() as db:
            master = EvolutionMasterService(db)
            await master.scan_and_evolve()
            # 策略衰减
            from greyfield_hive.services.policy_hit_tracker import PolicyHitTracker
            await PolicyHitTracker(db).decay_stale()
            await PolicyHitTracker(db).retire_decaying()
            # 器官退役
            from greyfield_hive.services.skill_registry import SkillRegistry
            await SkillRegistry(db).retire_degrading()
            await db.commit()
```

**预估**：30 分钟

---

### N-2 OrganCrystallizer 全域查询 bug 🔴

**问题**：`scan_and_crystallize` 调用 `self._ep_store.query_by_domain("", days=days)`，传空字符串查 domain=""，不是查全部 episode。全域扫描永远查不到数据。

**修复**：`EpisodeStore` 增加 `query_all(days)` 方法，`OrganCrystallizer` 改用它：

```python
# episode_store.py 增加
async def query_all(self, days: int = 60, limit: int = 500) -> list[Episode]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await self._db.execute(
        select(Episode)
        .where(Episode.created_at >= cutoff, Episode.finished_at.isnot(None))
        .order_by(Episode.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

# organ_crystallizer.py 改用
all_episodes = await self._ep_store.query_all(days=days)
```

**预估**：15 分钟

---

### N-3 WorldModel 没接入执行流水线 🟡

**问题**：`WorldModelService` 已实现，但 `dispatcher._dispatch()` 和各 runner 里没有读写。Agent 还是读完整上下文，不是读世界模型摘要。

**修复**：
- `dispatcher._build_enriched_message()` 末尾追加世界模型摘要
- `overmind` 分析完成后写入 `confirmed_facts` 和 `goal_tree`

**预估**：1 小时

---

## 应该补（否则进化效果弱）

### N-4 Policy 命中逻辑太粗 🟡

**问题**：`PolicyHitTracker.track_hits_for_episode()` 只检查 `prefer_mode == chosen_mode`，不看 policy 的 `trigger_conditions`。大部分 seed policy 有复杂触发条件（多路径/失败率/线性依赖），都没被真正评估，导致命中率统计不准。

**修复**：实现 `trigger_conditions` 的评估器，根据 `TaskFingerprint` 判断触发条件是否满足。

**预估**：2 小时

---

### N-5 Submind 选择未看 Credit 净值 🟡

**问题**：`CreditAssignment` 算了每步贡献分数并写入 `fitness_service`，但路由时没有"净值高的 Submind 优先"逻辑。生物质净值影响不了实际选人。

**修复**：`mode_router._route_trial()` 里从 `SkillRegistry` 或 `FitnessService` 按域选净值最高的两个 synapse 参赛，而不是用固定的 `["code-expert", "research-analyst"]`。

**预估**：1 小时

---

### N-6 旧门禁仍在双轨运行 🟡

**问题**：CLAUDE.md 里 `[HEURISTIC]` 标记的门禁（入口门禁、方案确认、修复门禁、完成门禁）还在生效。Phase 2 已经有了自动历史查询替代，但旧模板没有移除。

**行动**：等系统积累 30+ 天真实 Episode 数据，shadow 策略激活足够多后，逐步移除 `[HEURISTIC]` 条目。**当前不要删，先观察。**

---

## 可以后做（优化项）

### N-7 赛前论证未实现

GAP 里 P0 子项：主脑 ~500 token 快速推理决定是否开赛。现在每次 Trial 都直接开跑，浪费资源。

### N-8 真正的 Contextual Bandit

mode_router 目前是阈值比较（差 20%+5 样本），数据积累够了可以升级为 bandit 算法。

### N-9 UI 未显示进化状态

Dashboard 看不到 Policy / Skill / Episode / WorldModel。用户无法可视化"系统在进化"。

### N-10 跨 Hive 协作

README Phase 3 愿景：多 Hive 实例间基因同步。当前是单 Hive。

---

## 建议下一步执行顺序

```
第 1 步（立刻）：修 N-2 OrganCrystallizer bug（15 分钟）
第 2 步（立刻）：加定时调度 N-1（30 分钟）
第 3 步（近期）：WorldModel 接入执行流 N-3（1 小时）
第 4 步（近期）：Policy 命中逻辑升级 N-4（2 小时）
第 5 步（近期）：Submind 按净值选人 N-5（1 小时）
---------
以上完成后：跑一轮真实任务，观察：
  - episodes 表是否有记录
  - 进化大师是否蒸馏出 candidate policy
  - 器官结晶是否触发
  - 历史覆盖是否在路由中生效
```

---

## 参考文档

| 文档 | 用途 |
|------|------|
| `docs/EVOLUTION_BLUEPRINT.md` | 整体架构蓝图 |
| `docs/specs/phase1-hive-substrate.md` | Phase 1 详细规格 |
| `docs/specs/phase2-stigmergy-selection.md` | Phase 2 详细规格 |
| `docs/GAP_ANALYSIS.md` | 完成度矩阵（更新后） |
