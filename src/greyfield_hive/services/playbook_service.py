"""Playbook 服务 —— L2 战术手册 CRUD + 版本管理

版本规则：
- 同一 slug 可以有多个版本（v1, v2, v3…）
- create_new_version() 自动将旧版本 is_active=False，新版本 is_active=True
- rollback_version() 可将指定版本重新激活
- search() 返回按 use_count × success_rate 综合排序的 Top-K 激活版本
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.playbook import Playbook


class PlaybookNotFoundError(Exception):
    pass


class PlaybookService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 创建 ──────────────────────────────────────────────

    async def create(
        self,
        slug: str,
        domain: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source_lessons: list[str] | None = None,
        notes: str = "",
    ) -> Playbook:
        """创建 Playbook v1（若 slug 已存在则拒绝，用 create_new_version）"""
        existing = await self._get_active(slug)
        if existing:
            raise ValueError(f"slug={slug} 已存在（v{existing.version}），请用 create_new_version()")

        pb = Playbook(
            slug=slug,
            version=1,
            is_active=True,
            domain=domain,
            title=title,
            content=content,
            tags=",".join(tags or []),
            source_lessons=source_lessons or [],
            notes=notes,
        )
        self.db.add(pb)
        await self.db.commit()
        await self.db.refresh(pb)
        logger.info(f"[Playbook] 创建 {slug} v1 domain={domain}")
        return pb

    async def create_new_version(
        self,
        slug: str,
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
        source_lessons: list[str] | None = None,
        notes: str = "",
    ) -> Playbook:
        """基于已有 slug 创建新版本，旧版本自动归档（is_active=False）"""
        old = await self._get_active(slug)
        if old is None:
            raise PlaybookNotFoundError(f"slug={slug} 不存在")

        # 归档旧版本
        old.is_active = False
        old.updated_at = datetime.now(timezone.utc)

        # 新版本继承域和标签（除非显式覆盖）
        new_pb = Playbook(
            slug=slug,
            version=old.version + 1,
            is_active=True,
            domain=old.domain,
            title=title or old.title,
            content=content,
            tags=",".join(tags) if tags is not None else old.tags,
            source_lessons=source_lessons or [],
            notes=notes,
            # 继承历史使用统计（可选）
            use_count=0,
            success_rate=0.0,
        )
        self.db.add(new_pb)
        await self.db.commit()
        await self.db.refresh(new_pb)
        logger.info(f"[Playbook] 升版 {slug} v{old.version}→v{new_pb.version}")
        return new_pb

    # ── 查询 ──────────────────────────────────────────────

    async def get_by_id(self, pb_id: str) -> Playbook:
        result = await self.db.execute(select(Playbook).where(Playbook.id == pb_id))
        pb = result.scalar_one_or_none()
        if pb is None:
            raise PlaybookNotFoundError(pb_id)
        return pb

    async def get_active(self, slug: str) -> Playbook:
        pb = await self._get_active(slug)
        if pb is None:
            raise PlaybookNotFoundError(slug)
        return pb

    async def list_active(self, domain: str | None = None, limit: int = 50) -> list[Playbook]:
        q = select(Playbook).where(Playbook.is_active == True).order_by(Playbook.updated_at.desc()).limit(limit)
        if domain:
            q = q.where(Playbook.domain == domain)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def list_versions(self, slug: str) -> list[Playbook]:
        result = await self.db.execute(
            select(Playbook).where(Playbook.slug == slug).order_by(Playbook.version.desc())
        )
        return list(result.scalars().all())

    # ── 检索（Skill Router 使用）─────────────────────────

    async def search(
        self,
        domain: str,
        task_tags: list[str] | None = None,
        top_k: int = 5,
    ) -> list[Playbook]:
        """按 domain + tag 匹配，综合 use_count × success_rate 排序"""
        q = select(Playbook).where(Playbook.is_active == True, Playbook.domain == domain).limit(200)
        result = await self.db.execute(q)
        candidates = list(result.scalars().all())

        task_tags_set = set(task_tags or [])

        def _score(pb: Playbook) -> float:
            pb_tags = set((pb.tags or "").split(",")) - {""}
            overlap = len(pb_tags & task_tags_set)
            quality = (1 + pb.use_count) * max(pb.success_rate, 0.01)
            return quality * (1 + overlap)

        return sorted(candidates, key=_score, reverse=True)[:top_k]

    # ── 版本回滚 ──────────────────────────────────────────

    async def rollback(self, slug: str, target_version: int) -> Playbook:
        """将 slug 的指定版本重新激活（当前激活版本归档）"""
        # 归档当前激活版本
        current = await self._get_active(slug)
        if current:
            current.is_active = False
            current.updated_at = datetime.now(timezone.utc)

        # 激活目标版本
        result = await self.db.execute(
            select(Playbook).where(Playbook.slug == slug, Playbook.version == target_version)
        )
        target = result.scalar_one_or_none()
        if target is None:
            raise PlaybookNotFoundError(f"{slug} v{target_version}")
        target.is_active = True
        target.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(target)
        logger.info(f"[Playbook] 回滚 {slug} → v{target_version}")
        return target

    # ── 统计更新（Evolution Master 调用）────────────────

    async def record_usage(self, pb_id: str, success: bool) -> Playbook:
        """记录一次使用，更新 use_count 和 success_rate（指数移动平均）"""
        pb = await self.get_by_id(pb_id)
        pb.use_count = (pb.use_count or 0) + 1
        alpha = 0.1  # EMA 平滑系数
        pb.success_rate = (1 - alpha) * (pb.success_rate or 0.0) + alpha * (1.0 if success else 0.0)
        pb.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(pb)
        return pb

    async def mark_crystallized(self, pb_id: str) -> Playbook:
        """标记为专化生物形态（已结晶）"""
        pb = await self.get_by_id(pb_id)
        pb.crystallized = True
        pb.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(pb)
        logger.info(f"[Playbook] {pb.slug} v{pb.version} 已结晶为专化形态")
        return pb

    # ── 私有 ─────────────────────────────────────────────

    async def _get_active(self, slug: str) -> Playbook | None:
        result = await self.db.execute(
            select(Playbook).where(Playbook.slug == slug, Playbook.is_active == True)
        )
        return result.scalar_one_or_none()
