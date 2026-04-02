"""SkillRegistry —— 专化器官的注册与生命周期管理"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.skill import Skill, SkillState
from greyfield_hive.services.task_fingerprint import TaskFingerprint


class SkillRegistry:
    """管理蒸馏出的专化器官（Skill Appliance）"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        slug: str,
        domain: str,
        description: str,
        preferred_mode: str = "solo",
        preferred_synapse: str = "code-expert",
        playbook_slugs: Optional[list[str]] = None,
        match_criteria: Optional[dict] = None,
        avg_token_cost: int = 0,
        avg_wall_time: float = 0.0,
        success_rate: float = 0.0,
        source_episode_count: int = 0,
    ) -> Skill:
        """创建新器官（幂等：slug 已存在则跳过）"""
        existing = await self.get_by_slug(slug)
        if existing:
            return existing

        skill = Skill(
            id=str(uuid.uuid4()),
            slug=slug,
            domain=domain,
            description=description,
            preferred_mode=preferred_mode,
            preferred_synapse=preferred_synapse,
            playbook_slugs=playbook_slugs or [],
            match_criteria=match_criteria or {},
            avg_token_cost=avg_token_cost,
            avg_wall_time=avg_wall_time,
            success_rate=success_rate,
            source_episode_count=source_episode_count,
            source_domain=domain,
        )
        self._db.add(skill)
        await self._db.flush()
        logger.info(f"[SkillRegistry] 新建器官 [{skill.state}] {slug}")
        return skill

    async def get_by_slug(self, slug: str) -> Optional[Skill]:
        result = await self._db.execute(
            select(Skill).where(Skill.slug == slug)
        )
        return result.scalar_one_or_none()

    async def match_skill(self, fingerprint: TaskFingerprint) -> Optional[Skill]:
        """根据任务指纹匹配最佳 active 器官。

        匹配逻辑：domain 一致 + structural_tags 有交集 + 器官 active 状态。
        多个匹配时选成功率最高的。
        """
        result = await self._db.execute(
            select(Skill).where(
                Skill.state == SkillState.Active,
                Skill.domain == fingerprint.domain,
            )
        )
        candidates = result.scalars().all()
        if not candidates:
            return None

        best: Optional[Skill] = None
        best_score = -1.0
        for s in candidates:
            criteria = s.match_criteria or {}
            req_tags = set(criteria.get("structural_tags", []))
            fp_tags = set(fingerprint.structural_tags)
            if req_tags and not req_tags.intersection(fp_tags):
                continue
            score = s.success_rate * (1.0 + s.total_uses * 0.01)
            if score > best_score:
                best = s
                best_score = score
        return best

    async def record_use(self, skill_id: str, success: bool,
                         token_cost: int = 0, wall_time: float = 0.0) -> None:
        """记录一次器官使用，更新统计"""
        result = await self._db.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return

        s.total_uses += 1
        old_rate = s.success_rate
        # 移动平均更新成功率
        s.success_rate = (old_rate * (s.total_uses - 1) + (1.0 if success else 0.0)) / s.total_uses
        # 移动平均更新 token/wall_time
        if token_cost > 0:
            s.avg_token_cost = int((s.avg_token_cost * (s.total_uses - 1) + token_cost) / s.total_uses)
        if wall_time > 0:
            s.avg_wall_time = (s.avg_wall_time * (s.total_uses - 1) + wall_time) / s.total_uses
        s.last_used_at = datetime.now(timezone.utc)

        # 退化检测：成功率低于 60% → degrading
        if s.state == SkillState.Active and s.success_rate < 0.60 and s.total_uses >= 5:
            s.state = SkillState.Degrading
            logger.warning(f"[SkillRegistry] 器官退化: {s.slug} rate={s.success_rate:.0%}")

        await self._db.flush()

    async def activate(self, skill_id: str) -> Optional[Skill]:
        """incubating → active"""
        result = await self._db.execute(select(Skill).where(Skill.id == skill_id))
        s = result.scalar_one_or_none()
        if not s or s.state != SkillState.Incubating:
            return None
        s.state = SkillState.Active
        await self._db.flush()
        logger.info(f"[SkillRegistry] 器官激活: {s.slug}")
        return s

    async def retire_degrading(self, min_days: int = 14) -> int:
        """退役持续退化的器官"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_days)
        result = await self._db.execute(
            select(Skill).where(
                Skill.state == SkillState.Degrading,
                (Skill.last_used_at < cutoff) | (Skill.last_used_at.is_(None)),
            )
        )
        degrading = result.scalars().all()
        for s in degrading:
            s.state = SkillState.Retired
            s.retired_at = datetime.now(timezone.utc)
            logger.info(f"[SkillRegistry] 器官退役: {s.slug}")
        await self._db.flush()
        return len(degrading)

    async def list_active(self, domain: Optional[str] = None) -> list[Skill]:
        q = select(Skill).where(Skill.state == SkillState.Active)
        if domain:
            q = q.where(Skill.domain == domain)
        result = await self._db.execute(q)
        return list(result.scalars().all())
