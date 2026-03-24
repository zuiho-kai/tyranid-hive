"""ModeRouter —— 根据 exec_mode 路由到对应执行路径

Solo   → 直接派发给 assignee_synapse（或 code-expert）
Trial  → 调用 TrialRaceService 双路赛马
Chain  → 调用 ChainRunnerService 串行链
Swarm  → 调用 SwarmRunnerService 并发 Unit 池
"""

from __future__ import annotations

from loguru import logger

from greyfield_hive.models.task import ExecutionMode, TaskState
from greyfield_hive.services.event_bus import get_event_bus, TOPIC_TASK_DISPATCH
from greyfield_hive.services.execution_events import publish_stage_event


class ModeRouter:
    """执行模式路由器 —— 根据 task.exec_mode 选择执行路径"""

    def __init__(self, db) -> None:
        self._db = db
        self._bus = get_event_bus()

    async def route(self, task_id: str, trace_id: str = "") -> None:
        """读取 task.exec_mode，路由到对应执行路径"""
        from greyfield_hive.services.task_service import TaskService
        svc = TaskService(self._db)
        task = await svc.get_by_id(task_id)

        mode = task.exec_mode or ExecutionMode.Solo
        message = task.description or task.title
        meta = task.meta or {}
        success_state = self._success_state(meta)
        logger.info(f"[ModeRouter] {task_id} exec_mode={mode.value if hasattr(mode, 'value') else mode}")
        if task.state == TaskState.Spawning:
            task = await svc.transition(task_id, TaskState.Executing, agent="mode-router", reason="进入执行态")
            trace_id = task.trace_id
        await publish_stage_event(
            self._bus,
            trace_id=trace_id,
            producer="mode-router",
            event_type="task.execution.started",
            task_id=task_id,
            stage="execution",
            payload={"mode": mode.value if hasattr(mode, "value") else str(mode)},
        )

        if mode == ExecutionMode.Trial:
            success = await self._route_trial(task_id, message, meta, trace_id)
        elif mode == ExecutionMode.Chain:
            success = await self._route_chain(task_id, message, meta, trace_id)
        elif mode == ExecutionMode.Swarm:
            success = await self._route_swarm(task_id, message, meta, trace_id)
        else:
            await self._route_solo(task, trace_id, success_state)
            return

        task = await svc.transition(
            task_id,
            success_state if success else TaskState.Dormant,
            agent="mode-router",
            reason="执行完成" if success else "执行失败",
        )
        await publish_stage_event(
            self._bus,
            trace_id=task.trace_id,
            producer="mode-router",
            event_type="task.execution.completed" if success else "task.execution.failed",
            task_id=task_id,
            stage="execution",
            payload={"mode": mode.value if hasattr(mode, "value") else str(mode), "success": success},
        )

    async def _route_solo(self, task, trace_id: str, success_state: TaskState) -> None:
        """Solo: 派发给 assignee_synapse 或默认 code-expert，执行后推进到 Executing"""
        synapse = task.assignee_synapse or "code-expert"
        await self._bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=trace_id,
            event_type="task.dispatch.request",
            producer="mode-router",
            payload={
                "task_id": task.id,
                "synapse": synapse,
                "message": task.description or task.title,
                "domain": "general",
                "next_state": success_state.value,
            },
        )
        logger.info(f"[ModeRouter] Solo → {synapse} → next={TaskState.Consolidating.value}")

    @staticmethod
    def _success_state(meta: dict) -> TaskState:
        if meta.get("skip_consolidation"):
            return TaskState.Complete
        return TaskState.Consolidating

    async def _route_trial(self, task_id: str, message: str,
                           meta: dict, trace_id: str) -> bool:
        """Trial: 双路赛马"""
        from greyfield_hive.services.trial_race import TrialRaceService
        candidates = meta.get("trial_candidates", ["code-expert", "research-analyst"])
        synapse_a = candidates[0] if candidates else "code-expert"
        synapse_b = candidates[1] if len(candidates) > 1 else "research-analyst"
        logger.info(f"[ModeRouter] Trial → {synapse_a} vs {synapse_b}")
        svc = TrialRaceService(self._db)
        result = await svc.run(task_id=task_id, synapse_a=synapse_a,
                               synapse_b=synapse_b, message=message, trace_id=trace_id)
        return result.winner is not None

    async def _route_chain(self, task_id: str, message: str,
                           meta: dict, trace_id: str) -> bool:
        """Chain: 串行链"""
        from greyfield_hive.services.chain_runner import ChainRunnerService
        stages = meta.get("chain_stages", ["code-expert"])
        logger.info(f"[ModeRouter] Chain → {stages}")
        svc = ChainRunnerService(self._db)
        result = await svc.run(task_id=task_id, synapses=stages,
                               message=message, trace_id=trace_id)
        return result.success

    async def _route_swarm(self, task_id: str, message: str,
                           meta: dict, trace_id: str) -> bool:
        """Swarm: 并发 Unit 池"""
        from greyfield_hive.services.swarm_runner import SwarmRunnerService, SwarmUnit
        units_meta = meta.get("swarm_units") or [{"synapse": "code-expert", "message": message}]
        units = [
            SwarmUnit(synapse=u.get("synapse", "code-expert"),
                      message=u.get("message", message),
                      domain=u.get("domain", "general"))
            for u in units_meta if isinstance(u, dict)
        ]
        logger.info(f"[ModeRouter] Swarm → {len(units)} units")
        svc = SwarmRunnerService(self._db)
        result = await svc.run(task_id=task_id, units=units, trace_id=trace_id)
        return result.all_success
