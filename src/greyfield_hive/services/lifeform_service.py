"""Resident lifeform management and compatibility mapping."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.lifeform import Lifeform, LifeformKind, LifeformState


SOVEREIGN_KEY = "hive-sovereign"

DEFAULT_LIFEFORMS: tuple[dict, ...] = (
    {
        "key": SOVEREIGN_KEY,
        "kind": LifeformKind.Sovereign,
        "name": "虫群主宰",
        "display_name": "虫群主宰",
        "persona_summary": "系统唯一核心意志，负责接球、判断、委派与收束。",
        "lineage": "sovereign",
        "backing_synapse": "overmind",
    },
    {
        "key": "implementation-submind",
        "kind": LifeformKind.Submind,
        "name": "实施子主脑",
        "display_name": "实施子主脑",
        "persona_summary": "负责实现、修复、执行和验证。",
        "lineage": "implementation",
        "backing_synapse": "code-expert",
    },
    {
        "key": "research-submind",
        "kind": LifeformKind.Submind,
        "name": "研究子主脑",
        "display_name": "研究子主脑",
        "persona_summary": "负责搜索、整理、比较和归纳。",
        "lineage": "research",
        "backing_synapse": "research-analyst",
    },
    {
        "key": "market-submind",
        "kind": LifeformKind.Submind,
        "name": "市场子主脑",
        "display_name": "市场子主脑",
        "persona_summary": "负责市场、资金面和行情概览。",
        "lineage": "market",
        "backing_synapse": "finance-scout",
    },
    {
        "key": "evolution-submind",
        "kind": LifeformKind.Submind,
        "name": "演化子主脑",
        "display_name": "演化子主脑",
        "persona_summary": "负责复盘、演化和长期改进建议。",
        "lineage": "review",
        "backing_synapse": "evolution-master",
    },
)


class LifeformService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ensure_defaults(self) -> list[Lifeform]:
        keys = [item["key"] for item in DEFAULT_LIFEFORMS]
        result = await self.db.execute(select(Lifeform).where(Lifeform.key.in_(keys)))
        existing = {item.key: item for item in result.scalars().all()}
        created = False
        for row in DEFAULT_LIFEFORMS:
            if row["key"] in existing:
                continue
            self.db.add(
                Lifeform(
                    key=row["key"],
                    kind=row["kind"],
                    name=row["name"],
                    display_name=row["display_name"],
                    persona_summary=row["persona_summary"],
                    lineage=row["lineage"],
                    status=LifeformState.Active,
                    backing_synapse=row["backing_synapse"],
                )
            )
            created = True
        if created:
            await self.db.commit()
        return await self.list_all()

    async def list_all(self) -> list[Lifeform]:
        result = await self.db.execute(select(Lifeform).order_by(Lifeform.kind, Lifeform.created_at))
        return list(result.scalars().all())

    async def get_by_id(self, lifeform_id: Optional[str]) -> Optional[Lifeform]:
        if not lifeform_id:
            return None
        result = await self.db.execute(select(Lifeform).where(Lifeform.id == lifeform_id))
        return result.scalar_one_or_none()

    async def get_by_key(self, key: str) -> Optional[Lifeform]:
        result = await self.db.execute(select(Lifeform).where(Lifeform.key == key))
        return result.scalar_one_or_none()

    async def get_by_backing_synapse(self, synapse: Optional[str]) -> Optional[Lifeform]:
        if not synapse:
            return None
        result = await self.db.execute(select(Lifeform).where(Lifeform.backing_synapse == synapse))
        return result.scalar_one_or_none()

    async def get_sovereign(self) -> Optional[Lifeform]:
        return await self.get_by_key(SOVEREIGN_KEY)
