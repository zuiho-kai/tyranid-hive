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

默认战功类型（当 synapse 未配置 kill_mark_weights 时）：
  execution_success: 1.0 (成功), execution_failure: 1.0 (失败)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.fitness import KillMark


# 时间衰减系数：0.05 → 半衰期约 14 天
DECAY = 0.05


@dataclass
class SynapseScore:
    synapse_id:     str
    fitness:        float    # 衰减后的适存度
    raw_biomass:    float    # 未衰减的原始战功总和
    mark_count:     int      # 战功记录数
    success_count:  int      # 成功次数
    fail_count:     int      # 失败次数

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total else 0.0


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
    ) -> list[KillMark]:
        """记录一次执行的战功（基于 kill_mark_weights 配置）"""
        weights = _get_weights(synapse_id)
        marks: list[KillMark] = []

        if success:
            # 成功：所有成功相关类型 + 兜底 execution_success
            relevant = {k: v for k, v in weights.items()
                        if "fail" not in k and "penalty" not in k}
            if not relevant:
                relevant = {"execution_success": 1.0}
        else:
            # 失败：只记录 failure/penalty 类型，或兜底 execution_failure
            relevant = {k: v for k, v in weights.items()
                        if "fail" in k or "penalty" in k}
            if not relevant:
                relevant = {"execution_failure": 1.0}
            score = score * 0.3  # 失败的战功大幅削减

        for mark_type, weight in relevant.items():
            delta = weight * score
            km = KillMark(
                synapse_id=synapse_id,
                task_id=task_id,
                domain=domain,
                mark_type=mark_type,
                weight=weight,
                score=score,
                biomass_delta=delta,
            )
            self._db.add(km)
            marks.append(km)

        await self._db.flush()
        logger.debug(
            f"[Fitness] 战功入库 synapse={synapse_id} "
            f"success={success} marks={len(marks)}"
        )
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
