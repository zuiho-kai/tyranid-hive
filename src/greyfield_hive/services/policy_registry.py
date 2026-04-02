"""PolicyRegistry —— 策略实体的增删改查与生命周期管理

主要职责：
  - 灌入初始 seed 策略（启动时一次性）
  - 进化大师写入 candidate
  - mode_router 查询 active policy
  - 定时衰减/退役
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.policy import Policy, PolicyState


class PolicyRegistry:
    """策略注册表"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── 查询 ──────────────────────────────────────────────────────────────────

    async def get(self, policy_id: str) -> Optional[Policy]:
        result = await self._db.execute(
            select(Policy).where(Policy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Policy]:
        result = await self._db.execute(
            select(Policy).where(Policy.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_active(
        self,
        domain: str = "general",
        category: Optional[str] = None,
    ) -> list[Policy]:
        """返回对该域生效的 active 策略（包括 general 域的策略）"""
        q = select(Policy).where(
            Policy.state == PolicyState.Active,
            Policy.domain.in_([domain, "general"]),
        )
        if category:
            q = q.where(Policy.category == category)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def get_shadow(
        self,
        domain: str = "general",
        category: Optional[str] = None,
    ) -> list[Policy]:
        """返回 shadow 状态的策略（旁路预测用）"""
        q = select(Policy).where(
            Policy.state == PolicyState.Shadow,
            Policy.domain.in_([domain, "general"]),
        )
        if category:
            q = q.where(Policy.category == category)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def list_all(self, state: Optional[PolicyState] = None) -> list[Policy]:
        q = select(Policy)
        if state:
            q = q.where(Policy.state == state)
        result = await self._db.execute(q.order_by(Policy.created_at.desc()))
        return list(result.scalars().all())

    # ── 写入 ──────────────────────────────────────────────────────────────────

    async def create(
        self,
        slug: str,
        content: str,
        domain: str = "general",
        category: str = "mode_selection",
        rule_logic: Optional[dict] = None,
        source: str = "distilled",
        state: PolicyState = PolicyState.Candidate,
    ) -> Policy:
        """创建新策略（幂等：slug 已存在则跳过）"""
        existing = await self.get_by_slug(slug)
        if existing:
            logger.debug(f"[PolicyRegistry] 策略已存在，跳过: {slug}")
            return existing

        policy = Policy(
            id=str(uuid.uuid4()),
            slug=slug,
            domain=domain,
            category=category,
            state=state,
            content=content,
            rule_logic=rule_logic or {},
            source=source,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(policy)
        await self._db.flush()
        logger.info(f"[PolicyRegistry] 新建策略 [{state}] {slug}")
        return policy

    # ── 生命周期转换 ──────────────────────────────────────────────────────────

    async def promote_to_shadow(self, policy_id: str) -> Optional[Policy]:
        """candidate → shadow"""
        return await self._transition(policy_id, PolicyState.Candidate, PolicyState.Shadow)

    async def activate(self, policy_id: str) -> Optional[Policy]:
        """shadow → active"""
        p = await self._transition(policy_id, PolicyState.Shadow, PolicyState.Active)
        if p:
            p.activated_at = datetime.now(timezone.utc)
        return p

    async def decay(self, policy_id: str) -> Optional[Policy]:
        """active → decaying"""
        return await self._transition(policy_id, PolicyState.Active, PolicyState.Decaying)

    async def retire(self, policy_id: str) -> Optional[Policy]:
        """decaying → retired"""
        p = await self._transition(policy_id, PolicyState.Decaying, PolicyState.Retired)
        if p:
            p.retired_at = datetime.now(timezone.utc)
        return p

    async def record_hit(self, policy_id: str, success: bool) -> None:
        """记录一次命中"""
        p = await self.get(policy_id)
        if not p:
            return
        p.hit_count += 1
        if success:
            p.hit_success += 1
        else:
            p.hit_fail += 1
        p.last_hit_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def record_shadow_prediction(
        self, policy_id: str, correct: bool
    ) -> None:
        """记录一次 shadow 旁路预测结果"""
        p = await self.get(policy_id)
        if not p:
            return
        p.shadow_predictions += 1
        if correct:
            p.shadow_correct += 1
        await self._db.flush()

    # ── 批量维护 ──────────────────────────────────────────────────────────────

    async def auto_decay_stale(self, days_threshold: int = 14) -> int:
        """超过 N 天未命中的 active policy → decaying"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        result = await self._db.execute(
            select(Policy).where(
                Policy.state == PolicyState.Active,
                (Policy.last_hit_at < cutoff) | (Policy.last_hit_at.is_(None)),
            )
        )
        stale = result.scalars().all()
        for p in stale:
            p.state = PolicyState.Decaying
            logger.info(f"[PolicyRegistry] 衰减 {p.slug}（{days_threshold}天未命中）")
        await self._db.flush()
        return len(stale)

    async def auto_retire_decaying(self, days_threshold: int = 14) -> int:
        """持续 decaying 超过 N 天 → retired"""
        # 用 last_hit_at 作为衰减起点代理
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold * 2)
        result = await self._db.execute(
            select(Policy).where(
                Policy.state == PolicyState.Decaying,
                (Policy.last_hit_at < cutoff) | (Policy.last_hit_at.is_(None)),
            )
        )
        decaying = result.scalars().all()
        for p in decaying:
            p.state = PolicyState.Retired
            p.retired_at = datetime.now(timezone.utc)
            logger.info(f"[PolicyRegistry] 退役 {p.slug}")
        await self._db.flush()
        return len(decaying)

    # ── 内部 ─────────────────────────────────────────────────────────────────

    async def _transition(
        self,
        policy_id: str,
        from_state: PolicyState,
        to_state: PolicyState,
    ) -> Optional[Policy]:
        p = await self.get(policy_id)
        if not p:
            logger.warning(f"[PolicyRegistry] 找不到策略 {policy_id}")
            return None
        if p.state != from_state:
            logger.warning(
                f"[PolicyRegistry] 状态不匹配: {p.slug} "
                f"期望 {from_state} 实际 {p.state}"
            )
            return None
        p.state = to_state
        await self._db.flush()
        logger.info(f"[PolicyRegistry] {p.slug}: {from_state} → {to_state}")
        return p
