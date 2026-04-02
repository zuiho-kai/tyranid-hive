"""ShadowEvaluator —— 候选策略的旁路评估

Shadow 策略不影响真实决策，但旁路预测"如果我的建议被采纳，结果会怎样"。
当预测准确率 >= 70% 且预测次数 >= 10，自动激活为 active。
超过 30 天仍未达标，自动退役。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.policy import Policy, PolicyState
from greyfield_hive.services.policy_registry import PolicyRegistry

# 激活阈值
SHADOW_MIN_PREDICTIONS = 10
SHADOW_MIN_ACCURACY    = 0.70
SHADOW_MAX_DAYS        = 30   # 超过此天数仍未达标 → 退役


class ShadowEvaluator:
    """旁路评估器 —— 管理 shadow policy 的预测与激活"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._registry = PolicyRegistry(db)

    async def record_prediction(
        self,
        policy_id: str,
        episode_id: str,
        predicted_mode: str,
        actual_mode: str,
        actual_outcome: str,
    ) -> None:
        """记录一次旁路预测。

        预测正确定义：shadow 建议的模式与实际模式相同，且任务成功。
        或：shadow 建议与实际一致（不管结果），用于模式推荐准确率。
        这里采用"模式一致"作为正确标准，与结果无关。
        """
        correct = predicted_mode == actual_mode
        await self._registry.record_shadow_prediction(policy_id, correct=correct)
        logger.debug(
            f"[ShadowEvaluator] policy={policy_id[:8]} "
            f"predicted={predicted_mode} actual={actual_mode} correct={correct}"
        )

    async def promote_if_ready(self, policy_id: str) -> bool:
        """检查并激活达标的 shadow policy。返回是否激活。"""
        p = await self._registry.get(policy_id)
        if not p or p.state != PolicyState.Shadow:
            return False

        # 检查达标条件
        if (p.shadow_predictions >= SHADOW_MIN_PREDICTIONS
                and p.shadow_accuracy >= SHADOW_MIN_ACCURACY):
            await self._registry.activate(policy_id)
            logger.info(
                f"[ShadowEvaluator] 激活 {p.slug} "
                f"（准确率={p.shadow_accuracy:.0%} 预测={p.shadow_predictions}次）"
            )
            return True
        return False

    async def expire_stale_shadows(self) -> int:
        """退役超过 SHADOW_MAX_DAYS 仍未激活的 shadow policy。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=SHADOW_MAX_DAYS)
        result = await self._db.execute(
            select(Policy).where(
                Policy.state == PolicyState.Shadow,
                Policy.created_at < cutoff,
            )
        )
        stale = result.scalars().all()
        for p in stale:
            p.state = PolicyState.Retired
            p.retired_at = datetime.now(timezone.utc)
            logger.info(
                f"[ShadowEvaluator] 退役过期 shadow: {p.slug} "
                f"（准确率={p.shadow_accuracy:.0%}，未达 {SHADOW_MIN_ACCURACY:.0%}）"
            )
        await self._db.flush()
        return len(stale)

    async def evaluate_all_shadows(self, domain: str = "general") -> dict[str, bool]:
        """批量检查该域所有 shadow policy 是否可激活。"""
        shadows = await self._registry.get_shadow(domain=domain)
        results: dict[str, bool] = {}
        for p in shadows:
            promoted = await self.promote_if_ready(p.id)
            results[p.slug] = promoted
        return results
