"""WorldModel —— 极简版结构化世界状态

Phase 3 最小版本，只存 4 个字段：
  goal_tree       — 当前任务的目标树
  confirmed_facts — 已确认事实
  open_questions  — 未决问题
  resources       — 预算/资源状态

每个 task 一份 WorldModel（存 task.meta 或独立表）。
Agent 不必读完整上下文，只需读自己的任务切片 + 世界模型摘要。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.task import Task


@dataclass
class WorldState:
    """结构化世界状态（存入 task.meta["world_model"]）"""
    goal_tree:       list[dict]  = field(default_factory=list)
    confirmed_facts: list[str]   = field(default_factory=list)
    open_questions:  list[str]   = field(default_factory=list)
    resources:       dict        = field(default_factory=lambda: {
        "budget_tokens": 50000,
        "budget_time_sec": 300,
    })

    def to_dict(self) -> dict:
        return {
            "goal_tree":       self.goal_tree,
            "confirmed_facts": self.confirmed_facts,
            "open_questions":  self.open_questions,
            "resources":       self.resources,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorldState":
        return cls(
            goal_tree=d.get("goal_tree", []),
            confirmed_facts=d.get("confirmed_facts", []),
            open_questions=d.get("open_questions", []),
            resources=d.get("resources", {"budget_tokens": 50000, "budget_time_sec": 300}),
        )

    def summary(self, max_lines: int = 10) -> str:
        """生成可注入 prompt 的世界状态摘要"""
        lines = []
        if self.goal_tree:
            lines.append("目标：")
            for g in self.goal_tree[:3]:
                lines.append(f"  - {g.get('name', str(g))}")
        if self.confirmed_facts:
            lines.append("已确认：")
            for f in self.confirmed_facts[:3]:
                lines.append(f"  - {f}")
        if self.open_questions:
            lines.append("待决：")
            for q in self.open_questions[:2]:
                lines.append(f"  - {q}")
        if self.resources:
            budget = self.resources.get("budget_tokens", "?")
            lines.append(f"预算：{budget} tokens")
        return "\n".join(lines[:max_lines])


class WorldModelService:
    """WorldModel 存取服务 —— 存储于 task.meta["world_model"]"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, task_id: str) -> WorldState:
        """获取任务的世界模型（不存在则返回默认值）"""
        result = await self._db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return WorldState()
        meta = task.meta or {}
        wm_data = meta.get("world_model")
        if wm_data:
            return WorldState.from_dict(wm_data)
        return WorldState()

    async def save(self, task_id: str, state: WorldState) -> None:
        """保存世界模型到 task.meta"""
        result = await self._db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return
        meta = dict(task.meta or {})
        meta["world_model"] = state.to_dict()
        task.meta = meta
        await self._db.flush()

    async def add_fact(self, task_id: str, fact: str) -> None:
        """追加一条已确认事实"""
        ws = await self.get(task_id)
        if fact not in ws.confirmed_facts:
            ws.confirmed_facts.append(fact)
            await self.save(task_id, ws)

    async def add_question(self, task_id: str, question: str) -> None:
        """追加一条未决问题"""
        ws = await self.get(task_id)
        if question not in ws.open_questions:
            ws.open_questions.append(question)
            await self.save(task_id, ws)

    async def resolve_question(self, task_id: str, question: str,
                                fact: Optional[str] = None) -> None:
        """解决一个问题，可选转为已确认事实"""
        ws = await self.get(task_id)
        ws.open_questions = [q for q in ws.open_questions if q != question]
        if fact:
            ws.confirmed_facts.append(fact)
        await self.save(task_id, ws)

    async def consume_tokens(self, task_id: str, count: int) -> None:
        """扣减 token 预算"""
        ws = await self.get(task_id)
        current = ws.resources.get("budget_tokens", 0)
        ws.resources["budget_tokens"] = max(current - count, 0)
        await self.save(task_id, ws)
