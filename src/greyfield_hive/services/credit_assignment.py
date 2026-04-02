"""CreditAssignment —— 启发式贡献分账（Phase 2）

四条规则：
  1. 直接执行者（execute/chain_stage/trial_arm/swarm_unit）拿主 credit
  2. 被后续步骤复用的产出物 → 按复用次数加 bonus
  3. token 低消耗（< 200）→ 小奖励
  4. 执行超 60s → coordination penalty

分账结果写入 fitness_service 的 record_step_cost()，影响 Submind 生物质净值。
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.episode import Episode, EpisodeStep
from greyfield_hive.services.fitness_service import FitnessService

# 直接执行者的动作类型
_DIRECT_EXEC_TYPES = {"execute", "chain_stage", "trial_arm", "swarm_unit"}

# bonus / penalty 参数
_REUSE_BONUS_PER_COUNT  = 0.10
_LOW_TOKEN_BONUS        = 0.05
_LOW_TOKEN_THRESHOLD    = 200
_OVERTIME_PENALTY       = 0.05
_OVERTIME_THRESHOLD_SEC = 60.0


class HeuristicCreditAssignment:
    """启发式贡献分账 —— 将终局奖励分配到每个 Episode step"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._fitness = FitnessService(db)

    async def assign_and_record(
        self,
        episode_id: str,
        domain: str = "general",
        task_id: Optional[str] = None,
    ) -> dict[str, float]:
        """计算分账并写入 fitness。返回 {actor: total_credit}。"""
        ep = await self._get_episode(episode_id)
        if not ep:
            return {}

        steps = await self._get_steps(episode_id)
        if not steps:
            return {}

        terminal = 1.0 if ep.outcome == "success" else 0.2
        actor_credits: dict[str, float] = {}

        for step in steps:
            credit = self._calc_step_credit(step, terminal)
            actor_credits[step.actor] = actor_credits.get(step.actor, 0.0) + credit

            # 写入 fitness step_cost（正收益时记 harvest，负时记 drain）
            if credit > 0:
                try:
                    await self._fitness.record_step_cost(
                        synapse_id=step.actor,
                        task_id=task_id or ep.task_id,
                        domain=domain,
                        episode_id=episode_id,
                        episode_step_id=step.id,
                        token_count=step.token_cost,
                        wall_time=step.wall_time,
                    )
                except Exception as e:
                    logger.warning(f"[CreditAssignment] fitness 写入失败: {e}")

        logger.debug(
            f"[CreditAssignment] episode={episode_id[:8]} "
            f"terminal={terminal:.1f} actors={list(actor_credits.keys())}"
        )
        return actor_credits

    def _calc_step_credit(self, step: EpisodeStep, terminal: float) -> float:
        """四规则计算单步 credit。"""
        # 规则 1: 直接执行者拿主 credit，其余拿 30%
        base = terminal if step.action_type in _DIRECT_EXEC_TYPES else terminal * 0.3

        # 规则 2: 复用 bonus
        base += step.reused_by_count * _REUSE_BONUS_PER_COUNT

        # 规则 3: token 效率奖励
        if 0 < step.token_cost < _LOW_TOKEN_THRESHOLD:
            base += _LOW_TOKEN_BONUS

        # 规则 4: 超时惩罚
        if step.wall_time > _OVERTIME_THRESHOLD_SEC:
            base -= _OVERTIME_PENALTY

        return max(base, 0.0)

    async def _get_episode(self, episode_id: str) -> Optional[Episode]:
        result = await self._db.execute(
            select(Episode).where(Episode.id == episode_id)
        )
        return result.scalar_one_or_none()

    async def _get_steps(self, episode_id: str) -> list[EpisodeStep]:
        result = await self._db.execute(
            select(EpisodeStep)
            .where(EpisodeStep.episode_id == episode_id)
            .order_by(EpisodeStep.step_index)
        )
        return list(result.scalars().all())
