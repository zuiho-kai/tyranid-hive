"""停滞任务检测器 —— 定期扫描长期未流转的任务并发布 task.stalled 事件

策略：
  每隔 check_interval 秒扫描一次非终态任务。
  若某任务在 stall_seconds 时间内 updated_at 未变化，认定其停滞，
  发布 TOPIC_TASK_STALLED 事件由编排器介入。
"""

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select

from greyfield_hive.db import SessionLocal
from greyfield_hive.models.task import Task, TaskState, TERMINAL_STATES
from greyfield_hive.services.event_bus import get_event_bus, TOPIC_TASK_STALLED


class StallDetector:
    """后台 Worker —— 停滞任务检测"""

    def __init__(
        self,
        stall_seconds: int = 3600,    # 1 小时未流转视为停滞
        check_interval: int = 300,    # 每 5 分钟检查一次
    ) -> None:
        self.stall_seconds   = stall_seconds
        self.check_interval  = check_interval
        self._running        = False
        self.bus             = get_event_bus()
        # 已发出停滞告警的 task_id 集合（避免重复报警）
        self._alerted: set[str] = set()

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True
        logger.info(
            f"[StallDetector] 启动，停滞阈值={self.stall_seconds}s，"
            f"检测间隔={self.check_interval}s"
        )
        while self._running:
            try:
                await self._scan()
            except Exception as e:
                logger.warning(f"[StallDetector] 扫描异常: {e}")
            await asyncio.sleep(self.check_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("[StallDetector] 停止")

    async def _scan(self) -> None:
        """扫描所有非终态任务，对超时未流转的发出告警"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.stall_seconds)
        terminal = list(TERMINAL_STATES)

        async with SessionLocal() as db:
            result = await db.execute(
                select(Task).where(
                    Task.state.notin_(terminal),
                    Task.updated_at < cutoff,
                )
            )
            stalled_tasks = result.scalars().all()

        newly_stalled = [t for t in stalled_tasks if t.id not in self._alerted]
        if not newly_stalled:
            return

        logger.warning(f"[StallDetector] 检测到 {len(newly_stalled)} 个停滞任务")
        for task in newly_stalled:
            await self.bus.publish(
                topic=TOPIC_TASK_STALLED,
                trace_id=task.trace_id,
                event_type="task.stalled",
                producer="stall_detector",
                payload={
                    "task_id":     task.id,
                    "state":       task.state.value,
                    "updated_at":  task.updated_at.isoformat() if task.updated_at else None,
                    "stall_secs":  self.stall_seconds,
                },
            )
            self._alerted.add(task.id)
            logger.warning(
                f"[StallDetector] 任务停滞告警: {task.id} "
                f"state={task.state.value} 超时={self.stall_seconds}s"
            )

    def clear_alert(self, task_id: str) -> None:
        """任务流转后清除告警记录（由外部调用，避免永远不再告警）"""
        self._alerted.discard(task_id)
