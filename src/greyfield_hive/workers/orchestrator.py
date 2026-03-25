"""编排器 Worker —— 消费事件总线，驱动状态机流转

职责：
- 监听 task.created / task.status / task.stalled / task.completed
- 根据当前状态决定下一步：自动路由 → 发布 task.dispatch
- 不直接执行任务，只做状态路由
"""

import asyncio
from loguru import logger

from greyfield_hive.services.event_bus import (
    get_event_bus,
    BusEvent,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_STALLED,
    TOPIC_TASK_DISPATCH,
    TOPIC_AGENT_HEARTBEAT,
)
from greyfield_hive.services.execution_events import publish_task_event
from greyfield_hive.models.task import TaskState, STATE_SYNAPSE_MAP

# 每个状态完成 dispatch 后应推进到的下一状态
_STATE_NEXT: dict[TaskState, TaskState] = {
    TaskState.Planning:      TaskState.Reviewing,
    TaskState.Reviewing:     TaskState.Spawning,
    TaskState.Consolidating: TaskState.Complete,
}
from greyfield_hive.db import SessionLocal
from greyfield_hive.services.task_service import TaskService, TaskNotFoundError


def _build_task_message(task, stage: str) -> str:
    title = (task.title or "").strip()
    description = (task.description or "").strip()
    if description and description != title:
        return f"Stage: {stage}\nTitle: {title}\nDescription: {description}"
    return f"Stage: {stage}\nTask: {description or title}"


def _fallback_message(title: str, stage: str) -> str:
    clean = (title or "").strip() or "Untitled task"
    return f"Stage: {stage}\nTask: {clean}"


