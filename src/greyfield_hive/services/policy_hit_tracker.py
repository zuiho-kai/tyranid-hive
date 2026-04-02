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
        fingerprint: Optional[dict] = None,
        domain_fail_rate: float = 0.0,
    ) -> int:
        """批量追踪：对该域所有 active policy 检查是否命中。

        命中条件（同时满足）：
          1. policy.rule_logic.prefer_mode == chosen_mode
          2. trigger_conditions 全部满足（如果有定义）

        返回命中条数。
        """
        from greyfield_hive.services.task_fingerprint import TaskFingerprint
        fp_tags = set((fingerprint or {}).get("structural_tags", []))
        fp_complexity = (fingerprint or {}).get("complexity", "medium")

        policies = await self._registry.get_active(domain=domain, category="mode_selection")
        hit_count = 0
        for p in policies:
            rule = p.rule_logic or {}
            prefer_mode = rule.get("prefer_mode")
            if not prefer_mode or prefer_mode != chosen_mode:
                continue

            # 评估 trigger_conditions
            conditions = rule.get("trigger_conditions", [])
            if conditions and not self._eval_conditions(
                conditions, fp_tags, fp_complexity, domain_fail_rate
            ):
                continue

            await self.track_hit(p.id, episode_id, outcome)
            hit_count += 1
        return hit_count

    def _eval_conditions(
        self,
        conditions: list[str],
        fp_tags: set[str],
        complexity: str,
        domain_fail_rate: float,
    ) -> bool:
        """评估 trigger_conditions 是否满足（任意一条满足即计为命中）。"""
        cond_map = {
            "multiple_viable_paths":   "parallel" in fp_tags or "browser" in fp_tags,
            "objectively_comparable_results": True,  # 保守：默认满足
            "linear_dependency":       "linear-dep" in fp_tags,
            "sequential_required":     "linear-dep" in fp_tags,
            "fully_independent_subtasks": "parallel" in fp_tags,
            "single_file":             complexity == "low",
            "sequential_tool_chain":   complexity == "low",
            "daily_qa":                complexity == "low",
            "domain_fail_rate_gt_30_pct": domain_fail_rate > 0.30,
            "multiple_viable_paths":   True,   # 如果无法判断，保守为满足
        }
        # 如果无法识别 condition，保守返回 True（避免漏计）
        return any(cond_map.get(c, True) for c in conditions)

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
