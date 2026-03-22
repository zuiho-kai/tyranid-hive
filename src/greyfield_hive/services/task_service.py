"""任务服务 —— CRUD + 状态机 + 事件发布"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

# ── 进度日志并发写入锁 ────────────────────────────────────────────────
# SQLite 不支持行级锁，用 Python 层的 per-task asyncio.Lock 序列化并发写入
_progress_locks: dict[str, asyncio.Lock] = {}


def _progress_lock(task_id: str) -> asyncio.Lock:
    if task_id not in _progress_locks:
        _progress_locks[task_id] = asyncio.Lock()
    return _progress_locks[task_id]

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
    TOPIC_TASK_DELETED,
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
        labels: Optional[list] = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            priority=priority,
            creator=creator,
            assignee_synapse=assignee_synapse,
            meta=meta or {},
            labels=labels or [],
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

    # 优先级排序权重（数字越小排越前）
    _PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}

    async def list_tasks(
        self,
        state: Optional[TaskState] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        q: Optional[str] = None,
        label: Optional[str] = None,
        sort_by: str = "updated_at",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        from sqlalchemy import case, asc, desc as sa_desc

        # 构建排序列
        _order_fn = sa_desc if order == "desc" else asc
        if sort_by == "created_at":
            order_clause = _order_fn(Task.created_at)
        elif sort_by == "priority":
            # 用 CASE 表达式把 priority 字符串映射为数值再排序
            priority_case = case(
                (Task.priority == "critical", 0),
                (Task.priority == "high",     1),
                (Task.priority == "normal",   2),
                (Task.priority == "low",      3),
                else_=4,
            )
            order_clause = _order_fn(priority_case)
        elif sort_by == "state":
            order_clause = _order_fn(Task.state)
        else:  # default: updated_at
            order_clause = _order_fn(Task.updated_at)

        stmt = select(Task).order_by(order_clause).limit(limit).offset(offset)
        if state is not None:
            stmt = stmt.where(Task.state == state)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if assignee is not None:
            stmt = stmt.where(Task.assignee_synapse == assignee)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                Task.title.ilike(pattern)
                | Task.description.ilike(pattern)
                | Task.id.ilike(pattern)
            )
        if label:
            # JSON 数组序列化后包含 "label" 子串即命中（跨 SQLite/PG 兼容）
            from sqlalchemy import cast, Text
            stmt = stmt.where(cast(Task.labels, Text).contains(f'"{label}"'))
        result = await self.db.execute(stmt)
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
        # per-task asyncio.Lock 防止并发写入 progress_log 时 last-write-wins 丢数据
        async with _progress_lock(task_id):
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

    async def append_todo(self, task_id: str, title: str) -> Task:
        """追加单条 Todo（不替换已有清单）"""
        task = await self.get_by_id(task_id)
        todos = list(task.todos or [])
        todos.append({"id": str(uuid.uuid4()), "title": title, "done": False})
        task.todos = todos
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def toggle_todo(self, task_id: str, index: int) -> Task:
        """切换指定索引 Todo 的完成状态；索引越界抛 IndexError"""
        task = await self.get_by_id(task_id)
        todos = list(task.todos or [])
        if index < 0 or index >= len(todos):
            raise IndexError(f"Todo 索引越界: {index}，当前共 {len(todos)} 条")
        todos[index] = {**todos[index], "done": not todos[index].get("done", False)}
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

    async def patch_task(self, task_id: str, **fields) -> Task:
        """部分更新任务字段，只改传入的字段"""
        task = await self.get_by_id(task_id)   # raises TaskNotFoundError if missing
        allowed = {"title", "description", "priority"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(task, k, v)
        # labels 单独处理（允许传入空列表以清除所有标签）
        if "labels" in fields and fields["labels"] is not None:
            task.labels = list(fields["labels"])
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete_task(self, task_id: str) -> None:
        """硬删除单个任务；任务不存在时抛出 TaskNotFoundError"""
        task = await self.get_by_id(task_id)
        trace_id = task.trace_id
        title    = task.title
        await self.db.delete(task)
        await self.db.commit()
        await self.bus.publish(
            topic=TOPIC_TASK_DELETED,
            trace_id=trace_id,
            event_type="task.deleted",
            producer="task_service",
            payload={"task_id": task_id, "title": title},
        )
        logger.info(f"[TaskService] 删除任务 {task_id}: {title}")

    async def bulk_delete(self, task_ids: list[str]) -> dict:
        """批量硬删除；返回 {deleted: N, not_found: [...]}"""
        deleted = 0
        not_found: list[str] = []
        deleted_info: list[dict] = []
        for tid in task_ids:
            try:
                task = await self.get_by_id(tid)
                deleted_info.append({"task_id": tid, "trace_id": task.trace_id, "title": task.title})
                await self.db.delete(task)
                deleted += 1
            except TaskNotFoundError:
                not_found.append(tid)
        await self.db.commit()
        for info in deleted_info:
            await self.bus.publish(
                topic=TOPIC_TASK_DELETED,
                trace_id=info["trace_id"],
                event_type="task.deleted",
                producer="task_service",
                payload={"task_id": info["task_id"], "title": info["title"]},
            )
        return {"deleted": deleted, "not_found": not_found}

    async def delete_old_completed(self, days: int = 30) -> dict:
        """删除 days 天前已完成/已取消的任务；返回 {deleted: N}"""
        from datetime import timedelta
        from sqlalchemy import delete as sa_delete

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        terminal = [TaskState.Complete, TaskState.Cancelled]
        result = await self.db.execute(
            sa_delete(Task).where(
                Task.state.in_(terminal),
                Task.updated_at < cutoff,
            )
        )
        await self.db.commit()
        return {"deleted": result.rowcount}

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
