"""Lessons Bank —— L3 经验库 CRUD + 检索策略

Tier 1-2：简单衰减公式（exp 时效 × 频次 × domain × tag 重叠）
Tier 3+：BM25 + embeddings 混合检索（接口相同，策略可插拔）
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.lesson import Lesson


# ── 检索策略接口 ──────────────────────────────────────────

class RetrievalStrategy:
    """可插拔的检索策略基类"""

    async def search(
        self,
        db: AsyncSession,
        task_domain: str,
        task_tags: list[str],
        query: str,
        top_k: int = 5,
    ) -> list[Lesson]:
        raise NotImplementedError


class DecayRetrievalStrategy(RetrievalStrategy):
    """Tier 1-2：纯衰减公式排序（无需向量库）

    score = exp(−0.1×days) × (1 + log(1+freq)) × domain_match × (1 + tag_overlap)

    关键设计：
    - (1 + log(...)) 确保 frequency=0 的新 Lesson 基础分不为零
    - domain_match 三级：精确命中(3.0) / 父域命中(2.0) / 无关(1.0)
    - tag_overlap 奖励关键词命中数量
    """

    def _score(
        self,
        lesson: Lesson,
        task_domain: str,
        task_tags: list[str],
    ) -> float:
        now = datetime.now(timezone.utc)
        lu  = lesson.last_used
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=timezone.utc)
        days = max(0, (now - lu).days)

        recency    = math.exp(-0.1 * days)
        freq_w     = 1 + math.log(1 + (lesson.frequency or 0))

        if lesson.domain == task_domain:
            domain_m = 3.0
        elif task_domain.startswith(lesson.domain + "/"):
            domain_m = 2.0
        else:
            domain_m = 1.0

        lesson_tags = set((lesson.tags or "").split(",")) - {""}
        tag_overlap = len(lesson_tags & set(task_tags))

        return recency * freq_w * domain_m * (1 + tag_overlap)

    async def search(
        self,
        db: AsyncSession,
        task_domain: str,
        task_tags: list[str],
        query: str,
        top_k: int = 5,
    ) -> list[Lesson]:
        # 先按 domain 粗筛（同域 + 父域），再内存打分排序
        result = await db.execute(select(Lesson).limit(200))
        lessons = list(result.scalars().all())

        scored = sorted(
            lessons,
            key=lambda l: self._score(l, task_domain, task_tags),
            reverse=True,
        )
        return scored[:top_k]


# ── Lessons Bank ──────────────────────────────────────────

class LessonsBank:
    """Lessons 库操作入口"""

    def __init__(self, db: AsyncSession, strategy: Optional[RetrievalStrategy] = None) -> None:
        self.db = db
        self.strategy: RetrievalStrategy = strategy or DecayRetrievalStrategy()

    # ── 写入 ──────────────────────────────────────────────

    async def add(
        self,
        domain: str,
        content: str,
        outcome: str = "unknown",
        tags: list[str] | None = None,
        task_id: str | None = None,
        playbook_id: str | None = None,
        meta: dict | None = None,
    ) -> Lesson:
        lesson = Lesson(
            domain=domain,
            content=content,
            outcome=outcome,
            tags=",".join(tags or []),
            task_id=task_id,
            playbook_id=playbook_id,
            meta=meta or {},
        )
        self.db.add(lesson)
        await self.db.commit()
        await self.db.refresh(lesson)
        logger.debug(f"[LessonsBank] 写入 {lesson.id[:8]} domain={domain} outcome={outcome}")
        return lesson

    # ── 检索 ──────────────────────────────────────────────

    async def search(
        self,
        task_domain: str,
        task_tags: list[str] | None = None,
        query: str = "",
        top_k: int = 5,
    ) -> list[Lesson]:
        results = await self.strategy.search(
            self.db,
            task_domain=task_domain,
            task_tags=task_tags or [],
            query=query,
            top_k=top_k,
        )
        # 更新 frequency 和 last_used
        for lesson in results:
            lesson.frequency = (lesson.frequency or 0) + 1
            lesson.last_used = datetime.now(timezone.utc)
        if results:
            await self.db.commit()
        return results

    # ── CRUD ─────────────────────────────────────────────

    async def get(self, lesson_id: str) -> Optional[Lesson]:
        result = await self.db.execute(select(Lesson).where(Lesson.id == lesson_id))
        return result.scalar_one_or_none()

    async def list_by_domain(self, domain: str, limit: int = 50) -> list[Lesson]:
        result = await self.db.execute(
            select(Lesson).where(Lesson.domain == domain).order_by(Lesson.last_used.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def delete_expired(self, days: int = 30) -> int:
        """删除超过 N 天未使用的 Lesson（自然衰减）"""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(select(Lesson).where(Lesson.last_used < cutoff))
        expired = result.scalars().all()
        for l in expired:
            await self.db.delete(l)
        await self.db.commit()
        logger.info(f"[LessonsBank] 清理过期 Lesson {len(expired)} 条（>{days}天未用）")
        return len(expired)

    async def promote_to_playbook(self, lesson_id: str, playbook_id: str) -> Optional[Lesson]:
        """将 Lesson 晋升关联到 Playbook（Evolution Master 调用）"""
        lesson = await self.get(lesson_id)
        if lesson:
            lesson.playbook_id = playbook_id
            await self.db.commit()
        return lesson
