"""SubmindRegistry —— Submind 注册表，管理三态生命周期"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.submind import Submind, SubmindState


class SubmindRegistry:
    """Submind 注册表 —— CRUD + 三态流转"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(
        self,
        name: str,
        gene_seed: str = "",
        domains: list[str] | None = None,
        display_name: str = "",
        predecessor_id: str | None = None,
    ) -> Submind:
        """注册新 Submind（或重孵：继承前身 50% 生物质）"""
        biomass = 0.0
        if predecessor_id:
            pred = await self.get(predecessor_id)
            if pred:
                biomass = (pred.biomass or 0.0) * 0.5
                logger.info(f"[Registry] {name} 继承前身 {predecessor_id} 生物质 {biomass:.2f}")

        sm = Submind(
            name=name,
            display_name=display_name or name,
            gene_seed=gene_seed,
            domains=domains or [],
            biomass=biomass,
            predecessor_id=predecessor_id,
        )
        self.db.add(sm)
        await self.db.flush()
        logger.info(f"[Registry] 注册 Submind: {sm.id} name={name} gene={gene_seed}")
        return sm

    async def get(self, submind_id: str) -> Optional[Submind]:
        result = await self.db.execute(
            select(Submind).where(Submind.id == submind_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Submind]:
        result = await self.db.execute(
            select(Submind).where(Submind.name == name)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Submind]:
        result = await self.db.execute(
            select(Submind).where(Submind.state == SubmindState.Active)
        )
        return list(result.scalars().all())

    async def find_by_domain(self, domain: str) -> list[Submind]:
        """查找覆盖指定域的活跃 Submind"""
        active = await self.list_active()
        return [sm for sm in active if domain in (sm.domains or [])]

    async def enter_dormant(self, submind_id: str) -> Submind:
        sm = await self.get(submind_id)
        if sm is None:
            raise ValueError(f"Submind {submind_id} 不存在")
        sm.enter_dormant()
        await self.db.flush()
        logger.info(f"[Registry] {submind_id} → 休眠，生物质快照={sm.biomass_at_dormant}")
        return sm

    async def wake_up(self, submind_id: str) -> Submind:
        sm = await self.get(submind_id)
        if sm is None:
            raise ValueError(f"Submind {submind_id} 不存在")
        sm.wake_up()
        await self.db.flush()
        logger.info(f"[Registry] {submind_id} → 唤醒")
        return sm

    async def update_biomass(self, submind_id: str, delta: float) -> Submind:
        """更新生物质净值"""
        sm = await self.get(submind_id)
        if sm is None:
            raise ValueError(f"Submind {submind_id} 不存在")
        sm.biomass = (sm.biomass or 0.0) + delta
        await self.db.flush()
        return sm
