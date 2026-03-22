"""任务服务 —— CRUD + 状态机 + 事件发布"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from greyfield_hive.models.task import Task, TaskState, STATE_TRANSITIONS, TERMINAL_STATES
from greyfield_hive.models.event import HiveEvent
from greyfield_hive.services.event_bus import (
    get_event_bus,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_STALLED,
    TOPIC_TASK_DISPATCH,
)


class InvalidTransitionError(Exception):
    pass


class TaskNotFoundError(Exception):
    pass


class TaskService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.bus = get_event_bus()

    # ── 创建任务 ──────────────────────────────────────────

    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "normal",
        creator: str = "user",
        assignee_synapse: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            priority=priority,
            creator=creator,
            assignee_synapse=assignee_synapse,
            meta=meta or {},
        )
        task.append_flow(None, TaskState.Incubating.value, "system", "任务孵化")
        self.db.add(task)
        await self.db.flush()

        await self._persist_event(
            trace_id=task.trace_id,
            task_id=task.id,
            topic=TOPIC_TASK_CREATED,
            event_type="task.created",
            producer="task_service",
            payload={"task_id": task.id, "task_uuid": task.task_uuid, "title": title, "state": task.state.value},
        )
        await self.bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id=task.trace_id,
            event_type="task.created",
            producer="task_service",
            payload={"task_id": task.id, "task_uuid": task.task_uuid, "title": title},
        )
        await self.db.commit()
        await self.db.refresh(task)
        logger.info(f"[TaskService] 孵化任务 {task.id}: {title}")
        return task

    # ── 查询 ──────────────────────────────────────────────

    async def get_by_id(self, task_id: str) -> Task:
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def get_by_uuid(self, task_uuid: str) -> Task:
        result = await self.db.execute(select(Task).where(Task.task_uuid == task_uuid))
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(task_uuid)
        return task

    async def list_tasks(
        self,
        state: Optional[TaskState] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        q = select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
        if state is not None:
            q = q.where(Task.state == state)
        if priority is not None:
            q = q.where(Task.priority == priority)
        if assignee is not None:
            q = q.where(Task.assignee_synapse == assignee)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    # ── 状态流转 ──────────────────────────────────────────

    async def transition(
        self,
        task_id: str,
        new_state: TaskState,
        agent: str = "system",
        reason: str = "",
    ) -> Task:
        task = await self.get_by_id(task_id)
        old_state = task.state

        allowed = STATE_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"非法跳转: {old_state.value} → {new_state.value}（允许: {[s.value for s in allowed]}）"
            )

        task.state = new_state
        task.updated_at = datetime.now(timezone.utc)
        task.append_flow(old_state.value, new_state.value, agent, reason)

        topic = TOPIC_TASK_COMPLETED if new_state in TERMINAL_STATES else TOPIC_TASK_STATUS
        payload = {
            "task_id": task.id,
            "from": old_state.value,
            "to": new_state.value,
            "agent": agent,
            "assignee_synapse": task.assignee_synapse,
        }

        await self._persist_event(
            trace_id=task.trace_id,
            task_id=task.id,
            topic=topic,
            event_type=f"task.state.{new_state.value.lower()}",
            producer=agent,
            payload=payload,
        )
        await self.bus.publish(
            topic=topic,
            trace_id=task.trace_id,
            event_type=f"task.state.{new_state.value.lower()}",
            producer=agent,
            payload=payload,
        )
        await self.db.commit()
        await self.db.refresh(task)
        logger.info(f"[TaskService] {task.id}: {old_state.value} → {new_state.value} by {agent}")
        return task

    # ── 派发请求 ──────────────────────────────────────────

    async def request_dispatch(
        self,
        task_id: str,
        target_synapse: str,
        message: str = "",
    ) -> None:
        task = await self.get_by_id(task_id)
        task.assignee_synapse = target_synapse
        await self.db.commit()

        await self.bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=task.trace_id,
            event_type="task.dispatch.request",
            producer="task_service",
            payload={"task_id": task_id, "synapse": target_synapse, "message": message},
        )

    # ── 进度 / Todo ───────────────────────────────────────

    async def add_progress(self, task_id: str, agent: str, content: str) -> Task:
        task = await self.get_by_id(task_id)
        task.append_progress(agent, content)
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_todos(self, task_id: str, todos: list[dict]) -> Task:
        task = await self.get_by_id(task_id)
        task.todos = todos
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_exec_mode(self, task_id: str, exec_mode: str) -> Task:
        from greyfield_hive.models.task import ExecutionMode
        task = await self.get_by_id(task_id)
        task.exec_mode = ExecutionMode(exec_mode)
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def stats(self) -> dict:
        """返回各状态任务计数 + 汇总"""
        result = await self.db.execute(
            select(Task.state, func.count(Task.id)).group_by(Task.state)
        )
        by_state: dict[str, int] = {row[0].value: row[1] for row in result.all()}

        total = sum(by_state.values())
        terminal = {"Complete", "Cancelled"}
        active = sum(v for k, v in by_state.items() if k not in terminal)

        return {
            "total":    total,
            "active":   active,
            "complete": by_state.get("Complete", 0),
            "cancelled": by_state.get("Cancelled", 0),
            "by_state": by_state,
        }

    # ── 私有工具 ──────────────────────────────────────────

    async def _persist_event(
        self,
        trace_id: str,
        task_id: str,
        topic: str,
        event_type: str,
        producer: str,
        payload: dict,
    ) -> None:
        ev = HiveEvent(
            trace_id=trace_id,
            task_id=task_id,
            topic=topic,
            event_type=event_type,
            producer=producer,
            payload=payload,
        )
        self.db.add(ev)
