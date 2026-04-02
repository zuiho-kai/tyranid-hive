"""PolicyHitTracker —— 策略命中追踪与自动衰减

每次执行路径确定后，追踪哪些 active policy 被命中、结果如何。
定时任务调用 decay_stale() 自动降级长期未命中的策略。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.policy import PolicyState
from greyfield_hive.services.policy_registry import PolicyRegistry


class PolicyHitTracker:
    """策略命中追踪器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._registry = PolicyRegistry(db)

    async def track_hit(
        self,
        policy_id: str,
        episode_id: str,
        outcome: str,
    ) -> None:
        """记录一次策略命中。

        outcome: "success" / "failure" / "partial"
        """
        success = outcome == "success"
        await self._registry.record_hit(policy_id, success=success)
        logger.debug(
            f"[PolicyHitTracker] hit policy={policy_id} "
            f"episode={episode_id[:8]} success={success}"
        )

    async def track_hits_for_episode(
        self,
        domain: str,
        episode_id: str,
        chosen_mode: str,
        outcome: str,
    ) -> int:
        """批量追踪：对该域所有 active policy 检查是否命中。

        "命中"定义：policy 的 rule_logic.prefer_mode 与 chosen_mode 一致。
        返回命中条数。
        """
        policies = await self._registry.get_active(domain=domain, category="mode_selection")
        hit_count = 0
        for p in policies:
            rule = p.rule_logic or {}
            prefer_mode = rule.get("prefer_mode")
            if prefer_mode and prefer_mode == chosen_mode:
                await self.track_hit(p.id, episode_id, outcome)
                hit_count += 1
        return hit_count

    async def decay_stale(self, days_threshold: int = 14) -> int:
        """自动衰减超过 N 天未命中的 active policy。"""
        n = await self._registry.auto_decay_stale(days_threshold)
        if n:
            logger.info(f"[PolicyHitTracker] 衰减 {n} 条策略")
        return n

    async def retire_decaying(self, days_threshold: int = 14) -> int:
        """自动退役持续衰减超过 N 天的策略。"""
        n = await self._registry.auto_retire_decaying(days_threshold)
        if n:
            logger.info(f"[PolicyHitTracker] 退役 {n} 条策略")
        return n
