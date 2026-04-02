"""EpisodeStore —— 任务执行行为链的持久化存储

主要接口：
  begin_episode()   — 任务开始时创建 Episode
  record_step()     — 记录一个执行步骤
  finish_episode()  — 任务完成时关闭 Episode，汇总统计
  query_by_domain() — 按域查询近期 Episode（供 evolution_master 使用）
  get_mode_success_rate() — 查某域某模式成功率（供 mode_router 使用）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.episode import Episode, EpisodeStep
from greyfield_hive.services.task_fingerprint import TaskFingerprint


class EpisodeStore:
    """Episode 持久化存储服务"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── 写入接口 ──────────────────────────────────────────────────────────────

    async def begin_episode(
        self,
        task_id: str,
        fingerprint: TaskFingerprint,
        chosen_mode: str,
        justification: str = "",
    ) -> Episode:
        """任务开始时创建 Episode 记录。"""
        ep = Episode(
            id=str(uuid.uuid4()),
            task_id=task_id,
            fingerprint=fingerprint.to_dict(),
            chosen_mode=chosen_mode,
            mode_justification=justification,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(ep)
        await self._db.flush()
        logger.debug(f"[EpisodeStore] begin episode={ep.id} task={task_id} mode={chosen_mode}")
        return ep

    async def record_step(
        self,
        episode_id: str,
        *,
        actor: str,
        action_type: str,
        token_cost: int = 0,
        wall_time: float = 0.0,
        outcome: str = "success",
        error_class: Optional[str] = None,
        genes_used: Optional[list[str]] = None,
        artifacts: Optional[dict] = None,
    ) -> EpisodeStep:
        """记录 Episode 内的一个执行步骤。"""
        # 获取当前 step 序号
        count_result = await self._db.execute(
            select(func.count()).where(EpisodeStep.episode_id == episode_id)
        )
        step_index = count_result.scalar() or 0

        step = EpisodeStep(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            step_index=step_index,
            actor=actor,
            action_type=action_type,
            token_cost=token_cost,
            wall_time=wall_time,
            outcome=outcome,
            error_class=error_class,
            genes_used=genes_used or [],
            artifacts=artifacts or {},
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(step)
        await self._db.flush()
        logger.debug(
            f"[EpisodeStore] step[{step_index}] episode={episode_id} "
            f"actor={actor} outcome={outcome}"
        )
        return step

    async def finish_episode(
        self,
        episode_id: str,
        outcome: str,
        human_corrections: int = 0,
    ) -> Optional[Episode]:
        """关闭 Episode，汇总 token 和 wall_time 统计。"""
        result = await self._db.execute(
            select(Episode).where(Episode.id == episode_id)
        )
        ep = result.scalar_one_or_none()
        if ep is None:
            logger.warning(f"[EpisodeStore] finish_episode: episode {episode_id} 不存在")
            return None

        # 汇总子步骤统计
        steps_result = await self._db.execute(
            select(EpisodeStep).where(EpisodeStep.episode_id == episode_id)
        )
        steps = steps_result.scalars().all()
        ep.total_token_cost = sum(s.token_cost for s in steps)
        ep.total_wall_time  = sum(s.wall_time  for s in steps)
        ep.outcome          = outcome
        ep.human_corrections = human_corrections
        ep.finished_at      = datetime.now(timezone.utc)

        await self._db.flush()
        logger.info(
            f"[EpisodeStore] finish episode={episode_id} outcome={outcome} "
            f"tokens={ep.total_token_cost} steps={len(steps)}"
        )
        return ep

    # ── 查询接口 ──────────────────────────────────────────────────────────────

    async def query_by_domain(
        self,
        domain: str,
        days: int = 30,
        limit: int = 50,
    ) -> list[Episode]:
        """按域查询近期 Episode（供 evolution_master 使用）。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._db.execute(
            select(Episode)
            .where(
                Episode.created_at >= cutoff,
                Episode.fingerprint["domain"].as_string() == domain,
            )
            .order_by(Episode.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_mode_success_rate(
        self,
        domain: str,
        mode: str,
        days: int = 30,
    ) -> float:
        """查某域某模式近 N 天成功率（供 mode_router 辅助参考）。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._db.execute(
            select(Episode).where(
                Episode.created_at >= cutoff,
                Episode.chosen_mode == mode,
                Episode.fingerprint["domain"].as_string() == domain,
                Episode.finished_at.isnot(None),
            )
        )
        episodes = result.scalars().all()
        if not episodes:
            return 0.0
        success = sum(1 for e in episodes if e.outcome == "success")
        return round(success / len(episodes), 3)

    async def query_all(
        self,
        days: int = 60,
        limit: int = 500,
    ) -> list[Episode]:
        """查询全部域的近期 Episode（供 OrganCrystallizer 全域扫描）。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._db.execute(
            select(Episode)
            .where(
                Episode.created_at >= cutoff,
                Episode.finished_at.isnot(None),
            )
            .order_by(Episode.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def query_by_task(self, task_id: str) -> list[Episode]:
        """查询某任务的所有 Episode（供门禁连续失败检测）。"""
        result = await self._db.execute(
            select(Episode)
            .where(Episode.task_id == task_id)
            .order_by(Episode.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_domain_mode_stats(
        self,
        domain: str,
        days: int = 30,
    ) -> dict[str, dict]:
        """获取某域各模式的统计摘要（供 mode_router 决策用）。

        返回格式：{mode: {"success_rate": float, "sample_count": int, "days": int}}
        """
        modes = ["solo", "trial", "chain", "swarm"]
        stats: dict[str, dict] = {}
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for mode in modes:
            try:
                result = await self._db.execute(
                    select(Episode).where(
                        Episode.created_at >= cutoff,
                        Episode.chosen_mode == mode,
                        Episode.fingerprint["domain"].as_string() == domain,
                        Episode.finished_at.isnot(None),
                    )
                )
                episodes = result.scalars().all()
                if not episodes:
                    continue
                success = sum(1 for e in episodes if e.outcome == "success")
                stats[mode] = {
                    "success_rate": round(success / len(episodes), 3),
                    "sample_count": len(episodes),
                    "days": days,
                }
            except Exception:
                pass
        return stats
