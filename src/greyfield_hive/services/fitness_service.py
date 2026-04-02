"""FitnessService —— 适存度计算与战功记录

适存度公式：
  fitness(synapse) = Σ biomass_delta_i × exp(−DECAY × days_i)

  其中 DECAY=0.05，days_i = 战功记录距今的天数。
  新的战功权重高；60 天前的战功只剩 ~5%。

战功触发时机：
  - Trial（赛马）：胜者获胜方权重；败者获部分分
  - Chain Mode：每阶段执行后记录
  - Swarm Mode：每个 unit 执行后记录
  - Dispatch（单次）：执行后记录

Drain 触发时机（消耗侧）：
  - token_cost：每次 LLM 调用按输出长度扣分
  - coordination_cost：stderr / 协调开销扣分
  - env_failure：环境失败（网络/权限/超时）不惩罚，只记录

失败分类（先分类再惩罚）：
  - env_failure：环境失败 → 不惩罚
  - understanding_failure：理解失败 → 轻微惩罚 ×0.1
  - strategy_failure：策略失败 → 中等惩罚 ×0.3
  - quality_failure：质量失败 → 严重惩罚 ×0.6
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.fitness import KillMark


# 时间衰减系数：0.05 → 半衰期约 14 天
DECAY = 0.05

# 失败分类关键词
_ENV_KEYWORDS    = {"timeout", "connection", "permission", "network", "refused", "unreachable"}
_QUALITY_KEYWORDS = {"wrong", "incorrect", "invalid", "corrupt", "broken"}
_UNDERSTANDING_KEYWORDS = {"unclear", "ambiguous", "misunderstood", "confused"}

# 失败惩罚系数
_FAILURE_PENALTY = {
    "env_failure":           0.0,   # 环境失败不惩罚
    "understanding_failure": 0.1,
    "strategy_failure":      0.3,
    "quality_failure":       0.6,
}


@dataclass
class SynapseScore:
    synapse_id:     str
    fitness:        float
    raw_biomass:    float
    mark_count:     int
    success_count:  int
    fail_count:     int

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total else 0.0


def classify_failure(stdout: str, stderr: str) -> str:
    """根据输出内容分类失败原因"""
    combined = (stdout + " " + stderr).lower()
    if any(kw in combined for kw in _ENV_KEYWORDS):
        return "env_failure"
    if any(kw in combined for kw in _QUALITY_KEYWORDS):
        return "quality_failure"
    if any(kw in combined for kw in _UNDERSTANDING_KEYWORDS):
        return "understanding_failure"
    return "strategy_failure"


# ── 默认 kill_mark_weights（当 config 未定义时使用）──────────

_DEFAULT_WEIGHTS: dict[str, float] = {
    "execution_success": 1.0,
    "execution_failure": 1.0,
}


def _get_weights(synapse_id: str) -> dict[str, float]:
    """从 config/synapses/{synapse_id}.yaml 读取 kill_mark_weights"""
    try:
        from greyfield_hive.config_loader import load_synapse_config
        cfg = load_synapse_config(synapse_id)
        if cfg and "kill_mark_weights" in cfg:
            return cfg["kill_mark_weights"]
    except Exception:
        pass
    return _DEFAULT_WEIGHTS


class FitnessService:
    """适存度服务 —— 战功记录 + 排行榜计算"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── 记录战功 ──────────────────────────────────────────

    async def record_execution(
        self,
        synapse_id: str,
        task_id:    Optional[str],
        domain:     str,
        success:    bool,
        score:      float = 1.0,
        stdout:     str = "",
        stderr:     str = "",
    ) -> list[KillMark]:
        """记录一次执行的战功（失败先分类再惩罚，环境失败不背锅）"""
        weights = _get_weights(synapse_id)
        marks: list[KillMark] = []

        if success:
            relevant = {k: v for k, v in weights.items()
                        if "fail" not in k and "penalty" not in k}
            if not relevant:
                relevant = {"execution_success": 1.0}
        else:
            failure_type = classify_failure(stdout, stderr)
            penalty = _FAILURE_PENALTY[failure_type]
            if penalty == 0.0:
                # 环境失败：只记录，不扣分
                logger.info(f"[Fitness] 环境失败，不惩罚 synapse={synapse_id}")
                km = KillMark(
                    synapse_id=synapse_id, task_id=task_id, domain=domain,
                    mark_type=failure_type, weight=0.0, score=0.0, biomass_delta=0.0,
                )
                self._db.add(km)
                await self._db.flush()
                return [km]
            relevant = {k: v for k, v in weights.items()
                        if "fail" in k or "penalty" in k}
            if not relevant:
                relevant = {failure_type: 1.0}
            score = score * penalty

        for mark_type, weight in relevant.items():
            delta = weight * score
            km = KillMark(
                synapse_id=synapse_id, task_id=task_id, domain=domain,
                mark_type=mark_type, weight=weight, score=score, biomass_delta=delta,
            )
            self._db.add(km)
            marks.append(km)

        await self._db.flush()
        logger.debug(f"[Fitness] 战功入库 synapse={synapse_id} success={success} marks={len(marks)}")
        return marks

    async def record_step_cost(
        self,
        synapse_id:      str,
        task_id:         Optional[str],
        domain:          str,
        episode_id:      Optional[str] = None,
        episode_step_id: Optional[str] = None,
        token_count:     int = 0,
        wall_time:       float = 0.0,
    ) -> list[KillMark]:
        """按 step 粒度记录执行成本（Phase 1 新增）。

        token_cost   → drain_category=execution
        wall_time 过长（>60s）→ 额外 coordination 惩罚
        """
        marks: list[KillMark] = []

        if token_count > 0:
            token_drain = min(token_count / 1000 * 0.1, 2.0)
            km = KillMark(
                synapse_id=synapse_id, task_id=task_id, domain=domain,
                mark_type="step_token_cost", weight=0.1, score=token_count / 1000,
                biomass_delta=-token_drain,
                episode_id=episode_id, episode_step_id=episode_step_id,
                drain_category="execution",
            )
            self._db.add(km)
            marks.append(km)

        if wall_time > 60:
            coord_drain = min((wall_time - 60) / 60 * 0.05, 0.5)
            km = KillMark(
                synapse_id=synapse_id, task_id=task_id, domain=domain,
                mark_type="step_overtime", weight=0.05, score=wall_time / 60,
                biomass_delta=-coord_drain,
                episode_id=episode_id, episode_step_id=episode_step_id,
                drain_category="coordination",
            )
            self._db.add(km)
            marks.append(km)

        if marks:
            await self._db.flush()
            logger.debug(
                f"[Fitness] step_cost episode={episode_id} synapse={synapse_id} "
                f"tokens={token_count} wall={wall_time:.1f}s marks={len(marks)}"
            )
        return marks

    async def record_drain(
        self,
        synapse_id:   str,
        task_id:      Optional[str],
        domain:       str,
        token_count:  int = 0,
        stderr_len:   int = 0,
    ) -> list[KillMark]:
        """记录消耗侧 Drain（token 成本 + 协调开销）"""
        marks: list[KillMark] = []

        # token 成本：每 1000 token 扣 0.1 生物质
        if token_count > 0:
            token_drain = min(token_count / 1000 * 0.1, 2.0)
            km = KillMark(
                synapse_id=synapse_id, task_id=task_id, domain=domain,
                mark_type="token_cost", weight=0.1, score=token_count / 1000,
                biomass_delta=-token_drain,
            )
            self._db.add(km)
            marks.append(km)

        # 协调开销：stderr 每 100 字节扣 0.05
        if stderr_len > 0:
            coord_drain = min(stderr_len / 100 * 0.05, 1.0)
            km = KillMark(
                synapse_id=synapse_id, task_id=task_id, domain=domain,
                mark_type="coordination_cost", weight=0.05, score=stderr_len / 100,
                biomass_delta=-coord_drain,
            )
            self._db.add(km)
            marks.append(km)

        if marks:
            await self._db.flush()
            logger.debug(f"[Fitness] Drain 入库 synapse={synapse_id} items={len(marks)}")
        return marks

    # ── 计算适存度 ────────────────────────────────────────

    async def compute_fitness(self, synapse_id: str) -> SynapseScore:
        """计算单个 synapse 的当前适存度"""
        rows = (await self._db.execute(
            select(KillMark).where(KillMark.synapse_id == synapse_id)
        )).scalars().all()

        return _aggregate(synapse_id, rows)

    async def get_leaderboard(self, limit: int = 20) -> list[SynapseScore]:
        """返回所有 synapse 的适存度排行榜（降序）"""
        # 获取所有有战功的 synapse
        synapse_rows = (await self._db.execute(
            select(KillMark.synapse_id).distinct()
        )).scalars().all()

        scores: list[SynapseScore] = []
        for sid in synapse_rows:
            rows = (await self._db.execute(
                select(KillMark).where(KillMark.synapse_id == sid)
            )).scalars().all()
            scores.append(_aggregate(sid, rows))

        scores.sort(key=lambda s: s.fitness, reverse=True)
        return scores[:limit]

    async def get_synapse_history(
        self,
        synapse_id: str,
        limit:      int = 50,
    ) -> list[KillMark]:
        """返回某 synapse 最近 N 条战功记录"""
        rows = (await self._db.execute(
            select(KillMark)
            .where(KillMark.synapse_id == synapse_id)
            .order_by(KillMark.created_at.desc())
            .limit(limit)
        )).scalars().all()
        return list(rows)

    async def recommend_synapse(
        self,
        domain:     str = "general",
        candidates: Optional[list[str]] = None,
    ) -> Optional[SynapseScore]:
        """
        根据适存度推荐最适合指定领域的 synapse。

        逻辑：
          1. 若提供 candidates，仅从候选集中选取
          2. 按该 domain 的战功记录计算适存度
          3. 返回适存度最高的 SynapseScore；若无记录返回 None
        """
        # 查出有战功记录的 synapse（可按 candidates 过滤）
        stmt = select(KillMark.synapse_id).where(
            KillMark.domain == domain
        ).distinct()
        synapse_ids = (await self._db.execute(stmt)).scalars().all()

        if candidates:
            synapse_ids = [s for s in synapse_ids if s in candidates]

        if not synapse_ids:
            return None

        # 计算每个 synapse 的适存度（只取该 domain 的记录）
        scores: list[SynapseScore] = []
        for sid in synapse_ids:
            rows = (await self._db.execute(
                select(KillMark).where(
                    KillMark.synapse_id == sid,
                    KillMark.domain     == domain,
                )
            )).scalars().all()
            if rows:
                scores.append(_aggregate(sid, rows))

        if not scores:
            return None

        scores.sort(key=lambda s: s.fitness, reverse=True)
        return scores[0]


# ── 内部工具 ──────────────────────────────────────────────

def _aggregate(synapse_id: str, marks: list[KillMark]) -> SynapseScore:
    """从战功列表计算适存度分数"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    fitness = 0.0
    raw = 0.0
    success_count = 0
    fail_count = 0

    for m in marks:
        created = m.created_at
        if created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        days = max(0.0, (now - created).total_seconds() / 86400)
        decay_factor = math.exp(-DECAY * days)
        fitness += m.biomass_delta * decay_factor
        raw += m.biomass_delta
        if "fail" in m.mark_type or "penalty" in m.mark_type:
            fail_count += 1
        else:
            success_count += 1

    return SynapseScore(
        synapse_id=synapse_id,
        fitness=round(fitness, 4),
        raw_biomass=round(raw, 4),
        mark_count=len(marks),
        success_count=success_count,
        fail_count=fail_count,
    )