class OrchestratorWorker:
    """编排器 —— 无状态事件路由机"""

    def __init__(self) -> None:
        self.bus = get_event_bus()
        self._running = False
        self._queues: list[asyncio.Queue] = []

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True
        logger.info("[Orchestrator] 启动")

        # 订阅需要处理的 Topic
        q_created   = self.bus.subscribe(TOPIC_TASK_CREATED)
        q_status    = self.bus.subscribe(TOPIC_TASK_STATUS)
        q_stalled   = self.bus.subscribe(TOPIC_TASK_STALLED)
        q_completed = self.bus.subscribe(TOPIC_TASK_COMPLETED)
        self._queues = [q_created, q_status, q_stalled, q_completed]

        topics = {
            id(q_created):   TOPIC_TASK_CREATED,
            id(q_status):    TOPIC_TASK_STATUS,
            id(q_stalled):   TOPIC_TASK_STALLED,
            id(q_completed): TOPIC_TASK_COMPLETED,
        }

        while self._running:
            # 轮询所有 Queue，非阻塞
            tasks_got: list[tuple[str, BusEvent]] = []
            for q in self._queues:
                try:
                    event = q.get_nowait()
                    tasks_got.append((topics[id(q)], event))
                except asyncio.QueueEmpty:
                    pass

            if not tasks_got:
                await asyncio.sleep(0.1)
                continue

            for topic, event in tasks_got:
                try:
                    await self._handle(topic, event)
                except Exception as e:
                    logger.error(f"[Orchestrator] 处理事件失败 {topic}/{event.event_type}: {e}")

    async def stop(self) -> None:
        self._running = False
        logger.info("[Orchestrator] 停止")

    # ── 事件分发 ──────────────────────────────────────────

    async def _handle(self, topic: str, event: BusEvent) -> None:
        if topic == TOPIC_TASK_CREATED:
            await self._on_task_created(event)
        elif topic == TOPIC_TASK_STATUS:
            await self._on_task_status(event)
        elif topic == TOPIC_TASK_STALLED:
            await self._on_task_stalled(event)
        elif topic == TOPIC_TASK_COMPLETED:
            await self._on_task_completed(event)

    async def _on_task_created(self, event: BusEvent) -> None:
        """新任务 → 路由到主脑（Incubating → Planning）"""
        task_id = event.payload.get("task_id")
        if not task_id:
            return

        task = None
        try:
            async with SessionLocal() as db:
                task = await TaskService(db).get_by_id(task_id)
                mode_source = (task.meta or {}).get("mode_source")
        except TaskNotFoundError:
            mode_source = None

        if mode_source == "user":
            logger.info(f"[Orchestrator] 新任务 {task_id} 已显式指定模式，跳过主脑")
            return

        logger.info(f"[Orchestrator] 新任务 {task_id} → 派发给主脑")
        await publish_task_event(
            self.bus,
            topic=TOPIC_TASK_DISPATCH,
            trace_id=event.trace_id,
            event_type="task.dispatch.request",
            producer="orchestrator",
            task_id=task_id,
            payload={
                "synapse": "overmind",
                "message": _build_task_message(task, "Incubating") if task else _fallback_message(event.payload.get("title", ""), "Incubating"),
                "next_state": TaskState.Planning.value,
            },
        )

    async def _on_task_status(self, event: BusEvent) -> None:
        """状态变更 → 决定是否继续路由"""
        new_state_str = event.payload.get("to")
        task_id       = event.payload.get("task_id")
        if not new_state_str or not task_id:
            return

        try:
            new_state = TaskState(new_state_str)
        except ValueError:
            logger.warning(f"[Orchestrator] 未知状态: {new_state_str}")
            return

        # 特定状态需要主动派发
        task = None
        try:
            async with SessionLocal() as db:
                task = await TaskService(db).get_by_id(task_id)
                mode_source = (task.meta or {}).get("mode_source")
        except TaskNotFoundError:
            mode_source = None

        if (
            mode_source == "user"
            and new_state in {TaskState.Planning, TaskState.Reviewing}
        ):
            logger.info(f"[Orchestrator] {task_id}: {new_state_str} 为显式模式流程，跳过主脑")
            return

        synapse = STATE_SYNAPSE_MAP.get(new_state)
        if synapse is None:
            # Spawning → ModeRouter 路由到对应执行路径
            if new_state == TaskState.Spawning:
                asyncio.create_task(self._handle_spawning(task_id, event.trace_id))
            return

        logger.info(f"[Orchestrator] {task_id}: {new_state_str} → 派发给 {synapse}")
        await publish_task_event(
            self.bus,
            topic=TOPIC_TASK_DISPATCH,
            trace_id=event.trace_id,
            event_type="task.dispatch.request",
            producer="orchestrator",
            task_id=task_id,
            payload={
                "synapse": synapse,
                "message": _build_task_message(task, new_state_str) if task else _fallback_message(task_id, new_state_str),
                "next_state": _STATE_NEXT.get(new_state, new_state).value,
            },
        )

    async def _handle_spawning(self, task_id: str, trace_id: str) -> None:
        """Spawning 状态：调用 ModeRouter 路由到对应执行路径"""
        try:
            from greyfield_hive.db import SessionLocal
            from greyfield_hive.services.mode_router import ModeRouter
            async with SessionLocal() as db:
                router = ModeRouter(db)
                await router.route(task_id, trace_id)
        except Exception as e:
            logger.error(f"[Orchestrator] ModeRouter 失败 {task_id}: {e}")

    async def _on_task_stalled(self, event: BusEvent) -> None:
        """阻塞 → 通知主脑介入"""
        task_id = event.payload.get("task_id")
        logger.warning(f"[Orchestrator] 任务阻塞: {task_id}，通知主脑")
        await publish_task_event(
            self.bus,
            topic=TOPIC_TASK_DISPATCH,
            trace_id=event.trace_id,
            event_type="task.dispatch.request",
            producer="orchestrator",
            task_id=task_id,
            payload={
                "synapse": "overmind",
                "message": "任务已阻塞，请主脑介入处理",
                "next_state": TaskState.Dormant.value,
            },
        )

    async def _on_task_completed(self, event: BusEvent) -> None:
        task_id = event.payload.get("task_id")
        logger.info(f"[Orchestrator] 战团 {task_id} 完成")
        # 解除依赖此任务的等待任务（若其所有依赖均已完成）
        if task_id:
            await self._unblock_waiting_tasks(task_id)

    async def _unblock_waiting_tasks(self, completed_task_id: str) -> None:
        """检查所有依赖 completed_task_id 的任务，若依赖全部完成则派发"""
        try:
            async with SessionLocal() as db:
                svc = TaskService(db)
                waiting = await svc.get_waiting_tasks(completed_task_id)

            for task in waiting:
                # 检查该任务是否仍有其他未完成依赖
                async with SessionLocal() as db:
                    svc = TaskService(db)
                    still_blocked = await svc.is_blocked(task.id)

                if not still_blocked:
                    logger.info(f"[Orchestrator] 任务 {task.id} 依赖解除，自动派发")
                    await publish_task_event(
                        self.bus,
                        topic=TOPIC_TASK_DISPATCH,
                        trace_id=task.trace_id,
                        event_type="task.dispatch.request",
                        producer="orchestrator",
                        task_id=task.id,
                        payload={
                            "synapse": task.assignee_synapse or "overmind",
                            "message": f"依赖任务 {completed_task_id} 已完成，解除阻塞",
                        },
                    )
        except Exception as e:
            logger.warning(f"[Orchestrator] 依赖解除检查失败: {e}")
